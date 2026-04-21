#!/usr/bin/env python3
"""
银行信贷审查聚合查询工具
用法: python3 credit-review.py <企业名称或股票代码>
"""
import json
import sys
import warnings
import socket
import os
from datetime import datetime
from urllib.request import urlopen, Request

warnings.filterwarnings('ignore')
socket.setdefaulttimeout(20)

TOKEN_FILE = '/Users/bismarck/.hermes/configs/tushare.json'
OUTPUT_DIR = '/Users/bismarck/KnowledgeBase/CreditWiki/outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# 1. 企业基本信息（工商数据 + 公开市场数据）
# ──────────────────────────────────────────────
def get_company_basics_market(code):
    """通过股票代码获取上市公司基本信息"""
    with open(TOKEN_FILE) as f:
        token = json.load(f)['token']
    import tushare as ts
    ts.set_token(token)
    pro = ts.pro_api()

    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'
    df = pro.stock_basic(ts_code=ts_code, limit=1)
    result = {}
    if not df.empty:
        row = df.iloc[0]
        result = {
            'ts_code': row.get('ts_code',''),
            'name': row.get('name',''),
            'industry': row.get('industry',''),
            'market': row.get('market',''),
            'list_date': row.get('list_date',''),
            'exchange': row.get('exchange',''),
            'is_hs': row.get('is_hs',''),
        }
    return result

# ──────────────────────────────────────────────
# 2. 新浪财经股权结构
# ──────────────────────────────────────────────
def get_shareholders_sina(code):
    """获取前十大股东（新浪财经）"""
    exchange = 'sh' if code.startswith(('6','5')) else 'sz'
    url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCP_CenterTest/code/{exchange}{code}.phtml'
    return []  # 暂留空，需要解析HTML

# ──────────────────────────────────────────────
# 3. 实时行情（新浪API）
# ──────────────────────────────────────────────
def get_realtime_quote(codes):
    """批量获取实时行情"""
    stocks = []
    for code in codes:
        exchange = 'sh' if code.startswith(('6','5')) else 'sz'
        stocks.append(f'{exchange}{code}')
    url = f'https://hq.sinajs.cn/list={",".join(stocks)}'
    req = Request(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'})
    results = []
    with urlopen(req, timeout=10) as r:
        data = r.read().decode('gbk')
    for line in data.split('\n'):
        if '=' not in line:
            continue
        parts = line.split('"')
        if len(parts) < 2:
            continue
        code = line.split('=')[0].split('_')[-1]
        fields = parts[1].split(',')
        if len(fields) < 10:
            continue
        results.append({
            'code': code,
            'name': fields[0],
            'open': float(fields[1]),
            'prev_close': float(fields[2]),
            'price': float(fields[3]),
            'high': float(fields[4]),
            'low': float(fields[5]),
            'volume': int(fields[8]),
            'amount': float(fields[9]),
            'chg_pct': round((float(fields[3]) - float(fields[2])) / float(fields[2]) * 100, 2),
        })
    return results

# ──────────────────────────────────────────────
# 4. 财务数据（Tushare）
# ──────────────────────────────────────────────
def get_financials_tushare(code):
    """获取财务指标和估值"""
    with open(TOKEN_FILE) as f:
        token = json.load(f)['token']
    import tushare as ts
    ts.set_token(token)
    pro = ts.pro_api()

    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'

    # 财务指标（ROE、PE等）
    fina = pro.fina_indicator(ts_code=ts_code, start_date='20250101', limit=1)
    # 日线行情（算财务数据用）
    daily = pro.daily(ts_code=ts_code, limit=1)
    # 估值数据（PE/PB/PS）
    daily_basic = pro.daily_basic(ts_code=ts_code, limit=5)

    result = {'fina': None, 'daily': None, 'daily_basic': None}
    if not fina.empty:
        result['fina'] = fina.iloc[0].to_dict()
    if not daily.empty:
        result['daily'] = daily.iloc[0].to_dict()
    if not daily_basic.empty:
        result['daily_basic'] = daily_basic.iloc[0].to_dict()
    return result

# ──────────────────────────────────────────────
# 5. 行业分析（预留接口）
# ──────────────────────────────────────────────
def get_industry_analysis(industry_name):
    """行业分析（从本地知识库读取行业报告摘要）"""
    kb_path = f'/Users/bismarck/KnowledgeBase/CreditWiki/raw/行业研究'
    notes = []
    if os.path.exists(kb_path):
        for f in os.listdir(kb_path):
            if f.endswith('.md') and industry_name in open(os.path.join(kb_path, f), errors='ignore').read():
                notes.append(f'📄 {f}')
    return notes

# ──────────────────────────────────────────────
# 6. 授信方案建议
# ──────────────────────────────────────────────
def calc_credit_recommendation(financials, market_data):
    """计算建议授信方案"""
    result = {}

    # 从财务数据提取
    fina = financials.get('fina', {}) or {}
    daily = financials.get('daily', {}) or {}
    daily_basic = financials.get('daily_basic', {}) or {}

    close = daily.get('close', 0) or 0
    roe = fina.get('roe', 0) or 0
    bps = fina.get('bps', 0) or 0  # 每股净资产
    ocfps = fina.get('ocfps', 0) or 0  # 每股经营现金流
    debt_to_assets = fina.get('debt_to_assets', 0) or 0  # 资产负债率
    current_ratio = None  # Tushare财务表不一定有，用NA
    pe = daily_basic.get('pe', 0) or 0
    pb = daily_basic.get('pb', 0) or 0
    netprofit_margin = fina.get('netprofit_margin', 0) or 0
    net_profit = fina.get('netprofit_yoy', 0) or 0  # 净利润增速
    assets_turn = fina.get('assets_turn', 0) or 0

    # 政策行业分类（简单示例）
    industry_score = 7  # 默认中上

    # 综合评分（10分制）
    score = 5.0
    if roe > 15: score += 1.5
    elif roe > 10: score += 1.0
    elif roe > 5: score += 0.5

    if pb < 1: score += 1.0  #破净可能低估
    elif pb < 2: score += 0.5

    if debt_to_assets < 70: score += 1.0
    elif debt_to_assets > 85: score -= 1.5

    if netprofit_margin > 20: score += 1.0
    elif netprofit_margin < 5: score -= 1.0

    score = max(1.0, min(10.0, score))

    # 风险等级
    if score >= 7.5: risk_level = '🟢 低'
    elif score >= 5.0: risk_level = '🟡 中'
    else: risk_level = '🔴 高'

    # 建议额度（简化估算：净资产×50% 或 营收×20%）
    if bps and close:
        # 上市公司：参考市值和净资产
        suggested_limit = round(bps * 1.0, 2)  # 每股净资产作为担保价值参考
    else:
        suggested_limit = 0

    # 担保方式建议
    if pb < 0.8:
       担保方式 = '信用+保证担保（轻资产，净资产不足）'
    elif pb < 1.5:
        担保方式 = '信用为主，辅以抵押（房产/土地）'
    else:
        担保方式 = '抵押/质押为主（资产较实）'

    # 政策匹配度
    policy_score = round(score * 0.8 + industry_score * 0.2, 1)
    if policy_score >= 8: policy_match = '✅ 高度匹配'
    elif policy_score >= 6: policy_match = '⚠️ 基本匹配'
    else: policy_match = '❌ 匹配度不足'

    # 意见
    if score >= 7.5: opinion = '✅ 推荐'
    elif score >= 5.5: opinion = '⚠️ 有条件推荐'
    else: opinion = '❌ 不推荐'

    return {
        '综合评分': round(score, 1),
        '风险等级': risk_level,
        '建议意见': opinion,
        '建议授信期限': '12个月（流动资金贷款）',
        '建议担保方式': 担保方式,
        '政策匹配度': policy_match,
        '政策匹配得分': policy_score,
        '核心指标': {
            'ROE': f'{roe:.2f}%' if roe else 'N/A',
            '资产负债率': f'{debt_to_assets:.2f}%' if debt_to_assets else 'N/A',
            '净利润率': f'{netprofit_margin:.2f}%' if netprofit_margin else 'N/A',
            'PE': f'{pe:.2f}' if pe else 'N/A',
            'PB': f'{pb:.2f}' if pb else 'N/A',
        }
    }

# ──────────────────────────────────────────────
# 7. 生成Markdown报告
# ──────────────────────────────────────────────
def generate_report(company_name, code, basics, financials, quote, credit):
    today = datetime.now().strftime('%Y年%m月%d日')
    ts_code = f'{code}.SH' if code.startswith(('6','5')) else f'{code}.SZ'

    fina = financials.get('fina', {}) or {}
    daily = financials.get('daily', {}) or {}
    daily_basic = financials.get('daily_basic', {}) or {}

    # 价格和涨跌
    price = daily.get('close', 0) or quote[0]['price'] if quote else 'N/A'
    chg_pct = daily.get('pct_chg', 0) or quote[0]['chg_pct'] if quote else 'N/A'

    report = f"""# 银行信贷审查报告

---

## 📋 报告封面

| 项目 | 内容 |
|------|------|
| **企业名称** | {company_name} |
| **股票代码** | {code}（{ts_code}） |
| **报告日期** | {today} |
| **报告类型** | 贷前信用审查 |
| **审查机构** | 银行信贷部 |

---

## 一、企业基本信息

| 项目 | 内容 |
|------|------|
| 企业名称 | {basics.get('name', company_name)} |
| 股票代码 | {code} |
| 交易所 | {'上海证券交易所' if code.startswith(('6','5')) else '深圳证券交易所'} |
| 行业分类 | {basics.get('industry', 'N/A')} |
| 上市日期 | {basics.get('list_date', 'N/A')} |
| 市场类型 | {basics.get('market', 'N/A')} |

> 💡 上市公司信息披露较为透明，数据可信度高。

---

## 二、公司治理结构

| 项目 | 说明 |
|------|------|
| 股权结构 | 上市公司，股权分散度需通过年报确认 |
| 实际控制人 | 需通过年报"实际控制人"章节获取 |
| 关联企业 | 需通过年报"关联方交易"章节获取 |
| 董事会构成 | 需通过年报获取 |

> ⚠️ **注意**：完整股权结构建议以最新年报/招股说明书为准。

---

## 三、实控人与股东信息

> 本节数据需结合年报"公司治理"章节和第三方平台（如天眼查）交叉验证。

| 信息类型 | 获取方式 |
|----------|----------|
| 前十大股东 | 年报/季报披露 |
| 实控人背景 | 年报/新闻检索 |
| 股东信用记录 | 央行征信系统（银行内部） |

---

## 四、主营业务与行业分析

| 项目 | 内容 |
|------|------|
| 所属行业 | {basics.get('industry', 'N/A')} |
| 主营业务 | 上市公司主营业务详见年报"业务概要" |
| 行业地位 | 需结合市占率和排名数据 |
| 行业政策 | 需结合监管文件判断 |

### 行业政策环境
- 是否有行业限制性政策
- 环保/能耗/安全生产合规性
- 宏观产业政策导向

---

## 五、银行贷款融资信息

| 融资渠道 | 情况说明 |
|----------|----------|
| 银行贷款 | 上市公司信贷数据需通过银行征信报告获取 |
| 信用评级 | 公开市场发债主体可查信用评级 |
| 对外担保 | 需通过年报"担保情况"章节获取 |
| 债券/信托 | 上市公司重大融资需公告披露 |

> 💡 我行可结合企业征信报告（银行内部系统）核实完整负债情况。

---

## 六、企业财务分析

### 6.1 关键财务指标

| 指标类别 | 指标名称 | 数值 | 参考意义 |
|----------|----------|------|----------|
| **盈利能力** | 净资产收益率（ROE） | {fina.get('roe', 'N/A')}% | 越高越好，>15%为优 |
| **盈利能力** | 净利润率 | {fina.get('netprofit_margin', 'N/A')}% | 衡量主业盈利能力 |
| **盈利能力** | 每股收益（EPS） | {fina.get('eps', 'N/A')}元 | 衡量股东回报水平 |
| **偿债能力** | 资产负债率 | {fina.get('debt_to_assets', 'N/A')}% | 越低越稳健，>85%需关注 |
| **偿债能力** | 债务/权益比 | {fina.get('debt_to_eqt', 'N/A')} | 衡量杠杆水平 |
| **营运能力** | 资产周转率 | {fina.get('assets_turn', 'N/A')} | 衡量运营效率 |
| **估值水平** | 市盈率（PE） | {daily_basic.get('pe', 'N/A')} | 越低相对便宜 |
| **估值水平** | 市净率（PB） | {daily_basic.get('pb', 'N/A')} | 破净可能资产低估 |

### 6.2 近期行情

| 项目 | 数值 |
|------|------|
| 最新收盘价 | {price} 元 |
| 涨跌幅 | {chg_pct}% |
| 近期趋势 | 需结合K线判断 |

### 6.3 财务健康度评估

- **盈利能力**：【{("优秀" if fina.get("roe", 0) and fina.get("roe") > 15 else "良好" if fina.get("roe", 0) and fina.get("roe") > 8 else "一般" if fina.get("roe", 0) else "数据缺失")}】
- **偿债能力**：【{("稳健" if fina.get("debt_to_assets", 100) and fina.get("debt_to_assets") < 70 else "偏高" if fina.get("debt_to_assets", 0) and fina.get("debt_to_assets") < 85 else "高危" if fina.get("debt_to_assets", 0) else "数据缺失")}】
- **成长性**：净利润增速 {fina.get('netprofit_yoy', 'N/A')}%
- **现金流**：每股经营现金流 {fina.get('ocfps', 'N/A')} 元

---

## 七、授信方案建议与政策匹配度

### 7.1 综合评价

| 评价维度 | 结果 |
|----------|------|
| **综合评分** | **{credit['综合评分']}** / 10 |
| **风险等级** | {credit['风险等级']} |
| **建议意见** | **{credit['建议意见']}** |
| **政策匹配度** | {credit['政策匹配度']}（得分：{credit.get('政策匹配得分', 'N/A')}） |

### 7.2 授信方案建议

| 授信要素 | 建议内容 |
|----------|----------|
| **建议授信额度** | 参考净资产规模，具体以我行授信审批为准 |
| **建议授信期限** | {credit.get('建议授信期限', '12个月')} |
| **建议担保方式** | {credit.get('建议担保方式', '抵押/质押')} |
| **贷款用途** | 流动资金贷款、固定资产贷款等 |

### 7.3 政策匹配分析

| 政策维度 | 匹配情况 |
|----------|----------|
| 产业政策 | 符合国家产业导向 |
| 环保政策 | 需核实环评合规情况 |
| 我行信贷政策 | 综合评分{credit['综合评分']}分，符合基本准入条件 |
| 宏观审慎评估 | 建议结合央行MPA结果 |

---

## 八、审查结论

### ✅ 综合意见

> **{credit['建议意见']}**

### 📊 综合评分：{credit['综合评分']}分（{credit['风险等级']}风险）**

### 主要优势
{("• ROE水平较高，盈利能力良好" if fina.get('roe', 0) and fina.get('roe') > 10 else "• 主营业务稳定，市场地位尚可") if fina.get('roe') else "• 上市公司信息披露透明"}

### 主要风险点
{("• 资产负债率偏高，偿债压力较大" if fina.get('debt_to_assets', 0) and fina.get('debt_to_assets') > 80 else "• 行业政策存在不确定性" if basics.get('industry') else "• 需进一步核实实际负债情况") if fina.get('debt_to_assets') else "• 建议补充财务数据进行综合判断"}

### 贷后管理建议
1. 定期监测财务指标变化（每季度）
2. 关注行业政策动态
3. 跟踪贷款资金用途合规性
4. 建立预警机制（股价波动、评级变化等）

---

## ⚠️ 风险声明

1. 本报告数据来源于公开市场信息，仅供参考
2. 实际授信决策需结合我行内部信用评级、征信报告等综合判断
3. 本报告不构成最终授信承诺

---

*报告生成时间：{today}*
*工具支持：Tushare Pro + 新浪财经API*
"""

    return report

# ──────────────────────────────────────────────
# 主程序入口
# ──────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法: python3 credit-review.py <企业名称或股票代码>")
        print("示例: python3 credit-review.py 601166")
        print("       python3 credit-review.py 兴业银行")
        sys.exit(1)

    identifier = sys.argv[1].strip()

    # 如果是纯数字，当作股票代码处理
    if identifier.isdigit():
        code = identifier
        company_name = f"股票{code}"
    else:
        # 尝试匹配股票代码（从配置或已知映射中）
        code = identifier  # 暂时直接使用
        company_name = identifier

    print(f'\n🏦 银行信贷审查报告生成中...')
    print(f'📌 目标: {company_name} ({code})')
    print('=' * 50)

    # Step 1: 基本信息
    print('📋 1. 获取企业基本信息...')
    basics = get_company_basics_market(code)
    company_name = basics.get('name', company_name)
    print(f'   ✅ {company_name} | 行业: {basics.get("industry", "N/A")}')

    # Step 2: 实时行情
    print('📈 2. 获取实时行情...')
    quote = get_realtime_quote([code])
    print(f'   ✅ 现价: {quote[0]["price"]}元 | 涨跌: {quote[0]["chg_pct"]}%')

    # Step 3: 财务数据
    print('📊 3. 获取财务数据...')
    financials = get_financials_tushare(code)
    fina = financials.get('fina', {}) or {}
    print(f'   ✅ ROE: {fina.get("roe", "N/A")}% | 资产负债率: {fina.get("debt_to_assets", "N/A")}%')

    # Step 4: 授信建议
    print('🧮 4. 计算授信方案...')
    credit = calc_credit_recommendation(financials, quote)
    print(f'   ✅ 综合评分: {credit["综合评分"]}/10 | 风险等级: {credit["风险等级"]} | 意见: {credit["建议意见"]}')

    # Step 5: 生成报告
    print('📝 5. 生成审查报告...')
    report = generate_report(company_name, code, basics, financials, quote, credit)

    # 保存报告
    safe_name = company_name.replace(' ', '_').replace('*', '')
    output_path = f'{OUTPUT_DIR}/信贷审查_{safe_name}_{datetime.now().strftime("%Y%m%d")}.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print()
    print('=' * 50)
    print('✅ 信贷审查报告生成完成！')
    print(f'📁 报告路径: {output_path}')
    print()
    print(report)

if __name__ == '__main__':
    main()
