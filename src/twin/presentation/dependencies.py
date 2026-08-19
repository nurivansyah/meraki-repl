"""FastAPI dependencies for the auth realm."""

from typing import Annotated

from fastapi import Depends, Request

from twin.application.ports import TokenRepository
from twin.application.token_service import TokenService


def get_token_repository(request: Request) -> TokenRepository:
    """Return the token repository held on app state."""
    repo = getattr(request.app.state, "token_repo", None)
    if repo is None:
        raise RuntimeError("Token repository not initialized.")
    return repo


def get_token_service(
    repo: Annotated[TokenRepository, Depends(get_token_repository)],
) -> TokenService:
    """Provide an TokenService bound to the configured repository."""
    return TokenService(repo)
