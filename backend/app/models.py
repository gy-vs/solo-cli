"""数据模型。JSON 字段以 Text 存储，通过属性读写。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------- 任务状态 ----------------
AVAILABLE = "AVAILABLE"        # 题库中，未领取
CLAIMED = "CLAIMED"            # 已领取，未进队列（门禁未过）
QUEUED = "QUEUED"              # 等待槽位
RUNNING = "RUNNING"            # 容器运行中
FINISHED = "FINISHED"          # result.success
FAILED = "FAILED"              # result 非 success / 退出码非 0
TIMEOUT = "TIMEOUT"            # 超时被停止
INTERRUPTED = "INTERRUPTED"    # 容器异常消失 / 137 / 进程中断
REVIEWED = "REVIEWED"          # 五维齐全且核验无红项
UPLOADED = "UPLOADED"          # 已上传 solo-qa
DONE = "DONE"                  # 人工确认完成，容器已销毁
DISCARDED = "DISCARDED"        # 人工废弃，默认不在列表显示

ALL_STATUSES = (
    AVAILABLE, CLAIMED, QUEUED, RUNNING, FINISHED, FAILED, TIMEOUT,
    INTERRUPTED, REVIEWED, UPLOADED, DONE, DISCARDED,
)
RUN_END_STATUSES = frozenset({FINISHED, FAILED, TIMEOUT, INTERRUPTED})
# 允许进入分析的状态
ANALYZABLE = RUN_END_STATUSES | {REVIEWED, UPLOADED}
# 允许上传的状态
UPLOADABLE = frozenset({REVIEWED})

ANALYSIS_IDLE = "IDLE"
ANALYSIS_RUNNING = "RUNNING"
ANALYSIS_DONE = "DONE"
ANALYSIS_FAILED = "FAILED"

# 质检（调 solo-qa 的链路，只取结论）
QC_IDLE = "IDLE"
QC_RUNNING = "RUNNING"
QC_DONE = "DONE"
QC_FAILED = "FAILED"
# solo-qa 的结论取值
QC_PASS = "PASS"
QC_REJECT = "REJECT"
QC_DISCARD = "DISCARD"
QC_INCOMPLETE = "INCOMPLETE"

# 任务来源
ORIGIN_BANK = "bank"          # prompt.md 导入
ORIGIN_DESIGNED = "designed"  # /solo-prompt 设计产出

# 自动流水线阶段，仅用于界面展示当前卡在哪一步
STAGE_IDLE = ""
STAGE_DESTROY = "destroy"
STAGE_ANALYZE = "analyze"
STAGE_QC = "qc"
STAGE_DONE = "done"

# 设计任务状态
DESIGN_QUEUED = "QUEUED"
DESIGN_RUNNING = "RUNNING"
DESIGN_DEDUP = "DEDUP"
DESIGN_DONE = "DONE"
DESIGN_FAILED = "FAILED"
DESIGN_CANCELLED = "CANCELLED"


class JsonMixin:
    @staticmethod
    def _load(raw: str | None, default: Any) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)


class Task(Base, JsonMixin):
    __tablename__ = "task"
    __table_args__ = (UniqueConstraint("task_no", "prompt_hash", name="uq_task_no_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_no: Mapped[str] = mapped_column(String(32), index=True)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default=AVAILABLE, index=True)

    # ---- 来自 prompt.md ----
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    question_type: Mapped[str] = mapped_column(String(64), default="")
    difficulty: Mapped[str] = mapped_column(String(16), default="")
    languages: Mapped[str] = mapped_column(String(255), default="")
    harness: Mapped[str] = mapped_column(String(64), default="")
    harness_version: Mapped[str] = mapped_column(String(64), default="")
    os_platform: Mapped[str] = mapped_column(String(64), default="")
    repro_level: Mapped[str] = mapped_column(String(64), default="")
    env_snapshot: Mapped[str] = mapped_column(String(512), default="")
    user_prompt: Mapped[str] = mapped_column(Text, default="")

    # ---- 运行 ----
    session_id: Mapped[str] = mapped_column(String(128), default="")
    turn_id: Mapped[str] = mapped_column(String(128), default="")
    discarded_from: Mapped[str] = mapped_column(String(16), default="")
    container_name: Mapped[str] = mapped_column(String(64), default="")
    container_exists: Mapped[bool] = mapped_column(Boolean, default=False)
    image_tag: Mapped[str] = mapped_column(String(128), default="")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")       # stream-json 的 result 事件
    verdict_json: Mapped[str] = mapped_column(Text, default="{}")      # 三层判定明细
    trace_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    trace_file: Mapped[str] = mapped_column(String(512), default="")   # 导出后的 jsonl 路径
    git_diff_stat: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    # ---- 分析 / 评审 ----
    analysis_status: Mapped[str] = mapped_column(String(16), default=ANALYSIS_IDLE)
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")     # agent 原始输出（结构化）
    review_json: Mapped[str] = mapped_column(Text, default="{}")       # 人工可编辑的五维与描述
    verify_json: Mapped[str] = mapped_column(Text, default="{}")       # 交叉核验报告
    upload_json: Mapped[str] = mapped_column(Text, default="{}")

    # ---- 质检（solo-qa 链路的结论，不入它的库） ----
    qc_status: Mapped[str] = mapped_column(String(16), default=QC_IDLE)
    qc_json: Mapped[str] = mapped_column(Text, default="{}")
    qc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- 队列与来源 ----
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)   # 越小越先出队
    origin: Mapped[str] = mapped_column(String(16), default=ORIGIN_BANK)
    design_run_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    dedup_json: Mapped[str] = mapped_column(Text, default="{}")             # 设计产出的查重结论
    auto_stage: Mapped[str] = mapped_column(String(16), default=STAGE_IDLE)
    auto_error: Mapped[str] = mapped_column(Text, default="")

    # ---- 时间 ----
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- JSON 便捷属性 ----
    @property
    def meta(self) -> dict:
        return self._load(self.meta_json, {})

    @meta.setter
    def meta(self, v: dict) -> None:
        self.meta_json = self._dump(v)

    @property
    def result(self) -> dict:
        return self._load(self.result_json, {})

    @result.setter
    def result(self, v: dict) -> None:
        self.result_json = self._dump(v)

    @property
    def verdict(self) -> dict:
        return self._load(self.verdict_json, {})

    @verdict.setter
    def verdict(self, v: dict) -> None:
        self.verdict_json = self._dump(v)

    @property
    def trace_summary(self) -> dict:
        return self._load(self.trace_summary_json, {})

    @trace_summary.setter
    def trace_summary(self, v: dict) -> None:
        self.trace_summary_json = self._dump(v)

    @property
    def analysis(self) -> dict:
        return self._load(self.analysis_json, {})

    @analysis.setter
    def analysis(self, v: dict) -> None:
        self.analysis_json = self._dump(v)

    @property
    def review(self) -> dict:
        return self._load(self.review_json, {})

    @review.setter
    def review(self, v: dict) -> None:
        self.review_json = self._dump(v)

    @property
    def verify(self) -> dict:
        return self._load(self.verify_json, {})

    @verify.setter
    def verify(self, v: dict) -> None:
        self.verify_json = self._dump(v)

    @property
    def upload(self) -> dict:
        return self._load(self.upload_json, {})

    @upload.setter
    def upload(self, v: dict) -> None:
        self.upload_json = self._dump(v)

    @property
    def qc(self) -> dict:
        return self._load(self.qc_json, {})

    @qc.setter
    def qc(self, v: dict) -> None:
        self.qc_json = self._dump(v)

    @property
    def dedup(self) -> dict:
        return self._load(self.dedup_json, {})

    @dedup.setter
    def dedup(self, v: dict) -> None:
        self.dedup_json = self._dump(v)


class RunEvent(Base, JsonMixin):
    """容器 stream-json 的逐条事件。payload 截断保存，完整轨迹以 jsonl 为准。"""

    __tablename__ = "run_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    kind: Mapped[str] = mapped_column(String(32))          # system / assistant / user / result / stderr / lifecycle
    summary: Mapped[str] = mapped_column(Text, default="")  # 供时间线直接展示的一行摘要
    payload_json: Mapped[str] = mapped_column(Text, default="{}")

    @property
    def payload(self) -> dict:
        return self._load(self.payload_json, {})


class DesignRun(Base, JsonMixin):
    """一次「设计 N 道题」：跑 Cursor CLI 的 /solo-prompt，再对产出查重。"""

    __tablename__ = "design_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default=DESIGN_QUEUED, index=True)
    model: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")        # 来源提示，拼进 /solo-prompt 参数
    log: Mapped[str] = mapped_column(Text, default="")         # agent 输出尾部，供界面查看
    error: Mapped[str] = mapped_column(Text, default="")
    stats_json: Mapped[str] = mapped_column(Text, default="{}")  # {parsed, imported, passed, discarded}
    task_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def stats(self) -> dict:
        return self._load(self.stats_json, {})

    @stats.setter
    def stats(self, v: dict) -> None:
        self.stats_json = self._dump(v)

    @property
    def task_ids(self) -> list:
        return self._load(self.task_ids_json, [])

    @task_ids.setter
    def task_ids(self, v: list) -> None:
        self.task_ids_json = self._dump(v)


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_enc: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
