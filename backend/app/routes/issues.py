"""Issue report routes (kennel maintenance/safety)."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_session
from ..auth import get_current_user
from ..models.issue import Issue, IssueCreate, IssueRead, ResolveIssueRequest

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("", response_model=List[IssueRead], summary="List issue reports")
async def list_issues(
    kennel_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[IssueRead]:
    """Filter issues by kennel or resolution status."""
    query = select(Issue)

    if kennel_id is not None:
        query = query.where(Issue.kennel_id == kennel_id)

    if resolved is not None:
        query = query.where(Issue.resolved == resolved)

    issues = (await session.exec(query)).all()
    return [IssueRead.model_validate(i) for i in issues]


@router.post("", response_model=IssueRead, status_code=201, summary="Create issue report")
async def create_issue(
    body: IssueCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IssueRead:
    """File a new kennel issue. reported_by from JWT. Does not auto-change kennel status."""
    issue = Issue(**body.model_dump(), reported_by=username)
    session.add(issue)
    await session.commit()
    await session.refresh(issue)
    return IssueRead.model_validate(issue)


@router.get("/{issue_id}", response_model=IssueRead, summary="Get issue by ID")
async def get_issue(
    issue_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IssueRead:
    """Retrieve a single issue report."""
    issue = await session.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueRead.model_validate(issue)


@router.post("/{issue_id}/resolve", response_model=IssueRead, summary="Resolve issue")
async def resolve_issue(
    issue_id: str,
    body: ResolveIssueRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IssueRead:
    """Mark issue resolved. Records resolved_datetime and resolved_by."""
    issue = await session.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue.resolved = True
    issue.resolved_datetime = datetime.now(timezone.utc)
    issue.resolved_by = username

    session.add(issue)
    await session.commit()
    await session.refresh(issue)
    return IssueRead.model_validate(issue)
