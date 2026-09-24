from controlplane.app.security import extract_bearer, token_matches


def test_bearer_parser():
    assert extract_bearer("Bearer abc123") == "abc123"
    assert extract_bearer("bearer abc123") == "abc123"
    assert extract_bearer("Basic abc123") is None
    assert extract_bearer(None) is None


def test_token_compare():
    assert token_matches("secret", "secret")
    assert not token_matches("secret", "other")
    assert not token_matches("", "secret")
