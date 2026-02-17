"""
Config package compatibility layer.

This package name (`config/`) coexists with `backend/config.py`.
In some runtimes (e.g. production workers), `from config import config`
may resolve to this package instead of `config.py`.

To keep backward compatibility, expose a `config` object here by loading
`backend/config.py` dynamically when needed.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any


def _load_config_from_module() -> Any:
    """Load `backend/config.py` and return its `config` object."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.py")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "config.py")),
        os.path.abspath(os.path.join(os.getcwd(), "config.py")),
        os.path.abspath(os.path.join(os.getcwd(), "backend", "config.py")),
    ]

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend(
            [
                os.path.join(meipass, "config.py"),
                os.path.join(meipass, "backend", "config.py"),
            ]
        )

    module_path = next((path for path in candidates if os.path.exists(path)), None)
    if not module_path:
        raise ImportError("Could not locate runtime config.py")

    spec = importlib.util.spec_from_file_location("tutti_runtime_config", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "config"):
        raise ImportError("Loaded config module does not expose `config`")
    return module.config


config = _load_config_from_module()

__all__ = ["config"]
