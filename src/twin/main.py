"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from twin.adapters.elasticsearch import es_lifespan
from twin.adapters.elasticsearch_state_store import ElasticsearchStateStore
from twin.adapters.postgres_token_repository import postgres_lifespan
from twin.application.read_mirror import ReadMirror
from twin.application.token_service import TokenService
from twin.config import settings
from twin.domain.tokens import Token
from twin.presentation.admin_tokens import router as admin_tokens_router
from twin.presentation.bearer import require_bearer
from twin.presentation.chronology_router import router as chronology_router
from twin.presentation.mcp_server import configure_runtime, mcp_app
from twin.presentation.state_router import (
    router as state_router,
)
from twin.presentation.state_router import (
    router_clients as clients_router,
)
from twin.presentation.state_router import (
    router_devices as devices_router,
)
from twin.presentation.state_router import (
    router_switchports as switchports_router,
)
from twin.presentation.state_router import (
    router_topology as topology_router,
)
from twin.presentation.state_router import (
    router_uplinks as uplinks_router,
)
from twin.presentation.state_router import (
    router_vlans as vlans_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with es_lifespan() as es:
        app.state.es = es
        async with postgres_lifespan() as token_repo:
            app.state.token_repo = token_repo
            if token_repo is not None:
                token_service = TokenService(token_repo)
                if settings.bootstrap_token:
                    token = await token_service.create_bootstrap(settings.bootstrap_token)
                    if token is not None:
                        logger.info("Created bootstrap token '%s'", token.name)
                if es is not None:
                    configure_runtime(ReadMirror(ElasticsearchStateStore(es)), token_service)
            yield
    # Shutdown


app = FastAPI(
    title="Meraki Network Twin",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_tokens_router)
app.include_router(state_router)
app.include_router(devices_router)
app.include_router(uplinks_router)
app.include_router(switchports_router)
app.include_router(vlans_router)
app.include_router(topology_router)
app.include_router(clients_router)
app.include_router(chronology_router)
app.mount("/mcp", mcp_app())


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"service": "Meraki Network Twin", "version": "0.1.0"}


@app.get("/whoami")
async def whoami(token: Annotated[Token, Depends(require_bearer)]) -> dict[str, str | None]:
    """Return the identity of the authenticated token."""
    return {
        "id": str(token.id),
        "name": token.name,
        "created_at": token.created_at.isoformat(),
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
    }
