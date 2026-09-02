"""Transport and privileged execution for the Host Agent (WP-4).

Kept apart from ``host_agent`` on purpose. Everything that decides *whether* to
act lives there and runs anywhere; this file owns the two things that need a
real Linux host — the unix socket with its ownership and mode, and the actual
``nmcli`` / ``systemctl`` / ``reboot`` calls.

The split is what lets the refusal logic be tested exhaustively without a
Raspberry Pi, and it keeps the privileged surface small enough to read in one
sitting.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from host_agent import MAX_REQUEST_BYTES, HostAgent

#: Where CORE looks for us. /run is tmpfs, so a stale socket cannot outlive a
#: reboot and be mistaken for a live agent.
DEFAULT_SOCKET_PATH = Path("/run/rosy/host-agent.sock")

#: root owns it, the rosy group may connect, nobody else can see it.
SOCKET_MODE = 0o660


class PeerRejected(Exception):
    """The connecting process is not the one this agent serves."""


# --- who is on the other end ----------------------------------------------


def read_peer_credentials(connection: socket.socket) -> tuple[int, int, int]:
    """Return the peer's (pid, uid, gid) as reported by the kernel.

    SO_PEERCRED is filled in by the kernel at connect time, so a client cannot
    forge it — which is the whole reason this is a unix socket rather than a
    loopback port. There is no equivalent for TCP, and inventing a shared token
    to stand in for it would put a secret back in the image.
    """
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", raw)
    return pid, uid, gid


def peer_is_allowed(uid: int, *, expected_uid: int) -> bool:
    """Whether a connecting uid may issue commands.

    Split out as a pure function so the policy is testable without a socket.

    What this proves is "a process running as expected_uid", not "CORE". With
    no user-namespace remapping the container's uid 1000 is the host's uid
    1000, which on Raspberry Pi OS Lite is the ordinary login account — so the
    image build has to give CORE a dedicated system uid before this check means
    what the contract says it means.
    """
    return uid == expected_uid


def check_peer_credentials(connection: socket.socket, *, expected_uid: int) -> tuple[int, int, int]:
    """Read the peer identity and refuse anyone else."""
    pid, uid, gid = read_peer_credentials(connection)
    if not peer_is_allowed(uid, expected_uid=expected_uid):
        raise PeerRejected(f"uid {uid} (pid {pid}) may not use the host agent")
    return pid, uid, gid


# --- the socket ------------------------------------------------------------


def create_socket(path: Path, *, group_gid: int | None = None) -> socket.socket:
    """Bind the listening socket with its ownership and mode set.

    Order matters: the mode is applied before anything can connect, so there is
    no window in which the socket exists world-writable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    os.chmod(path, SOCKET_MODE)
    if group_gid is not None:
        os.chown(path, 0, group_gid)
    server.listen(8)
    return server


def _read_line(connection: socket.socket) -> bytes | None:
    """Read one newline-terminated request, bounded.

    The socket is reachable by anything running as ROSY_UID, so a client that
    never sends a newline must not be able to make the agent allocate until the
    device dies.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            return b"".join(chunks) or None
        chunks.append(chunk)
        total += len(chunk)
        if b"\n" in chunk:
            return b"".join(chunks).split(b"\n", 1)[0]
        if total > MAX_REQUEST_BYTES:
            return b"".join(chunks)[: MAX_REQUEST_BYTES + 1]


def serve_forever(
    agent: HostAgent,
    *,
    path: Path = DEFAULT_SOCKET_PATH,
    expected_uid: int,
    group_gid: int | None = None,
    should_continue: Callable[[], bool] = lambda: True,
) -> None:  # pragma: no cover - exercised on the device, not in the suite
    """Accept one request per connection, forever."""
    server = create_socket(path, group_gid=group_gid)
    try:
        while should_continue():
            connection, _ = server.accept()
            with connection:
                try:
                    check_peer_credentials(connection, expected_uid=expected_uid)
                except PeerRejected:
                    # Say nothing: a caller that is not permitted learns only
                    # that the connection closed.
                    continue

                line = _read_line(connection)
                if line is None:
                    continue
                connection.sendall(agent.handle_line(line).encode("utf-8") + b"\n")
    finally:
        server.close()
        path.unlink(missing_ok=True)


# --- the privileged actions ------------------------------------------------

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


def _run(argv: Sequence[str]) -> subprocess.CompletedProcess:
    """Execute with an argument list. Never a shell, never a string."""
    return subprocess.run(list(argv), capture_output=True, text=True, check=False)


@dataclass
class SubprocessCommands:
    """The real actions, as argument lists.

    The runner is injectable so the tests can assert on the argv this builds
    without executing anything — which is the only part of the privileged
    surface a test can meaningfully check off-device.
    """

    release_cli: str = "rosy-release"
    runner: Runner = _run

    def _json_or_text(self, result: subprocess.CompletedProcess, argv: Sequence[str]) -> dict:
        if result.returncode != 0:
            raise RuntimeError(f"{argv[0]} exited {result.returncode}: {result.stderr.strip()}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"output": result.stdout.strip()}

    def network_status(self) -> dict:
        argv = ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show", "--active"]
        return self._json_or_text(self.runner(argv), argv)

    def apply_network_profile(self, profile_id: str) -> dict:
        argv = ["nmcli", "connection", "up", "id", profile_id]
        return self._json_or_text(self.runner(argv), argv)

    def release_status(self) -> dict:
        argv = [self.release_cli, "status", "--json"]
        return self._json_or_text(self.runner(argv), argv)

    def install_release(self, release_id: str) -> dict:
        argv = [self.release_cli, "install", "--release-id", release_id, "--json"]
        return self._json_or_text(self.runner(argv), argv)

    def rollback_release(self) -> dict:
        argv = [self.release_cli, "rollback", "--json"]
        return self._json_or_text(self.runner(argv), argv)

    def clear_recovery_hold(self) -> dict:
        argv = [self.release_cli, "clear-hold", "--json"]
        return self._json_or_text(self.runner(argv), argv)

    def service_status(self, unit: str) -> dict:
        argv = ["systemctl", "is-active", unit]
        result = self.runner(argv)
        # is-active exits non-zero for a stopped unit, which is an answer
        # rather than a failure.
        return {"unit": unit, "active": result.stdout.strip() or "unknown"}

    def reboot(self) -> dict:
        argv = ["systemctl", "reboot"]
        return self._json_or_text(self.runner(argv), argv)
