#!/bin/bash
# CreditWiki 同步脚本
# 用法: ./sync.sh

cd /Users/bismarck/KnowledgeBase/CreditWiki

echo "📂 CreditWiki 同步中..."

# 添加所有更改
git add -A

# 检查是否有更改
if git diff --cached --quiet; then
    echo "✅ 没有新更改"
    exit 0
fi

# 提交
git commit -m "更新: $(date '+%Y-%m-%d %H:%M')"

# 推送到远程（如果远程已配置）
REMOTE=$(git remote)
if [ -n "$REMOTE" ]; then
    git push -u $REMOTE main
    echo "✅ 已推送到 $REMOTE"
else
    echo "⚠️ 暂无远程仓库配置"
fi

echo "✅ 同步完成"
