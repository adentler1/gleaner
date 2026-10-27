"""Loads watches and sources from YAML files in the private config directory."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

ADAPTER_TYPES = (
    "api",
    "rss",
    "html",
    "changedetection",
    "state",
    "playwright",
    "llm-extract",
    "imap",
)

# Adapters implemented and dispatchable in milestone 1a. Other values in
# ADAPTER_TYPES are valid config (so config for later milestones can be
# authored early) but the runner refuses to schedule them until implemented.
IMPLEMENTED_ADAPTERS = ("api", "rss", "html")


class SourceHealthConfig(BaseModel):
    stale_after_days: int = 30
    alert_on_zero_results: bool = True


class ExtractConfig(BaseModel):
    item: str | None = None  # html adapter: CSS selector for the item container
    fields: dict[str, str] = Field(default_factory=dict)  # field name -> selector/path, meaning is adapter-specific


class Source(BaseModel):
    id: str
    adapter: Literal[ADAPTER_TYPES]
    url: str
    schedule: str = "daily"
    extract: ExtractConfig | None = None
    items_path: str | None = None  # api adapter: dotted path to the list of items
    required_fields: list[str] = Field(default_factory=list)
    health: SourceHealthConfig = Field(default_factory=SourceHealthConfig)
    fixture: str | None = None
    terms_checked: date | None = None
    date_locale: str = "en"

    @field_validator("id")
    @classmethod
    def id_is_slug(cls, v: str) -> str:
        if not v or any(c.isspace() for c in v):
            raise ValueError(f"source id {v!r} must be a non-empty slug with no whitespace")
        return v


class Watch(BaseModel):
    id: str
    pattern: Literal["stream", "state"]
    description: str
    sources: list[str]
    hard_filters: dict[str, str] = Field(default_factory=dict)
    alert_threshold: int = Field(default=70, ge=0, le=100)
    calendar: str = "private"

    @field_validator("id")
    @classmethod
    def id_is_slug(cls, v: str) -> str:
        if not v or any(c.isspace() for c in v):
            raise ValueError(f"watch id {v!r} must be a non-empty slug with no whitespace")
        return v


class Config(BaseModel):
    watches: list[Watch]
    sources: list[Source]

    @model_validator(mode="after")
    def check_references_and_uniqueness(self) -> "Config":
        source_ids = [s.id for s in self.sources]
        if len(source_ids) != len(set(source_ids)):
            dupes = {s for s in source_ids if source_ids.count(s) > 1}
            raise ValueError(f"duplicate source ids: {sorted(dupes)}")

        watch_ids = [w.id for w in self.watches]
        if len(watch_ids) != len(set(watch_ids)):
            dupes = {w for w in watch_ids if watch_ids.count(w) > 1}
            raise ValueError(f"duplicate watch ids: {sorted(dupes)}")

        known_sources = set(source_ids)
        for watch in self.watches:
            missing = [s for s in watch.sources if s not in known_sources]
            if missing:
                raise ValueError(f"watch {watch.id!r} references unknown sources: {missing}")

        return self

    def source_by_id(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(f"no source with id {source_id!r}")

    def watch_by_id(self, watch_id: str) -> Watch:
        for w in self.watches:
            if w.id == watch_id:
                return w
        raise KeyError(f"no watch with id {watch_id!r}")


def load_config(config_dir: Path) -> Config:
    """Reads every *.yaml / *.yml file in config_dir and merges their
    top-level watches: / sources: lists, so each source or watch can live
    in its own file for a reviewable git history."""
    config_dir = Path(config_dir)
    watches: list[dict] = []
    sources: list[dict] = []

    yaml_files = sorted(config_dir.glob("*.yaml")) + sorted(config_dir.glob("*.yml"))
    if not yaml_files:
        raise FileNotFoundError(f"no *.yaml / *.yml files found in {config_dir}")

    for path in yaml_files:
        with path.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: top-level YAML must be a mapping")
        watches.extend(doc.get("watches", []) or [])
        sources.extend(doc.get("sources", []) or [])

    return Config(watches=watches, sources=sources)
