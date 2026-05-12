#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="${PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION:-vdev}"
rootfs_size="${PROJ_CREATOR_FIRECRACKER_ROOTFS_SIZE:-8G}"
artifact_dir="${PROJ_CREATOR_FIRECRACKER_ARTIFACT_DIR:-$repo_root/artifacts/$version}"
image_name="${PROJ_CREATOR_FIRECRACKER_ROOTFS_IMAGE:-proj-creator-firecracker-rootfs:$version}"
work_dir="${PROJ_CREATOR_FIRECRACKER_ROOTFS_BUILD_DIR:-$repo_root/.tmp/rootfs-build-$version}"
dry_run="${PROJ_CREATOR_FIRECRACKER_ROOTFS_DRY_RUN:-0}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "required command not found: $1" >&2
    exit 1
  fi
}

if [ "$dry_run" = "1" ]; then
  echo "dry run: would build Docker rootfs image and export ext4 rootfs $artifact_dir/rootfs.ext4"
  exit 0
fi

require_command docker
require_command e2fsck
require_command mkfs.ext4
require_command mountpoint
require_command tar
require_command truncate

run_privileged() {
  if [ "$(id -u)" = "0" ]; then
    "$@"
  else
    sudo "$@"
  fi
}

mkdir -p "$artifact_dir" "$work_dir/mnt"
docker build -t "$image_name" "$repo_root/rootfs"
container_id="$(docker create "$image_name")"
cleanup() {
  docker rm -f "$container_id" >/dev/null 2>&1 || true
  if mountpoint -q "$work_dir/mnt"; then
    run_privileged umount "$work_dir/mnt"
  fi
}
trap cleanup EXIT

docker export "$container_id" -o "$work_dir/rootfs.tar"
rootfs="$artifact_dir/rootfs.ext4"
rm -f "$rootfs"
truncate -s "$rootfs_size" "$rootfs"
mkfs.ext4 -F "$rootfs"
run_privileged mount -o loop "$rootfs" "$work_dir/mnt"
run_privileged tar -C "$work_dir/mnt" -xf "$work_dir/rootfs.tar"
run_privileged mkdir -p "$work_dir/mnt/dev" "$work_dir/mnt/proc" "$work_dir/mnt/sys" "$work_dir/mnt/run" "$work_dir/mnt/tmp"
run_privileged chmod 1777 "$work_dir/mnt/tmp"
run_privileged umount "$work_dir/mnt"
e2fsck -fy "$rootfs" >/dev/null

echo "rootfs: $rootfs"
