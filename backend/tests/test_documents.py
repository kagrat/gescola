"""AU-10 : reçus de paiement, attestations de scolarité, vérification publique par QR code."""
import io
from datetime import date, timedelta

from pypdf import PdfReader
from sqlalchemy import select

from app.db.session import SessionLocal, set_tenant_context
from app.models.audit import AuditLog
from app.models.user import UserRole

API = "/api/v1"
TODAY = date.today()


class S:
    pass


def _school(client, make_tenant, make_user, auth_headers):
    s = S()
    s.tenant = make_tenant()
    mk = lambda role: (lambda u, p: (u, auth_headers(u, p)))(*make_user(tenant=s.tenant, role=role))
    s.admin, s.h = mk(UserRole.SCHOOL_ADMIN)
    s.acc, s.acc_h = mk(UserRole.ACCOUNTANT)
    s.staff, s.staff_h = mk(UserRole.STAFF)
    s.teacher, s.teacher_h = mk(UserRole.TEACHER)
    s.cls = client.post(f"{API}/classes", json={"name": "6ème A", "level": "6ème"}, headers=s.h).json()
    s.ada = client.post(f"{API}/students", json={"first_name": "Ada", "last_name": "Zohoun", "class_id": s.cls["id"], "matricule": "M-001",
                                                "date_of_birth": "2012-04-09"}, headers=s.h).json()
    return s


def _invoice(client, s, amount=10000, student=None, label="Scolarité T1"):
    return client.post(f"{API}/invoices", json={"student_id": (student or s.ada)["id"], "label": label, "amount_due": amount,
                                                "due_date": str(TODAY + timedelta(days=10))}, headers=s.h).json()


def _pay(client, s, inv, amount, headers=None, **extra):
    r = client.post(f"{API}/payments", json={"invoice_id": inv["id"], "amount": amount, "method": "cash", **extra}, headers=headers or s.h)
    assert r.status_code == 201, r.text
    return r.json()


def _text(resp) -> str:
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf" and resp.content[:5] == b"%PDF-"
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(resp.content)).pages)


def _code(text: str) -> str:
    return text.split("Code :")[1].split()[0]


# ---------------- Reçus ----------------

def test_receipt_numbers_are_sequential_per_school_and_independent(client, make_tenant, make_user, auth_headers):
    a = _school(client, make_tenant, make_user, auth_headers)
    b = _school(client, make_tenant, make_user, auth_headers)
    ia, ib = _invoice(client, a, 30000), _invoice(client, b, 30000)
    nums_a = [_pay(client, a, ia, 1000)["receipt_number"] for _ in range(3)]
    assert nums_a == [1, 2, 3]
    assert _pay(client, b, ib, 1000)["receipt_number"] == 1                                    # autre établissement : sa propre suite
    assert _pay(client, a, ia, 1000)["receipt_number"] == 4


def test_rejected_payments_do_not_burn_receipt_numbers(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _invoice(client, s, 5000)
    assert client.post(f"{API}/payments", json={"invoice_id": inv["id"], "amount": 9999, "method": "cash"}, headers=s.h).status_code == 422
    assert _pay(client, s, inv, 5000)["receipt_number"] == 1                                   # pas de trou


def test_receipt_pdf_shows_the_balance_as_it_was_at_that_payment(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _invoice(client, s, 10000)
    p1 = _pay(client, s, inv, 4000, reference="MM-77", headers=s.acc_h)
    p2 = _pay(client, s, inv, 6000)
    t1 = _text(client.get(f"{API}/payments/{p1['id']}/receipt", headers=s.acc_h))
    t2 = _text(client.get(f"{API}/payments/{p2['id']}/receipt", headers=s.h))
    assert "REÇU DE PAIEMENT" in t1 and "N° 000001" in t1 and "ZOHOUN Ada" in t1 and "6ème A" in t1
    assert "4 000 F CFA" in t1 and "MM-77" in t1 and "6 000 F CFA" in t1                      # reste à payer après le 1er paiement
    assert "N° 000002" in t2 and "Soldé" in t2                                                # le 2e solde la facture
    assert "Reste à payer" in t1 and _code(t1) != _code(t2)


def test_student_payment_list_carries_receipt_numbers(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _invoice(client, s, 10000)
    _pay(client, s, inv, 1000)
    _pay(client, s, inv, 2000)
    rows = client.get(f"{API}/students/{s.ada['id']}/payments", headers=s.acc_h).json()
    assert [r["receipt_number"] for r in rows] == [2, 1] and rows[0]["invoice_label"] == "Scolarité T1" and rows[0]["amount"] == 2000.0


def test_receipt_access_is_limited_and_isolated(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    p = _pay(client, s, _invoice(client, s), 1000)
    for h in (s.staff_h, s.teacher_h):
        assert client.get(f"{API}/payments/{p['id']}/receipt", headers=h).status_code == 403
        assert client.get(f"{API}/students/{s.ada['id']}/payments", headers=h).status_code == 403
    assert client.get(f"{API}/payments/{p['id']}/receipt", headers=other.h).status_code == 404
    assert client.get(f"{API}/payments/{p['id']}/receipt").status_code in (401, 403)
    assert client.get(f"{API}/students/{s.ada['id']}/payments", headers=other.h).json() == []


# ---------------- Vérification publique ----------------

def test_public_verification_of_a_receipt(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    p = _pay(client, s, _invoice(client, s), 2500)
    code = _code(_text(client.get(f"{API}/payments/{p['id']}/receipt", headers=s.h)))
    r = client.get(f"{API}/public/verify/{code}")                                              # SANS authentification
    assert r.status_code == 200
    d = r.json()
    assert d["valid"] is True and d["kind"] == "receipt" and d["number"] == 1 and d["student_name"] == "ZOHOUN Ada"
    assert d["details"]["Montant reçu"] == "2 500 F CFA" and d["school_name"] == s.tenant.name
    assert "matricule" not in r.text and "guardian" not in r.text and "M-001" not in r.text   # rien de superflu
    assert client.get(f"{API}/public/verify/{code}x").status_code == 404
    assert client.get(f"{API}/public/verify/{'a' * 40}").status_code == 404


def test_public_verification_is_rate_limited(client):
    codes = [client.get(f"{API}/public/verify/inconnu{i}").status_code for i in range(32)]
    assert codes[:30] == [404] * 30 and codes[30] == 429


def test_verification_codes_do_not_leak_across_schools(client, make_tenant, make_user, auth_headers):
    a = _school(client, make_tenant, make_user, auth_headers)
    b = _school(client, make_tenant, make_user, auth_headers)
    pa = _pay(client, a, _invoice(client, a), 1000)
    pb = _pay(client, b, _invoice(client, b), 1000)
    ca = _code(_text(client.get(f"{API}/payments/{pa['id']}/receipt", headers=a.h)))
    cb = _code(_text(client.get(f"{API}/payments/{pb['id']}/receipt", headers=b.h)))
    assert ca != cb
    assert client.get(f"{API}/public/verify/{ca}").json()["school_name"] == a.tenant.name
    assert client.get(f"{API}/public/verify/{cb}").json()["school_name"] == b.tenant.name


# ---------------- Attestations ----------------

def test_certificate_is_issued_once_per_year_and_is_replayable(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    first = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.staff_h)
    assert first.status_code == 201 and first.json()["number"] == 1
    again = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h)
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]               # même document, même numéro
    bao = client.post(f"{API}/students", json={"first_name": "Bao", "last_name": "Agbo", "class_id": s.cls["id"]}, headers=s.h).json()
    assert client.post(f"{API}/students/{bao['id']}/certificate", headers=s.h).json()["number"] == 2
    assert len(client.get(f"{API}/students/{s.ada['id']}/certificates", headers=s.h).json()) == 1


def test_certificate_pdf_content_and_public_check(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    cert = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h).json()
    t = _text(client.get(f"{API}/certificates/{cert['id']}/pdf", headers=s.staff_h))
    assert "ATTESTATION DE SCOLARITÉ" in t and "N° 000001" in t and "ZOHOUN Ada" in t and "M-001" in t
    assert "09/04/2012" in t and "6ème A" in t and cert["academic_year"] in t
    pub = client.get(f"{API}/public/verify/{_code(t)}").json()
    assert pub["kind"] == "certificate" and pub["valid"] is True and pub["details"]["Classe"] == "6ème A"


def test_certificate_is_frozen_at_issue_time(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    cert = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h).json()
    assert client.patch(f"{API}/classes/{s.cls['id']}", json={"name": "6ème Z"}, headers=s.h).status_code in (200, 204)
    t = _text(client.get(f"{API}/certificates/{cert['id']}/pdf", headers=s.h))
    assert "6ème A" in t and "6ème Z" not in t


def test_certificate_requires_an_active_assigned_student(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    loose = client.post(f"{API}/students", json={"first_name": "Dan", "last_name": "Fado"}, headers=s.h).json()
    assert client.post(f"{API}/students/{loose['id']}/certificate", headers=s.h).status_code == 409
    client.post(f"{API}/students/{s.ada['id']}/status", json={"status": "transferred", "reason": "Départ"}, headers=s.h)
    assert client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h).status_code == 409
    assert client.post(f"{API}/students/00000000-0000-0000-0000-000000000000/certificate", headers=s.h).status_code == 404


def test_voiding_a_certificate_is_visible_publicly_and_audited(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    cert = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h).json()
    code = _code(_text(client.get(f"{API}/certificates/{cert['id']}/pdf", headers=s.h)))
    assert client.post(f"{API}/certificates/{cert['id']}/void", json={"reason": "Erreur de classe"}, headers=s.staff_h).status_code == 403
    assert client.post(f"{API}/certificates/{cert['id']}/void", json={"reason": "x"}, headers=s.h).status_code == 422
    ok = client.post(f"{API}/certificates/{cert['id']}/void", json={"reason": "Erreur de classe"}, headers=s.h)
    assert ok.status_code == 200 and ok.json()["voided_at"]
    assert client.post(f"{API}/certificates/{cert['id']}/void", json={"reason": "Encore une fois"}, headers=s.h).status_code == 409
    pub = client.get(f"{API}/public/verify/{code}").json()
    assert pub["valid"] is False and pub["voided_on"] == str(TODAY)
    assert "DOCUMENT ANNULÉ" in _text(client.get(f"{API}/certificates/{cert['id']}/pdf", headers=s.h))
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        actions = sorted(db.execute(select(AuditLog.action).where(AuditLog.action.like("certificate.%"))).scalars())
        assert actions == ["certificate.issued", "certificate.voided"]
    finally:
        db.close()


def test_certificate_roles_and_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    for h in (s.acc_h, s.teacher_h):
        assert client.post(f"{API}/students/{s.ada['id']}/certificate", headers=h).status_code == 403
    cert = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h).json()
    assert client.get(f"{API}/certificates/{cert['id']}/pdf", headers=other.h).status_code == 404
    assert client.post(f"{API}/students/{s.ada['id']}/certificate", headers=other.h).status_code == 404
    assert client.get(f"{API}/students/{s.ada['id']}/certificates", headers=other.h).status_code == 404


# ---------------- Parents ----------------

def _parent(client, make_user, auth_headers, s, child):
    u, pwd = make_user(tenant=s.tenant, role=UserRole.PARENT)
    r = client.post(f"{API}/guardian-links", json={"parent_user_id": str(u.id), "student_id": child["id"], "relationship_label": "Mère"}, headers=s.h)
    assert r.status_code == 201, r.text
    return auth_headers(u, pwd)


def test_a_parent_gets_only_their_own_childs_documents(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    bao = client.post(f"{API}/students", json={"first_name": "Bao", "last_name": "Agbo", "class_id": s.cls["id"]}, headers=s.h).json()
    mine, theirs = _parent(client, make_user, auth_headers, s, s.ada), _parent(client, make_user, auth_headers, s, bao)
    pay = _pay(client, s, _invoice(client, s), 1000)
    cert = client.post(f"{API}/students/{s.ada['id']}/certificate", headers=s.h).json()
    ada = s.ada["id"]
    assert "N° 000001" in _text(client.get(f"{API}/children/{ada}/payments/{pay['id']}/receipt", headers=mine))
    assert "ZOHOUN" in _text(client.get(f"{API}/children/{ada}/certificates/{cert['id']}/pdf", headers=mine))
    assert [p["receipt_number"] for p in client.get(f"{API}/children/{ada}/payments", headers=mine).json()] == [1]
    assert len(client.get(f"{API}/children/{ada}/certificates", headers=mine).json()) == 1
    # L'autre parent : 404 partout (on ne confirme même pas l'existence)
    for url in (f"/children/{ada}/payments", f"/children/{ada}/certificates", f"/children/{ada}/payments/{pay['id']}/receipt",
                f"/children/{ada}/certificates/{cert['id']}/pdf"):
        assert client.get(f"{API}{url}", headers=theirs).status_code == 404, url
    # Son propre enfant mais le document d'un autre élève : 404
    assert client.get(f"{API}/children/{bao['id']}/payments/{pay['id']}/receipt", headers=theirs).status_code == 404
    assert client.get(f"{API}/children/{bao['id']}/certificates/{cert['id']}/pdf", headers=theirs).status_code == 404
