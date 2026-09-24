# VOD Operations Runbook

## Normal daily mode

Maintenance window:
1. snapshot job state
2. refresh source metadata in controlled batches
3. reconcile catalog/category policies
4. update aliases
5. regenerate only affected VOD2MLIB records
6. request media-library rescan
7. verify health

Never run every heavy operation at the same time.

## Before bulk changes

1. Check Docker memory.
2. Check PostgreSQL health.
3. Check free storage.
4. Export control-plane policy.
5. Create a PostgreSQL backup.
6. Run a preview.
7. Inspect affected samples.
8. Confirm.
9. Apply as a background job.
10. Verify counts and audit.

## Playback incident

Classify first:
- source failure
- HTTP failure
- Range failure
- authentication/authorization failure
- expired link
- connection-limit failure
- audio incompatibility
- subtitle burn-in
- codec incompatibility
- bitrate restriction
- transcoder saturation
- storage I/O
- memory pressure

Do not change FFmpeg flags before classification.

## Provider degradation

1. increment health counters
2. apply bounded cooldown
3. stop aggressive retries
4. select another known-good source when policy allows
5. record the reason
6. re-probe periodically

## Database pressure

Symptoms:
- slow catalog searches
- Celery backlog
- connection exhaustion
- high PostgreSQL I/O

Action:
1. pause large catalog jobs
2. pause metadata jobs
3. keep active playback paths running
4. inspect expensive query
5. resume at smaller batch size

## Docker memory pressure

Symptoms:
- OOM kill
- worker restart
- database restart
- playback interruption during refresh

Action:
1. pause non-essential background work
2. check Docker memory
3. check PostgreSQL and Celery memory
4. increase Docker memory before imposing hard container caps
5. rerun playback canary

## Rollback rule

Do not use a database-wide restore as the first reaction to a small catalog mistake.

Use:
- operation rollback for supported changes
- database restore for deleted categories or structural mistakes
- filesystem cleanup only after validating the generated projection

## Upgrade rehearsal

1. record current Dispatcharr image tag/digest
2. backup PostgreSQL
3. backup /data/plugins
4. export control-plane policies
5. test on copied data
6. start the candidate image
7. reload plugins
8. run compatibility checks
9. run ten-title VOD canary
10. run one long movie
11. verify Jellyfin/Emby/Plex paths
12. only then update production

The final system must not require a Dispatcharr core patch after an upgrade.
