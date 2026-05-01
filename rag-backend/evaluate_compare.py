#!/usr/bin/env python3
"""RAG 系统对比测试脚本 — 批量运行问答并记录结果。

用法:
    python evaluate_compare.py --experiment topk3 --top-k 3
    python evaluate_compare.py --experiment topk5 --top-k 5
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error

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


def parse_args():
    parser = argparse.ArgumentParser(description="RAG 系统对比测试")
    parser.add_argument("--experiment", required=True, help="实验名称，如 topk3")
    parser.add_argument("--top-k", type=int, help="本轮实验要设置的 Top-K")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="后端服务地址")
    parser.add_argument("--questions", default="eval_questions.json", help="测试集路径")
    parser.add_argument("--output-dir", default="eval_results", help="输出目录")
    parser.add_argument("--delay", type=float, default=0.5, help="每个问题之间的等待秒数")
    return parser.parse_args()


def set_top_k(base_url, top_k):
    """设置后端 Top-K 并返回确认后的 actual_top_k。失败时抛异常。"""
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


def get_parameters(base_url):
    """获取知识库参数并返回关键字段。"""
    try:
        with urllib.request.urlopen(f"{base_url}/knowledge-base/parameters", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET parameters 失败 (HTTP {e.code}): {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接后端: {e.reason}")


def ask_question(base_url, question):
    """调用 POST /ask 并返回完整响应字典，含 _success/_error 标记。"""
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


def make_detail_row(experiment, configured_top_k, actual_top_k, q, resp):
    """将问题和响应组装为明细 CSV 的一行。"""
    metrics = resp.get("metrics") or {}
    sources = resp.get("sources") or []
    answer = resp.get("answer") or ""
    return {
        "experiment": experiment,
        "configured_top_k": configured_top_k,
        "actual_top_k": actual_top_k,
        "question_id": q["id"],
        "question": q["question"],
        "language": q.get("language", ""),
        "category": q.get("category", ""),
        "success": resp["_success"],
        "answer": answer.replace("\n", "\\n"),
        "sources_count": len(sources),
        "sources": "||".join(sources),
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


def write_detail_csv(output_dir, experiment, rows):
    path = os.path.join(output_dir, f"detail_{experiment}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"明细已保存: {path}")


def append_summary_csv(output_dir, experiment, configured_top_k, actual_top_k, rows):
    path = os.path.join(output_dir, "summary.csv")
    exist = os.path.exists(path)

    success_rows = [r for r in rows if r["success"]]
    times = [r["response_time_ms"] for r in success_rows if isinstance(r.get("response_time_ms"), (int, float))]
    retrieval_times = [r["retrieval_time_ms"] for r in success_rows if isinstance(r.get("retrieval_time_ms"), (int, float))]
    gen_times = [r["generation_time_ms"] for r in success_rows if isinstance(r.get("generation_time_ms"), (int, float))]
    source_counts = [r["sources_count"] for r in success_rows if isinstance(r.get("sources_count"), int)]

    summary_row = {
        "experiment": experiment,
        "configured_top_k": configured_top_k,
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


def main():
    args = parse_args()
    print(f"实验: {args.experiment}")
    print(f"后端: {args.base_url}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    actual_top_k = None
    if args.top_k is not None:
        print(f"设置 Top-K = {args.top_k} ...")
        actual_top_k = set_top_k(args.base_url, args.top_k)
        print(f"已确认 Top-K = {actual_top_k}")

    params = get_parameters(args.base_url)
    print(f"知识库: {params['collection_name']} ({params['collection_count']} 条)")
    print(f"嵌入模型: {params['embedding_model']} ({params['onnx_provider']})")
    print(f"LLM: {params['llm_model']}, API Key: {params['api_key_configured']}")

    if not params["api_key_configured"]:
        print("错误: API Key 未配置，请先在前端或环境变量中设置 OPENAI_API_KEY")
        sys.exit(1)

    if actual_top_k is None:
        actual_top_k = params["retrieval_top_k"]

    questions_path = os.path.join(script_dir, args.questions)
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    print(f"加载 {len(questions)} 个测试问题")
    print("-" * 60)

    detail_rows = []
    success_count = 0
    for i, q in enumerate(questions, 1):
        qid = q["id"]
        qtext = q["question"]
        print(f"[{i}/{len(questions)}] {qid}: {qtext[:60]}{'...' if len(qtext) > 60 else ''}")
        resp = ask_question(args.base_url, qtext)

        row = make_detail_row(args.experiment, args.top_k, actual_top_k, q, resp)
        detail_rows.append(row)

        if resp["_success"]:
            success_count += 1
            metrics = resp.get("metrics") or {}
            sources = resp.get("sources") or []
            print(f"    sources={len(sources)}, time={metrics.get('response_time_ms', 'N/A')}ms")
        else:
            print(f"    失败: {resp['_error'][:80]}")

        if args.delay > 0 and i < len(questions):
            time.sleep(args.delay)

    print("-" * 60)
    print(f"完成: {success_count}/{len(questions)} 成功")

    write_detail_csv(output_dir, args.experiment, detail_rows)
    append_summary_csv(output_dir, args.experiment, args.top_k, actual_top_k, detail_rows)


if __name__ == "__main__":
    main()
