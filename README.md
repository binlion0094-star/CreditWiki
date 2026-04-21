# 🏦 信贷知识库 2.0

> 基于 Karpathy LLM 知识库方法论的银行信贷专用知识管理系统

---

## 核心理念

**从"人找信息"到"信息找人"的范式转换**

用户不再需要手动整理笔记，只需要收集原始素材（链接、文档、截图），LLM 负责：
- 提取核心概念
- 分类整理成结构化文章
- 建立反向链接
- 自动维护索引
- 回答复杂问题

---

## 目录结构

```
CreditWiki/
├── 📂 raw/                    # 原始资料（按主题分类）
│   ├── 企业财报/              # 企业年报、季报、征信报告
│   ├── 行业研究/              # 行业分析报告、券商研报
│   ├── 监管政策/              # 政策法规、监管文件
│   ├── 法院判决/              # 司法案例、判决文书
│   └── 信贷合同/              # 合同模板、协议文本
│
├── 📂 wiki/                   # LLM 编译的知识库
│   ├── concepts/              # 概念文章（定义、术语、规则）
│   ├── articles/              # 主题文章（分析、案例、研究）
│   ├── backlinks/             # 反向链接
│   ├── INDEX.md               # 全部文章索引
│   ├── SUMMARY.md             # 知识库摘要
│   ├── STATS.md               # 统计报告
│   └── TEMPLATE.md            # 编译模板
│
├── 📂 output/                 # 查询输出结果
│
└── 📂 scripts/                # 核心脚本
    ├── wiki-search.py         # 全文搜索
    ├── wiki-lint.py           # 健康检查
    ├── wiki-index.py          # 索引生成
    └── wiki-compile.py        # 编译引擎
```

---

## 六大工作流

### 1. Data Ingest（数据摄入）
- 将网页文章、PDF 论文、截图等原始资料存入 `raw/` 对应分类
- 使用 url-to-knowledge 技能自动抓取网页内容
- 支持手动上传 PDF、Word 等文件

### 2. Compile（编译）
```bash
# 编译单个文件
python scripts/wiki-compile.py --file "raw/行业研究/某行业报告.md"

# 编译所有资料
python scripts/wiki-compile.py --all

# 按分类编译
python scripts/wiki-compile.py --category "监管政策"
```

### 3. Q&A（问答）
- 直接向知识库提问复杂信贷问题
- 支持关联图谱追溯
- 带来源引用的回答

### 4. Output（输出）
- Markdown 文档
- 可导出为报告格式
- 有价值输出回流知识库

### 5. Linting（健康检查）
```bash
# 检查知识库健康度
python scripts/wiki-lint.py
```

检查内容：
- 🔗 断裂链接
- 📑 重复概念
- 📚 孤立文章
- ⚙️ 数据一致性

### 6. Enhancement（增强）
- 发现概念间隐含关系
- 补充缺失数据
- 生成新文章候选

---

## 索引生成

```bash
# 生成索引文件
python scripts/wiki-index.py
```

生成文件：
- **INDEX.md**：全部文章索引
- **SUMMARY.md**：知识库摘要 + 标签分布
- **STATS.md**：统计报告

---

## 搜索功能

```bash
# 搜索知识库
python scripts/wiki-search.py "票据风险 招商银行"

# 搜索并包含原始资料
python scripts/wiki-search.py "票据" --raw

# JSON 格式输出
python scripts/wiki-search.py "票据" --json
```

---

## 与旧版知识库对比

| 维度 | 旧版 (KnowledgeBase/) | 新版 (CreditWiki/) |
|------|----------------------|-------------------|
| 数据摄入 | 手动发链接给我归档 | raw/ 目录 + 自动化 |
| 编译方式 | 依赖 AI 每次手动分析 | wiki-compile 自动编译 |
| 检索方式 | 问我问题，我读文件 | 直接搜索/问答 |
| 关联维护 | 手动更新 JSON | 自动建立反向链接 |
| 健康检查 | 无 | wiki-lint 定期检查 |
| 增强机制 | 无 | 发现隐含关系 |

---

## 迁移计划

### Phase 1：并行运行（现在）
- 新资料同时存入 `KnowledgeBase/` 和 `CreditWiki/raw/`
- 我继续提供 AI 分析能力

### Phase 2：脚本化（本周）
- 完成 `wiki-compile.py` 的 AI 增强
- 实现自动问答接口

### Phase 3：智能化（下一步）
- 定时自动摄入监管政策
- 行业报告自动摘要
- 信贷决策辅助问答

---

## 使用示例

### 归档一篇行业报告
1. 发链接给我 → 我抓取并存入 `raw/行业研究/`
2. 运行 `python scripts/wiki-compile.py --all`
3. LLM 自动编译成 `wiki/articles/` 下的结构化文章
4. 自动更新 `INDEX.md` 和关联图谱

### 问一个复杂问题
1. 向我提问："票据贴现余额下降对银行有什么影响？"
2. 我搜索知识库，读取相关文档
3. 综合分析后给出带来源的回答

---

*最后更新：2026-04-20*
