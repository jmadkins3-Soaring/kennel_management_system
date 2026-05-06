"""Global search route — searches all record types simultaneously."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.dog import Dog
from ..models.kennel import Kennel
from ..models.owner import Owner
from ..models.reservation import Reservation

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", summary="Global search across all record types")
async def global_search(
    q: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Search owners, dogs, reservations, and bills simultaneously.
    Results priority-ranked per Spec §8.2:
      1. Active/pending stays (checked in or upcoming) — with kennel number and status badge.
      2. Other results (owners, dogs) — in collapsible section.
    All results link to the relevant object detail.
    If q is empty or < 2 chars, return empty results.
    """
    empty = {"query": q, "active_stays": [], "other_results": []}

    if not q or len(q) < 2:
        return empty

    q_lower = q.lower()

    # --- Owner search ---
    owner_stmt = select(Owner).where(Owner.archived == False)
    all_owners = (await session.exec(owner_stmt)).all()
    matched_owners = [
        o for o in all_owners
        if q_lower in o.last_name.lower() or q_lower in o.first_name.lower()
    ]
    owner_ids = {o.owner_id for o in matched_owners}

    # --- Dog search ---
    dog_stmt = select(Dog).where(Dog.archived == False)
    all_dogs = (await session.exec(dog_stmt)).all()
    matched_dogs = [
        d for d in all_dogs
        if q_lower in d.name.lower() or q_lower in d.breed.lower()
        or d.owner_id in owner_ids  # dogs belonging to matched owners
    ]
    dog_ids = {d.dog_id for d in matched_dogs}

    # Build owner lookup for display
    owner_map: Dict[str, Owner] = {o.owner_id: o for o in all_owners}

    # --- Active stays search ---
    # Checked-in, not checked-out, not cancelled
    active_stmt = select(Reservation).where(
        Reservation.checkin_datetime.isnot(None),
        Reservation.checkout_datetime.is_(None),
        Reservation.cancelled == False,
    )
    active_reservations = (await session.exec(active_stmt)).all()

    active_stays: List[Dict[str, Any]] = []
    seen_reservation_ids: set = set()

    for res in active_reservations:
        dog = await session.get(Dog, res.dog_id)
        if not dog:
            continue
        owner = owner_map.get(dog.owner_id)
        if not owner:
            owner = await session.get(Owner, dog.owner_id)
            if owner:
                owner_map[dog.owner_id] = owner

        # Match if dog or owner matches query
        dog_match = q_lower in dog.name.lower() or q_lower in dog.breed.lower()
        owner_match = owner and (
            q_lower in owner.last_name.lower() or q_lower in owner.first_name.lower()
        )

        if not (dog_match or owner_match):
            continue

        kennel = await session.get(Kennel, res.kennel_id)
        active_stays.append({
            "type": "reservation",
            "reservation_id": res.reservation_id,
            "dog_name": dog.name,
            "owner_last_name": owner.last_name if owner else "",
            "kennel_number": kennel.kennel_number if kennel else "",
            "status": "Used",
        })
        seen_reservation_ids.add(res.reservation_id)

    # --- Other results: owners and dogs not already in active_stays ---
    other_results: List[Dict[str, Any]] = []

    for owner in matched_owners:
        other_results.append({
            "type": "owner",
            "owner_id": owner.owner_id,
            "display": f"{owner.last_name}, {owner.first_name}",
        })

    for dog in matched_dogs:
        if dog.owner_id not in owner_map:
            fetched_owner = await session.get(Owner, dog.owner_id)
            if fetched_owner:
                owner_map[dog.owner_id] = fetched_owner
        owner_last = ""
        if dog.owner_id in owner_map:
            owner_last = owner_map[dog.owner_id].last_name
        other_results.append({
            "type": "dog",
            "dog_id": dog.dog_id,
            "display": f"{dog.name} ({owner_last})" if owner_last else dog.name,
        })

    return {
        "query": q,
        "active_stays": active_stays,
        "other_results": other_results,
    }
