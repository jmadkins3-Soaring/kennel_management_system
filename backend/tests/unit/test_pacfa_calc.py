"""Unit tests: PACFA sqft calculation.

Spec §4.3 — Formula: (dog_length_inches + 6)^2 / 144
Size class lengths and resulting base sqft:
  XS: 12in → 2.25 sqft
  S:  18in → 4.00 sqft
  M:  24in → 6.25 sqft
  L:  30in → 9.00 sqft
  XL: 36in → 12.25 sqft

Stay duration multipliers:
  < 5 days:      1.0x
  5–30 days:     1.5x
  31–180 days:   2.0x
  181+ days:     3.0x (or 2.0x with confirmed daily qualifying activity)
"""

import pytest
from app.services.pacfa import required_sqft, combined_required_sqft


# ── Base sqft by size class (< 5 days, multiplier 1.0) ────────────────────────

@pytest.mark.parametrize("size_class,expected_sqft", [
    ("XS", 2.25),
    ("S",  4.00),
    ("M",  6.25),
    ("L",  9.00),
    ("XL", 12.25),
])
def test_base_sqft_by_size_class(size_class, expected_sqft):
    assert required_sqft(size_class, stay_days=3) == pytest.approx(expected_sqft, rel=1e-3)


# ── Multiplier boundaries ──────────────────────────────────────────────────────

@pytest.mark.parametrize("stay_days,multiplier", [
    (1,   1.0),
    (4,   1.0),
    (5,   1.5),
    (30,  1.5),
    (31,  2.0),
    (180, 2.0),
    (181, 3.0),
    (365, 3.0),
])
def test_multiplier_boundaries_medium_dog(stay_days, multiplier):
    base = 6.25  # M size class
    expected = base * multiplier
    result = required_sqft("M", stay_days=stay_days)
    assert result == pytest.approx(expected, rel=1e-3)


# ── 181+ day exception ─────────────────────────────────────────────────────────

def test_181_day_with_daily_qualifying_activity_uses_2x():
    """If every day has a confirmed Nature Walk or Play Yard, 2.0x applies instead of 3.0x."""
    base = 6.25
    result = required_sqft("M", stay_days=181, has_daily_qualifying_activity=True)
    assert result == pytest.approx(base * 2.0, rel=1e-3)


def test_181_day_without_qualifying_activity_uses_3x():
    """Without confirmed daily activity, full 3.0x applies."""
    base = 6.25
    result = required_sqft("M", stay_days=181, has_daily_qualifying_activity=False)
    assert result == pytest.approx(base * 3.0, rel=1e-3)


def test_180_day_is_not_181_exception():
    """Stay of exactly 180 days uses 2.0x regardless of activity."""
    base = 6.25
    assert required_sqft("M", stay_days=180) == pytest.approx(base * 2.0, rel=1e-3)


# ── All size classes at each multiplier bracket ────────────────────────────────

@pytest.mark.parametrize("size_class,base,stay_days,multiplier", [
    ("XS", 2.25,  3,  1.0),
    ("XS", 2.25,  5,  1.5),
    ("XS", 2.25,  31, 2.0),
    ("XS", 2.25,  181, 3.0),
    ("S",  4.00,  3,  1.0),
    ("S",  4.00,  5,  1.5),
    ("S",  4.00,  31, 2.0),
    ("S",  4.00,  181, 3.0),
    ("M",  6.25,  3,  1.0),
    ("M",  6.25,  5,  1.5),
    ("M",  6.25,  31, 2.0),
    ("M",  6.25,  181, 3.0),
    ("L",  9.00,  3,  1.0),
    ("L",  9.00,  5,  1.5),
    ("L",  9.00,  31, 2.0),
    ("L",  9.00,  181, 3.0),
    ("XL", 12.25, 3,  1.0),
    ("XL", 12.25, 5,  1.5),
    ("XL", 12.25, 31, 2.0),
    ("XL", 12.25, 181, 3.0),
])
def test_all_size_class_multiplier_combinations(size_class, base, stay_days, multiplier):
    assert required_sqft(size_class, stay_days=stay_days) == pytest.approx(base * multiplier, rel=1e-3)


# ── Multi-dog combined sqft ────────────────────────────────────────────────────

def test_two_dogs_combined_sqft():
    """Combined sqft is sum of each dog's individual required sqft."""
    dogs = [{"size_class": "M"}, {"size_class": "S"}]
    combined = combined_required_sqft(dogs, stay_days=3)
    assert combined == pytest.approx(6.25 + 4.00, rel=1e-3)


def test_three_dogs_combined_sqft():
    dogs = [{"size_class": "S"}, {"size_class": "S"}, {"size_class": "XS"}]
    combined = combined_required_sqft(dogs, stay_days=10)  # 1.5x bracket
    expected = (4.00 * 1.5) + (4.00 * 1.5) + (2.25 * 1.5)
    assert combined == pytest.approx(expected, rel=1e-3)


def test_multi_dog_181_exception_all_dogs_benefit():
    """181+ exception applies to each dog in the combined calculation."""
    dogs = [{"size_class": "M"}, {"size_class": "L"}]
    with_exception = combined_required_sqft(dogs, stay_days=200, has_daily_qualifying_activity=True)
    without_exception = combined_required_sqft(dogs, stay_days=200, has_daily_qualifying_activity=False)
    assert with_exception < without_exception
    assert with_exception == pytest.approx((6.25 + 9.00) * 2.0, rel=1e-3)
    assert without_exception == pytest.approx((6.25 + 9.00) * 3.0, rel=1e-3)


def test_invalid_size_class_raises():
    with pytest.raises((ValueError, KeyError)):
        required_sqft("XXL", stay_days=3)
