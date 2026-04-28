# API Key 输入模块优化——设计规格

## 目标

将 API Key 输入模块从 App.vue 中拆分为独立组件 `ApiKeyModal.vue`，同时增强 UX 和 Key 管理能力。

## 范围

- 新建 `src/components/ApiKeyModal.vue`
- 修改 `src/App.vue`：移除内联弹窗模板和逻辑，改用 ApiKeyModal 组件；侧边栏状态行增加编辑按钮
- 不改后端

## 组件架构

```
App.vue
├── 持有: apiKeyConfigured, showApiKeyModal, apiKeyError, isSubmittingApiKey
├── 方法: submitApiKey(), clearApiKey(), openKeyManager()
└── 模板:
    ├── 侧边栏状态行 → 已配时显示齿轮按钮 @click="openKeyManager"
    └── <ApiKeyModal
          :visible="showApiKeyModal"
          :loading="isSubmittingApiKey"
          :error="apiKeyError"
          :configured="apiKeyConfigured"
          @submit="submitApiKey"
          @close="closeApiKeyModal"
        />

ApiKeyModal.vue (新文件)
├── Props: visible, loading, error, configured
├── Events: submit, close
├── 内部状态: keyInput, showPassword, mode ('config' | 'manage')
└── 模板: 根据 configured 决定显示"首次配置"还是"管理模式"
```

## ApiKeyModal 两种模式

### 首次配置模式 (configured = false)
- 标题: "输入 API Key"
- 说明文字: 请输入 API Key 以启用问答功能
- 密码输入框 + 可见性切换按钮
- "验证并保存" 按钮
- 错误区域（红色提示）

### 管理模式 (configured = true)
- 标题: "管理 API Key"
- 显示当前 Key 部分信息（格式: `sk-...后4位`）
- "更换 Key" 按钮 → 展开输入框
- "移除 Key" 按钮 → 确认后清除本地状态，回到未配置
- 错误区域

## UX 增强清单

| 功能 | 实现 |
|------|------|
| 密码可见性切换 | 输入框右侧 眼/闭眼 图标 |
| ESC 关闭 | `@keydown.escape` 监听 |
| 点击遮罩关闭 | modal-backdrop 上 `@click.self` |
| 过渡动画 | CSS transition: opacity + transform 200ms |
| 输入框自动聚焦 | mounted/watch visible 时 autofocus |

## 错误分类

| 场景 | 检测 | 提示文案 |
|------|------|---------|
| 空输入 | 前端 trim | "API Key 不能为空" |
| Key 无效 | 后端 400 | error.response.data.detail（后端已验证，前端不做格式假设） |
| Key 失效/额度不足 | /ask 返回 401 | "Key 已失效或余额不足，请更换后重试" |
| 网络错误 | axios NetworkError | "网络请求失败，请检查网络连接后重试" |
| 后端不可达 | 5xx / timeout | "后端服务不可用，请稍后重试" |

## 侧边栏改动

- Key 已配置时: 状态行末显示齿轮按钮 `⚙`，点击打开 ApiKeyModal（管理模式）
- Key 未配置时: 保持现有橙色警告样式和行为（点击无法操作）
- 样式沿用现有 `.status-row`

## 数据流

```
用户输入 Key → submit → App.submitApiKey()
  → axios POST /api-key → 成功 → configured=true, modal关闭
                         → 失败 → error 回传 ApiKeyModal 显示

用户换 Key → 管理模式点"更换" → 展开输入框 → 输入新Key → submit 同上

用户移除 Key → 管理模式点"移除" → App.clearApiKey()
  → configured=false, modal 切换到配置模式

/ask 返回 401 → App 中 catch → configured=false, showModal=true
  → ApiKeyModal 以配置模式弹出，显示"Key 已失效"错误
```

## 文件变更

| 文件 | 操作 |
|------|------|
| `rag-frontend/src/components/ApiKeyModal.vue` | **新增** |
| `rag-frontend/src/App.vue` | **修改** —— 精简约 50 行，侧边栏加编辑按钮 |
| 后端 | **不改** |
