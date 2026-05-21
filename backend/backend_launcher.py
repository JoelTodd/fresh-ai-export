"""Import-safe entrypoint for the bundled Python backend.

The portable Windows app launches this file from the copied backend directory.
It adds that directory to `sys.path` before importing `app.desktop` so the same
backend package works both from source and from the build payload.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.desktop import main


main()
