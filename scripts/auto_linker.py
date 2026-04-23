#!/usr/bin/env python3
"""
Auto-Linker - 知识库智能关联引擎
基于标签共现 + 内容相似度自动推荐关联文档
"""

import re
import json
import yaml
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Optional

# ============================================================
# 路径配置
# ============================================================
WIKI_DIR = Path(__file__).parent.parent / "wiki"
GRAPH_FILE = Path(__file__).parent.parent / "元数据" / "关联图谱.json"

# ============================================================
# 标签共现权重矩阵（手动设定高关联标签对）
# ============================================================
TAG_CORRELATION = {
    # 同一业务场景的强关联
    ("银行", "信贷"): 0.9,
    ("银行", "风控"): 0.9,
    ("信贷", "风险"): 0.8,
    ("信贷", "不良"): 0.9,
    ("不良", "拨备"): 0.9,
    ("不良", "资本充足率"): 0.8,
    ("房地产", "城投"): 0.7,
    ("房地产", "渠道佣金"): 0.95,
    ("城投", "隐性债务"): 0.95,
    ("城投", "地方债"): 0.9,
    ("城投", "政信业务"): 0.9,
    ("以贷还贷", "借新还旧"): 0.95,
    ("以贷还贷", "保证责任"): 0.8,
    ("以贷还贷", "抵押权"): 0.8,
    ("供应链金融", "保理"): 0.85,
    ("供应链金融", "票据"): 0.8,
    ("供应链金融", "预付类"): 0.9,
    ("供应链金融", "存货类"): 0.9,
    ("票据", "贴现"): 0.8,
    ("票据", "银票"): 0.8,
    ("票据", "商票"): 0.8,
    ("保理", "应收账款"): 0.9,
    ("保理", "反向保理"): 0.9,
    ("信用风险", "市场风险"): 0.7,
    ("信用风险", "操作风险"): 0.7,
    ("合规风险", "监管"): 0.8,
    ("合规风险", "处罚"): 0.9,
    ("LPR", "降息"): 0.85,
    ("LPR", "贷款利率"): 0.85,
    ("降息", "银行"): 0.8,
    ("降准", "流动性"): 0.8,
    ("集采", "医药"): 0.9,
    ("集采", "仿制药"): 0.9,
    ("创新药", "医药"): 0.9,
    # 宏观-银行传导
    ("GDP", "银行"): 0.7,
    ("CPI", "银行"): 0.7,
    ("降息", "净息差"): 0.8,
    ("加息", "净息差"): 0.8,
    ("汇率", "银行"): 0.7,
    ("人民币贬值", "银行"): 0.7,
}


def get_correlation_score(tags1: List[str], tags2: List[str]) -> float:
    """计算两组标签的关联度分数"""
    if not tags1 or not tags2:
        return 0.0

    score = 0.0
    count = 0

    for t1 in tags1:
        for t2 in tags2:
            key = (t1, t2) if (t1, t2) in TAG_CORRELATION else (t2, t1)
            if key in TAG_CORRELATION:
                score += TAG_CORRELATION[key]
                count += 1

    # 直接交集得分
    intersection = set(tags1) & set(tags2)
    if intersection:
        score += len(intersection) * 0.3
        count += len(intersection)

    return score / count if count > 0 else 0.0


def extract_tags_from_frontmatter(frontmatter: Dict) -> List[str]:
    """从 frontmatter 提取标签"""
    tags = frontmatter.get("tags", [])
    if isinstance(tags, list):
        return [t.strip() for t in tags if t and t != "[]"]
    if isinstance(tags, str):
        # 可能是 "#tag1 #tag2" 格式
        return [t.strip() for t in tags.split("#") if t.strip()]
    return []


def extract_title_from_content(content: str) -> str:
    """从内容提取标题"""
    m = re.match(r'^#\s+(.+?)\s*\n', content)
    return m.group(1).strip() if m else ""


def load_all_articles() -> List[Dict]:
    """加载所有 wiki 文章"""
    articles = []

    for subdir in WIKI_DIR.iterdir():
        if not (subdir.is_dir() and not subdir.name.startswith(".")):
            continue
        for f in subdir.glob("*.md"):
            if f.name in {"INDEX.md", "SUMMARY.md", "STATS.md", "TEMPLATE.md", "README.md"}:
                continue

            content = f.read_text(encoding="utf-8")

            # 提取 frontmatter
            fm = {}
            fm_m = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if fm_m:
                try:
                    fm = yaml.safe_load(fm_m.group(1)) or {}
                except Exception:
                    pass

            # 提取标题
            title = (fm.get("title") or extract_title_from_content(content) or f.stem)

            # 提取标签
            tags = extract_tags_from_frontmatter(fm)
            if not tags:
                # 降级：从文件内容提取关键词
                tags = extract_fallback_tags(content)

            # 提取第一性原理
            fp_m = re.search(r"### 本质规律\s*\n+(.*?)(?:\n|$)", content)
            first_principle = fp_m.group(1).strip()[:200] if fp_m else ""

            articles.append({
                "doc_id": fm.get("doc_id", f.stem.split("_")[-1]),
                "title": title,
                "path": str(f),
                "subdir": subdir.name,
                "tags": tags,
                "first_principle": first_principle,
                "content": content,
                "frontmatter": fm,
            })

    return articles


def extract_fallback_tags(content: str) -> List[str]:
    """降级：从内容提取关键词作为标签"""
    keywords = [
        "银行", "信贷", "风控", "不良", "房地产", "城投", "医药", "科技",
        "集采", "票据", "保理", "供应链金融", "以贷还贷", "隐性债务",
        "监管", "合规", "处罚", "净息差", "资本充足率", "拨备",
        "LPR", "降息", "降准", "GDP", "CPI", "汇率"
    ]
    found = [kw for kw in keywords if kw in content]
    return found[:5]  # 最多5个


def compute_title_similarity(title1: str, title2: str) -> float:
    """计算标题相似度（基于字符重叠）"""
    s1 = set(title1)
    s2 = set(title2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


def find_related_articles(target: Dict, all_articles: List[Dict], top_n: int = 5) -> List[Tuple[Dict, float, str]]:
    """为指定文章找到最相关的其他文章"""
    results = []

    target_tags = target.get("tags", [])
    target_title = target.get("title", "")
    target_fp = target.get("first_principle", "")

    for article in all_articles:
        if article["doc_id"] == target["doc_id"]:
            continue

        score = 0.0
        reason = ""

        # 1. 标签共现得分
        article_tags = article.get("tags", [])
        tag_score = get_correlation_score(target_tags, article_tags)
        if tag_score > 0:
            score += tag_score * 0.5
            reason = f"标签关联"

        # 2. 标题相似度
        title_sim = compute_title_similarity(target_title, article["title"])
        if title_sim > 0.2:
            score += title_sim * 0.3
            reason = f"标题相似" if not reason else f"{reason} + 标题相似"

        # 3. 第一性原理内容重叠（如果有的话）
        if target_fp and article.get("first_principle"):
            fp_sim = compute_title_similarity(target_fp, article["first_principle"])
            if fp_sim > 0.1:
                score += fp_sim * 0.2
                reason = f"{reason} + 内容相关" if reason else f"内容相关"

        # 4. 同目录加成（同一分类的文章更可能相关）
        if article["subdir"] == target["subdir"]:
            score += 0.1

        if score > 0.05:
            results.append((article, score, reason))

    # 排序
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_n]


def build_correlation_reason(tags1: List[str], tags2: List[str]) -> str:
    """生成关联原因描述"""
    intersections = set(tags1) & set(tags2)
    if intersections:
        common = ", ".join(list(intersections)[:3])
        return f"共同标签：{common}"

    # 查找已知的强关联标签对
    for t1 in tags1:
        for t2 in tags2:
            key = (t1, t2) if (t1, t2) in TAG_CORRELATION else (t2, t1)
            if key in TAG_CORRELATION and TAG_CORRELATION[key] >= 0.8:
                return f"高关联标签对：{t1} + {t2}"

    return "内容相关"


def update_article_links(article_path: str, related: List[Tuple[Dict, float, str]]):
    """更新文章的关联文档区块"""
    if not related:
        return

    # 构建关联文档的 wikilink 块
    links_block = "\n".join([f"- [[{art['title']}]]：{reason}" for art, score, reason in related])

    content = Path(article_path).read_text(encoding="utf-8")

    # 替换关联文档区块
    pattern = r'(## 🔗 关联文档\n\n).*?(---\n)'
    replacement = rf'\1{links_block}\n\n\2'

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    if new_content != content:
        Path(article_path).write_text(new_content, encoding="utf-8")
        return True
    return False


def run_autolink_all():
    """对所有文章运行智能关联"""
    print("🔗 知识库智能关联引擎")
    print("=" * 50)

    articles = load_all_articles()
    print(f"📚 加载文章: {len(articles)} 篇")

    updated = 0
    for article in articles:
        related = find_related_articles(article, articles, top_n=4)
        if related:
            ok = update_article_links(article["path"], related)
            if ok:
                updated += 1
                related_titles = [r[0]["title"][:30] for r in related]
                print(f"  ✅ {article['title'][:40]}")
                print(f"     → {', '.join(related_titles)}")

    print(f"\n✅ 更新完成: {updated} 篇文章")


def suggest_links_for_article(title: str, tags: List[str], content: str = "") -> List[Dict]:
    """为指定文章推荐关联文档（不修改文件）"""
    all_articles = load_all_articles()

    # 构造临时文章对象
    target = {
        "doc_id": "__temp__",
        "title": title,
        "tags": tags,
        "first_principle": "",
        "subdir": "articles",
    }

    related = find_related_articles(target, all_articles, top_n=5)

    return [
        {
            "doc_id": art["doc_id"],
            "title": art["title"],
            "score": round(score, 3),
            "reason": reason,
            "path": art["path"],
        }
        for art, score, reason in related
    ]


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="知识库智能关联引擎")
    parser.add_argument("--all", action="store_true", help="对所有文章更新关联")
    parser.add_argument("--test", nargs="*", help="测试：输入标题和标签")
    args = parser.parse_args()

    if args.all:
        run_autolink_all()
    elif args.test:
        title = " ".join(args.test) if args.test else ""
        tags = []  # 可扩展
        results = suggest_links_for_article(title, tags)
        for r in results:
            print(f"  [{r['score']:.3f}] {r['title']} — {r['reason']}")
    else:
        print("用法: autolink.py --all  (更新所有文章关联)")
        print("   autolink.py --test 标题 [标签...]")
