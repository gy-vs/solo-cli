# GSB 双跑流程改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把一题单跑的流水线改造成一题双跑（A/B）、自动 GSB 对比、上传 solo2 平台的流水线。

**Architecture:** `Task` 瘦身为题面，新增 `TaskRun` 表一题两行；调度、运行、门禁全部下沉到 run 粒度；
新增 watchdog 作为唯一决策点，负责异常重跑与配对触发分析；分析、核验、上传三个模块围绕 GSB 口径重写。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（同步 Session）+ SQLite，Vue 3 + TypeScript + Vite，
Docker CLI 子进程，Cursor CLI（`agent -p`），pytest。

设计文档：`docs/superpowers/specs/2026-09-17-gsb-dual-run-design.md`。
平台字段样本：`docs/gsb-form-schema.sample.json`（仅供参考，运行时必须实时拉 schema）。

## Global Constraints

以下数值和格式直接来自 solo2 平台的判定规则，全部任务都受约束，不许改写：

- side 取值只有 `"A"` 和 `"B"` 两个字面量（大写），分支名同样是大写的 `A`、`B`。
- 仓库必须有且仅有三个分支：主分支（`main` 或 `master`）加 `A`、`B`。不合规一律阻断（规则 G2）。
- 产物快照的父提交必须等于初始环境快照的 SHA（规则 G3）。
- commit permalink 的格式正则：`^https://github\.com/[^/\s]+/[^/\s]+/commit/[0-9a-fA-F]{40}/?$`。
- `difficulty` 只允许 `"困难"` 和 `"地狱"`（规则 G1）。
- `question_type` 只允许这 7 个值，注意没有空格：`"0-1代码生成"`、`"feature迭代"`、`"Bug修复"`、
  `"代码理解"`、`"代码重构"`、`"工程化"`、`"代码测试"`。
- `harness` 固定 `"Claude Code"`；`os_platform` 固定 `"MacOS/Linux"`。
- `repro_level` 只允许 `"无外部依赖"`、`"有外部依赖，未容器化"`、`"已容器化，可一键起环境"`。
- `gsb_verdict` 只允许 `"A 更好"`、`"Same"`、`"B 更好"`。
- `validity` 只允许 `"有效"`、`"作废-工程故障"`、`"作废-环境未重置"`、`"作废-其他"`。
- `gsb_reason` 去掉全部空白字符后至少 60 字（平台 R=60）；本项目对 `Same` 额外要求 150 字。
- A 与 B 的 `session_id` 不能相同，`artifact_snapshot` 不能相同（规则 G9）。
- 一次跑只允许一个轨迹文件（规则 T4）；轨迹里真人输入必须恰好一轮（规则 T5）。
  **续跑机制整体删除，不许保留任何续跑代码路径。**
- 自动重跑上限默认 3 次重跑，即一个 run 最多跑 4 次（`attempt` 从 1 起，达到 4 后停止）。
- 上传接口 `POST /api/v1/gsb/submissions`，body 形如 `{"data": {...}, "schema_fingerprint": "..."}`。
  字段清单必须实时从 `GET /api/v1/gsb/form-schema` 拉取，不许硬编码字段列表。
- GSB 理由的写作要求：第一人称、口语、无 markdown、无表情符号、无绝对路径、无「第 N 步」这类
  步数说法、A 和 B 分别写优劣。推理时长、无报错的戛然而止、网络工程错误这三类不许纳入判断。
- 项目已有代码注释一律中文，新代码沿用同样风格：注释解释「为什么」，不解释「这行干了啥」。

---

## 文件结构

**新建**

| 文件 | 职责 |
|---|---|
| `backend/app/services/gsb_repo.py` | 远端分支探测、双分支 clone、reset 回快照、commit + push 拿产物快照 |
| `backend/app/services/watchdog.py` | 5 分钟周期任务：异常重跑 + 配对触发分析，唯一决策点 |
| `backend/app/services/gsb_analyzer.py` | Cursor CLI 跑 GSB 对比，产出结论、理由、两份启动方式 |
| `backend/app/services/gsb_verifier.py` | 本地预核验，把平台规则先过一遍 |
| `backend/app/services/gsb_uploader.py` | 拉 schema、填字段、传轨迹、提交 solo2 |

**大改**

| 文件 | 改动 |
|---|---|
| `backend/app/config.py` | `TaskPaths` 从 `round_no` 改 `side` |
| `backend/app/models.py` | `Task` 瘦身、新增 `TaskRun`、`RunEvent.side`、新状态常量 |
| `backend/app/services/gate.py` | 检查项按双跑重写 |
| `backend/app/services/runner.py` | `run_task` → `run_side`，结果落 `TaskRun`，删续跑 |
| `backend/app/services/scheduler.py` | 调度单位改 run，成对出队，删同项目互斥 |
| `backend/app/services/settings_store.py` | 设置项增删 |
| `backend/app/routers/tasks.py` | 接口按双跑重写 |
| `backend/app/schemas.py` | 出参结构重写 |
| `backend/app/main.py` | 接线 watchdog，去掉 pipeline |
| 前端 `api.ts` / `store.ts` / `Bank.vue` / `TaskCard.vue` / `TaskDetail.vue` / `Queue.vue` / `Settings.vue` | 按双跑重写 |

**删除**

`backend/app/services/{analyzer,verifier,uploader,pipeline,task_reset,repo}.py`、
`backend/bridges/qa_qc.py`、`qa_bridge.py` 的质检部分、
前端 `components/{ScoreEditor,VerifyBar,QcPanel}.vue`、
测试 `test_{desc_sanitize,trace_and_verify,continue_round,repo_commit,repo_siblings,reset_backfill,finalize,runner_status,runner_lines,task_branch}.py`。

---

### Task 1: 路径与设置项

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/settings_store.py`
- Test: `backend/tests/test_paths.py`（新建）

**Interfaces:**
- Produces: `config.SIDES = ("A", "B")`；`config.TaskPaths(task_no: str, side: str = "A")`，
  属性 `workspace`、`traces`、`analysis`、`analysis_repo`、`trace_index`、`export`、
  `workspace_host`、`traces_host`、`container_name`。
  `analysis` 不带 side（两侧共用一个分析目录），其余全部带 side。
- Produces: 设置键 `watchdog.interval_seconds`（默认 `"300"`）、`watchdog.max_retries`（默认 `"3"`）、
  `gsb.base_url`（默认 `"https://solo2.jzxhnh.com"`）、`gsb.session_cookie`、`gsb.csrf_token`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_paths.py
import pytest

from app import config


def test_paths_split_by_side():
    a = config.TaskPaths("07", "A")
    b = config.TaskPaths("07", "B")
    assert a.workspace.name == "A" and a.workspace.parent.name == "07"
    assert b.workspace.name == "B"
    assert a.traces.name == "A" and a.traces.parent.name == "07"
    assert a.container_name == "solo-cc-07-A"
    assert b.container_name == "solo-cc-07-B"
    assert a.export.name == "A" and a.export.parent.name == "07"


def test_analysis_dir_is_shared_but_repo_is_not():
    a = config.TaskPaths("07", "A")
    b = config.TaskPaths("07", "B")
    assert a.analysis == b.analysis
    assert a.analysis_repo.name == "repo-A"
    assert b.analysis_repo.name == "repo-B"
    assert a.trace_index.name == "trace_index_A.json"


def test_host_paths_use_host_root():
    a = config.TaskPaths("07", "A")
    assert a.workspace_host == f"{config.CODER_ROOT_HOST}/workspace/07/A"
    assert a.traces_host == f"{config.CODER_ROOT_HOST}/出题/轨迹/07/A"


def test_side_is_validated():
    with pytest.raises(ValueError):
        config.TaskPaths("07", "C")
    # 小写要能自动大写，别让调用方到处 .upper()
    assert config.TaskPaths("07", "a").side == "A"


def test_no_round_suffix_left():
    assert not hasattr(config.TaskPaths("07", "A"), "round_suffix")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_paths.py -v`
Expected: FAIL，`TaskPaths.__init__() takes ... 'round_no'` 或 `AttributeError: analysis_repo`

- [ ] **Step 3: 改 `config.py`**

把 `TaskPaths` 整个替换成：

```python
SIDES = ("A", "B")


class TaskPaths:
    """一道题某一侧（A 或 B）涉及的全部目录，同时给出宿主路径与挂载路径。

    A 和 B 是同一道题在同一个起点上的两次独立运行，代码、轨迹、容器全部分开，
    只有分析目录共用一个——GSB 对比要同时看两边，放一起省得来回跳。
    """

    def __init__(self, task_no: str, side: str = "A"):
        side = (side or "").upper()
        if side not in SIDES:
            raise ValueError(f"side 必须是 A 或 B，收到 {side!r}")
        self.task_no = task_no
        self.side = side

    # ---- 后端可读写的路径 ----
    @property
    def workspace(self) -> Path:
        return CODER_ROOT_MOUNT / WORKSPACE_DIR / self.task_no / self.side

    @property
    def traces(self) -> Path:
        return CODER_ROOT_MOUNT / TRACES_DIR / self.task_no / self.side

    @property
    def analysis(self) -> Path:
        return CODER_ROOT_MOUNT / ANALYSIS_DIR / self.task_no

    @property
    def analysis_repo(self) -> Path:
        return self.analysis / f"repo-{self.side}"

    @property
    def trace_index(self) -> Path:
        return self.analysis / f"trace_index_{self.side}.json"

    @property
    def export(self) -> Path:
        return EXPORT_DIR / self.task_no / self.side

    @property
    def prompt_archive(self) -> Path:
        return CODER_ROOT_MOUNT / PROMPTS_ARCHIVE_DIR / f"{self.task_no}.md"

    # ---- 传给 docker -v 的宿主路径 ----
    @property
    def workspace_host(self) -> str:
        return f"{CODER_ROOT_HOST}/{WORKSPACE_DIR}/{self.task_no}/{self.side}"

    @property
    def traces_host(self) -> str:
        return f"{CODER_ROOT_HOST}/{TRACES_DIR}/{self.task_no}/{self.side}"

    @property
    def container_name(self) -> str:
        return f"{CONTAINER_NAME_PREFIX}{self.task_no}-{self.side}"
```

删掉 `round_suffix`、`slug`、`export_host` 三个属性（`export_host` 没有调用方了，质检已删）。

- [ ] **Step 4: 改 `settings_store.py` 的 `SPECS`**

删掉这些项：`qa.base_url`、`qa.session_cookie`、`qa.csrf_token`、`auto.qc`、`qc.enabled`、
`git.commit_on_upload`、`git.task_branch`。

`qc.project_host`、`qc.image`、`qc.timeout_minutes` 保留（出题查重还要用它挂 solo-qa 源码），
但 group 从 `"solo-qa 质检"` 改成 `"题目查重"`。

新增与改动：

```python
    Spec("gsb.base_url", "solo2 平台地址", "GSB 平台", default="https://solo2.jzxhnh.com"),
    Spec("gsb.session_cookie", "solo_qa_session", "GSB 平台", secret=True,
         help="solo2.jzxhnh.com 的浏览器 Cookie，注意与旧站点不是一套"),
    Spec("gsb.csrf_token", "solo_qa_csrf", "GSB 平台", secret=True,
         help="Cookie 中 solo_qa_csrf 的值，同时作为 X-CSRF-Token 头"),
    Spec("watchdog.interval_seconds", "守护扫描间隔（秒）", "守护", default="300", kind="number",
         help="扫异常重跑与配对触发分析；run 一结束会立刻唤醒一次，这个间隔只是兜底"),
    Spec("watchdog.max_retries", "自动重跑次数上限", "守护", default="3", kind="number",
         help="指重跑次数，一个 run 最多跑 4 次；用尽后停下等人工"),
```

`scheduler.max_parallel` 的 label 改成 `"最大并发容器数"`，default 改成 `"4"`，
help 补一句 `"一道题占两个（A 与 B 成对启动），所以这里填偶数比较合适"`。

`auto.analyze` 的 label 改成 `"两边跑完后自动 GSB 分析"`。

同步改 `config.SEED_ENV`：`qa.session_cookie` / `qa.csrf_token` 两个键改成
`gsb.session_cookie` / `gsb.csrf_token`，环境变量名保持 `QA_SESSION_COOKIE` / `QA_CSRF_TOKEN` 不变。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_paths.py tests/test_settings_store.py -v`
Expected: PASS。`test_settings_store.py` 里如果断言了被删掉的键，一并改掉。

- [ ] **Step 6: 提交**

```bash
git add backend/app/config.py backend/app/services/settings_store.py backend/tests/test_paths.py
git commit -m "func(gsb): 路径按 A/B 分侧，设置项切到 GSB 平台与守护"
```

---

### Task 2: 数据模型

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models_gsb.py`（新建）
- Delete: `backend/tests/test_time_utc.py` 里针对 `Task.round_no` 的用例（若有）

**Interfaces:**
- Consumes: `config.SIDES`（Task 1）
- Produces:
  - Task 状态常量：`AVAILABLE`、`CLAIMED`、`QUEUED`、`RUNNING`、`RUN_DONE`、`ANALYZING`、
    `ANALYZED`、`UPLOADED`、`DONE`、`NEEDS_ATTENTION`、`DISCARDED`
  - Run 状态常量：`RUN_PENDING`、`RUN_QUEUED`、`RUN_RUNNING`、`RUN_FINISHED`、`RUN_FAILED`、
    `RUN_TIMEOUT`、`RUN_INTERRUPTED`；集合 `RUN_END_STATUSES`、`RUN_OK_STATUSES = {RUN_FINISHED}`
  - `class TaskRun(Base, JsonMixin)`，字段见下；JSON 属性 `result`、`verdict`、`trace_summary`、`abnormal`
  - `Task` 的 JSON 属性：`meta`、`gsb`、`verify`、`screencast`、`upload`、`analysis`、`dedup`、`branch_check`
  - `RunEvent.side`（`String(1)`，默认 `"A"`，`server_default="'A'"`）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_models_gsb.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models as m


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    m.Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_task_run_unique_per_side(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    db.flush()
    db.add(m.TaskRun(task_id=t.id, side="A"))
    db.add(m.TaskRun(task_id=t.id, side="B"))
    db.flush()
    db.add(m.TaskRun(task_id=t.id, side="A"))
    with pytest.raises(Exception):
        db.flush()


def test_task_run_defaults(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    db.flush()
    r = m.TaskRun(task_id=t.id, side="A")
    db.add(r)
    db.flush()
    assert r.status == m.RUN_PENDING
    assert r.attempt == 1
    assert r.artifact_sha == "" and r.artifact_url == ""
    assert r.verdict == {} and r.abnormal == {}


def test_task_run_json_roundtrip(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    db.flush()
    r = m.TaskRun(task_id=t.id, side="B")
    db.add(r)
    r.verdict = {"process": {"exit_code": 0}}
    r.abnormal = {"reason": "没有产出轨迹", "at": "2026-09-17T00:00:00Z"}
    db.flush()
    assert r.verdict["process"]["exit_code"] == 0
    assert r.abnormal["reason"] == "没有产出轨迹"


def test_task_gsb_fields(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    t.gsb = {"verdict": "A", "reason": "x"}
    t.screencast = {"A": "https://a", "B": "https://b"}
    t.branch_check = {"ok": True, "branches": ["main", "A", "B"]}
    db.flush()
    assert t.gsb["verdict"] == "A"
    assert t.screencast["B"] == "https://b"
    assert t.branch_check["branches"] == ["main", "A", "B"]


def test_run_event_has_side_not_round(db):
    e = m.RunEvent(task_id=1, seq=1, side="B", kind="system", summary="x")
    db.add(e)
    db.flush()
    assert e.side == "B"
    assert not hasattr(e, "round_no")


def test_dropped_task_columns_are_gone():
    dropped = {"session_id", "turn_id", "round_no", "rounds_json", "continue_prompt",
               "container_name", "container_exists", "image_tag", "exit_code",
               "result_json", "verdict_json", "trace_summary_json", "trace_file",
               "git_diff_stat", "review_json", "qc_status", "qc_json", "qc_at"}
    assert dropped & set(m.Task.__table__.columns.keys()) == set()


def test_task_statuses_cover_gsb_flow():
    for s in (m.RUN_DONE, m.ANALYZING, m.ANALYZED, m.NEEDS_ATTENTION):
        assert s in m.ALL_STATUSES
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_models_gsb.py -v`
Expected: FAIL，`AttributeError: module 'app.models' has no attribute 'TaskRun'`

- [ ] **Step 3: 改 `models.py`**

状态常量段整个替换：

```python
# ---------------- 任务状态 ----------------
AVAILABLE = "AVAILABLE"              # 题库中，未领取
CLAIMED = "CLAIMED"                  # 已领取，门禁未过或工作区未就绪
QUEUED = "QUEUED"                    # 两个 run 都在等槽位
RUNNING = "RUNNING"                  # 至少一个 run 在跑
RUN_DONE = "RUN_DONE"                # 两个 run 都结束，等 push 与分析
ANALYZING = "ANALYZING"              # GSB 对比进行中
ANALYZED = "ANALYZED"                # 有结论，等录屏与上传
UPLOADED = "UPLOADED"                # 已提交 solo2
DONE = "DONE"                        # 人工确认完成
NEEDS_ATTENTION = "NEEDS_ATTENTION"  # 重跑用尽或准备失败，等人工
DISCARDED = "DISCARDED"              # 人工废弃

ALL_STATUSES = (
    AVAILABLE, CLAIMED, QUEUED, RUNNING, RUN_DONE, ANALYZING, ANALYZED,
    UPLOADED, DONE, NEEDS_ATTENTION, DISCARDED,
)
# 允许上传的状态
UPLOADABLE = frozenset({ANALYZED})

# ---------------- 单侧运行状态 ----------------
RUN_PENDING = "PENDING"
RUN_QUEUED = "QUEUED"
RUN_RUNNING = "RUNNING"
RUN_FINISHED = "FINISHED"
RUN_FAILED = "FAILED"
RUN_TIMEOUT = "TIMEOUT"
RUN_INTERRUPTED = "INTERRUPTED"

RUN_END_STATUSES = frozenset({RUN_FINISHED, RUN_FAILED, RUN_TIMEOUT, RUN_INTERRUPTED})
RUN_OK_STATUSES = frozenset({RUN_FINISHED})

ANALYSIS_IDLE = "IDLE"
ANALYSIS_RUNNING = "RUNNING"
ANALYSIS_DONE = "DONE"
ANALYSIS_FAILED = "FAILED"

ORIGIN_BANK = "bank"
ORIGIN_DESIGNED = "designed"
```

删掉 `FINISHED`/`FAILED`/`TIMEOUT`/`INTERRUPTED`/`REVIEWED` 这几个 Task 级常量，
删掉 `ANALYZABLE`、`CONTINUABLE`、全部 `QC_*` 常量、全部 `STAGE_*` 常量。
`DESIGN_*` 常量保留不动。

`Task` 按设计文档 3.1 节增删列：新增
`repo_url: Mapped[str] = mapped_column(String(512), default="")`、
`branch_check_json`、`gsb_json`、`screencast_json`，
把 `review_json` 改名成 `gsb_json`（语义变了，直接换名不要留旧列），
删掉设计文档列出的那一批列，并同步删掉它们的 JSON 属性
（`result`、`verdict`、`trace_summary`、`review`、`qc`、`rounds`）。
新增属性照抄现有 `meta` 的写法：

```python
    @property
    def gsb(self) -> dict:
        return self._load(self.gsb_json, {})

    @gsb.setter
    def gsb(self, v: dict) -> None:
        self.gsb_json = self._dump(v)

    @property
    def screencast(self) -> dict:
        return self._load(self.screencast_json, {})

    @screencast.setter
    def screencast(self, v: dict) -> None:
        self.screencast_json = self._dump(v)

    @property
    def branch_check(self) -> dict:
        return self._load(self.branch_check_json, {})

    @branch_check.setter
    def branch_check(self, v: dict) -> None:
        self.branch_check_json = self._dump(v)
```

新增 `TaskRun`：

```python
class TaskRun(Base, JsonMixin):
    """一道题的一次跑（A 或 B）。一题固定两行，从 clone 到 push 的状态都在这里。"""

    __tablename__ = "task_run"
    __table_args__ = (UniqueConstraint("task_id", "side", name="uq_run_task_side"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    side: Mapped[str] = mapped_column(String(1), index=True)
    status: Mapped[str] = mapped_column(String(16), default=RUN_PENDING, index=True)
    # 第几次跑。重跑加一，达到上限后 watchdog 不再自动重跑
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    container_name: Mapped[str] = mapped_column(String(64), default="")
    container_exists: Mapped[bool] = mapped_column(Boolean, default=False)
    image_tag: Mapped[str] = mapped_column(String(128), default="")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session_id: Mapped[str] = mapped_column(String(128), default="")
    turn_id: Mapped[str] = mapped_column(String(128), default="")

    result_json: Mapped[str] = mapped_column(Text, default="{}")
    verdict_json: Mapped[str] = mapped_column(Text, default="{}")
    trace_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    trace_file: Mapped[str] = mapped_column(String(512), default="")
    git_diff_stat: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    # push 之后回填，是上传要交的产物快照
    artifact_sha: Mapped[str] = mapped_column(String(64), default="")
    artifact_url: Mapped[str] = mapped_column(String(512), default="")

    # watchdog 判定为异常时记原因与时间，题卡要显示
    abnormal_json: Mapped[str] = mapped_column(Text, default="{}")

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
```

`RunEvent` 的 `round_no` 换成：

```python
    side: Mapped[str] = mapped_column(String(1), default="A", server_default="'A'")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_models_gsb.py -v`
Expected: 7 passed

- [ ] **Step 5: 删掉库文件，确认建表干净**

```bash
cd backend && rm -f data/solo-cli.db && python -c "
from app.db import init_db, engine
from sqlalchemy import inspect
init_db()
print(sorted(inspect(engine).get_table_names()))
print(sorted(c['name'] for c in inspect(engine).get_columns('task_run')))
"
```
Expected: 表里有 `task_run`，且 `task` 表不含 `round_no`、`qc_status` 这些列。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/tests/test_models_gsb.py
git commit -m "func(gsb): Task 瘦身并新增 TaskRun，事件按 A/B 分侧"
```

---

### Task 3: 仓库分支探测与双分支 clone

**Files:**
- Create: `backend/app/services/gsb_repo.py`
- Test: `backend/tests/test_gsb_repo_branches.py`（新建）

**Interfaces:**
- Consumes: `config.TaskPaths`（Task 1）、`dockerx.run`、`settings_store.get`
- Produces:
  - `MAIN_NAMES = ("main", "master")`
  - `COMMIT_URL_RE: re.Pattern`，值为 Global Constraints 里那条正则
  - `parse_repo_url(meta: dict) -> str`
  - `repo_slug(repo_url: str) -> str` 返回 `"org/repo"`，解析不出来返回 `""`
  - `commit_url(repo_url: str, sha: str) -> str`
  - `snapshot_sha(env_snapshot: str) -> str`（从 `gate.py` 搬过来，`gate` 改为从这里导入）
  - `authed_url(repo_url: str, token: str) -> str`
  - `@dataclass BranchProbe: ok: bool; branches: list[str]; main: str; message: str`
  - `async probe_branches(repo_url: str) -> BranchProbe`
  - `async clone_side(task_no: str, repo_url: str, side: str) -> dict`
    返回 `{"ok": bool, "message": str, "reused": bool}`
  - `async verify_head(task_no: str, side: str, snapshot: str) -> dict`
    返回 `{"ok": bool, "head": str, "dirty": int, "message": str}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_gsb_repo_branches.py
import asyncio
import subprocess

import pytest

from app import config
from app.services import gsb_repo


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def origin(tmp_path, monkeypatch):
    """造一个本地裸仓库当远端，带 main/A/B 三个分支，都指向同一个初始提交。"""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    (work / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    sha = subprocess.run(["git", "-C", str(work), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    _git(work, "branch", "A")
    _git(work, "branch", "B")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(work), str(bare)],
                   check=True, capture_output=True, text=True)
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(config, "CODER_ROOT_HOST", str(tmp_path / "coder"))
    monkeypatch.setattr(gsb_repo.settings_store, "get", lambda k: "")
    return {"url": str(bare), "sha": sha}


def test_repo_slug_and_commit_url():
    url = "https://github.com/acme/widget.git"
    assert gsb_repo.repo_slug(url) == "acme/widget"
    sha = "a" * 40
    assert gsb_repo.commit_url(url, sha) == f"https://github.com/acme/widget/commit/{sha}"
    assert gsb_repo.COMMIT_URL_RE.match(gsb_repo.commit_url(url, sha))


def test_repo_slug_handles_ssh_and_trailing_slash():
    assert gsb_repo.repo_slug("git@github.com:acme/widget.git") == "acme/widget"
    assert gsb_repo.repo_slug("https://github.com/acme/widget/") == "acme/widget"
    assert gsb_repo.repo_slug("not-a-url") == ""


def test_parse_repo_url_from_meta():
    assert gsb_repo.parse_repo_url({"仓库": "https://github.com/acme/widget"}) == \
        "https://github.com/acme/widget"
    assert gsb_repo.parse_repo_url({}) == ""


def test_snapshot_sha():
    sha = "b" * 40
    assert gsb_repo.snapshot_sha(f"https://github.com/a/b/commit/{sha}") == sha
    assert gsb_repo.snapshot_sha("https://github.com/a/b/commit/short") == ""


def test_authed_url_injects_token():
    got = gsb_repo.authed_url("https://github.com/acme/widget", "tok")
    assert got == "https://x-access-token:tok@github.com/acme/widget"
    # 没 token 就原样返回，本地路径也不许被改坏
    assert gsb_repo.authed_url("/tmp/origin.git", "tok") == "/tmp/origin.git"


def test_probe_branches_accepts_exactly_three(origin):
    probe = asyncio.run(gsb_repo.probe_branches(origin["url"]))
    assert probe.ok is True
    assert probe.main == "main"
    assert sorted(probe.branches) == ["A", "B", "main"]


def test_probe_branches_rejects_missing_side(origin, tmp_path):
    subprocess.run(["git", "-C", origin["url"], "branch", "-D", "B"],
                   check=True, capture_output=True, text=True)
    probe = asyncio.run(gsb_repo.probe_branches(origin["url"]))
    assert probe.ok is False
    assert "B" in probe.message


def test_probe_branches_rejects_extra_branch(origin):
    subprocess.run(["git", "-C", origin["url"], "branch", "feature-x"],
                   check=True, capture_output=True, text=True)
    probe = asyncio.run(gsb_repo.probe_branches(origin["url"]))
    assert probe.ok is False
    assert "feature-x" in probe.message


def test_clone_side_puts_each_branch_in_its_own_dir(origin):
    for side in ("A", "B"):
        r = asyncio.run(gsb_repo.clone_side("07", origin["url"], side))
        assert r["ok"] is True, r["message"]
    for side in ("A", "B"):
        ws = config.TaskPaths("07", side).workspace
        assert (ws / ".git").exists()
        cur = subprocess.run(["git", "-C", str(ws), "symbolic-ref", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        assert cur == side


def test_clone_side_reuses_existing_clean_clone(origin):
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    again = asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    assert again["ok"] is True
    assert again["reused"] is True


def test_verify_head_matches_snapshot(origin):
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    r = asyncio.run(gsb_repo.verify_head("07", "A", origin["sha"]))
    assert r["ok"] is True
    assert r["dirty"] == 0


def test_verify_head_reports_dirty_worktree(origin):
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    ws = config.TaskPaths("07", "A").workspace
    (ws / "scratch.txt").write_text("x", encoding="utf-8")
    r = asyncio.run(gsb_repo.verify_head("07", "A", origin["sha"]))
    assert r["ok"] is False
    assert r["dirty"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_gsb_repo_branches.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.gsb_repo'`

- [ ] **Step 3: 写 `gsb_repo.py` 的前半部分**

```python
"""GSB 双跑的仓库操作：分支探测、双分支 clone、回退快照、产物提交。

一道题对应一个 GitHub 仓库，仓库下有且仅有三个分支：主分支加大写的 A、B。
A 和 B 各自 clone 到 workspace/<题号>/<side>，跑完各自提交到自己的分支。
平台要求两份产物快照的父提交都是初始环境快照，所以 push 之前会先校验 HEAD^。

GitHub Token 只在拼 URL 时进内存，不写进 .git/config，也不进日志。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app import config
from app.services import dockerx, settings_store

log = logging.getLogger("gsb_repo")

MAIN_NAMES = ("main", "master")
COMMIT_USER = "solo-cli"
COMMIT_EMAIL = "solo-cli@local"
BACKUP_NS = "refs/solo-backup"

COMMIT_URL_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/commit/[0-9a-fA-F]{40}/?$")
_SLUG_RE = re.compile(r"(?:github\.com[:/])([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_SHA_RE = re.compile(r"/commit/([0-9a-fA-F]{40})/?$")
_META_KEYS = ("仓库", "repo", "repository")


def parse_repo_url(meta: dict) -> str:
    for key in _META_KEYS:
        v = (meta or {}).get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def repo_slug(repo_url: str) -> str:
    m = _SLUG_RE.search((repo_url or "").strip())
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def commit_url(repo_url: str, sha: str) -> str:
    slug = repo_slug(repo_url)
    return f"https://github.com/{slug}/commit/{sha}" if slug and sha else ""


def snapshot_sha(env_snapshot: str) -> str:
    m = _SHA_RE.search(env_snapshot or "")
    return m.group(1).lower() if m else ""


def authed_url(repo_url: str, token: str) -> str:
    """把 token 拼进 https 地址。非 github https 地址（比如测试用的本地裸仓库）原样返回。"""
    url = (repo_url or "").strip()
    if not token or not url.startswith("https://github.com/"):
        return url
    return url.replace("https://", f"https://x-access-token:{token}@", 1)


def _token() -> str:
    return settings_store.get("gh.token")


@dataclass
class BranchProbe:
    ok: bool
    branches: list[str] = field(default_factory=list)
    main: str = ""
    message: str = ""


async def probe_branches(repo_url: str) -> BranchProbe:
    """远端必须恰好三个分支：主分支加 A、B（平台规则 G2）。"""
    if not repo_url:
        return BranchProbe(False, message="题块里没有仓库地址")
    r = await dockerx.run(["git", "ls-remote", "--heads", authed_url(repo_url, _token())], timeout=90)
    if not r.ok:
        # 报错里可能带着 token，整条压掉只留一句话
        return BranchProbe(False, message="读不到远端分支，检查仓库地址与 GitHub Token")
    names = sorted({line.rsplit("refs/heads/", 1)[-1].strip()
                    for line in r.out.splitlines() if "refs/heads/" in line})
    main = next((n for n in names if n in MAIN_NAMES), "")
    if not main:
        return BranchProbe(False, names, "", f"没有主分支（main 或 master），实际分支：{', '.join(names) or '无'}")
    want = {main, "A", "B"}
    if set(names) == want:
        return BranchProbe(True, names, main, f"分支合规：{', '.join(names)}")
    missing = sorted(want - set(names))
    extra = sorted(set(names) - want)
    parts = []
    if missing:
        parts.append(f"缺少 {', '.join(missing)}")
    if extra:
        parts.append(f"多出 {', '.join(extra)}")
    return BranchProbe(False, names, main,
                       f"分支不合规（{'；'.join(parts)}），实际分支：{', '.join(names)}")


async def _git(ws: Path, *args: str, timeout: float = 60) -> dockerx.CmdResult:
    return await dockerx.run(["git", "-C", str(ws), *args], timeout=timeout)


async def clone_side(task_no: str, repo_url: str, side: str) -> dict:
    """把某一侧的分支 clone 到它自己的目录。已有干净的同源 clone 就复用。"""
    ws = config.TaskPaths(task_no, side).workspace
    if (ws / ".git").exists():
        cur = (await _git(ws, "symbolic-ref", "--short", "-q", "HEAD", timeout=30)).out.strip()
        origin = (await _git(ws, "remote", "get-url", "origin", timeout=30)).out.strip()
        if cur == side and repo_slug(origin) == repo_slug(repo_url):
            return {"ok": True, "reused": True, "message": f"复用已有的 {side} 目录"}
        return {"ok": False, "reused": False,
                "message": f"{ws} 已存在但对不上（分支 {cur or '游离'}，远端 {origin or '无'}），先清掉再领取"}
    ws.parent.mkdir(parents=True, exist_ok=True)
    r = await dockerx.run(
        ["git", "clone", "--branch", side, "--single-branch",
         authed_url(repo_url, _token()), str(ws)], timeout=600,
    )
    if not r.ok:
        return {"ok": False, "reused": False, "message": f"clone {side} 分支失败，检查分支是否存在与 Token 权限"}
    # token 不留在 .git/config 里，push 的时候现拼
    await _git(ws, "remote", "set-url", "origin", repo_url, timeout=30)
    return {"ok": True, "reused": False, "message": f"已 clone {side} 分支到 {ws.name}"}


async def verify_head(task_no: str, side: str, snapshot: str) -> dict:
    """做题前这一侧必须停在初始快照上且工作区干净。"""
    ws = config.TaskPaths(task_no, side).workspace
    if not (ws / ".git").exists():
        return {"ok": False, "head": "", "dirty": 0, "message": f"{side} 侧还没有 clone"}
    head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).out.strip().lower()
    st = await _git(ws, "status", "--porcelain", "--untracked-files=all", timeout=60)
    dirty = len([x for x in st.out.splitlines() if x.strip()])
    if snapshot and head != snapshot.lower():
        return {"ok": False, "head": head, "dirty": dirty,
                "message": f"{side} 侧 HEAD {head[:12]} 不是初始快照 {snapshot[:12]}"}
    if dirty:
        return {"ok": False, "head": head, "dirty": dirty,
                "message": f"{side} 侧工作区有 {dirty} 处改动，需要先回退"}
    return {"ok": True, "head": head, "dirty": 0, "message": f"{side} 侧停在初始快照且干净"}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_gsb_repo_branches.py -v`
Expected: 11 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/gsb_repo.py backend/tests/test_gsb_repo_branches.py
git commit -m "func(gsb): 远端分支探测与 A/B 双分支 clone"
```

---

### Task 4: 回退快照与产物提交推送

**Files:**
- Modify: `backend/app/services/gsb_repo.py`
- Test: `backend/tests/test_gsb_repo_commit.py`（新建）

**Interfaces:**
- Consumes: Task 3 的全部
- Produces:
  - `async backup_head(task_no: str, side: str, snapshot: str) -> str` 返回备份 ref 名，没备份返回 `""`
  - `async reset_side(task_no: str, side: str, snapshot: str) -> dict`
    返回 `{"ok": bool, "message": str, "backup": str}`
  - `async commit_and_push(task_no: str, repo_url: str, side: str, snapshot: str, *, message: str) -> dict`
    成功返回 `{"ok": True, "sha": str, "url": str, "changed_files": int, "message": str}`，
    失败返回 `{"ok": False, "message": str}`
  - `def commit_message(task_no: str, side: str, session_id: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_gsb_repo_commit.py
import asyncio
import subprocess

import pytest

from app import config
from app.services import gsb_repo


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def cloned(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    (work / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    sha = _git(work, "rev-parse", "HEAD")
    _git(work, "branch", "A")
    _git(work, "branch", "B")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(work), str(bare)],
                   check=True, capture_output=True, text=True)
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(gsb_repo.settings_store, "get", lambda k: "")
    asyncio.run(gsb_repo.clone_side("07", str(bare), "A"))
    return {"url": str(bare), "sha": sha, "ws": config.TaskPaths("07", "A").workspace}


def test_commit_and_push_returns_permalink(cloned):
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", "https://github.com/acme/widget", "A", cloned["sha"], message="m"))
    assert r["ok"] is True, r["message"]
    assert r["changed_files"] == 1
    assert gsb_repo.COMMIT_URL_RE.match(r["url"]), r["url"]
    assert r["url"].endswith(r["sha"])


def test_commit_and_push_writes_to_the_side_branch(cloned):
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["url"], "A", cloned["sha"], message="m"))
    remote = _git(cloned["url"], "rev-parse", "refs/heads/A")
    local = _git(cloned["ws"], "rev-parse", "HEAD")
    assert remote == local
    # B 分支不许被动到
    assert _git(cloned["url"], "rev-parse", "refs/heads/B") == cloned["sha"]


def test_commit_and_push_refuses_empty_worktree(cloned):
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["url"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "没有改动" in r["message"]


def test_commit_and_push_refuses_wrong_parent(cloned):
    """已经有一个多余提交时，新提交的父提交就不是初始快照了，必须拦住（规则 G3）。"""
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "stray")
    (cloned["ws"] / "two.py").write_text("2\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["url"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "父提交" in r["message"]


def test_reset_side_restores_snapshot_and_backs_up(cloned):
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "stray")
    (cloned["ws"] / "dirt.txt").write_text("x", encoding="utf-8")
    r = asyncio.run(gsb_repo.reset_side("07", "A", cloned["sha"]))
    assert r["ok"] is True
    assert _git(cloned["ws"], "rev-parse", "HEAD") == cloned["sha"]
    assert not (cloned["ws"] / "dirt.txt").exists()
    assert r["backup"].startswith("refs/solo-backup/")
    assert _git(cloned["ws"], "rev-parse", r["backup"]) != cloned["sha"]


def test_reset_side_on_clean_snapshot_is_noop(cloned):
    r = asyncio.run(gsb_repo.reset_side("07", "A", cloned["sha"]))
    assert r["ok"] is True
    assert r["backup"] == ""


def test_commit_message_mentions_side_and_session():
    msg = gsb_repo.commit_message("07", "A", "sess-1")
    assert "07" in msg and "A" in msg and "sess-1" in msg
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_gsb_repo_commit.py -v`
Expected: FAIL，`AttributeError: module 'app.services.gsb_repo' has no attribute 'commit_and_push'`

- [ ] **Step 3: 在 `gsb_repo.py` 追加实现**

```python
async def backup_head(task_no: str, side: str, snapshot: str) -> str:
    """回退前把领先快照的 HEAD 记到 refs/solo-backup/*，事后用 git log 还能捞回来。"""
    ws = config.TaskPaths(task_no, side).workspace
    head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).out.strip()
    if not head or head.lower() == (snapshot or "").lower():
        return ""
    ref = f"{BACKUP_NS}/{task_no}-{side}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    r = await _git(ws, "update-ref", ref, head, timeout=30)
    if not r.ok:
        log.warning("题 %s %s 侧备份 HEAD 失败：%s", task_no, side, r.err.strip()[:200])
        return ""
    return ref


async def reset_side(task_no: str, side: str, snapshot: str) -> dict:
    """把这一侧退回初始快照。重跑之前必须做，否则产物快照的父提交对不上。"""
    ws = config.TaskPaths(task_no, side).workspace
    if not (ws / ".git").exists():
        return {"ok": False, "backup": "", "message": f"{side} 侧不是 git 仓库"}
    if not snapshot:
        return {"ok": False, "backup": "", "message": "初始环境快照缺少 40 位 SHA，无法回退"}
    backup = await backup_head(task_no, side, snapshot)
    r1 = await _git(ws, "reset", "--hard", snapshot, timeout=180)
    r2 = await _git(ws, "clean", "-fdx", timeout=180)
    if not (r1.ok and r2.ok):
        return {"ok": False, "backup": backup,
                "message": (r1.err or r2.err).strip()[:300] or "回退失败"}
    msg = f"{side} 侧已退回 {snapshot[:12]}"
    if backup:
        msg += f"，原提交备份在 {backup}"
    return {"ok": True, "backup": backup, "message": msg}


def commit_message(task_no: str, side: str, session_id: str) -> str:
    return (f"solo {task_no} · {side}\n\n"
            f"SessionID: {session_id or '-'}\n")


async def commit_and_push(task_no: str, repo_url: str, side: str, snapshot: str,
                          *, message: str) -> dict:
    """提交这一侧的产物并推到同名分支，返回产物快照 permalink。

    push 之前校验父提交等于初始快照：平台规则 G3 卡这个，等提交被打回才发现就晚了。
    """
    ws = config.TaskPaths(task_no, side).workspace
    if not (ws / ".git").exists():
        return {"ok": False, "message": f"{side} 侧不是 git 仓库"}
    slug = repo_slug(repo_url)
    if not slug:
        return {"ok": False, "message": f"仓库地址解析不出 org/repo：{repo_url}"}

    st = await _git(ws, "status", "--porcelain", "--untracked-files=all", timeout=60)
    changed = len([x for x in st.out.splitlines() if x.strip()])
    if not changed:
        return {"ok": False, "message": f"{side} 侧工作区没有改动，这一跑没有产出，不能当作产物提交"}

    add = await _git(ws, "add", "-A", timeout=180)
    if not add.ok:
        return {"ok": False, "message": f"git add 失败：{add.err.strip()[:300]}"}
    ci = await _git(ws, "-c", f"user.name={COMMIT_USER}", "-c", f"user.email={COMMIT_EMAIL}",
                    "commit", "-m", message, timeout=180)
    if not ci.ok:
        return {"ok": False, "message": f"git commit 失败：{(ci.err or ci.out).strip()[:300]}"}

    head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).out.strip()
    parent = (await _git(ws, "rev-parse", "HEAD^", timeout=30)).out.strip()
    if parent.lower() != (snapshot or "").lower():
        return {"ok": False,
                "message": f"{side} 侧产物的父提交是 {parent[:12]}，不是初始快照 {snapshot[:12]}；"
                           f"平台规则 G3 会打回，需要先回退这一侧再重跑"}

    push = await dockerx.run(
        ["git", "-C", str(ws), "push", authed_url(repo_url, _token()),
         f"HEAD:refs/heads/{side}"], timeout=300,
    )
    if not push.ok:
        return {"ok": False, "message": f"{side} 侧 push 失败，检查 Token 的 repo 写权限"}

    url = commit_url(repo_url, head)
    log.info("题 %s %s 侧产物 %s 已推到分支 %s（%d 个文件）", task_no, side, head[:12], side, changed)
    return {"ok": True, "sha": head, "url": url, "changed_files": changed,
            "message": f"{side} 侧已提交 {head[:12]} 并推到分支 {side}（{changed} 个文件）"}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_gsb_repo_commit.py -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/gsb_repo.py backend/tests/test_gsb_repo_commit.py
git commit -m "func(gsb): 回退快照与产物提交推送，push 前校验父提交"
```

---

### Task 5: 门禁按双跑重写

**Files:**
- Modify: `backend/app/services/gate.py`
- Test: `backend/tests/test_gate_gsb.py`（新建）
- Delete: `backend/tests/test_repo_siblings.py`

**Interfaces:**
- Consumes: `gsb_repo`（Task 3、4）、`config.TaskPaths`、`models.Task`
- Produces:
  - `QUESTION_TYPES: tuple[str, ...]`、`DIFFICULTIES = ("困难", "地狱")`、
    `REPRO_LEVELS: tuple[str, ...]`（值见 Global Constraints）
  - `def normalize_choice(value: str, options: tuple[str, ...]) -> str`
    去掉全部空白后比对，匹配上返回平台侧的原值，匹配不上返回 `""`
  - `@dataclass Check(name, level, message, fix="")`（保持不变）
  - `async run_checks(task: Task) -> list[Check]`
  - `def summarize(checks) -> dict`（保持不变）
  - `async prepare_workspaces(task: Task) -> dict`：对 A、B 各跑一次 `clone_side`，
    返回 `{"ok": bool, "sides": {"A": {...}, "B": {...}}, "message": str}`
- 删除：`_scan_blacklist` 保留，`repo_siblings_running`、`reset_to_snapshot`、`archive_traces` 删除
  （`archive_traces` 迁到 watchdog，`reset_to_snapshot` 由 `gsb_repo.reset_side` 取代）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_gate_gsb.py
import asyncio

import pytest

from app import models as m
from app.services import gate


def test_normalize_choice_ignores_whitespace():
    assert gate.normalize_choice("0-1 代码生成", gate.QUESTION_TYPES) == "0-1代码生成"
    assert gate.normalize_choice("feature 迭代", gate.QUESTION_TYPES) == "feature迭代"
    assert gate.normalize_choice("Bug修复", gate.QUESTION_TYPES) == "Bug修复"
    assert gate.normalize_choice("随便写的", gate.QUESTION_TYPES) == ""
    assert gate.normalize_choice("", gate.QUESTION_TYPES) == ""


def test_difficulty_options_are_exactly_two():
    assert gate.DIFFICULTIES == ("困难", "地狱")


def _task(**kw):
    base = dict(task_no="07", prompt_hash="h", difficulty="困难",
                question_type="0-1 代码生成", repo_url="https://github.com/acme/widget",
                env_snapshot="https://github.com/acme/widget/commit/" + "a" * 40)
    base.update(kw)
    return m.Task(**base)


def _levels(checks):
    return {c.name: c.level for c in checks}


@pytest.fixture()
def stub(monkeypatch, tmp_path):
    """把外部依赖全打桩，只测门禁自己的判断逻辑。"""
    async def ok_daemon():
        return True, "27.0"

    async def yes(*a, **k):
        return True

    async def version(image):
        return "2.1.197"

    async def no_container(name):
        return ""

    async def probe(url):
        from app.services.gsb_repo import BranchProbe
        return BranchProbe(True, ["A", "B", "main"], "main", "分支合规：A, B, main")

    async def verify(task_no, side, snapshot):
        return {"ok": True, "head": "a" * 40, "dirty": 0, "message": f"{side} 侧就绪"}

    async def label(image, key):
        return "cc"

    monkeypatch.setattr(gate.dockerx, "daemon_ok", ok_daemon)
    monkeypatch.setattr(gate.dockerx, "image_present", yes)
    monkeypatch.setattr(gate.dockerx, "claude_version", version)
    monkeypatch.setattr(gate.dockerx, "image_label", label)
    monkeypatch.setattr(gate.dockerx, "container_state", no_container)
    monkeypatch.setattr(gate.gsb_repo, "probe_branches", probe)
    monkeypatch.setattr(gate.gsb_repo, "verify_head", verify)
    monkeypatch.setattr(gate.settings_store, "is_configured", lambda k: True)
    monkeypatch.setattr(gate.settings_store, "get", lambda k: "" if k == "gate.blacklist" else "img")
    monkeypatch.setattr(gate, "_scan_blacklist", lambda root, pats, limit=20: [])
    monkeypatch.setattr(gate.config, "CODER_ROOT_MOUNT", tmp_path)
    for side in ("A", "B"):
        (tmp_path / "workspace" / "07" / side / ".git").mkdir(parents=True)
        (tmp_path / "出题" / "轨迹" / "07" / side).mkdir(parents=True)
    return tmp_path


def test_all_green_passes(stub):
    checks = asyncio.run(gate.run_checks(_task()))
    assert gate.summarize(checks)["passed"] is True


def test_easy_difficulty_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(difficulty="中等")))
    assert _levels(checks)["difficulty"] == "block"


def test_unknown_question_type_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(question_type="瞎写的类型")))
    assert _levels(checks)["question_type"] == "block"


def test_missing_repo_url_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(repo_url="")))
    assert _levels(checks)["repo_url"] == "block"


def test_bad_branches_are_blocked_with_actual_list(stub, monkeypatch):
    async def probe(url):
        from app.services.gsb_repo import BranchProbe
        return BranchProbe(False, ["main", "dev"], "main", "分支不合规（缺少 A, B），实际分支：main, dev")

    monkeypatch.setattr(gate.gsb_repo, "probe_branches", probe)
    checks = asyncio.run(gate.run_checks(_task()))
    branch = next(c for c in checks if c.name == "branches")
    assert branch.level == "block"
    assert "dev" in branch.message


def test_short_snapshot_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(env_snapshot="https://github.com/a/b/commit/abc")))
    assert _levels(checks)["snapshot"] == "block"


def test_both_sides_are_checked_independently(stub, monkeypatch):
    async def verify(task_no, side, snapshot):
        ok = side == "A"
        return {"ok": ok, "head": "a" * 40, "dirty": 0 if ok else 3,
                "message": f"{side} 侧工作区有 3 处改动"}

    monkeypatch.setattr(gate.gsb_repo, "verify_head", verify)
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["workspace_A"] == "ok"
    assert levels["workspace_B"] == "block"


def test_nonempty_trace_dir_is_blocked(stub):
    (stub / "出题" / "轨迹" / "07" / "B" / "stale.jsonl").write_text("{}", encoding="utf-8")
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["traces_A"] == "ok"
    assert levels["traces_B"] == "block"


def test_existing_container_is_blocked(stub, monkeypatch):
    async def state(name):
        return "exited" if name.endswith("-A") else ""

    monkeypatch.setattr(gate.dockerx, "container_state", state)
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["container_A"] == "block"
    assert levels["container_B"] == "ok"


def test_repo_busy_check_is_gone(stub):
    names = {c.name for c in asyncio.run(gate.run_checks(_task()))}
    assert "repo_busy" not in names
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_gate_gsb.py -v`
Expected: FAIL，`AttributeError: module 'app.services.gate' has no attribute 'normalize_choice'`

- [ ] **Step 3: 改写 `gate.py`**

顶部常量与新函数：

```python
from app.services import dockerx, gsb_repo, settings_store

QUESTION_TYPES = ("0-1代码生成", "feature迭代", "Bug修复", "代码理解",
                  "代码重构", "工程化", "代码测试")
DIFFICULTIES = ("困难", "地狱")
REPRO_LEVELS = ("无外部依赖", "有外部依赖，未容器化", "已容器化，可一键起环境")

_WS = re.compile(r"\s+")


def normalize_choice(value: str, options: tuple[str, ...]) -> str:
    """题块里写的值和平台选项差空格，去空白后比对，匹配不上返回空串让门禁报出来。"""
    want = _WS.sub("", value or "")
    if not want:
        return ""
    for o in options:
        if _WS.sub("", o) == want:
            return o
    return ""
```

`run_checks` 重写（保留原来的 Key / docker / image / 黑名单三段写法，其余替换）：

```python
async def run_checks(task: Task) -> list[Check]:
    checks: list[Check] = []

    # 1. 配置与镜像（沿用原有三项，此处省略不改）
    ...

    # 2. 题面必须符合平台口径，不然跑完也交不上去
    if normalize_choice(task.difficulty, DIFFICULTIES):
        checks.append(Check("difficulty", "ok", f"难度 {task.difficulty}"))
    else:
        checks.append(Check("difficulty", "block",
                            f"难度「{task.difficulty or '空'}」不收，本期只收困难与地狱（规则 G1）"))
    qt = normalize_choice(task.question_type, QUESTION_TYPES)
    if qt:
        checks.append(Check("question_type", "ok", f"任务类型 {qt}"))
    else:
        checks.append(Check("question_type", "block",
                            f"任务类型「{task.question_type or '空'}」不在平台选项里，"
                            f"可选：{'、'.join(QUESTION_TYPES)}"))
    if normalize_choice(task.repro_level, REPRO_LEVELS):
        checks.append(Check("repro_level", "ok", f"可复现等级 {task.repro_level}"))
    else:
        checks.append(Check("repro_level", "warn",
                            f"可复现等级「{task.repro_level or '空'}」不在平台选项里，上传前需要改题块"))

    # 3. 仓库与分支
    if not task.repo_url:
        checks.append(Check("repo_url", "block", "题块里没有仓库地址（「仓库：」那一行）"))
        return checks
    checks.append(Check("repo_url", "ok", f"仓库 {gsb_repo.repo_slug(task.repo_url) or task.repo_url}"))
    probe = await gsb_repo.probe_branches(task.repo_url)
    checks.append(Check("branches", "ok" if probe.ok else "block", probe.message))

    snapshot = gsb_repo.snapshot_sha(task.env_snapshot)
    if snapshot:
        checks.append(Check("snapshot", "ok", f"初始快照 {snapshot[:12]}"))
    else:
        checks.append(Check("snapshot", "block",
                            "初始环境快照不是 40 位 SHA 的 commit 链接，两边都没法对起跑点"))

    # 4. 两侧各自的工作目录、轨迹目录、容器名
    patterns = [p.strip() for p in settings_store.get("gate.blacklist").split(",") if p.strip()]
    for side in config.SIDES:
        paths = config.TaskPaths(task.task_no, side)
        ws = paths.workspace
        if not (ws / ".git").exists():
            checks.append(Check(f"workspace_{side}", "block",
                                f"{side} 侧还没 clone 到 {ws}", fix="clone_sides"))
        else:
            hv = await gsb_repo.verify_head(task.task_no, side, snapshot)
            checks.append(Check(f"workspace_{side}", "ok" if hv["ok"] else "block",
                                hv["message"], fix="" if hv["ok"] else "reset_sides"))
            hits = _scan_blacklist(str(ws), patterns)
            checks.append(Check(f"leak_{side}", "block" if hits else "ok",
                                f"{side} 侧发现可能泄漏的文件：{', '.join(hits[:5])}" if hits
                                else f"{side} 侧未发现黑名单文件"))

        tr = paths.traces
        if tr.exists() and any(tr.iterdir()):
            checks.append(Check(f"traces_{side}", "block",
                                f"{side} 侧轨迹目录非空：{tr}（一次跑只能有一份轨迹）",
                                fix="archive_traces"))
        else:
            checks.append(Check(f"traces_{side}", "ok", f"{side} 侧轨迹目录为空"))

        state = await dockerx.container_state(paths.container_name)
        if state:
            checks.append(Check(f"container_{side}", "block",
                                f"容器 {paths.container_name} 已存在（{state}）",
                                fix="remove_containers"))
        else:
            checks.append(Check(f"container_{side}", "ok", f"容器名 {paths.container_name} 可用"))

    return checks
```

新增 `prepare_workspaces`：

```python
async def prepare_workspaces(task: Task) -> dict:
    """领题时把 A、B 两个分支各 clone 一份。任一侧失败就整体失败，不留半套。"""
    probe = await gsb_repo.probe_branches(task.repo_url)
    if not probe.ok:
        return {"ok": False, "sides": {}, "message": probe.message}
    sides = {}
    for side in config.SIDES:
        sides[side] = await gsb_repo.clone_side(task.task_no, task.repo_url, side)
    ok = all(r["ok"] for r in sides.values())
    msg = "；".join(f"{s}: {r['message']}" for s, r in sides.items())
    return {"ok": ok, "sides": sides, "message": msg}
```

删掉 `repo_siblings_running`、`reset_to_snapshot`、`archive_traces`、`snapshot_sha`
（`snapshot_sha` 改为从 `gsb_repo` 导入使用）和 `qa_bridge` 导入。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_gate_gsb.py -v && rm backend/tests/test_repo_siblings.py`
Expected: 11 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/gate.py backend/tests/test_gate_gsb.py
git rm backend/tests/test_repo_siblings.py
git commit -m "func(gsb): 门禁按双跑重写，加难度与分支校验"
```

---

### Task 6: 运行改为单侧执行

**Files:**
- Modify: `backend/app/services/runner.py`
- Test: `backend/tests/test_runner_side.py`（新建）
- Delete: `backend/tests/test_finalize.py`、`test_runner_status.py`、`test_runner_lines.py`、
  `test_continue_round.py`（用例迁进新文件）

**Interfaces:**
- Consumes: `config.TaskPaths`（Task 1）、`models.TaskRun`（Task 2）
- Produces:
  - `async run_side(run_id: int) -> None`
  - `def decide_status(*, timed_out: bool, manual_stop: bool, result_event: dict,
    exit_code: int | None, has_trace: bool) -> tuple[str, bool]`（返回值改用 `RUN_*` 常量）
  - `async finalize(run_id: int, *, exit_code, result_event, timed_out=False,
    manual_stop=False, stderr_tail=None, thinking_tokens=0, dropped_events=0) -> None`
  - `async stop_run(run_id: int) -> dict`
  - `def gateway_errors(events: list[dict], stderr_tail: list[str]) -> list[str]`
    从 `system/api_retry` 的 `error_status` 与 stderr 文本里抽出 5xx/429，供 watchdog 判异常
- 保留不动：`_iter_lines`、`_summarize_event`、`MAX_LINE_BYTES`、`NOISY_SUBTYPES` 等常量
- 删除：`build_continue_prompt`、`queue_continue`、`prompt_bank.backfill` 调用

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_runner_side.py
import asyncio

import pytest

from app import models as m
from app.services import runner


def test_decide_status_uses_run_constants():
    assert runner.decide_status(timed_out=True, manual_stop=False, result_event={},
                                exit_code=None, has_trace=True) == (m.RUN_TIMEOUT, False)
    assert runner.decide_status(timed_out=False, manual_stop=True, result_event={},
                                exit_code=137, has_trace=True) == (m.RUN_INTERRUPTED, False)
    assert runner.decide_status(timed_out=False, manual_stop=False,
                                result_event={"subtype": "success"}, exit_code=0,
                                has_trace=True) == (m.RUN_FINISHED, False)
    assert runner.decide_status(timed_out=False, manual_stop=False, result_event={},
                                exit_code=0, has_trace=True) == (m.RUN_FINISHED, True)
    assert runner.decide_status(timed_out=False, manual_stop=False, result_event={},
                                exit_code=None, has_trace=False) == (m.RUN_INTERRUPTED, False)
    assert runner.decide_status(timed_out=False, manual_stop=False,
                                result_event={"subtype": "error_max_turns"}, exit_code=1,
                                has_trace=True) == (m.RUN_FAILED, False)


def test_gateway_errors_from_api_retry_events():
    events = [
        {"type": "system", "subtype": "api_retry", "error_status": 504},
        {"type": "system", "subtype": "api_retry", "error_status": 429},
        {"type": "system", "subtype": "init"},
    ]
    assert runner.gateway_errors(events, []) == ["504", "429"]


def test_gateway_errors_from_stderr_text():
    tail = ["upstream connect error", "HTTP 504 Gateway Timeout", "retrying"]
    assert runner.gateway_errors([], tail) == ["504"]


def test_gateway_errors_ignores_unrelated_numbers():
    assert runner.gateway_errors([], ["wrote 5040 bytes", "exit 200"]) == []


def test_continue_round_api_is_gone():
    assert not hasattr(runner, "queue_continue")
    assert not hasattr(runner, "build_continue_prompt")


@pytest.mark.asyncio
async def test_finalize_writes_to_the_run_not_the_task(tmp_path, monkeypatch, db_session):
    """finalize 之后判定、轨迹、session 都落在 TaskRun 上，Task 只剩题面。"""
    task, run = db_session
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)

    async def no_git(*a, **k):
        from app.services.dockerx import CmdResult
        return CmdResult(1, "", "not a repo")

    monkeypatch.setattr(runner.dockerx, "run", no_git)
    await runner.finalize(run.id, exit_code=1, result_event={"subtype": "error"},
                          stderr_tail=["HTTP 504"])
    from app.db import session
    with session() as s:
        got = s.get(m.TaskRun, run.id)
        assert got.status == m.RUN_FAILED
        assert got.verdict["process"]["exit_code"] == 1
        assert got.verdict["process"]["gateway_errors"] == ["504"]
        assert "504" in got.error
```

`db_session` fixture 放进 `backend/tests/conftest.py`（若已存在就追加）：

```python
# backend/tests/conftest.py
import pytest


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    """一套干净的库，外加一道题和它的 A 侧 run。"""
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    import importlib

    from app import db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    from app import models as m
    with db_mod.session() as s:
        t = m.Task(task_no="07", prompt_hash="h", user_prompt="做点事")
        s.add(t)
        s.flush()
        r = m.TaskRun(task_id=t.id, side="A", container_name="solo-cc-07-A")
        s.add(r)
        s.flush()
        s.expunge_all()
    with db_mod.session() as s:
        yield s.query(m.Task).first(), s.query(m.TaskRun).first()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_runner_side.py -v`
Expected: FAIL，`AttributeError: module 'app.services.runner' has no attribute 'gateway_errors'`

- [ ] **Step 3: 改写 `runner.py`**

新增 `gateway_errors`：

```python
_HTTP_ERR = re.compile(r"\b(50[0234]|429)\b")


def gateway_errors(events: list[dict], stderr_tail: list[str]) -> list[str]:
    """抽出网关层的 5xx/429。watchdog 靠它判断这一跑是不是被网关打断的。

    只认 api_retry 事件里的 error_status 和 stderr 里明确的 HTTP 码，
    不去正则匹配任意数字——"wrote 5040 bytes" 会被误判成 504。
    """
    out: list[str] = []
    for e in events:
        if e.get("type") == "system" and e.get("subtype") == "api_retry":
            code = str(e.get("error_status") or "").strip()
            if code and code not in out:
                out.append(code)
    for line in stderr_tail:
        for m in _HTTP_ERR.finditer(line):
            code = m.group(1)
            # 必须挨着 HTTP / status / error 之类的词，否则是普通数字
            head = line[max(0, m.start() - 24):m.start()].lower()
            if any(k in head for k in ("http", "status", "code", "error", "gateway")) and code not in out:
                out.append(code)
    return out
```

`run_task(task_id)` 改名 `run_side(run_id)`，开头改成从 `TaskRun` 读 side 并构造路径：

```python
async def run_side(run_id: int) -> None:
    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is None:
            return
        t = db.get(Task, r.task_id)
        if t is None:
            return
        task_no, side, prompt = t.task_no, r.side, t.user_prompt
    paths = config.TaskPaths(task_no, side)
    ...
```

容器启动那段的 `-v` 与 `--name` 全部改用 `paths`（已经按 side 分好），
`--label` 追加一个 `--label f"{config.CONTAINER_LABEL}.side={side}"`，
事件落库的 `round_no=round_no` 全改成 `side=side`，
`seq` 直接从 1 开始（没有续跑，不需要 `_max_seq`，删掉该函数）。

`finalize` 的签名第一个参数改 `run_id`，加一个 `retry_events: list[dict] | None = None` 参数，
内部把结果写进 `TaskRun`，`verdict["process"]` 里加一项
`"gateway_errors": gateway_errors(retry_events or [], stderr_tail or [])`。

`retry_events` 在 `run_side` 里收集：与 `stderr_tail` 并列声明 `retry_events: list[dict] = []`，
在 `pump_stdout` 处理 `system` 事件的地方顺手存一份。现有代码是把 `api_retry` 当普通事件落库，
watchdog 判异常时不该再去翻事件表，所以这里同时留一份在内存里：

```python
            kind = str(obj.get("type", "event"))
            if kind == "system" and obj.get("subtype") == "api_retry":
                # 网关重试是判断这一跑是否被打断的依据，留一份给 finalize
                retry_events.append(obj)
            if kind == "system" and obj.get("subtype") in NOISY_SUBTYPES:
                ...  # 原有的 thinking_tokens 节流逻辑不动
```

`pump_stdout` 的 `nonlocal` 声明里不用加 `retry_events`（只 append 不重新赋值），
`finalize` 调用处传 `retry_events=retry_events`。
删掉 `prompt_bank.backfill` 那一段和 `rounds` 留痕那一段。
结尾把 `pipeline.spawn(task_id)` 换成：

```python
    # 结束后不自己决定下一步：异常重跑与配对触发都归 watchdog，决策点只留一个
    from app.services import watchdog

    watchdog.wake()
```

`stop_task` 改名 `stop_run(run_id)`，`_manual_stop` 的键改成 run_id。
删掉 `queue_continue` 与 `build_continue_prompt` 整个函数。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_runner_side.py -v`
Expected: 6 passed

- [ ] **Step 5: 删掉被取代的老测试**

```bash
cd backend && git rm tests/test_finalize.py tests/test_runner_status.py \
  tests/test_runner_lines.py tests/test_continue_round.py tests/test_reset_backfill.py
```

把 `test_runner_lines.py` 里 `_iter_lines` 的用例原样搬进 `test_runner_side.py`
（超长行截断、无换行结尾、多行一次读入三个用例），`_iter_lines` 本身没改，用例不该丢。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/runner.py backend/tests/test_runner_side.py backend/tests/conftest.py
git commit -m "func(gsb): 运行改为单侧执行，结果落 TaskRun，删续跑"
```

---

### Task 7: 调度改为 run 粒度成对出队

**Files:**
- Modify: `backend/app/services/scheduler.py`
- Test: `backend/tests/test_scheduler_pairs.py`（新建）

**Interfaces:**
- Consumes: `runner.run_side`、`runner.finalize`（Task 6）、`models.TaskRun`（Task 2）
- Produces:
  - `Scheduler.max_parallel` 语义为「同时运行的容器数」
  - `Scheduler.pick(free: int) -> list[int]` 返回可启动的 **run id** 列表，成对出队
  - `Scheduler.snapshot() -> dict`，键 `{"running", "max_parallel", "running_ids", "queued", "paused"}`
  - 删除 `waiting_on_repo`、`_pick` 里的 repo 互斥

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_scheduler_pairs.py
import pytest

from app import models as m
from app.db import session
from app.services.scheduler import Scheduler


def _queued_task(db, no):
    t = m.Task(task_no=no, prompt_hash=f"h{no}", status=m.QUEUED)
    db.add(t)
    db.flush()
    ids = []
    for side in ("A", "B"):
        r = m.TaskRun(task_id=t.id, side=side, status=m.RUN_QUEUED)
        db.add(r)
        db.flush()
        ids.append(r.id)
    return t, ids


@pytest.fixture()
def sched(db_session):
    return Scheduler()


def test_pick_returns_both_sides_together(sched, db_session):
    with session() as db:
        db.query(m.TaskRun).delete()
        db.query(m.Task).delete()
        _t, ids = _queued_task(db, "01")
    picked = sched.pick(4)
    assert sorted(picked) == sorted(ids)


def test_pick_skips_task_when_only_one_slot_left(sched, db_session):
    with session() as db:
        db.query(m.TaskRun).delete()
        db.query(m.Task).delete()
        _queued_task(db, "01")
    assert sched.pick(1) == []


def test_pick_fills_two_tasks_when_four_slots(sched, db_session):
    with session() as db:
        db.query(m.TaskRun).delete()
        db.query(m.Task).delete()
        _queued_task(db, "01")
        _queued_task(db, "02")
    assert len(sched.pick(4)) == 4


def test_pick_respects_priority_order(sched, db_session):
    with session() as db:
        db.query(m.TaskRun).delete()
        db.query(m.Task).delete()
        t1, ids1 = _queued_task(db, "01")
        t2, ids2 = _queued_task(db, "02")
        t2.priority = -1
    assert sorted(sched.pick(2)) == sorted(ids2)


def test_same_repo_no_longer_blocks(sched, db_session):
    """两道题共用一个仓库也能同时跑，因为目录已经按题号和 side 分开了。"""
    with session() as db:
        db.query(m.TaskRun).delete()
        db.query(m.Task).delete()
        t1, ids1 = _queued_task(db, "01")
        t2, ids2 = _queued_task(db, "02")
        t1.repo_url = t2.repo_url = "https://github.com/acme/widget"
    assert len(sched.pick(4)) == 4


def test_repo_waiting_api_is_gone(sched):
    assert not hasattr(sched, "waiting_on_repo")
    assert "repo_waiting" not in sched.snapshot()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_scheduler_pairs.py -v`
Expected: FAIL，`AttributeError: 'Scheduler' object has no attribute 'pick'`

- [ ] **Step 3: 改写 `scheduler.py`**

```python
    def pick(self, free: int) -> list[int]:
        """挑这一轮能启动的 run。A 与 B 成对出队：只够一个槽就不启动。

        半边先跑会让另一边干等——容器占着额度却什么也没产出，配对分析也开不了。
        """
        if free < 2:
            return []
        with session() as db:
            tasks = db.execute(
                select(Task).where(Task.status == QUEUED)
                .order_by(Task.priority, Task.claimed_at, Task.id)
            ).scalars().all()
            picked: list[int] = []
            for t in tasks:
                runs = db.execute(
                    select(TaskRun).where(TaskRun.task_id == t.id,
                                          TaskRun.status == RUN_QUEUED)
                    .order_by(TaskRun.side)
                ).scalars().all()
                if len(runs) != 2:
                    continue
                if len(picked) + 2 > free:
                    break
                picked.extend(r.id for r in runs)
            return picked
```

`_tick` 里 `self._pick(free)` 改成 `self.pick(free)`，
`asyncio.create_task(runner.run_task(tid))` 改成 `runner.run_side(rid)`，
`self.running` 的键改成 run id。
`snapshot()` 去掉 `repo_waiting`，`waiting_on_repo` 整个删掉，`qa_bridge` 导入删掉。
`_adopt` 与 `_after_crash` 里的 `Task` 查询全部改成 `TaskRun`，
状态常量改用 `RUN_RUNNING` / `RUN_INTERRUPTED`。
`_wait_and_finalize` 的 `runner.finalize(tid, ...)` 参数改成 run id。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_scheduler_pairs.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/scheduler.py backend/tests/test_scheduler_pairs.py
git commit -m "func(gsb): 调度改 run 粒度，A/B 成对出队并删同项目互斥"
```

---

### Task 8: 守护任务

**Files:**
- Create: `backend/app/services/watchdog.py`
- Test: `backend/tests/test_watchdog.py`（新建）
- Delete: `backend/app/services/pipeline.py`、`backend/app/services/task_reset.py`

**Interfaces:**
- Consumes: `gsb_repo.reset_side` / `commit_and_push`（Task 3、4）、`models.TaskRun`（Task 2）
- Produces:
  - `def wake() -> None`：唤醒一次立即扫描
  - `async start() -> None` / `async stop() -> None`
  - `async tick() -> dict` 返回 `{"requeued": [run_id...], "analyzing": [task_id...]}`
  - `def abnormal_reason(run: TaskRun, container_alive: bool) -> str`，非空即异常
  - `async requeue_run(run_id: int, *, manual: bool = False) -> dict`
  - `def archive_traces(task_no: str, side: str) -> dict`（从 `gate.py` 搬来，加 side）
  - `async scan_abnormal() -> list[int]` / `async scan_paired() -> list[int]`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_watchdog.py
import pytest

from app import models as m
from app.services import watchdog


def _run(**kw):
    r = m.TaskRun(task_id=1, side="A", status=m.RUN_FINISHED, attempt=1)
    r.trace_file = "/tmp/x.jsonl"
    r.verdict = {"process": {"exit_code": 0, "gateway_errors": []},
                 "protocol": {"subtype": "success"},
                 "artifact": {"changed_files": 3}}
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def test_healthy_run_is_not_abnormal():
    assert watchdog.abnormal_reason(_run(), container_alive=False) == ""


def test_failed_status_is_abnormal():
    assert "FAILED" in watchdog.abnormal_reason(_run(status=m.RUN_FAILED), container_alive=False)


def test_timeout_is_abnormal():
    assert watchdog.abnormal_reason(_run(status=m.RUN_TIMEOUT), container_alive=False) != ""


def test_running_without_container_is_abnormal():
    r = _run(status=m.RUN_RUNNING)
    assert "容器" in watchdog.abnormal_reason(r, container_alive=False)
    assert watchdog.abnormal_reason(r, container_alive=True) == ""


def test_finished_without_trace_is_abnormal():
    assert "轨迹" in watchdog.abnormal_reason(_run(trace_file=""), container_alive=False)


def test_finished_with_zero_changes_is_abnormal():
    r = _run()
    r.verdict = {"process": {}, "protocol": {"subtype": "success"},
                 "artifact": {"changed_files": 0}}
    assert "零改动" in watchdog.abnormal_reason(r, container_alive=False)


def test_non_success_subtype_is_abnormal():
    r = _run()
    r.verdict = {"process": {}, "protocol": {"subtype": "error_max_turns"},
                 "artifact": {"changed_files": 2}}
    assert "error_max_turns" in watchdog.abnormal_reason(r, container_alive=False)


def test_gateway_error_is_abnormal():
    r = _run()
    r.verdict = {"process": {"gateway_errors": ["504"]},
                 "protocol": {"subtype": "success"},
                 "artifact": {"changed_files": 2}}
    assert "504" in watchdog.abnormal_reason(r, container_alive=False)


def test_retry_budget_is_three_retries():
    """attempt 从 1 起，重跑 3 次之后是 4，不能再跑。"""
    assert watchdog.can_retry(_run(attempt=1), limit=3) is True
    assert watchdog.can_retry(_run(attempt=3), limit=3) is True
    assert watchdog.can_retry(_run(attempt=4), limit=3) is False


def test_archive_traces_renames_nonempty_dir(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path)
    tr = config.TaskPaths("07", "B").traces
    tr.mkdir(parents=True)
    (tr / "s.jsonl").write_text("{}", encoding="utf-8")
    r = watchdog.archive_traces("07", "B")
    assert r["ok"] is True
    assert not any(tr.iterdir()) if tr.exists() else True
    assert list(tr.parent.glob("B.archived-*"))


def test_archive_traces_on_empty_dir_is_noop(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path)
    config.TaskPaths("07", "A").traces.mkdir(parents=True)
    assert watchdog.archive_traces("07", "A")["ok"] is True


@pytest.mark.asyncio
async def test_requeue_resets_and_increments_attempt(db_session, monkeypatch, tmp_path):
    task, run = db_session
    calls = {}

    async def fake_reset(task_no, side, snapshot):
        calls["reset"] = (task_no, side)
        return {"ok": True, "backup": "", "message": "ok"}

    async def fake_remove(name):
        calls["removed"] = name
        from app.services.dockerx import CmdResult
        return CmdResult(0, "", "")

    monkeypatch.setattr(watchdog.gsb_repo, "reset_side", fake_reset)
    monkeypatch.setattr(watchdog.dockerx, "remove_container", fake_remove)
    monkeypatch.setattr(watchdog, "archive_traces", lambda no, side: {"ok": True, "message": ""})

    r = await watchdog.requeue_run(run.id)
    assert r["ok"] is True
    from app.db import session
    with session() as s:
        got = s.get(m.TaskRun, run.id)
        assert got.attempt == 2
        assert got.status == m.RUN_QUEUED
        assert got.trace_file == ""
        assert got.container_exists is False
    assert calls["reset"][1] == "A"
    assert calls["removed"] == "solo-cc-07-A"


@pytest.mark.asyncio
async def test_requeue_refuses_when_budget_spent(db_session, monkeypatch):
    task, run = db_session
    from app.db import session
    with session() as s:
        s.get(m.TaskRun, run.id).attempt = 4
    monkeypatch.setattr(watchdog.settings_store, "get_int", lambda k, d=0: 3)
    r = await watchdog.requeue_run(run.id)
    assert r["ok"] is False
    with session() as s:
        assert s.get(m.Task, task.id).status == m.NEEDS_ATTENTION


@pytest.mark.asyncio
async def test_manual_requeue_ignores_budget_and_resets_counter(db_session, monkeypatch):
    task, run = db_session
    from app.db import session
    with session() as s:
        s.get(m.TaskRun, run.id).attempt = 9

    async def fake_reset(*a, **k):
        return {"ok": True, "backup": "", "message": "ok"}

    async def fake_remove(name):
        from app.services.dockerx import CmdResult
        return CmdResult(0, "", "")

    monkeypatch.setattr(watchdog.gsb_repo, "reset_side", fake_reset)
    monkeypatch.setattr(watchdog.dockerx, "remove_container", fake_remove)
    monkeypatch.setattr(watchdog, "archive_traces", lambda no, side: {"ok": True, "message": ""})

    r = await watchdog.requeue_run(run.id, manual=True)
    assert r["ok"] is True
    with session() as s:
        assert s.get(m.TaskRun, run.id).attempt == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_watchdog.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.watchdog'`

- [ ] **Step 3: 写 `watchdog.py`**

```python
"""守护任务：异常重跑 + 配对触发分析。

跑完之后该干什么，只在这里决定。runner 结束时唤醒一次，另有一个周期兜底，
这样不会出现 runner 和定时任务同时对一道题动手的竞态。

两类失败分得很清楚：模型侧的（跑挂、超时、戛然而止、网关打断）计入重跑次数；
工程侧的（push 失败、Token 失效）不计次数，停在原地下一轮再试。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_IDLE, ANALYSIS_RUNNING, ANALYZING, NEEDS_ATTENTION, QUEUED, RUN_DONE,
    RUN_END_STATUSES, RUN_FINISHED, RUN_QUEUED, RUN_RUNNING, RUNNING,
    Task, TaskRun, utc_now,
)
from app.services import dockerx, gsb_repo, settings_store

log = logging.getLogger("watchdog")

_wake = asyncio.Event()
_loop_task: asyncio.Task | None = None
_stopping = False


def wake() -> None:
    """让守护立刻扫一轮，不用等满一个周期。"""
    _wake.set()


def interval_s() -> int:
    return max(30, settings_store.get_int("watchdog.interval_seconds", 300))


def retry_limit() -> int:
    return max(0, settings_store.get_int("watchdog.max_retries", 3))


def can_retry(run: TaskRun, limit: int) -> bool:
    """attempt 从 1 起算，limit 是重跑次数，所以最多跑 limit + 1 次。"""
    return (run.attempt or 1) <= limit


def abnormal_reason(run: TaskRun, container_alive: bool) -> str:
    """非空字符串表示这一跑不算数，需要重来。空串表示正常。"""
    if run.status in (RUN_RUNNING,):
        return "" if container_alive else "容器已经不在了，状态却还停在运行中"
    if run.status not in RUN_END_STATUSES:
        return ""
    if run.status != RUN_FINISHED:
        return f"运行状态 {run.status}"
    verdict = run.verdict or {}
    codes = (verdict.get("process") or {}).get("gateway_errors") or []
    if codes:
        return f"网关返回 {', '.join(str(c) for c in codes)}，这一跑被打断了"
    subtype = (verdict.get("protocol") or {}).get("subtype") or ""
    if subtype and subtype != "success":
        return f"result.subtype={subtype}"
    if not run.trace_file:
        return "没有产出轨迹"
    if not (verdict.get("artifact") or {}).get("changed_files"):
        return "工作目录零改动，这一跑等于没做"
    return ""


def archive_traces(task_no: str, side: str) -> dict:
    """轨迹目录非空就整体改名归档，腾出空目录给下一次跑。镜像拒绝非空目录。"""
    tr = config.TaskPaths(task_no, side).traces
    if not tr.exists() or not any(tr.iterdir()):
        return {"ok": True, "message": "轨迹目录本就为空"}
    target = tr.with_name(f"{tr.name}.archived-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    tr.rename(target)
    tr.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "message": f"已归档到 {target.name}"}


async def requeue_run(run_id: int, *, manual: bool = False) -> dict:
    """把一次跑推倒重来：销毁容器、归档轨迹、回退快照、清结果、重新入队。

    手动重跑走同一条路，只是不看次数上限并把计数清零——两套逻辑迟早会跑偏。
    """
    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is None:
            return {"ok": False, "message": "run 不存在"}
        t = db.get(Task, r.task_id)
        if t is None:
            return {"ok": False, "message": "题目不存在"}
        task_no, side, name = t.task_no, r.side, r.container_name
        snapshot = gsb_repo.snapshot_sha(t.env_snapshot)
        attempt = r.attempt or 1
        task_id = t.id

    if not manual and not can_retry_by_attempt(attempt, retry_limit()):
        _mark_attention(task_id, run_id,
                        f"{side} 侧已经重跑 {retry_limit()} 次仍未正常结束，停下等人工处理")
        return {"ok": False, "message": "重跑次数已用尽"}

    if name:
        await dockerx.remove_container(name)
    archive_traces(task_no, side)
    if snapshot:
        rs = await gsb_repo.reset_side(task_no, side, snapshot)
        if not rs["ok"]:
            # 回退失败属于工程问题，不计次数，下一轮再试
            _note(task_id, f"{side} 侧回退快照失败：{rs['message']}")
            return {"ok": False, "message": rs["message"]}

    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is None:
            return {"ok": False, "message": "run 不存在"}
        r.attempt = 1 if manual else attempt + 1
        r.status = RUN_QUEUED
        r.container_exists = False
        r.exit_code = None
        r.session_id = r.turn_id = ""
        r.trace_file = r.git_diff_stat = r.error = ""
        r.artifact_sha = r.artifact_url = ""
        r.result_json = r.verdict_json = r.trace_summary_json = "{}"
        r.abnormal_json = "{}"
        r.started_at = r.finished_at = None
        t = db.get(Task, r.task_id)
        if t is not None:
            t.status = QUEUED
            t.analysis_status = ANALYSIS_IDLE
            t.gsb_json = t.verify_json = "{}"
        db.query(RunEvent).filter(RunEvent.task_id == task_id,
                                  RunEvent.side == side).delete()
    bus.publish("tasks", {"type": "task", "id": task_id})
    wake()
    return {"ok": True, "message": f"{side} 侧已重新入队"}
```

`RunEvent` 加进文件顶部那条 `from app.models import (...)`。另外两个小工具：

```python
def can_retry_by_attempt(attempt: int, limit: int) -> bool:
    return (attempt or 1) <= limit


def can_retry(run: TaskRun, limit: int) -> bool:
    return can_retry_by_attempt(run.attempt or 1, limit)


def _note(task_id: int, msg: str) -> None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        old = [s for s in (t.auto_error or "").split(" / ") if s]
        if msg not in old:
            old.append(msg)
        t.auto_error = " / ".join(old)[:1000]
    bus.publish("tasks", {"type": "task", "id": task_id})


def _mark_attention(task_id: int, run_id: int, msg: str) -> None:
    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is not None:
            r.abnormal = {"reason": msg, "at": utc_now().isoformat()}
        t = db.get(Task, task_id)
        if t is not None:
            t.status = NEEDS_ATTENTION
    _note(task_id, msg)
```

注意上面 `requeue_run` 草稿里 `db.query(RunEventShim...)` 那行是占位错误，实现时删掉，
事件清理走 `_clear_events`。`can_retry(run, limit)` 对外保留，内部调 `can_retry_by_attempt`。

两个扫描：

```python
async def scan_abnormal() -> list[int]:
    limit = retry_limit()
    with session() as db:
        runs = db.execute(
            select(TaskRun).join(Task, Task.id == TaskRun.task_id)
            .where(Task.status.notin_([NEEDS_ATTENTION, "DISCARDED", "UPLOADED", "DONE"]))
        ).scalars().all()
        items = [(r.id, r.container_name, r.status, r.attempt, r.task_id, r.side,
                  r.trace_file, r.verdict) for r in runs]
    requeued: list[int] = []
    for run_id, name, status, attempt, task_id, side, trace_file, verdict in items:
        alive = (await dockerx.container_state(name)) == "running" if name else False
        with session() as db:
            r = db.get(TaskRun, run_id)
            reason = abnormal_reason(r, alive) if r is not None else ""
        if not reason:
            continue
        if not can_retry_by_attempt(attempt, limit):
            _mark_attention(task_id, run_id,
                            f"{side} 侧第 {attempt} 次仍未正常结束（{reason}），停下等人工处理")
            continue
        log.info("题 %s %s 侧异常重跑：%s", task_id, side, reason)
        with session() as db:
            r = db.get(TaskRun, run_id)
            if r is not None:
                r.abnormal = {"reason": reason, "at": utc_now().isoformat(), "attempt": attempt}
        res = await requeue_run(run_id)
        if res["ok"]:
            requeued.append(run_id)
    return requeued


async def scan_paired() -> list[int]:
    """两侧都正常跑完的题：销毁容器、推产物、开分析。"""
    from app.services import gsb_analyzer

    started: list[int] = []
    with session() as db:
        tasks = db.execute(
            select(Task).where(Task.status.in_([RUNNING, RUN_DONE]),
                               Task.analysis_status == ANALYSIS_IDLE)
        ).scalars().all()
        candidates = []
        for t in tasks:
            runs = db.execute(select(TaskRun).where(TaskRun.task_id == t.id)).scalars().all()
            if len(runs) == 2 and all(r.status == RUN_FINISHED for r in runs):
                candidates.append((t.id, t.task_no, t.repo_url,
                                   gsb_repo.snapshot_sha(t.env_snapshot),
                                   {r.side: (r.id, r.session_id, r.container_name, r.trace_file)
                                    for r in runs}))
    for task_id, task_no, repo_url, snapshot, sides in candidates:
        # 有异常的不进分析，留给 scan_abnormal 重跑
        with session() as db:
            runs = db.execute(select(TaskRun).where(TaskRun.task_id == task_id)).scalars().all()
            if any(abnormal_reason(r, False) for r in runs):
                continue
        _set_task(task_id, status=RUN_DONE)
        if not await _destroy_and_push(task_id, task_no, repo_url, snapshot, sides):
            continue
        if not settings_store.get_bool("auto.analyze", True):
            continue
        _set_task(task_id, status=ANALYZING, analysis_status=ANALYSIS_RUNNING)
        asyncio.create_task(gsb_analyzer.analyze_task(task_id), name=f"gsb-{task_id}")
        started.append(task_id)
    return started


async def _destroy_and_push(task_id, task_no, repo_url, snapshot, sides) -> bool:
    """轨迹导出成功才销毁容器；两侧都 push 成功才算准备好分析。"""
    for side, (run_id, session_id, name, trace_file) in sorted(sides.items()):
        if trace_file and name:
            r = await dockerx.remove_container(name)
            if r.ok:
                _set_run(run_id, container_exists=False)
        elif not trace_file:
            _note(task_id, f"{side} 侧没导出轨迹，容器先留着等人工处理")
            return False
    for side, (run_id, session_id, _name, _tf) in sorted(sides.items()):
        with session() as db:
            r = db.get(TaskRun, run_id)
            if r is not None and r.artifact_url:
                continue
        res = await gsb_repo.commit_and_push(
            task_no, repo_url, side, snapshot,
            message=gsb_repo.commit_message(task_no, side, session_id))
        if not res["ok"]:
            _note(task_id, f"{side} 侧产物推送失败：{res['message']}")
            return False
        _set_run(run_id, artifact_sha=res["sha"], artifact_url=res["url"])
    return True


def _set_run(run_id: int, **fields) -> None:
    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is None:
            return
        for k, v in fields.items():
            setattr(r, k, v)


def _set_task(task_id: int, **fields) -> None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        for k, v in fields.items():
            setattr(t, k, v)
    bus.publish("tasks", {"type": "task", "id": task_id})


async def tick() -> dict:
    return {"requeued": await scan_abnormal(), "analyzing": await scan_paired()}


async def _loop() -> None:
    while not _stopping:
        try:
            await tick()
        except Exception:  # noqa: BLE001
            log.exception("守护扫描异常")
        try:
            await asyncio.wait_for(_wake.wait(), timeout=interval_s())
        except asyncio.TimeoutError:
            pass
        _wake.clear()


async def start() -> None:
    global _loop_task, _stopping
    _stopping = False
    _loop_task = asyncio.create_task(_loop(), name="watchdog-loop")


async def stop() -> None:
    global _stopping
    _stopping = True
    wake()
    if _loop_task:
        _loop_task.cancel()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_watchdog.py -v`
Expected: 14 passed

- [ ] **Step 5: 删掉被取代的模块**

```bash
cd backend && git rm app/services/pipeline.py app/services/task_reset.py
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/watchdog.py backend/tests/test_watchdog.py
git commit -m "func(gsb): 守护任务接管异常重跑与配对触发分析"
```

---

### Task 9: GSB 对比分析

**Files:**
- Create: `backend/app/services/gsb_analyzer.py`
- Test: `backend/tests/test_gsb_analyzer.py`（新建）
- Delete: `backend/app/services/analyzer.py`

**Interfaces:**
- Consumes: `config.TaskPaths`（Task 1）、`models.TaskRun`（Task 2）、`trace.write_index`
- Produces:
  - `VERDICT_LABEL = {"A": "A 更好", "B": "B 更好", "Same": "Same"}`
  - `def strip_paths(text: str, repos: dict[str, Path]) -> str`（从旧 analyzer 的 `_strip_paths` 演化，
    两个副本目录都要剥）
  - `def strip_steps(text: str) -> str`（原样搬 `_strip_steps`）
  - `def strip_markdown(text: str) -> str`
  - `def clean(text: str, repos: dict) -> str` = 上面三个串起来
  - `def extract_json(text: str) -> dict`（原 `_extract_json`，锚点键从 `delivery` 换成 `verdict`）
  - `def normalize(raw: dict, repos: dict) -> dict` 产出落库结构：
    `{"verdict", "reason", "a_findings", "b_findings", "a_startup", "b_startup", "evidence"}`
  - `async analyze_task(task_id: int) -> dict`
  - `async probe_models() -> list[str]` / `async probe_ping() -> dict`（原样搬）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_gsb_analyzer.py
from pathlib import Path

from app.services import gsb_analyzer as ga


def test_strip_markdown_removes_all_markers():
    src = "## 标题\n- 列表项\n1. 编号项\n**加粗** 和 `代码` 和 ~~删除~~"
    got = ga.strip_markdown(src)
    for bad in ("##", "- ", "1. ", "**", "`", "~~"):
        assert bad not in got
    assert "标题" in got and "加粗" in got


def test_strip_steps_removes_step_references():
    assert "第 38 步" not in ga.strip_steps("它在第 38 步里读了文件")
    assert "第 19、20 步" not in ga.strip_steps("第 19、20 步重复 grep")
    assert "步骤 12" not in ga.strip_steps("步骤 12 开始跑测试")


def test_strip_paths_squashes_both_repo_copies():
    repos = {"A": Path("/data/分析/07/repo-A"), "B": Path("/data/分析/07/repo-B")}
    got = ga.strip_paths("改了 /data/分析/07/repo-A/src/x.ts 和 /data/分析/07/repo-B/src/y.ts", repos)
    assert got == "改了 src/x.ts 和 src/y.ts"


def test_strip_paths_squashes_workspace_prefix():
    repos = {"A": Path("/x/repo-A"), "B": Path("/x/repo-B")}
    assert ga.strip_paths("/workspace/lib/a.js 改了", repos).startswith("lib/a.js")


def test_strip_paths_squashes_unknown_absolute_path():
    repos = {"A": Path("/x/repo-A"), "B": Path("/x/repo-B")}
    got = ga.strip_paths("我打开了 /Users/someone/secret/notes.md", repos)
    assert "/Users" not in got
    assert "notes.md" in got


def test_extract_json_tolerates_fence_and_prose():
    text = '好的，结论如下：\n```json\n{"verdict": "A", "reason": "r"}\n```\n'
    assert ga.extract_json(text)["verdict"] == "A"


def test_extract_json_repairs_truncated_tail():
    text = '{"verdict": "B", "reason": "r", "evidence": [{"side": "B"}'
    assert ga.extract_json(text)["verdict"] == "B"


def test_normalize_cleans_reason_and_keeps_structure():
    repos = {"A": Path("/x/repo-A"), "B": Path("/x/repo-B")}
    raw = {
        "verdict": "A",
        "reason": "**A** 在第 3 步改了 /x/repo-A/src/a.ts，B 没改。",
        "a_findings": {"good": ["跑通了 npm test"], "bad": []},
        "b_findings": {"good": [], "bad": ["src/b.ts 里漏了空值判断"]},
        "a_startup": {"steps": ["npm i", "npm run dev"], "commands": ["npm run dev"], "note": ""},
        "b_startup": {"steps": ["npm i"], "commands": [], "note": "起不来"},
        "evidence": [{"side": "A", "file": "src/a.ts", "quote": "export function"}],
    }
    out = ga.normalize(raw, repos)
    assert out["verdict"] == "A"
    assert "**" not in out["reason"]
    assert "第 3 步" not in out["reason"]
    assert "/x/repo-A" not in out["reason"]
    assert "src/a.ts" in out["reason"]
    assert out["a_startup"]["commands"] == ["npm run dev"]
    assert out["evidence"][0]["side"] == "A"


def test_normalize_rejects_unknown_verdict():
    repos = {"A": Path("/x/a"), "B": Path("/x/b")}
    out = ga.normalize({"verdict": "更好的是A", "reason": "x"}, repos)
    assert out["verdict"] == ""


def test_verdict_label_matches_platform_options():
    assert ga.VERDICT_LABEL == {"A": "A 更好", "B": "B 更好", "Same": "Same"}


def test_prompt_states_the_three_excluded_factors(tmp_path):
    prompt = ga.build_prompt(
        task_no="07", question_type="Bug修复", difficulty="困难", languages="Go",
        user_prompt="修一个并发 bug",
        repos={"A": tmp_path / "repo-A", "B": tmp_path / "repo-B"},
        indexes={"A": tmp_path / "i_A.json", "B": tmp_path / "i_B.json"},
        traces={"A": "/x/a.jsonl", "B": "/x/b.jsonl"},
    )
    assert "推理时长" in prompt
    assert "戛然而止" in prompt
    assert "网络" in prompt
    assert "60" in prompt
    # 两侧材料都要出现，不能只喂一边
    assert "repo-A" in prompt and "repo-B" in prompt
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_gsb_analyzer.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.gsb_analyzer'`

- [ ] **Step 3: 写 `gsb_analyzer.py`**

从 `analyzer.py` 搬这些原样不改的部分：`_agent_bin`、`_kill_group`、`SANDBOX_SKIP`、
`_prepare_sandbox`（改成接收 side）、`probe_models`、`probe_ping`、`_STEP_REF` 与
`_SPACE_BEFORE_PUNCT` 两个正则、`_ABS_PATH` 正则。

新增清洗：

```python
_MD_LINE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.、])\s+|^[ \t]*#{1,6}\s+", re.M)
_MD_INLINE = re.compile(r"\*\*|__|~~|`")


def strip_markdown(text: str) -> str:
    """理由会原样交付给评审方，带 markdown 一眼就是机器写的。"""
    if not text:
        return text
    return _MD_INLINE.sub("", _MD_LINE.sub("", text)).strip()
```

`strip_paths` 相比旧版多剥一个副本目录：

```python
def strip_paths(text: str, repos: dict) -> str:
    if not text:
        return text
    roots = [str(p).rstrip("/") for p in repos.values()] + ["/workspace"]
    for root in roots:
        if root and root != "/":
            text = text.replace(root + "/", "").replace(root, _HERE)

    def squash(m: re.Match) -> str:
        parts = [p for p in m.group(0).split("/") if p]
        return parts[-1] if parts and "." in parts[-1] else _HERE

    return _ABS_PATH.sub(squash, text)
```

写作规则与评分口径（`build_prompt` 里内联，不要抽成太多常量）：

```python
WRITING_RULES = """
理由的写法（gsb_reason 正文与 findings 里的每一条都要遵守）：
1. 用第一人称「我」，像我自己看完两份轨迹和两份产物之后随手记下来的口语，不要书面腔。
2. 只写看到的现象和位置。位置一律用文件名、函数名、命令、报错原文来指，
   例如「A 的 lib/dumper.js 里 writeNode 返回了 { text, tag }」「B 跑 npm test 有 3 个用例红」。
3. 禁止 markdown：不要标题、不要列表符号、不要加粗、不要反引号。禁止表情符号。
   禁止比喻、排比、反问、夸张。
4. 禁止「第 38 步」「第 19、20 步」「步骤 12」这类步数说法，一次都不要出现。
   步号只填进 evidence 字段，正文里不写。
5. 禁止任何绝对路径或磁盘目录名，只写仓库内相对路径，例如 src/parser.py。
6. 不写自己这次是怎么核验的：不写装没装依赖、有没有 node_modules、能不能联网、
   跑不跑得起来，不写「产物副本」「沙箱」「我这边」。命令跑不了就只依据代码和轨迹下结论。
7. 禁止使用这些词：首先、其次、最后、综上、总的来说、总之、值得注意的是、此外、另外、
   不仅、而且、显然、令人、堪称、优雅、精妙、丝滑、赋能、闭环、亮点、整体而言、
   可以看出、由此可见、体现了、展现了、表现出色、表现良好、表现一般、基本可用、
   效果不错、非常、极其、十分、相当。
8. A 和 B 必须分别写，不能只写「A 比 B 好」就收尾。每一侧都要写清好在哪、不好在哪，
   是产物问题还是过程问题。过程问题要写清出在哪一步（触发节点）、模型具体做了什么
   （实际行为）、导致了什么后果（业务影响）。产物问题要指向具体文件名、报错信息，
   或者点名哪个需求点没实现。
9. 要体现权衡。两次跑往往各有优劣，写清我在意的是什么、更满意哪一次、基于哪几点做的判断，
   不要给一个没有来由的结论。
10. 选 Same 同样要写详细。Same 不是「看不出差别」的兜底，要写清两边在哪些点上确实等价、
   哪些点上各有优劣相互抵消。一句话的 Same 会被直接拒收。
11. 理由去掉空白之后至少 60 个字；选 Same 时至少 150 个字。
""".strip()

EXCLUDED = """
下面三类情况不许作为判断依据，也不许写进理由：
1. 推理时长。可能受模型部署影响。要衡量效率就看轮次和篇幅，不看耗时。
2. 模型无报错的戛然而止。可能受部署与 harness 适配影响，不算模型自身能力问题。
3. 网络工程错误。网络波动、请求失败、网关 5xx 这类故障不计入。
这三类如果确实出现了，放进 engineering_notes 字段，不要写进 reason。
""".strip()
```

`build_prompt` 签名与主体：

```python
def build_prompt(*, task_no: str, question_type: str, difficulty: str, languages: str,
                 user_prompt: str, repos: dict, indexes: dict, traces: dict) -> str:
    return f"""你是资深工程师，正在复核同一道题的两次独立运行（A 与 B），然后做 GSB 对比判定。
两次跑用的是同一个镜像、同一套配置、同一份 prompt，起点也是同一个 commit，差异只来自模型自身。

【任务信息】
题号：{task_no}
任务类型：{question_type}   难度：{difficulty}   语言/框架：{languages}

【两次跑共用的原始 prompt】
<<<PROMPT
{user_prompt}
PROMPT>>>

【可用材料】
A 侧产物副本：{repos['A']}
B 侧产物副本：{repos['B']}
A 侧轨迹步骤索引（JSON）：{indexes['A']}
B 侧轨迹步骤索引（JSON）：{indexes['B']}
A 侧原始轨迹 jsonl（需要细节时再读，可能很大）：{traces.get('A') or '（无）'}
B 侧原始轨迹 jsonl：{traces.get('B') or '（无）'}

两份产物副本都可以随意改动。优先靠读代码核验需求是否真的实现；装依赖、跑测试、跑构建
这些能跑就跑，跑不起来就完全依据代码与轨迹判断。引用文件一律用相对各自副本根目录的路径。

【工作步骤】
1. 读 prompt，把需求拆成可核验的功能点与约束清单。
2. 分别读两份轨迹索引，看清各自做了什么、顺序如何、哪里出错、哪里重复。
3. 在两份产物副本上逐条核验功能点与约束。
4. 对比两次跑，判定谁更好，或者判定 Same。
5. 分别给出两侧的项目启动方式：读 README、package.json、Makefile、Dockerfile、
   以及轨迹里模型自己跑过的命令，整理成一份别人照着就能跑起来的步骤。
   跑不起来就在 note 里写清卡在哪。

【判定口径】
看交付完整性、指令遵循、任务规划、推理能力、执行能力这几个方面，但不要输出分数，
只输出对比结论与理由。

{EXCLUDED}

【写法要求】
{WRITING_RULES}

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏。结构如下（字段名必须完全一致）：
{{
  "verdict": "A" 或 "B" 或 "Same",
  "reason": "对比理由正文，按写法要求写",
  "a_findings": {{"good": ["…"], "bad": ["…"]}},
  "b_findings": {{"good": ["…"], "bad": ["…"]}},
  "a_startup": {{"steps": ["…"], "commands": ["…"], "note": ""}},
  "b_startup": {{"steps": ["…"], "commands": ["…"], "note": ""}},
  "evidence": [{{"side": "A", "step": 12, "file": "src/x.ts", "quote": "轨迹里出现过的原话片段"}}],
  "engineering_notes": "网关报错、无故中断这类工程问题写这里，没有就写空字符串"
}}
evidence 里的 side 必须是 A 或 B，step 必须是对应那一侧索引里真实存在的序号，
file 必须是那一侧轨迹或产物里出现过的路径，quote 必须是 summary 或 result 里的原文片段。
"""
```

`normalize`：

```python
VERDICT_LABEL = {"A": "A 更好", "B": "B 更好", "Same": "Same"}


def normalize(raw: dict, repos: dict) -> dict:
    c = lambda s: clean(str(s or ""), repos)  # noqa: E731
    verdict = str(raw.get("verdict") or "").strip()
    if verdict not in VERDICT_LABEL:
        verdict = ""
    out = {
        "verdict": verdict,
        "reason": c(raw.get("reason")),
        "engineering_notes": c(raw.get("engineering_notes")),
        "evidence": [],
    }
    for side in ("a", "b"):
        f = raw.get(f"{side}_findings") or {}
        out[f"{side}_findings"] = {
            "good": [c(x) for x in (f.get("good") or []) if str(x).strip()][:10],
            "bad": [c(x) for x in (f.get("bad") or []) if str(x).strip()][:10],
        }
        s = raw.get(f"{side}_startup") or {}
        out[f"{side}_startup"] = {
            # 启动命令是给人照着敲的，不能被 markdown 清洗掉反引号以外的东西，
            # 但绝对路径还是要剥，命令里带本机目录同样是泄漏
            "steps": [strip_paths(str(x), repos) for x in (s.get("steps") or [])][:20],
            "commands": [strip_paths(str(x), repos) for x in (s.get("commands") or [])][:20],
            "note": c(s.get("note")),
        }
    for e in (raw.get("evidence") or [])[:24]:
        if not isinstance(e, dict):
            continue
        side = str(e.get("side") or "").upper()
        if side not in ("A", "B"):
            continue
        out["evidence"].append({"side": side, "step": e.get("step"),
                                "file": c(e.get("file")), "quote": c(e.get("quote"))})
    return out
```

`analyze_task` 参照旧 `analyzer.analyze_task` 写，区别：
沙箱拷两份（`repo-A`、`repo-B`），索引写两份，
`agent` 的 `--workspace` 指向 `paths.analysis`（两个副本的父目录），`cwd` 同上，
落库写 `t.analysis`（原始）与 `t.gsb`（清洗后），`t.analysis_status = ANALYSIS_DONE`，
`t.status = ANALYZED`，最后调 `gsb_verifier.run_verify(task_id)`。
失败时 `t.analysis_status = ANALYSIS_FAILED`、`t.status = RUN_DONE`、
`t.auto_error` 追加原因，不抛出去。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_gsb_analyzer.py -v`
Expected: 11 passed

- [ ] **Step 5: 删掉旧 analyzer**

```bash
cd backend && git rm app/services/analyzer.py tests/test_desc_sanitize.py
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/gsb_analyzer.py backend/tests/test_gsb_analyzer.py
git commit -m "func(gsb): Cursor CLI 做 A/B 对比，产出结论理由与两份启动方式"
```

---

### Task 10: 本地预核验

**Files:**
- Create: `backend/app/services/gsb_verifier.py`
- Test: `backend/tests/test_gsb_verifier.py`（新建）
- Delete: `backend/app/services/verifier.py`、`backend/tests/test_trace_and_verify.py`

**Interfaces:**
- Consumes: `gsb_repo.COMMIT_URL_RE`（Task 3）、`models.Task` / `TaskRun`（Task 2）
- Produces:
  - `MIN_REASON_CHARS = 60`、`MIN_SAME_REASON_CHARS = 150`
  - `BANNED_WORDS: tuple[str, ...]`（与分析 prompt 第 7 条同一份词表）
  - `@dataclass Item(name: str, level: str, message: str)`，level 取 `ok` / `warn` / `block`
  - `def verify(payload: dict) -> dict` 返回 `{"overall": "ok"|"warn"|"block", "items": [...]}`
    `payload` 形如
    `{"gsb": {...}, "user_prompt": str, "env_snapshot": str, "sides": {"A": {...}, "B": {...}}}`
    每侧含 `session_id`、`artifact_url`、`trace_index`（解析好的 dict）、`trace_count`
  - `def run_verify(task_id: int) -> dict`：从库里组装 payload，跑 `verify`，写 `task.verify`
  - `def reason_chars(text: str) -> int` 去掉全部空白后的字数

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_gsb_verifier.py
from app.services import gsb_verifier as v

SHA_A = "a" * 40
SHA_B = "b" * 40
SNAP = "c" * 40
GOOD_REASON = (
    "A 在 src/parser.py 的 parse_header 里补了空值判断，跑 pytest tests/ 的 42 个用例全过。"
    "B 的同一个函数没改，pytest 报了 AssertionError: expected dict got None，"
    "我按报错找到 tests/test_parser.py 第一个用例就红。B 好在 README.md 写清了新参数的含义，"
    "A 的 README.md 没动，别人拿到产物不知道怎么传参。我更在意功能是不是真的跑通，所以选 A。"
)


def _payload(**kw):
    base = {
        "gsb": {"verdict": "A", "reason": GOOD_REASON},
        "user_prompt": "修一个解析 bug",
        "env_snapshot": f"https://github.com/acme/widget/commit/{SNAP}",
        "sides": {
            "A": {"session_id": "sess-a", "artifact_url": f"https://github.com/acme/widget/commit/{SHA_A}",
                  "trace_index": {"first_user_text": "修一个解析 bug", "counts": {"user": 9},
                                  "human_turns": 1}, "trace_count": 1},
            "B": {"session_id": "sess-b", "artifact_url": f"https://github.com/acme/widget/commit/{SHA_B}",
                  "trace_index": {"first_user_text": "修一个解析 bug", "counts": {"user": 7},
                                  "human_turns": 1}, "trace_count": 1},
        },
    }
    for k, val in kw.items():
        if k == "gsb":
            base["gsb"].update(val)
        elif k in ("A", "B"):
            base["sides"][k].update(val)
        else:
            base[k] = val
    return base


def _levels(report):
    return {i["name"]: i["level"] for i in report["items"]}


def test_reason_chars_ignores_whitespace():
    assert v.reason_chars("a b\nc\t d") == 4


def test_good_payload_passes():
    assert v.verify(_payload())["overall"] == "ok"


def test_short_reason_is_blocked():
    r = v.verify(_payload(gsb={"reason": "A 比 B 好。"}))
    assert _levels(r)["reason_length"] == "block"


def test_same_verdict_needs_longer_reason():
    r = v.verify(_payload(gsb={"verdict": "Same", "reason": GOOD_REASON[:80]}))
    assert _levels(r)["reason_length"] == "block"


def test_reason_must_mention_both_sides():
    only_a = "A 在 src/parser.py 的 parse_header 里补了空值判断，" * 4
    r = v.verify(_payload(gsb={"reason": only_a}))
    assert _levels(r)["reason_sides"] == "block"


def test_markdown_in_reason_is_blocked():
    r = v.verify(_payload(gsb={"reason": GOOD_REASON + "\n- 补充一点"}))
    assert _levels(r)["reason_format"] == "block"


def test_emoji_in_reason_is_blocked():
    r = v.verify(_payload(gsb={"reason": GOOD_REASON + " 很好👍"}))
    assert _levels(r)["reason_format"] == "block"


def test_absolute_path_in_reason_is_blocked():
    r = v.verify(_payload(gsb={"reason": GOOD_REASON + " 我打开了 /Users/me/x/y.py"}))
    assert _levels(r)["reason_format"] == "block"


def test_step_reference_in_reason_is_blocked():
    r = v.verify(_payload(gsb={"reason": GOOD_REASON + " 它在第 12 步才发现"}))
    assert _levels(r)["reason_format"] == "block"


def test_banned_word_in_reason_is_blocked():
    r = v.verify(_payload(gsb={"reason": GOOD_REASON + " 总的来说 A 更完整"}))
    assert _levels(r)["reason_format"] == "block"


def test_unknown_verdict_is_blocked():
    assert _levels(v.verify(_payload(gsb={"verdict": ""})))["verdict"] == "block"


def test_same_session_id_is_blocked():
    r = v.verify(_payload(B={"session_id": "sess-a"}))
    assert _levels(r)["session_ids"] == "block"


def test_empty_session_id_is_blocked():
    assert _levels(v.verify(_payload(B={"session_id": ""})))["session_ids"] == "block"


def test_same_artifact_snapshot_is_blocked():
    r = v.verify(_payload(B={"artifact_url": f"https://github.com/acme/widget/commit/{SHA_A}"}))
    assert _levels(r)["artifacts"] == "block"


def test_bad_artifact_url_format_is_blocked():
    r = v.verify(_payload(A={"artifact_url": "https://github.com/acme/widget/commit/abc123"}))
    assert _levels(r)["artifacts"] == "block"


def test_prompt_mismatch_between_traces_is_blocked():
    r = v.verify(_payload(B={"trace_index": {"first_user_text": "别的题", "human_turns": 1}}))
    assert _levels(r)["prompt_match"] == "block"


def test_multi_human_turn_is_blocked():
    r = v.verify(_payload(A={"trace_index": {"first_user_text": "修一个解析 bug", "human_turns": 2}}))
    assert _levels(r)["single_turn"] == "block"


def test_multiple_trace_files_is_blocked():
    assert _levels(v.verify(_payload(A={"trace_count": 2})))["trace_count"] == "block"


def test_missing_trace_is_blocked():
    assert _levels(v.verify(_payload(B={"trace_count": 0})))["trace_count"] == "block"


def test_overall_is_warn_when_only_warnings():
    r = v.verify(_payload(gsb={"reason": GOOD_REASON, "engineering_notes": "跑的时候网关 504 过一次"}))
    assert r["overall"] in ("ok", "warn")
    assert all(i["level"] != "block" for i in r["items"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_gsb_verifier.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.gsb_verifier'`

- [ ] **Step 3: 写 `gsb_verifier.py`**

```python
"""上传前的本地预核验：把 solo2 的判定规则先在本地过一遍。

红项挡住上传，黄项只提示。理由可以在界面上改完再核一次，
不要等平台打回来才发现少写了一半。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.services.gsb_repo import COMMIT_URL_RE

MIN_REASON_CHARS = 60
MIN_SAME_REASON_CHARS = 150

BANNED_WORDS = (
    "首先", "其次", "最后", "综上", "总的来说", "总之", "值得注意的是", "此外", "另外",
    "不仅", "而且", "显然", "令人", "堪称", "优雅", "精妙", "丝滑", "赋能", "闭环",
    "亮点", "整体而言", "可以看出", "由此可见", "体现了", "展现了", "表现出色",
    "表现良好", "表现一般", "基本可用", "效果不错", "非常", "极其", "十分", "相当",
)

_WS = re.compile(r"\s+")
_MD = re.compile(r"^[ \t]*(?:[-*+]|\d+[.、])\s+|^[ \t]*#{1,6}\s+|\*\*|__|~~|`", re.M)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B50\u2764]")
_ABS_PATH = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/)+")
_STEP_REF = re.compile(r"第\s*\d+\s*[步轮]|步骤\s*\d+")


@dataclass
class Item:
    name: str
    level: str
    message: str


def reason_chars(text: str) -> int:
    return len(_WS.sub("", text or ""))


def verify(payload: dict) -> dict:
    gsb = payload.get("gsb") or {}
    sides = payload.get("sides") or {}
    a, b = sides.get("A") or {}, sides.get("B") or {}
    reason = str(gsb.get("reason") or "")
    verdict = str(gsb.get("verdict") or "")
    items: list[Item] = []

    # 结论
    if verdict in ("A", "B", "Same"):
        items.append(Item("verdict", "ok", f"结论 {verdict}"))
    else:
        items.append(Item("verdict", "block", "没有有效的 GSB 结论，只能是 A、B 或 Same"))

    # 理由长度
    need = MIN_SAME_REASON_CHARS if verdict == "Same" else MIN_REASON_CHARS
    n = reason_chars(reason)
    if n >= need:
        items.append(Item("reason_length", "ok", f"理由 {n} 字（去空白）"))
    else:
        extra = "，选 Same 要写清哪些点等价、哪些点各有优劣相互抵消" if verdict == "Same" else ""
        items.append(Item("reason_length", "block", f"理由只有 {n} 字，至少要 {need} 字{extra}"))

    # 两侧都要写到
    mentions_a = bool(re.search(r"(?<![A-Za-z])A(?![A-Za-z])", reason))
    mentions_b = bool(re.search(r"(?<![A-Za-z])B(?![A-Za-z])", reason))
    if mentions_a and mentions_b:
        items.append(Item("reason_sides", "ok", "理由里 A 和 B 都写到了"))
    else:
        missing = "B" if mentions_a else "A"
        items.append(Item("reason_sides", "block",
                          f"理由里没写到 {missing}，两次跑要分别写清好在哪、不好在哪"))

    # 格式
    bad: list[str] = []
    if _MD.search(reason):
        bad.append("含 markdown 标记")
    if _EMOJI.search(reason):
        bad.append("含表情符号")
    if _ABS_PATH.search(reason):
        bad.append("含绝对路径")
    if _STEP_REF.search(reason):
        bad.append("含步数说法")
    hit = [w for w in BANNED_WORDS if w in reason]
    if hit:
        bad.append(f"含禁用词：{'、'.join(hit[:5])}")
    items.append(Item("reason_format", "block" if bad else "ok",
                      "；".join(bad) if bad else "理由格式干净"))

    # SessionID
    sa, sb = str(a.get("session_id") or ""), str(b.get("session_id") or "")
    if not sa or not sb:
        items.append(Item("session_ids", "block", "有一侧没拿到 SessionID"))
    elif sa == sb:
        items.append(Item("session_ids", "block",
                          "两侧 SessionID 相同，说明只跑了一次或者填重了（规则 G9）"))
    else:
        items.append(Item("session_ids", "ok", "两侧 SessionID 各不相同"))

    # 产物快照
    ua, ub = str(a.get("artifact_url") or ""), str(b.get("artifact_url") or "")
    bad_url = [s for s, u in (("A", ua), ("B", ub)) if not COMMIT_URL_RE.match(u or "")]
    if bad_url:
        items.append(Item("artifacts", "block",
                          f"{'、'.join(bad_url)} 侧的产物快照不是 40 位 SHA 的 commit 永久链接"))
    elif ua == ub:
        items.append(Item("artifacts", "block", "两侧产物快照是同一个提交，不可能"))
    else:
        items.append(Item("artifacts", "ok", "两侧产物快照各自独立且格式合规"))

    # 两份轨迹的 prompt 要一致且与表单一致
    want = _WS.sub("", str(payload.get("user_prompt") or ""))
    texts = {s: _WS.sub("", str((sides.get(s) or {}).get("trace_index", {}).get("first_user_text") or ""))
             for s in ("A", "B")}
    off = [s for s, t in texts.items() if t and want and not (t in want or want.startswith(t))]
    if not want:
        items.append(Item("prompt_match", "warn", "题面没有 prompt 正文，没法比对轨迹"))
    elif off:
        items.append(Item("prompt_match", "block",
                          f"{'、'.join(off)} 侧轨迹里的 prompt 与题面对不上（规则 G4）"))
    else:
        items.append(Item("prompt_match", "ok", "两份轨迹的 prompt 与题面一致"))

    # 只收首轮
    multi = [s for s in ("A", "B")
             if int(((sides.get(s) or {}).get("trace_index") or {}).get("human_turns") or 1) != 1]
    items.append(Item("single_turn", "block" if multi else "ok",
                      f"{'、'.join(multi)} 侧轨迹里真人输入不止一轮（规则 T5）" if multi
                      else "两侧都是首轮"))

    # 一次跑只能一份轨迹
    counts = {s: int((sides.get(s) or {}).get("trace_count") or 0) for s in ("A", "B")}
    wrong = [f"{s}={c}" for s, c in counts.items() if c != 1]
    items.append(Item("trace_count", "block" if wrong else "ok",
                      f"轨迹份数不对（{'、'.join(wrong)}），一次跑只允许一份（规则 T4）" if wrong
                      else "两侧各一份轨迹"))

    # 工程问题只提示
    notes = str(gsb.get("engineering_notes") or "").strip()
    if notes:
        items.append(Item("engineering", "warn", f"分析时记下的工程问题：{notes[:200]}"))

    levels = {i.level for i in items}
    overall = "block" if "block" in levels else ("warn" if "warn" in levels else "ok")
    return {"overall": overall, "items": [asdict(i) for i in items]}
```

`run_verify(task_id)` 从库里组装 payload：两侧的 `session_id`、`artifact_url` 从 `TaskRun` 读，
`trace_index` 读 `config.TaskPaths(task_no, side).trace_index` 的 JSON，
`trace_count` 用 `trace.count_traces(paths.traces)`，写 `t.verify = report`，
`overall != "block"` 且 `t.status == ANALYZED` 时保持 `ANALYZED`，不改状态。

`trace.parse_trace` 要补一个 `human_turns` 字段。平台规则 T5 只收首轮，这个数不是 1 就不合格。
在 `parse_trace` 的 `counts` 初始化里加一项 `"human_turns": 0`，并在处理 `type == "user"` 的
那个分支里累加：

```python
            if typ == "user":
                counts["user"] += 1
                is_tool_result = isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                )
                if is_tool_result:
                    ...  # 原有的 tool_result 处理不动
                elif not obj.get("isSidechain"):
                    # 真人这一轮的输入。工具回传和子 agent 的消息都不算
                    counts["human_turns"] += 1
                    if not prompt_id and obj.get("promptId"):
                        prompt_id = str(obj["promptId"])
                        first_user_text = _text_of(content, 200)
```

返回值里加一行 `"human_turns": counts["human_turns"]`（放在顶层，`gsb_verifier` 直接读
`trace_index["human_turns"]`，不用钻进 `counts`）。

配套用例加进 `backend/tests/test_trace_human_turns.py`：

```python
import json

from app.services import trace


def _write(tmp_path, rows):
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return p


def test_single_human_turn(tmp_path):
    p = _write(tmp_path, [
        {"type": "user", "sessionId": "s1", "promptId": "p1",
         "message": {"content": [{"type": "text", "text": "做点事"}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "a.py"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
    ])
    assert trace.parse_trace(p)["human_turns"] == 1


def test_second_human_turn_is_counted(tmp_path):
    p = _write(tmp_path, [
        {"type": "user", "sessionId": "s1", "promptId": "p1",
         "message": {"content": [{"type": "text", "text": "做点事"}]}},
        {"type": "user", "promptId": "p2",
         "message": {"content": [{"type": "text", "text": "继续"}]}},
    ])
    assert trace.parse_trace(p)["human_turns"] == 2


def test_sidechain_user_message_is_not_a_human_turn(tmp_path):
    p = _write(tmp_path, [
        {"type": "user", "sessionId": "s1", "promptId": "p1",
         "message": {"content": [{"type": "text", "text": "做点事"}]}},
        {"type": "user", "isSidechain": True, "promptId": "p9",
         "message": {"content": [{"type": "text", "text": "子 agent 的输入"}]}},
    ])
    assert trace.parse_trace(p)["human_turns"] == 1
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_gsb_verifier.py -v`
Expected: 20 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/gsb_verifier.py backend/app/services/trace.py backend/tests/test_gsb_verifier.py
git rm backend/app/services/verifier.py backend/tests/test_trace_and_verify.py
git commit -m "func(gsb): 本地预核验，平台规则先在本地过一遍"
```

---

### Task 11: 上传到 solo2

**Files:**
- Create: `backend/app/services/gsb_uploader.py`
- Test: `backend/tests/test_gsb_uploader.py`（新建）
- Delete: `backend/app/services/uploader.py`、`backend/app/services/repo.py`、
  `backend/bridges/qa_qc.py`，以及 `qa_bridge.py` 的 `qc_task` / `repo_id_of`

**Interfaces:**
- Consumes: `gate.normalize_choice` / `QUESTION_TYPES` / `REPRO_LEVELS`（Task 5）、
  `gsb_analyzer.VERDICT_LABEL`（Task 9）、`gsb_verifier.run_verify`（Task 10）
- Produces:
  - `API = "/api/v1"`
  - `@dataclass UploadContext`：`task_no`、`user_prompt`、`question_type`、`difficulty`、
    `languages`、`harness_version`、`repro_level`、`env_snapshot`、`verdict`、`reason`、
    `sides: dict[str, dict]`（含 `session_id`、`artifact_url`、`trace_file`、`screencast`）、
    `validity`、`remark`
  - `def field_value(field: dict, ctx: UploadContext) -> tuple[object, str]`
    返回 `(值, 错误说明)`；值为 `None` 且错误为空表示这个字段要人工填
  - `def build_data(fields: list[dict], ctx: UploadContext) -> tuple[dict, list[str]]`
    返回 `(data, 缺失字段的 label 列表)`
  - `async fetch_schema() -> dict` 返回 `{"fingerprint": str, "fields": [...]}`
  - `async probe_identity() -> dict`
  - `async upload_attachment(client, path: Path) -> dict`
  - `async upload_video(client, path: Path) -> str`
  - `async upload_task(task_id: int) -> dict`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_gsb_uploader.py
import json

import pytest

from app.services import gsb_uploader as up


def _schema_fields():
    return json.load(open("docs/gsb-form-schema.sample.json", encoding="utf-8"))["fields"]


def _ctx(**kw):
    base = dict(
        task_no="07", user_prompt="修一个解析 bug", question_type="0-1 代码生成",
        difficulty="困难", languages="Python, pytest", harness_version="2.1.197",
        repro_level="无外部依赖",
        env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40,
        verdict="A", reason="理由正文", validity="有效", remark="",
        sides={
            "A": {"session_id": "sess-a", "artifact_url": "https://github.com/acme/widget/commit/" + "a" * 40,
                  "trace_file": "/tmp/a.jsonl", "screencast": "https://v/a"},
            "B": {"session_id": "sess-b", "artifact_url": "https://github.com/acme/widget/commit/" + "b" * 40,
                  "trace_file": "/tmp/b.jsonl", "screencast": "https://v/b"},
        },
    )
    base.update(kw)
    return up.UploadContext(**base)


def _field(key):
    return next(f for f in _schema_fields() if f["field_key"] == key)


def test_question_type_is_normalized_to_platform_option():
    val, err = up.field_value(_field("question_type"), _ctx())
    assert val == "0-1代码生成"
    assert err == ""


def test_unknown_question_type_reports_error():
    val, err = up.field_value(_field("question_type"), _ctx(question_type="瞎写"))
    assert val is None
    assert "瞎写" in err


def test_harness_and_os_are_fixed():
    assert up.field_value(_field("harness"), _ctx())[0] == "Claude Code"
    assert up.field_value(_field("os_platform"), _ctx())[0] == "MacOS/Linux"


def test_verdict_uses_platform_label():
    assert up.field_value(_field("gsb_verdict"), _ctx())[0] == "A 更好"
    assert up.field_value(_field("gsb_verdict"), _ctx(verdict="Same"))[0] == "Same"
    assert up.field_value(_field("gsb_verdict"), _ctx(verdict="B"))[0] == "B 更好"


def test_side_fields_read_from_their_own_side():
    assert up.field_value(_field("a_session_id"), _ctx())[0] == "sess-a"
    assert up.field_value(_field("b_session_id"), _ctx())[0] == "sess-b"
    assert up.field_value(_field("a_screencast"), _ctx())[0] == "https://v/a"
    assert up.field_value(_field("b_screencast"), _ctx())[0] == "https://v/b"


def test_attachment_field_is_left_for_the_upload_step():
    val, err = up.field_value(_field("a_trace_file"), _ctx())
    assert val is up.PENDING_ATTACHMENT
    assert err == ""


def test_missing_screencast_is_reported_as_manual():
    ctx = _ctx()
    ctx.sides["B"]["screencast"] = ""
    data, missing = up.build_data(_schema_fields(), ctx)
    assert "B-运行录屏" in missing


def test_build_data_fills_every_auto_field():
    data, missing = up.build_data(_schema_fields(), _ctx())
    assert missing == []
    assert data["difficulty"] == "困难"
    assert data["validity"] == "有效"
    assert data["env_snapshot"].endswith("c" * 40)
    assert data["user_prompt"] == "修一个解析 bug"


def test_unknown_required_field_is_reported_not_guessed():
    fields = _schema_fields() + [{
        "field_key": "brand_new_thing", "label": "新字段", "field_type": "text",
        "is_required": True, "is_enabled": True, "side": "", "options": [],
    }]
    data, missing = up.build_data(fields, _ctx())
    assert "新字段" in missing
    assert "brand_new_thing" not in data


def test_disabled_field_is_skipped():
    fields = [dict(_field("remark"), is_enabled=False)]
    data, missing = up.build_data(fields, _ctx())
    assert data == {} and missing == []


def test_optional_empty_field_is_omitted():
    data, missing = up.build_data([_field("remark")], _ctx(remark=""))
    assert missing == []
    assert data.get("remark", "") == ""


@pytest.mark.asyncio
async def test_upload_reports_422_field_errors(monkeypatch, db_session):
    """422 要把平台给的逐字段说明原样带回界面。"""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/me"):
            return httpx.Response(200, json={"username": "me", "real_name": "我"})
        if request.url.path.endswith("/gsb/form-schema"):
            return httpx.Response(200, json={"fingerprint": "fp", "fields": _schema_fields()})
        if request.url.path.endswith("/submissions/upload"):
            return httpx.Response(200, json={"name": "a.jsonl", "path": "/p/a.jsonl", "size": 10})
        return httpx.Response(422, json={"detail": "校验未通过",
                                         "errors": [{"field": "gsb_reason", "message": "至少 60 字"}]})

    monkeypatch.setattr(up, "_transport", lambda: httpx.MockTransport(handler))
    res = await up.upload_task_with_context(_ctx(), task_id=1)
    assert res["ok"] is False
    assert res["fields"]["gsb_reason"] == "至少 60 字"


@pytest.mark.asyncio
async def test_upload_success_returns_submission_id(monkeypatch, tmp_path):
    import httpx

    for side in "ab":
        (tmp_path / f"{side}.jsonl").write_text('{"x":1}\n', encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/me"):
            return httpx.Response(200, json={"username": "me"})
        if request.url.path.endswith("/gsb/form-schema"):
            return httpx.Response(200, json={"fingerprint": "fp", "fields": _schema_fields()})
        if request.url.path.endswith("/submissions/upload"):
            return httpx.Response(200, json={"name": "t.jsonl", "path": "/p/t.jsonl", "size": 8})
        body = json.loads(request.content)
        assert body["schema_fingerprint"] == "fp"
        assert isinstance(body["data"]["a_trace_file"], list)
        assert body["data"]["a_trace_file"][0]["path"] == "/p/t.jsonl"
        return httpx.Response(201, json={"id": 321, "message": "提交成功"})

    monkeypatch.setattr(up, "_transport", lambda: httpx.MockTransport(handler))
    ctx = _ctx()
    ctx.sides["A"]["trace_file"] = str(tmp_path / "a.jsonl")
    ctx.sides["B"]["trace_file"] = str(tmp_path / "b.jsonl")
    res = await up.upload_task_with_context(ctx, task_id=1)
    assert res["ok"] is True
    assert res["submission_id"] == 321
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_gsb_uploader.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.gsb_uploader'`

- [ ] **Step 3: 写 `gsb_uploader.py`**

关键结构：

```python
PENDING_ATTACHMENT = object()  # 占位：值在上传轨迹那一步才拿得到

FIXED = {"harness": "Claude Code", "os_platform": "MacOS/Linux"}


def field_value(field: dict, ctx: UploadContext) -> tuple[object, str]:
    key = field.get("field_key") or ""
    ftype = field.get("field_type") or "text"
    if key in FIXED:
        return FIXED[key], ""
    if ftype in ("attachment", "file"):
        return PENDING_ATTACHMENT, ""
    side = (field.get("side") or "").upper()
    if side in ("A", "B"):
        s = ctx.sides.get(side) or {}
        if key.endswith("_session_id"):
            return s.get("session_id") or None, ""
        if key.endswith("_artifact_snapshot"):
            return s.get("artifact_url") or None, ""
        if key.endswith("_screencast"):
            return s.get("screencast") or None, ""
        return None, ""
    simple = {
        "user_prompt": ctx.user_prompt, "languages": ctx.languages,
        "harness_version": ctx.harness_version, "env_snapshot": ctx.env_snapshot,
        "gsb_reason": ctx.reason, "remark": ctx.remark,
    }
    if key in simple:
        return simple[key] or None, ""
    if key == "question_type":
        v = gate.normalize_choice(ctx.question_type, gate.QUESTION_TYPES)
        return (v, "") if v else (None, f"任务类型「{ctx.question_type}」不在平台选项里")
    if key == "difficulty":
        v = gate.normalize_choice(ctx.difficulty, gate.DIFFICULTIES)
        return (v, "") if v else (None, f"难度「{ctx.difficulty}」不在平台选项里")
    if key == "repro_level":
        v = gate.normalize_choice(ctx.repro_level, gate.REPRO_LEVELS)
        return (v, "") if v else (None, f"可复现等级「{ctx.repro_level}」不在平台选项里")
    if key == "gsb_verdict":
        return gsb_analyzer.VERDICT_LABEL.get(ctx.verdict) or None, ""
    if key == "validity":
        return ctx.validity or "有效", ""
    # schema 里冒出来没见过的字段，不猜，报出来让人工填
    return None, ""
```

`build_data` 遍历 `fields`，跳过 `is_enabled is False`；
值是 `PENDING_ATTACHMENT` 就放进 `data[key] = []` 占位并记进 `attachments` 列表；
值为 `None` 且 `is_required` 就把 `label` 放进 `missing`；
值为 `None` 且非必填就写空串；错误说明非空时把 `f"{label}：{err}"` 放进 `missing`。

`_transport()` 返回 `None`（生产）或 MockTransport（测试注入），`_client()` 里：

```python
def _client() -> httpx.AsyncClient:
    base = settings_store.get("gsb.base_url").rstrip("/")
    cookie = settings_store.get("gsb.session_cookie")
    csrf = settings_store.get("gsb.csrf_token")
    if not (base and cookie and csrf):
        raise RuntimeError("solo2 身份未配置完整（地址 / solo_qa_session / solo_qa_csrf）")
    return httpx.AsyncClient(
        base_url=base, transport=_transport(),
        cookies={"solo_qa_session": cookie, "solo_qa_csrf": csrf},
        headers={"X-CSRF-Token": csrf, "User-Agent": "solo-cli/2.0", "Accept": "application/json"},
        timeout=httpx.Timeout(300, connect=20), follow_redirects=False,
    )
```

`upload_task_with_context(ctx, task_id)` 的流程照设计文档 5.8，
`upload_task(task_id)` 从库里组装 `UploadContext` 后调它。
201 之后写 `t.upload`、`t.status = UPLOADED`、`t.uploaded_at`，不再做任何 git 提交。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_gsb_uploader.py -v`
Expected: 13 passed

- [ ] **Step 5: 清掉老上传链路**

```bash
cd backend && git rm app/services/uploader.py app/services/repo.py bridges/qa_qc.py \
  tests/test_repo_commit.py tests/test_task_branch.py
```

`qa_bridge.py` 里删掉 `qc_task`、`repo_id_of` 和它们用到的常量，只留查重相关的
`run_dedup` / `semantic_review` / `available`。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/gsb_uploader.py backend/app/services/qa_bridge.py backend/tests/test_gsb_uploader.py
git commit -m "func(gsb): 按实时 schema 自动填字段并提交 solo2"
```

---

### Task 12: 接口层与启动接线

**Files:**
- Modify: `backend/app/routers/tasks.py`、`backend/app/schemas.py`、`backend/app/main.py`、
  `backend/app/routers/system.py`
- Test: `backend/tests/test_api_gsb.py`（新建）

**Interfaces:**
- Consumes: 前面全部模块
- Produces（`/api` 前缀下）：
  - `GET  /tasks` 列表，每项含 `runs: [{side, status, attempt, session_id, artifact_url, abnormal}]`
  - `GET  /tasks/{id}` 详情，含 `gsb`、`verify`、`screencast`、`branch_check`、`runs`
  - `POST /tasks/{id}/claim` 领取：跑 `gate.prepare_workspaces` + `gate.run_checks`，
    全绿则建两个 `TaskRun` 并置 `QUEUED`，否则置 `CLAIMED` 并回检查结果
  - `POST /tasks/{id}/gate` 只跑检查
  - `POST /tasks/{id}/gate/fix` body `{"action": "clone_sides"|"reset_sides"|"archive_traces"|"remove_containers"}`
  - `POST /tasks/{id}/runs/{side}/stop`
  - `POST /tasks/{id}/runs/{side}/requeue` 人工重跑单侧（`manual=True`）
  - `POST /tasks/{id}/requeue` 两侧都重跑
  - `POST /tasks/{id}/analyze` 手动触发分析
  - `PUT  /tasks/{id}/gsb` body `{"verdict": str, "reason": str}` 人工改结论后自动重核验
  - `PUT  /tasks/{id}/screencast` body `{"A": url, "B": url}`
  - `POST /tasks/{id}/screencast/{side}/file` multipart 代传视频，回填 url
  - `POST /tasks/{id}/upload`
  - `GET  /tasks/{id}/events?side=A` 事件回放
  - `GET  /tasks/{id}/stream` SSE
  - 删除：`/continue`、`/review`、`/qc`、`/reset` 相关端点
- `main.py`：`pipeline` 换成 `watchdog`，启动日志改成打印守护间隔与重跑上限

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_api_gsb.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(db_session, monkeypatch):
    from app.main import app
    return TestClient(app)


def test_task_list_carries_both_runs(client, db_session):
    r = client.get("/api/tasks")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert {x["side"] for x in item["runs"]} == {"A"}  # fixture 里只建了 A 侧


def test_claim_blocks_and_returns_checks(client, monkeypatch):
    async def prepare(task):
        return {"ok": False, "sides": {}, "message": "分支不合规（缺少 B）"}

    from app.services import gate
    monkeypatch.setattr(gate, "prepare_workspaces", prepare)
    r = client.post("/api/tasks/1/claim")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "B" in r.json()["message"]


def test_put_gsb_reruns_verification(client, monkeypatch):
    called = {}

    from app.services import gsb_verifier
    monkeypatch.setattr(gsb_verifier, "run_verify",
                        lambda tid: called.setdefault("tid", tid) or {"overall": "ok", "items": []})
    r = client.put("/api/tasks/1/gsb", json={"verdict": "B", "reason": "x" * 80})
    assert r.status_code == 200
    assert called["tid"] == 1
    assert r.json()["verify"]["overall"] == "ok"


def test_put_screencast_saves_both_links(client):
    r = client.put("/api/tasks/1/screencast", json={"A": "https://v/a", "B": "https://v/b"})
    assert r.status_code == 200
    detail = client.get("/api/tasks/1").json()
    assert detail["screencast"] == {"A": "https://v/a", "B": "https://v/b"}


def test_requeue_side_calls_watchdog_manually(client, monkeypatch):
    seen = {}

    async def fake(run_id, *, manual=False):
        seen["manual"] = manual
        return {"ok": True, "message": "已重新入队"}

    from app.services import watchdog
    monkeypatch.setattr(watchdog, "requeue_run", fake)
    r = client.post("/api/tasks/1/runs/A/requeue")
    assert r.status_code == 200
    assert seen["manual"] is True


def test_removed_endpoints_are_gone(client):
    for path in ("/api/tasks/1/continue", "/api/tasks/1/review", "/api/tasks/1/qc"):
        assert client.post(path, json={}).status_code == 404


def test_events_can_be_filtered_by_side(client):
    r = client.get("/api/tasks/1/events", params={"side": "B"})
    assert r.status_code == 200
    assert r.json()["items"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_api_gsb.py -v`
Expected: FAIL，多数 404 或 500

- [ ] **Step 3: 改写 `schemas.py`**

```python
class RunOut(BaseModel):
    side: str
    status: str
    attempt: int
    container_name: str
    container_exists: bool
    session_id: str
    turn_id: str
    exit_code: int | None
    artifact_sha: str
    artifact_url: str
    trace_file: str
    git_diff_stat: str
    error: str
    verdict: dict
    trace_summary: dict
    abnormal: dict
    started_at: datetime | None
    finished_at: datetime | None


class TaskOut(BaseModel):
    id: int
    task_no: str
    status: str
    question_type: str
    difficulty: str
    languages: str
    harness: str
    harness_version: str
    os_platform: str
    repro_level: str
    env_snapshot: str
    repo_url: str
    user_prompt: str
    priority: int
    origin: str
    analysis_status: str
    auto_error: str
    branch_check: dict
    gsb: dict
    verify: dict
    screencast: dict
    upload: dict
    runs: list[RunOut]
    created_at: datetime
    updated_at: datetime
```

删掉 `ReviewIn`、`QcOut` 等旧结构，新增：

```python
class GsbIn(BaseModel):
    verdict: str
    reason: str
    validity: str = "有效"
    remark: str = ""


class ScreencastIn(BaseModel):
    A: str = ""
    B: str = ""


class GateFixIn(BaseModel):
    action: str
```

- [ ] **Step 4: 改写 `routers/tasks.py`**

按 Interfaces 里的端点表逐个实现。要点：

- `claim` 先 `prepare_workspaces`，失败就把 `message` 直接回去并留在 `CLAIMED`；
  成功再 `run_checks`，`summarize` 通过才建两个 `TaskRun(status=RUN_QUEUED)` 并置 `QUEUED`，
  同时把 `branch_check` 写进 Task。
- `gate/fix` 的四个动作分别调
  `gate.prepare_workspaces`、`gsb_repo.reset_side`（两侧）、`watchdog.archive_traces`（两侧）、
  `dockerx.remove_container`（两侧）。
- `PUT /gsb` 写完 `t.gsb` 后必须调 `gsb_verifier.run_verify(task_id)` 并把报告一起返回，
  否则界面上改完理由还显示着旧的红项。
- `POST /screencast/{side}/file` 用 `UploadFile`，存到临时文件后调
  `gsb_uploader.upload_video`，把返回的 url 写进 `t.screencast[side]`。
- `GET /events` 支持 `side` 查询参数，不传就两侧都回。

- [ ] **Step 5: 改 `main.py`**

```python
from app.services import prompt_bank, settings_store, watchdog
...
    await scheduler.start()
    await watchdog.start()
...
    log.info("守护: 每 %s 秒扫一轮，自动重跑上限 %s 次",
             settings_store.get_int("watchdog.interval_seconds", 300),
             settings_store.get_int("watchdog.max_retries", 3))
...
    yield
    await watchdog.stop()
    await scheduler.stop()
```

删掉 `pipeline` 的导入与 `resume_stale()` 调用（watchdog 每轮扫描天然覆盖了自愈）。

`routers/system.py` 里引用 `pipeline.snapshot()` 的地方换成 `watchdog` 的状态
（`{"interval": interval_s(), "max_retries": retry_limit()}`），
引用 `qa_bridge.available()` 的质检探针删掉。

- [ ] **Step 6: 跑全量后端测试**

Run: `cd backend && python -m pytest tests -v`
Expected: 全绿。有引用已删模块的残留测试就一并清掉。

- [ ] **Step 7: 提交**

```bash
git add backend/app
git commit -m "func(gsb): 接口层按双跑重写，守护接线到启动流程"
```

---

### Task 13: 前端数据层与题库页

**Files:**
- Modify: `frontend-console/src/api.ts`、`src/store.ts`、`src/status.ts`、
  `src/components/TaskCard.vue`、`src/pages/Bank.vue`、`src/pages/Runs.vue`
- Test: 手动验证（前端没有测试框架，按 Step 5 的清单逐条点）

**Interfaces:**
- Consumes: Task 12 的接口
- Produces:
  - `api.ts` 新增 `requeueRun(id, side)`、`requeueTask(id)`、`putGsb(id, body)`、
    `putScreencast(id, body)`、`uploadScreencastFile(id, side, file)`、`analyze(id)`；
    删除 `continueRound`、`saveReview`、`runQc`、`resetTask`
  - `status.ts` 补齐新状态的中文名与配色：
    `RUN_DONE` 两边跑完、`ANALYZING` 对比中、`ANALYZED` 待录屏上传、`NEEDS_ATTENTION` 需人工
  - `TaskCard.vue` 一张卡里显示 A、B 两个状态徽章，`attempt > 1` 时标出「第 N 次」，
    `abnormal.reason` 非空时红字显示原因

- [ ] **Step 1: 改 `status.ts`**

```ts
export const TASK_STATUS: Record<string, { text: string; tone: string }> = {
  AVAILABLE: { text: '待领取', tone: 'neutral' },
  CLAIMED: { text: '已领取', tone: 'neutral' },
  QUEUED: { text: '排队中', tone: 'info' },
  RUNNING: { text: '运行中', tone: 'active' },
  RUN_DONE: { text: '两边跑完', tone: 'info' },
  ANALYZING: { text: '对比中', tone: 'active' },
  ANALYZED: { text: '待录屏上传', tone: 'warn' },
  UPLOADED: { text: '已提交', tone: 'success' },
  DONE: { text: '已完成', tone: 'success' },
  NEEDS_ATTENTION: { text: '需人工', tone: 'danger' },
  DISCARDED: { text: '已废弃', tone: 'muted' },
}

export const RUN_STATUS: Record<string, { text: string; tone: string }> = {
  PENDING: { text: '未开始', tone: 'muted' },
  QUEUED: { text: '排队', tone: 'info' },
  RUNNING: { text: '运行中', tone: 'active' },
  FINISHED: { text: '已完成', tone: 'success' },
  FAILED: { text: '失败', tone: 'danger' },
  TIMEOUT: { text: '超时', tone: 'danger' },
  INTERRUPTED: { text: '中断', tone: 'danger' },
}
```

- [ ] **Step 2: 改 `api.ts`**

删掉老方法，新增：

```ts
export const requeueRun = (id: number, side: 'A' | 'B') =>
  post(`/tasks/${id}/runs/${side}/requeue`)
export const requeueTask = (id: number) => post(`/tasks/${id}/requeue`)
export const stopRun = (id: number, side: 'A' | 'B') => post(`/tasks/${id}/runs/${side}/stop`)
export const analyze = (id: number) => post(`/tasks/${id}/analyze`)
export const putGsb = (id: number, body: { verdict: string; reason: string; validity?: string; remark?: string }) =>
  put(`/tasks/${id}/gsb`, body)
export const putScreencast = (id: number, body: { A: string; B: string }) =>
  put(`/tasks/${id}/screencast`, body)
export const uploadScreencastFile = (id: number, side: 'A' | 'B', file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return postForm(`/tasks/${id}/screencast/${side}/file`, fd)
}
```

`Task` 类型补上 `runs: Run[]`、`gsb`、`verify`、`screencast`、`branch_check`、`repo_url`，
去掉 `review`、`qc`、`round_no`、`session_id` 等已删字段。

- [ ] **Step 3: 改 `TaskCard.vue`**

题卡主体保持现有布局，状态那一行换成两个并排的 side 徽章：

```vue
<div class="sides">
  <div v-for="r in task.runs" :key="r.side" class="side">
    <span class="side-name">{{ r.side }}</span>
    <StatusPill :status="r.status" :map="RUN_STATUS" />
    <span v-if="r.attempt > 1" class="retry">第 {{ r.attempt }} 次</span>
    <span v-if="r.abnormal?.reason" class="abnormal">{{ r.abnormal.reason }}</span>
  </div>
</div>
```

- [ ] **Step 4: 改 `Bank.vue` 与 `Runs.vue`**

`Bank.vue` 的状态标签页改成：全部 / 待领取 / 已领取 / 排队运行 / 待录屏上传 / 已提交 / 需人工 / 已废弃。
顶部「同项目提示」那一块整个删掉（不再有互斥）。
`Runs.vue` 的列表项按 run 展开，一道题两行。

- [ ] **Step 5: 手动验证**

```bash
cd frontend-console && npm run build
```
Expected: 构建通过，没有 TypeScript 报错。

起后端后逐条点：题库页八个标签页都能切；题卡上 A、B 两个徽章都在；
造一条 `attempt=2` 的数据，卡上显示「第 2 次」。

- [ ] **Step 6: 提交**

```bash
git add frontend-console/src
git commit -m "func(gsb): 前端数据层与题库页按双跑改造"
```

---

### Task 14: 详情页

**Files:**
- Modify: `frontend-console/src/pages/TaskDetail.vue`
- Create: `frontend-console/src/components/SideColumn.vue`、`GsbVerdictEditor.vue`、
  `StartupGuide.vue`、`ScreencastForm.vue`
- Delete: `frontend-console/src/components/{ScoreEditor,VerifyBar,QcPanel}.vue`

**Interfaces:**
- Consumes: Task 13 的 `api.ts`、`status.ts`
- Produces:
  - `SideColumn.vue` props `{ run: Run, events: Event[] }`：一侧的判定、轨迹、产物链接、事件流
  - `GsbVerdictEditor.vue` props `{ gsb, verify }`，emit `save({verdict, reason, validity, remark})`；
    文本域下方实时显示去空白字数与门槛（`Same` 时门槛 150，否则 60），
    核验红项列在上方，红项存在时上传按钮禁用
  - `StartupGuide.vue` props `{ side: string, startup: {steps, commands, note} }`，
    每条命令右侧一个复制按钮
  - `ScreencastForm.vue` props `{ screencast }`，emit `save({A, B})` 与 `upload({side, file})`

- [ ] **Step 1: 搭详情页骨架**

页面从上到下五块：题面与仓库信息（含 `branch_check` 的分支列表）；
A/B 两栏 `SideColumn`；`GsbVerdictEditor`；两个 `StartupGuide` 并排；
`ScreencastForm` 加上传区。

- [ ] **Step 2: 写 `GsbVerdictEditor.vue`**

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{ gsb: any; verify: any; saving: boolean }>()
const emit = defineEmits<{ save: [{ verdict: string; reason: string; validity: string; remark: string }] }>()

const verdict = ref(props.gsb?.verdict ?? '')
const reason = ref(props.gsb?.reason ?? '')
const validity = ref(props.gsb?.validity ?? '有效')
const remark = ref(props.gsb?.remark ?? '')

watch(() => props.gsb, (v) => {
  verdict.value = v?.verdict ?? ''
  reason.value = v?.reason ?? ''
  validity.value = v?.validity ?? '有效'
  remark.value = v?.remark ?? ''
})

// 平台按去掉空白之后的字数算，界面上要显示同一个口径，不然改到 60 还被打回
const chars = computed(() => reason.value.replace(/\s/g, '').length)
const need = computed(() => (verdict.value === 'Same' ? 150 : 60))
const blocks = computed(() => (props.verify?.items ?? []).filter((i: any) => i.level === 'block'))
</script>
```

模板：三个单选（A 更好 / Same / B 更好）、理由文本域、字数计数（不足时红色）、
有效性下拉、备注输入、红项列表、保存按钮。

- [ ] **Step 3: 写 `StartupGuide.vue` 与 `ScreencastForm.vue`**

`StartupGuide` 把 `steps` 渲染成有序步骤，`commands` 每条一行等宽字体加复制按钮，
`note` 非空时用警告色显示。

`ScreencastForm` 两个输入框（A、B），每个旁边一个「选文件代传」按钮；
上传中显示进度文案；两个链接都非空时才允许点「提交到 solo2」。

- [ ] **Step 4: 删旧组件并构建**

```bash
cd frontend-console && git rm src/components/ScoreEditor.vue src/components/VerifyBar.vue src/components/QcPanel.vue
npm run build
```
Expected: 构建通过。

- [ ] **Step 5: 手动验证**

造一条 `ANALYZED` 的数据，逐条点：两栏事件流各自独立；改结论为 Same 后字数门槛跳到 150；
理由里打一个星号立刻出红项；复制按钮能复制命令；填完两个视频链接后上传按钮可点。

- [ ] **Step 6: 提交**

```bash
git add frontend-console/src
git commit -m "func(gsb): 详情页改 A/B 分栏，加结论编辑、启动方式与录屏区"
```

---

### Task 15: 队列页、设置页与收尾

**Files:**
- Modify: `frontend-console/src/pages/Queue.vue`、`src/pages/Settings.vue`、`src/pages/Overview.vue`
- Modify: `README.md`、`docs/Requirements.md`、`docs/Roadmap.md`
- Modify: `docker-compose.yml`（如有 pipeline 相关环境变量）

**Interfaces:**
- Consumes: 前面全部

- [ ] **Step 1: 改 `Queue.vue`**

并发展示从「几道题」改成「几个容器」，去掉「等 #05 跑完（同项目）」那一块，
下半部分的自动流水线进度换成守护状态：上次扫描时间、下次扫描倒计时、本轮重跑了哪些。

- [ ] **Step 2: 改 `Settings.vue`**

按新的 `SPECS` 分组渲染即可（设置页本来就是按 `group` 动态分组的，确认没有硬编码的组名）。
如果有硬编码的「solo-qa 质检」「自动流水线」字样，改成「题目查重」「守护」。

- [ ] **Step 3: 清空运行数据**

```bash
cd /Users/gaoyong/solo-cli && rm -f data/solo-cli.db backend/data/solo-cli.db && rm -rf data/exports/*
```

`prompt.md` 由你手工清空并重新出题，这一步不动它。

- [ ] **Step 4: 重写文档**

`README.md` 的「单题流程」「队列」「一个项目同时只跑一道题」三节按双跑重写，
「目录约定」改成新的 A/B 布局，删掉五维与质检的描述，
新增「定时任务」一节说明扫描周期、异常判定范围与重跑上限。
`docs/Requirements.md` 与 `docs/Roadmap.md` 按设计文档同步。

- [ ] **Step 5: 端到端验证**

```bash
cd /Users/gaoyong/solo-cli && docker compose up --build -d && sleep 40 && docker compose logs backend | tail -30
```
Expected: 日志里有 `Startup Success`、`Console : http://localhost:8788`，
以及新增的一行 `守护: 每 300 秒扫一轮，自动重跑上限 3 次`。

```bash
curl -s localhost:8788/api/health && curl -s localhost:8788/api/tasks | head -c 300
```
Expected: 健康检查 200，任务列表返回空数组（库已清空）。

- [ ] **Step 6: 跑全量测试**

Run: `cd backend && python -m pytest tests -v`
Expected: 全绿，没有引用已删模块的残留。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "func(gsb): 队列设置页收尾，文档与运行数据同步重置"
```

---

## 自查

**规格覆盖**：设计文档 2.1 接口 → Task 11；2.2 字段映射 → Task 11；2.3 平台规则
G1/G2 → Task 5，G3 → Task 4，G4/G5/G6/G7/G9/T4/T5 → Task 10；2.4 出题前提 → 只校验不实现；
3.1/3.2/3.3/3.4 数据模型 → Task 2；4 目录 → Task 1；5.1 → Task 3+4；5.2 → Task 5；
5.3 → Task 7；5.4 → Task 6；5.5 → Task 8；5.6 → Task 9；5.7 → Task 10；5.8 → Task 11；
5.9 前端 → Task 13/14/15；6 删除清单 → 散在各任务的删除步骤，Task 15 收尾复查；
7 错误处理 → Task 8 的两类失败分流；8 测试 → 每个任务都带；9 文档 → Task 15。

**类型一致性**：`side` 全程是 `"A"` / `"B"` 字面量；`run_id` 与 `task_id` 在
Task 6、7、8、12 里始终分开命名；`config.TaskPaths(task_no, side)` 的参数顺序
在所有任务里一致；`gsb_repo.commit_and_push` 的返回键 `sha` / `url` 在 Task 8 的
`_destroy_and_push` 与 Task 11 的 `artifact_url` 里对得上；
`gsb_verifier.verify` 的返回结构 `{"overall", "items"}` 在 Task 12 接口与 Task 14 前端里一致。

**接口对齐复查**：`runner.finalize(run_id, ..., retry_events=...)` 的新参数在 Task 6 定义，
Task 7 的 `scheduler._wait_and_finalize` 与 `_adopt` 调用它时不传该参数（接管路径读不到 stdout，
本来就没有重试事件），默认 `None` 覆盖这种情况。
`trace.parse_trace` 的 `human_turns` 在 Task 10 加，`gsb_verifier` 从
`trace_index["human_turns"]` 顶层读，两处键名一致。
`watchdog.can_retry(run, limit)` 供测试与外部调用，`can_retry_by_attempt(attempt, limit)`
供 `requeue_run` 在已经拿到裸值时调用，两者语义相同。
