import os
import json
import random
import re
import threading
import time
import resource
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# --- API 服务 ---
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- LangChain 相关 ---
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
import chromadb

from embeddings import GTEOnnxEmbeddings
from ingest import IngestConfig, ingest_healthcare_data

try:
    import psutil
except ImportError:
    psutil = None

# === 全局配置 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 定义向量数据库和查询文件的路径
PERSIST_DIR = os.path.join(BASE_DIR, 'vector_store/vector_store_healthcare_st')
QUERIES_FILE = os.path.join(BASE_DIR, 'healthcaremagicR/generated_queries300.json')
INPUT_FILE = os.path.join(BASE_DIR, 'healthcaremagic/HealthCareMagic-100k-en.jsonl')

# 定义嵌入模型路径
EMBED_MODEL_PATH = os.path.join(BASE_DIR, 'gte-large-en-v1.5')
ONNX_MODEL_FILE = os.getenv("ONNX_MODEL_FILE", "onnx/model.onnx")
ONNX_PROVIDER = os.getenv("ONNX_PROVIDER", "cpu")
COLLECTION_NAME = "healthcare_qa_gte"
retrieval_top_k = 3

# --- OpenAI API 配置 ---
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# 与模型加载相关的配置
BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "32"))
TOKENIZE_MAX_LENGTH = int(os.getenv("TOKENIZE_MAX_LENGTH", "512"))
MAX_DOCUMENTS = int(os.getenv("MAX_DOCUMENTS", "0"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))


# === 初始化组件 ===
# 1. 加载嵌入模型
embeddings = GTEOnnxEmbeddings(
    model_path=EMBED_MODEL_PATH,
    onnx_model_file=ONNX_MODEL_FILE,
    batch_size=BATCH_SIZE,
    max_length=TOKENIZE_MAX_LENGTH,
    provider=ONNX_PROVIDER,
)

# 2. 加载向量数据库
retriever_lock = threading.Lock()


def create_vector_db() -> Chroma:
    print(f"💾 正在从 '{PERSIST_DIR}' 加载向量数据库...")
    return Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


vectordb = create_vector_db()

# 将检索器配置为返回Top-K文档
retriever = vectordb.as_retriever(search_kwargs={"k": retrieval_top_k})
print("✅ 向量数据库加载成功。")

process_monitor = psutil.Process(os.getpid()) if psutil else None
if process_monitor:
    process_monitor.cpu_percent(interval=None)

monitoring_lock = threading.Lock()
monitoring_state: Dict[str, Any] = {
    "request_count": 0,
    "total_response_time_ms": 0.0,
    "average_response_time_ms": 0.0,
    "last_response_time_ms": 0.0,
    "last_retrieval_time_ms": 0.0,
    "last_generation_time_ms": 0.0,
    "last_updated_at": None,
}


def refresh_retriever() -> None:
    global vectordb, retriever
    with retriever_lock:
        vectordb = create_vector_db()
        retriever = vectordb.as_retriever(search_kwargs={"k": retrieval_top_k})
    print("✅ 检索器已刷新。")


def update_top_k(new_k: int) -> None:
    """Update retrieval Top-K and rebuild retriever (without reloading vector DB)."""
    global retrieval_top_k, retriever
    with retriever_lock:
        retrieval_top_k = new_k
        retriever = vectordb.as_retriever(search_kwargs={"k": new_k})


# 3. 语言模型会在 API Key 可用后初始化
llm_lock = threading.Lock()
current_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
llm: Optional[ChatOpenAI] = None
rag_chain: Optional[Runnable] = None
translate_query_chain: Optional[Runnable] = None


# --- 提示模板 ---
template_basic = """<|im_start|>system
You are a helpful medical assistant. Please answer the question based on the provided context.
If the context does not contain relevant information to answer the question, please say so.
Do not make up information that is not present in the context.
Answer in the same language as the user's question.<|im_end|>
<|im_start|>user
Context:
{context}

Question: {question}<|im_end|>
<|im_start|>assistant
"""
prompt_basic = PromptTemplate.from_template(template_basic)

template_translate_query = """<|im_start|>system
Translate the user's medical question into concise English for vector database retrieval.
If the question is already English, return it unchanged.
Return only the translated query, without explanations or extra formatting.<|im_end|>
<|im_start|>user
Question: {question}<|im_end|>
<|im_start|>assistant
"""
prompt_translate_query = PromptTemplate.from_template(template_translate_query)


# === 辅助函数 ===
def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join([doc.page_content for doc in docs])


def contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


# === RAG 链 ===
def create_llm(api_key: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.7,
        base_url=OPENAI_API_BASE,
        api_key=api_key,
    )


def create_rag_chain(model: ChatOpenAI) -> Runnable:
    """创建 RAG 链"""
    return prompt_basic | model | StrOutputParser()


def create_translate_query_chain(model: ChatOpenAI) -> Runnable:
    return prompt_translate_query | model | StrOutputParser()


def is_api_key_configured() -> bool:
    return bool(current_api_key and llm and rag_chain and translate_query_chain)


def configure_llm(api_key: str) -> None:
    global current_api_key, llm, rag_chain, translate_query_chain
    model = create_llm(api_key)
    model.invoke("ping")

    with llm_lock:
        current_api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
        llm = model
        rag_chain = create_rag_chain(model)
        translate_query_chain = create_translate_query_chain(model)


def get_rag_chain() -> Runnable:
    with llm_lock:
        chain = rag_chain
    if chain is None:
        raise HTTPException(status_code=401, detail="请先输入 API Key")
    return chain


def get_translate_query_chain() -> Runnable:
    with llm_lock:
        chain = translate_query_chain
    if chain is None:
        raise HTTPException(status_code=401, detail="请先输入 API Key")
    return chain


if current_api_key:
    try:
        configure_llm(current_api_key)
        print("✅ 语言模型加载成功。")
    except Exception as exc:
        print(f"⚠️ 语言模型初始化失败，请重新输入 API Key：{exc}")
else:
    print("⚠️ 未配置 OPENAI_API_KEY，等待前端输入。")


def translate_query_for_retrieval(question: str) -> str:
    if not contains_chinese(question):
        return question

    translated_question = get_translate_query_chain().invoke({"question": question}).strip()
    return translated_question or question


class AskRequest(BaseModel):
    query: str


class ApiKeyRequest(BaseModel):
    api_key: str


class ApiKeyStatusResponse(BaseModel):
    configured: bool


class ApiKeyUpdateResponse(BaseModel):
    configured: bool
    message: str


class AskMetrics(BaseModel):
    retrieval_time_ms: float
    generation_time_ms: float
    response_time_ms: float
    average_response_time_ms: float


class AskResponse(BaseModel):
    answer: str
    sources: List[str]
    metrics: Optional[AskMetrics] = None


class ResourceUsage(BaseModel):
    cpu_percent: Optional[float] = None
    memory_rss_mb: float
    memory_percent: Optional[float] = None
    system_memory_percent: Optional[float] = None
    load_average_1m: Optional[float] = None


class MonitoringResponse(BaseModel):
    request_count: int
    average_response_time_ms: float
    last_response_time_ms: float
    last_retrieval_time_ms: float
    last_generation_time_ms: float
    last_updated_at: Optional[str] = None
    resources: ResourceUsage


class SamplePromptsResponse(BaseModel):
    prompts: List[str]


class IngestStartRequest(BaseModel):
    rebuild: bool = False


class IngestStartResponse(BaseModel):
    status: str
    message: str


class IngestStatusResponse(BaseModel):
    status: str
    running: bool
    mode: Optional[str] = None
    phase: Optional[str] = None
    processed: int = 0
    total: int = 0
    added: int = 0
    skipped: int = 0
    collection_count: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class KnowledgeBaseParametersResponse(BaseModel):
    collection_name: str
    collection_count: int
    retrieval_top_k: int
    max_documents: int
    batch_size: int
    tokenize_max_length: int
    embedding_model: str
    onnx_model_file: str
    onnx_provider: str
    llm_model: str
    api_base: str
    api_key_configured: bool


class TopKUpdateRequest(BaseModel):
    top_k: int


app = FastAPI(title="RAG Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ingest_state_lock = threading.Lock()
ingest_state: Dict[str, Any] = {
    "status": "idle",
    "running": False,
    "mode": None,
    "phase": None,
    "processed": 0,
    "total": 0,
    "added": 0,
    "skipped": 0,
    "collection_count": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_ms(start_time: float) -> float:
    return round((time.perf_counter() - start_time) * 1000, 2)


def snapshot_resource_usage() -> ResourceUsage:
    if process_monitor:
        memory = process_monitor.memory_info()
        virtual_memory = psutil.virtual_memory()
        load_average = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
        return ResourceUsage(
            cpu_percent=round(process_monitor.cpu_percent(interval=None), 2),
            memory_rss_mb=round(memory.rss / (1024 * 1024), 2),
            memory_percent=round(process_monitor.memory_percent(), 2),
            system_memory_percent=round(virtual_memory.percent, 2),
            load_average_1m=round(load_average, 2) if load_average is not None else None,
        )

    max_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    load_average = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    return ResourceUsage(
        memory_rss_mb=round(max_rss_kb / 1024, 2),
        load_average_1m=round(load_average, 2) if load_average is not None else None,
    )


def record_request_metrics(
    response_time_ms: float,
    retrieval_time_ms: float,
    generation_time_ms: float,
) -> AskMetrics:
    with monitoring_lock:
        monitoring_state["request_count"] += 1
        monitoring_state["total_response_time_ms"] += response_time_ms
        monitoring_state["average_response_time_ms"] = round(
            monitoring_state["total_response_time_ms"] / monitoring_state["request_count"],
            2,
        )
        monitoring_state["last_response_time_ms"] = response_time_ms
        monitoring_state["last_retrieval_time_ms"] = retrieval_time_ms
        monitoring_state["last_generation_time_ms"] = generation_time_ms
        monitoring_state["last_updated_at"] = now_iso()
        average_response_time_ms = monitoring_state["average_response_time_ms"]

    return AskMetrics(
        retrieval_time_ms=retrieval_time_ms,
        generation_time_ms=generation_time_ms,
        response_time_ms=response_time_ms,
        average_response_time_ms=average_response_time_ms,
    )


def snapshot_monitoring_state() -> Dict[str, Any]:
    with monitoring_lock:
        state = dict(monitoring_state)
    state.pop("total_response_time_ms", None)
    state["resources"] = snapshot_resource_usage()
    return state


def get_collection_count() -> int:
    try:
        client = chromadb.PersistentClient(path=PERSIST_DIR)
        collection = client.get_collection(name=COLLECTION_NAME)
        return collection.count()
    except Exception:
        return 0


def update_ingest_state(**updates: Any) -> None:
    with ingest_state_lock:
        ingest_state.update(updates)


def snapshot_ingest_state() -> Dict[str, Any]:
    with ingest_state_lock:
        state = dict(ingest_state)
    if not state.get("running"):
        state["collection_count"] = get_collection_count()
    return state


def handle_ingest_progress(payload: Dict[str, Any]) -> None:
    update_ingest_state(
        phase=payload.get("phase"),
        processed=payload.get("processed", 0),
        total=payload.get("total", 0),
        added=payload.get("added", 0),
        skipped=payload.get("skipped", 0),
        collection_count=payload.get("collection_count", 0),
    )


def run_ingest_task(rebuild: bool) -> None:
    mode = "rebuild" if rebuild else "incremental"
    update_ingest_state(
        status="running",
        running=True,
        mode=mode,
        phase="starting",
        processed=0,
        total=0,
        added=0,
        skipped=0,
        collection_count=get_collection_count(),
        started_at=now_iso(),
        finished_at=None,
        error=None,
    )

    try:
        stats = ingest_healthcare_data(
            IngestConfig(
                input_path=INPUT_FILE,
                persist_directory=PERSIST_DIR,
                model_path=EMBED_MODEL_PATH,
                collection_name=COLLECTION_NAME,
                max_documents=MAX_DOCUMENTS,
                batch_size=BATCH_SIZE,
                rebuild=rebuild,
                onnx_model_file=ONNX_MODEL_FILE,
                onnx_provider=ONNX_PROVIDER,
                tokenize_max_length=TOKENIZE_MAX_LENGTH,
            ),
            progress_callback=handle_ingest_progress,
        )
        refresh_retriever()
        update_ingest_state(
            status="succeeded",
            running=False,
            phase="completed",
            processed=stats.processed,
            total=stats.total,
            added=stats.added,
            skipped=stats.skipped,
            collection_count=stats.collection_count,
            finished_at=now_iso(),
            error=None,
        )
    except Exception as exc:
        update_ingest_state(
            status="failed",
            running=False,
            phase="failed",
            finished_at=now_iso(),
            error=str(exc),
            collection_count=get_collection_count(),
        )


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api-key/status", response_model=ApiKeyStatusResponse)
def api_key_status() -> ApiKeyStatusResponse:
    return ApiKeyStatusResponse(configured=is_api_key_configured())


@app.post("/api-key", response_model=ApiKeyUpdateResponse)
def update_api_key(request: ApiKeyRequest) -> ApiKeyUpdateResponse:
    api_key = request.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    try:
        configure_llm(api_key)
    except Exception:
        raise HTTPException(status_code=400, detail="API Key 验证失败，请检查 key、模型和 API 地址")

    return ApiKeyUpdateResponse(configured=True, message="API Key 已验证")


@app.get("/ingest/status", response_model=IngestStatusResponse)
def ingest_status() -> IngestStatusResponse:
    return IngestStatusResponse(**snapshot_ingest_state())


@app.get("/knowledge-base/parameters", response_model=KnowledgeBaseParametersResponse)
def knowledge_base_parameters() -> KnowledgeBaseParametersResponse:
    return KnowledgeBaseParametersResponse(
        collection_name=COLLECTION_NAME,
        collection_count=get_collection_count(),
        retrieval_top_k=retrieval_top_k,
        max_documents=MAX_DOCUMENTS,
        batch_size=BATCH_SIZE,
        tokenize_max_length=TOKENIZE_MAX_LENGTH,
        embedding_model=os.path.basename(EMBED_MODEL_PATH.rstrip(os.sep)),
        onnx_model_file=ONNX_MODEL_FILE,
        onnx_provider=ONNX_PROVIDER,
        llm_model=LLM_MODEL,
        api_base=OPENAI_API_BASE,
        api_key_configured=is_api_key_configured(),
    )


@app.patch("/knowledge-base/top-k", response_model=KnowledgeBaseParametersResponse)
def update_knowledge_base_top_k(request: TopKUpdateRequest) -> KnowledgeBaseParametersResponse:
    if not (1 <= request.top_k <= 100):
        raise HTTPException(status_code=422, detail="top_k 必须在 1-100 之间")

    update_top_k(request.top_k)
    return knowledge_base_parameters()


@app.get("/monitoring", response_model=MonitoringResponse)
def monitoring() -> MonitoringResponse:
    return MonitoringResponse(**snapshot_monitoring_state())


@app.post("/ingest/start", response_model=IngestStartResponse)
def ingest_start(request: IngestStartRequest) -> IngestStartResponse:
    with ingest_state_lock:
        if ingest_state.get("running"):
            raise HTTPException(status_code=409, detail="嵌入任务正在运行")

    thread = threading.Thread(target=run_ingest_task, args=(request.rebuild,), daemon=True)
    thread.start()
    return IngestStartResponse(
        status="running",
        message="重建任务已启动" if request.rebuild else "增量更新任务已启动",
    )


@app.get("/sample-prompts", response_model=SamplePromptsResponse)
def sample_prompts(limit: int = 3) -> SamplePromptsResponse:
    prompt_limit = max(1, min(limit, 12))
    try:
        with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
            queries = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="示例问题文件不存在")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="示例问题文件格式错误")

    prompts = [query.strip() for query in queries if isinstance(query, str) and query.strip()]
    if not prompts:
        return SamplePromptsResponse(prompts=[])

    return SamplePromptsResponse(
        prompts=random.sample(prompts, min(prompt_limit, len(prompts)))
    )


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    question = request.query.strip()
    if not question:
        raise HTTPException(status_code=400, detail="query 不能为空")

    answer_chain = get_rag_chain()
    request_start = time.perf_counter()
    state = snapshot_ingest_state()
    if state.get("running") and state.get("mode") == "rebuild":
        metrics = record_request_metrics(
            response_time_ms=elapsed_ms(request_start),
            retrieval_time_ms=0.0,
            generation_time_ms=0.0,
        )
        return AskResponse(
            answer="知识库正在重建中，请稍后再提问。",
            sources=[],
            metrics=metrics,
        )

    retrieval_query = translate_query_for_retrieval(question)
    retrieval_start = time.perf_counter()
    with retriever_lock:
        docs = retriever.invoke(retrieval_query)
    retrieval_time_ms = elapsed_ms(retrieval_start)
    if not docs:
        metrics = record_request_metrics(
            response_time_ms=elapsed_ms(request_start),
            retrieval_time_ms=retrieval_time_ms,
            generation_time_ms=0.0,
        )
        return AskResponse(
            answer="抱歉，无法在知识库中找到相关信息来回答您的问题。",
            sources=[],
            metrics=metrics,
        )

    generation_start = time.perf_counter()
    answer = answer_chain.invoke({
        "context": format_docs(docs),
        "question": question,
    })
    generation_time_ms = elapsed_ms(generation_start)
    metrics = record_request_metrics(
        response_time_ms=elapsed_ms(request_start),
        retrieval_time_ms=retrieval_time_ms,
        generation_time_ms=generation_time_ms,
    )

    return AskResponse(
        answer=answer,
        sources=[doc.page_content for doc in docs],
        metrics=metrics,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=API_HOST, port=API_PORT)
