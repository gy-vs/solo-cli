# Claude Code 使用说明（Mac）

镜像已发布到 Docker Hub，同时支持 Intel 和 Apple 芯片，Docker 会自动拉取匹配本机的版本。

## 当前发布版本：20260908

2026 年 9 月 8 日已重新上传并完成远端核验，`latest` 与 `20260908` 指向同一份新版多架构镜像。

| 项目 | 当前值 |
|---|---|
| 统一镜像 | `adminfather/benzhi-claude-code:latest` |
| 固定版本标签 | `adminfather/benzhi-claude-code:20260908` |
| 运行架构 | Intel `linux/amd64`、Apple Silicon `linux/arm64` |
| 网关地址 | `https://llm.jzxhnh.com` |
| 模型 | `auto_model/urm`，主模型、Opus、Sonnet、Haiku、子代理全部一致 |
| Claude Code CLI | `2.1.197`，两种架构均通过离线启动验证 |
| Key | 当前共享 Key 在运行时传入，不包含在镜像或本文中 |

新版已用当前共享 Key 对 `auto_model/urm` 发起一次最小对话测试，返回 HTTP 200 和有效消息响应。远端镜像索引摘要为：

```text
sha256:fd9b7e6fdd7fa609cb6c0d938f88979f126ad539b9fbff50f2dfb096c6e66b4a
```

拉取新版：

```bash
docker pull adminfather/benzhi-claude-code:latest
```

已有容器不会因为拉取镜像而自动升级，请先阅读下方「升级到 20260908：保留旧容器和轨迹」。本次发布操作没有迁移或删除使用者的现有容器。

## 日常命令

日常使用只有三条命令：

```bash
# 1. 启动容器（后台常驻，只需执行一次）
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code

# 2. 进入对话，末尾的 01 是题号，一题一个（每次使用都执行这条）
docker exec -it benzhi-claude-code cc 01

# 3. 把轨迹文件复制到桌面
docker cp benzhi-claude-code:/home/node/.claude/projects ~/Desktop/claude-轨迹-$(date +%m%d-%H%M)
```

**一题一个题号**：做第 2 题就写 `cc 02`，做第 3 题就写 `cc 03`。每个题号对应容器内一个独立的工作目录，各题的代码和对话轨迹互不干扰。

> 若需要把自己的代码放进容器给 Claude 改，命令见 [第 5 步](#把本地代码放进容器)，注意要连着后半段的 `chown` 一起执行，否则 Claude 只能读、不能改。

---

## 目录

1. [需要准备的东西](#一需要准备的东西)
2. [第 1 步：安装 Docker Desktop](#二第-1-步安装-docker-desktop)
3. [第 2 步：配置镜像加速器](#三第-2-步配置镜像加速器)
4. [第 3 步：启动容器](#四第-3-步启动容器)
5. [第 4 步：进入对话](#五第-4-步进入对话)
6. [第 5 步：与 Claude 对话](#六第-5-步与-claude-对话)
7. [第 6 步：取出轨迹文件](#七第-6-步取出轨迹文件)
8. [容器管理](#八容器管理)
9. [常见问题排查](#九常见问题排查)
10. [命令速查卡](#十命令速查卡)
11. [附录：管理员发布镜像的方法](#附录管理员发布镜像的方法)

---

## 一、需要准备的东西

只需要**一个 API Key**，形如 `sk-xxxxxxxxxxxxxxxx` 的一长串字符，由管理员单独发放。当前暂用管理员提供的共享 Key，仍在运行时传入，不写入镜像。

除 API Key 之外的全部配置（网关地址、模型名等）已固化在镜像内，无需设置。镜像也无需手动下载，首次启动时自动拉取。

> ⚠️ API Key 等同于密码。不要发到群里、不要提交到 Git、不要截图外传。

管理员本地的 `runtime.env` 保存当前共享 Key（文件权限为 600，已加入 Git 忽略规则）。可用 `docker run -d --name benzhi-claude-code --env-file ./runtime.env adminfather/benzhi-claude-code:20260908` 启动新版本；该文件不进入构建上下文，也不随镜像分发。已有同名容器时，先备份容器内的工作文件和轨迹，再单独安排迁移，不要直接删除容器。

### 升级到 20260908：保留旧容器和轨迹

`docker pull` 只更新本地镜像，`docker restart` 不会改变已有容器内的模型配置。升级需要创建新容器。下面的步骤保留旧容器，并迁移 `/workspace` 和 `/home/node/.claude`；如果还在其他目录保存了文件，也要另外备份。

先退出旧容器里的所有 Claude 对话。在项目目录下确认 `runtime.env` 已由管理员提供，再逐步执行；任一步报错都应停止，不要继续改名或迁移：

```bash
test -r ./runtime.env
docker pull adminfather/benzhi-claude-code:20260908
docker stop -t 30 benzhi-claude-code

BACKUP_DIR="$(mktemp -d "$HOME/Desktop/claude-backup-20260908.XXXXXX")"
docker cp benzhi-claude-code:/workspace "$BACKUP_DIR/workspace"
docker cp benzhi-claude-code:/home/node/.claude "$BACKUP_DIR/claude"

OLD_CONTAINER="benzhi-claude-code-before-20260908-$(date +%Y%m%d-%H%M%S)"
docker rename benzhi-claude-code "$OLD_CONTAINER"
docker run -d --name benzhi-claude-code \
  --env-file ./runtime.env adminfather/benzhi-claude-code:20260908

docker cp "$BACKUP_DIR/workspace/." benzhi-claude-code:/workspace
docker cp "$BACKUP_DIR/claude/." benzhi-claude-code:/home/node/.claude
docker exec -u root benzhi-claude-code \
  chown -R node:node /workspace /home/node/.claude
docker logs benzhi-claude-code
docker exec -it benzhi-claude-code cc 01 --continue
```

最后一条用于继续已有的第 1 题；首次做题时去掉 `--continue`。启动日志应显示模型 `auto_model/urm`。在确认新容器工作文件、轨迹和对话都正常前，不要删除旧容器或桌面备份。不要把 `runtime.env` 放入备份分享包。

### 重要：文件都在容器里

这套用法不挂载任何宿主目录，代码和对话记录**全部保存在容器内部**。

因此：

- 容器**不要删除**。删掉容器等于删掉里面的全部文件
- 提交轨迹前先用 `docker cp` 把文件复制出来（第 6 步）
- 停止容器（`docker stop`）不会丢数据，删除容器（`docker rm`）才会

### 关于芯片类型

本镜像为多架构镜像，Intel 和 Apple 芯片共用同一个地址，命令完全相同，无需自行判断芯片类型。

唯一需要区分芯片的地方是下一步下载 Docker Desktop 安装包。确认方式：点击屏幕左上角苹果图标 → 关于本机。

| 显示的字样 | 芯片类型 |
|---|---|
| 芯片：Apple M1 / M2 / M3 / M4（任意 M 开头） | **Apple 芯片** 🍎 |
| 处理器：Intel Core i5 / i7 / i9 等 | **Intel 芯片** 💻 |

---

## 二、第 1 步：安装 Docker Desktop

### 🍎 Apple 芯片（M1/M2/M3/M4）

1. 下载安装包：**https://desktop.docker.com/mac/main/arm64/Docker.dmg**
2. 双击 `Docker.dmg`
3. 在弹出的窗口中，把 Docker 图标拖到右侧的 Applications 文件夹
4. 打开「启动台」，点击 Docker 图标启动
5. 首次启动会提示安装 **Rosetta**，点「安装」（苹果官方兼容组件）
6. 弹出协议后勾选同意，点 Accept
7. 如提示输入 Mac 开机密码，输入即可

### 💻 Intel 芯片

1. 下载安装包：**https://desktop.docker.com/mac/main/amd64/Docker.dmg**
2. 双击 `Docker.dmg`
3. 在弹出的窗口中，把 Docker 图标拖到右侧的 Applications 文件夹
4. 打开「启动台」，点击 Docker 图标启动
5. 弹出协议后勾选同意，点 Accept
6. 如提示输入 Mac 开机密码，输入即可

> ⚠️ 最新版 Docker Desktop 要求 macOS 13 (Ventura) 或更高。
> macOS 11/12 请下载旧版本：**https://desktop.docker.com/mac/main/amd64/139021/Docker.dmg**（4.24.2 版，兼容 macOS 11+）

### 确认安装成功（两种芯片相同）

Docker 启动后，屏幕最上方菜单栏会出现鲸鱼图标 🐳。

等待 1~2 分钟，直到鲸鱼图标停止闪烁/抖动。点击该图标，显示 **Docker Desktop is running**（绿色）即为就绪。

然后打开终端执行：

```bash
docker --version
```

输出如下即成功（版本号无需一致）：

```
Docker version 29.1.5, build 0e6fee6
```

若提示 `command not found: docker`，说明 Docker 未安装成功或未启动，返回本步骤重做。

### 打开「终端」App 的方式

以下三种任选一种：

- 同时按 `Command` + `空格`，输入 `终端`，按回车
- 打开「启动台」，搜索 `终端`
- 打开「访达」→ 应用程序 → 实用工具 → 终端

后文所有命令均在终端窗口中粘贴执行。

> 💡 终端内粘贴使用 `Command` + `V`。粘贴后需按回车，命令才会执行。

### 调整内存分配

1. 点击菜单栏鲸鱼图标 → **Settings**（齿轮图标）
2. 左侧选择 **Resources**
3. 将 **Memory** 调至 **4 GB 以上**（Mac 内存为 16GB 时可调至 6~8GB）
4. 点击右下角 **Apply & restart**

---

## 三、第 2 步：配置镜像加速器

国内网络直连 Docker Hub 通常极慢或超时，需要先配置加速器，否则下一步拉取镜像会失败。

1. 点击菜单栏鲸鱼图标 → **Settings**
2. 左侧选择 **Docker Engine**
3. 在右侧 JSON 配置的最外层大括号内，增加 `registry-mirrors` 一项。修改后形如：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me",
    "https://hub.rat.dev"
  ]
}
```

> ⚠️ JSON 语法要求：各项之间用英文逗号分隔，最后一项后不能有逗号。语法错误时 Docker 会标红并拒绝保存。
> 只需新增 `registry-mirrors` 这一项，原有内容不要删改。

4. 点击右下角 **Apply & restart**，等待 Docker 重启完成

---

## 四、第 3 步：启动容器

把下面命令中的 `你的Key` 替换成管理员发给你的 API Key，然后整行粘贴执行：

```bash
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code
```

这条命令只需执行一次，容器会在后台常驻。

> ⚠️ 命令中各部分的顺序不能调整。`-d`、`--name`、`-e` 这些参数必须写在镜像名**前面**。
> 写成 `docker run adminfather/benzhi-claude-code -e apikey=xxx -d` 是错的，镜像名之后的内容会被当成要在容器里执行的命令。

### 首次启动

首次执行会自动下载镜像，约 700MB~1GB，视网速需要几分钟。终端会显示下载进度：

```
Unable to find image 'adminfather/benzhi-claude-code:latest' locally
latest: Pulling from adminfather/benzhi-claude-code
a1b2c3d4: Downloading [=========>       ]  120MB/350MB
```

下载完成后，终端会输出一串很长的容器 ID，例如：

```
7f3c1a22b4e4d51a0c82e5f7d9b1234aa9e137b0312aa8fd049667a9e137bbdf
```

**看到这串 ID 就说明启动成功了。** 镜像只下载一次，之后不再重复下载。

### 确认容器正在运行

```bash
docker ps
```

输出中应有 `benzhi-claude-code` 一行，`STATUS` 列显示 `Up`：

```
CONTAINER ID   IMAGE                              STATUS         NAMES
7f3c1a22b4e4   adminfather/benzhi-claude-code     Up 30 seconds  benzhi-claude-code
```

若这里没有输出，或没有 `benzhi-claude-code` 这一行，说明容器启动失败，见 [常见问题 Q5](#q5容器启动后立刻退出docker-ps-看不到)。

### 启动命令各部分说明

| 片段 | 作用 |
|---|---|
| `-d` | 后台运行，执行完命令立即回到终端 |
| `--name benzhi-claude-code` | 给容器起名，后续所有命令都用这个名字 |
| `-e apikey=你的Key` | 把 API Key 传入容器 |
| `adminfather/benzhi-claude-code` | 镜像地址，Docker 自动选择匹配本机芯片的版本 |

---

## 五、第 4 步：进入对话

**做每一道题时，用不同的题号执行这条命令。** 下面以第 1 题为例：

```bash
docker exec -it benzhi-claude-code cc 01
```

这是**每次使用都要执行**的命令。输出：

```
==================================================
  Claude Code
--------------------------------------------------
  运行架构 : x86_64
  网关地址 : https://llm.jzxhnh.com
  使用模型 : auto_model/urm
  Key 校验 : 已加载, 结尾 ...f456
  连通状态 : 网关可达, Key 已被接受
  当前题目 : 01
  工作目录 : /workspace/01
  轨迹目录 : /home/node/.claude/projects/-workspace-01/
==================================================
```

`运行架构` 一行显示 `x86_64`（Intel）或 `aarch64`（Apple 芯片），说明拉取到的是匹配本机的版本。

**`连通状态` 这一行务必看一眼**，它是进入对话前的体检结果：

| 显示内容 | 含义与处理 |
|---|---|
| `网关可达, Key 已被接受` | 正常，可以开始对话 |
| `网关拒绝该 Key (HTTP 401)` | Key 不对或已失效，联系管理员核对，此时对话会长时间无响应 |
| `无法连接网关` | 本机网络不通，若公司网络需要 VPN 请先连上，再重新进入 |

随后出现 Claude Code 界面，底部为输入框，可以开始对话。

> 命令末尾的 `cc` 是容器内置的启动入口，负责把 Key 转换成 Claude Code 需要的格式、准备题目目录并拉起程序。必须带上，不能省略。

### 一题一个 workspace

题号会决定这道题的工作目录和轨迹目录，两者一一对应：

| 命令 | 工作目录 | 轨迹目录 |
|---|---|---|
| `cc 01` | `/workspace/01` | `/home/node/.claude/projects/-workspace-01/` |
| `cc 02` | `/workspace/02` | `/home/node/.claude/projects/-workspace-02/` |
| `cc 03` | `/workspace/03` | `/home/node/.claude/projects/-workspace-03/` |

这样做的好处是各题的代码文件和对话轨迹天然隔离，提交时可以按题单独打包，不会混在一起。

关于题号的几点说明：

- 目录不存在时会自动创建，无需提前准备
- 题号可以是任意名字，例如 `01`、`5`、`task-3`、`q10`，但**不能包含斜杠和空格**
- 同一个题号重复使用会回到同一个目录，之前的文件都还在
- 不写题号（直接 `cc`）会在 `/workspace` 根目录下对话，多做几题就会混在一起，因此建议始终带题号

### 退出对话

在 Claude 界面输入 `/exit` 回车，退回终端。

**退出对话不会停止容器**，容器仍在后台运行。下次继续做同一道题，再执行一遍相同的命令即可，之前的文件都还在；换一道题就换一个题号。

### 查看已经做过哪些题

```bash
docker exec benzhi-claude-code ls -lh /workspace
```

输出即所有题号目录。

---

## 六、第 5 步：与 Claude 对话

### 基本用法

进入界面后直接用中文输入，按回车发送。例如：

```
你好，请介绍一下你自己
```

```
在当前目录写一个 Python 脚本 hello.py，功能是打印 1 到 100 的所有质数
```

```
读一下 hello.py，然后给它加上单元测试
```

Claude 会自行创建文件、执行命令并读取结果。生成的文件位于容器内的 `/workspace` 目录。

### 常用操作

| 操作 | 按键 / 命令 |
|---|---|
| 发送消息 | 输入后按 `回车` |
| 消息内换行（不发送） | `Option` + `回车` |
| 中断 Claude 当前执行 | `Esc` |
| 退出对话回到终端 | 输入 `/exit` 后回车，或连按两次 `Control` + `C` |
| 清空当前对话重新开始 | 输入 `/clear` |
| 恢复某题上一次的对话 | 退出后执行 `docker exec -it benzhi-claude-code cc 01 --continue` |
| 从某题的历史会话中选择恢复 | 退出后执行 `docker exec -it benzhi-claude-code cc 01 --resume` |
| 查看全部斜杠命令 | 输入 `/` 弹出列表 |

> 恢复对话时题号要写在 `--continue` 前面，题号决定去哪个题目目录里找历史记录。

### 把本地代码放进容器

用 `docker cp` 把 Mac 上的文件或文件夹复制进**对应题号的目录**。以第 1 题为例，**请连着后半段一起复制执行**：

```bash
docker cp ~/Desktop/我的项目 benzhi-claude-code:/workspace/01/ && docker exec -u root benzhi-claude-code chown -R node:node /workspace/01
```

复制完成后执行 `docker exec -it benzhi-claude-code cc 01` 进入对话，Claude 即可读取和修改这些文件。

> 后半段的 `chown` 不能省。`docker cp` 复制进容器的文件会保留 Mac 上的文件归属信息，容器内的 Claude 只能读、不能改，动手修改时会报 `Permission denied`。这条命令把文件归属改成容器内的用户，Claude 才能正常编辑。
>
> 万一忘了执行，也不用担心：进入对话时会看到「工作目录中存在当前用户无权修改的文件」的警告，按提示退出后补执行一次即可。

> 若目标题号目录尚未创建，先执行一次 `docker exec benzhi-claude-code mkdir -p /workspace/01`，或者先用 `cc 01` 进一次对话（目录会自动创建）再复制。

### 查看容器里有哪些文件

列出所有题号目录：

```bash
docker exec benzhi-claude-code ls -lh /workspace
```

列出某一题目录下的文件：

```bash
docker exec benzhi-claude-code ls -lh /workspace/01
```

> ⚠️ 容器内 Claude 以免确认模式运行（`--dangerously-skip-permissions`），会自行执行命令、修改和删除文件，不会逐步询问。
>
> 由于没有挂载任何宿主目录，它的影响范围完全限制在容器内部，碰不到 Mac 上的任何文件。
> 反过来说，容器内的文件也需要主动 `docker cp` 出来才能保存。

---

## 七、第 6 步：取出轨迹文件

### 7.1 轨迹文件的内容

轨迹文件（transcript）是一轮完整对话的原始记录，包含：

- 每一句用户输入
- 每一句 Claude 回复
- Claude 调用的工具（读文件、写文件、执行命令）
- 每个工具的返回结果
- 每一步的时间戳与 token 消耗

格式为 **JSONL**（每行一条独立 JSON 记录），一次会话对应一个 `.jsonl` 文件，文件名为会话 UUID。

因为一题一个工作目录，轨迹也按题分开存放。容器内的路径为：

```
/home/node/.claude/projects/-workspace-01/<会话UUID>.jsonl     ← 第 1 题
/home/node/.claude/projects/-workspace-02/<会话UUID>.jsonl     ← 第 2 题
```

> 💡 目录名的推导规则：Claude Code 把工作目录路径中的非字母数字字符全部替换为横线。工作目录 `/workspace/01` 因此对应 `-workspace-01`。

### 7.2 先确认对话已结束

在 Claude 界面输入 `/exit` 回车，退回终端。此步确保最后几条消息已写入磁盘。

### 7.3 查看有哪些题、各题有哪些轨迹

列出全部题目的轨迹目录：

```bash
docker exec benzhi-claude-code ls -lh /home/node/.claude/projects/
```

输出形如：

```
drwxr-xr-x 3 node node 4.0K Sep  7 18:12 -workspace-01
drwxr-xr-x 3 node node 4.0K Sep  7 19:05 -workspace-02
```

查看某一题的轨迹文件（按时间倒序，第一行为最近一次对话）：

```bash
docker exec benzhi-claude-code ls -lht /home/node/.claude/projects/-workspace-01/
```

```
total 248
-rw------- 1 node node 86K Sep  7 18:12 9f3c1a22-7b4e-4d51-a0c8-2e5f7d9b1234.jsonl
-rw------- 1 node node 12K Sep  7 17:45 3a8b2c11-5d6e-4f22-b1a9-8c4e6f2a7890.jsonl
```

### 7.4 导出单独一题的轨迹

以第 1 题为例，`-workspace-01` 换成对应题号即可：

```bash
docker cp benzhi-claude-code:/home/node/.claude/projects/-workspace-01 ~/Desktop/题01-轨迹 && open ~/Desktop
```

桌面会出现 `题01-轨迹` 文件夹，里面是该题的 `.jsonl` 文件。

### 7.5 一次导出全部题目的轨迹

```bash
docker cp benzhi-claude-code:/home/node/.claude/projects ~/Desktop/claude-轨迹-$(date +%m%d-%H%M) && open ~/Desktop
```

桌面会出现一个文件夹，名字形如 `claude-轨迹-0907-1815`，里面按题分成 `-workspace-01/`、`-workspace-02/` 等子目录。

> 文件夹名带时间戳，是为了避免与上一次导出的目录重名。`docker cp` 在目标路径已存在时行为会变化（会复制到该目录内部而不是覆盖），加时间戳可以规避这个问题。

### 7.6 打包成 zip 提交

```bash
cd ~/Desktop && zip -rq claude-轨迹-$(date +%m%d-%H%M).zip claude-轨迹-* && open ~/Desktop && echo "打包完成"
```

桌面会生成对应的 zip 文件，该文件即为需提交的产物。

### 7.7 连同其他记录一起导出

若需要完整的 Claude 目录（含提示词历史、文件备份快照等），复制整个 `.claude`：

```bash
docker cp benzhi-claude-code:/home/node/.claude ~/Desktop/claude-完整记录-$(date +%m%d-%H%M) && open ~/Desktop
```

导出内容说明：

| 名称 | 内容 |
|---|---|
| `projects/` | **轨迹文件本体**，即需提交的内容 |
| `history.jsonl` | 历史输入提示词的简要记录 |
| `file-history/` | Claude 修改文件前的备份快照 |
| `todos/` | Claude 维护的任务清单 |
| `settings.json` | 配置文件 |
| `statsig/`、`cache/` | 内部缓存 |

### 7.8 把 Claude 写的代码取出来

轨迹之外，Claude 生成的代码文件同样在容器内，需要单独复制。

导出某一题的代码：

```bash
docker cp benzhi-claude-code:/workspace/01 ~/Desktop/题01-代码 && open ~/Desktop
```

导出全部题目的代码：

```bash
docker cp benzhi-claude-code:/workspace ~/Desktop/claude-代码-$(date +%m%d-%H%M) && open ~/Desktop
```

> 若 Claude 在容器里执行过 `npm install`、`pip install` 之类的安装命令，题目目录下会多出体积很大的依赖目录（如 `node_modules`），导出会明显变慢。只需要源码时，可以先看一眼目录大小：
>
> ```bash
> docker exec benzhi-claude-code du -sh /workspace/*
> ```

---

## 八、容器管理

由于文件都存在容器内，以下命令需要分清哪些安全、哪些会丢数据。

### 查看状态

```bash
docker ps
```

只列出正在运行的容器。若 `benzhi-claude-code` 不在其中，用下面命令查看包括已停止的：

```bash
docker ps -a
```

`STATUS` 列的含义：

| STATUS 显示 | 含义 | 处理方式 |
|---|---|---|
| `Up X minutes` | 正在运行 | 可以直接 `docker exec` 进入 |
| `Exited (0) ...` | 已正常停止 | 执行 `docker start benzhi-claude-code` 重新启动 |
| `Exited (1) ...` | 启动失败 | 用 `docker logs` 查看原因，见 Q5 |
| `Exited (137) ...` | 被强制终止 | 多为直接退出 Docker Desktop 或强制关机所致。文件仍在，`docker start` 即可恢复 |

### 停止与重新启动（数据保留）

停止前建议先在 Claude 界面输入 `/exit` 退出对话，确保最后几条消息已写入轨迹文件。

```bash
# 停止容器，文件全部保留
docker stop benzhi-claude-code

# 重新启动，文件还在
docker start benzhi-claude-code
```

重启 Mac 或退出 Docker Desktop 后，容器会变为已停止状态，执行 `docker start benzhi-claude-code` 即可恢复，容器内文件不受影响。重启后 API Key 仍然有效，无需重新传入——它在容器创建时就已固定。

### 查看启动日志

```bash
docker logs benzhi-claude-code
```

用于排查容器启动失败的原因。

### 删除容器（会丢失全部文件）

```bash
docker rm -f benzhi-claude-code
```

> ⚠️ 该命令会**永久删除容器内的所有文件**，包括轨迹和 Claude 写的代码。
> 执行前务必先按第 6 步用 `docker cp` 导出需要保留的内容。

删除后重新执行第 3 步的启动命令即可得到一个全新的空容器。

### 更新到最新镜像

管理员发布新版镜像后：

```bash
# 1. 先导出要保留的文件
docker cp benzhi-claude-code:/home/node/.claude ~/Desktop/claude-备份-$(date +%m%d-%H%M)

# 2. 拉取新镜像
docker pull adminfather/benzhi-claude-code

# 3. 删除旧容器并用新镜像重建
docker rm -f benzhi-claude-code
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code
```

---

## 九、常见问题排查

### Q1：终端提示 `command not found: docker`

Docker Desktop 未启动或未安装成功。

1. 检查菜单栏是否有鲸鱼图标 🐳，没有则从「启动台」打开 Docker
2. 等待鲸鱼图标停止抖动，约 1 分钟
3. 关闭当前终端窗口，重新打开一个，再次尝试

### Q2：`Cannot connect to the Docker daemon`

Docker 引擎未运行。处理方式同 Q1：启动 Docker Desktop，等待状态变为绿色 running。

### Q3：拉取镜像卡住、超时或报网络错误

典型报错：`net/http: TLS handshake timeout`、`i/o timeout`、`connection reset by peer`、`error pulling image configuration`。

**处理方式一：确认已配置加速器**

回到 [第 2 步](#三第-2-步配置镜像加速器) 检查 `registry-mirrors` 是否已保存生效，并确认已点过 **Apply & restart**。

**处理方式二：改用加速器地址直接拉取**

在镜像名前加上加速器前缀，无需修改 Docker 设置：

```bash
docker pull docker.1ms.run/adminfather/benzhi-claude-code
```

拉取完成后重命名成标准名字，这样文档里的启动命令依然可用：

```bash
docker tag docker.1ms.run/adminfather/benzhi-claude-code adminfather/benzhi-claude-code
```

**处理方式三：关闭代理软件**

若本机运行 Clash、Surge 等代理软件，其对 Docker 流量的处理可能导致拉取中断（报错中出现 `198.18.x.x` 一类的地址即为此情况）。关闭代理后重试。

### Q4：`Conflict. The container name "/benzhi-claude-code" is already in use`

容器已经创建过了，不需要再次执行 `docker run`。

**如果只是想继续使用**，直接进入对话即可（`01` 换成你要做的题号）：

```bash
docker exec -it benzhi-claude-code cc 01
```

若提示容器未运行，先启动：

```bash
docker start benzhi-claude-code && docker exec -it benzhi-claude-code cc 01
```

**如果确实要重建容器**（例如之前 Key 填错了），先导出文件再删除重建：

```bash
docker cp benzhi-claude-code:/home/node/.claude ~/Desktop/claude-备份-$(date +%m%d-%H%M)
docker rm -f benzhi-claude-code
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code
```

### Q5：容器启动后立刻退出，`docker ps` 看不到

查看退出原因：

```bash
docker logs benzhi-claude-code
```

若输出 `启动失败：没有检测到 API Key`，说明启动命令里的 `你的Key` 没替换成实际的 Key，或参数顺序写错了（`-e` 必须在镜像名前面）。

删除失败的容器后重新启动：

```bash
docker rm -f benzhi-claude-code
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code
```

### Q6：`Error response from daemon: Container ... is not running`

容器处于已停止状态（重启 Mac 后常见）。启动它：

```bash
docker start benzhi-claude-code
```

然后再执行 `docker exec -it benzhi-claude-code cc 01`（题号换成你要做的那道题）。容器内文件不会因停止而丢失。

### Q7：报 401 / 认证失败，或发出消息后长时间无响应

两种表现的原因相同：Key 无效。

⚠️ Key 错误时 Claude Code 不会立即报错，而是在后台反复重试，界面表现为光标持续转动，可能持续一两分钟仍无任何提示。因此界面卡住时应首先排查 Key。

**最快的判断方式**：退出对话后重新执行 `docker exec -it benzhi-claude-code cc 01`，看信息面板里的 `连通状态` 一行。若显示「网关拒绝该 Key」，即为 Key 问题；若显示「无法连接网关」，则是网络问题。

若需要进一步确认，按下面的顺序排查。

**① 确认网关连通**（该命令不需要 Key）：

```bash
curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" --max-time 15 https://llm.jzxhnh.com/v1/models
```

- 输出 `HTTP状态码: 401`：网关正常，仅因未带 Key。问题在 Key 本身，继续看 ②
- 输出 `HTTP状态码: 000` 或命令卡住：网关无法连接。检查本地网络（是否需要连接公司 VPN），或联系管理员确认服务状态

**② 确认容器里的 Key 是否正确**：

```bash
docker exec benzhi-claude-code printenv apikey
```

把输出与管理员发放的 Key 逐字符核对。常见错误为复制时漏掉开头或结尾字符，或混入空格、引号。

Key 填错时无法直接修改，需要按 [Q4](#q4conflict-the-container-name-benzhi-claude-code-is-already-in-use) 的方式删除容器重建。

**③** 以上均正常仍失败时，联系管理员确认 Key 是否有效、过期或用量超额。

### Q8：报 `model not found` 或 `invalid model`

网关侧模型名称已变更，旧镜像内的默认模型可能失效。当前模型为 `auto_model/urm`，建议按前文「升级到 20260908」保留数据后迁移。

临时继续使用旧容器时，可以为本次对话同时覆盖主模型、三个默认模型和子代理模型，无需删除容器：

```bash
docker exec -it \
  -e ANTHROPIC_MODEL=auto_model/urm \
  -e ANTHROPIC_DEFAULT_OPUS_MODEL=auto_model/urm \
  -e ANTHROPIC_DEFAULT_SONNET_MODEL=auto_model/urm \
  -e ANTHROPIC_DEFAULT_HAIKU_MODEL=auto_model/urm \
  -e CLAUDE_CODE_SUBAGENT_MODEL=auto_model/urm \
  benzhi-claude-code cc 01
```

这些覆盖只对本次 `docker exec` 生效；下次仍需使用同一命令，或迁移到新版镜像。若 Key 也已更换，应按升级步骤用新的 `runtime.env` 创建容器。

### Q9（仅 Intel 芯片 💻）：Docker Desktop 无法安装或打开即闪退

1. 检查系统版本：苹果图标 → 关于本机
2. macOS 13 以下使用 [第 1 步](#-intel-芯片) 中提供的旧版本链接
3. 2015 年及更早的机型可能不支持虚拟化，需在「系统设置 → 隐私与安全性」中允许 Docker 的系统扩展加载

### Q10：`docker exec` 时提示 `executable file not found: cc`

镜像版本过旧，不含 `cc` 入口。请按前文「升级到 20260908」备份、保留旧容器并迁移到新版，不要直接执行 `docker rm -f` 删除工作文件和轨迹。

### Q11：轨迹目录为空，或 `docker cp` 提示路径不存在

典型报错：`Could not find the file /home/node/.claude/projects in container`。

排查顺序：

1. 确认已完整对话至少一轮（发送消息并收到回复）。启动容器后没有对话过是不会生成轨迹的
2. 确认题号对应的目录名写对了。`cc 01` 对应的轨迹目录是 `-workspace-01`，先列出实际存在的目录：
   ```bash
   docker exec benzhi-claude-code ls -lh /home/node/.claude/projects/
   ```
3. 直接列出全部轨迹文件的真实路径：
   ```bash
   docker exec benzhi-claude-code find /home/node/.claude -name "*.jsonl"
   ```

### Q12：中文显示为乱码或方块

镜像内已设置 `LANG=C.UTF-8` 和 `TERM=xterm-256color`，正常情况不会出现。若出现，检查终端设置：终端 → 设置 → 描述文件 → 高级 → 文本编码，选择 UTF-8。

### Q13：界面显示错乱、边框断裂

终端窗口太窄。把终端窗口拉大后，退出对话再重新 `docker exec` 进入即可。

### Q14：Claude 修改文件时报 `Permission denied`

出现在用 `docker cp` 把 Mac 上的代码复制进容器之后。原因是复制进去的文件保留了 Mac 上的文件归属信息，容器内的 Claude 只有读取权限。

先退出对话（`/exit`），然后在终端执行下面这条命令，把 `01` 换成实际题号：

```bash
docker exec -u root benzhi-claude-code chown -R node:node /workspace/01
```

重新执行 `docker exec -it benzhi-claude-code cc 01` 进入，即可正常修改。

> 进入对话时若看到「工作目录中存在当前用户无权修改的文件」的警告，也是同一个问题，处理方式相同。为避免这种情况，复制代码时建议直接用 [第 5 步](#把本地代码放进容器) 里那条带 `&& chown` 的完整命令。

### Q15：直接关了终端窗口，或用 Ctrl+C 中断了对话

请养成用 `/exit` 退出对话的习惯。直接关窗口或按 Ctrl+C 时，中断的只是 Mac 这一端的连接，容器里的 Claude 进程仍在后台运行，既占内存，也可能继续往轨迹文件里写内容。

下次 `docker exec` 进入不受影响。若想确认有没有残留进程：

```bash
docker exec benzhi-claude-code pgrep -a claude
```

有输出说明存在残留，清理掉即可：

```bash
docker exec benzhi-claude-code pkill -x claude
```

> 清理不会影响已经写入的轨迹文件。

---

## 十、命令速查卡

### 日常三条命令

```bash
# 启动容器（只需一次，之后容器一直在）
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code

# 进入对话，末尾是题号，做第几题就写几（每次使用）
docker exec -it benzhi-claude-code cc 01

# 导出全部轨迹到桌面
docker cp benzhi-claude-code:/home/node/.claude/projects ~/Desktop/claude-轨迹-$(date +%m%d-%H%M) && open ~/Desktop
```

### 按题操作（把 `01` 换成实际题号）

| 用途 | 命令 |
|---|---|
| 做第 1 题 | `docker exec -it benzhi-claude-code cc 01` |
| 做第 2 题 | `docker exec -it benzhi-claude-code cc 02` |
| 恢复某题上次的对话 | `docker exec -it benzhi-claude-code cc 01 --continue` |
| 查看已做过哪些题 | `docker exec benzhi-claude-code ls -lh /workspace` |
| 查看某题的文件 | `docker exec benzhi-claude-code ls -lh /workspace/01` |
| 把本地代码放进某题 | `docker cp ~/Desktop/我的项目 benzhi-claude-code:/workspace/01/ && docker exec -u root benzhi-claude-code chown -R node:node /workspace/01` |
| 导出某题的轨迹 | `docker cp benzhi-claude-code:/home/node/.claude/projects/-workspace-01 ~/Desktop/题01-轨迹` |
| 导出某题的代码 | `docker cp benzhi-claude-code:/workspace/01 ~/Desktop/题01-代码` |
| 修复某题的文件权限（报 `Permission denied` 时） | `docker exec -u root benzhi-claude-code chown -R node:node /workspace/01` |

### 容器管理

| 用途 | 命令 |
|---|---|
| 退出对话（容器继续运行） | 界面内输入 `/exit` |
| 查看容器是否在运行 | `docker ps` |
| 查看全部容器含已停止 | `docker ps -a` |
| 启动已停止的容器 | `docker start benzhi-claude-code` |
| 停止容器（数据保留） | `docker stop benzhi-claude-code` |
| 查看启动日志 | `docker logs benzhi-claude-code` |
| 查看全部轨迹目录 | `docker exec benzhi-claude-code ls -lh /home/node/.claude/projects/` |
| 更新镜像 | `docker pull adminfather/benzhi-claude-code` |
| **删除容器（丢失全部文件）** | `docker rm -f benzhi-claude-code` |

### Intel 与 Apple 芯片差异汇总

| 环节 | 🍎 Apple 芯片 | 💻 Intel 芯片 |
|---|---|---|
| Docker 安装包 | `.../mac/main/**arm64**/Docker.dmg` | `.../mac/main/**amd64**/Docker.dmg` |
| Rosetta | 首次启动提示时点「安装」 | 不涉及 |
| 系统版本要求 | macOS 13+ | macOS 13+，更低版本用 4.24.2 |
| 镜像地址 | 完全相同 | 完全相同 |
| 三条日常命令 | 完全相同 | 完全相同 |

除下载 Docker Desktop 安装包外，其余步骤两种芯片没有任何区别。

### 环境体检命令

排查无果时，执行以下命令并将完整输出提供给管理员。输出不包含 Key 内容，可安全分享：

```bash
echo "=== 芯片架构 ===" && uname -m && \
echo "=== macOS 版本 ===" && sw_vers -productVersion && \
echo "=== Docker 版本 ===" && (docker --version || echo "Docker 未安装/未启动") && \
echo "=== Docker 是否运行 ===" && (docker info > /dev/null 2>&1 && echo "运行中" || echo "未运行") && \
echo "=== 加速器配置 ===" && (docker info 2>/dev/null | grep -A3 "Registry Mirrors" || echo "未配置加速器") && \
echo "=== 容器状态 ===" && docker ps -a --filter name=benzhi-claude-code && \
echo "=== 容器日志末尾 ===" && (docker logs --tail 20 benzhi-claude-code 2>&1 || echo "容器不存在") && \
echo "=== Key 是否传入 ===" && (docker exec benzhi-claude-code sh -c 'if [ -n "$apikey" ]; then echo "已传入, 长度 ${#apikey}"; else echo "未传入"; fi' 2>/dev/null || echo "容器未运行") && \
echo "=== 网关连通性（本机，不带 Key）===" && curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" --max-time 15 https://llm.jzxhnh.com/v1/models && \
echo "=== 网关连通性（容器内，带 Key）===" && (docker exec benzhi-claude-code sh -c 'curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" --max-time 10 -H "Authorization: Bearer $apikey" https://llm.jzxhnh.com/v1/models' 2>/dev/null || echo "容器未运行") && \
echo "=== 轨迹文件数量 ===" && (docker exec benzhi-claude-code find /home/node/.claude -name "*.jsonl" 2>/dev/null | wc -l || echo "容器未运行")
```

最后两项的对照关系值得留意：本机那条不带 Key，返回 `401` 说明网关本身正常；容器内那条带了 Key，若同样返回 `401`，则问题出在 Key 上，返回 `200` 表示 Key 有效。若容器内返回 `000` 而本机正常，说明容器的网络出口有问题。

---

## 附录：管理员发布镜像的方法

使用者无需阅读本节。

### 正式发布：一个镜像地址兼容 Intel 和 Apple 芯片

正式镜像使用同一个地址 `adminfather/benzhi-claude-code:latest`。它是一个多架构镜像，内部包含 `linux/amd64` 和 `linux/arm64` 的平台内容，Docker 拉取时自动匹配芯片。使用者不需要选择两个不同的镜像或标签。

重新构建并发布正式镜像，不使用已有的 `claude-cli-local:test`：

```bash
docker login --username adminfather
bash claude-code-publish.sh adminfather
```

若需要先在本地完成打包、不上传：

```bash
bash claude-code-publish.sh --build-only adminfather
```

此命令使用同一个 Dockerfile 构建两个平台并导出为**一个 OCI 镜像包** `~/claude-docker-build/benzhi-claude-code-<版本>-multiarch.oci.tar`。两个平台均需通过构建时的 `claude --version` 检查，不读取或修改本地 test 镜像，也不会登录或上传。之后执行不带 `--build-only` 的正式发布命令，可复用此次构建缓存。

脚本只允许生成的 Dockerfile、entrypoint.sh、cc 和 .dockerignore 进入构建上下文，不会把目录中的其他文件或旧镜像包带入构建。API Key 仍只在运行容器时传入。

### 上传已打包的正式双架构镜像

本次镜像包位于项目的 `build-release/benzhi-claude-code-20260908-multiarch.oci.tar`。在启用 containerd 镜像存储的 Docker Desktop 中，可以直接导入并上传，无需重复构建，也不要使用只处理单架构的 `--push-local`：

```bash
docker login --username adminfather
docker load -i ./build-release/benzhi-claude-code-20260908-multiarch.oci.tar
docker image inspect adminfather/benzhi-claude-code:20260908 --format '{{.Id}}'
docker push adminfather/benzhi-claude-code:20260908
docker buildx imagetools inspect adminfather/benzhi-claude-code:20260908
```

本次导入的镜像 ID 与远端清单摘要都应为 `sha256:fd9b7e6fdd7fa609cb6c0d938f88979f126ad539b9fbff50f2dfb096c6e66b4a`，清单应包含 `linux/amd64` 和 `linux/arm64`。先检查日期标签成功，再把**同一摘要**发布为 `latest`：

```bash
docker tag sha256:fd9b7e6fdd7fa609cb6c0d938f88979f126ad539b9fbff50f2dfb096c6e66b4a adminfather/benzhi-claude-code:latest
docker push adminfather/benzhi-claude-code:latest
docker buildx imagetools inspect adminfather/benzhi-claude-code:latest
```

确认两个标签的摘要相同。清单中的 `unknown/unknown` 若标有 `attestation-manifest`，属于构建证明，不是额外的运行架构。旧版本 `20260907` 保留，不覆盖。

若提示 `personal access token is expired`，应在 Docker 账号设置中创建有效的 **Read & Write** 令牌，再运行 `docker login --username adminfather`，在密码提示处输入令牌。不需要 Delete 权限。Docker Hub 发布令牌与运行 Claude 的 API Key 是两种不同的凭据；二者都不要写进镜像、文档或构建参数。发布令牌不要使用 `--password 明文`，Claude 的 Key 优先使用权限为 600 的 `runtime.env` 传入。令牌过期后只需重新授权并重试 `docker push`，不需要重新打包。

### 可选：单架构测试镜像上传（不用于正式通用镜像）

下面的 `--local-push` 和 `--push-local` 只用于单架构调试分发。**要发布正文所用的通用镜像，请使用上一节的正式发布命令。**

首次发布前，在 Docker Hub 创建自己的仓库，并在本机终端登录：

```bash
docker login --username adminfather
```

将 `adminfather` 换成实际 Docker Hub 用户名（不是邮箱）；密码提示处输入具有仓库写权限的 Access Token。不要把 Token 或 Claude API Key 写进脚本、文档或构建参数。

**方式一：本地构建成功后自动上传**

```bash
bash claude-code-publish.sh --local-push adminfather
```

依次执行本机架构构建、加载为 `claude-cli-local:test`、离线运行 `claude --version` 验证、打标签、上传、检查远端 manifest。构建或 CLI 验证失败就终止，不会上传。验证不需要 API Key，不会调用网关；这只是 CLI 启动检查，不代替真实对话测试。

**方式二：直接上传已经打包好的本地镜像，不重新构建**

```bash
# 默认上传 claude-cli-local:test
bash claude-code-publish.sh --push-local adminfather

# 也可以指定仓库名和本地源镜像
bash claude-code-publish.sh --push-local adminfather benzhi-claude-code claude-cli-local:test
```

脚本从本地镜像读取架构，并固定镜像 ID 进行验证、打标签和上传，不会自动拉取缺失的源镜像。推送时复用本机 Docker 登录凭据。上传失败后镜像仍保留，按错误提示重试即可，不需要重新打包。

这两种方式上传的是**单架构镜像**，不会覆盖多架构的 `latest`。例如 2026 年 9 月 7 日上传 amd64 镜像会生成：

```text
adminfather/benzhi-claude-code:latest-amd64
adminfather/benzhi-claude-code:20260907-amd64
```

arm64 镜像对应 `latest-arm64` 和 `20260907-arm64`。默认同一天的架构版本标签会被再次发布覆盖；需要区分多次发布时可指定版本：

```bash
VERSION_TAG=20260907-v2 bash claude-code-publish.sh --push-local adminfather
```

启动单架构镜像时必须带标签，例如：

```bash
docker run -d --name benzhi-claude-code -e apikey=你的Key adminfather/benzhi-claude-code:latest-amd64
```

仅上传已有镜像不会修改其内部提示文字；旧镜像中的提示可能仍引用 `claude-cli-local:test`，分发时请使用脚本输出的 Docker Hub 地址。

### 多架构发布命令

需要让 Intel 和 Apple 芯片共用正文中的无标签镜像地址时，仍使用原来的多架构发布方式。在任意一台装有 Docker Desktop 的 Mac 上执行：

```bash
bash claude-code-publish.sh adminfather
```

脚本会依次完成：

1. 检查 Docker 服务，不在构建前试推 `permcheck` 镜像；发布前请自行完成 `docker login`
2. 生成 `Dockerfile`、`entrypoint.sh`、`cc` 和构建上下文白名单（位于 `~/claude-docker-build/`）
3. 复用或创建 `docker-container` 类型的 `ccpack` buildx builder，使用 Docker Desktop 自带的跨架构模拟支持
4. 一次构建 `linux/amd64` 和 `linux/arm64`，各自执行 CLI 启动检查，并发布为一个多架构镜像、同一个 tag
5. 执行 `docker buildx imagetools inspect` 检查 manifest 中包含两种架构

推送的标签有两个：`latest` 和当天日期（如 `20260907`），后者便于回滚。

### 发布前的本地验证

改动脚本后，建议先跑一次本地测试模式，确认镜像本身可用再推送：

```bash
bash claude-code-publish.sh --local-test
```

该模式只构建本机架构、加载为本地镜像 `claude-cli-local:test`，不登录、不推送，也跳过 QEMU 安装，命中缓存时通常半分钟内完成。随后即可验证：

```bash
docker run -d --name cc-test -e apikey=你的Key claude-cli-local:test
docker exec -it cc-test cc 01
docker rm -f cc-test && docker rmi claude-cli-local:test
```

### 容器的运行方式

`ENTRYPOINT` 只做 Key 校验、网关探活和信息打印，`CMD` 负责让容器常驻。因此 `docker run -d` 后容器空转，实际对话由 `docker exec` 拉起。

这样设计的原因是 Claude Code 是交互式 TUI 程序，若直接作为 PID 1 在 `-d` 模式下运行会因缺少终端输入而立即退出。

常驻用的 `CMD` 没有直接写 `sleep infinity`，而是写成：

```dockerfile
CMD ["bash", "-c", "trap 'pkill -TERM -x claude 2>/dev/null && sleep 3; exit 0' TERM INT; sleep infinity & wait"]
```

分两层原因。

第一层是退出码。`sleep` 不会为 `SIGTERM` 安装信号处理函数，而内核对 PID 1 会忽略这类没有处理函数的信号。若让 `sleep` 直接做 PID 1，`docker stop` 发出的 `SIGTERM` 无效，只能等 10 秒超时后靠 `SIGKILL` 收场，退出码 137。改用 `bash` 显式 `trap` 后 `docker stop` 立即返回、退出码为 0。

第二层是 `trap` 里为什么不只写 `exit 0`。Docker 只把 `SIGTERM` 发给 PID 1，而 `docker exec` 起的 `claude` 进程不在 PID 1 的进程树里（PPID 为 0）。PID 1 一退出容器立即终止，这些进程会被直接 `SIGKILL`，最后一段轨迹来不及落盘——实测在容器内起一个带 `trap` 的 exec 进程，`docker stop` 后它的处理函数根本不会被触发。所以 `trap` 里先把 `SIGTERM` 转发给 `claude`，留 3 秒写盘时间再退出。`pkill` 来自可选安装的 `procps`，缺失时 `&&` 短路跳过 `sleep`，退化为立即退出，不影响 `docker stop` 本身。

需要说明的是这只是尽力而为：使用者仍应先 `/exit` 退出对话再停容器，文档的容器管理一节已写明这一点。

### 关于启动时的网关探活

`entrypoint.sh` 和 `cc` 都会带 Key 对 `${ANTHROPIC_BASE_URL}/v1/models` 做一次 6 秒超时的 `curl`，把结论显示为「连通状态」一行。

加这一步是因为 Claude Code 在 Key 无效时不会报错，而是静默重试，界面表现为持续无响应且零输出，实测可超过 90 秒。使用者极易误判为镜像故障。探活把 401/403（Key 被拒）和连接失败（网络问题）在进入对话前就区分开。

判定上把 404 和 405 也视为「网关可达」，因为网关未必实现 `/v1/models` 端点，只有明确的 401/403 才判为 Key 问题。`curl` 由基础镜像保证存在，调用处仍做了 `command -v` 保护，缺失时只显示「未检测」而不影响启动。

### 为什么需要容器内的 `cc` 脚本

`docker exec` 不会经过 `ENTRYPOINT`，因此 entrypoint 中 `export` 的变量对 exec 进来的新进程不可见。

但 `docker run -e apikey=xxx` 传入的是**容器级环境变量**，`docker exec` 的新进程可以读到。所以 `/usr/local/bin/cc` 的职责是：读取 `apikey`，转换成 Claude Code 需要的 `ANTHROPIC_AUTH_TOKEN`，清除可能干扰鉴权的 `ANTHROPIC_API_KEY`，然后 `exec claude --dangerously-skip-permissions`。

`cc` 同时兼容 `apikey`、`APIKEY`、`ANTHROPIC_AUTH_TOKEN` 三种变量名，并会把额外参数透传给 `claude`，因此 `cc --continue` 这类用法可以直接工作。

### 题号与 workspace 的对应关系

`cc` 会把第一个不以 `-` 开头的参数当作题号，据此 `mkdir -p /workspace/<题号>` 并 `cd` 进去，然后才拉起 Claude Code。因此：

- `cc 01` 的工作目录是 `/workspace/01`，轨迹落在 `/home/node/.claude/projects/-workspace-01/`
- 不带题号时工作目录是 `/workspace`，轨迹落在 `-workspace/`

轨迹目录名由 Claude Code 自行推导：工作目录路径中的非字母数字字符全部替换为横线。这是各题轨迹能够自动分开的原因，无需额外配置。

题号中包含斜杠或空格时 `cc` 会直接报错退出，避免产生意外的嵌套目录。

另外，`/workspace/<题号>` 这类新建目录不在镜像预置的信任列表中，Claude Code 首次进入会弹出目录信任确认。`cc` 在 `cd` 之后会用 `node` 改写 `/home/node/.claude.json`，把当前目录标记为 `hasTrustDialogAccepted`，从而跳过该确认。这里用 `node` 而不是 `jq`，因为 `node` 由基础镜像保证存在，而 `jq` 属于容错安装的可选工具。

### 为什么 Dockerfile 里要显式声明 HOME

`docker exec` 不保证向新进程注入 `HOME` 环境变量，而 Claude Code 依赖 `HOME` 定位 `~/.claude` 目录。若 `HOME` 为空，轨迹会被写到意外位置，文档里所有 `docker cp` 的路径都会失效。

因此镜像的 `ENV` 段显式设置了 `HOME=/home/node`，同时 `cc` 中改写配置文件时使用绝对路径而非 `$HOME`，双重保证轨迹落在 `/home/node/.claude/projects/` 下。

### 关于 docker cp 的文件归属

方向不同，行为也不同，这是文档里唯一需要使用者多执行一条命令的地方。

**导出（容器 → Mac）没有问题**：Docker Desktop 会把文件归属映射为宿主机当前用户，导出的轨迹和代码直接可读。

**导入（Mac → 容器）会保留宿主机 uid**（macOS 上通常是 501），而容器内运行身份是 `node`（uid 1000）。结果是拷进去的文件对 Claude 只读，编辑时报 `Permission denied`。目录本身属于 `node`，所以新建文件正常，只有改动拷进来的文件会失败——这种「能读能建、不能改」的表现很容易误导排查方向。

这里没有在镜像内自动修复，因为 `cc` 以 `node` 身份运行，无权 `chown` 属于他人的文件。采取的方案是两层：文档把导入命令写成 `docker cp ... && docker exec -u root ... chown -R node:node ...` 的组合命令；同时 `cc` 在启动前用 `find ! -writable` 扫一遍工作目录，发现不可写文件就打印警告并给出修复命令，兜住使用者漏执行后半段的情况。

这段检测刻意不加 `-maxdepth`：拷单个文件到已存在的深层子目录时，父目录归属不变，限制深度会漏检。改为依靠 `-print -quit` 命中第一个即终止，因此即使工作目录里有 `node_modules` 这类大目录也不会退化成全量遍历。注意 `find ... | head -3` 达不到同样效果，`head` 退出前 `find` 已经走完了整棵树。

### 关于多架构镜像

推送结果是一个 **manifest list**：同一个镜像地址下挂着 amd64 和 arm64 两份镜像。使用者执行 `docker run` 时，Docker 根据本机架构自动选择，因此文档里的命令对所有人一致。

非本机架构那一份通过 QEMU 模拟构建，`npm install` 一步会明显变慢，整体耗时可能 15~30 分钟。这是单机构建多架构镜像的固有代价。

### 注意事项

仓库需在 Docker Hub 上设为 **Public**，否则使用者必须先 `docker login` 才能拉取。镜像内不含 API Key，仅含网关地址和模型名。

若本机运行代理软件，构建阶段拉取 Debian 源、npm 源，以及推送阶段上传镜像层都可能被打断（典型报错为 `502 Bad Gateway`，报错 IP 形如 `198.18.x.x`）。关闭代理后重跑即可，已上传的层会自动复用。

`Dockerfile` 中的可选工具层（`less`、`jq`、`ripgrep`）已设为容错，安装失败会跳过而不中断构建。`npm install -g @anthropic-ai/claude-code` 一步必须成功。

### 镜像内固化的配置

```
ANTHROPIC_BASE_URL=https://llm.jzxhnh.com
ANTHROPIC_MODEL=auto_model/urm
ANTHROPIC_DEFAULT_OPUS_MODEL=auto_model/urm
ANTHROPIC_DEFAULT_SONNET_MODEL=auto_model/urm
ANTHROPIC_DEFAULT_HAIKU_MODEL=auto_model/urm
CLAUDE_CODE_SUBAGENT_MODEL=auto_model/urm
CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000
CLAUDE_CODE_ATTRIBUTION_HEADER=0
CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1
LANG=C.UTF-8
TERM=xterm-256color
```

若网关地址或模型名变更，修改脚本中 Dockerfile 部分的 `ENV` 段后重新执行发布脚本，使用者拉取新镜像并重建容器即可。
