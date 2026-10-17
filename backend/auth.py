import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _get_token(
    token_header: Optional[str] = Depends(oauth2_scheme),
    token_cookie: Optional[str] = Cookie(default=None, alias="access_token"),
) -> Optional[str]:
    return token_header or token_cookie


def get_current_user(
    token: Optional[str] = Depends(_get_token),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nicht authentifiziert",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# Rollen (von oben nach unten): superadmin > admin > chorleiter / mitglied
ROLLE_SUPERADMIN = "superadmin"
ADMIN_ROLLEN = ("superadmin", "admin")
VERWALTUNGS_ROLLEN = ("superadmin", "admin", "chorleiter")
# Rollen, die singen und in der Stimmmatrix als Sänger geführt werden
SAENGER_ROLLEN = ("superadmin", "admin", "mitglied")
# Rollen, die vergeben werden dürfen – superadmin nie
VERGEBBARE_ROLLEN = ("mitglied", "chorleiter", "admin")


def require_superadmin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.rolle != ROLLE_SUPERADMIN:
        raise HTTPException(status_code=403, detail="Nur für Superadmin")
    return current_user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.rolle not in ADMIN_ROLLEN:
        raise HTTPException(status_code=403, detail="Nur Admins erlaubt")
    return current_user


def require_admin_or_chorleiter(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.rolle not in VERWALTUNGS_ROLLEN:
        raise HTTPException(status_code=403, detail="Nur Admins und Chorleiter erlaubt")
    return current_user
