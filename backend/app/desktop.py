"""Desktop backend launcher used by the WebView2 host."""

from __future__ import annotations

import os
from multiprocessing import freeze_support

import uvicorn


def main() -> None:
    """Run the FastAPI app with desktop-friendly defaults."""
    freeze_support()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "warning")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
    )


if __name__ == "__main__":
    main()
