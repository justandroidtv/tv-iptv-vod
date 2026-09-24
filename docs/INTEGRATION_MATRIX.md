# Plex / Jellyfin / Emby Integration Matrix

## Shared principles

All three clients share:
- canonical identity
- source health
- naming policy
- category policy
- audit
- source metadata

They do not need to share the same output projection.

## Playback order

Direct Play -> Direct Stream/remux -> hardware transcode -> software transcode

Do not force transcoding when compatible direct playback is available.

## Jellyfin

Projection:
- /VODS/Movies
- /VODS/Series

Recommended:
- dedicated Movies library
- dedicated Shows library
- read-only consumer mount
- NFO when metadata quality matters
- TMDB IDs where exact matching matters
- scheduled scan outside peak time

Acceptance:
1. movie opens
2. 2+ hour movie
3. seek forward
4. seek backward
5. pause/resume
6. audio switch
7. subtitle switch
8. episode start
9. next episode
10. library refresh during playback

## Emby

Recommended:
- same underlying VOD roots where practical
- Direct Play enabled
- Direct Stream enabled
- automatic bitrate initially
- hardware transcoding only when required
- transcode temp on SSD

Acceptance matches Jellyfin.

## Plex

Do not assume STRM playback equivalence.

Create a Plex-specific projection using Plex-compatible library behavior.

Acceptance:
1. metadata match
2. movie playback
3. long movie playback
4. seek
5. pause/resume
6. audio switch
7. subtitle behavior
8. collection visibility
9. refresh without duplicate entries

## VOD2MLIB

Reuse VOD2MLIB to write the filesystem projection.

The control plane decides:
- which items are included
- display naming
- TMDB identity
- folder naming
- category nesting
- rescan timing

Do not force one title string to serve every client.
