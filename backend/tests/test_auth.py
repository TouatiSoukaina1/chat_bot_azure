import pytest

from app.core import auth as auth_module


class FakeCredentials:
    def __init__(self, token: str):
        self.credentials = token


class FakeSigningKey:
    def __init__(self, key="fake-key"):
        self.key = key


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey()


def clear_auth_caches():
    if hasattr(auth_module.get_openid_config, "cache_clear"):
        auth_module.get_openid_config.cache_clear()
    if hasattr(auth_module.get_jwks_client, "cache_clear"):
        auth_module.get_jwks_client.cache_clear()


def test_require_scope_accepts_present_scope():
    auth_module._require_scope({"scp": "openid profile access_as_user"}, "access_as_user")


def test_require_scope_rejects_missing_scope():
    with pytest.raises(auth_module.HTTPException) as exc:
        auth_module._require_scope({"scp": "openid profile"}, "access_as_user")

    assert exc.value.status_code == 403
    assert "access_as_user" in exc.value.detail


def test_get_current_user_success(monkeypatch):
    clear_auth_caches()

    monkeypatch.setattr(
        auth_module,
        "get_openid_config",
        lambda token_version: {
            "issuer": "https://issuer.test",
            "jwks_uri": "https://issuer.test/jwks",
        },
    )
    monkeypatch.setattr(
        auth_module,
        "get_jwks_client",
        lambda token_version: FakeJwksClient(),
    )

    def fake_decode(token, *args, **kwargs):
        # 1er decode: lecture non vérifiée
        if kwargs.get("options"):
            return {"ver": "2.0"}

        # 2e decode: vérification
        assert token == "fake-token"
        assert args[0] == "fake-key"
        assert kwargs["algorithms"] == ["RS256"]
        assert kwargs["audience"] == auth_module.API_AUDIENCE
        assert kwargs["issuer"] == "https://issuer.test"
        return {
            "oid": "user-oid",
            "tid": "tenant-id",
            "name": "Soukaina",
            "preferred_username": "soukaina@example.com",
            "scp": "access_as_user",
        }

    monkeypatch.setattr(auth_module.jwt, "decode", fake_decode)

    user = auth_module.get_current_user(FakeCredentials("fake-token"))

    assert user.user_id == "tenant-id:user-oid"
    assert user.oid == "user-oid"
    assert user.tid == "tenant-id"
    assert user.display_name == "Soukaina"
    assert user.preferred_username == "soukaina@example.com"


def test_get_current_user_expired_token(monkeypatch):
    clear_auth_caches()

    monkeypatch.setattr(
        auth_module,
        "get_openid_config",
        lambda token_version: {
            "issuer": "https://issuer.test",
            "jwks_uri": "https://issuer.test/jwks",
        },
    )
    monkeypatch.setattr(
        auth_module,
        "get_jwks_client",
        lambda token_version: FakeJwksClient(),
    )

    def fake_decode(token, *args, **kwargs):
        if kwargs.get("options"):
            return {"ver": "2.0"}
        raise auth_module.jwt.ExpiredSignatureError("expired")

    monkeypatch.setattr(auth_module.jwt, "decode", fake_decode)

    with pytest.raises(auth_module.HTTPException) as exc:
        auth_module.get_current_user(FakeCredentials("expired-token"))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expiré"


def test_get_current_user_invalid_token(monkeypatch):
    clear_auth_caches()

    monkeypatch.setattr(
        auth_module,
        "get_openid_config",
        lambda token_version: {
            "issuer": "https://issuer.test",
            "jwks_uri": "https://issuer.test/jwks",
        },
    )
    monkeypatch.setattr(
        auth_module,
        "get_jwks_client",
        lambda token_version: FakeJwksClient(),
    )

    def fake_decode(token, *args, **kwargs):
        if kwargs.get("options"):
            return {"ver": "2.0"}
        raise auth_module.jwt.InvalidTokenError("bad token")

    monkeypatch.setattr(auth_module.jwt, "decode", fake_decode)

    with pytest.raises(auth_module.HTTPException) as exc:
        auth_module.get_current_user(FakeCredentials("bad-token"))

    assert exc.value.status_code == 401
    assert "Token invalide" in exc.value.detail


def test_get_current_user_missing_oid_or_tid(monkeypatch):
    clear_auth_caches()

    monkeypatch.setattr(
        auth_module,
        "get_openid_config",
        lambda token_version: {
            "issuer": "https://issuer.test",
            "jwks_uri": "https://issuer.test/jwks",
        },
    )
    monkeypatch.setattr(
        auth_module,
        "get_jwks_client",
        lambda token_version: FakeJwksClient(),
    )

    def fake_decode(token, *args, **kwargs):
        if kwargs.get("options"):
            return {"ver": "2.0"}
        return {
            "scp": "access_as_user",
            "name": "Soukaina",
        }

    monkeypatch.setattr(auth_module.jwt, "decode", fake_decode)

    with pytest.raises(auth_module.HTTPException) as exc:
        auth_module.get_current_user(FakeCredentials("token"))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Claims oid/tid absentes"