#!/usr/bin/env bash
# 源码安装：把 SteamFix 装到 /usr/local（任意发行版通用）
# 用法：sudo bash install.sh
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "请用 sudo 运行：sudo bash $0" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-/usr/local}"

echo "==> 检查 Python"
python3 -c "import sys; assert sys.version_info >= (3, 9)" || { echo "需要 Python 3.9+" >&2; exit 1; }

echo "==> 安装到 $PREFIX/lib/steamfix"
rm -rf "$PREFIX/lib/steamfix"
mkdir -p "$PREFIX/lib/steamfix"
cp -r "$HERE/steamfix" "$PREFIX/lib/steamfix/"
find "$PREFIX/lib/steamfix" -name '__pycache__' -type d -prune -exec rm -rf {} +

echo "==> 写入启动器"
cat > "$PREFIX/bin/steamfix" <<WRAP
#!/bin/sh
export PYTHONPATH="$PREFIX/lib/steamfix\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m steamfix "\$@"
WRAP
chmod 0755 "$PREFIX/bin/steamfix"

echo "==> 安装桌面入口"
mkdir -p "$PREFIX/share/applications" "$PREFIX/share/icons/hicolor/scalable/apps"
cp "$HERE/packaging/steamfix.desktop" "$PREFIX/share/applications/"
cp "$HERE/packaging/steamfix.svg" "$PREFIX/share/icons/hicolor/scalable/apps/"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true

echo
echo "完成。用法："
echo "  steamfix serve --open   # 图形界面"
echo "  steamfix diagnose       # 命令行诊断"
echo "  sudo steamfix fix       # 命令行修复"
