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
