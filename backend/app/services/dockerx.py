"""docker CLI 子进程封装。用 CLI 而不用 SDK：`-i` 注入 stdin 与逐行读 stdout 更直接。"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import re
import secrets
import shutil
import signal
import struct
import termios
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass

from app import config

# 读日志流的块大小。逐块读再自己切行，见 stream_container_logs 的说明。
READ_CHUNK_BYTES = 65536


@dataclass
class CmdResult:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


async def run(args: list[str], *, stdin: bytes | None = None, timeout: float = 60,
              cwd: str | None = None, env: dict[str, str] | None = None) -> CmdResult:
    """跑一条命令拿回码与输出。

    cwd 与 env 是给 git 和 gh 用的：出题要在临时目录里操作仓库，还要把 GitHub Token
    从环境里带进去——token 不能写进工作区的任何文件，那个目录会被挂进容器。
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return CmdResult(124, "", f"timeout after {timeout}s: {' '.join(args)}")
    return CmdResult(proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))


def docker_bin() -> str | None:
    return shutil.which("docker")


async def daemon_ok() -> tuple[bool, str]:
    if not docker_bin():
        return False, "docker CLI 不存在"
    r = await run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)
    return (True, r.out.strip()) if r.ok else (False, r.err.strip() or r.out.strip())


async def image_present(image: str) -> bool:
    r = await run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], timeout=15)
    return r.ok


async def image_label(image: str, label: str) -> str:
    r = await run(["docker", "image", "inspect", image, "--format", f'{{{{index .Config.Labels "{label}"}}}}'], timeout=15)
    return r.out.strip() if r.ok else ""


_version_cache: dict[str, str] = {}


async def claude_version(image: str) -> str:
    """读取镜像内 CLI 版本，如 `2.1.197 (Claude Code)` → `2.1.197`。"""
    if image in _version_cache:
        return _version_cache[image]
    r = await run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "claude", image, "--version"], timeout=60)
    m = re.search(r"(\d+\.\d+\.\d+)", r.out)
    version = m.group(1) if (r.ok and m) else ""
    if version:
        _version_cache[image] = version
    return version


# 出题要知道容器里有什么才能定题目可行性。命令清单取的是会左右选题的那些：
# 缺 docker 就不能出要起数据库的题，缺 sudo 就不能出要装系统包的题。
_PROBE_COMMANDS = ("docker", "sudo", "git", "node", "npm", "python3", "go", "cargo",
                   "rustc", "java", "make", "gcc", "psql")
_PROBE_URLS = ("https://registry.npmjs.org/", "https://proxy.golang.org/",
               "https://github.com/", "https://pypi.org/")
_caps_cache: dict[str, dict] = {}


async def image_capabilities(image: str) -> dict:
    """实测镜像里有哪些命令、外网通不通。

    这是 solo-prompt skill 的 Phase 1 要求的实测，它自己做不了：出题时 CLI 跑在只读
    模式下，起不了容器。所以由这里代为实测，把结论作为事实交给它约束选题 —— skill 对
    这一步的要求是「禁止假设」，镜像会升级，能力清单会变，硬编码一份迟早和实际不符。

    一次 docker run 里把命令与外网一起探完，省掉两次镜像启动。
    """
    if image in _caps_cache:
        return _caps_cache[image]
    script = (
        "for c in " + " ".join(_PROBE_COMMANDS) + "; do "
        'command -v "$c" >/dev/null 2>&1 && echo "cmd $c ok" || echo "cmd $c missing"; done; '
        "for u in " + " ".join(_PROBE_URLS) + "; do "
        'printf "net %s " "$u"; curl -s -o /dev/null -w "%{http_code}\\n" --max-time 12 "$u" '
        '|| echo 000; done'
    )
    r = await run(["docker", "run", "--rm", "--entrypoint", "sh", image, "-c", script], timeout=180)
    if not r.ok:
        return {"ok": False, "error": (r.err or r.out).strip()[:300], "commands": {}, "network": {}}
    commands: dict[str, bool] = {}
    network: dict[str, str] = {}
    for line in r.out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "cmd":
            commands[parts[1]] = parts[2] == "ok"
        elif len(parts) == 3 and parts[0] == "net":
            network[parts[1]] = parts[2]
    caps = {"ok": bool(commands), "commands": commands, "network": network, "error": ""}
    if caps["ok"]:
        _caps_cache[image] = caps
    return caps


async def container_state(name: str) -> str:
    """running / exited / created / '' (不存在)。"""
    r = await run(["docker", "inspect", name, "--format", "{{.State.Status}}"], timeout=15)
    return r.out.strip() if r.ok else ""


# 真正退出了的状态。`.State.ExitCode` 只在这两种状态下有意义：容器还在
# running / created / paused / restarting 时这个字段一律是 0，而 0 在收尾判定里
# 就是「正常结束」——于是一个根本没退出的容器会被读成跑完了，界面显示「正常结束 ·
# 退出码 0」，日志却停在半路。退出码只能由确实退出的容器提供，其余一律返回 None，
# 让上层按「取不到退出码」处理（判 INTERRUPTED 交给巡检重跑）。
_EXITED_STATES = frozenset({"exited", "dead"})

_STATE_FMT = "\t".join((
    "{{.State.Status}}", "{{.State.ExitCode}}", "{{.State.OOMKilled}}", "{{.State.Error}}",
    "{{.State.StartedAt}}", "{{.State.FinishedAt}}", "{{.Config.Image}}",
))


async def container_exit_code(name: str) -> int | None:
    """容器的退出码。没退出（或容器不存在）就返回 None，理由见 _EXITED_STATES。"""
    snap = await container_snapshot(name)
    return snap.get("exit_code")


async def container_snapshot(name: str) -> dict:
    """容器此刻的样子。exists 为假时其余字段都不作数。

    退出码单独按 _EXITED_STATES 过一遍：docker 对没退出的容器也给 0。
    """
    r = await run(["docker", "inspect", name, "--format", _STATE_FMT], timeout=15)
    if not r.ok:
        return {"name": name, "exists": False, "status": "", "running": False, "exit_code": None}
    parts = (r.out.strip("\n").split("\t") + [""] * 7)[:7]
    status, code, oom, err, started, finished, image = parts
    status = status.strip()
    exit_code: int | None = None
    if status in _EXITED_STATES:
        try:
            exit_code = int(code.strip())
        except ValueError:
            exit_code = None
    return {"name": name, "exists": True, "status": status, "running": status == "running",
            "exit_code": exit_code, "oom_killed": oom.strip() == "true",
            "error": err.strip(), "started_at": started.strip(),
            "finished_at": finished.strip(), "image": image.strip()}


async def container_stats(names: list[str]) -> dict[str, dict]:
    """一次问几个容器的 CPU 与内存占用。只有在跑的容器有数。

    `--no-stream` 要采样才出数，一次一两秒，所以两侧一起问，别一个一个来。
    """
    if not names:
        return {}
    r = await run(["docker", "stats", "--no-stream", "--format",
                   "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}", *names], timeout=30)
    out: dict[str, dict] = {}
    for line in r.out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            out[parts[0].strip()] = {"cpu": parts[1].strip(), "mem": parts[2].strip(),
                                     "mem_perc": parts[3].strip()}
    return out


async def container_top(name: str) -> list[dict]:
    """容器里现在跑着哪些进程。

    stdout 断流之后，「模型是不是还在干活」就没有别的证据了 —— 事件流是空的，
    退出码还没有，只有容器里那个 claude 进程能说明它还活着。
    """
    r = await run(["docker", "top", name], timeout=15)
    rows = [l for l in r.out.splitlines() if l.strip()]
    if not r.ok or len(rows) < 2:
        return []
    cols = rows[0].split()
    if "PID" not in cols or "CMD" not in cols:
        return []
    pid_i, cmd_i = cols.index("PID"), cols.index("CMD")
    time_i = cols.index("TIME") if "TIME" in cols else -1
    out = []
    for line in rows[1:]:
        # 最后一列是完整命令行，本身带空格，所以限制切分次数
        parts = line.split(None, len(cols) - 1)
        if len(parts) <= cmd_i:
            continue
        out.append({"pid": parts[pid_i],
                    "time": parts[time_i] if 0 <= time_i < len(parts) else "",
                    "cmd": parts[cmd_i][:300]})
    return out


async def last_log_line(name: str) -> str:
    """容器日志的最后一行，带 `docker logs -t` 的时间戳前缀。

    这一行的时刻就是「容器最后一次出声」，跟当前时间一减就知道它是还在干活还是
    已经卡住了。事件流断掉时，界面上唯一还能如实反映现状的就是这个数。
    """
    r = await run(["docker", "logs", "-t", "--tail", "1", name], timeout=20)
    text = (r.out or r.err or "").strip()
    return text.splitlines()[-1] if text else ""


async def tail_result_event(name: str, lines: int = 200) -> dict:
    """从容器日志尾部把 stream-json 的 result 事件捞回来，没有就返回空字典。

    收尾判定本来靠这条事件定性，可它只在 stdout 上出现一次，采集一断就永远拿不到：
    容器明明跑完了（日志最后一行就是 result·success），界面却只能显示「无 result」，
    轮次、耗时、用量全空，状态靠退出码猜。而 docker 把容器的每一行输出都留着，
    收尾时回头去日志里找一遍，这些东西就都回来了。
    """
    r = await run(["docker", "logs", "--tail", str(lines), name], timeout=60)
    for source in (r.out, r.err):
        for raw in reversed((source or "").splitlines()):
            s = raw.strip()
            if not s.startswith("{") or '"result"' not in s:
                continue
            try:
                obj = json.loads(s)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "result":
                return obj
    return {}


async def stream_container_logs(name: str, *, tail: int = 200, max_line: int = 8192):
    """跟着容器日志逐行往外送，供界面上的终端实时看。

    自己按块切行而不用 StreamReader.readline：一条 tool_result 能有几百 KB，
    readline 超过 limit 会抛 ValueError 把整条流打死。给人看的东西不需要完整 JSON，
    所以超长直接截断，跟收尾那条要留完整载荷的路径不共用实现。
    """
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "-f", "--tail", str(tail), name,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout
    try:
        buf = bytearray()
        while True:
            chunk = await proc.stdout.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            buf += chunk
            while (nl := buf.find(b"\n")) >= 0:
                line = bytes(buf[:nl])
                del buf[:nl + 1]
                yield line[:max_line].decode("utf-8", "replace")
            if len(buf) > max_line * 4:
                # 还没见到换行就已经远超一屏，先把看得见的部分交出去
                yield bytes(buf[:max_line]).decode("utf-8", "replace")
                buf.clear()
        if buf:
            yield bytes(buf[:max_line]).decode("utf-8", "replace")
    finally:
        # 浏览器一关就要把 docker logs -f 收掉，不然每开一次终端都留一个进程
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


# 终端默认尺寸。浏览器一连上就会报真实行列数改过来，这两个数只管第一屏。
PTY_ROWS, PTY_COLS = 30, 100
PTY_READ_BYTES = 65536
# 输出攒多少块。攒满了丢最老的，不能让读取停下来，见 PtySession._on_readable。
PTY_QUEUE_CHUNKS = 256


class PtySession:
    """接在伪终端上的一个 `docker exec`：能读、能写、能改窗口大小。

    为什么非要造一个伪终端，而不是像别处那样拿管道接 stdout：`docker exec -t` 要求
    自己的 stdin 是终端，喂管道给它，CLI 起手就拒绝（the input device is not a TTY）；
    去掉 `-t` 倒是能跑，但容器里的程序看到的就不是终端了 —— bash 不给提示符、输出没
    颜色、光标控制全失效，vim、top、git log 这类认终端的程序根本用不了。所以本地这端
    先开一个 pty：slave 交给 docker CLI 当它的终端，master 留在手里当键盘和屏幕。
    """

    def __init__(self, proc: asyncio.subprocess.Process, master: int) -> None:
        self._proc = proc
        self._master = master
        self._loop = asyncio.get_running_loop()
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=PTY_QUEUE_CHUNKS)
        self._reading = True
        # 收摊时还要做的事。容器里那个进程不会跟着本地客户端一起死，得另外收，见 pty_shell
        self.on_close: Callable[[], Awaitable[None]] | None = None
        self._loop.add_reader(master, self._on_readable)

    def _on_readable(self) -> None:
        try:
            data = os.read(self._master, PTY_READ_BYTES)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            # 容器里那头退出后，pty 主端读出来是 EIO 而不是 EOF，这是正常收场
            data = b""
        if not data:
            self._stop_reading()
            return
        try:
            self._chunks.put_nowait(data)
        except asyncio.QueueFull:
            # 刷屏比浏览器收得快时丢最老的一块，而不是不读。读一停，pty 缓冲立刻写满，
            # 容器里的程序被堵在 write 上，看着就像卡死了。
            self._chunks.get_nowait()
            self._chunks.put_nowait(data)

    def _stop_reading(self) -> None:
        if not self._reading:
            return
        self._reading = False
        self._loop.remove_reader(self._master)
        self._chunks.put_nowait(None)

    async def read(self) -> bytes | None:
        """取下一块输出，None 表示这一端结束了。"""
        return await self._chunks.get()

    async def write(self, data: bytes) -> None:
        """把键盘输入写进终端。"""
        view = memoryview(data)
        while view:
            try:
                view = view[os.write(self._master, view):]
            except BlockingIOError:
                # 粘一大段文本会写满 pty 缓冲，等容器那头读走一些再接着写
                await asyncio.sleep(0.01)
            except OSError:
                return

    def resize(self, rows: int, cols: int) -> None:
        """改窗口大小。

        两步都得做：ioctl 改的是本地 pty 的尺寸，而容器里那个终端的尺寸由 docker CLI
        同步过去，它只在收到 SIGWINCH 时才去读新尺寸。少了这一枪，浏览器里把窗口拉大，
        容器里的程序仍按旧行列数排版，换行位置全是错的。
        """
        try:
            fcntl.ioctl(self._master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            return
        if self._proc.returncode is None:
            with suppress(ProcessLookupError, OSError):
                self._proc.send_signal(signal.SIGWINCH)

    async def close(self) -> None:
        """收摊：先断本地这一端，再把容器里那个进程也收掉。"""
        self._stop_reading()
        if self._master >= 0:
            with suppress(OSError):
                os.close(self._master)
            self._master = -1
        if self._proc.returncode is None:
            with suppress(ProcessLookupError):
                self._proc.kill()
        with suppress(Exception):
            await asyncio.wait_for(self._proc.wait(), timeout=10)
        if self.on_close is not None:
            hook, self.on_close = self.on_close, None
            with suppress(Exception):
                await hook()


async def pty_exec(name: str, args: list[str], *, rows: int = PTY_ROWS, cols: int = PTY_COLS,
                   workdir: str = "", env: dict[str, str] | None = None) -> PtySession:
    """在容器里开一个带终端的进程，返回它的伪终端两端。"""
    master, slave = pty.openpty()
    with suppress(OSError):
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    os.set_blocking(master, False)
    cmd = ["docker", "exec", "-it"]
    for k, v in (env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    if workdir:
        cmd += ["-w", workdir]
    cmd += [name, *args]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=slave, stdout=slave, stderr=slave,
            # 单独一个会话：终端里按的 Ctrl-C 只该打到容器里那个 shell，
            # 不能顺着进程组捅到后端自己身上
            start_new_session=True,
        )
    except BaseException:
        os.close(master)
        raise
    finally:
        # slave 已经交给子进程，这边必须松手：不松手，容器里的 shell 退出后
        # 主端永远等不到挂断，这条连接就一直悬着
        os.close(slave)
    return PtySession(proc, master)


# 容器里那个 shell 的 PID 落脚处。放 /tmp：工作区和轨迹目录是这道题的产物，
# 终端这种临时东西一个字节都不能往里写。
PTY_PID_DIR = "/tmp/solo-term"
# 镜像里有 bash（entrypoint 就是 bash 脚本），但别把这条路押在它身上：换一版镜像、
# 换个基底就可能只剩 sh，那时整个终端开不起来，而人正等着进去看现场。
#
# 探测的 2>/dev/null 只能盖在 command 上。写成 `exec bash 2>/dev/null` 的话重定向
# 会跟着整个会话：bash 的提示符走 stderr，会被直接丢掉；而 bash 判定自己交互与否要看
# stdin 和 stderr 是不是都连着终端，stderr 一被改到 /dev/null 它就当自己在跑脚本，
# 于是没有提示符、没有行编辑、Ctrl-C 也不管用。
_SHELL_SCRIPT = "if command -v bash >/dev/null 2>&1; then exec bash; fi; exec sh"


async def pty_shell(name: str, *, rows: int = PTY_ROWS, cols: int = PTY_COLS,
                    workdir: str = "", env: dict[str, str] | None = None) -> PtySession:
    """在容器里开一个交互 shell，并保证这条连接断开后它会被收掉。

    为什么要专门收：杀掉本机这个 `docker exec` 客户端进程，容器里那个 shell 不会跟着
    死 —— 对 daemon 来说 exec 进程跟客户端没有从属关系，客户端没了它照样在自己的 pts
    上等输入。实测每开一次终端就在容器里留一个 bash，攒起来既污染详情页「容器里的进程」
    那一列，又让人分不清哪个进程是模型起的；更要紧的是终端里跑过的长命令会一直跑下去，
    而那是一道正在评测的题。所以让 shell 先把自己的 PID 写下来，收摊时照着它发挂断。
    """
    token = secrets.token_hex(8)
    pid_file = f"{PTY_PID_DIR}/{token}.pid"
    # exec 不换 PID，所以这里记下的就是待会儿那个 shell 自己的
    script = f"mkdir -p {PTY_PID_DIR}; echo $$ > {pid_file}; {_SHELL_SCRIPT}"
    term = await pty_exec(name, ["sh", "-c", script], rows=rows, cols=cols,
                          workdir=workdir, env=env)

    async def reap() -> None:
        # 先冲着进程组来（shell 是组长，负号打的是一整组），这样它在终端里起的东西
        # 一起带走；容器已经没了就什么也不做，反正东西跟着容器一起消失了
        await run(["docker", "exec", name, "sh", "-c",
                   f'p=$(cat {pid_file} 2>/dev/null) || exit 0; '
                   f'kill -HUP -"$p" 2>/dev/null || kill -HUP "$p" 2>/dev/null; '
                   f'rm -f {pid_file}'], timeout=20)

    term.on_close = reap
    return term


async def stop_container(name: str, grace: int = 30) -> CmdResult:
    return await run(["docker", "stop", "-t", str(grace), name], timeout=grace + 30)


async def remove_container(name: str) -> CmdResult:
    return await run(["docker", "rm", "-f", name], timeout=60)


async def remove_task_containers(task_no: str) -> CmdResult:
    """删掉这道题所有轮次的容器。

    续跑每轮一个容器（solo-cc-01、solo-cc-01-r2……），只按当前名字删会把前几轮
    的落下。各轮都带同一个 task 标签，按标签一次清干净。
    """
    ls = await run(["docker", "ps", "-aq", "--filter",
                    f"label={config.CONTAINER_LABEL}={task_no}"], timeout=30)
    ids = ls.out.split()
    if not ids:
        return CmdResult(0, "", "")
    return await run(["docker", "rm", "-f", *ids], timeout=120)


async def list_task_containers() -> list[dict]:
    r = await run(["docker", "ps", "-a", "--filter", f"label={config.CONTAINER_LABEL}",
                   "--format", "{{.Names}}\t{{.Status}}\t{{.Label \"" + config.CONTAINER_LABEL + "\"}}"], timeout=20)
    rows = []
    for line in r.out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append({"name": parts[0], "status": parts[1], "task_no": parts[2]})
    return rows
