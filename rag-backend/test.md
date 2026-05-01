# 医疗 RAG 系统对比测试程序实现建议

## 一、当前前后端基础

当前项目已经支持在前端修改检索 Top-K，可直接作为对比测试的变量。

已具备能力：

- 前端 `rag-frontend/src/App.vue` 已提供 Top-K 下拉框，选项包括 `1`、`3`、`5`、`10`。
- 前端调用 `PATCH /api/knowledge-base/top-k` 更新后端 Top-K。
- 后端 `rag-backend/main.py` 已提供 `PATCH /knowledge-base/top-k`。
- 后端更新 Top-K 后会重建 retriever，后续 `/ask` 请求会使用新的 Top-K。
- `/ask` 返回 `answer`、`sources` 和 `metrics`，可用于自动记录对比结果。
- `/knowledge-base/parameters` 返回当前 `retrieval_top_k`，可用于确认实验配置是否生效。

因此，对比测试程序不需要再实现 Top-K 前端控制，重点应放在批量测试、结果记录和汇总分析。

## 二、建议新增文件

建议在 `rag-backend` 目录新增以下文件：

```text
rag-backend/
  evaluate_compare.py
  eval_questions.json
  eval_results/
```

文件用途：

| 文件 | 作用 |
| --- | --- |
| `evaluate_compare.py` | 批量对比测试脚本 |
| `eval_questions.json` | 固定测试问题集 |
| `eval_results/detail_实验名.csv` | 每轮实验明细结果 |
| `eval_results/summary.csv` | 多轮实验汇总结果 |

## 三、测试集格式

新增 `rag-backend/eval_questions.json`。

建议格式：

```json
[
  {
    "id": "Q001",
    "question": "What are common causes of dizziness and nausea?",
    "language": "en",
    "category": "symptom",
    "expected_keywords": ["dizziness", "nausea"]
  },
  {
    "id": "Q002",
    "question": "孕期可以随便吃止痛药吗？",
    "language": "zh",
    "category": "pregnancy",
    "expected_keywords": ["pregnancy", "medicine", "doctor"]
  }
]
```

第一版建议准备 30 到 50 个问题，覆盖：

- 英文医疗问题。
- 中文医疗问题。
- 症状类问题。
- 药物副作用问题。
- 孕期、儿童健康等高风险问题。
- 知识库中可能没有答案的问题。

后续论文实验可扩展到 100 个左右。

## 四、对比测试脚本功能

新增 `rag-backend/evaluate_compare.py`。

建议脚本参数：

```powershell
python evaluate_compare.py --experiment topk3 --top-k 3
python evaluate_compare.py --experiment topk5 --top-k 5
```

建议支持参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--base-url` | `http://127.0.0.1:8080` | 后端服务地址 |
| `--experiment` | 必填 | 实验名称，例如 `topk1`、`topk3` |
| `--top-k` | 可选 | 本轮实验要设置的 Top-K |
| `--questions` | `eval_questions.json` | 测试集路径 |
| `--output-dir` | `eval_results` | 输出目录 |
| `--delay` | `0` | 每个问题之间的等待秒数，避免请求过快 |

脚本执行流程：

1. 读取 `eval_questions.json`。
2. 如果传入 `--top-k`，先调用 `PATCH /knowledge-base/top-k`。
3. 调用 `/knowledge-base/parameters`，确认返回的 `retrieval_top_k` 与实验配置一致。
4. 遍历测试问题，逐条调用 `POST /ask`。
5. 记录每题返回的 `answer`、`sources`、`metrics`。
6. 输出本轮明细 CSV。
7. 计算本轮自动汇总指标并追加到 `summary.csv`。

建议使用 Python 标准库 `urllib.request`、`json`、`csv`、`argparse` 实现，避免新增依赖。

## 五、接口调用建议

### 1. 设置 Top-K

请求：

```http
PATCH /knowledge-base/top-k
Content-Type: application/json
```

请求体：

```json
{
  "top_k": 3
}
```

校验：

- 成功后读取返回值中的 `retrieval_top_k`。
- 如果返回值不等于目标 Top-K，脚本应停止本轮实验。

### 2. 确认知识库参数

请求：

```http
GET /knowledge-base/parameters
```

建议记录字段：

- `retrieval_top_k`
- `collection_count`
- `embedding_model`
- `onnx_model_file`
- `onnx_provider`
- `llm_model`
- `api_key_configured`

如果 `api_key_configured=false`，脚本应提示先在前端或环境变量中配置 API Key。

### 3. 执行问答

请求：

```http
POST /ask
Content-Type: application/json
```

请求体：

```json
{
  "query": "What are common causes of dizziness and nausea?"
}
```

建议记录响应字段：

- `answer`
- `sources`
- `metrics.retrieval_time_ms`
- `metrics.generation_time_ms`
- `metrics.response_time_ms`
- `metrics.average_response_time_ms`

## 六、明细 CSV 字段

每轮实验输出一个文件：

```text
eval_results/detail_topk3.csv
```

建议字段：

| 字段 | 说明 |
| --- | --- |
| `experiment` | 实验名称 |
| `configured_top_k` | 本轮设置的 Top-K |
| `actual_top_k` | 后端确认的 Top-K |
| `question_id` | 问题编号 |
| `question` | 问题文本 |
| `language` | 语言 |
| `category` | 问题类别 |
| `success` | 请求是否成功 |
| `answer` | 系统回答 |
| `sources_count` | 返回来源数量 |
| `sources` | 来源文本，多个来源用 `||` 拼接 |
| `retrieval_time_ms` | 检索耗时 |
| `generation_time_ms` | 生成耗时 |
| `response_time_ms` | 总响应时间 |
| `average_response_time_ms` | 后端累计平均响应时间 |
| `error` | 错误信息 |
| `manual_correctness` | 人工评分：正确性，先留空 |
| `manual_faithfulness` | 人工评分：忠实性，先留空 |
| `manual_safety` | 人工评分：医学安全性，先留空 |
| `manual_note` | 人工备注，先留空 |

## 七、汇总 CSV 字段

每次运行后追加或更新：

```text
eval_results/summary.csv
```

建议字段：

| 字段 | 说明 |
| --- | --- |
| `experiment` | 实验名称 |
| `configured_top_k` | 脚本设置的 Top-K |
| `actual_top_k` | 后端实际 Top-K |
| `total_questions` | 总问题数 |
| `success_count` | 成功请求数 |
| `success_rate` | 成功率 |
| `avg_sources_count` | 平均来源数量 |
| `avg_retrieval_time_ms` | 平均检索耗时 |
| `avg_generation_time_ms` | 平均生成耗时 |
| `avg_response_time_ms` | 平均响应时间 |
| `max_response_time_ms` | 最大响应时间 |
| `min_response_time_ms` | 最小响应时间 |

第一版不需要自动计算 Recall、MRR，因为这些需要人工标注相关文档。可以先通过人工评分字段补充正确性、忠实性和医学安全性。

## 八、推荐实验命令

先启动后端服务，确保 API Key 已配置、知识库已加载。

然后执行：

```powershell
cd rag-backend
python evaluate_compare.py --experiment topk1 --top-k 1
python evaluate_compare.py --experiment topk3 --top-k 3
python evaluate_compare.py --experiment topk5 --top-k 5
python evaluate_compare.py --experiment topk10 --top-k 10
```

跑完后查看：

```text
eval_results/detail_topk1.csv
eval_results/detail_topk3.csv
eval_results/detail_topk5.csv
eval_results/detail_topk10.csv
eval_results/summary.csv
```

## 九、验收标准

Claude Code 实现完成后，应满足：

- 不破坏当前前端 Top-K 下拉功能。
- 不破坏现有 `/ask`、`/monitoring`、`/knowledge-base/parameters` 接口。
- `evaluate_compare.py --experiment topk3 --top-k 3` 可正常运行。
- 脚本会先设置后端 Top-K，再确认实际 Top-K。
- 每个测试问题都会写入明细 CSV。
- 请求失败时也会写入 CSV，并在 `error` 字段记录原因。
- `summary.csv` 能汇总成功率、平均响应时间、平均检索耗时和平均来源数量。
- 不要求第一版自动完成医学质量评分，人工评分字段可以留空。

## 十、后续扩展建议

### 1. 人工评分分析脚本

后续可新增 `analyze_manual_scores.py`，读取人工补充后的 `detail_*.csv`，计算：

- 平均正确性。
- 平均忠实性。
- 医学安全性通过率。
- 不同 Top-K 的质量对比。

### 2. embedding 模型对比

如果后续比较 `gte-large-en-v1.5` 和 `bge-base-en-v1.5`，必须注意：

- 切换 embedding 模型后需要重建 Chroma 向量库。
- 不要直接复用旧向量库。
- 每次模型对比应固定 Top-K，例如都使用 TopK=3。
- 实验名建议写成 `gte_large_topk3`、`bge_base_topk3`。

### 3. 前端导出结果

如果希望完全从前端操作，可后续增加“批量测试页面”，但第一版不建议做。当前更推荐用后端脚本跑实验，稳定、可复现，也更适合写论文实验结果。

## 十一、推荐给 Claude Code 的实现顺序

1. 新建 `rag-backend/eval_questions.json`，放入 10 个示例问题。
2. 新建 `rag-backend/evaluate_compare.py`。
3. 实现 Top-K 设置、参数确认、批量调用 `/ask`。
4. 实现明细 CSV 输出。
5. 实现 `summary.csv` 汇总。
6. 用 `--experiment topk3 --top-k 3` 做一次小规模验证。
7. 再扩展测试集和运行 TopK=1、5、10 对比。
