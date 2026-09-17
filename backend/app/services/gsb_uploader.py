"""GSB 提交：form-schema → 上传两份轨迹 → POST /gsb/submissions。

字段清单由平台后台配置，不能硬编码：上传前实时拉一次 schema，按返回的 fields 决定填
什么。schema 里出现映射表没覆盖的必填字段时，宁可停下来报字段名，也不猜一个值填进去——
猜错了提交会被算成无效，比停下来问一句贵得多。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from app import config
from app.db import session
from app.events import bus
from app.models import UPLOADABLE, UPLOADED, Task, TaskRun, utc_now
from app.services import dockerx, gate, gsb_repo, settings_store
from app.services.gsb_analyzer import VERDICT_LABEL

log = logging.getLogger("gsb_uploader")
API = "/api/v1"

# 平台固定选项，题块里不记这些
HARNESS = "Claude Code"
OS_PLATFORM = "MacOS/Linux"
DEFAULT_VALIDITY = "有效"

# 两侧共用的字段不带前缀，按侧取值的字段带 a_/b_ 前缀
_SIDE_FIELDS = ("session_id", "trace_file", "artifact_snapshot", "screencast")


def _client() -> httpx.AsyncClient:
    base = settings_store.get("gsb.base_url").rstrip("/")
    cookie = settings_store.get("gsb.session_cookie")
    csrf = settings_store.get("gsb.csrf_token")
    if not (base and cookie and csrf):
        raise RuntimeError("GSB 平台身份未配置完整（地址 / solo_qa_session / solo_qa_csrf）")
    return httpx.AsyncClient(
        base_url=base,
        cookies={"solo_qa_session": cookie, "solo_qa_csrf": csrf},
        headers={"X-CSRF-Token": csrf, "User-Agent": "solo-cli/2.0", "Accept": "application/json"},
        timeout=httpx.Timeout(120, connect=20),
        follow_redirects=False,
    )


async def probe_identity() -> dict:
    try:
        async with _client() as c:
            r = await c.get(f"{API}/auth/me")
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"请求失败：{exc}"}
    if r.status_code == 200:
        u = r.json()
        return {"ok": True,
                "message": f"已登录：{u.get('real_name') or u.get('username')}（{u.get('role', '')}）"}
    return {"ok": False, "message": f"HTTP {r.status_code}：{r.text[:200]}"}


async def probe_gateway() -> dict:
    key = settings_store.get("cc.api_key")
    if not key:
        return {"ok": False, "message": "未配置网关 Key"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://llm.jzxhnh.com/v1/models",
                            headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"无法连接网关：{exc}"}
    if r.status_code in (200, 404, 405):
        return {"ok": True, "message": f"网关可达，Key 已被接受（HTTP {r.status_code}）"}
    if r.status_code in (401, 403):
        return {"ok": False, "message": f"网关拒绝该 Key（HTTP {r.status_code}）"}
    return {"ok": False, "message": f"网关返回 HTTP {r.status_code}"}


async def build_values(task: Task, runs: dict[str, TaskRun]) -> dict:
    """算出所有能自动填的字段值。轨迹附件要先上传拿到引用，所以不在这里。"""
    gsb = task.gsb or {}
    screencast = task.screencast or {}
    version = task.harness_version
    image = runs["A"].image_tag or settings_store.get("cc.image")
    if image and (real := await dockerx.claude_version(image)):
        # 以镜像实测为准：题块里的版本号是出题时写的，镜像更新过就对不上了
        version = real
    values = {
        "user_prompt": task.user_prompt,
        "question_type": gate.normalize_choice(task.question_type, gate.QUESTION_TYPES),
        "difficulty": gate.normalize_choice(task.difficulty, gate.DIFFICULTIES),
        "languages": task.languages,
        "harness": HARNESS,
        "harness_version": version,
        "os_platform": OS_PLATFORM,
        "repro_level": gate.normalize_choice(task.repro_level, gate.REPRO_LEVELS),
        "env_snapshot": task.env_snapshot,
        "gsb_verdict": VERDICT_LABEL.get(gsb.get("verdict", ""), ""),
        "gsb_reason": gsb.get("reason", ""),
        "validity": gsb.get("validity") or DEFAULT_VALIDITY,
        "remark": gsb.get("remark", ""),
    }
    for side in config.SIDES:
        run = runs[side]
        low = side.lower()
        values[f"{low}_session_id"] = run.session_id
        values[f"{low}_artifact_snapshot"] = run.artifact_url or gsb_repo.commit_url(
            task.repo_url, run.artifact_sha)
        values[f"{low}_screencast"] = screencast.get(side, "")
    return values


def missing_required(schema: dict, values: dict) -> list[str]:
    """schema 说必填、而我们没值的字段。附件字段单独处理，不在这里查。"""
    out = []
    for f in (schema.get("fields") or []):
        key = f.get("field_key") or f.get("key")
        if not key or not f.get("required"):
            continue
        if key.endswith("trace_file"):
            continue
        if not str(values.get(key) or "").strip():
            out.append(key)
    return out


def unknown_required(schema: dict, values: dict) -> list[str]:
    """schema 要求必填、但映射表里根本没有的字段。

    平台后台加了新必填项时会走到这里。不猜值：猜错了这一单会被判无效，
    而报出字段名人工补一下只要一分钟。
    """
    known = set(values) | {f"{s.lower()}_trace_file" for s in config.SIDES}
    return [f.get("field_key") or f.get("key")
            for f in (schema.get("fields") or [])
            if f.get("required") and (f.get("field_key") or f.get("key")) not in known]


async def _upload_file(c: httpx.AsyncClient, path: Path, kind: str = "") -> dict:
    data = {"kind": kind} if kind else None
    with path.open("rb") as fp:
        r = await c.post(f"{API}/submissions/upload",
                         files={"file": (path.name, fp, "application/octet-stream")},
                         data=data)
    if r.status_code != 200:
        raise RuntimeError(f"上传 {path.name} 失败 HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


async def upload_screencast(task_id: int, side: str, path: Path) -> dict:
    """代传本地录屏文件，把平台返回的 URL 记进题目。"""
    if not path.exists():
        return {"ok": False, "message": f"文件不存在：{path}"}
    try:
        async with _client() as c:
            ref = await _upload_file(c, path, kind="video")
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"请求失败：{exc}"}
    url = ref.get("url") or ref.get("path") or ""
    if not url:
        return {"ok": False, "message": f"平台没返回视频地址：{str(ref)[:200]}"}
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        sc = dict(task.screencast)
        sc[side.upper()] = url
        task.screencast = sc
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "url": url, "message": f"{side} 侧录屏已上传"}


def _fail(task_id: int, record: dict, message: str, *,
          fields: dict | None = None, auth: bool = False) -> dict:
    record["ok"] = False
    record["message"] = message
    if fields:
        record["fields"] = fields
    with session() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.upload = record
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": False, "message": message, "fields": fields or {}, "auth_error": auth}


async def upload_task(task_id: int) -> dict:
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.status not in UPLOADABLE:
            return {"ok": False, "message": f"当前状态 {task.status} 不允许上传，需先完成 GSB 分析"}
        if (task.verify or {}).get("overall") == "block":
            return {"ok": False, "message": "核验存在红项，先处理后再上传"}
        runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
        if set(runs) != set(config.SIDES):
            return {"ok": False, "message": f"两侧的运行记录不全，只有 {sorted(runs) or '空'}"}
        traces = {s: Path(r.trace_file) for s, r in runs.items() if r.trace_file}
        values = await build_values(task, runs)
        task_no = task.task_no

    for side in config.SIDES:
        if side not in traces or not traces[side].exists():
            return {"ok": False, "message": f"{side} 侧的轨迹文件缺失，无法上传"}

    record: dict = {"started_at": utc_now().isoformat(), "steps": []}
    try:
        async with _client() as c:
            me = await c.get(f"{API}/auth/me")
            if me.status_code != 200:
                return _fail(task_id, record,
                             f"身份失效（HTTP {me.status_code}），请到设置页更新 Cookie", auth=True)
            record["steps"].append("auth/me ok")

            fs = await c.get(f"{API}/gsb/form-schema")
            if fs.status_code != 200:
                return _fail(task_id, record,
                             f"获取表单字段失败 HTTP {fs.status_code}: {fs.text[:200]}")
            schema = fs.json()
            fingerprint = schema.get("fingerprint", "")
            record["steps"].append(f"form-schema fingerprint={fingerprint}")

            if unknown := unknown_required(schema, values):
                return _fail(task_id, record,
                             f"平台新增了必填字段，本地没有对应来源，请人工确认：{', '.join(unknown)}",
                             fields={k: "本地无此字段" for k in unknown})
            if missing := missing_required(schema, values):
                human = {"a_screencast": "A 侧录屏链接", "b_screencast": "B 侧录屏链接"}
                names = [human.get(k, k) for k in missing]
                return _fail(task_id, record, f"字段缺失：{', '.join(names)}",
                             fields={k: "缺值" for k in missing})

            data = dict(values)
            for side in config.SIDES:
                ref = await _upload_file(c, traces[side])
                data[f"{side.lower()}_trace_file"] = [
                    {"name": ref.get("name"), "path": ref.get("path"), "size": ref.get("size")}]
                record["steps"].append(f"{side} 轨迹上传 ok path={ref.get('path')}")

            body_json = {"data": data, "schema_fingerprint": fingerprint}
            resp = await c.post(f"{API}/gsb/submissions", json=body_json)
            if resp.status_code == 503:
                # 轨迹落盘或 COS 暂不可用：等 3 秒重试一次
                record["steps"].append("503, retry once")
                await asyncio.sleep(3)
                resp = await c.post(f"{API}/gsb/submissions", json=body_json)
            record["status_code"] = resp.status_code
            try:
                body = resp.json()
            except ValueError:
                body = {"detail": resp.text[:500]}
            record["response"] = body

            if resp.status_code in (200, 201):
                with session() as db:
                    task = db.get(Task, task_id)
                    if task is not None:
                        task.status = UPLOADED
                        task.uploaded_at = utc_now()
                        record["ok"] = True
                        record["submission_id"] = body.get("id")
                        task.upload = record
                bus.publish("tasks", {"type": "task", "id": task_id})
                log.info("题 %s 上传成功 id=%s", task_no, body.get("id"))
                return {"ok": True, "message": body.get("message") or "提交成功",
                        "submission_id": body.get("id"), "status": body.get("status")}
            if resp.status_code == 422:
                errors = body.get("errors") or []
                fields = {e.get("field"): e.get("message") for e in errors if isinstance(e, dict)}
                return _fail(task_id, record, body.get("detail") or "校验未通过", fields=fields)
            if resp.status_code in (401, 403):
                return _fail(task_id, record,
                             f"HTTP {resp.status_code}：{body.get('detail', '')}", auth=True)
            return _fail(task_id, record,
                         f"HTTP {resp.status_code}：{str(body.get('detail', body))[:300]}")
    except RuntimeError as exc:
        return _fail(task_id, record, str(exc), auth=True)
    except httpx.HTTPError as exc:
        return _fail(task_id, record, f"请求失败：{exc}")
