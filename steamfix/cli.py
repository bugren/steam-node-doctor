"""SteamFix 命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import __version__
from . import engine


def _print_diagnosis(d: engine.Diagnosis) -> None:
    print(f"SteamFix {__version__} · Steam 连接诊断\n")

    print("[1/4] /etc/hosts")
    if d.hosts_hijack:
        print(f"  ✘ 发现 {len(d.hosts_hijack)} 条劫持：")
        for line in d.hosts_hijack[:5]:
            print(f"      {line.strip()}")
    else:
        print("  ✔ 无劫持条目")
    print(f"  {'✔' if d.hosts_writable else '✘'} hosts 可写: {d.hosts_writable}")

    print("\n[2/4] 域名解析")
    for ip in d.system_store_ips or ["(解析失败)"]:
        print(f"  store.steampowered.com → {ip}")

    print("\n[3/4] 节点连通性（商店）")
    for p in d.store_probes:
        if p.ok:
            print(f"  ✔ {p.ip:<16} HTTP {p.code}  {p.seconds}s  ({p.source})")
        else:
            print(f"  ✘ {p.ip:<16} 不可达  ({p.source})")

    if d.community_probes:
        print("\n    社区节点")
        for p in d.community_probes[:3]:
            mark = "✔" if p.ok else "✘"
            print(f"      {mark} {p.ip:<16} " + (f"HTTP {p.code}  {p.seconds}s" if p.ok else "不可达"))

    print("\n[4/4] 结论")
    print(f"  {d.verdict}")
    for hint in d.hints:
        print(f"  · {hint}")
    if d.best_store:
        print(f"  最快节点: {d.best_store}")


def cmd_diagnose(args: argparse.Namespace) -> int:
    d = engine.diagnose()
    if args.json:
        print(json.dumps(d.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_diagnosis(d)
    return 0 if d.store_reachable else 1


def cmd_fix(args: argparse.Namespace) -> int:
    try:
        res = engine.apply_fix(store_ip=getattr(args, "store_ip", None),
                               community_ip=getattr(args, "community_ip", None))
    except PermissionError as e:
        print(f"✘ {e}", file=sys.stderr)
        print("  请用: sudo steamfix fix", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    print(f"✔ 已固定 store → {res['store_ip']}")
    if res.get("community_ip"):
        print(f"✔ 已固定 community → {res['community_ip']}")
    print(f"  备份: {res['backup']}")
    print("  请完全退出 Steam 后重新打开。")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    print(f"守夜模式：每 {args.interval} 秒检查一次，Ctrl+C 退出")
    while True:
        try:
            d = engine.diagnose()
            if d.hosts_hijack:
                print("[warn] 发现 hosts 劫持，需要 sudo steamfix fix")
            elif not d.best_store:
                print(f"[{time.strftime('%H:%M:%S')}] 全部节点不可达，等待恢复")
            elif d.pinned_store == d.best_store:
                print(f"[{time.strftime('%H:%M:%S')}] OK  {d.pinned_store}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 需要更换: {d.pinned_store or '无'} → {d.best_store}")
                if engine.hosts_writable() and args.apply:
                    engine.apply_fix()
                    print("  已自动更换")
        except KeyboardInterrupt:
            print("\n已退出")
            return 0
        time.sleep(max(10, args.interval))


def cmd_serve(args: argparse.Namespace) -> int:
    from .web import serve

    return serve(port=args.port, open_browser=args.open)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="steamfix", description="Steam 网络诊断与修复")
    p.add_argument("--version", action="version", version=f"SteamFix {__version__}")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("diagnose", help="诊断（只读）")
    d.add_argument("--json", action="store_true", help="输出 JSON")
    d.set_defaults(func=cmd_diagnose)

    f = sub.add_parser("fix", help="修复（需要 root）")
    f.add_argument("--store-ip", help="手动指定 store 节点（调试/演示用）")
    f.add_argument("--community-ip", help="手动指定 community 节点")
    f.set_defaults(func=cmd_fix)

    w = sub.add_parser("watch", help="持续监控")
    w.add_argument("--interval", type=int, default=600)
    w.add_argument("--apply", action="store_true", help="有权限时自动修复")
    w.set_defaults(func=cmd_watch)

    s = sub.add_parser("serve", help="启动本地网页界面")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--open", action="store_true", help="自动打开浏览器")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
