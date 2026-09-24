from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    dispatcharr_base_url: str
    dispatcharr_api_key: str
    dispatcharr_plugin_key: str
    control_plane_api_token: str
    db_path: Path
    bind: str
    port: int


def load_settings() -> Settings:
    db = Path(os.environ.get("CONTROL_PLANE_DB", "./data/controlplane.sqlite3"))
    db.parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        dispatcharr_base_url=os.environ.get(
            "DISPATCHARR_BASE_URL", "http://127.0.0.1:9191"
        ).rstrip("/"),
        dispatcharr_api_key=_required("DISPATCHARR_API_KEY"),
        dispatcharr_plugin_key=os.environ.get(
            "DISPATCHARR_PLUGIN_KEY", "vod_catalog_manager"
        ),
        control_plane_api_token=_required("CONTROL_PLANE_API_TOKEN"),
        db_path=db,
        bind=os.environ.get("CONTROL_PLANE_BIND", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT", "9393")),
    )
