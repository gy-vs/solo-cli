"""docker CLI 子进程封装。用 CLI 而不用 SDK：`-i` 注入 stdin 与逐行读 stdout 更直接。"""

from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass

from app import config


@dataclass
class CmdResult:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


async def run(args: list[str], *, stdin: bytes | None = None, timeout: float = 60) -> CmdResult:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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


async def container_state(name: str) -> str:
    """running / exited / created / '' (不存在)。"""
    r = await run(["docker", "inspect", name, "--format", "{{.State.Status}}"], timeout=15)
    return r.out.strip() if r.ok else ""


async def container_exit_code(name: str) -> int | None:
    r = await run(["docker", "inspect", name, "--format", "{{.State.ExitCode}}"], timeout=15)
    try:
        return int(r.out.strip()) if r.ok else None
    except ValueError:
        return None


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
