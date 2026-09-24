# Dispatcharr VOD Control Plane — Master Plan

Version: 0.3
Date: 2026-09-24
Status: implementation plan

## Non-negotiable rules

1. Never modify Dispatcharr core source files.
2. Never add Dispatcharr core migrations for this project.
3. Never patch the Dispatcharr Docker image.
4. Use /data/plugins for Dispatcharr extensions.
5. Keep the external control plane separate from Dispatcharr runtime code.
6. Prefer non-destructive presentation rules over canonical database mutation.
7. Every bulk write follows preview -> backup/snapshot -> confirmation -> transaction -> audit.
8. Large jobs run asynchronously through Celery or the external job worker.
9. Secrets never enter Git, audit logs, snapshots, screenshots or diagnostics.
10. Only operate on sources and media the operator is authorized to access or use.

## Current verified baseline

- Dispatcharr 0.31.0
- Modular Docker deployment: web, celery, PostgreSQL 17, Redis
- Host CPU: Intel Core i5-12400F
- Host RAM: about 32 GB
- Host GPU: NVIDIA RTX 3050 6 GB
- Docker Linux VM: about 4 GB RAM currently exposed
- Movies: 66,289
- Series: 33,264
- Episodes: 37,373
- VOD categories: 2,084
- Movie source relations: 633,623
- Series source relations: 236,553
- Episode source relations: 27,395
- Account/category relations: 7,926

## Capacity baseline

Observed light-load container memory:

- web: about 766 MiB
- celery: about 428 MiB
- PostgreSQL: about 1.16 GiB
- Redis: about 27 MiB

These are point-in-time observations, not stress-test results. The first infrastructure task is to increase Docker memory to 8 GB and retest before applying arbitrary per-container caps.

## Target architecture

Client -> Plex/Jellyfin/Emby -> media-library projection -> Dispatcharr VOD

Management:

Operator -> Control Plane -> authenticated Dispatcharr plugin API -> VOD Catalog Manager -> Dispatcharr

Data ownership:

- Dispatcharr owns authoritative VOD records and provider relations.
- VOD Catalog Manager owns operation snapshots and audit data.
- Control Plane owns policy/profile configuration and job metadata.
- VOD2MLIB owns the generated .strm/NFO projection when selected.
- Plex/Jellyfin/Emby own their media-library indexes.

## Phase map

### Phase 0 — Safety and reproducibility

Deliver:
- PostgreSQL backup
- separate restore verification
- Docker compose/config backup
- plugin directory backup
- tested image version/digest record
- secret rotation plan
- rollback runbook

Gate:
- backup restores into isolated database
- production can return to previous image/plugin set

### Phase 1 — Docker and database stability

Deliver:
- Docker memory 8 GB baseline
- 6 vCPU baseline
- 2-4 GB swap protection
- persistent PostgreSQL storage
- internal-only Redis
- restricted PostgreSQL host exposure
- Docker log rotation
- storage free-space checks

Test:
- idle
- 2 simultaneous VOD sessions
- 3 simultaneous VOD sessions
- catalog refresh during playback
- metadata job during playback

Gate:
- no OOM
- no PostgreSQL pool exhaustion
- no Redis memory pressure
- no repeatable playback interruption from maintenance

### Phase 2 — Plugin boundary

Deliver:
- VOD Catalog Manager v0.3+
- manifest and action contract
- preview/write safety
- snapshots
- audit
- reload/enable compatibility

Gate:
- enable, disable, reload and run
- core source remains untouched
- plugin survives update rehearsal

### Phase 3 — Catalog Browser

Deliver:
- movie/series/episode search
- pagination
- category browser
- account/category relation view
- source relation counts
- filters by media type, category and source account

Read-only.

### Phase 4 — Category Studio

Deliver:
- rename
- per-account hide/show
- same-type merge
- delete empty category only
- multi-select
- preview impact
- transaction protection
- audit

Default preference:
hide > merge > delete

### Phase 5 — Regex Studio

Deliver:
- free-form regex
- replacement editor
- ordered multi-rule pipeline
- flags
- capture groups
- live preview
- whole-catalog match count
- changed/unchanged count
- bounded sync batch
- async bulk job
- import/export rule packs
- warnings and explanations

Canonical title mutation remains expert-only.

### Phase 6 — Alias and naming engine

Deliver:
- provider aliases
- profile aliases
- language aliases
- filesystem-safe names
- optional transliteration
- year normalization
- season/episode normalization
- punctuation policy
- Unicode normalization

Preferred path:
raw -> normalized -> canonical match -> display alias -> filesystem-safe name

### Phase 7 — Smart Collections

Deliver virtual rule-based collections:
- Arabic Movies
- Arabic Series
- 4K
- HD
- Kids
- Family
- New Releases
- Recently Added
- Completed Series
- Source Priority
- Manual Selection

Collections must not duplicate canonical media.

### Phase 8 — Source Health

Track:
- latency
- success/failure status
- timeout/reset counts
- cooldown
- last known good
- source edition identity
- last successful probe
- last successful playback

Do not hammer providers.

### Phase 9 — Playback continuity

Classify:
- source reset
- timeout
- signed-link expiry
- HTTP Range failure
- connection slot exhaustion
- audio incompatibility
- subtitle burn-in
- codec incompatibility
- bitrate limit
- transcoder saturation
- disk I/O
- memory pressure

Playback order:
1. Direct Play/Redirect
2. Direct Stream/remux
3. hardware transcoding
4. software transcoding

### Phase 10 — Jellyfin and Emby

Deliver:
- shared VOD projection
- read-only media mount
- STRM/NFO validation
- identity validation
- controlled library rescan
- long-play canary
- seek
- pause/resume
- audio/subtitle checks

### Phase 11 — Plex

Deliver a separate Plex projection. Do not assume STRM playback equivalence with Jellyfin/Emby.

### Phase 12 — VOD2MLIB coordination

Reuse the existing VOD2MLIB writer.

Control:
- inclusion
- naming
- TMDB identity
- category nesting
- rescan timing

### Phase 13 — Background jobs

Job states:
queued -> running -> paused -> completed
or
queued -> running -> failed -> retrying

Persist:
- job ID
- operation
- filter
- preview hash
- progress
- affected/skipped/conflict/error counts
- snapshot
- final status

### Phase 14 — Observability and release

Dashboards:
- VOD inventory
- source health
- playback failures
- job queue
- Celery queue age
- DB pressure
- Redis health
- Docker memory
- disk space
- media projection status

Release gates:
G1 backup restore
G2 Docker capacity
G3 plugin load/reload
G4 read-only catalog
G5 regex preview
G6 category dry-run
G7 category write/rollback
G8 ten movie canary
G9 ten episode canary
G10 Jellyfin canary
G11 Emby canary
G12 Plex canary
G13 30-minute playback
G14 60-minute playback
G15 120-minute playback
G16 catalog refresh during playback
G17 metadata job during playback
G18 update rehearsal
G19 secret scan
G20 checksum

## Definition of done

Production readiness requires:
- Dispatcharr core unchanged
- reproducible plugin installation
- tested rollback
- preview for destructive actions
- asynchronous large jobs
- deterministic playback failure classification
- separate verified Plex/Jellyfin/Emby paths
- different presentation policies without destroying provider identity
