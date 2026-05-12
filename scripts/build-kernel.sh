#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
provider="${PROJ_CREATOR_FIRECRACKER_KERNEL_PROVIDER:-ubuntu}"
firecracker_ref="${PROJ_CREATOR_FIRECRACKER_REF:-v1.15.1}"
firecracker_config_version="${PROJ_CREATOR_FIRECRACKER_CONFIG_VERSION:-6.1}"
kernel_version="${PROJ_CREATOR_FIRECRACKER_KERNEL_VERSION:-6.8}"
ubuntu_kernel_repo="${PROJ_CREATOR_UBUNTU_KERNEL_REPO:-https://git.launchpad.net/~ubuntu-kernel/ubuntu/+source/linux/+git/noble}"
ubuntu_kernel_tag="${PROJ_CREATOR_UBUNTU_KERNEL_TAG:-latest}"
ubuntu_kernel_tag_pattern="${PROJ_CREATOR_UBUNTU_KERNEL_TAG_PATTERN:-Ubuntu-6.8.0-*}"
arch="${PROJ_CREATOR_FIRECRACKER_ARCH:-$(uname -m)}"
work_dir="${PROJ_CREATOR_FIRECRACKER_KERNEL_BUILD_DIR:-$repo_root/.tmp/firecracker-kernel-build}"
out_root="${PROJ_CREATOR_FIRECRACKER_KERNEL_OUT_DIR:-$repo_root/artifacts}"
dry_run="${PROJ_CREATOR_FIRECRACKER_KERNEL_DRY_RUN:-0}"
patch_only="${PROJ_CREATOR_FIRECRACKER_KERNEL_PATCH_ONLY:-0}"
skip_vmclock="${PROJ_CREATOR_FIRECRACKER_SKIP_VMCLOCK:-1}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "required command not found: $1" >&2
    exit 1
  fi
}

case "$arch" in
  x86_64|aarch64) ;;
  *)
    echo "unsupported Firecracker kernel arch: $arch" >&2
    exit 1
    ;;
esac

require_command git
require_command docker
require_command sha256sum
require_command node
require_command python3

if [ -n "${PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION:-}" ]; then
  version_id="$PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION"
elif [ "$provider" = "firecracker-ci" ]; then
  version_id="${provider}-kernel-${firecracker_config_version}-${arch}"
else
  version_id="${provider}-kernel-${kernel_version}-${arch}"
fi
version_dir="$out_root/$version_id"
kernel_out="$version_dir/vmlinux"
manifest_fragment="$version_dir/kernel-artifact.json"

resolve_ubuntu_kernel_tag() {
  if [ "$ubuntu_kernel_tag" != "latest" ]; then
    echo "$ubuntu_kernel_tag"
    return
  fi
  git ls-remote --tags "$ubuntu_kernel_repo" "refs/tags/$ubuntu_kernel_tag_pattern" \
    | awk '{print $2}' \
    | sed -e 's#refs/tags/##' \
    | grep -v '\^{}' \
    | sort -uV \
    | tail -n 1
}

clone_firecracker_config_source() {
  local src_dir="$work_dir/firecracker"
  if [ ! -d "$src_dir/.git" ]; then
    git clone --depth 1 --branch "$firecracker_ref" \
      https://github.com/firecracker-microvm/firecracker.git "$src_dir"
  else
    git -C "$src_dir" fetch --depth 1 origin "$firecracker_ref"
    git -C "$src_dir" checkout --detach FETCH_HEAD
  fi
  git -C "$src_dir" reset --hard HEAD >/dev/null
  echo "$src_dir"
}

write_kernel_manifest() {
  local source_name="$1"
  local source_ref="$2"
  local sha
  local url
  sha="$(sha256sum "$kernel_out" | awk '{print $1}')"
  url="${PROJ_CREATOR_FIRECRACKER_KERNEL_PUBLIC_BASE_URL:-$version_dir}/vmlinux"

  KERNEL_VERSION_ID="$version_id" \
  KERNEL_URL="$url" \
  KERNEL_SHA="$sha" \
  KERNEL_SOURCE_NAME="$source_name" \
  KERNEL_SOURCE_REF="$source_ref" \
  node - <<'NODE' > "$manifest_fragment"
const fragment = {
  version: process.env.KERNEL_VERSION_ID,
  kernel: {
    url: process.env.KERNEL_URL,
    sha256: process.env.KERNEL_SHA,
    file_name: "vmlinux",
    source: {
      name: process.env.KERNEL_SOURCE_NAME,
      ref: process.env.KERNEL_SOURCE_REF
    }
  }
};
process.stdout.write(JSON.stringify(fragment, null, 2) + "\n");
NODE

  echo "kernel: $kernel_out"
  echo "sha256: $sha"
  echo "manifest fragment: $manifest_fragment"
}

build_ubuntu_kernel() {
  if [ "$arch" != "x86_64" ]; then
    echo "Ubuntu kernel provider currently supports x86_64 only; set PROJ_CREATOR_FIRECRACKER_KERNEL_PROVIDER=firecracker-ci for $arch" >&2
    exit 1
  fi

  local resolved_tag
  local fc_src
  local ubuntu_src
  local config_path
  resolved_tag="$(resolve_ubuntu_kernel_tag)"
  if [ -z "$resolved_tag" ]; then
    echo "failed to resolve Ubuntu kernel tag from $ubuntu_kernel_repo pattern $ubuntu_kernel_tag_pattern" >&2
    exit 1
  fi

  echo "Kernel provider: ubuntu"
  echo "Ubuntu kernel repo: $ubuntu_kernel_repo"
  echo "Ubuntu kernel tag: $resolved_tag"
  echo "Firecracker config ref: $firecracker_ref"
  echo "Firecracker config version: $firecracker_config_version"
  echo "Arch: $arch"
  echo "Build dir: $work_dir"
  echo "Output dir: $version_dir"

  if [ "$dry_run" = "1" ]; then
    echo "dry run: would build Ubuntu kernel tag $resolved_tag into $kernel_out"
    exit 0
  fi

  mkdir -p "$work_dir" "$version_dir"
  fc_src="$(clone_firecracker_config_source)"
  config_path="$fc_src/resources/guest_configs/microvm-kernel-ci-$arch-$firecracker_config_version.config"
  if [ ! -f "$config_path" ]; then
    echo "Firecracker guest kernel config not found: $config_path" >&2
    exit 1
  fi

  ubuntu_src="$work_dir/ubuntu-linux-$resolved_tag"
  if [ ! -d "$ubuntu_src/.git" ]; then
    git clone --depth 1 --branch "$resolved_tag" "$ubuntu_kernel_repo" "$ubuntu_src"
  else
    git -C "$ubuntu_src" fetch --depth 1 origin "$resolved_tag"
    git -C "$ubuntu_src" checkout --detach FETCH_HEAD
  fi
  git -C "$ubuntu_src" reset --hard HEAD >/dev/null
  cp "$config_path" "$ubuntu_src/.config"

  if [ "$patch_only" = "1" ]; then
    echo "patch only: prepared Ubuntu kernel source and Firecracker guest config"
    exit 0
  fi

  docker run --rm \
    -v "$ubuntu_src:/src" \
    -v "$version_dir:/out" \
    -w /src \
    ubuntu:24.04 \
    bash -lc '
      set -euo pipefail
      export DEBIAN_FRONTEND=noninteractive
      apt-get update
      apt-get install -y --no-install-recommends \
        bc bison build-essential ca-certificates dwarves flex git libelf-dev libssl-dev rsync
      make ARCH=x86_64 olddefconfig
      make ARCH=x86_64 -j"$(nproc)" vmlinux
      install -m 0644 vmlinux /out/vmlinux
    '

  write_kernel_manifest "ubuntu-noble" "$resolved_tag"
}

patch_firecracker_rebuild_for_no_vmclock() {
  local src_dir="$1"
  FIRECRACKER_SRC_DIR="$src_dir" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["FIRECRACKER_SRC_DIR"]) / "resources" / "rebuild.sh"
text = path.read_text()
old_patch_loop = """    # Apply any patchset we have for our kernels
    for patchset in ../patches/*; do
        echo "Applying patchset ${patchset}/${KERNEL_VERSION}"
        git apply ${patchset}/${KERNEL_VERSION}/*.patch
    done
"""
new_patch_loop = """    # Apply any patchset we have for our kernels, unless disabled by the wrapper.
    if [[ "${FC_SKIP_KERNEL_PATCHSETS:-0}" != "1" ]]; then
        for patchset in ../patches/*; do
            if ! compgen -G "${patchset}/${KERNEL_VERSION}/*.patch" >/dev/null; then
                continue
            fi
            echo "Applying patchset ${patchset}/${KERNEL_VERSION}"
            git apply ${patchset}/${KERNEL_VERSION}/*.patch
        done
    fi
"""
if old_patch_loop not in text:
    raise SystemExit("Firecracker resources/rebuild.sh patch loop changed; update build-kernel.sh")
text = text.replace(old_patch_loop, new_patch_loop)
text = text.replace(' "$VMCLOCK_CONFIG"', "")
path.write_text(text)
PY
}

build_firecracker_ci_kernel() {
  local src_dir
  echo "Kernel provider: firecracker-ci"
  echo "Firecracker ref: $firecracker_ref"
  echo "Kernel version: $firecracker_config_version"
  echo "Arch: $arch"
  echo "Build dir: $work_dir"
  echo "Output dir: $version_dir"
  echo "Skip vmclock patch/config: $skip_vmclock"

  if [ "$dry_run" = "1" ]; then
    echo "dry run: would clone Firecracker and run tools/devtool build_ci_artifacts kernels $firecracker_config_version"
    exit 0
  fi

  mkdir -p "$work_dir" "$version_dir"
  src_dir="$(clone_firecracker_config_source)"
  if [ "$skip_vmclock" = "1" ]; then
    patch_firecracker_rebuild_for_no_vmclock "$src_dir"
  fi

  if [ "$patch_only" = "1" ]; then
    echo "patch only: prepared Firecracker kernel build tree"
    exit 0
  fi

  (
    cd "$src_dir"
    if [ "$skip_vmclock" = "1" ]; then
      FC_SKIP_KERNEL_PATCHSETS=1 ./tools/devtool build_ci_artifacts kernels "$firecracker_config_version"
    else
      ./tools/devtool build_ci_artifacts kernels "$firecracker_config_version"
    fi
  )

  kernel_candidate="$(
    find "$src_dir/resources/$arch" -maxdepth 2 -type f \
      \( -name 'vmlinux*' -o -name 'Image*' \) \
      ! -name '*.config' \
      ! -name '*.json' \
      -printf '%T@ %p\n' \
      | sort -nr \
      | awk 'NR == 1 {print substr($0, index($0,$2))}'
  )"

  if [ -z "$kernel_candidate" ] || [ ! -f "$kernel_candidate" ]; then
    echo "failed to find built Firecracker kernel under $src_dir/resources/$arch" >&2
    exit 1
  fi

  install -m 0644 "$kernel_candidate" "$kernel_out"
  write_kernel_manifest "firecracker-ci" "$firecracker_ref"
}

case "$provider" in
  ubuntu) build_ubuntu_kernel ;;
  firecracker-ci) build_firecracker_ci_kernel ;;
  *)
    echo "unsupported kernel provider: $provider (expected ubuntu or firecracker-ci)" >&2
    exit 1
    ;;
esac
