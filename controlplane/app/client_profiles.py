from __future__ import annotations

CLIENT_PROFILES = {
    "jellyfin": {
        "name": "Jellyfin",
        "library_layout": ["Movies", "Shows"],
        "preferred_path": ["redirect", "direct_stream", "hardware_transcode", "software_transcode"],
        "tmdb_folder_tag": "[tmdbid-123]",
        "projection": "vod2mlib_strm_nfo",
        "notes": [
            "Use dedicated Movies and Shows libraries.",
            "Keep VOD2MLIB refresh outside peak playback windows.",
            "Do not use a mixed media library for VOD movies and series.",
        ],
    },
    "emby": {
        "name": "Emby",
        "library_layout": ["Movies", "TV"],
        "preferred_path": ["direct_play", "direct_stream", "hardware_transcode", "software_transcode"],
        "tmdb_folder_tag": "[tmdbid-123]",
        "projection": "vod2mlib_strm_nfo",
        "notes": [
            "Prefer Direct Play when the source is compatible.",
            "Use Direct Stream/remux when only transport/audio/subtitle adaptation is required.",
            "Use hardware transcoding only when required.",
        ],
    },
    "plex": {
        "name": "Plex",
        "library_layout": ["Movies", "TV Shows"],
        "preferred_path": ["direct_play", "direct_stream", "hardware_transcode", "software_transcode"],
        "tmdb_folder_tag": "{tmdb-123}",
        "projection": "separate_plex_projection",
        "notes": [
            "Keep Plex projection separate from Jellyfin/Emby .strm projection.",
            "Do not assume Jellyfin/Emby STRM behavior maps directly to Plex.",
            "Prefer compatible source delivery before any transcoding.",
        ],
    },
}


def get_client_profile(client: str) -> dict:
    key = str(client or "").strip().lower()
    if key not in CLIENT_PROFILES:
        raise ValueError(f"Unknown client: {client}")
    return CLIENT_PROFILES[key]


def all_client_profiles() -> list[dict]:
    return [
        {"id": key, **value}
        for key, value in CLIENT_PROFILES.items()
    ]
