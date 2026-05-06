"""Owner CRUD routes."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.dog import Dog, DogRead
from ..models.incident import Incident
from ..models.owner import Owner, OwnerCreate, OwnerRead, OwnerUpdate

router = APIRouter(prefix="/api/owners", tags=["owners"])


@router.get("", response_model=List[OwnerRead], summary="List or search owners")
async def list_owners(
    q: Optional[str] = None,
    archived: bool = False,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Search owners by last name or partial name. Excludes archived by default."""
    stmt = select(Owner).where(Owner.archived == archived)
    if q:
        stmt = stmt.where(Owner.last_name.ilike(f"%{q}%"))
    result = await session.exec(stmt)
    return result.all()


@router.post("", response_model=OwnerRead, status_code=201, summary="Create owner")
async def create_owner(
    body: OwnerCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new owner record."""
    owner = Owner.model_validate(body)
    session.add(owner)
    await session.commit()
    await session.refresh(owner)
    return owner


@router.get("/{owner_id}", response_model=OwnerRead, summary="Get owner by ID")
async def get_owner(
    owner_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve a single owner with all fields."""
    owner = await session.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return owner


@router.put("/{owner_id}", response_model=OwnerRead, summary="Update owner")
async def update_owner(
    owner_id: str,
    body: OwnerUpdate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update mutable owner fields. updated_at is set automatically."""
    owner = await session.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(owner, field, value)
    owner.updated_at = datetime.now(timezone.utc)
    session.add(owner)
    await session.commit()
    await session.refresh(owner)
    return owner


@router.delete("/{owner_id}", status_code=204, summary="Archive owner (soft delete)")
async def archive_owner(
    owner_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete owner by setting archived=true."""
    owner = await session.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    owner.archived = True
    owner.updated_at = datetime.now(timezone.utc)
    session.add(owner)
    await session.commit()


@router.get("/{owner_id}/dogs", response_model=List[DogRead], summary="List owner's dogs")
async def list_owner_dogs(
    owner_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return all non-archived dogs for an owner, with computed open_incidents flag."""
    owner = await session.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    result = await session.exec(
        select(Dog).where(Dog.owner_id == owner_id, Dog.archived == False)
    )
    dogs = result.all()

    dog_reads = []
    for dog in dogs:
        incidents = await session.exec(
            select(Incident).where(
                Incident.dog_id == dog.dog_id,
                Incident.resolved == False,
            )
        )
        has_open = incidents.first() is not None
        read = DogRead.model_validate(dog)
        read.open_incidents = has_open
        dog_reads.append(read)

    return dog_reads
