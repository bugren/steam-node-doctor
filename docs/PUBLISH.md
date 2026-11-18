# 发布到 GitHub

> 你需要在 GitHub 上有账号，并且本机能通过 SSH 或 Token 推送。
> 下面以仓库名 `steam-node-doctor` 为例，可自行替换。

## 0. 先确认没有重名

GitHub 上叫 `SteamFix` 的仓库有 200 多个，建议用更具体的名字：

- `steam-node-doctor`（推荐，描述准确）
- `steam-host-fix`
- `steam-cn-netfix`

## 1. 在 GitHub 建空仓库

打开 https://github.com/new ，仓库名填 `steam-node-doctor`，
**不要**勾选 README / .gitignore / License（本地已经有了）。

## 2. 关联远程仓库

SSH 方式（推荐，需要先加 SSH key 到 GitHub）：

```bash
git remote add origin git@github.com:<你的用户名>/steam-node-doctor.git
git branch -M main
git push -u origin main
```

HTTPS + Token 方式（没有 SSH key 时）：

```bash
git remote add origin https://github.com/<你的用户名>/steam-node-doctor.git
git branch -M main
git push -u origin main
# 用户名填 GitHub 用户名，密码填 Personal Access Token（不是登录密码）
```

## 3. 打标签触发自动发版

```bash
git tag v0.1.0
git push origin v0.1.0
```

`.github/workflows/release.yml` 会自动：

1. 构建 `steamfix_0.1.0_all.deb`
2. 创建 Release 并附上 `.deb` 和 `install.sh`

## 4. 首次发布前检查清单

- [ ] `python3 -m unittest discover -s tests -v` 全绿
- [ ] `bash packaging/build-deb.sh` 能出包
- [ ] `README.md` 里的 `<你的仓库地址>` 已替换
- [ ] 没有提交个人路径、邮箱、token
- [ ] LICENSE 年份/署名确认
- [ ] 试装一次：`sudo apt install ./dist/steamfix_0.1.0_all.deb`

## 5. 常见问题

**推送被拒（Permission denied）**
说明没配 SSH key。执行 `ssh-keygen -t ed25519`，把 `~/.ssh/id_ed25519.pub`
内容贴到 GitHub → Settings → SSH and GPG keys。

**想改仓库名**
GitHub 设置里改完，本地执行：

```bash
git remote set-url origin git@github.com:<用户名>/<新名字>.git
```
