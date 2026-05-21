"""Runtime configuration loaded from environment variables.

Defaults favor local browser development. The WebView2 host overrides several
values at launch time so desktop builds bind to generated loopback ports and write
exports beside the portable executable.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _csv_env(name: str, default: str) -> list[str]:
    """Parse comma-separated environment variables without empty entries."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


FRONTEND_ORIGINS = _csv_env(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "./exports"))
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "freshdesk_export_session")
