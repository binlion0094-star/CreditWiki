#!/usr/bin/env python3
"""
Wiki Auto-Archive - 微信文章一键归档
收到链接 → 抓取内容 → 编译为结构化Wiki → 存入 wiki/articles/ 或 wiki/concepts/
"""

import os
import re
import json
import hashlib
import argparse
import uuid
from datetime import datetime
from pathlib import Path

# 导入标签引擎和关联引擎
import sys
sys.path.insert(0, str(Path(__file__).parent))
from tag_engine import suggest_tags_for_article, TAG_DISPLAY
from auto_linker import suggest_links_for_article

# ========== 路径配置 ==========
WIKI_DIR = Path(__file__).parent.parent
WIKI_ARTICLES = WIKI_DIR / "wiki" / "articles"
WIKI_CONCEPTS = WIKI_DIR / "wiki" / "concepts"
RAW_DIR = WIKI_DIR / "raw"
STATE_FILE = WIKI_DIR / "scripts" / ".wechat_state.json"

# ========== 关键词 → 分类映射 ==========
CATEGORY_MAP = {
    "监管": "监管政策", "合规": "监管政策", "银保监": "监管政策", "证监会": "监管政策",
    "罚单": "监管政策", "整改": "监管政策", "处罚": "监管政策", "以贷还贷": "监管政策",
    "央行": "宏观研究", "货币政策": "宏观研究", "财政政策": "宏观研究",
    "利率": "宏观研究", "汇率": "宏观研究", "通胀": "宏观研究", "CPI": "宏观研究",
    "PPI": "宏观研究", "存款准备金": "宏观研究", "降息": "宏观研究", "加息": "宏观研究",
    "房地产": "行业研究", "城投": "行业研究", "平台贷": "行业研究", "地方债": "行业研究",
    "焦化": "行业研究", "钢铁": "行业研究", "煤炭": "行业研究", "化工": "行业研究",
    "医药": "行业研究", "医疗器械": "行业研究", "半导体": "行业研究",
    "银行": "行业研究", "信贷": "行业研究", "授信": "行业研究", "风控": "行业研究",
    "不良": "行业研究", "拨备": "行业研究", "供应链金融": "行业研究",
    "保理": "行业研究", "票据": "行业研究", "流动性": "行业研究",
    "金融科技": "行业研究", "AI": "行业研究", "数字化": "行业研究",
    "净值": "行业研究", "理财": "行业研究", "基金": "行业研究",
    "私募": "法院判决", "托管": "法院判决", "诉讼": "法院判决", "仲裁": "法院判决",
}

# ========== 工具函数 ==========

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"seen_urls": [], "last_run": None}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def compute_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:16]

def is_duplicate(url):
    state = load_state()
    return url in state.get('seen_urls', [])

def mark_done(url):
    state = load_state()
    seen = state.get('seen_urls', [])
    if url not in seen:
        seen.append(url)
        state['seen_urls'] = seen[-500:]
    state['last_run'] = datetime.now().isoformat()
    save_state(state)

def match_keywords(text):
    matched = []
    for kw in CATEGORY_MAP:
        if kw in text:
            matched.append(kw)
    return list(set(matched))

def determine_category(keywords):
    for kw in keywords:
        if kw in CATEGORY_MAP:
            cat = CATEGORY_MAP[kw]
            if cat in ["监管政策", "信贷合同", "企业财报"]:
                return "concepts"
            return "articles"
    return "articles"

def extract_first_principle(title, content, keywords):
    body = content[:3000] if len(content) > 3000 else content
    body = re.sub(r'<[^>]+>', '', body)
    body = re.sub(r'\s+', ' ', body).strip()

    sentences = re.split(r'[。\n]', body)
    key_sentences = [s.strip() for s in sentences if len(s.strip()) > 15][:3]

    fact = key_sentences[0] if key_sentences else "待分析"
    cause = key_sentences[1] if len(key_sentences) > 1 else "待分析"

    return {
        "底层事实": fact,
        "根本原因": cause,
        "本质规律": f"【{title}】的核心规律：{cause}",
        "信贷应用": "待结合具体业务场景分析"
    }

def extract_summary(content, max_len=500):
    body = re.sub(r'<[^>]+>', '', content)
    body = re.sub(r'\s+', ' ', body).strip()
    paragraphs = [p.strip() for p in re.split(r'\n', body) if len(p.strip()) > 50]
    summary = paragraphs[0] if paragraphs else body[:max_len]
    return summary[:max_len] + ("..." if len(summary) > max_len else "")

def build_wiki_content(title, content, url, source, date, keywords, doc_id, related_articles=None):
    category = determine_category(keywords)
    first_principle = extract_first_principle(title, content, keywords)
    summary = extract_summary(content)
    safe_title = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '_', title)[:40]
    content_clean = re.sub(r'<[^>]+>', '', content)
    content_clean = re.sub(r'\s+', '\n\n', content_clean).strip()

    # 生成关联文档区块
    if related_articles:
        links_block = "\n".join([
            f"- [[{art['title']}]]：{art['reason']}"
            for art in related_articles[:4]
        ])
    else:
        links_block = "- [[]]：（待关联）"

    wiki = f"""# {title}

> 来源：{source}
> 归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 标签：#{" #".join(keywords[:6]) if keywords else "未分类"}
> 文档ID：{doc_id}
> 分类：{category}

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

## 📊 核心要点

### 关键数据/指标
| 指标 | 数值 | 说明 |
|-----|------|-----|
| — | — | 待提取 |

### 关键观点
1. 待从正文中提取

### 潜在风险点
- 🟡 待评估

---

## 🔗 关联文档

{links_block}

---

## 📝 原始摘要

{summary}

---

## 原始链接

{url}

---

*归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*来源：微信文章自动归档*
"""
    return wiki, category, safe_title

def archive_article(title, content, url, source="微信公众号", date=None):
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    if is_duplicate(url):
        return None, "已存在，跳过"

    # 使用标签引擎自动打标签
    tag_result = suggest_tags_for_article(title, content[:3000])
    keywords = tag_result["flat_tags"]

    # 自动推荐关联文档
    related = suggest_links_for_article(title, keywords, content[:1000])

    doc_id = compute_id(url)
    wiki_content, category, safe_title = build_wiki_content(
        title, content, url, source, date, keywords, doc_id, related
    )

    out_dir = WIKI_CONCEPTS if category == "concepts" else WIKI_ARTICLES
    filename = f"{safe_title}_{doc_id}.md"
    filepath = out_dir / filename

    if filepath.exists():
        filename = f"{safe_title}_{doc_id}_1.md"
        filepath = out_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(wiki_content)

    # 同时存 raw/
    raw_path = RAW_DIR / category
    raw_path.mkdir(parents=True, exist_ok=True)
    raw_file = raw_path / f"wechat_{safe_title}_{date}.md"
    raw_content = f"""# {title}

> 来源：{source}
> URL：{url}
> 发布日期：{date}
> 标签：微信 | {" | ".join(keywords[:5])}
> 文档ID：wechat_{doc_id}
> 分类：{category}

---

{content[:8000]}

---

*归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*来源：微信文章自动抓取*
"""
    with open(raw_file, 'w', encoding='utf-8') as f:
        f.write(raw_content)

    mark_done(url)
    return str(filepath), f"成功，入库 {category}"

# ========== 主入口 ==========

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='微信文章一键归档')
    parser.add_argument('--title', help='文章标题')
    parser.add_argument('--content', help='文章正文内容')
    parser.add_argument('--url', help='文章URL')
    parser.add_argument('--source', default='微信公众号', help='公众号名称')
    parser.add_argument('--date', help='发布日期 YYYY-MM-DD')
    parser.add_argument('--check', nargs='?', const='dummy', help='仅检查URL是否已处理')
    args = parser.parse_args()

    if args.check:
        is_dup = is_duplicate(args.check)
        print(f"{'已归档' if is_dup else '新文章'}: {args.check[:60]}")
        exit(0)

    if not args.title or not args.content or not args.url:
        print("用法: wiki-auto-archive.py --title ... --content ... --url ... [--source ...]")
        print("  或: wiki-auto-archive.py --check <url>")
        exit(1)

    filepath, status = archive_article(
        title=args.title,
        content=args.content,
        url=args.url,
        source=args.source,
        date=args.date
    )

    if filepath:
        print(f"✅ {status}")
        print(f"   文件: {filepath}")
        print(f"   标题: {args.title[:50]}")
    else:
        print(f"⏭️ {status}")
