"""
Centralised configuration loaders for Texas Hold'em Poker.

Provides functions to load YAML configuration files from the ``config/``
directory.  These are used by :class:`GameController`, :class:`AIManager`,
and the FastAPI application entry-point.

Files loaded:
* ``config/llm_config.yaml`` — OpenAI model and trigger thresholds.
* ``config/personalities.yaml`` — AI personality profiles and decision timing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Paths resolved relative to the project root (parent of ``server/``).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LLM_CONFIG_PATH = _PROJECT_ROOT / "config" / "llm_config.yaml"
_PERSONALITIES_PATH = _PROJECT_ROOT / "config" / "personalities.yaml"


def load_llm_config() -> dict[str, Any]:
    """Load the LLM configuration from ``config/llm_config.yaml``.

    Returns a dictionary with keys such as ``model``, ``api_key``,
    ``max_output_tokens``, ``timeout_seconds``, and ``trigger``.

    Environment-variable placeholders (``${VAR_NAME}``) in string values
    are substituted automatically.

    Returns:
        The parsed config dict, or an empty dict if the file is missing
        or unparseable.
    """
    return _load_yaml(_LLM_CONFIG_PATH)


def load_personalities() -> dict[str, Any]:
    """Load personality profiles from ``config/personalities.yaml``.

    Returns a dictionary with keys ``personalities`` (a nested dict of
    profile definitions) and ``decision_timing`` (optional timing overrides).

    Returns:
        The parsed config dict, or an empty dict if the file is missing
        or unparseable.
    """
    return _load_yaml(_PERSONALITIES_PATH)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file from *path* with env-var substitution.

    Returns an empty dict on any failure so callers don't need to wrap
    every call in try/except.
    """
    try:
        if not path.exists():
            logger.warning("Config file not found: %s", path)
            return {}

        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        # Substitute ${ENV_VAR} placeholders
        _substitute_env_vars(data)

        return data

    except Exception:
        logger.exception("Failed to load config file: %s", path)
        return {}


def _substitute_env_vars(data: Any) -> None:
    """Recursively substitute ``${VAR_NAME}`` patterns in *data* in-place."""
    import os
    import re

    _re = re.compile(r"\$\{(\w+)\}")

    def _replace(value: str) -> str:
        return _re.sub(lambda m: os.environ.get(m.group(1), ""), value)

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = _replace(value)
            elif isinstance(value, (dict, list)):
                _substitute_env_vars(value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str):
                data[i] = _replace(item)
            elif isinstance(item, (dict, list)):
                _substitute_env_vars(item)
