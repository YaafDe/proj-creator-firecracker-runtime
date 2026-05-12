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
  && useradd -m -s /bin/bash appuser \
  && usermod -aG sudo,docker appuser \
  && printf 'appuser ALL=(ALL) NOPASSWD:ALL\n' >/etc/sudoers.d/appuser \
  && chmod 0440 /etc/sudoers.d/appuser

COPY proj-creator-init /sbin/proj-creator-init
RUN chmod 0755 /sbin/proj-creator-init

CMD ["/sbin/proj-creator-init"]
