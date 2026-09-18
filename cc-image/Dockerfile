# 挂载版 CC 任务镜像。solo-cli 把题目工作区（带初始快照的 git 仓库）和轨迹目录挂进
# 容器，而发布版镜像的 entrypoint 只接受空 /workspace，直接用会在启动前就被拒。
#
# 这里只放开这一条检查，其余守卫（轨迹目录必须为空、容器一次性、模式只允许
# interactive|print）保持原样。基础镜像按 digest 固定，避免 latest 变动后行为漂移。
#
# 这个 tag 从未推到 Docker Hub（见 docs/Requirements.md 的 R9），本机镜像一旦被
# prune 掉就无处可拉，docker run 的隐式拉取只会拿回一句加速器的报错。丢了就重建：
#
#   docker build -t adminfather/benzhi-claude-code:20260915-mount cc-image
FROM adminfather/benzhi-claude-code:20260909-isolated-git@sha256:f77014d9e56cd3db2ac96627a286814cb1aa9f0b4bb807bea98a01383c9bc4d8

USER root
RUN sed -i '\%^\[ -z "$(find /workspace -mindepth 1%,+1d' /usr/local/bin/entrypoint.sh \
 && ! grep -q 'The workspace must be empty' /usr/local/bin/entrypoint.sh \
 && grep -q 'The transcript directory must be empty' /usr/local/bin/entrypoint.sh \
 && bash -n /usr/local/bin/entrypoint.sh
USER node

LABEL org.benzhi.claude.task-mode=mount-v1
