"""Admin endpoints for issuing, listing and revoking API tokens."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from twin.application.token_service import TokenService
from twin.domain.tokens import Token, TokenAlreadyRevoked, TokenInvalid, TokenNameRequired
from twin.presentation.bearer import require_bearer
from twin.presentation.dependencies import get_token_service

router = APIRouter(prefix="/admin/tokens", tags=["admin-tokens"])


class IssueTokenRequest(BaseModel):
    name: str = Field(min_length=1)
    ttl_days: int | None = Field(default=None, gt=0)


class TokenView(BaseModel):
    id: str
    name: str
    created_at: str
    expires_at: str | None = None
    revoked_at: str | None = None
    revoked: bool = False


class TokenIssuedView(TokenView):
    token: str


def _view(token: Token) -> TokenView:
    return TokenView(
        id=str(token.id),
        name=token.name,
        created_at=token.created_at.isoformat(),
        expires_at=token.expires_at.isoformat() if token.expires_at else None,
        revoked_at=token.revoked_at.isoformat() if token.revoked_at else None,
        revoked=token.revoked_at is not None,
    )


AuthenticatedToken = Annotated[Token, Depends(require_bearer)]
Auth = Annotated[TokenService, Depends(get_token_service)]


@router.post("", response_model=TokenIssuedView, status_code=status.HTTP_201_CREATED)
async def issue_token(
    payload: IssueTokenRequest,
    _token: AuthenticatedToken,
    auth: Auth,
) -> TokenIssuedView:
    """Issue a new token. The plaintext is returned exactly once."""
    try:
        token, raw = await auth.issue_token(payload.name, ttl_days=payload.ttl_days)
    except TokenNameRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    view = _view(token).model_dump()
    view["token"] = raw
    return TokenIssuedView(**view)


@router.get("", response_model=list[TokenView])
async def list_tokens(
    _token: AuthenticatedToken,
    auth: Auth,
) -> list[TokenView]:
    """List tokens. The hashed value is never exposed."""
    tokens = await auth.list_tokens()
    return [_view(t) for t in tokens]


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: uuid.UUID,
    _token: AuthenticatedToken,
    auth: Auth,
) -> None:
    """Revoke a token; it stops authorizing immediately."""
    try:
        await auth.revoke_token(token_id)
    except TokenInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except TokenAlreadyRevoked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
