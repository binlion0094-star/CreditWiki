#!/usr/bin/env python3
"""
Wiki Lint - 信贷知识库健康检查工具
检查断裂链接、重复概念、孤立文章、数据不一致
"""

import os
import re
import json
import argparse
import yaml
from pathlib import Path
from collections import defaultdict

WIKI_DIR = Path(__file__).parent.parent / "wiki"
GRAPH_FILE = Path(__file__).parent.parent / "元数据" / "关联图谱.json"


SYSTEM_FILES = ['INDEX.md', 'SUMMARY.md', 'STATS.md', 'TEMPLATE.md', 'README.md']


def _build_title_index():
    """从所有 wiki 文章的 frontmatter 中构建 title → filename 索引"""
    title_to_file = {}
    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in SYSTEM_FILES:
                fp = Path(root) / file
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 从 frontmatter 提取 title
                fm_m = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                title = None
                if fm_m:
                    try:
                        fm = yaml.safe_load(fm_m.group(1)) or {}
                        title = fm.get("title", "")
                    except:
                        pass
                # 降级：从第一行 # 标题
                if not title:
                    m = re.match(r'^# (.+)', content)
                    title = m.group(1).strip() if m else file
                title_to_file[title] = fp.name
                # 标准化版本（去标点）
                norm = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', title)
                title_to_file[norm] = fp.name
    return title_to_file


def check_broken_links():
    """检查断裂的 wikilink（用 frontmatter title 索引解析）"""
    broken_links = []
    wikilink_pattern = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]')

    # 构建全局 title → filename 索引
    title_index = _build_title_index()

    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in SYSTEM_FILES:
                file_path = Path(root) / file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                links = wikilink_pattern.findall(content)
                for link in links:
                    link_stripped = link.strip()
                    norm = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', link_stripped)
                    # 精确 → 标准化 → 模糊相似度，三级匹配
                    target_file = (
                        title_index.get(link_stripped)
                        or title_index.get(norm)
                        or _fuzzy_match(link_stripped, title_index)
                    )
                    if not target_file:
                        broken_links.append({
                            "file": str(file_path),
                            "broken_link": link_stripped
                        })

    return broken_links


def _fuzzy_match(link, index_dict, threshold=0.7):
    """模糊匹配：标题相似度 >= threshold 时认为匹配成功"""
    from difflib import SequenceMatcher
    best, best_s = None, 0
    for title in index_dict:
        s = SequenceMatcher(None, link, title).ratio()
        if s > best_s and s >= threshold:
            best_s, best = s, index_dict[title]
    return best


def check_duplicate_concepts():
    """检查重复概念（相似标题）"""
    duplicates = []
    titles = []

    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in SYSTEM_FILES:
                file_path = Path(root) / file
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                title = ""
                for line in lines[:5]:
                    if line.startswith('# '):
                        title = line.strip('# ').strip()
                        break

                if title:
                    titles.append({"file": str(file_path), "title": title})

    stop_words = {"的", "了", "在", "是", "和", "与", "对", "为", "于", "以及", "等"}
    for i, t1 in enumerate(titles):
        for t2 in titles[i+1:]:
            words1 = set(t1["title"]) - stop_words
            words2 = set(t2["title"]) - stop_words
            if words1 & words2 and len(words1 & words2) >= 3:
                duplicates.append({
                    "file1": t1["file"],
                    "title1": t1["title"],
                    "file2": t2["file"],
                    "title2": t2["title"]
                })

    return duplicates

SYSTEM_FILES = ['INDEX.md', 'SUMMARY.md', 'STATS.md', 'TEMPLATE.md', 'README.md']


def check_orphan_articles():
    """检查孤立文章（没有反向链接的文章）"""
    orphans = []
    wikilink_pattern = re.compile(r'\[\[([^\]]+)\]\]')

    # 收集所有链接
    all_links = set()
    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in SYSTEM_FILES:
                file_path = Path(root) / file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                links = wikilink_pattern.findall(content)
                for link in links:
                    all_links.add(link)

    # 检查没有被链接的文章
    for root, dirs, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith('.md') and file not in SYSTEM_FILES:
                file_path = Path(root) / file
                article_name = file.replace('.md', '')
                if article_name in SYSTEM_FILES:
                    continue

                if article_name not in all_links:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    title = ""
                    for line in lines[:5]:
                        if line.startswith('# '):
                            title = line.strip('# ').strip()
                            break

                    orphans.append({
                        "file": str(file_path),
                        "title": title or article_name
                    })

    return orphans


def check_data_consistency():
    """检查数据一致性"""
    issues = []

    graph_file = GRAPH_FILE
    if graph_file.exists():
        with open(graph_file, 'r', encoding='utf-8') as f:
            try:
                graph = json.load(f)

                for doc_id, doc_info in graph.get("documents", {}).items():
                    if not doc_info.get("title"):
                        issues.append({
                            "type": "missing_title",
                            "doc_id": doc_id
                        })

            except json.JSONDecodeError:
                issues.append({"type": "json_parse_error", "file": str(graph_file)})
    else:
        issues.append({"type": "graph_file_not_found", "file": str(graph_file)})

    return issues


def generate_report():
    """生成健康检查报告"""
    report = {
        "timestamp": os.popen('date "+%Y-%m-%d %H:%M:%S"').read().strip(),
        "broken_links": check_broken_links(),
        "duplicate_concepts": check_duplicate_concepts(),
        "orphan_articles": check_orphan_articles(),
        "data_consistency": check_data_consistency()
    }

    total_issues = (
        len(report["broken_links"]) +
        len(report["duplicate_concepts"]) +
        len(report["orphan_articles"]) +
        len(report["data_consistency"])
    )

    report["total_issues"] = total_issues
    return report


def main():
    parser = argparse.ArgumentParser(description='信贷知识库健康检查')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    parser.add_argument('--fix', action='store_true', help='尝试自动修复')
    args = parser.parse_args()

    report = generate_report()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"🏥 信贷知识库健康检查报告")
        print(f"生成时间: {report['timestamp']}")
        print("=" * 50)

        if report['total_issues'] == 0:
            print("✅ 知识库状态良好，无问题发现")
        else:
            print(f"⚠️  发现 {report['total_issues']} 个问题\n")

            if report['broken_links']:
                print(f"\n🔗 断裂链接 ({len(report['broken_links'])} 个)")
                for item in report['broken_links'][:5]:
                    print(f"   - {item['file']} → [[{item['broken_link']}]]")

            if report['duplicate_concepts']:
                print(f"\n📑 重复概念 ({len(report['duplicate_concepts'])} 个)")
                for item in report['duplicate_concepts'][:5]:
                    print(f"   - {item['title1']} ≈ {item['title2']}")

            if report['orphan_articles']:
                print(f"\n📚 孤立文章 ({len(report['orphan_articles'])} 个)")
                for item in report['orphan_articles'][:5]:
                    print(f"   - {item['title']}")

            if report['data_consistency']:
                print(f"\n⚙️  数据一致性问题 ({len(report['data_consistency'])} 个)")
                for item in report['data_consistency'][:5]:
                    print(f"   - {item}")


if __name__ == "__main__":
    main()
