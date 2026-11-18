# SteamFix · Steam 网络急救包

诊断并修复 Linux 上 Steam 商店打不开、报错 **-102 / -118**、商店页面一直转圈的问题。

> 一句话原理：Steam 商店走的是 Akamai/Fastly 的 CDN 节点，某些网络会把部分节点整段拦掉；
> 而 DNS 往往只给你**一个已经失效的 IP**。SteamFix 会实测所有候选节点，把可用的那个写进
> `/etc/hosts`，改前自动备份、改后可回滚。

## 功能

- **诊断**：检查 `/etc/hosts` 劫持、系统解析结果、逐个节点实测（TCP + TLS 握手），给出结论
- **修复**：自动挑选最快的可达节点并写入 hosts，操作前备份
- **网页界面**：本地起一个页面，点按钮就行，不用记命令
- **命令行**：适合脚本化和远程使用
- **零第三方依赖**：只用 Python 标准库

## 界面

浏览器打开 `http://127.0.0.1:8765`，看到的是：

```text
┌────────────────────────────────────────────┐
│ SteamFix                                   │
│ Steam 网络急救包 · v0.1.0                    │
├────────────────────────────────────────────┤
│ 结论          节点已失效                     │
│ hosts 劫持    无                            │
│ 系统解析      104.83.198.104                │
│ 最快节点      23.15.142.182                 │
│ 当前固定      104.83.198.104                │
├────────────────────────────────────────────┤
│ [重新检查]  [一键修复]                       │
└────────────────────────────────────────────┘
```

## 安装

### 方式一：.deb（Debian / Ubuntu）

```bash
wget https://example.com/steamfix_0.1.0_all.deb
sudo apt install ./steamfix_0.1.0_all.deb
```

安装后应用菜单里会出现「Steam 急救包」。

### 方式二：从源码（任意发行版）

```bash
git clone https://example.com/steamfix.git
cd steamfix
sudo bash install.sh
```

### 方式三：不安装，直接跑

```bash
python3 -m steamfix serve --open
```

## 使用

### 图形界面

```bash
steamfix serve --open
```

浏览器会自动打开，点「重新检查」看诊断结果，点「一键修复」写入 hosts（会弹出系统密码框）。

### 命令行

```bash
steamfix diagnose          # 诊断，只读，不修改任何东西
steamfix diagnose --json   # 机器可读输出
sudo steamfix fix          # 修复：备份 hosts + 固定最快节点
steamfix watch             # 每 10 分钟检查一次
sudo steamfix watch --apply  # 自动修复模式
```

## 它到底改了什么

修复时只会往 `/etc/hosts` 写入一段带标记的区块：

```text
# >>> steamfix managed >>>
23.15.142.182 store.steampowered.com
# <<< steamfix managed <<<
```

- 首次修复会生成备份 `/etc/hosts.steamfix.bak`
- 重复修复会替换整个区块，不会越积越多
- 卸载后这段标记也可以手动删掉

## 已知限制（请一定看）

1. **社区域名（steamcommunity.com）不保证可用**。它常年被整段封锁，换 IP 也没用，需要代理。
   这不影响 Steam 登录、游戏库和游戏下载。
2. **节点 IP 会轮换**。Akamai 会回收节点，用着用着可能又失效，重新点一次「修复」即可；
   或者用 `watch` 让它自动换。
3. **整段网络封锁时无解**。如果所有候选节点都不可达，说明是网络层封锁，工具不会硬写无效 IP，
   会明确告诉你「需要代理」。
4. **需要 root 才能改 hosts**。诊断不需要，修复会通过 `pkexec` 弹窗提权。

## 开发

```bash
python3 -m steamfix diagnose     # 冒烟测试
python3 -m compileall steamfix   # 语法检查
bash packaging/build-deb.sh      # 构建 .deb（输出到 dist/）
```

目录结构：

```
steamfix/
├── steamfix/
│   ├── engine.py    # 核心：解析、探测、选节点、改 hosts
│   ├── cli.py       # 命令行
│   ├── web.py       # 本地网页界面
│   └── __main__.py
├── packaging/       # .deb 构建、桌面图标
└── install.sh       # 源码安装脚本
```

## 免责声明

本工具只修改本机 `/etc/hosts`，不修改 Steam 客户端文件，不绕过任何付费或 DRM。
它解决的是「域名解析到失效节点」这类网络问题，对「内容本身无法访问」无能为力。

## License

MIT
