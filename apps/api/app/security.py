from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import User

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

ROLES = {
    "SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS", "INVESTIGATOR", "REVIEWER",
    "APPEALS_OFFICER", "CENTRE_SUPERVISOR", "MARKER", "AUDITOR",
}


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user.id), "role": user.role, "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": "rwanda-examination-integrity", "type": "access",
    }, settings.jwt_secret, algorithm="HS256")


async def current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"],
            issuer="rwanda-examination-integrity",
            options={"require": ["sub", "exp", "iat", "iss", "type"]},
        )
        if payload.get("type") != "access":
            raise unauthorized
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError):
        raise unauthorized from None
    user = await session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permission for this operation")
        return user
    return dependency
