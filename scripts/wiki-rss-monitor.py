#!/usr/bin/env python3
"""
Wiki RSS Monitor - 信贷知识库RSS监控机器人 v3
自动抓取财经RSS源，发现新文章后归档
"""

import os
import re
import json
import time
import hashlib
import argparse
import ssl
import urllib.request
import urllib.parse
import signal
from datetime import datetime
from pathlib import Path
from html import escape

# ========== 配置 ==========
WIKI_DIR = Path(__file__).parent.parent
RAW_DIR = WIKI_DIR / "raw"
STATE_FILE = WIKI_DIR / "scripts" / ".rss_state.json"

# RSS源配置（只保留验证可用的源）
RSS_SOURCES = {
    "sina_finance": {
        "name": "新浪财经",
        "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=20",
        "type": "api",
        "category": "行业研究",
        "timeout": 10,
        "keywords": ["银行", "信贷", "授信", "风控", "不良", "拨备", "资本", "杠杆", "流动性", "净息差", "中间业务", "存款", "贷款", "信用卡", "普惠", "小微", "村镇银行", "农商行", "城商行", "股份行", "国有大行"]
    },
    "sina_macro": {
        "name": "新浪宏观",
        "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=1686&num=20",
        "type": "api",
        "category": "宏观研究",
        "timeout": 10,
        "keywords": ["货币政策", "财政政策", "利率", "汇率", "通胀", "GDP", "CPI", "PPI", "社融", "M2", "央行", "美联储", "降息", "加息", "存款准备金", "公开市场"]
    }
}

# ========== 工具函数 ==========

def fetch_url(url, timeout=10):
    """带超时抓取URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://finance.sina.com.cn/'
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode('utf-8')

def load_state():
    """加载已抓取文章状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}

def save_state(state):
    """保存状态"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def compute_id(item):
    """计算文章唯一ID"""
    content = f"{item.get('url', '')}{item.get('title', '')}"
    return hashlib.md5(content.encode()).hexdigest()[:16]

def match_keywords(text, keywords):
    """检查是否匹配关键词"""
    if not keywords:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

def parse_api_response(content, source_config):
    """解析新浪API格式"""
    data = json.loads(content)
    items = data.get('result', {}).get('data', [])
    results = []
    
    for item in items:
        title = item.get('title', '')
        url = item.get('url', '').replace('\\/', '/')
        intro = item.get('intro', '')
        ctime = item.get('ctime', '')
        
        if ctime:
            date = datetime.fromtimestamp(int(ctime)).strftime('%Y-%m-%d')
        else:
            date = datetime.now().strftime('%Y-%m-%d')
        
        results.append({
            'title': title,
            'url': url,
            'intro': intro,
            'date': date,
            'source': source_config['name'],
            'category': source_config['category']
        })
    
    return results

def fetch_feed(source_key, source_config):
    """抓取单个RSS源"""
    try:
        content = fetch_url(source_config['url'], timeout=source_config.get('timeout', 10))
        
        if source_config['type'] == 'api':
            return parse_api_response(content, source_config)
        else:
            return []
            
    except Exception as e:
        print(f"  ⚠️ 抓取失败 [{source_key}]: {e}")
        return []

def archive_article(item, keywords):
    """归档文章到知识库"""
    category = item['category']
    dir_path = RAW_DIR / category
    dir_path.mkdir(parents=True, exist_ok=True)
    
    # 生成安全的文件名
    safe_title = re.sub(r'[^\w\u4e00-\u9fa5]', '_', item['title'])[:30]
    filename = f"{safe_title}_{item['date']}.md"
    filepath = dir_path / filename
    
    # 检查是否已存在
    if filepath.exists():
        return None
    
    # 清理摘要HTML
    intro = re.sub(r'<[^>]+>', '', item['intro'])[:300]
    
    # 构建文章内容
    content = f"""# {item['title']}

> 来源：{item['source']}
> URL：{item['url']}
> 发布日期：{item['date']}
> 标签：RSS监控 | {" | ".join(keywords[:3])}
> 文档ID：rss_{compute_id(item)}
> 分类：{item['category']}

---

## 文章摘要

{intro or '（无摘要）'}

## 原始链接

{item['url']}

---

*归档时间：{datetime.now().strftime('%Y-%m-%d')}*
*来源：RSS监控自动抓取*
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(filepath)

def run_monitor(test_mode=True):
    """运行监控"""
    print("🔍 信贷知识库 RSS Monitor v3")
    print("=" * 50)
    
    state = load_state()
    seen_ids = set(state.get('seen_ids', []))
    new_count = 0
    total_matched = 0
    
    for source_key, source_config in RSS_SOURCES.items():
        print(f"\n📡 抓取: {source_config['name']}...", end=" ", flush=True)
        
        articles = fetch_feed(source_key, source_config)
        print(f"获取到 {len(articles)} 条")
        
        source_matched = 0
        for article in articles:
            article_id = compute_id(article)
            
            if article_id in seen_ids:
                continue
            
            text = f"{article['title']} {article['intro']}"
            if not match_keywords(text, source_config['keywords']):
                continue
            
            source_matched += 1
            total_matched += 1
            
            if test_mode:
                print(f"   🆕 {article['title'][:55]}...")
            else:
                filepath = archive_article(article, source_config['keywords'])
                if filepath:
                    print(f"   ✅ 已归档: {article['title'][:40]}...")
                    new_count += 1
            
            seen_ids.add(article_id)
        
        if source_matched == 0:
            print(f"   (无新增匹配)")
    
    # 更新状态
    seen_ids_list = list(seen_ids)[-2000:]
    state['seen_ids'] = seen_ids_list
    state['last_run'] = datetime.now().isoformat()
    save_state(state)
    
    print(f"\n{'=' * 50}")
    print(f"📊 统计: 匹配文章 {total_matched} 条")
    if test_mode:
        print(f"   (测试模式，未实际归档)")
    else:
        print(f"✅ 归档完成: {new_count} 篇")
    
    return new_count

# ========== 主入口 ==========

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='信贷知识库RSS监控 v3')
    parser.add_argument('--test', action='store_true', help='测试模式（只显示不归档）')
    parser.add_argument('--live', action='store_true', help='正式模式（实际归档）')
    args = parser.parse_args()
    
    test_mode = not args.live
    run_monitor(test_mode=test_mode)
