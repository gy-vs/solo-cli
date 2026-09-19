"""宿主机代理：路径换算与不可达时的兜底。

这两件事错了都很难从现象倒推：路径换错，上传接口会说「文件不存在」而文件明明在那儿；
代理没起来时若抛异常而不是给话，界面上只会看到一句「服务内部错误」。
"""

import httpx
import pytest

from app import config
from app.services import host_agent


def test_to_mount_rewrites_coder_root():
    """代理报的是宿主路径，后端读文件用的是挂载路径，中间这一下不能少。"""
    host = f"{config.CODER_ROOT_HOST}/reports/07/screencast-A-0101-000000.mp4"
    assert host_agent.to_mount(host) == f"{config.CODER_ROOT_MOUNT}/reports/07/screencast-A-0101-000000.mp4"


def test_to_mount_leaves_outside_paths_alone():
    assert host_agent.to_mount("/tmp/somewhere.mp4") == "/tmp/somewhere.mp4"
    # 前缀像但不是同一个目录，不能跟着改
    assert host_agent.to_mount(config.CODER_ROOT_HOST + "-backup/x.mp4") == config.CODER_ROOT_HOST + "-backup/x.mp4"


@pytest.mark.asyncio
async def test_unreachable_agent_reports_instead_of_raising(monkeypatch):
    """代理没起来是常态而不是故障，要给一句能照着做的话。"""
    async def boom(*_a, **_kw):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "request", boom)
    res = await host_agent.health()
    assert res["ok"] is False
    assert res["reachable"] is False
    assert "host-agent" in res["message"]


@pytest.mark.asyncio
async def test_stop_record_hands_back_a_path_the_backend_can_open(monkeypatch):
    host_file = f"{config.CODER_ROOT_HOST}/reports/07/screencast-B-0101-000000.mp4"

    async def fake(*_a, **_kw):
        return httpx.Response(200, json={"ok": True, "file": host_file, "size": 123, "seconds": 9})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake)
    res = await host_agent.stop_record("07", "B")
    assert res["host_file"] == host_file
    assert res["file"].startswith(str(config.CODER_ROOT_MOUNT))
