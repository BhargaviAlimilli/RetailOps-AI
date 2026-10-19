"""Real MCP handshake plus mocked HTTP: never calls a model or external account."""

import asyncio
import sys
from datetime import date
from uuid import uuid4

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

from app.mcp_server import (
    DocumentSearch,
    InventoryFilters,
    MCPRequestError,
    OrderFilters,
    ReadOnlyRetailClient,
    SalesFilters,
)


def test_mcp_standard_initialize_and_readonly_allowlist():
    async def run():
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"])
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.name == "RetailOps AI read-only"
            tools = (await session.list_tools()).tools
            assert {tool.name for tool in tools} == {
                "get_sales_summary",
                "get_inventory_levels",
                "list_purchase_orders",
                "search_documents",
            }
            assert all(tool.annotations.readOnlyHint for tool in tools)
            invalid = await session.call_tool("get_inventory_levels", {"page_size": 1000})
            assert invalid.isError

    asyncio.run(run())


def test_inventory_and_orders_forward_only_validated_read_filters():
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"items": [], "total": 0, "page": 3, "page_size": 20})

    async def run():
        client = ReadOnlyRetailClient(
            "https://retail.example", "fictional-session", transport=httpx.MockTransport(handle)
        )
        await client.inventory(InventoryFilters(q="rice & oil", status="low", page=3))
        await client.orders(OrderFilters(status="pending", page=3))

    asyncio.run(run())
    assert [request.method for request in seen] == ["GET", "GET"]
    assert seen[0].url.path == "/api/v1/inventory"
    assert seen[0].url.params["q"] == "rice & oil"
    assert seen[1].url.params["status"] == "pending"
    assert seen[1].url.params["page"] == "3"
    assert all(request.headers["Authorization"] == "Bearer fictional-session" for request in seen)


def test_documents_preserve_citations_and_actor_token_scope():
    citation = {
        "document_id": str(uuid4()),
        "chunk_id": str(uuid4()),
        "title": "Synthetic policy",
        "excerpt": "Review low stock.",
        "score": 0.5,
    }
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"citations": [citation]})

    async def run():
        client = ReadOnlyRetailClient(
            "http://127.0.0.1:8000", "fictional-session", transport=httpx.MockTransport(handle)
        )
        return await client.documents(DocumentSearch(query="inventory policy", limit=5))

    assert asyncio.run(run()) == {"citations": [citation]}
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/api/v1/documents/search"
    assert b'"query":"inventory policy"' in seen[0].content
    assert b"user_id" not in seen[0].content


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_errors_never_expose_headers_provider_text_or_redirect_tokens(status):
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(
            status,
            text="private-provider-or-database-details",
            headers={"location": "https://other.example"},
        )

    async def run():
        client = ReadOnlyRetailClient(
            "https://retail.example", "fictional-session", transport=httpx.MockTransport(handle)
        )
        await client.orders(OrderFilters())

    with pytest.raises(MCPRequestError) as error:
        asyncio.run(run())
    assert "private" not in str(error.value)
    assert "fictional-session" not in str(error.value)
    assert len(seen) == 1


def test_rejects_invalid_origins_and_inputs_before_any_http_call():
    for origin in [
        "http://external.example",
        "https://user:pass@example.com",
        "file:///etc/passwd",
        "https://example.com/path",
    ]:
        with pytest.raises(MCPRequestError):
            ReadOnlyRetailClient(origin, "fictional-session")
    with pytest.raises(MCPRequestError):
        ReadOnlyRetailClient("https://example.com", "")
    for arguments in [{"page_size": 101}, {"status": "approve"}, {"page": 0}, {"page": True}]:
        with pytest.raises(ValidationError):
            OrderFilters(**arguments)
    with pytest.raises(ValidationError):
        DocumentSearch(query=" ")
    with pytest.raises(ValidationError):
        SalesFilters(start_date=date(2026, 1, 1), end_date=date(2025, 1, 1))


def test_invalid_response_and_transport_errors_are_sanitized():
    async def handle(request):
        raise httpx.ReadTimeout("private connection information", request=request)

    async def run(transport):
        client = ReadOnlyRetailClient(
            "https://retail.example", "fictional-session", transport=transport
        )
        await client.orders(OrderFilters())

    for transport in [
        httpx.MockTransport(handle),
        httpx.MockTransport(lambda request: httpx.Response(200, json={"unexpected": True})),
    ]:
        with pytest.raises(MCPRequestError, match="unavailable or invalid"):
            asyncio.run(run(transport))
