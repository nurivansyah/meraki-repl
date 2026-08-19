"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from twin.adapters.elasticsearch import es_lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with es_lifespan() as es:
        app.state.es = es
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


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"service": "Meraki Network Twin", "version": "0.1.0"}
