from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth as auth_utils
import models
import stimmen
from database import get_db
from pdf_export import render_matrix_pdf

router = APIRouter(prefix="/api/stimmmatrix", tags=["stimmmatrix"])


class ZuordnungUpdate(BaseModel):
    stimme: Optional[str] = None  # None/"" = Standard (Fallback auf users.stimme)


def _matrix(db: Session) -> dict:
    stuecke = db.query(models.Stueck).order_by(models.Stueck.titel).all()
    saenger = stimmen.saenger_liste(db)
    zuo = stimmen.zuordnungen(db)
    return {
        "saenger": [stimmen.saenger_dict(u) for u in saenger],
        "stuecke": [
            {
                "id": s.id,
                "titel": s.titel,
                "komponist": s.komponist,
                "verfuegbare_stimmen": sorted({a.stimme for a in s.audios}),
                "zellen": {str(u.id): stimmen.zelle(u, s.id, zuo) for u in saenger},
            }
            for s in stuecke
        ],
    }


@router.get("")
def get_matrix(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    return _matrix(db)


@router.put("/{stueck_id}/{user_id}")
def set_zuordnung(
    stueck_id: int,
    user_id: int,
    data: ZuordnungUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")

    entry = db.query(models.UserStueckStimme).filter(
        models.UserStueckStimme.user_id == user_id,
        models.UserStueckStimme.stueck_id == stueck_id,
    ).first()

    if not data.stimme:
        if entry:
            db.delete(entry)
    elif entry:
        entry.stimme = data.stimme
    else:
        db.add(models.UserStueckStimme(user_id=user_id, stueck_id=stueck_id, stimme=data.stimme))
    db.commit()

    zuo = stimmen.zuordnungen(db, [stueck_id])
    return stimmen.zelle(user, stueck_id, zuo)


@router.get("/pdf")
def export_pdf(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    m = _matrix(db)
    zeilen = [
        {
            "titel": s["titel"],
            "zellen": {int(uid): z for uid, z in s["zellen"].items()},
        }
        for s in m["stuecke"]
    ]
    pdf = render_matrix_pdf(
        titel="Stimmmatrix",
        info_zeilen=[f"Stand: {date.today().strftime('%d.%m.%Y')}"],
        saenger=m["saenger"],
        zeilen=zeilen,
        mit_setlist_spalten=False,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": stimmen.content_disposition("Stimmmatrix.pdf")},
    )
