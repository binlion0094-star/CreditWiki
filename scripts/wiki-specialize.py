#!/usr/bin/env python3
"""
Wiki 专题聚合
将相关文章聚合成专题，生成专题索引 + 专题总结
"""
import os
import re
import json
from pathlib import Path

WIKI_DIR = Path(__file__).parent.parent / "wiki"
ARTICLES_DIR = WIKI_DIR / "articles"
SPECIALS_DIR = WIKI_DIR / "specials"

# 专题定义：名称 + 关键词列表（OR逻辑）
SPECIALS = {
    "银行信贷审查": {
        "keywords": ["以贷还贷", "信贷", "授信", "净息差", "银行承兑汇票", "票据", "信用风险", "不良贷款", "拨备", "资本充足率"],
        "description": "银行信贷业务的全流程审查要点、法律风险、行业监管"
    },
    "供应链金融": {
        "keywords": ["供应链金融", "保理", "应收账款", "预付账款", "存货融资", "核心企业", "供应商", "经销商"],
        "description": "供应链金融三大模式（应收/预付/存货）及创新方向"
    },
    "金融监管与合规": {
        "keywords": ["监管", "处罚", "合规", "反洗钱", "KYC", "AML", "金融法院", "托管人", "SEC", "市政债券"],
        "description": "国内外金融监管政策、处罚案例、合规要求"
    },
    "医药行业研究": {
        "keywords": ["医药", "集采", "仿制药", "创新药", "药企", "Biotech", "Biopharma", "医院"],
        "description": "医药行业政策分析、企业战略、竞争格局"
    },
    "跨境交易与地缘政治": {
        "keywords": ["中东", "伊朗", "跨境", "出口", "进口", "汇率", "外汇", "美元", "人民币国际化"],
        "description": "跨境交易动态、地缘政治对金融的影响"
    },
    "AI与金融科技": {
        "keywords": ["AI", "大模型", "LLM", "财务智能体", "数字化员工", "RPA", "自动化", "知识库", "Agent"],
        "description": "AI技术在金融领域的应用实践"
    },
    "房地产金融": {
        "keywords": ["房地产", "房贷", "预售制", "开发商", "土地财政", "城投", "房价", "地产"],
        "description": "房地产行业分析、信贷政策、风险评估"
    },
    "资本市场与交易": {
        "keywords": ["港股", "T+1", "结算", "股票", "二级市场", "做市商", "ETF", "量化"],
        "description": "资本市场交易制度、结算周期、市场结构"
    },
    "城投与政府融资": {
        "keywords": ["城投", "平台贷", "隐性债务", "化债", "政信", "城投债", "政府债务", "地方融资", "专项债"],
        "description": "城投平台融资、地方政府债务、化债政策"
    },
    "新能源行业": {
        "keywords": ["新能源", "光伏", "风电", "储能", "锂电池", "新能源汽车", "动力电池", "碳中和", "绿电", "充电桩"],
        "description": "新能源行业政策、技术路线、产能周期与信贷风险"
    },
    "消费行业": {
        "keywords": ["消费", "白酒", "乳制品", "家电", "汽车", "零售", "食品", "饮料", "纺织", "日化", "4S店"],
        "description": "消费品行业格局、品牌渠道、消费周期与授信要点"
    },
    "港口航运": {
        "keywords": ["港口", "航运", "集装箱", "干散货", "油轮", "船舶", "运价", "造船", "波罗的海", "LNG船"],
        "description": "港口航运周期、运力供需、船舶抵押与贸易金融"
    }
}


def extract_frontmatter(content):
    """提取 frontmatter"""
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
    """提取标题"""
    fm = extract_frontmatter(content)
    if fm.get('title'):
        return fm['title']
    # 尝试从 # 标题行提取
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# ') and not line.startswith('# '):
            return line[2:].strip()
    # 从文件名还原
    name = filename.rsplit('_', 1)[0]
    return name.replace('_', ' ')


def score_article(text, keywords):
    """计算文章与专题的相关性得分"""
    text_lower = text.lower()
    score = 0
    for kw in keywords:
        count = text_lower.count(kw.lower())
        score += count
    return score


def load_articles():
    """加载所有文章"""
    articles = []
    for fp in ARTICLES_DIR.glob("*.md"):
        content = fp.read_text(encoding='utf-8')
        title = extract_title(content, fp.name)
        score_text = content.lower()
        tags_match = re.search(r'tags:\s*\[(.*?)\]', content, re.DOTALL)
        tags = []
        if tags_match:
            tags = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(',') if t.strip()]
        
        articles.append({
            "path": fp.name,
            "title": title,
            "content": content,
            "score_text": score_text,
            "tags": tags,
            "date": fp.stem.split('_')[-1] if re.search(r'\d{4}-\d{2}-\d{2}', fp.name) else ""
        })
    return articles


def classify_articles(articles):
    """将文章分类到专题"""
    # 每个专题取得分最高的前5篇
    special_map = {}  # special_name -> [(article, score), ...]
    
    for special_name, spec in SPECIALS.items():
        scored = []
        for art in articles:
            s = score_article(art["content"], spec["keywords"])
            if s > 0:
                scored.append((art, s))
        scored.sort(key=lambda x: -x[1])
        special_map[special_name] = scored[:5]
    
    return special_map


def generate_special_index(special_map):
    """生成专题索引"""
    SPECIALS_DIR.mkdir(exist_ok=True)
    
    index_content = ["# 📚 CreditWiki 专题索引\n"]
    index_content.append(f"共 {len(SPECIALS)} 个专题，更新时间：自动\n")
    index_content.append("""
> 专题按相关性自动聚合，每篇最多显示5篇核心文章。
> 使用 `python3 scripts/wiki-specialize.py [专题名]` 可查看专题详情。

---
""")
    
    for special_name, spec in SPECIALS.items():
        arts = special_map.get(special_name, [])
        index_content.append(f"## {special_name}\n")
        index_content.append(f"{spec['description']}\n")
        index_content.append(f"相关文章：**{len(arts)}** 篇\n")
        
        if arts:
            for art, score in arts:
                date_str = f"（{art['date']}）" if art['date'] else ""
                index_content.append(f"- [[{art['title']}]] {date_str}\n")
        else:
            index_content.append("- （暂无相关文章）\n")
        index_content.append("\n---\n\n")
    
    index_fp = SPECIALS_DIR / "index.md"
    index_fp.write_text(''.join(index_content), encoding='utf-8')
    print(f"✅ 专题索引已更新：wiki/specials/index.md")


def generate_special_pages(special_map):
    """为每个专题生成独立页面"""
    for special_name, spec in SPECIALS.items():
        arts = special_map.get(special_name, [])
        if not arts:
            continue
        
        lines = [f"# {special_name}\n\n"]
        lines.append(f"**专题简介**：{spec['description']}\n\n")
        lines.append(f"**核心文章**：{len(arts)} 篇\n\n")
        lines.append("---\n\n")
        
        for i, (art, score) in enumerate(arts, 1):
            date_str = f"**日期**：{art['date']}  \n" if art['date'] else ""
            tags_str = " | ".join(art['tags']) if art['tags'] else "无标签"
            
            lines.append(f"### {i}. {art['title']}\n\n")
            lines.append(f"{date_str}")
            lines.append(f"**标签**：{tags_str}  \n")
            lines.append(f"**相关度得分**：{score}  \n\n")
            
            # 提取前200字摘要
            content = art['content']
            # 去掉 frontmatter
            content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
            # 去掉标题行
            content = re.sub(r'^#+\s+[^\n]+\n', '', content)
            # 去掉图片和链接
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
            content = re.sub(r'[*_`#|]', '', content)
            content = re.sub(r'\n+', ' ', content).strip()
            
            excerpt = content[:200] + "..." if len(content) > 200 else content
            lines.append(f"> {excerpt}\n\n")
            lines.append(f"📄 [[{art['title']}]]\n\n")
            lines.append("---\n\n")
        
        # 保存专题页面
        safe_name = special_name.replace(" ", "_").replace("/", "_")
        fp = SPECIALS_DIR / f"{safe_name}.md"
        fp.write_text(''.join(lines), encoding='utf-8')
    
    print(f"✅ 专题页面已生成：wiki/specials/*.md")


def show_special_detail(special_name):
    """显示特定专题详情"""
    fp = SPECIALS_DIR / f"{special_name}.md"
    if fp.exists():
        print(fp.read_text(encoding='utf-8'))
    else:
        print(f"专题 '{special_name}' 不存在，请先运行 `python3 scripts/wiki-specialize.py --build`")


def main():
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--build":
            articles = load_articles()
            special_map = classify_articles(articles)
            generate_special_index(special_map)
            generate_special_pages(special_map)
            print(f"\n📊 专题聚合完成，共 {len(SPECIALS)} 个专题")
        elif sys.argv[1] == "--list":
            for name in SPECIALS:
                print(f"  • {name}")
        else:
            show_special_detail(sys.argv[1])
    else:
        # 默认构建
        articles = load_articles()
        special_map = classify_articles(articles)
        generate_special_index(special_map)
        generate_special_pages(special_map)


if __name__ == "__main__":
    main()
