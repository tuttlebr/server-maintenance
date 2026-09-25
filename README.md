# Fleet Manager

A capability-driven fleet operations platform for Linux compute, edge devices, and robots. It discovers what each device can do, shows only eligible operations, and keeps NVIDIA support as a first-class integration rather than the product identity. The backend uses FastAPI, Ansible, and adapter services; the frontend is Vue 3.

## Features

- **Mixed-fleet overview** with device reachability, attention, optional GPU and robot summaries, and recent activity
- **Capability discovery** for portable Linux facts, NVIDIA features, and Reachy Mini Wireless daemon health
- **Adaptive operations** that appear only when at least one device supports them
- **Access management** for Linux accounts on devices that advertise `users.manage`
- **Integration operations** for NVIDIA drivers, Fabric Manager, MIG, and Kubernetes when discovery finds them
- **Safe Reachy Mini support** for health, logs, daemon restart, stable software updates, and an explicitly enabled app-environment reset, without motion, torque, camera, or audio controls
- **Activity tracking**: full history with output logs for every operation, indexed for Fleet Help after success, failure, or cancellation
- **Neutral UI** with NVIDIA, Kubernetes, and Reachy features presented as labeled integrations
- **CLI compatible**: all Ansible playbooks still work directly from the command line

## Prerequisites

- Docker and Docker Compose
- SSH access from the management host to all managed Linux machines
- A dedicated SSH key loaded into an SSH agent
- An existing Linux SSH account on each managed machine

## Startup

Before the first start, complete [Create the `.env` secrets](#create-the-env-secrets).

If upgrading a stack that used MinIO, follow [Switching from MinIO](#switching-from-minio) before starting. The search indexes need a one-time rebuild.

Use the idempotent startup target for both first-time setup and normal restarts:

```bash
make start
```

It creates or reuses `~/.ssh/fleet-management-key`, creates or reconnects the project-local agent at `.fleet-ssh/agent.sock`, loads exactly that one key, creates the `known_hosts` seed file, starts the Compose stack, waits for it to become healthy, and then syncs `hosts.csv` when that ignored local file exists.

The first key creation prompts for a passphrase. After a host reboot, the first startup prompts once to unlock that key into the new agent. If `.env` is missing, the command copies `.env.example` and stops so you can fill in the required secrets before rerunning it.

Useful narrower targets are:

```bash
make prepare       # Prepare only the key, agent socket, and known_hosts seed
make enroll-hosts  # Sync hosts.csv into an already-running stack
make status        # Show the dedicated agent's loaded identity
```

Host sync is idempotent: matching existing devices are skipped. A new SSH device is enrolled only when its discovered Ed25519 fingerprint is already trusted by Fleet Manager, matches the verified `.fleet-ssh/known_hosts` seed, or matches an optional `ssh_fingerprint` column in `hosts.csv`. Verify fingerprints through an independent channel before adding them. Startup never accepts an unverified `ssh-keyscan` result on first sight. Fingerprint pins are checked when creating missing devices; existing devices continue to use Fleet Manager's persistent strict host-key trust.

Set `FLEET_SSH_KEY_PATH`, `FLEET_SSH_DIR`, or `FLEET_HOSTS_CSV` to override their defaults. Set `FLEET_HOSTS_CSV=` to start without syncing a CSV.

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

If that command prints the key fingerprint, reuse the running agent. If it reports that it can't connect to the agent, remove only the stale project socket, repeat step 3, and recreate the proxy container so Docker remounts the host socket:

```bash
rm -f "$PWD/.fleet-ssh/agent.sock"
# Repeat step 3 to start the agent and load the key.
export SSH_AUTH_SOCK_PATH="$PWD/.fleet-ssh/agent.sock"
docker compose up -d --build --force-recreate ssh-agent-proxy
```

## Create the `.env` secrets

Run the setup commands from the repository root. Keep real values in the ignored `.env` file and your password manager. Do not put them in `.env.example`, source control, chat, or issue reports.

### 1. Generate the three required local secrets

These credentials are created locally. No external account or API key is needed for them.

| Variable | Purpose and required format | Generated value |
|----------|-----------------------------|-----------------|
| `SECRET_KEY` | Signs Fleet Manager login tokens; at least 32 characters | 64 random hexadecimal characters |
| `ADMIN_PASSWORD` | Password for the default `admin` web account; at least 12 characters | 32 random URL-safe characters |
| `HOST_SECRET_KEY` | Encrypts stored SSH and sudo passwords; a URL-safe Base64 encoding of exactly 32 random bytes | 44 characters, including the final `=` |

Run this complete script with Python 3.6 or later. It uses only the Python standard library. It creates `.env` from `.env.example` if needed, fills blank local secrets, and sets file permissions to `0600`. Existing nonempty values remain unchanged. It prints variable names only.

```bash
python3 - <<'PY'
import base64
import os
from pathlib import Path
import secrets

os.umask(0o077)
env_path = Path(".env")
if env_path.is_symlink() or (env_path.exists() and not env_path.is_file()):
    raise SystemExit(".env must be a regular file, not a symbolic link")

source = env_path if env_path.exists() else Path(".env.example")
lines = source.read_text(encoding="utf-8").splitlines()
generators = {
    "SECRET_KEY": lambda: secrets.token_hex(32),
    "ADMIN_PASSWORD": lambda: secrets.token_urlsafe(24),
    "HOST_SECRET_KEY": lambda: base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
}
updated = []
for name, generate in generators.items():
    matches = [i for i, line in enumerate(lines) if line.startswith(name + "=")]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {name}= line; fix .env before retrying")
    index = matches[0]
    value = lines[index].partition("=")[2].strip()
    if value in ("", "''", '\"\"'):
        lines[index] = name + "=" + generate()
        updated.append(name)

if env_path.exists():
    env_path.chmod(0o600)
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
env_path.chmod(0o600)
print("Generated: " + (", ".join(updated) if updated else "none; existing values retained"))
print("Saved .env with permissions 0600. Secret values were not printed.")
PY
```

Open `.env` in a local editor. Save the generated `ADMIN_PASSWORD` in your password manager; use it with username `admin`. The application expects the password itself, not a password hash. The script preserves nonempty placeholder values too, so replace any placeholders before startup.

Back up `HOST_SECRET_KEY` with the Fleet Manager database. If restoring an existing database, restore its original key before running the script. A new key cannot decrypt passwords encrypted with the old key. The generated value follows the [Fernet key format](https://cryptography.io/en/latest/fernet/); preserve its final `=`.

Milvus stores its search indexes in a local Docker volume. No object-storage service, storage credentials, or AWS account is required.

### 2. Create `AI_HELPER_API_KEY`

The default `AI_HELPER_BASE_URL=https://inference-api.nvidia.com/v1` uses NVIDIA's internal Inference Hub. Create its key through the service:

1. Open [Inference Hub](https://inference.nvidia.com/) and sign in with NVIDIA SSO.
2. Select **Profile**, then **Key Management**, then **Generate API Key**.
3. Select **Personal Key** for experiments, **Non-Prod Service** for application development, or **Prod Service** for production.
4. Complete the required service details and select an expiration period.
5. Generate the key and save it in your password manager.
6. In your local `.env`, paste the key after `AI_HELPER_API_KEY=`. Do not include the `Bearer ` prefix.
7. In the model catalog's **Developer Tools**, confirm the model ID for your selected model and set `AI_HELPER_MODEL`.

The template selects `aws/anthropic/bedrock-claude-sonnet-4-6`. Model access and availability depend on the service. Keep the base URL at `/v1`; Fleet Manager appends `/chat/completions`. These steps follow the internal [Inference Hub Getting Started guide](https://nvidia.atlassian.net/wiki/spaces/ITBU/pages/2814902879/Getting+Started), which requires NVIDIA access.

If you use public NVIDIA hosted inference, create a key through [NVIDIA API Catalog](https://build.nvidia.com/): sign in, open a model, select **Get API Key**, then **Generate Key**. Set `AI_HELPER_BASE_URL=https://integrate.api.nvidia.com/v1` and copy that model's API ID into `AI_HELPER_MODEL`. Use the public key with this public endpoint. See NVIDIA's [hosted inference setup instructions](https://docs.nvidia.com/vss/2.2.0/content/installation-remote.html#using-nims-from-build-nvidia-com).

For another OpenAI-compatible provider, create the key in that provider's console. Set the matching base URL and model ID. Random strings generated locally cannot authenticate to a hosted provider.

`AI_HELPER_API_KEY` is needed for Fleet Help chat. Core fleet operations do not use it. Without an AI key or a separate embedding key, document and job-log embedding also remain unavailable.

### 3. Set `EMBED_API_KEY` only when needed

If chat and embeddings use the same provider and credential, leave `EMBED_API_KEY` and `EMBED_BASE_URL` commented out. The embedding clients fall back to `AI_HELPER_API_KEY` and `AI_HELPER_BASE_URL`. For the standalone Rust ingester, an uncommented empty override prevents that fallback.

If embeddings use a different provider or credential:

1. Create a key through that provider's console, using the applicable process in step 2.
2. Enable access to the chosen embedding model where the provider requires it.
3. Uncomment `EMBED_API_KEY` and paste the issued key after `=`.
4. Uncomment `EMBED_BASE_URL` and set the provider's OpenAI-compatible base URL, usually ending in `/v1`.
5. Set `EMBED_MODEL` to the embedding model's API ID and `EMBED_DIM` to its output dimension.

The template uses `nvidia/qwen/qwen3-embedding-0.6b` with dimension `1024`. Confirm both values for your provider. A chat model ID cannot be used as an embedding model ID. Rebuild the documentation and job-log indexes if you change embedding models or dimensions.

### 4. Prepare SSH and optional Kubernetes credentials

`SSH_AUTH_SOCK_PATH` is the path to an agent socket. The SSH private key and its passphrase do not belong in `.env`.

```bash
make prepare
```

This creates or reuses the dedicated SSH key, prompts for its passphrase when needed, and prepares the agent and `known_hosts` seed. Follow [Dedicated SSH Key and Agent Setup](#dedicated-ssh-key-and-agent-setup) to install the public key on managed hosts. Choose the passphrase locally and keep it in your password manager.

`make start` supplies the socket and seed paths to Compose automatically. For direct `docker compose` commands, set `SSH_AUTH_SOCK_PATH` to the absolute socket path, normally `/absolute/path/to/server-maintenance/.fleet-ssh/agent.sock`. `SSH_KNOWN_HOSTS_PATH` contains verified server public keys and needs no password.

For Kubernetes-aware maintenance, obtain a kubeconfig for an authorized controller identity from your cluster administrator or provider's login tooling. Follow [Kubernetes-aware maintenance](#kubernetes-aware-maintenance) for permissions and configuration. Set `FLEET_KUBECONFIG_PATH` to its absolute host path and protect the file with `chmod 600`. A kubeconfig can contain tokens or private keys. Leave this variable empty if Kubernetes integration is unused.

### 5. Leave `MILVUS_TOKEN` unset for the bundled stack

The supplied Compose stack does not enable Milvus user authentication. Leave `# MILVUS_TOKEN=root:Milvus` commented out. `root:Milvus` is the upstream initial username/password pair, not a newly generated secret. Milvus is reachable only from the Docker network and host loopback.

For the standalone Rust ingester against a separate, authenticated Milvus server, obtain an authorized account from its administrator. `MILVUS_TOKEN` is the literal `username:password` pair. For example, after the administrator creates `fleet_ingester`, store its assigned password locally as `MILVUS_TOKEN='fleet_ingester:the-assigned-password'`. Replace the example password. The account needs permission to create, drop, index, load, and write the target collection.

If you administer that server, use the [Milvus 2.4 authentication guide](https://milvus.io/docs/v2.4.x/authenticate.md) to enable `common.security.authorizationEnabled` in `milvus.yaml`. Use its `MilvusClient.create_user(user_name=..., password=...)` procedure to create the account, then [assign its roles and privileges](https://milvus.io/docs/v2.4.x/users_and_roles.md). Generate the account password in your password manager. Change the initial root password with `MilvusClient.update_password(user_name="root", old_password=..., new_password=...)` before using the server. Creating a `MILVUS_TOKEN` entry alone does not create an account or enable authentication.

Current integration limit: only the Rust ingester reads `MILVUS_TOKEN`. The Python documentation and job-log clients and NAT do not pass it to Milvus. Enabling authentication for the bundled server requires changes to those clients and Compose before the full application can use it.

### 6. Check the configuration and start

Keep secrets on one line in `.env`. If a provider-issued value contains `$` or `#`, surround the value with single quotes. Compose treats single-quoted values literally; see its [`.env` syntax rules](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/#env-file-syntax). The locally generated values above need no quotes.

After SSH preparation, validate Compose without printing the resolved secrets:

```bash
SSH_AUTH_SOCK_PATH="$PWD/.fleet-ssh/agent.sock" docker compose config --quiet
make start
```

If you used a custom `FLEET_SSH_DIR`, substitute its absolute agent socket path in the validation command. Compose validation checks configuration, not provider access. After startup, log in as `admin`, ask Fleet Help a question, and use the Context page's re-index action to check embedding access. A successful web login alone does not verify the AI or embedding key.

After changing `.env`, run `make start` so Compose recreates affected containers. Changing `SECRET_KEY` invalidates existing login tokens. Changing `ADMIN_PASSWORD` changes future logins but does not revoke issued tokens. Preserve `HOST_SECRET_KEY` unless you also migrate the encrypted credentials; the application has no automatic key-rotation migration.

## Quick Start

Complete [Create the `.env` secrets](#create-the-env-secrets), then run:

```bash
# Prepare SSH, build, run, wait for health, and sync hosts.csv if present
make start

# Open the web UI
open http://localhost:8080
```

Startup validates the admin password, JWT signing key, and host-encryption key.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLEET_PORT` | `8080` | Port the web UI listens on |
| `SSH_AUTH_SOCK_PATH` | required | Dedicated host SSH agent socket bridged to the non-root web container |
| `SSH_KNOWN_HOSTS_PATH` | `./.fleet-ssh/known_hosts` | Optional seed file copied into the UI-managed persistent trust database |
| `FLEET_KUBECONFIG_PATH` | empty | Absolute host path to the controller kubeconfig; required for Kubernetes-aware maintenance in Docker |
| `APP_ENV` | `development` | Application environment; required secrets are validated in every environment |
| `SECRET_KEY` | required | JWT signing key with at least 32 characters |
| `ADMIN_PASSWORD` | required | Web UI admin password with at least 12 characters |
| `HOST_SECRET_KEY` | required | Fernet key used to encrypt stored SSH and sudo passwords |
| `CORS_ORIGINS` | dev localhost origins | Comma-separated list of allowed browser origins |
| `ANSIBLE_JOB_TIMEOUT_SECONDS` | `3600` | Maximum runtime for one queued Ansible job |
| `ANSIBLE_MAX_CONCURRENT_JOBS` | `4` | Maximum concurrent Ansible jobs |
| `ANSIBLE_FORKS` | `10` | Maximum hosts Ansible may operate on concurrently inside one fleet-scoped job; playbook `serial` still takes precedence |
| `AI_HELPER_API_KEY` | empty | Provider-issued credential for Fleet Help; see secret setup above |
| `AI_HELPER_MODEL` | `aws/anthropic/bedrock-claude-sonnet-4-6` | Chat model API ID in `.env.example` |
| `AI_HELPER_BASE_URL` | `https://inference-api.nvidia.com/v1` | Chat API base URL in `.env.example`; use the endpoint matching the key |
| `EMBED_MODEL` | `nvidia/qwen/qwen3-embedding-0.6b` | Embedding model shared by documentation and completed-job retrieval |
| `EMBED_DIM` | `1024` | Embedding output dimension in `.env.example`; must match the selected model |
| `EMBED_API_KEY` | unset | Optional embedding credential; omit to reuse `AI_HELPER_API_KEY` |
| `EMBED_BASE_URL` | unset | Optional embedding endpoint; omit to reuse `AI_HELPER_BASE_URL` |
| `MILVUS_URI` | `http://localhost:19530` | Host-facing URI in `.env.example`; Compose sets `http://milvus:19530` inside containers |
| `MILVUS_TOKEN` | unset | Optional `username:password` for the Rust ingester only; leave commented for the bundled stack |
| `DOCS_URLS_FILE` | `/app/docs/urls.txt` | URL-prefix list used by the web container's documentation indexer |
| `DOCS_MARKDOWN_DIR` | `/app/data/docs-crawled` | Directory for crawled Markdown |
| `DOCS_INGESTER_BIN` | `/usr/local/bin/fleet-doc-ingester` | Rust documentation ingester executable |
| `NAT_BASE_URL` | `http://nat:8000` | Internal NeMo Agent Toolkit endpoint in `.env.example`; no secret is required for this URL |

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

For unattended `make start` enrollment, copy `hosts.csv.example` to the ignored `hosts.csv` file and add the independently verified fingerprint for each new SSH device:

```csv
name,endpoint,transport,ssh_user,ssh_password,become_password,passwordless_ssh,bootstrap_password,daemon_port,ssh_fingerprint
compute-01,192.0.2.10,ssh,fleetadmin,,,true,,,SHA256:REPLACE_WITH_VERIFIED_ED25519_FINGERPRINT
reachy-lab,reachy-mini.local,reachy_daemon,,,,true,,8000,
```

Protect a credential-bearing manifest with `chmod 600 hosts.csv`. Remove any one-time `bootstrap_password` after successful enrollment; matching existing password-authenticated devices can be synced later without putting their stored password back in the CSV.

For password authentication, set `passwordless_ssh=false` and put the persistent SSH password in `ssh_password`. One-time bootstrap passwords are never stored; persistent SSH and sudo passwords are encrypted before database storage. Treat CSV files containing passwords as temporary secrets and delete them securely after import.

Use **Download CSV** on the Devices page to export every device with the same columns used by the importer. The export includes inventory names and connection settings, but never stored SSH, sudo, or one-time bootstrap passwords. Add the password back to any password-authenticated SSH row before importing it.

### Generated Ansible Inventory

The database is the source of truth. Fleet Manager regenerates `data/inventory/hosts.json` after enrollment and whenever a scan changes capabilities. It provides `managed_hosts`, `compute`, `gpu`, `nvidia_gpu`, `cpu`, `fabric_manager`, `mig`, and `reachy_ssh` groups. Reachy daemon devices stay out of general SSH groups. A Reachy enters only `reachy_ssh` after its dedicated maintenance access is verified.

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
5. To enable app reset, open the device and select **Enable app reset**. Verify the robot's ED25519 SSH fingerprint through a trusted channel and configure the `pollen` SSH account or another authorized account.

**Reset Reachy apps** is a destructive, typed-confirmation operation. It verifies `/venvs/mini_daemon` exists, removes only `/venvs/apps_venv`, and reports whether the environment was removed or already absent. Apps must be reinstalled afterward.

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
ansible-playbook playbooks/system_update.yml
ansible-playbook playbooks/docker_cleanup.yml
ansible-playbook playbooks/maintenance_assessment.yml

# Add users (safe groups/shell defaults are built in; override explicitly if needed)
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

# Reset the app environment on a verified Reachy SSH target
ansible-playbook playbooks/reachy_app_reset.yml --limit reachy-mini

# Manage sudoers
ansible-playbook playbooks/manage_sudoers.yml
ansible-playbook playbooks/host_bootstrap.yml --limit ast-spark-01
ansible-playbook playbooks/host_drain.yml -e '{"drain_action":"status"}'
ansible-playbook playbooks/mig_management.yml -e '{"mig_action":"status"}'

# Target specific hosts
ansible-playbook playbooks/system_update.yml --limit ast-spark-01
```

### Kubernetes-aware maintenance

Kubernetes API work runs on the Ansible controller. Managed nodes do not need `kubectl` or a kubeconfig. Set the controller kubeconfig before running Ansible directly:

```bash
export KUBECONFIG="$HOME/.kube/config"
ansible-playbook playbooks/host_drain.yml -e drain_action=status
```

For Fleet Manager in Docker, set an absolute host path in `.env`, then recreate the web container:

```dotenv
FLEET_KUBECONFIG_PATH=/absolute/path/to/.kube/config
```

```bash
docker compose up -d --build --force-recreate web
```

The controller identity needs enough RBAC to list nodes and pods, patch node schedulability, and create pod evictions. A host matches a Kubernetes node by the optional `kubernetes_node_name` host variable, then by inventory name, `ansible_host`, discovered hostname/FQDN, or primary IP. Set `kubernetes_context` per host or group when one controller kubeconfig contains multiple clusters. If local kubelet, K3s, RKE2, or MicroK8s files indicate membership but the selected context has no matching node, disruptive work stops instead of treating the host as standalone.

Disruptive playbooks run one host at a time by default. A matching node is drained before maintenance and returned to its original scheduling state afterward. A node that was already cordoned stays cordoned. Hosts that do not match a node continue normally. If the Kubernetes API cannot be checked, disruptive work fails closed.

Normal drains use the Eviction API, respect PodDisruptionBudgets, ignore DaemonSets, and refuse to delete `emptyDir` data. Allow `emptyDir` eviction for a planned operation explicitly:

```bash
ansible-playbook playbooks/reboot.yml \
  -e force_reboot=true \
  -e kubernetes_delete_emptydir_data=true
```

`force_reboot=true` only reboots a host without `/var/run/reboot-required`; it does not bypass Kubernetes safety. The emergency `force=true` option is intentionally destructive: it permits unmanaged pods and `emptyDir` deletion, bypasses PodDisruptionBudgets by deleting instead of evicting, and continues even if membership or drain cannot be verified.

```bash
ansible-playbook playbooks/reboot.yml \
  --limit ast-spark-01 \
  -e force_reboot=true \
  -e force=true
```

Use manual drain control when needed:

```bash
ansible-playbook playbooks/host_drain.yml -e drain_action=status
ansible-playbook playbooks/host_drain.yml -e drain_action=drain
ansible-playbook playbooks/host_drain.yml -e drain_action=resume
```

The main controls are `maintenance_batch_size` (default `1`), `kubernetes_drain_timeout` (default `900` seconds), `kubernetes_delete_emptydir_data` (default `false`), `kubernetes_node_name`, `kubernetes_context`, and `kubernetes_kubeconfig`. Set `kubernetes_membership_required=false` only to dismiss stale local membership files on a confirmed standalone host. Direct CLI runs can pass `-e force=true` as an emergency bypass.

## Fleet Documentation Ingestion

The bundled standalone Milvus uses `COMMON_STORAGETYPE=local`, as in the [upstream Milvus 2.4.21 standalone script](https://github.com/milvus-io/milvus/blob/v2.4.21/scripts/standalone_embed.sh). Vector data and the message queue persist in `milvus-local-data`; metadata persists in `etcd-local-data`. Back up and restore these volumes together. This configuration is for the single-container Milvus service, not a distributed Milvus cluster.

The Rust doc ingester crawls every HTML page under each URL prefix in `docs/urls.txt`, includes local Markdown guidance from `docs/*.md`, converts content to Markdown, embeds the chunks with the `.env` embedding settings, and rebuilds the `fleet_docs` collection in Milvus. The Context UI also accepts UTF-8 `.txt`, `.md`, and `.markdown` uploads, optionally associates them with a device, and adds current discovery facts plus manual device attributes to the same rebuild. The included `docs/fleet-manager-ui.md` file teaches Fleet Help how to guide users through the UI.

In Docker, the web image builds this tool into `/usr/local/bin/fleet-doc-ingester`. The Context page's re-index action runs that binary inside the web container and writes generated Markdown to `/app/data/docs-crawled`. Uploaded source text and associations are stored in the Fleet Manager database; temporary Markdown index sources are generated for each rebuild.

```bash
# Start Milvus first
docker compose up -d etcd milvus

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

Both Fleet Help chat modes also read fresh job evidence directly from the activity database for every question, independently of embeddings or Milvus. Expand a run in Activity and choose **Ask Fleet Help** to discuss that exact job. Chat on a device page scopes recent runs to that device; explicit job IDs or device names in a question take precedence. Follow-ups refresh the evidence. The supplied context includes job metadata, per-host recaps, structured results, and bounded log excerpts that prioritize failed tasks, matching output and the log tail. Running logs are marked partial, and omitted output is identified. These records describe observed operation results, not live device health.

NAT uses `tool_calling_agent` to preserve conversation history, the system prompt and streamed tool calls. Optional Kubernetes and UniFi MCP definitions are omitted at startup unless both their server URL and token are configured; missing optional settings no longer prevent Fleet Help from starting. Embedding failures can still limit historical semantic search, but do not prevent fresh job evidence from reaching either chat mode.

Fleet Help's sole system prompt is `workflow.system_prompt` in `nat/config.yml`. NAT uses it directly, and the direct-LLM fallback reads the same text for each request. Supplied documentation, uploaded context, and job evidence stay separate from system instructions. The prompt favors direct answers, evidence-backed diagnoses, and a small number of useful next steps. NAT can search fleet guidance, completed job history, and NVIDIA Dynamo, AIPerf, NVCF, and DSX documentation. Kubernetes and UniFi definitions are not exposed to the agent unless explicitly added to `workflow.tool_names`; the fallback has no callable tools.

Both images include the canonical config, and Compose mounts the same file read-only into both services. After editing the prompt, restart `nat` to reload its workflow; the fallback picks up edits on its next request. When upgrading to this shared-prompt setup, rebuild and recreate `web` and `nat` with `docker compose up -d --build web nat`. Image-only deployments also need both images rebuilt after prompt changes. The direct fallback reports a configuration error if the prompt is missing or invalid instead of silently using another policy.

### Switching from MinIO

Existing installations start with empty search indexes in the new `etcd-local-data` and `milvus-local-data` volumes. Both volumes are new because the old etcd metadata points to objects stored in MinIO. Changing only the storage backend would leave those objects unavailable. This is a rebuild of derived indexes, not an in-place conversion of MinIO data.

1. Finish any running fleet operations, then stop the stack using the updated Compose file. Keep the same Compose project name used by your existing deployment:

   ```bash
   SSH_AUTH_SOCK_PATH="$PWD/.fleet-ssh/agent.sock" docker compose down --remove-orphans
   ```

   Substitute your dedicated socket path if customized. This removes the retired MinIO container too. Do not add `--volumes` or `-v`. Back up `fleet-data`, the old `etcd-data`, `milvus-data`, and `minio-data` volumes, and `.env` while the services are stopped. Docker prefixes volume names with the Compose project name.
2. Remove the unused `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` entries from `.env`, then run `make start`. Fleet Manager's database, uploaded context, credentials, and job history remain in the existing `fleet-data` volume.
3. Open **Context** and run its re-index action to rebuild documentation and uploaded-context search. Completed-job search backfills from the activity database at web startup. Both rebuilds require working embedding credentials and can incur provider usage. Check re-index status and web logs before relying on semantic search; restart `web` to retry the job backfill if the embedding service was unavailable.

The old storage volumes remain available for rollback. To roll back, stop the updated stack without deleting volumes, restore the previous Compose file and its storage credentials, and start with the same project name. Keep the old three storage volumes together; they do not contain indexing changes made after the switch. Delete them only after verifying the new indexes and your backups. Custom Milvus collections outside Fleet Manager are not rebuilt by these steps; export them before switching if you need them.

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
│   ├── system_update.yml       # Focused rolling package updates
│   ├── maintenance_assessment.yml # Preflight and health assessment
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
├── templates/                  # User config templates
├── scripts/                    # Startup and enrollment helpers
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
