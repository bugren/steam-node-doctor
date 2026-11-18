# Steam Node Doctor · Steam 网络急救包

[![Release](https://img.shields.io/github/v/release/bugren/steam-node-doctor)](https://github.com/bugren/steam-node-doctor/releases)
[![CI](https://github.com/bugren/steam-node-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/bugren/steam-node-doctor/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Linux 上 Steam 商店打不开、报错 **-102 / -118**、商店页一直转圈时，用来快速定位并修复的小工具。

> **适用范围先说清楚**：它解决的是「DNS 给了一个失效的 CDN 节点」这一类问题。
> 如果整个 IP 段被封，它不会硬改，会明确告诉你需要代理。
> 社群（创意工坊、个人资料）常年不可直连，本工具不处理。

## 它怎么工作

```text
DNS 查到的 IP  →  逐个实测（TCP + TLS 握手）  →  挑最快可达的  →  写进 /etc/hosts
```

`/etc/hosts` 的优先级高于 DNS，所以写进去之后就固定走那个节点。
修复前自动备份，写入的内容带标记块，卸载时可以直接删掉。

## 功能

- **诊断**（只读）：hosts 劫持、系统解析、多 DNS 交叉验证、逐个节点实测
- **修复**：自动挑最快节点写入 hosts，备份 + 标记块 + 幂等（重复修复不会累积）
- **网页界面**：本地起一个页面，点按钮就行
- **命令行**：`diagnose` / `fix` / `watch` / `serve`
- **零第三方依赖**：只用 Python 标准库

## 适用 / 不适用

| 情况 | 表现 | 能不能治 |
|---|---|---|
| `/etc/hosts` 被改、Steam 域名指向 127.0.0.1 | 报错 -102 | ✅ 能 |
| DNS 返回失效 IP，但其他节点可达 | 商店白屏、转圈 | ✅ 能 |
| 节点轮换导致昨天能用今天失效 | 时好时坏 | ✅ 能（重新修复） |
| 整个 IP 段被运营商封锁 | 全部节点不可达 | ⚠️ 不能，需要代理 |
| 社群 / 创意工坊 | 打不开 | ❌ 不能，需要代理 |

## 安装

### 方式一：.deb（Debian / Ubuntu）

```bash
sudo apt install ./steam-node-doctor_0.1.1_all.deb
```

安装后应用菜单出现「Steam 急救包」。

### 方式二：源码

```bash
git clone <你的仓库地址> steam-node-doctor
cd steam-node-doctor
sudo bash install.sh     # 装到 /usr/local
# 或者不安装，直接运行：
python3 -m steam_node_doctor serve --open
```

## 使用

### 图形界面

```bash
steam-node-doctor serve --open
```

浏览器打开后：

1. 点「重新检查」看诊断结果
2. 结论为「节点已失效」时点「一键修复」（会弹系统密码框）
3. 完全退出 Steam 后重新打开

### 命令行

```bash
steam-node-doctor diagnose            # 诊断，只读
steam-node-doctor diagnose --json     # 机器可读
sudo steam-node-doctor fix            # 修复
steam-node-doctor watch               # 每 10 分钟检查一次
sudo steam-node-doctor watch --apply  # 自动修复
```

## 卸载

```bash
# deb 安装的
sudo apt remove steam-node-doctor

# 源码安装的
sudo rm -rf /usr/local/lib/steam-node-doctor /usr/local/bin/steam-node-doctor
sudo rm -f /usr/local/share/applications/steam-node-doctor.desktop
```

然后清理 `/etc/hosts` 里的标记块（二选一）：

```bash
# 方式一：删掉标记块
sudo sed -i '/# >>> steam-node-doctor managed >>>/,/# <<< steam-node-doctor managed <<</d' /etc/hosts

# 方式二：直接恢复首次修复时的备份
sudo cp /etc/hosts.steam-node-doctor.bak /etc/hosts
```

## 常见问题

**Q：修复完商店还是打不开？**
先完全退出 Steam 再重开；然后重新点「诊断」，看结论是「正常」还是「节点不可达」。
如果是「正常」但页面仍白屏，试试 Ctrl+F5 强制刷新（webhelper 有缓存）。

**Q：提示「所有候选节点都被拦截」？**
说明网络层把整段 IP 封了，工具不会写无效 IP。这种情况只能等封锁解除或使用代理，
换 DNS、改 hosts 都无效。

**Q：提示「hosts 可写: False」？**
诊断不需要 root，但修复需要。命令行用 `sudo steam-node-doctor fix`，
桌面界面点「一键修复」会弹系统密码框。

**Q：会不会把系统改坏？**
只修改 `/etc/hosts` 这一个文件，且：
首次修复前备份为 `/etc/hosts.steam-node-doctor.bak`；
写入内容带标记块，可整段删除；
重复修复是幂等的，不会越积越多。

**Q：社区域名（创意工坊、个人资料）为什么修不好？**
它和商店不是一组节点，常年被整段封锁，换 IP 无效。这不影响登录、游戏库和下载。

**Q：支持哪些发行版？**
目前只在 Ubuntu 24.04 + X11 上实测过。Debian 系理论上都能用；
其他发行版可以用源码安装（`install.sh`），但没有验证。

## 安全说明

- 只修改本机 `/etc/hosts`，不改 Steam 客户端文件
- 首次修复生成备份 `/etc/hosts.steam-node-doctor.bak`
- 写入内容带 `# >>> steam-node-doctor managed >>>` 标记，可手动整段删除
- 诊断模式完全只读，不需要 root
- 修复需要 root，桌面环境下通过 `pkexec` 弹密码框

## 已知限制

1. **社区域名不保证可用**：`steamcommunity.com` 常年被整段封锁，换 IP 无效。不影响登录、游戏库和下载。
2. **节点 IP 会轮换**：Akamai 回收节点后需要重新修复，或启用 `watch`。
3. **只支持 Linux**：Windows 版未实现。
4. **仅在 Ubuntu 24.04 + X11 上实测过**，其他发行版理论上可用但未验证。

## 开发

```bash
python3 -m unittest discover -s tests -v   # 单元测试
python3 -m compileall steam-node-doctor             # 语法检查
bash packaging/build-deb.sh                # 构建 .deb
```

目录：

```text
steam-node-doctor/
├── steam-node-doctor/
│   ├── engine.py    # 核心：解析、探测、选节点、写 hosts
│   ├── cli.py       # 命令行
│   └── web.py       # 本地网页界面
├── tests/           # 单元测试（不联网）
├── packaging/       # .deb 构建、桌面入口、图标
└── install.sh
```

## 发布新版本

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions 会自动构建 `.deb` 并创建 Release。

## License

MIT
