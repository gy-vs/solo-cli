"""业务配置：Fernet 加密落库，界面掩码读取。

所有值统一加密（不只密钥），避免「哪个字段该加密」的判断散落各处。
密钥文件 secret.key 首次启动生成，权限 600，随 ./data 卷持久化。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app import config
from app.db import session
from app.models import Setting

log = logging.getLogger("settings")

MASK_PLACEHOLDER = "••••••••"


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    group: str
    secret: bool = False
    default: str = ""
    kind: str = "text"      # text / number / select
    help: str = ""


SPECS: tuple[Spec, ...] = (
    Spec("qa.base_url", "solo-qa 地址", "solo-qa 身份", default="https://solo2.jzxhnh.com"),
    Spec("qa.session_cookie", "solo_qa_session", "solo-qa 身份", secret=True, help="浏览器 Cookie 中 solo_qa_session 的值"),
    Spec("qa.csrf_token", "solo_qa_csrf", "solo-qa 身份", secret=True, help="Cookie 中 solo_qa_csrf 的值，同时作为 X-CSRF-Token 头"),
    Spec("cc.api_key", "网关 Key", "Claude Code 容器", secret=True, help="注入容器的 apikey，形如 sk-…"),
    Spec("cc.image", "镜像", "Claude Code 容器", default="adminfather/benzhi-claude-code:20260915-mount"),
    Spec("cc.memory", "容器内存上限", "Claude Code 容器", default="4g"),
    Spec("cc.cpus", "容器 CPU 上限", "Claude Code 容器", default="2"),
    Spec("cursor.api_key", "Cursor API Key", "Cursor CLI 分析", secret=True, help="cursor.com/dashboard/api 创建的 User API Key"),
    Spec("cursor.model", "分析模型", "Cursor CLI 分析", default="claude-opus-5-thinking-high", kind="select"),
    Spec("cursor.timeout_minutes", "分析超时（分钟）", "Cursor CLI 分析", default="40", kind="number"),
    Spec("scheduler.max_parallel", "最大并发容器数", "调度", default="3", kind="number"),
    Spec("scheduler.paused", "暂停出队", "调度", default="0", kind="bool",
         help="暂停后队列不再启动新容器，已在跑的不受影响"),
    Spec("run.timeout_minutes", "单题运行超时（分钟）", "调度", default="120", kind="number"),
    Spec("gate.blacklist", "泄漏扫描黑名单（逗号分隔 glob）", "调度",
         default="CLAUDE.md,AGENTS.md,.claude,.cursor,.cursorrules,*.mdc,prompt*.md,题*,需求文档,*.jsonl"),
    Spec("auto.destroy_on_finish", "结束后自动销毁容器", "自动流水线", default="1", kind="bool",
         help="轨迹导出成功后才销毁；导出失败会保留容器等待人工处理"),
    Spec("auto.analyze", "结束后自动五维分析", "自动流水线", default="1", kind="bool"),
    Spec("auto.qc", "分析后自动质检", "自动流水线", default="1", kind="bool"),
    Spec("auto.max_parallel", "分析/质检并发", "自动流水线", default="2", kind="number",
         help="这两步都在调模型，并发过高会互相拖慢"),
    Spec("qc.enabled", "启用 solo-qa 质检", "solo-qa 质检", default="1", kind="bool"),
    Spec("qc.project_host", "solo-qa 项目路径（宿主机）", "solo-qa 质检", default="/Users/gaoyong/solo-qa-0908",
         help="挂进质检容器的源码与 .env 所在目录"),
    Spec("qc.image", "质检镜像", "solo-qa 质检", default="solo-qa-backend:latest",
         help="复用 solo-qa 自己的后端镜像，避免依赖版本冲突"),
    Spec("qc.timeout_minutes", "质检超时（分钟）", "solo-qa 质检", default="15", kind="number"),
    Spec("design.count", "默认设计题数", "题目设计", default="5", kind="number"),
    Spec("design.model", "设计模型", "题目设计", default="claude-opus-5-thinking-high", kind="select"),
    Spec("design.timeout_minutes", "设计超时（分钟）", "题目设计", default="90", kind="number"),
    Spec("design.auto_dedup", "设计后自动查重（规则 A+C）", "题目设计", default="1", kind="bool",
         help="命中规则 A 或 C 的题直接废弃，通过的留在题库队列"),
    Spec("gh.token", "GitHub Token", "题目设计", secret=True,
         help="出题要建仓库和推快照。本机执行 gh auth token 取值，需要 repo 权限"),
)
SPEC_BY_KEY = {s.key: s for s in SPECS}


def _fernet() -> Fernet:
    path = config.SECRET_KEY_FILE
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
        os.chmod(path, 0o600)
    return Fernet(path.read_bytes().strip())


def _enc(v: str) -> str:
    return _fernet().encrypt(v.encode("utf-8")).decode("ascii")


def _dec(v: str) -> str:
    if not v:
        return ""
    try:
        return _fernet().decrypt(v.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def get(key: str) -> str:
    spec = SPEC_BY_KEY.get(key)
    with session() as db:
        row = db.get(Setting, key)
        if row and row.value_enc:
            return _dec(row.value_enc)
    return spec.default if spec else ""


def get_int(key: str, fallback: int = 0) -> int:
    try:
        return int(float(get(key)))
    except (TypeError, ValueError):
        return fallback


def get_bool(key: str, fallback: bool = False) -> bool:
    v = get(key).strip().lower()
    if not v:
        return fallback
    return v not in ("0", "false", "no", "off")


def set_one(key: str, value: str) -> None:
    set_many({key: value})


def looks_masked(value: str) -> bool:
    """界面掩码识别。

    掩码是「占位符 + 末 4 位」，早期只判前缀，一旦格式变一点就会把掩码当真值
    写进库里，密钥当场作废、用户以为「配置又丢了」。真实的 key 里不可能出现
    圆点字符，所以只要出现在任何位置就一律当掩码拒绝。
    """
    return MASK_PLACEHOLDER in value or "•" in value


def set_many(values: dict[str, str]) -> list[str]:
    """写入多项。值为掩码时跳过（界面未修改该密钥）。返回实际写入的 key。"""
    written: list[str] = []
    skipped: list[str] = []
    with session() as db:
        for key, value in values.items():
            if key not in SPEC_BY_KEY:
                continue
            if looks_masked(value):
                skipped.append(key)
                continue
            value = (value or "").strip()
            row = db.get(Setting, key)
            if row is None:
                row = Setting(key=key)
                db.add(row)
            row.value_enc = _enc(value) if value else ""
            written.append(key)
    # 只记 key 不记值：配置一旦「莫名丢了」，靠这行日志能确认是谁清的
    if written:
        log.info("设置写入：%s", ", ".join(f"{k}{'(清空)' if not values[k].strip() else ''}" for k in written))
    if skipped:
        log.info("设置跳过（界面掩码，保留原值）：%s", ", ".join(skipped))
    return written


def is_configured(key: str) -> bool:
    return bool(get(key))


def masked(value: str, secret: bool) -> str:
    if not value:
        return ""
    if not secret:
        return value
    tail = value[-4:] if len(value) > 8 else ""
    return f"{MASK_PLACEHOLDER}{tail}"


def all_for_ui() -> list[dict]:
    out = []
    for spec in SPECS:
        value = get(spec.key)
        out.append({
            "key": spec.key,
            "label": spec.label,
            "group": spec.group,
            "secret": spec.secret,
            "kind": spec.kind,
            "help": spec.help,
            "default": spec.default,
            "configured": bool(value),
            "value": masked(value, spec.secret),
        })
    return out


def sanitize() -> list[str]:
    """清掉被掩码污染的值。

    早期版本的「保存全部」会把界面上的掩码写回库里，这种值拿去当密钥用
    只会在运行时报一个难懂的鉴权错误。启动时清空并记日志，界面上直接显示未配置。
    """
    cleaned: list[str] = []
    with session() as db:
        for spec in SPECS:
            row = db.get(Setting, spec.key)
            if row is None or not row.value_enc:
                continue
            if looks_masked(_dec(row.value_enc)):
                row.value_enc = ""
                cleaned.append(spec.key)
    return cleaned


def seed_from_env() -> list[str]:
    """首次启动：设置为空且环境变量有值时写入。"""
    seeded: list[str] = []
    with session() as db:
        existing = {r.key for r in db.execute(select(Setting)).scalars() if r.value_enc}
    for key, value in config.SEED_ENV.items():
        if value and key not in existing:
            set_many({key: value})
            seeded.append(key)
    return seeded
