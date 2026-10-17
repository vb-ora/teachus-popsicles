"""PDF-Erzeugung (reportlab) für Stimmmatrix und Setlist-Matrix."""
import io
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from stimmen import GRUPPEN_REIHENFOLGE

# Hintergrund der Sängerspalten (Zellen) und der Gruppenköpfe je Stimmgruppe
GRUPPEN_FARBEN = {
    "Sopran":   (colors.HexColor("#FBE3E6"), colors.HexColor("#F2B8C0")),
    "Mezzo":    (colors.HexColor("#FDEBDD"), colors.HexColor("#F7C9A6")),
    "Alt":      (colors.HexColor("#FFF5D6"), colors.HexColor("#F5DE8E")),
    "Tenor":    (colors.HexColor("#E3F1DE"), colors.HexColor("#B5D8A7")),
    "Bass":     (colors.HexColor("#DDEBF7"), colors.HexColor("#A8CBEA")),
    "Sonstige": (colors.HexColor("#EEEEEE"), colors.HexColor("#CCCCCC")),
}
HEADER_BG = colors.HexColor("#3B4BD0")
GRID = colors.HexColor("#9E9E9E")

PAGE = landscape(A4)
MARGIN = 10 * mm


class VerticalText(Flowable):
    """Um 90° gedrehter Text für schmale Spaltenköpfe (Sängernamen)."""

    def __init__(self, text: str, font: str = "Helvetica-Bold", size: float = 7):
        super().__init__()
        self.text = text
        self.font = font
        self.size = size

    def wrap(self, avail_width, avail_height):
        self.width = self.size * 1.2
        self.height = stringWidth(self.text, self.font, self.size) + 4
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFont(self.font, self.size)
        c.rotate(90)
        c.drawString(2, -self.size * 0.95, self.text)
        c.restoreState()


def _kurzname(name: str, max_len: int = 18) -> str:
    return name if len(name) <= max_len else name[: max_len - 1] + "…"


def render_matrix_pdf(
    titel: str,
    info_zeilen: list[str],
    saenger: list[dict],
    zeilen: list[dict],
    mit_setlist_spalten: bool,
    zusatz_zeilen: Optional[list[tuple[str, str]]] = None,
    gesamtzeit: Optional[str] = None,
) -> bytes:
    """
    saenger: [{id, name, gruppe}] – nach Standardstimme gruppiert sortiert
    zeilen:  [{nr, titel, zellen: {user_id: {kuerzel, gruppe}}, begleitung, dauer}]
             Die Zellfarbe richtet sich nach zellen[..]["gruppe"], also nach der
             Stimme, die der Sänger in diesem Stück tatsächlich singt.
    mit_setlist_spalten: Nr / Begleitung / Zeit anzeigen
    zusatz_zeilen: [(Bezeichnung, Dauer)] – Zeilen unter der Liedliste (nur Setlist)
    gesamtzeit: abschließende Gesamtzeit-Zeile (nur Setlist)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=titel,
    )

    title_style = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16, leading=20)
    info_style = ParagraphStyle("i", fontName="Helvetica", fontSize=10, leading=13)

    n = len(saenger)
    avail = PAGE[0] - 2 * MARGIN

    # Spaltenbreiten: Sängerspalten so breit wie möglich (max 9 mm), Rest für Titel
    nr_w = 9 * mm if mit_setlist_spalten else 0
    beg_w = 32 * mm if mit_setlist_spalten else 0
    zeit_w = 13 * mm if mit_setlist_spalten else 0
    titel_min = 45 * mm
    s_w = min(9 * mm, max(4.5 * mm, (avail - nr_w - beg_w - zeit_w - titel_min) / n)) if n else 0
    titel_w = min(90 * mm, max(titel_min, avail - nr_w - beg_w - zeit_w - s_w * n))

    cell_size = 7 if s_w >= 6.5 * mm else 5.5
    body_size = 8.5
    titel_para = ParagraphStyle("st", fontName="Helvetica-Oblique", fontSize=body_size, leading=body_size + 2)
    body_para = ParagraphStyle("b", fontName="Helvetica", fontSize=body_size - 0.5, leading=body_size + 1.5)
    head_para = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=body_size, leading=body_size + 2,
                               textColor=colors.white)

    # Spaltenindizes
    cols_widths = []
    if mit_setlist_spalten:
        cols_widths.append(nr_w)
    titel_col = len(cols_widths)
    cols_widths.append(titel_w)
    first_s = len(cols_widths)
    cols_widths.extend([s_w] * n)
    if mit_setlist_spalten:
        zeit_col = len(cols_widths) + 1
        cols_widths.extend([beg_w, zeit_w])

    # Eine Kopfzeile: Sängernamen vertikal, ohne Gruppenüberschrift
    header = []
    if mit_setlist_spalten:
        header.append(Paragraph("Nr", head_para))
    header.append(Paragraph("Stück", head_para))
    header += [VerticalText(_kurzname(s["name"]), size=cell_size) for s in saenger]
    if mit_setlist_spalten:
        header += [Paragraph("Begleitung", head_para), Paragraph("Zeit", head_para)]

    # Letzte Zeile der Liedliste (danach folgen ggf. Zusatzzeiten und Gesamtzeit)
    lied_ende = max(len(zeilen), 1)

    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), body_size),
    ]
    if n:
        s0, s1 = first_s, first_s + n - 1
        style += [
            ("VALIGN", (s0, 0), (s1, 0), "BOTTOM"),
            ("ALIGN", (s0, 0), (s1, lied_ende), "CENTER"),
            ("LEFTPADDING", (s0, 0), (s1, lied_ende), 1),
            ("RIGHTPADDING", (s0, 0), (s1, lied_ende), 1),
            ("FONTSIZE", (s0, 1), (s1, lied_ende), cell_size + 1),
            ("FONTNAME", (s0, 1), (s1, lied_ende), "Helvetica-Bold"),
            ("LINEAFTER", (s1, 0), (s1, lied_ende), 1.2, colors.black),
        ]
    if mit_setlist_spalten:
        style += [
            ("ALIGN", (0, 1), (0, -1), "RIGHT"),
            ("ALIGN", (zeit_col, 1), (zeit_col, -1), "RIGHT"),
        ]

    # Namensköpfe leicht nach Standardstimme getönt; dicke Linie zwischen den Gruppen
    for i, s in enumerate(saenger):
        c = first_s + i
        style += [
            ("BACKGROUND", (c, 0), (c, 0), GRUPPEN_FARBEN.get(s["gruppe"], GRUPPEN_FARBEN["Sonstige"])[1]),
            ("TEXTCOLOR", (c, 0), (c, 0), colors.black),
        ]
        if i == 0 or saenger[i - 1]["gruppe"] != s["gruppe"]:
            style.append(("LINEBEFORE", (c, 0), (c, lied_ende), 1.2, colors.black))

    data = [header]
    for r, z in enumerate(zeilen, start=1):
        row = []
        if mit_setlist_spalten:
            row.append(str(z.get("nr", "")))
        row.append(Paragraph(_esc(z["titel"]), titel_para))
        for i, s in enumerate(saenger):
            zelle = z["zellen"].get(s["id"]) or {}
            row.append(zelle.get("kuerzel", ""))
            if zelle.get("kuerzel"):
                farbe = GRUPPEN_FARBEN.get(zelle.get("gruppe"), GRUPPEN_FARBEN["Sonstige"])[0]
                style.append(("BACKGROUND", (first_s + i, r), (first_s + i, r), farbe))
        if mit_setlist_spalten:
            row.append(Paragraph(_esc(z.get("begleitung") or ""), body_para))
            row.append(z.get("dauer") or "")
        data.append(row)

    if not zeilen:
        empty = [""] * len(cols_widths)
        empty[titel_col] = Paragraph("<i>Keine Einträge</i>", body_para)
        data.append(empty)

    if mit_setlist_spalten:
        # Zusatzzeiten und Gesamtzeit: Bezeichnung über Stück…Begleitung, Dauer in "Zeit"
        def summenzeile(label: str, dauer: str) -> list:
            row = [""] * len(cols_widths)
            row[titel_col] = label
            row[zeit_col] = dauer
            r = len(data)
            style.extend([
                ("SPAN", (titel_col, r), (zeit_col - 1, r)),
                ("ALIGN", (titel_col, r), (titel_col, r), "RIGHT"),
            ])
            return row

        for label, dauer in zusatz_zeilen or []:
            data.append(summenzeile(label, dauer))
        if gesamtzeit is not None:
            data.append(summenzeile("Gesamtzeit", gesamtzeit))
            r = len(data) - 1
            style.extend([
                ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
                ("FONTSIZE", (0, r), (-1, r), body_size + 1),
                ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#EEF0FF")),
                ("LINEABOVE", (0, r), (-1, r), 1.2, colors.black),
            ])

    table = Table(data, colWidths=cols_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle(style))

    story = [Paragraph(_esc(titel), title_style)]
    for z in info_zeilen:
        story.append(Paragraph(_esc(z), info_style))
    story += [Spacer(1, 5 * mm), table]

    doc.build(story)
    return buf.getvalue()


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


assert set(GRUPPEN_REIHENFOLGE) <= set(GRUPPEN_FARBEN)
