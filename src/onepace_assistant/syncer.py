"""Rsync-based file synchronization."""

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class SyncError(Exception):
    """Error during rsync synchronization."""


@dataclass
class SyncOptions:
    """Configuration for an rsync sync operation."""

    source: Path
    target: str
    ssh_key: Path | None = None
    port: int | None = None
    dry_run: bool = False
    delete: bool = False
    exclude: tuple[str, ...] = field(default_factory=tuple)
    bwlimit: str | None = None
    verbose: bool = False


def check_rsync_installed() -> str:
    """Check that rsync is available on PATH.

    Returns the path to rsync.
    Raises SyncError if rsync is not found.
    """
    rsync_path = shutil.which("rsync")
    if rsync_path is None:
        raise SyncError(
            "rsync is not installed or not found on PATH. "
            "Install it with: apt install rsync (Debian/Ubuntu), "
            "brew install rsync (macOS), or pacman -S rsync (Arch)"
        )
    return rsync_path


def _parse_remote_host(target: str) -> str | None:
    """Extract user@host from a target like user@host:/path.

    Returns None if the target appears to be a local path.
    """
    if ":" not in target:
        return None
    # Handle user@host:/path and user@host:path
    return target.split(":")[0]


def _build_ssh_cmd(ssh_key: Path | None, port: int | None) -> list[str]:
    """Build the SSH sub-command parts.

    Includes ControlMaster options so the remote rsync check and the actual
    rsync transfer share a single SSH connection (one auth prompt, not two).
    """
    parts = [
        "ssh",
        "-o", "ControlMaster=auto",
        "-o", "ControlPath=/tmp/onepace-ssh-%r@%h:%p",
        "-o", "ControlPersist=30",
    ]
    if port:
        parts.extend(["-p", str(port)])
    if ssh_key:
        parts.extend(["-i", str(ssh_key)])
    return parts


def check_remote_rsync(
    target: str, ssh_key: Path | None = None, port: int | None = None
) -> None:
    """Check that rsync is installed on the remote host.

    Skipped if the target is a local path (no ':' separator).
    Raises SyncError if rsync is not found on the remote.
    """
    remote_host = _parse_remote_host(target)
    if remote_host is None:
        return

    ssh_cmd = _build_ssh_cmd(ssh_key, port)
    cmd = [*ssh_cmd, remote_host, "which", "rsync"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as e:
        raise SyncError(
            f"SSH connection to '{remote_host}' timed out. "
            "Check that the host is reachable and SSH is configured."
        ) from e

    if result.returncode == 255:
        # SSH itself failed (connection refused, auth failure, host not found, etc.)
        stderr = result.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise SyncError(
            f"SSH connection to '{remote_host}' failed{detail}"
        )

    if result.returncode != 0 or not result.stdout.strip():
        raise SyncError(
            f"rsync is not installed on '{remote_host}'. "
            "Install it with: sudo apt install rsync (Debian/Ubuntu), "
            "sudo yum install rsync (RHEL/CentOS), or sudo pacman -S rsync (Arch)"
        )


def build_rsync_command(options: SyncOptions) -> list[str]:
    """Construct the rsync command from SyncOptions.

    Returns a list of command arguments suitable for subprocess.
    """
    cmd = ["rsync"]

    # -a: archive (recursive, preserves symlinks, permissions, times, group, owner, devices)
    # -h: human-readable sizes
    # -z: compress during transfer
    # --info=progress2: single-line overall progress
    cmd.extend(["-ahz", "--info=progress2"])

    if options.dry_run:
        cmd.append("--dry-run")

    if options.delete:
        cmd.append("--delete")

    if options.verbose:
        cmd.append("-v")

    if options.bwlimit:
        cmd.append(f"--bwlimit={options.bwlimit}")

    for pattern in options.exclude:
        cmd.append(f"--exclude={pattern}")

    # SSH options: always pass -e for remote targets so rsync uses the same
    # ControlMaster socket established by check_remote_rsync (one auth prompt).
    if _parse_remote_host(options.target) is not None:
        ssh_cmd = _build_ssh_cmd(options.ssh_key, options.port)
        cmd.extend(["-e", " ".join(ssh_cmd)])

    # Trailing slash on source syncs contents, not the directory itself
    source_str = str(options.source)
    if not source_str.endswith("/"):
        source_str += "/"

    cmd.append(source_str)
    cmd.append(options.target)

    return cmd


_RSYNC_ERROR_MESSAGES = {
    1: "Syntax or usage error in rsync command",
    2: "Protocol incompatibility",
    3: "Errors selecting input/output files or directories",
    5: "Error starting client-server protocol",
    10: "Error in socket I/O",
    11: "Error in file I/O",
    12: "Error in rsync protocol data stream",
    23: "Partial transfer due to errors",
    24: "Partial transfer due to vanished source files",
    25: "The --max-delete limit stopped deletions",
    30: "Timeout in data send/receive",
    255: "SSH connection failed. Check your target, SSH key, and port settings.",
}


def run_rsync(options: SyncOptions) -> int:
    """Execute rsync with the given options, streaming output to the terminal.

    Returns the rsync exit code (0 on success).
    Raises SyncError on non-zero exit with a descriptive message.
    """
    check_rsync_installed()
    cmd = build_rsync_command(options)

    # Let rsync handle its own progress display via inherited stdout/stderr.
    # --info=progress2 uses carriage returns for live updates which works
    # correctly when attached to a real TTY.
    result = subprocess.run(cmd)

    if result.returncode != 0:
        msg = _RSYNC_ERROR_MESSAGES.get(
            result.returncode,
            f"rsync exited with code {result.returncode}",
        )
        raise SyncError(msg)

    return result.returncode
