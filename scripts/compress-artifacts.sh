#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="${PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION:-${VERSION:-vdev}}"
artifact_dir="${PROJ_CREATOR_FIRECRACKER_ARTIFACT_DIR:-$repo_root/artifacts/$version}"
level="${PROJ_CREATOR_FIRECRACKER_ZSTD_LEVEL:-19}"

if ! command -v zstd >/dev/null 2>&1; then
  echo "required command not found: zstd" >&2
  exit 1
fi

for file in vmlinux rootfs.ext4 firecracker-runner; do
  if [ ! -f "$artifact_dir/$file" ]; then
    echo "missing artifact: $artifact_dir/$file" >&2
    exit 1
  fi
  zstd -T0 "-$level" -f --rm "$artifact_dir/$file" -o "$artifact_dir/$file.zst"
done
