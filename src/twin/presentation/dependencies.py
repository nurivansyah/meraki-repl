"""FastAPI dependencies for the auth realm."""

from typing import Annotated, Any

from fastapi import Depends, Request

from twin.adapters.elasticsearch import get_es_client
from twin.adapters.elasticsearch_state_store import ElasticsearchStateStore
from twin.application.ports import TokenRepository
from twin.application.read_mirror import ReadMirror
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


def get_read_mirror(
    store: Annotated[StateStore, Depends(get_state_store)],
    request: Request,
) -> ReadMirror:
    """Return the shared read core bound to the current ``StateStore``.

    If ``app.state.graph_store`` is set, an ``ImpactAnalyzer`` is wired.
    """
    graph_store = getattr(request.app.state, "graph_store", None)
    analyzer = None
    if graph_store is not None:
        from twin.application.impact_analyzer import ImpactAnalyzer

        default_depth = getattr(request.app.state, "impact_default_depth", 10)
        analyzer = ImpactAnalyzer(graph=graph_store, default_depth=default_depth)
    return ReadMirror(store, impact_analyzer=analyzer)


def get_token_service(
    repo: Annotated[TokenRepository, Depends(get_token_repository)],
) -> TokenService:
    """Provide an TokenService bound to the configured repository."""
    return TokenService(repo)
