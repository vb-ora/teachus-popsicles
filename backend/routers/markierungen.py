from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from database import get_db
import models
import auth as auth_utils

router = APIRouter(prefix="/api/markierungen", tags=["markierungen"])


class MarkierungCreate(BaseModel):
    audio_id: int
    name: str
    start_sekunden: float
    ende_sekunden: float
    ist_oeffentlich: bool = False
    notiz: Optional[str] = None


@router.post("", status_code=201)
def create_markierung(
    data: MarkierungCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    # Mitglieder dürfen nur private Markierungen anlegen
    if current_user.rolle == "mitglied" and data.ist_oeffentlich:
        raise HTTPException(status_code=403, detail="Mitglieder dürfen nur private Markierungen anlegen")

    audio = db.query(models.Audio).filter(models.Audio.id == data.audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden")

    m = models.Markierung(
        audio_id=data.audio_id,
        user_id=current_user.id,
        name=data.name,
        start_sekunden=data.start_sekunden,
        ende_sekunden=data.ende_sekunden,
        ist_oeffentlich=data.ist_oeffentlich,
        notiz=data.notiz,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {
        "id": m.id,
        "name": m.name,
        "start_sekunden": m.start_sekunden,
        "ende_sekunden": m.ende_sekunden,
        "ist_oeffentlich": m.ist_oeffentlich,
        "notiz": m.notiz,
        "ist_eigen": True,
    }


@router.delete("/{markierung_id}")
def delete_markierung(
    markierung_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    m = db.query(models.Markierung).filter(models.Markierung.id == markierung_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Markierung nicht gefunden")

    if m.user_id != current_user.id and current_user.rolle not in ("admin", "chorleiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    db.delete(m)
    db.commit()
    return {"ok": True}
