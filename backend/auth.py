"""Authentication — JWT + Google OAuth."""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from models import User, UserProfile, init_db

SECRET_KEY = os.environ.get("MK_SECRET_KEY", "monkeyking-secret-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
SessionLocal = init_db()


class TokenData(BaseModel):
    user_id: int
    email: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user.id), "email": user.email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", 0))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def register_user(db: Session, req: RegisterRequest) -> User:
    existing = db.query(User).filter_by(email=req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        name=req.name,
        auth_provider="local",
    )
    db.add(user)
    db.flush()
    # Only create profile if one doesn't exist
    existing_profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not existing_profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, req: LoginRequest) -> tuple[User, str]:
    user = db.query(User).filter_by(email=req.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user)
    return user, token


def google_login_or_register(db: Session, google_user: dict) -> tuple[User, str]:
    """Handle Google OAuth callback — login or auto-register."""
    email = google_user["email"]
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            name=google_user.get("name", email.split("@")[0]),
            auth_provider="google",
            google_id=google_user.get("sub", ""),
            avatar_url=google_user.get("picture", ""),
        )
        db.add(user)
        db.flush()
        existing_profile = db.query(UserProfile).filter_by(user_id=user.id).first()
        if not existing_profile:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
        db.commit()
        db.refresh(user)
    token = create_token(user)
    return user, token
