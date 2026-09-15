FROM python:3.12-slim-bookworm

ARG TARGETARCH
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/root/.local/bin:${PATH}"

# git：门禁校验与回填；curl/ca-certificates：拉取 docker CLI 与 Cursor CLI；libstdc++6：Cursor CLI 运行依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates bash libstdc++6 procps \
    && rm -rf /var/lib/apt/lists/*

# docker CLI（静态二进制，只用 CLI，通过挂入的 docker.sock 操控宿主 daemon）
ARG DOCKER_VERSION=27.5.1
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in amd64) ARCH=x86_64 ;; arm64) ARCH=aarch64 ;; *) echo "unsupported arch ${TARGETARCH}" && exit 1 ;; esac; \
    curl -fsSL "https://download.docker.com/linux/static/stable/${ARCH}/docker-${DOCKER_VERSION}.tgz" -o /tmp/docker.tgz; \
    tar -xzf /tmp/docker.tgz -C /tmp; \
    mv /tmp/docker/docker /usr/local/bin/docker; \
    rm -rf /tmp/docker /tmp/docker.tgz; \
    docker --version

# GitHub CLI：出题要建仓库、推初始快照。Token 运行时注入，不写入镜像。
ARG GH_VERSION=2.63.2
RUN set -eux; \
    ARCH="${TARGETARCH:-amd64}"; \
    curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/gh.tgz; \
    tar -xzf /tmp/gh.tgz -C /tmp; \
    mv "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh; \
    rm -rf /tmp/gh*; \
    gh --version

# Cursor CLI（agent）。凭证在运行时以 CURSOR_API_KEY 注入，不写入镜像。
RUN curl -fsS https://cursor.com/install | bash \
    && ln -sf /root/.local/bin/agent /usr/local/bin/agent \
    && agent --version

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
# 查重与质检的桥接脚本。运行时按宿主路径挂进 solo-qa 镜像执行，这里放一份便于查看。
COPY bridges ./bridges

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
