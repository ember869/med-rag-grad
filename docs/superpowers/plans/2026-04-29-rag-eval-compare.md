# RAG Evaluation Compare Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a batch comparison testing script that evaluates RAG system performance across different Top-K settings, outputting detail and summary CSVs.

**Architecture:** A single Python script (`evaluate_compare.py`) using only stdlib (urllib, json, csv, argparse) reads a JSON question set, configures the backend's Top-K via PATCH, confirms it via GET, runs each question through POST /ask, and writes per-experiment detail CSVs + an append-only summary CSV.

**Tech Stack:** Python 3 stdlib only (urllib.request, json, csv, argparse, time, os, datetime)

---

### Task 1: Create eval_questions.json

**Files:**
- Create: `rag-backend/eval_questions.json`

- [ ] **Step 1: Write the test question file**

Write `rag-backend/eval_questions.json` with 10 diverse questions covering English/Chinese, symptoms/drugs/pregnancy/edge cases:

```json
[
  {
    "id": "Q001",
    "question": "What are common causes of dizziness and nausea?",
    "language": "en",
    "category": "symptom"
  },
  {
    "id": "Q002",
    "question": "What are the side effects of metformin?",
    "language": "en",
    "category": "drug_side_effect"
  },
  {
    "id": "Q003",
    "question": "孕期可以随便吃止痛药吗？",
    "language": "zh",
    "category": "pregnancy"
  },
  {
    "id": "Q004",
    "question": "Is it safe to take ibuprofen while breastfeeding?",
    "language": "en",
    "category": "pregnancy"
  },
  {
    "id": "Q005",
    "question": "儿童发烧多少度需要去医院？",
    "language": "zh",
    "category": "child_health"
  },
  {
    "id": "Q006",
    "question": "How is type 2 diabetes diagnosed?",
    "language": "en",
    "category": "diagnosis"
  },
  {
    "id": "Q007",
    "question": "高血压患者应该避免哪些食物？",
    "language": "zh",
    "category": "chronic_disease"
  },
  {
    "id": "Q008",
    "question": "What are the symptoms of vitamin D deficiency?",
    "language": "en",
    "category": "symptom"
  },
  {
    "id": "Q009",
    "question": "Can antibiotics treat viral infections?",
    "language": "en",
    "category": "drug_side_effect"
  },
  {
    "id": "Q010",
    "question": "What is the rarest disease in medical history that has only been documented once in 1923?",
    "language": "en",
    "category": "edge_case"
  }
]
```

### Task 2: Create evaluate_compare.py scaffold

**Files:**
- Create: `rag-backend/evaluate_compare.py`

- [ ] **Step 1: Write argument parser and main entry point**

```python
#!/usr/bin/env python3
"""RAG 系统对比测试脚本 — 批量运行问答并记录结果。"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="RAG 系统对比测试")
    parser.add_argument("--experiment", required=True, help="实验名称，如 topk3")
    parser.add_argument("--top-k", type=int, help="本轮实验要设置的 Top-K")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="后端服务地址")
    parser.add_argument("--questions", default="eval_questions.json", help="测试集路径")
    parser.add_argument("--output-dir", default="eval_results", help="输出目录")
    parser.add_argument("--delay", type=float, default=0.5, help="每个问题之间的等待秒数")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"实验: {args.experiment}")
    print(f"后端: {args.base_url}")
```

- [ ] **Step 2: Verify it runs**

Run: `cd rag-backend && python evaluate_compare.py --experiment topk3`
Expected: prints experiment name and base URL, exits cleanly.

### Task 3: Implement Top-K setting and verification

**Files:**
- Modify: `rag-backend/evaluate_compare.py` (append new functions)

- [ ] **Step 1: Write the PATCH and GET functions**

```python
def set_top_k(base_url: str, top_k: int) -> int:
    """设置后端 Top-K 并返回确认后的 actual_top_k。失败时抛异常。"""
    # PATCH /knowledge-base/top-k
    data = json.dumps({"top_k": top_k}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/knowledge-base/top-k",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PATCH top-k 失败 (HTTP {e.code}): {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接后端: {e.reason}")

    actual = result.get("retrieval_top_k")
    if actual != top_k:
        raise RuntimeError(f"Top-K 设置不匹配: 期望 {top_k}, 实际 {actual}")
    return actual


def get_parameters(base_url: str) -> dict:
    """获取知识库参数并返回关键字段。"""
    try:
        with urllib.request.urlopen(f"{base_url}/knowledge-base/parameters", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET parameters 失败 (HTTP {e.code}): {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接后端: {e.reason}")
```

- [ ] **Step 2: Wire into main() — call set_top_k, verify, print confirmation**

Add to main after arg parsing:
```python
    os.makedirs(args.output_dir, exist_ok=True)

    if args.top_k is not None:
        print(f"设置 Top-K = {args.top_k} ...")
        actual = set_top_k(args.base_url, args.top_k)
        print(f"已确认 Top-K = {actual}")

    params = get_parameters(args.base_url)
    print(f"知识库: {params['collection_name']} ({params['collection_count']} 条)")
    print(f"LLM: {params['llm_model']}, API Key: {params['api_key_configured']}")
    if not params["api_key_configured"]:
        print("错误: API Key 未配置，请先在前端或环境变量中设置 OPENAI_API_KEY")
        sys.exit(1)
```

### Task 4: Implement batch /ask execution

**Files:**
- Modify: `rag-backend/evaluate_compare.py` (append)

- [ ] **Step 1: Write the ask function**

```python
def ask_question(base_url: str, question: str) -> dict:
    """调用 POST /ask 并返回完整响应字典，含 success/error 标记。"""
    data = json.dumps({"query": question}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/ask",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            result["_success"] = True
            result["_error"] = ""
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"answer": "", "sources": [], "metrics": {}, "_success": False, "_error": f"HTTP {e.code}: {body}"}
    except urllib.error.URLError as e:
        return {"answer": "", "sources": [], "metrics": {}, "_success": False, "_error": f"连接失败: {e.reason}"}
```

- [ ] **Step 2: Wire batch loop into main()**

Add after parameter check:
```python
    script_dir = os.path.dirname(os.path.abspath(__file__))
    questions_path = os.path.join(script_dir, args.questions)
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    print(f"加载 {len(questions)} 个测试问题")

    detail_rows = []
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['id']}: {q['question'][:60]}...")
        resp = ask_question(args.base_url, q["question"])

        metrics = resp.get("metrics") or {}
        sources = resp.get("sources") or []
        row = {
            "experiment": args.experiment,
            "configured_top_k": args.top_k,
            "actual_top_k": actual if args.top_k is not None else params["retrieval_top_k"],
            "question_id": q["id"],
            "question": q["question"],
            "language": q.get("language", ""),
            "category": q.get("category", ""),
            "success": resp["_success"],
            "answer": resp["answer"].replace("\n", "\\n") if resp.get("answer") else "",
            "sources_count": len(sources),
            "sources": "||".join(sources) if sources else "",
            "retrieval_time_ms": metrics.get("retrieval_time_ms", ""),
            "generation_time_ms": metrics.get("generation_time_ms", ""),
            "response_time_ms": metrics.get("response_time_ms", ""),
            "average_response_time_ms": metrics.get("average_response_time_ms", ""),
            "error": resp["_error"],
            "manual_correctness": "",
            "manual_faithfulness": "",
            "manual_safety": "",
            "manual_note": "",
        }
        detail_rows.append(row)

        if resp["_success"]:
            print(f"    sources={len(sources)}, time={metrics.get('response_time_ms', 'N/A')}ms")
        else:
            print(f"    失败: {resp['_error'][:80]}")

        if args.delay > 0 and i < len(questions):
            time.sleep(args.delay)
```

### Task 5: Implement CSV output

**Files:**
- Modify: `rag-backend/evaluate_compare.py` (append functions + wire into main)

- [ ] **Step 1: Write CSV output functions**

```python
DETAIL_FIELDS = [
    "experiment", "configured_top_k", "actual_top_k", "question_id", "question",
    "language", "category", "success", "answer", "sources_count", "sources",
    "retrieval_time_ms", "generation_time_ms", "response_time_ms",
    "average_response_time_ms", "error", "manual_correctness",
    "manual_faithfulness", "manual_safety", "manual_note",
]

SUMMARY_FIELDS = [
    "experiment", "configured_top_k", "actual_top_k", "total_questions",
    "success_count", "success_rate", "avg_sources_count",
    "avg_retrieval_time_ms", "avg_generation_time_ms",
    "avg_response_time_ms", "max_response_time_ms", "min_response_time_ms",
]


def write_detail_csv(output_dir: str, experiment: str, rows: list):
    path = os.path.join(output_dir, f"detail_{experiment}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"明细已保存: {path}")
    return path


def append_summary_csv(output_dir: str, experiment: str, top_k: int, actual_top_k: int, rows: list):
    path = os.path.join(output_dir, "summary.csv")
    exist = os.path.exists(path)

    success_rows = [r for r in rows if r["success"]]
    times = [r["response_time_ms"] for r in success_rows if isinstance(r.get("response_time_ms"), (int, float))]
    retrieval_times = [r["retrieval_time_ms"] for r in success_rows if isinstance(r.get("retrieval_time_ms"), (int, float))]
    gen_times = [r["generation_time_ms"] for r in success_rows if isinstance(r.get("generation_time_ms"), (int, float))]
    source_counts = [r["sources_count"] for r in success_rows if isinstance(r.get("sources_count"), int)]

    summary_row = {
        "experiment": experiment,
        "configured_top_k": top_k,
        "actual_top_k": actual_top_k,
        "total_questions": len(rows),
        "success_count": len(success_rows),
        "success_rate": f"{len(success_rows) / len(rows) * 100:.1f}%" if rows else "0%",
        "avg_sources_count": f"{sum(source_counts) / len(source_counts):.2f}" if source_counts else "",
        "avg_retrieval_time_ms": f"{sum(retrieval_times) / len(retrieval_times):.1f}" if retrieval_times else "",
        "avg_generation_time_ms": f"{sum(gen_times) / len(gen_times):.1f}" if gen_times else "",
        "avg_response_time_ms": f"{sum(times) / len(times):.1f}" if times else "",
        "max_response_time_ms": f"{max(times):.1f}" if times else "",
        "min_response_time_ms": f"{min(times):.1f}" if times else "",
    }

    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        if not exist:
            writer.writeheader()
        writer.writerow(summary_row)
    print(f"汇总已追加: {path}")
```

- [ ] **Step 2: Wire into main() — call both after batch loop**

Add after the batch loop:
```python
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    write_detail_csv(output_dir, args.experiment, detail_rows)
    append_summary_csv(output_dir, args.experiment, args.top_k, actual if args.top_k is not None else params["retrieval_top_k"], detail_rows)
    print("完成。")
```

### Task 6: End-to-end verification

- [ ] **Step 1: Verify the script runs end-to-end with the backend**

Ensure backend is running, then:
```bash
cd rag-backend && source .venv/bin/activate && python evaluate_compare.py --experiment topk3 --top-k 3
```
Expected: 10 questions processed, `eval_results/detail_topk3.csv` and `eval_results/summary.csv` created.

- [ ] **Step 2: Verify CSV content**

Check that `detail_topk3.csv` has 10 data rows + header, and `summary.csv` has 1 data row with correct summary stats.

- [ ] **Step 3: Run a second experiment to verify summary append**

```bash
cd rag-backend && source .venv/bin/activate && python evaluate_compare.py --experiment topk5 --top-k 5
```
Expected: `eval_results/detail_topk5.csv` created, `summary.csv` now has 2 data rows.
