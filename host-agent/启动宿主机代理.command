#!/bin/bash
# 双击我就行。窗口留着别关，关了控制台上的「启动项目 / 录屏」按钮就不好使了。
cd "$(dirname "$0")" || exit 1
exec /usr/bin/env python3 solo_host_agent.py
