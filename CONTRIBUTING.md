# 参与开发

## 环境

- Python 3.9+
- 不需要任何第三方依赖

## 跑测试

```bash
python3 -m unittest discover -s tests -v
```

测试全部基于临时 hosts 文件，**不联网**、不需要 root。

## 本地运行

```bash
python3 -m steam_node_doctor diagnose      # 诊断
python3 -m steam_node_doctor serve --open  # 网页界面
```

## 构建 .deb

```bash
bash packaging/build-deb.sh   # 输出到 dist/
```

## 提交前检查

- [ ] `python3 -m unittest discover -s tests` 通过
- [ ] `python3 -m compileall steam_node_doctor` 无报错
- [ ] `bash packaging/build-deb.sh` 能出包
- [ ] 改动涉及 hosts 写入时，确认仍会备份且幂等

## 代码约定

- 只用 Python 标准库，不引入依赖
- 诊断路径必须**只读**
- 任何写入 `/etc/hosts` 的操作都要：先备份、带标记块、可重复执行
- 提交信息用中文或英文均可，但要说清「为什么改」
