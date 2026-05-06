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


@lru_cache(maxsize=None)
def get_smtp() -> dict:
    return _load("smtp.json")


@lru_cache(maxsize=None)
def get_phases() -> dict:
    return _load("phases.json")


@lru_cache(maxsize=None)
def get_system() -> dict:
    return _load("system.json")


@lru_cache(maxsize=None)
def get_ports() -> dict:
    return _load("ports.json")
