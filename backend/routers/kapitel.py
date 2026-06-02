from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database import get_db
import models
import auth as auth_utils

router = APIRouter(prefix="/api/kapitel", tags=["kapitel"])


class KapitelCreate(BaseModel):
    audio_id: int
    name: str
    start_sekunden: float


class KapitelTransfer(BaseModel):
    ziel_audio_ids: List[int]


class KapitelBulkTransfer(BaseModel):
    ziel_audio_ids: List[int]
    modus: str = "skip"  # "skip" | "overwrite"


@router.post("", status_code=201)
def create_kapitel(
    data: KapitelCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    audio = db.query(models.Audio).filter(models.Audio.id == data.audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden")

    k = models.Kapitel(
        audio_id=data.audio_id,
        user_id=current_user.id,
        name=data.name,
        start_sekunden=data.start_sekunden,
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return {"id": k.id, "name": k.name, "start_sekunden": k.start_sekunden}


@router.post("/{kapitel_id}/uebertragen")
def transfer_kapitel(
    kapitel_id: int,
    data: KapitelTransfer,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    source = db.query(models.Kapitel).filter(models.Kapitel.id == kapitel_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Kapitel nicht gefunden")

    created = []
    for audio_id in data.ziel_audio_ids:
        audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
        if not audio:
            continue
        k = models.Kapitel(
            audio_id=audio_id,
            user_id=current_user.id,
            name=source.name,
            start_sekunden=source.start_sekunden,
        )
        db.add(k)
        created.append(audio_id)

    db.commit()
    return {"uebertragen_auf": created}


@router.post("/audio/{audio_id}/uebertragen")
def transfer_alle_kapitel(
    audio_id: int,
    data: KapitelBulkTransfer,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    """Überträgt alle Kapitel eines Audios auf mehrere Ziel-Audios."""
    quell_kapitel = db.query(models.Kapitel).filter(models.Kapitel.audio_id == audio_id).all()
    if not quell_kapitel:
        raise HTTPException(status_code=404, detail="Keine Kapitel vorhanden")

    kopiert = 0
    uebersprungen = 0
    konflikte = []

    for ziel_id in data.ziel_audio_ids:
        ziel_audio = db.query(models.Audio).filter(models.Audio.id == ziel_id).first()
        if not ziel_audio:
            continue

        vorhandene = db.query(models.Kapitel).filter(models.Kapitel.audio_id == ziel_id).all()
        vorhandene_namen = {k.name for k in vorhandene}
        konflikt_namen = {k.name for k in quell_kapitel} & vorhandene_namen

        if konflikt_namen:
            typ_label = "Gesungen" if ziel_audio.typ == "gesungen" else "Instrumental"
            label = f"{ziel_audio.stimme} – {typ_label}"
            if ziel_audio.bezeichnung:
                label += f" – {ziel_audio.bezeichnung}"
            konflikte.append({"audio_id": ziel_id, "label": label, "namen": sorted(konflikt_namen)})

        for k in quell_kapitel:
            if k.name in vorhandene_namen:
                if data.modus == "overwrite":
                    existing = db.query(models.Kapitel).filter(
                        models.Kapitel.audio_id == ziel_id,
                        models.Kapitel.name == k.name,
                    ).first()
                    if existing:
                        db.delete(existing)
                    db.add(models.Kapitel(
                        audio_id=ziel_id, user_id=current_user.id,
                        name=k.name, start_sekunden=k.start_sekunden,
                    ))
                    kopiert += 1
                else:
                    uebersprungen += 1
            else:
                db.add(models.Kapitel(
                    audio_id=ziel_id, user_id=current_user.id,
                    name=k.name, start_sekunden=k.start_sekunden,
                ))
                kopiert += 1

    db.commit()
    return {"kopiert": kopiert, "uebersprungen": uebersprungen, "konflikte": konflikte}


@router.delete("/{kapitel_id}")
def delete_kapitel(
    kapitel_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    k = db.query(models.Kapitel).filter(models.Kapitel.id == kapitel_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Kapitel nicht gefunden")
    db.delete(k)
    db.commit()
    return {"ok": True}
