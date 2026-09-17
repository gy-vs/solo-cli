"""路径分侧：A 与 B 是同一道题的两次独立运行，除分析目录外全部隔开。"""

import pytest

from app import config


def test_paths_split_by_side():
    a = config.TaskPaths("07", "A")
    b = config.TaskPaths("07", "B")
    assert a.workspace.name == "A" and a.workspace.parent.name == "07"
    assert b.workspace.name == "B"
    assert a.traces.name == "A" and a.traces.parent.name == "07"
    assert a.container_name == "solo-cc-07-A"
    assert b.container_name == "solo-cc-07-B"
    assert a.export.name == "A" and a.export.parent.name == "07"


def test_analysis_dir_is_shared_but_repo_is_not():
    a = config.TaskPaths("07", "A")
    b = config.TaskPaths("07", "B")
    assert a.analysis == b.analysis
    assert a.analysis_repo.name == "repo-A"
    assert b.analysis_repo.name == "repo-B"
    assert a.trace_index.name == "trace_index_A.json"


def test_host_paths_use_host_root():
    a = config.TaskPaths("07", "A")
    assert a.workspace_host == f"{config.CODER_ROOT_HOST}/workspace/07/A"
    assert a.traces_host == f"{config.CODER_ROOT_HOST}/出题/轨迹/07/A"


def test_side_is_validated():
    with pytest.raises(ValueError):
        config.TaskPaths("07", "C")
    # 小写要能自动大写，别让调用方到处 .upper()
    assert config.TaskPaths("07", "a").side == "A"


def test_no_round_suffix_left():
    assert not hasattr(config.TaskPaths("07", "A"), "round_suffix")
