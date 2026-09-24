from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_ASYNC_ROWS = 100_000
SUPPORTED_SCOPES = {"movie", "series", "episode"}
TERMINAL_STATES = {"completed", "failed", "revoked"}


@dataclass(frozen=True)
class JobRequest:
    scope: str
    max_rows: int = 0
    pattern: str = ""
    replacement: str = ""
    case_insensitive: bool = True


def normalize_job_request(params: dict[str, Any] | None) -> JobRequest:
    params = dict(params or {})
    scope = str(params.get("scope") or "movie").strip().lower()
    if scope not in SUPPORTED_SCOPES:
        raise ValueError("scope must be movie, series or episode")
    pattern = str(params.get("pattern") or "")
    replacement = str(params.get("replacement") or "")
    case_value = params.get("case_insensitive", True)
    case_insensitive = str(case_value).lower() not in {"false", "0", "no"}
    try:
        max_rows = int(params.get("max_rows") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_rows must be an integer") from exc
    max_rows = max(0, min(MAX_ASYNC_ROWS, max_rows))
    return JobRequest(
        scope=scope,
        max_rows=max_rows,
        pattern=pattern,
        replacement=replacement,
        case_insensitive=case_insensitive,
    )
