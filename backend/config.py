from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


INSECURE_SECRET_KEYS = {
    "changeme",
    "change-this-to-a-random-string",
    "secret",
    "development",
}
INSECURE_ADMIN_PASSWORDS = {
    "admin",
    "changeme",
    "password",
    "password123",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:////app/data/fleet.db"
    secret_key: str = ""
    admin_username: str = "admin"
    admin_password: str = ""
    jwt_expiry_hours: int = 8
    ansible_dir: Path = Path("/app/ansible")
    data_dir: Path = Path("/app/data")
    inventory_file: Path | None = None
    ansible_job_timeout_seconds: int = 3600
    ansible_max_concurrent_jobs: int = 4
    ansible_forks: int = 10
    ssh_known_hosts_file: Path = Path("/app/data/ssh/known_hosts")
    ssh_known_hosts_seed_file: Path | None = None
    host_secret_key: str = ""
    cors_origins: str = ""

    # AI Helper (OpenAI-compatible endpoint)
    ai_helper_api_key: str = ""
    ai_helper_model: str = ""
    ai_helper_base_url: str = ""

    # NeMo Agent Toolkit
    nat_base_url: str = ""  # e.g. "http://nat:8000"

    # Milvus / docs indexing
    milvus_uri: str = "http://milvus:19530"
    embed_model: str = "nvidia/qwen/qwen3-embedding-0.6b"
    embed_dim: int | None = None
    embed_api_key: str = ""
    embed_base_url: str = ""
    docs_dir: Path = Path("/app/docs")
    docs_urls_file: Path = Path("/app/docs/urls.txt")
    docs_markdown_dir: Path = Path("/app/data/docs-crawled")
    docs_ingester_bin: Path = Path("/usr/local/bin/dgx-doc-ingester")

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"dev", "development", "local", "test"}

    @property
    def resolved_inventory_file(self) -> Path:
        return self.inventory_file or (self.data_dir / "inventory" / "hosts.json")

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if not origins and self.is_development:
            origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

        validated = []
        for origin in origins:
            if origin == "*":
                raise RuntimeError("CORS_ORIGINS must not contain a wildcard")
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise RuntimeError(f"Invalid CORS origin: {origin}")
            validated.append(f"{parsed.scheme}://{parsed.netloc}")
        return list(dict.fromkeys(validated))

    def validate_runtime_settings(self) -> None:
        problems = []
        if self.secret_key.lower() in INSECURE_SECRET_KEYS or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be set to a non-default value with at least 32 characters")
        if self.admin_password.lower() in INSECURE_ADMIN_PASSWORDS or len(self.admin_password) < 12:
            problems.append("ADMIN_PASSWORD must be changed from the default and be at least 12 characters")
        if not self.host_secret_key:
            problems.append("HOST_SECRET_KEY must be set so stored host credentials are encrypted")
        else:
            try:
                Fernet(self.host_secret_key.encode("utf-8"))
            except (TypeError, ValueError):
                problems.append("HOST_SECRET_KEY must be a valid Fernet key")
        try:
            self.cors_origin_list
        except RuntimeError as exc:
            problems.append(str(exc))
        if not 1 <= self.ansible_forks <= 100:
            problems.append("ANSIBLE_FORKS must be between 1 and 100")
        if problems:
            raise RuntimeError("; ".join(problems))


settings = Settings()
