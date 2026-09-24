# Dispatcharr VOD Control Plane

A non-core control plane for Dispatcharr VOD installations, designed around movies and TV series first.

## Design goals

- Never patch Dispatcharr core files or core migrations.
- Keep policy, naming, catalog curation and operational logic outside the Dispatcharr image.
- Prefer Direct or Redirect playback for VOD and reserve transcoding for genuine compatibility problems.
- Treat Plex, Jellyfin and Emby as different integration targets.
- Make every destructive or bulk change preview-first, snapshot-first, transactional and auditable.
- Make regex powerful for experts while providing safe recipes and explanations.
- Run long jobs through background workers.

## Current environment baseline

The companion deployment audit found:

- Dispatcharr 0.31.0 in a modular Docker deployment.
- Intel Core i5-12400F, 32 GB host RAM and RTX 3050 6 GB.
- Docker currently exposes about 4 GB to the Linux VM.
- VOD inventory: 66,289 movies, 33,264 series, 37,373 episodes and 2,084 categories.
- Installed plugins include VOD Metadata Fetcher, VOD to Media Library, Media Platform, IPTV Checker and VOD Catalog Manager.

Secrets are intentionally never stored in this repository.

## Architecture

The project has two independent pieces:

1. vod-catalog-manager: a Dispatcharr plugin under /data/plugins.
2. control-plane: an external FastAPI dashboard using the authenticated plugin API.

Dispatcharr core remains untouched.

## Safety contract

preview -> validate -> backup or snapshot -> confirm -> transaction -> audit

Rollback uses optimistic checks. A row is restored only when its current value still equals the value written by the original operation. Conflicts are skipped.

## Planned modules

- Catalog Browser
- Category Studio
- Regex Studio
- Naming Profiles
- Virtual and Smart Collections
- Source Health and Last-Known-Good tracking
- Provider circuit-breaker policy
- Client profiles for Plex, Jellyfin and Emby
- VOD2MLIB bridge controls
- Job queue and maintenance windows
- Audit and rollback
- Import/export of non-secret policy JSON

## Legal boundary

Use only source data and media that the operator is authorized to access and use. No DRM bypass, session-cookie extraction, credential harvesting or access-control circumvention.

## Repository status

This repository is the implementation and documentation home for the non-core VOD control plane. Dispatcharr remains an external dependency.
