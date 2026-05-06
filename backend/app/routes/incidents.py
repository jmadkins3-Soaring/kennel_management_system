"""Incident report routes."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_session
from ..auth import get_current_user
from ..models.incident import Incident, IncidentCreate, IncidentRead, ResolveIncidentRequest

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=List[IncidentRead], summary="List incident reports")
async def list_incidents(
    dog_id: Optional[str] = None,
    reservation_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[IncidentRead]:
    """Filter incidents by dog, reservation, or resolution status."""
    query = select(Incident)

    if dog_id is not None:
        query = query.where(Incident.dog_id == dog_id)

    if reservation_id is not None:
        query = query.where(Incident.reservation_id == reservation_id)

    if resolved is not None:
        query = query.where(Incident.resolved == resolved)

    incidents = (await session.exec(query)).all()
    return [IncidentRead.model_validate(i) for i in incidents]


@router.post("", response_model=IncidentRead, status_code=201, summary="Create incident report")
async def create_incident(
    body: IncidentCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IncidentRead:
    """File a new incident. Sets reported_by from JWT."""
    incident = Incident(**body.model_dump(), reported_by=username)
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return IncidentRead.model_validate(incident)


@router.get("/{incident_id}", response_model=IncidentRead, summary="Get incident by ID")
async def get_incident(
    incident_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IncidentRead:
    """Retrieve a single incident report."""
    incident = await session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentRead.model_validate(incident)


@router.post("/{incident_id}/resolve", response_model=IncidentRead, summary="Resolve incident")
async def resolve_incident(
    incident_id: str,
    body: ResolveIncidentRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IncidentRead:
    """Mark incident resolved. Records resolved_datetime and resolved_by."""
    incident = await session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.resolved = True
    incident.resolved_datetime = datetime.now(timezone.utc)
    incident.resolved_by = username

    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return IncidentRead.model_validate(incident)
