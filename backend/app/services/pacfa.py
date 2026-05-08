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

from ..config import get_pacfa
from .phase import get_pacfa_multiplier

SIZE_CLASS_ORDER = ["XS", "S", "M", "L", "XL"]


def _size_classes() -> dict:
    return get_pacfa()["size_classes"]


def required_sqft(size_class: str, stay_days: int, has_daily_qualifying_activity: bool = False) -> float:
    """Return required sqft for a dog given its size class and stay duration."""
    if stay_days <= 0:
        raise ValueError(f"stay_days must be a positive integer, got {stay_days}")
    size_classes = _size_classes()
    if size_class not in size_classes:
        raise ValueError(f"Unknown size class: {size_class!r}. Must be one of {SIZE_CLASS_ORDER}.")
    base = size_classes[size_class]["base_sqft"]
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
