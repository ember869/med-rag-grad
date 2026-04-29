# RAG Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `rag-frontend/src/App.vue` with modern professional style while keeping all logic intact.

**Architecture:** Single-file approach — all changes in App.vue's `<template>` and `<style>`. `<script>` block untouched. Visual system from demo-modern.html.

**Tech Stack:** Vue 3 (Options API), plain CSS (no preprocessor), vue-cli build

**Reference file:** `rag-frontend/demo-modern.html` — the approved visual design

---

### Task 1: Replace CSS variables and base layout styles

**Files:**
- Modify: `rag-frontend/src/App.vue` — replace `:root` block and base styles

- [ ] **Step 1: Replace `:root` CSS variables**

Find the `:root` block in `<style>` (line 621) and replace with:

```css
:root {
  --bg: #f0f4f8;
  --surface: #ffffff;
  --text: #1e293b;
  --muted: #64748b;
  --border: #e2e8f0;
  --primary: #2563eb;
  --primary-dark: #1d4ed8;
  --primary-soft: #eff6ff;
  --accent: #0891b2;
  --accent-soft: #ecfeff;
  --success: #059669;
  --success-soft: #ecfdf5;
  --warning: #d97706;
  --warning-soft: #fffbeb;
  --danger: #dc2626;
  --danger-soft: #fef2f2;
  --radius: 12px;
  --radius-sm: 8px;
  --radius-xs: 6px;
  --shadow-card: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
  --shadow-elevated: 0 4px 12px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04);
  --gradient-brand: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
  --gradient-hero: linear-gradient(180deg, #f8fafc 0%, #f0f4f8 100%);
}
```

- [ ] **Step 2: Replace base element styles**

Replace the `*`, `html, body`, `body/button/input/textarea`, `button/input/textarea`, `button`, `button:disabled/...`, `#app`, `.workspace`, `.sidebar`, `.sidebar, .chat-shell` rules with:

```css
* { box-sizing: border-box; margin: 0; }

html, body {
  height: 100%;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 14px;
  color: var(--text);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}

body, button, input, textarea {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  letter-spacing: 0;
}

button, input, textarea { font: inherit; }
button { cursor: pointer; }
button:disabled, input:disabled, textarea:disabled { cursor: not-allowed; }

#app {
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  height: 100vh;
  max-width: 1220px;
  margin: 0 auto;
  padding: 16px;
  gap: 16px;
  background: var(--bg);
}

.workspace {
  display: contents;
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  overflow-y: auto;
}

.chat-shell {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
}
```

Note: `.workspace` becomes `display: contents` — the grid is now on `#app` directly. This eliminates the nested grid wrapper.

- [ ] **Step 3: Remove old sidebar/chat-shell border/shadow rules**

Delete these old rules (they are now replaced by the `.chat-shell` above):
```css
.sidebar,
.chat-shell {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow);
}
```
And the old `.sidebar` rules with `scrollbar-color`.

### Task 2: Rewrite brand area and status panel

**Files:**
- Modify: `rag-frontend/src/App.vue` — template + style for brand and status sections

- [ ] **Step 1: Update brand `<template>`**

Replace lines 5-11:
```html
<div class="brand">
  <div class="brand-mark">R</div>
  <div>
    <h1>RAG 医疗助手</h1>
    <p>基于知识库回答</p>
  </div>
</div>
```

With:
```html
<div class="brand-card">
  <div class="brand-row">
    <div class="brand-mark">R</div>
    <div>
      <h1>RAG 医疗助手</h1>
      <p>检索增强生成 · 智能问答</p>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Update brand CSS**

Replace `.brand`, `.brand-mark`, `.brand h1`, `.brand p`, `.brand h1, .brand p, ...` rules with:

```css
.brand-card {
  padding: 20px;
  border-radius: var(--radius);
  background: var(--gradient-brand);
  color: #fff;
  box-shadow: var(--shadow-elevated);
}
.brand-card .brand-row {
  display: flex; align-items: center; gap: 10px;
}
.brand-mark {
  width: 38px; height: 38px;
  display: grid; place-items: center;
  background: rgba(255,255,255,0.2);
  backdrop-filter: blur(4px);
  border-radius: var(--radius-sm);
  font-size: 16px; font-weight: 800;
}
.brand-card h1 { font-size: 16px; font-weight: 700; }
.brand-card p { font-size: 12px; opacity: 0.85; margin-top: 3px; }
```

- [ ] **Step 3: Update status panel `<template>`**

Replace lines 12-47 (the `<div class="status-panel">` block) with:

```html
<div class="card">
  <div :class="['status-row', { offline: !apiKeyConfigured }]" style="margin-bottom:12px;">
    <span :class="['status-dot', apiKeyConfigured ? 'online' : 'offline']"></span>
    <span>{{ apiKeyStatusLabel }}</span>
    <span v-if="apiKeyConfigured" class="status-badge ready" style="margin-left:auto;">就绪</span>
    <span v-else class="status-badge waiting" style="margin-left:auto;">待配置</span>
    <button
      v-if="apiKeyConfigured"
      type="button"
      class="gear-button"
      title="管理 API Key"
      @click="openKeyManager"
    >&#9881;</button>
  </div>
  <div class="stat-inline">
    <span class="stat-value">{{ userMessageCount }}</span>
    <span class="stat-label">本轮问题</span>
  </div>
  <div class="stat-inline">
    <span class="stat-value">Top
      <select
        class="topk-select"
        v-model="selectedTopK"
        @change="onTopKChange"
        :disabled="isLoading || _topKChanging"
      >
        <option :value="1">1</option>
        <option :value="3">3</option>
        <option :value="5">5</option>
        <option :value="10">10</option>
      </select>
    </span>
    <span class="stat-label">检索来源数</span>
  </div>
</div>
```

- [ ] **Step 4: Update status panel CSS**

Delete old rules: `.status-panel`, `.status-row`, `.status-dot`, `.status-row.warning`, `.status-row.warning .status-dot`, `.gear-button`, `.gear-button:hover`, `.metric`, `.metric strong`, `.metric span`, `.topk-metric`, `.topk-select`, `.topk-select:focus`, `.topk-select:disabled`.

Add new rules:

```css
.card {
  padding: 16px;
  border-radius: var(--radius);
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
}

.status-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600;
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(5,150,105,0.15);
}
.status-dot.online { background: var(--success); }
.status-dot.offline { background: var(--warning); }

.status-badge {
  padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
}
.status-badge.ready { background: var(--success-soft); color: var(--success); }
.status-badge.waiting { background: var(--warning-soft); color: var(--warning); }

.stat-inline {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 12px 0;
}
.stat-inline + .stat-inline { border-top: 1px solid var(--border); }
.stat-inline .stat-value { font-size: 20px; font-weight: 700; }
.stat-inline .stat-label { font-size: 12px; color: var(--muted); }

.topk-select {
  padding: 0 4px; border: none; border-radius: 6px;
  color: var(--primary); background: var(--primary-soft);
  font: inherit; font-size: 20px; font-weight: 700;
  cursor: pointer; appearance: none;
}
.topk-select:focus {
  outline: 2px solid rgba(37, 99, 235, 0.25);
  outline-offset: 2px;
}
.topk-select:disabled {
  color: var(--muted);
  background: #f3f5f8;
  cursor: not-allowed;
}

.gear-button {
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--muted);
  font-size: 16px; line-height: 1;
  cursor: pointer;
}
.gear-button:hover { border-color: var(--primary); color: var(--primary); }
```

### Task 3: Rewrite monitoring panel

**Files:**
- Modify: `rag-frontend/src/App.vue` — template + style for monitor section

- [ ] **Step 1: Update monitoring `<template>`**

Replace lines 48-86 (the `<div class="monitor-panel">` block) with:

```html
<div class="card">
  <div class="card-header">
    <span class="card-label">前端监控</span>
    <span class="monitor-count">{{ monitoringStatus.request_count || 0 }} 次</span>
  </div>
  <div class="monitor-grid">
    <div class="monitor-kpi">
      <span class="kpi-label">单次检索</span>
      <strong class="kpi-value">{{ formatDuration(monitoringStatus.last_retrieval_time_ms) }}</strong>
    </div>
    <div class="monitor-kpi">
      <span class="kpi-label">回答生成</span>
      <strong class="kpi-value">{{ formatDuration(monitoringStatus.last_generation_time_ms) }}</strong>
    </div>
    <div class="monitor-kpi">
      <span class="kpi-label">平均响应</span>
      <strong class="kpi-value">{{ formatDuration(monitoringStatus.average_response_time_ms) }}</strong>
    </div>
    <div class="monitor-kpi">
      <span class="kpi-label">本次响应</span>
      <strong class="kpi-value">{{ formatDuration(monitoringStatus.last_response_time_ms) }}</strong>
    </div>
  </div>
  <div v-if="monitoringError" class="monitor-error">{{ monitoringError }}</div>
</div>
```

Note: The resource strip (CPU/memory/system memory) is removed from the template.

- [ ] **Step 2: Update monitoring CSS**

Delete old rules: `.monitor-panel`, `.monitor-header`, `.monitor-header strong`, `.monitor-grid`, `.monitor-item`, `.monitor-item span`, `.monitor-item strong`, `.resource-strip`, `.resource-strip div`, `.resource-strip span`, `.resource-strip strong`, `.monitor-error`.

Add new rules:

```css
.card-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px;
}
.card-label {
  font-size: 11px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.6px;
}
.monitor-count { font-size: 12px; font-weight: 700; color: var(--primary); }

.monitor-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}
.monitor-kpi {
  padding: 12px; border-radius: var(--radius-sm);
  background: var(--gradient-hero);
  border: 1px solid var(--border);
}
.kpi-label {
  font-size: 10px; color: var(--muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.3px;
}
.kpi-value {
  font-size: 17px; font-weight: 700; margin-top: 4px;
  font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
  color: #1e293b;
}

.monitor-error {
  margin-top: 8px; padding: 8px 10px;
  border: 1px solid #ffe1a6; border-radius: var(--radius-xs);
  color: #936000; background: #fff9ec;
  font-size: 12px; line-height: 1.4;
}
```

### Task 4: Rewrite ingest/knowledge base panel

**Files:**
- Modify: `rag-frontend/src/App.vue` — template + style for ingest section

- [ ] **Step 1: Update ingest `<template>`**

Replace lines 87-115 (the `<div class="ingest-panel">` block) with:

```html
<div class="card">
  <div class="card-header">
    <span class="card-label">知识库状态</span>
    <strong :class="['ingest-badge', ingestStatus.status]">{{ ingestStatusLabel }}</strong>
  </div>
  <div class="ingest-bar">
    <div class="ingest-bar-fill" :style="{ width: ingestProgressPercent + '%' }"></div>
  </div>
  <div class="ingest-meta">
    <span>{{ ingestProgressText }}</span>
    <span>{{ ingestStatus.collection_count || 0 }} 向量</span>
  </div>
  <div v-if="ingestStatus.error" class="ingest-error">{{ ingestStatus.error }}</div>
  <div class="param-grid" v-if="knowledgeBaseParameters">
    <div class="param-item"><span class="name">Top-K</span> <span class="val">{{ formatParameterNumber(knowledgeBaseParameters.retrieval_top_k) }}</span></div>
    <div class="param-item"><span class="name">批大小</span> <span class="val">{{ formatParameterNumber(knowledgeBaseParameters.batch_size) }}</span></div>
    <div class="param-item"><span class="name">Token 长度</span> <span class="val">{{ formatParameterNumber(knowledgeBaseParameters.tokenize_max_length) }}</span></div>
    <div class="param-item"><span class="name">LLM</span> <span class="val">{{ knowledgeBaseParameters.llm_model || '-' }}</span></div>
  </div>
  <div v-if="knowledgeBaseParametersError" class="kb-params-error">{{ knowledgeBaseParametersError }}</div>
</div>
```

Note: The params are now a 2x2 grid of only 4 items, directly inline — no more `knowledgeBaseParameterItems` computed usage. The loading spinner for params is removed (kept simple).

- [ ] **Step 2: Update ingest CSS**

Delete old rules: `.ingest-panel`, `.ingest-header`, `.ingest-meta`, `.ingest-badge`, `.ingest-badge.running`, `.ingest-badge.succeeded`, `.ingest-badge.failed`, `.ingest-progress`, `.ingest-progress-bar`, `.ingest-error`, `.kb-params`, `.kb-params-title`, `.kb-params-title span:last-child`, `.kb-param-list`, `.kb-param-list dt`, `.kb-param-list dd`, `.kb-params-error`.

Add new rules:

```css
.ingest-badge {
  padding: 3px 10px; border-radius: 20px; font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.2px;
}
.ingest-badge.idle { background: #f1f5f9; color: #64748b; }
.ingest-badge.running { background: var(--primary-soft); color: var(--primary); }
.ingest-badge.succeeded { background: var(--success-soft); color: var(--success); }
.ingest-badge.failed { background: var(--danger-soft); color: var(--danger); }

.ingest-bar {
  height: 6px; border-radius: 3px; background: #f1f5f9;
  overflow: hidden; margin-top: 12px;
}
.ingest-bar-fill {
  height: 100%; border-radius: 3px;
  background: var(--gradient-brand);
  transition: width 0.3s ease;
}

.ingest-meta {
  display: flex; justify-content: space-between;
  font-size: 11px; color: var(--muted); margin-top: 6px;
}

.ingest-error {
  margin-top: 8px; padding: 8px 10px;
  border: 1px solid #ffd6d2; border-radius: var(--radius-xs);
  color: #b42318; background: #fff8f7;
  font-size: 12px; line-height: 1.4;
}

.param-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px;
  margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
}
.param-item { font-size: 12px; }
.param-item .name { color: var(--muted); }
.param-item .val { font-weight: 600; font-family: "SF Mono", "Fira Code", monospace; }

.kb-params-error {
  margin-top: 8px; padding: 8px 10px;
  border: 1px solid #ffe1a6; border-radius: var(--radius-xs);
  color: #936000; background: #fff9ec;
  font-size: 12px; line-height: 1.4;
}
```

### Task 5: Rewrite prompt section

**Files:**
- Modify: `rag-frontend/src/App.vue` — template + style for hint/prompt section

- [ ] **Step 1: Update prompts `<template>`**

Replace lines 116-132 (the `.hint-header` and `.hint-list` blocks) with:

```html
<div class="card">
  <div class="card-header">
    <span class="card-label">随机问题</span>
    <button type="button" class="refresh-chip" @click="loadSamplePrompts" :disabled="isLoading || isLoadingPrompts">
      {{ isLoadingPrompts ? '抽取中' : '换一批' }}
    </button>
  </div>
  <div class="prompt-list">
    <button
      v-for="prompt in samplePrompts"
      :key="prompt"
      type="button"
      class="prompt-btn"
      @click="fillPrompt(prompt)"
      :disabled="isLoading"
    >{{ prompt }}</button>
  </div>
</div>
```

- [ ] **Step 2: Update prompt CSS**

Delete old rules: `.hint-header`, `.hint-list`, `.hint-list button`, `.hint-header button`, `.ghost-button`, `.hint-list button:hover:not(:disabled)`, `.hint-header button:hover:not(:disabled)`, `.ghost-button:hover:not(:disabled)`, `.hint-list button:focus-visible`, `.hint-header button:focus-visible`, `.ghost-button:focus-visible`, `.hint-list button:disabled`, `.hint-header button:disabled`, `.ghost-button:disabled`.

Also delete: `.status-row`, `.sender, .eyebrow` (the old eyebrow rule).

Add new rules:

```css
.prompt-list { display: grid; gap: 6px; }
.prompt-btn {
  text-align: left; padding: 11px 14px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); font-size: 12px; line-height: 1.5;
  color: var(--text); cursor: pointer;
  transition: all 0.15s ease;
}
.prompt-btn:hover:not(:disabled) {
  border-color: var(--primary); background: var(--primary-soft);
  box-shadow: 0 0 0 3px rgba(37,99,235,0.08);
}
.prompt-btn:disabled { color: #98a2b3; background: #f3f5f8; }

.refresh-chip {
  padding: 4px 10px; border: 1px solid var(--border);
  border-radius: 20px; background: var(--surface);
  font-size: 11px; color: var(--primary); cursor: pointer;
  font-weight: 600; transition: all 0.15s;
}
.refresh-chip:hover:not(:disabled) { border-color: var(--primary); background: var(--primary-soft); }
.refresh-chip:disabled { color: #98a2b3; background: #f3f5f8; }
```

### Task 6: Rewrite chat area styles

**Files:**
- Modify: `rag-frontend/src/App.vue` — template adjustments + style for chat area

- [ ] **Step 1: Minor chat `<template>` adjustments**

The chat area template is largely compatible. Make these targeted edits:

In the chat-header (lines 136-146), replace `.ghost-button` class with `.ghost-btn`:
```html
<button type="button" class="ghost-btn" @click="clearChat" :disabled="isLoading">
  清空
</button>
```

In the message metrics (lines 159-163), replace `message-metrics` class with `metrics-row`:
```html
<div v-if="message.metrics" class="metrics-row">
```

In the chat input button (line 195), replace the inline button with:
```html
<button type="submit" class="send-btn" :disabled="isLoading || !apiKeyConfigured || userInput.trim() === ''">
  {{ isLoading ? '思考中' : '发送' }}
</button>
```

- [ ] **Step 2: Rewrite chat CSS**

Delete ALL old chat-related rules and replace with:

```css
/* Chat Header */
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 24px;
  background: var(--gradient-hero);
  border-bottom: 1px solid var(--border);
}
.eyebrow {
  font-size: 10px; color: var(--primary); font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px;
}
.chat-header h2 { font-size: 19px; font-weight: 700; margin: 0; }

.ghost-btn {
  padding: 7px 14px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--surface);
  font-size: 13px; font-weight: 600; cursor: pointer;
  color: var(--muted);
  transition: all 0.15s;
}
.ghost-btn:hover:not(:disabled) {
  border-color: var(--primary); color: var(--primary); background: var(--primary-soft);
}
.ghost-btn:disabled { color: #98a2b3; background: #f3f5f8; }

/* Chat History */
.chat-history {
  flex: 1; overflow-y: auto; padding: 24px;
  background: #f8fafc;
  display: flex; flex-direction: column; gap: 16px;
  scrollbar-color: #c7d0dd transparent;
  scrollbar-width: thin;
}

/* Messages */
.message { display: flex; gap: 10px; align-items: flex-start; }
.message.user { flex-direction: row-reverse; }

.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: grid; place-items: center; font-size: 11px; font-weight: 700;
  flex-shrink: 0; box-shadow: var(--shadow-card);
}
.message.bot .avatar {
  background: var(--surface); color: var(--primary);
  border: 1px solid var(--border);
}
.message.user .avatar {
  background: var(--gradient-brand); color: #fff;
}

.bubble {
  max-width: 72%; padding: 14px 16px; border-radius: var(--radius);
  font-size: 14px; line-height: 1.7;
}
.message.bot .bubble {
  background: var(--surface); border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
  border-top-left-radius: 4px;
}
.message.user .bubble {
  background: var(--gradient-brand); color: #fff;
  box-shadow: var(--shadow-elevated);
  border-top-right-radius: 4px;
}

.bubble .sender { font-size: 11px; font-weight: 700; margin-bottom: 4px; }
.message.bot .bubble .sender { color: var(--primary); }
.message.user .bubble .sender { color: rgba(255,255,255,0.75); }

/* Message text content */
.text {
  overflow-wrap: anywhere; font-size: 15px; line-height: 1.7;
}
.text :first-child { margin-top: 0; }
.text :last-child { margin-bottom: 0; }
.text p { margin: 8px 0; }
.text ul, .text ol { margin: 8px 0; padding-left: 22px; }
.text li + li { margin-top: 4px; }
.text a { color: var(--primary-dark); }
.message.user .text a { color: #fff; }

/* Metrics row */
.metrics-row { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.metrics-row span {
  padding: 2px 8px; border: 1px solid var(--border);
  border-radius: 20px; font-size: 10px; color: var(--muted);
  font-family: "SF Mono", "Fira Code", monospace;
  background: var(--surface);
}

/* Sources box */
.sources-box {
  margin-top: 10px; padding: 12px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: #f8fafc;
}
.sources-title {
  font-size: 11px; font-weight: 700; color: var(--accent);
  display: flex; align-items: center; gap: 6px;
}
.sources-title::before {
  content: ''; display: block; width: 4px; height: 4px;
  border-radius: 50%; background: var(--accent);
}
.sources-list {
  display: grid; gap: 8px; margin: 6px 0 0; padding-left: 18px;
}
.sources-list li { padding-left: 2px; color: var(--muted); }
.sources-list pre {
  margin: 0; color: var(--text);
  font-family: "SF Mono", "Fira Code", monospace; font-size: 11px;
  white-space: pre-wrap;
}

/* Chat Input */
.chat-input {
  display: flex; gap: 10px; padding: 16px 24px;
  border-top: 1px solid var(--border); background: var(--surface);
}
.chat-input textarea {
  flex: 1; min-height: 46px; max-height: 130px; resize: vertical;
  padding: 12px 14px; border: 1px solid #cbd5e1;
  border-radius: var(--radius-sm); font: inherit; font-size: 14px;
  outline: none; transition: all 0.15s; background: #f8fafc;
  color: var(--text);
}
.chat-input textarea:focus {
  border-color: var(--primary); background: var(--surface);
  box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}
.chat-input textarea::placeholder { color: #94a3b8; }
.chat-input textarea:disabled { background: #f3f5f8; }

.send-btn {
  padding: 0 22px; min-height: 46px;
  border: none; border-radius: var(--radius-sm);
  background: var(--gradient-brand); color: #fff;
  font-weight: 700; font-size: 13px; cursor: pointer;
  box-shadow: 0 2px 6px rgba(37,99,235,0.25);
  transition: all 0.15s;
}
.send-btn:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(37,99,235,0.35); transform: translateY(-1px);
}
.send-btn:disabled {
  background: #b7c0ce; box-shadow: none; transform: none;
}

/* Typing animation */
.typing {
  display: flex; gap: 5px; padding-top: 8px;
}
.typing span {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--muted);
  animation: pulse 1s infinite ease-in-out;
}
.typing span:nth-child(2) { animation-delay: 0.14s; }
.typing span:nth-child(3) { animation-delay: 0.28s; }

/* Code blocks */
pre {
  max-width: 100%; margin: 10px 0; padding: 12px;
  overflow-x: auto; border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: #1e293b;
  background: #f1f5f9; white-space: pre-wrap; word-wrap: break-word;
}
code {
  font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
  font-size: 0.92em;
}
.message.user pre {
  border-color: rgba(255,255,255,0.28); color: #fff;
  background: rgba(255,255,255,0.12);
}

@keyframes pulse {
  0%, 80%, 100% { opacity: 0.35; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
```

### Task 7: Update responsive styles

**Files:**
- Modify: `rag-frontend/src/App.vue` — responsive media queries

- [ ] **Step 1: Replace responsive media queries**

Delete both `@media (max-width: 900px)` and `@media (max-width: 640px)` blocks.

Add new responsive rules:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}

@media (max-width: 900px) {
  #app {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 100vh;
    padding: 12px;
  }
  .sidebar { gap: 12px; }
  .chat-shell { min-height: 70vh; }
}

@media (max-width: 640px) {
  #app { padding: 8px; gap: 8px; }
  .sidebar { gap: 8px; }
  .chat-header { padding: 14px; }
  .chat-history { padding: 14px; }
  .chat-input { padding: 12px 14px; flex-direction: column; }
  .send-btn { width: 100%; }
  .bubble { max-width: calc(100vw - 80px); }
  .brand-card { padding: 16px; }
  .card { padding: 14px; }
}
```

### Task 8: Build verification

**Files:**
- No file changes, verification only

- [ ] **Step 1: Install dependencies if needed**

Run: `cd /home/msi/projects/rag-frontend && npm install`
Expected: no errors

- [ ] **Step 2: Build the project**

Run: `cd /home/msi/projects/rag-frontend && npm run build`
Expected: Build completes without errors. The output should be in `dist/`.

- [ ] **Step 3: Check for leftover old CSS class references**

Grep the `<template>` for old class names that no longer have CSS rules:
- `status-panel`, `metric`, `monitor-panel`, `monitor-header`, `monitor-item`, `resource-strip`, `ingest-panel`, `ingest-header`, `kb-params`, `kb-params-title`, `kb-param-list`, `hint-header`, `hint-list`, `ghost-button`, `message-metrics`, `header-actions`, `loading-bubble`, `topk-metric`, `chat-input button`

Run: `grep -n 'status-panel\|monitor-panel\|monitor-header\|monitor-item\|resource-strip\|ingest-panel\|ingest-header\|kb-params\|kb-params-title\|kb-param-list\|hint-header\|hint-list\|ghost-button\|header-actions\|loading-bubble\|topk-metric' /home/msi/projects/rag-frontend/src/App.vue`
Expected: No matches (all references should be updated to new class names).

- [ ] **Step 4: Commit**

```bash
git add rag-frontend/src/App.vue
git commit -m "refactor: redesign App.vue with modern professional style"
```
