"""跨设备查重池：条目身份、字面查重、索引投影。

这层要兜住的是 solo-qa 查不到的那一段 —— 两台设备各自本地出的新题在提交到平台之前
对彼此不可见。所以这里的判定错了不会立刻报错，只会让两边出重题，等机器时间烧完了
才在平台判重时发现，因此每条规则都值得钉住。

不测 git 同步：那部分是对 gh / git 的编排，本地没有远端可打，留给实际调用。
"""

from __future__ import annotations

import json

import pytest

from app import config
from app.services import pool, settings_store


@pytest.fixture()
def pooled(tmp_path, tmp_db, monkeypatch):
    """把池指到临时目录，并配好一台叫 mac 的设备。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    settings_store.set_many({"pool.enabled": "1", "pool.repo": "me/pool",
                             "pool.device": "mac", "gh.token": "t"})
    return tmp_path / "pool" / "pool.jsonl"


def _entry(**kw) -> pool.Entry:
    base = {"task_no": "01", "device": "mac", "repo_name": "r", "base_id": "自行设计",
            "question_type": "功能实现", "difficulty": "困难", "summary": "摘要",
            "user_prompt": "做一个带重试的任务队列"}
    return pool.Entry(**{**base, **kw})


# ---------------- 条目身份 ----------------

def test_id_includes_the_device(pooled):
    """两台设备各自从 01 开始编号，光靠题号会把两道不同的题看成同一道。"""
    a, b = _entry(device="mac"), _entry(device="win")
    assert a.task_no == b.task_no
    assert a.id != b.id


def test_editing_a_prompt_makes_a_new_row_instead_of_shadowing(pooled):
    """改题面要成为新的一行：池是 append-only 的，两行都在，查重按最像的那行判。"""
    before = _entry()
    after = _entry(user_prompt="做一个带重试和优先级的任务队列")
    assert before.id != after.id

    pool.append([before, after])
    assert len(pool.load()) == 2


def test_load_folds_the_duplicate_lines_union_leaves_behind(pooled):
    """pool.jsonl 是 merge=union：两台设备同时加同一行时合并结果里会留两份。

    不折掉的话，那道题在字面查重里被比两次、在配额统计里被数两次。
    """
    pool.append([_entry()])
    line = pooled.read_text(encoding="utf-8").strip()
    with pooled.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    assert len(pooled.read_text(encoding="utf-8").strip().splitlines()) == 2
    assert len(pool.load()) == 1


def test_load_prefers_the_row_that_carries_the_full_draft(pooled):
    """同一条记录补过题面之后，折叠要留补过的那份。

    题面全文是后加的字段，补的办法是把整行重写一遍追加进去，两行 id 相同。而 union
    合并后的行序不保证，取「先出现的」会让补进去的题面在一部分设备上永远读不到 ——
    那边看到的仍是一道缺仓库地址、领不了的题。
    """
    bare = _entry()
    filled = _entry(draft="题号：01\n\n完整题面")
    assert bare.id == filled.id

    for order in ([bare, filled], [filled, bare]):
        pool._write_scaffold()
        pooled.write_text("", encoding="utf-8")
        with pooled.open("a", encoding="utf-8") as fh:
            for e in order:
                fh.write(json.dumps(e.to_json(), ensure_ascii=False) + "\n")
        loaded = pool.load()
        assert len(loaded) == 1
        assert loaded[0].draft == "题号：01\n\n完整题面"


def test_append_writes_a_readable_copy_of_each_draft(pooled):
    """题面在仓库里另存一份 .md，好在 GitHub 上直接读。按设备分目录，两台设备的
    01 题不会写到同一个文件上。"""
    pool.append([_entry(device="mac", draft="题号：01\n本机"),
                 _entry(device="mac-air", draft="题号：01\n那边")])

    root = pooled.parent / pool.DRAFTS_DIR
    assert (root / "mac" / "01.md").read_text(encoding="utf-8") == "题号：01\n本机"
    assert (root / "mac-air" / "01.md").read_text(encoding="utf-8") == "题号：01\n那边"


def test_append_skips_what_is_already_there(pooled):
    """出题失败重跑一次是常事，同一道题不该在池里堆几份。"""
    assert pool.append([_entry()]) == 1
    assert pool.append([_entry()]) == 0


def test_load_survives_a_broken_line(pooled):
    """push 被中断可能留下半行。一行坏掉不能让整池读不出来 —— 那等于查重静默失效。"""
    pool.append([_entry()])
    with pooled.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "半行", "user_prompt": "被截断了\n')
        fh.write(json.dumps(_entry(task_no="02").to_json(), ensure_ascii=False) + "\n")

    assert {e.task_no for e in pool.load()} == {"01", "02"}


# ---------------- 相似度 ----------------

def test_similarity_ignores_wording_noise(pooled):
    """查的是「同一道题换了措辞」，标点与空白不参与比较。"""
    assert pool.similarity("做一个带重试的任务队列。", "做一个带重试的任务队列") > 0.99


def test_similarity_never_reports_the_upper_bound(pooled):
    """低于 floor 时返回 0，不能返回 quick_ratio。

    quick_ratio 只比字符频次，是真实相似度的**上界**。把它当相似度报出去，
    「用词重合但讲的是两件事」的题会被判成重复 —— 出题会因此白拒一批好题，
    而拒绝理由看上去还挺像真的。
    """
    a = "实现一个支持优先级与重试的分布式任务队列调度器"
    b = "重试优先级队列任务分布式调度支持实现一个与器"   # 同字不同序：上界高，真实低
    assert pool.similarity(a, b, floor=0.45) in (0.0,) or pool.similarity(a, b) < 0.45
    # 关键断言：带 floor 的结果绝不会高于不带 floor 的真实值
    assert pool.similarity(a, b, floor=0.45) <= pool.similarity(a, b)


def test_similarity_handles_empty_text(pooled):
    assert pool.similarity("", "有内容") == 0.0


# ---------------- 字面查重 ----------------

def test_find_duplicates_catches_a_rephrased_pool_entry(pooled):
    """池里已有的题换个说法再出一遍，要被拦下来。"""
    pool.append([_entry(user_prompt="实现一个支持优先级和重试的任务队列调度器，"
                                    "要求处理任务超时与重复投递")])
    hits = pool.find_duplicates([{
        "key": "候选1",
        "user_prompt": "实现一个支持优先级与重试的任务队列调度器，"
                       "需要处理任务超时和重复投递",
    }])
    assert "候选1" in hits
    assert "池内 01@mac" in hits["候选1"]["against"]


def test_find_duplicates_catches_collisions_inside_one_batch(pooled):
    """一次要 10 道，模型自己批内撞车是常事。这时池里还没有任何一条。"""
    text = "实现一个支持优先级与重试的任务队列调度器，处理超时与重复投递"
    hits = pool.find_duplicates([
        {"key": "a", "user_prompt": text},
        {"key": "b", "user_prompt": text + "，并补上指标上报"},
        {"key": "c", "user_prompt": "给命令行工具加一个交互式的配置向导"},
    ])
    assert {"a", "b"} <= set(hits)
    assert "c" not in hits          # 不相干的题不能被连带拦掉
    assert "同批" in hits["a"]["against"]


def test_find_duplicates_leaves_different_questions_alone(pooled):
    """两道题都在讲队列，但一个是调度、一个是可视化，不算重复。

    阈值定在 0.45 就是为了这种情况：背景段落雷同会把相似度顶起来。
    """
    pool.append([_entry(user_prompt="实现一个支持优先级与重试的任务队列调度器")])
    hits = pool.find_duplicates([{
        "key": "候选1",
        "user_prompt": "给任务队列做一个实时看板，展示积压量与失败率的趋势曲线",
    }])
    assert hits == {}


def test_find_duplicates_skips_blank_candidates(pooled):
    assert pool.find_duplicates([{"key": "空", "user_prompt": "   "}]) == {}


def test_threshold_falls_back_when_the_setting_is_junk(pooled):
    """阈值配歪了要退回默认值。取 0 会把所有题判成重复，出题直接全军覆没。"""
    for bad in ("", "abc", "0", "-1", "2"):
        settings_store.set_many({"pool.similarity": bad})
        assert pool._threshold() == pool.DEFAULT_THRESHOLD

    settings_store.set_many({"pool.similarity": "0.6"})
    assert pool._threshold() == 0.6


# ---------------- 索引投影 ----------------

def test_render_index_marks_the_other_device(pooled):
    """skill 读这张表做语义查重。别的设备的题必须标出来：题号两边各自编号，
    不标会被当成本机的题，题面归档路径也会指向一个本机不存在的文件。"""
    pool.append([_entry(task_no="01", device="mac", summary="本机的题"),
                 _entry(task_no="01", device="win", summary="那边的题")])
    text = pool.render_index()

    assert "| 01 |" in text and "本机的题" in text
    assert "01@win" in text and "（另一台设备）" in text
    assert text.startswith(pool.INDEX_HEADER)


def test_write_index_rebuilds_the_whole_table(pooled, monkeypatch):
    """索引由池整表重建，不是追加：池是唯一真相源，两边各记一份就会对不上。"""
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", pooled.parent.parent / "coder")
    (config.CODER_ROOT_MOUNT / "drafts").mkdir(parents=True)
    target = config.CODER_ROOT_MOUNT / "drafts" / "index.md"
    target.write_text("| 旧表 | 该被换掉 |\n", encoding="utf-8")

    pool.append([_entry(summary="池里的题")])
    res = pool.write_index()

    assert res["ok"], res
    text = target.read_text(encoding="utf-8")
    assert "池里的题" in text and "旧表" not in text


# ---------------- 可用性 ----------------

def test_available_requires_an_explicit_device_name(pooled):
    """不许回退到 hostname：后端在容器里，hostname 是容器 ID，每次 --build 都换，
    标识一变同一道题就以新 id 再入池，那边会把它看成新设备出的新题。"""
    settings_store.set_many({"pool.device": ""})
    ok, why = pool.available()
    assert not ok and "本机标识" in why


def test_available_reports_each_missing_piece(pooled):
    for key, hint in (("pool.enabled", "未启用"), ("pool.repo", "仓库"),
                      ("gh.token", "GitHub Token")):
        settings_store.set_many({key: ""})
        ok, why = pool.available()
        assert not ok and hint in why
        settings_store.set_many({key: "1" if key == "pool.enabled" else "x"})
