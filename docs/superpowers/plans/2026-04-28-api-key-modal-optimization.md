# ApiKeyModal 组件拆分与优化——实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 API Key 输入弹窗从 App.vue 拆分为独立组件 ApiKeyModal.vue，增加 Key 管理能力（换 Key/移除 Key）和 UX 增强（可见性切换/ESC关闭/遮罩关闭/过渡动画/错误分类）。

**Architecture:** 新建 `src/components/ApiKeyModal.vue` 作为纯展示组件，通过 props 接收状态，通过 events 向上传递操作。App.vue 持有所有业务逻辑和 API 调用，精简弹窗模板。

**Tech Stack:** Vue 3 Options API（与 App.vue 保持一致）、plain CSS（不引入 CSS 框架）

**Note:** 本项目无自动化测试，验证步骤为手动检查 UI 行为。

---

## 文件规划

| 文件 | 职责 |
|------|------|
| `rag-frontend/src/components/ApiKeyModal.vue` | 弹窗的模板、样式、内部交互（密码切换/模式切换/键盘监听） |
| `rag-frontend/src/App.vue` | 状态持有、API 调用、侧边栏编辑按钮、错误分类逻辑 |

---

### Task 1: 创建 ApiKeyModal.vue 组件

**Files:**
- Create: `rag-frontend/src/components/ApiKeyModal.vue`

- [ ] **Step 1: 创建组件文件**

```bash
mkdir -p rag-frontend/src/components
```

- [ ] **Step 2: 编写 ApiKeyModal.vue 完整代码**

写入以下内容到 `rag-frontend/src/components/ApiKeyModal.vue`:

```vue
<template>
  <div>
    <transition name="modal-fade">
      <div
        v-if="visible"
        class="modal-backdrop"
        @click.self="$emit('close')"
        @keydown.escape="$emit('close')"
        tabindex="-1"
      >
        <div class="api-key-modal">
          <div class="modal-header">
            <p class="eyebrow">模型访问</p>
            <h2>{{ mode === 'manage' ? '管理 API Key' : '输入 API Key' }}</h2>
          </div>

          <!-- 管理模式：已配置 Key -->
          <template v-if="mode === 'manage'">
            <p class="modal-copy">当前已配置 API Key，你可以更换或移除。</p>

            <div class="key-info">
              <span class="key-info-label">当前 Key</span>
              <code class="key-info-value">{{ maskedKey }}</code>
            </div>

            <template v-if="!showEditor">
              <button type="button" @click="openEditor" class="primary-button">
                更换 Key
              </button>
              <button type="button" @click="handleRemove" class="danger-button">
                移除 Key
              </button>
            </template>

            <template v-if="showEditor">
              <label class="api-key-field">
                <span>新 API Key</span>
                <div class="input-wrap">
                  <input
                    ref="keyInput"
                    v-model="keyInput"
                    :type="showPassword ? 'text' : 'password'"
                    autocomplete="off"
                    placeholder="请输入新的 API Key"
                    :disabled="loading"
                  >
                  <button
                    type="button"
                    class="toggle-visibility"
                    :title="showPassword ? '隐藏' : '显示'"
                    @click="togglePassword"
                  >
                    {{ showPassword ? '🙈' : '👁' }}
                  </button>
                </div>
              </label>
              <div v-if="error" class="api-key-error">{{ error }}</div>
              <div class="editor-actions">
                <button type="button" @click="handleSubmit" :disabled="loading" class="primary-button">
                  {{ loading ? '验证中' : '验证并更新' }}
                </button>
                <button type="button" @click="cancelEditor" class="ghost-button-inline">
                  取消
                </button>
              </div>
            </template>
          </template>

          <!-- 配置模式：未配置 Key -->
          <template v-else>
            <p class="modal-copy">
              请输入 API Key 以启用问答功能，提交后会立即验证。
            </p>
            <label class="api-key-field">
              <span>API Key</span>
              <div class="input-wrap">
                <input
                  ref="keyInput"
                  v-model="keyInput"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="off"
                  placeholder="请输入 API Key"
                  :disabled="loading"
                >
                <button
                  type="button"
                  class="toggle-visibility"
                  :title="showPassword ? '隐藏' : '显示'"
                  @click="togglePassword"
                >
                  {{ showPassword ? '🙈' : '👁' }}
                </button>
              </div>
            </label>
            <div v-if="error" class="api-key-error">{{ error }}</div>
            <button type="button" @click="handleSubmit" :disabled="loading" class="primary-button">
              {{ loading ? '验证中' : '验证并保存' }}
            </button>
          </template>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
export default {
  name: 'ApiKeyModal',
  props: {
    visible: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' },
    configured: { type: Boolean, default: false },
  },
  emits: ['submit', 'close', 'remove'],
  data() {
    return {
      keyInput: '',
      showPassword: false,
      showEditor: false,
    };
  },
  computed: {
    mode() {
      if (this.configured) {
        return this.showEditor ? 'config' : 'manage';
      }
      return 'config';
    },
    maskedKey() {
      if (!this.configured) return '';
      return this.keyInput || '••••••••';
    },
  },
  watch: {
    visible(newVal) {
      if (newVal) {
        this.$nextTick(() => {
          this.$refs.keyInput?.focus();
        });
      }
    },
    configured(newVal) {
      if (!newVal) {
        this.showEditor = false;
        this.keyInput = '';
      }
    },
  },
  methods: {
    togglePassword() {
      this.showPassword = !this.showPassword;
    },
    openEditor() {
      this.showEditor = true;
      this.keyInput = '';
      this.$nextTick(() => {
        this.$refs.keyInput?.focus();
      });
    },
    cancelEditor() {
      this.showEditor = false;
      this.keyInput = '';
    },
    handleSubmit() {
      const trimmed = this.keyInput.trim();
      if (!trimmed) {
        return;
      }
      this.$emit('submit', trimmed);
    },
    handleRemove() {
      this.$emit('remove');
      this.showEditor = false;
    },
  },
  mounted() {
    if (this.visible) {
      this.$nextTick(() => {
        this.$refs.keyInput?.focus();
      });
    }
  },
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.38);
}

.api-key-modal {
  display: grid;
  gap: 16px;
  width: min(440px, 100%);
  padding: 22px;
  border: 1px solid #e4e8ef;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 22px 60px rgba(15, 23, 42, 0.22);
}

.modal-header h2,
.modal-header p,
.modal-copy {
  margin: 0;
}

.modal-header h2 {
  font-size: 22px;
  line-height: 1.2;
}

.modal-copy {
  color: #667085;
  font-size: 14px;
  line-height: 1.6;
}

.eyebrow {
  margin-bottom: 4px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.key-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid #e4e8ef;
  border-radius: 8px;
  background: #f8fafc;
}

.key-info-label {
  color: #667085;
  font-size: 12px;
}

.key-info-value {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  color: #263143;
}

.api-key-field {
  display: grid;
  gap: 8px;
  color: #667085;
  font-size: 13px;
  font-weight: 700;
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrap input {
  width: 100%;
  min-height: 46px;
  border: 1px solid #cfd7e3;
  border-radius: 8px;
  padding: 12px 40px 12px 13px;
  color: #172033;
  background: #ffffff;
  outline: none;
  transition: border-color 160ms ease;
}

.input-wrap input::placeholder {
  color: #98a2b3;
}

.input-wrap input:focus {
  border-color: #2563eb;
}

.toggle-visibility {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  padding: 4px 8px;
  line-height: 1;
}

.api-key-error {
  padding: 9px 11px;
  border: 1px solid #ffd6d2;
  border-radius: 8px;
  color: #b42318;
  background: #fff8f7;
  font-size: 13px;
  line-height: 1.45;
}

.primary-button {
  min-height: 46px;
  border: 1px solid #2563eb;
  border-radius: 8px;
  color: #ffffff;
  background: #2563eb;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease;
}

.primary-button:hover:not(:disabled) {
  border-color: #1d4ed8;
  background: #1d4ed8;
}

.primary-button:disabled {
  border-color: #b7c0ce;
  background: #b7c0ce;
  cursor: not-allowed;
}

.danger-button {
  min-height: 46px;
  border: 1px solid #ffd6d2;
  border-radius: 8px;
  color: #b42318;
  background: #ffffff;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  transition: background 160ms ease;
}

.danger-button:hover {
  background: #fff8f7;
}

.editor-actions {
  display: grid;
  gap: 10px;
}

.ghost-button-inline {
  min-height: 40px;
  border: 1px solid #e4e8ef;
  border-radius: 8px;
  color: #667085;
  background: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: border-color 160ms ease, color 160ms ease;
}

.ghost-button-inline:hover {
  border-color: #2563eb;
  color: #2563eb;
}

/* Transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 200ms ease;
}

.modal-fade-enter-active .api-key-modal,
.modal-fade-leave-active .api-key-modal {
  transition: transform 200ms ease, opacity 200ms ease;
}

.modal-fade-enter-from {
  opacity: 0;
}

.modal-fade-enter-from .api-key-modal {
  transform: scale(0.95);
  opacity: 0;
}

.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-leave-to .api-key-modal {
  transform: scale(0.95);
  opacity: 0;
}
</style>
```

- [ ] **Step 3: 验证组件语法**

```bash
cd rag-frontend && npx vue-cli-service lint src/components/ApiKeyModal.vue --no-fix 2>&1 | head -20
```

Expected: 无 lint 错误（可能有 warning，无 error 即可）。

- [ ] **Step 4: 验证构建**

```bash
cd rag-frontend && npm run build 2>&1 | tail -10
```

Expected: Build 成功，输出到 dist/。

- [ ] **Step 5: Commit**

```bash
git add rag-frontend/src/components/ApiKeyModal.vue
git commit -m "feat: add ApiKeyModal component with UX enhancements"
```

---

### Task 2: 修改 App.vue——集成 ApiKeyModal 组件

**Files:**
- Modify: `rag-frontend/src/App.vue`

- [ ] **Step 1: 修改 `<script>` 部分——导入组件并注册**

将 App.vue 中 `<script>` 顶部（第 208-211 行区域），在 `import { marked } from 'marked';` 之后添加:

```javascript
import ApiKeyModal from './components/ApiKeyModal.vue';
```

在 `export default` 的 `name: 'App',` 之后，`data() {` 之前，将 `components:` 段添加进来:

因为当前没有 `components:` 注册项，需要在 `name: 'App',` 后面加上:

```javascript
  components: {
    ApiKeyModal,
  },
```

- [ ] **Step 2: 修改 data()——移除 apiKeyInput**

在 `data()` 中，删除这一行（当前第 223 行附近）:

```
apiKeyInput: '',
```

保留其余所有 data 属性不变。

- [ ] **Step 3: 添加新方法——clearApiKey、openKeyManager、closeApiKeyModal**

在 `methods:` 对象中，`loadApiKeyStatus()` 方法之前（第 383 行附近），添加以下三个方法:

```javascript
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
```

- [ ] **Step 4: 修改 submitApiKey——接受 apiKey 参数**

将 `submitApiKey()` 方法（当前第 397-422 行）修改为接受 `apiKey` 参数:

```javascript
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
```

- [ ] **Step 5: 修改 sendMessage 中的 401 处理——细化错误分类**

在 `sendMessage()` 方法的 catch 块中（当前第 527-535 行），将 401 处理的 `apiKeyError` 赋值改为:

```javascript
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
```

- [ ] **Step 6: 修改 loadApiKeyStatus 方法——网络错误时给出具体提示**

将 `loadApiKeyStatus()` 方法（第 384-396 行）的 catch 块改为:

```javascript
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
```

- [ ] **Step 7: 修改模板——替换弹窗为 ApiKeyModal 组件**

删除模板中第 180-204 行的整个弹窗块:

```html
    <div v-if="showApiKeyModal" class="modal-backdrop">
      <form class="api-key-modal" @submit.prevent="submitApiKey">
        <div class="modal-header">
          <p class="eyebrow">模型访问</p>
          <h2>输入 API Key</h2>
        </div>
        <p class="modal-copy">
          当前后端还没有可用的 API Key。提交后会立即验证，验证通过后即可开始问答。
        </p>
        <label class="api-key-field">
          <span>API Key</span>
          <input
            v-model="apiKeyInput"
            type="password"
            autocomplete="off"
            placeholder="请输入 API Key"
            :disabled="isSubmittingApiKey"
          >
        </label>
        <div v-if="apiKeyError" class="api-key-error">{{ apiKeyError }}</div>
        <button type="submit" :disabled="isSubmittingApiKey">
          {{ isSubmittingApiKey ? '验证中' : '验证并保存' }}
        </button>
      </form>
    </div>
```

替换为:

```html
    <ApiKeyModal
      :visible="showApiKeyModal"
      :loading="isSubmittingApiKey"
      :error="apiKeyError"
      :configured="apiKeyConfigured"
      @submit="submitApiKey"
      @remove="clearApiKey"
      @close="closeApiKeyModal"
    />
```

- [ ] **Step 8: 修改侧边栏状态行——添加编辑按钮**

将侧边栏状态行（第 13-16 行）:

```html
          <div :class="['status-row', { warning: !apiKeyConfigured }]">
            <span class="status-dot"></span>
            <span>{{ apiKeyStatusLabel }}</span>
          </div>
```

替换为:

```html
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
```

- [ ] **Step 9: 添加齿轮按钮样式**

在 `<style>` 部分中，`.status-row` 样式之后添加:

```css
.gear-button {
  margin-left: auto;
  border: 1px solid #e4e8ef;
  border-radius: 6px;
  background: #ffffff;
  color: #667085;
  font-size: 16px;
  line-height: 1;
  padding: 2px 6px;
  cursor: pointer;
  transition: border-color 160ms ease, color 160ms ease;
}

.gear-button:hover {
  border-color: #2563eb;
  color: #2563eb;
}
```

- [ ] **Step 10: 验证 lint**

```bash
cd rag-frontend && npx vue-cli-service lint src/App.vue --no-fix 2>&1 | head -20
```

Expected: 无 error（warning 可忽略）。

- [ ] **Step 11: 验证构建**

```bash
cd rag-frontend && npm run build 2>&1 | tail -10
```

Expected: Build 成功。

- [ ] **Step 12: 验证弹窗 CSS**

注意保留 App.vue 的 `<style>` 中已有的 modal-backdrop、api-key-modal 等样式（第 1292-1393 行区域），因为 ApiKeyModal 组件的样式是 scoped 的。但 ApiKeyModal 组件已自带样式，App.vue 中的旧弹窗样式已成为死代码。

- [ ] **Step 13: 清理 App.vue 中的旧弹窗样式（死代码）**

删除 App.vue `<style>` 中以下样式块（约第 1292-1393 行）：

```css
  .modal-backdrop {
    ...
  }

  .api-key-modal {
    ...
  }

  .modal-header h2,
  .modal-header p,
  .modal-copy {
    ...
  }

  .modal-header h2 {
    ...
  }

  .modal-copy {
    ...
  }

  .api-key-field {
    ...
  }

  .api-key-field input {
    ...
  }

  .api-key-field input::placeholder {
    ...
  }

  .api-key-field input:focus {
    ...
  }

  .api-key-error {
    ...
  }

  .api-key-modal button {
    ...
  }

  .api-key-modal button:hover:not(:disabled) {
    ...
  }

  .api-key-modal button:disabled {
    ...
  }
```

这些样式块现在在 ApiKeyModal.vue 的 scoped style 中。**只删除弹窗相关的样式**，其余聊天、侧边栏、typing 等样式全部保留。

- [ ] **Step 14: 最终构建验证**

```bash
cd rag-frontend && npm run build 2>&1 | tail -15
```

Expected: Build 成功，无 error。

- [ ] **Step 15: Commit**

```bash
git add rag-frontend/src/App.vue
git commit -m "refactor: extract ApiKeyModal component, add key management and UX enhancements"
```

---

### Task 3: 手动验证检查清单

**Files:** 无新建/修改

- [ ] **Step 1: 启动开发环境验证**

启动后端:
```bash
cd rag-backend && source .venv/bin/activate && OPENAI_API_KEY="" python main.py &
```

启动前端:
```bash
cd rag-frontend && npm run serve &
```

访问 `http://localhost:3000`。

- [ ] **Step 2: 验证首次配置流程**

1. 页面加载 → 弹窗弹出，标题"输入 API Key"
2. 密码框默认隐藏输入内容
3. 点击👁图标 → 输入内容可见
4. 再次点击🙈 → 恢复隐藏
5. 留空点击"验证并保存" → 不发送请求（组件内 trim 检查）
6. 输入有效 Key → 点击验证 → 弹窗关闭 → 侧边栏显示绿色"API Key 已配置"+ 齿轮按钮

- [ ] **Step 3: 验证管理模式**

1. 点击侧边栏齿轮按钮 → 弹窗弹出，标题"管理 API Key"
2. 显示"当前 Key"
3. 点击"更换 Key" → 展开输入框
4. 点击"取消" → 回到管理模式
5. 点击"移除 Key" → 弹窗变为首次配置模式

- [ ] **Step 4: 验证 UX 增强**

1. 弹窗打开时按 ESC → 关闭
2. 点击遮罩（弹窗外灰色区域）→ 关闭
3. 弹窗打开/关闭有过渡动画（200ms fade + scale）
4. 弹窗打开时输入框自动聚焦

- [ ] **Step 5: 验证错误分类**

1. 输入无效 Key（如 "invalid-key"）→ 显示后端返回的错误详情
2. 配置有效 Key 后 → 后端重启（Key 丢失）→ 发送问题 → 弹窗弹出 "Key 已失效"
3. 停止后端 → 操作 → 弹窗显示 "网络请求失败"

- [ ] **Step 6: 停止服务**

```bash
pkill -f "python main.py" 2>/dev/null
pkill -f "vue-cli-service" 2>/dev/null
```
