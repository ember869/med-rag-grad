# rag-frontend/ AGENTS.md

> **Generated:** 2026-04-29 | **Commit:** `09acb86` | **Branch:** `main`
> Parent: [../AGENTS.md](../AGENTS.md) — read first for overview, env vars, and shared gotchas.

## OVERVIEW

Vue 3 (Vue CLI, not Vite) + Express 5 production server. Plain JS, no TypeScript. Single-component architecture.

## STRUCTURE

```
rag-frontend/
├── src/
│   ├── App.vue              # ENTIRE application (1554 lines) — chat, monitoring, ingest, settings
│   ├── main.js              # Vue bootstrap: createApp(App).mount('#app')
│   └── components/
│       ├── ApiKeyModal.vue   # API key input modal (emits-based parent coupling)
│       └── HelloWorld.vue    # DEAD CODE — Vue CLI boilerplate, never imported
├── server.js                # Express 5 production server + /api/* proxy
├── vue.config.js            # Dev proxy config (port 3000, /api → :8080)
├── public/index.html        # HTML shell with <div id="app">
└── package.json             # Scripts: serve, build, lint. Inline eslintConfig.
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Chat UI / messages | `src/App.vue` | Everything in one component — template, script, data(), methods, watch, computed |
| Add new feature/module | `src/App.vue` | No router or state management. Conditionally rendered with v-if. |
| Change polling interval | `src/App.vue` | Ingest: 2s (lines ~499), monitoring: 5s (lines ~510) |
| API key flow | `src/App.vue` | `checkApiKeyStatus()` on mount, modal blocks usage until configured |
| Markdown rendering | `src/App.vue` | `formatMessage()` at line ~601 — uses `marked` library, renders via `v-html` |
| Proxy config (dev) | `vue.config.js` | Strips `/api` prefix, forwards to `http://localhost:8080` |
| Proxy config (prod) | `server.js` | Express 5 + `http-proxy-middleware` v3, also strips `/api` prefix |
| Environment overrides | `server.js` | `API_TARGET` env var overrides backend URL, `PORT` overrides listen port |

## CONVENTIONS

- **CommonJS** (`require`/`module.exports`) — not ESM. Vue SFC uses Options API, not `<script setup>`.
- **2-space indent**, semicolons always present
- **Chinese comments** in component methods
- **No TypeScript** — all plain JS. `jsconfig.json` exists for IDE hints only.
- **No router** (`vue-router` not in deps), **no state management** (no Pinia/Vuex)
- **ESLint 7** with inline config in `package.json` (`eslint:recommended` + `plugin:vue/vue3-essential`)
- **No Prettier**, no editorconfig — formatting is unenforced

## ANTI-PATTERNS

- **XSS via `v-html` + `marked`** — `formatMessage()` renders LLM output as raw HTML (line ~158, 601). No DOMPurify sanitization.
- **God component** — `App.vue` is 1554 lines of template, logic, and styles. No separation of concerns.
- **Dead code** — `src/components/HelloWorld.vue` is unused boilerplate. `src/assets/logo.png` also unreferenced.
- **Express 5** — API differs from Express 4 (e.g., `req.query` is a proper object, route params handling). Be aware when adding middleware.
- **Double proxy stripping** — both dev (`vue.config.js`) and prod (`server.js`) strip the `/api/` prefix. Requests to `/api/ask` → `/ask` on backend.
- **No error handling on API calls** — axios calls in `App.vue` lack robust error handling for 401/network failures.
- **Vue CLI** — deprecated build tool. Modern Vue 3 projects use Vite. Migration needed eventually.

## GOTCHAS

- **Proxy prefix is stripped in both dev and prod identically** — `/api/ask` → `/ask` on backend always.
- **Polling cleanup** — `beforeUnmount` clears both `setInterval` timers. If you add new timers, wire cleanup.
- **API key modal** — reopens on any 401 from `/api/ask`. Check `GET /api/api-key/status` on mount.
- **Browserslist** is `["> 1%", "last 2 versions", "not dead", "not ie 11"]` in `package.json`.
- **`axios` version** in package.json is `^1.15.2` — verify this resolves on your registry (latest npm is ~1.7.x).

## COMMANDS

```bash
# Dev server (port 3000, proxies /api/* → :8080)
npm run serve

# Production build + serve
npm run build
node server.js

# Lint
npm run lint
```
