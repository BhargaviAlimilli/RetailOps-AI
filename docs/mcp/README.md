# Authenticated read-only MCP facade

Run `python -m app.mcp_server` from `backend/` using the installed backend environment. This is a standard MCP SDK stdio server. It exposes exactly four tools:

| Tool | Fixed API | Boundaries |
|---|---|---|
| `get_sales_summary` | `GET /api/v1/dashboard` | UUID store/category filters, ordered UTC dates, at most 366 days |
| `get_inventory_levels` | `GET /api/v1/inventory` | Literal stock status, bounded search, page size at most 100 |
| `list_purchase_orders` | `GET /api/v1/purchase-orders` | Literal status and server-side pagination |
| `search_documents` | `POST /api/v1/documents/search` | Query at most 2,000 characters, at most ten owner-scoped citations |

Set `RETAILOPS_MCP_BASE_URL` to the API origin and `RETAILOPS_MCP_TOKEN` to a current authenticated RetailOps session token. Obtain the token using the normal login flow for the intended account; the server never logs in, stores passwords, or elevates its role. Tokens expire and are revocable. Keep the token in your MCP client's protected environment/secret configuration, never in a committed JSON file or command-line argument. `RETAILOPS_MCP_TOKEN` belongs to the MCP process environment; it is not a browser configuration variable.

Example client configuration shape, replacing the executable/path with the local environment and supplying secrets through the client's secure mechanism:

```json
{
  "mcpServers": {
    "retailops-readonly": {
      "command": "/absolute/path/backend/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/backend",
      "env": { "RETAILOPS_MCP_BASE_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

Use `.venv/Scripts/python.exe` on Windows. Configuration keys such as `cwd` depend on the MCP host. The token must additionally be supplied through that host's secret environment facility. A missing token produces a safe tool error; initialization and tool discovery require no API token or network connection.

Only HTTPS origins are allowed except loopback HTTP. Redirects and environment HTTP proxies are disabled so credentials are not forwarded to another origin. Inputs and response contracts are validated; errors omit transport internals, upstream response bodies, and credentials. No SQL, URL selection, file access, model code execution, or business write tool is exposed. HTTP POST for search is a read operation and does not authorize mutations. Document excerpts remain untrusted evidence, never instructions.

Document search may request configured embeddings through the backend when owned documents exist; that can incur provider cost. The facade itself does not generate answers. Unit tests use mocked HTTP and the MCP handshake test only initializes/discovers tools; neither makes paid model requests. Authentication and document ownership are enforced by the existing API, so a token grants the same account scope through MCP as through the browser.

Verification command: `python -m pytest tests/test_mcp_server.py`. This includes a real local stdio initialize/list-tools exchange, invalid argument rejection, fixed read endpoint forwarding, citation preservation, redirect rejection, and sanitized HTTP errors.
