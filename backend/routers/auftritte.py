import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session, object_session

import auth as auth_utils
import models
import stimmen
from database import get_db
from pdf_export import render_matrix_pdf

router = APIRouter(prefix="/api/auftritte", tags=["auftritte"])

_UHRZEIT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class AuftrittIn(BaseModel):
    name: str
    datum: date
    uhrzeit_einsingen: Optional[str] = None
    uhrzeit_konzert: Optional[str] = None
    notizen: Optional[str] = None
    dauer_aufabgang: Optional[int] = Field(default=None, ge=0)
    dauer_moderation: Optional[int] = Field(default=None, ge=0)
    dauer_applaus_tonangabe: Optional[int] = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def name_nicht_leer(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name fehlt")
        return v

    @field_validator("uhrzeit_einsingen", "uhrzeit_konzert")
    @classmethod
    def uhrzeit_format(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        if not _UHRZEIT.match(v):
            raise ValueError("Uhrzeit im Format HH:MM angeben")
        return v


ZUSATZZEITEN = [
    ("dauer_aufabgang", "Auf- und Abgang"),
    ("dauer_moderation", "Moderation"),
    ("dauer_applaus_tonangabe", "Applaus & Tonangabe"),
]


def _lieddauer(a: models.Auftritt) -> int:
    return sum(e.dauer_sekunden or 0 for e in a.eintraege)


def _gesamtdauer(a: models.Auftritt) -> int:
    """Lied-Dauern + Auf-/Abgang + Moderation + Applaus/Tonangabe."""
    return _lieddauer(a) + sum(getattr(a, feld) or 0 for feld, _ in ZUSATZZEITEN)


def _auftritt_kurz(a: models.Auftritt) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "datum": a.datum.isoformat(),
        "uhrzeit_einsingen": a.uhrzeit_einsingen,
        "uhrzeit_konzert": a.uhrzeit_konzert,
        "notizen": a.notizen,
        "dauer_aufabgang": a.dauer_aufabgang,
        "dauer_moderation": a.dauer_moderation,
        "dauer_applaus_tonangabe": a.dauer_applaus_tonangabe,
        "anzahl_stuecke": len(a.eintraege),
        "lieddauer_sekunden": _lieddauer(a),
        "gesamtdauer_sekunden": _gesamtdauer(a),
    }


def eintrag_dict(e: models.SetlistEintrag) -> dict:
    return {
        "id": e.id,
        "stueck_id": e.stueck_id,
        "titel": e.stueck.titel,
        "komponist": e.stueck.komponist,
        "reihenfolge": e.reihenfolge,
        "begleitung": e.begleitung,
        "dauer_sekunden": e.dauer_sekunden,
        "notizen": e.notizen,
    }


def get_auftritt_or_404(db: Session, auftritt_id: int) -> models.Auftritt:
    a = db.query(models.Auftritt).filter(models.Auftritt.id == auftritt_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Auftritt nicht gefunden")
    return a


def _anwesende_ids(a: models.Auftritt) -> set[int]:
    return {s.user_id for s in a.saenger}


def auftritt_detail(a: models.Auftritt) -> dict:
    """Auftritt mit Setlist und Besetzungs-Matrix (alle Sänger, mit Anwesenheit)."""
    db = object_session(a)
    saenger = stimmen.saenger_liste(db)
    zuo = stimmen.zuordnungen(db, [e.stueck_id for e in a.eintraege])
    anwesend = _anwesende_ids(a)
    return {
        **_auftritt_kurz(a),
        "saenger": [{**stimmen.saenger_dict(u), "anwesend": u.id in anwesend} for u in saenger],
        "eintraege": [
            {
                **eintrag_dict(e),
                "zellen": {str(u.id): stimmen.zelle(u, e.stueck_id, zuo) for u in saenger},
            }
            for e in a.eintraege
        ],
    }


@router.get("")
def list_auftritte(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    auftritte = db.query(models.Auftritt).order_by(models.Auftritt.datum.desc()).all()
    return [_auftritt_kurz(a) for a in auftritte]


@router.post("", status_code=201)
def create_auftritt(
    data: AuftrittIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    a = models.Auftritt(**data.model_dump())
    db.add(a)
    db.flush()
    # Alle aktiven Sänger (keine Chorleiter) sind zunächst anwesend
    for u in db.query(models.User).filter(models.User.rolle.in_(auth_utils.SAENGER_ROLLEN)).all():
        db.add(models.AuftrittSaenger(auftritt_id=a.id, user_id=u.id))
    db.commit()
    db.refresh(a)
    return auftritt_detail(a)


@router.get("/{auftritt_id}")
def get_auftritt(
    auftritt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    return auftritt_detail(get_auftritt_or_404(db, auftritt_id))


@router.put("/{auftritt_id}")
def update_auftritt(
    auftritt_id: int,
    data: AuftrittIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    a = get_auftritt_or_404(db, auftritt_id)
    for k, v in data.model_dump().items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return auftritt_detail(a)


@router.delete("/{auftritt_id}")
def delete_auftritt(
    auftritt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    a = get_auftritt_or_404(db, auftritt_id)
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.post("/{auftritt_id}/saenger/{user_id}/toggle")
def toggle_anwesenheit(
    auftritt_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    """Anwesenheit eines Sängers umschalten: anwesend ↔ abwesend."""
    a = get_auftritt_or_404(db, auftritt_id)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.rolle not in auth_utils.SAENGER_ROLLEN:
        raise HTTPException(status_code=404, detail="Sänger nicht gefunden")

    eintrag = db.query(models.AuftrittSaenger).filter(
        models.AuftrittSaenger.auftritt_id == a.id,
        models.AuftrittSaenger.user_id == user_id,
    ).first()
    if eintrag:
        db.delete(eintrag)
    else:
        db.add(models.AuftrittSaenger(auftritt_id=a.id, user_id=user_id))
    db.commit()
    return {"user_id": user_id, "anwesend": eintrag is None}


@router.get("/{auftritt_id}/pdf")
def export_pdf(
    auftritt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    a = get_auftritt_or_404(db, auftritt_id)
    # Nur anwesende Sänger erscheinen als Spalten
    anwesend = _anwesende_ids(a)
    saenger = [u for u in stimmen.saenger_liste(db) if u.id in anwesend]
    zuo = stimmen.zuordnungen(db, [e.stueck_id for e in a.eintraege])

    zeilen = [
        {
            "nr": i,
            "titel": e.stueck.titel,
            "zellen": {u.id: stimmen.zelle(u, e.stueck_id, zuo) for u in saenger},
            "begleitung": e.begleitung,
            "dauer": stimmen.format_dauer(e.dauer_sekunden),
        }
        for i, e in enumerate(a.eintraege, start=1)
    ]

    zeiten = []
    if a.uhrzeit_einsingen:
        zeiten.append(f"Einsingen: {a.uhrzeit_einsingen} Uhr")
    if a.uhrzeit_konzert:
        zeiten.append(f"Konzert: {a.uhrzeit_konzert} Uhr")
    info = ["  ·  ".join(zeiten)] if zeiten else []

    pdf = render_matrix_pdf(
        titel=f"{a.name} – {a.datum.strftime('%d.%m.%Y')}",
        info_zeilen=info,
        saenger=[stimmen.saenger_dict(u) for u in saenger],
        zeilen=zeilen,
        mit_setlist_spalten=True,
        zusatz_zeilen=[
            (label, stimmen.format_dauer(getattr(a, feld)))
            for feld, label in ZUSATZZEITEN if getattr(a, feld) is not None
        ],
        gesamtzeit=stimmen.format_dauer(_gesamtdauer(a)),
    )
    dateiname = f"Setlist {stimmen.safe_filename(a.name)} {a.datum.isoformat()}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": stimmen.content_disposition(dateiname)},
    )
