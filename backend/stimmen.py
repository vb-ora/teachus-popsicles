"""Hilfsfunktionen rund um Stimmen: Gruppierung, Kürzel und Stimmmatrix-Daten."""
import re
from typing import Optional

from sqlalchemy.orm import Session

import models
from auth import SAENGER_ROLLEN

STIMMGRUPPEN = ["Sopran", "Mezzo", "Alt", "Tenor", "Bass"]
GRUPPE_SONSTIGE = "Sonstige"
GRUPPEN_REIHENFOLGE = STIMMGRUPPEN + [GRUPPE_SONSTIGE]


def stimmgruppe(stimme: Optional[str]) -> str:
    """'Alt 2' → 'Alt', 'Männer'/None → 'Sonstige'."""
    if not stimme:
        return GRUPPE_SONSTIGE
    for g in STIMMGRUPPEN:
        if stimme.lower().startswith(g.lower()):
            return g
    return GRUPPE_SONSTIGE


def kuerzel(stimme: Optional[str]) -> str:
    """'Sopran' → 'S', 'Alt 2' → 'A2', 'Bass 1' → 'B1', 'Männer' → 'Mä'."""
    if not stimme:
        return ""
    gruppe = stimmgruppe(stimme)
    if gruppe == GRUPPE_SONSTIGE:
        return {"männer": "Mä", "alle": "Alle"}.get(stimme.lower(), stimme[:3])
    nummer = re.findall(r"\d+", stimme)
    return gruppe[0] + (nummer[0] if nummer else "")


def _stimme_sortkey(stimme: Optional[str]):
    gruppe = stimmgruppe(stimme)
    return (GRUPPEN_REIHENFOLGE.index(gruppe), stimme or "")


# Stimmen, die einem Sänger als Standardstimme zugewiesen werden können
USER_STIMMEN = [
    "Sopran", "Sopran 1", "Sopran 2",
    "Mezzo", "Mezzo 1", "Mezzo 2",
    "Alt", "Alt 1", "Alt 2",
    "Tenor", "Tenor 1", "Tenor 2",
    "Bass", "Bass 1", "Bass 2",
    "Männer",
]


def saenger_liste(db: Session) -> list[models.User]:
    """Alle Sänger (Superadmin, Admin, Mitglied – keine Chorleiter).
    Sortiert nach Stimmgruppe (Sopran → Mezzo → Alt → Tenor → Bass), dann Stimme, dann Name."""
    users = db.query(models.User).filter(models.User.rolle.in_(SAENGER_ROLLEN)).all()
    users.sort(key=lambda u: (*_stimme_sortkey(u.stimme), u.name.lower()))
    return users


def saenger_dict(u: models.User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "stimme": u.stimme,
        "gruppe": stimmgruppe(u.stimme),
    }


def zuordnungen(db: Session, stueck_ids: Optional[list[int]] = None) -> dict[tuple[int, int], str]:
    """(user_id, stueck_id) → stückspezifische Stimme."""
    q = db.query(models.UserStueckStimme)
    if stueck_ids is not None:
        q = q.filter(models.UserStueckStimme.stueck_id.in_(stueck_ids))
    return {(e.user_id, e.stueck_id): e.stimme for e in q.all()}


def zelle(user: models.User, stueck_id: int, zuo: dict[tuple[int, int], str]) -> dict:
    """Stimme eines Sängers in einem Stück, mit Fallback auf die Standardstimme."""
    spezifisch = zuo.get((user.id, stueck_id))
    stimme = spezifisch or user.stimme
    return {
        "stimme": stimme,
        "kuerzel": kuerzel(stimme),
        "gruppe": stimmgruppe(stimme),  # bestimmt die Zellfarbe
        "ist_standard": spezifisch is None,
    }


def format_dauer(sekunden: Optional[int]) -> str:
    if sekunden is None:
        return ""
    sekunden = int(sekunden)
    return f"{sekunden // 60}:{sekunden % 60:02d}"


def content_disposition(dateiname: str) -> str:
    """Content-Disposition mit ASCII-Fallback und UTF-8-Dateiname (Umlaute)."""
    from urllib.parse import quote
    ascii_name = dateiname.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(dateiname)}"


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "export"
