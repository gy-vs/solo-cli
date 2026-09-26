"""录屏协作：事件折叠、READY 投影、文档生成的边角、录屏仓库的真实 git 往返、巡检编排。"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from app import config
from app import models as m
from app.services import gsb_precheck as gp
from app.services import rec_repo, rec_report, recording
from app.services.gsb_factcheck import ATTRIBUTION_VERSION

REASON = "A 侧把超限判定放在解析入口，越界时返回的错误里带着是步数超了还是深度超了，B 侧没有区分。"


def _ev(kind, at, by="rec1", owner="dev1", no="101", **kw):
    return {"type": kind, "owner": owner, "task_no": no, "by": by, "at": at, **kw}


def _settled(t: m.Task, reason: str = REASON) -> None:
    t.gsb = {"verdict": "A", "reason": reason}
    t.factcheck_status = m.FACTCHECK_PASS
    t.factcheck = {"reason_digest": gp.reason_digest(reason), "attribution_version": ATTRIBUTION_VERSION}
    t.precheck_status = m.PRECHECK_PASS
    t.precheck = {"passed": True, "reason_digest": gp.reason_digest(reason)}


# ---------------- 事件折叠 ----------------

def test_fold_walks_the_happy_path():
    evs = [_ev("published", "1", by="dev1", digest="d1"), _ev("claimed", "2", digest="d1"),
           _ev("recorded", "3", digest="d1", files={"A": "A.mp4", "B": "B.mp4"}),
           _ev("collected", "4", by="dev1", digest="d1")]
    e = rec_repo.fold(evs)["dev1/101"]
    assert e.state == rec_repo.S_COLLECTED and e.claimed_by == "rec1" and e.recorded_by == "rec1"


def test_fold_is_order_independent_after_union_merge():
    """merge=union 之后行序不保证，结论只能看时间戳。"""
    evs = [_ev("claimed", "2", digest="d1"), _ev("published", "1", by="dev1", digest="d1")]
    assert rec_repo.fold(evs)["dev1/101"].state == rec_repo.S_CLAIMED
    assert rec_repo.fold(list(reversed(evs)))["dev1/101"].state == rec_repo.S_CLAIMED


def test_first_claim_wins():
    evs = [_ev("published", "1", by="dev1", digest="d1"),
           _ev("claimed", "3", by="rec2", digest="d1"), _ev("claimed", "2", by="rec1", digest="d1")]
    assert rec_repo.fold(evs)["dev1/101"].claimed_by == "rec1"


def test_someone_else_cannot_record_or_release_a_claimed_task():
    evs = [_ev("published", "1", by="dev1", digest="d1"), _ev("claimed", "2", by="rec1", digest="d1"),
           _ev("released", "3", by="rec2", digest="d1"), _ev("recorded", "4", by="rec2", digest="d1")]
    e = rec_repo.fold(evs)["dev1/101"]
    assert e.state == rec_repo.S_CLAIMED and e.claimed_by == "rec1"


def test_republish_starts_a_new_round_and_old_videos_do_not_count():
    """理由改过重新发布，按旧稿录的视频不能收。"""
    evs = [_ev("published", "1", by="dev1", digest="d1"), _ev("claimed", "2", digest="d1"),
           _ev("published", "3", by="dev1", digest="d2"), _ev("recorded", "4", digest="d1")]
    e = rec_repo.fold(evs)["dev1/101"]
    assert e.state == rec_repo.S_OPEN and e.digest == "d2" and not e.claimed_by


def test_withdrawn_closes_the_round():
    evs = [_ev("published", "1", by="dev1", digest="d1"), _ev("withdrawn", "2", by="dev1"),
           _ev("claimed", "3", digest="d1")]
    assert rec_repo.fold(evs)["dev1/101"].state == rec_repo.S_WITHDRAWN


def test_release_puts_it_back_in_the_queue():
    evs = [_ev("published", "1", by="dev1", digest="d1"), _ev("claimed", "2", digest="d1"),
           _ev("released", "3", digest="d1"), _ev("claimed", "4", by="rec2", digest="d1")]
    assert rec_repo.fold(evs)["dev1/101"].claimed_by == "rec2"


# ---------------- READY 投影 ----------------

def test_qc_with_both_screencasts_moves_on_to_ready(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="101", prompt_hash="h", user_prompt="x", status=m.QC)
        _settled(t)
        t.screencast = {"A": "u1", "B": "u2"}
        db.add(t)
        db.flush()
        assert gp.sync_stage(db, t) is True and t.status == m.READY
        assert "当前状态" not in gp.submit_block(t)


def test_ready_falls_straight_back_to_analyzed_when_reason_is_edited(tmp_db):
    """录屏链接留着，重新放行之后一步回到 READY。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no="101", prompt_hash="h", user_prompt="x", status=m.READY)
        _settled(t)
        t.gsb = {"verdict": "A", "reason": REASON + "补一句。"}
        t.screencast = {"A": "u1", "B": "u2"}
        db.add(t)
        db.flush()
        assert gp.sync_stage(db, t) is True and t.status == m.ANALYZED
        _settled(t, REASON + "补一句。")
        assert gp.sync_stage(db, t) is True and t.status == m.READY


def test_ready_without_screencast_goes_back_to_qc(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="101", prompt_hash="h", user_prompt="x", status=m.READY)
        _settled(t)
        t.screencast = {"A": "u1"}
        db.add(t)
        db.flush()
        assert gp.sync_stage(db, t) is True and t.status == m.QC


# ---------------- 文档生成 ----------------

def test_extract_fragment_strips_fences_and_preamble():
    raw = "好的，片段如下：\n```markdown\n## 第 101 题　特性开发　·　中等　·　纯后端\n\n仓库：x\n```"
    assert rec_report.extract_fragment(raw, "101").startswith("## 第 101 题")
    with pytest.raises(rec_report.ReportError):
        rec_report.extract_fragment("我不知道", "101")


def test_render_prepends_the_skill_marker():
    md = rec_report.render("## 第 101 题　a　·　b\n", task_no="101", owner="dev1", digest="abc")
    assert md.startswith("<!-- solo-report:task=101 ") and "digest=abc" in md


def test_verify_wrapper_translates_docker_mounts_to_host_paths(tmp_path, monkeypatch):
    """verify_ps 挂的是容器内路径，宿主 daemon 找不到；包装器要把它们翻成宿主路径。"""
    skills = tmp_path / "skills"
    scripts = skills / "solo-report" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "verify_ps.py").write_text(
        "import pathlib, subprocess, sys, tempfile\n"
        "w = tempfile.mkdtemp(prefix='solo-report-ps-')\n"
        "here = pathlib.Path(__file__).resolve().parent\n"
        "r = subprocess.run(['docker', 'run', '--rm', '-v', f'{w}:/work:ro', '-v', f'{here}:/check:ro', 'img'],"
        " capture_output=True, text=True)\n"
        "print(r.stdout)\n"
        "print('结论：全部通过')\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\necho \"ARGS $*\"\n", encoding="utf-8")
    (fake_bin / "docker").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(config, "SKILL_DIR_MOUNT", skills)
    monkeypatch.setattr(config, "SKILL_DIR_HOST", "/HOST/skills")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "DATA_DIR_HOST", "/HOST/data")

    ok, out = asyncio.run(rec_report.verify("## 第 101 题\n"))
    assert ok, out
    assert "-v /HOST/data/rec/tmp/solo-report-ps-" in out
    assert f"-v /HOST/skills/solo-report/scripts:/check:ro" in out


def test_generate_feeds_verify_errors_back_until_it_passes(tmp_path, monkeypatch):
    from app.services import llm

    for rel in ("SKILL.md", "references/report-template.md", "references/powershell-rules.md",
                "scripts/collect.py", "scripts/verify_ps.py"):
        p = tmp_path / "skills" / "solo-report" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("规则", encoding="utf-8")
    monkeypatch.setattr(config, "SKILL_DIR_MOUNT", tmp_path / "skills")

    async def fake_collect(no):
        return {"task_no": no, "kind_label": "纯后端"}

    prompts = []

    async def fake_ask(prompt, **kw):
        prompts.append(prompt)
        return llm.LlmResult(text=f"## 第 101 题　稿{len(prompts)}\n", model="m", session_id="",
                             usage={}, duration_s=1, attempts=1)

    verdicts = iter([(False, "L3: 含 && 或 ||"), (True, "全部通过")])

    async def fake_verify(fragment):
        return next(verdicts)

    monkeypatch.setattr(rec_report, "collect", fake_collect)
    monkeypatch.setattr(rec_report.llm, "ask", fake_ask)
    monkeypatch.setattr(rec_report, "verify", fake_verify)
    rep = asyncio.run(rec_report.generate("101"))
    assert rep.rounds == 2 and "稿2" in rep.fragment
    assert "含 && 或 ||" in prompts[1] and "稿1" in prompts[1]


# ---------------- 录屏仓库：真实 git 往返 ----------------

def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def local_remote(tmp_db, tmp_path, monkeypatch):
    bare = tmp_path / "remote.git"
    _git("init", "-q", "--bare", "-b", "main", str(bare))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(rec_repo, "_url", lambda: str(bare))
    monkeypatch.setattr(rec_repo, "available", lambda: (True, ""))
    monkeypatch.setattr(rec_repo, "device", lambda: "dev1")

    async def ok(slug):
        return True, ""

    monkeypatch.setattr(rec_repo, "_ensure_remote_repo", ok)
    return bare


def test_repo_round_trip(local_remote, tmp_path):
    async def flow():
        assert (await rec_repo.sync())["ok"]
        pub = await rec_repo.publish_branch("dev1", "101", {"report.md": "# doc\n", "meta.json": "{}"})
        assert pub["ok"] and pub["branch"] == "rec/dev1/101"
        await rec_repo.append([rec_repo.event("published", "dev1", "101", digest="d1")], subject="p")
        assert rec_repo.entries()["dev1/101"].state == rec_repo.S_OPEN

        ok, body = await rec_repo.read_file("dev1", "101", "report.md")
        assert ok and body == "# doc\n"

        video = tmp_path / "A.mp4"
        video.write_bytes(b"\x00video")
        (tmp_path / "B.mp4").write_bytes(b"\x00video-b")
        added = await rec_repo.add_files("dev1", "101", {"A.mp4": video, "B.mp4": tmp_path / "B.mp4"},
                                         subject="rec")
        assert added["ok"], added
        got = await rec_repo.fetch_files("dev1", "101", ["A.mp4", "B.mp4", "report.md"], tmp_path / "out")
        assert got["ok"] and (tmp_path / "out" / "A.mp4").read_bytes() == b"\x00video"

        assert (await rec_repo.delete_branch("dev1", "101"))["ok"]
        ok, why = await rec_repo.read_file("dev1", "101", "report.md")
        assert not ok

    asyncio.run(flow())


def test_append_rebases_over_a_concurrent_push_from_another_device(local_remote, tmp_path):
    """两台设备同时写事件：后推的一方被拒，rebase 之后 union 合并，两行都在。"""
    async def first():
        assert (await rec_repo.sync())["ok"]

    asyncio.run(first())
    other = tmp_path / "other"
    _git("clone", "-q", str(local_remote), str(other))
    with (other / "events.jsonl").open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(_ev("claimed", "2", by="rec2", digest="d1")) + "\n")
    _git("-c", "user.email=x@x", "-c", "user.name=x", "commit", "-qam", "claim", cwd=other)
    _git("push", "-q", "origin", "HEAD:main", cwd=other)

    async def second():
        res = await rec_repo.append([_ev("published", "1", by="dev1", digest="d1")], subject="p")
        assert res["ok"], res
        await rec_repo.sync()
        return rec_repo.entries()["dev1/101"]

    e = asyncio.run(second())
    assert e.state == rec_repo.S_CLAIMED and e.claimed_by == "rec2"


# ---------------- 巡检编排 ----------------

@pytest.fixture()
def stub_repo(tmp_db, monkeypatch):
    state = {"entries": {}, "appended": [], "deleted": [], "started": [], "collected": []}

    async def sync():
        return {"ok": True, "message": ""}

    async def append(events, *, subject, attempts=3):
        state["appended"].extend(events)
        return {"ok": True, "message": ""}

    async def delete_branch(owner, no):
        state["deleted"].append(no)
        return {"ok": True}

    monkeypatch.setattr(rec_repo, "available", lambda: (True, ""))
    monkeypatch.setattr(rec_repo, "recorder_only", lambda: False)
    monkeypatch.setattr(rec_repo, "device", lambda: "dev1")
    monkeypatch.setattr(rec_repo, "sync", sync)
    monkeypatch.setattr(rec_repo, "append", append)
    monkeypatch.setattr(rec_repo, "delete_branch", delete_branch)
    monkeypatch.setattr(rec_repo, "entries", lambda: state["entries"])
    monkeypatch.setattr(recording, "start_generate",
                        lambda tid, force=False: state["started"].append(tid) or {"ok": True})
    monkeypatch.setattr(recording, "_start_collect", lambda tid, e: state["collected"].append(tid))
    monkeypatch.setattr(recording.settings_store, "get_bool", lambda k, d=False: d)
    return state


def _add(no, status, **kw):
    from app.db import session

    with session() as db:
        t = m.Task(task_no=no, prompt_hash=f"h{no}", user_prompt="x", status=status)
        _settled(t)
        for k, v in kw.items():
            setattr(t, k, v)
        db.add(t)
        db.flush()
        return t.id


def _entry(no, state, digest=None, **kw):
    return rec_repo.Entry(owner="dev1", task_no=no, state=state,
                          digest=digest if digest is not None else gp.reason_digest(REASON), **kw)


def test_scan_queues_generation_for_new_qc_tasks(stub_repo):
    tid = _add("101", m.QC)
    _add("102", m.ANALYZED)
    asyncio.run(recording.scan())
    assert stub_repo["started"] == [tid]


def test_scan_skips_tasks_whose_document_is_current(stub_repo):
    _add("101", m.QC, recording={"state": "published", "digest": gp.reason_digest(REASON)})
    stub_repo["entries"] = {"dev1/101": _entry("101", rec_repo.S_OPEN)}
    asyncio.run(recording.scan())
    assert stub_repo["started"] == [] and stub_repo["appended"] == []


def test_scan_withdraws_when_task_leaves_qc(stub_repo):
    _add("101", m.ANALYZED, recording={"state": "published", "digest": gp.reason_digest(REASON)})
    stub_repo["entries"] = {"dev1/101": _entry("101", rec_repo.S_CLAIMED, claimed_by="rec1")}
    asyncio.run(recording.scan())
    assert [e["type"] for e in stub_repo["appended"]] == ["withdrawn"]


def test_scan_withdraws_and_regenerates_when_reason_changed(stub_repo):
    tid = _add("101", m.QC, recording={"state": "published", "digest": "old"})
    stub_repo["entries"] = {"dev1/101": _entry("101", rec_repo.S_OPEN, digest="old")}
    asyncio.run(recording.scan())
    assert [e["type"] for e in stub_repo["appended"]] == ["withdrawn"]
    assert stub_repo["started"] == [tid]


def test_scan_collects_recorded_videos(stub_repo):
    tid = _add("101", m.QC, recording={"state": "published", "digest": gp.reason_digest(REASON)})
    stub_repo["entries"] = {"dev1/101": _entry("101", rec_repo.S_RECORDED, recorded_by="rec1")}
    asyncio.run(recording.scan())
    assert stub_repo["collected"] == [tid] and stub_repo["appended"] == []


def test_scan_deletes_branch_once_task_is_uploaded(stub_repo):
    from app.db import session

    tid = _add("101", m.UPLOADED, recording={"state": "collected", "digest": gp.reason_digest(REASON)})
    stub_repo["entries"] = {"dev1/101": _entry("101", rec_repo.S_COLLECTED)}
    asyncio.run(recording.scan())
    asyncio.run(recording.scan())
    assert stub_repo["deleted"] == ["101"]
    with session() as db:
        assert db.get(m.Task, tid).recording["branch_deleted"] is True


def test_collect_uploads_both_sides_and_task_becomes_ready(stub_repo, monkeypatch):
    from app.db import session

    tid = _add("101", m.QC, recording={"state": "published", "digest": gp.reason_digest(REASON)})

    async def fetch_files(owner, no, names, into):
        into.mkdir(parents=True, exist_ok=True)
        for n in names:
            (into / n).write_bytes(b"v")
        return {"ok": True, "files": {}, "missing": [], "message": ""}

    async def upload(task_id, side, path):
        assert path.is_file()
        with session() as db:
            t = db.get(m.Task, task_id)
            t.screencast = {**t.screencast, side: f"https://cdn/{side}"}
            gp.sync_stage(db, t)
        return {"ok": True, "message": ""}

    monkeypatch.setattr(rec_repo, "fetch_files", fetch_files)
    monkeypatch.setattr(rec_repo, "scratch_dir", lambda: Path(os.environ.get("TMPDIR", "/tmp")))
    monkeypatch.setattr(recording.gsb_uploader, "upload_screencast", upload)
    entry = _entry("101", rec_repo.S_RECORDED, recorded_by="rec1")
    asyncio.run(recording._collect(tid, entry))
    with session() as db:
        t = db.get(m.Task, tid)
        assert t.status == m.READY and t.recording["state"] == "collected"
    assert [e["type"] for e in stub_repo["appended"]] == ["collected"]


def test_claim_reports_when_someone_else_got_there_first(stub_repo, monkeypatch):
    seq = iter([{"dev1/101": _entry("101", rec_repo.S_OPEN)},
                {"dev1/101": _entry("101", rec_repo.S_CLAIMED, claimed_by="rec2")}])
    current = {}

    def entries():
        return current

    async def sync():
        current.clear()
        current.update(next(seq, current))
        return {"ok": True, "message": ""}

    monkeypatch.setattr(rec_repo, "entries", entries)
    monkeypatch.setattr(rec_repo, "sync", sync)
    res = asyncio.run(recording.claim("dev1/101"))
    assert not res["ok"] and "rec2" in res["message"]
    assert [e["type"] for e in stub_repo["appended"]] == ["claimed"]
