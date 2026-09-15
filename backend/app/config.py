"""进程级配置：全部来自环境变量，业务配置（Key、Cookie 等）走 settings_store。

两套路径的区别必须分清：
- *_HOST：宿主机绝对路径，只用于拼 `docker run -v`（daemon 在宿主机解析）；
- *_MOUNT：后端容器内看到的路径，用于读写文件。
本机直接跑（不进容器）时两者相同。
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


DATA_DIR = Path(_env("DATA_DIR", "./data")).resolve()
# 宿主机上的 data 目录。质检要把轨迹挂进 solo-qa 容器，docker -v 的源路径
# 由宿主机的 daemon 解析，不能用后端容器内看到的 /data。
DATA_DIR_HOST = _env("DATA_DIR_HOST") or str(DATA_DIR)
CODER_ROOT_HOST = _env("CODER_ROOT_HOST") or _env("CODER_ROOT") or "/Users/gaoyong/solo-coder-0908"
CODER_ROOT_MOUNT = Path(_env("CODER_ROOT_MOUNT") or CODER_ROOT_HOST)
SECRET_KEY_FILE = Path(_env("SECRET_KEY_FILE") or str(DATA_DIR / "secret.key"))
DB_PATH = DATA_DIR / "solo-cli.db"
EXPORT_DIR = DATA_DIR / "exports"
HOST_PORT = _env("HOST_PORT", "8788")

# 环境种子：首次启动写入设置表（仅当设置为空时）
SEED_ENV = {
    "cursor.api_key": _env("CURSOR_API_KEY"),
    "cursor.model": _env("CURSOR_MODEL"),
    "cc.api_key": _env("CC_API_KEY"),
    "qa.session_cookie": _env("QA_SESSION_COOKIE"),
    "qa.csrf_token": _env("QA_CSRF_TOKEN"),
    "qc.project_host": _env("QA_PROJECT_HOST"),
    "gh.token": _env("GH_TOKEN"),
}

# 桥接脚本目录：挂进 solo-qa 镜像执行查重与质检
BRIDGE_DIR_HOST = _env("BRIDGE_DIR_HOST") or str(Path(__file__).resolve().parents[1] / "bridges")

# prompt.md 与各子目录的相对位置（相对 coder_root）
PROMPT_FILE = "prompt.md"
WORKSPACE_DIR = "workspace"
TRACES_DIR = "出题/轨迹"
ANALYSIS_DIR = "出题/分析"
PROMPTS_ARCHIVE_DIR = "出题/prompts"

# 容器内固定路径（由镜像决定）
CONTAINER_WORKSPACE = "/workspace"
CONTAINER_PROJECTS = "/home/node/.claude/projects"
CONTAINER_NAME_PREFIX = "solo-cc-"
CONTAINER_LABEL = "solo-cli.task"


class TaskPaths:
    """一道题涉及的全部目录，同时给出宿主路径与挂载路径。"""

    def __init__(self, task_no: str):
        self.task_no = task_no

    # ---- 后端可读写的路径 ----
    @property
    def workspace(self) -> Path:
        return CODER_ROOT_MOUNT / WORKSPACE_DIR / self.task_no

    @property
    def traces(self) -> Path:
        return CODER_ROOT_MOUNT / TRACES_DIR / self.task_no

    @property
    def analysis(self) -> Path:
        return CODER_ROOT_MOUNT / ANALYSIS_DIR / self.task_no

    @property
    def analysis_repo(self) -> Path:
        return self.analysis / "repo"

    @property
    def export(self) -> Path:
        return EXPORT_DIR / self.task_no

    @property
    def export_host(self) -> str:
        return f"{DATA_DIR_HOST}/exports/{self.task_no}"

    @property
    def prompt_archive(self) -> Path:
        return CODER_ROOT_MOUNT / PROMPTS_ARCHIVE_DIR / f"{self.task_no}.md"

    # ---- 传给 docker -v 的宿主路径 ----
    @property
    def workspace_host(self) -> str:
        return f"{CODER_ROOT_HOST}/{WORKSPACE_DIR}/{self.task_no}"

    @property
    def traces_host(self) -> str:
        return f"{CODER_ROOT_HOST}/{TRACES_DIR}/{self.task_no}"

    @property
    def container_name(self) -> str:
        return f"{CONTAINER_NAME_PREFIX}{self.task_no}"


def prompt_file() -> Path:
    return CODER_ROOT_MOUNT / PROMPT_FILE


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
