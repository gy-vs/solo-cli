# GSB 双跑流程改造 · 设计

日期：2026-09-17
状态：待评审

## 1. 背景与目标

现在的流水线是「一道题跑一次 → Cursor 五维打分 → solo-qa 质检 → 上传 `/api/v1/submissions`」。
新的评测口径变成 GSB 对比：一道题在同一个起点上跑两次（A 与 B），人工录屏，再对两次跑做
对比判定，上传到 solo2 平台的 `/api/v1/gsb/submissions`。

这次改造要达成的目标：

1. 领题时校验远端仓库恰好三个分支（主分支 + A + B），把 A、B 分别 clone 到两个目录。
2. 同一个镜像、同一套配置、同一份 prompt，起两个容器并发跑。
3. 跑完自动 commit 并 push 到各自分支，得到两个产物快照 permalink。
4. 两边都正常跑完后自动触发 GSB 对比分析，产出结论、理由、以及 A/B 各自的项目启动方式。
5. 人工录屏并填两个视频链接，一键上传到 solo2。
6. 一个 5 分钟周期的定时任务，负责异常重跑与配对触发分析。

五维评分、solo-qa 质检、老上传链路全部删除。数据库与导出目录清空重来。

## 2. 平台契约

### 2.1 接口

| 用途 | 方法与路径 |
|---|---|
| 身份校验 | `GET /api/v1/auth/me` |
| 字段清单 | `GET /api/v1/gsb/form-schema` |
| 附件上传 | `POST /api/v1/submissions/upload`，FormData `file`，返回 `{name, path, size}` |
| 视频代传 | `POST /api/v1/submissions/upload`，FormData `file` + `kind=video`，返回 `{url, name}` |
| 提交 | `POST /api/v1/gsb/submissions`，body `{"data": {...}, "schema_fingerprint": "..."}` |

认证沿用 Cookie `solo_qa_session` / `solo_qa_csrf` 加请求头 `X-CSRF-Token`，但站点是
solo2.jzxhnh.com，与旧站点是两套凭证，设置项独立。

`form-schema` 的字段由后台可配，不能硬编码。上传前实时拉一次，按返回的 `fields` 决定
填什么、校验什么，`fingerprint` 原样带回。一份样本存在 `docs/gsb-form-schema.sample.json`，
只作参考，不作为运行时依据。

### 2.2 字段与自动填值

| field_key | 类型 | 必填 | 来源 |
|---|---|---|---|
| `user_prompt` | textarea | 是 | `Task.user_prompt` |
| `question_type` | select | 是 | `Task.question_type` 归一化到平台选项 |
| `difficulty` | select | 是 | `Task.difficulty`，只允许「困难」「地狱」 |
| `languages` | text | 是 | `Task.languages` |
| `harness` | select | 是 | 固定 `Claude Code` |
| `harness_version` | text | 是 | 镜像实测的 CLI 版本 |
| `os_platform` | select | 是 | 固定 `MacOS/Linux` |
| `repro_level` | select | 是 | `Task.repro_level` 归一化 |
| `env_snapshot` | url | 是 | `Task.env_snapshot` |
| `a_session_id` / `b_session_id` | text | 是 | 对应 run 的 `session_id` |
| `a_trace_file` / `b_trace_file` | attachment | 是 | 上传轨迹 jsonl 得到的 `[{name,path,size}]` |
| `a_artifact_snapshot` / `b_artifact_snapshot` | url | 是 | push 后的 commit permalink |
| `a_screencast` / `b_screencast` | video（URL 字符串） | 是 | **人工** 填链接，或选本地文件代传 |
| `gsb_verdict` | select | 是 | 分析产出，取值 `A 更好` / `Same` / `B 更好`，可人工改 |
| `gsb_reason` | textarea | 是 | 分析产出，可人工改 |
| `validity` | select | 是 | 默认「有效」，可人工改 |
| `remark` | textarea | 否 | 人工选填 |

归一化规则：`question_type` 去掉全部空白后与平台选项比对（`0-1 代码生成` → `0-1代码生成`）；
`repro_level` 按完全匹配，匹配不上就在门禁里标出来让人工改题块。两者都匹配不上时阻断上传，
不做猜测性映射。

### 2.3 平台判定规则对流程的硬约束

- **G1**：只收「困难」「地狱」。门禁校验，不符合直接阻断领取。
- **G2**：仓库下有且仅有三个分支，主分支（`main` 或 `master`）加大写的 `A`、`B`。领题时用
  `git ls-remote --heads` 校验，不符合阻断并列出实际分支。
- **G3**：两个产物快照的父提交都必须是初始环境快照。push 前校验 `HEAD^` 等于 `env_snapshot`
  里的 SHA，不符合阻断上传。这也决定了重跑必须先把工作目录 reset 回快照。
- **G4**：两份轨迹里的 prompt 必须一致，且与表单填的 `user_prompt` 相符。核验阶段逐字比对。
- **G5 / G6 / G7**：理由至少 60 字（去空白计），A 和 B 分别写优劣，理由里提到的文件和报错
  要能在对应侧的轨迹或产物里找到，选 Same 要写清等价点。
- **G9**：两个 SessionID 不能相同。
- **T4**：一次跑只允许一个轨迹文件。
- **T5**：只收首轮，轨迹里真人输入必须恰好一轮。**续跑机制在这套流程里是违规的，全部删除。**

## 3. 数据模型

清库重来，不做迁移。`data/solo-cli.db` 与 `data/exports/` 清空。

### 3.1 Task（瘦身）

保留题面与流程状态，去掉所有单跑字段：

```
id, task_no, prompt_hash, status, priority, origin, design_run_id, dedup_json
meta_json, question_type, difficulty, languages, harness, harness_version,
os_platform, repro_level, env_snapshot, user_prompt
repo_url            新增，从题块 meta 的「仓库」解析
branch_check_json   新增，远端分支校验结果
analysis_status, analysis_json    GSB 分析的原始输出
gsb_json            新增，可编辑的结论：verdict / reason / a_startup / b_startup
verify_json         核验报告（含义改为 GSB 核验）
screencast_json     新增，两个视频链接
upload_json
auto_stage, auto_error
created_at, updated_at, claimed_at, finished_at, uploaded_at, done_at, discarded_at
```

删除：`session_id`、`turn_id`、`round_no`、`rounds_json`、`continue_prompt`、`container_name`、
`container_exists`、`image_tag`、`exit_code`、`result_json`、`verdict_json`、
`trace_summary_json`、`trace_file`、`git_diff_stat`、`error`、`review_json`、
`qc_status`、`qc_json`、`qc_at`、`started_at`。

### 3.2 TaskRun（新表）

一道题固定两行，`(task_id, side)` 唯一，side 取 `A` / `B`。

```
id, task_id, side, status, attempt
container_name, container_exists, image_tag, exit_code
session_id, turn_id
result_json, verdict_json, trace_summary_json, trace_file, git_diff_stat, error
artifact_sha, artifact_url        push 后回填
started_at, finished_at
abnormal_json                     watchdog 判定为异常时记原因与时间
```

`attempt` 从 1 起，每次重跑加一。上限设置项叫「自动重跑次数上限」，默认 3，指的是重跑次数，
所以一个 run 最多跑 4 次（首次加 3 次重跑），`attempt` 达到 4 后不再自动重跑。

`TaskRun.status` 取值：`PENDING` / `QUEUED` / `RUNNING` / `FINISHED` / `FAILED` / `TIMEOUT` /
`INTERRUPTED`。

### 3.3 RunEvent

`round_no` 列换成 `side`，其余不变。事件流按 side 分栏展示。

### 3.4 Task 状态机

```
AVAILABLE ──领取──> CLAIMED ──门禁+clone通过──> QUEUED
QUEUED ──调度出队──> RUNNING（至少一个 run 在跑）
RUNNING ──两个 run 都结束──> RUN_DONE
RUN_DONE ──两边都正常 + push 成功──> ANALYZING ──> ANALYZED
ANALYZED ──录屏填好 + 核验无红项 + 上传成功──> UPLOADED ──> DONE

任意阶段失败且不可自动恢复 ──> NEEDS_ATTENTION
人工废弃 ──> DISCARDED
```

`RUN_DONE` 时若有任一 run 异常，由 watchdog 接管重跑，题目退回 `QUEUED`；重跑次数用尽
则落到 `NEEDS_ATTENTION`。

## 4. 目录与命名

```
workspace/<题号>/A          A 分支的 clone
workspace/<题号>/B          B 分支的 clone
出题/轨迹/<题号>/A/          容器挂载点，启动前必须为空
出题/轨迹/<题号>/B/
出题/分析/<题号>/repo-A/     分析沙箱副本
出题/分析/<题号>/repo-B/
出题/分析/<题号>/trace_index_A.json
出题/分析/<题号>/trace_index_B.json
出题/分析/<题号>/gsb_prompt.md
data/exports/<题号>/A/       轨迹副本
data/exports/<题号>/B/
```

容器名：`solo-cc-<题号>-A` / `solo-cc-<题号>-B`。

`config.TaskPaths` 的构造参数从 `round_no` 改成 `side`，`round_suffix` 逻辑删除。

## 5. 模块改造

### 5.1 `services/gsb_repo.py`（新）

取代现有 `repo.py` 的大部分职责。

- `parse_repo_url(meta)`：从题块 meta 的「仓库」字段拿 URL，解析出 `org/repo`。
- `probe_branches(repo_url)`：`git ls-remote --heads`，返回分支列表与是否合规（恰好
  `{main|master, A, B}`）。
- `clone_side(task, side)`：用 `gh.token` 拼 `https://x-access-token:<token>@github.com/...`
  形式的 URL，`git clone --branch <side> --single-branch` 到 `workspace/<题号>/<side>`；
  目录已存在则先校验再决定复用或重建。
- `verify_head(task, side)`：HEAD 等于 `env_snapshot` 的 SHA，且工作区干净。
- `reset_side(task, side)`：`reset --hard <snapshot>` + `clean -fdx`，重跑前调用。
  reset 前把领先快照的 HEAD 备份到 `refs/solo-backup/*`（沿用现有做法）。
- `commit_and_push(task, side)`：`add -A` → commit（作者固定 solo-cli）→ 校验
  `HEAD^ == snapshot` → `push origin <side>` → 返回 `{sha, url}`，url 为
  `https://github.com/<org>/<repo>/commit/<40位SHA>`。
  工作区无改动时返回失败，因为没有改动意味着这一跑没产出，不该提交。

凭证只在拼 URL 时内存拼接，不写进仓库 config，不落日志。

### 5.2 `services/gate.py`（改造）

检查项重写为：

| 名称 | 级别 | 内容 |
|---|---|---|
| `cc.api_key` / `docker` / `image` | block | 沿用 |
| `difficulty` | block | 必须是「困难」或「地狱」（G1） |
| `question_type` | block | 归一化后必须落在平台选项内 |
| `repo_url` | block | 题块里有可解析的仓库地址 |
| `branches` | block | 远端恰好主分支 + A + B（G2），不合规列出实际分支 |
| `snapshot` | block | `env_snapshot` 是 40 位 SHA 的 commit permalink |
| `workspace_A` / `workspace_B` | block | clone 成功、HEAD 等于快照、工作区干净 |
| `leak_A` / `leak_B` | block | 黑名单扫描 |
| `traces_A` / `traces_B` | block | 两个轨迹目录为空 |
| `container_A` / `container_B` | block | 容器名可用 |

删除 `repo_busy` 检查（目录已独立，不再需要同项目互斥）。
修复动作新增 `clone_sides`、`reset_sides`、`archive_traces_both`、`remove_containers_both`。

### 5.3 `services/scheduler.py`（改造）

- 调度单位从 Task 变成 TaskRun。`max_parallel` 语义改为「同时运行的容器数」，默认 4。
- 出队时一道题的 A、B 两个 run 一起入选（要么都起，要么都不起），避免一边先跑完干等。
  若剩余槽位只够一个，这道题留在队列里等下一轮。
- 删除 `_pick` 里的同项目互斥逻辑与 `waiting_on_repo`。
- `_adopt` 按 TaskRun 逐个接管。

### 5.4 `services/runner.py`（改造）

- 入口改为 `run_side(task_id, side)`，挂载 `workspace/<题号>/<side>` 与
  `出题/轨迹/<题号>/<side>`。
- `finalize` 的结果写进 TaskRun 而不是 Task。
- 删除 `build_continue_prompt`、`queue_continue`、`_max_seq` 的续跑分支，以及回填
  `prompt.md` 的 SessionID / TurnID 逻辑（GSB 提交不依赖 prompt.md 回填）。
- 结束后不再直接 spawn 流水线，改为只更新 run 状态，然后唤醒一次 watchdog 立即扫一轮。
  决策逻辑只有 watchdog 一处，不会出现两边同时动手；周期扫描退化成兜底，正常情况下
  跑完到进分析不需要等满 5 分钟。

### 5.5 `services/watchdog.py`（新）

独立的周期任务，间隔默认 300 秒（设置可改）。每轮两件事，互不阻塞。

**扫异常**。对所有非终态的 run 判定 `is_abnormal`：

- `status` 是 `FAILED` / `TIMEOUT` / `INTERRUPTED`；
- `status` 是 `RUNNING` 但容器已不存在；
- `status` 是 `FINISHED` 但没产出轨迹，或工作目录零改动（戛然而止）；
- `verdict.protocol.subtype` 不是 `success`；
- 事件或 stderr 里出现网关 5xx / 429（`system/api_retry` 的 `error_status`，以及 stderr 文本）。

命中则走重跑：销毁容器 → 归档轨迹目录（带时间戳改名）→ `reset_side` 回快照 →
清空该 run 的事件与结果 → `attempt += 1` → `status = QUEUED`。
`attempt` 超过上限（默认 3）时不再重跑，把 run 标成终态，题目落 `NEEDS_ATTENTION`，
原因写进 `abnormal_json` 与题卡。

**扫配对**。找 `analysis_status == IDLE` 且两个 run 都是 `FINISHED` 且都不异常的题，
按顺序做三件事：轨迹已经导出到宿主机就销毁两个容器（没导出成功就留着容器让人工去捞，
这一条沿用现有流水线的做法）；对两边 `commit_and_push` 拿产物快照；触发 GSB 分析。
push 失败记 `auto_error` 并停在 `RUN_DONE`，下一轮再试，不计入重跑次数，因为这不是
模型的问题。

**人工入口**。题卡上保留一个「重跑这一侧」和一个「两边都重跑」，走的是和自动重跑
完全相同的那套动作（销毁容器、归档轨迹、reset 回快照、清事件、重新入队），区别只是
不检查 `attempt` 上限并把计数清零。这取代原来的 `task_reset.py`。

### 5.6 `services/gsb_analyzer.py`（取代 `analyzer.py`）

在后端进程（宿主侧）跑 Cursor CLI，工作目录设为 `出题/分析/<题号>/`，里面有 `repo-A`、
`repo-B` 两个产物副本和两份轨迹索引。

产出 JSON：

```json
{
  "verdict": "A" | "B" | "Same",
  "reason": "对比理由正文",
  "a_findings": {"good": ["..."], "bad": ["..."]},
  "b_findings": {"good": ["..."], "bad": ["..."]},
  "a_startup": {"steps": ["..."], "commands": ["..."], "note": "跑不起来时写原因"},
  "b_startup": {"steps": ["..."], "commands": ["..."], "note": ""},
  "evidence": [{"side": "A", "file": "src/x.ts", "quote": "轨迹或产物里的原文片段"}]
}
```

理由的写作规则（写进 prompt，落库前再机器清洗一遍）：

1. 第一人称「我」，口语，像我自己看完两份轨迹和两份产物后记下来的。
2. 只写事实与位置，位置用文件名、函数名、命令、报错原文来指。
3. 禁止 markdown（标题、列表符号、加粗、反引号）、禁止表情符号、禁止比喻排比反问。
4. 禁止「第 N 步」这类步数说法，步号只进 `evidence`。
5. 禁止绝对路径，只写仓库内相对路径。
6. 禁止写自己的核验环境状况（装没装依赖、跑不跑得起来、「产物副本」「我这边」）。
7. 禁用词表沿用现有 `WRITING_RULES` 第 4 条那一串。
8. A 和 B 分别写，各自好在哪、不好在哪，是产物问题还是过程问题。过程问题要写清出在哪一步
   （触发节点）、模型具体做了什么（实际行为）、导致了什么后果（业务影响）；产物问题要指到
   具体文件名、报错信息或未实现的需求点。
9. 要体现权衡：两次跑往往各有优劣，写清我在意什么、基于哪几点做的判断，不给没来由的结论。
10. 选 Same 同样要写详细，写清哪些点确实等价、哪些点各有优劣相互抵消。一句话的 Same 不合格。
11. **不许纳入判断的因素**（明确写进 prompt）：推理时长（可能受部署影响，效率只看轮次与篇幅）；
    模型无报错的戛然而止（受部署与 harness 适配影响）；网络工程错误（网络波动、请求失败）。
    这三类如果出现，只在 `remark` 里提，不写进理由，也不作为 GSB 结论的依据。

`_strip_paths` 与 `_strip_steps` 从现有 analyzer 搬过来复用，再补一个 `_strip_markdown`。

### 5.7 `services/gsb_verifier.py`（取代 `verifier.py`）

落库后跑核验，红项阻止上传，黄项提示。

红项：

- 理由去空白后不足 60 字；
- 理由里没有分别写到 A 和 B；
- `verdict` 是 `Same` 但理由不足 150 字或没写等价点；
- 理由含 markdown 标记、表情符号、绝对路径、步数说法、禁用词；
- 理由提到的文件在对应侧的轨迹索引与产物副本里都找不到（对应 G6）；
- 两个 `session_id` 相同（G9）或为空；
- 两个 `artifact_snapshot` 相同或格式不符合平台的 40 位 SHA 正则；
- 任一 `artifact_snapshot` 的父提交不是 `env_snapshot`（G3）；
- 两份轨迹里的 prompt 不一致，或与 `user_prompt` 不符（G4）；
- 任一轨迹里真人输入不是恰好一轮（T5）；
- 任一 side 的轨迹文件缺失或多于一份（T4）。

黄项：`harness_version` 与镜像实测值不一致；某一侧零改动；理由里提到的报错在轨迹里找不到原文。

### 5.8 `services/gsb_uploader.py`（取代 `uploader.py`）

1. `GET /auth/me` 验身份，失败提示更新 Cookie。
2. `GET /gsb/form-schema` 拿 `fields` 与 `fingerprint`。
3. 遍历 `fields`，按 5.2 的映射表取值。schema 里出现了映射表没覆盖的必填字段时，
   不猜值，直接把字段名报出来要求人工填。
4. 两份轨迹各 `POST /submissions/upload` 拿 `{name, path, size}`，组成单元素数组。
5. 视频字段取 `screencast_json` 里的链接；若用户上传的是本地文件，先
   `POST /submissions/upload` 带 `kind=video` 换成 url。
6. `POST /gsb/submissions`，body `{data, schema_fingerprint}`。
7. 201 成功写 `upload_json` 并置 `UPLOADED`；422 把 `errors[]` 逐字段回显；
   401/403 提示更新 Cookie；503 等 3 秒重试一次（沿用现有做法）。

上传成功后不再做「提交工作区代码」——产物在分析阶段就已经 commit 并 push 了。

### 5.9 前端

- `TaskCard.vue`：一张卡显示 A/B 两个状态徽章与各自 `attempt`，异常次数超限标红。
- `TaskDetail.vue`：改成左右分栏。上半部分是题面、仓库、分支校验；中间 A/B 两栏各自的
  事件流、判定、轨迹、产物快照链接；下半部分依次是 GSB 结论区（verdict 单选 + reason
  文本域，实时显示去空白字数与核验红黄项）、启动方式区（A/B 各一块，步骤与命令带复制
  按钮）、录屏区（两个输入框贴链接，另有本地文件上传代传）、上传区（字段预览 + 上传 +
  422 逐字段回显）。
- `Queue.vue`：并发展示改成容器级。
- `Settings.vue`：删掉 solo-qa 质检组与五维相关项；新增 GSB 平台组（base_url、
  `solo_qa_session`、`solo_qa_csrf`）与守护组（扫描间隔、重跑上限）。
- 删除 `ScoreEditor.vue`、`VerifyBar.vue`、`QcPanel.vue`。

## 6. 删除清单

- `backend/app/services/verifier.py`、`analyzer.py`、`uploader.py`、`pipeline.py`、
  `task_reset.py`（重写为 watchdog 里的 reset）
- `backend/app/services/qa_bridge.py` 的质检部分与 `repo_id_of`（查重部分保留给出题页）
- `backend/bridges/qa_qc.py`
- `backend/app/services/repo.py`（职责并入 `gsb_repo.py`）
- 前端 `ScoreEditor.vue`、`VerifyBar.vue`、`QcPanel.vue`
- 续跑相关的全部代码、字段、接口与测试
- 对应的测试文件：`test_desc_sanitize.py`、`test_trace_and_verify.py`、
  `test_continue_round.py`、`test_repo_commit.py`、`test_repo_siblings.py`、
  `test_reset_backfill.py` 按新逻辑重写或删除

## 7. 错误处理原则

- 模型侧的问题（跑挂、超时、戛然而止）由 watchdog 自动重跑，上限 3 次。
- 工程侧的问题（push 失败、schema 拉不到、Cookie 过期）不计入重跑次数，停在当前阶段，
  原因写进 `auto_error`，下一轮 watchdog 再试或等人工。
- 核验红项不阻塞流程推进，只阻止上传，理由可以人工编辑后重新核验。
- 任何一步都不回滚已经拿到的结果：轨迹导出成功才销毁容器，push 成功才进分析。

## 8. 测试

- `gsb_repo`：分支校验的各种组合（少 A、多一个分支、主分支叫 master）、产物快照
  父提交校验、URL 拼接。
- `watchdog`：异常判定的每一条分支、重跑上限、配对触发的前置条件。
- `gsb_analyzer`：JSON 提取容错、markdown 与步数与绝对路径的清洗。
- `gsb_verifier`：每一条红项都有一个用例。
- `gsb_uploader`：字段映射、schema 出现未知必填字段时的行为、422 回显。
- 调度：A/B 成对出队、槽位不足时不半边启动。

## 9. 文档同步

`docs/Requirements.md` 与 `docs/Roadmap.md` 按本设计重写，`README.md` 的流程章节同步更新。
