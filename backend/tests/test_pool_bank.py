"""远端题库投影成本机题目表。

这一步决定界面上「能领哪些题」。投影少了，本机看不到别的设备出的题，跨设备协作就没了；
投影多了（把别人领走的题也摆出来），人点下去才发现领不了，而那时远端已经被问过一轮。

题号改写也在这里测。两台设备各自从 01 开始编号，而题号会拼成工作区目录名和容器名，
撞号的后果是两道不同的题共用一个工作区 —— 界面上看不出任何异常。
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app import config
from app.db import session
from app.models import AVAILABLE, CLAIMED, DISCARDED, ORIGIN_POOL, QUEUED, Task
from app.services import pool, pool_bank, settings_store

DRAFT = """题号：{no}

对应项目

仓库：https://github.com/acme/{repo}（本题专属，分支只有 main / A / B）
A 侧：分支 A，本地 /Users/them/coder/workspace/{no}/A，容器 /workspace，轨迹 /Users/them/coder/sessions/{no}/A/
B 侧：分支 B，本地 /Users/them/coder/workspace/{no}/B，容器 /workspace，轨迹 /Users/them/coder/sessions/{no}/B/
来源说明：自行设计。

提交参数

任务类型：0-1 代码生成
任务难度：困难
语言/框架：Rust
Harness：Claude Code
Harness 版本：1.2.3
操作系统：MacOS/Linux
环境可复现等级：完全可复现
初始环境快照：https://github.com/acme/{repo}/commit/{sha}（A、B 两侧共用）

以下为发送给模型的 prompt 正文，A 侧与 B 侧发送同一份，整段复制。

{body}
"""


@pytest.fixture()
def pooled(tmp_path, tmp_db, monkeypatch):
    """池与工作区都指到临时目录，本机叫 mac。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(config, "CODER_ROOT_HOST", str(tmp_path / "coder"))
    settings_store.set_many({"pool.enabled": "1", "pool.repo": "me/pool",
                             "pool.device": "mac", "gh.token": "t"})
    return tmp_path


def _entry(no="01", device="mac", body="做一个带重试的任务队列，要求支持优先级与超时",
           repo="widget", with_draft=True) -> pool.Entry:
    draft = DRAFT.format(no=no, repo=repo, sha="c" * 40, body=body) if with_draft else ""
    return pool.Entry(task_no=no, device=device, repo_name=repo, base_id="自行设计",
                      question_type="0-1 代码生成", difficulty="困难",
                      summary="摘要", snapshot="c" * 40, user_prompt=body, draft=draft)


def _hold(entry: pool.Entry, device: str) -> None:
    pool._write_scaffold()
    with pool.claims_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(pool.Claim(entry_id=entry.id, device=device,
                                       at="2020-01-01T00:00:00+00:00",
                                       task_no=entry.task_no).to_json()) + "\n")


def _tasks() -> list[Task]:
    with session() as db:
        return list(db.execute(select(Task).order_by(Task.task_no)).scalars())


# ---------------- 题号改写 ----------------

def test_another_device_gets_a_suffixed_task_no(pooled):
    """两台设备的 01 题不能都叫 01：题号是工作区目录名和容器名的一部分。"""
    assert pool.local_task_no(_entry(device="mac")) == "01"
    assert pool.local_task_no(_entry(device="mac-air")) == "01-mac-air"


def test_device_name_is_slugged_into_something_docker_accepts(pooled):
    """设备名里的空格、下划线、中文都得抹掉。

    容器名只认 [a-zA-Z0-9_.-]，一个非法字符就让整道题起不来容器，而报错要等到出闸
    那一刻才出现 —— 在此之前 clone、门禁全都正常通过。
    """
    no = pool.local_task_no(_entry(device="我的 Mac Studio_01"))
    assert no == "01-mac-studio-01"
    assert all(c.isalnum() or c in "-_." for c in f"solo-cc-{no}-A")


def test_localize_draft_rewrites_the_task_no_and_paths(pooled):
    text = DRAFT.format(no="01", repo="widget", sha="c" * 40, body="正文 01 提到了 01 这个数字")
    out = pool_bank.localize_draft(text, "01", "01-air")

    assert "题号：01-air" in out
    assert f"{config.CODER_ROOT_HOST}/workspace/01-air/A" in out
    assert f"{config.CODER_ROOT_HOST}/sessions/01-air/B" in out
    assert "/Users/them/coder" not in out
    # 正文里的数字不能被连带改掉：题目内容里出现 01 太常见了
    assert "正文 01 提到了 01 这个数字" in out


# ---------------- 投影 ----------------

def test_a_pool_entry_becomes_a_claimable_task(pooled):
    pool.append([_entry(device="mac-air")])
    res = pool_bank.sync_tasks()

    assert res["added"] == ["01-mac-air"]
    t = _tasks()[0]
    assert t.status == AVAILABLE
    assert t.origin == ORIGIN_POOL
    assert t.pool_device == "mac-air"
    # 领题要 clone 两个分支、要比对 HEAD，这两个值缺一道题就领不了
    assert t.repo_url == "https://github.com/acme/widget"
    assert t.env_snapshot.endswith("c" * 40)


def test_the_draft_is_archived_under_the_local_task_no(pooled):
    """题面落到本机归档目录，人工核对时能直接打开；文件名带设备后缀，
    不是纯数字，所以本地导入那条路径不会把它当成本机题再解析一遍。"""
    pool.append([_entry(device="mac-air")])
    pool_bank.sync_tasks()

    path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / "01-mac-air.md"
    assert path.is_file()
    assert "题号：01-mac-air" in path.read_text(encoding="utf-8")


def test_a_question_someone_else_holds_never_shows_up(pooled):
    """别人领走的题不进本机列表。摆出来只会让人点下去才发现领不了。"""
    e = _entry(device="mac-air")
    pool.append([e])
    _hold(e, "mac-air")

    res = pool_bank.sync_tasks()
    assert res["added"] == []
    assert _tasks() == []


def test_a_question_taken_while_it_sat_in_the_list_gets_removed(pooled):
    """同步前还能领、同步时已被领走 —— 这正是两台设备并行的常态，本机那行要撤掉。"""
    e = _entry(device="mac-air")
    pool.append([e])
    pool_bank.sync_tasks()
    assert len(_tasks()) == 1

    _hold(e, "mac-air")
    res = pool_bank.sync_tasks()
    assert res["removed"] == ["01-mac-air"]
    assert _tasks() == []


def test_a_question_we_are_already_working_on_is_never_removed(pooled):
    """已经动过手的题不能因为一次同步就消失。

    那时本机有工作区、有容器、可能还有轨迹，删掉数据库里这一行并不能把它们收回去，
    只会让这些东西变成没人认领的垃圾，界面上还再也看不到这道题。
    """
    e = _entry(device="mac-air")
    pool.append([e])
    pool_bank.sync_tasks()
    with session() as db:
        db.execute(select(Task)).scalars().one().status = QUEUED

    _hold(e, "mac-air")     # 远端判给了对方，但本机已经在跑了
    res = pool_bank.sync_tasks()
    assert res["removed"] == []
    assert _tasks()[0].status == QUEUED


def test_our_own_claim_keeps_the_question_visible(pooled):
    """本机领的题当然要留着 —— 领取后紧接着就是一次同步。"""
    e = _entry(device="mac")
    pool.append([e])
    _hold(e, "mac")

    pool_bank.sync_tasks()
    assert [t.task_no for t in _tasks()] == ["01"]
    assert _tasks()[0].claimed_by == "mac"


def test_an_entry_without_a_draft_is_not_claimable(pooled):
    """只有 prompt 正文的老条目缺仓库地址与初始快照，建成待领取的题只会在领取那一步才炸。"""
    pool.append([_entry(device="mac-air", with_draft=False)])
    res = pool_bank.sync_tasks()

    assert res["skipped"] == ["01-mac-air"]
    assert _tasks() == []


def test_syncing_twice_does_not_duplicate(pooled):
    pool.append([_entry(device="mac-air")])
    pool_bank.sync_tasks()
    res = pool_bank.sync_tasks()

    assert res["added"] == []
    assert len(_tasks()) == 1


def test_an_existing_local_task_gets_linked_to_its_pool_entry(pooled):
    """本机刚出的题已经在库里了，同步要给它补上远端条目 id。

    不补的话这道题在本机没有远端归属，领取时会绕过跨设备独占 —— 另一台设备同步到之后
    照样能领同一道题，而两边都不会有任何提示。
    """
    e = _entry(device="mac")
    pool.append([e])
    with session() as db:
        db.add(Task(task_no="01", prompt_hash=e.prompt_sha, status=AVAILABLE,
                    user_prompt=e.user_prompt))

    res = pool_bank.sync_tasks()
    assert res["adopted"] == ["01"]
    assert _tasks()[0].pool_entry_id == e.id


def test_a_linked_task_is_found_by_entry_id_not_by_task_no(pooled):
    """认过领的题只按 entry id 找，题号对不上也算同一道。

    池启用之前从题面文件导进来的题用的是原题号 01，而这道题在远端属于别的设备，本机
    口径叫 01-mac-air。只按 (题号, 指纹) 找必然落空，同一道题就会在本机多出一行待领取
    的空壳 —— 而本机跑过的产物、废弃记录全挂在原来那行上，界面上两行并排摆着。
    """
    e = _entry(device="mac-air")
    pool.append([e])
    with session() as db:
        db.add(Task(task_no="01", prompt_hash=e.prompt_sha, status=DISCARDED,
                    user_prompt=e.user_prompt, origin=ORIGIN_POOL,
                    pool_entry_id=e.id, pool_device="mac-air"))

    res = pool_bank.sync_tasks()
    assert res["added"] == []
    assert [t.task_no for t in _tasks()] == ["01"]
    assert _tasks()[0].status == DISCARDED


def test_two_devices_numbering_from_01_coexist(pooled):
    """同号不同题必须并存，而且各有各的工作区。"""
    pool.append([_entry(no="01", device="mac", body="本机的题：实现一个增量构建缓存"),
                 _entry(no="01", device="air", body="那边的题：实现一个分布式限流器")])
    pool_bank.sync_tasks()

    nos = [t.task_no for t in _tasks()]
    assert nos == ["01", "01-air"]
    assert len({config.TaskPaths(n, "A").workspace for n in nos}) == 2


def test_a_claimed_task_keeps_its_local_progress(pooled):
    """远端只管归属，做题进度归本机。同步不能把状态打回待领取。"""
    e = _entry(device="mac")
    pool.append([e])
    pool_bank.sync_tasks()
    with session() as db:
        db.execute(select(Task)).scalars().one().status = CLAIMED
    _hold(e, "mac")

    pool_bank.sync_tasks()
    assert _tasks()[0].status == CLAIMED
