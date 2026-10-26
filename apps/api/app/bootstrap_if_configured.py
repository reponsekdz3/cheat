"""Create the first privileged account only with explicit bootstrap credentials."""
import asyncio
import os

from sqlalchemy import select

from app.database import SessionLocal
from app.models import AuditHead, User
from app.security import hash_password


async def main() -> None:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email and not password:
        return
    if not email or len(password) < 16:
        raise SystemExit("Bootstrap requires an email and a password of at least 16 characters")
    async with SessionLocal() as session:
        existing = await session.scalar(select(User.id).where(User.role == "SUPER_ADMIN").limit(1))
        if existing:
            return
        session.add(User(email=email, full_name="Initial System Administrator", password_hash=hash_password(password), role="SUPER_ADMIN"))
        if await session.get(AuditHead, 1) is None:
            session.add(AuditHead(id=1, head_hash="0" * 64))
        await session.commit()
    print("Initial administrator created using explicit bootstrap credentials.")


if __name__ == "__main__":
    asyncio.run(main())
