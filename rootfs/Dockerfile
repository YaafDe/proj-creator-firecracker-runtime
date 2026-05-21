FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    docker.io \
    git \
    iproute2 \
    iptables \
    openssh-client \
    openssh-server \
    procps \
    python3 \
    sudo \
    tar \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /run/sshd /workspace /var/lib/proj-creator \
  && if getent passwd 1000 >/dev/null; then userdel -r "$(getent passwd 1000 | cut -d: -f1)" 2>/dev/null || userdel "$(getent passwd 1000 | cut -d: -f1)"; fi \
  && if getent group 10001 >/dev/null; then groupmod -n appuser "$(getent group 10001 | cut -d: -f1)"; else groupadd --gid 10001 appuser; fi \
  && useradd --uid 10001 --gid 10001 -m -s /bin/bash appuser \
  && usermod -aG sudo,docker appuser \
  && chown appuser:appuser /workspace /var/lib/proj-creator \
  && printf 'appuser ALL=(ALL) NOPASSWD:ALL\n' >/etc/sudoers.d/appuser \
  && chmod 0440 /etc/sudoers.d/appuser

COPY proj-creator-init /sbin/proj-creator-init
RUN chmod 0755 /sbin/proj-creator-init

CMD ["/sbin/proj-creator-init"]
