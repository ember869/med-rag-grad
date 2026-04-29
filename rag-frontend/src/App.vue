<template>
  <div id="app">
    <main class="workspace">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">R</div>
          <div>
            <h1>RAG 医疗助手</h1>
            <p>基于知识库回答</p>
          </div>
        </div>
        <div class="status-panel">
          <div :class="['status-row', { warning: !apiKeyConfigured }]">
            <span class="status-dot"></span>
            <span>{{ apiKeyStatusLabel }}</span>
            <button
              v-if="apiKeyConfigured"
              type="button"
              class="gear-button"
              title="管理 API Key"
              @click="openKeyManager"
            >
              &#9881;
            </button>
          </div>
          <div class="metric">
            <strong>{{ userMessageCount }}</strong>
            <span>本轮问题</span>
          </div>
          <div class="metric">
            <strong class="topk-metric">
              Top
              <select
                class="topk-select"
                v-model="selectedTopK"
                @change="onTopKChange"
                :disabled="isLoading"
              >
                <option :value="1">1</option>
                <option :value="3">3</option>
                <option :value="5">5</option>
                <option :value="10">10</option>
              </select>
            </strong>
            <span>检索来源</span>
          </div>
        </div>
        <div class="monitor-panel">
          <div class="monitor-header">
            <span>前端监控</span>
            <strong>{{ monitoringStatus.request_count || 0 }} 次</strong>
          </div>
          <div class="monitor-grid">
            <div class="monitor-item">
              <span>单次检索</span>
              <strong>{{ formatDuration(monitoringStatus.last_retrieval_time_ms) }}</strong>
            </div>
            <div class="monitor-item">
              <span>回答生成</span>
              <strong>{{ formatDuration(monitoringStatus.last_generation_time_ms) }}</strong>
            </div>
            <div class="monitor-item">
              <span>平均响应</span>
              <strong>{{ formatDuration(monitoringStatus.average_response_time_ms) }}</strong>
            </div>
            <div class="monitor-item">
              <span>本次响应</span>
              <strong>{{ formatDuration(monitoringStatus.last_response_time_ms) }}</strong>
            </div>
          </div>
          <div class="resource-strip">
            <div>
              <span>CPU</span>
              <strong>{{ formatPercent(monitoringResources.cpu_percent) }}</strong>
            </div>
            <div>
              <span>内存</span>
              <strong>{{ formatMegabytes(monitoringResources.memory_rss_mb) }}</strong>
            </div>
            <div>
              <span>系统内存</span>
              <strong>{{ formatPercent(monitoringResources.system_memory_percent) }}</strong>
            </div>
          </div>
          <div v-if="monitoringError" class="monitor-error">{{ monitoringError }}</div>
        </div>
        <div class="ingest-panel">
          <div class="ingest-header">
            <span>知识库状态</span>
            <strong :class="['ingest-badge', ingestStatus.status]">{{ ingestStatusLabel }}</strong>
          </div>
          <div class="ingest-progress">
            <div class="ingest-progress-bar" :style="{ width: ingestProgressPercent + '%' }"></div>
          </div>
          <div class="ingest-meta">
            <span>{{ ingestProgressText }}</span>
            <span>{{ ingestStatus.collection_count || 0 }} 向量</span>
          </div>
          <div v-if="ingestStatus.error" class="ingest-error">{{ ingestStatus.error }}</div>
          <div class="kb-params">
            <div class="kb-params-title">
              <span>运行参数</span>
              <span v-if="isLoadingKnowledgeBaseParameters">读取中</span>
            </div>
            <div v-if="knowledgeBaseParametersError" class="kb-params-error">
              {{ knowledgeBaseParametersError }}
            </div>
            <dl v-else class="kb-param-list">
              <template v-for="item in knowledgeBaseParameterItems" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </template>
            </dl>
          </div>
        </div>
        <div class="hint-header">
          <span>随机问题</span>
          <button type="button" @click="loadSamplePrompts" :disabled="isLoading || isLoadingPrompts">
            {{ isLoadingPrompts ? '抽取中' : '换一批' }}
          </button>
        </div>
        <div class="hint-list">
          <button
            v-for="prompt in samplePrompts"
            :key="prompt"
            type="button"
            @click="fillPrompt(prompt)"
            :disabled="isLoading"
          >
            {{ prompt }}
          </button>
        </div>
      </aside>

      <section class="chat-shell">
        <header class="chat-header">
          <div>
            <p class="eyebrow">知识库问答</p>
            <h2>智能问答</h2>
          </div>
          <div class="header-actions">
            <button type="button" class="ghost-button" @click="clearChat" :disabled="isLoading">
              清空
            </button>
          </div>
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
              <div v-if="message.metrics" class="message-metrics">
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
            <div class="bubble loading-bubble">
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
          <button type="submit" :disabled="isLoading || !apiKeyConfigured || userInput.trim() === ''">
            {{ isLoading ? '思考中' : '发送' }}
          </button>
        </form>
      </section>
    </main>

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
      const previousValue = this.retrievalTopK;
      try {
        await axios.patch('/api/knowledge-base/top-k', {
          top_k: this.selectedTopK,
        });
        await this.loadKnowledgeBaseParameters();
      } catch (error) {
        console.error('更新 Top-K 时出错:', error);
        this.selectedTopK = previousValue;
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
    --bg: #f5f7fb;
    --surface: #ffffff;
    --surface-muted: #f8fafc;
    --text: #172033;
    --muted: #667085;
    --border: #e4e8ef;
    --border-strong: #cfd7e3;
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --primary-soft: #eef4ff;
    --success: #15966b;
    --radius: 8px;
    --shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  * {
    box-sizing: border-box;
  }

  html,
  body {
    margin: 0;
    min-height: 100%;
    color: var(--text);
    background: var(--bg);
  }

  body,
  button,
  input,
  textarea {
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", ui-sans-serif, sans-serif;
    letter-spacing: 0;
  }

  button,
  input,
  textarea {
    font: inherit;
  }

  button {
    cursor: pointer;
  }

  button:disabled,
  input:disabled,
  textarea:disabled {
    cursor: not-allowed;
  }

  #app {
    min-height: 100vh;
    padding: 24px;
    background: var(--bg);
  }

  .workspace {
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 16px;
    width: min(1120px, 100%);
    height: calc(100dvh - 48px);
    min-height: 640px;
    margin: 0 auto;
  }

  .sidebar,
  .chat-shell {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: var(--shadow);
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 18px;
    min-width: 0;
    padding: 20px;
    overflow-y: auto;
    scrollbar-color: #c7d0dd transparent;
    scrollbar-width: thin;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .brand-mark {
    display: grid;
    width: 40px;
    height: 40px;
    flex: 0 0 40px;
    place-items: center;
    border-radius: var(--radius);
    color: var(--primary);
    background: var(--primary-soft);
    font-size: 18px;
    font-weight: 800;
  }

  .brand h1,
  .brand p,
  .chat-header h2,
  .eyebrow {
    margin: 0;
  }

  .brand h1 {
    font-size: 17px;
    line-height: 1.25;
    text-wrap: pretty;
  }

  .brand p {
    margin-top: 3px;
    color: var(--muted);
    font-size: 12px;
  }

  .status-panel {
    display: grid;
    gap: 10px;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface-muted);
  }

  .monitor-panel {
    display: grid;
    gap: 12px;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
  }

  .monitor-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    color: var(--muted);
    font-size: 13px;
    font-weight: 700;
  }

  .monitor-header strong {
    color: var(--primary);
    font-size: 12px;
  }

  .monitor-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .monitor-item {
    display: grid;
    gap: 4px;
    min-width: 0;
    padding: 9px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface-muted);
  }

  .monitor-item span,
  .resource-strip span {
    color: var(--muted);
    font-size: 11px;
    line-height: 1.25;
  }

  .monitor-item strong {
    color: #263143;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 14px;
    line-height: 1.2;
    overflow-wrap: anywhere;
  }

  .resource-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1px;
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--border);
  }

  .resource-strip div {
    display: grid;
    gap: 4px;
    min-width: 0;
    padding: 8px;
    background: #ffffff;
  }

  .resource-strip strong {
    color: #263143;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 12px;
    line-height: 1.2;
    overflow-wrap: anywhere;
  }

  .monitor-error {
    padding: 8px 10px;
    border: 1px solid #ffe1a6;
    border-radius: var(--radius);
    color: #936000;
    background: #fff9ec;
    font-size: 12px;
    line-height: 1.4;
  }

  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--success);
    font-size: 13px;
    font-weight: 700;
  }

  .status-row.warning {
    color: #936000;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
  }

  .status-row.warning .status-dot {
    background: #f59e0b;
  }

  .gear-button {
    margin-left: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--muted);
    font-size: 16px;
    line-height: 1;
    padding: 2px 6px;
    cursor: pointer;
    transition: border-color 160ms var(--ease), color 160ms var(--ease);
  }

  .gear-button:hover {
    border-color: var(--primary);
    color: var(--primary);
  }

  .ingest-panel {
    display: grid;
    gap: 10px;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
  }

  .ingest-header,
  .ingest-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .ingest-header {
    color: var(--muted);
    font-size: 13px;
    font-weight: 700;
  }

  .ingest-badge {
    min-width: 58px;
    padding: 4px 8px;
    border-radius: 999px;
    color: #475467;
    background: #eef2f6;
    font-size: 12px;
    text-align: center;
  }

  .ingest-badge.running {
    color: var(--primary);
    background: var(--primary-soft);
  }

  .ingest-badge.succeeded {
    color: var(--success);
    background: #eaf8f2;
  }

  .ingest-badge.failed {
    color: #b42318;
    background: #fff1f0;
  }

  .ingest-progress {
    height: 8px;
    overflow: hidden;
    border-radius: 999px;
    background: #edf1f6;
  }

  .ingest-progress-bar {
    height: 100%;
    border-radius: inherit;
    background: var(--primary);
    transition: width 200ms var(--ease);
  }

  .ingest-meta {
    color: var(--muted);
    font-size: 12px;
    line-height: 1.4;
  }

  .ingest-error {
    padding: 8px 10px;
    border: 1px solid #ffd6d2;
    border-radius: var(--radius);
    color: #b42318;
    background: #fff8f7;
    font-size: 12px;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }

  .kb-params {
    display: grid;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }

  .kb-params-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
  }

  .kb-params-title span:last-child {
    color: var(--primary);
    font-weight: 600;
  }

  .kb-param-list {
    display: grid;
    grid-template-columns: minmax(68px, auto) minmax(0, 1fr);
    gap: 7px 10px;
    margin: 0;
  }

  .kb-param-list dt,
  .kb-param-list dd {
    min-width: 0;
    margin: 0;
    font-size: 12px;
    line-height: 1.35;
  }

  .kb-param-list dt {
    color: var(--muted);
  }

  .kb-param-list dd {
    color: #263143;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    text-align: right;
    overflow-wrap: anywhere;
  }

  .kb-params-error {
    padding: 8px 10px;
    border: 1px solid #ffe1a6;
    border-radius: var(--radius);
    color: #936000;
    background: #fff9ec;
    font-size: 12px;
    line-height: 1.4;
  }

  .metric {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }

  .metric strong {
    font-size: 22px;
    line-height: 1;
  }

  .metric span,
  .sender,
  .eyebrow {
    color: var(--muted);
    font-size: 12px;
  }

  .hint-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    color: var(--muted);
    font-size: 13px;
    font-weight: 700;
  }

  .hint-list {
    display: grid;
    gap: 8px;
  }

  .hint-list button,
  .hint-header button,
  .ghost-button {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    background: var(--surface);
    transition:
      border-color 160ms var(--ease),
      background 160ms var(--ease),
      color 160ms var(--ease);
  }

  .hint-header button {
    height: 30px;
    padding: 0 10px;
    color: var(--primary);
    font-size: 13px;
  }

  .hint-list button {
    min-height: 44px;
    padding: 10px 11px;
    text-align: left;
    color: #344054;
    line-height: 1.4;
    text-wrap: pretty;
  }

  .hint-list button:hover:not(:disabled),
  .hint-header button:hover:not(:disabled),
  .ghost-button:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--primary-soft);
  }

  .hint-list button:focus-visible,
  .hint-header button:focus-visible,
  .ghost-button:focus-visible,
  .chat-input button:focus-visible,
  input:focus-visible,
  textarea:focus-visible {
    outline: 3px solid rgba(37, 99, 235, 0.16);
    outline-offset: 2px;
  }

  .hint-list button:disabled,
  .hint-header button:disabled,
  .ghost-button:disabled {
    color: #98a2b3;
    background: #f3f5f8;
  }

  .chat-shell {
    display: flex;
    min-width: 0;
    flex-direction: column;
    overflow: hidden;
  }

  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 18px 22px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .eyebrow {
    margin-bottom: 4px;
    font-weight: 700;
  }

  .chat-header h2 {
    font-size: 22px;
    line-height: 1.2;
  }

  .ghost-button {
    min-width: 68px;
    height: 36px;
    padding: 0 12px;
    font-weight: 700;
  }

  .chat-history {
    flex: 1;
    overflow-y: auto;
    padding: 22px;
    background: #fbfcfe;
    scrollbar-color: #c7d0dd transparent;
    scrollbar-width: thin;
  }

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
    color: var(--primary);
    background: var(--primary-soft);
    font-size: 12px;
    font-weight: 800;
  }

  .message.user .avatar {
    color: #ffffff;
    background: var(--primary);
  }

  .bubble {
    width: fit-content;
    max-width: min(720px, 78%);
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
  }

  .message.user .bubble {
    color: #ffffff;
    border-color: var(--primary);
    background: var(--primary);
  }

  .sender {
    margin-bottom: 4px;
    font-weight: 700;
  }

  .message.user .sender {
    color: rgba(255, 255, 255, 0.78);
  }

  .text {
    overflow-wrap: anywhere;
    font-size: 15px;
    line-height: 1.7;
    text-wrap: pretty;
  }

  .text :first-child {
    margin-top: 0;
  }

  .text :last-child {
    margin-bottom: 0;
  }

  .text p {
    margin: 8px 0;
  }

  .text ul,
  .text ol {
    margin: 8px 0;
    padding-left: 22px;
  }

  .text li + li {
    margin-top: 4px;
  }

  .text a {
    color: var(--primary-dark);
  }

  .message.user .text a {
    color: #ffffff;
  }

  .sources-box {
    display: grid;
    gap: 10px;
    max-width: 100%;
    margin-top: 12px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface-muted);
  }

  .message-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
  }

  .message-metrics span {
    padding: 3px 7px;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    background: var(--surface-muted);
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 11px;
    line-height: 1.4;
  }

  .sources-title {
    color: var(--muted);
    font-size: 13px;
    font-weight: 800;
    line-height: 1.3;
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
    color: #263143;
    background: #ffffff;
  }

  .chat-input {
    display: flex;
    gap: 10px;
    padding: 14px;
    border-top: 1px solid var(--border);
    background: var(--surface);
  }

  textarea {
    flex: 1;
    min-height: 48px;
    max-height: 140px;
    resize: vertical;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius);
    padding: 13px 14px;
    color: var(--text);
    background: var(--surface);
    line-height: 1.45;
    outline: none;
    transition:
      border-color 160ms var(--ease),
      background 160ms var(--ease);
  }

  textarea::placeholder {
    color: #98a2b3;
  }

  textarea:focus {
    border-color: var(--primary);
    background: #ffffff;
  }

  .chat-input button {
    width: 88px;
    min-height: 48px;
    border: 1px solid var(--primary);
    border-radius: var(--radius);
    color: #ffffff;
    background: var(--primary);
    font-weight: 800;
    transition:
      background 160ms var(--ease),
      border-color 160ms var(--ease);
  }

  .chat-input button:hover:not(:disabled) {
    border-color: var(--primary-dark);
    background: var(--primary-dark);
  }

  .chat-input button:disabled {
    border-color: #b7c0ce;
    background: #b7c0ce;
  }


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

  .typing span:nth-child(2) {
    animation-delay: 0.14s;
  }

  .typing span:nth-child(3) {
    animation-delay: 0.28s;
  }

  pre {
    max-width: 100%;
    margin: 10px 0;
    padding: 12px;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: #263143;
    background: #f3f6fa;
    white-space: pre-wrap;
    word-wrap: break-word;
  }

  code {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 0.92em;
  }

  .message.user pre {
    border-color: rgba(255, 255, 255, 0.28);
    color: #ffffff;
    background: rgba(255, 255, 255, 0.12);
  }

  @keyframes pulse {
    0%,
    80%,
    100% {
      opacity: 0.35;
      transform: translateY(0);
    }

    40% {
      opacity: 1;
      transform: translateY(-3px);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      transition-duration: 0.01ms !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
    }
  }

  @media (max-width: 900px) {
    #app {
      padding: 14px;
    }

    .workspace {
      grid-template-columns: 1fr;
      height: auto;
      min-height: calc(100dvh - 28px);
    }

    .sidebar {
      gap: 14px;
    }

    .status-panel {
      grid-template-columns: 1fr 1fr;
    }

    .monitor-panel {
      grid-template-columns: minmax(220px, 0.8fr) minmax(280px, 1fr);
      align-items: start;
    }

    .monitor-header,
    .resource-strip,
    .monitor-error {
      grid-column: 1 / -1;
    }

    .status-row {
      grid-column: 1 / -1;
    }

    .ingest-panel {
      grid-template-columns: 1fr;
    }

    .hint-list {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .chat-shell {
      min-height: 68dvh;
    }
  }

  @media (max-width: 640px) {
    #app {
      padding: 10px;
    }

    .sidebar,
    .chat-header,
    .chat-history,
    .chat-input {
      padding: 14px;
    }

    .status-panel,
    .monitor-panel,
    .monitor-grid,
    .resource-strip,
    .hint-list {
      grid-template-columns: 1fr;
    }

    .chat-header {
      align-items: flex-start;
      flex-direction: column;
    }

    .header-actions,
    .ghost-button {
      width: 100%;
    }

    .chat-input {
      flex-direction: column;
    }

    .chat-input button {
      width: 100%;
    }

    .bubble {
      max-width: calc(100vw - 88px);
    }
  }
.topk-metric {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}

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
  outline: 2px solid rgba(37, 99, 235, 0.25);
  outline-offset: 2px;
}

.topk-select:disabled {
  color: #98a2b3;
  background: #f3f5f8;
  cursor: not-allowed;
}
</style>
