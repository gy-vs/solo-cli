"""GSB 提交：form-schema → 上传两份轨迹 → POST /gsb/submissions。

字段清单由平台后台配置，不能硬编码：上传前实时拉一次 schema，按返回的 fields 决定填
什么。schema 里出现映射表没覆盖的必填字段时，宁可停下来报字段名，也不猜一个值填进去——
猜错了提交会被算成无效，比停下来问一句贵得多。
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

import httpx

from app import config
from app.db import session
from app.events import bus
from app.models import UPLOADED, Task, TaskRun, utc_now
from app.services import (
    dockerx, gate, gsb_attribution, gsb_precheck, gsb_repo, gsb_rules, settings_store,
)
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


async def build_values_for(task_id: int) -> dict:
    """按题号装配提交字段。

    质检要的字段和上传是同一套：送去质检的必须就是将来要提交的那份，
    两边各拼一次早晚会拼出差异，于是质检过了、提交却被打回。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            raise ValueError("题目不存在")
        runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
        if set(runs) != set(config.SIDES):
            raise ValueError(f"两侧的运行记录不全，只有 {sorted(runs) or '空'}")
        return await build_values(task, runs)


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
        delivery = gsb.get(f"{low}_delivery") or {}
        score = gsb_rules.parse_score(delivery.get("score"))
        values[f"{low}_score_delivery"] = score if score is not None else ""
        values[f"{low}_desc_delivery"] = str(delivery.get("desc") or "")
    return values


# 交付完整性这两对字段的 key 没拿到过实物：form-schema 要登录态，而写这段的时候平台身份
# 已经失效。先按老五维的 score_delivery / desc_delivery 加侧别前缀取名；后台实际用的 key
# 不一样时，按字段标签认——标签里同时写着「交付完整性」和侧别的那两个，按「描述」还是
# 「分」分给描述和评分。认不出来的照旧落到 unknown_required 那里停下来报字段名，不猜。
_DELIVERY_KIND = (("desc", ("描述", "说明", "desc")), ("score", ("评分", "分数", "得分", "score", "分")))


def _delivery_target(f: dict) -> str:
    """这个 schema 字段对应的本地交付完整性字段名，认不出来返回空串。"""
    key = _field_key(f)
    label = " ".join(str(f.get(k) or "") for k in ("label", "name", "title"))
    text = f"{label} {key}"
    if "交付完整性" not in text and "delivery" not in key.lower():
        return ""
    side = ""
    if re.search(r"(?<![A-Za-z])A(?![A-Za-z])", label) or key.lower().startswith("a_"):
        side = "a"
    if re.search(r"(?<![A-Za-z])B(?![A-Za-z])", label) or key.lower().startswith("b_"):
        side = "" if side else "b"
    kind = next((k for k, words in _DELIVERY_KIND if any(w in text.lower() for w in words)), "")
    return f"{side}_{kind}_delivery" if side and kind else ""


def _score_value(f: dict, score):
    """评分按字段类型给：数字类型给整数，下拉给能对上的那个选项值，其余给字符串。"""
    if score in ("", None):
        return ""
    options = f.get("options") or []
    for o in options:
        v = o.get("value") if isinstance(o, dict) else o
        lab = str(o.get("label") if isinstance(o, dict) else o)
        if str(v).strip() == str(score) or re.match(rf"\s*{score}(?!\d)", lab):
            return v
    if f.get("field_type") in ("number", "integer", "int", "rating", "score", "slider"):
        return int(score)
    return str(score)


def resolve_fields(schema: dict, values: dict) -> dict:
    """按 schema 把交付完整性的值挂到平台实际用的 key 上，评分按字段类型换成对应的形态。"""
    out = dict(values)
    for f in enabled_fields(schema):
        key = _field_key(f)
        target = key if key in values and key.endswith("_delivery") else _delivery_target(f)
        if not target or target not in values:
            continue
        v = values[target]
        out[key] = _score_value(f, v) if "_score_" in target else v
    return out


def _field_key(f: dict) -> str:
    return f.get("field_key") or f.get("key") or ""


def _required(f: dict) -> bool:
    """平台 schema 里必填标记叫 is_required；`required` 只是兼容早期字段名。"""
    return bool(f.get("is_required", f.get("required", False)))


def enabled_fields(schema: dict) -> list[dict]:
    """后台可以停用字段，停用的不填也不校验。"""
    return [f for f in (schema.get("fields") or [])
            if _field_key(f) and f.get("is_enabled", True)]


def is_attachment(f: dict) -> bool:
    """附件字段的值是对象数组，其余字段都是字符串。录屏是 video 类型，存的是 URL 字符串。"""
    return f.get("field_type") in ("attachment", "file")


def missing_required(schema: dict, values: dict) -> list[str]:
    """schema 说必填、而我们没值的字段。附件字段单独处理，不在这里查。"""
    return [k for f in enabled_fields(schema)
            if _required(f) and not is_attachment(f)
            and not str(values.get(k := _field_key(f)) or "").strip()]


def unknown_required(schema: dict, values: dict) -> list[str]:
    """schema 要求必填、但映射表里根本没有的字段。

    平台后台加了新必填项时会走到这里。不猜值：猜错了这一单会被判无效，
    而报出字段名人工补一下只要一分钟。
    """
    known = set(values) | {f"{s.lower()}_trace_file" for s in config.SIDES}
    return [_field_key(f) for f in enabled_fields(schema)
            if _required(f) and _field_key(f) not in known]


def too_long(schema: dict, values: dict) -> dict[str, str]:
    """超出 schema 的 max_length 的字段。理由写太长会被 422 打回，提交前先自己量一遍。"""
    out = {}
    for f in enabled_fields(schema):
        limit = f.get("max_length") or 0
        v = str(values.get(_field_key(f)) or "")
        if limit and len(v) > limit:
            out[_field_key(f)] = f"{len(v)} 字，超出上限 {limit} 字"
    return out


async def _upload_file(c: httpx.AsyncClient, path: Path, kind: str = "") -> dict:
    data = {"kind": kind} if kind else None
    with path.open("rb") as fp:
        r = await c.post(f"{API}/submissions/upload",
                         files={"file": (path.name, fp, "application/octet-stream")},
                         data=data)
    if r.status_code != 200:
        raise RuntimeError(f"上传 {path.name} 失败 HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi")


def ingest_screencast(task_no: str, side: str, src: Path) -> Path:
    """把外部录好的视频收进这道题自己的目录，返回归档后的路径。

    录屏是在宿主机上录完之后贴过来的，路径五花八门：桌面、下载目录、某个临时文件夹。
    原地传也能传，但那份文件随时会被人清掉或改名，而重传（第一次被平台拒了、或者
    链接过期）要的就是同一个文件。收进题目目录之后，这道题的产物、轨迹、录屏在一个
    地方，人要回头找也只用看一个目录。

    文件名按题号和侧别定死，不沿用原名。原名通常是录屏软件给的时间戳，两侧摆在一起
    分不出哪个是哪个；而定死之后重录会直接覆盖上一份，不会在目录里堆出一串看不出
    新旧的文件。

    同一个文件重复收（人把已经归档过的路径又贴了一次）直接返回，不做无谓的拷贝。
    """
    dst = config.TaskPaths(task_no).analysis / f"screencast-{task_no}-{side.upper()}{src.suffix.lower()}"
    if dst.exists() and src.resolve() == dst.resolve():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 拷贝而不是移动：源文件多半还在人的桌面上，他可能要自己留一份或者再看一遍。
    # 录屏就几十上百兆，多存一份不值得为此冒「文件被搬走了找不到」的险。
    shutil.copy2(src, dst)
    return dst


async def upload_screencast(task_id: int, side: str, path: Path) -> dict:
    """收下本地录屏文件、代传到平台，把返回的 URL 记进题目。"""
    if not path.exists():
        return {"ok": False, "message": f"文件不存在：{path}"}
    if path.suffix.lower() not in VIDEO_SUFFIXES:
        # 早拦一道。传上去平台才回一句格式不对的话，一个几百兆的文件已经上行完了。
        return {"ok": False,
                "message": f"{path.name} 不像是视频文件（认 {'、'.join(VIDEO_SUFFIXES)}）"}
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        task_no = task.task_no
    try:
        kept = await asyncio.to_thread(ingest_screencast, task_no, side, path)
    except OSError as exc:
        return {"ok": False, "message": f"归档录屏失败：{exc}"}
    try:
        async with _client() as c:
            ref = await _upload_file(c, kept, kind="video")
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
        # 和界面上手填链接走同一条路。录屏不再决定题落在哪一栏（那由质检决定），
        # 但它决定提交门禁开不开，所以仍然要过一遍阶段投影把状态对齐。
        gsb_precheck.sync_stage(db, task)
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "url": url, "path": str(kept),
            "message": f"{side} 侧录屏已收下并上传"}


async def deliver_screencasts(task_id: int, paths: dict[str, str],
                              *, submit: bool = True) -> dict:
    """交付录屏：两侧一起收下、代传，齐了就直接提交。

    这是「我只提供录屏文件」那条路的落点。分侧调三次接口也能做到同样的事，但录屏是
    整条流水线上最后一个人工动作，让它一次做完，人贴完路径就不用再管了。

    提交只在两侧都齐了的时候发。缺一侧就发出去，平台会以「字段缺失」回绝，而那句话
    在这里提前说更清楚。
    """
    results: dict[str, dict] = {}
    for side in config.SIDES:
        src = str(paths.get(side) or "").strip()
        if not src:
            continue
        results[side] = await upload_screencast(task_id, side, Path(src).expanduser())

    failed = [f"{s}：{r['message']}" for s, r in results.items() if not r["ok"]]
    if failed:
        return {"ok": False, "uploaded": results, "submitted": None,
                "message": "；".join(failed)}

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "uploaded": results, "submitted": None,
                    "message": "题目不存在"}
        blocked = gsb_precheck.submit_block(task)

    done = f"收下并上传了 {'、'.join(sorted(results)) or '零'} 侧的录屏"
    if not submit:
        return {"ok": True, "uploaded": results, "submitted": None, "message": done}
    if blocked:
        return {"ok": True, "uploaded": results, "submitted": None,
                "message": f"{done}，但还不能提交：{blocked}"}
    submitted = await upload_task(task_id)
    return {"ok": submitted["ok"], "uploaded": results, "submitted": submitted,
            "message": f"{done}；{submitted['message']}"}


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
        # 状态、提交前质检与结论新鲜度三件事合在 submit_block 里判，界面上按钮灰不灰
        # 照的是同一个函数。两边各写一套的下场是按钮亮着、点下去被回绝，而回绝的理由
        # 跟按钮的提示还不一样。
        if blocked := gsb_precheck.submit_block(task):
            return {"ok": False, "message": blocked}
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

    # 最后一道：拿马上要交出去的这两份轨迹，对马上要交出去的这段理由按侧再核一遍。
    # 前面几道的结论都是存下来的，中间理由被人手改过、轨迹被重跑换过，都可能让那份
    # 结论和这一刻交出去的东西对不上；而串侧一旦交上去，平台的锚点核验必然打回。
    if left := gsb_attribution.hard(values.get("gsb_reason") or "",
                                    gsb_attribution.corpora_from_files(traces)):
        detail = "；".join(f"「{h['quote'][:50]}」{h['why']}" for h in left[:3])
        return {"ok": False, "message": f"理由里有 {len(left)} 处与对应那一侧的轨迹对不上：{detail}"}

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
            values = resolve_fields(schema, values)

            if unknown := unknown_required(schema, values):
                return _fail(task_id, record,
                             f"平台新增了必填字段，本地没有对应来源，请人工确认：{', '.join(unknown)}",
                             fields={k: "本地无此字段" for k in unknown})
            if missing := missing_required(schema, values):
                human = {"a_screencast": "A 侧录屏链接", "b_screencast": "B 侧录屏链接"}
                names = [human.get(k, k) for k in missing]
                return _fail(task_id, record, f"字段缺失：{', '.join(names)}",
                             fields={k: "缺值" for k in missing})
            if over := too_long(schema, values):
                return _fail(task_id, record,
                             f"字段超长：{', '.join(f'{k} {v}' for k, v in over.items())}",
                             fields=over)

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
