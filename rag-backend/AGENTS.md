# rag-backend/ AGENTS.md

> **Generated:** 2026-04-29 | **Commit:** `09acb86` | **Branch:** `main`
> Parent: [../AGENTS.md](../AGENTS.md) — read first for overview, env vars, and shared gotchas.

## OVERVIEW

Python FastAPI + ChromaDB + ONNX embeddings. 4 source files, flat layout, no package structure.

## STRUCTURE

```
rag-backend/
├── main.py                # API server, all routes, all models, RAG chain, ingest thread (665 lines)
├── ingest.py              # JSONL → ChromaDB pipeline, also imported by main.py
├── embeddings.py          # GTE ONNX wrapper, CUDA preload at import time
├── generate_queries.py    # LLM-driven synthetic query generator (evaluation only)
└── requirements.txt       # Python deps (unpinned >= versions)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add API route | `main.py` | All routes are `@app.get`/`@app.post` on the global FastAPI app. No routers. |
| Add Pydantic model | `main.py` | 16+ models defined inline around lines 234-327 |
| Change collection name | `main.py` | `COLLECTION_NAME = "healthcare_qa_gte"` (line ~45) |
| Change prompt template | `main.py` | `PROMPT_TEMPLATE` using `<\|im_start\|>` tokens (line ~130-150) |
| Adjust retrieval top-k | `main.py` | `RETRIEVAL_TOP_K = 3` (line ~85) |
| Ingest logic | `ingest.py` | `ingest_healthcare_data()`, SHA-256 dedup, reservoir sampling |
| Embedding model | `embeddings.py` | `GTEOnnxEmbeddings` class, GPU→CPU fallback in `embed_batch()` |
| Generate eval queries | `generate_queries.py` | Uses `ChatPromptTemplate.from_messages()` — **different** prompt paradigm from main.py |

## CONVENTIONS

- **4-space indent**, single-quote strings (mostly), f-strings
- **Chinese comments** throughout — all inline comments, docstrings, tqdm descs are Chinese
- **No `__init__.py`** — imports rely on files being in the same directory and PYTHONPATH
- **No logging** — all output is `print()`. No `import logging`.
- **Imports**: stdlib first, then third-party, then local (no blank-line separation)

## ANTI-PATTERNS

- **`import resource` at line 7 of main.py** — POSIX-only, crashes on Windows. Wrap in try/except.
- **`embeddings.py` mutates global env** — `os.environ["LD_LIBRARY_PATH"]` modified at import time, `TRANSFORMERS_OFFLINE` and `TOKENIZERS_PARALLELISM` set in `__init__`.
- **Constants duplicated across 3 files** — `ONNX_PROVIDER` defaults differ: `"cpu"` in main.py vs `"auto"` in ingest.py.
- **Two prompt paradigms** — main.py uses raw `<\|im_start\|>` tokens, generate_queries.py uses `ChatPromptTemplate.from_messages()`. Do not cross-pollinate.
- **Daemon thread for ingest** — `threading.Thread(daemon=True)`, killed silently if main process exits.
- **Silent GPU→CPU fallback** — no alert when ONNX falls back from CUDA to CPU.

## GOTCHAS

- **LLM lazy init**: Not initialized at startup unless `OPENAI_API_KEY` env is set. `POST /api-key` triggers `configure_llm()`.
- **ONNX provider default differs**: API server uses `cpu`, standalone ingest uses `auto`.
- **Chinese translation**: Queries with CJK characters (\u4e00-\u9fff) are LLM-translated to English before vector retrieval.
- **`ONNX_MODEL_FILE`** expects `onnx/model.onnx` relative to `EMBED_MODEL_PATH` (`gte-large-en-v1.5/`).
- **Ingest format**: Parses `<human>: ... \n<bot>: ...` from JSONL.

## COMMANDS

```bash
# Activate venv (first time: python3 -m venv .venv && pip install -r requirements.txt)
source .venv/bin/activate

# Run API server
OPENAI_API_KEY="sk-..." python main.py

# Run ingest (standalone)
python ingest.py --rebuild --max-documents 2000

# Generate eval queries
OPENAI_API_KEY="sk-..." python generate_queries.py
```
