"""电报体：句号级孤立短句串。平台命中即打回，判法必须和 solo-qa 的 readability 一致。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.services import gsb_rules as gr

# 21727 被打回的原文：第 2 到第 5 句连着四句短句、没有衔接词
REJECTED_B = (
    "标记逻辑按 Worker 对象同一性和 clock 判定，unverified 写进了搜索索引；详情页隐藏 Terminate，"
    "并给出警告文字；持久化恢复后会重建索引。扣分有两处。一是 flower/events.py 依赖 Celery 私有函数 "
    "_serialize_Task_WeakSet_Mapping。二是执行记录里只有分模块的测试通过，而且都在最后一次改代码之前；"
    "收尾说的“393 个测试全部通过”找不到对应输出，中途还出现过持久化用例报错。"
)
REWRITTEN_B = (
    "标记逻辑按 Worker 对象同一性和 clock 判定，unverified 也写进了搜索索引。详情页在待核实时会隐藏 "
    "Terminate 并给出警告文字，持久化恢复之后还会重建索引，这几项功能都已实现。扣分有两处，一是 "
    "flower/events.py 依赖了 Celery 的私有函数 _serialize_Task_WeakSet_Mapping，Celery 升级后存在失效风险；"
    "二是执行记录里只有分模块的测试通过，而且都在最后一次改代码之前。收尾说的“393 个测试全部通过”"
    "找不到对应输出，中途还出现过持久化用例报错，因此无法确认最终代码能通过测试。"
)
PASSED_A = (
    "列表、详情、API、服务端筛选、持久化恢复和淘汰清理都实现了。flower/events.py 在离线时只标记 STARTED "
    "任务，worker-online 不会解除标记，详情页在待核实时隐藏 Terminate。执行记录显示，最后一次改代码之后"
    "完整单测和 pylint 都通过了。扣分在于解除标记时不比较 clock，迟到的 task-started 会提前解除标记；"
    "另外待核实筛选不能用搜索语法组合查询。"
)
# 平台注释里的典型样本
CLASSIC = "数据库未动。service 层修改。迁移目录核对。无新增文件。约束满足。"


def test_rejected_description_is_caught():
    run = gr.telegraph_run(REJECTED_B)
    assert run[0].startswith("详情页隐藏 Terminate") and run[2] == "扣分有两处"
    assert len(run) == 4


@pytest.mark.parametrize("text", [REWRITTEN_B, PASSED_A, "A 侧没问题。B 侧也没问题。都跑过。"])
def test_connected_or_short_runs_pass(text):
    assert gr.telegraph_run(text) == []


def test_classic_list_is_caught():
    assert len(gr.telegraph_run(CLASSIC)) == 5


def test_connective_breaks_the_run():
    assert gr.telegraph_run("数据库未动。service 层修改。但迁移目录核对过。无新增文件。约束满足。") == []


def test_delivery_check_blocks_and_rewrite_clears():
    names = lambda desc: {n for n, lvl, _ in gr.delivery_checks(
        {"score": 4, "desc": desc}, side="B") if lvl == "block"}
    assert "delivery_telegraph" in names(REJECTED_B)
    assert "delivery_telegraph" not in names(REWRITTEN_B)


def test_reason_check_blocks():
    names = {n for n, lvl, _ in gr.reason_checks("A 和 B 都改了。" + CLASSIC) if lvl == "block"}
    assert "reason_telegraph" in names


# 平台源码在本机时逐条对拍，判法漂了这里会先红
_QA_READABILITY = Path.home() / "SOLO-QA-0908" / "backend" / "qc" / "readability.py"


@pytest.mark.skipif(not _QA_READABILITY.exists(), reason="本机没有 solo-qa 源码")
@pytest.mark.parametrize("text", [REJECTED_B, REWRITTEN_B, PASSED_A, CLASSIC,
                                  "数据库未动，service 层修改，迁移目录核对。无新增文件。约束满足。好。1。"])
def test_matches_platform(text):
    spec = importlib.util.spec_from_file_location("qa_readability", _QA_READABILITY)
    rd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rd)
    assert bool(gr.telegraph_run(text)) == bool(rd.telegraphic_run_ids(text))
    assert gr.visual_len(text) == rd.visual_len(text)
