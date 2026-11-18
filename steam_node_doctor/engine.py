"""Steam Node Doctor 核心引擎：诊断与修复 Steam 商店/社区连接问题。

设计原则：
- 只依赖 Python 标准库
- 诊断（diagnose）永远只读，不做任何修改
- 修复（apply_fix）需要 root，改动前自动备份，可回滚
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field

__version__ = "0.1.0"

HOSTS_PATH = os.environ.get("STEAM_NODE_DOCTOR_HOSTS") or os.environ.get("STEAMFIX_HOSTS") or "/etc/hosts"

STORE = "store.steampowered.com"
COMMUNITY = "steamcommunity.com"

# 候选节点池：DNS 只给失效 IP 时的兜底。定期用实测淘汰。
KNOWN_STORE_IPS = [
    "23.15.142.182",
    "23.41.38.92",
    "23.209.218.108",
    "23.217.70.119",
    "104.83.198.104",
    "184.28.184.117",
    "23.45.70.196",
]

# 用于多来源 DNS 交叉验证
RESOLVERS = ["223.5.5.5", "119.29.29.29", "180.76.76.76", "1.1.1.1"]

MARK_BEGIN = "# >>> steam_node_doctor managed >>>"
MARK_END = "# <<< steam_node_doctor managed <<<"

HIJACK_RE = re.compile(
    r"^\s*127\.0\.0\.1\s+.*(steampowered\.com|steamcommunity\.com|steamstatic\.com|eccdnx|akamaihd)",
    re.IGNORECASE,
)
PINNED_RE = re.compile(r"^\s*([0-9.]+)\s+(store\.steampowered\.com|steamcommunity\.com)\s*$")


@dataclass
class Probe:
    ip: str
    code: int
    seconds: float
    source: str  # "dns" / "pool" / "system"

    @property
    def ok(self) -> bool:
        return self.code not in (0,)


@dataclass
class Diagnosis:
    hosts_hijack: list[str] = field(default_factory=list)
    hosts_writable: bool = False
    pinned_store: str = ""
    pinned_community: str = ""
    system_store_ips: list[str] = field(default_factory=list)
    store_probes: list[Probe] = field(default_factory=list)
    community_probes: list[Probe] = field(default_factory=list)
    best_store: str = ""
    best_community: str = ""
    resolution_ok: bool = False
    store_reachable: bool = False
    community_reachable: bool = False
    verdict: str = ""
    hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _read_hosts() -> str:
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def scan_hosts() -> list[str]:
    """返回被劫持的行（指向 127.0.0.1 的 Steam 域名）。"""
    return [line for line in _read_hosts().splitlines() if HIJACK_RE.match(line)]


def pinned_ips() -> tuple[str, str]:
    store = community = ""
    for line in _read_hosts().splitlines():
        m = PINNED_RE.match(line)
        if not m:
            continue
        if m.group(2) == STORE:
            store = m.group(1)
        else:
            community = m.group(1)
    return store, community


def hosts_writable() -> bool:
    return os.access(HOSTS_PATH, os.W_OK)


def system_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return []
    return sorted({info[4][0] for info in infos})


def _dig_one(host: str, resolver: str) -> list[str]:
    try:
        p = subprocess.run(
            ["dig", "@" + resolver, "+short", "+time=2", "+tries=1", "A", host],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in p.stdout.splitlines()
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", line.strip())]


def dig_ips(host: str, resolvers: list[str] | None = None) -> list[str]:
    """用 dig 从多个 DNS 拿 IP（并发），做交叉验证。没有 dig 就退化为系统解析。"""
    resolvers = resolvers or RESOLVERS
    found: set[str] = set()
    with ThreadPoolExecutor(max_workers=len(resolvers)) as pool:
        for ips in pool.map(lambda r: _dig_one(host, r), resolvers):
            found.update(ips)
    return sorted(found)


def probe(host: str, ip: str, timeout: float = 3.0) -> tuple[int, float]:
    """直连 IP、带正确 SNI/Host 做一次 HTTPS 请求，返回 (状态码, 首字节秒数)。"""
    ctx = ssl.create_default_context()
    started = time.monotonic()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                req = (
                    f"GET / HTTP/1.1\r\nHost: {host}\r\n"
                    "User-Agent: steam_node_doctor/0.1\r\nConnection: close\r\n\r\n"
                )
                tls.sendall(req.encode())
                head = tls.recv(64)
        m = re.match(rb"HTTP/\d\.\d (\d{3})", head)
        return (int(m.group(1)) if m else 0), round(time.monotonic() - started, 3)
    except (OSError, ssl.SSLError, ValueError):
        return 0, 0.0


def candidates_for(host: str) -> list[tuple[str, str]]:
    """(ip, 来源) 列表，去重。"""
    seen: dict[str, str] = {}
    for ip in system_ips(host):
        seen.setdefault(ip, "system")
    for ip in dig_ips(host):
        seen.setdefault(ip, "dns")
    if host == STORE:
        for ip in KNOWN_STORE_IPS:
            seen.setdefault(ip, "pool")
    return [(ip, src) for ip, src in seen.items()]


def probe_all(host: str, timeout: float = 3.0, retries: int = 1,
              limit: int | None = None, workers: int = 5) -> list[Probe]:
    cands = candidates_for(host)
    if limit:
        cands = cands[:limit]
    if not cands:
        return []

    from concurrent.futures import wait  # 局部导入，避免顶部再改

    pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(cands))))
    futures = {pool.submit(probe, host, ip, timeout): (ip, src) for ip, src in cands}
    deadline = timeout * 2 + 1.5
    done, pending = wait(futures, timeout=deadline)

    out: list[Probe] = []
    retry_list: list[tuple[str, str]] = []
    for fut in done:
        ip, src = futures[fut]
        try:
            code, secs = fut.result()
        except Exception:
            code, secs = 0, 0.0
        if code == 0 and retries > 0:
            retry_list.append((ip, src))
        out.append(Probe(ip=ip, code=code, seconds=secs, source=src))

    # 超时未完成的直接判失败，不再等它们
    for fut in pending:
        ip, src = futures[fut]
        out.append(Probe(ip=ip, code=0, seconds=0.0, source=src))
    pool.shutdown(wait=False, cancel_futures=True)

    # 对第一次失败的做一次快速重试（最多 3 个，避免拖慢）
    for ip, src in retry_list[:3]:
        code, secs = probe(host, ip, min(2.0, timeout))
        for p in out:
            if p.ip == ip and p.source == src:
                p.code, p.seconds = code, secs
                break

    out.sort(key=lambda p: (not p.ok, p.seconds))
    return out


def best_of(probes: list[Probe]) -> str:
    ok = [p for p in probes if p.ok]
    return min(ok, key=lambda p: p.seconds).ip if ok else ""


def diagnose() -> Diagnosis:
    pinned_store, pinned_comm = pinned_ips()

    # 快路径：固定的 IP 还活着，1 秒内给出结论，不必全量探测
    if pinned_store and not scan_hosts():
        code, secs = probe(STORE, pinned_store, timeout=3.0)
        if code:
            store_probes = [Probe(ip=pinned_store, code=code, seconds=secs, source="pinned")]
            comm_probes = []
            d = Diagnosis(
                hosts_hijack=[], hosts_writable=hosts_writable(),
                pinned_store=pinned_store, pinned_community=pinned_comm,
                system_store_ips=system_ips(STORE),
                store_probes=store_probes, community_probes=comm_probes,
                best_store=pinned_store, best_community="",
                store_reachable=True, community_reachable=False,
                verdict="正常",
                hints=[f"当前固定的 {pinned_store} 可用（快速检查）"],
            )
            return d

    store_probes = probe_all(STORE, timeout=2.5, retries=1, limit=6, workers=6)
    # 社区常年整段被封，只抽 3 个探一下，避免拖慢整个诊断
    comm_probes = probe_all(COMMUNITY, timeout=2.0, retries=0, limit=2, workers=2)
    pinned_store, pinned_comm = pinned_ips()

    d = Diagnosis(
        hosts_hijack=scan_hosts(),
        hosts_writable=hosts_writable(),
        pinned_store=pinned_store,
        pinned_community=pinned_comm,
        system_store_ips=system_ips(STORE),
        store_probes=store_probes,
        community_probes=comm_probes,
        best_store=best_of(store_probes),
        best_community=best_of(comm_probes),
        store_reachable=bool(best_of(store_probes)),
        community_reachable=bool(best_of(comm_probes)),
    )

    ok_ips = {p.ip for p in store_probes if p.ok}
    pinned_ok = bool(d.pinned_store) and d.pinned_store in ok_ips

    if d.hosts_hijack:
        d.verdict = "hosts 被劫持"
        d.hints.append("发现 hosts 里有 Steam 域名指向 127.0.0.1，这是 -102 的典型原因")
    elif not d.system_store_ips:
        d.verdict = "域名解析失败"
        d.hints.append("系统无法解析 store.steampowered.com，检查 DNS 配置")
    elif not d.store_reachable:
        d.verdict = "节点不可达"
        d.hints.append("所有候选节点都被拦截：可能是运营商 IP 段封锁，需要代理")
    elif pinned_ok:
        d.verdict = "正常"
        d.hints.append(f"当前固定的 {d.pinned_store} 可用")
        if d.best_store and d.best_store != d.pinned_store:
            d.hints.append(f"另有更快的节点 {d.best_store}（可选优化，不必改）")
    elif d.pinned_store:
        d.verdict = "节点已失效"
        d.hints.append(f"当前固定的 {d.pinned_store} 已不可用，建议改为 {d.best_store}")
    else:
        d.verdict = "未固定节点"
        d.hints.append(f"没有手动固定 IP，建议固定到 {d.best_store}")

    if not d.community_reachable:
        d.hints.append("社区域名整段被封，需要代理；这不影响登录、游戏库和下载")
    return d


def _strip_managed_block(text: str) -> str:
    lines = text.splitlines()
    out, skipping = [], False
    for line in lines:
        if line.strip() == MARK_BEGIN:
            skipping = True
            continue
        if line.strip() == MARK_END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def apply_fix(store_ip: str | None = None, community_ip: str | None = None) -> dict:
    """写入 hosts。需要 root。返回操作摘要。"""
    # 只有改真正的 /etc/hosts 才强制 root；测试用的副本允许直接写
    if os.geteuid() != 0 and os.path.abspath(HOSTS_PATH) == "/etc/hosts":
        raise PermissionError("需要 root 权限才能修改 " + HOSTS_PATH)

    # 只有没指定 store 节点时才需要联网探测
    if not store_ip:
        d = diagnose()
        store_ip = d.best_store
        community_ip = community_ip or d.best_community
    if not store_ip:
        raise RuntimeError("没有找到可达的 store 节点，拒绝写入无效 IP")

    before_hijack = len(scan_hosts())
    original = _read_hosts()
    backup = HOSTS_PATH + ".steam_node_doctor.bak"
    if not os.path.exists(backup):
        shutil.copy2(HOSTS_PATH, backup)

    cleaned = "\n".join(
        line for line in _strip_managed_block(original).splitlines()
        if not HIJACK_RE.match(line) and not PINNED_RE.match(line)
    ).rstrip("\n") + "\n"

    block = [MARK_BEGIN, f"{store_ip} {STORE}"]
    if community_ip:
        block.append(f"{community_ip} {COMMUNITY}")
    block.append(MARK_END)
    new_text = cleaned + "\n".join(block) + "\n"

    fd, tmp = tempfile.mkstemp(prefix=".hosts.", dir=os.path.dirname(os.path.abspath(HOSTS_PATH)) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
        shutil.copymode(HOSTS_PATH, tmp)
        os.replace(tmp, HOSTS_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    try:
        subprocess.run(["resolvectl", "flush-caches"], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass

    return {
        "store_ip": store_ip,
        "community_ip": community_ip,
        "removed_hijack": before_hijack,
        "backup": backup,
    }


def run_as_root_cli_fix() -> int:
    """在需要提权的场合调用自己（供 GUI 通过 pkexec 调用）。"""
    try:
        res = apply_fix()
    except (PermissionError, RuntimeError) as e:
        print(f"修复失败: {e}", flush=True)
        return 1
    print(f"已固定 store → {res['store_ip']}", flush=True)
    if res.get("community_ip"):
        print(f"已固定 community → {res['community_ip']}", flush=True)
    print(f"备份: {res['backup']}", flush=True)
    return 0
