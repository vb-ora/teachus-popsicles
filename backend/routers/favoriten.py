from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import auth as auth_utils

router = APIRouter(prefix="/api/favoriten", tags=["favoriten"])


@router.post("/stueck/{stueck_id}")
def toggle_stueck_favorit(
    stueck_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")

    existing = db.query(models.StueckFavorit).filter(
        models.StueckFavorit.user_id == current_user.id,
        models.StueckFavorit.stueck_id == stueck_id,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"is_favorit": False}
    else:
        fav = models.StueckFavorit(user_id=current_user.id, stueck_id=stueck_id)
        db.add(fav)
        db.commit()
        return {"is_favorit": True}


@router.post("/audio/{audio_id}")
def toggle_audio_favorit(
    audio_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden")

    existing = db.query(models.AudioFavorit).filter(
        models.AudioFavorit.user_id == current_user.id,
        models.AudioFavorit.audio_id == audio_id,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"is_favorit": False}
    else:
        fav = models.AudioFavorit(user_id=current_user.id, audio_id=audio_id)
        db.add(fav)
        db.commit()
        return {"is_favorit": True}
