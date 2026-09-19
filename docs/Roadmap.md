# Roadmap · Solo CLI 控制台

> 依据 `docs/Requirements.md` v0.2。每个任务完成后勾选并记录验证方式。
> 阶段之间串行；阶段内任务可并行。所有阶段的最终验收口径：`docker compose up` 后 `http://localhost:8788` 可用。
> 2026-09-15 全部功能阶段（P0–P6）完成，验证记录见各条目。

## Phase 0 · 基建与设置（可启动、可配置、可测连）

- [x] P0-1 后端骨架：FastAPI 应用、SQLite 初始化、`/api/health`、结构化日志、启动时打印 `Startup Success` 与访问 URL — `docker compose logs backend` 可见
- [x] P0-2 前端骨架：Vite + Vue 3 + TS + Tailwind + Naive UI，暗色主题、侧边导航、五个路由 — `npm run build` 通过 vue-tsc
- [x] P0-3 `docker-compose.yml`：backend（挂 `docker.sock`、`coder_root`、`./data`）+ frontend-console（Nginx 反代 `/api`，SSE 不缓冲），healthcheck 依赖 — `docker compose up -d` 两容器 healthy，`:8788` 200
- [x] P0-4 设置模块：`SPECS` 配置项模型、Fernet 加密存储、掩码读取、`GET/PUT /api/settings`
- [x] P0-5 测试连接：solo-qa `auth/me`、网关 `/v1/models`、Cursor `pong`；模型下拉 `--model __probe__` 报错解析（容器内实测 `source=live`）+ 静态兜底；`.env` 种子导入
- [x] P0-6 后端镜像内安装 Cursor CLI 与 docker CLI — 容器内探测返回 `Docker 29.1.5 · 镜像就绪 CLI 2.1.197`、`claude-opus-5-thinking-high · pong`

## Phase 1 · 题库（W1）

- [x] P1-1 `prompt.md` 多题解析器：题块切分、键值行、正文提取 — `tests/test_prompt_bank.py`（多题 / 空 SessionID / 正文含「：」）
- [x] P1-2 `Task` 模型与增量导入（唯一键 `task_no + sha256(user_prompt)`），启动时自动导入 + 「重新扫描」按钮
- [x] P1-3 `GET /api/tasks`、`POST /api/tasks/{id}/claim`（含门禁）、`release`、`batch/claim`
- [x] P1-4 题库页：题卡、筛选、搜索、领取并启动、门禁弹窗（修复动作 / 强制启动）、批量启动

## Phase 2 · 运行舱（W2）

- [x] P2-1 启动前门禁：Key/镜像/容器名、git HEAD 校验、工作区干净（含忽略文件提醒）、黑名单扫描、轨迹目录为空；修复动作 `reset_snapshot`（二次确认）/ `archive_traces` / `remove_container`
- [x] P2-2 镜像探测：`claude --version` 缓存回填 `harness_version`（上传以实测为准），镜像 label `org.benzhi.claude.task-mode` 缺失时提醒
- [x] P2-3 runner：`docker run -i … print < prompt`，stdin 注入、stream-json 逐行采集、`RunEvent` 落库、退出码捕获 — 实测无效 Key 路径：15 条事件、`result.is_error` → `FAILED`
- [x] P2-4 scheduler：槽位、队列、超时 `docker stop`；重启接管残留容器（running → `docker wait`；exited → 直接判定）
- [x] P2-5 SSE `GET /api/events`、`GET /api/tasks/{id}/events`（回放 + 实时）；运行舱页（实时卡片 + 最近 3 条调用）与详情页事件流时间线（筛选 / 展开）
- [x] P2-6 实测 R1（bind mount 可写）与 R2（非空目录挂载）— 2026-09-15 通过，镜像 `20260915-mount`

## Phase 3 · 判定与回填（W3）

- [x] P3-1 三层判定：进程 / 协议 / 产物 → `FINISHED | FAILED | TIMEOUT | INTERRUPTED`，附备注（多份轨迹、无改动、session 不一致）
- [x] P3-2 轨迹解析：`sessionId`、首条非 sidechain `user.promptId`、步骤索引 `trace_index.json` — `tests/test_trace_and_verify.py`
- [x] P3-3 轨迹导出 `data/exports/NN/<sessionId>.jsonl` 与 `GET /api/tasks/{id}/trace` 下载
- [x] P3-4 回填 `prompt.md` 与 `出题/prompts/NN.md`（备份 + 仅改两行）— 单测断言仅 2 行变化；实测隔离副本回填成功
- [x] P3-5 详情页：判定三层卡片、回填面板（点击复制）、git diff 统计、模型最后一段话、Prompt 原文与元信息

## Phase 4 · Cursor CLI 五维分析（W4）

- [x] P4-1 分析沙箱：复制产物到 `出题/分析/NN/repo/`（每次重建）
- [x] P4-2 分析模板：rubric 锚点、写法约束（第一人称、禁词、禁 markdown/表情）、JSON 输出契约、需求覆盖表、实际验证命令
- [x] P4-3 analyzer：`agent -p --force --trust --model … --output-format json`，超时可配，输出 JSON 容错（前置说明 / 围栏 / 缺括号）— 真实调用 Opus 5 一次 203s 成功落库
- [x] P4-4 交叉核验：步骤存在 / 文件匹配 / 引文定位 / 分数-覆盖一致 / 描述雷同 / 去 AI 化黑名单 / 第一人称 — 真实输出核验 `pass`，证据命中 100%
- [x] P4-5 详情页五维编辑器：1–5 分段、等宽描述框、证据 chips（跳转轨迹步骤）、核验圆点、命中词高亮、核验条、保存并核验、重新分析

## Phase 5 · 上传（W5）

- [x] P5-1 uploader：`auth/me` → `form-schema` → `upload` → `submissions`，字段映射（五维分数/描述、`harness_version` 实测）
- [x] P5-2 错误回显：422 逐字段、401/403 身份提示、503 重试一次；未配置身份时明确报错（实测）
- [x] P5-3 单题上传（详情页，红项禁用）与运行舱批量上传，上传记录（步骤 / 响应 / submission_id）展示

## Phase 6 · 生命周期与交付（W6/W7）

- [x] P6-1 「完成并销毁」：轨迹导出校验 → `docker rm` → `DONE`；未上传需 `force` 二次确认；另提供「仅销毁容器」— 实测容器删除、状态 DONE
- [x] P6-2 总览页：六项指标、流水线阶段计数、环境/配置状态、残留容器、运行舱预览、最近活动
- [x] P6-3 UI 打磨：空态提示行、按钮 loading、错误 toast（含逐字段原因）、响应式网格（xl 三列 / md 两列 / 单列）
- [x] P6-4 `/deploy`：Dockerfile（静态 docker CLI + Cursor CLI）、healthcheck、启动日志 `Startup Success` + URL、README
- [ ] P6-5 `/report`：`docs/SelfTestReport.md`（待 `/report` 指令）

## Phase 7 · 迭代（用户反馈）

- [x] P7-1 主题由深色改为浅色（`tailwind.config.js` / `theme.ts` / `DesignSpec.md` 同步），颜色常量收敛到 `status.ts`
- [x] P7-2 整体字号上调一档（正文 14px，Tailwind 字阶重映射，Naive UI 同步）
- [x] P7-3 题目详情页补全：未运行的题显示提交参数 / prompt 全文 / 项目路径 / 时间线，左栏内联门禁检查与修复动作；tab 按状态动态；加返回按钮
- [x] P7-4 废弃功能：`DISCARDED` 状态 + `discard` / `restore` 接口，列表默认隐藏，题库「已废弃」标签页可恢复；容器随废弃销毁
- [x] P7-5 SQLite 最小迁移（`db._ensure_columns`），旧库自动补列，设置与题库数据无损
- [x] P7-6 交互冒烟脚本 `frontend-console/scripts/probe.mjs`（puppeteer-core 驱动 headless Chrome，10 项断言全绿）

## Phase 8 · 全自动流水线 · 质检 · 出题（用户反馈）

- [x] P8-1 数据模型扩展：`qc_status` / `qc_json` / `priority` / `origin` / `design_run_id` / `dedup_json` / `auto_stage` / `auto_error`，新增 `design_run` 表；旧库经 `_ensure_columns` 自动补列（实测 6 列）
- [x] P8-2 自动流水线 `services/pipeline.py`：运行结束自动「销毁容器 → 五维分析 → 质检」，三步各自可关；分析与质检共用信号量限流；没有轨迹时跳过分析并保留容器，告警逐条累加不覆盖
- [x] P8-3 队列管理：`priority` 出队排序、置顶/上移/下移/放回、暂停出队、在线调并发；队列管理台页面
- [x] P8-4 质检接入：`bridges/qa_qc.py` 挂进 `solo-qa-backend` 镜像跑完整质检链路（只读，不入库、不写飞书），13 项检查 + 模型描述判定实测 28s 返回；`harness_version` 改为以轨迹为准
- [x] P8-5 题目设计：`services/designer.py` 调 Cursor CLI 执行 solo-prompt SOP，后端镜像内置 `gh`，Token 写成 credential store；产出扫描 `出题/prompts` 增量导入
- [x] P8-6 设计产出自动查重：`bridges/qa_dedup.py` 跑规则 A + 规则 C（含批内互查），命中即废弃并记录原因，查重没跑成不放行
- [x] P8-7 前端：队列管理台、质检面板（结论/未通过项/全部检查项）、设计题目页（前置检查 + 设计记录 + 日志）、设置页开关型字段、总览与题卡展示质检与查重结论
- [x] P8-8 端到端验证：并发 1 下两题排队与自动补位、容器自动销毁、无轨迹跳过分析；UI 冒烟 23 项断言全绿

## Phase 9 · 详情页卡死与重启后遗症（用户反馈）

- [x] P9-1 事件洪水：Claude Code 每产生 1 个思考 token 就推一条 `system/thinking_tokens`，单题刷出 36896 条（占全库 99.7%，13.8MB），详情页一挂载就把回放全塞进渲染，浏览器直接无响应。改为不落库、按 2 秒节流推一条进度，前端当状态行显示；另加单题 8000 条落库上限兜住未知的高频事件。
- [x] P9-2 事件接口加尾部上限：SSE 默认回放最后 600 条并先发一条 `truncated` 告知总数，`events/list` 支持 `limit`；历史脏数据已清理（46843 → 204 条，库 16MB → 964KB）。
- [x] P9-3 结束状态判定抽成 `runner.decide_status`：后端重启后接管的容器读不到 stdout，`result` 恒为空，退出码 0 的题会被误判成 FAILED（实测题 06 跑了 63 分钟、60 次工具调用、改了 3 个文件仍标记失败）。现在退出码 0 且本轮有轨迹即算完成，并在 notes 说明轮次与用量为空；补 6 项单测覆盖各分支。
- [x] P9-4 启动自愈 `pipeline.resume_stale()`：分析与质检是进程内的活，后端一重启状态就永远卡在「分析中」。启动时复位中断状态并把没走完的题重新排进流水线。

## Phase 10 · 交付安全与可重跑（用户反馈）

- [x] P10-1 配置不再「莫名丢失」：查明 `secret.key` 与库都在挂载卷里、重建镜像不影响，丢的那次是界面掩码被当真值写回覆盖。掩码判断从前缀改为出现圆点即拒绝，写入与跳过都记审计日志（只记 key 不记值）。
- [x] P10-2 五维描述不再泄漏本机路径：产物副本与 `/workspace` 前缀剥成仓库内相对路径，其他绝对路径整条压掉（像文件留文件名，像目录换成一句话），描述、证据、需求覆盖、verification 四处全洗；核验对宿主路径报红、对 `/workspace` 报黄。
- [x] P10-3 五维描述不再自述核验环境：prompt 明令禁止写有没有装依赖、有没有 node_modules、跑不跑得起来、「产物副本」「我这边」，核验命中即红项。实测题 04 的两段描述被准确拦下。
- [x] P10-4 题库按具体状态分 8 个 tab（全部/待领取/已领取未跑/排队运行中/待评审/已评审/已上传完成/已废弃）。此前点过领取的题会从默认视图消失，看起来像丢了。
- [x] P10-5 「还原到做题前」：销毁容器、工作区 git clean 并回到快照 commit、轨迹归档、删除导出副本与分析产物、prompt.md 回填改回占位、清空运行分析评审质检记录与事件。实测题 02 还原后门禁 8 项全绿，可直接重跑。

## Phase 11 · 收尾流程事故（线上暴露）

- [x] P11-1 `finalize` 抛 `NameError: subtype`：P9-3 把状态判定抽成函数时删掉了局部变量，下面拼 verdict 的地方还在用。任何一次运行结束都会崩，题 03 跑满 4 小时 14 分后判定、轨迹导出、回填、事件全丢，只留下一个 INTERRUPTED。补 `tests/test_finalize.py` 真调一次收尾（正常结束 / 被杀无产出 / 重启接管三种），回退修复能复现 NameError。
- [x] P11-2 接管路径没有超时：`_wait_and_finalize` 只 `docker wait`，`run.timeout_minutes` 对它不生效，题 03 因此跑了 4 小时。改为按已运行时长算剩余额度，超时就 `docker stop` 并按 TIMEOUT 收尾。

## Phase 12 · 交付即提交 · 一项目一并发（用户反馈）

- [x] P12-1 上传 solo-qa 成功后提交工作区：`services/repo.py` 把改动 `git add -A` + commit 到这道题自己的分支（默认 `q` + 题号，模板可配），提交信息带 SessionID / TurnID / 初始快照；不 push。游离 HEAD 或落在别的分支时拒绝提交并说明原因，避免把这一轮写到别人头上。提交失败只记一笔，不会把已经成功的上传判成失败。
- [x] P12-2 一道题一个分支：领取时自动 `ensure_task_branch` 切到题目分支（工作区有改动时不动手，交给门禁报），门禁新增 `branch` 检查项与「切到题目分支」修复动作（本地没有就从 `origin` 建跟踪分支）。
- [x] P12-3 还原不再吞掉交付：`reset --hard` 前把 HEAD 记到 `refs/solo-backup/<分支>-<时间戳>`，还原后回到题目分支。实测题 05 提交→还原→从备份 ref 找回提交全链路通过。
- [x] P12-4 一个项目同时只跑一道题：`scheduler._pick` 出队时按 `repo_id` 过滤，同项目有 RUNNING 就跳过（强制启动也绕不过），`waiting_on_repo()` 把「等谁」暴露给队列页；门禁 `repo_busy` 阻断启动，但 claim 允许入队等待，自动补位照常。
- [x] P12-5 共用项目可见：`repo_id` 随任务下发，题库顶部汇总共用项目与题号，题卡与详情页点名同项目的题并高亮正在跑的那道，队列页写明「等 #05 跑完（同项目）」。

## Phase 13 · 描述读起来像机器写的（用户反馈）

- [x] P13-1 描述里不再出现步数：位置改用文件名、函数名、命令来指，prompt 明令禁止「第 38 步」「第 19、20 步」「步骤 12」，落库前用 `_strip_steps` 连着前面的「在/于」一起剥掉（覆盖顿号并列、「48 到 51」范围、「步骤 N 里」等写法，句子保持通顺），核验对残留报红兜底。
- [x] P13-2 第一句必须是现象不是总评：prompt 给出「我把需求逐条对了产物」「推进顺序我认可」「几个关键判断都做对了」「调用路径十分紧凑」四个反例和一个正例；核验拆出首句，套话且没点到文件/函数/命令的判红，点到了但夹评价词的给黄项，完全没锚点的给黄项。实测用户截图里的五段描述全部被准确拦下。

## Phase 14 · 详情页的「终端」不是终端（用户反馈）

- [x] P14-1 终端改成真终端：原来点开只是 `docker logs -f` 的只读回放，看得见模型往外写什么，却问不了它任何问题 —— 而「模型此刻把工作区改成了什么样」这件事，收尾前界面上根本不存在，只有进去 `git status` 亲眼看一遍才算数。新增 WebSocket `GET /api/tasks/{id}/container/exec`，后端开一个 pty 接 `docker exec -it`，前端换成 xterm.js；日志降为同一个抽屉里的第二个视图，默认进终端。实测：真 TTY（`/dev/pts/2`）、彩色提示符、行编辑、窗口改大小容器里跟着变、中文不被切碎，在跑着的题里直接看到 `M lib/root.js`、`?? lib/patch.js`。
- [x] P14-2 用完的 shell 要收掉：杀掉本机那个 `docker exec` 客户端进程，容器里的 shell 不会跟着死 —— 对 daemon 来说两者没有从属关系，客户端没了它照样在自己的 pts 上等输入。实测每开一次终端就在容器里留一个 bash，而终端里跑过的长命令会一直跑下去，那是一道正在评测的题。改为让 shell 先把 PID 写到 `/tmp`（工作区和轨迹是产物，一个字节都不能写），断开时照着发 SIGHUP，冲进程组发，把它起的子进程一起带走。实测开关抽屉、切换视图、换侧各条路径走下来，容器内 shell 数每次都回到 0，终端里 `sleep 987 &` 起的后台进程也一并消失。
- [x] P14-3 配套：nginx 同一个 `/api/` 要同时伺候 SSE 和 WebSocket，按 `map $http_upgrade` 分流（SSE 必须拿到 `Connection: ""`，ws 要 `upgrade`），实测三条 SSE 无回归；容器不在、已退出、side 非法一律先握手再发原因关连接 —— 在握手阶段拒绝的话浏览器只会给一个「连接失败」，人分不清是容器没了还是后端挂了；容器名一律由 `task_id + side` 推算，不接受调用方传，否则这个能执行任意命令的接口等于把宿主机上所有容器都开放了。

## Phase 15 · 题库收到远端，领取跨设备互斥（用户反馈）

- [x] P15-1 一个仓库同时当题库与查重池：`pool.Entry` 新增 `draft`（整份题面 Markdown）。此前池里只有 prompt 正文，够查重但不够领题 —— 仓库地址、初始快照、语言、Harness 版本、可复现等级全在题面的字段区里，缺了它另一台设备拿到的只是一段没有出处的文字。出题落地时顺带入池，并在仓库里写一份 `prompts/<设备>/NN.md` 供人直接阅读。
- [x] P15-2 领取归属记在远端：新增 `claims.jsonl`（append-only + `merge=union`），一次领取或释放一行。归属由 `owners()` 把全部动作按 `(时间, 设备, 动作)` 排序重放算出 —— 先 claim 的赢，release 只认本人发的。排序键不含行号，两台设备读同一份文件必然算出同一个归属，不需要中心仲裁。
- [x] P15-3 抢占三步走：`claim_remote` 先拉最新看有没有主，再写一行并推，**推完再拉一次重新核对**。第三步不能省：union 会把两台设备的 claim 都留下，谁赢由时间戳判而不是由谁先 push 判，少了它两边都会看到自己成功然后双双开工。推不上去就抹掉本地那行，这次领取整个不算数。
- [x] P15-4 领取发生在准备工作区之前：clone 两个分支要几十秒到几分钟，跑完才发现题没了等于白烧这段机器时间，磁盘上还留着一份没人要的工作区。被抢先时返回 `POST /api/tasks/{id}/claim` 409 + `code=POOL_TAKEN`，后端顺手按远端重投影本机题库，前端提示一句并立刻刷新列表；连不上远端另给 `POOL_UNREACHABLE`，不和「被人领走」混成一个提示。
- [x] P15-5 题库来源收敛到远端：新增 `services/pool_bank.py` 把池条目投影成本机待领取的题，`POST /api/tasks/sync` 与启动时各跑一次；池启用后不再重复导入本机 `drafts/`，两个来源并存会让同一道题多出一行没有远端归属、因而不受独占保护的副本。池没启用时一切照旧走本地题面文件。
- [x] P15-6 跨设备题号不撞车：别的设备的题一律加设备后缀（`01` → `01-mac-air`），题面里的题号与工作区路径同步改写。题号是工作区目录名和容器名的一部分，两台设备都从 01 开始编号，不区分就会让两道不同的题共用一个工作区，而界面上看不出任何异常；设备名先 slug 成 `[a-z0-9-]`，否则一个空格就让容器起不来，且要到出闸那一刻才报错。
- [x] P15-7 远端只管归属、本机只管进度：远端记「这道题归谁」，`CLAIMED → QUEUED → … → DONE` 全是本机口径。同步不碰已经动过手的题 —— 那时本机有工作区、有容器、有轨迹，删掉数据库里一行并不能把它们收回去。「放回」撤销远端登记，做完与废弃都不撤销。
- [x] P15-8 老条目自动补题面：题面全文是后加的字段，早于它入池的题在别的设备上领不了。每次同步检查一次，从本机 `drafts/NN.md` 读全文重写整行追加；`load()` 同 id 折叠改为「题面更全者优先」而不是「先出现者优先」，union 合并后的行序不保证，取先出现的会让补进去的题面在一部分设备上永远读不到。
- [x] P15-9 测试 39 项：仲裁（先到先得、行序无关、越权释放、重复行、坏行）、抢占（推完核对输给更早的 claim、推失败回滚、同设备重入、断网不盲领）、投影（被领走的不出现 / 中途被领走则撤下 / 已开工的不撤、同号不同题并存、题号与路径改写、缺题面不可领）、路由（被抢先时不 clone、顺带刷新题库、归属落库）。全量 469 项通过。
- [x] P15-10 出题规则同步回 skill：题库来源换到远端后，`~/.cursor/skills/solo-prompt` 里三处描述失效 —— Phase 6 还写着「solo-cli 从这两个位置导入题目」，Phase 3 的索引格式没有跨设备行（`07@air` / 归档列「（另一台设备）」），Phase 3.5 只数本机最大题号会和另一台设备撞车。一并改掉，并在 Phase 6 末尾补「推上远端题库」：直接敲 `/solo-prompt` 出的题落盘后要调一次幂等的 `POST /api/design/pool/bootstrap`，控制台不扫 `drafts/`，不推就等于这道题没出过。经控制台出题的批次由后端代劳，自检清单里标注免核。规则只有 skill 一份，实现改了不回写就是漂移，而漂移不报错。

### 修掉的真实缺陷

- 设置页「保存全部」会把界面掩码写回库里，密钥当场作废（容器报 `Header '14' has invalid value: 'Bearer ••••••••r0QA'`）。掩码比较改为前缀判断，前端不再提交掩码，启动时清理被污染的值并提示重填。
- 轨迹目录按题号复用，一次没产出轨迹的运行会捡起上一轮的 jsonl 当成自己的，把旧 SessionID 回填进 `prompt.md`。改为只认本轮开始之后写过的文件。
