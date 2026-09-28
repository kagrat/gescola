"""Génération du PDF d'un bulletin de notes (A4 portrait).

Mise en page inspirée de la maquette fournie : en-tête (logo, nom, devise,
autorité de tutelle), titre, cadre d'identité, RÉSULTATS SCOLAIRES,
SYNTHÈSE GÉNÉRALE, VIE SCOLAIRE, APPRÉCIATIONS, décision du conseil de classe
et signatures avec cachets.

Trois blocs sont configurables par l'établissement (voir Tenant.bulletin_*) :
  * appréciations (colonne « Appréciation du professeur » + appréciation
    générale du professeur principal) ;
  * vie scolaire (absences, retards, incidents) ;
  * signature du professeur principal.
La signature du Directeur et celle du Censeur, chacune avec le cachet de son
titulaire, figurent toujours ; un espace vierge est laissé quand une signature
ou un cachet n'est pas enregistré, pour permettre la signature manuscrite.

Police DejaVu Sans embarquée (app/assets/fonts) : elle couvre les caractères
des noms d'Afrique de l'Ouest (ɖ, ɛ, ɔ, ŋ…) que les polices PDF standard ne
savent pas afficher. Repli sur Helvetica si les fichiers sont absents.
"""
import base64
import io
import re
from datetime import date
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#123B73")
HEADER_BG = colors.HexColor("#E6ECF5")
BOX_BG = colors.HexColor("#F3F5F8")
GRID = colors.HexColor("#B5C1D4")
MUTED = colors.HexColor("#5B6577")

TERM_LABELS = {"T1": "1er Trimestre", "T2": "2e Trimestre", "T3": "3e Trimestre"}
_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_fonts_ready: tuple[str, str] | None = None

CONTENT_WIDTH = 182 * mm  # A4 (210 mm) moins deux marges de 14 mm


def _fonts() -> tuple[str, str]:
    global _fonts_ready
    if _fonts_ready is None:
        regular, bold = _FONT_DIR / "DejaVuSans.ttf", _FONT_DIR / "DejaVuSans-Bold.ttf"
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
            pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")
            _fonts_ready = ("DejaVu", "DejaVu-Bold")
        else:  # pragma: no cover - repli si l'installation est incomplète
            _fonts_ready = ("Helvetica", "Helvetica-Bold")
    return _fonts_ready


def _style(name: str, size: float = 8.5, bold: bool = False, color=colors.black, align=TA_LEFT, leading: float | None = None) -> ParagraphStyle:
    regular, bold_font = _fonts()
    return ParagraphStyle(
        name, fontName=bold_font if bold else regular, fontSize=size, textColor=color, alignment=align,
        leading=leading or size * 1.3,
    )


def _esc(text: str | None) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(value: float | None, decimals: int = 2) -> str:
    return "—" if value is None else f"{value:.{decimals}f}".replace(".", ",")


def _fmt_coef(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else _fmt(value, 1)


def _rank(rank: int | None) -> str:
    if rank is None:
        return "—"
    return "1er" if rank == 1 else f"{rank}e"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def _image(data_uri: str | None, max_w: float, max_h: float) -> Image | None:
    """Décode un data URI en image redimensionnée à la boîte donnée (ratio
    conservé). Toute image illisible ou non prise en charge (ex. SVG) est
    ignorée : le bulletin reste imprimable, l'espace est laissé vierge."""
    if not data_uri:
        return None
    try:
        raw = base64.b64decode(data_uri.split(",", 1)[1])
        im = PILImage.open(io.BytesIO(raw))
        im.load()
        im = im.convert("RGBA")
        im.thumbnail((900, 900))
        buffer = io.BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        ratio = min(max_w / im.width, max_h / im.height)
        return Image(buffer, width=im.width * ratio, height=im.height * ratio, mask="auto")
    except Exception:
        return None


def _section_bar(title: str, width: float) -> Table:
    bar = Table([[Paragraph(_esc(title), _style("bar", 9, True, colors.white))]], colWidths=[width])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return bar


def _boxed(title: str, content: Table, width: float) -> Table:
    outer = Table([[_section_bar(title, width)], [content]], colWidths=[width])
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


def _header(settings: dict, images: dict) -> Table:
    logo = _image(images.get("logo"), 22 * mm, 22 * mm)
    school_name = settings.get("trade_name") or settings["name"]
    identity = [Paragraph(_esc(school_name.upper()), _style("school", 14, True, NAVY, leading=17))]
    if settings.get("motto"):
        identity.append(Paragraph(_esc(settings["motto"]), _style("motto", 8.5, False, NAVY)))
    details = " · ".join(x for x in [settings.get("address"), f"RCCM : {settings['rccm']}" if settings.get("rccm") else None,
                                     f"IFU : {settings['ifu']}" if settings.get("ifu") else None] if x)
    if details:
        identity.append(Paragraph(_esc(details), _style("details", 7, False, MUTED)))
    authority = [
        Paragraph(_esc(line.strip()), _style("auth", 7.5, i == 0, colors.black, TA_RIGHT))
        for i, line in enumerate((settings.get("authority_header") or "").splitlines()) if line.strip()
    ]
    header = Table([[logo or "", identity, authority or ""]], colWidths=[26 * mm, 100 * mm, 56 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return header


def _identity_box(student: dict) -> Table:
    gender = {"male": "Masculin", "female": "Féminin"}.get(student.get("gender") or "", "—")
    label, value = _style("lbl", 8.5, False, MUTED), _style("val", 8.5, True)
    rows = [
        ["Nom et prénom :", student["name"], "Date de naissance :", _fmt_date(student.get("date_of_birth"))],
        ["Classe :", student["class_name"], "Sexe :", gender],
        ["Matricule :", student.get("matricule") or "—", "Redoublement :", "Oui" if student.get("is_repeater") else "Non"],
    ]
    table = Table(
        [[Paragraph(_esc(c), label if i % 2 == 0 else value) for i, c in enumerate(r)] for r in rows],
        colWidths=[34 * mm, 54 * mm, 36 * mm, 58 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BOX_BG), ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _results_table(snapshot: dict, show_appreciations: bool) -> Table:
    head = _style("th", 7.5, True, NAVY, TA_CENTER)
    cell = _style("td", 8.5)
    center = _style("tdc", 8.5, align=TA_CENTER)
    bold_center = _style("tdb", 8.5, True, align=TA_CENTER)
    small = _style("tds", 7.5)

    headers = ["N°", "Matières", "Coef.", "Note / 20", "Moyenne classe", "Rang"] + (["Appréciation du professeur"] if show_appreciations else [])
    data = [[Paragraph(h, head) for h in headers]]
    for i, row in enumerate(snapshot["subjects"], start=1):
        line = [
            Paragraph(str(i), center), Paragraph(_esc(row["name"]), cell), Paragraph(_fmt_coef(row["coefficient"]), center),
            Paragraph(_fmt(row["average"]), bold_center), Paragraph(_fmt(row["class_average"]), center),
            Paragraph(_rank(row["rank"]), center),
        ]
        if show_appreciations:
            line.append(Paragraph(_esc(row.get("appreciation")) or "—", small))
        data.append(line)
    total = [Paragraph("", cell), Paragraph("<b>Total des coefficients</b>", cell), Paragraph(_fmt_coef(snapshot["total_coefficients"]), bold_center)]
    total += [Paragraph("-", center)] * 3 + ([Paragraph("-", center)] if show_appreciations else [])
    data.append(total)

    widths = [8, 42, 12, 16, 20, 14, 70] if show_appreciations else [8, 74, 18, 26, 32, 24]
    table = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG), ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("BACKGROUND", (0, -1), (-1, -1), BOX_BG),
    ]))
    return table


def _kv_table(rows: list[tuple[str, str]], widths: tuple[float, float]) -> Table:
    label, value = _style("kl", 8.5), _style("kv", 8.5, True)
    table = Table([[Paragraph(_esc(k), label), Paragraph(_esc(v), value)] for k, v in rows], colWidths=[w * mm for w in widths])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRID), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return table


def _synthesis(general: dict, width: float) -> Table:
    def note(item: dict | None) -> str:
        return "—" if not item else f"{_fmt(item['value'])} / 20 ({item['name']})"
    rank = "—" if general["rank"] is None else f"{general['rank']} / {general['class_size']}"
    rows = [
        ("Moyenne générale :", f"{_fmt(general['average'])} / 20" if general["average"] is not None else "—"),
        ("Rang :", rank),
        ("Moyenne de la classe :", f"{_fmt(general['class_average'])} / 20" if general["class_average"] is not None else "—"),
        ("Note de matière la plus haute :", note(general["highest"])),
        ("Note de matière la plus faible :", note(general["lowest"])),
    ]
    return _boxed("SYNTHÈSE GÉNÉRALE", _kv_table(rows, (width / mm * 0.5, width / mm * 0.5)), width)


def _school_life(life: dict, width: float) -> Table:
    rows = [
        ("Absences justifiées :", str(life["justified_absences"])),
        ("Absences non justifiées :", str(life["unjustified_absences"])),
        ("Retards :", str(life["lateness"])),
        ("Incidents :", str(life["incidents"])),
    ]
    return _boxed("VIE SCOLAIRE", _kv_table(rows, (width / mm * 0.72, width / mm * 0.28)), width)


def _comment_box(title: str, text: str | None, width: float) -> Table:
    body = Table([[Paragraph(_esc(text) or "—", _style("cm", 8.5, leading=11))]], colWidths=[width])
    body.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRID), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return _boxed(title, body, width)


def _signature_block(title: str, name: str | None, signature_uri: str | None, stamp_uri: str | None, width: float) -> Table:
    signature = _image(signature_uri, width * 0.5, 16 * mm)
    stamp = _image(stamp_uri, 24 * mm, 24 * mm)
    proof = Table([[signature or "", stamp or ""]], colWidths=[width * 0.52, width * 0.44], rowHeights=[24 * mm])
    proof.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    block = Table(
        [[Paragraph(f"<b>{_esc(title)}</b>", _style("st", 8.5, align=TA_CENTER))],
         [Paragraph(_esc(name) if name else "&nbsp;", _style("sn", 7.5, False, MUTED, TA_CENTER))],
         [proof]],
        colWidths=[width],
    )
    block.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return block


def build_report_card_pdf(
    *, snapshot: dict, settings: dict, images: dict, principal_comment: str | None, council_decision: str | None,
    is_published: bool, issued_on: date,
) -> bytes:
    """`settings` : name, trade_name, address, rccm, ifu, motto, authority_header, place,
    show_appreciations, show_school_life, show_head_teacher_signature.
    `images` : logo, director_signature, director_stamp, censor_signature,
    censor_stamp, head_signature, head_stamp (data URIs ou None)."""
    regular, bold_font = _fonts()
    show_appreciations = bool(settings.get("show_appreciations", True))
    show_life = bool(settings.get("show_school_life", True))
    signers = snapshot.get("signers", {})
    show_head = bool(settings.get("show_head_teacher_signature")) and bool(signers.get("head_teacher"))

    story: list = [_header(settings, images), Spacer(1, 4 * mm)]
    story.append(Paragraph("BULLETIN DE NOTES", _style("title", 15, True, NAVY, TA_CENTER, leading=18)))
    story.append(Paragraph(
        f"{TERM_LABELS.get(snapshot['term'], snapshot['term'])} – Année scolaire {snapshot['academic_year']}",
        _style("sub", 9.5, False, colors.black, TA_CENTER),
    ))
    story += [Spacer(1, 3 * mm), _identity_box(snapshot["student"]), Spacer(1, 3 * mm)]
    story += [_boxed("RÉSULTATS SCOLAIRES", _results_table(snapshot, show_appreciations), CONTENT_WIDTH), Spacer(1, 3 * mm)]

    if show_life:
        left_w, right_w, gap = 108 * mm, 70 * mm, 4 * mm
        side = Table([[_synthesis(snapshot["general"], left_w), "", _school_life(snapshot["school_life"], right_w)]],
                     colWidths=[left_w, gap, right_w])
        side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
        story.append(side)
    else:
        story.append(_synthesis(snapshot["general"], CONTENT_WIDTH))
    story.append(Spacer(1, 3 * mm))

    if show_appreciations:
        story += [_comment_box("APPRÉCIATION GÉNÉRALE DU PROFESSEUR PRINCIPAL", principal_comment, CONTENT_WIDTH), Spacer(1, 3 * mm)]

    place = settings.get("place")
    issued = issued_on.strftime("%d/%m/%Y")
    made_at = f"Fait à {place}, le {issued}" if place else f"Fait le {issued}"
    decision = Table(
        [[Paragraph("<b>Décision du conseil de classe :</b> " + (_esc(council_decision) or "—"), _style("dec", 8.5)),
          Paragraph(_esc(made_at), _style("made", 8.5, False, colors.black, TA_RIGHT))]],
        colWidths=[CONTENT_WIDTH * 0.68, CONTENT_WIDTH * 0.32],
    )
    decision.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRID), ("BACKGROUND", (0, 0), (-1, -1), BOX_BG),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [decision, Spacer(1, 4 * mm)]

    columns = []
    if show_head:
        columns.append(("Le Professeur principal", signers["head_teacher"], images.get("head_signature"), images.get("head_stamp")))
    columns.append(("Le Censeur", signers.get("censor"), images.get("censor_signature"), images.get("censor_stamp")))
    columns.append(("Le Directeur", signers.get("director"), images.get("director_signature"), images.get("director_stamp")))
    col_w = CONTENT_WIDTH / len(columns)
    sign_row = Table(
        [[_signature_block(t, (who or {}).get("name"), sig, stamp, col_w - 6 * mm) for t, who, sig, stamp in columns]],
        colWidths=[col_w] * len(columns),
    )
    sign_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(KeepTogether(sign_row))

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 6.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(A4[0] / 2, 7 * mm, f"Document généré par GESCOLA — {settings.get('trade_name') or settings['name']}")
        if not is_published:
            canvas.setFont(bold_font, 62)
            canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.13))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "BROUILLON")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=13 * mm,
        title=f"Bulletin — {snapshot['student']['name']}", author="GESCOLA",
    )
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
