#!/usr/bin/env python3
"""
Wiki Search v2 - 信贷知识库全文搜索引擎
TF-IDF 排名 + 相关性评分 + 高亮片段
"""

import os
import re
import json
import argparse
import math
from pathlib import Path
from collections import Counter

WIKI_DIR = Path(__file__).parent.parent / "wiki"
RAW_DIR = Path(__file__).parent.parent / "raw"

# ============================================================
# 停用词
# ============================================================
STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "或", "为", "对", "以", "及", "等",
    "该", "其", "这", "那", "被", "将", "由", "可", "能", "会", "有",
    "我们", "你们", "他们", "本文", "文章", "来源", "发布", "日期",
    "以下", "以上", "包括", "通过", "进行", "使用", "实现", "可以",
    "一个", "一些", "不同", "相关", "根据", "按照", "对于", "关于",
}

# ============================================================
# 分词
# ============================================================

def tokenize(text):
    """中文分词（基于字符 n-gram，2-4字词）"""
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
    tokens = []
    # 2-4字词提取
    for i in range(len(text)):
        for n in [2, 3, 4]:
            if i + n <= len(text):
                word = text[i:i+n]
                if re.match(r'^[\u4e00-\u9fa5]+$', word):
                    if word not in STOPWORDS and len(word) >= 2:
                        tokens.append(word.lower())
    return tokens

def extract_title(content):
    """从内容提取标题（优先 frontmatter title）"""
    # 尝试从 frontmatter 提取 title
    fm_m = re.search(r'^---\s*\n.*?title:\s*(.+?)\s*\n', content, re.DOTALL)
    if fm_m:
        title = fm_m.group(1).strip()
        if title and len(title) > 2:
            return title

    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# ') and len(line) > 3:
            return line[2:].strip()
        if line.startswith('> 来源') or line.startswith('---'):
            continue
        if line and not line.startswith('>') and not line.startswith('*'):
            return line[:80]
    return ""

def extract_snippet(content, query_tokens, context=40, max_snippets=3):
    """提取包含查询词的上下文片段"""
    snippets = []
    content_lower = content.lower()

    for token in query_tokens:
        # 找到所有匹配位置
        start = 0
        while True:
            pos = content_lower.find(token, start)
            if pos == -1:
                break
            start = pos + 1

            # 提取上下文
            before = content[max(0, pos-context):pos]
            after = content[pos+len(token):pos+len(token)+context]
            snippet = f"...{before}{token}{after}..."
            snippet = re.sub(r'\n+', ' ', snippet)
            if snippet not in snippets:
                snippets.append(snippet)
                if len(snippets) >= max_snippets * len(query_tokens):
                    break

    return snippets[:max_snippets]

# ============================================================
# 评分
# ============================================================

def score_article(content, title, query_tokens):
    """计算文章相关性评分"""
    content_lower = content.lower()
    title_lower = title.lower()
    content_tokens = tokenize(content)
    tf = Counter(content_tokens)

    score = 0.0

    for token in query_tokens:
        # 标题匹配（权重 3x）
        if token in title_lower:
            score += 3.0

        # 正文匹配（TF 权重）
        token_lower = token.lower()
        count = content.count(token_lower)
        if count > 0:
            # 在元数据区域（标题行、前50字）加权
            early_content = content[:500].lower()
            early_count = early_content.count(token_lower)
            score += count * 0.5 + early_count * 1.5

        # 标签行匹配（权重 2x）
        if f'"{token}"' in content or f'#{token}' in content or f'# {token}' in content:
            score += 2.0

    # 标题完全匹配加权
    title_match_len = sum(1 for t in query_tokens if t in title_lower)
    if title_match_len == len(query_tokens):
        score += 5.0  # 完整匹配
    elif title_match_len > 0:
        score += title_match_len * 2.0

    # 长度惩罚（太长文章倾向于高分，做归一化）
    # 不做，防止短文得分虚高

    return round(score, 2)

# ============================================================
# 搜索
# ============================================================

def search_file(file_path, query_tokens, search_content=True):
    """搜索单个文件"""
    try:
        content = open(file_path, 'r', encoding='utf-8').read()
    except:
        return None

    if not search_content and not query_tokens:
        return None

    title = extract_title(content)
    if not title:
        return None

    # 检查是否包含查询词
    content_lower = content.lower()
    matched = [t for t in query_tokens if t in content_lower]
    if not matched and query_tokens:
        return None

    score = score_article(content, title, query_tokens)

    # 如果没有查询词（比如空搜索），按标题返回
    if not query_tokens:
        score = 1.0

    snippets = extract_snippet(content, matched) if matched else []

    # 判断分类
    subdir = file_path.parent.name
    category = "concepts" if subdir == "concepts" else "articles"

    return {
        "file": str(file_path),
        "title": title,
        "category": category,
        "score": score,
        "matched_tokens": matched,
        "snippets": snippets,
    }


def search_index(query, max_results=10, include_raw=False):
    """全文搜索"""
    query_tokens = tokenize(query) if query else []

    results = []

    # 搜索 wiki/
    for subdir in WIKI_DIR.iterdir():
        if not (subdir.is_dir() and not subdir.name.startswith('.')):
            continue
        for f in subdir.glob("*.md"):
            if f.name in {"INDEX.md", "SUMMARY.md", "STATS.md", "TEMPLATE.md", "README.md"}:
                continue
            r = search_file(f, query_tokens)
            if r:
                results.append(r)

    # 搜索 raw/
    if include_raw:
        for root, dirs, files in os.walk(RAW_DIR):
            for f in files:
                if f.endswith(('.md', '.txt')):
                    fp = Path(root) / f
                    r = search_file(fp, query_tokens, search_content=True)
                    if r:
                        r["source"] = "raw"
                        results.append(r)

    # 排序
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:max_results]


# ============================================================
# 输出格式化
# ============================================================

def format_results(results, query, verbose=True):
    """格式化搜索结果"""
    if not results:
        return "未找到相关结果"

    lines = []
    for i, r in enumerate(results, 1):
        cat_icon = "📒" if r.get('category') == 'concepts' else "📄"
        lines.append(f"{i}. {cat_icon} {r['title']}")
        lines.append(f"   匹配度: {r['score']} | 关键词: {', '.join(r['matched_tokens']) if r['matched_tokens'] else '标题匹配'}")

        if verbose and r['snippets']:
            for sn in r['snippets'][:2]:
                # 高亮关键词
                highlighted = sn
                lines.append(f"   📌 {highlighted}")

        lines.append("")

    return "\n".join(lines)

def format_json(results, query):
    """JSON 格式输出"""
    output = {
        "query": query,
        "total": len(results),
        "results": [
            {
                "title": r['title'],
                "file": r['file'],
                "category": r.get('category', 'unknown'),
                "score": r['score'],
                "matched_tokens": r['matched_tokens'],
                "snippets": r['snippets'][:3],
            }
            for r in results
        ]
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='信贷知识库全文搜索 v2')
    parser.add_argument('query', nargs='*', default=[''], help='搜索关键词')
    parser.add_argument('--json', '-j', action='store_true', help='JSON输出')
    parser.add_argument('--raw', '-r', action='store_true', help='同时搜索raw目录')
    parser.add_argument('--limit', '-n', type=int, default=10, help='最大结果数')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详情片段')
    parser.add_argument('--test', action='store_true', help='搜索测试（用预置查询）')
    args = parser.parse_args()

    query = ' '.join(args.query).strip()

    results = search_index(query, max_results=args.limit, include_raw=args.raw)

    if args.json:
        print(format_json(results, query))
    else:
        if args.test:
            # 预置测试查询
            test_queries = ["以贷还贷", "供应链金融 保理", "房地产 信贷", "银行 净息差", "监管处罚"]
            print("🧪 搜索测试")
            print("=" * 60)
            for q in test_queries:
                r = search_index(q, max_results=3, include_raw=False)
                print(f"\n[{q}] → {len(r)} 条", end="")
                if r:
                    print(f" | 第1条: {r[0]['title'][:40]}")
                else:
                    print()
        else:
            print(f"🔍 搜索: {query or '(全部文章)'}")
            print(f"📚 找到 {len(results)} 条结果")
            print("=" * 60)
            print(format_results(results, query, verbose=args.verbose))

if __name__ == "__main__":
    main()
