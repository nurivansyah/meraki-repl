"""Bearer-token authentication shared by the REST and MCP surfaces."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from twin.application.token_service import TokenService
from twin.domain.tokens import Token, TokenError
from twin.presentation.dependencies import get_token_service

WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}


async def validate_bearer_header(authorization: str | None, auth: TokenService) -> Token:
    """Parse and validate an ``Authorization`` header, raising 401 on failure."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers=WWW_AUTHENTICATE,
        )
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers=WWW_AUTHENTICATE,
        )
    try:
        return await auth.validate_bearer(value)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=WWW_AUTHENTICATE,
        ) from exc


async def require_bearer(
    auth: Annotated[TokenService, Depends(get_token_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> Token:
    """FastAPI dependency enforcing the bearer-token scheme."""
    return await validate_bearer_header(authorization, auth)
