"""PACFA compliance calculation service.

Formula: (dog_length_inches + 6)^2 / 144 = required_sqft
Multipliers applied per stay duration (Spec §4.3).

Hard rules (no override):
  - Individual dog required_sqft must not exceed kennel sqft
  - Combined multi-dog sqft must not exceed kennel sqft
  - Size class hierarchy: XS < S < M < L < XL — dog must not exceed kennel max_size_class

181+ day exception: 2.0x applies instead of 3.0x IF a qualifying activity
(Nature Walk or Play Yard) is confirmed for EVERY day of the stay.
If any day missing, 3.0x applies for the ENTIRE stay.
"""

from typing import List

from .phase import get_pacfa_multiplier

# Implemented by Agent B (PACFA & Phase Engine stream)

SIZE_CLASS_ORDER = ["XS", "S", "M", "L", "XL"]

SIZE_CLASSES = {
    "XS": {"est_length_in": 12, "base_sqft": 2.25},
    "S":  {"est_length_in": 18, "base_sqft": 4.00},
    "M":  {"est_length_in": 24, "base_sqft": 6.25},
    "L":  {"est_length_in": 30, "base_sqft": 9.00},
    "XL": {"est_length_in": 36, "base_sqft": 12.25},
}


def required_sqft(size_class: str, stay_days: int, has_daily_qualifying_activity: bool = False) -> float:
    """Return required sqft for a dog given its size class and stay duration."""
    if stay_days <= 0:
        raise ValueError(f"stay_days must be a positive integer, got {stay_days}")
    if size_class not in SIZE_CLASSES:
        raise ValueError(f"Unknown size class: {size_class!r}. Must be one of {SIZE_CLASS_ORDER}.")
    base = SIZE_CLASSES[size_class]["base_sqft"]
    multiplier = get_pacfa_multiplier(stay_days, has_daily_qualifying_activity)
    return base * multiplier


def combined_required_sqft(dogs: List[dict], stay_days: int, has_daily_qualifying_activity: bool = False) -> float:
    """Return combined required sqft for multiple dogs sharing a kennel."""
    return sum(required_sqft(dog["size_class"], stay_days, has_daily_qualifying_activity) for dog in dogs)


def validate_size_class(dog_size_class: str, kennel_max_size_class: str) -> bool:
    """Return True if dog size class does not exceed kennel max_size_class."""
    return SIZE_CLASS_ORDER.index(dog_size_class) <= SIZE_CLASS_ORDER.index(kennel_max_size_class)


def validate_pacfa_single(dog_size_class: str, stay_days: int, kennel_sqft: float,
                           has_daily_qualifying_activity: bool = False) -> tuple[bool, float, float]:
    """Return (passes, required_sqft, kennel_sqft). Hard block if not passes."""
    req = required_sqft(dog_size_class, stay_days, has_daily_qualifying_activity)
    passes = req <= kennel_sqft
    return (passes, req, kennel_sqft)


def validate_pacfa_multi(dogs: List[dict], stay_days: int, kennel_sqft: float,
                          has_daily_qualifying_activity: bool = False) -> tuple[bool, float, float]:
    """Return (passes, combined_required_sqft, kennel_sqft) for multi-dog kennel."""
    combined = combined_required_sqft(dogs, stay_days, has_daily_qualifying_activity)
    passes = combined <= kennel_sqft
    return (passes, combined, kennel_sqft)
