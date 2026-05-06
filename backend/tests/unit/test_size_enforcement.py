"""Unit tests: size class enforcement — dog must not exceed kennel max_size_class.

Spec §6.5 — Size hierarchy: XS < S < M < L < XL. Hard block, no override.
"""

import pytest
from app.services.pacfa import validate_size_class

SIZE_HIERARCHY = ["XS", "S", "M", "L", "XL"]


# ── Dog size == kennel max (always valid) ──────────────────────────────────────

@pytest.mark.parametrize("size_class", SIZE_HIERARCHY)
def test_dog_matches_kennel_max_size(size_class):
    assert validate_size_class(size_class, size_class) is True


# ── Dog smaller than kennel max (always valid) ─────────────────────────────────

@pytest.mark.parametrize("dog_size,kennel_max", [
    ("XS", "S"),
    ("XS", "M"),
    ("XS", "L"),
    ("XS", "XL"),
    ("S",  "M"),
    ("S",  "L"),
    ("S",  "XL"),
    ("M",  "L"),
    ("M",  "XL"),
    ("L",  "XL"),
])
def test_dog_smaller_than_kennel_max_is_valid(dog_size, kennel_max):
    assert validate_size_class(dog_size, kennel_max) is True


# ── Dog larger than kennel max (always blocked) ────────────────────────────────

@pytest.mark.parametrize("dog_size,kennel_max", [
    ("S",  "XS"),
    ("M",  "XS"),
    ("M",  "S"),
    ("L",  "XS"),
    ("L",  "S"),
    ("L",  "M"),
    ("XL", "XS"),
    ("XL", "S"),
    ("XL", "M"),
    ("XL", "L"),
])
def test_dog_larger_than_kennel_max_is_invalid(dog_size, kennel_max):
    assert validate_size_class(dog_size, kennel_max) is False


def test_xl_dog_cannot_go_in_small_kennel():
    assert validate_size_class("XL", "S") is False


def test_xs_dog_fits_in_xl_kennel():
    assert validate_size_class("XS", "XL") is True
