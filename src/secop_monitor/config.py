import yaml
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

import pytz


class AppConfig(BaseModel):
    db_url: str = Field(default="sqlite:///./secop.db")
    timezone: str = Field(default="America/Bogota")
    notifier: Literal["stdout", "slack"] = Field(default="stdout")
    score_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    max_items_per_run: int = Field(default=500, gt=0)


class SECopApiConfig(BaseModel):
    base_url: str
    auth: dict | None = None


class SourceConfig(BaseModel):
    collector: Literal["fixture", "secop_api"] = Field(default="fixture")
    fixture_path: str = Field(default="./data/fixtures/secop_items.json")
    secop_api: SECopApiConfig | None = None


class FiltersConfig(BaseModel):
    published_within_days: int = Field(default=14, ge=0)
    min_budget: float = Field(default=0.0, ge=0.0)
    entity_allowlist: list[str] = Field(default_factory=list)
    entity_blocklist: list[str] = Field(default_factory=list)
    location_allowlist: list[str] = Field(default_factory=list)
    modality_allowlist: list[str] = Field(default_factory=list)


class QueryConfig(BaseModel):
    name: str
    keywords_any: list[str] = Field(default_factory=list)
    keywords_all: list[str] = Field(default_factory=list)
    keywords_not: list[str] = Field(default_factory=list)
    phrases: list[str] = Field(default_factory=list)
    synonyms: dict[str, list[str]] = Field(default_factory=dict)


class SlackConfig(BaseModel):
    webhook_env_var: str = Field(default="SLACK_WEBHOOK_URL", min_length=1)
    username: str = Field(default="secop-monitor")


class NotificationsConfig(BaseModel):
    slack: SlackConfig = Field(default_factory=SlackConfig)
    max_alerts_per_run: int = Field(default=20, gt=0)


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    source: SourceConfig = Field(default_factory=SourceConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    queries: list[QueryConfig] = Field(default_factory=list)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)

    @model_validator(mode="after")
    def check_slack_config(self) -> "Config":
        if self.app.notifier == "slack" and not self.notifications.slack.webhook_env_var:
            raise ValueError("Slack notifier selected but webhook_env_var is empty")
        return self

    @model_validator(mode="after")
    def check_source_config(self) -> "Config":
        if self.source.collector == "secop_api" and self.source.secop_api is None:
            raise ValueError("secop_api config required when collector=secop_api")
        return self

    def get_timezone(self) -> pytz.BaseTzInfo:
        """Retorna el objeto timezone compilado para cálculos."""
        return pytz.timezone(self.app.timezone)


def load_config(path: str) -> Config:
    """Carga y valida la configuración desde un archivo YAML."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Config(**data)
