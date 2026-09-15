"""五维描述的两类交付事故：写出本机路径、写出我自己的核验环境。

描述会原样交付给评审方，所以路径在落库前就要洗掉，环境自述要在核验里拦成红项。
"""

from app.services.analyzer import _normalize, _strip_paths
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
    assert _strip_paths("第 9 步读了 /workspace/lib/common/x.js") == "第 9 步读了 lib/common/x.js"
    codes = {i["code"]: i["level"] for i in check_text_style("我看第 9 步它读了 /workspace/lib/common/x.js，改动没落地，函数还是旧的。")}
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
    good = ("我把 prompt 里六条需求逐条对了产物，lib/rules_inline.mjs 里没有位置字段的赋值，"
            "第 12 步它只用 grep 找了 getLines 就去写 README，导致 README 说的接口在代码里找不到。")
    codes = {i["code"] for i in check_text_style(good)}
    assert "abs_path" not in codes and "meta_talk" not in codes
