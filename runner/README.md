# Firecracker Runner

This directory is the source location for the host-side `firecracker-runner`
binary.

The runner must implement the `FirecrackerRunnerRequest` JSON contract emitted
by `proj-creator-runner-cli`. It is responsible for launching Firecracker,
booting the prepared rootfs, executing the requested agent workflow inside the
guest, syncing controlled outputs back, and exiting with the agent exit status.

The current placeholder is intentionally non-production and exits with a clear
error. Replace it with the real runner implementation before publishing a
production runtime release.
