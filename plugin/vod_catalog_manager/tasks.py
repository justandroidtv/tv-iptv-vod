from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from celery import shared_task
from celery.exceptions import Ignore
from django.db import close_old_connections, transaction

from .engine import RegexRule, apply_rule, validate_pattern
from .job_contract import normalize_job_request

logger = logging.getLogger("vod_catalog_manager")

JOB_NAME = "vod_catalog_manager.regex_apply"
BATCH_SIZE = 250


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent


def _job_dir() -> Path:
    path = _plugin_root() / "data" / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_job_event(task_id: str, event: dict[str, Any]) -> None:
    path = _job_dir() / f"{task_id}.jsonl"
    record = {"at": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _model_for_scope(scope: str):
    from apps.vod.models import Episode, Movie, Series

    return {"movie": Movie, "series": Series, "episode": Episode}[scope]


def cancel_path(task_id: str) -> Path:
    return _job_dir() / f"{task_id}.cancel"


def request_cancel(task_id: str) -> str:
    path = cancel_path(task_id)
    path.write_text("requested\n", encoding="utf-8")
    return path.name


def _snapshot_path(task_id: str) -> Path:
    path = _job_dir() / f"{task_id}.snapshot.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _progress(task_id: str, state: str, **values: Any) -> dict[str, Any]:
    payload = {"state": state, **values}
    _write_job_event(task_id, payload)
    return payload


@shared_task(
    bind=True,
    name=JOB_NAME,
    acks_late=True,
    reject_on_worker_lost=True,
)
def regex_apply_task(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply a reviewed regex across a VOD title set in bounded transactions.

    The task changes only canonical name fields. Every batch gets a JSONL
    snapshot before its transaction so the original value is available for
    optimistic rollback tooling.
    """
    task_id = str(self.request.id)
    try:
        request = normalize_job_request(params)
        validate_pattern(request.pattern)
        flags = re.IGNORECASE if request.case_insensitive else 0
        rule = RegexRule(
            pattern=request.pattern,
            replacement=request.replacement,
            flags=flags,
            enabled=True,
        )
        model = _model_for_scope(request.scope)
        queryset = model.objects.all().order_by("id").values("id", "name")
        total = queryset.count()
        if request.max_rows:
            total = min(total, request.max_rows)
            queryset = queryset[:request.max_rows]
        scanned = matched = updated = conflicts = 0
        snapshot = _snapshot_path(task_id)
        _write_job_event(
            task_id,
            {
                "state": "started",
                "scope": request.scope,
                "total": total,
                "max_rows": request.max_rows,
                "snapshot": snapshot.name,
            },
        )
        batch: list[dict[str, Any]] = []

        def flush() -> None:
            nonlocal updated, conflicts
            if not batch:
                return
            with snapshot.open("a", encoding="utf-8") as fh:
                for item in batch:
                    fh.write(
                        json.dumps(
                            {
                                "id": item["id"],
                                "old": item["old"],
                                "new": item["new"],
                                "scope": request.scope,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            with transaction.atomic():
                for item in batch:
                    changed = model.objects.filter(
                        id=item["id"], name=item["old"]
                    ).update(name=item["new"][:255])
                    if changed:
                        updated += 1
                    else:
                        conflicts += 1
            batch.clear()

        for row in queryset.iterator(chunk_size=BATCH_SIZE):
            if cancel_path(task_id).exists():
                result = _progress(
                    task_id,
                    "revoked",
                    scope=request.scope,
                    total=total,
                    scanned=scanned,
                    matched=matched,
                    updated=updated,
                    conflicts=conflicts,
                    snapshot=snapshot.name,
                )
                self.update_state(state="REVOKED", meta=result)
                raise Ignore()
            scanned += 1
            old = str(row["name"] or "")
            new = apply_rule(old, rule)
            if new != old:
                matched += 1
                batch.append({"id": row["id"], "old": old, "new": new})
            if len(batch) >= BATCH_SIZE:
                flush()
                if cancel_path(task_id).exists():
                    result = _progress(
                        task_id,
                        "revoked",
                        scope=request.scope,
                        total=total,
                        scanned=scanned,
                        matched=matched,
                        updated=updated,
                        conflicts=conflicts,
                        snapshot=snapshot.name,
                    )
                    self.update_state(state="REVOKED", meta=result)
                    raise Ignore()
                meta = _progress(
                    task_id,
                    "running",
                    scope=request.scope,
                    total=total,
                    scanned=scanned,
                    matched=matched,
                    updated=updated,
                    conflicts=conflicts,
                )
                self.update_state(state="PROGRESS", meta=meta)
        flush()
        result = _progress(
            task_id,
            "completed",
            scope=request.scope,
            total=total,
            scanned=scanned,
            matched=matched,
            updated=updated,
            conflicts=conflicts,
            snapshot=snapshot.name,
        )
        self.update_state(state="SUCCESS", meta=result)
        return result
    except Exception as exc:
        logger.exception("VOD async regex task failed")
        result = _progress(task_id, "failed", error=str(exc)[:500])
        self.update_state(state="FAILURE", meta=result)
        raise
    finally:
        close_old_connections()
