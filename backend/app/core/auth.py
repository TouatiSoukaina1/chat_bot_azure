import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from urllib.request import urlopen

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth_settings import TENANT_ID, API_AUDIENCE, REQUIRED_SCOPE

security = HTTPBearer(auto_error=True)
logger = logging.getLogger("app.auth")


@dataclass
class CurrentUser:
    user_id: str
    oid: str
    tid: str
    display_name: str | None
    preferred_username: str | None
    raw_claims: dict


def get_openid_config(token_version: str) -> dict:
    if token_version == "2.0":
        url = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration"
    else:
        url = f"https://login.microsoftonline.com/{TENANT_ID}/.well-known/openid-configuration"

    with urlopen(url) as response:
        return json.load(response)


@lru_cache
def get_jwks_client(jwks_uri: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_uri)


def _require_scope(claims: dict, required_scope: str) -> None:
    scopes = claims.get("scp", "")
    values = scopes.split() if scopes else []
    if required_scope not in values:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Scope '{required_scope}' absente du token",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials

    unverified_claims = jwt.decode(
        token,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_iss": False,
        },
    )
    token_version = unverified_claims.get("ver", "1.0")

    openid_config = get_openid_config(token_version)
    jwks_client = get_jwks_client(openid_config["jwks_uri"])

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=API_AUDIENCE,
            issuer=openid_config["issuer"],
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token expiré")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré",
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT invalide: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide: {exc}",
        )

    _require_scope(claims, REQUIRED_SCOPE)

    oid = claims.get("oid")
    tid = claims.get("tid")

    if not oid or not tid:
        logger.warning("Claims oid/tid absentes")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Claims oid/tid absentes",
        )

    user_id = f"{tid}:{oid}"

    logger.info(
        "Utilisateur authentifié | tid=%s oid=%s name=%s",
        tid,
        oid,
        claims.get("name"),
    )

    return CurrentUser(
        user_id=user_id,
        oid=oid,
        tid=tid,
        display_name=claims.get("name"),
        preferred_username=claims.get("preferred_username"),
        raw_claims=claims,
    )