#!/usr/bin/env python3
"""
Tushare Pro 查询工具
用法:
  python3 tushare-query.py daily 601166        # 实时行情
  python3 tushare-query.py financial 601166    # 财务指标
  python3 tushare-query.py basics 601166       # 基本信息
  python3 tushare-query.py pe 601166           # PE/PB等估值
"""
import urllib.request
import json
import sys
import warnings
import socket
warnings.filterwarnings('ignore')
socket.setdefaulttimeout(15)

TOKEN_FILE = '/Users/bismarck/.hermes/configs/tushare.json'

def load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)['token']

def init_pro():
    import tushare as ts
    token = load_token()
    ts.set_token(token)
    return ts.pro_api()

def cmd_daily(code):
    """查询近期行情 K线"""
    pro = init_pro()
    # 转换代码格式
    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'
    df = pro.daily(ts_code=ts_code, limit=5)
    print(f'\n📈 {code} 近期行情（前5个交易日）')
    print('-' * 50)
    print(df[['trade_date','open','high','low','close','vol','pct_chg']].to_string(index=False))

def cmd_financial(code):
    """查询财务指标"""
    pro = init_pro()
    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'
    try:
        df = pro.fina_indicator(ts_code=ts_code, start_date='20250101', limit=1)
        print(f'\n📊 {code} 最新财务指标')
        print('-' * 50)
        # 打印所有可用字段
        for col in df.columns:
            val = df[col].values[0]
            if val is not None and val != '':
                print(f'  {col}: {val}')
    except Exception as e:
        print(f'  ⚠️ 财务指标查询失败: {e}')
        print('  （可能需要积分权限，尝试基础接口...）')
        # 降级：只用日线数据展示
        df2 = pro.daily(ts_code=ts_code, limit=1)
        if not df2.empty:
            row = df2.iloc[0]
            print(f'  最新价: {row["close"]} 元')
            print(f'  涨跌幅: {row["pct_chg"]}%')

def cmd_basics(code):
    """查询股票基本信息"""
    pro = init_pro()
    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'
    df = pro.stock_basic(ts_code=ts_code, limit=1)
    print(f'\n🏢 {code} 基本信息')
    print('-' * 50)
    print(df[['ts_code','name','industry','list_date','market']].to_string(index=False))

def cmd_pe(code):
    """查询PE/PB等估值数据"""
    pro = init_pro()
    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'
    try:
        df = pro.daily_basic(ts_code=ts_code, limit=5)
        print(f'\n💰 {code} 估值数据（前5交易日）')
        print('-' * 50)
        print(df[['trade_date','close','pe','pb','ps','dv_ttm']].to_string(index=False))
    except Exception as e:
        print(f'  ⚠️ 估值接口失败: {e}')

def cmd_help():
    print('\n📖 Tushare Pro 查询工具')
    print('=' * 50)
    print('  daily <code>      - 近期行情（K线）')
    print('  financial <code> - 财务指标')
    print('  basics <code>    - 基本信息')
    print('  pe <code>        - PE/PB/PS估值')
    print('  help              - 显示帮助')
    print()
    print('示例:')
    print('  python3 tushare-query.py daily 601166')
    print('  python3 tushare-query.py pe 600036')
    print('  python3 tushare-query.py financial 000001')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    code = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == 'daily' and code:
        cmd_daily(code)
    elif cmd == 'financial' and code:
        cmd_financial(code)
    elif cmd == 'basics' and code:
        cmd_basics(code)
    elif cmd == 'pe' and code:
        cmd_pe(code)
    else:
        cmd_help()
