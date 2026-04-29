<template>
  <div id="app">
    <aside class="sidebar">
        <div class="brand-card">
          <div class="brand-row">
            <div class="brand-mark">R</div>
            <div>
              <h1>RAG 医疗助手</h1>
              <p>检索增强生成 · 智能问答</p>
            </div>
          </div>
        </div>
        <div class="card">
          <div :class="['status-row', { offline: !apiKeyConfigured }]" style="margin-bottom:12px;">
            <span :class="['status-dot', apiKeyConfigured ? 'online' : 'offline']"></span>
            <span>{{ apiKeyStatusLabel }}</span>
            <span v-if="apiKeyConfigured" class="status-badge ready" style="margin-left:auto;">就绪</span>
            <span v-else class="status-badge waiting" style="margin-left:auto;">待配置</span>
            <button v-if="apiKeyConfigured" type="button" class="gear-button" title="管理 API Key" @click="openKeyManager">&#9881;</button>
          </div>
          <div class="stat-inline">
            <span class="stat-value">{{ userMessageCount }}</span>
            <span class="stat-label">本轮问题</span>
          </div>
          <div class="stat-inline">
            <span class="stat-value">Top
              <select class="topk-select" v-model="selectedTopK" @change="onTopKChange" :disabled="isLoading || _topKChanging">
                <option :value="1">1</option><option :value="3">3</option><option :value="5">5</option><option :value="10">10</option>
              </select>
            </span>
            <span class="stat-label">检索来源数</span>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-label">前端监控</span>
            <span class="monitor-count">{{ monitoringStatus.request_count || 0 }} 次</span>
          </div>
          <div class="monitor-grid">
            <div class="monitor-kpi"><span class="kpi-label">单次检索</span><strong class="kpi-value">{{ formatDuration(monitoringStatus.last_retrieval_time_ms) }}</strong></div>
            <div class="monitor-kpi"><span class="kpi-label">回答生成</span><strong class="kpi-value">{{ formatDuration(monitoringStatus.last_generation_time_ms) }}</strong></div>
            <div class="monitor-kpi"><span class="kpi-label">平均响应</span><strong class="kpi-value">{{ formatDuration(monitoringStatus.average_response_time_ms) }}</strong></div>
            <div class="monitor-kpi"><span class="kpi-label">本次响应</span><strong class="kpi-value">{{ formatDuration(monitoringStatus.last_response_time_ms) }}</strong></div>
          </div>
          <div v-if="monitoringError" class="monitor-error">{{ monitoringError }}</div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-label">知识库状态</span>
            <strong :class="['ingest-badge', ingestStatus.status]">{{ ingestStatusLabel }}</strong>
          </div>
          <div class="ingest-bar"><div class="ingest-bar-fill" :style="{ width: ingestProgressPercent + '%' }"></div></div>
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
        <div class="card">
          <div class="card-header">
            <span class="card-label">随机问题</span>
            <button type="button" class="refresh-chip" @click="loadSamplePrompts" :disabled="isLoading || isLoadingPrompts">{{ isLoadingPrompts ? '抽取中' : '换一批' }}</button>
          </div>
          <div class="prompt-list">
            <button v-for="prompt in samplePrompts" :key="prompt" type="button" class="prompt-btn" @click="fillPrompt(prompt)" :disabled="isLoading">{{ prompt }}</button>
          </div>
        </div>
      </aside>

      <section class="chat-shell">
        <header class="chat-header">
          <div>
            <p class="eyebrow">知识库问答</p>
            <h2>智能问答</h2>
          </div>
          <button type="button" class="ghost-btn" @click="clearChat" :disabled="isLoading">
            清空
          </button>
        </header>

        <div class="chat-history" ref="chatHistory">
          <div
            v-for="(message, index) in messages"
            :key="index"
            class="message"
            :class="message.sender"
          >
            <div class="avatar">{{ message.sender === 'user' ? '你' : 'AI' }}</div>
            <div class="bubble">
              <div class="sender">{{ message.sender === 'user' ? '你' : '助手' }}</div>
              <div class="text" v-html="formatMessage(message.text)"></div>
              <div v-if="message.metrics" class="metrics-row">
                <span>检索 {{ formatDuration(message.metrics.retrieval_time_ms) }}</span>
                <span>生成 {{ formatDuration(message.metrics.generation_time_ms) }}</span>
                <span>响应 {{ formatDuration(message.metrics.response_time_ms) }}</span>
              </div>
              <div v-if="message.sources && message.sources.length" class="sources-box">
                <div class="sources-title">参考文献</div>
                <ol class="sources-list">
                  <li v-for="(source, sourceIndex) in message.sources" :key="sourceIndex">
                    <pre>{{ source }}</pre>
                  </li>
                </ol>
              </div>
            </div>
          </div>
          <div v-if="isLoading" class="message bot">
            <div class="avatar">AI</div>
            <div class="bubble">
              <div class="sender">助手</div>
              <div class="typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>

        <form class="chat-input" @submit.prevent="sendMessage">
          <textarea
            v-model="userInput"
            @keydown.enter.exact.prevent="sendMessage"
            placeholder="请输入医疗健康相关问题..."
            :disabled="isLoading || !apiKeyConfigured"
            rows="1"
          ></textarea>
          <button type="submit" class="send-btn" :disabled="isLoading || !apiKeyConfigured || userInput.trim() === ''">
            {{ isLoading ? '思考中' : '发送' }}
          </button>
        </form>
      </section>

    <ApiKeyModal
      :visible="showApiKeyModal"
      :loading="isSubmittingApiKey"
      :error="apiKeyError"
      :configured="apiKeyConfigured"
      @submit="submitApiKey"
      @remove="clearApiKey"
      @close="closeApiKeyModal"
    />
  </div>
</template>

<script>
import axios from 'axios';
import { marked } from 'marked';
import ApiKeyModal from './components/ApiKeyModal.vue';

export default {
  name: 'App',
  components: {
    ApiKeyModal,
  },
  data() {
    return {
      messages: [
        { sender: 'bot', text: '你好！我是你的个人智能助手。你可以问我医疗健康相关问题，我会结合知识库检索结果回答。', sources: [] }
      ],
      userInput: '',
      isLoading: false,
      apiKeyConfigured: false,
      apiKeyError: '',
      showApiKeyModal: false,
      isSubmittingApiKey: false,
      isLoadingPrompts: false,
      selectedTopK: 3,
      fallbackPrompts: [
        'What can cause chest pain after exercise?',
        'How should I understand persistent headaches?',
        'What are common causes of stomach pain?'
      ],
      samplePrompts: [],
      ingestStatus: {
        status: 'idle',
        running: false,
        mode: null,
        phase: null,
        processed: 0,
        total: 0,
        added: 0,
        skipped: 0,
        collection_count: 0,
        started_at: null,
        finished_at: null,
        error: null,
      },
      knowledgeBaseParameters: null,
      knowledgeBaseParametersError: '',
      isLoadingKnowledgeBaseParameters: false,
      ingestPollTimer: null,
      monitoringPollTimer: null,
      monitoringError: '',
      monitoringStatus: {
        request_count: 0,
        average_response_time_ms: 0,
        last_response_time_ms: 0,
        last_retrieval_time_ms: 0,
        last_generation_time_ms: 0,
        last_updated_at: null,
        resources: {},
      },
    };
  },
  computed: {
    userMessageCount() {
      return this.messages.filter((message) => message.sender === 'user').length;
    },
    isIngestRunning() {
      return Boolean(this.ingestStatus.running);
    },
    ingestStatusLabel() {
      const labels = {
        idle: '空闲',
        running: this.ingestStatus.mode === 'rebuild' ? '重建中' : '更新中',
        succeeded: '已完成',
        failed: '失败',
      };
      return labels[this.ingestStatus.status] || this.ingestStatus.status;
    },
    ingestProgressPercent() {
      if (!this.ingestStatus.total) {
        return this.isIngestRunning ? 12 : 0;
      }
      return Math.min(100, Math.round((this.ingestStatus.processed / this.ingestStatus.total) * 100));
    },
    ingestProgressText() {
      if (this.isIngestRunning) {
        return `${this.ingestStatus.processed || 0}/${this.ingestStatus.total || 0} · 新增 ${this.ingestStatus.added || 0} · 跳过 ${this.ingestStatus.skipped || 0}`;
      }
      if (this.ingestStatus.status === 'succeeded') {
        return `完成 · 新增 ${this.ingestStatus.added || 0} · 跳过 ${this.ingestStatus.skipped || 0}`;
      }
      if (this.ingestStatus.status === 'failed') {
        return '任务失败';
      }
      return '等待任务';
    },
    retrievalTopK() {
      return this.knowledgeBaseParameters?.retrieval_top_k || 3;
    },
    apiKeyStatusLabel() {
      return this.apiKeyConfigured ? 'API Key 已配置' : 'API Key 待配置';
    },
    monitoringResources() {
      return this.monitoringStatus.resources || {};
    },
    knowledgeBaseParameterItems() {
      const params = this.knowledgeBaseParameters || {};
      const collectionCount = this.ingestStatus.collection_count || params.collection_count;
      return [
        { label: '集合', value: params.collection_name || '-' },
        { label: '向量数', value: this.formatParameterNumber(collectionCount) },
        { label: 'TopK', value: this.formatParameterNumber(params.retrieval_top_k) },
        { label: '最大文档', value: this.formatMaxDocuments(params.max_documents) },
        { label: '批大小', value: this.formatParameterNumber(params.batch_size) },
        { label: 'Token 长度', value: this.formatParameterNumber(params.tokenize_max_length) },
        { label: '嵌入模型', value: params.embedding_model || '-' },
        { label: 'ONNX', value: params.onnx_model_file || '-' },
        { label: 'Provider', value: params.onnx_provider || '-' },
        { label: 'LLM', value: params.llm_model || '-' },
        { label: 'API', value: params.api_base || '-' },
        { label: 'Key', value: this.apiKeyConfigured ? '已配置' : '待配置' },
      ];
    },
  },
  methods: {
    formatParameterNumber(value) {
      if (value === null || value === undefined || value === '') {
        return '-';
      }
      return Number(value).toLocaleString();
    },
    formatMaxDocuments(value) {
      if (value === null || value === undefined || value === '') {
        return '-';
      }
      return Number(value) <= 0 ? '全部' : this.formatParameterNumber(value);
    },
    formatDuration(value) {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue) || numberValue <= 0) {
        return '-';
      }
      if (numberValue >= 1000) {
        return `${(numberValue / 1000).toFixed(2)}s`;
      }
      return `${numberValue.toFixed(0)}ms`;
    },
    formatPercent(value) {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return '-';
      }
      return `${numberValue.toFixed(1)}%`;
    },
    formatMegabytes(value) {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return '-';
      }
      return `${numberValue.toFixed(1)}MB`;
    },
    async loadSamplePrompts() {
      this.isLoadingPrompts = true;
      try {
        const response = await axios.get('/api/sample-prompts', {
          params: { limit: 3 },
        });
        const prompts = Array.isArray(response.data.prompts) ? response.data.prompts : [];
        this.samplePrompts = prompts.length > 0 ? prompts : this.getRandomFallbackPrompts();
      } catch (error) {
        console.error('抽取示例问题时出错:', error);
        this.samplePrompts = this.getRandomFallbackPrompts();
      } finally {
        this.isLoadingPrompts = false;
      }
    },
    getRandomFallbackPrompts() {
      return [...this.fallbackPrompts].sort(() => Math.random() - 0.5).slice(0, 3);
    },
    fillPrompt(prompt) {
      this.userInput = prompt;
    },
    clearApiKey() {
      this.apiKeyConfigured = false;
      this.showApiKeyModal = true;
      this.apiKeyError = '';
    },
    openKeyManager() {
      this.apiKeyError = '';
      this.showApiKeyModal = true;
    },
    closeApiKeyModal() {
      this.showApiKeyModal = false;
      this.apiKeyError = '';
    },
    async loadApiKeyStatus() {
      try {
        const response = await axios.get('/api/api-key/status');
        this.apiKeyConfigured = Boolean(response.data.configured);
        this.showApiKeyModal = !this.apiKeyConfigured;
        this.apiKeyError = '';
      } catch (error) {
        console.error('读取 API Key 状态时出错:', error);
        this.apiKeyConfigured = false;
        this.showApiKeyModal = true;
        if (error.request && !error.response) {
          this.apiKeyError = '网络请求失败，请检查网络连接后重试';
        } else {
          this.apiKeyError = '后端服务不可用，请稍后重试';
        }
      }
    },
    async submitApiKey(apiKey) {
      if (!apiKey || apiKey.trim() === '') {
        this.apiKeyError = 'API Key 不能为空';
        return;
      }

      this.isSubmittingApiKey = true;
      this.apiKeyError = '';
      try {
        await axios.post('/api/api-key', {
          api_key: apiKey.trim(),
        });
        this.apiKeyConfigured = true;
        this.showApiKeyModal = false;
        this.loadKnowledgeBaseParameters();
      } catch (error) {
        console.error('提交 API Key 时出错:', error);
        this.apiKeyConfigured = false;
        if (error.response) {
          this.apiKeyError = error.response.data?.detail || 'Key 验证失败，请检查后重试';
        } else if (error.request) {
          this.apiKeyError = '网络请求失败，请检查网络连接后重试';
        } else {
          this.apiKeyError = '后端服务不可用，请稍后重试';
        }
      } finally {
        this.isSubmittingApiKey = false;
      }
    },
    async loadIngestStatus() {
      try {
        const response = await axios.get('/api/ingest/status');
        this.ingestStatus = {
          ...this.ingestStatus,
          ...response.data,
        };
        if (this.ingestStatus.running) {
          this.ensureIngestPolling();
        } else {
          this.stopIngestPolling();
        }
      } catch (error) {
        console.error('读取知识库状态时出错:', error);
      }
    },
    async loadKnowledgeBaseParameters() {
      this.isLoadingKnowledgeBaseParameters = true;
      this.knowledgeBaseParametersError = '';
      try {
        const response = await axios.get('/api/knowledge-base/parameters');
        this.knowledgeBaseParameters = response.data;
        this.selectedTopK = response.data.retrieval_top_k;
      } catch (error) {
        console.error('读取知识库参数时出错:', error);
        this.knowledgeBaseParametersError = '参数读取失败';
      } finally {
        this.isLoadingKnowledgeBaseParameters = false;
      }
    },
    async loadMonitoringStatus() {
      try {
        const response = await axios.get('/api/monitoring');
        this.monitoringStatus = {
          ...this.monitoringStatus,
          ...response.data,
          resources: response.data.resources || {},
        };
        this.monitoringError = '';
      } catch (error) {
        console.error('读取监控指标时出错:', error);
        this.monitoringError = '监控读取失败';
      }
    },
    ensureIngestPolling() {
      if (this.ingestPollTimer) return;
      this.ingestPollTimer = window.setInterval(() => {
        this.loadIngestStatus();
      }, 2000);
    },
    stopIngestPolling() {
      if (!this.ingestPollTimer) return;
      window.clearInterval(this.ingestPollTimer);
      this.ingestPollTimer = null;
    },
    startMonitoringPolling() {
      if (this.monitoringPollTimer) return;
      this.monitoringPollTimer = window.setInterval(() => {
        this.loadMonitoringStatus();
      }, 5000);
    },
    stopMonitoringPolling() {
      if (!this.monitoringPollTimer) return;
      window.clearInterval(this.monitoringPollTimer);
      this.monitoringPollTimer = null;
    },
    async onTopKChange() {
      if (this._topKChanging) return;
      this._topKChanging = true;
      const previousValue = this.retrievalTopK;
      try {
        const response = await axios.patch('/api/knowledge-base/top-k', {
          top_k: this.selectedTopK,
        });
        this.knowledgeBaseParameters = response.data;
        this.selectedTopK = response.data.retrieval_top_k;
      } catch (error) {
        console.error('更新 Top-K 时出错:', error);
        this.selectedTopK = previousValue;
      } finally {
        this._topKChanging = false;
      }
    },
    clearChat() {
      this.messages = [
        { sender: 'bot', text: '聊天已清空。请输入新的问题，我会重新检索知识库。', sources: [] }
      ];
      this.scrollToBottom();
    },
    async sendMessage() {
      if (this.userInput.trim() === '' || this.isLoading) return;

      const userMessage = this.userInput;
      this.messages.push({ sender: 'user', text: userMessage, sources: [] });
      this.userInput = '';
      this.isLoading = true;
      this.scrollToBottom();

      try {
        const response = await axios.post('/api/ask', {
          query: userMessage,
        });

        const sources = Array.isArray(response.data.sources) ? response.data.sources : [];
        this.messages.push({
          sender: 'bot',
          text: response.data.answer,
          sources,
          metrics: response.data.metrics || null,
        });
        if (response.data.metrics) {
          this.monitoringStatus = {
            ...this.monitoringStatus,
            average_response_time_ms: response.data.metrics.average_response_time_ms,
            last_response_time_ms: response.data.metrics.response_time_ms,
            last_retrieval_time_ms: response.data.metrics.retrieval_time_ms,
            last_generation_time_ms: response.data.metrics.generation_time_ms,
          };
        }
        this.loadMonitoringStatus();

      } catch (error) {
        console.error('发送消息时出错:', error);
        if (error.response?.status === 401) {
          this.apiKeyConfigured = false;
          this.showApiKeyModal = true;
          this.apiKeyError = error.response?.data?.detail || 'Key 已失效或余额不足，请更换后重试';
          this.messages.push({ sender: 'bot', text: 'API Key 已失效，请重新输入后再继续提问。', sources: [] });
        } else if (error.response) {
          this.messages.push({ sender: 'bot', text: '抱歉，我遇到了一个错误，请稍后再试。', sources: [] });
        } else if (error.request) {
          this.messages.push({ sender: 'bot', text: '网络请求失败，请检查网络连接后重试。', sources: [] });
        } else {
          this.messages.push({ sender: 'bot', text: '后端服务不可用，请稍后重试。', sources: [] });
        }
      } finally {
        this.isLoading = false;
        this.scrollToBottom();
      }
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.chatHistory;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },
    formatMessage(text) {
      return marked(text);
    }
  },
  mounted() {
    this.loadApiKeyStatus();
    this.loadSamplePrompts();
    this.loadIngestStatus();
    this.loadKnowledgeBaseParameters();
    this.loadMonitoringStatus();
    this.startMonitoringPolling();
  },
  beforeUnmount() {
    this.stopIngestPolling();
    this.stopMonitoringPolling();
  }
};
</script>

<style>
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
    --border-strong: #cbd5e1;
    --surface-muted: #f8fafc;
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    --shadow-card: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
    --shadow-elevated: 0 4px 12px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04);
    --gradient-brand: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
    --gradient-hero: linear-gradient(180deg, #f8fafc 0%, #f0f4f8 100%);
  }

  * { box-sizing: border-box; }

  html, body {
    margin: 0;
    min-height: 100%;
    color: var(--text);
    background: var(--bg);
  }

  body, button, input, textarea {
    font-family: "Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", ui-sans-serif, sans-serif;
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
    padding: 16px;
    gap: 16px;
    margin: 0 auto;
    background: var(--bg);
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 16px;
    overflow-y: auto;
    scrollbar-color: #c7d0dd transparent;
    scrollbar-width: thin;
  }

  .chat-shell {
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-card);
    background: var(--surface);
  }

  /* Brand Card */
  .brand-card {
    padding: 20px;
    border-radius: var(--radius);
    background: var(--gradient-brand);
    color: #fff;
    box-shadow: var(--shadow-elevated);
  }
  .brand-card .brand-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .brand-mark {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    background: rgba(255,255,255,0.2);
    backdrop-filter: blur(4px);
    border-radius: var(--radius-sm);
    font-size: 16px;
    font-weight: 800;
  }
  .brand-card h1 {
    font-size: 16px;
    font-weight: 700;
    margin: 0;
  }
  .brand-card p {
    font-size: 12px;
    opacity: 0.85;
    margin: 3px 0 0 0;
  }

  /* Card Base */
  .card {
    padding: 16px;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    background: var(--surface);
    box-shadow: var(--shadow-card);
  }
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 12px;
  }
  .card-label {
    color: var(--muted);
    font-size: 13px;
    font-weight: 700;
  }

  /* Status Row */
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 700;
    color: var(--success);
  }
  .status-row.offline { color: var(--warning); }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: 0 0 8px;
  }
  .status-dot.online { background: var(--success); }
  .status-dot.offline { background: var(--warning); }

  .status-badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
  }
  .status-badge.ready { color: var(--success); background: var(--success-soft); }
  .status-badge.waiting { color: var(--warning); background: var(--warning-soft); }

  .stat-inline {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
  .stat-value {
    font-size: 22px;
    line-height: 1;
    font-weight: 700;
  }
  .stat-label {
    color: var(--muted);
    font-size: 12px;
  }

  .gear-button {
    border: 1px solid var(--border);
    border-radius: var(--radius-xs);
    background: var(--surface);
    color: var(--muted);
    font-size: 16px;
    line-height: 1;
    padding: 2px 6px;
    cursor: pointer;
    transition: border-color 160ms ease, color 160ms ease;
  }
  .gear-button:hover {
    border-color: var(--primary);
    color: var(--primary);
  }

  /* TopK Select */
  .topk-select {
    padding: 0 2px;
    border: none;
    border-radius: 4px;
    color: var(--primary);
    background: var(--primary-soft);
    font: inherit;
    font-size: 22px;
    font-weight: inherit;
    line-height: 1;
    cursor: pointer;
    appearance: none;
    -webkit-appearance: none;
  }
  .topk-select:focus {
    outline: 2px solid rgba(37,99,235,0.25);
    outline-offset: 2px;
  }
  .topk-select:disabled {
    color: var(--muted);
    background: var(--primary-soft);
    cursor: not-allowed;
  }

  /* Monitor Grid */
  .monitor-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .monitor-kpi {
    display: grid;
    gap: 4px;
    padding: 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--gradient-hero);
  }
  .kpi-label {
    color: var(--muted);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .kpi-value {
    font-size: 17px;
    font-weight: 700;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    line-height: 1.2;
  }
  .monitor-count {
    color: var(--primary);
    font-size: 12px;
    font-weight: 700;
  }
  .monitor-error {
    margin-top: 10px;
    padding: 8px 10px;
    border: 1px solid #ffe1a6;
    border-radius: var(--radius);
    color: #936000;
    background: #fff9ec;
    font-size: 12px;
    line-height: 1.4;
  }

  /* Ingest */
  .ingest-badge {
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
  }
  .ingest-badge.idle { color: var(--muted); background: #eef2f6; }
  .ingest-badge.running { color: var(--primary); background: var(--primary-soft); }
  .ingest-badge.succeeded { color: var(--success); background: var(--success-soft); }
  .ingest-badge.failed { color: var(--danger); background: var(--danger-soft); }

  .ingest-bar {
    height: 8px;
    overflow: hidden;
    border-radius: 999px;
    background: #edf1f6;
    margin-bottom: 8px;
  }
  .ingest-bar-fill {
    height: 100%;
    border-radius: inherit;
    background: var(--gradient-brand);
    transition: width 200ms ease;
  }

  .ingest-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    color: var(--muted);
    font-size: 12px;
    line-height: 1.4;
  }

  .ingest-error {
    margin-top: 8px;
    padding: 8px 10px;
    border: 1px solid #ffd6d2;
    border-radius: var(--radius);
    color: var(--danger);
    background: var(--danger-soft);
    font-size: 12px;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }

  /* Param Grid */
  .param-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 12px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
  .param-item {
    display: flex;
    justify-content: space-between;
    gap: 6px;
    font-size: 12px;
    line-height: 1.35;
  }
  .param-item .name { color: var(--muted); }
  .param-item .val {
    color: var(--text);
    font-weight: 600;
    text-align: right;
    overflow-wrap: anywhere;
  }

  .kb-params-error {
    margin-top: 8px;
    padding: 8px 10px;
    border: 1px solid #ffe1a6;
    border-radius: var(--radius);
    color: #936000;
    background: #fff9ec;
    font-size: 12px;
    line-height: 1.4;
  }

  /* Prompt Section */
  .prompt-list {
    display: grid;
    gap: 8px;
  }
  .prompt-btn {
    display: block;
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    background: var(--surface);
    font-size: 13px;
    line-height: 1.45;
    text-align: left;
    text-wrap: pretty;
    cursor: pointer;
    transition: border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
  }
  .prompt-btn:hover:not(:disabled) {
    border-color: var(--primary);
    background: var(--primary-soft);
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
  }
  .prompt-btn:focus-visible {
    outline: 3px solid rgba(37,99,235,0.16);
    outline-offset: 2px;
  }
  .prompt-btn:disabled {
    color: #98a2b3;
    background: #f3f5f8;
  }

  .refresh-chip {
    height: 28px;
    padding: 0 12px;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--primary);
    background: var(--surface);
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    transition: border-color 160ms ease, background 160ms ease;
  }
  .refresh-chip:hover:not(:disabled) {
    border-color: var(--primary);
    background: var(--primary-soft);
  }
  .refresh-chip:disabled {
    color: #98a2b3;
    background: #f3f5f8;
    cursor: not-allowed;
  }

  /* Chat Header */
  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 18px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--gradient-hero);
  }
  .eyebrow {
    margin: 0 0 4px 0;
    color: var(--primary);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .chat-header h2 {
    margin: 0;
    font-size: 22px;
    line-height: 1.2;
  }

  .ghost-btn {
    min-width: 68px;
    height: 36px;
    padding: 0 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    background: var(--surface);
    font-weight: 700;
    cursor: pointer;
    transition: border-color 160ms ease, background 160ms ease, color 160ms ease;
  }
  .ghost-btn:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--primary-soft);
  }
  .ghost-btn:focus-visible {
    outline: 3px solid rgba(37,99,235,0.16);
    outline-offset: 2px;
  }
  .ghost-btn:disabled {
    color: #98a2b3;
    background: #f3f5f8;
  }

  /* Chat History */
  .chat-history {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 24px;
    background: #f8fafc;
    scrollbar-color: #c7d0dd transparent;
    scrollbar-width: thin;
  }

  /* Message Layout */
  .message {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 16px;
  }
  .message.user {
    flex-direction: row-reverse;
  }

  .avatar {
    display: grid;
    width: 34px;
    height: 34px;
    flex: 0 0 34px;
    place-items: center;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 800;
    background: var(--surface);
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .message.user .avatar {
    color: #fff;
    background: var(--gradient-brand);
    border: none;
  }

  .bubble {
    width: fit-content;
    max-width: min(720px, 78%);
    padding: 12px 16px;
    border-radius: var(--radius);
    line-height: 1.6;
  }
  .message.bot .bubble {
    border: 1px solid var(--border);
    background: var(--surface);
    box-shadow: var(--shadow-card);
    border-top-left-radius: 4px;
  }
  .message.user .bubble {
    color: #fff;
    background: var(--gradient-brand);
    box-shadow: var(--shadow-elevated);
    border-top-right-radius: 4px;
  }

  .sender {
    margin-bottom: 4px;
    font-size: 12px;
    font-weight: 700;
  }
  .message.user .sender {
    color: rgba(255,255,255,0.78);
  }

  .text {
    overflow-wrap: anywhere;
    font-size: 15px;
    line-height: 1.7;
    text-wrap: pretty;
  }
  .text :first-child { margin-top: 0; }
  .text :last-child { margin-bottom: 0; }
  .text p { margin: 8px 0; }
  .text ul, .text ol { margin: 8px 0; padding-left: 22px; }
  .text li + li { margin-top: 4px; }
  .text a { color: var(--primary-dark); }
  .message.user .text a { color: #fff; }

  /* Metrics Row */
  .metrics-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
  }
  .metrics-row span {
    padding: 3px 7px;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    background: var(--primary-soft);
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 11px;
    line-height: 1.4;
  }

  /* Sources Box */
  .sources-box {
    display: grid;
    gap: 10px;
    max-width: 100%;
    margin-top: 12px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--gradient-hero);
  }
  .sources-title {
    font-size: 13px;
    font-weight: 700;
    line-height: 1.3;
  }
  .sources-title::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    margin-right: 6px;
    vertical-align: middle;
  }
  .sources-list {
    display: grid;
    gap: 8px;
    margin: 0;
    padding-left: 20px;
  }
  .sources-list li {
    padding-left: 2px;
    color: var(--muted);
  }
  .sources-list pre {
    margin: 0;
    color: var(--text);
    background: transparent;
    font-size: 13px;
  }

  /* Chat Input */
  .chat-input {
    display: flex;
    gap: 10px;
    padding: 16px 20px;
    border-top: 1px solid var(--border);
    background: var(--surface);
  }
  .chat-input textarea {
    flex: 1;
    min-height: 48px;
    max-height: 140px;
    resize: vertical;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 13px 14px;
    color: var(--text);
    background: var(--surface);
    line-height: 1.45;
    outline: none;
    transition: border-color 160ms ease, box-shadow 160ms ease;
  }
  .chat-input textarea::placeholder {
    color: #98a2b3;
  }
  .chat-input textarea:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12);
  }

  .send-btn {
    min-width: 88px;
    min-height: 48px;
    padding: 0 16px;
    border: none;
    border-radius: var(--radius-sm);
    color: #fff;
    background: var(--gradient-brand);
    font-weight: 800;
    box-shadow: 0 2px 6px rgba(37,99,235,0.25);
    cursor: pointer;
    transition: opacity 160ms ease, transform 160ms ease, box-shadow 160ms ease;
  }
  .send-btn:hover:not(:disabled) {
    box-shadow: 0 4px 12px rgba(37,99,235,0.35);
    transform: translateY(-1px);
  }
  .send-btn:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: 0 1px 3px rgba(37,99,235,0.25);
  }
  .send-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* Typing */
  .typing {
    display: flex;
    gap: 5px;
    padding-top: 8px;
  }
  .typing span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--muted);
    animation: pulse 1s infinite ease-in-out;
  }
  .typing span:nth-child(2) { animation-delay: 0.14s; }
  .typing span:nth-child(3) { animation-delay: 0.28s; }

  /* pre/code */
  pre {
    max-width: 100%;
    margin: 10px 0;
    padding: 12px;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    background: #f3f6fa;
    white-space: pre-wrap;
    word-wrap: break-word;
  }
  .message.user pre {
    color: #fff;
    background: rgba(255,255,255,0.15);
  }
  code {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 0.92em;
  }

  @keyframes pulse {
    0%, 80%, 100% { opacity: 0.35; transform: translateY(0); }
    40% { opacity: 1; transform: translateY(-3px); }
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
  }
  @media (max-width: 900px) {
    #app { grid-template-columns: 1fr; height: auto; min-height: 100vh; padding: 12px; }
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
</style>
