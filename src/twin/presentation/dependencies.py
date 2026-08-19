"""FastAPI dependencies for the auth realm."""

from typing import Annotated, Any

from fastapi import Depends, Request

from twin.adapters.elasticsearch import get_es_client
from twin.adapters.elasticsearch_state_store import ElasticsearchStateStore
from twin.application.ports import TokenRepository
from twin.application.state_store import StateStore
from twin.application.token_service import TokenService


def get_token_repository(request: Request) -> TokenRepository:
    """Return the token repository held on app state."""
    repo = getattr(request.app.state, "token_repo", None)
    if repo is None:
        raise RuntimeError("Token repository not initialized.")
    return repo


def get_state_store(
    es: Annotated[Any, Depends(get_es_client)],
) -> StateStore:
    """Return a ``StateStore`` bound to the current Elasticsearch client."""
    return ElasticsearchStateStore(es)


def get_token_service(
    repo: Annotated[TokenRepository, Depends(get_token_repository)],
) -> TokenService:
    """Provide an TokenService bound to the configured repository."""
    return TokenService(repo)
