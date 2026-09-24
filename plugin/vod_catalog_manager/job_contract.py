from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_JOB_LIMIT = 500
SUPPORTED_SCOPES = {"movie", "series"}
TERMINAL_STATES = {"completed", "failed", "revoked"}


@dataclass(frozen=True)
class JobRequest:
    scope: str
    limit: int = MAX_JOB_LIMIT
    pattern: str = ""
    replacement: str = ""
    case_insensitive: bool = True


def normalize_job_request(params: dict[str, Any] | None) -> JobRequest:
    params = dict(params or {})
    scope = str(params.get("scope") or "movie").strip().lower()
    if scope not in SUPPORTED_SCOPES:
        raise ValueError("scope must be movie or series")
    pattern = str(params.get("pattern") or "")
    replacement = str(params.get("replacement") or "")
    case_value = params.get("case_insensitive", True)
    case_insensitive = str(case_value).lower() not in {"false", "0", "no"}
    try:
        limit = int(params.get("limit") or MAX_JOB_LIMIT)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    limit = max(1, min(MAX_JOB_LIMIT, limit))
    return JobRequest(
        scope=scope,
        limit=limit,
        pattern=pattern,
        replacement=replacement,
        case_insensitive=case_insensitive,
    )
