from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth as auth_utils
import models
from database import get_db
from routers.auftritte import auftritt_detail, get_auftritt_or_404

router = APIRouter(prefix="/api/setlists", tags=["setlists"])


class EintragCreate(BaseModel):
    stueck_id: int
    begleitung: Optional[str] = None
    dauer_sekunden: Optional[int] = Field(default=None, ge=0)
    notizen: Optional[str] = None


class EintragUpdate(BaseModel):
    begleitung: Optional[str] = None
    dauer_sekunden: Optional[int] = Field(default=None, ge=0)
    notizen: Optional[str] = None


class Reihenfolge(BaseModel):
    eintrag_ids: list[int]


def _get_eintrag_or_404(db: Session, eintrag_id: int) -> models.SetlistEintrag:
    e = db.query(models.SetlistEintrag).filter(models.SetlistEintrag.id == eintrag_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Setlist-Eintrag nicht gefunden")
    return e


def _neu_nummerieren(a: models.Auftritt):
    for i, e in enumerate(sorted(a.eintraege, key=lambda e: e.reihenfolge), start=1):
        e.reihenfolge = i


@router.post("/{auftritt_id}/eintraege", status_code=201)
def add_eintrag(
    auftritt_id: int,
    data: EintragCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    a = get_auftritt_or_404(db, auftritt_id)
    if not db.query(models.Stueck).filter(models.Stueck.id == data.stueck_id).first():
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")

    naechste = max((e.reihenfolge for e in a.eintraege), default=0) + 1
    db.add(models.SetlistEintrag(
        auftritt_id=a.id,
        stueck_id=data.stueck_id,
        reihenfolge=naechste,
        begleitung=(data.begleitung or "").strip() or None,
        dauer_sekunden=data.dauer_sekunden,
        notizen=(data.notizen or "").strip() or None,
    ))
    db.commit()
    db.refresh(a)
    return auftritt_detail(a)


@router.put("/eintraege/{eintrag_id}")
def update_eintrag(
    eintrag_id: int,
    data: EintragUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    e = _get_eintrag_or_404(db, eintrag_id)
    e.begleitung = (data.begleitung or "").strip() or None
    e.dauer_sekunden = data.dauer_sekunden
    e.notizen = (data.notizen or "").strip() or None
    db.commit()
    a = e.auftritt
    db.refresh(a)
    return auftritt_detail(a)


@router.delete("/eintraege/{eintrag_id}")
def delete_eintrag(
    eintrag_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    e = _get_eintrag_or_404(db, eintrag_id)
    a = e.auftritt
    a.eintraege.remove(e)
    _neu_nummerieren(a)
    db.commit()
    db.refresh(a)
    return auftritt_detail(a)


@router.put("/{auftritt_id}/reihenfolge")
def set_reihenfolge(
    auftritt_id: int,
    data: Reihenfolge,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    a = get_auftritt_or_404(db, auftritt_id)
    by_id = {e.id: e for e in a.eintraege}
    if sorted(data.eintrag_ids) != sorted(by_id):
        raise HTTPException(status_code=400, detail="Reihenfolge passt nicht zur Setlist")
    for i, eid in enumerate(data.eintrag_ids, start=1):
        by_id[eid].reihenfolge = i
    db.commit()
    db.expire(a, ["eintraege"])
    return auftritt_detail(a)
