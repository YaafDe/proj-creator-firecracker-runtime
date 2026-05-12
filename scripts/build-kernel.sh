#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
firecracker_ref="${PROJ_CREATOR_FIRECRACKER_REF:-v1.15.1}"
kernel_version="${PROJ_CREATOR_FIRECRACKER_KERNEL_VERSION:-6.1}"
arch="${PROJ_CREATOR_FIRECRACKER_ARCH:-$(uname -m)}"
work_dir="${PROJ_CREATOR_FIRECRACKER_KERNEL_BUILD_DIR:-$repo_root/.tmp/firecracker-kernel-build}"
out_root="${PROJ_CREATOR_FIRECRACKER_KERNEL_OUT_DIR:-$repo_root/artifacts}"
dry_run="${PROJ_CREATOR_FIRECRACKER_KERNEL_DRY_RUN:-0}"
skip_vmclock="${PROJ_CREATOR_FIRECRACKER_SKIP_VMCLOCK:-1}"
patch_only="${PROJ_CREATOR_FIRECRACKER_KERNEL_PATCH_ONLY:-0}"

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

src_dir="$work_dir/firecracker"
version_id="${PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION:-${firecracker_ref#v}-kernel-${kernel_version}-${arch}}"
version_dir="$out_root/$version_id"
kernel_out="$version_dir/vmlinux"
manifest_fragment="$version_dir/kernel-artifact.json"

echo "Firecracker ref: $firecracker_ref"
echo "Kernel version: $kernel_version"
echo "Arch: $arch"
echo "Build dir: $work_dir"
echo "Output dir: $version_dir"
echo "Skip vmclock patch/config: $skip_vmclock"

if [ "$dry_run" = "1" ]; then
  echo "dry run: would clone Firecracker and run tools/devtool build_ci_artifacts kernels $kernel_version"
  exit 0
fi

mkdir -p "$work_dir" "$version_dir"
if [ ! -d "$src_dir/.git" ]; then
  git clone --depth 1 --branch "$firecracker_ref" \
    https://github.com/firecracker-microvm/firecracker.git "$src_dir"
else
  git -C "$src_dir" fetch --depth 1 origin "$firecracker_ref"
  git -C "$src_dir" checkout --detach FETCH_HEAD
fi
git -C "$src_dir" reset --hard HEAD

if [ "$skip_vmclock" = "1" ]; then
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
fi

if [ "$patch_only" = "1" ]; then
  echo "patch only: prepared Firecracker kernel build tree"
  exit 0
fi

(
  cd "$src_dir"
  if [ "$skip_vmclock" = "1" ]; then
    FC_SKIP_KERNEL_PATCHSETS=1 ./tools/devtool build_ci_artifacts kernels "$kernel_version"
  else
    ./tools/devtool build_ci_artifacts kernels "$kernel_version"
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
sha="$(sha256sum "$kernel_out" | awk '{print $1}')"
url="${PROJ_CREATOR_FIRECRACKER_KERNEL_PUBLIC_BASE_URL:-$version_dir}/vmlinux"

KERNEL_VERSION_ID="$version_id" \
KERNEL_URL="$url" \
KERNEL_SHA="$sha" \
node - <<'NODE' > "$manifest_fragment"
const fragment = {
  version: process.env.KERNEL_VERSION_ID,
  kernel: {
    url: process.env.KERNEL_URL,
    sha256: process.env.KERNEL_SHA,
    file_name: "vmlinux"
  }
};
process.stdout.write(JSON.stringify(fragment, null, 2) + "\n");
NODE

echo "kernel: $kernel_out"
echo "sha256: $sha"
echo "manifest fragment: $manifest_fragment"
