"""Bearer-token authentication dependency for the REST surface."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from twin.application.token_service import TokenService
from twin.domain.tokens import Token, TokenError
from twin.presentation.dependencies import get_token_service

_WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}


async def require_bearer(
    auth: Annotated[TokenService, Depends(get_token_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> Token:
    """Validate the `Authorization: Bearer <token>` header and return the token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers=_WWW_AUTHENTICATE,
        )
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers=_WWW_AUTHENTICATE,
        )
    try:
        return await auth.validate_bearer(value)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=_WWW_AUTHENTICATE,
        ) from exc
