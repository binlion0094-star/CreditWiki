#!/usr/bin/env python3
"""
股票数据查询工具 - 新浪财经API
用法:
  python3 stock-query.py 601166      # 单股查询
  python3 stock-query.py 601166 600000 600036  # 多股查询
"""
import urllib.request
import json
import sys
import warnings
warnings.filterwarnings('ignore')


def get_stock(code: str) -> dict:
    """获取单只股票实时行情"""
    exchange = 'sh' if code.startswith(('6', '5')) else 'sz'
    url = f'https://hq.sinajs.cn/list={exchange}{code}'
    req = urllib.request.Request(url, headers={'Referer': 'https://finance.sina.com.cn'})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = r.read().decode('gbk')
    parts = data.split('"')[1].split(',')
    name = parts[0]
    prev_close = float(parts[2])
    open_price = float(parts[1])
    price = float(parts[3])
    high = float(parts[4])
    low = float(parts[5])
    volume = int(parts[8])  # 手
    amount = float(parts[9])  # 元
    chg = round((price - prev_close) / prev_close * 100, 2)
    return {
        'code': code,
        'name': name,
        'price': price,
        'prev_close': prev_close,
        'open': open_price,
        'high': high,
        'low': low,
        'chg_pct': chg,
        'volume': volume,
        'amount': amount,
    }


def format_stock(s: dict) -> str:
    """格式化输出"""
    arrow = '▲' if s['chg_pct'] >= 0 else '▼'
    sign = '+' if s['chg_pct'] >= 0 else ''
    return (
        f"{s['name']} ({s['code']})\n"
        f"  现价: {s['price']} 元  {arrow} {sign}{s['chg_pct']}%\n"
        f"  今开: {s['open']}  昨收: {s['prev_close']}\n"
        f"  最高: {s['high']}  最低: {s['low']}\n"
        f"  成交: {s['volume']:,} 手  金额: {s['amount']/1e8:.2f} 亿"
    )


if __name__ == '__main__':
    codes = sys.argv[1:] or ['601166']
    print(f"📊 股票实时行情 ({len(codes)} 只)\n{'='*40}")
    for code in codes:
        try:
            s = get_stock(code.strip())
            print(format_stock(s))
        except Exception as e:
            print(f"❌ {code}: {e}")
        print()
