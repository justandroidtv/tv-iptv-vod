# Docker and Database Hardening

Date: 2026-09-24

## Current baseline

The deployment uses separate web, celery, PostgreSQL and Redis containers.

Point-in-time light-load observations:

- Docker memory exposure is about 4 GB.
- Docker exposes 6 vCPUs.
- web is about 766 MiB.
- celery is about 428 MiB.
- PostgreSQL is about 1.16 GiB.
- Redis is about 27 MiB.

These are observations, not stress limits.

## Required order

1. Raise Docker Desktop memory to 8 GB.
2. Retest idle, two VOD sessions, three VOD sessions, catalog refresh during playback, and metadata work during playback.
3. Pin Dispatcharr and Redis to tested image tags/digests.
4. Rotate exposed credentials and API keys.
5. Move secrets to untracked environment/secret storage.
6. Remove host database/Redis exposure when it is not required.
7. Add Docker log rotation and storage checks.
8. Keep PostgreSQL persistent and put transcode temporary storage on SSD when transcoding is used.

## PostgreSQL

Current baseline:

- shared_buffers = 128MB
- work_mem = 4MB
- maintenance_work_mem = 64MB
- max_connections = 100
- effective_cache_size = 4GB

Do not tune these from guesswork. Measure after the Docker memory change and workload test.

## Backup

A PostgreSQL custom-format backup was restored successfully into an isolated database. Keep the verified backup outside Git.

## Change policy

No Dispatcharr core source edit, core migration, or image patch is required for hardening.
