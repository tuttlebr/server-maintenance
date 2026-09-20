#!/usr/bin/env bash

set -euo pipefail
umask 077

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"

COMMAND="${1:-start}"
SSH_DIR_INPUT="${FLEET_SSH_DIR:-$PROJECT_ROOT/.fleet-ssh}"
KEY_PATH_INPUT="${FLEET_SSH_KEY_PATH:-$HOME/.ssh/fleet-management-key}"
HOSTS_CSV_INPUT="${FLEET_HOSTS_CSV-$PROJECT_ROOT/hosts.csv}"
ENV_FILE="$PROJECT_ROOT/.env"

PREPARE_LOCK_HELD=0
KEY_CHECK_TEMP=""
HOSTS_CSV_EXPLICIT=0
if [[ -n "${FLEET_HOSTS_CSV+x}" ]]; then
    HOSTS_CSV_EXPLICIT=1
fi

log() {
    printf '[fleet] %s\n' "$*"
}

die() {
    printf '[fleet] ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: scripts/start.sh [start|prepare|enroll-hosts|status]

  start         Prepare SSH, start the Compose stack, and sync hosts.csv.
  prepare       Create/reuse the fleet key, agent socket, and known_hosts seed.
  enroll-hosts  Prepare SSH and sync hosts.csv into an already-running stack.
  status        Show the dedicated SSH agent status.

Environment overrides:
  FLEET_SSH_DIR       Agent state directory (default: .fleet-ssh).
  FLEET_SSH_KEY_PATH  Dedicated private key (default: ~/.ssh/fleet-management-key).
  FLEET_HOSTS_CSV     Device CSV path; set to an empty string to skip enrollment.
EOF
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

absolute_from_root() {
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf '%s/%s\n' "$PROJECT_ROOT" "$1" ;;
    esac
}

path_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}

path_owner() {
    stat -c '%u' "$1" 2>/dev/null || stat -f '%u' "$1"
}

validate_private_directory() {
    local path="$1" label="$2" mode owner
    mode="$(path_mode "$path")" || die "Could not inspect $label permissions: $path"
    owner="$(path_owner "$path")" || die "Could not inspect $label owner: $path"
    [[ "$owner" == "$(id -u)" ]] || die "$label must be owned by the current user: $path"
    [[ -w "$path" && -x "$path" ]] || die "$label must be writable and searchable: $path"
    case "$mode" in
        *00) ;;
        *) die "$label must not be accessible by group or other users: $path (mode $mode)" ;;
    esac
}

resolve_paths() {
    local create_state="${1:-1}" state_created=0
    SSH_DIR="$(absolute_from_root "$SSH_DIR_INPUT")"
    KEY_PATH="$(absolute_from_root "$KEY_PATH_INPUT")"
    HOSTS_CSV=""
    if [[ -n "$HOSTS_CSV_INPUT" ]]; then
        HOSTS_CSV="$(absolute_from_root "$HOSTS_CSV_INPUT")"
    fi

    if [[ -L "$SSH_DIR" ]]; then
        die "FLEET_SSH_DIR must not be a symbolic link: $SSH_DIR"
    fi
    if [[ -e "$SSH_DIR" && ! -d "$SSH_DIR" ]]; then
        die "FLEET_SSH_DIR is not a directory: $SSH_DIR"
    fi
    if [[ "$create_state" == "1" ]]; then
        if [[ ! -d "$SSH_DIR" ]]; then
            mkdir -p "$SSH_DIR"
            state_created=1
        fi
        if [[ "$state_created" == "1" || "$SSH_DIR" == "$PROJECT_ROOT/.fleet-ssh" ]]; then
            chmod 700 "$SSH_DIR"
        fi
    elif [[ ! -d "$SSH_DIR" ]]; then
        die "Fleet SSH state directory is unavailable: $SSH_DIR"
    fi
    validate_private_directory "$SSH_DIR" "Fleet SSH state directory"
    SSH_DIR="$(CDPATH= cd -- "$SSH_DIR" && pwd -P)"
    SOCKET_PATH="$SSH_DIR/agent.sock"
    if (( $(LC_ALL=C printf '%s' "$SOCKET_PATH" | wc -c) > 100 )); then
        die "Agent socket path is too long; set FLEET_SSH_DIR to a shorter private directory"
    fi
    AGENT_PID_FILE="$SSH_DIR/agent.pid"
    KNOWN_HOSTS_PATH="$SSH_DIR/known_hosts"
}

ensure_key() {
    local key_dir key_dir_created=0 private_fingerprint public_fingerprint pub_tmp pub_identity pub_lines
    key_dir="$(dirname "$KEY_PATH")"

    if [[ ! -d "$key_dir" ]]; then
        mkdir -p "$key_dir"
        key_dir_created=1
    fi
    if [[ "$key_dir_created" == "1" || "$key_dir" == "$HOME/.ssh" ]]; then
        chmod 700 "$key_dir"
    fi
    validate_private_directory "$key_dir" "Fleet key directory"

    if [[ -L "$KEY_PATH" || -L "$KEY_PATH.pub" ]]; then
        die "Fleet key files must not be symbolic links: $KEY_PATH"
    fi
    if [[ -e "$KEY_PATH" && ! -f "$KEY_PATH" ]]; then
        die "Fleet private key is not a regular file: $KEY_PATH"
    fi
    if [[ -e "$KEY_PATH.pub" && ! -f "$KEY_PATH.pub" ]]; then
        die "Fleet public key is not a regular file: $KEY_PATH.pub"
    fi
    if [[ ! -f "$KEY_PATH" && -f "$KEY_PATH.pub" ]]; then
        die "Public key exists without its private key: $KEY_PATH.pub"
    fi

    if [[ ! -f "$KEY_PATH" ]]; then
        log "Creating dedicated Ed25519 key at $KEY_PATH"
        log "Choose a strong passphrase; ssh-add will cache it in the dedicated agent."
        ssh-keygen -t ed25519 -a 100 -f "$KEY_PATH" -C fleet-management
    elif [[ ! -f "$KEY_PATH.pub" ]]; then
        log "Rebuilding missing public key $KEY_PATH.pub"
        pub_tmp="$(mktemp "$key_dir/.fleet-management-key.pub.XXXXXX")"
        if ! ssh-keygen -y -f "$KEY_PATH" >"$pub_tmp"; then
            rm -f "$pub_tmp"
            die "Could not rebuild the fleet public key"
        fi
        chmod 600 "$pub_tmp"
        mv "$pub_tmp" "$KEY_PATH.pub"
    fi

    chmod 600 "$KEY_PATH"
    chmod 644 "$KEY_PATH.pub"

    pub_lines="$(awk 'NF >= 2 && $1 !~ /^#/ { count++ } END { print count + 0 }' "$KEY_PATH.pub")"
    [[ "$pub_lines" == "1" ]] || die "Fleet public key must contain exactly one key: $KEY_PATH.pub"
    pub_identity="$(awk 'NF >= 2 && $1 !~ /^#/ { print $1 " " $2 }' "$KEY_PATH.pub")"
    [[ "$pub_identity" == ssh-ed25519\ * ]] || die "Fleet key must be Ed25519: $KEY_PATH.pub"
    KEY_CHECK_TEMP="$(mktemp "$key_dir/.fleet-private-key-check.XXXXXX")"
    cp "$KEY_PATH" "$KEY_CHECK_TEMP"
    chmod 600 "$KEY_CHECK_TEMP"
    private_fingerprint="$(ssh-keygen -lf "$KEY_CHECK_TEMP" 2>/dev/null | awk 'NR == 1 { print $2 }')" \
        || die "Fleet private key is invalid: $KEY_PATH"
    rm -f "$KEY_CHECK_TEMP"
    KEY_CHECK_TEMP=""
    public_fingerprint="$(ssh-keygen -lf "$KEY_PATH.pub" 2>/dev/null | awk 'NR == 1 { print $2 }')" \
        || die "Fleet public key is invalid: $KEY_PATH.pub"
    [[ -n "$private_fingerprint" && -n "$public_fingerprint" ]] || die "Fleet key pair is invalid: $KEY_PATH"
    [[ "$private_fingerprint" == "$public_fingerprint" ]] || die "Fleet private and public keys do not match: $KEY_PATH"

    FLEET_PUBLIC_IDENTITY="$pub_identity"
}

start_agent() {
    local agent_output agent_pid pid_tmp socket_status

    if [[ -L "$SOCKET_PATH" ]]; then
        die "Agent socket path must not be a symbolic link: $SOCKET_PATH"
    fi
    if [[ -e "$SOCKET_PATH" && ! -S "$SOCKET_PATH" ]]; then
        die "Refusing to replace a non-socket agent path: $SOCKET_PATH"
    fi
    if [[ -L "$AGENT_PID_FILE" || ( -e "$AGENT_PID_FILE" && ! -f "$AGENT_PID_FILE" ) ]]; then
        die "Agent PID path must be a regular, non-symlink file: $AGENT_PID_FILE"
    fi

    socket_status=2
    if [[ -S "$SOCKET_PATH" ]]; then
        set +e
        SSH_AUTH_SOCK="$SOCKET_PATH" ssh-add -l >/dev/null 2>&1
        socket_status=$?
        set -e
    fi

    case "$socket_status" in
        0|1)
            log "Reusing dedicated SSH agent socket."
            ;;
        2)
            if [[ -S "$SOCKET_PATH" ]]; then
                log "Replacing stale dedicated SSH agent socket."
                rm -f "$SOCKET_PATH"
            fi
            agent_output="$(ssh-agent -s -a "$SOCKET_PATH")"
            agent_pid="$(printf '%s\n' "$agent_output" | sed -n 's/^SSH_AGENT_PID=\([0-9][0-9]*\);.*$/\1/p' | head -n 1)"
            [[ -n "$agent_pid" && -S "$SOCKET_PATH" ]] || die "ssh-agent did not create the expected socket"
            pid_tmp="$(mktemp "$SSH_DIR/.agent.pid.XXXXXX")"
            printf '%s\n' "$agent_pid" >"$pid_tmp"
            chmod 600 "$pid_tmp"
            if ! mv "$pid_tmp" "$AGENT_PID_FILE"; then
                rm -f "$pid_tmp"
                die "Could not record the dedicated SSH agent PID"
            fi
            log "Started dedicated SSH agent (PID $agent_pid)."
            ;;
        *)
            die "Could not query the dedicated SSH agent (ssh-add exit $socket_status)"
            ;;
    esac
}

load_agent_identities() {
    local status
    set +e
    AGENT_IDENTITIES="$(SSH_AUTH_SOCK="$SOCKET_PATH" ssh-add -L 2>&1)"
    status=$?
    set -e
    case "$status" in
        0) ;;
        1) AGENT_IDENTITIES="" ;;
        *) die "Could not read identities from the dedicated SSH agent (ssh-add exit $status)" ;;
    esac
}

verify_agent_identity() {
    local identity_count matching_count
    load_agent_identities
    identity_count="$(printf '%s\n' "$AGENT_IDENTITIES" | awk 'NF > 0 { count++ } END { print count + 0 }')"
    matching_count="$(printf '%s\n' "$AGENT_IDENTITIES" | awk -v expected="$FLEET_PUBLIC_IDENTITY" 'NF >= 2 && ($1 " " $2) == expected { count++ } END { print count + 0 }')"

    [[ "$identity_count" == "1" && "$matching_count" == "1" ]]
}

ensure_agent_identity() {
    local identity_count
    load_agent_identities
    identity_count="$(printf '%s\n' "$AGENT_IDENTITIES" | awk 'NF > 0 { count++ } END { print count + 0 }')"

    if [[ "$identity_count" == "0" ]]; then
        log "Loading the fleet-management key into the dedicated agent."
        SSH_AUTH_SOCK="$SOCKET_PATH" ssh-add "$KEY_PATH"
    elif ! verify_agent_identity; then
        die "Dedicated SSH agent contains a different or additional identity; refusing to expose it to Fleet Manager"
    fi

    verify_agent_identity || die "Dedicated SSH agent must contain exactly the configured Ed25519 fleet key"
    log "Dedicated SSH agent contains exactly one fleet key."
}

release_prepare_lock() {
    local recorded_pid=""
    if [[ "$PREPARE_LOCK_HELD" != "1" ]]; then
        return
    fi
    if [[ -n "$KEY_CHECK_TEMP" && -f "$KEY_CHECK_TEMP" && ! -L "$KEY_CHECK_TEMP" ]]; then
        rm -f "$KEY_CHECK_TEMP"
        KEY_CHECK_TEMP=""
    fi
    if [[ -f "$PREPARE_LOCK_DIR/pid" && ! -L "$PREPARE_LOCK_DIR/pid" ]]; then
        recorded_pid="$(tr -d '[:space:]' <"$PREPARE_LOCK_DIR/pid")"
    fi
    if [[ "$recorded_pid" == "$$" ]]; then
        rm -f "$PREPARE_LOCK_DIR/pid"
        rmdir "$PREPARE_LOCK_DIR" 2>/dev/null || true
    fi
    PREPARE_LOCK_HELD=0
}

prepare_interrupted() {
    local status="$1"
    release_prepare_lock
    trap - EXIT HUP INT TERM
    exit "$status"
}

acquire_prepare_lock() {
    local attempt=0 lock_pid="" missing_pid_attempts=0
    PREPARE_LOCK_DIR="$SSH_DIR/.prepare.lock"

    while (( attempt < 300 )); do
        if mkdir "$PREPARE_LOCK_DIR" 2>/dev/null; then
            PREPARE_LOCK_HELD=1
            trap release_prepare_lock EXIT
            trap 'prepare_interrupted 129' HUP
            trap 'prepare_interrupted 130' INT
            trap 'prepare_interrupted 143' TERM
            printf '%s\n' "$$" >"$PREPARE_LOCK_DIR/pid"
            return
        fi
        if [[ -L "$PREPARE_LOCK_DIR" || ! -d "$PREPARE_LOCK_DIR" ]]; then
            die "SSH preparation lock is not a regular directory: $PREPARE_LOCK_DIR"
        fi
        if [[ -L "$PREPARE_LOCK_DIR/pid" || ( -e "$PREPARE_LOCK_DIR/pid" && ! -f "$PREPARE_LOCK_DIR/pid" ) ]]; then
            die "SSH preparation lock PID is not a regular file: $PREPARE_LOCK_DIR/pid"
        fi

        lock_pid=""
        if [[ -f "$PREPARE_LOCK_DIR/pid" ]]; then
            lock_pid="$(tr -d '[:space:]' <"$PREPARE_LOCK_DIR/pid")"
        fi
        if [[ "$lock_pid" =~ ^[0-9]+$ ]] && kill -0 "$lock_pid" 2>/dev/null; then
            missing_pid_attempts=0
        elif [[ -n "$lock_pid" || "$missing_pid_attempts" -ge 20 ]]; then
            if [[ -f "$PREPARE_LOCK_DIR/pid" && ! -L "$PREPARE_LOCK_DIR/pid" ]]; then
                rm -f "$PREPARE_LOCK_DIR/pid"
            fi
            if rmdir "$PREPARE_LOCK_DIR" 2>/dev/null; then
                continue
            fi
        else
            missing_pid_attempts=$((missing_pid_attempts + 1))
        fi
        attempt=$((attempt + 1))
        sleep 0.1
    done
    die "Timed out waiting for SSH preparation lock: $PREPARE_LOCK_DIR"
}

ensure_known_hosts() {
    if [[ -L "$KNOWN_HOSTS_PATH" ]]; then
        die "known_hosts seed must not be a symbolic link: $KNOWN_HOSTS_PATH"
    fi
    if [[ -e "$KNOWN_HOSTS_PATH" && ! -f "$KNOWN_HOSTS_PATH" ]]; then
        die "known_hosts seed is not a regular file: $KNOWN_HOSTS_PATH"
    fi
    if [[ ! -e "$KNOWN_HOSTS_PATH" ]]; then
        : >"$KNOWN_HOSTS_PATH"
        log "Created empty known_hosts seed at $KNOWN_HOSTS_PATH"
    fi
    chmod 600 "$KNOWN_HOSTS_PATH"
}

prepare_ssh() {
    require_command ssh-agent
    require_command ssh-add
    require_command ssh-keygen
    resolve_paths
    acquire_prepare_lock
    ensure_key
    start_agent
    ensure_agent_identity
    ensure_known_hosts
    release_prepare_lock
    trap - EXIT HUP INT TERM
}

require_env_file() {
    if [[ -L "$ENV_FILE" ]]; then
        die "Environment file must not be a symbolic link: $ENV_FILE"
    fi
    if [[ ! -e "$ENV_FILE" ]]; then
        cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        die "Created $ENV_FILE. Fill in the required secrets, then run make start again."
    fi
    [[ -f "$ENV_FILE" ]] || die "Environment file is not a regular file: $ENV_FILE"
    chmod 600 "$ENV_FILE"
}

compose() {
    SSH_AUTH_SOCK_PATH="$SOCKET_PATH" \
    SSH_KNOWN_HOSTS_PATH="$KNOWN_HOSTS_PATH" \
        docker compose --project-directory "$PROJECT_ROOT" -f "$PROJECT_ROOT/docker-compose.yml" "$@"
}

sync_hosts() {
    if [[ -z "$HOSTS_CSV" ]]; then
        log "Host enrollment disabled because FLEET_HOSTS_CSV is empty."
        return
    fi
    if [[ ! -e "$HOSTS_CSV" ]]; then
        if [[ "$HOSTS_CSV_EXPLICIT" == "1" || "$COMMAND" == "enroll-hosts" ]]; then
            die "Hosts CSV not found: $HOSTS_CSV"
        else
            log "No hosts CSV found at $HOSTS_CSV; skipping host enrollment."
            return
        fi
    fi
    [[ -f "$HOSTS_CSV" && ! -L "$HOSTS_CSV" ]] || die "Hosts CSV must be a regular, non-symlink file: $HOSTS_CSV"
    [[ "$(path_owner "$HOSTS_CSV")" == "$(id -u)" ]] || die "Hosts CSV must be owned by the current user: $HOSTS_CSV"
    if [[ "$HOSTS_CSV" == "$PROJECT_ROOT/hosts.csv" ]]; then
        chmod 600 "$HOSTS_CSV"
    fi
    case "$(path_mode "$HOSTS_CSV")" in
        *00) ;;
        *) die "Hosts CSV must not be accessible by group or other users: $HOSTS_CSV" ;;
    esac

    log "Syncing devices from $HOSTS_CSV"
    compose exec -T web \
        python /app/ansible/scripts/enroll_hosts.py \
        --known-hosts /run/fleet-known-hosts-seed \
        <"$HOSTS_CSV"
}

show_status() {
    local status identities
    resolve_paths 0
    if [[ ! -S "$SOCKET_PATH" ]]; then
        die "Dedicated SSH agent socket is unavailable: $SOCKET_PATH"
    fi
    set +e
    identities="$(SSH_AUTH_SOCK="$SOCKET_PATH" ssh-add -l 2>&1)"
    status=$?
    set -e
    printf '%s\n' "$identities"
    [[ "$status" == "0" ]] || die "Dedicated SSH agent is reachable but not ready"
}

case "$COMMAND" in
    start)
        require_command docker
        require_env_file
        prepare_ssh
        compose config --quiet
        log "Refreshing the proxy mount for the dedicated agent socket."
        compose up -d --build --force-recreate ssh-agent-proxy
        log "Starting Fleet Manager."
        compose up -d --build --wait --wait-timeout "${FLEET_START_TIMEOUT_SECONDS:-600}"
        sync_hosts
        log "Fleet Manager is ready."
        ;;
    prepare)
        prepare_ssh
        log "SSH prerequisites are ready."
        ;;
    enroll-hosts)
        require_command docker
        require_env_file
        prepare_ssh
        compose config --quiet
        log "Refreshing the proxy mount for the dedicated agent socket."
        compose up -d --build --force-recreate ssh-agent-proxy
        sync_hosts
        ;;
    status)
        require_command ssh-add
        show_status
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
