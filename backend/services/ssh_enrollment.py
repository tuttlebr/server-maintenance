import base64
import binascii
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from backend.config import settings


SSH_COMMAND_TIMEOUT_SECONDS = 15
SSH_KEYSCAN_TIMEOUT_SECONDS = 8
_KNOWN_HOSTS_LOCK = threading.Lock()


class SshEnrollmentError(RuntimeError):
    pass


def _fingerprint(key_type: str, encoded_key: str) -> str:
    if key_type != "ssh-ed25519":
        raise SshEnrollmentError(f"Unsupported SSH host key type: {key_type}")
    try:
        key_blob = base64.b64decode(encoded_key.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SshEnrollmentError("SSH host returned an invalid public key") from exc
    digest = base64.b64encode(hashlib.sha256(key_blob).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


def _parse_public_key(line: str) -> tuple[str, str]:
    fields = line.strip().split()
    if len(fields) < 2:
        raise SshEnrollmentError("SSH host returned a malformed public key")
    if fields[0].startswith("#"):
        raise SshEnrollmentError("SSH host returned no usable public key")
    if fields[0] == "ssh-ed25519":
        return fields[0], fields[1]
    if len(fields) >= 3 and fields[1] == "ssh-ed25519":
        return fields[1], fields[2]
    raise SshEnrollmentError("SSH host did not return an ED25519 public key")


def initialize_known_hosts() -> Path:
    known_hosts = settings.ssh_known_hosts_file
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    known_hosts.parent.chmod(0o700)
    if not known_hosts.exists():
        seed = settings.ssh_known_hosts_seed_file
        if seed and seed.is_file():
            shutil.copyfile(seed, known_hosts)
        else:
            known_hosts.touch()
    known_hosts.chmod(0o600)
    return known_hosts


def _scan_host_key(address: str) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["ssh-keyscan", "-T", "5", "-t", "ed25519", address],
            capture_output=True,
            text=True,
            timeout=SSH_KEYSCAN_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SshEnrollmentError(f"Could not reach SSH at {address}: {exc}") from exc

    key_lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not key_lines:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise SshEnrollmentError(f"No ED25519 host key received from {address}{suffix}")

    key_type, encoded_key = _parse_public_key(key_lines[0])
    return {
        "address": address,
        "key_type": key_type,
        "public_key": encoded_key,
        "fingerprint": _fingerprint(key_type, encoded_key),
        "known_hosts_line": f"{address} {key_type} {encoded_key}",
    }


def _trusted_keys(address: str) -> set[tuple[str, str]]:
    known_hosts = initialize_known_hosts()
    result = subprocess.run(
        ["ssh-keygen", "-F", address, "-f", str(known_hosts)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    keys = set()
    for line in result.stdout.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            keys.add(_parse_public_key(line))
        except SshEnrollmentError:
            continue
    return keys


def preview_host_key(hostname: str, address: str) -> dict:
    try:
        key = _scan_host_key(address)
        trusted_keys = _trusted_keys(address)
        current = (key["key_type"], key["public_key"])
        if current in trusted_keys:
            trust_status = "trusted"
        elif trusted_keys:
            trust_status = "changed"
        else:
            trust_status = "new"
        return {
            "hostname": hostname,
            "address": address,
            "reachable": True,
            "trust_status": trust_status,
            "fingerprint": key["fingerprint"],
            "key_type": key["key_type"],
            "detail": "",
        }
    except SshEnrollmentError as exc:
        return {
            "hostname": hostname,
            "address": address,
            "reachable": False,
            "trust_status": "unavailable",
            "fingerprint": "",
            "key_type": "",
            "detail": str(exc),
        }


def _agent_environment() -> dict[str, str]:
    environment = {
        "HOME": str(Path.home()),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }
    socket_path = os.environ.get("SSH_AUTH_SOCK")
    if socket_path:
        environment["SSH_AUTH_SOCK"] = socket_path
    return environment


def get_agent_status() -> dict:
    socket_path = os.environ.get("SSH_AUTH_SOCK", "")
    if not socket_path:
        return {
            "ready": False,
            "fingerprints": [],
            "public_keys": [],
            "detail": "SSH_AUTH_SOCK is not configured in the web container",
        }
    if not Path(socket_path).is_socket():
        return {
            "ready": False,
            "fingerprints": [],
            "public_keys": [],
            "detail": f"The forwarded SSH agent socket is unavailable at {socket_path}",
        }

    try:
        result = subprocess.run(
            ["ssh-add", "-L"],
            capture_output=True,
            text=True,
            timeout=5,
            env=_agent_environment(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ready": False,
            "fingerprints": [],
            "public_keys": [],
            "detail": f"Could not query the forwarded SSH agent: {exc}",
        }

    public_keys = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    fingerprints = []
    for public_key in public_keys:
        try:
            key_type, encoded_key = _parse_public_key(public_key)
            fingerprints.append(_fingerprint(key_type, encoded_key))
        except SshEnrollmentError:
            continue

    if result.returncode != 0:
        detail = result.stderr.strip() or "The forwarded SSH agent has no identities"
    elif len(public_keys) != 1:
        detail = (
            "The dedicated fleet SSH agent must contain exactly one key; "
            f"found {len(public_keys)}"
        )
    elif len(fingerprints) != 1:
        detail = "The dedicated fleet SSH agent must contain one ED25519 key"
    else:
        detail = "Dedicated fleet SSH agent is ready"

    return {
        "ready": result.returncode == 0 and len(public_keys) == 1 and len(fingerprints) == 1,
        "fingerprints": fingerprints,
        "public_keys": public_keys,
        "detail": detail,
    }


def trust_host_key(address: str, expected_fingerprint: str) -> dict[str, str]:
    current = _scan_host_key(address)
    if current["fingerprint"] != expected_fingerprint:
        raise SshEnrollmentError(
            f"Host key for {address} changed during enrollment: expected "
            f"{expected_fingerprint}, received {current['fingerprint']}"
        )

    known_hosts = initialize_known_hosts()
    with _KNOWN_HOSTS_LOCK:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".known_hosts.",
            dir=str(known_hosts.parent),
        )
        os.close(file_descriptor)
        temporary = Path(temporary_name)
        backup = Path(f"{temporary}.old")
        try:
            shutil.copyfile(known_hosts, temporary)
            subprocess.run(
                ["ssh-keygen", "-R", address, "-f", str(temporary)],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            with temporary.open("a") as stream:
                stream.write(current["known_hosts_line"] + "\n")
            temporary.chmod(0o600)
            temporary.replace(known_hosts)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise SshEnrollmentError(f"Could not update SSH trust for {address}: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)
    return current


def _ssh_base_command(address: str, remote_user: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={settings.ssh_known_hosts_file}",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "LogLevel=ERROR",
        f"{remote_user}@{address}",
    ]


def _result_detail(result: subprocess.CompletedProcess) -> str:
    lines = (result.stderr or result.stdout or "").strip().splitlines()
    return lines[-1] if lines else "SSH authentication failed"


def test_public_key_auth(address: str, remote_user: str) -> tuple[bool, str]:
    command = _ssh_base_command(address, remote_user)
    command[1:1] = [
        "-o",
        "BatchMode=yes",
        "-o",
        "PreferredAuthentications=publickey",
        "-o",
        "PasswordAuthentication=no",
    ]
    try:
        result = subprocess.run(
            [*command, "true"],
            capture_output=True,
            text=True,
            timeout=SSH_COMMAND_TIMEOUT_SECONDS,
            env=_agent_environment(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"SSH key authentication check failed: {exc}"
    if result.returncode == 0:
        return True, "Fleet SSH key authentication succeeded"
    return False, _result_detail(result)


def test_password_auth(address: str, remote_user: str, password: str) -> tuple[bool, str]:
    environment = _agent_environment()
    environment["SSHPASS"] = password
    base_command = _ssh_base_command(address, remote_user)
    command = [
        "sshpass",
        "-e",
        *base_command[:-1],
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        "PubkeyAuthentication=no",
        base_command[-1],
        "true",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=SSH_COMMAND_TIMEOUT_SECONDS,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"SSH password authentication check failed: {exc}"
    if result.returncode == 0:
        return True, "SSH password authentication succeeded"
    return False, _result_detail(result)


def install_agent_key(
    address: str,
    remote_user: str,
    bootstrap_password: str,
    public_key: str,
) -> tuple[bool, str]:
    environment = _agent_environment()
    environment["SSHPASS"] = bootstrap_password
    base_command = _ssh_base_command(address, remote_user)
    remote_command = (
        'umask 077; mkdir -p "$HOME/.ssh"; touch "$HOME/.ssh/authorized_keys"; '
        'IFS= read -r fleet_key; grep -qxF "$fleet_key" "$HOME/.ssh/authorized_keys" '
        '|| printf "%s\\n" "$fleet_key" >> "$HOME/.ssh/authorized_keys"'
    )
    command = [
        "sshpass",
        "-e",
        *base_command[:-1],
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        "PubkeyAuthentication=no",
        base_command[-1],
        remote_command,
    ]
    try:
        result = subprocess.run(
            command,
            input=public_key + "\n",
            capture_output=True,
            text=True,
            timeout=SSH_COMMAND_TIMEOUT_SECONDS,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not install the fleet SSH key: {exc}"
    if result.returncode == 0:
        return True, "Installed the fleet SSH key for the remote user"
    return False, _result_detail(result)
