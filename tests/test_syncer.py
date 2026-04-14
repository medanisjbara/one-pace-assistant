"""Tests for rsync synchronization module."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from onepace_assistant.cli import cli
from onepace_assistant.syncer import (
    SyncError,
    SyncOptions,
    build_rsync_command,
    check_remote_rsync,
    check_rsync_installed,
    run_rsync,
)


def _make_options(**overrides) -> SyncOptions:
    """Create SyncOptions with sensible defaults for testing."""
    defaults = {
        "source": Path("/tmp/downloads"),
        "target": "user@host:/media/onepace",
    }
    defaults.update(overrides)
    return SyncOptions(**defaults)


# --- build_rsync_command tests ---


class TestBuildRsyncCommand:
    def test_basic_command(self):
        opts = _make_options()
        cmd = build_rsync_command(opts)
        assert cmd[0] == "rsync"
        assert "-ahz" in cmd
        assert "--info=progress2" in cmd
        assert cmd[-2] == "/tmp/downloads/"
        assert cmd[-1] == "user@host:/media/onepace"

    def test_dry_run_flag(self):
        opts = _make_options(dry_run=True)
        cmd = build_rsync_command(opts)
        assert "--dry-run" in cmd

    def test_delete_flag(self):
        opts = _make_options(delete=True)
        cmd = build_rsync_command(opts)
        assert "--delete" in cmd

    def test_verbose_flag(self):
        opts = _make_options(verbose=True)
        cmd = build_rsync_command(opts)
        assert "-v" in cmd

    def test_bwlimit(self):
        opts = _make_options(bwlimit="5000")
        cmd = build_rsync_command(opts)
        assert "--bwlimit=5000" in cmd

    def test_exclude_patterns(self):
        opts = _make_options(exclude=("*.nfo", "poster.jpg"))
        cmd = build_rsync_command(opts)
        assert "--exclude=*.nfo" in cmd
        assert "--exclude=poster.jpg" in cmd

    def test_ssh_key_option(self):
        opts = _make_options(ssh_key=Path("/home/user/.ssh/id_rsa"))
        cmd = build_rsync_command(opts)
        assert "-e" in cmd
        ssh_arg = cmd[cmd.index("-e") + 1]
        assert "-i" in ssh_arg
        assert "/home/user/.ssh/id_rsa" in ssh_arg

    def test_ssh_port_option(self):
        opts = _make_options(port=2222)
        cmd = build_rsync_command(opts)
        assert "-e" in cmd
        ssh_arg = cmd[cmd.index("-e") + 1]
        assert "-p" in ssh_arg
        assert "2222" in ssh_arg

    def test_ssh_key_and_port_combined(self):
        opts = _make_options(ssh_key=Path("/home/user/.ssh/id_rsa"), port=2222)
        cmd = build_rsync_command(opts)
        # Should be a single -e argument with both options
        assert cmd.count("-e") == 1
        ssh_arg = cmd[cmd.index("-e") + 1]
        assert "-p 2222" in ssh_arg
        assert "-i /home/user/.ssh/id_rsa" in ssh_arg

    def test_ssh_always_included_for_remote_target(self):
        opts = _make_options()  # default target is user@host:/media/onepace
        cmd = build_rsync_command(opts)
        assert "-e" in cmd
        ssh_arg = cmd[cmd.index("-e") + 1]
        assert "ControlMaster=auto" in ssh_arg

    def test_no_ssh_option_for_local_target(self):
        opts = _make_options(target="/local/path")
        cmd = build_rsync_command(opts)
        assert "-e" not in cmd

    def test_trailing_slash_added(self):
        opts = _make_options(source=Path("/tmp/downloads"))
        cmd = build_rsync_command(opts)
        assert cmd[-2] == "/tmp/downloads/"

    def test_trailing_slash_not_doubled(self):
        # Path objects strip trailing slashes, but test the string logic
        opts = _make_options(source=Path("/tmp/downloads"))
        cmd = build_rsync_command(opts)
        assert not cmd[-2].endswith("//")


# --- check_rsync_installed tests ---


class TestCheckRsyncInstalled:
    @patch("onepace_assistant.syncer.shutil.which", return_value="/usr/bin/rsync")
    def test_rsync_found(self, mock_which):
        result = check_rsync_installed()
        assert result == "/usr/bin/rsync"

    @patch("onepace_assistant.syncer.shutil.which", return_value=None)
    def test_rsync_not_found(self, mock_which):
        with pytest.raises(SyncError, match="rsync is not installed"):
            check_rsync_installed()


# --- check_remote_rsync tests ---


class TestCheckRemoteRsync:
    @patch("onepace_assistant.syncer.subprocess.run")
    def test_remote_rsync_found(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "/usr/bin/rsync\n"
        # Should not raise
        check_remote_rsync("user@host:/path")
        mock_run.assert_called_once()

    @patch("onepace_assistant.syncer.subprocess.run")
    def test_remote_rsync_not_found(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        with pytest.raises(SyncError, match="rsync is not installed on"):
            check_remote_rsync("user@host:/path")

    @patch("onepace_assistant.syncer.subprocess.run")
    def test_ssh_connection_failed(self, mock_run):
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "ssh: connect to host badhost port 22: Connection refused"
        with pytest.raises(SyncError, match="SSH connection to 'user@host' failed"):
            check_remote_rsync("user@host:/path")

    @patch("onepace_assistant.syncer.subprocess.run")
    def test_ssh_connection_failed_includes_stderr(self, mock_run):
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Permission denied (publickey)"
        with pytest.raises(SyncError, match="Permission denied"):
            check_remote_rsync("user@host:/path")

    def test_skipped_for_local_path(self):
        # Should not raise or attempt SSH for local paths
        check_remote_rsync("/local/path")

    @patch("onepace_assistant.syncer.subprocess.run")
    def test_uses_ssh_key_and_port(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "/usr/bin/rsync\n"
        check_remote_rsync(
            "user@host:/path",
            ssh_key=Path("/home/user/.ssh/id_rsa"),
            port=2222,
        )
        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        assert "2222" in cmd
        assert "-i" in cmd
        assert "/home/user/.ssh/id_rsa" in cmd


# --- run_rsync tests ---


class TestRunRsync:
    @patch("onepace_assistant.syncer.subprocess.run")
    @patch("onepace_assistant.syncer.shutil.which", return_value="/usr/bin/rsync")
    def test_successful_sync(self, mock_which, mock_run):
        mock_run.return_value.returncode = 0
        opts = _make_options()
        result = run_rsync(opts)
        assert result == 0

    @patch("onepace_assistant.syncer.subprocess.run")
    @patch("onepace_assistant.syncer.shutil.which", return_value="/usr/bin/rsync")
    def test_ssh_failure(self, mock_which, mock_run):
        mock_run.return_value.returncode = 255
        opts = _make_options()
        with pytest.raises(SyncError, match="SSH connection failed"):
            run_rsync(opts)

    @patch("onepace_assistant.syncer.subprocess.run")
    @patch("onepace_assistant.syncer.shutil.which", return_value="/usr/bin/rsync")
    def test_partial_transfer(self, mock_which, mock_run):
        mock_run.return_value.returncode = 23
        opts = _make_options()
        with pytest.raises(SyncError, match="Partial transfer"):
            run_rsync(opts)

    @patch("onepace_assistant.syncer.subprocess.run")
    @patch("onepace_assistant.syncer.shutil.which", return_value="/usr/bin/rsync")
    def test_unknown_exit_code(self, mock_which, mock_run):
        mock_run.return_value.returncode = 99
        opts = _make_options()
        with pytest.raises(SyncError, match="rsync exited with code 99"):
            run_rsync(opts)


# --- CLI integration tests ---


class TestRsyncCLI:
    def test_rsync_not_installed(self, tmp_path):
        # Create a non-empty source dir
        (tmp_path / "test.mkv").touch()
        runner = CliRunner()
        with patch(
            "onepace_assistant.cli.check_rsync_installed",
            side_effect=SyncError("rsync is not installed"),
        ):
            result = runner.invoke(cli, ["rsync", "-s", str(tmp_path), "-t", "host:/path"])
        assert result.exit_code != 0
        assert "rsync is not installed" in result.output

    def test_empty_source_dir(self, tmp_path):
        runner = CliRunner()
        with patch("onepace_assistant.cli.check_rsync_installed"), patch(
            "onepace_assistant.cli.check_remote_rsync"
        ):
            result = runner.invoke(cli, ["rsync", "-s", str(tmp_path), "-t", "host:/path"])
        assert result.exit_code != 0
        assert "empty" in result.output

    def test_dry_run_output(self, tmp_path):
        (tmp_path / "test.mkv").touch()
        runner = CliRunner()
        with patch("onepace_assistant.cli.check_rsync_installed"), patch(
            "onepace_assistant.cli.check_remote_rsync"
        ), patch("onepace_assistant.cli.run_rsync"):
            result = runner.invoke(
                cli, ["rsync", "-s", str(tmp_path), "-t", "host:/path", "--dry-run"]
            )
        assert "DRY RUN" in result.output

    def test_successful_sync_output(self, tmp_path):
        (tmp_path / "test.mkv").touch()
        runner = CliRunner()
        with patch("onepace_assistant.cli.check_rsync_installed"), patch(
            "onepace_assistant.cli.check_remote_rsync"
        ), patch("onepace_assistant.cli.run_rsync"):
            result = runner.invoke(cli, ["rsync", "-s", str(tmp_path), "-t", "host:/path"])
        assert result.exit_code == 0
        assert "Sync complete!" in result.output

    def test_sync_failure_output(self, tmp_path):
        (tmp_path / "test.mkv").touch()
        runner = CliRunner()
        with patch("onepace_assistant.cli.check_rsync_installed"), patch(
            "onepace_assistant.cli.check_remote_rsync"
        ), patch("onepace_assistant.cli.run_rsync", side_effect=SyncError("SSH connection failed")):
            result = runner.invoke(cli, ["rsync", "-s", str(tmp_path), "-t", "host:/path"])
        assert result.exit_code != 0
        assert "SSH connection failed" in result.output
