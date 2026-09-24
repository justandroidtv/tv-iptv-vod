# Phase 1 Baseline — 2026-09-24

## Docker

- CPUs visible to Docker: 6
- Memory visible to Docker: 4,154,580,992 bytes (about 3.87 GiB)

Current containers have not shown OOM kills or restart loops during the audit.

## PostgreSQL

Observed settings:

- shared_buffers: 128MB
- work_mem: 4MB
- maintenance_work_mem: 64MB
- max_connections: 100
- effective_cache_size: 4GB

Current activity at audit time:

- active sessions: 1
- idle sessions: 15
- unknown state sessions: 5

Database container health: healthy.

## Redis

Observed:

- memory: about 2.50 MB
- maxmemory: unlimited
- connected clients: 27
- blocked clients: 3
- container health: healthy
- OOM: false
- restarts: 0

The Redis fragmentation ratio reported by INFO is not a reason to tune aggressively at this point; the dataset is small and the ratio is sensitive to allocator behavior.

## Capacity conclusion

Do not start by changing PostgreSQL memory settings.

First increase Docker memory to 8 GB and repeat:

1. 2 simultaneous VOD playbacks
2. 3 simultaneous VOD playbacks
3. one catalog refresh
4. one metadata batch
5. playback during refresh
6. playback during metadata batch

Only then tune PostgreSQL or Celery concurrency.

## Security blockers discovered

The current compose file contains plaintext credentials/tokens.

These values are not copied into this repository.

Required before production:

- rotate exposed provider/API secrets
- rotate media signing secret
- rotate PostgreSQL password through controlled maintenance
- move secrets to untracked environment/secret storage

## Core boundary verification

- apps/proxy/vod_proxy/views.py hash matches upstream main.
- core/models.py differs from upstream.
- apps/plugins/api_views.py differs from upstream.

The latter two differences predate this project and are intentionally left untouched.

## Entry criteria for Phase 2

- Docker memory increase completed and benchmarked
- secret rotation plan executed
- plugin package v0.3 tested in an isolated copy
- no new core changes
