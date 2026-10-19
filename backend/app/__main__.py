"""Run the API with a psycopg-compatible event loop on Windows."""

import asyncio
import sys

import uvicorn

if __name__ == "__main__":
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=8000, access_log=False)
    server = uvicorn.Server(config)
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(server.serve())
