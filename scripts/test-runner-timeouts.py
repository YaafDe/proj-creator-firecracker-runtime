#!/usr/bin/env python3
import contextlib
import importlib.machinery
import importlib.util
import io
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

    def fake_run(command, **kwargs):
        assert kwargs.get("timeout") == 7
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    runner.subprocess.run = fake_run
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            try:
                runner.run(["docker", "image", "inspect", "proj-creator-agent:default"], timeout=7)
            except SystemExit as exc:
                assert exc.code == 70
            else:
                raise AssertionError("runner.run should fail on command timeout")
    finally:
        runner.subprocess.run = original_run

    output = stderr.getvalue()
    assert "command timed out after 7s" in output
    assert "docker image inspect proj-creator-agent:default" in output


if __name__ == "__main__":
    main()
