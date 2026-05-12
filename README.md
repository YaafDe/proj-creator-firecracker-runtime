# Proj Creator Firecracker Runtime

Versioned Firecracker runtime artifacts for `proj-creator-runner-cli`.

This repository is intentionally separate from the application/backend
repository. Normal app releases should not build kernels, root filesystems, or
VM runners. Worker hosts consume one pinned manifest URL and download only the
runtime artifacts they need.

## Release Shape

Each release publishes:

```text
manifest.json
vmlinux
rootfs.ext4
firecracker-runner
SHA256SUMS
```

The manifest is consumed by:

```bash
PROJ_CREATOR_AGENT_RUNTIME=firecracker \
proj-creator-runner-cli install-worker \
  --backend-url https://create.example.com \
  --api-key "$PROJ_CREATOR_API_KEY" \
  --firecracker-artifact-manifest https://github.com/YaafDe/proj-creator-firecracker-runtime/releases/download/v2026.05.0/manifest.json \
  --yes
```

## Repository Connection

Do not connect this repo to the main app repo with a submodule, subtree, or
vendored artifacts. The connection point is only the immutable release manifest
URL. This keeps app CI fast and keeps worker setup reproducible.

## Build A Kernel Artifact

The kernel build uses Firecracker's own artifact recipe through Docker.

```bash
PROJ_CREATOR_FIRECRACKER_REF=v1.15.1 \
PROJ_CREATOR_FIRECRACKER_KERNEL_VERSION=6.1 \
./scripts/build-kernel.sh
```

Output is written under:

```text
artifacts/<version>/vmlinux
artifacts/<version>/kernel-artifact.json
```

## Assemble A Manifest

Put the three runtime files in `artifacts/<version>/`:

```text
artifacts/v2026.05.0/vmlinux
artifacts/v2026.05.0/rootfs.ext4
artifacts/v2026.05.0/firecracker-runner
```

Then render the release manifest:

```bash
VERSION=v2026.05.0 \
BASE_URL=https://github.com/YaafDe/proj-creator-firecracker-runtime/releases/download/v2026.05.0 \
node scripts/render-manifest.mjs
```

This writes:

```text
artifacts/v2026.05.0/manifest.json
artifacts/v2026.05.0/SHA256SUMS
```

## Publish

After reviewing artifacts locally:

```bash
scripts/publish-release.sh v2026.05.0
```

This uses the GitHub CLI if authenticated locally. GitHub Actions can be added
later to run the same scripts when the rootfs and runner builds are automated.

## Security Rules

Public release assets must not contain:

- worker tokens
- API keys
- SSH keys
- private registry credentials
- app/customer data
- environment-specific secrets

The rootfs should be a generic bootable runtime image. Per-worker and per-run
configuration is injected at install time or through the Firecracker runner
request.
