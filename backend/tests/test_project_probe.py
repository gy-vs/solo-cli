"""项目形态探测：录屏该怎么录全看这个判定，判错了整段录屏就录偏了。

这里锁住的都是踩过的坑：关键词扫描把库判成服务端、按目录名认子项目把纯后端判成全栈。
"""

import json

import pytest

import app.services.project_probe as pp
from app.services.project_probe import BACKEND, FRONTEND, FULLSTACK, HEADLESS, UNKNOWN


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """把 TaskPaths 指到临时目录，想摆什么项目摆什么项目。"""
    class Paths:
        def __init__(self, *_a):
            self.workspace = tmp_path

    monkeypatch.setattr(pp.config, "TaskPaths", Paths)
    return tmp_path


def write_pkg(root, deps=None, scripts=None):
    (root / "package.json").write_text(json.dumps({
        "dependencies": {d: "*" for d in (deps or [])},
        "scripts": scripts or {},
    }), "utf-8")


def test_library_without_any_framework_is_headless(workspace):
    write_pkg(workspace, deps=["acorn", "source-map"], scripts={"test": "mocha"})
    r = pp.probe("01", "A")
    assert r["kind"] == HEADLESS
    assert r["serve"] == ""          # 没有可访问的地址，别给人一个跑不通的启动命令
    assert r["test"] == "npm run test"


def test_frontend_deps_make_it_frontend(workspace):
    write_pkg(workspace, deps=["vue", "vite"], scripts={"dev": "vite"})
    r = pp.probe("01", "A")
    assert r["kind"] == FRONTEND
    assert r["serve"] == "npm run dev"


def test_server_deps_make_it_backend(workspace):
    write_pkg(workspace, deps=["express", "mongoose"], scripts={"start": "node index.js"})
    assert pp.probe("01", "A")["kind"] == BACKEND


def test_both_sides_make_it_fullstack(workspace):
    write_pkg(workspace, deps=["react", "express"])
    assert pp.probe("01", "A")["kind"] == FULLSTACK


def test_prose_mentioning_a_framework_does_not_count(workspace):
    """jinja2 的 setup.py 里有一句「Django inspired syntax」。

    早先在 setup.py 上做关键词扫描，把这个模板库判成了 Django 服务端项目，
    录屏指引就会让人去 runserver 一个根本没有的服务。
    """
    (workspace / "setup.py").write_text(
        'setup(description="A template engine with Django inspired syntax")', "utf-8")
    (workspace / "setup.cfg").write_text("[metadata]\nname = jinja2\n", "utf-8")
    (workspace / "tests").mkdir()
    r = pp.probe("01", "A")
    assert r["kind"] == HEADLESS
    assert r["serve"] == ""


def test_declared_dependency_does_count(workspace):
    (workspace / "requirements.txt").write_text("flask>=2.0\nrequests\n", "utf-8")
    assert pp.probe("01", "A")["kind"] == BACKEND


def test_source_package_named_app_is_not_a_frontend(workspace):
    """Python 后端里的 app/ 是源码包，不是前端子项目。

    只按目录名认 monorepo 子项目的话，一个纯后端仓库会被判成全栈。
    """
    (workspace / "requirements.txt").write_text("fastapi\nuvicorn\n", "utf-8")
    (workspace / "app").mkdir()
    (workspace / "app" / "main.py").write_text("x = 1", "utf-8")
    assert pp.probe("01", "A")["kind"] == BACKEND


def test_monorepo_subdirs_need_real_project_files(workspace):
    """前端目录名是 frontend-<角色>，按前缀认；但里面得真有个项目。"""
    (workspace / "requirements.txt").write_text("fastapi\n", "utf-8")
    (workspace / "frontend-console").mkdir()
    write_pkg(workspace / "frontend-console", deps=["vue"])
    assert pp.probe("01", "A")["kind"] == FULLSTACK


def test_empty_dir_is_unknown_not_a_guess(workspace):
    """认不出来就说认不出来。猜一个形态比不猜更耽误事。"""
    r = pp.probe("01", "A")
    assert r["kind"] == UNKNOWN
    assert "认不出形态" in " ".join(r["evidence"])


def test_headless_plan_uses_gsb_demo_commands(workspace):
    """无界面项目没有界面可录，演示命令就是内容本身，必须原样进步骤。"""
    write_pkg(workspace, deps=["acorn"], scripts={"test": "mocha"})
    plan = pp.record_plan("01", "A", ["npm install", "node test/compress.js", "node -e \"...\""])
    assert plan["kind"] == HEADLESS
    assert plan["demo_commands"] == ["node -e \"...\""]   # 装依赖和跑套件都不算演示
    assert plan["install_commands"] == ["npm install"]


@pytest.mark.parametrize(("cmd", "bucket"), [
    ("node --input-type=module -e \"import ...\"", "demo"),
    ("curl -s http://localhost:8000/api", "demo"),
    # 点名跑某个文件或某条用例
    ("node test/compress.js default-parameters-scope", "case"),
    ("python -m pytest tests/test_api.py -q", "case"),
    # 跑整套
    ("node test/compress.js", "suite"),
    ("npx mocha test/mocha", "suite"),
    ("python -m pytest tests/ -q", "suite"),
    ("python -m pytest -q", "suite"),
])
def test_commands_land_in_the_right_take(cmd, bucket):
    """跑复现、跑点名用例、跑全套是录屏里三个不同的环节，命令不能混着塞。"""
    assert pp._classify(cmd) == bucket


def test_suite_and_case_commands_split_into_separate_steps(workspace):
    write_pkg(workspace, deps=["acorn"], scripts={"test": "mocha"})
    plan = pp.record_plan("01", "A", [
        "npm install",
        "node test/compress.js default-parameters-scope",
        "node test/compress.js",
        "node -e \"console.log(1)\"",
    ])
    titles = {s["title"]: s["cmds"] for s in plan["steps"]}
    assert titles["跑改动针对的那个场景"] == ["node -e \"console.log(1)\""]
    assert titles["跑点名的那几条用例"] == ["node test/compress.js default-parameters-scope"]
    assert titles["跑完整测试套件"] == ["node test/compress.js"]


def test_frontend_plan_tells_you_to_open_the_browser(workspace):
    write_pkg(workspace, deps=["react"], scripts={"dev": "vite"})
    plan = pp.record_plan("01", "A", [])
    assert plan["kind"] == FRONTEND
    assert any("localhost" in s["title"] for s in plan["steps"])
