import json
from datetime import datetime, timedelta, timezone

from app.models.user import UserRole


class World:
    """Établissement de test : un élève en 6ème A avec deux parents, un élève en 5ème B avec un parent,
    un parent non rattaché, et toute l'équipe. Les connexions (`w.<nom>_h`) sont faites à la demande :
    se connecter coûte un hachage de mot de passe, inutile pour les personnes qu'un test n'utilise pas."""

    def __init__(self, auth_headers):
        self._auth_headers, self._passwords, self._headers = auth_headers, {}, {}

    def __getattr__(self, name):
        if name.endswith("_h") and name[:-2] in self._passwords:
            key = name[:-2]
            if key not in self._headers:
                self._headers[key] = self._auth_headers(getattr(self, key), self._passwords[key])
            return self._headers[key]
        raise AttributeError(name)


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _world(client, make_tenant, make_user, auth_headers) -> World:
    w = World(auth_headers)
    w.tenant = make_tenant()

    def add(key, role, name):
        user, pwd = make_user(tenant=w.tenant, role=role, full_name=name)
        setattr(w, key, user)
        w._passwords[key] = pwd

    add("direction", UserRole.SCHOOL_ADMIN, "Mme Direction")
    add("founder", UserRole.FOUNDER, "M. Fondateur")
    add("censor", UserRole.CENSOR, "M. Censeur")
    add("supervisor", UserRole.SUPERVISOR, "M. Surveillant")
    add("staff", UserRole.STAFF, "Mme Secrétaire")
    add("accountant", UserRole.ACCOUNTANT, "M. Comptable")
    add("teacher_a", UserRole.TEACHER, "M. Prof A")                # enseigne en 6ème A
    add("teacher_b", UserRole.TEACHER, "M. Prof B")                # enseigne en 5ème B seulement
    add("teacher_none", UserRole.TEACHER, "M. Prof Sans Classe")
    add("parent1", UserRole.PARENT, "Mme Parent Un")
    add("parent2", UserRole.PARENT, "M. Parent Deux")
    add("parent3", UserRole.PARENT, "Mme Parent Trois")
    add("parent4", UserRole.PARENT, "M. Parent Étranger")           # rattaché à personne

    d = w.direction_h
    w.class_a = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème"}, headers=d).json()
    w.class_b = client.post("/api/v1/classes", json={"name": "5ème B", "level": "5ème"}, headers=d).json()
    w.maths = client.post("/api/v1/subjects", json={"name": "Mathématiques"}, headers=d).json()
    for teacher, cls in ((w.teacher_a, w.class_a), (w.teacher_b, w.class_b)):
        r = client.post("/api/v1/teacher-assignments", json={"teacher_id": str(teacher.id), "class_id": cls["id"], "subject_id": w.maths["id"]}, headers=d)
        assert r.status_code == 201
    w.kid_a = client.post("/api/v1/students", json={"first_name": "Aya", "last_name": "Diallo", "class_id": w.class_a["id"]}, headers=d).json()
    w.kid_b = client.post("/api/v1/students", json={"first_name": "Koffi", "last_name": "Mensah", "class_id": w.class_b["id"]}, headers=d).json()
    for parent, kid, label in ((w.parent1, w.kid_a, "Mère"), (w.parent2, w.kid_a, "Père"), (w.parent3, w.kid_b, "Mère")):
        r = client.post("/api/v1/guardian-links", json={"parent_user_id": str(parent.id), "student_id": kid["id"], "relationship_label": label}, headers=d)
        assert r.status_code == 201
    return w


def _new_thread(client, headers, student, **overrides):
    body = {"student_id": student["id"], "subject": "Point sur le trimestre", "body": "Bonjour, pouvons-nous faire le point ?"}
    body.update(overrides)
    return client.post("/api/v1/messages/threads", json=body, headers=headers)


# ======================= Personnel → parents =======================

def test_staff_writes_to_all_guardians_by_default_and_unread_state_is_correct(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    resp = _new_thread(client, w.censor_h, w.kid_a)
    assert resp.status_code == 201
    thread = resp.json()
    assert {p["full_name"] for p in thread["participants"]} == {"M. Censeur", "Mme Parent Un", "M. Parent Deux"}
    assert thread["student_name"] == "DIALLO Aya" and len(thread["messages"]) == 1
    assert thread["messages"][0]["sender_id"] == str(w.censor.id) and thread["messages"][0]["sender_role"] == "censor"

    for headers, others in ((w.parent1_h, ["M. Censeur", "M. Parent Deux"]), (w.parent2_h, ["M. Censeur", "Mme Parent Un"])):
        assert client.get("/api/v1/messages/unread-count", headers=headers).json() == {"unread": 1}
        listed = client.get("/api/v1/messages/threads", headers=headers).json()
        assert len(listed) == 1 and listed[0]["unread"] is True
        assert listed[0]["participant_names"] == others          # « avec qui », sans soi-même
    assert client.get("/api/v1/messages/unread-count", headers=w.censor_h).json() == {"unread": 0}   # son propre message ne compte pas
    assert client.get("/api/v1/messages/threads?unread=true", headers=w.censor_h).json() == []


def test_explicit_recipients_must_be_guardians_of_that_student(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    only_p1 = _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.parent1.id)])
    assert only_p1.status_code == 201
    assert {p["full_name"] for p in only_p1.json()["participants"]} == {"M. Censeur", "Mme Parent Un"}
    assert client.get("/api/v1/messages/threads", headers=w.parent2_h).json() == []                 # non destinataire : rien

    assert _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.parent3.id)]).status_code == 400     # parent d'un autre élève
    assert _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.teacher_a.id)]).status_code == 400   # un enseignant n'est pas un parent
    assert _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.parent4.id)]).status_code == 400     # parent non rattaché


def test_cannot_write_about_a_student_without_active_guardians(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    orphan = client.post("/api/v1/students", json={"first_name": "Sans", "last_name": "Parent"}, headers=w.direction_h).json()
    resp = _new_thread(client, w.censor_h, orphan)
    assert resp.status_code == 409 and "parent" in resp.json()["detail"].lower()


def test_deactivated_parent_is_not_reachable(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    client.post(f"/api/v1/users/{w.parent2.id}/deactivate", headers=w.direction_h)
    thread = _new_thread(client, w.censor_h, w.kid_a).json()
    assert {p["full_name"] for p in thread["participants"]} == {"M. Censeur", "Mme Parent Un"}
    assert _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.parent2.id)]).status_code == 400
    listed = client.get(f"/api/v1/messages/guardians?student_id={w.kid_a['id']}", headers=w.censor_h).json()
    assert [g["full_name"] for g in listed] == ["Mme Parent Un"] and listed[0]["detail"] == "Mère"


def test_teacher_can_only_write_to_parents_of_their_own_classes(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    assert _new_thread(client, w.teacher_a_h, w.kid_a).status_code == 201                      # affecté à 6ème A
    for headers in (w.teacher_b_h, w.teacher_none_h):
        resp = _new_thread(client, headers, w.kid_a)
        assert resp.status_code == 403 and "vos classes" in resp.json()["detail"]
        assert client.get(f"/api/v1/messages/guardians?student_id={w.kid_a['id']}", headers=headers).status_code == 403
    # Le professeur principal d'une classe peut écrire aux parents de sa classe, même sans affectation de matière.
    assert client.patch(f"/api/v1/classes/{w.class_a['id']}", json={"head_teacher_id": str(w.teacher_none.id)}, headers=w.direction_h).status_code == 200
    assert _new_thread(client, w.teacher_none_h, w.kid_a).status_code == 201


def test_other_staff_roles_can_write_about_any_student(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    for headers in (w.direction_h, w.founder_h, w.censor_h, w.supervisor_h, w.staff_h, w.accountant_h):
        assert _new_thread(client, headers, w.kid_b).status_code == 201


def test_roles_outside_the_school_cannot_use_messaging(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    support, p = make_user(role=UserRole.SUPER_ADMIN)
    network, p2 = make_user(role=UserRole.NETWORK_ADMIN)
    for user, pwd in ((support, p), (network, p2)):
        headers = auth_headers(user, pwd)
        assert client.get("/api/v1/messages/threads", headers=headers).status_code == 403
        assert client.get("/api/v1/messages/unread-count", headers=headers).status_code == 403
        assert client.get("/api/v1/announcements", headers=headers).status_code == 403
    assert client.get("/api/v1/messages/threads").status_code == 401


# ======================= Parent → école =======================

def test_parent_contacts_are_exactly_the_childs_team(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    client.patch(f"/api/v1/classes/{w.class_a['id']}", json={"head_teacher_id": str(w.teacher_none.id)}, headers=w.direction_h)
    inactive_staff, _ = make_user(tenant=w.tenant, role=UserRole.CENSOR, full_name="M. Censeur Parti")
    client.post(f"/api/v1/users/{inactive_staff.id}/deactivate", headers=w.direction_h)

    contacts = client.get(f"/api/v1/children/{w.kid_a['id']}/contacts", headers=w.parent1_h).json()
    names = {c["full_name"]: c["detail"] for c in contacts}
    assert set(names) == {"Mme Direction", "M. Censeur", "M. Surveillant", "Mme Secrétaire", "M. Comptable", "M. Prof A", "M. Prof Sans Classe"}
    assert names["M. Prof A"] == "Mathématiques" and names["M. Prof Sans Classe"] == "Professeur principal"
    assert "M. Fondateur" not in names and "M. Prof B" not in names and "M. Censeur Parti" not in names   # pas le fondateur, ni la classe voisine, ni un compte désactivé
    assert client.get(f"/api/v1/children/{w.kid_b['id']}/contacts", headers=w.parent1_h).status_code == 404   # enfant d'un autre parent
    assert client.get(f"/api/v1/children/{w.kid_a['id']}/contacts", headers=w.censor_h).status_code == 403    # réservé aux parents


def test_parent_writes_only_to_contacts_of_their_child(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    ok = _new_thread(client, w.parent1_h, w.kid_a, recipient_user_ids=[str(w.teacher_a.id), str(w.censor.id)], subject="Devoirs")
    assert ok.status_code == 201
    assert {p["full_name"] for p in ok.json()["participants"]} == {"Mme Parent Un", "M. Prof A", "M. Censeur"}   # l'autre parent n'est PAS inclus
    assert client.get("/api/v1/messages/threads", headers=w.parent2_h).json() == []
    assert client.get("/api/v1/messages/unread-count", headers=w.teacher_a_h).json() == {"unread": 1}

    refusals = [
        (_new_thread(client, w.parent1_h, w.kid_a, recipient_user_ids=[str(w.teacher_b.id)]), 403),          # enseignant d'une autre classe
        (_new_thread(client, w.parent1_h, w.kid_a, recipient_user_ids=[str(w.founder.id)]), 403),            # le Fondateur n'est pas un contact
        (_new_thread(client, w.parent1_h, w.kid_a, recipient_user_ids=[str(w.parent3.id)]), 403),            # un autre parent
        (_new_thread(client, w.parent1_h, w.kid_a), 400),                                                    # aucun destinataire
        (_new_thread(client, w.parent1_h, w.kid_a, recipient_user_ids=[str(w.direction.id), str(w.censor.id), str(w.staff.id), str(w.accountant.id)]), 400),  # plus de 3
        (_new_thread(client, w.parent1_h, w.kid_b, recipient_user_ids=[str(w.censor.id)]), 404),             # élève d'un autre parent
        (_new_thread(client, w.parent4_h, w.kid_a, recipient_user_ids=[str(w.censor.id)]), 404),             # parent non rattaché
    ]
    for resp, expected in refusals:
        assert resp.status_code == expected, resp.text


def test_only_staff_can_send_a_convocation(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    convocation = {"kind": "convocation", "meeting_at": _iso(3), "meeting_place": "Bureau du Censeur", "subject": "Convocation"}
    assert _new_thread(client, w.parent1_h, w.kid_a, recipient_user_ids=[str(w.censor.id)], **convocation).status_code == 403
    ok = _new_thread(client, w.censor_h, w.kid_a, **convocation)
    assert ok.status_code == 201 and ok.json()["kind"] == "convocation" and ok.json()["meeting_place"] == "Bureau du Censeur"
    listed = client.get("/api/v1/messages/threads", headers=w.parent1_h).json()
    assert listed[0]["kind"] == "convocation" and listed[0]["meeting_at"] is not None


def test_convocation_and_conversation_field_rules(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    assert _new_thread(client, w.censor_h, w.kid_a, kind="convocation").status_code == 422                                  # date manquante
    assert _new_thread(client, w.censor_h, w.kid_a, kind="convocation", meeting_at=_iso(-2)).status_code == 422            # dans le passé
    assert _new_thread(client, w.censor_h, w.kid_a, meeting_at=_iso(2)).status_code == 422                                  # date sur une simple conversation
    assert _new_thread(client, w.censor_h, w.kid_a, kind="convocation", meeting_at=_iso(2)).status_code == 201


# ======================= Confidentialité : qui peut lire quoi =======================

def test_only_participants_can_read_or_write_a_thread(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    thread_id = _new_thread(client, w.teacher_a_h, w.kid_a, recipient_user_ids=[str(w.parent1.id)]).json()["id"]
    url = f"/api/v1/messages/threads/{thread_id}"
    outsiders = {
        "autre parent du même élève": w.parent2_h, "parent non rattaché": w.parent4_h, "enseignant d'une autre classe": w.teacher_b_h,
        "Direction (aucune supervision)": w.direction_h, "Fondateur": w.founder_h, "Censeur": w.censor_h,
    }
    for label, headers in outsiders.items():
        assert client.get(url, headers=headers).status_code == 404, label
        assert client.post(url + "/read", headers=headers).status_code == 404, label
        assert client.post(url + "/messages", json={"body": "intrus"}, headers=headers).status_code == 404, label
        assert client.get("/api/v1/messages/threads", headers=headers).json() == [], label
        assert client.get("/api/v1/messages/unread-count", headers=headers).json() == {"unread": 0}, label
    assert client.get(url, headers=w.parent1_h).status_code == 200


def test_parent_loses_access_when_the_guardian_link_is_removed(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    thread_id = _new_thread(client, w.censor_h, w.kid_a).json()["id"]
    url = f"/api/v1/messages/threads/{thread_id}"
    assert client.get(url, headers=w.parent1_h).status_code == 200

    link = next(l for l in client.get("/api/v1/guardian-links", headers=w.direction_h).json() if l["parent_user_id"] == str(w.parent1.id))
    assert client.delete(f"/api/v1/guardian-links/{link['id']}", headers=w.direction_h).status_code == 204
    assert client.get(url, headers=w.parent1_h).status_code == 404
    assert client.post(url + "/messages", json={"body": "encore là ?"}, headers=w.parent1_h).status_code == 404
    assert client.post(url + "/read", headers=w.parent1_h).status_code == 404
    assert client.get("/api/v1/messages/threads", headers=w.parent1_h).json() == []
    assert client.get("/api/v1/messages/unread-count", headers=w.parent1_h).json() == {"unread": 0}
    assert client.get(url, headers=w.parent2_h).status_code == 200                              # l'autre parent, lui, garde son accès

    client.post("/api/v1/guardian-links", json={"parent_user_id": str(w.parent1.id), "student_id": w.kid_a["id"], "relationship_label": "Mère"}, headers=w.direction_h)
    assert client.get(url, headers=w.parent1_h).status_code == 200                              # rattaché à nouveau : accès rétabli


def test_threads_are_isolated_between_schools(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    thread_id = _new_thread(client, w.censor_h, w.kid_a).json()["id"]
    other = make_tenant()
    foreign_admin, p = make_user(tenant=other, role=UserRole.CENSOR)
    foreign_h = auth_headers(foreign_admin, p)
    assert client.get("/api/v1/messages/threads", headers=foreign_h).json() == []
    assert client.get(f"/api/v1/messages/threads/{thread_id}", headers=foreign_h).status_code == 404
    assert _new_thread(client, foreign_h, w.kid_a).status_code == 404                           # élève d'un autre établissement
    assert client.get(f"/api/v1/messages/guardians?student_id={w.kid_a['id']}", headers=foreign_h).status_code == 404


# ======================= Conversation : envoi, lecture, accusés =======================

def test_conversation_flow_unread_read_receipts_and_ordering(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    thread_id = _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.parent1.id)]).json()["id"]
    url = f"/api/v1/messages/threads/{thread_id}"

    def receipt(viewer_h, who):
        return {p["full_name"]: p["last_read_at"] for p in client.get(url, headers=viewer_h).json()["participants"]}[who]

    assert receipt(w.censor_h, "Mme Parent Un") is None                                        # pas encore lu
    assert client.post(url + "/read", headers=w.parent1_h).status_code == 204
    assert client.get("/api/v1/messages/unread-count", headers=w.parent1_h).json() == {"unread": 0}
    assert receipt(w.censor_h, "Mme Parent Un") is not None                                    # accusé « lu » visible de l'expéditeur

    reply = client.post(url + "/messages", json={"body": "  Merci, je viens demain.  "}, headers=w.parent1_h)
    assert reply.status_code == 201 and reply.json()["body"] == "Merci, je viens demain." and reply.json()["sender_id"] == str(w.parent1.id)
    assert client.get("/api/v1/messages/unread-count", headers=w.censor_h).json() == {"unread": 1}
    assert client.get("/api/v1/messages/unread-count", headers=w.parent1_h).json() == {"unread": 0}     # écrire vaut lecture
    listed = client.get("/api/v1/messages/threads?unread=true", headers=w.censor_h).json()
    assert len(listed) == 1 and listed[0]["last_message_preview"] == "Merci, je viens demain." and listed[0]["last_message_sender_id"] == str(w.parent1.id)

    client.post(url + "/read", headers=w.censor_h)
    assert client.get("/api/v1/messages/unread-count", headers=w.censor_h).json() == {"unread": 0}
    client.post(url + "/messages", json={"body": "Parfait, à demain."}, headers=w.censor_h)
    assert client.get("/api/v1/messages/unread-count", headers=w.parent1_h).json() == {"unread": 1}     # un message qui arrive après la lecture reste non lu
    messages = client.get(url, headers=w.parent1_h).json()["messages"]
    assert [m["body"] for m in messages] == ["Bonjour, pouvons-nous faire le point ?", "Merci, je viens demain.", "Parfait, à demain."]
    # les fils sont triés par dernière activité
    other_id = _new_thread(client, w.censor_h, w.kid_a, subject="Autre sujet", recipient_user_ids=[str(w.parent1.id)]).json()["id"]
    assert [t["id"] for t in client.get("/api/v1/messages/threads", headers=w.parent1_h).json()][0] == other_id


def test_message_and_thread_validation(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    assert _new_thread(client, w.censor_h, w.kid_a, subject="   ").status_code == 422
    assert _new_thread(client, w.censor_h, w.kid_a, body="   ").status_code == 422
    assert _new_thread(client, w.censor_h, w.kid_a, body="x" * 5001).status_code == 422
    assert _new_thread(client, w.censor_h, w.kid_a, subject="x" * 201).status_code == 422
    assert _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[]).status_code == 422
    assert _new_thread(client, w.censor_h, w.kid_a, recipient_user_ids=[str(w.parent1.id)] * 2).status_code == 422
    assert _new_thread(client, w.censor_h, w.kid_a, body="x" * 5000).status_code == 201
    thread_id = _new_thread(client, w.censor_h, w.kid_a).json()["id"]
    url = f"/api/v1/messages/threads/{thread_id}/messages"
    assert client.post(url, json={"body": ""}, headers=w.censor_h).status_code == 422
    assert client.post(url, json={"body": "y" * 5001}, headers=w.censor_h).status_code == 422
    assert client.post(url, json={}, headers=w.censor_h).status_code == 422


def test_message_sender_cannot_be_forged(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    thread_id = _new_thread(client, w.censor_h, w.kid_a).json()["id"]
    resp = client.post(f"/api/v1/messages/threads/{thread_id}/messages",
                       json={"body": "Bonjour", "sender_id": str(w.direction.id), "created_at": "2001-01-01T00:00:00Z"}, headers=w.parent1_h)
    assert resp.status_code == 201 and resp.json()["sender_id"] == str(w.parent1.id) and not resp.json()["created_at"].startswith("2001")


def test_message_rate_limit(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    thread_id = _new_thread(client, w.censor_h, w.kid_a).json()["id"]
    url = f"/api/v1/messages/threads/{thread_id}/messages"
    codes = [client.post(url, json={"body": f"message {i}"}, headers=w.censor_h).status_code for i in range(62)]
    assert codes[:60] == [201] * 60 and 429 in codes[60:]


def test_audit_records_thread_creation_but_never_message_content(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    secret = "Contenu confidentiel sur la santé de l'enfant"
    _new_thread(client, w.censor_h, w.kid_a, body=secret, subject="Sujet sensible")
    logs = client.get("/api/v1/audit-logs", headers=w.direction_h).json()
    created = [l for l in logs if l["action"] == "message_thread.created"]
    assert len(created) == 1 and created[0]["target_type"] == "MessageThread"
    assert secret not in json.dumps(logs) and "Sujet sensible" not in json.dumps(logs)


# ======================= Annonces =======================

def test_announcements_reach_the_right_families_only(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    general = client.post("/api/v1/announcements", json={"title": "Rentrée", "body": "La rentrée a lieu lundi."}, headers=w.direction_h)
    only_a = client.post("/api/v1/announcements", json={"title": "Sortie 6ème A", "body": "Sortie jeudi.", "class_id": w.class_a["id"]}, headers=w.censor_h)
    only_b = client.post("/api/v1/announcements", json={"title": "Devoir 5ème B", "body": "Cahier à rendre.", "class_id": w.class_b["id"]}, headers=w.staff_h)
    assert (general.status_code, only_a.status_code, only_b.status_code) == (201, 201, 201)
    assert only_a.json()["class_name"] == "6ème A" and only_a.json()["author_name"] == "M. Censeur" and general.json()["class_name"] is None

    def titles(headers):
        return {a["title"] for a in client.get("/api/v1/announcements", headers=headers).json()}

    assert titles(w.parent1_h) == {"Rentrée", "Sortie 6ème A"}          # parent de 6ème A
    assert titles(w.parent3_h) == {"Rentrée", "Devoir 5ème B"}          # parent de 5ème B
    assert titles(w.parent4_h) == {"Rentrée"}                            # parent non rattaché : seulement le général
    assert titles(w.teacher_a_h) == {"Rentrée", "Sortie 6ème A", "Devoir 5ème B"}   # le personnel voit tout
    assert client.get("/api/v1/announcements", headers=w.direction_h).json()[0]["title"] == "Devoir 5ème B"   # plus récente d'abord


def test_only_designated_roles_publish_announcements(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    body = {"title": "Info", "body": "Texte"}
    for headers in (w.direction_h, w.founder_h, w.censor_h, w.staff_h):
        assert client.post("/api/v1/announcements", json=body, headers=headers).status_code == 201
    for headers in (w.teacher_a_h, w.parent1_h, w.accountant_h, w.supervisor_h):
        assert client.post("/api/v1/announcements", json=body, headers=headers).status_code == 403
    assert client.post("/api/v1/announcements", json={"title": " ", "body": "x"}, headers=w.direction_h).status_code == 422
    assert client.post("/api/v1/announcements", json={"title": "x", "body": "y" * 5001}, headers=w.direction_h).status_code == 422
    other = make_tenant()
    foreign, p = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    assert client.post("/api/v1/announcements", json={**body, "class_id": w.class_a["id"]}, headers=auth_headers(foreign, p)).status_code == 404


def test_announcement_removal_rights_and_isolation(client, make_tenant, make_user, auth_headers):
    w = _world(client, make_tenant, make_user, auth_headers)
    by_direction = client.post("/api/v1/announcements", json={"title": "D", "body": "x"}, headers=w.direction_h).json()
    by_censor = client.post("/api/v1/announcements", json={"title": "C", "body": "x"}, headers=w.censor_h).json()
    assert client.delete(f"/api/v1/announcements/{by_direction['id']}", headers=w.censor_h).status_code == 403      # pas celle d'un autre
    assert client.delete(f"/api/v1/announcements/{by_censor['id']}", headers=w.censor_h).status_code == 204        # la sienne
    assert client.delete(f"/api/v1/announcements/{by_direction['id']}", headers=w.parent1_h).status_code == 403
    other = make_tenant()
    foreign, p = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    foreign_h = auth_headers(foreign, p)
    assert client.get("/api/v1/announcements", headers=foreign_h).json() == []
    assert client.delete(f"/api/v1/announcements/{by_direction['id']}", headers=foreign_h).status_code == 404
    third = client.post("/api/v1/announcements", json={"title": "E", "body": "x"}, headers=w.censor_h).json()
    assert client.delete(f"/api/v1/announcements/{third['id']}", headers=w.direction_h).status_code == 204          # la Direction peut retirer toute annonce
    actions = [l["action"] for l in client.get("/api/v1/audit-logs", headers=w.direction_h).json()]
    assert "announcement.published" in actions and "announcement.deleted" in actions
