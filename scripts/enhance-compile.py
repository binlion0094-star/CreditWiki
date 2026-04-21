#!/usr/bin/env python3
"""
增强版 Wiki Compile v2 - 修复标签提取 + 自动构建关联骨架
- 统一加载 graph，避免重复 doc_id
- 支持 YAML 和内联两种标签格式
- 自动构建同分类/同企业关联
"""

import os, re, json, uuid, yaml
from pathlib import Path
from datetime import datetime

from graph_utils import (
    get_stable_doc_id, load_graph, save_graph, rebuild_graph,
    WIKI_DIR, RAW_DIR, GRAPH_FILE, CATEGORY_MAP
)


def extract_tags(content):
    """从 frontmatter 或内联格式提取标签"""
    tags = []
    fm = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if fm:
        try:
            fm_data = yaml.safe_load(fm.group(1)) or {}
            raw_tags = fm_data.get('tags', [])
            if isinstance(raw_tags, list):
                tags = [t for t in raw_tags if t and t != 'report-required']
        except:
            pass
    if not tags:
        inline = re.search(r'> 标签：(.+)', content)
        if inline:
            raw = inline.group(1)
            # | 分隔 or 空格分隔
            if '|' in raw:
                tags = [t.strip() for t in raw.split('|') if t.strip()]
            else:
                tags = [t for t in raw.split() if t.strip()]
    return tags


def extract_category(content):
    cat_m = re.search(r'> 分类：(.+)', content)
    if cat_m:
        return cat_m.group(1).strip().split('>')[0].strip()
    return None


def compile_single(raw_path, graph):
    """编译单个文件（复用已有 doc_id）"""
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    title = ""
    for line in raw.split('\n'):
        m = re.match(r'^# (.+)', line)
        if m:
            title = m.group(1).strip()
            break

    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', raw, flags=re.DOTALL)
    tags = extract_tags(raw)
    inline_cat = extract_category(raw)
    cat = inline_cat or raw_path.parent.name

    # 复用已有 ID
    doc_id = get_stable_doc_id(title, cat, graph)
    if not doc_id:
        doc_id = uuid.uuid4().hex[:8]

    # 第一性原理
    fp_m = re.search(r'### 底层事实\s*\n+(.{10,})', body)
    segs = re.split(r'[。\n]', (fp_m.group(1) if fp_m else body)[:500])
    key_sents = [s.strip() for s in segs if len(s.strip()) > 20][:3]
    fp_text = ' '.join(key_sents[:2]) if key_sents else '待分析'

    # Wiki 输出
    subdir = CATEGORY_MAP.get(cat, 'articles')
    output_dir = WIKI_DIR / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '_', title)[:50]
    out_file = output_dir / f"{safe}_{doc_id}.md"

    wiki_content = f"""---
doc_id: {doc_id}
title: {title}
date: {datetime.now().strftime('%Y-%m-%d')}
category: {cat}
source: {inline_cat or ''}
tags:
{chr(10).join(f"  - {t}" for t in tags) if tags else '  []'}
---

# {title}

> 归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 文档ID：{doc_id}
> 分类：{cat}

---

## 🔬 第一性原理分析

### 核心规律
【{title}】的核心规律：{fp_text}

### 信贷应用
待分析

---

## 📌 核心要点

{body[:800]}...

---

_本条目由 CreditWiki 自动编译生成_
"""

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(wiki_content)

    return {
        'doc_id': doc_id, 'title': title, 'category': cat,
        'subcategory': subdir, 'key_tags': tags,
        'first_principle': f"【{title}】的核心规律：{fp_text}",
        'file': str(out_file)
    }


def auto_link(doc, all_docs):
    """自动建立关联"""
    connections = []
    my_title = doc['title']
    my_tags = set(doc['key_tags'])
    my_cat = doc['category']

    for oid, other in all_docs.items():
        if oid == doc['doc_id']:
            continue
        reason = None

        # 同分类 + 共享标签
        if other.get('category') == my_cat and my_tags:
            shared = my_tags & set(other.get('key_tags', []))
            if shared:
                reason = f"同{my_cat}，共享标签: {'/'.join(list(shared)[:2])}"

        # 企业/银行 → 监管政策
        if not reason:
            for tag in my_tags:
                if tag in other.get('title', '') and other.get('category') == '监管政策':
                    reason = f"涉及{tag}，关联监管政策"
                    break

        # 票据/信贷 → 银行
        if not reason and ('票据' in my_title or '信贷' in my_title):
            if '银行' in other.get('title', '') and '授信' in other.get('title', ''):
                reason = "票据/信贷业务关联银行授信政策"

        # 行业研究 → 十五五
        if not reason and my_cat == '行业研究' and '十五五' in other.get('title', ''):
            reason = "行业研究与十五五产业布局关联"

        if reason:
            connections.append((oid, reason))

    seen, result = set(), []
    for cid, r in connections:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result[:5]


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--all', action='store_true')
    p.add_argument('--category', '-c')
    p.add_argument('--reindex', action='store_true', help='重建索引和图谱（不重新编译）')
    args = p.parse_args()

    if args.reindex:
        rebuild_graph()
        save_graph(rebuild_graph())
        import subprocess
        subprocess.run(['python3', 'scripts/wiki-index.py'])
        print("✅ 索引重建完成")
        return

    # 预加载 graph（只加载一次）
    graph = load_graph()

    raw_files = []
    for cat_dir in RAW_DIR.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith('.'):
            continue
        if args.category and cat_dir.name != args.category:
            continue
        raw_files.extend(cat_dir.glob('*.md'))

    compiled = []
    for rf in raw_files:
        print(f"📚 {rf.parent.name}/{rf.name}")
        try:
            doc = compile_single(rf, graph)
            compiled.append(doc)
            # 更新内存中的 graph
            graph['documents'][doc['doc_id']] = {
                'title': doc['title'], 'category': doc['category'],
                'subcategory': doc['subcategory'],
                'first_principle': doc['first_principle'],
                'key_tags': doc['key_tags'],
                'created': datetime.now().strftime('%Y-%m-%d'),
                'connections': []
            }
        except Exception as e:
            print(f"  ⚠️ {e}")

    # 批量自动关联
    for did, doc_data in graph['documents'].items():
        doc_data['connections'] = auto_link(
            {'doc_id': did, 'title': doc_data.get('title', ''),
             'category': doc_data.get('category', ''),
             'key_tags': doc_data.get('key_tags', [])},
            graph['documents']
        )

    for did, doc_data in graph['documents'].items():
        for tid in doc_data.get('connections', []):
            key = f"{did}-{tid}"
            if key not in graph.get('connection_reasons', {}):
                graph.setdefault('connection_reasons', {})[key] = "自动关联"

    save_graph(graph)
    rebuild_graph()
    save_graph(graph)

    print(f"\n✅ 完成：{len(compiled)} 篇 | 图谱 {len(graph['documents'])} 文档 | {len(graph.get('connection_reasons', {}))} 条关联")


if __name__ == "__main__":
    main()
