# TeachUs — Choir Audio Manager

TeachUs ist eine Web-App für Chöre zum Verwalten und Anhören von Übungsaufnahmen (Teachme-Audios). Mitglieder können Audios nach ihrer Stimme filtern, persönliche Markierungen setzen und Favoriten speichern. Admins und Chorleiter verwalten das Repertoire, laden Audiodateien hoch und organisieren Kapitel.

---

## Features

- **Repertoire-Übersicht** — alle Stücke auf einen Blick, durchsuchbar und filterbar
- **Audio-Player** — mit Fortschrittsbalken, Kapitelmarken und Lautstärkeregelung
- **Stimmen-Filter** — jedes Mitglied sieht zuerst die eigene Stimme
- **Markierungen** — persönliche oder öffentliche Zeitstempel mit Namen
- **Kapitel** — strukturierte Sprungmarken, übertragbar auf mehrere Audios
- **Favoriten** — Stücke und Audios als Favorit markieren
- **ZIP-Download** — alle Audios eines Stücks mit korrekten ID3-Tags als ZIP herunterladen
- **Rollensystem** — Mitglied · Chorleiter · Admin
- **Einladungslink** — geschlossene Registrierung per Invite-Code

---

## Voraussetzungen

- [Docker](https://www.docker.com/) & Docker Compose

---

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/vb-ora/teachus.git
cd teachus
```

### 2. Umgebungsvariablen anlegen

```bash
cp .env.example .env
```

Dann `.env` öffnen und die Werte anpassen:

```env
SECRET_KEY=<langer-zufälliger-string>
INVITE_CODE=<einladungscode-für-neue-mitglieder>
ADMIN_USERNAME=<benutzername-des-ersten-admins>
ADMIN_PASSWORD=<passwort-des-ersten-admins>
```

### 3. App starten

```bash
docker-compose up -d
```

Die App ist anschließend erreichbar unter: **http://localhost:8080**

---

## Erster Admin-Account

Beim ersten Start wird automatisch ein Admin-Account mit den Werten aus `.env` angelegt (`ADMIN_USERNAME` / `ADMIN_PASSWORD`). Dieser Account kann direkt verwendet werden, um das Repertoire zu befüllen und weitere Nutzer zu verwalten.

---

## Neue Mitglieder einladen

Neue Nutzer können sich nur über einen Einladungslink registrieren:

```
http://localhost:8080/register?code=<INVITE_CODE>
```

Den Link einfach per E-Mail oder Messenger an die Chormitglieder schicken.

---

## Datenpersistenz

Datenbank und Audiodateien werden im lokalen Verzeichnis `./data/` gespeichert, das per Volume in den Container gemountet ist. Die Daten bleiben auch nach einem Container-Neustart erhalten.

---

## Nützliche Befehle

| Aktion | Befehl |
|---|---|
| App starten | `docker-compose up -d` |
| App stoppen | `docker-compose down` |
| Logs anzeigen | `docker-compose logs -f` |
| Image neu bauen | `docker-compose up --build -d` |
| Alles inkl. Daten löschen | `docker-compose down -v` |

---

## Technik

| Schicht | Technologie |
|---|---|
| Frontend | Vanilla HTML / CSS / JavaScript |
| Backend | Python · FastAPI |
| Datenbank | SQLite |
| Auth | JWT (Bearer Token) |
| Audio-Tags | mutagen |
| Deployment | Docker · Docker Compose |

---

## Lizenz

Privates Projekt — alle Rechte vorbehalten.
