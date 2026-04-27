import os
import json
import argparse
import math
import re
import time
from dataclasses import dataclass
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tqdm import tqdm

# === 配置 ===
# （重要）请在这里定义您的领域背景，这将指导模型生成相关问题。
DOMAIN_CONTEXT = """
This context pertains to a general medical and health advisory knowledge base.
The knowledge base contains information provided by doctors and healthcare professionals on a wide range of topics, including but not limited to:
Common Symptoms: Dizziness, nausea, fever, fatigue, headaches, stomach pain, rashes, and breathing difficulties.
Specific Conditions: Benign Paroxysmal Positional Vertigo (BPPV), viral diarrhea, diabetes, hypertension, and common colds.
Medication Inquiries: Questions about side effects, drug interactions (e.g., Oxycodone), and safety during pregnancy or breastfeeding.
Pediatric Health: Issues related to infants and children, such as feeding, vaccination schedules, fevers, and developmental milestones.
Lifestyle and Prevention: Advice on diet, exercise, stress management, and preventive screenings.
Surgical and Post-Op Care: Queries about recovery after surgery, pain management, and wound care.
Mental Health: Questions concerning anxiety, depression, and stress.
Dermatology: Skin conditions like acne, eczema, and rashes.
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_env_int(name: str, default: int, minimum: Optional[int] = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        print(f"⚠️ 环境变量 {name}={raw_value!r} 不是整数，使用默认值 {default}。")
        return default
    if minimum is not None and value < minimum:
        print(f"⚠️ 环境变量 {name}={value} 小于 {minimum}，使用 {minimum}。")
        return minimum
    return value


# 定义要生成的查询总数
TOTAL_QUERIES = get_env_int("TOTAL_QUERIES", 300, minimum=1)
# 定义每次API调用生成的查询数量
QUERIES_PER_BATCH = get_env_int("QUERIES_PER_BATCH", 10, minimum=1)
# 输出文件名
OUTPUT_FILE = os.path.join(BASE_DIR, "healthcaremagicR/generated_queries300.json")

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
MAX_ATTEMPTS_MULTIPLIER = get_env_int("MAX_ATTEMPTS_MULTIPLIER", 4, minimum=1)


@dataclass
class QueryGenerationConfig:
    total_queries: int = TOTAL_QUERIES
    queries_per_batch: int = QUERIES_PER_BATCH
    output_file: str = OUTPUT_FILE
    api_base: str = OPENAI_API_BASE
    model: str = LLM_MODEL
    temperature: float = 0.7
    max_attempts_multiplier: int = MAX_ATTEMPTS_MULTIPLIER


def require_openai_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("请先设置环境变量 OPENAI_API_KEY")


def clean_query(line: str) -> str:
    query = line.strip()
    query = re.sub(r"^\s*(?:[-*•]|\d+[\).、]|[A-Za-z][\).])\s*", "", query)
    query = query.strip().strip("\"'“”‘’")
    query = re.sub(r"\s+", " ", query)
    return query


def parse_queries(response: str) -> List[str]:
    cleaned_queries = []
    for line in response.splitlines():
        query = clean_query(line)
        if not query:
            continue
        if query.lower() in {"questions:", "question:"}:
            continue
        cleaned_queries.append(query)
    return cleaned_queries


def save_queries(queries: List[str], output_file: str) -> None:
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(queries, f, indent=2, ensure_ascii=False)


def build_chain(config: QueryGenerationConfig):
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        openai_api_base=config.api_base,
    )
    prompt_template = ChatPromptTemplate.from_messages([
        (
            "system",
            (
                "You are an expert assistant specialized in formulating user questions. "
                "Generate diverse, realistic user questions based on the provided context. "
                "Do not answer the questions. Return only one question per line, without numbering."
            ),
        ),
        (
            "human",
            (
                "Based on the following context, generate exactly {batch_size} unique user questions.\n"
                "Avoid repeating any of these existing questions:\n{existing_queries}\n\n"
                "CONTEXT:\n{context}\n\nQUESTIONS:"
            ),
        ),
    ])
    return prompt_template | llm | StrOutputParser()


def generate_queries(config: Optional[QueryGenerationConfig] = None) -> List[str]:
    """
    使用DeepSeek模型生成指定领域的查询。
    """
    config = config or QueryGenerationConfig()
    require_openai_api_key()

    print("🚀 开始生成查询...")

    chain = build_chain(config)
    unique_queries = []
    seen_queries = set()
    max_attempts = math.ceil(config.total_queries / config.queries_per_batch) * config.max_attempts_multiplier
    attempts = 0

    with tqdm(total=config.total_queries, desc="生成查询中") as pbar:
        while len(unique_queries) < config.total_queries and attempts < max_attempts:
            attempts += 1
            remaining = config.total_queries - len(unique_queries)
            batch_size = min(config.queries_per_batch, remaining)
            response = chain.invoke({
                "context": DOMAIN_CONTEXT,
                "batch_size": batch_size,
                "existing_queries": "\n".join(unique_queries[-50:]) or "(none)",
            })
            added = 0
            for query in parse_queries(response):
                normalized_query = query.casefold()
                if normalized_query in seen_queries:
                    continue
                seen_queries.add(normalized_query)
                unique_queries.append(query)
                added += 1
                if len(unique_queries) >= config.total_queries:
                    break
            pbar.update(added)
            if added == 0:
                time.sleep(0.5)

    final_queries = unique_queries[:config.total_queries]
    save_queries(final_queries, config.output_file)
    print(f"\n🎉 查询生成完成！")
    print(f"总共生成了 {len(final_queries)} 个独立查询，并已保存到 '{config.output_file}'。")
    if len(final_queries) < config.total_queries:
        print(f"⚠️ 未达到目标数量 {config.total_queries}，可调大 MAX_ATTEMPTS_MULTIPLIER 后重试。")
    return final_queries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 HealthcareMagic RAG 评测查询")
    parser.add_argument("--total", type=int, default=TOTAL_QUERIES)
    parser.add_argument("--batch-size", type=int, default=QUERIES_PER_BATCH)
    parser.add_argument("--output-file", default=OUTPUT_FILE)
    parser.add_argument("--model", default=LLM_MODEL)
    parser.add_argument("--api-base", default=OPENAI_API_BASE)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-attempts-multiplier", type=int, default=MAX_ATTEMPTS_MULTIPLIER)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> QueryGenerationConfig:
    return QueryGenerationConfig(
        total_queries=max(1, args.total),
        queries_per_batch=max(1, args.batch_size),
        output_file=args.output_file,
        api_base=args.api_base,
        model=args.model,
        temperature=args.temperature,
        max_attempts_multiplier=max(1, args.max_attempts_multiplier),
    )


if __name__ == "__main__":
    generate_queries(config_from_args(parse_args()))
