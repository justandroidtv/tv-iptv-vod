# Phase Gates

## Gate policy

A phase is not complete because code exists.

A phase is complete only when implementation, tests, evidence and rollback requirements pass.

## Gate sequence

G0 Safety:
- verified PostgreSQL restore
- verified plugin backup
- no secrets committed

G1 Capacity:
- Docker memory baseline verified
- no OOM
- database healthy
- Redis healthy

G2 Plugin:
- manifest valid
- plugin imports in the target Dispatcharr version
- enable/disable/reload
- read-only status canary

G3 Catalog:
- search correctness
- category listing
- pagination
- relation counts

G4 Mutation:
- preview
- confirmation
- transaction
- conflict detection
- audit
- rollback

G5 Regex:
- invalid-pattern rejection
- nested-quantifier rejection
- Arabic/Latin normalization
- filename sanitization
- deterministic replacements

G6 Client:
- Jellyfin canary
- Emby canary
- Plex-specific canary

G7 Playback:
- 30 minutes
- 60 minutes
- 120 minutes
- seek
- pause/resume
- catalog refresh during playback

G8 Upgrade:
- candidate image
- plugin reload
- catalog canary
- playback canary
- rollback rehearsal

## Stop conditions

Stop production rollout when:
- backup restore fails
- any core file is newly modified by this project
- a bulk write has no preview
- a bulk write has no audit
- a write cannot be rolled back or restored
- a client requires an undocumented workaround
- provider behavior has not been verified
- memory pressure becomes repeatable
