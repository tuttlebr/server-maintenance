# Security Policy: Fleet Manager

## Reporting a Vulnerability

If you discover a potential security vulnerability in Fleet Manager, please **do not open a public issue, merge request, or discussion.**

Report the vulnerability privately through one of these channels:

- **Web, preferred:** [NVIDIA Vulnerability Disclosure Program](https://www.nvidia.com/en-us/security/)
- **Email:** [psirt@nvidia.com](mailto:psirt@nvidia.com)
  - Use the [NVIDIA public PGP key](https://www.nvidia.com/en-us/security/pgp-key) when sending sensitive information.
- **GitLab:** Use this repository's **Security** tab and its private vulnerability reporting workflow.

Include:

- Fleet Manager version, branch, or commit
- Affected component or API
- Vulnerability type
- Reproduction steps
- Proof-of-concept material, if available
- Required access and deployment conditions
- Potential impact on the management service or managed hosts
- Suggested mitigation, if known

Detailed reports help NVIDIA evaluate and address issues faster.

NVIDIA's Product Security Incident Response Team will acknowledge the report, validate the issue and its severity, coordinate remediation, and publish a security bulletin when appropriate.

## Security Architecture & Context

Fleet Manager is a Dockerized FastAPI and Vue application for administering Linux compute, edge devices, and supported robots. It uses capability-gated Ansible operations for SSH devices and documented adapter APIs for other transports, including Reachy Mini Wireless.

This software operates as an administrative application and service. Its primary security responsibility is protecting fleet-management authority, host credentials, SSH access, privileged automation, operational state, and job output.

**Repository Exposure Classification:** Internal.
Basis: the origin remote is hosted on NVIDIA's self-managed GitLab service.

**Service Exposure Classification:** Internal-Sensitive (medium confidence).
Basis: the service performs privileged fleet administration, handles SSH and sudo credentials, receives an SSH agent socket, and manages system accounts, packages, firmware, and host state. No external distribution, customer-facing exposure, or regulated scope was identified in the repository.

### Components and Security Boundaries

- The Vue SPA communicates with the FastAPI API through `/api/v2`.
- `/api/v2/auth/login` accepts the configured administrator credentials. Successful authentication produces an HS256 bearer token with an eight-hour lifetime.
- With the exception of login, health, favicon, and static frontend routes, API operations require a valid bearer token.
- The application has one administrative identity and no role separation. An authenticated user can perform every supported fleet operation.
- `backend/services/ansible_runner.py` restricts execution to an explicit playbook allowlist, validates target hosts and extra variables, and applies per-host locking and concurrency limits.
- The runtime inventory is generated from SQLite by `backend/services/inventory_writer.py`. It excludes passwords and enforces strict SSH host-key checking.
- SSH and sudo passwords are encrypted with Fernet before storage. They are decrypted only when a job runs and are passed to Ansible through an anonymous file descriptor rather than command-line arguments.
- Job metadata and output are stored in SQLite and in mode `0600` log files under the application data volume. Known sensitive values are redacted before output is persisted.
- The web container receives a dedicated SSH agent socket and a read-only verified `known_hosts` file.
- Reachy Mini adapters use the robot daemon's local HTTP and WebSocket endpoints. That transport doesn't provide the SSH fingerprint trust flow and must remain on a trusted, segmented management network.
- The web container runs as a non-root user with a read-only root filesystem, all Linux capabilities dropped, and `no-new-privileges` enabled.
- Milvus, MinIO, etcd, and the NeMo Agent Toolkit service communicate over the Docker network. Milvus host ports are bound to loopback; the other auxiliary services aren't published by the Compose configuration.
- The documentation indexer crawls configured integration documentation URL prefixes, sends document chunks to an embedding service, and rebuilds the `fleet_docs` Milvus collection.
- The help-chat path can send prompts and retrieved documentation to configured LLM, embedding, and documentation services.
- Direct command-line use of the Ansible playbooks is outside the web authentication boundary and depends on host operating-system access controls.

### Existing Security Controls

- Required startup validation for the JWT key, administrator password, and Fernet key
- Persistent account and client login throttling
- Constant-time administrator credential and token-signature comparisons
- Expiring signed bearer tokens
- Explicit CORS origin validation with wildcard origins rejected
- Pydantic validation for hostnames, addresses, Linux account names, targeting, passwords, and Ansible values
- Rejection of Ansible template expressions and unsafe control characters
- An explicit playbook allowlist
- Explicit target selection or `all_hosts=true`
- Strict SSH host-key verification
- Encrypted host credentials and fail-closed decryption
- Secret transfer through anonymous file descriptors
- Secret redaction in stored job variables and streamed output
- Read-only container filesystem, dropped capabilities, and non-root processes
- Dependency audits in CI for Python, npm, and Rust dependencies

### Threat Model

1. **Administrative Session Compromise:** Fleet Manager uses one administrator identity without RBAC or operation-level authorization. Theft or guessing of the administrator password, JWT signing key, or an active bearer token would permit device registration, access changes, software operations, reboots, and other privileged actions across the fleet. Login throttling reduces online guessing but doesn't limit the authority of a valid session.

2. **Management-Plane Compromise Exposes Delegated Host Access:** The web process can access the SSH agent socket, the SQLite database, encrypted host credentials, and `HOST_SECRET_KEY`. Code execution in the web container could therefore request SSH signatures, decrypt stored passwords, and invoke allowed playbooks against registered hosts. Container hardening limits host-level privileges but doesn't preserve these application-level boundaries after process compromise.

3. **Credential Interception Without TLS:** Uvicorn listens over HTTP, and Compose publishes the web service through `FLEET_PORT`. If the service is exposed without a trusted TLS reverse proxy, login credentials, bearer tokens, host passwords, and user password operations could be intercepted or modified in transit.

4. **Automation Pivot Through Registered Targets:** `HostCreate` and the generated inventory validate the syntax of hostnames and addresses but don't enforce network ranges or an approved-host registry. A compromised administrator session could register another reachable address and run privileged allowlisted playbooks against it. Strict host-key verification mitigates impersonation only when `known_hosts` entries have been independently verified.

5. **Operational Data Disclosure Through Job History:** Ansible output is streamed to log files and copied into the `Job.output_log` database field. Redaction covers known secret keys and concrete secret values, but playbook output can still contain hostnames, account names, package state, hardware details, process information, filesystem information, and unexpected sensitive output from future tasks. Every authenticated administrator can retrieve this history.

6. **Browser Session Theft Through Client-Side Compromise:** `frontend/src/api.js` stores the administrative bearer token in `localStorage`, and the backend doesn't set a Content Security Policy or related browser-hardening headers. The current ANSI log renderer enables XML escaping, but a future unsafe rendering path, compromised frontend dependency, or injected script could read the token and obtain full administrative authority.

7. **Documentation and AI Trust-Boundary Abuse:** The Rust documentation ingester crawls configured URL prefixes, sends chunks to an embedding API, and replaces the Milvus collection by default. The help-chat service can also contact configured LLM and external documentation endpoints. Compromised upstream documentation or configuration could poison retrieval results, while sensitive chat content or internal documentation could be disclosed to an external provider. The help-chat path doesn't directly execute fleet operations, which limits the immediate impact of poisoned answers.

### Critical Security Assumptions

- Production deployments place a trusted TLS reverse proxy in front of the FastAPI service and restrict access to approved management networks.
- Every authenticated user is a trusted fleet administrator. The application doesn't provide multi-user isolation, RBAC, approval workflows, or separation of duties.
- The management host, Docker daemon, environment configuration, application data volume, and SSH agent socket are protected from untrusted users and workloads.
- The forwarded SSH agent is dedicated to this service and contains only the keys required for managed fleet hosts.
- Every SSH host key is verified through an independent trusted channel before being added to `known_hosts`.
- Network segmentation or deployment policy limits which systems the management container can reach. The application itself doesn't enforce address allowlists.
- `SECRET_KEY`, `ADMIN_PASSWORD`, `HOST_SECRET_KEY`, MinIO credentials, and external API keys are strong, unique, stored outside version control, and rotated after suspected exposure.
- Rotating `SECRET_KEY` is an acceptable mechanism for invalidating all existing bearer tokens. The service doesn't otherwise maintain a token-revocation list.
- Ansible playbooks, roles, templates, and group variables are reviewed as privileged code before deployment.
- Sensitive Ansible tasks use `no_log`, and future secret fields follow the runner's sensitive-key naming conventions so redaction recognizes them.
- MinIO, Milvus, etcd, and the NeMo Agent Toolkit service remain inaccessible from untrusted networks.
- Chat prompts and indexed documents are safe to send to the configured LLM and embedding providers. Operators don't submit credentials or confidential operational data to the help-chat interface.
- Direct CLI access to the playbooks is limited through management-host operating-system permissions and is granted only to trusted fleet administrators.
- SQLite and Docker volumes receive appropriate filesystem protection, backup, retention, and recovery handling. The application doesn't provide high availability or encrypted volume storage itself.

## Trust Model

Fleet Manager treats the authenticated administrator as fully trusted. It doesn't attempt to protect managed devices from an authorized administrator or distinguish read-only, maintenance, user-management, and security-sensitive roles.

The principal trust boundaries are:

- Browser to FastAPI API
- FastAPI API to SQLite and application data
- FastAPI and Ansible runner to the SSH agent
- Management container to managed fleet hosts
- Web service to NAT, Milvus, MinIO, and etcd
- Documentation indexer and chat services to external documentation, embedding, LLM, and MCP endpoints
- Trusted management-host shell users to direct Ansible execution

## Deployment and Operational Security

Operators should:

- Terminate TLS before traffic reaches the FastAPI service.
- Restrict `FLEET_PORT` with host firewall rules or bind it only to an approved management interface.
- Avoid exposing MinIO, etcd, Milvus, or NAT ports outside the trusted Docker network.
- Use a dedicated SSH agent with minimal key scope.
- Maintain a verified, read-only `known_hosts` file.
- Restrict and monitor access to `.env`, the Docker daemon, named volumes, backups, and application logs.
- Rotate all application, storage, SSH, and external API credentials after suspected compromise.
- Establish retention limits for job logs and operational scan data.
- Restrict outbound access to approved managed-host networks and approved NVIDIA documentation, LLM, embedding, and MCP endpoints.
- Review disruptive operations such as firmware updates, reboots, Kubernetes drains, MIG changes, sudoers changes, and bulk password resets before execution.

## Dependency Security

The repository uses npm and Cargo lockfiles, but Python dependencies are primarily specified as version ranges and container base images aren't pinned by digest. Production builds can therefore change when rebuilt.

CI runs Python, npm, and Rust vulnerability audits. Maintainers should also review audit failures, rebuild images regularly from approved versions, pin security-sensitive production dependencies where reproducibility is required, and validate updates before deploying them to the management environment.
