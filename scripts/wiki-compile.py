#!/usr/bin/env python3
"""
Wiki Compile - 信贷知识库核心编译引擎
将原始资料编译为结构化 Wiki
"""

import os
import re
import json
import uuid
import argparse
from pathlib import Path
from datetime import datetime

WIKI_DIR = Path(__file__).parent.parent / "wiki"
RAW_DIR = Path(__file__).parent.parent / "raw"
GRAPH_FILE = Path(__file__).parent.parent / "元数据" / "关联图谱.json"


# 信贷知识库分类映射
CATEGORY_MAP = {
    "企业财报": "concepts",
    "行业研究": "articles",
    "监管政策": "concepts",
    "法院判决": "articles",
    "信贷合同": "concepts"
}


def get_raw_files():
    """获取所有原始资料"""
    files = []
    for root, dirs, folders in os.walk(RAW_DIR):
        for file in files:
            pass
    for category in RAW_DIR.iterdir():
        if category.is_dir() and not category.name.startswith('.'):
            for file in category.iterdir():
                if file.suffix in ['.md', '.txt', '.pdf']:
                    files.append({
                        "path": file,
                        "category": category.name,
                        "name": file.stem
                    })
    return files


def extract_metadata(content):
    """提取文档元数据"""
    metadata = {
        "title": "",
        "source": "",
        "date": "",
        "tags": [],
        "doc_id": ""
    }

    lines = content.split('\n')
    for line in lines[:20]:
        if line.startswith('# '):
            metadata["title"] = line.strip('# ').strip()
        if '来源' in line and ':' in line:
            metadata["source"] = line.split(':')[1].strip()
        if '时间' in line and ':' in line:
            metadata["date"] = line.split(':')[1].strip()
        if '标签' in line and ':' in line:
            tags_str = line.split(':')[1].strip()
            metadata["tags"] = [t.strip() for t in tags_str.split() if t.strip()]

    return metadata


def analyze_first_principle(content, title):
    """分析第一性原理（模拟，实际由LLM完成）"""
    # 提取核心句子
    sentences = re.split(r'[。\n]', content)
    key_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:5]

    # 生成本质规律摘要
    first_principle = f"【{title}】的核心规律：{' '.join(key_sentences[:2])}"

    return {
        "底层事实": key_sentences[0] if key_sentences else "",
        "根本原因": key_sentences[1] if len(key_sentences) > 1 else "",
        "本质规律": first_principle,
        "信贷应用": "待分析"
    }


def find_related_docs(current_doc_id, content, existing_graph):
    """查找关联文档"""
    related = []

    if not existing_graph:
        return related

    current_tags = set()
    current_words = set(re.findall(r'[\u4e00-\u9fa5]{4,}', content))

    for doc_id, doc_info in existing_graph.get("documents", {}).items():
        if doc_id == current_doc_id:
            continue

        doc_tags = set(doc_info.get("key_tags", []))
        doc_words = set(re.findall(r'[\u4e00-\u9fa5]{4,}', doc_info.get("first_principle", "")))

        # 计算关联度
        tag_overlap = len(current_tags & doc_tags)
        word_overlap = len(current_words & doc_words)

        if tag_overlap >= 1 or word_overlap >= 3:
            related.append({
                "doc_id": doc_id,
                "title": doc_info.get("title", ""),
                "reason": doc_info.get("first_principle", "")[:50]
            })

    return related[:3]


def compile_to_wiki(raw_file, existing_graph=None):
    """将原始资料编译为 Wiki 格式"""
    with open(raw_file['path'], 'r', encoding='utf-8') as f:
        content = f.read()

    metadata = extract_metadata(content)
    first_principle = analyze_first_principle(content, metadata['title'])

    doc_id = uuid.uuid4().hex[:8]
    related = find_related_docs(doc_id, content, existing_graph or {})

    # 确定输出目录
    subdir = CATEGORY_MAP.get(raw_file['category'], 'articles')
    output_dir = WIKI_DIR / subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成 Wiki 文章
    wiki_content = f"""# {metadata['title']}

> 来源：{metadata['source'] or raw_file['path'].name}
> 归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 标签：{' '.join(metadata['tags']) if metadata['tags'] else raw_file['category']}
> 文档ID：{doc_id}

---

## 🔬 第一性原理分析

### 底层事实
{first_principle['底层事实']}

### 根本原因
{first_principle['根本原因']}

### 本质规律
{first_principle['本质规律']}

### 信贷应用
{first_principle['信贷应用']}

---

## 📌 核心要点

{content[:1000]}...

---

## 🔗 关联文档

"""

    for rel in related:
        wiki_content += f"- [[{rel['title']}]]：{rel['reason']}\n"

    if not related:
        wiki_content += "_暂无关联文档_\n"

    # 保存文件
    safe_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '_', metadata['title'])[:50]
    output_file = output_dir / f"{safe_name}_{doc_id}.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(wiki_content)

    return {
        "doc_id": doc_id,
        "title": metadata['title'],
        "category": raw_file['category'],
        "subcategory": subdir,
        "first_principle": first_principle['本质规律'],
        "key_tags": metadata['tags'],
        "file": str(output_file),
        "related": [r['doc_id'] for r in related]
    }


def update_graph(new_doc_info, existing_graph=None):
    """更新关联图谱"""
    if existing_graph is None:
        existing_graph = {"documents": {}, "connection_reasons": {}}

    doc_id = new_doc_info['doc_id']

    # 添加文档
    existing_graph["documents"][doc_id] = {
        "title": new_doc_info['title'],
        "category": new_doc_info['category'],
        "subcategory": new_doc_info['subcategory'],
        "first_principle": new_doc_info['first_principle'],
        "key_tags": new_doc_info['key_tags'],
        "created": datetime.now().strftime('%Y-%m-%d'),
        "connections": new_doc_info['related']
    }

    # 添加关联关系
    for rel_id in new_doc_info['related']:
        key = f"{doc_id}-{rel_id}"
        existing_graph["connection_reasons"][key] = "领域关联"

    return existing_graph


def main():
    parser = argparse.ArgumentParser(description='信贷知识库编译引擎')
    parser.add_argument('--file', '-f', help='指定编译单个文件')
    parser.add_argument('--category', '-c', help='指定编译分类')
    parser.add_argument('--all', '-a', action='store_true', help='编译所有原始资料')
    parser.add_argument('--dry-run', action='store_true', help='试运行不实际写入')
    args = parser.parse_args()

    # 加载现有图谱
    graph = {}
    if GRAPH_FILE.exists():
        with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
            graph = json.load(f)

    compiled = []

    if args.all or args.category or args.file:
        raw_files = get_raw_files()

        for raw_file in raw_files:
            if args.category and raw_file['category'] != args.category:
                continue
            if args.file and args.file not in str(raw_file['path']):
                continue

            print(f"📚 编译: {raw_file['path'].name}")

            doc_info = compile_to_wiki(raw_file, graph)

            if not args.dry_run:
                graph = update_graph(doc_info, graph)

            compiled.append(doc_info)

        # 保存图谱
        if not args.dry_run:
            GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
                json.dump(graph, f, ensure_ascii=False, indent=2)

    else:
        print("用法: wiki-compile.py [--all|--category <name>|--file <path>]")
        return

    print(f"\n✅ 编译完成，共处理 {len(compiled)} 个文件")
    for doc in compiled:
        print(f"   - {doc['title']} ({doc['doc_id']})")


if __name__ == "__main__":
    main()
