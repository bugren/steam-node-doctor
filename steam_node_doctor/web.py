"""本地网页界面：浏览器打开 http://127.0.0.1:8765 即可使用。

不引入任何 Web 框架，只用标准库 http.server。修复按钮会通过 pkexec 提权。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, engine

_INDEX = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Steam Node Doctor · Steam 网络急救包</title>
<style>
  :root { --bg:#0f1115; --card:#181b22; --line:#2a2f3a; --text:#e6e9ef;
          --dim:#8b93a7; --ok:#3fb950; --warn:#d29922; --err:#f85149; --accent:#58a6ff; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:14px/1.6 -apple-system,"Segoe UI","Noto Sans CJK SC",sans-serif; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 32px 20px 64px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: var(--dim); margin-bottom: 24px; }
  .card { background: var(--card); border:1px solid var(--line); border-radius: 10px;
          padding: 18px; margin-bottom: 16px; }
  .row { display:flex; justify-content:space-between; gap:12px; padding:6px 0;
         border-bottom:1px dashed var(--line); }
  .row:last-child { border-bottom:none; }
  .k { color: var(--dim); }
  .ok { color: var(--ok); } .warn { color: var(--warn); } .err { color: var(--err); }
  button { background: var(--accent); color:#08111f; border:none; border-radius:8px;
           padding:10px 18px; font-size:14px; font-weight:600; cursor:pointer; }
  button.ghost { background:transparent; color:var(--accent); border:1px solid var(--accent); }
  button:disabled { opacity:.5; cursor:not-allowed; }
  .actions { display:flex; gap:10px; flex-wrap:wrap; }
  .verdict { font-size:16px; font-weight:600; }
  ul { margin:8px 0 0 18px; padding:0; color:var(--dim); }
  code { background:#0b0d12; border:1px solid var(--line); border-radius:4px; padding:1px 5px; }
  .foot { color:var(--dim); font-size:12px; margin-top:24px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Steam Node Doctor</h1>
  <div class="sub">Steam 网络急救包 · v__VERSION__ · 诊断只读，修复前自动备份</div>

  <div class="card">
    <div class="row"><span class="k">结论</span><span id="verdict" class="verdict">—</span></div>
    <div class="row"><span class="k">hosts 劫持</span><span id="hijack">—</span></div>
    <div class="row"><span class="k">系统解析</span><span id="sysip">—</span></div>
    <div class="row"><span class="k">最快节点</span><span id="best">—</span></div>
    <div class="row"><span class="k">当前固定</span><span id="pinned">—</span></div>
  </div>

  <div class="card">
    <div class="k" style="margin-bottom:8px">节点探测</div>
    <div id="probes">—</div>
  </div>

  <div class="card">
    <div class="actions">
      <button id="btn-check">重新检查</button>
      <button id="btn-fix" class="ghost">一键修复</button>
    </div>
    <ul id="hints"></ul>
  </div>

  <div class="foot">
    修复会修改 <code>/etc/hosts</code> 并自动备份为 <code>/etc/hosts.steam_node_doctor.bak</code>。
    社区域名若整段被封，仅靠 hosts 无法解决，需要代理。
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);

function cls(ok, warn) { return ok ? 'ok' : (warn ? 'warn' : 'err'); }

async function refresh() {
  const r = await fetch('/api/status');
  const d = await r.json();
  $('verdict').textContent = d.verdict;
  $('verdict').className = 'verdict ' + (d.store_reachable ? 'ok' : 'err');

  $('hijack').textContent = d.hosts_hijack.length ? d.hosts_hijack.length + ' 条' : '无';
  $('hijack').className = d.hosts_hijack.length ? 'err' : 'ok';

  $('sysip').textContent = (d.system_store_ips || ['解析失败']).join(', ');
  $('best').textContent = d.best_store || '无可用节点';
  $('best').className = d.best_store ? 'ok' : 'err';
  $('pinned').textContent = d.pinned_store || '未固定';

  const rows = d.store_probes.map(p => {
    const s = p.code ? 'HTTP ' + p.code + ' · ' + p.seconds + 's' : '不可达';
    return `<div class="row"><span class="k">${p.ip} <small>(${p.source})</small></span>
            <span class="${p.code ? 'ok' : 'err'}">${s}</span></div>`;
  }).join('');
  $('probes').innerHTML = rows || '无候选节点';

  $('hints').innerHTML = d.hints.map(h => `<li>${h}</li>`).join('');
}

async function fix() {
  $('btn-fix').disabled = true;
  $('btn-fix').textContent = '修复中…';
  try {
    const r = await fetch('/api/fix', { method: 'POST' });
    const d = await r.json();
    if (!d.ok) alert('修复失败：' + d.error);
  } catch (e) {
    alert('修复请求失败：' + e);
  } finally {
    $('btn-fix').disabled = false;
    $('btn-fix').textContent = '一键修复';
    refresh();
  }
}

$('btn-check').onclick = refresh;
$('btn-fix').onclick = fix;
refresh();
</script>
</body>
</html>
"""


def _run_fix_privileged() -> tuple[bool, str]:
    """尝试用 pkexec 提权执行修复；失败则提示。"""
    if os.geteuid() == 0:
        try:
            res = engine.apply_fix()
            return True, f"已固定 store → {res['store_ip']}"
        except Exception as e:  # noqa: BLE001
            return False, str(e)

    pkexec = shutil.which("pkexec")
    if not pkexec:
        return False, "未找到 pkexec，请在终端执行 sudo steam_node_doctor fix"

    # 优先用安装后的启动器；源码运行时退回「显式带 PYTHONPATH 的 pkexec env」
    exe = shutil.which("steam_node_doctor")
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if exe:
        cmd = [pkexec, exe, "fix"]
    else:
        cmd = [pkexec, "env", f"PYTHONPATH={pkg_root}",
               sys.executable, "-m", "steam_node_doctor", "fix"]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.SubprocessError as e:
        return False, f"提权失败: {e}"

    if p.returncode == 0:
        return True, p.stdout.strip() or "修复完成"
    if p.returncode in (126, 127):
        return False, "已取消授权"
    return False, (p.stderr or p.stdout or "未知错误").strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "Steam Node Doctor/" + __version__

    def log_message(self, fmt, *args):  # 安静一点
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = _INDEX.replace("__VERSION__", __version__).encode("utf-8")
            self._send(200, html, "text/html; charset=utf-8")
        elif self.path == "/api/status":
            try:
                d = engine.diagnose()
                body = json.dumps(d.to_dict(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            except Exception as e:  # noqa: BLE001
                self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path == "/api/fix":
            ok, msg = _run_fix_privileged()
            body = json.dumps({"ok": ok, "message": msg, "error": "" if ok else msg},
                              ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")


def serve(port: int = 8765, open_browser: bool = False) -> int:
    httpd = None
    for candidate in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        print(f"端口 {port}-{port + 9} 都被占用，请用 --port 指定其他端口", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{port}/"
    print(f"Steam Node Doctor 已启动：{url}")
    print("按 Ctrl+C 停止")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
    return 0
