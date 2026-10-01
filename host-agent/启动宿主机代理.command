#!/bin/bash
# 双击我就行。窗口留着别关，关了控制台上的「启动项目 / 录屏」按钮就不好使了，防熄屏也跟着失效。
# 代理意外退出会自动拉起；Ctrl+C 或端口已被另一个代理占着时才真正退出。
cd "$(dirname "$0")" || exit 1
while true; do
  /usr/bin/env python3 solo_host_agent.py
  code=$?
  if [ "$code" -eq 0 ] || [ "$code" -eq 2 ] || [ "$code" -eq 130 ]; then
    exit "$code"
  fi
  echo "[$(date +%H:%M:%S)] 代理异常退出（$code），3 秒后自动拉起"
  sleep 3
done
