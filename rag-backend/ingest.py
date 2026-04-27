import argparse
import hashlib
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromadb
from tqdm import tqdm

from embeddings import GTEOnnxEmbeddings


ProgressCallback = Callable[[Dict[str, Any]], None]


def get_env_int(name: str, default: int, minimum: Optional[int] = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        print(f"⚠️ 环境变量 {name}={raw_value!r} 不是整数，使用默认值 {default}。")
        return default
    if minimum is not None and value < minimum:
        print(f"⚠️ 环境变量 {name}={value} 小于 {minimum}，使用 {minimum}。")
        return minimum
    return value


def get_optional_env_int(name: str) -> Optional[int]:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return None
    try:
        return int(raw_value)
    except ValueError:
        print(f"⚠️ 环境变量 {name}={raw_value!r} 不是整数，已忽略。")
        return None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "healthcaremagic/HealthCareMagic-100k-en.jsonl")
PERSIST_DIR = os.path.join(BASE_DIR, "vector_store/vector_store_healthcare_st")
EMBED_MODEL_PATH = os.path.join(BASE_DIR, "gte-large-en-v1.5")
ONNX_MODEL_FILE = os.getenv("ONNX_MODEL_FILE", "onnx/model.onnx")
ONNX_PROVIDER = os.getenv("ONNX_PROVIDER", "auto").strip().lower()
COLLECTION_NAME = "healthcare_qa_gte"
MAX_DOCUMENTS = get_env_int("MAX_DOCUMENTS", 0, minimum=0)
SAMPLED_DATA_OUTPUT_FILE = os.path.join(BASE_DIR, "healthcaremagicR/sampled_healthcare_2000qa.json")
BATCH_SIZE = get_env_int("INGEST_BATCH_SIZE", 32, minimum=1)
TOKENIZE_MAX_LENGTH = get_env_int("TOKENIZE_MAX_LENGTH", 512, minimum=1)
_ENV_SAMPLE_SEED = get_optional_env_int("SAMPLE_SEED")
SAMPLE_SEED = 42 if _ENV_SAMPLE_SEED is None else _ENV_SAMPLE_SEED
ORT_INTRA_OP_THREADS = get_env_int("ORT_INTRA_OP_THREADS", 0, minimum=0)
ORT_INTER_OP_THREADS = get_env_int("ORT_INTER_OP_THREADS", 0, minimum=0)


@dataclass
class IngestConfig:
    input_path: str = INPUT_FILE
    persist_directory: str = PERSIST_DIR
    model_path: str = EMBED_MODEL_PATH
    collection_name: str = COLLECTION_NAME
    max_documents: int = MAX_DOCUMENTS
    batch_size: int = BATCH_SIZE
    sample_seed: Optional[int] = SAMPLE_SEED
    rebuild: bool = False
    sampled_output_file: str = SAMPLED_DATA_OUTPUT_FILE
    onnx_model_file: str = ONNX_MODEL_FILE
    onnx_provider: str = ONNX_PROVIDER
    tokenize_max_length: int = TOKENIZE_MAX_LENGTH
    ort_intra_op_threads: int = ORT_INTRA_OP_THREADS
    ort_inter_op_threads: int = ORT_INTER_OP_THREADS


@dataclass
class IngestStats:
    input_path: str
    persist_directory: str
    collection_name: str
    mode: str
    parsed: int = 0
    json_errors: int = 0
    total: int = 0
    processed: int = 0
    added: int = 0
    skipped: int = 0
    collection_count: int = 0
    elapsed_seconds: float = 0.0


def batch_iterator(data: List[Any], batch_size: int):
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]


def parse_dialogue_line(dialogue_text: str) -> Dict[str, str]:
    try:
        human_start_tag = "<human>: "
        bot_start_tag = "\n<bot>: "
        human_start_index = dialogue_text.find(human_start_tag)
        bot_start_index = dialogue_text.find(bot_start_tag, human_start_index + len(human_start_tag))
        if human_start_index == -1 or bot_start_index == -1:
            return {}
        question_start = human_start_index + len(human_start_tag)
        question = dialogue_text[question_start:bot_start_index].strip()
        answer_start = bot_start_index + len(bot_start_tag)
        answer = dialogue_text[answer_start:].strip()
        return {"question": question, "answer": answer}
    except Exception as exc:
        print(f"解析行时出错: {dialogue_text[:100]}... | 错误: {exc}")
        return {}


def build_document(qa_pair: Dict[str, str], input_path: str) -> Dict[str, Any]:
    page_content = f"Question: {qa_pair['question']}\nAnswer: {qa_pair['answer']}"
    doc_hash = hashlib.sha256(page_content.encode("utf-8")).hexdigest()
    metadata = {
        "source": input_path,
        "original_question": qa_pair["question"],
        "doc_hash": doc_hash,
    }
    return {"id": f"doc_{doc_hash}", "page_content": page_content, "metadata": metadata}


def parse_healthcare_documents(
    input_path: str,
    max_documents: int,
    sample_seed: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    documents: List[Dict[str, Any]] = []
    parsed_count = 0
    json_error_count = 0
    sample_limit: Optional[int] = max_documents if max_documents > 0 else None
    rng = random.Random(sample_seed) if sample_seed is not None else random.Random()

    with open(input_path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="解析对话中", unit="line"):
            if not line or line.isspace():
                continue
            try:
                data_obj = json.loads(line)
            except json.JSONDecodeError:
                json_error_count += 1
                continue

            dialogue_text = data_obj.get("text")
            if not dialogue_text:
                continue

            qa_pair = parse_dialogue_line(dialogue_text)
            if not qa_pair:
                continue

            parsed_count += 1
            document = build_document(qa_pair, input_path)
            if sample_limit is None:
                documents.append(document)
                continue

            if len(documents) < sample_limit:
                documents.append(document)
                continue

            replace_index = rng.randint(0, parsed_count - 1)
            if replace_index < sample_limit:
                documents[replace_index] = document

    return documents, parsed_count, json_error_count


def save_sampled_documents(documents: List[Dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)


def get_collection(client: chromadb.PersistentClient, collection_name: str, rebuild: bool):
    if rebuild:
        try:
            client.delete_collection(name=collection_name)
            print(f"🧹 已删除旧集合 '{collection_name}'，准备重新写入。")
        except Exception:
            pass
        return client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
    return client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})


def get_existing_ids(collection, ids: List[str]) -> set:
    if not ids:
        return set()
    result = collection.get(ids=ids)
    return set(result.get("ids", []))


def emit_progress(callback: Optional[ProgressCallback], stats: IngestStats, phase: str) -> None:
    if callback is None:
        return
    payload = asdict(stats)
    payload["phase"] = phase
    callback(payload)


def ingest_healthcare_data(
    config: Optional[IngestConfig] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> IngestStats:
    config = config or IngestConfig()
    started_at = time.monotonic()
    stats = IngestStats(
        input_path=config.input_path,
        persist_directory=config.persist_directory,
        collection_name=config.collection_name,
        mode="rebuild" if config.rebuild else "incremental",
    )

    print(f"🚀 开始处理Healthcaremagic数据集: {config.input_path}")
    if not os.path.exists(config.input_path):
        raise FileNotFoundError(f"输入文件未找到: {config.input_path}")

    emit_progress(progress_callback, stats, "parsing")
    print("📜 正在解析数据...")
    if config.max_documents > 0:
        print(f"🔎 当前为抽样模式，最多保留 {config.max_documents} 个文档。")
    else:
        print("🔎 当前为全量模式，将保留全部可解析文档。")
    documents, parsed_count, json_error_count = parse_healthcare_documents(
        config.input_path,
        config.max_documents,
        config.sample_seed,
    )
    stats.parsed = parsed_count
    stats.json_errors = json_error_count
    stats.total = len(documents)
    emit_progress(progress_callback, stats, "parsed")
    print(f"✅ 数据解析完成！总共解析了 {parsed_count} 个问答对，准备写入 {len(documents)} 个文档。")
    if json_error_count:
        print(f"⚠️ 跳过 {json_error_count} 行无法解析的JSON。")

    if config.max_documents > 0 and parsed_count > config.max_documents:
        print(f"✅ 已通过流式抽样保留 {len(documents)} 个文档。")
        print(f"💾 正在将抽样后的数据保存到 '{config.sampled_output_file}'...")
        save_sampled_documents(documents, config.sampled_output_file)
        print("✅ 抽样数据已成功保存。")
    elif not documents:
        print("❌ 没有可写入的文档，流程结束。")
        return stats

    embeddings = GTEOnnxEmbeddings(
        model_path=config.model_path,
        onnx_model_file=config.onnx_model_file,
        batch_size=config.batch_size,
        max_length=config.tokenize_max_length,
        provider=config.onnx_provider,
        intra_op_threads=config.ort_intra_op_threads,
        inter_op_threads=config.ort_inter_op_threads,
    )

    print(f"💾 正在创建或加载向量数据库于 '{config.persist_directory}'...")
    os.makedirs(config.persist_directory, exist_ok=True)
    db_client = chromadb.PersistentClient(path=config.persist_directory)
    collection = get_collection(db_client, config.collection_name, config.rebuild)

    print("✍️ 开始分批生成嵌入并存入数据库...")
    total_batches = math.ceil(len(documents) / config.batch_size)
    for batch in tqdm(
        batch_iterator(documents, config.batch_size),
        total=total_batches,
        desc="嵌入并存储中",
        unit="batch",
    ):
        batch_ids = [doc["id"] for doc in batch]
        existing_ids = get_existing_ids(collection, batch_ids)
        new_docs = [doc for doc in batch if doc["id"] not in existing_ids]
        stats.skipped += len(batch) - len(new_docs)

        if new_docs:
            batch_texts = [doc["page_content"] for doc in new_docs]
            batch_embeddings = embeddings.embed_batch(batch_texts).tolist()
            collection.add(
                ids=[doc["id"] for doc in new_docs],
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=[doc["metadata"] for doc in new_docs],
            )
            stats.added += len(new_docs)

        stats.processed += len(batch)
        stats.collection_count = collection.count()
        stats.elapsed_seconds = round(time.monotonic() - started_at, 3)
        emit_progress(progress_callback, stats, "embedding")

    stats.collection_count = collection.count()
    stats.elapsed_seconds = round(time.monotonic() - started_at, 3)
    emit_progress(progress_callback, stats, "completed")
    print("✅ 数据嵌入和存储流程完成！")
    print(
        f"解析: {stats.parsed}，JSON错误: {stats.json_errors}，"
        f"新增: {stats.added}，跳过重复: {stats.skipped}，"
        f"集合向量数: {stats.collection_count}，耗时: {stats.elapsed_seconds}s"
    )
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HealthcareMagic 数据嵌入到 Chroma 向量库")
    parser.add_argument("--input-file", default=INPUT_FILE)
    parser.add_argument("--persist-dir", default=PERSIST_DIR)
    parser.add_argument("--model-path", default=EMBED_MODEL_PATH)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--max-documents", type=int, default=MAX_DOCUMENTS)
    parser.add_argument("--sample-seed", type=int, default=SAMPLE_SEED)
    parser.add_argument("--sampled-output-file", default=SAMPLED_DATA_OUTPUT_FILE)
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> IngestConfig:
    return IngestConfig(
        input_path=args.input_file,
        persist_directory=args.persist_dir,
        model_path=args.model_path,
        collection_name=args.collection,
        batch_size=max(1, args.batch_size),
        max_documents=args.max_documents,
        sample_seed=args.sample_seed,
        sampled_output_file=args.sampled_output_file,
        rebuild=args.rebuild,
    )


if __name__ == "__main__":
    ingest_healthcare_data(config_from_args(parse_args()))
