# Med RAG Grad

医疗问答 RAG 系统，FastAPI, ChromaDB, Vue 3，毕设用。

Medical Q&A RAG application with a FastAPI backend and Vue frontend. The backend retrieves relevant healthcare Q&A examples from a local ChromaDB vector store, then sends the retrieved context to an OpenAI-compatible chat API. The frontend provides the chat UI, API key setup, references, and monitoring panels.

## Project Layout

```text
rag-backend/
  main.py              FastAPI API service and RAG chain
  ingest.py            Healthcare dataset ingestion into ChromaDB
  embeddings.py        Local ONNX embedding wrapper
  generate_queries.py  Synthetic query generation for evaluation
  requirements.txt     Python dependencies
  healthcaremagicR/
    generated_queries300.json

rag-frontend/
  src/App.vue          Main Vue chat interface
  server.js            Production Express static server and API proxy
  vue.config.js        Vue dev-server proxy config
  package.json         Frontend scripts and dependencies
```

Large local runtime assets are intentionally not committed:

- `rag-backend/gte-large-en-v1.5/`
- `rag-backend/bge-base-en-v1.5/`
- `rag-backend/vector_store/`
- `rag-backend/healthcaremagic/`
- Python virtual environments, `node_modules`, and frontend build output

Keep those files locally or restore them from their original model, dataset, or generated vector-store sources before running retrieval.

## Backend

```bash
cd rag-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OPENAI_API_KEY="<your-key>" python main.py
```

Useful environment variables:

- `OPENAI_API_KEY`: required for LLM calls unless entered through the frontend.
- `OPENAI_API_BASE`: OpenAI-compatible API base URL. Defaults to DeepSeek.
- `LLM_MODEL`: chat model name. Defaults to `deepseek-chat`.
- `API_HOST`: backend bind host. Defaults to `0.0.0.0`.
- `API_PORT`: backend port. Defaults to `8080`.
- `ONNX_PROVIDER`: embedding runtime provider. The API defaults to CPU for stability.
- `MAX_DOCUMENTS`: ingest document limit. `0` means all documents.
- `CORS_ALLOW_ORIGINS`: comma-separated allowed origins. Defaults to `*`.

The backend expects the embedding model at `rag-backend/gte-large-en-v1.5/` and the vector store at `rag-backend/vector_store/vector_store_healthcare_st/`.

## Ingest

```bash
cd rag-backend
source .venv/bin/activate
python ingest.py --rebuild
```

The full dataset should be placed at:

```text
rag-backend/healthcaremagic/HealthCareMagic-100k-en.jsonl
```

For a smaller debug run:

```bash
python ingest.py --max-documents 2000
```

## Frontend

```bash
cd rag-frontend
npm install
npm run serve
```

The dev server runs on port `3000` and proxies `/api/*` to `http://localhost:8080`.

For production build and local serving:

```bash
npm run build
node server.js
```

`server.js` serves `dist/` and proxies `/api/*` to the backend. Set `API_TARGET` to override the backend URL.

## Notes

This repository is source-only. Do not commit API keys, `.env` files, virtual environments, model weights, vector databases, or raw healthcare datasets.
