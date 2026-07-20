#!/usr/bin/env python3

import importlib.machinery
import importlib.util
import pathlib
import signal
import unittest
from unittest import mock


RUNNER = pathlib.Path(__file__).resolve().parents[1] / "runner" / "firecracker-runner"
loader = importlib.machinery.SourceFileLoader("firecracker_runner", str(RUNNER))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class DockerServiceArgsTests(unittest.TestCase):
    def test_required_service_mounts_guest_socket_and_adds_socket_group(self):
        self.assertEqual(
            module.docker_service_args(True, "998\n"),
            [
                "-v",
                "/var/run/docker.sock:/var/run/docker.sock",
                "--group-add",
                "998",
            ],
        )

    def test_optional_service_does_not_mount_socket(self):
        self.assertEqual(module.docker_service_args(False, "not-used"), [])

    def test_required_service_rejects_invalid_socket_group(self):
        with self.assertRaises(SystemExit):
            module.docker_service_args(True, "root")


class NetworkCleanupTests(unittest.TestCase):
    def test_preexisting_per_run_rule_is_still_owned_for_cleanup(self):
        with mock.patch.object(module, "iptables_rule_exists", return_value=True), mock.patch.object(
            module, "run_privileged"
        ) as run_privileged:
            cleanup = module.ensure_iptables_rule(
                "nat", "POSTROUTING", ["-s", "172.31.20.0/24", "-j", "MASQUERADE"]
            )

        self.assertEqual(
            cleanup,
            [
                "iptables",
                "-t",
                "nat",
                "-D",
                "POSTROUTING",
                "-s",
                "172.31.20.0/24",
                "-j",
                "MASQUERADE",
            ],
        )
        run_privileged.assert_not_called()

    def test_partial_nat_setup_rolls_back_before_propagating_failure(self):
        first_cleanup = ["iptables", "-t", "nat", "-D", "POSTROUTING", "rule"]
        with mock.patch.object(module, "require_command"), mock.patch.object(
            module, "run_privileged"
        ), mock.patch.object(
            module,
            "ensure_iptables_rule",
            side_effect=[first_cleanup, RuntimeError("injected failure")],
        ), mock.patch.object(module, "cleanup_guest_nat") as cleanup_guest_nat:
            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                module.setup_guest_nat("pcfctest", "172.31.20.1")

        cleanup_guest_nat.assert_called_once_with([first_cleanup])


class SignalHandlingTests(unittest.TestCase):
    def test_utility_decoding_does_not_install_process_signal_handlers(self):
        before = {
            signum: signal.getsignal(signum)
            for signum in (signal.SIGTERM, signal.SIGINT)
        }

        self.assertEqual(module.base64_decode("dGVzdA=="), "test")

        self.assertEqual(
            {
                signum: signal.getsignal(signum)
                for signum in (signal.SIGTERM, signal.SIGINT)
            },
            before,
        )


if __name__ == "__main__":
    unittest.main()
