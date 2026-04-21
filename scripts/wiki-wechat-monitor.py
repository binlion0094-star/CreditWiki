#!/usr/bin/env python3
"""
Wiki WeChat Monitor - 信贷知识库微信文章自动抓取
当你发送微信文章链接时，自动抓取并归档
"""

import os
import re
import json
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ========== 配置 ==========
WIKI_DIR = Path(__file__).parent.parent
RAW_DIR = WIKI_DIR / "raw"
STATE_FILE = WIKI_DIR / "scripts" / ".wechat_state.json"

# 关键词配置
KEYWORDS = [
    # 银行信贷相关
    "银行", "信贷", "授信", "风控", "不良", "拨备", "资本", "杠杆", 
    "流动性", "净息差", "中间业务", "存款", "贷款", "信用卡", 
    "普惠", "小微", "村镇银行", "农商行", "城商行", "股份行", "国有大行",
    # 金融监管
    "监管", "合规", "央行", "银保监", "证监会", "罚单", "整改",
    # 宏观政策
    "货币政策", "财政政策", "利率", "汇率", "通胀", "GDP", "CPI", "PPI",
    # 行业
    "房地产", "城投", "地方债", "平台贷", "焦化", "钢铁", "煤炭", "化工",
    # 金融科技
    "金融科技", "数字化", "转型", "AI", "人工智能", "区块链"
]

# 分类映射
CATEGORY_MAP = {
    "银行": "行业研究",
    "信贷": "行业研究", 
    "授信": "行业研究",
    "风控": "行业研究",
    "不良": "行业研究",
    "拨备": "行业研究",
    "监管": "监管政策",
    "合规": "监管政策",
    "央行": "宏观研究",
    "货币政策": "宏观研究",
    "财政政策": "宏观研究",
    "利率": "宏观研究",
    "汇率": "宏观研究",
    "通胀": "宏观研究",
    "GDP": "宏观研究",
    "房地产": "行业研究",
    "城投": "行业研究",
    "平台贷": "行业研究",
    "金融科技": "行业研究",
    "数字化": "行业研究",
    "转型": "行业研究"
}

# ========== 工具函数 ==========

def load_state():
    """加载已处理文章状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"seen_urls": [], "last_run": None}

def save_state(state):
    """保存状态"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def compute_id(url):
    """计算URL唯一ID"""
    return hashlib.md5(url.encode()).hexdigest()[:16]

def is_wechat_url(url):
    """检查是否是微信文章URL"""
    parsed = urlparse(url)
    return 'mp.weixin.qq.com' in parsed.netloc and '/s/' in parsed.path

def match_keywords(text):
    """检查是否匹配关键词"""
    matched = []
    for kw in KEYWORDS:
        if kw in text:
            matched.append(kw)
    return matched

def determine_category(keywords):
    """根据关键词确定分类"""
    for kw in keywords:
        if kw in CATEGORY_MAP:
            return CATEGORY_MAP[kw]
    return "行业研究"

def parse_wechat_url(url):
    """解析微信URL获取biz和mid"""
    parsed = urlparse(url)
    path_parts = parsed.path.split('/')
    
    # 格式: /s/xxxxx
    if len(path_parts) >= 3:
        sig = path_parts[-1]
    else:
        sig = ""
    
    # 从查询参数获取更多信息
    query = dict(param.split('=') for param in parsed.query.split('&') if '=' in param) if parsed.query else {}
    
    return {
        'url': url,
        'sig': sig,
        'biz': query.get('__biz', ''),
        'mid': query.get('mid', ''),
        'idx': query.get('idx', ''),
        'sn': query.get('sn', '')
    }

def archive_article(title, content, url, source, date, matched_keywords):
    """归档文章到知识库"""
    category = determine_category(matched_keywords)
    dir_path = RAW_DIR / category
    dir_path.mkdir(parents=True, exist_ok=True)
    
    # 生成安全的文件名
    safe_title = re.sub(r'[^\w\u4e00-\u9fa5]', '_', title)[:30]
    filename = f"{safe_title}_{date}.md"
    filepath = dir_path / filename
    
    # 检查是否已存在
    if filepath.exists():
        return None, "已存在"
    
    # 清理HTML标签
    content_clean = re.sub(r'<[^>]+>', '', content)
    content_clean = re.sub(r'\s+', ' ', content_clean).strip()
    
    # 构建文章内容
    article_content = f"""# {title}

> 来源：{source}
> URL：{url}
> 发布日期：{date}
> 标签：微信 | {" | ".join(matched_keywords[:5])}
> 文档ID：wechat_{compute_id(url)}
> 分类：{category}

---

## 文章正文

{content_clean[:5000]}{"..." if len(content_clean) > 5000 else ""}

## 原始链接

{url}

---

*归档时间：{datetime.now().strftime('%Y-%m-%d')}*
*来源：微信文章自动抓取*
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(article_content)
    
    return str(filepath), "成功"

def process_wechat_url(url):
    """处理单个微信URL"""
    if not is_wechat_url(url):
        return None, "非微信文章URL"
    
    state = load_state()
    if url in state.get('seen_urls', []):
        return None, "已处理过"
    
    # 解析URL
    parsed = parse_wechat_url(url)
    
    return {
        'url': url,
        'sig': parsed['sig']
    }, "待抓取"

def add_to_seen(url):
    """添加到已处理列表"""
    state = load_state()
    seen = state.get('seen_urls', [])
    if url not in seen:
        seen.append(url)
        # 只保留最近500条
        state['seen_urls'] = seen[-500:]
        state['last_run'] = datetime.now().isoformat()
        save_state(state)

# ========== 主入口 ==========

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='信贷知识库微信文章抓取工具')
    parser.add_argument('--url', help='单个微信文章URL')
    parser.add_argument('--file', help='包含URL列表的文件（每行一个）')
    parser.add_argument('--list', nargs='*', help='多个微信文章URL')
    args = parser.parse_args()
    
    urls = []
    
    if args.url:
        urls.append(args.url)
    elif args.file:
        with open(args.file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    elif args.list:
        urls = args.list
    else:
        print("请提供URL参数:")
        print("  --url 'https://mp.weixin.qq.com/s/xxxxx'")
        print("  --file urls.txt")
        print("  --list 'url1' 'url2' ...")
        exit(1)
    
    print(f"🔍 将处理 {len(urls)} 个微信文章链接")
    print("=" * 60)
    
    results = []
    for url in urls:
        info, status = process_wechat_url(url)
        if info:
            print(f"✅ {info['sig'][:20]}... -> 待抓取")
            results.append(info)
        else:
            print(f"⏭️ {status}: {url[:50]}...")
    
    print(f"\n📊 可抓取: {len(results)} 个")
    print("\n⚠️  请使用Hermes AI的browser_navigate工具抓取文章内容")
    print("   然后调用归档功能存入知识库")
