#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [ -z "$version" ]; then
  echo "usage: $0 v2026.05.0" >&2
  exit 1
fi

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
artifact_dir="$repo_root/artifacts/$version"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required to publish from this machine" >&2
  exit 1
fi

for file in manifest.json SHA256SUMS vmlinux.zst rootfs.ext4.zst firecracker-runner.zst; do
  if [ ! -f "$artifact_dir/$file" ]; then
    echo "missing artifact: $artifact_dir/$file" >&2
    exit 1
  fi
done

gh release create "$version" \
  "$artifact_dir/manifest.json" \
  "$artifact_dir/SHA256SUMS" \
  "$artifact_dir/vmlinux.zst" \
  "$artifact_dir/rootfs.ext4.zst" \
  "$artifact_dir/firecracker-runner.zst" \
  --title "$version" \
  --notes "Proj Creator Firecracker runtime $version"
