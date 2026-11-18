#!/usr/bin/env bash
# 源码安装：把 Steam Node Doctor 装到 /usr/local（任意发行版通用）
# 用法：sudo bash install.sh
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "请用 sudo 运行：sudo bash $0" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-/usr/local}"

echo "==> 检查 Python"
python3 -c "import sys; assert sys.version_info >= (3, 9)" || { echo "需要 Python 3.9+" >&2; exit 1; }

echo "==> 安装到 $PREFIX/lib/steam-node-doctor"
rm -rf "$PREFIX/lib/steam-node-doctor"
mkdir -p "$PREFIX/lib/steam-node-doctor"
cp -r "$HERE/steam_node_doctor" "$PREFIX/lib/steam-node-doctor/"
find "$PREFIX/lib/steam-node-doctor" -name '__pycache__' -type d -prune -exec rm -rf {} +

echo "==> 写入启动器"
cat > "$PREFIX/bin/steam-node-doctor" <<WRAP
#!/bin/sh
export PYTHONPATH="$PREFIX/lib/steam-node-doctor\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m steam_node_doctor "\$@"
WRAP
chmod 0755 "$PREFIX/bin/steam-node-doctor"

echo "==> 安装桌面入口"
mkdir -p "$PREFIX/share/applications" "$PREFIX/share/icons/hicolor/scalable/apps"
cp "$HERE/packaging/steam-node-doctor.desktop" "$PREFIX/share/applications/"
cp "$HERE/packaging/steam-node-doctor.svg" "$PREFIX/share/icons/hicolor/scalable/apps/"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true

echo
echo "完成。用法："
echo "  steam-node-doctor serve --open   # 图形界面"
echo "  steam-node-doctor diagnose       # 命令行诊断"
echo "  sudo steam-node-doctor fix       # 命令行修复"
