from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .client_profiles import all_client_profiles
from .config import Settings, load_settings
from .db import ControlPlaneDB
from .dispatcharr import DispatcharrClient
from .security import extract_bearer, token_matches


class RegexPreviewIn(BaseModel):
    scope: str = Field(default="movie", pattern="^(movie|series|episode)$")
    pattern: str = Field(min_length=1, max_length=256)
    replacement: str = Field(default="")
    limit: int = Field(default=100, ge=1, le=500)
    case_insensitive: bool = True


class RegexJobIn(BaseModel):
    scope: str = Field(default="movie", pattern="^(movie|series|episode)$")
    pattern: str = Field(min_length=1, max_length=256)
    replacement: str = Field(default="")
    max_rows: int = Field(default=0, ge=0, le=100_000)
    case_insensitive: bool = True
    confirm: bool = False


class CategoryRenameIn(BaseModel):
    category_id: int
    new_name: str = Field(min_length=1, max_length=255)
    confirm: bool = False


class CategoryVisibilityIn(BaseModel):
    account_id: int
    category_id: int
    enabled: bool
    confirm: bool = False


class CategoryMergeIn(BaseModel):
    source_category_id: int
    target_category_id: int
    confirm: bool = False


class CategoryDeleteIn(BaseModel):
    category_id: int
    confirm: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.db = ControlPlaneDB(settings.db_path)
    app.state.dispatcharr = DispatcharrClient(
        settings.dispatcharr_base_url,
        settings.dispatcharr_api_key,
        settings.dispatcharr_plugin_key,
    )
    yield


app = FastAPI(
    title="Dispatcharr VOD Control Plane",
    version="0.4.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/assets", StaticFiles(directory=_FRONTEND), name="assets")


def runtime() -> tuple[Settings, ControlPlaneDB, DispatcharrClient]:
    try:
        return app.state.settings, app.state.db, app.state.dispatcharr
    except AttributeError as exc:
        raise HTTPException(status_code=503, detail="Control Plane is starting") from exc


async def auth(
    authorization: str | None = Header(default=None),
) -> tuple[Settings, ControlPlaneDB, DispatcharrClient]:
    settings, db, client = runtime()
    token = extract_bearer(authorization)
    if not token_matches(token, settings.control_plane_api_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return settings, db, client


def _plugin_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc)[:500])


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_FRONTEND / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dispatcharr-vod-control-plane"}


@app.get("/api/dashboard")
async def dashboard(
    ctx=Depends(auth),
) -> dict[str, Any]:
    _, db, client = ctx
    try:
        plugin = await client.plugin_status()
    except Exception as exc:
        raise _plugin_error(exc)
    status = None
    status_error = None
    if plugin.get("enabled"):
        try:
            status = await client.action("status", {})
        except Exception as exc:
            status_error = str(exc)[:500]
    return {
        "plugin": {
            "key": plugin.get("key"),
            "name": plugin.get("name"),
            "version": plugin.get("version"),
            "enabled": plugin.get("enabled"),
            "loaded": plugin.get("loaded"),
        },
        "ready": bool(plugin.get("enabled") and status),
        "status": status,
        "status_error": status_error,
        "jobs": db.list_jobs(10),
    }


@app.get("/api/catalog")
async def catalog(
    kind: str = Query("movie", pattern="^(movie|series|episode)$"),
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx=Depends(auth),
) -> dict[str, Any]:
    _, _, client = ctx
    try:
        return await client.action(
            "catalog_query",
            {"kind": kind, "q": q, "page": page, "page_size": page_size},
        )
    except Exception as exc:
        raise _plugin_error(exc)


@app.get("/api/categories")
async def categories(
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx=Depends(auth),
) -> dict[str, Any]:
    _, _, client = ctx
    try:
        return await client.action(
            "category_list",
            {"q": q, "page": page, "page_size": page_size},
        )
    except Exception as exc:
        raise _plugin_error(exc)


@app.get("/api/regex/recipes")
async def regex_recipes(ctx=Depends(auth)) -> dict[str, Any]:
    _, _, client = ctx
    try:
        return await client.action("regex_library", {})
    except Exception as exc:
        raise _plugin_error(exc)


@app.post("/api/regex/preview")
async def regex_preview(
    payload: RegexPreviewIn,
    ctx=Depends(auth),
) -> dict[str, Any]:
    _, _, client = ctx
    try:
        return await client.action("regex_preview", payload.model_dump())
    except Exception as exc:
        raise _plugin_error(exc)


@app.post("/api/regex/jobs")
async def regex_job(
    payload: RegexJobIn,
    ctx=Depends(auth),
) -> dict[str, Any]:
    _, db, client = ctx
    preview_params = payload.model_dump(exclude={"confirm"})
    preview_params["limit"] = 100
    try:
        preview = await client.action("regex_preview", preview_params)
        if not payload.confirm:
            return {"status": "preview_required", "preview": preview}
        queued = await client.action(
            "regex_apply_async",
            payload.model_dump(),
        )
    except Exception as exc:
        raise _plugin_error(exc)
    if queued.get("job_id"):
        db.add_job(
            queued["job_id"],
            "regex_apply_async",
            payload.scope,
            payload.model_dump(exclude={"confirm"}),
        )
        db.audit(
            "control-plane",
            "regex_apply_async",
            {
                "job_id": queued["job_id"],
                "scope": payload.scope,
                "max_rows": payload.max_rows,
            },
        )
    return {"preview": preview, "queued": queued}


@app.get("/api/jobs")
async def jobs(limit: int = Query(50, ge=1, le=200), ctx=Depends(auth)):
    _, db, _ = ctx
    return {"jobs": db.list_jobs(limit)}


@app.get("/api/jobs/{task_id}")
async def job(task_id: str, ctx=Depends(auth)):
    _, db, client = ctx
    try:
        result = await client.action("job_status", {"job_id": task_id})
    except Exception as exc:
        raise _plugin_error(exc)
    db.update_job(task_id, result.get("state", "unknown"), result.get("meta"))
    return {"job": result, "record": db.get_job(task_id)}


@app.post("/api/jobs/{task_id}/cancel")
async def cancel_job(task_id: str, ctx=Depends(auth)):
    _, db, client = ctx
    try:
        result = await client.action(
            "job_revoke",
            {"job_id": task_id, "confirm": True},
        )
    except Exception as exc:
        raise _plugin_error(exc)
    db.audit("control-plane", "job_revoke", {"job_id": task_id})
    return result


@app.post("/api/categories/rename")
async def rename_category(payload: CategoryRenameIn, ctx=Depends(auth)):
    _, db, client = ctx
    try:
        result = await client.action("category_rename", payload.model_dump())
    except Exception as exc:
        raise _plugin_error(exc)
    db.audit(
        "control-plane",
        "category_rename",
        {"category_id": payload.category_id, "confirmed": payload.confirm},
    )
    return result


@app.post("/api/categories/visibility")
async def category_visibility(payload: CategoryVisibilityIn, ctx=Depends(auth)):
    _, db, client = ctx
    try:
        result = await client.action("category_visibility", payload.model_dump())
    except Exception as exc:
        raise _plugin_error(exc)
    db.audit(
        "control-plane",
        "category_visibility",
        {
            "account_id": payload.account_id,
            "category_id": payload.category_id,
            "confirmed": payload.confirm,
        },
    )
    return result


@app.post("/api/categories/merge")
async def merge_categories(payload: CategoryMergeIn, ctx=Depends(auth)):
    _, db, client = ctx
    try:
        result = await client.action("category_merge", payload.model_dump())
    except Exception as exc:
        raise _plugin_error(exc)
    db.audit(
        "control-plane",
        "category_merge",
        {
            "source_category_id": payload.source_category_id,
            "target_category_id": payload.target_category_id,
            "confirmed": payload.confirm,
        },
    )
    return result


@app.post("/api/categories/delete-empty")
async def delete_empty_category(payload: CategoryDeleteIn, ctx=Depends(auth)):
    _, db, client = ctx
    try:
        result = await client.action("category_delete_empty", payload.model_dump())
    except Exception as exc:
        raise _plugin_error(exc)
    db.audit(
        "control-plane",
        "category_delete_empty",
        {"category_id": payload.category_id, "confirmed": payload.confirm},
    )
    return result


@app.get("/api/source-health")
async def source_health(ctx=Depends(auth)):
    _, _, client = ctx
    try:
        return await client.action("source_health", {})
    except Exception as exc:
        raise _plugin_error(exc)


@app.get("/api/integrations")
async def integrations(ctx=Depends(auth)):
    import os

    profiles = {p["id"]: p for p in all_client_profiles()}
    for key in ("plex", "jellyfin", "emby"):
        profiles[key]["configured"] = bool(os.environ.get(f"{key.upper()}_BASE_URL"))
    profiles["vod2mlib"] = {
        "mode": os.environ.get("VOD2MLIB_MODE", "disabled"),
        "configured": os.environ.get("VOD2MLIB_MODE", "disabled") != "disabled",
    }
    return profiles


@app.get("/api/audit")
async def audit(limit: int = Query(50, ge=1, le=200), ctx=Depends(auth)):
    _, db, _ = ctx
    return {"audit": db.tail_audit(limit)}


@app.get("/api/settings/public")
async def public_settings(ctx=Depends(auth)):
    settings, _, _ = ctx
    return {
        "dispatcharr_base_url": settings.dispatcharr_base_url,
        "dispatcharr_plugin_key": settings.dispatcharr_plugin_key,
        "control_plane_bind": settings.bind,
        "control_plane_port": settings.port,
        "secrets": "not exposed to browser",
    }
