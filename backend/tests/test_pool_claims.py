"""远端题库的领取归属：仲裁规则与抢占流程。

这一层错了的后果是两台设备同时做同一道题 —— 两边各烧掉两个容器的机器时间，跑完才在
上传时撞车。而且它不会报错：双方都会看到自己领取成功。所以每条规则都得钉住。

git 那部分（clone / pull / push）不在这里测，本地没有远端可打；这些用例把 sync 与
commit_push 换成假的，专测「拿到什么样的文件内容，就该得出什么样的归属」。
"""

from __future__ import annotations

import json

import pytest

from app import config
from app.services import pool, settings_store


@pytest.fixture()
def pooled(tmp_path, tmp_db, monkeypatch):
    """池指到临时目录，本机叫 mac。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    settings_store.set_many({"pool.enabled": "1", "pool.repo": "me/pool",
                             "pool.device": "mac", "gh.token": "t"})
    return tmp_path / "pool"


@pytest.fixture()
def offline(monkeypatch):
    """把远端换成本地文件：sync 什么都不做，push 直接算成功。

    这样 claim_remote 的三步（拉最新 → 写一行并推 → 推完重新核对）全都落在本地
    claims.jsonl 上，正好能模拟「另一台设备的记录已经合并进来了」。
    """
    async def fake_sync():
        return {"ok": True, "message": "", "count": 0}

    async def fake_push(subject, *, done, attempts=3):
        return {"ok": True, "message": done}

    monkeypatch.setattr(pool, "sync", fake_sync)
    monkeypatch.setattr(pool, "commit_push", fake_push)


def _write_claims(rows: list[dict]) -> None:
    pool._write_scaffold()
    with pool.claims_path().open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _claim(device: str, at: str, action: str = pool.ACTION_CLAIM, entry_id: str = "e1") -> dict:
    return {"entry_id": entry_id, "device": device, "action": action, "at": at, "task_no": "01"}


# ---------------- 仲裁 ----------------

def test_the_earlier_claim_wins(pooled):
    """两台设备几乎同时领同一道题，按时间戳判，先发的赢。

    不能按「谁先 push」判：merge=union 会把两行都留下，而后 push 的那台设备自己也会
    看到推送成功。只有内容里的时间戳是两边都能读到的同一个事实。
    """
    _write_claims([_claim("win", "2026-09-19T02:00:01+00:00"),
                   _claim("mac", "2026-09-19T02:00:00+00:00")])
    assert pool.owners() == {"e1": "mac"}


def test_owner_does_not_depend_on_line_order(pooled):
    """union 合并出来的行序两台设备未必一致，归属却必须一致。"""
    rows = [_claim("mac", "2026-09-19T02:00:00+00:00"),
            _claim("win", "2026-09-19T02:00:01+00:00")]
    _write_claims(rows)
    first = pool.owners()

    pool.claims_path().write_text("", encoding="utf-8")
    _write_claims(list(reversed(rows)))
    assert pool.owners() == first


def test_a_later_claim_cannot_steal_a_held_question(pooled):
    """有主之后别人再写一行 claim 也不作数，否则回写机制形同虚设。"""
    _write_claims([_claim("mac", "2026-09-19T02:00:00+00:00"),
                   _claim("win", "2026-09-19T03:00:00+00:00")])
    assert pool.owners() == {"e1": "mac"}


def test_release_frees_the_question(pooled):
    _write_claims([_claim("mac", "2026-09-19T02:00:00+00:00"),
                   _claim("mac", "2026-09-19T03:00:00+00:00", pool.ACTION_RELEASE)])
    assert pool.owners() == {}


def test_only_the_holder_can_release(pooled):
    """别的设备发的释放不作数：否则一台机器就能把另一台正在做的题抢过来。"""
    _write_claims([_claim("mac", "2026-09-19T02:00:00+00:00"),
                   _claim("win", "2026-09-19T03:00:00+00:00", pool.ACTION_RELEASE)])
    assert pool.owners() == {"e1": "mac"}


def test_a_released_question_can_be_claimed_again(pooled):
    """放回题库的题要能被另一台设备领走，不然「放回」只是本机的自我安慰。"""
    _write_claims([_claim("mac", "2026-09-19T02:00:00+00:00"),
                   _claim("mac", "2026-09-19T03:00:00+00:00", pool.ACTION_RELEASE),
                   _claim("win", "2026-09-19T04:00:00+00:00")])
    assert pool.owners() == {"e1": "win"}


def test_duplicate_claim_lines_are_harmless(pooled):
    """union 会留下重复行。同一台设备的同一次领取重放几遍，结论不能变。"""
    row = _claim("mac", "2026-09-19T02:00:00+00:00")
    _write_claims([row, row, row])
    assert pool.owners() == {"e1": "mac"}


def test_claims_from_different_questions_do_not_mix(pooled):
    _write_claims([_claim("mac", "2026-09-19T02:00:00+00:00", entry_id="e1"),
                   _claim("win", "2026-09-19T02:00:00+00:00", entry_id="e2")])
    assert pool.owners() == {"e1": "mac", "e2": "win"}


def test_owners_survives_a_broken_line(pooled):
    """推送被中断可能留下半行。一行坏掉不能让整份归属读不出来 —— 那等于独占静默失效。"""
    pool._write_scaffold()
    with pool.claims_path().open("a", encoding="utf-8") as fh:
        fh.write('{"entry_id": "半行", "device": "被截断\n')
        fh.write(json.dumps(_claim("mac", "2026-09-19T02:00:00+00:00"), ensure_ascii=False) + "\n")
    assert pool.owners() == {"e1": "mac"}


# ---------------- 抢占流程 ----------------

@pytest.mark.asyncio
async def test_claim_remote_registers_the_holder(pooled, offline):
    res = await pool.claim_remote("e1", task_no="01")
    assert res["ok"], res
    assert pool.owners() == {"e1": "mac"}


@pytest.mark.asyncio
async def test_claim_remote_refuses_a_question_someone_else_holds(pooled, offline):
    """领之前先看一眼远端，已经有主就别再往下走 —— 后面是几十秒的 clone。"""
    _write_claims([_claim("win", "2026-09-19T02:00:00+00:00")])
    res = await pool.claim_remote("e1", task_no="01")
    assert not res["ok"]
    assert res["taken_by"] == "win"


@pytest.mark.asyncio
async def test_claim_remote_loses_to_an_earlier_claim_that_arrives_with_the_pull(pooled, monkeypatch):
    """推成功也不等于领到了。

    这是整套机制里最容易漏的一步：push 成功只说明这一行进了远端，而 union 会把对方那行
    一起留下，谁赢由时间戳判。少了推完再核对这一下，两台设备会各自看到自己成功，然后
    双双开工 —— 而远端文件里写得清清楚楚只有一个赢家。
    """
    pushed: list[str] = []

    async def fake_sync():
        # 第二次 sync（推完那次）才把对方的那行带进来，模拟并发。时间取得远早于此刻，
        # 好让它稳定地排在本机这次领取之前
        if pushed:
            _write_claims([_claim("win", "2020-01-01T00:00:00+00:00")])
        return {"ok": True, "message": "", "count": 0}

    async def fake_push(subject, *, done, attempts=3):
        pushed.append(subject)
        return {"ok": True, "message": done}

    monkeypatch.setattr(pool, "sync", fake_sync)
    monkeypatch.setattr(pool, "commit_push", fake_push)

    res = await pool.claim_remote("e1", task_no="01")
    assert not res["ok"]
    assert res["taken_by"] == "win"


@pytest.mark.asyncio
async def test_a_claim_that_cannot_be_pushed_is_rolled_back(pooled, monkeypatch):
    """推不上去就不算领到。

    本地留着那行的话，本机以为自己占着题，而远端不知情、另一台设备照领不误 ——
    正是回写要防的重复领取，只是方向反了。
    """
    async def fake_sync():
        return {"ok": True, "message": "", "count": 0}

    async def fake_push(subject, *, done, attempts=3):
        return {"ok": False, "message": "推送题库失败：网络不通"}

    monkeypatch.setattr(pool, "sync", fake_sync)
    monkeypatch.setattr(pool, "commit_push", fake_push)

    res = await pool.claim_remote("e1", task_no="01")
    assert not res["ok"]
    assert pool.owners() == {}
    assert pool.load_claims() == []


@pytest.mark.asyncio
async def test_claim_remote_is_reentrant_for_the_same_device(pooled, offline):
    """门禁没过的题会停在已领取，人修好后再点一次。第二次不能被自己的第一次挡住。"""
    assert (await pool.claim_remote("e1", task_no="01"))["ok"]
    again = await pool.claim_remote("e1", task_no="01")
    assert again["ok"] and again["already"]


@pytest.mark.asyncio
async def test_claim_is_skipped_when_the_pool_is_off(pooled, offline):
    """单设备模式下没有第二台机器，独占无从谈起，不能因此拦住领取。"""
    settings_store.set_many({"pool.enabled": "0"})
    res = await pool.claim_remote("e1", task_no="01")
    assert res["ok"] and res["skipped"]


@pytest.mark.asyncio
async def test_claim_refuses_when_the_remote_is_unreachable(pooled, monkeypatch):
    """拉不到远端就不能盲领：断网恰恰是两边最容易撞在一起的时候。"""
    async def fake_sync():
        return {"ok": False, "message": "连不上 github", "count": 0}

    monkeypatch.setattr(pool, "sync", fake_sync)
    res = await pool.claim_remote("e1", task_no="01")
    assert not res["ok"] and not res.get("taken_by")


@pytest.mark.asyncio
async def test_claim_refuses_a_stale_local_copy(pooled, monkeypatch):
    """`sync` 返回 ok=True + stale 是「拉失败了，手上这份是旧的」。

    查重时旧副本顶一顶无非漏查一批，领取不行 —— 归属就记在远端，读旧副本等于没问过，
    两台设备会双双认为这题没人领。线上真出过一次：pull 少传了工作目录，在后端容器的
    cwd 里跑 git，每次都失败回退到本地副本，而日志只是一行 WARNING。
    """
    async def fake_sync():
        return {"ok": True, "message": "拉取失败，暂用本地副本", "count": 0, "stale": True}

    monkeypatch.setattr(pool, "sync", fake_sync)
    res = await pool.claim_remote("e1", task_no="01")
    assert not res["ok"] and not res.get("taken_by")
    assert pool.load_claims() == []


@pytest.mark.asyncio
async def test_release_remote_only_works_for_the_holder(pooled, offline):
    _write_claims([_claim("win", "2026-09-19T02:00:00+00:00")])
    res = await pool.release_remote("e1", task_no="01")
    assert not res["ok"]
    assert pool.owners() == {"e1": "win"}


@pytest.mark.asyncio
async def test_release_remote_hands_the_question_back(pooled, offline):
    await pool.claim_remote("e1", task_no="01")
    res = await pool.release_remote("e1", task_no="01")
    assert res["ok"], res
    assert pool.owners() == {}
