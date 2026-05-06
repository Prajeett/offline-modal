from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_runtime_env: str = "mac_test"
    model_runtime: str = "ollama"
    model_name: str = "gemma4:4b"
    ollama_base_url: str = "http://127.0.0.1:11434"

    max_concurrent_streams: int = 5
    queue_size: int = 20
    max_tokens_default: int = 700
    max_tokens_hard_cap: int = 900
    request_timeout_seconds: int = 300

    auth_shared_bearer_token: str = "replace_me"
    cors_allowed_origins: str = "http://localhost,https://sydaux.com,https://www.sydaux.com"

    search_scope_mode: str = "open"
    search_allowed_domains: str = ""

    sqlite_db_path: str = "./data/app.db"

    rate_limit_per_minute: int = 20
    rate_limit_burst: int = 5

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def allowed_domains(self) -> set[str]:
        return {d.strip().lower() for d in self.search_allowed_domains.split(",") if d.strip()}
