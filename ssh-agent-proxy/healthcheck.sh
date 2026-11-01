#!/bin/sh
set -eu

# Query through the listener, including the host-side forwarding path. A socket
# inode alone survives an agent failure and cannot establish readiness.
export SSH_AUTH_SOCK=/run/fleet-agent/agent.sock
if ! identities=$(timeout 3 ssh-add -L 2>/dev/null); then
    echo "Fleet SSH agent unavailable, unresponsive, or empty; run make repair-ssh on the host." >&2
    exit 1
fi
if ! printf '%s\n' "$identities" | awk '
    NF { count++; if ($1 != "ssh-ed25519" || NF < 2) invalid = 1 }
    END { exit (count != 1 || invalid) }
'; then
    echo "Fleet SSH agent must contain exactly one Ed25519 identity." >&2
    exit 1
fi
