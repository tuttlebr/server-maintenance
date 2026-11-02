#!/usr/bin/env python3
"""Locate an IPv4 endpoint by its previously trusted ED25519 host key.

Runs on the controller. Never receives credentials or modifies known_hosts.
SSH authentication is a separate Ansible task after a unique key match.
"""

import argparse
import base64
import hashlib
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import socket
import subprocess
import xml.etree.ElementTree as ET


NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,252}\Z")


def run(argv, timeout=8):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def subnet_value(value):
    if not value:
        return None
    network = ipaddress.ip_network(value, strict=True)
    if network.version != 4 or network.num_addresses > 256:
        raise ValueError("Use an IPv4 subnet with at most 256 addresses (/24 or smaller).")
    return network


def trusted_keys(known_hosts, aliases, port):
    if not Path(known_hosts).is_file():
        raise ValueError("The trusted known_hosts file is missing. Restore the existing trust record first.")
    preferred_keys = set()
    for alias in dict.fromkeys(aliases):
        lookup = alias if port == 22 else f"[{alias}]:{port}"
        result = run(["ssh-keygen", "-F", lookup, "-f", known_hosts])
        if result.returncode not in (0, 1):
            raise ValueError("Could not read the existing SSH trust record.")
        keys = set()
        for line in result.stdout.splitlines():
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            if fields[0] == "@revoked":
                raise ValueError("The host has a revoked SSH key. Review its trust record first.")
            if len(fields) >= 3 and fields[1] == "ssh-ed25519":
                keys.add(fields[2])
        # Keep endpoint trust authoritative, but check every relevant alias for
        # revocation before allowing a probe or forwarding credentials.
        if not preferred_keys:
            preferred_keys = keys
    if preferred_keys:
        return preferred_keys
    raise ValueError("No trusted ED25519 key exists for this endpoint or inventory hostname. Restore its trust record first.")


def resolve(names):
    addresses = set()
    for name in dict.fromkeys(names):
        try:
            addresses.update(item[4][0] for item in socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM))
        except socket.gaierror:
            continue
    return sorted(addresses, key=ipaddress.ip_address)


def key_match(address, port, trusted):
    try:
        result = run(["ssh-keyscan", "-T", "3", "-p", str(port), "-t", "ed25519", address], timeout=5)
    except subprocess.TimeoutExpired:
        return None
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[1] == "ssh-ed25519" and fields[2] in trusted:
            return {"ip": address, "key": fields[2]}
    return None


def scan(network, port):
    result = run(["nmap", "--unprivileged", "-sn", "-n", f"-PS{port}", "--max-rate", "10",
                  "-oX", "-", str(network)], timeout=180)
    if result.returncode:
        raise ValueError("Nmap discovery failed. Check controller network access and Nmap availability.")
    addresses = set()
    for host in ET.fromstring(result.stdout).findall("host"):
        status = host.find("status")
        if status is None or status.get("state") != "up":
            continue
        for entry in host.findall("address"):
            if entry.get("addrtype") == "ipv4":
                address = ipaddress.IPv4Address(entry.get("addr"))
                if address not in network:
                    raise ValueError("Nmap returned an address outside the requested subnet.")
                addresses.add(str(address))
    return sorted(addresses, key=ipaddress.ip_address)


def discover(hostname, endpoint, known_hosts, subnet="", port=22):
    if not all(NAME_RE.fullmatch(name) for name in (hostname, endpoint)):
        raise ValueError("Use a valid inventory hostname and an IPv4 address or DNS endpoint.")
    if not 1 <= port <= 65535:
        raise ValueError("The SSH port must be between 1 and 65535.")
    network = subnet_value(subnet)
    trusted = trusted_keys(known_hosts, [endpoint, hostname], port)
    addresses = resolve([endpoint, hostname])
    source = "configured endpoint or DNS"

    def matches(candidates):
        # Limit simultaneous key probes. No authentication is attempted here.
        with ThreadPoolExecutor(max_workers=4) as pool:
            return [item for item in pool.map(lambda ip: key_match(ip, port, trusted), candidates) if item]

    found = matches(addresses)
    if not found and network is not None:
        candidates = [ip for ip in scan(network, port) if ip not in addresses]
        addresses.extend(candidates)
        found = matches(candidates)
        source = "subnet discovery"
    result = {"status": "not_found", "candidate_ip": None, "candidate_ips": [item["ip"] for item in found],
              "source": source, "probed_addresses": len(addresses), "subnet": str(network) if network else None,
              "detail": "No matching host key found. The host may be offline, filtered, outside the search range, or reinstalled."}
    if not found and network is None:
        result["detail"] += " Supply a subnet to search beyond DNS."
    if len(found) > 1:
        result.update(status="ambiguous", detail="Multiple IPs present the trusted key. These may be multiple interfaces or cloned keys; no address was selected.")
    elif found:
        match = found[0]
        digest = hashlib.sha256(base64.b64decode(match["key"], validate=True)).digest()
        result.update(status="candidate", candidate_ip=match["ip"],
                      fingerprint="SHA256:" + base64.b64encode(digest).decode().rstrip("="),
                      pinned_key=f"fleet-ip-discovery ssh-ed25519 {match['key']}\n",
                      detail="The trusted host key matched. SSH authentication must still be verified.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--known-hosts", required=True)
    parser.add_argument("--subnet", default="")
    parser.add_argument("--port", type=int, default=22)
    args = parser.parse_args()
    try:
        result = discover(args.hostname, args.endpoint, args.known_hosts, args.subnet, args.port)
    except (OSError, ValueError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        # Never include subprocess output or local configuration contents.
        detail = str(exc) if isinstance(exc, ValueError) else "Discovery could not complete. Check controller tools, network access, and the trust file."
        result = {"status": "error", "candidate_ip": None, "candidate_ips": [], "detail": detail}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
