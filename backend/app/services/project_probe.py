"""这一侧的工作目录是个什么项目，录屏该怎么录。

录屏卡人的从来不是工具，是「这玩意儿到底该录什么」：库项目没有界面，对着终端跑测试
就行；带 dev server 的得开浏览器走一遍交互；纯后端要把接口打出来看响应。所以先认出
项目形态，再按形态给一份照着做就能录完的步骤。

判定只看依赖清单和目录结构这些确定性证据，认不出来就老实说认不出来（UNKNOWN），
由人按 GSB 的启动说明自己拿主意 —— 猜错形态比不猜更耽误事。
"""

from __future__ import annotations

import json
import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from app import config

log = logging.getLogger("probe")

FULLSTACK = "fullstack"
FRONTEND = "frontend"
BACKEND = "backend"
HEADLESS = "headless"
UNKNOWN = "unknown"

KIND_LABEL = {
    FULLSTACK: "全栈",
    FRONTEND: "纯前端",
    BACKEND: "纯后端",
    HEADLESS: "无界面（库 / CLI）",
    UNKNOWN: "认不出形态",
}

# 命中即算前端：这些包只有要渲染界面才会装
FRONTEND_PKGS = {
    "react", "react-dom", "vue", "svelte", "preact", "solid-js", "@angular/core",
    "next", "nuxt", "gatsby", "@remix-run/react", "astro", "@sveltejs/kit",
    "vite", "@vitejs/plugin-vue", "@vitejs/plugin-react", "react-scripts",
    "element-plus", "antd", "naive-ui", "@mui/material", "vuetify",
}
# 命中即算后端：都是要监听端口对外提供服务的
BACKEND_PKGS = {
    "express", "koa", "fastify", "@nestjs/core", "@hapi/hapi", "restify",
    "apollo-server", "@apollo/server", "socket.io", "sequelize", "typeorm",
    "prisma", "@prisma/client", "mongoose", "egg", "midway",
}
PY_FRONTEND = {"streamlit", "gradio", "dash", "nicegui", "panel", "reflex"}
PY_BACKEND = {"django", "flask", "fastapi", "starlette", "tornado", "aiohttp", "sanic",
              "bottle", "pyramid", "uvicorn", "gunicorn", "quart", "falcon"}
GO_BACKEND = ("gin-gonic/gin", "labstack/echo", "gofiber/fiber", "gorilla/mux",
              "go-chi/chi", "beego/beego")
JAVA_BACKEND = ("spring-boot", "spring-webmvc", "javax.servlet", "jakarta.servlet")

# monorepo 里的子项目目录。前端一律 frontend-<角色>（frontend-admin、frontend-console…），
# 所以按前缀认而不是穷举，否则新起一个角色名就漏判
FRONTEND_DIR_PREFIX = ("frontend", "client", "web-", "webapp", "miniprogram")
FRONTEND_DIR_EXACT = ("web", "ui", "h5")
BACKEND_DIR_PREFIX = ("backend", "server", "service")
BACKEND_DIR_EXACT = ("api", "srv")
# 子目录得真的像个能单独跑的项目才算数。只按名字认的话，Python 项目里的 app/ 包
# 会被当成前端子项目，一个纯后端仓库就判成全栈了。
PROJECT_MARKERS = ("package.json", "requirements.txt", "pyproject.toml", "go.mod",
                   "pom.xml", "build.gradle", "Dockerfile", "index.html", "Cargo.toml")

# 起服务的 npm script，按优先级找
DEV_SCRIPTS = ("dev", "start", "serve", "start:dev", "dev:server")
TEST_SCRIPTS = ("test", "test:unit", "jest", "mocha")


@dataclass
class Probe:
    kind: str = UNKNOWN
    stack: list[str] = field(default_factory=list)
    """判成这个形态的依据。人要能复核，不能只给个结论"""
    evidence: list[str] = field(default_factory=list)
    """起服务的命令。无界面项目为空"""
    serve: str = ""
    test: str = ""
    install: str = ""
    """探到的端口。没探到就留空，别瞎猜一个让人白等"""
    port: int | None = None
    root: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind, "kind_label": KIND_LABEL[self.kind],
            "stack": self.stack, "evidence": self.evidence,
            "serve": self.serve, "test": self.test, "install": self.install,
            "port": self.port, "root": self.root,
        }


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text("utf-8", "replace"))
    except (OSError, ValueError):
        return {}


def _text(p: Path) -> str:
    try:
        return p.read_text("utf-8", "replace")
    except OSError:
        return ""


def _pkg_deps(pkg: dict) -> set[str]:
    deps = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps |= set(pkg.get(key) or {})
    return deps


def _dep_name(raw: str) -> str:
    """从 `flask>=2.0; python_version<"3.9"` 这种声明里抠出 flask。"""
    for sep in ("[", "=", ">", "<", "!", "~", ";", " "):
        raw = raw.split(sep)[0]
    return raw.strip().lower()


def _py_deps(root: Path) -> set[str]:
    """Python 依赖名。

    只认真正的依赖声明，不在 setup.py 里做关键词扫描 —— jinja2 的 setup.py 描述里
    有一句「Django inspired syntax」，扫文本会把一个模板库判成 Django 服务端项目。
    """
    names: set[str] = set()
    for rel in ("requirements.txt", "requirements/base.txt", "requirements/dev.txt"):
        for line in _text(root / rel).splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "-")):
                names.add(_dep_name(line))
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(_text(pyproject))
        except (tomllib.TOMLDecodeError, ValueError):
            data = {}
        project = data.get("project") or {}
        names |= {_dep_name(str(d)) for d in (project.get("dependencies") or [])}
        poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        names |= {str(k).lower() for k in poetry}
    # setup.cfg 的 install_requires 是结构化的，可以放心读
    cfg = _text(root / "setup.cfg")
    if "install_requires" in cfg:
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(cfg)
            names |= {_dep_name(d) for d in parser.get("options", "install_requires", fallback="").splitlines() if d.strip()}
        except configparser.Error:
            pass
    names.discard("")
    return names


def _port_from_config(root: Path) -> int | None:
    """从常见配置里找端口。找不到就返回 None —— 让界面去探真实监听的端口，比猜准。"""
    import re
    for rel in ("vite.config.ts", "vite.config.js", "vue.config.js", "next.config.js",
                ".env", ".env.development", "docker-compose.yml"):
        m = re.search(r"(?:port|PORT)\s*[:=]\s*[\"']?(\d{2,5})", _text(root / rel))
        if m:
            return int(m.group(1))
    return None


def _npm_cmd(root: Path, pkg: dict, names: tuple[str, ...]) -> str:
    scripts = pkg.get("scripts") or {}
    runner = "pnpm" if (root / "pnpm-lock.yaml").exists() else \
             "yarn" if (root / "yarn.lock").exists() else "npm"
    for n in names:
        if n in scripts:
            return f"{runner} run {n}" if runner != "npm" else f"npm run {n}"
    return ""


def probe(task_no: str, side: str) -> dict:
    """看一眼这一侧的工作目录，判个形态出来。"""
    root = config.TaskPaths(task_no, side).workspace
    p = Probe(root=str(root))
    if not root.is_dir():
        p.evidence.append(f"工作目录不存在：{root}")
        return p.as_dict()

    fe, be = False, False
    pkg = _read_json(root / "package.json")

    if pkg:
        deps = _pkg_deps(pkg)
        hit_fe = sorted(deps & FRONTEND_PKGS)
        hit_be = sorted(deps & BACKEND_PKGS)
        p.stack.append("Node.js")
        if hit_fe:
            fe = True
            p.evidence.append(f"package.json 里有前端框架：{'、'.join(hit_fe[:4])}")
        if hit_be:
            be = True
            p.evidence.append(f"package.json 里有服务端框架：{'、'.join(hit_be[:4])}")
        if not hit_fe and not hit_be:
            p.evidence.append("package.json 里既没有前端框架也没有服务端框架，是个库或工具")
        p.install = "pnpm install" if (root / "pnpm-lock.yaml").exists() else \
                    "yarn install" if (root / "yarn.lock").exists() else \
                    "npm ci" if (root / "package-lock.json").exists() else "npm install"
        p.serve = _npm_cmd(root, pkg, DEV_SCRIPTS) if (fe or be) else ""
        p.test = _npm_cmd(root, pkg, TEST_SCRIPTS)

    py = _py_deps(root)
    if py or (root / "setup.py").exists() or (root / "pyproject.toml").exists():
        p.stack.append("Python")
        hit_fe = sorted(py & PY_FRONTEND)
        hit_be = sorted(py & PY_BACKEND)
        if hit_fe:
            fe = True
            p.evidence.append(f"Python 依赖里有界面框架：{'、'.join(hit_fe[:3])}")
        if hit_be:
            be = True
            p.evidence.append(f"Python 依赖里有服务端框架：{'、'.join(hit_be[:3])}")
        if not hit_fe and not hit_be:
            p.evidence.append("Python 依赖里没有任何 Web 或界面框架，是个库或命令行工具")
        if not p.install:
            p.install = "python3 -m venv .venv && . .venv/bin/activate && pip install -e ."
        if not p.test and (root / "tests").is_dir() or (root / "test").is_dir():
            p.test = p.test or "python -m pytest -q"
        if hit_be and not p.serve:
            if "django" in py:
                p.serve = "python manage.py runserver"
            elif {"fastapi", "uvicorn"} & py:
                p.serve = "uvicorn main:app --reload"
            elif "flask" in py:
                p.serve = "flask run"

    go_mod = _text(root / "go.mod")
    if go_mod:
        p.stack.append("Go")
        hit = [f for f in GO_BACKEND if f in go_mod]
        if hit:
            be = True
            p.evidence.append(f"go.mod 里有 Web 框架：{'、'.join(hit[:3])}")
        p.install = p.install or "go mod download"
        p.test = p.test or "go test ./..."

    pom = _text(root / "pom.xml") + _text(root / "build.gradle")
    if pom:
        p.stack.append("Java")
        if any(f in pom for f in JAVA_BACKEND):
            be = True
            p.evidence.append("构建文件里有 Spring / Servlet，是个服务端项目")
        p.test = p.test or "mvn test"

    # 纯静态页面：没有任何框架，但根上就摆着 index.html
    if not fe and (root / "index.html").exists():
        fe = True
        p.evidence.append("根目录有 index.html，是可以直接开浏览器看的页面")
        p.serve = p.serve or "python3 -m http.server 8080"

    # monorepo：前后端各自在子目录里
    subdirs = sorted(d.name for d in root.iterdir()
                     if d.is_dir() and not d.name.startswith(".")
                     and any((d / m).exists() for m in PROJECT_MARKERS))
    subs_fe = [d for d in subdirs if d.startswith(FRONTEND_DIR_PREFIX) or d in FRONTEND_DIR_EXACT]
    subs_be = [d for d in subdirs if d.startswith(BACKEND_DIR_PREFIX) or d in BACKEND_DIR_EXACT]
    if subs_fe:
        fe = True
        p.evidence.append(f"有前端子项目目录：{'、'.join(subs_fe)}")
    if subs_be:
        be = True
        p.evidence.append(f"有服务端子项目目录：{'、'.join(subs_be)}")
    if (root / "docker-compose.yml").exists():
        p.evidence.append("有 docker-compose.yml，可以用 docker compose up 一把起")
        p.serve = p.serve or "docker compose up"

    # 认出了技术栈但没有任何界面或服务信号，那就是库 / CLI；连栈都认不出才叫 unknown
    p.kind = FULLSTACK if (fe and be) else FRONTEND if fe else BACKEND if be else \
        HEADLESS if p.stack else UNKNOWN
    if p.kind == HEADLESS:
        p.serve = ""
        p.port = None
        p.evidence.append("没有可访问的地址，录屏只能靠终端里的命令与输出说话")
    else:
        p.port = _port_from_config(root)
    if p.kind == UNKNOWN:
        p.evidence.append("没找到依赖清单或构建文件，认不出形态，请按 GSB 的启动说明自行判断")
    return p.as_dict()


# ---------------- 录制步骤 ----------------

def _steps_headless(test: str, demo: list[str], case: list[str], suite: list[str]) -> list[dict]:
    return [
        {"title": "先亮出改动范围", "why": "开头就让人看清这一侧动了哪几个文件，后面的结论才有落点",
         "cmds": ["git diff --stat main...HEAD"]},
        {"title": "跑改动针对的那个场景", "why": "这是整段录屏最该有的一镜：同一段输入，改动前后行为到底变没变。没有界面可看，这段输出就是效果本身",
         "cmds": demo or ["（用 GSB 启动说明里的复现 / 演示命令）"]},
        {"title": "跑点名的那几条用例", "why": "证明改动是有测试兜着的，不是改完就算",
         "cmds": case or ["（GSB 启动说明里点名的用例文件）"]},
        {"title": "跑完整测试套件", "why": "对上「现有测试保持全绿」这条要求，没有回归要亲眼看到",
         "cmds": suite or ([test] if test else ["（仓库的完整测试命令）"])},
    ]


def _steps_frontend(serve: str, port: int | None, test: str) -> list[dict]:
    url = f"http://localhost:{port}" if port else "http://localhost:<端口>"
    return [
        {"title": "先亮出改动范围", "why": "让人看清这一侧动了哪几个文件",
         "cmds": ["git diff --stat main...HEAD"]},
        {"title": "把界面起起来", "why": "等编译完、终端打出地址再切浏览器，别切早了拍到白屏",
         "cmds": [serve or "（仓库的 dev 命令）"]},
        {"title": f"开 {url}，走一遍改动涉及的交互", "why": "这是最该占篇幅的一段：鼠标点到哪、界面怎么变，要让人不看代码也知道做了什么",
         "cmds": []},
        {"title": "把边界情况也点一遍", "why": "空数据、报错、加载中这些状态最容易露馅，顺手点到能显著加分",
         "cmds": []},
        {"title": "跑测试或构建", "why": "证明改完还能构建、测试还是绿的",
         "cmds": [test] if test else ["（仓库的测试或构建命令）"]},
    ]


def _steps_backend(serve: str, port: int | None, test: str) -> list[dict]:
    url = f"http://localhost:{port}" if port else "http://localhost:<端口>"
    return [
        {"title": "先亮出改动范围", "why": "让人看清这一侧动了哪几个文件",
         "cmds": ["git diff --stat main...HEAD"]},
        {"title": "把服务起起来", "why": "等日志打出监听端口再往下走，这一句也是「跑得起来」的证据",
         "cmds": [serve or "（仓库的启动命令）"]},
        {"title": "打改动涉及的接口，把响应摆出来", "why": "没有界面，接口的真实响应就是效果本身。改动前后各打一次对比最直观",
         "cmds": [f"curl -s {url}/<接口路径> | python3 -m json.tool"]},
        {"title": "打一次异常入参", "why": "错误码、报错信息是否符合预期，比正常路径更能说明改动的完成度",
         "cmds": [f"curl -s -i {url}/<接口路径> -d '<不合法的入参>'"]},
        {"title": "跑测试套件", "why": "对上「现有测试保持全绿」这条要求",
         "cmds": [test] if test else ["（仓库的测试命令）"]},
    ]


def _steps_fullstack(serve: str, port: int | None, test: str) -> list[dict]:
    url = f"http://localhost:{port}" if port else "http://localhost:<端口>"
    return [
        {"title": "先亮出改动范围", "why": "前后端各动了什么，开头一次说清",
         "cmds": ["git diff --stat main...HEAD"]},
        {"title": "先起服务端，再起前端", "why": "顺序反了前端会先报一片接口错，录进去很难看",
         "cmds": [serve or "docker compose up"]},
        {"title": f"开 {url}，从界面走完整条链路", "why": "全栈项目最该录的是端到端：界面上点一下，数据真的存下去、再读出来",
         "cmds": []},
        {"title": "顺手把后端日志或浏览器网络面板带一眼", "why": "证明界面上的变化确实来自这次改动的接口，而不是前端写死的",
         "cmds": []},
        {"title": "跑测试套件", "why": "对上「现有测试保持全绿」这条要求",
         "cmds": [test] if test else ["（仓库的测试命令）"]},
    ]


INSTALL_HINTS = ("install", "venv", "mod download", " ci")
# 一行式脚本：录屏里真正把效果演出来的就是它们
DEMO_HINTS = (" -e ", " -c ", "--input-type", "<<", "curl ")
TEST_RUNNERS = ("pytest", "jest", "mocha", "vitest", "test.js", "test/", "npm test",
                "npm run test", "go test", "cargo test", "phpunit", "rspec")


def _points_at_specific_cases(tok: str) -> bool:
    """这个参数是在点名跑某几条（文件名或用例名），还是指整个目录。

    `pytest tests/` 是跑全套，`pytest tests/test_api.py` 和 `node test/compress.js default-params`
    是跑指定的那几条 —— 录屏里这两者该出现在不同的环节。
    """
    import re
    return bool(re.search(r"\.[a-z]{2,4}$", tok)) or "/" not in tok


def _classify(cmd: str) -> str:
    """一条启动命令在录屏里该放在哪一环：演示、点名用例、还是完整套件。"""
    import re
    if any(h in cmd for h in DEMO_HINTS):
        return "demo"
    if not any(r in cmd.lower() for r in TEST_RUNNERS):
        return "demo"
    rest = re.sub(r"^\s*(npx |npm run |npm |python3? -m |python3? |node |go |cargo )+", "", cmd)
    tokens = [t for t in rest.split() if not t.startswith("-")]
    # 第一个是运行器或运行器脚本本身，之后的才是它要跑什么
    targets = tokens[1:]
    return "case" if any(_points_at_specific_cases(t) for t in targets) else "suite"


def record_plan(task_no: str, side: str, startup_commands: list[str]) -> dict:
    """探形态 + 配一份录制步骤。startup_commands 来自 GSB，用来填无界面项目的各个环节。"""
    p = probe(task_no, side)
    runnable = [c for c in startup_commands if not any(h in c for h in INSTALL_HINTS)]
    buckets: dict[str, list[str]] = {"demo": [], "case": [], "suite": []}
    for c in runnable:
        buckets[_classify(c)].append(c)
    demo = buckets["demo"]
    kind = p["kind"]
    if kind == FRONTEND:
        steps = _steps_frontend(p["serve"], p["port"], p["test"])
    elif kind == BACKEND:
        steps = _steps_backend(p["serve"], p["port"], p["test"])
    elif kind == FULLSTACK:
        steps = _steps_fullstack(p["serve"], p["port"], p["test"])
    else:
        steps = _steps_headless(p["test"], demo, buckets["case"], buckets["suite"])
    return {**p, "steps": steps, "demo_commands": demo, "install_commands": [
        c for c in startup_commands if any(h in c for h in INSTALL_HINTS)]}
