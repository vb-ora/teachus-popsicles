"""Benutzerverwaltung – ausschließlich für die Rolle superadmin."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth as auth_utils
import models
from database import get_db
from stimmen import USER_STIMMEN

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


class UserCreate(BaseModel):
    name: str
    username: str
    password: str
    rolle: str
    stimme: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    rolle: Optional[str] = None
    stimme: Optional[str] = None


def _user_dict(u: models.User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "username": u.username,
        "rolle": u.rolle,
        "stimme": u.stimme,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _get_user_or_404(db: Session, user_id: int) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    return user


def _pruefe_rolle(rolle: str):
    if rolle == auth_utils.ROLLE_SUPERADMIN:
        raise HTTPException(status_code=403, detail="Die Rolle superadmin kann nicht vergeben werden")
    if rolle not in auth_utils.VERGEBBARE_ROLLEN:
        raise HTTPException(status_code=400, detail="Ungültige Rolle")


def _stimme_fuer_rolle(rolle: str, stimme: Optional[str]) -> Optional[str]:
    """Chorleiter haben keine Stimme, alle anderen Rollen brauchen eine."""
    if rolle == "chorleiter":
        return None
    if not stimme:
        raise HTTPException(status_code=400, detail="Sänger (Superadmin, Admin, Mitglied) brauchen eine Stimme")
    if stimme not in USER_STIMMEN:
        raise HTTPException(status_code=400, detail="Ungültige Stimme")
    return stimme


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_superadmin),
):
    users = db.query(models.User).order_by(models.User.name).all()
    return [_user_dict(u) for u in users]


@router.post("/users", status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_superadmin),
):
    name, username = data.name.strip(), data.username.strip()
    if not name or not username or not data.password:
        raise HTTPException(status_code=400, detail="Name, Benutzername und Passwort sind Pflicht")
    _pruefe_rolle(data.rolle)
    stimme = _stimme_fuer_rolle(data.rolle, data.stimme)
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Benutzername bereits vergeben")

    user = models.User(
        name=name,
        username=username,
        password_hash=auth_utils.hash_password(data.password),
        rolle=data.rolle,
        stimme=stimme,
    )
    db.add(user)
    db.flush()

    # Wie bei der Registrierung: passende Audios automatisch als Favorit
    if stimme:
        for audio in db.query(models.Audio).filter(models.Audio.stimme == stimme).all():
            db.add(models.AudioFavorit(user_id=user.id, audio_id=audio.id))

    db.commit()
    db.refresh(user)
    return _user_dict(user)


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_superadmin),
):
    user = _get_user_or_404(db, user_id)

    rolle = user.rolle
    if data.rolle is not None and data.rolle != user.rolle:
        if user.rolle == auth_utils.ROLLE_SUPERADMIN:
            raise HTTPException(status_code=403, detail="Die Rolle superadmin kann nicht geändert werden")
        _pruefe_rolle(data.rolle)
        rolle = data.rolle

    stimme = data.stimme if data.stimme is not None else user.stimme
    user.stimme = _stimme_fuer_rolle(rolle, stimme)
    user.rolle = rolle

    if data.name is not None:
        if not data.name.strip():
            raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
        user.name = data.name.strip()
    if data.password:
        user.password_hash = auth_utils.hash_password(data.password)

    db.commit()
    return _user_dict(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_superadmin),
):
    user = _get_user_or_404(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Eigenen Account nicht löschbar")
    if user.rolle == auth_utils.ROLLE_SUPERADMIN:
        raise HTTPException(status_code=403, detail="Superadmin kann nicht gelöscht werden")

    # Persönliches löschen; für alle sichtbare Inhalte (Kapitel, öffentliche
    # Markierungen) an den löschenden Superadmin übertragen, damit sie erhalten bleiben.
    for model in (models.StueckFavorit, models.AudioFavorit, models.UserStueckStimme, models.AuftrittSaenger):
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    db.query(models.Markierung).filter(
        models.Markierung.user_id == user.id, models.Markierung.ist_oeffentlich.is_(False)
    ).delete(synchronize_session=False)
    db.query(models.Markierung).filter(models.Markierung.user_id == user.id).update(
        {"user_id": current_user.id}, synchronize_session=False
    )
    db.query(models.Kapitel).filter(models.Kapitel.user_id == user.id).update(
        {"user_id": current_user.id}, synchronize_session=False
    )
    db.expire(user)
    db.delete(user)
    db.commit()
    return {"ok": True}
