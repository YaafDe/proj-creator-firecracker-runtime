#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="${PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION:-vdev}"
artifact_dir="${PROJ_CREATOR_FIRECRACKER_ARTIFACT_DIR:-$repo_root/artifacts/$version}"

mkdir -p "$artifact_dir"
install -m 0755 "$repo_root/runner/firecracker-runner" "$artifact_dir/firecracker-runner"
echo "runner: $artifact_dir/firecracker-runner"
