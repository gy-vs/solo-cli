"""定时巡检：异常重跑、产物推送、自动开分析。完整实现见后续任务。"""

from __future__ import annotations

import asyncio

_wake = asyncio.Event()


def wake() -> None:
    """催一次巡检。单侧跑完后调用，不必等下一个周期到点。"""
    _wake.set()
