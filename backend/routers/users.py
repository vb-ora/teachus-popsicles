from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
import models
import auth as auth_utils

router = APIRouter(prefix="/api/users", tags=["users"])


class UserOut(BaseModel):
    id: int
    name: str
    username: str
    rolle: str
    stimme: Optional[str]

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    rolle: Optional[str] = None
    stimme: Optional[str] = None
    password: Optional[str] = None


@router.get("", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin),
):
    return db.query(models.User).all()


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")

    if data.name:
        user.name = data.name
    if data.rolle:
        user.rolle = data.rolle
    if data.stimme is not None:
        user.stimme = data.stimme or None
    if data.password:
        user.password_hash = auth_utils.hash_password(data.password)

    db.commit()
    return {"ok": True}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Eigenen Account nicht löschbar")
    db.delete(user)
    db.commit()
    return {"ok": True}
