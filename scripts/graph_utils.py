#!/usr/bin/env python3
"""
graph_utils.py — 关联图谱统一管理模块
供 wiki-compile / wiki-index / wiki-lint 共享使用
"""

import json
import re
import yaml
from pathlib import Path
from difflib import SequenceMatcher

WIKI_DIR = Path(__file__).parent.parent / "wiki"
RAW_DIR  = Path(__file__).parent.parent / "raw"
GRAPH_FILE = Path(__file__).parent.parent / "元数据" / "关联图谱.json"
CATEGORY_MAP = {
    "企业财报": "concepts",
    "行业研究": "articles",
    "监管政策": "concepts",
    "法院判决": "articles",
    "信贷合同": "concepts"
}
SYSTEM_FILES = {'INDEX.md', 'SUMMARY.md', 'STATS.md', 'TEMPLATE.md', 'README.md'}


# ── 读写图谱 ───────────────────────────────────────────────────

def load_graph():
    if GRAPH_FILE.exists():
        with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"documents": {}, "connection_reasons": {}}


def save_graph(graph):
    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)


# ── 构建标题索引（支持精确+标准化+模糊三级匹配） ──────────────────

def build_title_index(articles=None):
    """建立 title → doc_id 映射"""
    if articles is None:
        graph = load_graph()
        articles = graph.get("documents", {})

    title_index = {}
    for doc_id, doc in articles.items():
        title = doc.get("title", "")
        if title:
            title_index[title] = doc_id
            title_index[normalize(title)] = doc_id
    return title_index


def normalize(s):
    return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', str(s))


def fuzzy_match(link, index, threshold=0.65):
    """模糊匹配，返回 doc_id 或 None"""
    best, best_s = None, 0
    for title, doc_id in index.items():
        s = SequenceMatcher(None, link, title).ratio()
        if s > best_s and s >= threshold:
            best_s, best = s, doc_id
    return best


def resolve_link(link_text, title_index):
    """将 wikilink 文本解析为 doc_id"""
    lt = link_text.strip()
    if lt in title_index:
        return title_index[lt]
    norm = normalize(lt)
    if norm in title_index:
        return title_index[norm]
    return fuzzy_match(lt, title_index)


# ── 从现有 wiki 文章读取（用于图谱重建） ─────────────────────────

def load_wiki_articles():
    """读取所有 wiki 文章的 frontmatter + 内容"""
    articles = {}
    title_index = {}

    for subdir in WIKI_DIR.iterdir():
        if not (subdir.is_dir() and not subdir.name.startswith('.')):
            continue
        for f in subdir.glob("*.md"):
            if f.name in SYSTEM_FILES:
                continue
            content = f.read_text(encoding='utf-8')

            # 提取 frontmatter
            fm = {}
            fm_m = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if fm_m:
                try:
                    fm = yaml.safe_load(fm_m.group(1)) or {}
                except Exception:
                    pass

            # 提取标题
            m = re.match(r'^# (.+)', content)
            title = (fm.get("title") or (m.group(1).strip() if m else None) or f.stem)

            # 提取 doc_id（优先 frontmatter，其次文件名末尾）
            doc_id = (fm.get("doc_id") or
                      re.search(r'^doc_id:\s*(.+?)\s*$', content, re.MULTILINE).group(1).strip() if re.search(r'^doc_id:\s*(.+?)\s*$', content, re.MULTILINE) else
                      f.stem.split('_')[-1])

            category = str(subdir.name)

            articles[doc_id] = {
                "title": title,
                "doc_id": doc_id,
                "path": str(f),
                "content": content,
                "frontmatter": fm,
                "category": fm.get("category", category),
                "subcategory": fm.get("subcategory", category),
                "key_tags": fm.get("tags", []),
                "created": str(fm.get("date") or "")[:10],
            }

            # 建立标题索引
            title_index[title] = doc_id
            title_index[normalize(title)] = doc_id

    return articles, title_index


# ── 从文章内容提取 wikilink（用于图谱重建） ─────────────────────

WIKILINK_PAT = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]')


def extract_connections(content, title_index):
    """从文章内容中提取所有 wikilink 并解析为 doc_id 列表"""
    links = WIKILINK_PAT.findall(content)
    conns = set()
    for lt in links:
        resolved = resolve_link(lt, title_index)
        if resolved:
            conns.add(resolved)
    return list(conns)


# ── 重建完整图谱（从 wiki 文章提取，不依赖 compile 时查找） ───────

def rebuild_graph():
    """
    从现有 wiki 文章重建关联图谱。
    调用此函数后，图的 documents 和 connection_reasons 与 wiki 文章完全同步。
    """
    articles, title_index = load_wiki_articles()
    graph = {"documents": {}, "connection_reasons": {}}

    for doc_id, art in articles.items():
        # 提取第一性原理（从文章正文）
        fp_m = re.search(r'### 本质规律\s*\n+(.*)', art['content'])
        first_principle = (fp_m.group(1).strip()[:200] if fp_m else "")

        # 从 wikilink 提取关联
        connections = extract_connections(art['content'], title_index)
        connections = [c for c in connections if c != doc_id]

        graph["documents"][doc_id] = {
            "title": art['title'],
            "category": art['category'],
            "subcategory": art['subcategory'],
            "first_principle": first_principle,
            "key_tags": art['key_tags'],
            "created": art['created'],
            "connections": connections,
        }

    # 生成 connection_reasons
    for doc_id, doc in graph["documents"].items():
        for target in doc.get("connections", []):
            key = f"{doc_id}-{target}"
            if key not in graph["connection_reasons"]:
                graph["connection_reasons"][key] = (
                    f"{doc.get('title', '')[:20]} → {target}"
                )

    return graph


# ── 增量更新图谱（给 wiki-compile.py 用） ───────────────────────

def get_stable_doc_id(title, category, existing_graph):
    """
    根据标题+分类查找已有 doc_id。
    若找到，复用该 ID（保持稳定）；否则返回 None。
    """
    docs = existing_graph.get("documents", {})
    for doc_id, doc in docs.items():
        if doc.get("title") == title and doc.get("category") == category:
            return doc_id
    return None


if __name__ == "__main__":
    # CLI：直接运行则重建图谱
    g = rebuild_graph()
    save_graph(g)
    print(f"✅ 图谱已重建：{len(g['documents'])} 文档，{len(g['connection_reasons'])} 条关联")
