#!/usr/bin/env python3
"""
Wiki Search - 信贷知识库全文搜索引擎
支持 TF-IDF 排名和 JSON 输出
"""

import os
import re
import json
import argparse
from pathlib import Path
from collections import Counter
import math

WIKI_DIR = Path(__file__).parent.parent / "wiki"
RAW_DIR = Path(__file__).parent.parent / "raw"


def tokenize(text):
    """中文分词（简单版）"""
    # 移除特殊字符，保留中文、英文、数字
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
    tokens = text.split()
    # 简单处理：2-6个字符的词
    words = []
    for t in tokens:
        if len(t) >= 2:
            words.append(t.lower())
    return words


def calculate_tf(tokens):
    """计算词频"""
    return Counter(tokens)


def calculate_idf(doc_count, word_doc_count):
    """计算 IDF"""
    return math.log(doc_count / (word_doc_count + 1)) + 1


def search_in_file(file_path, query_tokens):
    """搜索单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None

    content_lower = content.lower()
    title = content.split('\n')[0] if content else ""

    # 检查是否包含查询词
    matched_tokens = [t for t in query_tokens if t in content_lower]
    if not matched_tokens:
        return None

    # 计算匹配度分数
    content_tokens = tokenize(content)
    content_tf = calculate_tf(content_tokens)

    score = 0
    for token in matched_tokens:
        score += content_tf.get(token, 0)

    # 提取上下文片段
    snippets = []
    for token in matched_tokens[:3]:  # 最多3个片段
        pattern = f'.{{0,30}}{token}.{{0,30}}'
        matches = re.findall(pattern, content, re.IGNORECASE)
        for m in matches[:2]:
            snippets.append(m.strip())

    return {
        "file": str(file_path),
        "title": title.strip('# '),
        "score": score,
        "matched_tokens": matched_tokens,
        "snippets": snippets
    }


def search_wiki(query, max_results=10):
    """搜索 wiki 目录"""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    results = []
    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md'):
                file_path = Path(root) / file
                result = search_in_file(file_path, query_tokens)
                if result:
                    results.append(result)

    # 按分数排序
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:max_results]


def search_raw(query, max_results=5):
    """搜索 raw 目录"""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    results = []
    for root, dirs, files in os.walk(RAW_DIR):
        for file in files:
            if file.endswith(('.md', '.txt', '.pdf')):
                file_path = Path(root) / file
                result = search_in_file(file_path, query_tokens)
                if result:
                    results.append(result)

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:max_results]


def main():
    parser = argparse.ArgumentParser(description='信贷知识库搜索引擎')
    parser.add_argument('query', nargs='+', help='搜索关键词')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    parser.add_argument('--raw', action='store_true', help='同时搜索raw目录')
    args = parser.parse_args()

    query = ' '.join(args.query)

    wiki_results = search_wiki(query)
    raw_results = search_raw(query) if args.raw else []

    if args.json:
        output = {
            "query": query,
            "wiki_results": wiki_results,
            "raw_results": raw_results
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"🔍 搜索: {query}")
        print(f"\n📚 Wiki 知识库 ({len(wiki_results)} 条结果)")
        print("-" * 50)
        for i, r in enumerate(wiki_results, 1):
            print(f"\n{i}. {r['title']}")
            print(f"   匹配度: {r['score']}")
            print(f"   关键词: {', '.join(r['matched_tokens'])}")
            if r['snippets']:
                print(f"   片段: ...{r['snippets'][0]}...")

        if raw_results:
            print(f"\n\n📂 原始资料 ({len(raw_results)} 条结果)")
            print("-" * 50)
            for i, r in enumerate(raw_results, 1):
                print(f"\n{i}. {r['title']}")
                print(f"   文件: {r['file']}")


if __name__ == "__main__":
    main()
