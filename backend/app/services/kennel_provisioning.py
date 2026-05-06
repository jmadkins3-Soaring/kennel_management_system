"""Kennel provisioning helpers — number generation and deactivation guard."""


def compute_next_kennel_number(existing_numbers: list[str]) -> str:
    """Return next sequential kennel number given existing ones (e.g. 'K-01', 'K-02')."""
    if not existing_numbers:
        return "K-01"
    max_n = max(int(n.split("-")[1]) for n in existing_numbers if "-" in n)
    return f"K-{max_n + 1:02d}"


def natural_sort_kennel_numbers(numbers: list[str]) -> list[str]:
    """Sort kennel numbers naturally (K-02 before K-10)."""
    return sorted(numbers, key=lambda n: int(n.split("-")[1]) if "-" in n else 0)


def assert_no_future_reservations(kennel_id: str, future_reservations: list[dict]) -> None:
    """Raise ValueError if kennel has any future reservations."""
    if future_reservations:
        raise ValueError(
            f"Kennel {kennel_id} has future reservations and cannot be deactivated"
        )
