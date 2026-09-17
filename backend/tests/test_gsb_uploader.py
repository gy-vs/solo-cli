"""GSB 提交：字段映射、schema 驱动的必填校验、两份轨迹上传。

HTTP 全部打桩。这里要守住的是「不猜值」：平台加了必填字段时必须停下来报出字段名，
猜一个填进去会让这一单被判无效。
"""

from __future__ import annotations

import asyncio

import pytest

from app import models as m
from app.services import gsb_uploader as up


def _schema(*keys, required=True, fingerprint="fp1"):
    """按平台真实 schema 的形状造：必填标记是 is_required，附件靠 field_type 认。"""
    return {"fingerprint": fingerprint,
            "fields": [{"field_key": k, "is_required": required, "is_enabled": True,
                        "field_type": "attachment" if k.endswith("trace_file")
                        else "video" if k.endswith("screencast") else "text"}
                       for k in keys]}


@pytest.fixture()
def ready_task(tmp_db, tmp_path, monkeypatch):
    """一道分析完、两侧都有产物和轨迹、只差录屏的题。"""
    from app.db import session

    async def version(image):
        return "2.1.200"

    monkeypatch.setattr(up.dockerx, "claude_version", version)
    monkeypatch.setattr(up.settings_store, "get",
                        lambda k: {"cc.image": "img", "gsb.base_url": "https://solo2.example",
                                   "gsb.session_cookie": "ck", "gsb.csrf_token": "cs"}.get(k, ""))
    with session() as db:
        t = m.Task(task_no="07", prompt_hash="h", status=m.ANALYZED,
                   user_prompt="做个解析器", question_type="0-1 代码生成", difficulty="困难",
                   languages="JavaScript", harness_version="2.1.197",
                   repro_level="无外部依赖",
                   repo_url="https://github.com/acme/widget",
                   env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        t.gsb = {"verdict": "A", "reason": "A 侧更好"}
        t.verify = {"overall": "ok"}
        db.add(t)
        db.flush()
        ids = {}
        for side in ("A", "B"):
            f = tmp_path / f"{side}.jsonl"
            f.write_text("{}", encoding="utf-8")
            r = m.TaskRun(task_id=t.id, side=side, status=m.RUN_FINISHED,
                          session_id=f"sess-{side}", image_tag="img",
                          artifact_sha=side.lower() * 40, trace_file=str(f))
            db.add(r)
            db.flush()
            ids[side] = r.id
        return t.id, ids


# ---------------- 字段映射 ----------------

def _values(task_id):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, task_id)
        runs = {r.side: r for r in db.query(m.TaskRun).filter(m.TaskRun.task_id == task_id).all()}
        return asyncio.run(up.build_values(t, runs))


def test_values_normalize_question_type(ready_task):
    task_id, _ = ready_task
    # 题块里写的是「0-1 代码生成」，平台选项没有空格
    assert _values(task_id)["question_type"] == "0-1代码生成"


def test_values_use_measured_harness_version(ready_task):
    """题块里的版本号是出题时写的，镜像更新过就对不上了。"""
    task_id, _ = ready_task
    assert _values(task_id)["harness_version"] == "2.1.200"


def test_values_use_platform_verdict_label(ready_task):
    task_id, _ = ready_task
    assert _values(task_id)["gsb_verdict"] == "A 更好"


def test_values_fill_both_sides(ready_task):
    task_id, _ = ready_task
    v = _values(task_id)
    assert v["a_session_id"] == "sess-A" and v["b_session_id"] == "sess-B"
    assert v["a_artifact_snapshot"].endswith("a" * 40)
    assert v["b_artifact_snapshot"].endswith("b" * 40)


def test_values_take_screencast_from_task(ready_task):
    from app.db import session

    task_id, _ = ready_task
    with session() as db:
        db.get(m.Task, task_id).screencast = {"A": "https://v.example/a", "B": "https://v.example/b"}
    v = _values(task_id)
    assert v["a_screencast"] == "https://v.example/a"


def test_values_fill_fixed_platform_choices(ready_task):
    task_id, _ = ready_task
    v = _values(task_id)
    assert v["harness"] == "Claude Code"
    assert v["os_platform"] == "MacOS/Linux"
    assert v["validity"] == "有效"


# ---------------- schema 驱动的校验 ----------------

def test_missing_required_reports_empty_fields():
    values = {"user_prompt": "x", "a_screencast": "", "b_screencast": ""}
    got = up.missing_required(_schema("user_prompt", "a_screencast", "b_screencast"), values)
    assert got == ["a_screencast", "b_screencast"]


def test_missing_required_ignores_optional_fields():
    assert up.missing_required(_schema("remark", required=False), {"remark": ""}) == []


def test_missing_required_ignores_disabled_fields():
    """后台停用的字段不填也不校验。"""
    schema = {"fields": [{"field_key": "legacy", "is_required": True, "is_enabled": False}]}
    assert up.missing_required(schema, {}) == []
    assert up.unknown_required(schema, {}) == []


def test_missing_required_reads_legacy_required_key():
    """兼容早期只有 required 的字段名，别因为改名把校验整段跳过。"""
    schema = {"fields": [{"field_key": "languages", "required": True}]}
    assert up.missing_required(schema, {"languages": ""}) == ["languages"]


def test_missing_required_skips_trace_attachments():
    """附件是提交时上传的，这一步还没有值，不该算缺失。"""
    schema = _schema("a_trace_file", "b_trace_file")
    assert up.missing_required(schema, {}) == []


def test_unknown_required_reports_new_platform_fields():
    """平台加了必填项时必须报出来，猜一个值填进去会让这一单被判无效。"""
    values = {"user_prompt": "x"}
    assert up.unknown_required(_schema("user_prompt", "brand_new_field"), values) == ["brand_new_field"]


def test_unknown_required_accepts_trace_attachments():
    assert up.unknown_required(_schema("a_trace_file", "b_trace_file"), {}) == []


def test_unknown_required_ignores_optional_unknown():
    assert up.unknown_required(_schema("whatever", required=False), {}) == []


def test_too_long_flags_over_max_length():
    """理由超长会被平台 422 打回，提交前先自己量一遍。"""
    schema = {"fields": [{"field_key": "gsb_reason", "is_required": True,
                          "is_enabled": True, "max_length": 10}]}
    assert "gsb_reason" in up.too_long(schema, {"gsb_reason": "x" * 11})
    assert up.too_long(schema, {"gsb_reason": "x" * 10}) == {}


# ---------------- 提交流程 ----------------

class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeClient:
    """按 (method, path) 回放响应，并记下发出的请求。"""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.posted = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, path):
        self.calls.append(("GET", path))
        return self.routes[("GET", path)]

    async def post(self, path, json=None, files=None, data=None):
        self.calls.append(("POST", path))
        if json is not None:
            self.posted[path] = json
        r = self.routes[("POST", path)]
        return r.pop(0) if isinstance(r, list) else r


@pytest.fixture()
def full_flow(ready_task, monkeypatch):
    from app.db import session

    task_id, ids = ready_task
    with session() as db:
        db.get(m.Task, task_id).screencast = {"A": "https://v.example/a", "B": "https://v.example/b"}

    schema = _schema("user_prompt", "question_type", "difficulty", "languages", "harness",
                     "harness_version", "os_platform", "repro_level", "env_snapshot",
                     "a_session_id", "b_session_id", "a_trace_file", "b_trace_file",
                     "a_artifact_snapshot", "b_artifact_snapshot",
                     "a_screencast", "b_screencast", "gsb_verdict", "gsb_reason", "validity")
    routes = {
        ("GET", "/api/v1/auth/me"): _FakeResponse(200, {"username": "me"}),
        ("GET", "/api/v1/gsb/form-schema"): _FakeResponse(200, schema),
        ("POST", "/api/v1/submissions/upload"): _FakeResponse(
            200, {"name": "t.jsonl", "path": "cos/t.jsonl", "size": 12}),
        ("POST", "/api/v1/gsb/submissions"): _FakeResponse(201, {"id": 4242, "status": "pending"}),
    }
    client = _FakeClient(routes)
    monkeypatch.setattr(up, "_client", lambda: client)
    return task_id, ids, client, routes


def test_upload_posts_both_traces_and_marks_uploaded(full_flow):
    from app.db import session

    task_id, _ids, client, _routes = full_flow
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is True
    assert r["submission_id"] == 4242

    # 两份轨迹各上传一次
    assert client.calls.count(("POST", "/api/v1/submissions/upload")) == 2
    body = client.posted["/api/v1/gsb/submissions"]
    assert body["schema_fingerprint"] == "fp1"
    assert body["data"]["a_trace_file"] == [{"name": "t.jsonl", "path": "cos/t.jsonl", "size": 12}]
    assert body["data"]["b_trace_file"] == [{"name": "t.jsonl", "path": "cos/t.jsonl", "size": 12}]
    assert body["data"]["gsb_verdict"] == "A 更好"

    with session() as db:
        t = db.get(m.Task, task_id)
        assert t.status == m.UPLOADED
        assert t.uploaded_at is not None
        assert t.upload["submission_id"] == 4242


def test_upload_blocked_without_screencast(ready_task, monkeypatch):
    schema = _schema("a_screencast", "b_screencast")
    client = _FakeClient({
        ("GET", "/api/v1/auth/me"): _FakeResponse(200, {"username": "me"}),
        ("GET", "/api/v1/gsb/form-schema"): _FakeResponse(200, schema),
    })
    monkeypatch.setattr(up, "_client", lambda: client)
    task_id, _ = ready_task
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is False
    assert "录屏" in r["message"]
    # 没凑齐就别往平台发东西
    assert ("POST", "/api/v1/submissions/upload") not in client.calls


def test_upload_stops_on_unknown_required_field(ready_task, monkeypatch):
    from app.db import session

    task_id, _ = ready_task
    with session() as db:
        db.get(m.Task, task_id).screencast = {"A": "u", "B": "u"}
    client = _FakeClient({
        ("GET", "/api/v1/auth/me"): _FakeResponse(200, {"username": "me"}),
        ("GET", "/api/v1/gsb/form-schema"): _FakeResponse(200, _schema("brand_new")),
    })
    monkeypatch.setattr(up, "_client", lambda: client)
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is False
    assert "brand_new" in r["message"]


def test_upload_retries_once_on_503(full_flow):
    task_id, _ids, client, routes = full_flow
    routes[("POST", "/api/v1/gsb/submissions")] = [
        _FakeResponse(503, None, "storage busy"),
        _FakeResponse(201, {"id": 7}),
    ]
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is True
    assert client.calls.count(("POST", "/api/v1/gsb/submissions")) == 2


def test_upload_reports_field_errors_on_422(full_flow):
    task_id, _ids, _client, routes = full_flow
    routes[("POST", "/api/v1/gsb/submissions")] = _FakeResponse(
        422, {"detail": "校验未通过", "errors": [{"field": "gsb_reason", "message": "太短"}]})
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is False
    assert r["fields"] == {"gsb_reason": "太短"}


def test_upload_flags_auth_error_on_401(full_flow):
    task_id, _ids, _client, routes = full_flow
    routes[("GET", "/api/v1/auth/me")] = _FakeResponse(401, None, "unauthorized")
    r = asyncio.run(up.upload_task(task_id))
    assert r["auth_error"] is True


def test_upload_refuses_when_verify_blocked(ready_task):
    from app.db import session

    task_id, _ = ready_task
    with session() as db:
        db.get(m.Task, task_id).verify = {"overall": "block"}
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is False and "红项" in r["message"]


def test_upload_refuses_before_analysis(ready_task):
    from app.db import session

    task_id, _ = ready_task
    with session() as db:
        db.get(m.Task, task_id).status = m.RUN_DONE
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is False and "不允许上传" in r["message"]


def test_upload_refuses_when_a_trace_missing(ready_task):
    from app.db import session

    task_id, ids = ready_task
    with session() as db:
        db.get(m.TaskRun, ids["B"]).trace_file = ""
    r = asyncio.run(up.upload_task(task_id))
    assert r["ok"] is False and "B 侧的轨迹文件缺失" in r["message"]


def test_screencast_upload_records_returned_url(ready_task, monkeypatch, tmp_path):
    from app.db import session

    task_id, _ = ready_task
    video = tmp_path / "a.mp4"
    video.write_bytes(b"x")
    client = _FakeClient({("POST", "/api/v1/submissions/upload"):
                          _FakeResponse(200, {"url": "https://v.example/uploaded", "name": "a.mp4"})})
    monkeypatch.setattr(up, "_client", lambda: client)

    r = asyncio.run(up.upload_screencast(task_id, "A", video))
    assert r["ok"] is True
    with session() as db:
        assert db.get(m.Task, task_id).screencast["A"] == "https://v.example/uploaded"
