"""Optional same-origin frontend for a single-container demo deployment."""

from starlette.staticfiles import StaticFiles
from starlette.types import Scope

WEB_ROUTES = frozenset(
    {
        "",
        ".",
        "login",
        "system",
        "sales",
        "products",
        "inventory",
        "suppliers",
        "purchase-orders",
        "settings",
        "assistant",
        "documents",
        "agents",
        "showcase",
    }
)


class WebFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        path = path.replace("\\", "/")
        # Only actual client routes receive the SPA. Unknown API routes and missing
        # assets retain their HTTP 404 instead of returning a misleading HTML 200.
        if path.strip("/") in WEB_ROUTES:
            path = "index.html"
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if path.startswith("assets/") and response.status_code == 200
            else "no-cache"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
