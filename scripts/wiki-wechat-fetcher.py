#!/usr/bin/env python3
"""
Wiki WeChat Fetcher - 微信文章抓取工具
配合Hermes browser工具使用，自动归档微信文章
"""

import os
import re
import json
import hashlib
import argparse
from datetime import datetime
from pathlib import Path

# ========== 配置 ==========
WIKI_DIR = Path(__file__).parent.parent
RAW_DIR = WIKI_DIR / "raw"
STATE_FILE = WIKI_DIR / "scripts" / ".wechat_state.json"

# 关键词配置
KEYWORDS = [
    # 银行信贷
    "银行", "信贷", "授信", "风控", "不良", "拨备", "资本充足率", "杠杆",
    "流动性", "净息差", "中间业务", "存款", "贷款", "信用卡", "普惠金融", 
    "小微", "村镇银行", "农商行", "城商行", "股份行", "国有大行", "村镇银行",
    # 监管合规
    "监管", "合规", "央行", "银保监", "证监会", "银保监局", "罚单", "整改", "处罚",
    # 宏观政策
    "货币政策", "财政政策", "利率", "汇率", "通胀", "CPI", "PPI", "社融", "M2",
    "存款准备金", "公开市场操作", "降息", "加息",
    # 行业
    "房地产", "城投", "地方债", "平台贷", "焦化", "钢铁", "煤炭", "化工", "水泥",
    "造船", "航运", "港口", "航空", "医药", "医疗器械", "白酒", "食品",
    # 金融科技
    "金融科技", " fintech", "数字化转型", "AI", "人工智能", "区块链", "数字货币",
    # 信贷产品
    "供应链金融", "保理", "票据", "福费廷", "信用证", "保兑仓"
]

# 分类映射
CATEGORY_MAP = {
    "监管": "监管政策", "合规": "监管政策", "银保监": "监管政策", "证监会": "监管政策",
    "罚单": "监管政策", "整改": "监管政策", "处罚": "监管政策",
    "央行": "宏观研究", "货币政策": "宏观研究", "财政政策": "宏观研究", 
    "利率": "宏观研究", "汇率": "宏观研究", "通胀": "宏观研究", "CPI": "宏观研究",
    "PPI": "宏观研究", "存款准备金": "宏观研究", "降息": "宏观研究", "加息": "宏观研究",
    "房地产": "行业研究", "城投": "行业研究", "平台贷": "行业研究",
    "焦化": "行业研究", "钢铁": "行业研究", "煤炭": "行业研究", "化工": "行业研究",
    "医药": "行业研究", "医疗器械": "行业研究",
    "金融科技": "行业研究", "AI": "行业研究", "数字化转型": "行业研究",
    "供应链金融": "行业研究", "保理": "行业研究", "票据": "行业研究"
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

def is_wechat_url(url):
    return 'mp.weixin.qq.com' in url and '/s/' in url

def match_keywords(text):
    """返回匹配的关键词列表"""
    matched = []
    for kw in KEYWORDS:
        if kw.lower() in text.lower():
            matched.append(kw)
    return matched

def determine_category(keywords):
    for kw in keywords:
        if kw in CATEGORY_MAP:
            return CATEGORY_MAP[kw]
    return "行业研究"

def archive_wechat_article(title, content, url, author="微信公众号", date=None):
    """归档微信文章"""
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    # 匹配关键词
    full_text = f"{title} {content[:1000]}"
    keywords = match_keywords(full_text)
    category = determine_category(keywords)
    
    dir_path = RAW_DIR / category
    dir_path.mkdir(parents=True, exist_ok=True)
    
    # 生成安全文件名
    safe_title = re.sub(r'[^\w\u4e00-\u9fa5]', '_', title)[:30]
    filename = f"wechat_{safe_title}_{date}.md"
    filepath = dir_path / filename
    
    if filepath.exists():
        return None, "已存在"
    
    # 清理HTML
    content_clean = re.sub(r'<[^>]+>', '', content)
    content_clean = re.sub(r'\s+', ' ', content_clean).strip()
    
    # 提取摘要（前500字）
    summary = content_clean[:500]
    if len(content_clean) > 500:
        summary += "..."
    
    article = f"""# {title}

> 来源：微信公众号 - {author}
> URL：{url}
> 发布日期：{date}
> 标签：微信 | {" | ".join(keywords[:5]) if keywords else "未分类"}
> 文档ID：wechat_{compute_id(url)}
> 分类：{category}

---

## 文章摘要

{summary}

---

## 文章正文

{content_clean[:8000]}{"..." if len(content_clean) > 8000 else ""}

## 原始链接

{url}

---

*归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*来源：微信文章自动抓取*
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(article)
    
    # 更新状态
    state = load_state()
    seen = state.get('seen_urls', [])
    if url not in seen:
        seen.append(url)
        state['seen_urls'] = seen[-500:]
    state['last_run'] = datetime.now().isoformat()
    save_state(state)
    
    return str(filepath), "成功"

def check_url_duplicate(url):
    """检查URL是否已处理"""
    state = load_state()
    return url in state.get('seen_urls', [])

# ========== 主入口 ==========

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='微信文章归档工具')
    parser.add_argument('--title', help='文章标题')
    parser.add_argument('--content', help='文章内容')
    parser.add_argument('--url', help='文章URL')
    parser.add_argument('--author', default='微信公众号', help='公众号名称')
    parser.add_argument('--date', help='发布日期 YYYY-MM-DD')
    parser.add_argument('--check', help='仅检查URL是否已处理')
    args = parser.parse_args()
    
    if args.check:
        is_dup = check_url_duplicate(args.check)
        print(f"{'已处理' if is_dup else '新文章'}: {args.check[:50]}...")
        exit(0)
    
    if not args.title or not args.content or not args.url:
        print("请提供 --title, --content, --url 参数")
        exit(1)
    
    filepath, status = archive_wechat_article(
        title=args.title,
        content=args.content,
        url=args.url,
        author=args.author,
        date=args.date
    )
    
    if filepath:
        print(f"✅ 归档成功: {filepath}")
        print(f"   标题: {args.title[:50]}...")
    else:
        print(f"⏭️ {status}")
