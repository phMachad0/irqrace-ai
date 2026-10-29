"""Entrypoint for the native Windows (Win32/Tkinter) irqrace MVP GUI.

Usage:
    python project-src/desktop_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from irqrace.ui.desktop import main  # noqa: E402

if __name__ == "__main__":
    main()
