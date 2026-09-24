from plugin.vod_catalog_manager.job_contract import (
    JobRequest,
    TERMINAL_STATES,
    normalize_job_request,
)


def test_job_request_defaults_and_bounds():
    req = normalize_job_request({"scope": "movie", "limit": 9999})
    assert isinstance(req, JobRequest)
    assert req.scope == "movie"
    assert req.limit == 500


def test_job_request_rejects_unknown_scope():
    try:
        normalize_job_request({"scope": "episode"})
    except ValueError as exc:
        assert "scope" in str(exc)
    else:
        raise AssertionError("episode scope must be rejected by the title job contract")


def test_terminal_states_are_stable():
    assert TERMINAL_STATES == {"completed", "failed", "revoked"}
