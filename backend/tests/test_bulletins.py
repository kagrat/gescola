import base64
import io

import pypdf
from PIL import Image

from app.models.user import UserRole
from app.services.bulletin_pdf import _image
from app.services.results_service import competition_ranks, weighted_general_average


def _pdf_text(response) -> str:
    reader = pypdf.PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


def _png_uri(color=(10, 30, 120, 255), size=(40, 20)) -> str:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


class School:
    """Établissement de test : direction, censeur, professeur principal, 3 élèves
    en 6ème A, deux matières (Maths coef 4, Français coef 2) et des notes."""


def _school(client, make_tenant, make_user, auth_headers, *, lock=True, with_head_teacher=True):
    s = School()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN, full_name="M. Directeur")
    s.admin_h = auth_headers(s.admin, pwd)
    s.censor, pwd_c = make_user(tenant=s.tenant, role=UserRole.CENSOR, full_name="Mme Censeur")
    s.censor_h = auth_headers(s.censor, pwd_c)
    s.teacher, pwd_t = make_user(tenant=s.tenant, role=UserRole.TEACHER)
    s.teacher_h = auth_headers(s.teacher, pwd_t)
    s.cls = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème", "cycle": "secondaire"}, headers=s.admin_h).json()
    s.maths = client.post("/api/v1/subjects", json={"name": "Mathématiques", "default_coefficient": 4}, headers=s.admin_h).json()
    s.french = client.post("/api/v1/subjects", json={"name": "Français", "default_coefficient": 2}, headers=s.admin_h).json()
    s.students = {}
    scores = {"A": (16, 10), "B": (12, 14), "C": (12, 14)}
    for key, (m, f) in scores.items():
        st = client.post(
            "/api/v1/students",
            json={"first_name": f"Prénom{key}", "last_name": f"Nom{key}", "class_id": s.cls["id"], "matricule": f"M-{key}",
                  "gender": "female", "date_of_birth": "2012-04-05"},
            headers=s.admin_h,
        ).json()
        s.students[key] = st
        for subject, value in ((s.maths, m), (s.french, f)):
            client.post("/api/v1/grades", json={"student_id": st["id"], "subject_id": subject["id"], "term": "T1",
                                                "evaluation_label": "D1", "value": value}, headers=s.admin_h)
        if lock:
            client.post(f"/api/v1/students/{st['id']}/grades/lock?term=T1", headers=s.admin_h)
    if with_head_teacher:
        r = client.patch(f"/api/v1/classes/{s.cls['id']}", json={"head_teacher_id": str(s.teacher.id)}, headers=s.admin_h)
        assert r.status_code == 200
    return s


def _generate(client, s, headers=None):
    return client.post("/api/v1/report-cards/generate", json={"class_id": s.cls["id"], "term": "T1"}, headers=headers or s.admin_h)


def _cards(client, s, headers=None):
    return {c["student_name"].split()[0]: c for c in client.get("/api/v1/report-cards", headers=headers or s.admin_h).json()}


# ---------------- Calculs ----------------

def test_competition_ranks_share_rank_on_ties():
    assert competition_ranks({"a": 14.0, "b": 12.0, "c": 12.0, "d": 10.0}) == {"a": 1, "b": 2, "c": 2, "d": 4}
    assert competition_ranks({}) == {}


def test_general_average_uses_subject_coefficients_not_evaluation_counts():
    a, b = "subject-a", "subject-b"
    assert weighted_general_average({a: 12.0, b: 16.0}, {a: 4.0, b: 3.0}) == 13.71
    assert weighted_general_average({a: 12.0}, {a: 0.0}) is None  # coefficient nul : matière ignorée


def test_generate_computes_averages_ranks_and_class_stats(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    resp = _generate(client, s)
    assert resp.status_code == 200 and resp.json() == {"created": 3, "updated": 0, "skipped_published": 0}

    cards = _cards(client, s)
    a = client.get(f"/api/v1/report-cards/{cards['NOMA']['id']}", headers=s.admin_h).json()
    assert a["general_average"] == 14.0 and a["rank"] == 1 and a["class_size"] == 3
    snap = a["snapshot"]
    assert snap["general"]["class_average"] == 13.11           # (14 + 12,67 + 12,67) / 3
    assert snap["general"]["highest"]["name"] == "Mathématiques" and snap["general"]["highest"]["value"] == 16.0
    assert snap["general"]["lowest"]["name"] == "Français"
    assert snap["total_coefficients"] == 6
    maths = next(r for r in snap["subjects"] if r["name"] == "Mathématiques")
    assert maths["coefficient"] == 4 and maths["average"] == 16.0 and maths["rank"] == 1 and maths["class_average"] == 13.33
    # ex æquo : B et C partagent le rang 2
    assert cards["NOMB"]["rank"] == 2 and cards["NOMC"]["rank"] == 2
    # snapshot : identité de l'élève
    assert snap["student"]["name"] == "NOMA PrénomA" and snap["student"]["matricule"] == "M-A"


def test_regenerate_updates_drafts_and_never_overwrites_published(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _generate(client, s)
    cards = _cards(client, s)
    assert client.post(f"/api/v1/report-cards/{cards['NOMA']['id']}/publish", headers=s.admin_h).status_code == 200

    again = _generate(client, s).json()
    assert again == {"created": 0, "updated": 2, "skipped_published": 1}


# ---------------- Publication ----------------

def test_publish_requires_all_grades_locked(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, lock=False)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    resp = client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h)
    assert resp.status_code == 409 and "verrouillées" in resp.json()["detail"]

    client.post(f"/api/v1/students/{s.students['A']['id']}/grades/lock?term=T1", headers=s.admin_h)
    assert client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h).status_code == 200


def test_publish_refreshes_stale_figures_and_unpublish_reopens(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, lock=False)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    grades = client.get(f"/api/v1/students/{s.students['A']['id']}/grades?term=T1", headers=s.admin_h).json()
    maths_grade = next(g for g in grades if g["subject_id"] == s.maths["id"])
    client.patch(f"/api/v1/grades/{maths_grade['id']}", json={"value": 20}, headers=s.admin_h)  # après génération
    client.post(f"/api/v1/students/{s.students['A']['id']}/grades/lock?term=T1", headers=s.admin_h)

    published = client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h).json()
    assert published["status"] == "published" and published["published_at"]
    assert published["general_average"] == round((20 * 4 + 10 * 2) / 6, 2)  # 16,67 : pas la valeur périmée 14,0

    # publier deux fois : refusé ; un bulletin publié n'est plus modifiable
    assert client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h).status_code == 409
    assert client.patch(f"/api/v1/report-cards/{card['id']}", json={"principal_comment": "x"}, headers=s.admin_h).status_code == 409

    reopened = client.post(f"/api/v1/report-cards/{card['id']}/unpublish", headers=s.admin_h).json()
    assert reopened["status"] == "draft" and reopened["published_at"] is None
    assert client.post(f"/api/v1/report-cards/{card['id']}/unpublish", headers=s.admin_h).status_code == 409


def test_cannot_publish_card_without_any_grade(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    empty = client.post("/api/v1/students", json={"first_name": "Zoé", "last_name": "Vide", "class_id": s.cls["id"]}, headers=s.admin_h).json()
    _generate(client, s)
    card = next(c for c in client.get(f"/api/v1/report-cards?student_id={empty['id']}", headers=s.admin_h).json())
    assert card["general_average"] is None and card["rank"] is None
    assert client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h).status_code == 409


# ---------------- Permissions et visibilité ----------------

def test_roles_and_visibility(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other_teacher, pwd_o = make_user(tenant=s.tenant, role=UserRole.TEACHER)
    staff, pwd_s = make_user(tenant=s.tenant, role=UserRole.STAFF)
    _generate(client, s)
    cards = _cards(client, s)
    card_id = cards["NOMA"]["id"]

    # Le professeur principal voit les brouillons de SA classe ; un autre enseignant : rien (404).
    assert len(client.get("/api/v1/report-cards", headers=s.teacher_h).json()) == 3
    other_h = auth_headers(other_teacher, pwd_o)
    assert client.get("/api/v1/report-cards", headers=other_h).json() == []
    assert client.get(f"/api/v1/report-cards/{card_id}", headers=other_h).status_code == 404

    # Le secrétariat ne voit que les bulletins publiés.
    staff_h = auth_headers(staff, pwd_s)
    assert client.get("/api/v1/report-cards", headers=staff_h).json() == []
    client.post(f"/api/v1/report-cards/{card_id}/publish", headers=s.censor_h)
    assert len(client.get("/api/v1/report-cards", headers=staff_h).json()) == 1

    # Générer / publier : réservés à Direction, Censeur, Fondateur.
    assert _generate(client, s, s.teacher_h).status_code == 403
    assert _generate(client, s, staff_h).status_code == 403
    assert client.post(f"/api/v1/report-cards/{cards['NOMB']['id']}/publish", headers=s.teacher_h).status_code == 403

    # Comptable et surveillant : aucun accès.
    for role in (UserRole.ACCOUNTANT, UserRole.SUPERVISOR, UserRole.PARENT):
        user, pwd = make_user(tenant=s.tenant, role=role)
        assert client.get("/api/v1/report-cards", headers=auth_headers(user, pwd)).status_code == 403


def test_head_teacher_writes_comment_but_not_council_decision(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _generate(client, s)
    card_id = _cards(client, s)["NOMA"]["id"]

    ok = client.patch(f"/api/v1/report-cards/{card_id}", json={"principal_comment": "  Élève sérieux.  "}, headers=s.teacher_h)
    assert ok.status_code == 200 and ok.json()["principal_comment"] == "Élève sérieux."
    denied = client.patch(f"/api/v1/report-cards/{card_id}", json={"council_decision": "Admis"}, headers=s.teacher_h)
    assert denied.status_code == 403
    decided = client.patch(f"/api/v1/report-cards/{card_id}", json={"council_decision": "Félicitations"}, headers=s.censor_h)
    assert decided.status_code == 200 and decided.json()["council_decision"] == "Félicitations"


def test_cross_tenant_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _generate(client, s)
    card_id = _cards(client, s)["NOMA"]["id"]
    other_tenant = make_tenant()
    other_admin, pwd = make_user(tenant=other_tenant, role=UserRole.SCHOOL_ADMIN)
    other_h = auth_headers(other_admin, pwd)
    assert client.get("/api/v1/report-cards", headers=other_h).json() == []
    assert client.get(f"/api/v1/report-cards/{card_id}", headers=other_h).status_code == 404
    assert client.get(f"/api/v1/report-cards/{card_id}/pdf", headers=other_h).status_code == 404
    assert client.post(f"/api/v1/report-cards/{card_id}/publish", headers=other_h).status_code == 404
    assert client.post("/api/v1/report-cards/generate", json={"class_id": s.cls["id"], "term": "T1"}, headers=other_h).status_code == 404


def test_parent_sees_only_published_report_cards_of_own_child(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    parent, pwd = make_user(tenant=s.tenant, role=UserRole.PARENT)
    parent_h = auth_headers(parent, pwd)
    client.post("/api/v1/guardian-links", json={"parent_user_id": str(parent.id), "student_id": s.students["A"]["id"], "relationship_label": "Mère"}, headers=s.admin_h)
    _generate(client, s)
    cards = _cards(client, s)
    a, b = s.students["A"]["id"], s.students["B"]["id"]

    assert client.get(f"/api/v1/children/{a}/report-cards", headers=parent_h).json() == []          # brouillon : invisible
    assert client.get(f"/api/v1/children/{a}/report-cards/{cards['NOMA']['id']}/pdf", headers=parent_h).status_code == 404
    client.post(f"/api/v1/report-cards/{cards['NOMA']['id']}/publish", headers=s.admin_h)
    client.post(f"/api/v1/report-cards/{cards['NOMB']['id']}/publish", headers=s.admin_h)

    listed = client.get(f"/api/v1/children/{a}/report-cards", headers=parent_h).json()
    assert len(listed) == 1 and listed[0]["status"] == "published"
    pdf = client.get(f"/api/v1/children/{a}/report-cards/{cards['NOMA']['id']}/pdf", headers=parent_h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # enfant non rattaché, ou bulletin d'un autre enfant : 404
    assert client.get(f"/api/v1/children/{b}/report-cards", headers=parent_h).status_code == 404
    assert client.get(f"/api/v1/children/{a}/report-cards/{cards['NOMB']['id']}/pdf", headers=parent_h).status_code == 404


# ---------------- PDF et réglages d'affichage ----------------

def test_pdf_content_and_configurable_sections(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.patch("/api/v1/establishment/settings", json={"bulletin_motto": "Discipline - Travail - Réussite", "bulletin_place": "Cotonou",
                                                          "academic_year": "2026-2027"}, headers=s.admin_h)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    client.patch(f"/api/v1/report-cards/{card['id']}", json={"principal_comment": "Excellent trimestre.", "council_decision": "Félicitations"}, headers=s.admin_h)

    full = client.get(f"/api/v1/report-cards/{card['id']}/pdf", headers=s.admin_h)
    assert full.status_code == 200 and full.headers["content-type"] == "application/pdf" and full.content.startswith(b"%PDF")
    text = _pdf_text(full)
    for expected in ("BULLETIN DE NOTES", "1er Trimestre", "2026-2027", "NOMA PrénomA", "M-A", "Mathématiques", "Total des coefficients",
                     "SYNTHÈSE GÉNÉRALE", "VIE SCOLAIRE", "APPRÉCIATION GÉNÉRALE DU PROFESSEUR PRINCIPAL", "Excellent trimestre.",
                     "Félicitations", "Fait à Cotonou", "Le Censeur", "Le Directeur", "Le Professeur principal", "BROUILLON",
                     "Discipline - Travail - Réussite", "14,00"):
        assert expected in text, f"« {expected} » absent du PDF"

    # L'établissement masque la vie scolaire et les appréciations, et retire la signature du professeur principal.
    client.patch("/api/v1/establishment/settings", json={"bulletin_show_appreciations": False, "bulletin_show_school_life": False,
                                                          "bulletin_show_head_teacher_signature": False}, headers=s.admin_h)
    minimal = _pdf_text(client.get(f"/api/v1/report-cards/{card['id']}/pdf", headers=s.admin_h))
    for hidden in ("VIE SCOLAIRE", "Appréciation du professeur", "APPRÉCIATION GÉNÉRALE", "Excellent trimestre.", "Le Professeur principal"):
        assert hidden not in minimal, f"« {hidden} » devrait être masqué"
    for still_there in ("SYNTHÈSE GÉNÉRALE", "Le Censeur", "Le Directeur", "Félicitations", "Total des coefficients"):
        assert still_there in minimal


def test_published_pdf_has_no_draft_watermark(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h)
    assert "BROUILLON" not in _pdf_text(client.get(f"/api/v1/report-cards/{card['id']}/pdf", headers=s.admin_h))


def test_head_teacher_signature_only_when_a_head_teacher_is_assigned(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, with_head_teacher=False)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    assert "Le Professeur principal" not in _pdf_text(client.get(f"/api/v1/report-cards/{card['id']}/pdf", headers=s.admin_h))


def test_signers_director_falls_back_to_founder_and_censor_is_included(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    founder, pwd_f = make_user(tenant=tenant, role=UserRole.FOUNDER, full_name="M. Fondateur")
    censor, _ = make_user(tenant=tenant, role=UserRole.CENSOR, full_name="Mme Censeur")
    h = auth_headers(founder, pwd_f)
    cls = client.post("/api/v1/classes", json={"name": "CM2", "level": "CM2"}, headers=h).json()
    subject = client.post("/api/v1/subjects", json={"name": "Calcul"}, headers=h).json()
    st = client.post("/api/v1/students", json={"first_name": "Léa", "last_name": "Test", "class_id": cls["id"]}, headers=h).json()
    client.post("/api/v1/grades", json={"student_id": st["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D", "value": 15}, headers=h)
    client.post("/api/v1/report-cards/generate", json={"class_id": cls["id"], "term": "T1"}, headers=h)
    card = client.get("/api/v1/report-cards", headers=h).json()[0]
    signers = client.get(f"/api/v1/report-cards/{card['id']}", headers=h).json()["snapshot"]["signers"]
    assert signers["director"]["name"] == founder.full_name        # pas de Direction : le Fondateur signe
    assert signers["censor"]["name"] == censor.full_name
    assert signers["head_teacher"] is None


def test_pdf_image_helper_ignores_unusable_images():
    assert _image(_png_uri(), 20, 20) is not None
    assert _image("data:image/svg+xml;base64," + base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg'/>").decode(), 20, 20) is None
    assert _image("data:image/png;base64,@@@@", 20, 20) is None
    assert _image(None, 20, 20) is None


def test_pdf_still_renders_with_signature_and_stamp_images(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    # Images distinctes : reportlab n'embarque qu'une fois deux images identiques.
    images = {
        "admin": (_png_uri((200, 0, 0, 255), (40, 20)), _png_uri((0, 200, 0, 255), (30, 30))),
        "censor": (_png_uri((0, 0, 200, 255), (50, 20)), _png_uri((200, 200, 0, 255), (32, 32))),
    }
    for headers, (signature, stamp) in ((s.admin_h, images["admin"]), (s.censor_h, images["censor"])):
        assert client.patch("/api/v1/users/me/signature", json={"signature_base64": signature, "stamp_base64": stamp}, headers=headers).status_code == 200
    client.patch("/api/v1/establishment/settings", json={"logo_base64": _png_uri((0, 200, 200, 255), (60, 60))}, headers=s.admin_h)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    with_images = client.get(f"/api/v1/report-cards/{card['id']}/pdf", headers=s.admin_h)
    assert with_images.status_code == 200 and with_images.content.startswith(b"%PDF")
    reader = pypdf.PdfReader(io.BytesIO(with_images.content))
    assert sum(len(page.images) for page in reader.pages) >= 5   # logo + signature/cachet du directeur et du censeur


# ---------------- Vie scolaire ----------------

def test_school_life_counts_respect_configured_term_period(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    sid = s.students["A"]["id"]
    for day, status, justified in [("2026-10-05", "absent", False), ("2026-10-06", "absent", True), ("2026-10-07", "late", False),
                                   ("2026-10-08", "present", False), ("2027-02-01", "absent", False)]:  # dernier : hors trimestre
        client.post("/api/v1/attendance", json={"student_id": sid, "date": day, "status": status, "justified": justified}, headers=s.admin_h)
    client.post("/api/v1/incidents", json={"student_id": sid, "occurred_at": "2026-10-09T10:00:00+00:00", "category": "behavior",
                                            "severity": "minor", "description": "Bavardage."}, headers=s.admin_h)
    client.post("/api/v1/incidents", json={"student_id": sid, "occurred_at": "2027-03-09T10:00:00+00:00", "category": "behavior",
                                            "severity": "minor", "description": "Hors période."}, headers=s.admin_h)
    resp = client.patch("/api/v1/establishment/settings", json={"academic_year": "2026-2027",
                        "term_periods": {"T1": {"start": "2026-09-15", "end": "2026-12-20"}}}, headers=s.admin_h)
    assert resp.status_code == 200 and resp.json()["term_periods"]["T1"]["start"] == "2026-09-15"

    _generate(client, s)
    card = client.get(f"/api/v1/report-cards?student_id={sid}", headers=s.admin_h).json()[0]
    life = client.get(f"/api/v1/report-cards/{card['id']}", headers=s.admin_h).json()["snapshot"]["school_life"]
    assert (life["justified_absences"], life["unjustified_absences"], life["lateness"], life["incidents"]) == (1, 1, 1, 1)
    assert life["period_configured"] is True


# ---------------- Appréciations de matière ----------------

def test_teacher_writes_subject_appreciation_which_appears_on_report_card(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post("/api/v1/teacher-assignments", json={"teacher_id": str(s.teacher.id), "class_id": s.cls["id"], "subject_id": s.maths["id"]}, headers=s.admin_h)
    body = {"student_id": s.students["A"]["id"], "subject_id": s.maths["id"], "term": "T1", "text": "  Très bon niveau.  "}
    assert client.put("/api/v1/appreciations", json=body, headers=s.teacher_h).status_code == 200
    assert client.put("/api/v1/appreciations", json={**body, "text": "Excellent."}, headers=s.teacher_h).status_code == 200  # mise à jour, pas doublon

    listed = client.get(f"/api/v1/appreciations?class_id={s.cls['id']}&subject_id={s.maths['id']}&term=T1", headers=s.teacher_h).json()
    assert len(listed) == 1 and listed[0]["text"] == "Excellent."

    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    snap = client.get(f"/api/v1/report-cards/{card['id']}", headers=s.admin_h).json()["snapshot"]
    assert next(r for r in snap["subjects"] if r["name"] == "Mathématiques")["appreciation"] == "Excellent."
    assert "Excellent." in _pdf_text(client.get(f"/api/v1/report-cards/{card['id']}/pdf", headers=s.admin_h))

    # texte vide = effacement
    client.put("/api/v1/appreciations", json={**body, "text": ""}, headers=s.teacher_h)
    assert client.get(f"/api/v1/appreciations?class_id={s.cls['id']}&subject_id={s.maths['id']}&term=T1", headers=s.teacher_h).json() == []


def test_appreciation_respects_teacher_assignment_and_roles(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post("/api/v1/teacher-assignments", json={"teacher_id": str(s.teacher.id), "class_id": s.cls["id"], "subject_id": s.maths["id"]}, headers=s.admin_h)
    outside = {"student_id": s.students["A"]["id"], "subject_id": s.french["id"], "term": "T1", "text": "Hors affectation"}
    assert client.put("/api/v1/appreciations", json=outside, headers=s.teacher_h).status_code == 403
    assert client.put("/api/v1/appreciations", json={**outside, "term": "T9"}, headers=s.teacher_h).status_code == 422
    assert client.put("/api/v1/appreciations", json={**outside, "text": "x" * 301}, headers=s.admin_h).status_code == 422
    supervisor, pwd = make_user(tenant=s.tenant, role=UserRole.SUPERVISOR)
    assert client.put("/api/v1/appreciations", json=outside, headers=auth_headers(supervisor, pwd)).status_code == 403


# ---------------- Élèves, classes, réglages, enseignants ----------------

def test_student_administrative_fields_and_matricule_uniqueness(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    dup = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y", "matricule": "M-A"}, headers=s.admin_h)
    assert dup.status_code == 409
    fresh = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y", "matricule": " M-Z "}, headers=s.admin_h).json()
    assert fresh["matricule"] == "M-Z" and fresh["is_repeater"] is False and fresh["gender"] is None
    upd = client.patch(f"/api/v1/students/{fresh['id']}", json={"gender": "male", "is_repeater": True}, headers=s.admin_h).json()
    assert upd["gender"] == "male" and upd["is_repeater"] is True
    assert client.patch(f"/api/v1/students/{fresh['id']}", json={"matricule": "M-A"}, headers=s.admin_h).status_code == 409
    # deux établissements peuvent réutiliser le même matricule
    other = make_tenant()
    other_admin, pwd = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    assert client.post("/api/v1/students", json={"first_name": "A", "last_name": "B", "matricule": "M-A"}, headers=auth_headers(other_admin, pwd)).status_code == 201


def test_head_teacher_assignment_rules(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, with_head_teacher=False)
    staff, pwd_s = make_user(tenant=s.tenant, role=UserRole.STAFF)
    accountant, _ = make_user(tenant=s.tenant, role=UserRole.ACCOUNTANT)
    staff_h = auth_headers(staff, pwd_s)
    url = f"/api/v1/classes/{s.cls['id']}"
    assert client.patch(url, json={"head_teacher_id": str(s.teacher.id)}, headers=staff_h).status_code == 403   # secrétariat : non
    assert client.patch(url, json={"name": "6ème A bis"}, headers=staff_h).status_code == 200                    # mais il peut renommer
    assert client.patch(url, json={"head_teacher_id": str(accountant.id)}, headers=s.censor_h).status_code == 404  # pas un enseignant
    ok = client.patch(url, json={"head_teacher_id": str(s.teacher.id)}, headers=s.censor_h)
    assert ok.status_code == 200 and ok.json()["head_teacher_id"] == str(s.teacher.id)
    assert client.patch(url, json={"head_teacher_id": None}, headers=s.censor_h).json()["head_teacher_id"] is None


def test_teachers_list_available_to_censor_but_not_staff(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    staff, pwd = make_user(tenant=s.tenant, role=UserRole.STAFF)
    listed = client.get("/api/v1/teachers", headers=s.censor_h)
    assert listed.status_code == 200 and [t["id"] for t in listed.json()] == [str(s.teacher.id)]
    assert set(listed.json()[0]) == {"id", "full_name"}    # aucune autre donnée (e-mail, etc.)
    assert client.get("/api/v1/teachers", headers=auth_headers(staff, pwd)).status_code == 403


def test_bulletin_settings_validation_and_persistence(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    url = "/api/v1/establishment/settings"
    assert client.patch(url, json={"academic_year": "2026-2028"}, headers=s.admin_h).status_code == 422
    assert client.patch(url, json={"academic_year": "26-27"}, headers=s.admin_h).status_code == 422
    assert client.patch(url, json={"term_periods": {"T1": {"start": "2026-12-01", "end": "2026-09-01"}}}, headers=s.admin_h).status_code == 422
    assert client.patch(url, json={"term_periods": {"T4": {"start": "2026-09-01", "end": "2026-12-01"}}}, headers=s.admin_h).status_code == 422
    body = client.get(url, headers=s.admin_h).json()
    assert body["bulletin_show_appreciations"] is True and body["bulletin_show_school_life"] is True
    assert body["bulletin_show_head_teacher_signature"] is True and body["academic_year"] is None

    ok = client.patch(url, json={"bulletin_motto": "  Travail  ", "bulletin_show_school_life": False}, headers=s.admin_h).json()
    assert ok["bulletin_motto"] == "Travail" and ok["bulletin_show_school_life"] is False
    assert client.patch(url, json={"bulletin_motto": "   "}, headers=s.admin_h).json()["bulletin_motto"] is None
    assert client.patch(url, json={"bulletin_show_school_life": None}, headers=s.admin_h).json()["bulletin_show_school_life"] is False  # null ignoré
    assert client.patch(url, json={"bulletin_motto": "x"}, headers=s.teacher_h).status_code == 403


def test_bulletin_actions_are_audited(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _generate(client, s)
    card = _cards(client, s)["NOMA"]
    client.patch(f"/api/v1/report-cards/{card['id']}", json={"principal_comment": "Bien"}, headers=s.admin_h)
    client.post(f"/api/v1/report-cards/{card['id']}/publish", headers=s.admin_h)
    client.post(f"/api/v1/report-cards/{card['id']}/unpublish", headers=s.admin_h)
    actions = {log["action"] for log in client.get("/api/v1/audit-logs", headers=s.admin_h).json()}
    assert {"report_card.generated", "report_card.remarks_updated", "report_card.published", "report_card.unpublished"} <= actions


def test_generate_rejects_invalid_input(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    assert client.post("/api/v1/report-cards/generate", json={"class_id": s.cls["id"], "term": "T7"}, headers=s.admin_h).status_code == 422
    empty_class = client.post("/api/v1/classes", json={"name": "Vide", "level": "X"}, headers=s.admin_h).json()
    assert client.post("/api/v1/report-cards/generate", json={"class_id": empty_class["id"], "term": "T1"}, headers=s.admin_h).status_code == 409


def test_subject_coefficient_can_be_corrected_and_drives_the_average(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    url = f"/api/v1/subjects/{s.maths['id']}"
    assert client.patch(url, json={"default_coefficient": 0}, headers=s.admin_h).status_code == 422
    assert client.patch(url, json={"default_coefficient": 21}, headers=s.admin_h).status_code == 422
    accountant, pwd = make_user(tenant=s.tenant, role=UserRole.ACCOUNTANT)
    assert client.patch(url, json={"default_coefficient": 2}, headers=auth_headers(accountant, pwd)).status_code == 403
    assert client.patch(f"/api/v1/subjects/{s.french['id']}", json={"name": "  "}, headers=s.admin_h).status_code == 422

    # Maths coef 4 -> 1 : élève A = (16*1 + 10*2) / 3 = 12,00 au lieu de 14,00
    assert client.patch(url, json={"default_coefficient": 1}, headers=s.censor_h).json()["default_coefficient"] == 1
    avg = client.get(f"/api/v1/students/{s.students['A']['id']}/average?term=T1", headers=s.admin_h).json()
    assert avg["general_average"] == 12.0
    other = make_tenant()
    other_admin, pwd_o = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    assert client.patch(url, json={"default_coefficient": 3}, headers=auth_headers(other_admin, pwd_o)).status_code == 404
