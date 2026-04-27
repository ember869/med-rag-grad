import os
import ctypes
import glob
import site
import threading
from typing import List, Optional

import numpy as np
from langchain_core.embeddings import Embeddings
from transformers import BertTokenizerFast


def preload_nvidia_libraries() -> None:
    if os.name != "posix":
        return

    candidate_roots = []
    for site_dir in site.getsitepackages():
        candidate_roots.append(os.path.join(site_dir, "nvidia"))
    user_site = site.getusersitepackages()
    if user_site:
        candidate_roots.append(os.path.join(user_site, "nvidia"))

    lib_dirs = []
    for root in candidate_roots:
        lib_dirs.extend(glob.glob(os.path.join(root, "*", "lib")))
    if not lib_dirs:
        return

    existing_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = ":".join(lib_dirs + ([existing_ld_path] if existing_ld_path else []))

    preferred_libraries = [
        "libcudart.so*",
        "libcublas.so*",
        "libcublasLt.so*",
        "libcurand.so*",
        "libcufft.so*",
        "libcudnn*.so*",
        "*.so*",
    ]
    for pattern in preferred_libraries:
        for lib_dir in lib_dirs:
            for library_path in glob.glob(os.path.join(lib_dir, pattern)):
                try:
                    ctypes.CDLL(library_path, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


preload_nvidia_libraries()

import onnxruntime as ort


def get_onnx_providers(provider: str = "auto") -> List[str]:
    provider = provider.strip().lower()
    available_providers = ort.get_available_providers()
    if provider in {"cpu", "cpuexecutionprovider"}:
        return ["CPUExecutionProvider"]
    if provider in {"cuda", "gpu", "cudaexecutionprovider"}:
        if "CUDAExecutionProvider" in available_providers:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        print("⚠️ CUDAExecutionProvider 不可用，回退到 CPUExecutionProvider。")
        return ["CPUExecutionProvider"]
    if provider in {"tensorrt", "tensorrtexecutionprovider"}:
        if "TensorrtExecutionProvider" in available_providers:
            return ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
        print("⚠️ TensorrtExecutionProvider 不可用，回退到自动选择。")
    if "CUDAExecutionProvider" in available_providers:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def build_onnx_session(
    model_path: str,
    onnx_model_file: str = "onnx/model.onnx",
    provider: str = "auto",
    intra_op_threads: int = 0,
    inter_op_threads: int = 0,
) -> ort.InferenceSession:
    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if intra_op_threads > 0:
        session_options.intra_op_num_threads = intra_op_threads
    if inter_op_threads > 0:
        session_options.inter_op_num_threads = inter_op_threads

    onnx_model_path = os.path.join(model_path, onnx_model_file)
    return ort.InferenceSession(
        onnx_model_path,
        sess_options=session_options,
        providers=get_onnx_providers(provider),
    )


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    embeddings = embeddings.astype(np.float32, copy=False)
    norms = np.linalg.norm(embeddings, ord=2, axis=1, keepdims=True)
    np.maximum(norms, np.finfo(np.float32).eps, out=norms)
    return embeddings / norms


class GTEOnnxEmbeddings(Embeddings):
    def __init__(
        self,
        model_path: str,
        onnx_model_file: str = "onnx/model.onnx",
        batch_size: int = 32,
        max_length: int = 512,
        provider: str = "auto",
        intra_op_threads: int = 0,
        inter_op_threads: int = 0,
    ):
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")
        print(f"🧠 正在从本地路径 '{model_path}' 加载Tokenizer和GTE ONNX Embedding Model...")
        self.tokenizer = BertTokenizerFast.from_pretrained(model_path, local_files_only=True)
        self.model_path = model_path
        self.onnx_model_file = onnx_model_file
        self.provider = provider
        self.intra_op_threads = intra_op_threads
        self.inter_op_threads = inter_op_threads
        self._session_lock = threading.RLock()
        self._retired_gpu_sessions = []
        self.session = build_onnx_session(
            model_path=model_path,
            onnx_model_file=onnx_model_file,
            provider=provider,
            intra_op_threads=intra_op_threads,
            inter_op_threads=inter_op_threads,
        )
        self.input_names = [input_meta.name for input_meta in self.session.get_inputs()]
        self.batch_size = batch_size
        self.max_length = max_length
        print(f"✅ GTE ONNX嵌入模型加载成功，Execution Providers: {self.session.get_providers()}")

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        batch_dict = self.tokenizer(
            texts,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="np",
        )
        ort_inputs = {
            input_name: batch_dict[input_name]
            for input_name in self.input_names
            if input_name in batch_dict
        }
        try:
            with self._session_lock:
                outputs = self.session.run(None, ort_inputs)
        except Exception as exc:
            if not self._should_retry_on_cpu(exc):
                raise
            print(f"⚠️ ONNX CUDA 推理失败，正在切换到 CPUExecutionProvider 后重试。错误: {exc}")
            self._switch_to_cpu_provider()
            with self._session_lock:
                outputs = self.session.run(None, ort_inputs)
        return normalize_embeddings(outputs[0][:, 0])

    def _should_retry_on_cpu(self, exc: Exception) -> bool:
        active_providers = self.session.get_providers()
        if "CUDAExecutionProvider" not in active_providers and "TensorrtExecutionProvider" not in active_providers:
            return False

        message = str(exc).lower()
        return (
            "cuda" in message
            or "cudnn" in message
            or "cublas" in message
            or "tensorrt" in message
            or "cudaexecutionprovider" in message
        )

    def _switch_to_cpu_provider(self) -> None:
        with self._session_lock:
            if self.session.get_providers() == ["CPUExecutionProvider"]:
                return
            old_session = self.session
            cpu_session = build_onnx_session(
                model_path=self.model_path,
                onnx_model_file=self.onnx_model_file,
                provider="cpu",
                intra_op_threads=self.intra_op_threads,
                inter_op_threads=self.inter_op_threads,
            )
            self._retired_gpu_sessions.append(old_session)
            self.session = cpu_session
            self.input_names = [input_meta.name for input_meta in self.session.get_inputs()]
            self.provider = "cpu"
            print(f"✅ GTE ONNX嵌入模型已切换到 Execution Providers: {self.session.get_providers()}")

    def _embed(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        effective_batch_size = max(1, batch_size or self.batch_size)
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), effective_batch_size):
            batch_texts = texts[i:i + effective_batch_size]
            all_embeddings.extend(self.embed_batch(batch_texts).tolist())
        return all_embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text])[0]
