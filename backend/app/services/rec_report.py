"""录屏文档生成：把 /solo-report 那套流程拆开，确定性的步骤由后端跑，只有写片段问模型。

规则只有 `~/.cursor/skills/solo-report` 那一份，本项目不留副本：素材靠 skill 自带的
collect.py 收，片段按 skill 的模板与 PowerShell 规则写，校验跑 skill 自带的 verify_ps.py。
skill 改了什么这里自动跟上。

为什么不让 Cursor CLI 整个跑 skill：那要放开 shell（collect 要读库、verify 要起 docker），
而分析、质检、出题一律是问答模式，动作由后端做。这里沿用同一条线 —— 模型只负责
「设计验证点、写片段」这一步，校验不过就把报错原样喂回去，最多 MAX_ROUNDS 轮。

verify_ps.py 会 `docker run -v <临时目录>:/work -v <脚本目录>:/check`，这两个源路径在
后端容器里看到的是 /data/... 和 /host/skills/...，宿主 daemon 找不到。脚本不改，
用一个包装器拦住 subprocess.run，把 -v 的源翻译成宿主路径，临时目录也挪到 DATA_DIR 下。
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app import config
from app.services import dockerx, llm

log = logging.getLogger("solo-cli.rec")

SKILL = "solo-report"
MAX_ROUNDS = 3
# 素材 JSON 的上限。轨迹命令输出已经被 collect 截过，但全栈题两侧加起来仍可能过大，
# 超了先丢最不要紧的字段（失败命令、收尾总结）。
MATERIAL_LIMIT = 90_000

_VERIFY_WRAPPER = r"""
import json, os, runpy, subprocess, sys, tempfile
tempfile.tempdir = os.environ["REC_TMP"]
MAP = json.loads(os.environ["REC_PATHMAP"])
_run = subprocess.run

def _tr(p):
    for m, h in MAP:
        m = m.rstrip("/")
        if p == m or p.startswith(m + "/"):
            return h.rstrip("/") + p[len(m):]
    return p

def run(args, *a, **k):
    if isinstance(args, list) and args and args[0] == "docker":
        out, i = [], 0
        while i < len(args):
            if args[i] == "-v" and i + 1 < len(args):
                src, _, rest = args[i + 1].partition(":")
                out += ["-v", _tr(src) + ":" + rest]
                i += 2
                continue
            out.append(args[i])
            i += 1
        args = out
    return _run(args, *a, **k)

subprocess.run = run
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
"""


class ReportError(RuntimeError):
    pass


@dataclass
class Report:
    fragment: str
    material: dict
    rounds: int
    verify_tail: str
    model: str


def skill_dir() -> Path:
    return config.SKILL_DIR_MOUNT / SKILL


def preflight() -> list[str]:
    """缺什么。空表示可以生成。"""
    d = skill_dir()
    missing = []
    for rel in ("SKILL.md", "references/report-template.md", "references/powershell-rules.md",
                "scripts/collect.py", "scripts/verify_ps.py"):
        if not (d / rel).is_file():
            missing.append(f"skill 缺 {rel}（{d}）")
    return missing


def _scratch() -> Path:
    d = config.DATA_DIR / "rec" / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def collect(task_no: str) -> dict:
    """跑 skill 的 collect.py 拿这道题的素材。

    collect 认的是 `<root>/data/solo-cli.db`，root 是 solo-cli 仓库根目录；后端容器里没有
    仓库，只有 /data。搭一个临时 root，把 data 链到真正的数据目录。临时 root 不放在
    DATA_DIR 里：data 链回自己的上级，谁要是递归扫 DATA_DIR 就会绕圈。
    """
    script = skill_dir() / "scripts" / "collect.py"
    with tempfile.TemporaryDirectory(prefix="rec-root-") as root:
        (Path(root) / "data").symlink_to(config.DATA_DIR, target_is_directory=True)
        out = Path(root) / "material.json"
        r = await dockerx.run(
            [sys.executable, str(script), "--root", root, "--task", str(task_no), "--all",
             "--out", str(out), "--coder-root", str(config.CODER_ROOT_MOUNT)],
            timeout=900)
        if not r.ok or not out.is_file():
            raise ReportError(f"collect.py 失败：{(r.err or r.out).strip()[-400:]}")
        data = json.loads(out.read_text(encoding="utf-8"))
    for item in data.get("tasks") or []:
        if str(item.get("task_no")) == str(task_no):
            return item
    raise ReportError("collect.py 没有收到这道题：它只收状态为待录屏（QC）的题")


def _trim(material: dict) -> str:
    text = json.dumps(material, ensure_ascii=False, indent=1)
    if len(text) <= MATERIAL_LIMIT:
        return text
    slim = json.loads(text)
    for side in (slim.get("sides") or {}).values():
        side.pop("trace_failed", None)
        side.pop("final_summary", None)
    text = json.dumps(slim, ensure_ascii=False, indent=1)
    return text[:MATERIAL_LIMIT] + "\n…（素材过长已截断）"


def build_prompt(material: dict) -> str:
    d = skill_dir()
    read = lambda rel: (d / rel).read_text(encoding="utf-8")  # noqa: E731
    no = material.get("task_no")
    return f"""你在执行 solo-report skill 里「设计验证点 → 核对 → 写片段」这几步，只做第 {no} 题。

分工：collect 已经由程序跑完，素材在最后；PowerShell 校验（verify_ps）、写标记、落盘都由程序做，
你不用也不能跑命令。工作目录是这道题的作答目录，A/ 和 B/ 是两侧的最终代码，需要核对端口、
路由、界面文案时可以只读查看。

输出要求：只输出这一道题的片段 markdown，从标题行 `## 第 {no} 题　…` 开始，到 B 侧最后一个
代码块或界面操作结束。不要写 `<!-- solo-report:... -->` 标记行，不要任何解释、前言、总结，
不要把整段包进代码围栏。命令必须能在素材的 trace_commands 里找到依据，找不到的不要编。

===== SKILL.md =====
{read("SKILL.md")}

===== references/report-template.md =====
{read("references/report-template.md")}

===== references/powershell-rules.md =====
{read("references/powershell-rules.md")}

===== 第 {no} 题素材（collect.py 输出）=====
{_trim(material)}
"""


def build_fix_prompt(base: str, fragment: str, verify_out: str, round_no: int) -> str:
    return f"""{base}

===== 你上一稿的片段（第 {round_no} 稿）=====
{fragment}

===== verify_ps.py 校验输出 =====
{verify_out[-6000:]}

上一稿没过校验。只改报错指出的地方，其余保持不变，按同样的输出要求重新输出完整片段。"""


def extract_fragment(text: str, task_no: str) -> str:
    """从模型输出里抠出片段：去掉外层围栏和标题前的废话。"""
    s = (text or "").strip()
    if s.startswith("```"):
        first, _, rest = s.partition("\n")
        if first.strip() in ("```", "```markdown", "```md"):
            s = rest.rstrip()
            if s.endswith("```"):
                s = s[:-3].rstrip()
    idx = s.find(f"## 第 {task_no} 题")
    if idx < 0:
        idx = s.find("## 第")
    if idx < 0:
        raise ReportError("模型输出里没有 `## 第 N 题` 标题行")
    return s[idx:].strip() + "\n"


async def verify(fragment: str) -> tuple[bool, str]:
    """跑 skill 的 verify_ps.py 四层校验。返回 (是否通过, 输出)。"""
    script = skill_dir() / "scripts" / "verify_ps.py"
    work = _scratch()
    with tempfile.TemporaryDirectory(dir=work, prefix="verify-") as tmp:
        doc = Path(tmp) / "fragment.md"
        doc.write_text(fragment, encoding="utf-8")
        pathmap = [[str(config.DATA_DIR), config.DATA_DIR_HOST],
                   [str(config.SKILL_DIR_MOUNT), config.SKILL_DIR_HOST]]
        env = {**os.environ, "REC_TMP": str(work), "REC_PATHMAP": json.dumps(pathmap)}
        r = await dockerx.run([sys.executable, "-c", _VERIFY_WRAPPER, str(script), str(doc)],
                              timeout=900, env=env)
    out = (r.out + ("\n" + r.err if r.err.strip() else "")).strip()
    return r.ok, out


def render(fragment: str, *, task_no: str, owner: str, digest: str) -> str:
    """最终的 report.md：skill 的标记行加片段。"""
    mark = f"<!-- solo-report:task={task_no} generated={dt.date.today().isoformat()} " \
           f"device={owner} digest={digest} -->"
    return f"{mark}\n\n{fragment.strip()}\n"


async def generate(task_no: str, *, progress=None) -> Report:  # noqa: ANN001
    """一道题从素材到通过校验的片段。失败抛 ReportError / llm.LlmError。"""
    if missing := preflight():
        raise ReportError("；".join(missing))
    note = progress or (lambda *_: None)
    note("collect", "收集素材")
    material = await collect(task_no)
    base = build_prompt(material)
    ws = config.CODER_ROOT_MOUNT / config.WORKSPACE_DIR / str(task_no)
    cwd = ws if ws.is_dir() else None

    prompt, fragment, out, model = base, "", "", ""
    for round_no in range(1, MAX_ROUNDS + 1):
        note("write", f"第 {round_no} 稿：模型写片段")
        res = await llm.ask(prompt, purpose=f"录屏文档 {task_no}", attempts=2, cwd=cwd)
        model = res.model
        try:
            fragment = extract_fragment(res.text, str(task_no))
        except ReportError as exc:
            out = str(exc)
            prompt = build_fix_prompt(base, res.text[:4000], out, round_no)
            continue
        note("verify", f"第 {round_no} 稿：PowerShell 四层校验")
        ok, out = await verify(fragment)
        if ok:
            return Report(fragment=fragment, material=material, rounds=round_no,
                          verify_tail=out[-1500:], model=model)
        log.info("录屏文档 %s 第 %d 稿没过校验：%s", task_no, round_no, out[-300:])
        prompt = build_fix_prompt(base, fragment, out, round_no)
    raise ReportError(f"写了 {MAX_ROUNDS} 稿仍没过 PowerShell 校验，最后一次输出：{out[-600:]}")
