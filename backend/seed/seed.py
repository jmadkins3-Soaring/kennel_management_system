"""First-run seed data. Runs only when the database is empty.

Seeds:
  - One placeholder Owner (is_seed flagged via notes field)
  - One placeholder Dog linked to that Owner
  - Initial activity types per Spec §5.9
  - K-01 kennel provisioned from kennels.json (rest auto-provisioned on startup)
"""

import uuid
from datetime import datetime, timezone

SEED_ACTIVITY_TYPES = [
    {"name": "Nature Walk",               "qualifies_for_pacfa_exception": True},
    {"name": "Playtime",                  "qualifies_for_pacfa_exception": False},
    {"name": "Medication Administration", "qualifies_for_pacfa_exception": False},
    {"name": "Emergency Grooming",        "qualifies_for_pacfa_exception": False},
    {"name": "Play Yard",                 "qualifies_for_pacfa_exception": True},
]


async def run_seed(session) -> None:
    """Insert seed data if database is empty. Idempotent."""
    from sqlmodel import select
    from ..app.models.owner import Owner
    from ..app.models.dog import Dog, SizeClass, MedicalStatus
    from ..app.models.activity_type import ActivityType

    # Seed activity types
    for at in SEED_ACTIVITY_TYPES:
        existing = await session.exec(select(ActivityType).where(ActivityType.name == at["name"]))
        if not existing.first():
            session.add(ActivityType(
                activity_type_id=str(uuid.uuid4()),
                name=at["name"],
                qualifies_for_pacfa_exception=at["qualifies_for_pacfa_exception"],
            ))

    # Seed placeholder owner and dog only on truly empty DB
    owner_count = await session.exec(select(Owner))
    if not owner_count.first():
        owner_id = str(uuid.uuid4())
        session.add(Owner(
            owner_id=owner_id,
            first_name="Seed",
            last_name="Record",
            phone_number="000-000-0000",
            email="seed@soaringheightskennel.com",
            notes="[SEED RECORD - safe to delete]",
        ))
        session.add(Dog(
            dog_id=str(uuid.uuid4()),
            owner_id=owner_id,
            name="Seed Dog",
            breed="Mixed",
            size_class=SizeClass.M,
            medical_status=MedicalStatus.HEALTHY,
            notes="[SEED RECORD - safe to delete]",
        ))

    await session.commit()
