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
import yaml
from pathlib import Path
from datetime import datetime

from graph_utils import (
    get_stable_doc_id, load_graph, save_graph, rebuild_graph,
    WIKI_DIR, RAW_DIR, GRAPH_FILE, CATEGORY_MAP
)


def get_raw_files():
    """获取所有原始资料"""
    files = []
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
    """提取文档元数据（支持 YAML frontmatter + 降级解析）"""
    metadata = {
        "title": "",
        "source": "",
        "date": "",
        "tags": [],
        "doc_id": ""
    }

    # 优先尝试 YAML frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1))
            if fm:
                metadata["title"] = fm.get("title", "")
                metadata["source"] = fm.get("source", "")
                metadata["date"] = fm.get("created", "")
                tags = fm.get("tags", [])
                if isinstance(tags, list):
                    metadata["tags"] = [t for t in tags if t != "report-required"]
                metadata["doc_id"] = str(fm.get("id", "")) or fm.get("doc_id", "")
        except yaml.YAMLError:
            pass

    # 降级：从正文第一行提取标题（# 标题）
    lines = content.split('\n')
    for line in lines:
        if line.startswith('# ') and not metadata["title"]:
            metadata["title"] = line.strip('# ').strip()
            break

    # 降级：解析正文中的 > 来源/归档时间
    for line in lines[:30]:
        if '来源' in line and ':' in line and not metadata["source"]:
            metadata["source"] = line.split('：', 1)[-1].strip().split(']')[0].strip('[')
        if '归档时间' in line and ':' in line and not metadata["date"]:
            metadata["date"] = line.split('：', 1)[-1].strip()

    return metadata


def analyze_first_principle(content, title):
    """分析第一性原理（跳过 frontmatter 头部，从正文分析区开始提取）"""
    # 跳过文档头部（标题 + 来源行 + frontmatter 残留）
    header_pattern = re.compile(r'^# .+\n+>\s*来源[：:].+\n+归档时间.*\n+文档ID.*\n+---\s*\n+', re.MULTILINE)
    body = header_pattern.sub('', content)

    # 定位 "底层事实" 之后的内容作为分析素材
    first_principle_marker = re.search(r'### 底层事实\s*\n+(.{10,})', body)
    analysis_text = first_principle_marker.group(1) if first_principle_marker else body

    sentences = re.split(r'[。\n]', analysis_text)
    key_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:5]

    first_principle_text = ' '.join(key_sentences[:2]) if key_sentences else '待分析'

    return {
        "底层事实": key_sentences[0] if key_sentences else "待分析",
        "根本原因": key_sentences[1] if len(key_sentences) > 1 else "待分析",
        "本质规律": f"【{title}】的核心规律：{first_principle_text}",
        "信贷应用": "待分析"
    }



def compile_to_wiki(raw_file, existing_graph=None):
    """将原始资料编译为 Wiki 格式"""
    with open(raw_file['path'], 'r', encoding='utf-8') as f:
        raw_content = f.read()

    metadata = extract_metadata(raw_content)

    # 跳过 YAML frontmatter 后再分析
    content_body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', raw_content, flags=re.DOTALL)
    first_principle = analyze_first_principle(content_body, metadata['title'])

    # 复用已有 doc_id（同一标题+分类保持稳定）
    doc_id = get_stable_doc_id(metadata['title'], raw_file['category'], existing_graph or {})
    if not doc_id:
        doc_id = uuid.uuid4().hex[:8]

    # 确定输出目录
    subdir = CATEGORY_MAP.get(raw_file['category'], 'articles')
    output_dir = WIKI_DIR / subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成 Wiki 文章（含标准化 frontmatter）
    wiki_content = f"""---
doc_id: {doc_id}
title: {metadata['title']}
date: {datetime.now().strftime('%Y-%m-%d')}
category: {raw_file['category']}
source: {metadata['source'] or ''}
tags:
{chr(10).join(f"  - {t}" for t in metadata['tags']) if metadata['tags'] else '  []'}
---

# {metadata['title']}

> 来源：{metadata['source'] or raw_file['path'].name}
> 归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
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

{content_body[:1000]}...

---

_关联关系由 graph_utils 统一从 wikilink 自动提取_
"""

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
    }


def main():
    parser = argparse.ArgumentParser(description='信贷知识库编译引擎')
    parser.add_argument('--file', '-f', help='指定编译单个文件')
    parser.add_argument('--category', '-c', help='指定编译分类')
    parser.add_argument('--all', '-a', action='store_true', help='编译所有原始资料')
    parser.add_argument('--dry-run', action='store_true', help='试运行不实际写入')
    args = parser.parse_args()

    graph = load_graph()
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
                # 增量更新图谱
                subdir = CATEGORY_MAP.get(raw_file['category'], 'articles')
                graph["documents"][doc_info['doc_id']] = {
                    "title": doc_info['title'],
                    "category": doc_info['category'],
                    "subcategory": subdir,
                    "first_principle": doc_info['first_principle'],
                    "key_tags": doc_info['key_tags'],
                    "created": datetime.now().strftime('%Y-%m-%d'),
                    "connections": []
                }

            compiled.append(doc_info)

        # 统一重建连接关系后保存
        if not args.dry_run:
            graph = rebuild_graph()
            save_graph(graph)

    else:
        print("用法: wiki-compile.py [--all|--category <name>|--file <path>]")
        return

    print(f"\n✅ 编译完成，共处理 {len(compiled)} 个文件")
    for doc in compiled:
        print(f"   - {doc['title']} ({doc['doc_id']})")


if __name__ == "__main__":
    main()
