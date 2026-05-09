"""Dog CRUD routes."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.dog import Dog, DogCreate, DogRead, DogUpdate, VaccinationRecord
from ..models.incident import Incident

router = APIRouter(prefix="/api/dogs", tags=["dogs"])


async def _compute_open_incidents(session: AsyncSession, dog_id: str) -> bool:
    """Return True if the dog has any unresolved incidents."""
    result = await session.exec(
        select(Incident).where(
            Incident.dog_id == dog_id,
            Incident.resolved == False,
        )
    )
    return result.first() is not None


async def _dog_read(session: AsyncSession, dog: Dog) -> DogRead:
    """Build a DogRead with computed open_incidents."""
    has_open = await _compute_open_incidents(session, dog.dog_id)
    read = DogRead.model_validate(dog)
    read.open_incidents = has_open
    return read


@router.get("", response_model=List[DogRead], summary="List or search dogs")
async def list_dogs(
    q: Optional[str] = None,
    owner_id: Optional[str] = None,
    archived: bool = False,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Search dogs by name, breed, or owner. Returns open_incidents computed flag."""
    stmt = select(Dog).where(Dog.archived == archived)
    if owner_id:
        stmt = stmt.where(Dog.owner_id == owner_id)
    if q:
        stmt = stmt.where(
            Dog.name.ilike(f"%{q}%") | Dog.breed.ilike(f"%{q}%")
        )
    result = await session.exec(stmt)
    dogs = result.all()
    return [await _dog_read(session, dog) for dog in dogs]


@router.post("", response_model=DogRead, status_code=201, summary="Create dog")
async def create_dog(
    body: DogCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new dog linked to an owner."""
    data = body.model_dump(mode="json")
    dog = Dog.model_validate(data)
    session.add(dog)
    await session.commit()
    await session.refresh(dog)
    return await _dog_read(session, dog)


@router.get("/{dog_id}", response_model=DogRead, summary="Get dog by ID")
async def get_dog(
    dog_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve a single dog profile including vaccination_records and computed open_incidents."""
    dog = await session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    return await _dog_read(session, dog)


@router.put("/{dog_id}", response_model=DogRead, summary="Update dog")
async def update_dog(
    dog_id: str,
    body: DogUpdate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update mutable dog fields."""
    dog = await session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    update_data = body.model_dump(exclude_unset=True, mode="json")
    for field, value in update_data.items():
        setattr(dog, field, value)
    if "vaccination_records" in update_data:
        flag_modified(dog, "vaccination_records")
    dog.updated_at = datetime.now(timezone.utc)
    session.add(dog)
    await session.commit()
    await session.refresh(dog)
    return await _dog_read(session, dog)


@router.delete("/{dog_id}", status_code=204, summary="Archive dog (soft delete)")
async def archive_dog(
    dog_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete dog by setting archived=true."""
    dog = await session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    dog.archived = True
    dog.updated_at = datetime.now(timezone.utc)
    session.add(dog)
    await session.commit()


@router.post("/{dog_id}/vaccinations", response_model=DogRead, summary="Add vaccination record")
async def add_vaccination(
    dog_id: str,
    body: VaccinationRecord,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Append a vaccination record to the dog's vaccination_records JSON array."""
    dog = await session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    existing = dog.vaccination_records or []
    existing.append(body.model_dump(mode="json"))
    dog.vaccination_records = existing
    flag_modified(dog, "vaccination_records")
    dog.updated_at = datetime.now(timezone.utc)
    session.add(dog)
    await session.commit()
    await session.refresh(dog)
    return await _dog_read(session, dog)


@router.put("/{dog_id}/vaccinations/{vacc_index}", response_model=DogRead, summary="Update vaccination record")
async def update_vaccination(
    dog_id: str,
    vacc_index: int,
    body: VaccinationRecord,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a vaccination record by index in the JSON array."""
    dog = await session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    records = dog.vaccination_records or []
    if vacc_index < 0 or vacc_index >= len(records):
        raise HTTPException(status_code=404, detail="Vaccination record index out of range")
    records[vacc_index] = body.model_dump(mode="json")
    dog.vaccination_records = records
    flag_modified(dog, "vaccination_records")
    dog.updated_at = datetime.now(timezone.utc)
    session.add(dog)
    await session.commit()
    await session.refresh(dog)
    return await _dog_read(session, dog)
