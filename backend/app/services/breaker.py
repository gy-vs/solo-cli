"""网络熔断：出网链路整个断掉时停出队、停动手，探到恢复再自动放行。

模型网关证书出错、GitHub 的 TLS 被掐断这类故障，换哪道题都一样会挂。巡检若照单题处理，
每道题先跑挂一次、重跑准备再因为 clone 不下来连败两次，就按次数整题废弃，调度器紧接着
发出下一道，于是一次半小时的断网能把整条队列刷进废弃列表，而这些题缺的只是一次能连上
网的重跑。所以一旦认出是网络的问题，就整体停下：调度不出闸，巡检只记不动手，每轮巡检
探一次，模型网关和 GitHub 都连得上了再放开。

状态放在进程内而不是设置里：它不是人的决定，进程重启后第一道再挂的题会重新把它拉起来。
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.models import as_utc, utc_now
from app.services import dockerx, settings_store

log = logging.getLogger("breaker")

# 模型网关连不上时 Claude Code 报的原话，以及 git/curl 断网时的 stderr 特征。都是连接层的，
# 连上之后才会有的 4xx/5xx 不在其中 —— 那些由 CC 自己的重试和网关报错那条线处理。
_NETWORK_MARKERS = (
    "unable to connect to api", "certificate", "self signed", "self-signed", "ssl",
    "tls connection", "gnutls", "econnrefused", "econnreset", "enotfound", "etimedout",
    "eai_again", "socket hang up", "fetch failed", "could not resolve host",
    "failed to connect", "connection timed out", "connection reset", "connection refused",
    "network is unreachable", "timeout after",
)
# 连上了但被拒的。和上面同时出现时以这里为准：权限问题等网络恢复也好不了。
_AUTH_MARKERS = (
    "authentication failed", "repository not found", "could not read username",
    "error: 403", "returned error: 401", "returned error: 404", "invalid api key",
)

GITHUB_PROBE = "https://github.com/"
PROBE_TIMEOUT = 15

_state: dict = {}
_reset_at: datetime | None = None
_api_url_cache: dict[str, str] = {}


def network_failure(text: str) -> bool:
    blob = (text or "").lower()
    if not blob or any(n in blob for n in _AUTH_MARKERS):
        return False
    return any(n in blob for n in _NETWORK_MARKERS)


def tripped() -> bool:
    return bool(_state)


def state() -> dict:
    return {**_state, "reset_at": _reset_at.isoformat() if _reset_at else None}


def trip(reason: str) -> bool:
    """拉闸。已经拉着的不改原因，返回这次是不是新拉的。"""
    if _state:
        return False
    _state.update({"reason": reason[:500], "at": utc_now().isoformat()})
    log.warning("网络熔断：%s。暂停出队与自动重跑/废弃，每轮巡检探一次，恢复后自动放开", reason)
    return True


def reset() -> None:
    global _reset_at
    if _state:
        log.info("网络熔断解除（拉闸于 %s）：%s", _state.get("at"), _state.get("reason"))
    _state.clear()
    _reset_at = utc_now()


def after_reset(at: datetime | None) -> bool:
    """这次失败是不是发生在上一次放开之后。

    放开之前跑挂的那些侧本来就是断网期间挂的，放开后正该拿去重跑；拿它们再拉一次闸，
    闸就永远放不开了。
    """
    if _reset_at is None:
        return True
    when = as_utc(at)
    return when is None or when > _reset_at


async def _api_url() -> str:
    image = settings_store.get("cc.image")
    if not image:
        return ""
    if image not in _api_url_cache:
        env = await dockerx.image_env(image)
        url = env.get("ANTHROPIC_BASE_URL", "")
        if not url:
            return ""
        _api_url_cache[image] = url
    return _api_url_cache[image]


async def probe() -> tuple[bool, str]:
    """模型网关和 GitHub 都连一下。拿到任何 HTTP 响应就算通，401/404 也是连上了。"""
    targets = [("GitHub", GITHUB_PROBE)]
    if api := await _api_url():
        targets.insert(0, ("模型网关", api))
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT, follow_redirects=False) as client:
        for name, url in targets:
            try:
                await client.get(url)
            except httpx.HTTPError as exc:
                return False, f"{name} {url} 仍连不上：{type(exc).__name__}: {exc}"[:300]
    return True, "、".join(n for n, _ in targets) + " 均已连通"
