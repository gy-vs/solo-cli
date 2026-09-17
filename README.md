# Solo CLI · 指挥中心

把「设计题目 → 领题排队 → Docker 跑 Claude Code → 判定 → Cursor 五维分析 → solo-qa 质检 → 上传」串成一条可视化流水线，支持多题并发，一题一容器。

超出并发的题自动排队，前面一结束就补位；运行结束后自动销毁容器、自动分析、自动质检，不需要人工点确认。

## 一键启动

```bash
cp .env.example .env        # 至少确认 CODER_ROOT 指向宿主机上的 solo-coder 目录
docker compose up --build   # 首次约 3–5 分钟（拉取 docker CLI、安装 Cursor CLI、构建前端）
```

启动成功后后端日志会打印：

```
Startup Success
Console : http://localhost:8788
API     : http://localhost:8788/api/health
```

浏览器打开 <http://localhost:8788>。

## 首次配置（设置页）

| 分组 | 必填项 | 说明 |
|---|---|---|
| solo-qa 身份 | `solo_qa_session`、`solo_qa_csrf` | 从已登录浏览器的 Cookie 复制；「测试 solo-qa 身份」应显示登录用户 |
| Claude Code 容器 | 网关 Key | 注入容器的 `apikey`；镜像默认 `adminfather/benzhi-claude-code:20260915-mount`，需已 `docker pull` 到本机 |
| Cursor CLI 分析 | Cursor API Key、模型 | Key 在 cursor.com/dashboard/api 创建；「测试 Cursor」返回 `pong` 即可 |
| 调度 | 并发数、超时、暂停出队 | 默认 3 并发、单题 120 分钟 |
| 自动流水线 | 销毁 / 分析 / 质检三个开关 | 默认全开；分析与质检共用并发额度，默认 2 |
| solo-qa 质检 | 项目路径、镜像 | 复用 solo-qa 自己的后端镜像，只读挂载它的源码与 `.env`；「测试质检通道」会连一次远程库 |
| 题目设计 | GitHub Token | 出题要建仓库、推快照；本机执行 `gh auth token` 取值 |

所有值 Fernet 加密存于 `./data`，界面只回显密钥末 4 位。`.env` 中的 `CURSOR_API_KEY` 等仅作首次种子。

密钥在界面上显示为掩码（`••••••••` + 末 4 位），保存时不会回传，留空也不会清掉已存的值；要换值就直接覆盖输入。加密密钥 `secret.key` 和库一样在挂载的 `./data` 下，重建镜像、`docker compose down` 都不会丢配置。写入时只要值里出现掩码字符就一律拒绝，避免「保存全部」把掩码当真值覆盖掉密钥；每次写入与跳过都记在后端日志里（只记项目名不记值），配置真出问题时能追溯。启动时还会体检一次，发现库里存的是掩码就清空并在日志里点名。

## 目录约定（CODER_ROOT 下）

```
prompt.md            题库：多题，每题以「题号：NN」起头，正文位于「以下为发送给模型的 prompt 正文」之后
workspace/NN/        初始快照 git 仓库，挂为容器 /workspace（门禁要求 HEAD == 快照 SHA 且干净）
出题/轨迹/NN/         容器 ~/.claude/projects 挂载点，启动前必须为空，结束后含一份 <sessionId>.jsonl
出题/分析/NN/         产物副本 repo/、trace_index.json、analysis_prompt.md、agent 原始输出
出题/prompts/NN.md   可选归档，回填 SessionID / TurnID 时一并更新
```

## 单题流程

1. **题库** → 「领取并启动」：先把工作区切到这道题的分支（默认 `q` + 题号，设置里可改模板），再做门禁检查（Key、镜像、容器名、题目分支、HEAD、干净、黑名单泄漏扫描、轨迹目录空、同项目是否有题在跑）。阻断项可一键「切到题目分支」「重置到快照」「归档轨迹」「删除残留容器」。并发满了就进队列。
2. **运行舱**：`docker run -i … print < prompt`，只把 prompt 正文送进 stdin；stream-json 事件实时落库并通过 SSE 推到事件流。超时自动 `docker stop`。思考 token 那种一秒几百条的心跳不落库，只按 2 秒推一条进度；事件流默认回放最后 600 条，完整过程看轨迹 jsonl。
3. **判定**：进程层（退出码）/ 协议层（`result.subtype`）/ 产物层（轨迹、git 改动）→ `FINISHED | FAILED | TIMEOUT | INTERRUPTED`。后端重启后接管的容器读不到 stdout，拿不到 `result`，这时退出码 0 且本轮有轨迹就按正常结束算，轮次与用量留空并在判定备注里说明；导出轨迹到 `data/exports/NN/`，把 SessionID、TurnID/PromptID 写回 `prompt.md`（原文件另存 `.bak`，只改两行）。只认本轮开始之后写过的 jsonl，上一轮留在目录里的不会被当成这次的结果。
4. **自动流水线**：轨迹导出成功后销毁容器 → 跑五维分析 → 跑质检。没产出轨迹时保留容器并跳过分析，原因写在题目卡上。
5. **五维评审**：在产物副本上运行 `agent -p --model claude-opus-5-thinking-high`，产出分数、第一人称口语描述、证据（步骤号/文件/引文）、需求覆盖表。后端交叉核验：证据能否在轨迹中定位、分数与覆盖是否自洽、描述是否含表情/markdown/结构词。红项禁止上传，黄项人工确认；描述可直接编辑后「保存评审并核验」。

   描述只写现象，位置一律用文件名、函数名、命令来指。**不许用「第 38 步」「第 19、20 步」这类步数说法**（步号只填进 evidence，正文里的残留会在落库前自动剥掉，核验再报红兜底），**第一句必须落在具体东西上**，「我把需求逐条对了产物」「推进顺序我认可」「几个关键判断都做对了」这种总评开头一律红项；第一句夹了评价用词但点到了文件或命令的，只给黄项提醒。

   描述会原样交付给评审方，所以另有两类内容被卡死：**本机路径**（产物副本与 `/workspace` 前缀落库前就剥成仓库内相对路径，其他绝对路径整条压掉，核验再对宿主路径报红兜底）和**对核验环境的自述**（有没有装依赖、有没有 node_modules、跑不跑得起来、「产物副本」「我这边」一律红项）。命令跑不了就只依据代码与轨迹下结论，不写为什么没跑。
6. **质检**：调 solo-qa 的质检链路跑硬校验、查重、模型描述判定，只取结论，不写它的库、不碰飞书。未通过的项会指出缺什么、原文哪句有问题、该怎么改。
7. **上传**：`form-schema → /submissions/upload → /submissions` 两步上传；422 逐字段回显，401 提示更新 Cookie。`harness_version` 以轨迹里的版本为准（和镜像实测值不一致时以轨迹为准，否则质检直接打回）。上传成功后把工作区改动提交到这道题的分支（`git add -A` + commit，带 SessionID / TurnID / 初始快照，不 push），提交信息回显在上传页；工作区处于游离 HEAD 或落在别的分支时不提交，直接把原因报出来。不想自动提交就关掉设置里的「上传后提交工作区代码」。
8. **完成并销毁**：容器通常已被流水线销毁；手动点击可再次确认并标记 `DONE`。

## 队列

「队列」页看排队与在跑的题，可以置顶 / 上移 / 下移 / 放回题库，也能在线改并发上限、暂停出队（暂停只影响新题出队，已在跑的不受影响）。下半部分是自动流水线的实时进度，卡在哪一步、什么原因一目了然。

## 一个项目同时只跑一道题

几道题可能用同一个 GitHub 仓库（比如 04 和 05 都是 markdown-engine），各自有自己的分支。题库顶部会列出这类项目和对应题号，题卡与详情页也会点名「与 #05 共用项目」，正在跑的用橙色标出来。

这条规则由调度器硬保证：出队时按仓库过滤，同一个项目里已经有题在 RUNNING 就跳过，留在队列里等前一道结束自动补位（强制启动也绕不过）。所以同项目的题照常领取、照常排队，只是不会同时跑；队列页会写明「等 #05 跑完（同项目）」。

## 设计题目

「设计题目」页输入数量后，Cursor CLI 按 solo-prompt 的 SOP 出题，产出写进 `出题/prompts/NN.md` 并自动导入题库。随后对新题跑 solo-qa 的查重规则 A（字面/近字面）与规则 C（同仓库语义雷同，含同批互查），命中的直接废弃并记下原因，通过的留在题库等领取。查重本身没跑成时不会放行，题会留在库里并标注，人工决定。

出题需要后端容器里的 `gh` 与 GitHub Token，还需要工作区根目录有需求文档；页面顶部的前置检查会逐项标出缺什么。

后端重启不会打断容器里正在跑的题：启动时按容器实际状态重新接管，结束后照常收尾。分析与质检是后端进程内的活，重启会中断，启动时会把卡在「分析中/质检中」的题复位并自动重新排进流水线。

题库按状态分了八个标签页（全部 / 待领取 / 已领取未跑 / 排队运行中 / 待评审 / 已评审 / 已上传完成 / 已废弃），点过领取但还没跑的题在「已领取未跑」里。

想重跑一道题就点题卡上的「还原」（详情页是「还原到做题前」）：销毁残留容器 → 工作区回到题目分支并 `reset --hard` 回初始快照 commit、`git clean -fdx` → 轨迹目录带时间戳归档 → 删掉导出的轨迹副本与分析中间产物 → `prompt.md` 里回填过的 SessionID 与 TurnID 改回占位 → 清空运行、分析、评审、质检记录与事件。做完这道题回到「待领取」，门禁能直接过。工作区里未提交的改动会被清掉，轨迹是归档不是删除；分支上已有的交付提交在 reset 前会记到 `refs/solo-backup/<分支>-<时间戳>`，用 `git log refs/solo-backup/...` 能找回来。

不想做的题点「废弃」：从题库与运行舱列表中隐藏，残留容器一并销毁，轨迹和工作目录仍留在磁盘上；需要时在题库「已废弃」标签页恢复到废弃前的状态。运行中或排队中的题需先停止或放回才能废弃。

每道题的详情页（题卡「详情」按钮）分两种形态：还没跑的题显示提交参数、prompt 全文、项目路径、时间线，左侧可直接执行门禁检查并修复；跑过的题显示事件流、三层判定、五维评审、上传字段与轨迹步骤索引。

## 开发

```bash
# 后端
cd backend && uv venv --python 3.12 .venv && source .venv/bin/activate && uv pip install -r requirements.txt pytest
DATA_DIR=/tmp/solo-data CODER_ROOT_HOST=/path/to/solo-coder uvicorn app.main:app --port 8001 --reload
python -m pytest tests

# 前端（vite 代理 /api → :8001）
cd frontend-console && npm install && npm run dev
```

## 与 solo-qa 的对接方式

查重和质检都复用 `solo-qa-0908` 自己的后端镜像执行：把 `backend/bridges/*.py` 挂进去，stdin/stdout 传 JSON。这样既拿到它最新的规则实现，又不用把它 pin 死的依赖装进本项目。

桥接只调只读函数（`run_dedup`、`semantic.review`、`qc.runner.evaluate_one`），不写结论、不入查重池、不同步飞书，模型缓存也关掉；待查题目用 `MAX(id)` 之上的虚拟 id，只存在于内存。需要 solo-qa 的 `.env` 能连上它的远程库与模型网关。

## 文档

- `docs/Requirements.md` 需求与设计（SSOT）
- `docs/Roadmap.md` 阶段与验收
- `docs/DesignSpec.md` 视觉规范
