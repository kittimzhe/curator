#!/usr/bin/env bash
# Curator 一键发布:用 PAT 建仓 + 推送 + 验证
# 用法: CURATOR_GH_TOKEN=ghp_xxx bash scripts/push_with_token.sh [repo名] [用户名]
set -euo pipefail

TOKEN="${CURATOR_GH_TOKEN:?需要环境变量 CURATOR_GH_TOKEN=ghp_xxx}"
REPO="${1:-curator}"
USER="${2:-kittimzhe}"
cd "$(dirname "$0")/.."

echo "▶ 1/4 检查 token 身份..."
LOGIN=$(curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/user | python3 -c 'import json,sys; print(json.load(sys.stdin).get("login",""))')
[ "$LOGIN" = "$USER" ] || { echo "✗ token 属于 '$LOGIN',不是 $USER"; exit 1; }
echo "  ✓ token 属于 $LOGIN"

echo "▶ 2/4 创建仓库 $USER/$REPO (public)..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO\",\"description\":\"🏛️ 给你的数字大脑雇一队 AI 图书管理员 — 可见 multi-agent 流水线的个人知识工作台\",\"public\":true}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  ✓", d.get("html_url") or d.get("message"))'

echo "▶ 3/4 推送..."
git remote remove origin 2>/dev/null || true
git remote add origin "https://$USER:$TOKEN@github.com/$USER/$REPO.git"
git push -u origin HEAD:main 2>&1 | sed "s/$TOKEN/****/g"

echo "▶ 4/4 清理 token 并验证远端..."
git remote set-url origin "https://github.com/$USER/$REPO.git"   # 从 remote 配置抹掉 token
curl -s -o /dev/null -w "  远端 HTTP %{http_code}\n" "https://github.com/$USER/$REPO"
git log --oneline -1
echo "✅ 发布完成: https://github.com/$USER/$REPO"
