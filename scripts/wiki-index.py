#!/usr/bin/env python3
"""
Wiki Index - 自动生成索引和统计
生成 INDEX.md, SUMMARY.md, STATS.md
"""

import os
import json
import argparse
from pathlib import Path
from collections import Counter

WIKI_DIR = Path(__file__).parent.parent / "wiki"
RAW_DIR = Path(__file__).parent.parent / "raw"
GRAPH_FILE = Path(__file__).parent.parent / "元数据" / "关联图谱.json"


def get_timestamp():
    return os.popen('date "+%Y-%m-%d %H:%M"').read().strip()


def get_all_articles():
    """获取所有文章"""
    articles = []
    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in ['INDEX.md', 'SUMMARY.md', 'STATS.md']:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(WIKI_DIR)

                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                title = ""
                tags = []
                doc_id = ""

                for line in lines[:20]:
                    if line.startswith('# ') and not title:
                        title = line.strip('# ').strip()
                    if '文档ID' in line or 'doc_id' in line.lower():
                        parts = line.split('：')
                        if len(parts) > 1:
                            doc_id = parts[-1].strip()
                    if '标签' in line:
                        tag_line = line.replace('标签', '').replace('：', ':').strip()
                        if ':' in tag_line:
                            tags = [t.strip() for t in tag_line.split(':')[-1].split()]

                articles.append({
                    "file": str(rel_path),
                    "title": title or file.replace('.md', ''),
                    "doc_id": doc_id,
                    "tags": tags
                })

    return articles


def get_categories():
    """按分类组织文章"""
    categories = {}
    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in ['INDEX.md', 'SUMMARY.md', 'STATS.md']:
                rel_path = Path(root).relative_to(WIKI_DIR)
                category = str(rel_path).split('/')[0] if str(rel_path) != '.' else 'root'

                if category not in categories:
                    categories[category] = []

                with open(Path(root) / file, 'r', encoding='utf-8') as f:
                    title = f.readline().strip('# \n') if f.readline().startswith('# ') else file

                categories[category].append({
                    "file": file,
                    "title": title
                })

    return categories


def generate_index_md():
    """生成 INDEX.md"""
    categories = get_categories()
    articles = get_all_articles()
    ts = get_timestamp()

    md = "# 📚 信贷知识库索引\n\n"
    md += f"> 自动生成时间: {ts}\n"
    md += f"> 共 {len(articles)} 篇文章\n\n"

    for category, arts in sorted(categories.items()):
        md += f"## 📂 {category}\n\n"
        for art in arts:
            md += f"- [[{art['title']}]]\n"
        md += "\n"

    return md


def generate_summary_md():
    """生成 SUMMARY.md"""
    articles = get_all_articles()
    graph_data = {}
    ts = get_timestamp()

    if GRAPH_FILE.exists():
        with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)

    md = "# 📊 信贷知识库摘要\n\n"
    md += f"> 自动生成时间: {ts}\n\n"

    # 关联统计
    docs = graph_data.get("documents", {})
    connections = graph_data.get("connection_reasons", {})

    md += "## 🔗 关联统计\n\n"
    md += f"- 文档总数: {len(docs)}\n"
    md += f"- 关联关系数: {len(connections)}\n\n"

    # 标签云
    all_tags = []
    for art in articles:
        all_tags.extend(art.get('tags', []))

    if all_tags:
        tag_counts = Counter(all_tags)
        md += "## 🏷️ 标签分布\n\n"
        for tag, count in tag_counts.most_common(20):
            md += f"- {tag}: {count}\n"

    return md


def generate_stats_md():
    """生成 STATS.md"""
    articles = get_all_articles()
    raw_count = 0
    ts = get_timestamp()

    for root, dirs, files in os.walk(RAW_DIR):
        raw_count += len(files)

    md = "# 📈 信贷知识库统计\n\n"
    md += f"> 统计时间: {ts}\n\n"

    md += "## 概览\n\n"
    md += "| 指标 | 数值 |\n"
    md += "|------|------|\n"
    md += f"| 编译文章数 | {len(articles)} |\n"
    md += f"| 原始资料数 | {raw_count} |\n"

    # 分类统计
    categories = get_categories()
    md += f"| 分类数 | {len(categories)} |\n\n"

    md += "## 分类详情\n\n"
    md += "| 分类 | 文章数 |\n"
    md += "|------|--------|\n"
    for cat, arts in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
        md += f"| {cat} | {len(arts)} |\n"

    return md


def main():
    parser = argparse.ArgumentParser(description='信贷知识库索引生成器')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    args = parser.parse_args()

    articles = get_all_articles()

    if args.json:
        output = {
            "articles": articles,
            "categories": get_categories(),
            "total": len(articles)
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # 生成并保存索引文件
        index_md = generate_index_md()
        with open(WIKI_DIR / "INDEX.md", 'w', encoding='utf-8') as f:
            f.write(index_md)

        summary_md = generate_summary_md()
        with open(WIKI_DIR / "SUMMARY.md", 'w', encoding='utf-8') as f:
            f.write(summary_md)

        stats_md = generate_stats_md()
        with open(WIKI_DIR / "STATS.md", 'w', encoding='utf-8') as f:
            f.write(stats_md)

        print(f"✅ 已生成索引文件:")
        print(f"   - INDEX.md ({len(articles)} 篇文章)")
        print(f"   - SUMMARY.md")
        print(f"   - STATS.md")


if __name__ == "__main__":
    main()
