"""Loads and caches all JSON config files from /config/ at startup."""

import json
import os
from functools import lru_cache
from typing import Any

CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")


def _load(filename: str) -> dict[str, Any]:
    path = os.path.join(CONFIG_DIR, filename)
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=None)
def get_business() -> dict:
    return _load("business.json")


@lru_cache(maxsize=None)
def get_kennels() -> dict:
    return _load("kennels.json")


@lru_cache(maxsize=None)
def get_pricing() -> dict:
    return _load("pricing.json")


@lru_cache(maxsize=None)
def get_pacfa() -> dict:
    return _load("pacfa.json")


def get_smtp() -> dict:
    """Return SMTP config with password injected from SMTP_PASSWORD env var.

    The smtp.json file must NOT contain a password; the credential is supplied
    exclusively via the SMTP_PASSWORD environment variable so it is never stored
    in the repository or on disk as plain text.
    """
    cfg = _load("smtp.json")
    password = os.environ.get("SMTP_PASSWORD", "")
    if not password:
        import logging
        logging.getLogger(__name__).warning(
            "SMTP_PASSWORD env var is not set — outbound email will fail"
        )
    cfg["password"] = password
    return cfg


@lru_cache(maxsize=None)
def get_phases() -> dict:
    return _load("phases.json")


@lru_cache(maxsize=None)
def get_system() -> dict:
    return _load("system.json")


@lru_cache(maxsize=None)
def get_ports() -> dict:
    return _load("ports.json")
