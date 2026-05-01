# Top-K 可切换功能设计

## 目标

在网页侧边栏中可通过下拉菜单切换检索 Top-K 值（1/3/5/10），切换后即时生效于后续所有提问。

## 架构

### 后端改动（rag-backend/main.py）

1. **`RETRIEVAL_TOP_K` 常量改为可变变量**

   ```python
   # 模块级可变变量，默认为 3
   retrieval_top_k = 3
   ```

   `refresh_retriever()` 中将 `RETRIEVAL_TOP_K` 引用改为 `retrieval_top_k`。

2. **新增轻量更新函数**

   ```python
   def update_top_k(new_k: int) -> None:
       global retrieval_top_k, retriever
       with retriever_lock:
           retrieval_top_k = new_k
           retriever = vectordb.as_retriever(search_kwargs={"k": new_k})
   ```

   只重建 retriever 包装器，不重建 ChromaDB 连接，零开销。

3. **新增 `PATCH /api/knowledge-base/top-k` 端点**

   请求体：`{"top_k": 5}`
   校验：top_k 必须是 1-100 之间的整数
   成功返回 200 + 更新后的参数，失败返回 422

4. **现有 `GET /api/knowledge-base/parameters` 保持不变** — 它已读取 `retrieval_top_k`，自动返回最新值。

### 前端改动（rag-frontend/src/App.vue）

1. **`data()` 新增** `selectedTopK: 3`

2. **侧边栏 "检索来源" 区域** — 将静态展示改为下拉：

   ```html
   <div class="metric">
     <strong>
       Top
       <select v-model="selectedTopK" @change="onTopKChange" :disabled="isLoading">
         <option :value="1">1</option>
         <option :value="3">3</option>
         <option :value="5">5</option>
         <option :value="10">10</option>
       </select>
     </strong>
     <span>检索来源</span>
   </div>
   ```

3. **`onTopKChange` 方法** — 发送 `PATCH /api/knowledge-base/top-k`，成功后刷新 `knowledgeBaseParameters`；失败时回滚 `selectedTopK`。

4. **初始化** — 在 `loadKnowledgeBaseParameters` 成功后，将 `selectedTopK` 同步为后端当前值。

### 数据流

```
下拉 onChange → PATCH /api/knowledge-base/top-k {top_k: 值}
  → 后端 retrieval_top_k = 新值 → retriever 重建（k 参数更新）
  → 前端 loadKnowledgeBaseParameters() → 参数面板同步
  → 下次提问使用新的 k 值检索
```

## 边界情况

- **非法值**：后端校验 1-100，返回 422
- **PATCH 失败**：前端回滚 `selectedTopK` 到上一个有效值，不阻塞提问
- **并发安全**：更新和检索共用 `retriever_lock`
- **初始值**：页面加载时从 `GET /api/knowledge-base/parameters` 同步
- **加载中**：`isLoading` 为 true 时下拉 disabled
