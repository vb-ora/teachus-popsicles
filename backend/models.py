from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, backref
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rolle = Column(String, nullable=False)  # superadmin / admin / chorleiter / mitglied
    stimme = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    markierungen = relationship("Markierung", back_populates="user")
    kapitel = relationship("Kapitel", back_populates="user")
    stueck_favoriten = relationship("StueckFavorit", back_populates="user")
    audio_favoriten = relationship("AudioFavorit", back_populates="user")
    stueck_stimmen = relationship("UserStueckStimme", back_populates="user")


class Stueck(Base):
    __tablename__ = "stuecke"

    id = Column(Integer, primary_key=True)
    titel = Column(String, nullable=False)
    komponist = Column(String, nullable=True)
    notizen = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    audios = relationship("Audio", back_populates="stueck", cascade="all, delete-orphan")
    favoriten = relationship("StueckFavorit", back_populates="stueck", cascade="all, delete-orphan")
    stimmen = relationship("UserStueckStimme", back_populates="stueck", cascade="all, delete-orphan")


class Audio(Base):
    __tablename__ = "audios"

    id = Column(Integer, primary_key=True)
    stueck_id = Column(Integer, ForeignKey("stuecke.id"), nullable=False)
    stimme = Column(String, nullable=False)
    typ = Column(String, nullable=False)  # gesungen / instrumental
    bezeichnung = Column(String, nullable=True)
    dateiname = Column(String, nullable=False)
    dateipfad = Column(String, nullable=False)
    dauer_sekunden = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    stueck = relationship("Stueck", back_populates="audios")
    markierungen = relationship("Markierung", back_populates="audio", cascade="all, delete-orphan")
    kapitel = relationship("Kapitel", back_populates="audio", cascade="all, delete-orphan")
    favoriten = relationship("AudioFavorit", back_populates="audio", cascade="all, delete-orphan")


class Markierung(Base):
    __tablename__ = "markierungen"

    id = Column(Integer, primary_key=True)
    audio_id = Column(Integer, ForeignKey("audios.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    start_sekunden = Column(Float, nullable=False)
    ende_sekunden = Column(Float, nullable=False)
    ist_oeffentlich = Column(Boolean, default=False)
    notiz = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    audio = relationship("Audio", back_populates="markierungen")
    user = relationship("User", back_populates="markierungen")


class Kapitel(Base):
    __tablename__ = "kapitel"

    id = Column(Integer, primary_key=True)
    audio_id = Column(Integer, ForeignKey("audios.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    start_sekunden = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    audio = relationship("Audio", back_populates="kapitel")
    user = relationship("User", back_populates="kapitel")


class StueckFavorit(Base):
    __tablename__ = "stueck_favoriten"
    __table_args__ = (UniqueConstraint("user_id", "stueck_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stueck_id = Column(Integer, ForeignKey("stuecke.id"), nullable=False)

    user = relationship("User", back_populates="stueck_favoriten")
    stueck = relationship("Stueck", back_populates="favoriten")


class AudioFavorit(Base):
    __tablename__ = "audio_favoriten"
    __table_args__ = (UniqueConstraint("user_id", "audio_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    audio_id = Column(Integer, ForeignKey("audios.id"), nullable=False)

    user = relationship("User", back_populates="audio_favoriten")
    audio = relationship("Audio", back_populates="favoriten")


class UserStueckStimme(Base):
    __tablename__ = "user_stueck_stimme"
    __table_args__ = (UniqueConstraint("user_id", "stueck_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stueck_id = Column(Integer, ForeignKey("stuecke.id"), nullable=False)
    stimme = Column(String, nullable=False)

    user = relationship("User", back_populates="stueck_stimmen")
    stueck = relationship("Stueck", back_populates="stimmen")


class Auftritt(Base):
    __tablename__ = "auftritte"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    datum = Column(Date, nullable=False)
    uhrzeit_einsingen = Column(String, nullable=True)  # "HH:MM"
    uhrzeit_konzert = Column(String, nullable=True)    # "HH:MM"
    notizen = Column(Text, nullable=True)
    # Zusatzzeiten in Sekunden (zählen zur Gesamtdauer)
    dauer_aufabgang = Column(Integer, nullable=True)
    dauer_moderation = Column(Integer, nullable=True)
    dauer_applaus_tonangabe = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    eintraege = relationship(
        "SetlistEintrag",
        back_populates="auftritt",
        cascade="all, delete-orphan",
        order_by="SetlistEintrag.reihenfolge",
    )
    saenger = relationship("AuftrittSaenger", back_populates="auftritt", cascade="all, delete-orphan")


class SetlistEintrag(Base):
    __tablename__ = "setlist_eintraege"

    id = Column(Integer, primary_key=True)
    auftritt_id = Column(Integer, ForeignKey("auftritte.id"), nullable=False)
    stueck_id = Column(Integer, ForeignKey("stuecke.id"), nullable=False)
    reihenfolge = Column(Integer, nullable=False, default=0)
    begleitung = Column(Text, nullable=True)
    dauer_sekunden = Column(Integer, nullable=True)
    notizen = Column(Text, nullable=True)

    auftritt = relationship("Auftritt", back_populates="eintraege")
    # backref statt Änderung an Stueck: beim Löschen eines Stücks werden
    # seine Setlist-Einträge mit entfernt.
    stueck = relationship(
        "Stueck",
        backref=backref("setlist_eintraege", cascade="all, delete-orphan"),
    )


class AuftrittSaenger(Base):
    """Sänger, die bei einem Auftritt anwesend sind (fehlender Eintrag = abwesend)."""
    __tablename__ = "auftritt_saenger"
    __table_args__ = (UniqueConstraint("auftritt_id", "user_id"),)

    id = Column(Integer, primary_key=True)
    auftritt_id = Column(Integer, ForeignKey("auftritte.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    auftritt = relationship("Auftritt", back_populates="saenger")
