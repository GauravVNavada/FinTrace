import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status

from app.controls.schemas import ActorContext, Role
from app.core.config import get_settings


def _unauthorized(message: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message, headers={"WWW-Authenticate": "Bearer"})


def _decode_part(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verified_claims(authorization: str | None) -> dict[str, Any] | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Bearer authentication is required")
    parts = token.split(".")
    if len(parts) != 3:
        raise _unauthorized("Invalid access token")
    try:
        header = json.loads(_decode_part(parts[0]))
        claims = json.loads(_decode_part(parts[1]))
        signature = _decode_part(parts[2])
    except (ValueError, json.JSONDecodeError) as error:
        raise _unauthorized("Invalid access token") from error
    settings = get_settings()
    if header.get("alg") != "HS256" or header.get("typ") not in {None, "JWT"}:
        raise _unauthorized("Unsupported access token")
    expected = hmac.new(settings.auth_secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise _unauthorized("Invalid access token")
    now = int(time.time())
    skew = settings.auth_clock_skew_seconds
    if claims.get("iss") != settings.auth_issuer or claims.get("aud") != settings.auth_audience:
        raise _unauthorized("Invalid access token claims")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise _unauthorized("Invalid access token subject")
    if not isinstance(claims.get("organization_id"), str) or not claims["organization_id"]:
        raise _unauthorized("Invalid access token organization")
    if not isinstance(claims.get("role"), str):
        raise _unauthorized("Invalid access token role")
    if not isinstance(claims.get("exp"), (int, float)) or now > float(claims["exp"]) + skew:
        raise _unauthorized("Access token expired")
    if "iat" in claims and (not isinstance(claims["iat"], (int, float)) or float(claims["iat"]) > now + skew):
        raise _unauthorized("Invalid access token issued-at time")
    return claims


def get_organization_id(
    x_organization_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """Resolve tenant scope from a verified token, with explicit dev-only fallback."""
    claims = _verified_claims(authorization)
    settings = get_settings()
    if claims is not None:
        claim_org = str(claims["organization_id"])
        if x_organization_id and x_organization_id != claim_org:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant scope mismatch")
        return claim_org
    if settings.auth_mode == "required":
        raise _unauthorized("Bearer authentication is required")
    if not x_organization_id:
        raise _unauthorized()
    return x_organization_id


def get_actor_context(
    organization_id: Annotated[str, Depends(get_organization_id)],
    x_actor_id: Annotated[str | None, Header()] = None,
    x_actor_role: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ActorContext:
    """Build actor context from verified identity claims or an explicitly enabled dev context."""
    try:
        claims = _verified_claims(authorization)
        actor_id = str(claims["sub"]) if claims is not None else (x_actor_id or "dev-analyst")
        actor_role = str(claims["role"]) if claims is not None else (x_actor_role or "ANALYST")
        return ActorContext(
            organization_id=organization_id,
            actor_id=actor_id,
            role=Role(actor_role),
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid actor context") from error
