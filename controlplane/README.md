# Dispatcharr VOD Control Plane

A separate operator console and API for VOD catalog administration. It does not patch Dispatcharr core and keeps the Dispatcharr API key server-side.

## Start

Copy `.env.example` to `.env`, set a strong `CONTROL_PLANE_API_TOKEN`, and provide a dedicated Dispatcharr API key with the minimum permissions required.

    docker compose -f docker-compose.yml up -d --build

Open http://127.0.0.1:9393/.

## Safety contract

- Read-only until an explicit write action is confirmed.
- Regex changes require preview before queueing.
- Large regex operations run through Dispatcharr Celery in bounded transactions.
- Category delete requires zero movie/series/account relations.
- Secrets never reach the browser.
- Runtime SQLite data is not committed.
- Bind to localhost unless remote administration is explicitly protected.

## Dispatcharr integration

    GET  /api/plugins/plugins/
    POST /api/plugins/plugins/vod_catalog_manager/run/

Authentication uses the `X-API-Key` header. The VOD Catalog Manager plugin must be enabled before actions execute.

## Release path

Finish plugin canaries, add playback/source diagnostics, implement Jellyfin/Emby and Plex projections, run playback continuity tests, then pin tested Docker images and complete secret rotation.
