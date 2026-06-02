import os
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
import models
import auth as auth_utils
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVITE_CODE = os.getenv("INVITE_CODE", "")

STIMMEN = [
    "Sopran",
    "Mezzo",
    "Alt",
    "Tenor",
    "Bass",
]


class RegisterRequest(BaseModel):
    name: str
    username: str
    password: str
    rolle: str = "mitglied"
    stimme: Optional[str] = None
    invite_code: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if req.invite_code != INVITE_CODE:
        raise HTTPException(status_code=403, detail="Ungültiger Einladungscode")

    if req.rolle not in ("mitglied", "chorleiter"):
        req.rolle = "mitglied"

    if req.rolle == "mitglied" and not req.stimme:
        raise HTTPException(status_code=400, detail="Mitglieder müssen eine Stimme wählen")

    if req.rolle == "chorleiter":
        req.stimme = None

    if req.stimme and req.stimme not in STIMMEN:
        raise HTTPException(status_code=400, detail="Ungültige Stimme")

    existing = db.query(models.User).filter(models.User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Benutzername bereits vergeben")

    user = models.User(
        name=req.name,
        username=req.username,
        password_hash=auth_utils.hash_password(req.password),
        rolle=req.rolle,
        stimme=req.stimme,
    )
    db.add(user)
    db.flush()

    # Auto-favorites: alle Audios deren stimme zum User passt
    if req.stimme:
        matching_audios = db.query(models.Audio).filter(
            models.Audio.stimme == req.stimme
        ).all()
        for audio in matching_audios:
            fav = models.AudioFavorit(user_id=user.id, audio_id=audio.id)
            db.add(fav)

    db.commit()
    token = auth_utils.create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "rolle": user.rolle}


@router.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth_utils.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")

    token = auth_utils.create_access_token({"sub": user.username})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"access_token": token, "token_type": "bearer", "rolle": user.rolle, "name": user.name, "id": user.id}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@router.get("/me")
def me(current_user: models.User = Depends(auth_utils.get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "username": current_user.username,
        "rolle": current_user.rolle,
        "stimme": current_user.stimme,
    }
