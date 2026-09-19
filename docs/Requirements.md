# Solo CLI 控制台 · 需求与方案设计

> 版本 v0.2 · 状态：已确认（2026-09-15）
> 项目定位：本地运行的可视化控制台，把「领题 → 一次性容器内跑 Claude Code → 判定 → Cursor CLI 分析打分 → 补全参数 → 一键上传 solo-qa → 人工确认后销毁容器」串成流水线，支持多题并行。

---

## 0. 已确认的决策

| 问题 | 决策 |
|---|---|
| 五维打分与描述 | 调用 **Cursor CLI（`agent`）+ Opus 5** 做项目实现分析并按需求文档五维评分表打分与描述；描述第一人称、口语化、去 AI 化、禁表情与修辞；结果须与轨迹文件相互印证 |
| `prompt.md` 形态 | 多题汇总文件，以 `题号：` 分段 |
| 镜像 | `adminfather/benzhi-claude-code2:20260919`：已推到 Docker Hub，`docker pull` 即可获得。入口脚本与隔离参数同 `20260915-mount`（`/workspace` 允许非空，用于映射初始快照仓库），CLI 仍为 2.1.197。旧的 `adminfather/benzhi-claude-code:20260915-mount` 不再使用 |
| 容器销毁 | 人工点「完成」后销毁 |
| 轮次 | 每题只跑一轮 |

---

## 1. 工作点清单

| # | 工作点 | 一句话目标 | 关键约束 |
|---|---|---|---|
| W1 | 题库拉取与消费标记 | 解析 `prompt.md` 多题，列出未领取题目；领取后标记，下次不再展示 | 标记状态落库；只回填 SessionID / PromptID 两行，不改正文 |
| W2 | 一次性容器执行 CC，多开并行 | 每题一个容器 `solo-cc-NN`，宿主 `workspace/NN` 挂到容器 `/workspace`，prompt 经 stdin 注入；并发上限可配 | 只发送 prompt 正文；容器内不出现任何 CLAUDE.md / skill / memory / 题库文件 |
| W3 | 完成判定与轨迹回填 | 区分 正常完成 / 异常中断 / 超时；提取 SessionID、PromptID 回填 `prompt.md`；导出 `.jsonl` | 信号来自 `stream-json` 的 `result` 事件 + 轨迹 jsonl + git diff |
| W4 | Cursor CLI 五维分析 | 在产物副本上运行 `agent -p --model <opus-5>`，输出五维分数、第一人称描述与证据索引；后端与轨迹交叉核验 | 分析在宿主侧/后端容器内进行，不进 CC 容器、不进轨迹 |
| W5 | 一键上传 solo-qa | 按 `POST /api/v1/submissions` 契约组装 23 字段上传；Cookie/CSRF/CC Key/Cursor Key 为设置页配置项，持久化 | 两步上传：`/submissions/upload` → `/submissions` |
| W6 | 隔离与生命周期 | 一题一容器；人工点「完成」后 `rm`；代码与轨迹在宿主侧持久化 | 销毁前校验轨迹已导出 |
| W7 | 高端大气的界面 | 深色「任务指挥中心」：舱位卡片 + 实时事件流 + 详情抽屉 | `docker compose up` 后 `localhost` 可访问 |

---

## 2. 系统架构

```
┌──────────────────────────── 浏览器  http://localhost:8788 ─────────────────────────────┐
│  frontend-console  (Vue 3 + TypeScript + Tailwind + Naive UI)                            │
│  总览 · 题库 · 运行舱 · 题目详情(五维编辑器) · 设置                                       │
└───────────────────────────────────────┬──────────────────────────────────────────────────┘
                                        │ REST + SSE
┌───────────────────────────────────────▼──────────────────────────────────────────────────┐
│  backend  (Python 3.12 + FastAPI + SQLite + docker CLI/SDK + Cursor CLI `agent`)          │
│  ├─ prompt_bank   解析/标记/回填 prompt.md                                                │
│  ├─ scheduler     并发槽位、队列、超时                                                    │
│  ├─ runner        docker run -i … print < prompt · stream-json 采集 · 销毁                │
│  ├─ verdict       完成判定 · 轨迹解析(sessionId/promptId) · 轨迹步骤索引                  │
│  ├─ analyzer      产物副本 + 轨迹摘要 → agent -p --model opus-5 → 五维 JSON → 交叉核验     │
│  ├─ uploader      solo-qa 两步上传                                                        │
│  └─ settings      配置项加密持久化                                                        │
└──────────┬──────────────────────────────────────┬────────────────────────────────────────┘
           │ /var/run/docker.sock                 │ bind mount（宿主机绝对路径）
┌──────────▼───────────────┐         ┌────────────▼──────────────────────────────────────┐
│  Docker Desktop (宿主机)  │         │  /Users/gaoyong/solo-coder-0908/                   │
│  solo-cc-01  solo-cc-02… │  ◄────► │   ├─ prompt.md               题库 + 回填            │
│  一题一容器，一次性        │         │   ├─ workspace/NN/          → 容器 /workspace       │
└──────────────────────────┘         │   ├─ 出题/轨迹/NN/           → 容器 projects 目录    │
                                     │   └─ 出题/分析/NN/           产物副本 + 分析结果      │
                                     └───────────────────────────────────────────────────┘
```

backend 通过挂入的 `docker.sock` 让宿主 daemon 创建 CC 容器，`-v` 的宿主路径由配置 `paths.coder_root` 提供；同时 `coder_root` 也挂进 backend（`/host/coder`），供轨迹解析与 Cursor CLI 分析直接读取。

**项目目录**

```
solo-cli/
├─ docs/               Requirements.md · Roadmap.md · DesignSpec.md
├─ backend/
├─ frontend-console/
├─ docker-compose.yml
└─ .sop
```

---

## 3. 详细设计

### 3.1 W1 · 题库解析与消费标记

**格式**：文件由多个题块组成，每块以 `题号：NN` 起始；随后为 `键：值` 行（全角冒号）；`以下为发送给模型的 prompt 正文，整段复制。` 之后到下一个 `题号：` 或文件末尾之间的文本为 **prompt 正文**（原样保留）。

**字段映射**

| prompt.md 键 | 落库字段 | solo-qa 字段 |
|---|---|---|
| 题号 | `task_no` | — |
| 仓库 / 本地路径 / 容器工作目录 / 轨迹目录 / 来源说明 | `meta.*` | — |
| 任务类型 | `question_type` | `question_type`（solo-qa 侧会把「0-1 代码生成」归一为「0-1代码生成」） |
| 任务难度 | `difficulty` | `difficulty` |
| 语言/框架 | `languages` | `languages` |
| Harness | `harness` | `harness` |
| Harness 版本 | `harness_version` | `harness_version`（以镜像 `claude --version` 实测值为准，冲突时界面提示） |
| 操作系统 / 环境可复现等级 | 同名 | `os_platform` `repro_level` |
| 初始环境快照 | `env_snapshot` | `env_snapshot`（40 位 SHA permalink 正则校验） |
| SessionID / TurnID/PromptID | `session_id` `turn_id` | 运行后回填 |
| prompt 正文 | `user_prompt` | `user_prompt` |

**消费标记**：唯一键 `task_no + sha256(user_prompt)`。题库页只显示 `AVAILABLE`。`prompt.md` 变更时只增量导入未见过的题块。

**回填**：仅替换目标题块内 `SessionID：` 与 `TurnID/PromptID：` 两行的值；若 `出题/prompts/NN.md` 存在且与题块一致，同步回写。回填前生成 `prompt.md.bak.<时间戳>`。

### 3.2 W2 · 一次性容器执行与隔离

**镜像入口事实（`benzhi-claude-code2:20260919`，CLI 2.1.197，源文件 `~/Desktop/claude-code-镜像/runtime/entrypoint.sh`）**

- `ENTRYPOINT /usr/local/bin/entrypoint.sh`，`CMD interactive`，`WORKDIR /workspace`，`USER node`
- 只接受一个参数 `interactive | print`；`print` = `-p --output-format stream-json --verbose`
- 固定隔离参数：`--safe-mode --disable-slash-commands --setting-sources '' --settings '{"autoMemoryEnabled":false}' --strict-mcp-config --mcp-config '{"mcpServers":{}}' --tools 'Bash,Read,Write,Edit,Glob,Grep' --dangerously-skip-permissions`
- 一次性：`~/.task-session-started` 存在即拒绝二次启动；轨迹目录必须为空；禁止 memory 目录
- `/workspace` 允许非空（2026-09-15 修改），用于挂载已 clone 到快照 commit 的仓库

**挂载与启动**

```bash
docker run -i --name solo-cc-NN --label solo-cli.task=NN \
  -e apikey=<cc.api_key> \
  -v <coder_root>/workspace/NN:/workspace \
  -v <coder_root>/出题/轨迹/NN:/home/node/.claude/projects \
  --memory 4g --cpus 2 \
  <cc.image> print  < prompt.txt
```

prompt 经 stdin 注入，不出现在命令行、`docker inspect`、`ps`。stdout 逐行为 `stream-json` 事件，写入 `RunEvent` 并 SSE 推送；`result` 事件即结论。容器退出后**保留**，供人工点「完成」后销毁。

**已实测（2026-09-15，Docker Desktop 29.1.5 / x86_64）**：非空 `/workspace` 挂载可正常到达 CLI 且隔离参数完整；容器内 `node`(uid 1000) 对挂载的工作目录、已有文件、轨迹目录均可写；宿主侧文件归属为当前用户。

**启动前泄漏扫描（硬门禁）**

1. `workspace/NN` 为 git 仓库，`HEAD == env_snapshot SHA`，`git status --porcelain` 为空（含未跟踪）；不满足时提供「重置到快照」（`git clean -fdx && git reset --hard <sha>`，二次确认）。
2. 目录内不存在黑名单：`CLAUDE.md` `AGENTS.md` `.claude/` `.cursor*` `*.mdc` `prompt*.md` `题*` `需求文档`（可配置）。
3. `出题/轨迹/NN/` 为空（一题一份轨迹，规则 T4）。

**并发与超时**：`scheduler.max_parallel`（默认 3）；`run.timeout_minutes`（默认 120）超时 `docker stop -t 30` 后标记 `TIMEOUT`。

### 3.3 W3 · 完成判定、轨迹与回填

| 层 | 来源 | 判定 |
|---|---|---|
| 进程层 | `docker wait` 退出码、容器状态 | 非 0 / 137 → `INTERRUPTED` |
| 协议层 | `result.subtype`（`success` / `error_max_turns` / `error_during_execution`）、`is_error` | 非 success → `FAILED` |
| 产物层 | 轨迹 jsonl（`sessionId`、首条非 sidechain `user.promptId`、消息数、工具调用数）；`git status/diff --stat` | 轨迹缺失或 diff 为空 → 标「疑似未产出」 |

`session_id` = 轨迹文件名 UUID（与 `result.session_id` 交叉校验）；`turn_id` = 首条 `type=user` 且 `isSidechain=false` 的 `promptId`（本机 2.1.x 轨迹已验证该字段存在）。轨迹从 `出题/轨迹/NN/-workspace/<sessionId>.jsonl` 复制到 `exports/NN/`，详情页可下载。

**轨迹步骤索引**（供 W4 印证）：解析 jsonl 生成 `steps[]`：`{step, ts, role, tool, args_summary, result_summary, files[]}`，并持久化为 `出题/分析/NN/trace_index.json`。

### 3.4 W4 · Cursor CLI 五维分析

**运行方式**：backend 镜像内安装 Cursor CLI（`curl https://cursor.com/install -fsS | bash`），凭证走配置项 `cursor.api_key`（`CURSOR_API_KEY`）。模型配置项 `cursor.model`，默认 **`claude-opus-5-thinking-high`**（2026-09-15 用 User API Key 实测调通）。

**实测事实（CLI 2026.02.27）**：API Key 模式下 `agent models` / `--list-models` 返回「No models available」，但 `--model` 校验正常；完整模型列表可从 `agent -p --model __probe__ "x"` 的报错 `Cannot use this model: … Available models: a, b, c` 中解析得到，偶发返回空列表需重试 1–3 次。设置页模型下拉即用此方式拉取，失败时回退到内置静态列表（Opus 5 系列：`claude-opus-5-{low,medium,high}`、`claude-opus-5-thinking-{low,medium,high,xhigh,max}`）。

**分析沙箱**：把 `workspace/NN` 复制到 `出题/分析/NN/repo/`（含 `.git`），`agent` 在副本上运行，允许执行命令（跑测试、构建）以验证产物，绝不触碰原目录。

```bash
agent -p --force --trust --model <cursor.model> --output-format json \
  --workspace <coder_root>/出题/分析/NN/repo  < analysis_prompt.txt
```

**输入**（`analysis_prompt.txt`，由后端模板生成）

1. 题目 prompt 原文
2. 五维评分表（需求文档「第三步」的维度定义与 1–5 档锚点，转写为结构化 rubric）
3. 轨迹步骤索引 `trace_index.json` 路径（agent 自行读取）
4. 输出契约：严格 JSON

```json
{
  "delivery":    {"score": 1-5, "description": "…", "evidence": [{"step": 12, "file": "src/diff.ts", "quote": "…"}]},
  "instruction": {…}, "planning": {…}, "reasoning": {…}, "execution": {…},
  "other_issues": "…",
  "requirement_coverage": [{"point": "Myers 行级差分", "status": "done|partial|missing", "evidence": "…"}],
  "verification": {"commands": ["npm test"], "summary": "…"}
}
```

**描述写作约束（模板内强制，后端再校验）**

- 第一人称「我」，口语化，直接描述看到的现象与位置（第几步、哪个文件、哪条命令、什么报错）
- 禁止：表情符号、markdown 标记、比喻/排比/反问/夸张、「首先/其次/最后/综上/总的来说/值得注意的是/此外/不仅…而且」等结构词与 AI 高频词
- 每条描述 2–6 句；满分时写一句「我逐条对了约束，没发现违背」类的具体说明
- 只写模型自身能力造成的问题，不写网关/网络问题

**后端交叉核验（「相互印证」的落地）**

| 检查 | 方法 | 结果 |
|---|---|---|
| 证据步骤存在 | `evidence.step` ∈ `trace_index.steps` | 缺失 → 该维度标黄 |
| 文件出现于轨迹 | `evidence.file` 在对应步骤 `files[]` 中 | 不符 → 标黄 |
| 引文可定位 | `quote` 为该步骤 args/result 的子串（归一化空白） | 不符 → 标黄 |
| 分数与描述一致 | `delivery.score ≥ 4` 但 `requirement_coverage` 含 `missing` → 冲突 | 标红 |
| 去 AI 化 | 黑名单词表 + emoji/markdown 正则 | 命中 → 标黄并高亮词 |

核验结果与命中率展示在详情页；任一标红禁止上传，标黄允许人工改后上传。人工可直接编辑五维分数与描述，编辑后重新跑核验。

### 3.5 W5 · 一键上传 solo-qa

**配置项（设置页，SQLite 加密存储，掩码显示）**

| 键 | 说明 | 默认 |
|---|---|---|
| `qa.base_url` | solo-qa 地址 | `https://solo2.jzxhnh.com` |
| `qa.session_cookie` | `solo_qa_session` 值 | — |
| `qa.csrf_token` | `solo_qa_csrf` 值，同时用于 `X-CSRF-Token` 头 | — |
| `cc.api_key` | 网关 Key，注入容器 `apikey` | — |
| `cc.image` | 镜像 | `adminfather/benzhi-claude-code2:20260919` |
| `cursor.api_key` / `cursor.model` | Cursor CLI 凭证与模型；首次启动可从 `.env` 的 `CURSOR_API_KEY` / `CURSOR_MODEL` 种子导入 | — / `claude-opus-5-thinking-high` |
| `paths.coder_root` | 宿主机绝对路径 | `/Users/gaoyong/solo-coder-0908` |
| `scheduler.max_parallel` / `run.timeout_minutes` | 并发与超时 | `3` / `120` |

设置页「测试连接」：`GET /api/v1/auth/me`（solo-qa 身份）、带 Key `GET /v1/models`（网关）、`agent -p --output-format json --model <cursor.model> "pong"` 期望 `result=="pong"`（Cursor，约 6–10 秒）。

**上传流程**

1. `GET /api/v1/submissions/form-schema` → `fingerprint`
2. `POST /api/v1/submissions/upload`（multipart `file`，`.jsonl`）→ `{name, path, size}`
3. `POST /api/v1/submissions`
   ```json
   { "data": { "question_type", "difficulty", "languages",
               "harness", "harness_version", "os_platform", "repro_level", "env_snapshot",
               "user_prompt", "session_id", "turn_id", "trace_file": [{"name","path","size"}],
               "score_delivery", "score_instruction", "score_planning", "score_reasoning", "score_execution",
               "desc_delivery", "desc_instruction", "desc_planning", "desc_reasoning", "desc_execution",
               "other_issues" },
     "schema_fingerprint": "<fingerprint>" }
   ```
   头：`Cookie: solo_qa_session=…; solo_qa_csrf=…`、`X-CSRF-Token: <csrf>`
4. 记录 `{id, status, round_no, message}`；`422` 按 `fields` 逐字段标红；`401/403` 提示身份失效跳设置页。

批量：勾选多题串行上传，失败不阻塞其余。

### 3.6 W6 · 容器生命周期

```
run -i (print) ──► exited ──► 轨迹落盘校验 ──► 导出 exports/ ──► 人工「完成」 ──► docker rm
                     │
                     └─► TIMEOUT / INTERRUPTED ──► 同样走人工「完成」销毁
```

销毁前提：`出题/轨迹/NN/` 有 `.jsonl` 且已复制到 `exports/`。启动时扫描 `solo-cli.task` 标签的残留容器并接管显示。

### 3.7 W7 · 界面

| 页面 | 内容 |
|---|---|
| 总览 | 槽位占用、题库剩余、今日完成/分析/上传、三项连通状态 |
| 题库 | 未领取题卡（题号、类型、难度、语言、正文摘要），「领取并启动」/「批量启动」 |
| 运行舱 | 每容器一张实时卡片：阶段、耗时、轮次、token、最近工具调用；点开为事件流时间线 |
| 题目详情 | 参数面板、prompt 原文、判定结论、需求覆盖表、五维评分与描述编辑器（含核验标记）、轨迹下载、上传结果、「完成并销毁」 |
| 设置 | §3.5 配置项，测试连接 |

视觉规范见 `docs/DesignSpec.md`。

### 3.8 任务状态机

```
AVAILABLE → CLAIMED → QUEUED → RUNNING → ┬─ FINISHED ─┐
                                          ├─ FAILED ───┼─► ANALYZING → REVIEWED → UPLOADED → DONE(销毁)
                                          ├─ TIMEOUT ──┤
                                          └─ INTERRUPTED┘
```

`REVIEWED` 要求五维齐全且核验无红项；`DONE` 由人工点「完成」触发容器销毁。

---

## 4. 技术栈

| 层 | 选型 |
|---|---|
| backend | Python 3.12 · FastAPI · SQLAlchemy(SQLite) · httpx · sse-starlette · docker CLI（子进程，便于 `-i` 注入 stdin）· Cursor CLI |
| frontend-console | Vue 3 · TypeScript · Vite · Tailwind CSS · Naive UI |
| 交付 | `docker compose up` → `http://localhost:8788`；backend 挂 `docker.sock` 与 `coder_root`；数据卷 `./data` |

---

## 5. 风险与验证项

| # | 风险 | 处理 |
|---|---|---|
| R1 | bind mount 下容器 `node`(uid 1000) 对宿主目录不可写 | **已关闭**：实测可写 |
| R2 | 镜像要求 `/workspace` 为空，与初始快照仓库冲突 | **已关闭**：`20260915-mount` 去掉该检查 |
| R3 | 分析描述被质检识别为 AI 生成 | 分析在宿主侧执行、不进轨迹；描述第一人称口语化 + 黑名单校验 + 人工审阅后上传 |
| R4 | 描述雷同触发 solo-qa 规则 B、与轨迹不符触发 V1 | 描述必须带证据步骤且通过交叉核验；模板要求引用具体文件/命令/报错 |
| R5 | 同题重跑产生第二份轨迹（规则 T4） | 门禁要求轨迹目录为空；重跑前归档 |
| R6 | Cookie 过期导致批量上传中途失败 | 上传前 `auth/me` 探活；失败项可重试 |
| R7 | Cursor CLI 模型列表获取 | **已关闭**：Key 已验证，`claude-opus-5-thinking-high` 调通；列表用 `--model __probe__` 报错解析 + 静态兜底（§3.4） |
| R9 | Docker Hub 令牌已过期，多架构正式镜像尚未推送 | 用户 `docker login` 后执行 `VERSION_TAG=20260915-mount BUILD_DIR="$PWD/build-20260915-mount-multiarch" bash claude-code-publish.sh adminfather`；本机开发不受影响 |
| R8 | 宿主 `workspace/01` 当前含 `node_modules`，HEAD 可能 ≠ 快照 | 门禁拦截并提示重置 |
