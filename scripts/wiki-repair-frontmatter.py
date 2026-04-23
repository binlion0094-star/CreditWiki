#!/usr/bin/env python3
"""
Wiki Frontmatter 批量修复脚本
- 修复标签格式错误（#在YAML里是注释）
- 补充分类
- 从内容提取第一性原理补充到frontmatter
"""

import re
import yaml
from pathlib import Path
from datetime import datetime

# 导入标签引擎
import sys
sys.path.insert(0, str(Path(__file__).parent))
from tag_engine import suggest_tags_for_article

WIKI_DIR = Path(__file__).parent.parent / "wiki"
SKIP_FILES = {"INDEX.md", "SUMMARY.md", "STATS.md", "TEMPLATE.md", "README.md"}

# 分类关键词映射
CATEGORY_KEYWORDS = {
    "articles": ["研究", "分析", "报告", "案例", "深度", "年度", "趋势", "展望", "合集"],
    "concepts": ["审查要点", "授信政策", "信贷指引", "行业规范", "管理办法", "评审策略", "通知书"],
    "specials": [],
}

def extract_first_principle_from_content(content):
    """从正文提取第一性原理"""
    # 找本质规律段落
    m = re.search(r"### 本质规律\s*\n+(.*?)(?:\n|---\n)", content, re.DOTALL)
    if m:
        return m.group(1).strip()[:300]
    
    # 降级：找第一个h2正文段落
    paras = re.findall(r"(?:^#{1,3}\s+.+?\n)(.+?)(?=^#|\n---\n)", content, re.DOTALL | re.MULTILINE)
    for p in paras:
        p = p.strip()
        if len(p) > 30:
            return p[:300]
    return ""


def extract_tags_from_content(title, content):
    """从标题+内容提取标签"""
    result = suggest_tags_for_article(title, content[:5000])
    return result.get("flat_tags", [])


def determine_category(title, content, existing_category):
    """智能判断分类"""
    if existing_category in ("articles", "concepts", "specials"):
        return existing_category
    
    # 基于文件名判断
    for kw in CATEGORY_KEYWORDS["concepts"]:
        if kw in title:
            return "concepts"
    
    # 基于文件名判断specials
    specials_kws = ["金融监管与合规", "银行信贷审查", "供应链金融", "医药行业研究", 
                   "房地产金融", "AI与金融科技", "城投与政府融资", "港口航运",
                   "新能源行业", "消费行业", "资本市场与交易"]
    for kw in specials_kws:
        if kw in title:
            return "specials"
    
    return "articles"


def repair_frontmatter(filepath):
    """修复单个文件的frontmatter"""
    content = filepath.read_text(encoding="utf-8")
    
    # 提取现有frontmatter
    fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    
    title_match = re.match(r"^#\s+(.+?)\n", content)
    title = title_match.group(1).strip() if title_match else filepath.stem
    
    # 提取本质规律
    first_principle = extract_first_principle_from_content(content)
    
    # 提取标签
    tags = extract_tags_from_content(title, content)
    
    # 确定分类
    existing_category = ""
    if fm_match:
        try:
            existing_fm = yaml.safe_load(fm_match.group(1)) or {}
            existing_category = existing_fm.get("分类", "") or existing_fm.get("category", "")
            # frontmatter的"分类"字段存的是中文如"行业研究"，需要转英文
            cat_map = {"行业研究": "articles", "监管政策": "concepts", "风险管理": "articles",
                       "信贷应用": "concepts", "知识管理": "articles", "未分类": "articles"}
            existing_category = cat_map.get(existing_category, existing_category)
        except:
            pass
    
    category = determine_category(title, content, existing_category)
    
    # 构建新的frontmatter
    new_fm = {
        "title": title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "tags": tags if tags else ["未分类"],
        "doc_id": filepath.stem.split("_")[-1] if filepath.stem.split("_")[-1].isalnum() else filepath.stem[:16],
        "category": category,
        "first_principle": first_principle[:200] if first_principle else "",
    }
    
    # 如果已有url/from保留
    if fm_match:
        try:
            existing_fm = yaml.safe_load(fm_match.group(1)) or {}
            if existing_fm.get("来源"):
                new_fm["来源"] = existing_fm["来源"]
            if existing_fm.get("url"):
                new_fm["url"] = existing_fm["url"]
            if existing_fm.get("来源链接"):
                new_fm["来源链接"] = existing_fm["来源链接"]
        except:
            pass
    
    # 序列化YAML
    yaml_str = yaml.dump(new_fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # 清理：移除空的first_principle行
    yaml_str = re.sub(r"first_principle:\s*\n", "first_principle: \n", yaml_str)
    
    # 替换frontmatter
    if fm_match:
        new_content = re.sub(
            r"^---\s*\n.*?\n---\s*\n",
            f"---\n{yaml_str}---\n",
            content,
            flags=re.DOTALL
        )
    else:
        # 没有frontmatter，在标题后插入
        new_content = re.sub(
            r"^(#\s+.+?\n)",
            rf"\1\n---\n{yaml_str}---\n\n",
            content,
            flags=re.MULTILINE
        )
    
    # 修复标签格式问题：把"标签：#xxx #yyy"改为正确的YAML列表格式
    new_content = re.sub(
        r">\s*标签：(#.*?)\s*\n",
        lambda m: f"> 标签：{', '.join(tags) if tags else '未分类'}\n",
        new_content
    )
    
    if new_content != content:
        filepath.write_text(new_content, encoding="utf-8")
        return True, category, tags
    return False, category, tags


def main():
    print("🔧 CreditWiki Frontmatter 批量修复")
    print("=" * 50)
    
    total = 0
    fixed = 0
    categories = {"articles": 0, "concepts": 0, "specials": 0}
    
    for subdir in WIKI_DIR.iterdir():
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue
        for f in subdir.glob("*.md"):
            if f.name in SKIP_FILES:
                continue
            
            total += 1
            ok, cat, tags = repair_frontmatter(f)
            if ok:
                fixed += 1
                categories[cat] = categories.get(cat, 0) + 1
                tag_str = ", ".join(tags[:4]) if tags else "无标签"
                print(f"  ✅ {f.name[:50]}")
                print(f"     → [{cat}] {tag_str}")
    
    print(f"\n📊 修复完成: {fixed}/{total} 篇")
    print(f"   articles: {categories.get('articles', 0)}")
    print(f"   concepts: {categories.get('concepts', 0)}")
    print(f"   specials: {categories.get('specials', 0)}")


if __name__ == "__main__":
    main()
