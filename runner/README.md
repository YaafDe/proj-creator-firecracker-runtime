# Firecracker Runner

This directory is the source location for the host-side `firecracker-runner`
executable.

The runner must implement the `FirecrackerRunnerRequest` JSON contract emitted
by `proj-creator-runner-cli`. It is responsible for launching Firecracker,
booting the prepared rootfs, executing the requested agent workflow inside the
guest, syncing controlled outputs back, and exiting with the agent exit status.

The checked-in runner is a Python 3 executable with only standard-library
runtime dependencies. It expects the host to provide `docker`, `firecracker`,
`ip`, `ssh`, `ssh-keygen`, `tar`, `mount`, `umount`, and either root privileges
or passwordless `sudo` for loop mounting the per-run rootfs and creating the tap
device.

The runner stages the host workspace into the guest over SSH, runs the selected
agent Docker image inside the VM after loading it from the host Docker daemon,
then syncs the workspace back while excluding `.git` so host Git metadata is not
overwritten by the guest copy.
