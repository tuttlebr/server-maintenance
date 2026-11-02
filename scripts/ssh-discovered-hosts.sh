#!/usr/bin/env bash
# Discover hosts on the requested subnet, then offer interactive SSH sessions.
# Compatible with the Bash 3.2 supplied with macOS.
set -euo pipefail

usage() {
    printf 'Usage: %s [SSH_USERNAME] [IPV4_SUBNET]\n' "${0##*/}"
    printf 'Scan an IPv4 subnet (/24 or smaller), then connect, skip, or quit at each host.\n'
    printf 'Default subnet: 10.110.16.0/24.\n'
    printf 'If you omit SSH_USERNAME, the script prompts for it.\n'
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
if (( $# > 2 )); then
    usage >&2
    exit 2
fi
if [[ ! -t 0 || ! -t 1 ]]; then
    printf 'Run this script in an interactive terminal.\n' >&2
    exit 1
fi
for required_command in nmap ssh awk mktemp python3; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$required_command" >&2
        exit 1
    fi
done

ssh_user="${1:-}"
if [[ -z "$ssh_user" ]]; then
    read -r -p 'SSH username: ' ssh_user || exit 0
fi
case "$ssh_user" in
    ''|-*|*[[:space:]]*)
        printf 'Enter a username without spaces or a leading dash.\n' >&2
        exit 2
        ;;
esac

subnet=${2:-10.110.16.0/24}
if ! subnet=$(python3 - "$subnet" <<'PY'
import ipaddress
import sys
try:
    network = ipaddress.ip_network(sys.argv[1], strict=True)
    if network.version != 4 or network.num_addresses > 256:
        raise ValueError()
except ValueError:
    print('Use an IPv4 subnet with at most 256 addresses (/24 or smaller).', file=sys.stderr)
    sys.exit(2)
print(network)
PY
); then
    exit 2
fi
scan_file=$(mktemp "${TMPDIR:-/tmp}/ssh-discovered.XXXXXX")
trap 'rm -f "$scan_file"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '\nDiscovering hosts on %s...\n' "$subnet"
if ! nmap --unprivileged -sn -n -PS22 --max-rate 10 -oG "$scan_file" "$subnet"; then
    printf 'Nmap failed. No SSH connections attempted.\n' >&2
    exit 1
fi

hosts=$(awk '$1 == "Host:" && $(NF-1) == "Status:" && $NF == "Up" { print $2 }' "$scan_file")
if [[ -z "$hosts" ]]; then
    printf '\nNo hosts responded. Filtering can hide active hosts.\n'
    exit 0
fi

host_count=$(printf '%s\n' "$hosts" | awk 'END { print NR }')
printf '\nFound %s responding hosts. SSH may still be unavailable on some hosts.\n' "$host_count"
printf 'After connecting, run hostname to identify the machine.\n'
printf 'Run exit to return here. Choose q at the next prompt to stop.\n'

index=0
# Keep the host list on descriptor 3 so SSH can read your terminal normally.
while IFS= read -r ip <&3; do
    index=$((index + 1))
    while true; do
        printf '\n[%s/%s] %s@%s: [Enter/c] connect, [s] skip, [q] quit: ' \
            "$index" "$host_count" "$ssh_user" "$ip"
        read -r choice || exit 0
        case "$choice" in
            ''|c|C) break ;;
            s|S) continue 2 ;;
            q|Q) exit 0 ;;
            *) printf 'Choose Enter, c, s, or q.\n' ;;
        esac
    done

    # Let SSH handle passwords and host-key verification directly.
    # Disable forwarding and local commands when trying unfamiliar hosts.
    if ssh \
        -o ConnectTimeout=5 \
        -o ConnectionAttempts=1 \
        -o NumberOfPasswordPrompts=1 \
        -o StrictHostKeyChecking=ask \
        -o ForwardAgent=no \
        -o ForwardX11=no \
        -o ClearAllForwardings=yes \
        -o PermitLocalCommand=no \
        -l "$ssh_user" "$ip" 3<&-; then
        printf '\nSSH session ended for %s.\n' "$ip"
    else
        ssh_status=$?
        printf '\nSSH ended for %s with status %s.\n' "$ip" "$ssh_status"
    fi
done 3<<< "$hosts"

printf '\nFinished all discovered hosts.\n'
