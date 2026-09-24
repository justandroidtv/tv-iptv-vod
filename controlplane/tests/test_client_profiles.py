from controlplane.app.client_profiles import all_client_profiles, get_client_profile


def test_profiles_cover_target_clients():
    ids = {x["id"] for x in all_client_profiles()}
    assert ids == {"jellyfin", "emby", "plex"}


def test_jellyfin_uses_separate_library_layout():
    p = get_client_profile("jellyfin")
    assert p["library_layout"] == ["Movies", "Shows"]
    assert p["projection"] == "vod2mlib_strm_nfo"


def test_plex_has_separate_projection():
    p = get_client_profile("plex")
    assert p["projection"] == "separate_plex_projection"
