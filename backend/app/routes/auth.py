"""Staff authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..database import get_session
from ..auth import verify_password, create_access_token
from ..models.staff_user import StaffUser

router = APIRouter(prefix="/api/auth", tags=["auth"])
_limiter = Limiter(key_func=get_remote_address)


@router.post("/login", summary="Obtain a JWT access token")
@_limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """Authenticate staff user and return bearer token. Token valid for 8 hours."""
    result = await session.exec(
        select(StaffUser).where(StaffUser.username == form_data.username, StaffUser.active == True)
    )
    user = result.first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username)
    return {"access_token": token, "token_type": "bearer"}
