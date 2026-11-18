#!/usr/bin/env bash
# 构建 .deb 安装包（无需 root）
# 用法：bash packaging/build-deb.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c "import sys; sys.path.insert(0, '$ROOT'); import steamfix; print(steamfix.__version__)")"
PKG="steamfix"
ARCH="all"
OUT="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

DEST="$STAGE/${PKG}_${VERSION}_${ARCH}"
mkdir -p "$DEST/DEBIAN" \
         "$DEST/usr/lib/steamfix" \
         "$DEST/usr/bin" \
         "$DEST/usr/share/applications" \
         "$DEST/usr/share/icons/hicolor/scalable/apps" \
         "$DEST/usr/share/doc/steamfix"

echo "==> 复制代码"
cp -r "$ROOT/steamfix" "$DEST/usr/lib/steamfix/"
find "$DEST/usr/lib/steamfix" -name '__pycache__' -type d -prune -exec rm -rf {} +
cp "$ROOT/README.md" "$ROOT/LICENSE" "$DEST/usr/share/doc/steamfix/"

echo "==> 生成启动器"
cat > "$DEST/usr/bin/steamfix" <<'WRAP'
#!/bin/sh
export PYTHONPATH="/usr/lib/steamfix${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m steamfix "$@"
WRAP
chmod 0755 "$DEST/usr/bin/steamfix"

cp "$ROOT/packaging/steamfix.desktop" "$DEST/usr/share/applications/"
cp "$ROOT/packaging/steamfix.svg" "$DEST/usr/share/icons/hicolor/scalable/apps/steamfix.svg"

echo "==> 写控制文件"
INSTALLED_SIZE="$(du -sk "$DEST/usr" | cut -f1)"
cat > "$DEST/DEBIAN/control" <<CTRL
Package: ${PKG}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: SteamFix contributors <noreply@example.com>
Depends: python3 (>= 3.9)
Recommends: dnsutils
Description: Steam network diagnostic and repair tool
 Diagnoses and fixes Steam store connection failures on Linux:
 hosts hijacking, stale DNS answers and unreachable CDN nodes.
 It backs up /etc/hosts before changing anything and can pin the
 fastest reachable node automatically.
CTRL

cat > "$DEST/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q || true
fi
exit 0
POST
chmod 0755 "$DEST/DEBIAN/postinst"

echo "==> 修正权限"
find "$DEST/usr" -type d -exec chmod 0755 {} +
find "$DEST/usr" -type f -exec chmod 0644 {} +
chmod 0755 "$DEST/usr/bin/steamfix"
chmod 0755 "$DEST/DEBIAN/postinst"

mkdir -p "$OUT"
echo "==> 打包"
dpkg-deb --root-owner-group -Zxz --build "$DEST" "$OUT/${PKG}_${VERSION}_${ARCH}.deb" >/dev/null

echo
echo "生成: $OUT/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb -I "$OUT/${PKG}_${VERSION}_${ARCH}.deb" | sed -n '1,12p'
