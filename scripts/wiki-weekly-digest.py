#!/usr/bin/env python3
"""
Wiki 每周知识摘要
每周日生成"本周新增知识摘要"，推送微信
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta

WIKI_DIR = Path(__file__).parent.parent / "wiki"
ARTICLES_DIR = WIKI_DIR / "articles"

# 专题关键词（与 wiki-specialize.py 保持一致）
SPECIALS = {
    "银行信贷审查": ["以贷还贷", "信贷", "授信", "净息差", "银行承兑汇票", "票据", "信用风险", "不良贷款", "拨备", "资本充足率"],
    "供应链金融": ["供应链金融", "保理", "应收账款", "预付账款", "存货融资", "核心企业", "供应商", "经销商"],
    "金融监管与合规": ["监管", "处罚", "合规", "反洗钱", "KYC", "AML", "金融法院", "托管人", "SEC", "市政债券"],
    "医药行业研究": ["医药", "集采", "仿制药", "创新药", "药企", "Biotech", "Biopharma", "医院"],
    "AI与金融科技": ["AI", "大模型", "LLM", "财务智能体", "数字化员工", "RPA", "自动化", "知识库", "Agent"],
    "房地产金融": ["房地产", "房贷", "预售制", "开发商", "土地财政", "城投", "房价", "地产"],
    "资本市场与交易": ["港股", "T+1", "结算", "股票", "二级市场", "做市商", "ETF", "量化"],
}


def get_this_week_range():
    """获取本周日期范围（周一到周日）"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def extract_frontmatter(content):
    match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def extract_title(content, filename):
    fm = extract_frontmatter(content)
    if fm.get('title'):
        return fm['title']
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    name = filename.rsplit('_', 1)[0]
    return name.replace('_', ' ')


def get_article_date(filename):
    """从文件名提取日期"""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)
    return ""


def get_source(content):
    """提取文章来源"""
    match = re.search(r'> 来源：([^\n>]+)', content)
    if match:
        return match.group(1).strip()
    return "未知来源"


def get_tags(content):
    """提取标签"""
    tags_match = re.search(r'tags:\s*\[(.*?)\]', content, re.DOTALL)
    if not tags_match:
        return []
    return [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(',') if t.strip()]


def get_summary(content):
    """提取摘要（前300字）"""
    text = content
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
    text = re.sub(r'^#+\s+[^\n]+\n', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'[*_`#|>\n]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:300] + "..." if len(text) > 300 else text


def detect_special(title, content):
    """检测文章所属专题"""
    text = (title + " " + content).lower()
    results = []
    for special, keywords in SPECIALS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            results.append((special, score))
    results.sort(key=lambda x: -x[1])
    return results[0][0] if results else "其他"


def build_digest():
    """构建本周摘要"""
    monday, sunday = get_this_week_range()
    week_str = f"{monday.strftime('%m/%d')}～{sunday.strftime('%m/%d')}"
    
    # 收集本周文章
    week_articles = []
    all_articles = []
    
    for fp in sorted(ARTICLES_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        fname = fp.name
        date_str = get_article_date(fname)
        
        if date_str:
            try:
                art_date = datetime.strptime(date_str, "%Y-%m-%d")
                in_week = monday <= art_date <= sunday
            except:
                in_week = False
        else:
            in_week = False
        
        content = fp.read_text(encoding='utf-8')
        title = extract_title(content, fname)
        source = get_source(content)
        tags = get_tags(content)
        summary = get_summary(content)
        special = detect_special(title, content)
        
        art = {
            "file": fname,
            "title": title,
            "date": date_str,
            "source": source,
            "tags": tags,
            "summary": summary,
            "special": special,
        }
        
        all_articles.append(art)
        if in_week:
            week_articles.append(art)
    
    return week_str, week_articles, all_articles


def format_digest_text(week_str, week_articles, all_articles):
    """生成纯文本摘要（推送微信）"""
    lines = []
    lines.append(f"📊 CreditWiki 知识周报")
    lines.append(f"📅 {week_str} | 共 {len(all_articles)} 篇")
    lines.append("")
    
    if not week_articles:
        lines.append("本周无新增文章")
        lines.append(f"知识库累计 {len(all_articles)} 篇，均为历史文章")
    else:
        lines.append(f"🆕 本周新增 {len(week_articles)} 篇：")
        lines.append("")
        
        # 按专题分组
        by_special = {}
        for art in week_articles:
            sp = art['special']
            if sp not in by_special:
                by_special[sp] = []
            by_special[sp].append(art)
        
        for sp, arts in by_special.items():
            lines.append(f"【{sp}】")
            for art in arts:
                date = art['date'].split('-')[-1] if art['date'] else ''
                lines.append(f"  • {art['title']}")
                if art['tags']:
                    lines.append(f"    标签: {' '.join(art['tags'])}")
            lines.append("")
    
    # 全库统计
    lines.append("─── 全库概览 ───")
    special_counts = {}
    for art in all_articles:
        sp = art['special']
        special_counts[sp] = special_counts.get(sp, 0) + 1
    
    for sp, cnt in sorted(special_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {sp}: {cnt}篇")
    
    lines.append("")
    lines.append(f"💬 输入关键词搜索：`python3 scripts/wiki-search.py 以贷还贷`")
    
    return '\n'.join(lines)


def format_digest_markdown(week_str, week_articles, all_articles):
    """生成 Markdown 摘要"""
    lines = []
    lines.append(f"# 📊 CreditWiki 知识周报")
    lines.append(f"**周期**：{week_str}  ")
    lines.append(f"**全库总量**：{len(all_articles)} 篇")
    lines.append("")
    
    if not week_articles:
        lines.append("> 📭 本周无新增文章")
    else:
        lines.append(f"## 🆕 本周新增 ({len(week_articles)} 篇)")
        lines.append("")
        
        by_special = {}
        for art in week_articles:
            sp = art['special']
            if sp not in by_special:
                by_special[sp] = []
            by_special[sp].append(art)
        
        for sp, arts in by_special.items():
            lines.append(f"### 【{sp}】({len(arts)}篇)")
            for art in arts:
                date = art['date'] if art['date'] else ""
                tags_str = " | ".join(art['tags']) if art['tags'] else ""
                lines.append(f"- **{art['title']}** {date}")
                if tags_str:
                    lines.append(f"  - 标签：{tags_str}")
                lines.append(f"  - {art['summary']}")
                lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## 📚 全库专题分布")
    special_counts = {}
    for art in all_articles:
        sp = art['special']
        special_counts[sp] = special_counts.get(sp, 0) + 1
    
    for sp, cnt in sorted(special_counts.items(), key=lambda x: -x[1]):
        bar = "█" * cnt
        lines.append(f"- **{sp}**: {cnt}篇 {bar}")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**搜索**：`python3 scripts/wiki-search.py <关键词>`")
    lines.append("**专题索引**：`wiki/specials/index.md`")
    
    return '\n'.join(lines)


def save_digest(week_str, week_articles, all_articles):
    """保存摘要文件"""
    OUTPUTS_DIR = WIKI_DIR.parent / "outputs"
    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    week_safe = week_str.replace("/", "-")
    
    # 纯文本版
    text = format_digest_text(week_str, week_articles, all_articles)
    txt_fp = OUTPUTS_DIR / f"知识周报_{week_safe}.txt"
    txt_fp.write_text(text, encoding='utf-8')
    
    # Markdown版
    md = format_digest_markdown(week_str, week_articles, all_articles)
    md_fp = OUTPUTS_DIR / f"知识周报_{week_safe}.md"
    md_fp.write_text(md, encoding='utf-8')
    
    return txt_fp, md_fp


def main():
    week_str, week_articles, all_articles = build_digest()
    
    if len(all_articles) == 0:
        print("知识库为空，无内容可摘要")
        return
    
    txt_fp, md_fp = save_digest(week_str, week_articles, all_articles)
    print(f"✅ 知识周报已生成：")
    print(f"   文本：{txt_fp}")
    print(f"   Markdown：{md_fp}")
    print()
    print("─── 预览 ───")
    print(format_digest_text(week_str, week_articles, all_articles))


if __name__ == "__main__":
    main()
