"""PDF des reçus de paiement et des attestations de scolarité (A4).

Même charte, même police (DejaVu) et même en-tête d'établissement que les
bulletins. Chaque document porte un QR code vers la page publique de
vérification (`/verifier/<code>`) et le code en clair : un tiers (banque,
ambassade, autre école) peut s'assurer que le document est authentique et
non annulé, sans compte."""
from datetime import date

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.bulletin_pdf import CONTENT_WIDTH, GRID, MUTED, NAVY, _esc, _fmt_date, _header, _style

METHOD_LABELS = {"cash": "Espèces", "mobile_money": "Mobile Money", "bank_transfer": "Virement bancaire"}


class _Qr(Flowable):
    def __init__(self, url: str, size: float):
        super().__init__()
        self.size = size
        widget = QrCodeWidget(url, barLevel="M")
        x0, y0, x1, y1 = widget.getBounds()
        self.drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
        self.drawing.add(widget)
        self.width = self.height = size

    def draw(self):
        renderPDF.draw(self.drawing, self.canv, 0, 0)


def _money(amount: float) -> str:
    return f"{amount:,.0f} F CFA".replace(",", " ")


def _kv(rows: list[tuple[str, str]], widths=(55 * mm, 127 * mm)) -> Table:
    t = Table([[Paragraph(_esc(k), _style("k", 9, False, MUTED)), Paragraph(_esc(v), _style("v", 10, True))] for k, v in rows], colWidths=list(widths))
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _verification_block(code: str, verify_url: str, voided: bool) -> Table:
    text = [
        Paragraph("Vérifier l'authenticité de ce document", _style("vt", 8.5, True, NAVY)),
        Paragraph(_esc(f"Scannez le QR code ou ouvrez : {verify_url}"), _style("vu", 7.5, False, MUTED)),
        Paragraph(_esc(f"Code : {code}"), _style("vc", 9, True)),
    ]
    if voided:
        text.append(Paragraph("DOCUMENT ANNULÉ", _style("vv", 10, True, colors.HexColor("#B3261E"))))
    t = Table([[_Qr(verify_url, 26 * mm), text]], colWidths=[30 * mm, 152 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, GRID),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def _doc(story: list, title: str) -> bytes:
    import io

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                      title=title, author="GESCOLA").build(story)
    return buffer.getvalue()


def build_receipt_pdf(*, settings: dict, images: dict, data: dict, code: str, verify_url: str, issued_on: date) -> bytes:
    """`data` : number, student_name, class_name, invoice_label, academic_year, amount, method, reference,
    balance_after, total_due, paid_on (iso)."""
    story = [_header(settings, images), Spacer(1, 6 * mm)]
    story.append(Paragraph("REÇU DE PAIEMENT", _style("t", 17, True, NAVY, TA_CENTER, leading=21)))
    story.append(Paragraph(_esc(f"N° {data['number']:06d}"), _style("n", 11, True, colors.black, TA_CENTER)))
    story.append(Spacer(1, 6 * mm))
    rows = [
        ("Reçu de", data["student_name"] + (f" — {data['class_name']}" if data.get("class_name") else "")),
        ("Objet", f"{data['invoice_label']} (année {data['academic_year']})"),
        ("Date du paiement", _fmt_date(data["paid_on"])),
        ("Mode de paiement", METHOD_LABELS.get(data["method"], data["method"]) + (f" — réf. {data['reference']}" if data.get("reference") else "")),
        ("MONTANT REÇU", _money(data["amount"])),
        ("Total de la facture", _money(data["total_due"])),
        ("Reste à payer", "Soldé" if data["balance_after"] <= 0 else _money(data["balance_after"])),
    ]
    story.append(_kv(rows))
    story += [Spacer(1, 10 * mm), Paragraph(_esc(f"{settings.get('place') or ''}{', le ' if settings.get('place') else 'Émis le '}{_fmt_date(issued_on.isoformat())}"),
                                           _style("d", 9, False, colors.black, TA_RIGHT)), Spacer(1, 4 * mm)]
    story.append(Paragraph("Cachet et signature de l'établissement", _style("s", 8.5, False, MUTED, TA_RIGHT)))
    story.append(Spacer(1, 22 * mm))
    story.append(_verification_block(code, verify_url, False))
    return _doc(story, f"Reçu {data['number']:06d}")


def build_certificate_pdf(*, settings: dict, images: dict, snapshot: dict, number: int, code: str, verify_url: str,
                          issued_on: date, voided: bool) -> bytes:
    """`snapshot` : student_name, date_of_birth (iso|None), matricule, class_name, academic_year."""
    story = [_header(settings, images), Spacer(1, 8 * mm)]
    story.append(Paragraph("ATTESTATION DE SCOLARITÉ", _style("t", 17, True, NAVY, TA_CENTER, leading=21)))
    story.append(Paragraph(_esc(f"N° {number:06d}"), _style("n", 11, True, colors.black, TA_CENTER)))
    story.append(Spacer(1, 10 * mm))
    school = settings.get("trade_name") or settings["name"]
    body = _style("b", 11, False, colors.black, leading=19)
    story.append(Paragraph(f"Nous, soussignés, Direction de <b>{_esc(school)}</b>, attestons que :", body))
    story.append(Spacer(1, 5 * mm))
    rows = [("Nom et prénoms", snapshot["student_name"])]
    if snapshot.get("date_of_birth"):
        rows.append(("Né(e) le", _fmt_date(snapshot["date_of_birth"])))
    if snapshot.get("matricule"):
        rows.append(("Matricule", snapshot["matricule"]))
    rows.append(("Classe", snapshot["class_name"]))
    story.append(_kv(rows))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"est <b>régulièrement inscrit(e)</b> dans notre établissement pour l'année scolaire <b>{_esc(snapshot['academic_year'])}</b>.", body))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("La présente attestation est délivrée à l'intéressé(e) pour servir et valoir ce que de droit.", body))
    story += [Spacer(1, 10 * mm), Paragraph(_esc(f"{settings.get('place') or ''}{', le ' if settings.get('place') else 'Émis le '}{_fmt_date(issued_on.isoformat())}"),
                                           _style("d", 9.5, False, colors.black, TA_RIGHT)), Spacer(1, 4 * mm)]
    story.append(Paragraph("La Direction", _style("s", 9.5, True, colors.black, TA_RIGHT)))
    story.append(Spacer(1, 26 * mm))
    story.append(_verification_block(code, verify_url, voided))
    return _doc(story, f"Attestation {number:06d}")
