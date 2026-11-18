# Changelog

## Unreleased

- hosts 标记块改为 `steam-node-doctor`，并兼容清理旧版本写入的标记
- 备份文件名改为 `/etc/hosts.steam-node-doctor.bak`
- 端口 8765 被占用时自动向后寻找可用端口
- 版本号改为单一来源（`pyproject.toml` 从包读取）
- 新增：卸载说明、常见问题、Issue 模板、CONTRIBUTING

## 0.1.0 — 2026-11-18

首个可用版本。

### 功能
- 诊断：hosts 劫持检测、系统解析、多 DNS 交叉验证、节点实测（TCP + TLS）
- 修复：自动挑选最快可达节点写入 `/etc/hosts`，带标记块、自动备份、幂等
- 界面：本地网页（`steam-node-doctor serve`），一键修复走 `pkexec` 提权
- 命令行：`diagnose` / `fix` / `watch` / `serve`
- 打包：`.deb`、`install.sh`、GitHub Actions 自动发版

### 已知限制
- 社区域名整段被封时无法修复（需要代理）
- 节点 IP 会轮换，失效后需重新修复
- 仅支持 Linux

### 修复
- 探测失败增加重试，避免网络抖动导致假阴性
- 固定的 IP 可用时判定为「正常」，不再误报失效
- 探测增加总时限，避免单个节点拖住整个诊断
