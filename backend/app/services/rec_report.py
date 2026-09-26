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
import re
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


# 单条命令的输出、命令本身、收尾总结各留多少。录屏文档只要命令形态和关键输出行
# （监听端口、状态码），几千字符的 npm 安装日志留头尾就够。
OUTPUT_KEEP = 800
CMD_KEEP = 400
SUMMARY_KEEP = 1200
BATCH_MAX = 5


def _clip(text: str, keep: int) -> str:
    text = text or ""
    if len(text) <= keep:
        return text
    half = keep // 2
    return f"{text[:half]}\n…（中间省略 {len(text) - keep} 字符）…\n{text[-half:]}"


def _slim_cmds(items: list, seen: set) -> list:
    kept = []
    for it in items or []:
        if not isinstance(it, dict):
            kept.append(it)
            continue
        cmd = str(it.get("cmd") or "").strip()
        if cmd and cmd in seen:
            continue
        seen.add(cmd)
        kept.append({**it, "cmd": _clip(cmd, CMD_KEEP), "output": _clip(str(it.get("output") or ""), OUTPUT_KEEP)})
    return kept


def slim(material: dict) -> dict:
    """去掉素材里对写文档没用的重量：同一侧重复的命令、超长输出、两侧一样的探测结果。"""
    m = json.loads(json.dumps(material, ensure_ascii=False))
    sides = m.get("sides") or {}
    for side in sides.values():
        seen: set = set()
        cmds = side.get("trace_commands")
        if isinstance(cmds, dict):
            side["trace_commands"] = {k: _slim_cmds(v, seen) for k, v in cmds.items()}
        failed = side.get("trace_failed")
        if isinstance(failed, list):
            side["trace_failed"] = _slim_cmds(failed, set())
        elif isinstance(failed, dict):
            side["trace_failed"] = {k: _slim_cmds(v, set()) for k, v in failed.items()}
        if isinstance(side.get("final_summary"), str):
            side["final_summary"] = _clip(side["final_summary"], SUMMARY_KEEP)
    probes = [s.get("probe") for s in sides.values()]
    if len(probes) == 2 and all(isinstance(p, dict) for p in probes):
        bare = [{k: v for k, v in p.items() if k != "root"} for p in probes]
        if bare[0] == bare[1]:
            m["probe_shared"] = bare[0]
            for s in sides.values():
                s["probe"] = "两侧相同，见 probe_shared"
    return m


def _trim(material: dict) -> str:
    text = json.dumps(slim(material), ensure_ascii=False, indent=1)
    if len(text) <= MATERIAL_LIMIT:
        return text
    lean = json.loads(text)
    for side in (lean.get("sides") or {}).values():
        side.pop("trace_failed", None)
        side.pop("final_summary", None)
    text = json.dumps(lean, ensure_ascii=False, indent=1)
    return text[:MATERIAL_LIMIT] + "\n…（素材过长已截断）"


def _skill_docs() -> str:
    d = skill_dir()
    read = lambda rel: (d / rel).read_text(encoding="utf-8")  # noqa: E731
    return f"""===== SKILL.md =====
{read("SKILL.md")}

===== references/report-template.md =====
{read("references/report-template.md")}

===== references/powershell-rules.md =====
{read("references/powershell-rules.md")}"""


def build_prompt(materials: list[dict], prev: dict[str, tuple[str, str]] | None = None) -> str:
    """一次写一道或几道。prev 给了就是重写轮：题号 → (上一稿片段, 校验输出)，只放没过的题。"""
    nos = [str(x.get("task_no")) for x in materials]
    if len(nos) == 1:
        no = nos[0]
        head = f"""你在执行 solo-report skill 里「设计验证点 → 核对 → 写片段」这几步，只做第 {no} 题。

分工：collect 已经由程序跑完，素材在最后；PowerShell 校验（verify_ps）、写标记、落盘都由程序做，
你不用也不能跑命令。工作目录是这道题的作答目录，A/ 和 B/ 是两侧的最终代码，需要核对端口、
路由、界面文案时可以只读查看。

输出要求：只输出这一道题的片段 markdown，从标题行 `## 第 {no} 题　…` 开始，到 B 侧最后一个
代码块或界面操作结束。"""
    else:
        listed = "、".join(nos)
        head = f"""你在执行 solo-report skill 里「设计验证点 → 核对 → 写片段」这几步，这次一起写 {len(nos)} 道题：第 {listed} 题。
这几道互不相关，每道只能用它自己那份素材：端口、路由、命令、界面文案一律不许串题。

分工：collect 已经由程序跑完，素材在最后；PowerShell 校验（verify_ps）、写标记、落盘都由程序做，
你不用也不能跑命令。工作目录下只放了这几道题，第 N 题两侧的最终代码在 N/A/ 和 N/B/，需要核对端口、
路由、界面文案时按路径直接读文件，不要整目录搜索。

输出要求：按 {listed} 的顺序依次输出每道题的片段 markdown，一道都不能少。每道从标题行
`## 第 N 题　…` 开始，到该题 B 侧最后一个代码块或界面操作结束，紧接着就是下一道的标题行，
中间不要加分隔线或说明。"""
    body = f"""{head}不要写 `<!-- solo-report:... -->` 标记行，不要任何解释、前言、总结，
不要把整段包进代码围栏。命令必须能在该题素材的 trace_commands 里找到依据，找不到的不要编。

{_skill_docs()}
"""
    for x in materials:
        body += f"\n===== 第 {x.get('task_no')} 题素材（collect.py 输出）=====\n{_trim(x)}\n"
    if not prev:
        return body
    for no, (fragment, out) in prev.items():
        body += f"""
===== 第 {no} 题：你上一稿的片段 =====
{fragment or "（上一稿没有输出这道题）"}

===== 第 {no} 题：verify_ps.py 校验输出 =====
{out[-6000:]}
"""
    which = "这道题" if len(prev) == 1 else "这几道题"
    return body + f"\n{which}上一稿没过校验。只改报错指出的地方，其余保持不变，按同样的输出要求重新输出完整片段。"


def _unfence(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        first, _, rest = s.partition("\n")
        if first.strip() in ("```", "```markdown", "```md"):
            s = rest.rstrip()
            if s.endswith("```"):
                s = s[:-3].rstrip()
    return s


def _tidy(fragment: str) -> str:
    """切出来的片段尾巴上可能挂着分隔线，或模型给每道单独包的围栏（开头那半截落在上一道尾部）。"""
    lines = fragment.rstrip().splitlines()
    while lines:
        last = lines[-1].strip()
        fences = sum(1 for ln in lines if ln.lstrip().startswith("```"))
        if last in ("", "---", "***", "```markdown", "```md") or (last.startswith("```") and fences % 2 == 1):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip() + "\n"


def extract_fragment(text: str, task_no: str) -> str:
    """从模型输出里抠出片段：去掉外层围栏和标题前的废话。"""
    s = _unfence(text)
    idx = s.find(f"## 第 {task_no} 题")
    if idx < 0:
        idx = s.find("## 第")
    if idx < 0:
        raise ReportError("模型输出里没有 `## 第 N 题` 标题行")
    return s[idx:].strip() + "\n"


def extract_fragments(text: str, task_nos: list[str]) -> dict[str, str]:
    """合写的输出按标题行切开。没找到标题的题不在结果里。"""
    s = _unfence(text)
    marks = sorted((idx, no) for no in task_nos if (idx := s.find(f"## 第 {no} 题")) >= 0)
    out = {}
    for k, (idx, no) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(s)
        out[no] = _tidy(s[idx:end])
    return out


def pack(sizes: list[tuple[str, int]], *, limit: int, max_n: int) -> list[list[str]]:
    """按顺序装批：道数不超 max_n，素材合计不超 limit。一道自己就超的单独一批。"""
    max_n = max(1, min(max_n, BATCH_MAX))
    batches: list[list[str]] = []
    cur: list[str] = []
    total = 0
    for no, size in sizes:
        if cur and (len(cur) >= max_n or total + size > limit):
            batches.append(cur)
            cur, total = [], 0
        cur.append(no)
        total += size
    if cur:
        batches.append(cur)
    return batches


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


_DOC_MARK = re.compile(r"^<!-- solo-report:task=(\d+)([^>]*)-->\s*$", re.M)


@dataclass
class DocSection:
    task_no: str
    fragment: str
    generated: str      # 标记里的日期，YYYY-MM-DD
    digest: str         # 本项目写的标记才有；对话里 render.py 写的没有

    @property
    def kind_label(self) -> str:
        head = self.fragment.splitlines()[0] if self.fragment else ""
        return head.rsplit("·", 1)[-1].strip() if "·" in head else ""


def parse_doc(text: str) -> dict[str, DocSection]:
    """把 docs/SoloReport.md 按题切开。一道题出现多次取最后一段。

    skill 的 render.py 把标记放在标题行下面，本项目的 render 放在上面，两种都认：
    一段从这道题的标题行开始，到下一道的开头为止，标记行本身不进片段。
    """
    text = text or ""
    spans = []
    for mk in _DOC_MARK.finditer(text):
        no = mk.group(1)
        head = f"## 第 {no} 题"
        after = text[mk.end():].lstrip()
        if after.startswith(head):
            start = mk.start()
        else:
            start = text.rfind(head, 0, mk.start())
            if start < 0 or text[start:mk.start()].count("\n") > 2:
                continue
        spans.append((start, mk))
    out: dict[str, DocSection] = {}
    for k, (start, mk) in enumerate(spans):
        end = spans[k + 1][0] if k + 1 < len(spans) else len(text)
        before, after = text[start:mk.start()].strip(), text[mk.end():end].strip()
        body = f"{before}\n\n{after}" if before else after
        if not body.startswith("## 第"):
            continue
        attrs = dict(re.findall(r"(\w+)=(\S+)", mk.group(2)))
        out[mk.group(1)] = DocSection(task_no=mk.group(1), fragment=_tidy(body),
                                      generated=attrs.get("generated", ""), digest=attrs.get("digest", ""))
    return out


def read_doc() -> dict[str, DocSection]:
    try:
        return parse_doc(config.SOLO_REPORT_DOC.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _workdir(nos: list[str], scratch: Path) -> Path | None:
    """模型的工作目录。合写时不能给作答总目录：几百道题带 node_modules，几路 CLI 同时 rg
    全盘扫，Docker Desktop 的文件共享会被压垮，整个后端卡死在读文件上。建一个只链这几道题的
    临时目录，rg 默认不跟软链接，读文件照样能读。"""
    root = config.CODER_ROOT_MOUNT / config.WORKSPACE_DIR
    if len(nos) == 1:
        ws = root / nos[0]
        return ws if ws.is_dir() else None
    linked = 0
    for no in nos:
        if (root / no).is_dir():
            (scratch / no).symlink_to(root / no, target_is_directory=True)
            linked += 1
    return scratch if linked else None


async def _write(nos: list[str], materials: dict[str, dict], note, model: str) -> dict:  # noqa: ANN001
    """一批题调一次模型；没过校验的题留下来，下一稿只带它们重写。"""
    results: dict[str, Report | Exception] = {}
    frags: dict[str, str] = {}
    outs: dict[str, str] = {}
    pending = list(nos)
    for round_no in range(1, MAX_ROUNDS + 1):
        together = f"（{len(pending)} 道合写）" if len(pending) > 1 else ""
        for no in pending:
            note(no, "write", f"第 {round_no} 稿：模型写片段{together}")
        prev = {no: (frags.get(no, ""), outs.get(no, "")) for no in pending} if round_no > 1 else None
        prompt = build_prompt([materials[no] for no in pending], prev)
        try:
            # 放容器自己的 /tmp，不放 DATA_DIR：那也是共享挂载
            with tempfile.TemporaryDirectory(prefix="rec-ws-") as scratch:
                res = await llm.ask(prompt, model=model, purpose=f"录屏文档 {'、'.join(pending)}",
                                    attempts=2, cwd=_workdir(pending, Path(scratch)))
        except Exception as exc:  # noqa: BLE001
            return {**results, **{no: exc for no in pending}}
        if len(pending) == 1:
            try:
                got = {pending[0]: extract_fragment(res.text, pending[0])}
            except ReportError:
                got = {}
        else:
            got = extract_fragments(res.text, pending)
        left = []
        for no in pending:
            if no not in got:
                frags[no], outs[no] = "", f"模型输出里没有 `## 第 {no} 题` 标题行"
                left.append(no)
                continue
            note(no, "verify", f"第 {round_no} 稿：PowerShell 四层校验")
            ok, out = await verify(got[no])
            frags[no], outs[no] = got[no], out
            if ok:
                results[no] = Report(fragment=got[no], material=materials[no], rounds=round_no,
                                     verify_tail=out[-1500:], model=res.model)
            else:
                log.info("录屏文档 %s 第 %d 稿没过校验：%s", no, round_no, out[-300:])
                left.append(no)
        pending = left
        if not pending:
            return results
    for no in pending:
        results[no] = ReportError(f"写了 {MAX_ROUNDS} 稿仍没过 PowerShell 校验，最后一次输出：{outs[no][-600:]}")
    return results


async def generate_many(task_nos: list[str], *, progress=None, model: str = "",  # noqa: ANN001
                        max_n: int = 1, limit: int = 120_000) -> dict[str, Report | Exception]:
    """几道题一起写。每道各自成功或失败，结果按题号给：Report 或异常。

    素材按 limit / max_n 装成若干批，一批一次模型调用，批与批串行。
    """
    note = progress or (lambda *_: None)
    if missing := preflight():
        err = ReportError("；".join(missing))
        return {str(no): err for no in task_nos}
    results: dict[str, Report | Exception] = {}
    materials: dict[str, dict] = {}
    for no in map(str, task_nos):
        note(no, "collect", "收集素材")
        try:
            materials[no] = await collect(no)
        except Exception as exc:  # noqa: BLE001
            results[no] = exc
    sizes = [(no, len(_trim(mat))) for no, mat in materials.items()]
    for nos in pack(sizes, limit=limit, max_n=max_n):
        results.update(await _write(nos, materials, note, model))
    return results


async def generate(task_no: str, *, progress=None, model: str = "") -> Report:  # noqa: ANN001
    """一道题从素材到通过校验的片段。失败抛 ReportError / llm.LlmError。"""
    note = (lambda _no, stage, text: progress(stage, text)) if progress else None
    res = (await generate_many([str(task_no)], progress=note, model=model))[str(task_no)]
    if isinstance(res, Exception):
        raise res
    return res
