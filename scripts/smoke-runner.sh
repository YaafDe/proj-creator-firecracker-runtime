#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(
  "$repo_root/runner/firecracker-runner" 2>&1 <<'JSON' || true
{
  "runtime": "firecracker",
  "selected_image": "proj-creator-agent:smoke",
  "repo": "/definitely/missing/proj-creator-firecracker-smoke-repo",
  "workdir": "/workspace",
  "kernel_image": "/definitely/missing/vmlinux",
  "rootfs": "/definitely/missing/rootfs.ext4",
  "warm_dir": "/tmp/proj-creator-firecracker-smoke/warm",
  "run_dir": "/tmp/proj-creator-firecracker-smoke/run",
  "clone_mode": "reflink",
  "docker_service_required": true,
  "mount_policy": "sync-workspace-explicit-support-mounts",
  "mounts": [],
  "sync": {
    "sync_git_changes": true,
    "sync_artifacts": true,
    "sync_logs": true,
    "sync_usage": true,
    "normalize_ownership": true
  },
  "envs": [],
  "extra_docker_args": null,
  "inner_script": "true",
  "pid_file": "/tmp/proj-creator-firecracker-smoke/agent.pid",
  "conversation_id": null,
  "app_id": null,
  "message_id": null
}
JSON
)"

case "$output" in
  *"rootfs does not exist"*) ;;
  *)
    printf '%s\n' "$output" >&2
    echo "expected runner smoke check to fail before host-impacting setup" >&2
    exit 1
    ;;
esac
