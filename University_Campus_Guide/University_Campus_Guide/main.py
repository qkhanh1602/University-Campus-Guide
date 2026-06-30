from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT, "campus_guide")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from main import main  # type: ignore  # imports campus_guide/main.py because APP_DIR is first in sys.path

if __name__ == "__main__":
    raise SystemExit(main())
