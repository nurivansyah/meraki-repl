"""Configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # Elasticsearch
    es_hosts: str = Field(default="http://localhost:9200", alias="ELASTICSEARCH_HOSTS")
    es_username: str = Field(default="elastic", alias="ES_USERNAME")
    es_password: str = Field(default="changeme", alias="ELASTIC_PASSWORD")

    # Meraki
    meraki_org_id: str = Field(default="", alias="MERAKI_ORG_ID")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="changeme", alias="NEO4J_PASSWORD")
    neo4j_auth: bool = Field(default=True, alias="NEO4J_AUTH")
    impact_default_depth: int = Field(default=10, alias="IMPACT_DEFAULT_DEPTH")

    # NetBox
    netbox_url: str = Field(default="http://localhost:8000", alias="NETBOX_URL")
    netbox_token: str = Field(default="", alias="NETBOX_TOKEN")

    # Postgres
    pg_host: str = Field(default="localhost", alias="PG_HOST")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_database: str = Field(default="twin", alias="PG_DATABASE")
    pg_user: str = Field(default="twin", alias="PG_USER")
    pg_password: str = Field(default="changeme", alias="PG_PASSWORD")

    # Auth
    jwt_secret: str = Field(default="dev-secret-change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_hours: int = Field(default=24 * 30, alias="JWT_EXPIRY_HOURS")
    bootstrap_token: str | None = Field(default=None, alias="BOOTSTRAP_TOKEN")

    # Session
    session_secret: str = Field(default="dev-session-secret", alias="SESSION_SECRET")
    session_idle_hours: int = Field(default=8, alias="SESSION_IDLE_HOURS")

    # Setup
    setup_enabled: bool = Field(default=True, alias="SETUP_ENABLED")

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )


settings = Settings()
