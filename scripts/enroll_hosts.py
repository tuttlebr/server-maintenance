#!/usr/bin/env python3
"""Idempotently enroll verified devices from the frontend-compatible CSV format."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

TRUE_VALUES = {"1", "true", "yes", "y", "on", "key", "passwordless"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "password"}
FINGERPRINT_RE = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")
REQUIRED_COLUMNS = {"name", "endpoint", "transport"}
SENSITIVE_FIELDS = {"password", "ssh_password", "become_password", "bootstrap_password"}


class EnrollmentError(RuntimeError):
    pass


class ApiError(EnrollmentError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _validation_detail(status: int, content: bytes) -> str:
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return f"HTTP {status}"
    if not isinstance(parsed, dict):
        return f"HTTP {status}"
    detail = parsed.get("detail")
    if isinstance(detail, str):
        return detail[:500]
    if isinstance(detail, list):
        messages = []
        for item in detail[:10]:
            if not isinstance(item, dict):
                continue
            location = ".".join(str(part) for part in item.get("loc", []) if part != "body")
            message = str(item.get("msg") or "invalid value")
            messages.append(f"{location}: {message}" if location else message)
        if messages:
            return "Validation failed: " + "; ".join(messages)
    return f"HTTP {status}"


def _sensitive_values(payload: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in SENSITIVE_FIELDS and isinstance(value, str) and value:
                values.add(value)
            else:
                values.update(_sensitive_values(value))
    elif isinstance(payload, list):
        for value in payload:
            values.update(_sensitive_values(value))
    return values


def _redact_sensitive(detail: str, payload: Any) -> str:
    for secret in sorted(_sensitive_values(payload), key=len, reverse=True):
        detail = detail.replace(secret, "[redacted]")
    return detail


@dataclass(frozen=True)
class CsvDevice:
    line_number: int
    payload: dict[str, Any]
    expected_fingerprint: str | None = None

    @property
    def name(self) -> str:
        return self.payload["name"]


class ApiClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = ""

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30,
        authenticated: bool = True,
    ) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if authenticated and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            content = exc.read()
            detail = _redact_sensitive(_validation_detail(exc.code, content), payload)
            raise ApiError(exc.code, detail) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise EnrollmentError(f"Fleet Manager API request failed: {exc}") from exc
        if not content:
            return None
        return json.loads(content)

    def wait_until_healthy(self, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        last_error = "not ready"
        while time.monotonic() < deadline:
            try:
                result = self._request("GET", "/api/health", authenticated=False, timeout=3)
                if result == {"status": "ok"}:
                    return
                last_error = f"unexpected health response: {result!r}"
            except EnrollmentError as exc:
                last_error = str(exc)
            time.sleep(1)
        raise EnrollmentError(f"Fleet Manager did not become healthy: {last_error}")

    def login(self) -> None:
        result = self._request(
            "POST",
            "/api/v2/auth/login",
            {"username": self.username, "password": self.password},
            authenticated=False,
        )
        self.token = str(result.get("access_token", ""))
        if not self.token:
            raise EnrollmentError("Fleet Manager login returned no access token")

    def list_devices(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v2/devices")

    def discover(self, device: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v2/devices/discover", device, timeout=45)

    def add(self, device: dict[str, Any], fingerprint: str | None) -> dict[str, Any]:
        approval = {"fingerprint": fingerprint} if fingerprint else None
        return self._request(
            "POST",
            "/api/v2/devices",
            {"device": device, "approval": approval},
            timeout=120,
        )


def _optional(row: dict[str, str], field: str, *, strip: bool = False) -> str | None:
    value = row.get(field, "")
    if value is None or value == "":
        return None
    return value.strip() if strip else value


def _parse_bool(value: str | None, line_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return True
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise EnrollmentError(
        f"CSV line {line_number}: unsupported passwordless_ssh value {value!r}"
    )


def read_devices(stream: TextIO) -> list[CsvDevice]:
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise EnrollmentError("Hosts CSV is empty")
    reader.fieldnames = [field.strip().lower().lstrip("\ufeff") for field in reader.fieldnames]
    duplicate_headers = sorted(
        {field for field in reader.fieldnames if reader.fieldnames.count(field) > 1}
    )
    if duplicate_headers:
        raise EnrollmentError(
            f"Hosts CSV contains duplicate columns: {', '.join(duplicate_headers)}"
        )
    missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
    if missing:
        raise EnrollmentError(f"Hosts CSV is missing columns: {', '.join(missing)}")

    devices: list[CsvDevice] = []
    names: set[str] = set()
    endpoints: set[str] = set()
    for line_number, raw_row in enumerate(reader, start=2):
        if None in raw_row:
            raise EnrollmentError(f"CSV line {line_number}: too many columns")
        row = {(key or "").strip().lower(): value or "" for key, value in raw_row.items()}
        if not any(value.strip() for value in row.values()):
            continue

        name = row.get("name", "").strip()
        endpoint = row.get("endpoint", "").strip()
        transport = row.get("transport", "").strip().lower()
        if not name or not endpoint:
            raise EnrollmentError(f"CSV line {line_number}: name and endpoint are required")
        if transport not in {"ssh", "reachy_daemon"}:
            raise EnrollmentError(
                f"CSV line {line_number}: unsupported transport {transport!r}"
            )
        if name in names:
            raise EnrollmentError(f"CSV line {line_number}: duplicate device name {name!r}")
        if endpoint in endpoints:
            raise EnrollmentError(f"CSV line {line_number}: duplicate endpoint {endpoint!r}")
        names.add(name)
        endpoints.add(endpoint)

        passwordless = _parse_bool(row.get("passwordless_ssh"), line_number)
        ssh_user = _optional(row, "ssh_user", strip=True)
        ssh_password = _optional(row, "ssh_password")
        if transport == "ssh" and not ssh_user:
            raise EnrollmentError(f"CSV line {line_number}: ssh_user is required for SSH")

        daemon_port: int | None = None
        if transport == "reachy_daemon":
            raw_port = row.get("daemon_port", "").strip() or "8000"
            try:
                daemon_port = int(raw_port)
            except ValueError as exc:
                raise EnrollmentError(
                    f"CSV line {line_number}: invalid daemon_port {raw_port!r}"
                ) from exc
            if not 1 <= daemon_port <= 65535:
                raise EnrollmentError(
                    f"CSV line {line_number}: daemon_port must be between 1 and 65535"
                )

        ssh_fingerprint = _optional(row, "ssh_fingerprint", strip=True)
        fingerprint_alias = _optional(row, "fingerprint", strip=True)
        if (
            ssh_fingerprint
            and fingerprint_alias
            and ssh_fingerprint != fingerprint_alias
        ):
            raise EnrollmentError(
                f"CSV line {line_number}: ssh_fingerprint and fingerprint disagree"
            )
        expected_fingerprint = ssh_fingerprint or fingerprint_alias
        if expected_fingerprint and not FINGERPRINT_RE.fullmatch(expected_fingerprint):
            raise EnrollmentError(
                f"CSV line {line_number}: invalid SSH SHA256 fingerprint"
            )

        devices.append(
            CsvDevice(
                line_number=line_number,
                payload={
                    "name": name,
                    "endpoint": endpoint,
                    "transport": transport,
                    "ssh_user": ssh_user,
                    "ssh_password": ssh_password,
                    "become_password": _optional(row, "become_password"),
                    "bootstrap_password": _optional(row, "bootstrap_password"),
                    "passwordless_ssh": passwordless,
                    "daemon_port": daemon_port,
                },
                expected_fingerprint=expected_fingerprint,
            )
        )

    if not devices:
        raise EnrollmentError("Hosts CSV contains no devices")
    return devices


def _fingerprint(encoded_key: str) -> str:
    try:
        key_blob = base64.b64decode(encoded_key.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EnrollmentError("known_hosts contains an invalid Ed25519 key") from exc
    digest = base64.b64encode(hashlib.sha256(key_blob).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


def known_host_fingerprints(path: Path, endpoint: str) -> set[str]:
    if not path.is_file():
        return set()
    try:
        result = subprocess.run(
            ["ssh-keygen", "-F", endpoint, "-f", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnrollmentError(f"Could not inspect known_hosts seed: {exc}") from exc
    if result.returncode not in {0, 1}:
        raise EnrollmentError("ssh-keygen could not read the known_hosts seed")

    fingerprints: set[str] = set()
    for line in result.stdout.splitlines():
        fields = line.strip().split()
        if not fields or fields[0].startswith("#"):
            continue
        if fields[0] == "@revoked":
            if len(fields) >= 4 and fields[2] == "ssh-ed25519":
                raise EnrollmentError(
                    f"The Ed25519 key for {endpoint} is marked revoked in known_hosts"
                )
            continue
        if fields[0].startswith("@"):
            continue
        if len(fields) >= 3 and fields[1] == "ssh-ed25519":
            fingerprints.add(_fingerprint(fields[2]))
    return fingerprints


def _device_drift(device: CsvDevice, existing: dict[str, Any]) -> list[str]:
    expected = device.payload
    checks: list[tuple[str, Any, Any]] = [
        ("endpoint", expected["endpoint"], existing.get("endpoint")),
        ("transport", expected["transport"], existing.get("transport")),
    ]
    if expected["transport"] == "ssh":
        checks.extend(
            [
                ("ssh_user", expected["ssh_user"], existing.get("ssh_user")),
                (
                    "passwordless_ssh",
                    expected["passwordless_ssh"],
                    existing.get("passwordless_ssh"),
                ),
            ]
        )
    else:
        checks.append(("daemon_port", expected["daemon_port"], existing.get("daemon_port")))
    return [field for field, wanted, actual in checks if wanted != actual]


def enroll_devices(
    devices: list[CsvDevice], client: ApiClient, known_hosts: Path, output: TextIO
) -> bool:
    existing_devices = client.list_devices()
    existing_by_name = {
        str(item.get("inventory_name") or item.get("name")): item
        for item in existing_devices
    }
    existing_by_endpoint = {
        str(item.get("endpoint")): item
        for item in existing_devices
        if item.get("endpoint")
    }
    added = 0
    skipped = 0
    failures: list[str] = []

    for device in devices:
        existing = existing_by_name.get(device.name)
        if existing is not None:
            drift = _device_drift(device, existing)
            if drift:
                failures.append(
                    f"{device.name}: already exists with different {', '.join(drift)}"
                )
            else:
                skipped += 1
                print(f"[hosts] {device.name}: already enrolled", file=output)
            continue

        endpoint_owner = existing_by_endpoint.get(device.payload["endpoint"])
        if endpoint_owner is not None:
            owner_name = str(
                endpoint_owner.get("inventory_name") or endpoint_owner.get("name")
            )
            failures.append(
                f"{device.name}: endpoint is already enrolled as {owner_name}"
            )
            continue

        try:
            if (
                device.payload["transport"] == "ssh"
                and not device.payload["passwordless_ssh"]
                and not device.payload["ssh_password"]
            ):
                raise EnrollmentError(
                    "ssh_password is required to enroll a new password-authenticated device"
                )
            discovery = client.discover(device.payload)
            if not discovery.get("reachable"):
                raise EnrollmentError(discovery.get("detail") or "device is unreachable")

            approved_fingerprint: str | None = None
            if device.payload["transport"] == "ssh":
                discovered = str(discovery.get("fingerprint") or "")
                if not FINGERPRINT_RE.fullmatch(discovered):
                    raise EnrollmentError("discovery returned no valid Ed25519 fingerprint")

                seed_fingerprints = known_host_fingerprints(
                    known_hosts, device.payload["endpoint"]
                )
                if device.expected_fingerprint and discovered != device.expected_fingerprint:
                    raise EnrollmentError(
                        "discovered fingerprint does not match ssh_fingerprint from CSV"
                    )
                if seed_fingerprints and discovered not in seed_fingerprints:
                    raise EnrollmentError(
                        "discovered fingerprint does not match the verified known_hosts seed"
                    )

                already_trusted = not bool(discovery.get("trust_required", True))
                externally_verified = (
                    discovered == device.expected_fingerprint
                    or discovered in seed_fingerprints
                )
                if not already_trusted and not externally_verified:
                    raise EnrollmentError(
                        f"fingerprint {discovered} needs independent verification; "
                        "add it to known_hosts or the ssh_fingerprint CSV column"
                    )
                approved_fingerprint = discovered

            added_device = client.add(device.payload, approved_fingerprint)
            existing_by_name[device.name] = added_device
            existing_by_endpoint[device.payload["endpoint"]] = added_device
            added += 1
            print(f"[hosts] {device.name}: enrolled", file=output)
        except EnrollmentError as exc:
            failures.append(f"{device.name}: {exc}")

    print(
        f"[hosts] Sync complete: {added} added, {skipped} already enrolled, "
        f"{len(failures)} failed",
        file=output,
    )
    for failure in failures:
        print(f"[hosts] ERROR: {failure}", file=output)
    return not failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--known-hosts",
        type=Path,
        default=Path(os.environ.get("SSH_KNOWN_HOSTS_SEED_FILE", "/run/fleet-known-hosts-seed")),
        help="Verified host-key seed used to authorize unattended enrollment",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("FLEET_API_BASE_URL", "http://127.0.0.1:8000"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        devices = read_devices(sys.stdin)
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not password:
            raise EnrollmentError("ADMIN_PASSWORD is unavailable in the web container")
        client = ApiClient(
            args.api_base_url,
            os.environ.get("ADMIN_USERNAME", "admin"),
            password,
        )
        client.wait_until_healthy()
        client.login()
        return 0 if enroll_devices(devices, client, args.known_hosts, sys.stdout) else 1
    except EnrollmentError as exc:
        print(f"[hosts] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
