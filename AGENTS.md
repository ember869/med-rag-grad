# AGENTS.md

> **Generated:** 2026-04-29 | **Commit:** `09acb86` | **Branch:** `main`

Compact instruction file for OpenCode agents working in this repository.
See sub-directory AGENTS.md for module-specific details:
- `rag-backend/AGENTS.md` — Python backend internals
- `rag-frontend/AGENTS.md` — Vue frontend internals

## Two independent sub-projects

- `rag-backend/` — Python FastAPI + ChromaDB + ONNX embeddings. Activate `.venv` first.
- `rag-frontend/` — Vue 3 (Vue CLI, not Vite) + Express production server. Plain JS, no TypeScript.
- They run independently. Backend on 8080, frontend dev on 3000 proxying to 8080.

## No tests, no CI, no pre-commit

There are zero tests, zero CI workflows, and no pre-commit hooks. Do not hunt for test runners or try `pytest`/`npm test` — they don't exist. Verification means running the app and checking manually.

## Backend gotchas

### Lazy LLM initialization
The LLM is NOT initialized at startup unless `OPENAI_API_KEY` is set in the environment. The frontend sends the key via `POST /api-key`, which calls `configure_llm()` to validate the key and create the chains. API key is held in **memory only** — not persisted. If the key is missing, all `/ask` calls return 401.

### ONNX GPU → CPU fallback
`embeddings.py` preloads NVIDIA CUDA libraries at import time. If ONNX GPU inference fails, it silently switches to CPU. The `ONNX_PROVIDER` env var defaults to `auto` in standalone ingest but `cpu` in the API server (`main.py`). These defaults differ between the two entrypoints — be aware.

### Embeddings module sets env vars at class init
`GTEOnnxEmbeddings.__init__` sets `os.environ["TRANSFORMERS_OFFLINE"] = "1"` and `os.environ["TOKENIZERS_PARALLELISM"] = "true"`. The offline flag blocks HuggingFace network calls — the tokenizer must already be cached locally at `gte-large-en-v1.5/`.

### `resource` module is POSIX-only
`main.py` imports `resource` at the top. `snapshot_resource_usage()` calls `resource.getrusage()` as a fallback when `psutil` is not installed. This crashes on Windows. The app is Linux-only in practice.

### Query translation
Chinese queries are translated to English via LLM **before** vector retrieval (the GTE model encodes English). If the translation chain returns empty, the original question is used as fallback. `contains_chinese()` uses a basic Unicode range check (`\u4e00-\u9fff`).

### Threading model
- `retriever_lock` (threading.Lock) — protects vector DB access during ingest
- `llm_lock` (threading.Lock) — protects LLM configuration
- `ingest_state_lock` (threading.Lock) — protects ingest status state
- Ingest runs on a **daemon thread** — if the main process exits, ingest is killed silently

### Ingest pipeline details
- Parses `<human>: ... \n<bot>: ...` format from JSONL
- Deduplicates via SHA-256 content hashing (`doc_<hash>` as ID)
- Reservoir sampling when `MAX_DOCUMENTS > 0`
- ChromaDB collection uses cosine similarity: `metadata={"hnsw:space": "cosine"}`
- After ingest completes, `refresh_retriever()` reloads the vector DB
- Progress is reported via callback; the API endpoint polls `GET /ingest/status`

### Prompt format — CRITICAL
`main.py` uses DeepSeek `<|im_start|>` chat tokens in prompt templates — **NOT** standard ChatOpenAI message format. Changing the prompt template must preserve this structure.

HOWEVER: `generate_queries.py` uses the **standard** `ChatPromptTemplate.from_messages()` format. These two files use DIFFERENT prompt paradigms. Do not confuse them.

### `generate_queries.py` — synthetic query generator
Uses the LLM to generate diverse healthcare Q&A questions for evaluation. Reads queries from `healthcaremagicR/generated_queries300.json` (committed to git). Run with `OPENAI_API_KEY` set.

### Hardcoded constants in main.py
- `COLLECTION_NAME = "healthcare_qa_gte"`
- `RETRIEVAL_TOP_K = 3`
- `EMBED_MODEL_PATH` expects `gte-large-en-v1.5/` at backend root
- `PERSIST_DIR` expects `vector_store/vector_store_healthcare_st/` at backend root

## Frontend gotchas

### Single component architecture
`src/App.vue` is the **entire application** — 1554 lines. No router (`vue-router`), no state management library (Vuex/Pinia). All state is component `data()`. The only other source files are `src/main.js` (4-line bootstrap) and `src/components/HelloWorld.vue` (unused boilerplate — dead code).

### Proxy double-layer — `/api/` prefix stripped both in dev and prod
- **Dev**: `vue.config.js` proxies `/api/` → `http://localhost:8080`. The `/api/` prefix is stripped by webpack-dev-server automatically.
- **Production**: `server.js` uses `http-proxy-middleware` (v3) with `app.use('/api/', ...)`, which **also** strips the prefix.
- In both cases, requests to `/api/ask` hit the backend as `/ask`, `/api/monitoring` as `/monitoring`, etc.
- Set `API_TARGET` env var in production to override the backend URL.

### Express 5, not Express 4
`server.js` runs on Express 5 (`"express": "^5.2.1"`). API differences from Express 4 apply (e.g., `req.query` is a proper object, route parameter handling differs).

### Polling
- Ingest status: polled **every 2s** while `ingestStatus.running` is true. Polling auto-stops when ingest completes.
- Monitoring: polled **every 5s** continuously via `setInterval`.
- Both timers are cleaned up in `beforeUnmount`.

### Markdown rendering — XSS risk
Messages are rendered with the `marked` library (v18). User messages and bot messages are rendered through `v-html="formatMessage(message.text)"`. Any LLM output containing HTML/scripts will be rendered — this is a known XSS vector if the LLM output is ever untrusted.

### API key flow
On mount, the frontend checks `GET /api/api-key/status`. If `configured` is false, it shows a modal that blocks usage. On successful `POST /api-key`, the modal closes. On any 401 from `/api/ask`, the modal reopens.

## Environment variables reference

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. Can also be submitted via frontend. |
| `OPENAI_API_BASE` | `https://api.deepseek.com/v1` | OpenAI-compatible API |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `API_HOST` | `0.0.0.0` | Backend bind host |
| `API_PORT` | `8080` | Backend listen port |
| `ONNX_PROVIDER` | `cpu` (API) / `auto` (ingest) | `cpu`, `cuda`, `tensorrt`, or `auto` |
| `ONNX_MODEL_FILE` | `onnx/model.onnx` | Path relative to model dir |
| `MAX_DOCUMENTS` | `0` (= all) | Ingest document limit |
| `INGEST_BATCH_SIZE` | `32` | Embedding batch size |
| `TOKENIZE_MAX_LENGTH` | `512` | Tokenizer max input length |
| `SAMPLE_SEED` | `42` | Random seed for reservoir sampling |
| `ORT_INTRA_OP_THREADS` | `0` (= auto) | ONNX intra-op parallelism |
| `ORT_INTER_OP_THREADS` | `0` (= auto) | ONNX inter-op parallelism |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated |
| `API_TARGET` (frontend) | `http://localhost:8080` | Production backend URL |
| `PORT` (frontend) | `3000` | Express production listen port |
| `TOTAL_QUERIES` | `300` | Query generation target count |
| `QUERIES_PER_BATCH` | `10` | Queries per LLM batch in generator |
| `MAX_ATTEMPTS_MULTIPLIER` | `4` | Generator retry multiplier |

## What's gitignored (must exist locally)

These are in `.gitignore` and are required at runtime:
- `rag-backend/gte-large-en-v1.5/` — ONNX embedding model (~670MB, contains tokenizer + onnx model)
- `rag-backend/vector_store/vector_store_healthcare_st/` — ChromaDB persistence
- `rag-backend/healthcaremagic/HealthCareMagic-100k-en.jsonl` — source dataset
- `rag-backend/.venv/` — Python virtual environment
- `rag-frontend/node_modules/`, `rag-frontend/dist/`

Committed to git (NOT gitignored):
- `rag-backend/healthcaremagicR/generated_queries300.json` — pre-generated sample queries

Note: `.gitignore` blacklists `*.onnx` files globally, but the model is already in its own ignored directory.
