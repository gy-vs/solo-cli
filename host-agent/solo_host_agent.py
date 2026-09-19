#!/usr/bin/env python3
"""宿主机执行代理：替容器里的后端在这台 Mac 上干两件事——把项目跑起来、把屏幕录下来。

为什么非要有这么个东西：后端跑在 Linux 容器里，工作目录虽然挂进去了，但在那儿执行
命令用的是容器的 Node/Python/系统依赖，屏幕上也不会有终端窗口；屏幕录制更是 macOS
按「发起进程所属 App」授权的系统权限，容器根本拿不到。所以录屏交付这一段必须由一个
你亲手启动过、授过权的宿主机进程来接活。

只用标准库，不装任何依赖。启动：

    python3 solo_host_agent.py            # 或双击同目录的「启动宿主机代理.command」

首次启动会在 <仓库>/data/host-agent/token 生成一个随机口令，后端通过挂载的 /data
读到它。监听 0.0.0.0 是因为容器访问宿主只能走 host.docker.internal 那个网关地址，
127.0.0.1 到不了；所以每个接口都强制校验口令，且工作目录必须落在 CODER_ROOT 之内。
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "1.0.0"
DEFAULT_PORT = 8790
REPO_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = REPO_ROOT / "data" / "host-agent" / "token"

# 录屏参数。高度锁 720、宽度按屏幕比例取偶数，避免把画面拉变形。
RECORD_HEIGHT = 720
RECORD_FPS = 30
# 等第一帧的耐心。授过权的话半秒就有，等这么久是留给系统弹授权对话框的时间。
PERMISSION_WAIT_SECONDS = 6
PERMISSION_HINT = (
    "ffmpeg 起来了但一帧都录不到，基本可以断定是屏幕录制权限没给这个进程。"
    "打开「系统设置 → 隐私与安全性 → 屏幕录制」，把启动本代理的那个 App（双击 .command "
    "启动的话就是「终端」）勾上，然后回到代理窗口 Ctrl+C 重跑一次"
)

# 这些命令自动替你执行：装依赖是纯等待，没有演示价值，录屏时先跑完省得干等。
# 其余命令（跑测试、演示脚本）只预置到终端历史里，按上箭头调出来，自己掌握节奏。
AUTO_RUN_PATTERNS = [
    r"^\s*(npm|pnpm|yarn|bun)\s+(ci|install|i)\b",
    r"^\s*(pip3?|python3?\s+-m\s+pip)\s+install\b",
    r"^\s*python3?\s+-m\s+venv\b",
    r"^\s*(poetry|bundle|composer)\s+install\b",
    r"^\s*go\s+mod\s+(download|tidy)\b",
    r"^\s*cargo\s+(fetch|build)\b",
]


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def coder_root() -> str:
    """工作目录白名单的根。优先环境变量，否则从仓库 .env 里读 CODER_ROOT。"""
    v = os.environ.get("CODER_ROOT", "").strip()
    if v:
        return str(Path(v).resolve())
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text("utf-8", "replace").splitlines():
            if line.strip().startswith("CODER_ROOT="):
                return str(Path(line.split("=", 1)[1].strip()).resolve())
    return str(Path.home())


def ensure_token() -> str:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        tok = TOKEN_FILE.read_text("utf-8").strip()
        if tok:
            return tok
    tok = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(tok, "utf-8")
    TOKEN_FILE.chmod(0o600)
    return tok


# ---------------- 屏幕与录制 ----------------

def ffmpeg_bin() -> str | None:
    for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"):
        try:
            if subprocess.run([p, "-version"], capture_output=True, timeout=10).returncode == 0:
                return p
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def list_screens(ff: str) -> list[dict]:
    """列出可录的屏幕。

    avfoundation 的设备号是摄像头和屏幕混编的（0 往往是 FaceTime 摄像头），
    直接把「screen 0」当 -i 的下标会录到自己的脸，所以必须解析真实索引。
    """
    r = subprocess.run([ff, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                       capture_output=True, text=True, timeout=20)
    out = r.stderr or r.stdout
    screens = []
    for m in re.finditer(r"\[(\d+)\]\s+(Capture screen \d+)", out):
        screens.append({"index": int(m.group(1)), "label": m.group(2)})
    return screens


class Recording:
    """一次录制。停止靠往 ffmpeg 的 stdin 写 q，让它自己收尾写完 moov；kill 会留下坏文件。"""

    def __init__(self, rec_id: str, task_no: str, side: str, path: Path, proc: subprocess.Popen):
        self.id = rec_id
        self.task_no = task_no
        self.side = side
        self.path = path
        self.proc = proc
        self.started_at = time.time()
        self.stderr_tail: list[str] = []
        # 屏幕录制权限没给时 ffmpeg 是卡在打开设备上、不是退出，光看进程活着会误判成
        # 「录上了」，实际一帧都没有。所以以它自己报出第一帧为准。
        self.first_frame = threading.Event()
        threading.Thread(target=self._drain, daemon=True).start()
        threading.Thread(target=self._watch_progress, daemon=True).start()

    def _drain(self) -> None:
        for raw in iter(self.proc.stderr.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self.stderr_tail.append(line)
                del self.stderr_tail[:-40]

    def _watch_progress(self) -> None:
        for raw in iter(self.proc.stdout.readline, b""):
            if raw.startswith(b"frame=") and raw.strip() != b"frame=0":
                self.first_frame.set()

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def brief(self) -> dict:
        return {
            "id": self.id, "task_no": self.task_no, "side": self.side,
            "file": str(self.path), "seconds": round(time.time() - self.started_at, 1),
            "alive": self.alive,
        }

    def stop(self, timeout: float = 15) -> dict:
        if self.alive:
            try:
                self.proc.stdin.write(b"q")
                self.proc.stdin.flush()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.send_signal(signal.SIGINT)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        size = self.path.stat().st_size if self.path.exists() else 0
        return {
            "ok": size > 0, "file": str(self.path), "size": size,
            "seconds": round(time.time() - self.started_at, 1),
            "message": "录屏已保存" if size > 0 else "录屏没产出文件：" + " / ".join(self.stderr_tail[-3:]),
        }


RECORDINGS: dict[str, Recording] = {}
REC_LOCK = threading.Lock()


def start_record(task_no: str, side: str, out_dir: Path, screen_index: int) -> dict:
    ff = ffmpeg_bin()
    if not ff:
        return {"ok": False, "message": "找不到 ffmpeg，先 brew install ffmpeg"}
    # 设备号是摄像头和屏幕混编的，没指定或指了个不是屏幕的下标就退回第一块屏，
    # 否则一不留神录的就是摄像头里的自己
    screens = list_screens(ff)
    if not screens:
        return {"ok": False, "message": "ffmpeg 列不出可录的屏幕，检查屏幕录制权限"}
    if screen_index not in {s["index"] for s in screens}:
        screen_index = screens[0]["index"]
    with REC_LOCK:
        for rec in RECORDINGS.values():
            if rec.alive and rec.task_no == task_no and rec.side == side:
                return {"ok": False, "message": f"{task_no} {side} 侧已经在录了", "id": rec.id}
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"screencast-{side}-{datetime.now():%m%d-%H%M%S}.mp4"
    args = [
        ff, "-hide_banner", "-loglevel", "warning", "-y",
        "-f", "avfoundation", "-capture_cursor", "1", "-framerate", str(RECORD_FPS),
        "-i", f"{screen_index}:none",
        # -2 让宽度按比例取最近的偶数，h264 要求偶数宽高
        "-vf", f"scale=-2:{RECORD_HEIGHT}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-progress", "pipe:1", str(path),
    ]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rec_id = secrets.token_hex(6)
    rec = Recording(rec_id, task_no, side, path, proc)
    # 录不上有两种死法：进程直接退（参数或设备不对），或卡在权限对话框上一帧不出。
    # 两种都得在这儿拦下来，不能让人对着「正在录」的按钮录完一场空气。
    if not rec.first_frame.wait(PERMISSION_WAIT_SECONDS) and proc.poll() is None:
        rec.proc.kill()
        path.unlink(missing_ok=True)
        return {"ok": False, "message": PERMISSION_HINT}
    if proc.poll() is not None:
        err = "\n".join(rec.stderr_tail).strip()
        path.unlink(missing_ok=True)
        return {"ok": False, "message": f"ffmpeg 启动失败：{err[-300:] or PERMISSION_HINT}"}
    with REC_LOCK:
        RECORDINGS[rec_id] = rec
    log(f"开录 {task_no} {side} 侧 → {path.name}（screen {screen_index}，{RECORD_HEIGHT}p）")
    return {"ok": True, "id": rec_id, "file": str(path), "message": f"正在录 {RECORD_HEIGHT}p"}


def stop_record(task_no: str = "", side: str = "", rec_id: str = "") -> dict:
    with REC_LOCK:
        rec = RECORDINGS.get(rec_id) if rec_id else next(
            (r for r in RECORDINGS.values() if r.alive and r.task_no == task_no and r.side == side), None)
    if not rec:
        return {"ok": False, "message": "没有正在进行的录制"}
    res = rec.stop()
    with REC_LOCK:
        RECORDINGS.pop(rec.id, None)
    log(f"停录 {rec.task_no} {rec.side} 侧 → {res['message']}（{res['seconds']}s，{res['size']} 字节）")
    return res


# ---------------- 启动项目 ----------------

def osascript(script: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)


SESSIONS: dict[str, dict] = {}


def start_project(task_no: str, side: str, cwd: Path, commands: list[str]) -> dict:
    """在 Terminal.app 新窗口里把这一侧跑起来。

    装依赖的命令直接执行；其余命令用 zsh 的 `print -s` 倒序塞进这个窗口的历史，
    按上箭头就是第一条，录屏时一条条敲、节奏自己控制。
    """
    if not cwd.is_dir():
        return {"ok": False, "message": f"工作目录不存在：{cwd}"}
    auto = [c for c in commands if any(re.search(p, c) for p in AUTO_RUN_PATTERNS)]
    manual = [c for c in commands if c not in auto]

    lines = [f"cd {shlex.quote(str(cwd))}", "clear", f"echo '# {task_no} {side} · '$PWD"]
    if manual:
        lines.append(f"echo '# 以下 {len(manual)} 条命令已放进历史，按 ↑ 依次调出'")
        for i, c in enumerate(manual, 1):
            lines.append(f"echo {shlex.quote(f'#  {i}. {c}')}")
        # 倒着塞，按一次 ↑ 拿到的就是第 1 条
        for c in reversed(manual):
            lines.append(f"print -s {shlex.quote(c)}")
    if auto:
        lines.append(f"echo '# 先自动装依赖（{len(auto)} 条）'")
        lines.extend(auto)

    # 命令里带引号、反斜杠和中文，直接塞进 AppleScript 字符串必挂（它不认 \\uXXXX）。
    # 落成临时脚本再 source，AppleScript 那边就只剩一个纯 ASCII 路径。source 不回显
    # 命令本身，所以录屏里看到的是干净的提示而不是一长串脚本内容。
    # 文件名刻意取中性：录屏会拍到这一行。
    sh = Path(f"/tmp/.start-{secrets.token_hex(4)}.sh")
    sh.write_text("\n".join(lines) + f"\nrm -f {sh}\n", "utf-8")

    r = osascript(f'''
tell application "Terminal"
  activate
  set newTab to do script "source {sh}"
  return tty of newTab
end tell''', timeout=25)
    if r.returncode != 0:
        return {"ok": False, "message": f"打不开终端窗口：{r.stderr.strip()[:300]}"}
    tty = r.stdout.strip()
    SESSIONS[f"{task_no}/{side}"] = {"tty": tty, "cwd": str(cwd), "at": time.time()}
    log(f"启动 {task_no} {side} 侧于 {cwd}（tty {tty}，自动 {len(auto)} 条 / 待敲 {len(manual)} 条）")
    return {
        "ok": True, "tty": tty, "cwd": str(cwd),
        "auto": auto, "manual": manual,
        "message": f"终端已打开，自动执行 {len(auto)} 条装依赖命令，另有 {len(manual)} 条待你敲",
    }


def session_ports(tty: str) -> list[int]:
    """这个终端窗口里跑出来的东西监听了哪些端口。

    先由 tty 找到那个 shell，顺着父子关系收全它的后代，再只对这些 pid 问 lsof——
    不这么框一下，机器上别的服务端口会混进来。
    """
    if not tty:
        return []
    ps = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,tty="], capture_output=True, text=True, timeout=10)
    tree: dict[int, list[int]] = {}
    roots: list[int] = []
    short = tty.replace("/dev/", "")
    for line in ps.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, t = int(parts[0]), int(parts[1]), parts[2].strip()
        tree.setdefault(ppid, []).append(pid)
        if t == short:
            roots.append(pid)
    if not roots:
        return []
    seen, stack = set(), list(roots)
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(tree.get(pid, []))
    lsof = subprocess.run(
        ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-a", "-p", ",".join(str(p) for p in seen)],
        capture_output=True, text=True, timeout=15)
    ports = {int(m.group(1)) for m in re.finditer(r":(\d+)\s+\(LISTEN\)", lsof.stdout)}
    return sorted(ports)


# ---------------- HTTP ----------------

class Handler(BaseHTTPRequestHandler):
    server_version = f"solo-host-agent/{VERSION}"

    def log_message(self, *_args) -> None:  # 默认日志太吵，只留业务日志
        pass

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authed(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Agent-Token", ""), self.server.token)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _safe_dir(self, raw: str) -> Path | None:
        """只许碰 CODER_ROOT 底下的目录。代理开在 0.0.0.0，这道门不能省。"""
        try:
            p = Path(raw).resolve()
        except (OSError, ValueError):
            return None
        root = Path(self.server.coder_root)
        return p if p == root or root in p.parents else None

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/health"):
            ff = ffmpeg_bin()
            with REC_LOCK:
                recs = [r.brief() for r in RECORDINGS.values()]
            return self._send(200, {
                "ok": True, "version": VERSION, "coder_root": self.server.coder_root,
                "ffmpeg": bool(ff), "screens": list_screens(ff) if ff else [],
                "height": RECORD_HEIGHT, "recordings": recs,
            })
        if not self._authed():
            return self._send(401, {"ok": False, "message": "口令不对"})
        if self.path.startswith("/project/status"):
            key = self.path.split("key=", 1)[-1].replace("%2F", "/")
            s = SESSIONS.get(key)
            if not s:
                return self._send(200, {"ok": True, "running": False, "ports": []})
            ports = session_ports(s["tty"])
            return self._send(200, {"ok": True, "running": True, "tty": s["tty"], "cwd": s["cwd"],
                                    "ports": ports, "urls": [f"http://localhost:{p}" for p in ports]})
        return self._send(404, {"ok": False, "message": "没有这个接口"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authed():
            return self._send(401, {"ok": False, "message": "口令不对"})
        try:
            body = self._body()
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "message": "请求体不是合法 JSON"})
        try:
            if self.path.startswith("/project/start"):
                cwd = self._safe_dir(body.get("cwd", ""))
                if not cwd:
                    return self._send(400, {"ok": False, "message": "工作目录不在 CODER_ROOT 之内，拒了"})
                return self._send(200, start_project(
                    str(body.get("task_no", "")), str(body.get("side", "")),
                    cwd, [str(c) for c in body.get("commands", []) if str(c).strip()]))
            if self.path.startswith("/record/start"):
                out = self._safe_dir(body.get("out_dir", ""))
                if not out:
                    return self._send(400, {"ok": False, "message": "输出目录不在 CODER_ROOT 之内，拒了"})
                return self._send(200, start_record(
                    str(body.get("task_no", "")), str(body.get("side", "")),
                    out, int(body.get("screen", 0))))
            if self.path.startswith("/record/stop"):
                return self._send(200, stop_record(
                    str(body.get("task_no", "")), str(body.get("side", "")), str(body.get("id", ""))))
        except Exception as e:  # noqa: BLE001
            log(f"接口出错 {self.path}：{e}")
            return self._send(500, {"ok": False, "message": f"代理内部错误：{e}"})
        return self._send(404, {"ok": False, "message": "没有这个接口"})


def main() -> None:
    port = int(os.environ.get("HOST_AGENT_PORT", DEFAULT_PORT))
    token = ensure_token()
    root = coder_root()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.token = token
    srv.coder_root = root

    ff = ffmpeg_bin()
    screens = list_screens(ff) if ff else []
    print("=" * 64)
    print(f"  Solo 宿主机代理 {VERSION} · Startup Success")
    print(f"  监听    : http://localhost:{port}（容器侧 http://host.docker.internal:{port}）")
    print(f"  工作根  : {root}")
    print(f"  口令    : {TOKEN_FILE}")
    print(f"  ffmpeg  : {ff or '未安装，录屏不可用（brew install ffmpeg）'}")
    print(f"  可录屏幕: {', '.join(s['label'] for s in screens) or '无'}")
    print("=" * 64)
    print("  这个窗口留着别关。首次录屏若失败，去「系统设置 → 隐私与安全性 → 屏幕录制」")
    print("  勾上「终端」，然后回到这里 Ctrl+C 再重跑一次。")
    print("=" * 64, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("收到退出信号，正在停掉未结束的录制")
        for rec in list(RECORDINGS.values()):
            rec.stop()
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
