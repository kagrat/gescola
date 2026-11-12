"""AU-06 : import en masse des élèves (CSV / Excel)."""
import io
import zipfile
from datetime import date

from openpyxl import Workbook

from app.models.user import UserRole

API = "/api/v1"
HEADER = "Nom;Prénom;Classe;Matricule;Sexe;Date de naissance;Redoublant;Tuteur;Téléphone du tuteur;E-mail du tuteur"


def _school(client, make_tenant, make_user, auth_headers):
    class S:
        pass

    s = S()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    s.admin_h = auth_headers(s.admin, pwd)
    s.cls = client.post(f"{API}/classes", json={"name": "6ème A", "level": "6ème"}, headers=s.admin_h).json()
    return s


def _csv(*lines, header=HEADER) -> bytes:
    return ("\r\n".join([header, *lines]) + "\r\n").encode("utf-8")


def _up(client, h, content: bytes, name="eleves.csv", dry_run=True):
    return client.post(f"{API}/students/import", params={"dry_run": str(dry_run).lower()}, files={"file": (name, content)}, headers=h)


def _count(client, h) -> int:
    return int(client.get(f"{API}/students", headers=h).headers["X-Total-Count"])


GOOD = [
    "KAKPO;Jean;6ème A;MAT-1;M;14/03/2014;non;Mme Kakpo;+229 97 00 00 00;parent@exemple.bj",
    "DIALLO;Aya;6eme a;MAT-2;F;02/11/2013;oui;;;",
    "MENSAH;Koffi;;;;;;;;",
]


# ======================= Cas nominal =======================

def test_preview_writes_nothing_then_import_creates_everything(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    r = _up(client, s.admin_h, _csv(*GOOD))
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True and body["total_rows"] == 3 and body["valid_rows"] == 3 and body["error_count"] == 0
    assert body["imported"] == 0 and _count(client, s.admin_h) == 0       # l'aperçu n'écrit rien
    assert [p["last_name"] for p in body["preview"]] == ["KAKPO", "DIALLO", "MENSAH"]

    real = _up(client, s.admin_h, _csv(*GOOD), dry_run=False)
    assert real.status_code == 200 and real.json()["imported"] == 3 and _count(client, s.admin_h) == 3
    students = {x["last_name"]: x for x in client.get(f"{API}/students", headers=s.admin_h).json()}
    assert students["KAKPO"]["class_id"] == s.cls["id"] and students["KAKPO"]["gender"] == "male"
    assert students["KAKPO"]["date_of_birth"] == "2014-03-14" and students["KAKPO"]["guardian_email"] == "parent@exemple.bj"
    assert students["DIALLO"]["class_id"] == s.cls["id"]                 # « 6eme a » = « 6ème A »
    assert students["DIALLO"]["is_repeater"] is True and students["DIALLO"]["gender"] == "female"
    assert students["MENSAH"]["class_id"] is None and students["MENSAH"]["status"] == "active"


def test_import_is_audited_once_with_a_file_fingerprint(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _up(client, s.admin_h, _csv(*GOOD), name="rentree-2026.csv", dry_run=False)
    logs = [a for a in client.get(f"{API}/audit-logs", headers=s.admin_h).json() if a["action"] == "students.imported"]
    assert len(logs) == 1
    meta = logs[0]["metadata_json"]
    assert meta["count"] == 3 and meta["filename"] == "rentree-2026.csv" and len(meta["sha256"]) == 64
    _up(client, s.admin_h, _csv(*GOOD))                                    # un aperçu ne laisse aucune trace
    assert len([a for a in client.get(f"{API}/audit-logs", headers=s.admin_h).json() if a["action"] == "students.imported"]) == 1


def test_windows_1252_comma_and_header_variants_are_understood(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    content = "NOM,PRENOMS,CLASSE,Sexe\r\nÉLOGE,Hélène,6ème A,féminin\r\n".encode("cp1252")   # Excel FR
    r = _up(client, s.admin_h, content, dry_run=False)
    assert r.status_code == 200 and r.json()["imported"] == 1
    kid = client.get(f"{API}/students", headers=s.admin_h).json()[0]
    assert kid["last_name"] == "ÉLOGE" and kid["first_name"] == "Hélène" and kid["gender"] == "female"
    bom = ("﻿" + HEADER + "\r\nBELLO;Awa;;;;;;;;\r\n").encode("utf-8")                 # UTF-8 avec BOM
    assert _up(client, s.admin_h, bom, dry_run=False).json()["imported"] == 1


def test_xlsx_with_real_dates_and_numeric_phones(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    wb = Workbook()
    ws = wb.active
    ws.append(["Nom", "Prénom", "Classe", "Date de naissance", "Téléphone du tuteur", "Colonne inutile"])
    ws.append(["KAKPO", "Jean", "6ème A", date(2014, 3, 14), 97000000, "x"])
    ws.append([None, None, None, None, None, None])                                           # ligne vide ignorée
    ws.append(["DIALLO", "Aya", "6ème A", "02/11/2013", "97 11 22 33", None])
    buf = io.BytesIO()
    wb.save(buf)
    r = _up(client, s.admin_h, buf.getvalue(), name="eleves.xlsx", dry_run=False)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2 and r.json()["ignored_columns"] == ["Colonne inutile"]
    by_name = {x["last_name"]: x for x in client.get(f"{API}/students", headers=s.admin_h).json()}
    assert by_name["KAKPO"]["date_of_birth"] == "2014-03-14" and by_name["KAKPO"]["guardian_phone"] == "97000000"


def test_template_can_be_downloaded_and_reimported(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    r = client.get(f"{API}/students/import/template", headers=s.admin_h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")                                              # BOM UTF-8
    again = _up(client, s.admin_h, r.content)
    assert again.status_code == 200 and again.json()["error_count"] == 0 and again.json()["valid_rows"] == 1
    # Dans une école SANS la classe « 6ème A », la même ligne d'exemple est refusée : aucune classe n'est créée en silence.
    fresh_tenant = make_tenant()
    admin, pwd = make_user(tenant=fresh_tenant, role=UserRole.SCHOOL_ADMIN)
    refused = _up(client, auth_headers(admin, pwd), r.content).json()
    assert refused["error_count"] == 1 and "Classe introuvable" in refused["errors"][0]["message"]


# ======================= Validation ligne par ligne =======================

def test_every_bad_row_is_reported_with_its_line_number_and_nothing_is_written(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    bad = [
        "OK;Valide;6ème A;;;;;;;",                                      # ligne 2 : valide
        ";SansNom;;;;;;;;",                                             # 3 : nom manquant
        "A;B;Classe fantôme;;;;;;;",                                    # 4 : classe inconnue
        "C;D;;;X;;;;;",                                                 # 5 : sexe invalide
        "E;F;;;;31/02/2014;;;;",                                        # 6 : date impossible
        "G;H;;;;01/01/2099;;;;",                                        # 7 : futur
        "I;J;;;;01/01/1950;;;;",                                        # 8 : invraisemblable
        "K;L;;;;;peut-être;;;",                                         # 9 : redoublant
        "M;N;;;;;;;abc;",                                               # 10 : téléphone
        "O;P;;;;;;;;pas-un-mail",                                       # 11 : e-mail
        "=cmd|' /C calc'!A0;Q;;;;;;;;",                                 # 12 : formule
        "R;S;;" + "M" * 31 + ";;;;;;",                                 # 13 : matricule trop long
    ]
    r = _up(client, s.admin_h, _csv(*bad))
    body = r.json()
    assert r.status_code == 200 and body["valid_rows"] == 1 and body["error_count"] == 11
    assert [e["row"] for e in body["errors"]] == list(range(3, 14))
    assert {e["field"] for e in body["errors"]} >= {"last_name", "class", "gender", "date_of_birth", "is_repeater", "guardian_phone", "guardian_email", "matricule"}

    messages = {e["row"]: e["message"] for e in body["errors"]}
    assert "futur" in messages[7] and "invraisemblable" in messages[8]
    refused = _up(client, s.admin_h, _csv(*bad), dry_run=False)
    assert refused.status_code == 422 and "Aucun élève n'a été enregistré" in refused.json()["detail"]
    assert _count(client, s.admin_h) == 0                                                      # tout ou rien


def test_duplicates_in_file_and_against_existing_students(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post(f"{API}/students", json={"first_name": "Jean", "last_name": "Kakpo", "matricule": "MAT-1", "date_of_birth": "2014-03-14"}, headers=s.admin_h)
    client.post(f"{API}/students", json={"first_name": "Aya", "last_name": "Diallo"}, headers=s.admin_h)
    lines = [
        "NOUVEAU;Un;;mat-1;;;;;;",                                      # 2 : matricule existant (casse différente)
        "NOUVEAU;Deux;;MAT-9;;;;;;",                                    # 3 : OK
        "AUTRE;Trois;;MAT-9;;;;;;",                                     # 4 : matricule en double dans le fichier
        "KAKPO;Jean;;;;14/03/2014;;;;",                                 # 5 : même nom + même naissance qu'un existant
        "DIALLO;Aya;;;;;;;;",                                           # 6 : homonyme sans date -> avertissement seulement
        "TWIN;Un;;;;01/05/2013;;;;",                                    # 7 : OK
        "TWIN;Un;;;;01/05/2013;;;;",                                    # 8 : même identité que la ligne 7
    ]
    body = _up(client, s.admin_h, _csv(*lines)).json()
    assert [e["row"] for e in body["errors"]] == [2, 4, 5, 8]
    assert [w["row"] for w in body["warnings"]] == [6]
    assert body["valid_rows"] == 3


def test_reimporting_the_same_file_does_not_create_duplicates(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    lines = ["KAKPO;Jean;;MAT-1;;14/03/2014;;;;", "DIALLO;Aya;;MAT-2;;;;;;"]
    assert _up(client, s.admin_h, _csv(*lines), dry_run=False).status_code == 200
    again = _up(client, s.admin_h, _csv(*lines), dry_run=False)
    assert again.status_code == 409 and "déjà été importé" in again.json()["detail"] and _count(client, s.admin_h) == 2
    # Fichier légèrement différent (une ligne de plus) : les anciens matricules sont refusés ligne par ligne.
    changed = _up(client, s.admin_h, _csv(*lines, "NEW;Eleve;;MAT-3;;;;;;"), dry_run=False)
    assert changed.status_code == 422 and _count(client, s.admin_h) == 2


def test_same_file_without_matricule_or_birthdate_is_not_imported_twice(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    content = _csv("MENSAH;Koffi;;;;;;;;", "BELLO;Awa;;;;;;;;")
    assert _up(client, s.admin_h, content, dry_run=False).status_code == 200
    assert _up(client, s.admin_h, content, dry_run=False).status_code == 409          # un double clic ne duplique rien
    assert _count(client, s.admin_h) == 2


def test_two_simultaneous_imports_of_the_same_file_create_the_students_once(make_tenant, make_user, auth_headers):
    import threading
    from fastapi.testclient import TestClient
    from app.main import app

    c1, c2 = TestClient(app), TestClient(app)
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    content = _csv(*[f"NOM{i};Prenom{i};;;;;;;;" for i in range(300)])
    results = []

    def fire(c):
        results.append(_up(c, headers, content, dry_run=False).status_code)

    threads = [threading.Thread(target=fire, args=(c,)) for c in (c1, c2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [200, 409]
    assert _count(c1, headers) == 300


# ======================= Fichiers hostiles ou invalides =======================

def test_hostile_or_invalid_files_are_rejected_cleanly(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    h = s.admin_h
    assert _up(client, h, b"").status_code == 400
    assert _up(client, h, b"   \n  ").status_code == 400
    assert _up(client, h, _csv()).status_code == 400                                          # en-tête seul
    assert _up(client, h, b"Prenom;Age\r\nJean;12\r\n").status_code == 400                    # colonne Nom absente
    assert _up(client, h, b"Nom\x00Prenom\x00\x01\x02").status_code == 400                    # binaire
    assert _up(client, h, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 100, name="vieux.xls").status_code == 400
    assert _up(client, h, b"PK\x03\x04 pas vraiment un zip", name="x.xlsx").status_code == 400
    assert _up(client, h, b"x" * (2 * 1024 * 1024 + 10)).status_code == 413                   # trop gros
    too_many = _csv(*[f"N{i};P{i};;;;;;;;" for i in range(2001)])
    assert _up(client, h, too_many).status_code == 413
    assert _up(client, h, _csv(*[f"N{i};P{i};;;;;;;;" for i in range(2000)])).status_code == 200   # la limite exacte passe
    assert _count(client, h) == 0


def test_xlsx_with_macros_is_refused(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("xl/vbaProject.bin", b"macro")
    r = _up(client, s.admin_h, buf.getvalue(), name="macro.xlsx")
    assert r.status_code == 400 and "macros" in r.json()["detail"]


def test_decompression_bomb_is_refused(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"0" * (50 * 1024 * 1024))                     # ~50 Mo décompressés, quelques Ko compressés
    assert len(buf.getvalue()) < 2 * 1024 * 1024
    r = _up(client, s.admin_h, buf.getvalue(), name="bombe.xlsx")
    assert r.status_code == 400 and "volumineux" in r.json()["detail"]


# ======================= Droits et isolation =======================

def test_only_registry_managers_can_import_and_data_stays_in_the_school(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    for role in (UserRole.TEACHER, UserRole.CENSOR, UserRole.SUPERVISOR, UserRole.ACCOUNTANT, UserRole.PARENT):
        user, pwd = make_user(tenant=s.tenant, role=role)
        h = auth_headers(user, pwd)
        assert _up(client, h, _csv(*GOOD), dry_run=False).status_code == 403, role
        assert client.get(f"{API}/students/import/template", headers=h).status_code == 403, role
    assert _count(client, s.admin_h) == 0
    # La classe « 6ème A » de l'autre école n'est pas visible pour cette école : même nom, id différent.
    assert _up(client, other.admin_h, _csv(GOOD[0]), dry_run=False).json()["imported"] == 1
    mine = client.get(f"{API}/students", headers=s.admin_h)
    assert mine.headers["X-Total-Count"] == "0"
    theirs = client.get(f"{API}/students", headers=other.admin_h).json()
    assert theirs[0]["class_id"] == other.cls["id"] != s.cls["id"]
    anonymous = client.post(f"{API}/students/import", files={"file": ("a.csv", _csv(*GOOD))})
    assert anonymous.status_code == 401
