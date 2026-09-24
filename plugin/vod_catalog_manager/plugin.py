from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Any

from django.db import transaction

from .engine import DEFAULT_RECIPES, MAX_SYNC_BATCH, RegexRule, apply_rule, validate_pattern
from .job_contract import normalize_job_request

# Import task definitions when the plugin module is loaded so Celery workers register them.
from .tasks import JOB_NAME, regex_apply_task  # noqa: F401

NAME = "VOD Catalog Manager"
VERSION = "0.3.0"

class Plugin:
    name = NAME
    version = VERSION
    description = "Non-core VOD catalog management for categories, naming rules, aliases and safe bulk changes."
    author = "justandroidtv"
    help_url = "https://github.com/justandroidtv/tv-iptv-vod"

    fields = [
        {"id":"notice","label":"Safety","type":"info","description":"Dispatcharr core is never edited. Writes require preview, confirmation, snapshot and audit."},
        {"id":"regex_scope","label":"Regex scope","type":"select","default":"movie","options":[{"value":"movie","label":"Movie"},{"value":"series","label":"Series"},{"value":"episode","label":"Episode"}]},
        {"id":"regex_pattern","label":"Regex pattern","type":"text","default":"","placeholder":r"\s+\[1080p\]$"},
        {"id":"regex_replacement","label":"Replacement","type":"string","default":"","placeholder":r"\g<1>"},
        {"id":"regex_limit","label":"Synchronous batch limit","type":"number","default":100},
        {"id":"regex_case_insensitive","label":"Case insensitive","type":"boolean","default":True},
        {"id":"confirm_write","label":"Confirm write","type":"boolean","default":False},
    ]

    actions = [
        {"id":"status","label":"VOD Control Status","description":"Read-only VOD counts and plugin state.","button_label":"Status","button_variant":"outline","button_color":"blue"},
        {"id":"catalog_query","label":"Catalog Query","description":"Read-only paginated title search.","button_label":"Query","button_variant":"outline","button_color":"cyan"},
        {"id":"category_list","label":"Category List","description":"Read-only category listing.","button_label":"Categories","button_variant":"outline","button_color":"cyan"},
        {"id":"regex_library","label":"Regex Recipe Library","description":"Safe recipes with explanations and examples.","button_label":"Recipes","button_variant":"outline","button_color":"violet"},
        {"id":"regex_preview","label":"Regex Preview","description":"Preview changes without writing.","button_label":"Preview","button_variant":"filled","button_color":"blue"},
        {"id":"regex_apply","label":"Regex Apply","description":"Apply a bounded, reviewed regex batch.","button_label":"Apply","button_variant":"filled","button_color":"orange","confirm":{"required":True,"title":"Apply Regex changes?","message":"Review preview and backup before confirming."}},
        {"id":"regex_apply_async","label":"Regex Apply Async","description":"Queue a large reviewed regex job in Celery.","button_label":"Queue Job","button_variant":"filled","button_color":"violet","confirm":{"required":True,"title":"Queue regex job?","message":"The job writes in bounded transactions."}},
        {"id":"job_status","label":"Job Status","description":"Inspect a background VOD job.","button_label":"Job Status","button_variant":"outline","button_color":"cyan"},
        {"id":"job_revoke","label":"Cancel Job","description":"Request cooperative cancellation.","button_label":"Cancel","button_variant":"filled","button_color":"red","confirm":{"required":True,"title":"Cancel job?","message":"Cancellation stops at a safe boundary."}},
        {"id":"category_rename","label":"Category Rename","description":"Preview or rename one category.","button_label":"Rename","button_variant":"filled","button_color":"orange","confirm":{"required":True,"title":"Rename category?","message":"Only the category label changes."}},
        {"id":"category_visibility","label":"Category Visibility","description":"Hide/show one category for one M3U account.","button_label":"Visibility","button_variant":"filled","button_color":"orange","confirm":{"required":True,"title":"Change category visibility?","message":"No provider media is deleted."}},
        {"id":"category_merge","label":"Category Merge","description":"Merge same-type categories transactionally.","button_label":"Merge","button_variant":"filled","button_color":"red","confirm":{"required":True,"title":"Merge categories?","message":"Backup first. The source category is removed only after relations move."}},
        {"id":"category_delete_empty","label":"Delete Empty Category","description":"Delete only when no content or account relations exist.","button_label":"Delete Empty","button_variant":"filled","button_color":"red","confirm":{"required":True,"title":"Delete empty category?","message":"Backup first; automatic recreation is not guaranteed."}},
        {"id":"source_health","label":"Source Health","description":"Read-only source status, coverage and extension health.","button_label":"Source Health","button_variant":"outline","button_color":"cyan"},
        {"id":"audit_tail","label":"Audit","description":"Show recent non-secret audit records.","button_label":"Audit","button_variant":"subtle"},
    ]

    def __init__(self):
        self.root = Path(__file__).resolve().parent
        self.data = self.root / "data"
        self.data.mkdir(exist_ok=True)
        self.audit_path = self.data / "audit.jsonl"
        self.snapshot_dir = self.data / "snapshots"
        self.snapshot_dir.mkdir(exist_ok=True)
        self._params: dict[str, Any] = {}

    def run(self, action: str, params: dict, context: dict):
        self._params = dict(params or {})
        settings = context.get("settings") or {}
        for key in ("scope","pattern","replacement","limit","case_insensitive","confirm_write"):
            self._params.setdefault(key, settings.get(f"regex_{key}", settings.get(key)))
        try:
            return {
                "status": self._dispatch(action)
            }["status"]
        except Exception as exc:
            logging.getLogger(NAME).exception("VOD Catalog Manager action failed")
            self._audit({"action":action,"status":"error","error":str(exc)[:500]})
            return {"status":"error","message":str(exc)[:500]}

    @staticmethod
    def _models():
        from apps.vod.models import Movie, Series, Episode, VODCategory, M3UVODCategoryRelation, M3UMovieRelation, M3USeriesRelation
        return Movie, Series, Episode, VODCategory, M3UVODCategoryRelation, M3UMovieRelation, M3USeriesRelation

    @staticmethod
    def _confirmed(params):
        return str(params.get("confirm","")).lower() in {"true","1","yes","confirm"} or str(params.get("confirm_write","")).lower() in {"true","1","yes","confirm"}

    def _dispatch(self, action):
        handlers = {
            "status":self._status, "catalog_query":self._catalog_query, "category_list":self._category_list,
            "regex_library":lambda:self._regex_library(), "regex_preview":lambda:self._regex(False),
            "regex_apply":lambda:self._regex(True), "regex_apply_async":self._regex_apply_async,
            "job_status":self._job_status, "job_revoke":self._job_revoke,
            "category_rename":self._category_rename,
            "category_visibility":self._category_visibility, "category_merge":self._category_merge,
            "category_delete_empty":self._category_delete_empty, "source_health":self._source_health,
            "audit_tail":self._audit_tail,
        }
        if action not in handlers:
            raise ValueError(f"Unknown action: {action}")
        return handlers[action]()

    def _status(self):
        Movie, Series, Episode, Category, CatRel, MovieRel, SeriesRel = self._models()
        return {"status":"ok","version":VERSION,"core_write_prohibited":True,"counts":{
            "movies":Movie.objects.count(),"series":Series.objects.count(),"episodes":Episode.objects.count(),
            "categories":Category.objects.count(),"movie_relations":MovieRel.objects.count(),
            "series_relations":SeriesRel.objects.count(),"category_account_relations":CatRel.objects.count()}}

    def _catalog_query(self):
        Movie, Series, Episode, *_ = self._models()
        p=self._params; kind=str(p.get("kind") or "movie"); query=str(p.get("q") or "").strip()
        page=max(1,int(p.get("page") or 1)); size=min(100,max(1,int(p.get("page_size") or 50)))
        model={"movie":Movie,"series":Series,"episode":Episode}.get(kind)
        if model is None: raise ValueError("kind must be movie, series or episode")
        qs=model.objects.all().order_by("name","id")
        if query: qs=qs.filter(name__icontains=query)
        total=qs.count()
        rows=qs[(page-1)*size:page*size]
        return {"status":"ok","kind":kind,"total":total,"page":page,"page_size":size,
                "items":[{"id":x.id,"name":x.name,"year":getattr(x,"year",None)} for x in rows]}

    def _category_list(self):
        from django.db.models import Count
        *_, Category, CatRel, MovieRel, SeriesRel = self._models()
        p = self._params
        query = str(p.get("q") or "").strip()
        page = max(1, int(p.get("page") or 1))
        size = min(100, max(1, int(p.get("page_size") or 50)))
        qs = Category.objects.all().order_by("category_type", "name", "id")
        if query:
            qs = qs.filter(name__icontains=query)
        total = qs.count()
        rows = list(qs[(page - 1) * size : page * size])
        ids = [cat.id for cat in rows]
        movie_counts = dict(
            MovieRel.objects.filter(category_id__in=ids)
            .values("category_id")
            .annotate(c=Count("id"))
            .values_list("category_id", "c")
        )
        series_counts = dict(
            SeriesRel.objects.filter(category_id__in=ids)
            .values("category_id")
            .annotate(c=Count("id"))
            .values_list("category_id", "c")
        )
        account_counts = dict(
            CatRel.objects.filter(category_id__in=ids)
            .values("category_id")
            .annotate(c=Count("id"))
            .values_list("category_id", "c")
        )
        return {
            "status": "ok",
            "total": total,
            "page": page,
            "page_size": size,
            "items": [
                {
                    "id": cat.id,
                    "name": cat.name,
                    "type": cat.category_type,
                    "account_links": account_counts.get(cat.id, 0),
                    "movie_links": movie_counts.get(cat.id, 0),
                    "series_links": series_counts.get(cat.id, 0),
                }
                for cat in rows
            ],
        }

    def _regex_library(self):
        return {"status":"ok","syntax":r"Python re; replacement uses \g<1>","recipes":DEFAULT_RECIPES}

    def _regex(self, applying):
        Movie, Series, Episode, *_ = self._models()
        p=self._params; scope=str(p.get("scope") or "movie")
        pattern=str(p.get("pattern") or ""); replacement=str(p.get("replacement") or "")
        validate_pattern(pattern)
        import re
        case=str(p.get("case_insensitive",True)).lower() not in {"false","0","no"}
        flags=re.IGNORECASE if case else 0
        limit=min(MAX_SYNC_BATCH,max(1,int(p.get("limit") or 100)))
        model={"movie":Movie,"series":Series,"episode":Episode}.get(scope)
        if model is None: raise ValueError("scope must be movie, series or episode")
        rows=list(model.objects.all().order_by("id")[:limit]); changes=[]
        for obj in rows:
            old=str(obj.name or ""); rule=RegexRule(pattern=pattern,replacement=replacement,flags=flags,enabled=True)
            new=apply_rule(old,rule)
            if new!=old: changes.append({"id":obj.id,"old":old,"new":new})
        preview={"status":"preview","scope":scope,"scanned":len(rows),"matches":len(changes),"changes":changes[:100],"truncated":len(changes)>100}
        if not applying: return preview
        if not self._confirmed(p): return {"status":"preview_required","preview":preview}
        snapshot=self._snapshot("regex_"+scope,{"model":scope,"changes":changes})
        updated=0
        with transaction.atomic():
            for row in changes:
                updated += model.objects.filter(id=row["id"],name=row["old"]).update(name=row["new"][:255])
        self._audit({"action":"regex_apply","scope":scope,"updated":updated,"snapshot":snapshot})
        return {"status":"ok","updated":updated,"snapshot":snapshot}

    def _regex_apply_async(self):
        p = self._params
        request = normalize_job_request({
            "scope": p.get("scope"),
            "pattern": p.get("pattern"),
            "replacement": p.get("replacement"),
            "max_rows": p.get("max_rows", 0),
            "case_insensitive": p.get("case_insensitive", True),
        })
        validate_pattern(request.pattern)
        if not self._confirmed(p):
            return {
                "status": "preview_required",
                "message": "Set confirm=true after reviewing Regex Preview.",
            }
        task = regex_apply_task.delay({
            "scope": request.scope,
            "pattern": request.pattern,
            "replacement": request.replacement,
            "max_rows": request.max_rows,
            "case_insensitive": request.case_insensitive,
        })
        self._audit({
            "action": "regex_apply_async",
            "status": "queued",
            "job_id": task.id,
            "task_name": JOB_NAME,
            "scope": request.scope,
        })
        return {
            "status": "queued",
            "job_id": task.id,
            "task_name": JOB_NAME,
            "scope": request.scope,
            "message": "Background job queued. Use job_status with this job_id.",
        }

    def _job_status(self):
        task_id = str(self._params.get("job_id") or "").strip()
        if not task_id:
            raise ValueError("job_id is required")
        from celery.result import AsyncResult

        result = AsyncResult(task_id)
        state_map = {
            "PENDING": "queued",
            "STARTED": "running",
            "PROGRESS": "running",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "REVOKED": "revoked",
        }
        state = state_map.get(result.state, result.state.lower())
        info = result.info if isinstance(result.info, dict) else None
        return {
            "status": "ok",
            "job_id": task_id,
            "state": state,
            "raw_state": result.state,
            "meta": info,
        }

    def _job_revoke(self):
        task_id = str(self._params.get("job_id") or "").strip()
        if not task_id:
            raise ValueError("job_id is required")
        if not self._confirmed(self._params):
            return {
                "status": "preview",
                "job_id": task_id,
                "message": "Repeat with confirm=true to request cancellation.",
            }
        from celery import current_app

        from .tasks import request_cancel

        request_cancel(task_id)
        current_app.control.revoke(task_id, terminate=False)
        self._audit({
            "action": "job_revoke",
            "status": "requested",
            "job_id": task_id,
        })
        return {
            "status": "revocation_requested",
            "job_id": task_id,
            "message": "Cancellation requested. A running task stops at its next safe boundary.",
        }

    def _category_delete_empty(self):
        p = self._params
        category_id = int(p.get("category_id") or 0)
        if not category_id:
            raise ValueError("category_id is required")
        from apps.vod.models import (
            M3UMovieRelation,
            M3USeriesRelation,
            M3UVODCategoryRelation,
            VODCategory,
        )

        category = VODCategory.objects.filter(pk=category_id).first()
        if not category:
            raise ValueError("Category not found")
        movie_links = M3UMovieRelation.objects.filter(category=category).count()
        series_links = M3USeriesRelation.objects.filter(category=category).count()
        account_links = M3UVODCategoryRelation.objects.filter(category=category).count()
        preview = {
            "status": "preview",
            "category_id": category_id,
            "name": category.name,
            "type": category.category_type,
            "movie_links": movie_links,
            "series_links": series_links,
            "account_links": account_links,
            "deletable": not any((movie_links, series_links, account_links)),
        }
        if any((movie_links, series_links, account_links)):
            return preview
        if not self._confirmed(p):
            return preview
        snapshot = self._snapshot("category_delete_empty", preview)
        with transaction.atomic():
            VODCategory.objects.filter(
                pk=category_id, name=category.name, category_type=category.category_type
            ).delete()
        self._audit(
            {
                "action": "category_delete_empty",
                "category_id": category_id,
                "name": category.name,
                "snapshot": snapshot,
            }
        )
        return {"status": "ok", "deleted": True, "snapshot": snapshot}

    def _category_rename(self):
        p=self._params; cid=int(p.get("category_id") or 0); new=str(p.get("new_name") or "").strip()
        if not cid or not new: raise ValueError("category_id and new_name are required")
        from apps.vod.models import VODCategory
        cat=VODCategory.objects.filter(pk=cid).first()
        if not cat: raise ValueError("Category not found")
        if VODCategory.objects.filter(name=new,category_type=cat.category_type).exclude(pk=cid).exists(): raise ValueError("Conflicting category exists")
        preview={"status":"preview","category_id":cid,"old_name":cat.name,"new_name":new}
        if not self._confirmed(p): return preview
        snapshot=self._snapshot("category_rename",preview)
        with transaction.atomic(): VODCategory.objects.filter(pk=cid,name=cat.name).update(name=new)
        self._audit({"action":"category_rename","category_id":cid,"snapshot":snapshot})
        return {"status":"ok","category_id":cid,"new_name":new,"snapshot":snapshot}

    def _category_visibility(self):
        p=self._params; account_id=int(p.get("account_id") or 0); category_id=int(p.get("category_id") or 0)
        if not account_id or not category_id or "enabled" not in p: raise ValueError("account_id, category_id and enabled required")
        enabled=str(p["enabled"]).lower() in {"true","1","yes","on"}
        from apps.vod.models import M3UVODCategoryRelation
        rel=M3UVODCategoryRelation.objects.filter(m3u_account_id=account_id,category_id=category_id).first()
        if not rel: raise ValueError("Account/category relation not found")
        preview={"status":"preview","account_id":account_id,"category_id":category_id,"old_enabled":bool(rel.enabled),"new_enabled":enabled}
        if not self._confirmed(p): return preview
        snapshot=self._snapshot("category_visibility",preview)
        with transaction.atomic(): M3UVODCategoryRelation.objects.filter(pk=rel.pk,enabled=rel.enabled).update(enabled=enabled)
        self._audit({"action":"category_visibility","relation_id":rel.pk,"snapshot":snapshot})
        return {"status":"ok","relation_id":rel.pk,"enabled":enabled,"snapshot":snapshot}

    def _category_merge(self):
        p=self._params; src_id=int(p.get("source_category_id") or 0); dst_id=int(p.get("target_category_id") or 0)
        from apps.vod.models import VODCategory, M3UVODCategoryRelation, M3UMovieRelation, M3USeriesRelation
        src=VODCategory.objects.filter(pk=src_id).first(); dst=VODCategory.objects.filter(pk=dst_id).first()
        if not src or not dst or src_id==dst_id: raise ValueError("Valid different source/target required")
        if src.category_type!=dst.category_type: raise ValueError("Only same-type categories can merge")
        links=list(M3UVODCategoryRelation.objects.filter(category=src).values("m3u_account_id","enabled","custom_properties"))
        movies=list(M3UMovieRelation.objects.filter(category=src).values_list("id",flat=True))
        series=list(M3USeriesRelation.objects.filter(category=src).values_list("id",flat=True))
        preview={"status":"preview","source":{"id":src_id,"name":src.name,"links":len(links),"movies":len(movies),"series":len(series)},"target":{"id":dst_id,"name":dst.name}}
        if not self._confirmed(p): return preview
        snapshot=self._snapshot("category_merge",{"source":{"id":src_id,"name":src.name,"type":src.category_type,"links":links},"target":{"id":dst_id,"name":dst.name},"movie_ids":movies,"series_ids":series})
        with transaction.atomic():
            for link in links:
                existing, created = M3UVODCategoryRelation.objects.get_or_create(
                    m3u_account_id=link["m3u_account_id"],
                    category=dst,
                    defaults={"enabled":link["enabled"],"custom_properties":link["custom_properties"]},
                )
                if not created and link["enabled"] and not existing.enabled:
                    existing.enabled = True
                    existing.save(update_fields=["enabled", "updated_at"])
            M3UMovieRelation.objects.filter(id__in=movies,category=src).update(category=dst)
            M3USeriesRelation.objects.filter(id__in=series,category=src).update(category=dst)
            src.delete()
        self._audit({"action":"category_merge","source_id":src_id,"target_id":dst_id,"snapshot":snapshot})
        return {"status":"ok","moved_movies":len(movies),"moved_series":len(series),"snapshot":snapshot}

    def _snapshot(self,label,payload):
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path=self.snapshot_dir / f"{stamp}_{label}_{int(time.time())}.json"
        path.write_text(json.dumps({"created_at":stamp,"label":label,"payload":payload},ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        return path.name

    def _audit(self,row):
        with self.audit_path.open("a",encoding="utf-8") as f:
            f.write(json.dumps({"at":datetime.now(timezone.utc).isoformat(),**row},ensure_ascii=False,default=str)+"\n")

    def _source_health(self):
        Movie, Series, Episode, Category, CatRel, MovieRel, SeriesRel = self._models()
        from apps.vod.models import M3UEpisodeRelation
        from apps.m3u.models import M3UAccount
        from django.db.models import Count

        movie_total = MovieRel.objects.count()
        series_total = SeriesRel.objects.count()
        episode_total = M3UEpisodeRelation.objects.count()

        movie_ext = list(
            MovieRel.objects.values("container_extension")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        episode_ext = list(
            M3UEpisodeRelation.objects.values("container_extension")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        movie_by_account = dict(
            MovieRel.objects.values("m3u_account_id")
            .annotate(count=Count("id"))
            .values_list("m3u_account_id", "count")
        )
        series_by_account = dict(
            SeriesRel.objects.values("m3u_account_id")
            .annotate(count=Count("id"))
            .values_list("m3u_account_id", "count")
        )
        episode_by_account = dict(
            M3UEpisodeRelation.objects.values("m3u_account_id")
            .annotate(count=Count("id"))
            .values_list("m3u_account_id", "count")
        )

        accounts = list(
            M3UAccount.objects.values(
                "id", "name", "status", "is_active", "priority", "max_streams"
            ).order_by("-priority", "id")
        )
        for account in accounts:
            account_id = account["id"]
            account["movie_relations"] = movie_by_account.get(account_id, 0)
            account["series_relations"] = series_by_account.get(account_id, 0)
            account["episode_relations"] = episode_by_account.get(account_id, 0)
            account["total_relations"] = (
                account["movie_relations"]
                + account["series_relations"]
                + account["episode_relations"]
            )
        accounts = [x for x in accounts if x["total_relations"] > 0]

        inactive_movie = MovieRel.objects.filter(
            m3u_account__is_active=False
        ).count()
        inactive_series = SeriesRel.objects.filter(
            m3u_account__is_active=False
        ).count()
        inactive_episode = M3UEpisodeRelation.objects.filter(
            m3u_account__is_active=False
        ).count()

        return {
            "status": "ok",
            "accounts": {
                "total": len(accounts),
                "active": sum(1 for x in accounts if x["is_active"]),
                "inactive": sum(1 for x in accounts if not x["is_active"]),
                "with_vod_relations": len(accounts),
            },
            "relations": {
                "movies": movie_total,
                "series": series_total,
                "episodes": episode_total,
                "total": movie_total + series_total + episode_total,
                "inactive_account_relations": {
                    "movies": inactive_movie,
                    "series": inactive_series,
                    "episodes": inactive_episode,
                    "total": inactive_movie + inactive_series + inactive_episode,
                },
            },
            "container_extensions": {
                "movies": movie_ext,
                "episodes": episode_ext,
                "series": "not stored on M3USeriesRelation",
            },
            "top_accounts": accounts[:25],
            "limits": {
                "max_streams": "Per-account limit; 0 means unlimited."
            },
            "interpretation": {
                "direct_play": "Not inferred: codec/audio/subtitle metadata is not stored on these relations.",
                "failover": "Existing VOD proxy selection/failover remains authoritative.",
            },
        }

    def _audit_tail(self):
        if not self.audit_path.exists(): return {"status":"ok","audit":[]}
        out=[]
        for line in self.audit_path.read_text(encoding="utf-8",errors="replace").splitlines()[-50:]:
            try: out.append(json.loads(line))
            except json.JSONDecodeError: pass
        return {"status":"ok","audit":out}
