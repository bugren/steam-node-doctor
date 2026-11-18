#!/usr/bin/env bash
# 双击运行：启动 SteamFix 网页界面并自动打开浏览器
cd "$(dirname "$0")" || exit 1
exec python3 -m steamfix serve --open --port 8765
