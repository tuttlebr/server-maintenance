# Fleet Manager

A web-based Linux fleet management platform with optional NVIDIA GPU and DGX-specific operations. It provides a clean web UI for user management, driver upgrades, networking, and system maintenance — backed by Ansible playbooks and packaged in Docker.

## Features

- **Fleet dashboard** with host status, GPU info, disk usage, and job history
- **User management**: bulk add (form or CSV), bulk update, password changes, sudoers management
- **Driver upgrades**: one-click driver updates per host or fleet-wide, with firmware handled separately
- **Networking**: fabric manager control, NIC status monitoring
- **System maintenance**: routine diagnostics and cleanup plus advanced full-system maintenance, firmware actions, host drain/resume, MIG controls, and disk monitoring
- **Job tracking**: full history with output logs for every operation, indexed for DGX Help after success, failure, or cancellation
- **NVIDIA-branded UI** following official design guidelines
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
| `ansible_user` from the UI or CSV | On every selected remote host | The Linux account used for SSH and remote Ansible tasks |

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

## Adding Hosts to the Fleet

### Via Web UI (Recommended)

1. Log in to the dashboard
2. Click **Add Host**
3. Enter the hostname or IP, machine type, and the existing remote **SSH Username**. Use **Unknown / Auto-detect** when the product class is not known; an omitted CSV machine type also remains `unknown`.
4. Select **Dedicated fleet SSH key**:
   - If the key is already in that user's `authorized_keys`, leave the bootstrap password blank.
   - Otherwise enter a one-time bootstrap password so the UI can install the key.
5. Click **Verify SSH & Add**. The UI retrieves the ED25519 host key and shows its fingerprint.
6. Compare that fingerprint with `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the host console.
7. Click **Approve, verify & add**. The application records the approved key, verifies authentication, and only then saves the host.
8. Click **Scan Fleet** to gather GPU, driver, disk, and network information.

Bulk import uses the same enrollment workflow for every row. `ansible_user` is required. Values such as `true`, `yes`, `key`, or `passwordless` in `passwordless_ssh` use the dedicated agent key. Use `bootstrap_password` only when that public key is not installed yet:

```csv
hostname,ip_address,machine_type,ansible_user,ansible_password,ansible_become_password,passwordless_ssh,bootstrap_password
daedalus-01,192.168.1.234,dgx_spark,brandon,,,true,one-time-ssh-password
daedalus-02,192.168.1.235,dgx_spark,brandon,,,true,
```

For password authentication, set `passwordless_ssh=false` and put the persistent SSH password in `ansible_password`. One-time bootstrap passwords are never stored; persistent SSH and sudo passwords are encrypted before database storage. Treat CSV files containing passwords as temporary secrets and delete them securely after import.

### Via Inventory File

Edit `inventory/hosts.ini` directly:

```ini
[dgx_spark]
ast-spark-01 ansible_connection=local
ast-spark-02 ansible_host=10.0.0.2

[dgx_workstation]
ast-ws-01 ansible_host=10.0.0.10

[cpu_node]
server-01 ansible_host=10.0.0.20

[gpu_node]
gpu-01 ansible_host=10.0.0.30

[unknown]

[managed_hosts:children]
unknown
dgx_spark
dgx_workstation
cpu_node
gpu_node

# Compatibility alias for older playbooks.
[workstations:children]
unknown
dgx_spark
dgx_workstation
cpu_node
gpu_node

[nvidia_gpu:children]
dgx_spark
dgx_workstation
gpu_node

[all:vars]
ansible_user=btuttle
ansible_python_interpreter=/usr/bin/python3
```

The UI-generated runtime inventory also provides `managed_hosts`, `compute`,
`gpu`, `nvidia_gpu`, `cpu`, and `fabric_manager` capability groups. New
playbooks should target `all` or `managed_hosts` and gate optional tasks on a
capability group. `workstations` remains only as a compatibility alias.

## Initial Host Setup

### DGX Spark

1. **First boot**: Complete the 10-step setup wizard (language, user account, network, software download)
2. **Enable SSH**: SSH is available after first boot completes
3. **Network**: Connect Ethernet (10 GbE) and optionally CX7 QSFP cables for Spark Stacking
4. **Verify GPU**: Run `nvidia-smi` to confirm the Grace Blackwell GPU is detected
5. **Add to fleet**: Add the host via the web UI or inventory file
6. **Scan**: Run a scan to populate dashboard data

Key specs: DGX OS 7.4.0, CUDA 13.0.2, driver 580.142, Grace Blackwell superchip, 128 GB unified memory, CX7 QSFP networking.

### DGX Workstation

1. **First boot**: Complete Ubuntu 24.04 LTS setup with NVIDIA AI Developer Tools
2. **BMC**: Configure the BMC via the dedicated 1 GbE RJ45 port for out-of-band management
3. **Network**: Connect 10 GbE for standard networking and ConnectX-8 QSFP112 ports for high-speed fabric
4. **MIG** (optional): Configure Multi-Instance GPU for up to 7 isolated GPU instances
5. **Verify GPU**: Run `nvidia-smi` to confirm the Blackwell Ultra GPU is detected
6. **Add to fleet**: Add the host via the web UI or inventory file

Key specs: Ubuntu 24.04 LTS, Blackwell Ultra GPU, 252 GB HBM3e, 496 GB LPDDR5X, ConnectX-8 SuperNIC (800 Gb/s), MIG support.

## Common Operations

### User Management

**Bulk add users** via the web UI:
- Enter users manually (full name + email) or upload a CSV file
- Select target hosts (individual, all Spark, or all Workstation)
- Users are created with home directories, SSH keys, standard configs, and `/raid` directories

CSV format:
```
full_name,email
Jane Smith,jsmith@nvidia.com
John Doe,jdoe@nvidia.com
```

**Password management**:
- Change individual user passwords via the Manage Users tab
- Bulk reset non-system user passwords with an operator-provided temporary password
- New and bulk-reset users are forced to change passwords on next login

**Sudoers**:
- Add or remove users from passwordless sudo via the Sudoers tab

### Driver Upgrades

The web UI shows current driver and CUDA versions across the fleet. Select hosts and click **Upgrade Selected** to run:

- **Standard**: rolling package-level driver/system updates
- **Major Version**: installs a specific `nvidia-driver-<branch>` package, such as `nvidia-driver-570`

Each UI job launches one fleet-scoped Ansible process. Driver upgrades still
run one host at a time because the playbook declares `serial: 4`; read-only
playbooks can use Ansible forks across the selected fleet. Check the Jobs tab
for output.
Firmware updates are handled separately from driver upgrades on the Maintenance page.

### Fabric Manager

The Networking page shows fabric manager status per host with controls to start, stop, or restart the service.

### System Maintenance

- **Preflight checks**: SSH reachability through Ansible, apt/dpkg activity, disk pressure, reboot flag, GPU processes, and service state
- **Health diagnostics**: nvidia-smi, Fabric Manager, DCGM, NVSM, IB, failed units, critical journal, and storage summaries
- **Full system maintenance**: advanced package and firmware updates, mount remediation, kernel and container cleanup, storage checks, and zombie-process remediation with conditional automatic reboots
- **Docker cleanup**: prune unused images, build cache, networks, and containerd images without removing volumes
- **Bootstrap**: common groups, admin sudo setup, Docker/NVIDIA Container Toolkit install, and host scan
- **Firmware**: inventory and update actions independent of driver upgrades
- **Drain/Resume**: inspect active GPU work and run Kubernetes cordon/drain/uncordon when kubectl is configured
- **MIG**: query or toggle MIG mode on DGX Workstation hosts after active GPU checks
- **Disk monitoring**: root and automatically discovered mounted-storage usage across the fleet

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

## DGX Documentation Ingestion

The Rust doc ingester crawls every HTML page under each URL prefix in `docs/urls.txt`, includes local Markdown guidance from `docs/*.md`, converts content to Markdown, embeds the chunks with the `.env` embedding settings, and rebuilds the `dgx_docs` collection in Milvus. The included `docs/fleet-manager-ui.md` file teaches DGX Help how to guide users through the Fleet Manager UI.

In Docker, the web image builds this tool into `/usr/local/bin/dgx-doc-ingester`. The **Maintenance → Reindex Documentation** button calls the backend reindex endpoint, which runs that binary inside the web container and writes generated Markdown to `/app/data/docs-crawled`.

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

The tool reads `EMBED_MODEL`, optional `EMBED_DIM`, `EMBED_API_KEY`/`AI_HELPER_API_KEY`, `EMBED_BASE_URL`/`AI_HELPER_BASE_URL`, and `MILVUS_URI` from `.env`. By default it rebuilds `dgx_docs`; pass `--append` to keep an existing collection or `--no-local-markdown` to exclude local UI guidance.

Completed Ansible runs are indexed separately in the `fleet_job_logs` collection. Every terminal outcome (success, failure, or cancellation) adds redacted metadata, recap, error context, and bounded log chunks. Each ingestion also refreshes a latest-completed-job-per-host snapshot so DGX Help can answer questions such as “What’s the overall status of my fleet based on the most recent jobs?” The SQL job history and full on-disk log remain the source of truth; Milvus is a derived search index. Startup reconciliation backfills terminal jobs that were missed while Milvus or the embedding endpoint was unavailable.

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
└── frontend/                   # Vue 3 SPA (NVIDIA-branded UI)
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
