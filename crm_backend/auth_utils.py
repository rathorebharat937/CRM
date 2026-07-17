from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

# passlib reads bcrypt.__about__.__version__; removed in bcrypt 4.1+
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type(
        "_About",
        (),
        {"__version__": getattr(bcrypt, "__version__", "4.2.0")},
    )()
from sqlalchemy.orm import Session

from config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from database import SessionLocal
from models import User
from permissions import role_has_permission

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "company_id": user.company_id,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is inactive")

    token_company_id = payload.get("company_id")
    if token_company_id is not None and user.company_id != token_company_id:
        raise HTTPException(status_code=401, detail="Session expired — please sign in again")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_permission(permission_code: str):
    def _checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not role_has_permission(db, user.role, permission_code):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission_code}",
            )
        return user

    return _checker
