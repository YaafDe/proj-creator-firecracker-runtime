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

The runner accepts Firecracker runner contract version `1`. Requests that omit
`contract_version` are treated as v1 for compatibility with older Runner CLI
releases; unknown versions are rejected before host resources are acquired.

When the request sets `docker_service_required: true`, the runner mounts the
guest's `/var/run/docker.sock` into the agent container and adds the socket's
numeric group ID to the container process. This exposes only the disposable
guest Docker daemon; the executor host Docker socket is never mounted into the
microVM or agent container.

The guest init starts Docker with its bridge and iptables networking enabled so
agent-started application and dependency containers can use ordinary Docker
networks and Compose-style service discovery inside the microVM.
