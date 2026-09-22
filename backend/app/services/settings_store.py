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
    Spec("gsb.base_url", "solo2 平台地址", "GSB 平台", default="https://solo2.jzxhnh.com"),
    Spec("gsb.session_cookie", "solo_qa_session", "GSB 平台", secret=True,
         help="solo2.jzxhnh.com 的浏览器 Cookie，注意与旧站点不是一套"),
    Spec("gsb.csrf_token", "solo_qa_csrf", "GSB 平台", secret=True,
         help="Cookie 中 solo_qa_csrf 的值，同时作为 X-CSRF-Token 头"),
    Spec("cc.api_key", "网关 Key", "Claude Code 容器", secret=True, help="注入容器的 apikey，形如 sk-…"),
    Spec("cc.image", "镜像", "Claude Code 容器", default="adminfather/benzhi-claude-code:20260915-mount"),
    Spec("cc.memory", "容器内存上限", "Claude Code 容器", default="4g"),
    Spec("cc.cpus", "容器 CPU 上限", "Claude Code 容器", default="2"),
    Spec("cursor.api_key", "Cursor API Key", "Cursor CLI 分析", secret=True, help="cursor.com/dashboard/api 创建的 User API Key"),
    Spec("cursor.model", "分析模型", "Cursor CLI 分析", default="claude-opus-5-thinking-high", kind="select"),
    Spec("cursor.timeout_minutes", "分析超时（分钟）", "Cursor CLI 分析", default="40", kind="number"),
    Spec("scheduler.max_parallel", "最大并发容器数", "调度", default="8", kind="number",
         help="上限由网关 Key 的并发决定：Key 允许 8 路并发就填 8。排队和额度的单位都是"
              "容器，一个空槽放一个容器，A 与 B 各排各的队，两侧跑完再配对分析；"
              "填奇数也不浪费槽位"),
    Spec("scheduler.paused", "暂停出队", "调度", default="0", kind="bool",
         help="暂停后队列不再启动新容器，已在跑的不受影响"),
    Spec("run.timeout_minutes", "单题运行超时（分钟）", "调度", default="120", kind="number"),
    Spec("gate.blacklist", "泄漏扫描黑名单（逗号分隔 glob）", "调度",
         default="CLAUDE.md,AGENTS.md,.claude,.cursor,.cursorrules,*.mdc,"
                 "drafts,sessions,reports,staging,current.md,index.md,brief.md,"
                 "prompt*.md,题*,需求文档,出题,轨迹,*.jsonl",
         help="工作副本里出现这些就是出题资料漏进了映射目录。旧命名一并留着兜底"),
    Spec("auto.destroy_on_finish", "结束后自动销毁容器", "自动流水线", default="1", kind="bool",
         help="轨迹导出成功后才销毁；导出失败会保留容器等待人工处理"),
    Spec("auto.analyze", "两边跑完后自动 GSB 分析", "自动流水线", default="1", kind="bool"),
    Spec("auto.max_parallel", "分析/质检并发", "自动流水线", default="30", kind="number",
         help="分析与两道质检都在调模型，这个数就是同时在跑的模型调用数。"
              "一道题的分析十几分钟、每道质检一两分钟，积压上百道时低并发要跑一整天；"
              "撞限流的话调用会自己退避重试，代价比串行等着小"),
    Spec("watchdog.interval_seconds", "守护扫描间隔（秒）", "守护", default="300", kind="number",
         help="扫异常重跑与配对触发分析；run 一结束会立刻唤醒一次，这个间隔只是兜底"),
    Spec("watchdog.paused", "暂停自动重跑与废弃", "守护", default="0", kind="bool",
         help="打开后巡检不再自动重跑、也不再因次数用尽自动废弃，题目保持当前状态。"
              "运行中的容器不受影响，配对分析仍照常。人工点「重跑」或「废弃」仍然有效。"
              "模型或网关要停机时先开这个：重跑的动作是把工作区连 .git 一起删掉重建，"
              "停机期间每一侧都会跑挂，不暂停就会被逐一清空、跑满次数后整题废弃"),
    Spec("watchdog.max_retries", "自动重跑次数上限", "守护", default="3", kind="number",
         help="一侧最多跑几次，用尽后整道题自动废弃（可在废弃列表里恢复）。这和 CC 自己的"
              "十次网关重试是两回事：那十次在容器内部发生，重试期间不介入，"
              "只有重试用尽仍没跑成才算一次容器级重跑"),
    Spec("watchdog.max_timeouts", "超时次数上限", "守护", default="2", kind="number",
         help="超时单独计数，先撞到哪个上限就按哪个废弃。一次超时要烧掉一整个运行超时的"
              "机器时间，所以容忍次数比普通重跑更低"),
    # qc.* 三项保留：solo-qa 质检已废弃，但出题查重还要靠它们把 solo-qa 源码挂进桥接容器
    Spec("qc.project_host", "solo-qa 项目路径（宿主机）", "题目查重", default="/Users/gaoyong/solo-qa-0908",
         help="挂进质检容器的源码与 .env 所在目录"),
    Spec("qc.image", "质检镜像", "题目查重", default="solo2-backend:latest",
         help="复用 solo-qa 自己的后端镜像（它的 compose 里就叫这个名），避免依赖版本冲突"),
    Spec("qc.timeout_minutes", "质检超时（分钟）", "题目查重", default="15", kind="number"),
    Spec("design.count", "默认设计题数", "题目设计", default="5", kind="number"),
    Spec("design.model", "设计模型", "题目设计", default="claude-opus-5-thinking-high", kind="select"),
    Spec("design.timeout_minutes", "设计超时（分钟）", "题目设计", default="90", kind="number"),
    Spec("design.auto_dedup", "设计后自动查重（规则 A+C）", "题目设计", default="1", kind="bool",
         help="命中规则 A 或 C 的题直接废弃，通过的留在题库队列"),
    Spec("gh.token", "GitHub Token", "题目设计", secret=True,
         help="出题要建仓库和推快照。本机执行 gh auth token 取值，需要 repo 权限"),
    Spec("pool.enabled", "启用远端题库", "跨设备题库", default="0", kind="bool",
         help="多台设备共用一个 GitHub 私有仓库当题库：出的题全推上去，领题从那里拉，"
              "谁领了哪道题也记在上面，两台机器不会领到同一道。同时充当查重池。"
              "关掉则回到单设备模式，题库只认本机题面文件，另一台设备出的题在本机不可见"),
    Spec("pool.repo", "远端题库仓库", "跨设备题库",
         help="GitHub 私有仓库，填 owner/repo 或完整 https 地址。仓库不存在会自动创建为 private。"
              "里面存题面全文，必须是私有仓库"),
    Spec("pool.device", "本机标识", "跨设备题库", default="",
         help="区分题目出自哪台设备、谁领了哪道题，例如 mac-studio / mac-air。必填且两台设备"
              "不能重名：后端跑在容器里，不填会取到每次重建都变的容器 ID，同一道题会被反复"
              "当成新题入库，领取归属也会跟着失效"),
    Spec("pool.similarity", "字面查重阈值", "跨设备题库", default="0.45", kind="number",
         help="题面归一化后的相似度上限，超过即判重。实测同一道题换措辞在 0.5 上下，"
              "同基底的不同功能点在 0.3 上下，0.45 落在两者之间。往低调更容易误杀真题，"
              "但被拒的候选只是没落地、日志里写明了相似度和撞的是哪道题；往高调会漏掉"
              "同义改写的重复题，代价是两个容器白跑两小时"),
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
