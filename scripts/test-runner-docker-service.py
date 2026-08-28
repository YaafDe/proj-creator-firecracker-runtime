#!/usr/bin/env python3

import importlib.machinery
import importlib.util
import os
import pathlib
import signal
import tempfile
import unittest
from unittest import mock


RUNNER = pathlib.Path(__file__).resolve().parents[1] / "runner" / "firecracker-runner"
loader = importlib.machinery.SourceFileLoader("firecracker_runner", str(RUNNER))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class DockerServiceArgsTests(unittest.TestCase):
    def test_unknown_runner_contract_is_rejected_before_resource_setup(self):
        with self.assertRaises(SystemExit):
            module.run_request({"contract_version": 2})

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

    def test_agent_container_has_stable_runtime_owned_identity_labels(self):
        self.assertEqual(
            module.agent_container_identity_args(
                {
                    "conversation_id": "conversation-1",
                    "message_id": "message-1",
                }
            ),
            [
                "--label",
                "proj-creator.runtime-role=agent",
                "--label",
                "proj-creator.conversation-id=conversation-1",
                "--label",
                "proj-creator.message-id=message-1",
            ],
        )

    def test_agent_container_identity_omits_absent_request_ids(self):
        self.assertEqual(
            module.agent_container_identity_args({}),
            ["--label", "proj-creator.runtime-role=agent"],
        )


class GuestImageStagingTests(unittest.TestCase):
    def test_waits_for_ssh_after_image_load_before_staging_workspace(self):
        operations = mock.Mock()
        ssh_base = ["ssh", "appuser@guest"]
        root_ssh_base = ["ssh", "root@guest"]
        repo = pathlib.Path("/tmp/repo")

        with mock.patch.object(module, "emit_status"), mock.patch.object(
            module,
            "guest_docker_image_id",
            side_effect=[None, "sha256:guest"],
        ), mock.patch.object(
            module,
            "load_docker_image_to_guest",
            operations.load_image,
        ), mock.patch.object(
            module,
            "wait_for_ssh",
            operations.wait_for_ssh,
        ), mock.patch.object(
            module,
            "ensure_guest_image_reference",
            operations.ensure_image_reference,
        ), mock.patch.object(
            module,
            "tar_to_guest",
            operations.tar_to_guest,
        ), mock.patch.object(
            module,
            "chown_guest_workspace",
            operations.chown_guest_workspace,
        ):
            operations.load_image.return_value = ("sha256:guest", [])
            module.load_image_and_stage_workspace(
                ssh_base,
                root_ssh_base,
                "proj-creator-agent:test",
                repo,
                "/workspace",
                10001,
                10001,
                "sha256:expected",
            )

        self.assertEqual(
            operations.mock_calls,
            [
                mock.call.load_image(
                    ssh_base,
                    "proj-creator-agent:test",
                    "sha256:expected",
                ),
                mock.call.wait_for_ssh(ssh_base, 120),
                mock.call.ensure_image_reference(
                    ssh_base, "sha256:guest", "proj-creator-agent:test"
                ),
                mock.call.tar_to_guest(ssh_base, repo, "/workspace"),
                mock.call.chown_guest_workspace(
                    root_ssh_base,
                    "/workspace",
                    10001,
                    10001,
                ),
            ],
        )

    def test_imported_guest_id_is_used_when_docker_rewrites_the_host_id(self):
        operations = mock.Mock()
        ssh_base = ["ssh", "appuser@guest"]
        root_ssh_base = ["ssh", "root@guest"]
        repo = pathlib.Path("/tmp/repo")
        host_id = "sha256:" + "a" * 64
        guest_id = "sha256:" + "b" * 64

        with mock.patch.object(module, "emit_status"), mock.patch.object(
            module,
            "guest_docker_image_id",
            side_effect=[None, guest_id],
        ), mock.patch.object(
            module,
            "load_docker_image_to_guest",
            return_value=(guest_id, []),
        ) as load_image, mock.patch.object(
            module,
            "wait_for_ssh",
            operations.wait_for_ssh,
        ), mock.patch.object(
            module,
            "ensure_guest_image_reference",
            operations.ensure_image_reference,
        ), mock.patch.object(
            module,
            "tar_to_guest",
            operations.tar_to_guest,
        ), mock.patch.object(
            module,
            "chown_guest_workspace",
            operations.chown_guest_workspace,
        ):
            resolved = module.load_image_and_stage_workspace(
                ssh_base,
                root_ssh_base,
                "proj-creator-agent:test",
                repo,
                "/workspace",
                10001,
                10001,
                host_id,
                expected_guest_image_id=guest_id,
            )

        self.assertEqual(resolved, guest_id)
        load_image.assert_called_once_with(
            ssh_base,
            "proj-creator-agent:test",
            host_id,
        )
        self.assertEqual(
            operations.mock_calls,
            [
                mock.call.wait_for_ssh(ssh_base, 120),
                mock.call.ensure_image_reference(
                    ssh_base, guest_id, "proj-creator-agent:test"
                ),
                mock.call.tar_to_guest(ssh_base, repo, "/workspace"),
                mock.call.chown_guest_workspace(
                    root_ssh_base,
                    "/workspace",
                    10001,
                    10001,
                ),
            ],
        )

    def test_prepared_image_skips_host_transfer(self):
        operations = mock.Mock()
        ssh_base = ["ssh", "appuser@guest"]
        root_ssh_base = ["ssh", "root@guest"]
        repo = pathlib.Path("/tmp/repo")

        with mock.patch.object(module, "emit_status"), mock.patch.object(
            module,
            "guest_docker_image_id",
            return_value="sha256:prepared",
        ), mock.patch.object(
            module,
            "load_docker_image_to_guest",
            operations.load_image,
        ), mock.patch.object(
            module,
            "wait_for_ssh",
            operations.wait_for_ssh,
        ), mock.patch.object(
            module,
            "ensure_guest_image_reference",
            operations.ensure_image_reference,
        ), mock.patch.object(
            module,
            "tar_to_guest",
            operations.tar_to_guest,
        ), mock.patch.object(
            module,
            "chown_guest_workspace",
            operations.chown_guest_workspace,
        ):
            module.load_image_and_stage_workspace(
                ssh_base,
                root_ssh_base,
                "proj-creator-agent:test",
                repo,
                "/workspace",
                10001,
                10001,
                "sha256:prepared",
            )

        self.assertEqual(
            operations.mock_calls,
            [
                mock.call.ensure_image_reference(
                    ssh_base, "sha256:prepared", "proj-creator-agent:test"
                ),
                mock.call.tar_to_guest(ssh_base, repo, "/workspace"),
                mock.call.chown_guest_workspace(
                    root_ssh_base,
                    "/workspace",
                    10001,
                    10001,
                ),
            ],
        )


class PreparedImageCacheTests(unittest.TestCase):
    def test_cache_requires_matching_immutable_image_id(self):
        with tempfile.TemporaryDirectory() as directory:
            warm_dir = pathlib.Path(directory)
            (warm_dir / "rootfs.ext4").write_bytes(b"prepared")
            (warm_dir / "prepared.json").write_text(
                '{"selected_image_id":"sha256:image-a",'
                '"guest_image_id":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
                encoding="utf-8",
            )

            self.assertTrue(
                module.prepared_image_cache_ready(warm_dir, "sha256:image-a")
            )
            self.assertFalse(
                module.prepared_image_cache_ready(warm_dir, "sha256:image-b")
            )

    def test_legacy_cache_without_guest_image_id_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            warm_dir = pathlib.Path(directory)
            (warm_dir / "rootfs.ext4").write_bytes(b"prepared")
            (warm_dir / "prepared.json").write_text(
                '{"selected_image_id":"sha256:image-a"}',
                encoding="utf-8",
            )

            self.assertFalse(
                module.prepared_image_cache_ready(warm_dir, "sha256:image-a")
            )


class DockerLoadOutputTests(unittest.TestCase):
    def test_bulk_image_transfer_uses_operation_timeout_not_short_ssh_keepalives(self):
        ssh_base = [
            "ssh",
            "-i",
            "/tmp/guest-key",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ServerAliveInterval=15",
            "-oServerAliveCountMax=2",
            "appuser@guest",
        ]

        transfer_base = module.ssh_base_for_bounded_bulk_transfer(ssh_base)

        self.assertEqual(
            transfer_base,
            [
                "ssh",
                "-i",
                "/tmp/guest-key",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ServerAliveInterval=0",
                "appuser@guest",
            ],
        )
        self.assertEqual(ssh_base[-1], "appuser@guest")

    def test_parses_guest_id_rewritten_during_cross_version_load(self):
        guest_id = "sha256:" + "b" * 64
        self.assertEqual(
            module.parse_docker_load_output(f"Loaded image ID: {guest_id}\n"),
            (guest_id, []),
        )

    def test_parses_loaded_tag_as_fallback_reference(self):
        self.assertEqual(
            module.parse_docker_load_output("Loaded image: proj-creator-agent:test\n"),
            (None, ["proj-creator-agent:test"]),
        )

    def test_preserves_requested_guest_image_tag(self):
        guest_id = "sha256:" + "b" * 64
        with mock.patch.object(module, "ssh_command") as ssh_command:
            module.ensure_guest_image_reference(
                ["ssh", "appuser@guest"],
                guest_id,
                "proj-creator-agent:test",
            )

        ssh_command.assert_called_once_with(
            ["ssh", "appuser@guest"],
            f"docker image tag {guest_id} proj-creator-agent:test",
        )

    def test_does_not_treat_an_immutable_id_as_a_tag(self):
        guest_id = "sha256:" + "b" * 64
        with mock.patch.object(module, "ssh_command") as ssh_command:
            module.ensure_guest_image_reference(
                ["ssh", "appuser@guest"],
                guest_id,
                "sha256:" + "a" * 64,
            )

        ssh_command.assert_not_called()


class PreparedImageShutdownTests(unittest.TestCase):
    def test_guest_shutdown_requests_restart_instead_of_unsupported_poweroff(self):
        script = module.guest_shutdown_script()

        self.assertIn("0x01234567", script)
        self.assertIn("use_errno=True", script)
        self.assertIn("reboot -f", script)
        self.assertNotIn("0x4321fedc", script)
        self.assertNotIn("poweroff", script)

    def test_large_guest_image_flush_has_a_separate_bounded_phase(self):
        root_ssh_base = [
            "ssh",
            "-o",
            "ServerAliveInterval=15",
            "-oServerAliveCountMax=2",
            "root@guest",
        ]

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            module,
            "emit_status",
        ) as emit_status, mock.patch.object(module, "run") as run:
            module.flush_prepared_guest_filesystem(root_ssh_base)

        emit_status.assert_called_once_with(
            "setup",
            "Flushing prepared agent image filesystem",
        )
        run.assert_called_once_with(
            [
                "timeout",
                "900",
                "ssh",
                "-o",
                "ServerAliveInterval=0",
                "root@guest",
                "sync",
            ]
        )

    def test_large_guest_image_flush_timeout_is_configurable(self):
        root_ssh_base = ["ssh", "root@guest"]

        with mock.patch.dict(
            os.environ,
            {"PROJ_CREATOR_FIRECRACKER_PREPARED_SYNC_TIMEOUT_SECONDS": "1200"},
            clear=True,
        ), mock.patch.object(module, "emit_status"), mock.patch.object(
            module,
            "run",
        ) as run:
            module.flush_prepared_guest_filesystem(root_ssh_base)

        run.assert_called_once_with(
            [
                "timeout",
                "1200",
                "ssh",
                "-o",
                "ServerAliveInterval=0",
                "root@guest",
                "sync",
            ]
        )


class SshCommandTransportTests(unittest.TestCase):
    def test_large_remote_script_is_streamed_instead_of_added_to_argv(self):
        script = "printf x\n" * 20000
        ssh_base = ["ssh", "appuser@guest"]

        with mock.patch.object(module, "run") as run:
            module.ssh_command(ssh_base, script, check=False)

        run.assert_called_once_with(
            [*ssh_base, "bash", "-l", "-s"],
            check=False,
            stdout=None,
            input_data=script.encode("utf-8"),
        )
        self.assertNotIn(script, run.call_args.args[0])

    def test_payload_stdin_keeps_the_remote_script_as_a_small_argument(self):
        script = "tar -C /workspace -xf -"
        payload = object()
        ssh_base = ["ssh", "root@guest"]

        with mock.patch.object(module, "run") as run:
            module.ssh_command(ssh_base, script, stdin=payload)

        run.assert_called_once_with(
            [*ssh_base, "bash", "-lc", module.shlex.quote(script)],
            check=True,
            stdout=None,
            stdin=payload,
        )

    def test_ssh_output_streams_script_and_decodes_stdout(self):
        script = "id -u"
        ssh_base = ["ssh", "appuser@guest"]
        result = mock.Mock(returncode=0, stdout=b"10001\n")

        with mock.patch.object(module, "run", return_value=result) as run:
            output = module.ssh_output(ssh_base, script)

        self.assertEqual(output, "10001\n")
        run.assert_called_once_with(
            [*ssh_base, "bash", "-l", "-s"],
            check=False,
            stdout=module.subprocess.PIPE,
            input_data=script.encode("utf-8"),
        )

    def test_large_agent_script_is_staged_instead_of_added_to_docker_argv(self):
        script = "printf x\n" * 20000
        ssh_base = ["ssh", "appuser@guest"]

        with mock.patch.object(module, "write_guest_file") as write_guest_file:
            mount_args, command_args = module.stage_agent_script(
                ssh_base,
                "proj-creator-agent-message-1",
                script,
            )

        write_guest_file.assert_called_once_with(
            ssh_base,
            "/tmp/proj-creator-agent-message-1-inner-script.sh",
            script.encode("utf-8"),
        )
        self.assertEqual(
            mount_args,
            [
                "-v",
                "/tmp/proj-creator-agent-message-1-inner-script.sh:/tmp/proj-creator-inner-script.sh:ro",
            ],
        )
        self.assertEqual(
            command_args,
            ["/bin/bash", "-l", "/tmp/proj-creator-inner-script.sh"],
        )
        self.assertNotIn(script, mount_args + command_args)

    def test_guest_file_contents_are_streamed_instead_of_added_to_argv(self):
        contents = b"x" * (256 * 1024)
        ssh_base = ["ssh", "appuser@guest"]

        with mock.patch.object(module, "run") as run:
            module.write_guest_file(
                ssh_base,
                "/tmp/proj-creator-agent-script.sh",
                contents,
            )

        command = run.call_args.args[0]
        self.assertNotIn(contents.decode("utf-8"), command)
        run.assert_called_once_with(
            [
                *ssh_base,
                "bash",
                "-lc",
                module.shlex.quote(
                    "umask 077; cat > /tmp/proj-creator-agent-script.sh; "
                    "chmod 0600 /tmp/proj-creator-agent-script.sh"
                ),
            ],
            input_data=contents,
        )


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
    def test_closed_parent_pipes_do_not_interrupt_cleanup_diagnostics(self):
        with mock.patch("builtins.print", side_effect=BrokenPipeError):
            module.log("cleanup diagnostic")
            module.emit_status("cleanup", "removing resources")

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

    def test_main_installs_handlers_before_request_setup_and_restores_them(self):
        before = {
            signum: signal.getsignal(signum)
            for signum in (signal.SIGTERM, signal.SIGINT)
        }

        def interrupt_during_setup(_request):
            self.assertIs(signal.getsignal(signal.SIGTERM), module.raise_runner_interrupted)
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        with mock.patch.object(module.json, "load", return_value={}), mock.patch.object(
            module, "run_request", side_effect=interrupt_during_setup
        ), self.assertRaises(SystemExit) as exited:
            module.main()

        self.assertEqual(exited.exception.code, 128 + signal.SIGTERM)
        self.assertEqual(
            {
                signum: signal.getsignal(signum)
                for signum in (signal.SIGTERM, signal.SIGINT)
            },
            before,
        )

    def test_ssh_key_mount_is_unmounted_when_setup_is_interrupted(self):
        rootfs = pathlib.Path("/tmp/rootfs.ext4")
        mount_dir = pathlib.Path("/tmp/rootfs-mount")
        with mock.patch.object(module, "run_privileged") as run_privileged, mock.patch.object(
            module,
            "rootfs_user_ids",
            side_effect=module.RunnerInterrupted(signal.SIGTERM),
        ), self.assertRaises(module.RunnerInterrupted):
            module.inject_ssh_key(rootfs, mount_dir, "ssh-ed25519 test")

        self.assertEqual(
            run_privileged.call_args_list,
            [
                mock.call(["mount", "-o", "loop", str(rootfs), str(mount_dir)]),
                mock.call(["umount", str(mount_dir)], check=False),
            ],
        )


if __name__ == "__main__":
    unittest.main()
