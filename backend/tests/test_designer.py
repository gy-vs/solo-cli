"""出题：候选校验、题号分配、题面渲染、上游基线解析。

这几样是出题里唯一由本地代码决定的东西。模型只写字，字写得好不好没法在单测里判，
但「模型写回来的东西能不能用」必须判得住——仓库名不合法、难度填错、正文太短都要在
建仓库之前拦下来，否则 GitHub 上会留下一个建了一半的仓库。
"""

from __future__ import annotations

import pytest

from app.services import designer


def _candidate(**over) -> dict:
    base = {
        "source": "A",
        "upstream": "https://github.com/csstree/csstree",
        "repo_name": "css-syntax-core",
        "question_type": "功能开发",
        "difficulty": "困难",
        "languages": "JavaScript, Node.js",
        "repro_level": "完全可复现",
        "summary": "补齐选择器解析",
        "origin_reason": "该版本已有解析框架但尚未支持嵌套",
        "prompt_body": "需求正文。" * 40,
    }
    base.update(over)
    return base


# ---------------- 候选校验 ----------------

def test_valid_candidate_passes():
    assert designer.validate_candidate(_candidate()) == ""


@pytest.mark.parametrize("name", ["q1", "q7-parser", "task-runner", "demo-app", "eval-core", "case-2"])
def test_repo_name_exposing_question_semantics_is_rejected(name):
    """红线：仓库名不能暴露编号或出题语义，模型在容器里看得到 origin。"""
    assert designer.validate_candidate(_candidate(repo_name=name)) != ""


@pytest.mark.parametrize("name", ["CssTree", "css_tree", "-abc", "a", "css tree"])
def test_malformed_repo_name_is_rejected(name):
    assert "不合法" in designer.validate_candidate(_candidate(repo_name=name))


@pytest.mark.parametrize("level", ["简单", "中等", "", "hard"])
def test_only_hard_and_hell_difficulty_are_accepted(level):
    assert "难度" in designer.validate_candidate(_candidate(difficulty=level))


def test_short_prompt_body_is_rejected():
    assert "太短" in designer.validate_candidate(_candidate(prompt_body="改个 bug"))


def test_non_github_upstream_is_rejected():
    got = designer.validate_candidate(_candidate(upstream="git@github.com:a/b.git"))
    assert "上游地址" in got


def test_source_c_does_not_need_upstream():
    assert designer.validate_candidate(_candidate(source="C", upstream="")) == ""


# ---------------- 题号分配 ----------------

def test_next_task_no_fills_the_first_gap():
    """题号要补空位而不是一直往后加，否则删过题之后号会越跳越大。"""
    assert designer.next_task_no({"01", "02", "04"}) == "03"


def test_next_task_no_starts_at_01():
    assert designer.next_task_no(set()) == "01"


def test_next_task_no_pads_to_two_digits():
    assert designer.next_task_no({f"{n:02d}" for n in range(1, 9)}) == "09"


# ---------------- 候选解析 ----------------

def test_parse_candidates_reads_plain_array():
    assert designer._parse_candidates('[{"repo_name":"a"}]')[0]["repo_name"] == "a"


def test_parse_candidates_strips_code_fence():
    text = '```json\n[{"repo_name":"a"}]\n```'
    assert designer._parse_candidates(text)[0]["repo_name"] == "a"


def test_parse_candidates_skips_leading_prose():
    text = '好的，这是 3 道题：\n[{"repo_name":"a"},{"repo_name":"b"}]'
    assert len(designer._parse_candidates(text)) == 2


def test_parse_candidates_raises_without_array():
    with pytest.raises(ValueError):
        designer._parse_candidates("我没法完成这个任务")


# ---------------- 题面渲染 ----------------

SHA = "a" * 40


def test_rendered_draft_is_parsable_by_prompt_bank():
    """渲染出来的题面必须能被导入解析，两边的字段名是同一套。"""
    from app.services import prompt_bank

    text = designer.render_draft("07", _candidate(), "https://github.com/me/css-syntax-core",
                                 SHA, "1.2.3")
    parsed = prompt_bank.parse_text(text)
    assert len(parsed) == 1
    t = parsed[0]
    assert t.task_no == "07"
    assert t.fields["difficulty"] == "困难"
    assert t.fields["question_type"] == "功能开发"
    assert t.fields["harness_version"] == "1.2.3"
    assert t.meta["仓库"].startswith("https://github.com/me/css-syntax-core")
    assert SHA in t.fields["env_snapshot"]
    assert t.user_prompt.startswith("需求正文。")


def test_rendered_draft_carries_prompt_body_verbatim():
    body = "请把解析器的嵌套选择器支持补齐，注意不要引入新依赖。" * 10
    text = designer.render_draft("07", _candidate(prompt_body=body),
                                 "https://github.com/me/x", SHA, "1.2.3")
    assert body in text


def test_rendered_draft_records_upstream_and_reason():
    """来源说明要能查证：选了哪个上游、哪个 commit、为什么选它。"""
    text = designer.render_draft("07", _candidate(), "https://github.com/me/x", SHA, "1.2.3")
    assert "https://github.com/csstree/csstree" in text
    assert "尚未支持嵌套" in text
    assert f"csstree/csstree@{SHA}" in text


def test_rendered_draft_marks_self_designed_source():
    text = designer.render_draft("07", _candidate(source="C", upstream=""),
                                 "https://github.com/me/x", SHA, "1.2.3")
    assert "自行设计" in text


# ---------------- 上游基线 ----------------

@pytest.mark.asyncio
async def test_resolve_upstream_head_picks_the_sha(monkeypatch, tmp_db):
    """要带 tmp_db：取上游 HEAD 会经过 _gh_env()，那里要读设置表拿 token。"""
    from app.services import dockerx

    out = f"ref: refs/heads/main\tHEAD\n{SHA}\tHEAD\n"

    async def fake_run(args, **kw):
        return dockerx.CmdResult(0, out, "")

    monkeypatch.setattr(dockerx, "run", fake_run)
    sha, err = await designer.resolve_upstream_head("https://github.com/a/b")
    assert (sha, err) == (SHA, "")


@pytest.mark.asyncio
async def test_resolve_upstream_head_reports_unreachable_repo(monkeypatch, tmp_db):
    """上游拉不到要当场说清楚，不能等到 clone 那一步才炸。"""
    from app.services import dockerx

    async def fake_run(args, **kw):
        return dockerx.CmdResult(128, "", "repository not found")

    monkeypatch.setattr(dockerx, "run", fake_run)
    sha, err = await designer.resolve_upstream_head("https://github.com/a/nope")
    assert sha == "" and "读不到上游" in err
