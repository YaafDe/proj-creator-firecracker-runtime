#!/usr/bin/env python3
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import subprocess
from pathlib import Path


def load_runner():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "runner" / "firecracker-runner"
    loader = importlib.machinery.SourceFileLoader("firecracker_runner", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main():
    runner = load_runner()
    original_run = runner.subprocess.run
    original_timeout = os.environ.get("PROJ_CREATOR_FIRECRACKER_DOCKER_DIAGNOSTIC_TIMEOUT_SECONDS")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs.get("timeout") == 3
        assert kwargs.get("stdout") == subprocess.PIPE
        assert kwargs.get("stderr") == subprocess.STDOUT
        output = b"docker ok\nAI_FENCE_MASTER_KEY=secret-value\nAuthorization: Bearer token-value\n"
        return subprocess.CompletedProcess(command, 0, stdout=output)

    runner.subprocess.run = fake_run
    os.environ["PROJ_CREATOR_FIRECRACKER_DOCKER_DIAGNOSTIC_TIMEOUT_SECONDS"] = "3"
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            runner.collect_guest_docker_load_diagnostics(["ssh", "appuser@172.31.1.2"], "proj-creator-agent:default")
    finally:
        runner.subprocess.run = original_run
        if original_timeout is None:
            os.environ.pop("PROJ_CREATOR_FIRECRACKER_DOCKER_DIAGNOSTIC_TIMEOUT_SECONDS", None)
        else:
            os.environ["PROJ_CREATOR_FIRECRACKER_DOCKER_DIAGNOSTIC_TIMEOUT_SECONDS"] = original_timeout

    assert calls, "diagnostic command was not executed"
    command, _kwargs = calls[0]
    assert command[:2] == ["ssh", "appuser@172.31.1.2"]
    assert "docker image inspect --format" in command[-1]
    assert "proj-creator-agent:default" in command[-1]

    output = stderr.getvalue()
    assert "guest docker-load diagnostic: docker ok" in output
    assert "AI_FENCE_MASTER_KEY=<redacted>" in output
    assert "Bearer <redacted>" in output
    assert "secret-value" not in output
    assert "token-value" not in output


if __name__ == "__main__":
    main()
