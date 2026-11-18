#!/usr/bin/env bash
# 辅助发布：检查 → 建 tag → 推送（需要先配好 remote 和凭据）
set -euo pipefail
cd "$(dirname "$0")"

VERSION="$(python3 -c "import steam_node_doctor; print(steam_node_doctor.__version__)")"
TAG="v${VERSION}"

echo "==> 1/4 单元测试"
python3 -m unittest discover -s tests -q

echo "==> 2/4 构建 .deb"
bash packaging/build-deb.sh >/dev/null
echo "    dist/steam-node-doctor_${VERSION}_all.deb"

echo "==> 3/4 检查工作区"
if [ -n "$(git status --porcelain)" ]; then
  echo "工作区不干净，请先提交："
  git status --short
  exit 1
fi

echo "==> 4/4 推送 main 与 tag ${TAG}"
git branch -M main
git push -u origin main
git tag -f "$TAG"
git push -f origin "$TAG"

echo
echo "完成。GitHub Actions 会构建并发布 Release。"
