import io
import os
import re
import shutil
import tempfile
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
import models
import auth as auth_utils

UPLOAD_DIR = "/data/uploads"

router = APIRouter(prefix="/api/stuecke", tags=["stuecke"])


class StueckCreate(BaseModel):
    titel: str
    komponist: Optional[str] = None
    notizen: Optional[str] = None


class StueckOut(BaseModel):
    id: int
    titel: str
    komponist: Optional[str]
    notizen: Optional[str]
    is_favorit: bool = False

    class Config:
        from_attributes = True


@router.get("", response_model=List[dict])
def list_stuecke(
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    query = db.query(models.Stueck)
    if q:
        query = query.filter(
            (models.Stueck.titel.ilike(f"%{q}%")) |
            (models.Stueck.komponist.ilike(f"%{q}%"))
        )
    stuecke = query.order_by(models.Stueck.titel).all()

    fav_ids = {
        f.stueck_id for f in db.query(models.StueckFavorit).filter(
            models.StueckFavorit.user_id == current_user.id
        ).all()
    }

    return [
        {
            "id": s.id,
            "titel": s.titel,
            "komponist": s.komponist,
            "notizen": s.notizen,
            "is_favorit": s.id in fav_ids,
        }
        for s in stuecke
    ]


@router.post("", status_code=201)
def create_stueck(
    data: StueckCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    stueck = models.Stueck(**data.model_dump())
    db.add(stueck)
    db.commit()
    db.refresh(stueck)
    return {"id": stueck.id, "titel": stueck.titel}


@router.get("/{stueck_id}")
def get_stueck(
    stueck_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")

    is_fav = db.query(models.StueckFavorit).filter(
        models.StueckFavorit.user_id == current_user.id,
        models.StueckFavorit.stueck_id == stueck_id,
    ).first() is not None

    user_stimme_entry = db.query(models.UserStueckStimme).filter(
        models.UserStueckStimme.user_id == current_user.id,
        models.UserStueckStimme.stueck_id == stueck_id,
    ).first()

    # Verfügbare Stimmen in diesem Stück
    stimmen = list({a.stimme for a in stueck.audios})

    return {
        "id": stueck.id,
        "titel": stueck.titel,
        "komponist": stueck.komponist,
        "notizen": stueck.notizen,
        "is_favorit": is_fav,
        "meine_stimme": user_stimme_entry.stimme if user_stimme_entry else None,
        "verfuegbare_stimmen": stimmen,
    }


@router.put("/{stueck_id}")
def update_stueck(
    stueck_id: int,
    data: StueckCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")
    for k, v in data.model_dump().items():
        setattr(stueck, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{stueck_id}")
def delete_stueck(
    stueck_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")
    db.delete(stueck)
    db.commit()
    return {"ok": True}


@router.get("/{stueck_id}/download-zip")
def download_zip(
    stueck_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_admin_or_chorleiter),
):
    """Packt alle Audios eines Stücks mit angepassten ID3-Tags in eine ZIP-Datei."""
    import logging
    log = logging.getLogger("zip_download")
    logging.basicConfig(level=logging.INFO)

    stueck = db.query(models.Stueck).filter(models.Stueck.id == stueck_id).first()
    if not stueck:
        raise HTTPException(status_code=404, detail="Stück nicht gefunden")

    audios = db.query(models.Audio).filter(models.Audio.stueck_id == stueck_id).all()
    log.info(f"[ZIP] Stück '{stueck.titel}' (id={stueck_id}): {len(audios)} Audio(s) in DB gefunden")

    if not audios:
        raise HTTPException(status_code=404, detail="Keine Audios vorhanden")

    # Sichere Dateinamen ohne problematische Zeichen
    def safe(name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

    # Uploads-Verzeichnis diagnostizieren
    if os.path.isdir(UPLOAD_DIR):
        existing_files = os.listdir(UPLOAD_DIR)
        log.info(f"[ZIP] UPLOAD_DIR='{UPLOAD_DIR}' existiert, {len(existing_files)} Datei(en): {existing_files}")
    else:
        log.error(f"[ZIP] UPLOAD_DIR='{UPLOAD_DIR}' existiert NICHT!")

    buf = io.BytesIO()
    packed = 0
    skipped = 0
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        used_names: dict[str, int] = {}

        for audio in audios:
            # dateipfad enthält den echten UUID-Pfad; dateiname ist der Originalname (nur für Anzeige)
            src_path = audio.dateipfad if audio.dateipfad else os.path.join(UPLOAD_DIR, audio.dateiname)
            log.info(f"[ZIP] Audio id={audio.id} stimme='{audio.stimme}' typ='{audio.typ}' dateiname='{audio.dateiname}' dateipfad='{audio.dateipfad}' → src_path='{src_path}'")

            if not os.path.exists(src_path):
                log.warning(f"[ZIP] NICHT GEFUNDEN: {src_path} — wird übersprungen")
                skipped += 1
                continue

            file_size = os.path.getsize(src_path)
            log.info(f"[ZIP] Datei gefunden, Größe={file_size} Bytes")

            ext = os.path.splitext(src_path)[1].lower()

            # Metadaten zusammenstellen
            typ_suffix = " Gesungen" if audio.typ == "gesungen" else ""
            track_title = f"{stueck.titel} {audio.stimme}{typ_suffix}"
            album       = stueck.titel
            artist      = "Gebrannte Mandeln"

            # Dateiname im ZIP:
            # Titel + Stimme [+ Gesungen] [+ Bezeichnung bei Duplikat] [+ _2 usw. bei Duplikat]
            bez = (audio.bezeichnung or "").strip()
            name_base = f"{stueck.titel} {audio.stimme}{typ_suffix}"
            zip_basename = safe(f"{name_base}{ext}")
            # Duplikat? → Bezeichnung anhängen
            if zip_basename in used_names:
                zip_basename = safe(f"{name_base} {bez}{ext}") if bez else zip_basename
            # Immer noch Duplikat? → _2, _3 …
            if zip_basename in used_names:
                base, extension = os.path.splitext(zip_basename)
                n = 2
                while f"{base}_{n}{extension}" in used_names:
                    n += 1
                zip_basename = f"{base}_{n}{extension}"
            used_names[zip_basename] = True

            # In Tempfile kopieren und Tags setzen
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp_path = tmp.name

            try:
                shutil.copy2(src_path, tmp_path)

                try:
                    from mutagen import File as MutagenFile

                    mf = MutagenFile(tmp_path, easy=True)
                    log.info(f"[ZIP] mutagen erkanntes Format: {type(mf).__name__} für ext='{ext}'")

                    if mf is not None:
                        if ext in (".mp3",):
                            mf["title"]       = track_title
                            mf["album"]       = album
                            mf["artist"]      = artist
                            mf["albumartist"] = artist
                            mf.save()
                            log.info(f"[ZIP] ID3-Tags gesetzt und gespeichert")
                        elif ext in (".m4a", ".aac", ".mp4"):
                            from mutagen.mp4 import MP4
                            mp4 = MP4(tmp_path)
                            mp4["\xa9nam"] = track_title
                            mp4["\xa9alb"] = album
                            mp4["\xa9ART"] = artist
                            mp4["aART"]   = artist
                            mp4.save()
                            log.info(f"[ZIP] MP4-Tags gesetzt und gespeichert")
                        else:
                            log.info(f"[ZIP] Keine Tag-Unterstützung für ext='{ext}', Datei wird ohne Tags eingepackt")
                    else:
                        log.warning(f"[ZIP] mutagen konnte Datei nicht lesen (mf=None)")
                except Exception as tag_err:
                    log.warning(f"[ZIP] Tag-Fehler (nicht fatal): {tag_err}")

                zf.write(tmp_path, zip_basename)
                log.info(f"[ZIP] ✓ Eingepackt als '{zip_basename}'")
                packed += 1
            except Exception as pack_err:
                log.error(f"[ZIP] Fehler beim Einpacken von '{src_path}': {pack_err}")
                skipped += 1
            finally:
                os.unlink(tmp_path)

    log.info(f"[ZIP] Fertig: {packed} eingepackt, {skipped} übersprungen")
    buf.seek(0)
    zip_name = safe(stueck.titel) + ".zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


@router.post("/{stueck_id}/stimme")
def set_stimme(
    stueck_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    stimme = data.get("stimme")
    if not stimme:
        raise HTTPException(status_code=400, detail="Stimme fehlt")

    entry = db.query(models.UserStueckStimme).filter(
        models.UserStueckStimme.user_id == current_user.id,
        models.UserStueckStimme.stueck_id == stueck_id,
    ).first()

    if entry:
        entry.stimme = stimme
    else:
        entry = models.UserStueckStimme(
            user_id=current_user.id,
            stueck_id=stueck_id,
            stimme=stimme,
        )
        db.add(entry)
    db.commit()
    return {"ok": True}
