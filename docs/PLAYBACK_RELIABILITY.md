# VOD Playback Reliability

Date: 2026-09-24

## Verified deployment facts

Dispatcharr 0.31.0 VOD proxy core is untouched in this project. The proxy already provides Redirect, proxy sessions, Range handling, Redis capacity/locking, connection reuse, and a retry for expired provider sessions.

The current provider request timeout in the connection manager is 10 seconds for connect/read. No project-owned VOD timeout setting was found in the current tree.

## Policy

Do not patch the Dispatcharr VOD proxy core.

Use this decision order:

1. Redirect / direct delivery when compatible.
2. Direct Stream / remux when only transport/audio/subtitle adaptation is required.
3. Hardware transcoding only when required.
4. Software transcoding as the final fallback.

Do not globally force a transcode-heavy VOD profile.

## Failure taxonomy

Classify interruptions as provider timeout, provider reset, signed-link expiry, HTTP Range failure, account slot exhaustion, source unavailability, codec incompatibility, audio incompatibility, subtitle burn-in, bitrate ceiling, transcoder saturation, storage latency, or Docker memory pressure.

A passing long-play test means no repeatable interruption under the tested conditions; it is not a promise of zero buffering.

## Client paths

Jellyfin: dedicated Movies and Shows libraries; use the VOD filesystem projection as presentation, not canonical identity.

Emby: start with Direct Play and Direct Stream, automatic bitrate, and hardware transcoding only when required.

Plex: keep a separate projection path; do not assume the same STRM behavior as Jellyfin/Emby.

## Long-play matrix

Per client:

- start a known-good movie
- record source/account
- run 30 minute test
- seek forward/back
- pause/resume
- continue to 60 minutes
- continue to 120 minutes
- repeat during catalog refresh
- repeat during controlled metadata work
- classify every interruption
