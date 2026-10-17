import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import models
import auth as auth_utils

router = APIRouter(prefix="/api/audios", tags=["audios"])

UPLOAD_DIR = "/data/uploads"
ALLOWED_EXTENSIONS = {".mp3", ".aac", ".m4a", ".wav"}
STIMMEN_ALLE = [
    "Sopran", "Sopran 1", "Sopran 2",
    "Mezzo", "Mezzo 1", "Mezzo 2",
    "Alt", "Alt 1", "Alt 2",
    "Tenor", "Tenor 1", "Tenor 2",
    "Bass", "Bass 1", "Bass 2",
    "Männer",
    "Alle",
]


def _stimme_matches(user_stimme: str, audio_stimme: str) -> bool:
    """Check if user stimme matches audio stimme (case-insensitive)."""
    return user_stimme.lower() == audio_stimme.lower()


def _auto_favorites_for_audio(db: Session, audio: models.Audio):
    """Create audio_favoriten entries for all matching singers."""
    users = db.query(models.User).filter(models.User.rolle.in_(auth_utils.SAENGER_ROLLEN)).all()
    for user in users:
        # Check stück-spezifischen Eintrag
        stueck_stimme = db.query(models.UserStueckStimme).filter(
            models.UserStueckStimme.user_id == user.id,
            models.UserStueckStimme.stueck_id == audio.stueck_id,
        ).first()

        if stueck_stimme:
            matches = _stimme_matches(stueck_stimme.stimme, audio.stimme)
        elif user.stimme:
            matches = _stimme_matches(user.stimme, audio.stimme)
        else:
            matches = False

        if matches:
            existing = db.query(models.AudioFavorit).filter(
                models.AudioFavorit.user_id == user.id,
                models.AudioFavorit.audio_id == audio.id,
            ).first()
            if not existing:
                db.add(models.AudioFavorit(user_id=user.id, audio_id=audio.id))


@router.get("/stueck/{stueck_id}")
def list_audios(
    stueck_id: int,
    stimme: Optional[str] = None,
    typ: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")

    query = db.query(models.Audio).filter(models.Audio.stueck_id == stueck_id)
    if stimme:
        query = query.filter(models.Audio.stimme == stimme)
    if typ:
        query = query.filter(models.Audio.typ == typ)

    audios = query.all()

    fav_ids = {
        f.audio_id for f in db.query(models.AudioFavorit).filter(
            models.AudioFavorit.user_id == current_user.id
        ).all()
    }

    result = []
    for a in audios:
        result.append({
            "id": a.id,
            "stimme": a.stimme,
            "typ": a.typ,
            "bezeichnung": a.bezeichnung,
            "dateiname": a.dateiname,
            "dauer_sekunden": a.dauer_sekunden,
            "is_favorit": a.id in fav_ids,
        })

    # Favoriten zuerst
    result.sort(key=lambda x: (0 if x["is_favorit"] else 1, x["stimme"]))
    return result


@router.post("/stueck/{stueck_id}", status_code=201)
async def upload_audio(
    stueck_id: int,
    stimme: str = Form(...),
    typ: str = Form(...),
    bezeichnung: Optional[str] = Form(None),
    dauer_sekunden: Optional[float] = Form(None),
    datei: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")

    if stimme not in STIMMEN_ALLE:
        raise HTTPException(status_code=400, detail="Ungültige Stimme")
    if typ not in ("gesungen", "instrumental"):
        raise HTTPException(status_code=400, detail="Ungültiger Typ")

    ext = os.path.splitext(datei.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nicht unterstütztes Dateiformat")

    unique_name = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, unique_name)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    content = await datei.read()
    with open(filepath, "wb") as f:
        f.write(content)

    audio = models.Audio(
        stueck_id=stueck_id,
        stimme=stimme,
        typ=typ,
        bezeichnung=bezeichnung,
        dateiname=datei.filename,
        dateipfad=filepath,
        dauer_sekunden=dauer_sekunden,
    )
    db.add(audio)
    db.flush()

    _auto_favorites_for_audio(db, audio)
    db.commit()
    db.refresh(audio)
    return {"id": audio.id}


@router.get("/{audio_id}")
def get_audio(
    audio_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden")

    is_fav = db.query(models.AudioFavorit).filter(
        models.AudioFavorit.user_id == current_user.id,
        models.AudioFavorit.audio_id == audio_id,
    ).first() is not None

    kapitel = sorted(audio.kapitel, key=lambda k: k.start_sekunden)
    markierungen = [
        m for m in audio.markierungen
        if m.ist_oeffentlich or m.user_id == current_user.id
    ]

    return {
        "id": audio.id,
        "stueck_id": audio.stueck_id,
        "stimme": audio.stimme,
        "typ": audio.typ,
        "bezeichnung": audio.bezeichnung,
        "dateiname": audio.dateiname,
        "dauer_sekunden": audio.dauer_sekunden,
        "is_favorit": is_fav,
        "kapitel": [{"id": k.id, "name": k.name, "start_sekunden": k.start_sekunden} for k in kapitel],
        "markierungen": [
            {
                "id": m.id,
                "name": m.name,
                "start_sekunden": m.start_sekunden,
                "ende_sekunden": m.ende_sekunden,
                "ist_oeffentlich": m.ist_oeffentlich,
                "notiz": m.notiz,
                "ist_eigen": m.user_id == current_user.id,
            }
            for m in markierungen
        ],
    }


@router.put("/{audio_id}")
def update_audio(
    audio_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden")
    for field in ("stimme", "typ", "bezeichnung", "dauer_sekunden"):
        if field in data:
            setattr(audio, field, data[field])
    db.commit()
    return {"ok": True}


@router.delete("/{audio_id}")
def delete_audio(
    audio_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden")
    if os.path.exists(audio.dateipfad):
        os.remove(audio.dateipfad)
    db.delete(audio)
    db.commit()
    return {"ok": True}
