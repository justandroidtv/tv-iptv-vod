# Architecture

## Boundary

Dispatcharr core is an immutable dependency.

Allowed:

- supported Dispatcharr plugin API
- plugin folders under /data/plugins
- authenticated REST endpoints
- Celery through the plugin contract
- persistent plugin-owned data

Never edit:

- /app/apps
- core
- Dispatcharr migrations
- the Dispatcharr Docker image
- upstream files inside the running image

## Runtime topology

Client -> Plex/Jellyfin/Emby -> VOD output
                                   |
                                   v
                          Dispatcharr
                             |
                    supported plugin API
                             |
                 VOD Catalog Manager plugin
                             ^
                             |
                    External Control Plane

The control plane owns policy, profiles and audit data. Dispatcharr remains the authoritative VOD database.

## VOD playback policy

Decision order:

1. Validate source availability.
2. Prefer Redirect or direct delivery when compatible.
3. Prefer Direct Stream or remux when only container, audio or subtitle adaptation is needed.
4. Use hardware transcoding only when necessary.
5. Use software transcoding as final fallback.

Do not apply a transcode-heavy Output Profile globally to VOD. Extra processing can turn a compatible direct path into a fragile pipeline.

## Failure handling

Track:

- provider or account health
- timeout and reset counts
- cooldown state
- last known good source
- source edition identity
- selected source and reason
- client compatibility profile

A dead provider must not consume the worker pool through repeated long retries.

## Catalog model

Logical layers:

1. canonical identity
2. source edition
3. presentation policy
4. output projection

A provider label should normally be removed from presentation rules rather than destroying source identity.

## Naming

Preferred flow:

raw provider title -> normalization rules -> canonical match -> display alias -> filesystem-safe name

Canonical mutation is an expert operation, not the default.

## Background operations

Full-catalog tasks are jobs:

- catalog scan
- metadata enrichment
- regex apply
- category migration
- STRM regeneration
- health sampling
- reconciliation

The UI submits jobs and polls status; it does not hold a browser request open for a full catalogue.

## Upgrade model

1. backup
2. use a tested Dispatcharr image tag or digest
3. start containers
4. reload plugins
5. run compatibility tests
6. run a ten-title VOD canary

No core patch should be required.
