# extmute image: the upstream bot plus the command-line mute patch.
# Same runtime as the official Dockerfile, but built from the checked-out
# source (COPY) instead of downloading dgongut's release zip, which would
# not carry the patch. Build from the repository root:
#   docker buildx build -f extmute/Dockerfile .
# or just run extmute/build.sh.
ARG BASE_IMAGE=alpine:3.24.3
FROM ${BASE_IMAGE}
ARG BASE_IMAGE

ARG VERSION
LABEL org.opencontainers.image.title="docker-controller-bot-cli" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/xorguy/docker-controller-bot-extmute" \
      org.opencontainers.image.url="https://hub.docker.com/r/xorguy/docker-controller-bot-cli" \
      org.opencontainers.image.licenses="GPL-3.0" \
      org.opencontainers.image.description="docker-controller-bot with mute from the command line (.muted_until)." \
      org.opencontainers.image.documentation="https://github.com/xorguy/docker-controller-bot-extmute/blob/extmute/extmute/README.md" \
      org.opencontainers.image.base.name="${BASE_IMAGE}"

ENV TZ=UTC \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache python3 py3-pip tzdata py3-paramiko openssh-client

# requirements.txt first so the pip layer is cached across code-only changes.
COPY requirements.txt /app/
RUN export PIP_BREAK_SYSTEM_PACKAGES=1 && \
    pip3 install --no-cache-dir -Ur /app/requirements.txt

# Every module at the root: .dockerignore already keeps tests/ out.
COPY *.py /app/
COPY locale /app/locale

RUN mkdir -p /etc/ssh/ssh_config.d && \
    printf 'Host *\n    BatchMode yes\n    ConnectTimeout 10\n    ServerAliveInterval 10\n    ServerAliveCountMax 3\n' \
        > /etc/ssh/ssh_config.d/docker-controller-bot.conf

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/tmp/dcb-heartbeat') < 120 else 1)" || exit 1

ENTRYPOINT ["python3", "docker-controller-bot.py"]

ARG BUILD_DATE
ARG VCS_REF
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"
