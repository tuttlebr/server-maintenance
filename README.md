# Fleet Manager

A capability-driven fleet operations platform for Linux compute, edge devices, and robots. It discovers what each device can do, shows only eligible operations, and keeps NVIDIA support as a first-class integration rather than the product identity. The backend uses FastAPI, Ansible, and adapter services; the frontend is Vue 3.

## Features

- **Mixed-fleet overview** with device reachability, attention, optional GPU and robot summaries, and recent activity
- **Capability discovery** for portable Linux facts, NVIDIA features, and Reachy Mini Wireless daemon health
- **Adaptive operations** that appear only when at least one device supports them
- **Access management** for Linux accounts on devices that advertise `users.manage`
- **Integration operations** for NVIDIA drivers, Fabric Manager, MIG, and Kubernetes when discovery finds them
- **Safe Reachy Mini support** for health, logs, daemon restart, and stable software updates, without motion, torque, camera, audio, or app controls
- **Activity tracking**: full history with output logs for every operation, indexed for Fleet Help after success, failure, or cancellation
- **Neutral UI** with NVIDIA, Kubernetes, and Reachy features presented as labeled integrations
- **CLI compatible**: all Ansible playbooks still work directly from the command line

## Prerequisites

- Docker and Docker Compose
- SSH access from the management host to all managed Linux machines
- A dedicated SSH key loaded into an SSH agent
- An existing Linux SSH account on each managed machine

## Dedicated SSH Key and Agent Setup

The web container receives an SSH agent socket, not private key files. Use a dedicated agent containing only the fleet-management key so the container can't request signatures from unrelated SSH identities. A small proxy container bridges the host-owned socket to the non-root `fleet` process; the private key remains in the host agent.

There are two different users in this design:

| User | Where it exists | Purpose |
|------|-----------------|---------|
| `fleet` | Inside the web container only | Runs Ansible and owns its local temporary files |
| `ssh_user` from the UI or CSV | On every selected remote device | The Linux account used for SSH and remote Ansible tasks |

The remote machines do not need a `fleet` account unless you deliberately set `ansible_user=fleet`.

### 1. Create the key pair

Generate an Ed25519 key pair on the management host. `ssh-keygen` prompts for a passphrase. Use a strong passphrase because the agent will cache it after you unlock the key.

```bash
FLEET_KEY="$HOME/.ssh/fleet-management-key"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -a 100 -f "$FLEET_KEY" -C "fleet-management"
ssh-keygen -lf "$FLEET_KEY.pub"
```

This creates:

- `~/.ssh/fleet-management-key`, the private key that must remain on the management host
- `~/.ssh/fleet-management-key.pub`, the public key to install on each managed host

### 2. Choose how the public key reaches each managed host

The UI can install the agent's public key automatically when a host is enrolled. Supply the remote account's password in the **One-time bootstrap password** field or CSV column. The application uses it once to update that account's `~/.ssh/authorized_keys`, verifies key authentication, and discards the password without storing it.

If SSH password login is disabled, preinstall the public key instead. Run this once for each remote account and host:

If `ssh-copy-id` is available:

```bash
SSH_USER=your-ssh-user
MANAGED_HOST=dgx-01.example.com
ssh-copy-id -i "$FLEET_KEY.pub" "$SSH_USER@$MANAGED_HOST"
```

If `ssh-copy-id` isn't available, append the public key over an authenticated SSH connection:

```bash
ssh "$SSH_USER@$MANAGED_HOST" \
    'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys' \
    < "$FLEET_KEY.pub"
```

Then verify key-based access:

```bash
ssh -i "$FLEET_KEY" "$SSH_USER@$MANAGED_HOST" true
```

### 3. Start a dedicated SSH agent

Create the agent socket inside the ignored `.fleet-ssh` directory and load only the fleet-management key:

```bash
mkdir -p .fleet-ssh
chmod 700 .fleet-ssh
eval "$(ssh-agent -a "$PWD/.fleet-ssh/agent.sock")"
ssh-add "$FLEET_KEY"
ssh-add -l
```

Confirm that `ssh-add -l` lists only `fleet-management`. Don't load personal, Git, or other administrative keys into this agent.

### 4. Set `SSH_AUTH_SOCK_PATH`

The correct value is the absolute path printed by `$SSH_AUTH_SOCK`. Validate it and export it for Docker Compose:

```bash
printf 'SSH_AUTH_SOCK_PATH=%s\n' "$SSH_AUTH_SOCK"
test -S "$SSH_AUTH_SOCK" && echo "Valid SSH agent socket"
export SSH_AUTH_SOCK_PATH="$SSH_AUTH_SOCK"
```

Copy the printed assignment into `.env`. For this project-local agent it will look like:

```dotenv
SSH_AUTH_SOCK_PATH=/absolute/path/to/server-maintenance/.fleet-ssh/agent.sock
```

Use the absolute path. Don't put command substitution such as `$(pwd)` in `.env`.

The agent process doesn't survive a host restart. First check whether the dedicated agent is still reachable:

```bash
SSH_AUTH_SOCK="$PWD/.fleet-ssh/agent.sock" ssh-add -l
```

If that command prints the key fingerprint, reuse the running agent. If it reports that it can't connect to the agent, remove only the stale project socket, repeat step 3, and recreate the web container so Docker remounts the socket:

```bash
rm -f "$PWD/.fleet-ssh/agent.sock"
# Repeat step 3 to start the agent and load the key.
export SSH_AUTH_SOCK_PATH="$PWD/.fleet-ssh/agent.sock"
docker compose up -d --build --force-recreate web
```

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env and set every required secret

# Create the seed file expected by Compose. The UI manages verified host keys
# in the persistent fleet-data volume after fingerprint approval.
mkdir -p .fleet-ssh
chmod 700 .fleet-ssh
touch .fleet-ssh/known_hosts

# Build and run
docker compose up -d --build

# Open the web UI
open http://localhost:8080
```

Startup fails if authentication, host-encryption, or MinIO secrets are missing or use known placeholder values.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLEET_PORT` | `8080` | Port the web UI listens on |
| `SSH_AUTH_SOCK_PATH` | required | Dedicated host SSH agent socket bridged to the non-root web container |
| `SSH_KNOWN_HOSTS_PATH` | `./.fleet-ssh/known_hosts` | Optional seed file copied into the UI-managed persistent trust database |
| `SECRET_KEY` | required | JWT signing key with at least 32 characters |
| `ADMIN_PASSWORD` | required | Web UI admin password with at least 12 characters |
| `HOST_SECRET_KEY` | required | Fernet key used to encrypt stored SSH and sudo passwords |
| `CORS_ORIGINS` | dev localhost origins | Comma-separated list of allowed browser origins |
| `ANSIBLE_JOB_TIMEOUT_SECONDS` | `3600` | Maximum runtime for one queued Ansible job |
| `ANSIBLE_MAX_CONCURRENT_JOBS` | `4` | Maximum concurrent Ansible jobs |
| `ANSIBLE_FORKS` | `10` | Maximum hosts Ansible may operate on concurrently inside one fleet-scoped job; playbook `serial` still takes precedence |
| `MINIO_ACCESS_KEY` | required | Non-default MinIO root user shared with Milvus |
| `MINIO_SECRET_KEY` | required | Non-default MinIO root password shared with Milvus |
| `EMBED_MODEL` | `nvidia/qwen/qwen3-embedding-0.6b` | Embedding model shared by documentation and completed-job retrieval |

## Adding Devices to the Fleet

### Via Web UI (Recommended)

1. Log in to the dashboard
2. Open **Devices** and click **Add device**
3. Choose **Linux over SSH** or **Reachy Mini Wireless**.
4. Enter an inventory-safe device name, network endpoint, and connection details. Hardware type is discovered instead of selected.
5. Select **Dedicated fleet SSH key**:
   - If the key is already in that user's `authorized_keys`, leave the bootstrap password blank.
   - Otherwise enter a one-time bootstrap password so the UI can install the key.
6. For SSH, click **Discover device**. The UI retrieves the ED25519 host key and shows its fingerprint.
7. Compare that fingerprint with `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the device console.
8. Approve the verified fingerprint and add the device. Fleet Manager verifies authentication before saving it.
9. Run **Scan device** so portable facts and capabilities replace the initial generic profile.

Use **Import CSV** on the Devices page to preview, discover, fingerprint-check, and enroll multiple devices. `ssh_user` is required for SSH rows. Values such as `true`, `yes`, `key`, or `passwordless` in `passwordless_ssh` use the dedicated agent key. Use `bootstrap_password` only when that public key is not installed yet:

```csv
name,endpoint,transport,ssh_user,ssh_password,become_password,passwordless_ssh,bootstrap_password,daemon_port
compute-01,192.168.1.234,ssh,brandon,,,true,one-time-ssh-password,
edge-01,192.168.1.235,ssh,brandon,,,true,,
reachy-lab,reachy-mini.local,reachy_daemon,,,,true,,8000
```

For password authentication, set `passwordless_ssh=false` and put the persistent SSH password in `ssh_password`. One-time bootstrap passwords are never stored; persistent SSH and sudo passwords are encrypted before database storage. Treat CSV files containing passwords as temporary secrets and delete them securely after import.

### Generated Ansible Inventory

The database is the source of truth. Fleet Manager regenerates `data/inventory/hosts.json` after enrollment and whenever a scan changes capabilities. It provides `managed_hosts`, `compute`, `gpu`, `nvidia_gpu`, `cpu`, `fabric_manager`, and `mig` groups. Reachy daemon devices are intentionally excluded because they are not SSH playbook targets.

## Integration Setup Notes

### DGX Spark

1. **First boot**: Complete the 10-step setup wizard (language, user account, network, software download)
2. **Enable SSH**: SSH is available after first boot completes
3. **Network**: Connect Ethernet (10 GbE) and optionally CX7 QSFP cables for Spark Stacking
4. **Verify GPU**: Run `nvidia-smi` to confirm the Grace Blackwell GPU is detected
5. **Add to fleet**: Enroll the device through the Devices page
6. **Scan**: Run a scan to populate dashboard data

Key specs: DGX OS 7.4.0, CUDA 13.0.2, driver 580.142, Grace Blackwell superchip, 128 GB unified memory, CX7 QSFP networking.

### DGX Workstation

1. **First boot**: Complete Ubuntu 24.04 LTS setup with NVIDIA AI Developer Tools
2. **BMC**: Configure the BMC via the dedicated 1 GbE RJ45 port for out-of-band management
3. **Network**: Connect 10 GbE for standard networking and ConnectX-8 QSFP112 ports for high-speed fabric
4. **MIG** (optional): Configure Multi-Instance GPU for up to 7 isolated GPU instances
5. **Verify GPU**: Run `nvidia-smi` to confirm the Blackwell Ultra GPU is detected
6. **Add to fleet**: Enroll the device through the Devices page

Key specs: Ubuntu 24.04 LTS, Blackwell Ultra GPU, 252 GB HBM3e, 496 GB LPDDR5X, ConnectX-8 SuperNIC (800 Gb/s), MIG support.

### Reachy Mini Wireless

1. Connect the robot to the same trusted network as Fleet Manager.
2. Confirm its daemon is available on port `8000`, or enter the configured port.
3. Add it with **Reachy Mini Wireless** as the connection type.
4. Discovery reads `/api/state/full` and never sends movement, torque, camera, audio, or app-control commands.

## Common Operations

The **Operations** page derives eligibility from each device's discovered capabilities. It groups read-only inspection, system changes, NVIDIA integration tasks, Kubernetes checks, and Reachy management separately. Unsupported operations are hidden, and high-impact actions require confirmation.

Use **Access** for Linux account provisioning, password changes, and sudoers management. Only SSH devices with `users.manage` can be targeted. Use **Activity** for job status, output, cancellation, and history.

## CLI Usage

All playbooks work directly with `ansible-playbook` for power users:

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install required Ansible collections (first-time setup)
ansible-galaxy collection install -r requirements.yml

# System maintenance
ansible-playbook playbooks/system_maintenance.yml
ansible-playbook playbooks/docker_cleanup.yml
ansible-playbook playbooks/preflight_check.yml
ansible-playbook playbooks/health_diagnostics.yml

# Add users (edit group_vars/workstations.yml first)
ansible-playbook playbooks/user_management.yml

# Change a user's password
ansible-playbook playbooks/change_password.yml

# Upgrade drivers
ansible-playbook playbooks/driver_upgrade.yml
ansible-playbook playbooks/driver_upgrade.yml -e '{"upgrade_mode":"major","target_driver_version":"570"}'
ansible-playbook playbooks/firmware_inventory.yml
ansible-playbook playbooks/firmware_update.yml -e '{"firmware_mode":"update"}'

# Check fabric manager status
ansible-playbook playbooks/fabric_manager.yml

# Gather host facts
ansible-playbook playbooks/host_facts.yml

# Manage sudoers
ansible-playbook playbooks/manage_sudoers.yml
ansible-playbook playbooks/host_bootstrap.yml --limit ast-spark-01
ansible-playbook playbooks/host_drain.yml -e '{"drain_action":"status"}'
ansible-playbook playbooks/mig_management.yml -e '{"mig_action":"status"}'

# Target specific hosts
ansible-playbook playbooks/system_maintenance.yml --limit ast-spark-01
```

## Fleet Documentation Ingestion

The Rust doc ingester crawls every HTML page under each URL prefix in `docs/urls.txt`, includes local Markdown guidance from `docs/*.md`, converts content to Markdown, embeds the chunks with the `.env` embedding settings, and rebuilds the `fleet_docs` collection in Milvus. The included `docs/fleet-manager-ui.md` file teaches Fleet Help how to guide users through the UI.

In Docker, the web image builds this tool into `/usr/local/bin/fleet-doc-ingester`. The documentation reindex endpoint runs that binary inside the web container and writes generated Markdown to `/app/data/docs-crawled`.

```bash
# Start Milvus first
docker compose up -d etcd minio milvus

# Crawl, convert, embed, and ingest
cargo run --release --manifest-path tools/dgx-doc-ingester/Cargo.toml -- \
  --urls docs/urls.txt \
  --local-docs-dir docs \
  --env-file .env \
  --markdown-dir docs/crawled

# Crawl/Markdown verification only, no embedding or Milvus writes
cargo run --manifest-path tools/dgx-doc-ingester/Cargo.toml -- \
  --urls docs/urls.txt \
  --local-docs-dir docs \
  --env-file .env \
  --dry-run
```

The tool reads `EMBED_MODEL`, optional `EMBED_DIM`, `EMBED_API_KEY`/`AI_HELPER_API_KEY`, `EMBED_BASE_URL`/`AI_HELPER_BASE_URL`, and `MILVUS_URI` from `.env`. By default it rebuilds `fleet_docs`; pass `--append` to keep an existing collection or `--no-local-markdown` to exclude local UI guidance.

Completed operations are indexed separately in `fleet_job_logs`. Every terminal outcome adds redacted metadata, recap, error context, and bounded log chunks. Each ingestion also refreshes a latest-completed-job-per-device snapshot so Fleet Help can answer questions about recent fleet evidence. SQL activity and full on-disk logs remain the source of truth; Milvus is a derived search index.

## Project Structure

```
server-maintenance/
├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Multi-stage build (Node + Python)
├── .env.example                # Environment variable template
├── ansible.cfg                 # Ansible configuration
├── inventory/
│   └── hosts.ini               # Optional CLI inventory and capability groups
├── group_vars/                 # Ansible group variables
├── playbooks/
│   ├── user_management.yml     # Bulk user creation
│   ├── change_password.yml     # Single user password change
│   ├── bulk_password_reset.yml # Bulk password reset
│   ├── manage_sudoers.yml      # Add users to sudoers
│   ├── remove_sudoers.yml      # Remove users from sudoers
│   ├── remove_user.yml         # Remove a user
│   ├── manage_groups.yml       # Create system groups
│   ├── admin_setup.yml         # Single admin sudo setup
│   ├── host_bootstrap.yml      # Groups, admin, Docker/toolkit, scan
│   ├── system_maintenance.yml  # Advanced full-system maintenance workflow
│   ├── docker_cleanup.yml      # Docker/containerd image and cache cleanup
│   ├── preflight_check.yml     # Read-only maintenance readiness checks
│   ├── health_diagnostics.yml  # Deep host health diagnostics
│   ├── driver_upgrade.yml      # NVIDIA driver upgrades
│   ├── firmware_inventory.yml  # Firmware inventory
│   ├── firmware_update.yml     # Firmware updates
│   ├── host_drain.yml          # Kubernetes drain/resume helper
│   ├── mig_management.yml      # MIG status/enable/disable
│   ├── fabric_manager.yml      # Fabric manager service control
│   └── host_facts.yml          # Gather host info for dashboard
├── roles/                      # Ansible roles
├── templates/                  # User config templates
├── scripts/                    # Shell scripts and design guide
├── backend/                    # FastAPI backend (API + Ansible runner)
└── frontend/                   # Vue 3 capability-driven UI
```

## Security

- **SSH keys**: Private keys stay in a dedicated host SSH agent. A constrained proxy exposes only that dedicated agent to the non-root web container.
- **SSH host trust**: Host key verification is always strict. The UI scans ED25519 keys, requires fingerprint approval, rechecks the key before saving it, and maintains the trusted keys in the persistent data volume.
- **Admin password**: `ADMIN_PASSWORD` is required in every environment and must contain at least 12 characters.
- **JWT tokens**: Tokens expire after 8 hours. `SECRET_KEY` is required in every environment and must contain at least 32 characters.
- **Host SSH credentials**: Prefer SSH keys. One-time bootstrap passwords are used only to install the agent public key and are never stored. Persistent SSH and sudo passwords are Fernet-encrypted in SQLite and passed to the single fleet-scoped Ansible process as a host-keyed map through a mode-0600 named pipe. They are never written to the runtime inventory or command line.
- **Fleet execution**: One Ansible process receives the complete selected-host limit, so playbook `serial`, `run_once`, delegation, and cross-host recap behavior remain effective. Per-host locks prevent overlapping jobs on the same machines.
- **Targeting**: Mutating APIs require either explicit host names or `all_hosts=true`; empty host lists are rejected.
- **User passwords**: Passed through to Ansible, hashed with SHA-512 on the target host, marked `no_log` in playbooks, and redacted from job `extra_vars`.
- **TLS**: For production, put a reverse proxy (nginx, Traefik) with TLS in front of the container.
- **Ansible Vault**: Encrypt sensitive group_vars with `ansible-vault encrypt` for secrets at rest.

## Development

```bash
# Backend (from repo root)
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload

# Database migrations
alembic upgrade head

# Frontend (from frontend/)
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to the backend at `localhost:8000`.


## Embedding Test

```bash
export EMBED_API_KEY="not-used"
export EMBED_MODEL="nvidia/llama-nemotron-embed-vl-1b-v2"
export EMBED_BASE_URL="http://192.168.1.12:8000/v1"

curl "${EMBED_BASE_URL}/embeddings" \
  -H "Authorization: Bearer ${EMBED_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"${EMBED_MODEL}\",
    \"input\": [\"NVIDIA Dynamo optimizes distributed LLM inference.\"],
    \"encoding_format\": \"float\"
  }"
```
