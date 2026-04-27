# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a two-part RAG (Retrieval-Augmented Generation) application for medical Q&A. The backend retrieves relevant healthcare Q&A pairs from a ChromaDB vector store and feeds them as context to an LLM. The frontend provides a chat interface with monitoring and ingest controls.

## Repository layout

```
projects/
├── rag-backend/          # FastAPI Python backend
│   ├── main.py           # API entry point, LLM/RAG chain, monitoring
│   ├── ingest.py         # ChromaDB vector store ingestion pipeline
│   ├── embeddings.py     # GTE ONNX embedding model wrapper (LangChain-compatible)
│   └── generate_queries.py  # LLM-based synthetic query generator for evaluation
└── rag-frontend/         # Vue 3 + Express frontend
    ├── server.js         # Production Express server (serves dist + proxies /api)
    ├── vue.config.js     # Vue CLI dev server with proxy
    └── src/
        ├── App.vue       # Single-file chat app (sidebar + chat + API key modal)
        └── main.js       # Vue app bootstrap
```

## Running the backend

```bash
cd rag-backend
source .venv/bin/activate
OPENAI_API_KEY="<key>" python main.py
# Optional env vars: LLM_MODEL (default: deepseek-chat), API_PORT (default: 8080),
# ONNX_PROVIDER (default: cpu), MAX_DOCUMENTS (0 = all), CORS_ALLOW_ORIGINS
```

## Running the frontend

```bash
cd rag-frontend
npm run serve        # Vue CLI dev server on port 3000, proxies /api to localhost:8080
npm run build        # Production build to dist/
node server.js       # Express server on port 3000, serves dist/ + proxies /api
```

## Running the ingest pipeline standalone

```bash
cd rag-backend
source .venv/bin/activate
python ingest.py --rebuild              # Rebuild vector store from scratch
python ingest.py --max-documents 2000   # Sample 2000 docs (reservoir sampling)
python ingest.py --batch-size 64
```

## Architecture notes

- **Embedding model**: gte-large-en-v1.5 exported to ONNX. The `GTEOnnxEmbeddings` class in `embeddings.py` uses `onnxruntime` for inference and normalizes output vectors for cosine similarity. It preloads NVIDIA CUDA libraries and can auto-fallback from GPU to CPU on inference failure.
- **LLM integration**: Uses LangChain's `ChatOpenAI` pointed at DeepSeek's API by default (`OPENAI_API_BASE` env var). The LLM is lazily initialized when the frontend submits an API key via `POST /api-key`. The API key is held in memory only.
- **RAG flow**: User question → translate Chinese queries to English via LLM → retrieve top-K from ChromaDB → format docs into prompt → LLM answers in the user's language.
- **Query translation**: Non-English queries are translated to English before vector retrieval (`translate_query_for_retrieval` in `main.py`), since the GTE model encodes English text.
- **Ingest**: `ingest.py` parses `<human>: ... <bot>: ...` dialogue format from a JSONL file, deduplicates via SHA-256 content hashing, and supports both incremental (skip existing IDs) and rebuild modes. Reservoir sampling is used when `MAX_DOCUMENTS` > 0.
- **Frontend is a single component**: `App.vue` is the entire application — no router, no store. It polls `/api/ingest/status` every 2s during active ingest jobs and `/api/monitoring` every 5s for system metrics.
- **Production frontend serving**: `server.js` is an Express server that serves the Vue production build and proxies all `/api/*` requests to the backend (stripping the `/api` prefix).
