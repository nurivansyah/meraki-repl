"""Smoke test for the MCP server surface.

Spins up the real app under uvicorn on a free port (with the fake ES + token
repo wired in), connects an official MCP client over SSE, and confirms the
tools reach the same core behavior the REST seam already covers.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading

import httpx
import pytest
import uvicorn
from fastapi import status
from mcp import ClientSession
from mcp.client.sse import sse_client

from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.adapters.elasticsearch import get_es_client
from twin.adapters.elasticsearch_state_store import ElasticsearchStateStore
from twin.application.read_mirror import ReadMirror
from twin.application.token_service import TokenService
from twin.main import app
from twin.presentation.dependencies import get_token_repository
from twin.presentation.mcp_server import configure_runtime

NETWORK_DOC = {
    "name": "HQ",
    "timeZone": "UTC",
    "tags": ["prod"],
    "productTypes": ["switch"],
    "meraki_org_id": "",
    "network_id": "N_123",
    "@timestamp": "2026-01-01T00:00:00Z",
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _wait_until_ready(port: int) -> None:
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            await asyncio.sleep(0.05)
    raise AssertionError("uvicorn server did not become ready")


@pytest.mark.asyncio
async def test_mcp_smoke(fake_es, token_repo: FakeTokenRepository):
    fake_es.seed("meraki-network-metrics", {"N_123": NETWORK_DOC})
    app.dependency_overrides[get_es_client] = lambda: fake_es
    app.dependency_overrides[get_token_repository] = lambda: token_repo
    configure_runtime(ReadMirror(ElasticsearchStateStore(fake_es)), TokenService(token_repo))

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=lambda: asyncio.run(server.serve()), daemon=True)
    thread.start()
    try:
        await _wait_until_ready(port)

        unauth = httpx.get(f"http://127.0.0.1:{port}/mcp/sse")
        assert unauth.status_code == status.HTTP_401_UNAUTHORIZED
        assert unauth.headers["www-authenticate"] == "Bearer"

        service = TokenService(token_repo)
        _, raw = await service.issue_token("reader")
        url = f"http://127.0.0.1:{port}/mcp/sse"
        async with sse_client(
            url, headers={"Authorization": f"Bearer {raw}"}
        ) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert "list_networks" in {t.name for t in tools.tools}
            assert "get_network" in {t.name for t in tools.tools}

            res = await session.call_tool("list_networks", {})
            assert not res.is_error
            result = res.structured_content["result"]
            assert result[0]["id"] == "N_123"
            assert result[0]["name"] == "HQ"
            assert result[0]["as_of"] == "2026-01-01T00:00:00Z"

            res = await session.call_tool("get_network", {"network_id": "N_123"})
            assert not res.is_error
            payload = json.loads(res.content[0].text)
            assert payload["name"] == "HQ"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        app.dependency_overrides.clear()
