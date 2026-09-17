"""五维描述的几类交付事故：写出本机路径、写出我自己的核验环境、用步数指位置、拿总评当开场。

描述会原样交付给评审方，所以路径和步数在落库前就洗掉，环境自述和总评开场在核验里拦成红项。
"""

from app.services.analyzer import _normalize, _strip_paths, _strip_steps
from app.services.verifier import check_text_style

REAL_DESC = (
    "我把 prompt 要交的六件东西逐条在产物里找了一遍，一件都没有。轨迹第 1 到 48 步全是 Read 和 grep，"
    "没有出现过一次 Edit 或 Write。我在 /host/coder/出题/分析/04/repo 里跑 git status 得到 working tree clean，"
    "lib/presets/default.mjs 的选项表仍然停在 maxNesting，没有新开关。"
)
REAL_OTHER = (
    "产物副本里没有 node_modules，我这边也没有 node 可执行文件，想 import md from './index.mjs' "
    "打印 token.map 来验证跑不起来，所以核验是靠 git status 和对 lib、test 的 grep 做的。这不影响结论。"
)


REPO = "/host/coder/出题/分析/04/repo"


def test_strip_mount_path_keeps_sentence_readable():
    out = _strip_paths(REAL_DESC, REPO)
    assert "/host" not in out and "出题" not in out and "04/repo" not in out
    assert "仓库根目录 里跑 git status" in out
    # 仓库内的相对路径不能被动到
    assert "lib/presets/default.mjs" in out


def test_strip_paths_reduces_abs_to_repo_relative():
    assert _strip_paths(f"看 {REPO}/lib/token.mjs 就知道", REPO) == "看 lib/token.mjs 就知道"
    assert _strip_paths("相对路径 test/markdown-it.test.mjs 不动", REPO) == "相对路径 test/markdown-it.test.mjs 不动"
    # 不认识的绝对路径也不能原样留着：像文件就留文件名，像目录就抹掉
    assert _strip_paths("在 /Users/gaoyong/x/y/a.jsonl 里") == "在 a.jsonl 里"
    assert _strip_paths("cd /host/coder/出题") == "cd 仓库根目录"


def test_normalize_strips_paths_everywhere():
    raw = {
        "delivery": {"score": 2, "description": REAL_DESC,
                     "evidence": [{"step": 3, "file": f"{REPO}/lib/a.mjs", "quote": f"cd {REPO}"}]},
        "other_issues": f"我在 {REPO} 里核对过",
        "requirement_coverage": [{"point": "位置字段", "status": "missing", "evidence": f"{REPO}/README.md"}],
        "verification": {"commands": [f"cd {REPO} && git status"], "summary": f"在 {REPO} 里跑的"},
    }
    out = _normalize(raw, REPO)
    blob = str(out)
    assert "/host" not in blob and "出题" not in blob and "/repo" not in blob
    assert out["evidence"]["delivery"][0]["file"] == "lib/a.mjs"
    assert out["verification"]["commands"] == ["cd 仓库根目录 && git status"]


def test_container_workspace_is_relative_not_leak():
    """容器里的 /workspace 就是仓库根，剥成相对路径；它不算本机泄漏，只提醒。"""
    assert _strip_paths("它读了 /workspace/lib/common/x.js") == "它读了 lib/common/x.js"
    codes = {i["code"]: i["level"] for i in check_text_style("我看它读了 /workspace/lib/common/x.js，改动没落地，函数还是旧的。")}
    assert "abs_path" not in codes
    assert codes.get("container_path") == "warn"


def test_abs_path_is_blocked():
    codes = {i["code"]: i["level"] for i in check_text_style("我在 /host/coder/出题/分析/04/repo 里跑了 git status，产物没有变化，我核对过六条需求。")}
    assert codes.get("abs_path") == "block"


def test_env_self_talk_is_blocked():
    items = check_text_style(REAL_OTHER)
    hit = next(i for i in items if i["code"] == "meta_talk")
    assert hit["level"] == "block"
    assert "node_modules" in hit["words"]


def test_clean_desc_passes():
    good = ("lib/rules_inline.mjs 里没有位置字段的赋值，prompt 要的六条需求只落了四条。"
            "它只用 grep 找了 getLines 就去写 README，README 说的 setLines 在代码里根本没有，"
            "我按 README 的说法找不到对应函数。")
    assert check_text_style(good) == []


# ---- 用步数指位置 ----

def test_strip_steps_keeps_sentence_readable():
    assert _strip_steps("第 38 步新建的 lib/dump-scalar.js") == "新建的 lib/dump-scalar.js"
    assert _strip_steps("它在第 19、20 步追到 Error: Cannot find module") == "它追到 Error: Cannot find module"
    assert _strip_steps("它在第 48 到 51 步建 HEAD worktree") == "它建 HEAD worktree"
    assert _strip_steps("改完在第 43、59、60、64 步分批核黄金样本") == "改完分批核黄金样本"
    assert _strip_steps("步骤 12 里它只读了一半") == "它只读了一半"
    # 正常的数字别被误伤
    assert _strip_steps("npm test 的 core 用例 329 个全过，第二处的 foo 也对上了") == \
        "npm test 的 core 用例 329 个全过，第二处的 foo 也对上了"


def test_normalize_strips_steps_from_descriptions():
    raw = {"delivery": {"score": 4, "description": "第 66 步 git status 只有 lib/dumper.js 改动。"}}
    out = _normalize(raw)
    assert out["descs"]["delivery"] == "git status 只有 lib/dumper.js 改动。"


def test_step_ref_is_blocked():
    codes = {i["code"]: i["level"] for i in check_text_style(
        "lib/dumper.js 的 writeNode 改了返回值，第 38 步它才补上 chooseScalarStyle，中间的用例一直是红的。")}
    assert codes.get("step_ref") == "block"


# ---- 拿总评当开场 ----

def test_canned_opener_is_blocked():
    for head in ("我把需求逐条对了产物", "推进顺序我认可", "几个关键判断都做对了", "调用路径十分紧凑"):
        items = check_text_style(f"{head}。lib/dumper.js 的 writeNode 返回了 text 和 tag，npm test 全过。")
        hit = next((i for i in items if i["code"] == "opener_talk"), None)
        assert hit and hit["level"] == "block", head


def test_judgement_with_anchor_is_only_warned():
    """带了具体文件还夹一句评价，提醒就行，不至于拦住上传。"""
    codes = {i["code"]: i["level"] for i in check_text_style(
        "lib/dumper.js 的 writeNode 改得还行，返回值换成了 text 和 tag。我跑 npm test 全过。")}
    assert codes.get("opener_judgement") == "warn"
    assert "opener_talk" not in codes


def test_vague_opener_is_warned():
    codes = {i["code"]: i["level"] for i in check_text_style(
        "它先看了一圈就动手改。writeNode 现在返回 text 和 tag，我跑 npm test 全过。")}
    assert codes.get("vague_opener") == "warn"


def test_concrete_opener_passes():
    ok = ("lib/dumper.js 的 writeNode 现在返回 { text, tag }，writeBlockSequence 也跟着改了。"
          "我跑 npm test，core 的 329 个用例全过。")
    assert check_text_style(ok) == []
