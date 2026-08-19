"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from twin.adapters.elasticsearch import es_lifespan
from twin.adapters.postgres_token_repository import postgres_lifespan
from twin.application.token_service import TokenService
from twin.config import settings
from twin.domain.tokens import Token
from twin.presentation.admin_tokens import router as admin_tokens_router
from twin.presentation.bearer import require_bearer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with es_lifespan() as es:
        app.state.es = es
        async with postgres_lifespan() as token_repo:
            app.state.token_repo = token_repo
            if token_repo is not None and settings.bootstrap_token:
                token = await TokenService(token_repo).create_bootstrap(settings.bootstrap_token)
                if token is not None:
                    logger.info("Created bootstrap token '%s'", token.name)
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
