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

## Build Runtime Artifacts Locally

The release workflow does this in GitHub Actions. Local builds are mainly for
debugging the artifact process.

```bash
PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION=v2026.05.0 \
PROJ_CREATOR_FIRECRACKER_REF=v1.15.1 \
PROJ_CREATOR_FIRECRACKER_KERNEL_VERSION=6.1 \
./scripts/build-kernel.sh

PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION=v2026.05.0 \
./scripts/build-rootfs.sh

PROJ_CREATOR_FIRECRACKER_RUNTIME_VERSION=v2026.05.0 \
./scripts/build-runner.sh
```

Output is written under:

```text
artifacts/<version>/vmlinux
artifacts/<version>/kernel-artifact.json
```

The kernel wrapper skips Firecracker's optional vmclock backport patch/config by
default (`PROJ_CREATOR_FIRECRACKER_SKIP_VMCLOCK=1`). Firecracker v1.15.1's
vmclock patchset no longer applies cleanly to current Amazon Linux 6.1 tags, and
the worker runtime does not require the vmclock device. Set
`PROJ_CREATOR_FIRECRACKER_SKIP_VMCLOCK=0` only when intentionally rebuilding
against a kernel tag known to accept those patches.

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

## One-Click Release In GitHub Actions

Open **Actions > release > Run workflow** and fill in:

- `version`, for example `v2026.05.0`

That is the only release form input. The workflow builds the kernel, builds the
rootfs, packages the runner, renders `manifest.json`, and publishes all release
assets to GitHub Releases. The
manifest URL for worker setup is then:

```text
https://github.com/YaafDe/proj-creator-firecracker-runtime/releases/download/<version>/manifest.json
```

## Publish From A Local Machine

After reviewing artifacts locally:

```bash
scripts/publish-release.sh v2026.05.0
```

This uses the GitHub CLI if authenticated locally.

## Runner

`runner/firecracker-runner` is the host-side VM launcher packaged into each
release. It reads the `FirecrackerRunnerRequest` JSON from stdin, configures a
tap device, injects an ephemeral SSH key into the per-run rootfs, starts
Firecracker through its Unix API socket, stages the workspace into the guest,
runs the selected agent Docker image inside the VM, syncs workspace changes
back, and exits with the agent status.

The runner expects the host to provide `docker`, `firecracker`, `ip`, `ssh`,
`ssh-keygen`, `tar`, `mount`, `umount`, and either root privileges or
passwordless `sudo` for the tap and loop-mount steps. It loads the selected
agent image from the host Docker daemon into the guest with `docker save` /
`docker load`, so the guest does not need registry access just to start the
agent image.

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
