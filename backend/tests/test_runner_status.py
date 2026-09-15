"""结束状态判定：正常收尾、超时、人工停止，以及后端重启后接管的容器。"""

from app.models import FAILED, FINISHED, INTERRUPTED, TIMEOUT
from app.services.runner import decide_status

SUCCESS = {"type": "result", "subtype": "success", "is_error": False}


def test_success_result_is_finished():
    st, adopted = decide_status(timed_out=False, manual_stop=False, result_event=SUCCESS,
                                exit_code=0, has_trace=True)
    assert (st, adopted) == (FINISHED, False)


def test_error_result_is_failed():
    st, _ = decide_status(timed_out=False, manual_stop=False,
                          result_event={"subtype": "error_during_execution", "is_error": True},
                          exit_code=1, has_trace=True)
    assert st == FAILED


def test_timeout_and_manual_stop_win():
    assert decide_status(timed_out=True, manual_stop=False, result_event={}, exit_code=None, has_trace=True)[0] == TIMEOUT
    assert decide_status(timed_out=False, manual_stop=True, result_event={}, exit_code=None, has_trace=True)[0] == INTERRUPTED


def test_adopted_container_with_trace_is_finished():
    """重启后接管：读不到 stdout 所以 result 为空，但退出码 0 且有轨迹，算跑完。"""
    st, adopted = decide_status(timed_out=False, manual_stop=False, result_event={},
                                exit_code=0, has_trace=True)
    assert (st, adopted) == (FINISHED, True)


def test_adopted_without_trace_is_failed():
    """退出码 0 但一份轨迹都没有，说明没真正干活，不能算完成。"""
    st, adopted = decide_status(timed_out=False, manual_stop=False, result_event={},
                                exit_code=0, has_trace=False)
    assert (st, adopted) == (FAILED, False)


def test_killed_container_is_interrupted():
    for code in (137, 143, None):
        st, _ = decide_status(timed_out=False, manual_stop=False, result_event={},
                              exit_code=code, has_trace=True)
        assert st == INTERRUPTED, code
