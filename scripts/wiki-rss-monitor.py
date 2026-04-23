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

# RSS源配置（适配授信审批部6科室职责）
# 注意：新浪API仅 lid=2516/2517/2518 返回数据，其他lid已废弃
# 各科室通过关键词从同一数据源中过滤相关内容
RSS_SOURCES = {
    # === D1 地产基建评审科 + D5 普惠业务科 + 通用 ===
    "sina_finance": {
        "name": "新浪财经(综合)",
        "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=20",
        "type": "api",
        "category": "D1_地产基建",
        "timeout": 10,
        "dept": "D1",
        "keywords": [
            # 地产基建
            "房地产开发贷款", "房地产信贷", "住房贷款", "商业地产贷款", "项目贷款",
            "土地储备贷款", "棚改贷款", "城市更新贷款", "城中村改造", "保障房",
            "共有产权房", "城建贷款", "基础设施建设", "新基建", "交通基础设施",
            "水利贷款", "园区贷款", "开发区融资", "棚改", "城市更新",
            # 普惠
            "普惠贷款", "小微企业贷款", "小微贷款", "税贷", "流水贷",
            "个体工商户贷款", "中小企业贷款", "个人经营贷款", "个人消费贷款",
            "消费贷", "汽车消费贷款", "三农贷款", "农户贷款", "农业贷款",
            "乡村振兴贷款", "惠农贷款", "两增两控", "首贷户", "无还本续贷",
            # 通用宏观监管
            "货币政策", "财政政策", "利率", "汇率", "通胀", "CPI", "PPI",
            "GDP", "社融", "M2", "信贷总量", "新增贷款", "LPR", "MLF", "降准", "降息",
            "金融监管", "国家金融监管总局", "人民银行", "外管局",
            "合规检查", "现场检查", "资本管理", "杠杆率", "流动性风险",
            "大额风险暴露", "集中度风险", "信贷政策", "授信政策",
            "商业银行法", "银行业监督管理法", "民法典担保篇"
        ]
    },
    # === D3 跨境评审科 + 城投政信 ===
    "sina_crossborder": {
        "name": "新浪国际财经",
        "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2517&num=20",
        "type": "api",
        "category": "D3_跨境评审",
        "timeout": 10,
        "dept": "D3",
        "keywords": [
            # 跨境业务
            "跨境融资", "跨境贷款", "进出口融资", "国际贸易融资", "出口信贷",
            "进口信贷", "打包贷款", "进出口押汇", "代付业务", "福费廷",
            "保理", "国际保理", "出口保理", "进口保理",
            # 外汇
            "外汇管理", "外债管理", "跨境人民币", "外汇管制", "外汇政策",
            "资本项目开放", "经常项目", "外汇登记", "外债规模", "外债比例",
            # 跨境担保
            "跨境担保", "对外担保", "备用信用证", "保函", "转开保函",
            # 同业/FT
            "境内外联动", "NRA账户", "FT账户", "境外代理行",
            # 城投政信
            "城投", "平台贷", "地方融资平台", "城投公司", "城投债", "城投评级",
            "隐性债务", "化债", "地方化债", "政信业务", "政府债务",
            "开发区", "园区债", "城投转型", "城投违约", "城投风险"
        ]
    },
    # === D2 产业评审科 + D4 投行金融市场科 ===
    "sina_industry": {
        "name": "新浪产业金融",
        "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2518&num=20",
        "type": "api",
        "category": "D2_产业评审",
        "timeout": 10,
        "dept": "D2",
        "keywords": [
            # 制造业/科技
            "制造业贷款", "工业贷款", "技改贷款", "设备贷款", "智能制造",
            "科技贷款", "高新技术企业", "科技型中小企业", "知识产权质押",
            "商贸服务贷款", "零售贷款", "批发零售", "供应链融资", "存货融资",
            # 新兴产业
            "新能源贷款", "光伏贷款", "风电贷款", "储能贷款", "新能源汽车贷款",
            "动力电池贷款", "半导体贷款", "生物医药贷款", "新材料贷款",
            "人工智能贷款", "数字经济贷款",
            # 投行金融市场
            "债券投资", "城投债", "企业债", "公司债", "金融债", "次级债",
            "永续债", "可转债", "绿色债券", "碳中和债",
            "ABS", "资产证券化", "信贷ABS", "企业ABS", "ABN", "资产支持票据",
            "CMBS", "REITs", "基础设施REITs",
            "北金所", "理财直融", "债权融资计划", "定向融资", "金交所",
            "金融市场业务", "资金业务", "同业业务", "票据业务", "贴现",
            "转贴现", "回购", "同业拆借", "大额存单",
            "并购贷款", "杠杆收购", "M&A融资", "股权融资"
        ]
    },
    # === 36氪 - 科技/商业/产业 ===
    "36kr": {
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "type": "rss",
        "category": "D2_产业评审",
        "timeout": 15,
        "dept": "D2",
        "keywords": [
            "贷款", "融资", "信贷", "银行", "金融", "科技", "半导体", "新能源",
            "人工智能", "生物医药", "新材料", "数字经济", "智能制造", "产业",
            "小微企业", "普惠", "供应链金融", "金融科技", "FinTech"
        ]
    },
    # === 彭博Bloomberg RSS（英文，关键词过滤）===
    "bloomberg_china": {
        "name": "Bloomberg中国",
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "type": "rss",
        "category": "宏观政策",
        "timeout": 15,
        "dept": "ALL",
        "keywords": [
            "China", "yuan", "RMB", "PBOC", "bank", "lending", "credit",
            "property", "real estate", "economy", "GDP", "trade", "yuan",
            "China banks", "shadow banking", "NPL", "bad loan"
        ]
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
        elif source_config['type'] == 'rss':
            # XML RSS解析
            return parse_rss_feed(content, source_config)
        else:
            return []

    except Exception as e:
        print(f"  ⚠️ 抓取失败 [{source_key}]: {e}")
        return []


def parse_rss_feed(content, source_config):
    """解析标准XML RSS格式"""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    items = []
    for item in root.findall('.//item') + root.findall('.//entry'):
        title = (item.findtext('title') or '').strip()
        url = (item.findtext('link') or '').strip()
        desc = (item.findtext('description') or item.findtext('summary') or item.findtext('content') or '').strip()
        pub_date = (item.findtext('pubDate') or item.findtext('published') or '').strip()
        # 清理HTML
        desc = re.sub(r'<[^>]+>', '', desc)
        if len(desc) > 200:
            desc = desc[:200] + '...'
        if title and url:
            # 简单日期解析
            date_str = datetime.now().strftime('%Y-%m-%d')
            items.append({
                'title': title,
                'url': url,
                'intro': desc,
                'date': date_str,
                'source': source_config['name'],
                'category': source_config['category']
            })
    return items

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
