"""数据模型。JSON 字段以 Text 存储，通过属性读写。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """把从库里读出来的时间补上 UTC 时区。

    列声明是 DateTime(timezone=True)，但 SQLite 不存时区，读回来一律是 naive。
    直接拿去和 utc_now() 相减会抛 TypeError，拿去 .timestamp() 则会被按本地时区
    解释而整体偏移。凡是参与算术的时间都要先过这里。
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class Base(DeclarativeBase):
    pass


# ---------------- 任务状态 ----------------
# 题级状态只描述「这道题走到哪一步」，单侧容器跑得怎样由 TaskRun.status 承担。
# 两层分开是因为 GSB 一题两跑：A 跑完 B 还在跑时题仍是 RUNNING，
# 若把 FINISHED/FAILED 留在题级，任一侧的结果都会把另一侧的状态盖掉。
AVAILABLE = "AVAILABLE"              # 题库中，未领取
CLAIMED = "CLAIMED"                  # 已领取，门禁未过或工作区未就绪
QUEUED = "QUEUED"                    # 两个 run 都在等槽位
RUNNING = "RUNNING"                  # 至少一个 run 在跑
RUN_DONE = "RUN_DONE"                # 两个 run 都结束，等 push 与分析
ANALYZING = "ANALYZING"              # GSB 对比进行中
ANALYZED = "ANALYZED"                # 有结论，等提交前质检（事实核验 + 措辞）
QC = "QC"                            # 质检已放行，等录屏与提交
UPLOADED = "UPLOADED"                # 已提交 solo2
DONE = "DONE"                        # 人工确认完成
NEEDS_ATTENTION = "NEEDS_ATTENTION"  # 重跑用尽或准备失败，等人工
DISCARDED = "DISCARDED"              # 人工废弃

ALL_STATUSES = (
    AVAILABLE, CLAIMED, QUEUED, RUNNING, RUN_DONE, ANALYZING, ANALYZED, QC,
    UPLOADED, DONE, NEEDS_ATTENTION, DISCARDED,
)
# 允许上传的状态。只有 QC —— 提交前质检是提交的必经一步，ANALYZED 表示它还没过。
# 把 ANALYZED 留在这里等于给绕过质检开一条路。
#
# 录屏齐不齐不由状态承担，由 submit_block 单独判。录屏是在外部录完之后贴进来的，
# 它不影响质检结论，所以不该决定题落在哪一栏 —— 早先按录屏推状态的做法把质检排到了
# 录屏后面，措辞一改就得重录一遍。
UPLOADABLE = frozenset({QC})
# 结论已经出来、还没提交的两个状态。质检放行与否决定题落在哪一个，见 gsb_precheck.sync_stage。
SETTLING = frozenset({ANALYZED, QC})

# 还可以往外发容器的题。RUNNING 必须在内：槽位按容器算，一道题的两侧各排各的队，
# A 先出闸把题带成 RUNNING 之后，B 仍然在队列里等自己那个槽。只认 QUEUED 的话，
# 凡是「一侧在跑、另一侧被退回重跑」的题，那一侧就再也发不出去了。
SCHEDULABLE = frozenset({QUEUED, RUNNING})
# 巡检还要盯着的题。已经分析完、交上去或废弃的题不必每轮再扫一遍它们的 run。
WATCHED = frozenset({QUEUED, RUNNING, RUN_DONE, NEEDS_ATTENTION})

# ---------------- 单侧运行状态 ----------------
# 取值字面量与题级的 QUEUED/RUNNING 同名，故常量名加 RUN_ 前缀区分；
# 比较时务必用常量而不是字面量，否则题级和侧级会混用。
RUN_PENDING = "PENDING"
RUN_QUEUED = "QUEUED"
RUN_RUNNING = "RUNNING"
RUN_FINISHED = "FINISHED"
RUN_FAILED = "FAILED"
RUN_TIMEOUT = "TIMEOUT"
RUN_INTERRUPTED = "INTERRUPTED"

RUN_END_STATUSES = frozenset({RUN_FINISHED, RUN_FAILED, RUN_TIMEOUT, RUN_INTERRUPTED})
# 只有 FINISHED 算正常结束；其余结束态由 watchdog 决定重跑还是废弃
RUN_OK_STATUSES = frozenset({RUN_FINISHED})
# 在等槽位的两种状态：刚建出来的是 PENDING，被退回重跑的是 QUEUED
RUN_WAITING = frozenset({RUN_PENDING, RUN_QUEUED})

ANALYSIS_IDLE = "IDLE"
ANALYSIS_RUNNING = "RUNNING"
ANALYSIS_DONE = "DONE"
ANALYSIS_FAILED = "FAILED"

# ---------------- 提交前质检 ----------------
# 质检这一步有两道，各记各的档，不能合成一个字段：一道查事实、一道查措辞，过不了的
# 原因和该做的动作完全不同。合成一档的话，界面上只能显示「质检没过」，而人分不出
# 该去核对轨迹还是该去改句子。
#
# ERROR 和 FAIL 也必须分开：FAIL 是判出了问题、该改内容；ERROR 是这道检查自己没跑成
# （模型超时、账单被拒、输出解不开），该做的是重跑。混成一档会让人跑去改一段没问题的话。

# 事实核验：理由里关于执行结果的话和轨迹对不对得上。见 gsb_factcheck。
FACTCHECK_IDLE = "IDLE"
FACTCHECK_RUNNING = "RUNNING"
FACTCHECK_PASS = "PASS"              # 与轨迹一致，或不符处已自动订正
FACTCHECK_FAIL = "FAIL"              # 报出了不符但没能自动订正，等人工
FACTCHECK_CONFIRMED = "CONFIRMED"    # 人工看过并放行
FACTCHECK_ERROR = "ERROR"            # 核验没跑完
FACTCHECK_OK = frozenset({FACTCHECK_PASS, FACTCHECK_CONFIRMED})

# 措辞质检：理由读起来像不像一个人写的。见 gsb_precheck。
PRECHECK_IDLE = "IDLE"              # 还没质检过
PRECHECK_RUNNING = "RUNNING"
PRECHECK_PASS = "PASS"              # 模型判读起来像人写的
PRECHECK_FAIL = "FAIL"              # 模型挑出了机械化表达，改完要人工确认
PRECHECK_CONFIRMED = "CONFIRMED"    # 人工看过并放行
PRECHECK_ERROR = "ERROR"            # 质检没跑完

# 放行提交的两档。是否真能提交还要看理由有没有在质检之后被改过，见 gsb_precheck.submit_block。
PRECHECK_OK = frozenset({PRECHECK_PASS, PRECHECK_CONFIRMED})

ORIGIN_BANK = "bank"        # 本机题面文件解析而来
ORIGIN_DESIGNED = "designed"  # 本机 /solo-prompt 刚出的
ORIGIN_POOL = "pool"        # 从远端题库拉下来的（可能是别的设备出的）

# 设计任务状态
DESIGN_QUEUED = "QUEUED"
DESIGN_RUNNING = "RUNNING"
DESIGN_DEDUP = "DEDUP"
DESIGN_DONE = "DONE"
DESIGN_FAILED = "FAILED"
DESIGN_CANCELLED = "CANCELLED"


def derive_task_status(runs: list["TaskRun"]) -> str | None:
    """按两侧 run 推出题级状态。两侧都不在运行阶段时返回 None，交给巡检判断。

    以前是谁动谁写：调度出闸写 RUNNING、重跑退回写 QUEUED。而「A 在跑、B 在等」
    是双跑最常见的组合，题级取哪个值全看最后一次写的是谁 —— 写成 RUNNING，B 就再也
    排不上队；写成 QUEUED，界面上一道正在跑的题却显示在排队。两种都错，所以题级状态
    不再由动作方各写各的，一律从两侧 run 现在的样子推。
    """
    if any(r.status == RUN_RUNNING for r in runs):
        return RUNNING
    if any(r.status in RUN_WAITING for r in runs):
        return QUEUED
    return None


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
    # 题块 meta 里的「仓库」。GSB 题要求仓库自带 main/A/B 三个分支，
    # clone 与分支校验都从这里取地址，不再从 user_prompt 里现场解析。
    repo_url: Mapped[str] = mapped_column(String(512), default="")

    # ---- 工作区准备 ----
    # 远端分支校验结果。校验失败题会停在 CLAIMED，把原因存下来是为了题卡能直接
    # 显示缺哪个分支，而不是让人翻日志。
    branch_check_json: Mapped[str] = mapped_column(Text, default="{}")
    # 废弃前的状态，恢复时按它回退；不属于单跑字段，所以留在题级
    discarded_from: Mapped[str] = mapped_column(String(16), default="")

    # ---- GSB 分析 / 结论 ----
    # 容器、会话、result、verdict 这些「一次跑」的信息全在 TaskRun 上，
    # 题级只放对比两侧才得出的东西。
    analysis_status: Mapped[str] = mapped_column(String(16), default=ANALYSIS_IDLE)
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")     # GSB 分析 agent 的原始输出
    # 人工可编辑的结论：verdict / reason / a_startup / b_startup。
    # 前身是五维评分的 review_json，语义完全变了，直接换名而不是复用旧列名，
    # 避免旧代码按五维结构去读它。
    gsb_json: Mapped[str] = mapped_column(Text, default="{}")
    verify_json: Mapped[str] = mapped_column(Text, default="{}")       # GSB 核验报告
    # solo-qa 的 GSB 质检结论，含 AI 化评分与命中的规则号。
    #
    # 自动流程已经不写它了：那一步要给每道题起一个 solo2-backend 容器跑几分钟，
    # 而换回来的结论和提交之后平台自己给的是同一份，等于把平台的活先干一遍。
    # 列留着是因为历史数据在里面，手动调 qa_bridge.gsb_qc 对口径时也还会写。
    #
    # 叫 gsb_qc_json 而不是 qc_json：后者是五维质检时代的列，已经废弃删掉了，名字重用
    # 会让老库里残留的旧格式数据被当成新结论读出来。
    gsb_qc_json: Mapped[str] = mapped_column(Text, default="{}")
    # 两侧录屏链接 {"A": url, "B": url}，平台上传必填，由人工录完后填入
    screencast_json: Mapped[str] = mapped_column(Text, default="{}")
    # 提交前质检：理由读起来像不像人写的。与上面两个都不重复 —— verify_json 判确定性
    # 规则（字数、步号、markdown），gsb_qc_json 是平台口径的质检，这里判的是措辞和句子，
    # 正则和平台规则都碰不到那一类毛病（见 gsb_precheck 模块说明）。
    precheck_status: Mapped[str] = mapped_column(String(16), default=PRECHECK_IDLE)
    precheck_json: Mapped[str] = mapped_column(Text, default="{}")
    # 事实核验：理由里关于执行结果的断言和轨迹对不对得上。和上面三个都不重复 ——
    # verify_json 判格式、gsb_qc_json 是平台口径、precheck_json 判措辞，
    # 「说的是不是真的」三者一个都碰不到（见 gsb_factcheck 模块说明）。
    factcheck_status: Mapped[str] = mapped_column(String(16), default=FACTCHECK_IDLE)
    factcheck_json: Mapped[str] = mapped_column(Text, default="{}")
    # 难度筛选结论：两侧的步数与用时，加当时那套阈值。见 difficulty 模块说明。
    # 不另立状态：判废弃就走 DISCARDED，那套废弃、恢复、列表过滤已经现成。而结论要留下来，
    # 一道题事后被问起「这么简单为什么还评了」或者「凭什么把它废了」，凭据只有这四个数。
    # 列名不叫 screen_json：题级已经有个 screencast_json 是录屏链接，两个名字摆在一起读代码
    # 的人分不清哪个是哪个；也不叫 difficulty_json，那会和题面自带的 difficulty 撞。
    difficulty_screen_json: Mapped[str] = mapped_column(Text, default="{}")
    # 开跑前的改动面体检：题面要动哪几个模块，加当时的题面指纹。见 scope 模块说明。
    # 和上面那条是一前一后两道关，都在拦难度不够的题，所以两个字段挨着放。
    scope_json: Mapped[str] = mapped_column(Text, default="{}")
    upload_json: Mapped[str] = mapped_column(Text, default="{}")

    # ---- 队列与来源 ----
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)   # 越小越先出队
    origin: Mapped[str] = mapped_column(String(16), default=ORIGIN_BANK)
    # 这道题在远端题库里的条目 id（pool.Entry.id）。领取要拿它去远端占位，没有这个值
    # 的题就是纯本机题（池没启用时导入的），领取不走跨设备独占。
    pool_entry_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    # 出这道题的设备。与本机标识不同就是别的设备出的，题号带设备后缀，见 pool.local_task_no。
    pool_device: Mapped[str] = mapped_column(String(64), default="")
    # 远端登记的领取者。本机领到时写自己的标识，释放后清空。做题进度不看它 —— 远端只
    # 管「这道题归谁」，归属之后走到哪一步由本机的 status 说了算。
    claimed_by: Mapped[str] = mapped_column(String(64), default="")
    design_run_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    dedup_json: Mapped[str] = mapped_column(Text, default="{}")             # 设计产出的查重结论
    # 自动流水线当前卡在哪一步，仅供界面展示；取值由流水线模块自行定义
    auto_stage: Mapped[str] = mapped_column(String(16), default="")
    auto_error: Mapped[str] = mapped_column(Text, default="")

    # ---- 时间 ----
    # started_at 不在题级：两侧各有自己的开始时间，题级没有一个有意义的「开始」。
    # finished_at 则是两侧都结束的时刻，题级保留。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    def gsb(self) -> dict:
        return self._load(self.gsb_json, {})

    @gsb.setter
    def gsb(self, v: dict) -> None:
        self.gsb_json = self._dump(v)

    @property
    def verify(self) -> dict:
        return self._load(self.verify_json, {})

    @verify.setter
    def verify(self, v: dict) -> None:
        self.verify_json = self._dump(v)

    @property
    def gsb_qc(self) -> dict:
        return self._load(self.gsb_qc_json, {})

    @gsb_qc.setter
    def gsb_qc(self, v: dict) -> None:
        self.gsb_qc_json = self._dump(v)

    @property
    def screencast(self) -> dict:
        return self._load(self.screencast_json, {})

    @screencast.setter
    def screencast(self, v: dict) -> None:
        self.screencast_json = self._dump(v)

    @property
    def precheck(self) -> dict:
        return self._load(self.precheck_json, {})

    @precheck.setter
    def precheck(self, v: dict) -> None:
        self.precheck_json = self._dump(v)

    @property
    def factcheck(self) -> dict:
        return self._load(self.factcheck_json, {})

    @factcheck.setter
    def factcheck(self, v: dict) -> None:
        self.factcheck_json = self._dump(v)

    @property
    def difficulty_screen(self) -> dict:
        return self._load(self.difficulty_screen_json, {})

    @difficulty_screen.setter
    def difficulty_screen(self, v: dict) -> None:
        self.difficulty_screen_json = self._dump(v)

    @property
    def scope(self) -> dict:
        return self._load(self.scope_json, {})

    @scope.setter
    def scope(self, v: dict) -> None:
        self.scope_json = self._dump(v)

    @property
    def upload(self) -> dict:
        return self._load(self.upload_json, {})

    @upload.setter
    def upload(self, v: dict) -> None:
        self.upload_json = self._dump(v)

    @property
    def analysis(self) -> dict:
        return self._load(self.analysis_json, {})

    @analysis.setter
    def analysis(self, v: dict) -> None:
        self.analysis_json = self._dump(v)

    @property
    def dedup(self) -> dict:
        return self._load(self.dedup_json, {})

    @dedup.setter
    def dedup(self, v: dict) -> None:
        self.dedup_json = self._dump(v)

    @property
    def branch_check(self) -> dict:
        return self._load(self.branch_check_json, {})

    @branch_check.setter
    def branch_check(self, v: dict) -> None:
        self.branch_check_json = self._dump(v)


class TaskRun(Base, JsonMixin):
    """一道题的一次跑（A 或 B）。一题固定两行，从 clone 到 push 的状态都在这里。

    单跑时代这些列全挂在 Task 上；改成双跑后若继续放题级，就得给每列复制一份
    带 a_/b_ 前缀的版本，调度、watchdog、时间线全都要写两套分支。拆成按 side 分行，
    所有只关心「一次跑」的代码拿到一行 TaskRun 就够了，不必知道自己是 A 还是 B。
    """

    __tablename__ = "task_run"
    # (task_id, side) 唯一：调度器和 watchdog 都会在并发下尝试建 run，
    # 靠数据库约束兜底而不是靠应用层「先查再插」。
    __table_args__ = (UniqueConstraint("task_id", "side", name="uq_run_task_side"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    side: Mapped[str] = mapped_column(String(1), index=True)   # 取值见 config.SIDES
    status: Mapped[str] = mapped_column(String(16), default=RUN_PENDING, index=True)
    # 第几次跑。重跑加一，达到上限后整道题废弃。
    # server_default 不能省：_ensure_columns 给没有 DDL 默认值的整型列补的是 DEFAULT 0，
    # 补出来的第 0 次会让重跑计数错位。
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # 其中有几次是跑超时的。超时单独计数是因为它的代价跟别的异常不是一个量级：
    # 一次超时要整整烧掉 timeout_minutes，连着两次就是四个小时的机器时间换一份没有的
    # 结果，所以它的容忍次数比普通重跑更低，先撞到哪个上限就按哪个废弃。
    timeouts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    container_name: Mapped[str] = mapped_column(String(64), default="")
    container_exists: Mapped[bool] = mapped_column(Boolean, default=False)
    image_tag: Mapped[str] = mapped_column(String(128), default="")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session_id: Mapped[str] = mapped_column(String(128), default="")
    turn_id: Mapped[str] = mapped_column(String(128), default="")

    result_json: Mapped[str] = mapped_column(Text, default="{}")        # stream-json 的 result 事件
    verdict_json: Mapped[str] = mapped_column(Text, default="{}")       # 三层判定明细
    trace_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    trace_file: Mapped[str] = mapped_column(String(512), default="")    # 导出后的 jsonl 路径
    git_diff_stat: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    # push 之后回填，是上传要交的产物快照。存 sha 而不只存分支名，
    # 是因为分支可能被后续重跑覆盖，而平台要的是当时评的那份代码。
    artifact_sha: Mapped[str] = mapped_column(String(64), default="")
    artifact_url: Mapped[str] = mapped_column(String(512), default="")

    # watchdog 判定为异常时记原因与时间，题卡要显示
    abnormal_json: Mapped[str] = mapped_column(Text, default="{}")
    # 人按过停止。这件事必须落库：它以前只是 runner 里的一个内存集合，后端一重启、
    # 或者容器换了协程接管，标记就没了，于是人按的停止在收尾时被当成异常结束，
    # watchdog 转头把这一侧整个清掉重跑 —— 人看到的是「我明明停了它，它自己又跑起来了」，
    # 而且刚改的配置会被那次重跑盖掉。
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    def abnormal(self) -> dict:
        return self._load(self.abnormal_json, {})

    @abnormal.setter
    def abnormal(self, v: dict) -> None:
        self.abnormal_json = self._dump(v)


class RunEvent(Base, JsonMixin):
    """容器 stream-json 的逐条事件。payload 截断保存，完整轨迹以 jsonl 为准。"""

    __tablename__ = "run_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    # 事件流按 A/B 分栏展示，靠这列区分。挂 task_id 而不是 run_id，
    # 是因为重跑会换 run 的 attempt 但事件仍归同一侧，按 (task_id, side) 查最直接。
    # server_default 写裸的 A 而不是 'A'：SQLAlchemy 编译 DDL 时会自己给字符串加引号，
    # 写成 'A' 会被编成 DEFAULT '''A'''，_ensure_columns 补列时老行的 side 就成了三个字符的 'A'。
    side: Mapped[str] = mapped_column(String(1), default="A", server_default="A")
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
