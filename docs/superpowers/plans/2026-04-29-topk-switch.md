# Top-K 可切换功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在网页侧边栏中通过下拉菜单切换检索 Top-K 值，切换后即时生效。

**Architecture:** 后端新增 `PATCH /api/knowledge-base/top-k` 端点更新全局 `retrieval_top_k` 变量并轻量重建 retriever；前端在侧边栏 "检索来源" 区域用 `<select>` 替换静态展示，onChange 时调用 PATCH 端点。

**Tech Stack:** Python FastAPI + Vue 3 (Options API) + axios

---

### Task 1: 后端 — 变量、更新函数、API 端点

**Files:**
- Modify: `rag-backend/main.py:46,86,109,527-535`
- Add: `rag-backend/main.py:115-122` (new `update_top_k` function)
- Add: `rag-backend/main.py:545-575` (new PATCH endpoint)

- [ ] **Step 1: 将常量改为变量并更新所有引用**

将第 46 行 `RETRIEVAL_TOP_K = 3` 改为 `retrieval_top_k = 3`：

```python
retrieval_top_k = 3
```

将第 86 行和第 109 行的 `RETRIEVAL_TOP_K` 引用改为 `retrieval_top_k`：

```python
# Line 86
retriever = vectordb.as_retriever(search_kwargs={"k": retrieval_top_k})

# Line 109 (in refresh_retriever)
retriever = vectordb.as_retriever(search_kwargs={"k": retrieval_top_k})
```

将第 531 行 `knowledge_base_parameters()` 中的引用改为小写变量：

```python
retrieval_top_k=retrieval_top_k,
```

- [ ] **Step 2: 新增 `update_top_k()` 函数**

在 `refresh_retriever()` 函数之后（约第 112 行后）添加轻量更新函数：

```python
def update_top_k(new_k: int) -> None:
    """更新检索 Top-K 值并重建 retriever（不重建向量库连接）。"""
    global retrieval_top_k, retriever
    with retriever_lock:
        retrieval_top_k = new_k
        retriever = vectordb.as_retriever(search_kwargs={"k": new_k})
```

- [ ] **Step 3: 新增 TopKUpdateRequest 模型和 PATCH 端点**

在 Pydantic 模型区域（`KnowledgeBaseParametersResponse` 之后）添加请求模型：

```python
class TopKUpdateRequest(BaseModel):
    top_k: int
```

在 `ingest_start` 端点之前添加新端点：

```python
@app.patch("/knowledge-base/top-k", response_model=KnowledgeBaseParametersResponse)
def update_knowledge_base_top_k(request: TopKUpdateRequest) -> KnowledgeBaseParametersResponse:
    if not (1 <= request.top_k <= 100):
        raise HTTPException(status_code=422, detail="top_k 必须在 1-100 之间")

    update_top_k(request.top_k)
    return knowledge_base_parameters()
```

- [ ] **Step 4: 验证后端**

重启后端，用 curl 验证新端点：

```bash
curl -s -X PATCH http://localhost:8080/knowledge-base/top-k \
  -H "Content-Type: application/json" \
  -d '{"top_k": 5}' | python3 -m json.tool
```

预期：返回 JSON，`retrieval_top_k` 为 5，其他字段正常。

验证边界值：
```bash
# 非法值
curl -s -X PATCH http://localhost:8080/knowledge-base/top-k \
  -H "Content-Type: application/json" \
  -d '{"top_k": 0}'
```
预期：422 状态码。

- [ ] **Step 5: 提交**

```bash
git add rag-backend/main.py
git commit -m "feat: add PATCH /api/knowledge-base/top-k endpoint"
```

---

### Task 2: 前端 — 下拉选择和 API 调用

**Files:**
- Modify: `rag-frontend/src/App.vue:31-33` (template)
- Modify: `rag-frontend/src/App.vue:258` (data)
- Modify: `rag-frontend/src/App.vue:323-326` (loadKnowledgeBaseParameters)
- Add: `rag-frontend/src/App.vue:372-389` (onTopKChange method)

- [ ] **Step 1: 在 `data()` 中新增 `selectedTopK`**

在 `data()` 返回对象中，约 `isLoadingPrompts: false,` 之后添加：

```javascript
selectedTopK: 3,
```

- [ ] **Step 2: 替换模板中的静态展示为下拉**

将第 31-33 行：

```html
<strong>Top {{ retrievalTopK }}</strong>
<span>检索来源</span>
```

替换为：

```html
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
```

- [ ] **Step 3: 新增 `onTopKChange` 方法**

在 methods 中，`clearChat()` 方法之前添加：

```javascript
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
```

- [ ] **Step 4: 在 `loadKnowledgeBaseParameters` 成功后同步 selectedTopK**

在 `loadKnowledgeBaseParameters` 方法的 `.then()` 中（`this.knowledgeBaseParameters = response.data;` 之后），添加：

```javascript
this.selectedTopK = response.data.retrieval_top_k;
```

完整修改后该段为：

```javascript
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
```

- [ ] **Step 5: 添加下拉样式**

在 `<style>` 部分末尾（`</style>` 之前）添加：

```css
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
```

- [ ] **Step 6: 验证前端**

启动前端开发服务器（和后端一起），在浏览器中：
1. 确认侧边栏 "检索来源" 显示为下拉
2. 切换 Top-K 到 5，确认参数面板中的 TopK 同步更新为 5
3. 发送一个提问，确认返回了 5 条参考文献
4. 切换回 1，再次提问，确认只返回 1 条参考文献

- [ ] **Step 7: 提交**

```bash
git add rag-frontend/src/App.vue
git commit -m "feat: add Top-K dropdown switcher in sidebar"
```
