"""Jeu de démonstration « Collège Sainte Anne » — pour présenter GESCOLA à une école.

Usage (depuis le dossier backend) :

    DATABASE_URL=... python -m scripts.seed_demo --password 'MotDePasseDemo#2026'

* **Idempotent** : si l'école de démonstration contient déjà des élèves, le script ne
  touche à rien et le dit. Il ne supprime JAMAIS de données.
* **Données fictives uniquement** : noms inventés, adresses en @demo.gescola.com.
* **Passe par l'API réelle** (RLS, validations, droits, journal d'audit comme en
  production) ; l'import des élèves utilise l'import CSV de la plateforme, ce qui le
  teste au passage.
* En production (ENVIRONMENT=production) il exige --confirm-production.
"""
import argparse
import os
import random
import secrets
import sys
from datetime import datetime, timezone

os.environ.setdefault("LOGIN_RATE_LIMIT", "100000/minute")  # le script se connecte à plusieurs comptes d'affilée

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

API = "/api/v1"
TENANT_CODE = "demo-sainte-anne"
DOMAIN = "demo.gescola.com"

ACCOUNTS = [
    # (clé, rôle, nom affiché)
    ("direction", UserRole.SCHOOL_ADMIN, "Mme la Directrice Houngbo"),
    ("censeur", UserRole.CENSOR, "M. le Censeur Adjovi"),
    ("surveillant", UserRole.SUPERVISOR, "M. Tossou (surveillant)"),
    ("comptable", UserRole.ACCOUNTANT, "Mme Comlan (comptable)"),
    ("secretariat", UserRole.STAFF, "Mme Dossou (secrétariat)"),
    ("prof.maths", UserRole.TEACHER, "M. Agbo (Mathématiques, SVT)"),
    ("prof.francais", UserRole.TEACHER, "Mme Zinsou (Français, Anglais)"),
    ("prof.histoire", UserRole.TEACHER, "M. Ahouansou (Histoire-Géographie)"),
    ("parent.kakpo", UserRole.PARENT, "Mme Kakpo (parent)"),
    ("parent.mensah", UserRole.PARENT, "M. Mensah (parent)"),
]

STUDENTS_6A = [
    ("KAKPO", "Jean", "M"), ("DIALLO", "Aïcha", "F"), ("MENSAH", "Koffi", "M"), ("BELLO", "Awa", "F"),
    ("AGOSSOU", "Marc", "M"), ("HOUNKPATIN", "Sika", "F"), ("TOGNIFODE", "Paul", "M"), ("ADJOVI", "Chantal", "F"),
    ("GBEDO", "Rodrigue", "M"), ("SOSSOU", "Nadège", "F"), ("AKPOVI", "Basile", "M"), ("DEGBE", "Prisca", "F"),
]
STUDENTS_5B = [
    ("AHOUANDJINOU", "Eric", "M"), ("VIGAN", "Mireille", "F"), ("ZANNOU", "Yves", "M"), ("CAKPO", "Estelle", "F"),
    ("LOKONON", "Franck", "M"), ("AMOUSSOU", "Carine", "F"), ("DOSSA", "Hervé", "M"), ("TCHOKPON", "Laure", "F"),
    ("HOUESSOU", "Brice", "M"), ("ALLADAYE", "Judith", "F"), ("FADONOUGBO", "Armel", "M"), ("GLELE", "Rachel", "F"),
]
SUBJECTS = [("Français", 2), ("Mathématiques", 4), ("Anglais", 2), ("SVT", 2), ("Histoire-Géographie", 2)]
TEACHER_OF = {
    "Mathématiques": "prof.maths", "SVT": "prof.maths", "Français": "prof.francais",
    "Anglais": "prof.francais", "Histoire-Géographie": "prof.histoire",
}


def die(message: str) -> None:
    print(f"ERREUR : {message}", file=sys.stderr)
    sys.exit(1)


def ok(response, expected=(200, 201), what=""):
    if response.status_code not in expected:
        die(f"{what or response.request.url} -> {response.status_code} {response.text[:300]}")
    return response


def reset_demo() -> None:
    """Supprime UNIQUEMENT l'établissement de démonstration et ses données (cascade en base)."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        tenant = db.execute(select(Tenant).where(Tenant.code == TENANT_CODE)).scalar_one_or_none()
        if tenant is None:
            print("Aucune école de démonstration à supprimer.")
            return
        tid = tenant.id
        # Toutes les tables de l'établissement sont liées à lui en suppression en cascade ; seules les notes
        # référencent des enseignants/matières en « RESTRICT » : on les supprime d'abord.
        db.execute(text("SET LOCAL app.current_tenant = :t"), {"t": str(tid)})
        db.execute(text("DELETE FROM grades WHERE tenant_id = :t"), {"t": tid})
        db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
        db.commit()
        print("École de démonstration supprimée.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--password", default=os.environ.get("DEMO_PASSWORD"), help="mot de passe commun des comptes de démonstration")
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--reset-demo", action="store_true", help="supprime l'école de démonstration (et elle seule) avant de la recréer")
    args = parser.parse_args()

    if os.environ.get("ENVIRONMENT", "").lower() == "production" and not args.confirm_production:
        die("ENVIRONMENT=production : relancez avec --confirm-production si vous voulez bien créer l'école de démonstration ici.")
    if args.reset_demo:
        reset_demo()
    generated = args.password is None
    password = args.password or ("Demo-" + secrets.token_urlsafe(9) + "#1")

    db = SessionLocal()
    try:
        tenant = db.execute(select(Tenant).where(Tenant.code == TENANT_CODE)).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="Collège Sainte Anne", code=TENANT_CODE)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        user_ids: dict[str, str] = {}
        for key, role, full_name in ACCOUNTS:
            email = f"{key}@{DOMAIN}"
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user is None:
                user = User(
                    tenant_id=tenant.id, email=email, full_name=full_name, role=role,
                    hashed_password=hash_password(password), must_change_password=False,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            user_ids[key] = str(user.id)
    finally:
        db.close()

    client = TestClient(app)

    def login(key: str) -> dict:
        r = client.post(f"{API}/auth/login", json={"email": f"{key}@{DOMAIN}", "password": password})
        if r.status_code != 200:
            die(f"connexion de {key} impossible ({r.status_code}). Les comptes existent peut-être déjà avec un autre mot de passe.")
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    direction = login("direction")
    existing = client.get(f"{API}/students", params={"limit": 1}, headers=direction)
    ok(existing, what="liste des élèves")
    if int(existing.headers["X-Total-Count"]) > 0:
        announcements = ok(client.get(f"{API}/announcements", headers=direction), what="annonces").json()
        if any(a["title"] == "Réunion des parents" for a in announcements):
            print("L'école de démonstration est déjà complète : rien n'a été modifié.")
            return
        die("L'école de démonstration est dans un état partiel (un lancement précédent a échoué en cours de route). "
            "Relancez avec --reset-demo pour la supprimer puis la recréer (seule l'école « demo-sainte-anne » est touchée).")

    rng = random.Random(2026)
    censor, supervisor, staff = login("censeur"), login("surveillant"), login("secretariat")
    teachers = {k: login(k) for k in ("prof.maths", "prof.francais", "prof.histoire")}

    have_classes = {c["name"]: c for c in ok(client.get(f"{API}/classes", headers=direction)).json()}
    have_subjects = {c["name"]: c for c in ok(client.get(f"{API}/subjects", headers=direction)).json()}
    classes = {}
    for name, level in (("6ème A", "6ème"), ("5ème B", "5ème")):
        classes[name] = have_classes.get(name) or ok(
            client.post(f"{API}/classes", json={"name": name, "level": level, "cycle": "secondaire"}, headers=direction), what="classe"
        ).json()
    subjects = {
        name: have_subjects.get(name) or ok(
            client.post(f"{API}/subjects", json={"name": name, "default_coefficient": coef}, headers=direction), what="matière"
        ).json()
        for name, coef in SUBJECTS
    }
    for cls in classes.values():
        for subject_name, teacher_key in TEACHER_OF.items():
            ok(client.post(f"{API}/teacher-assignments", json={
                "teacher_id": user_ids[teacher_key], "class_id": cls["id"], "subject_id": subjects[subject_name]["id"],
            }, headers=direction), expected=(201, 409), what="affectation")
    ok(client.patch(f"{API}/classes/{classes['6ème A']['id']}", json={"head_teacher_id": user_ids["prof.francais"]}, headers=direction))
    ok(client.patch(f"{API}/classes/{classes['5ème B']['id']}", json={"head_teacher_id": user_ids["prof.maths"]}, headers=direction))

    # Import des élèves par le vrai import CSV de la plateforme (aperçu puis import réel).
    lines = ["Nom;Prénom;Classe;Matricule;Sexe;Date de naissance;Redoublant;Tuteur;Téléphone du tuteur"]
    number = 1
    for class_name, group in (("6ème A", STUDENTS_6A), ("5ème B", STUDENTS_5B)):
        for last, first, sex in group:
            year = 2013 if class_name == "6ème A" else 2012
            born = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{year}"
            lines.append(f"{last};{first};{class_name};DEMO-{number:04d};{sex};{born};{'oui' if rng.random() < 0.1 else 'non'};Famille {last.title()};+229 97 00 {number:02d} {number:02d}")
            number += 1
    content = ("\r\n".join(lines) + "\r\n").encode("utf-8")
    for dry in ("true", "false"):
        report = ok(client.post(f"{API}/students/import", params={"dry_run": dry}, files={"file": ("demo.csv", content)}, headers=direction), what="import").json()
        if report["error_count"]:
            die(f"le fichier de démonstration contient des erreurs : {report['errors'][:3]}")
    students = client.get(f"{API}/students", params={"limit": 500}, headers=direction).json()
    by_class: dict[str, list[dict]] = {}
    name_of_class = {c["id"]: n for n, c in classes.items()}
    for s in students:
        by_class.setdefault(name_of_class[s["class_id"]], []).append(s)

    # Parents de démonstration.
    kakpo = next(s for s in students if s["last_name"] == "KAKPO")
    mensah = next(s for s in students if s["last_name"] == "MENSAH")
    for parent_key, student, label in (("parent.kakpo", kakpo, "Mère"), ("parent.mensah", mensah, "Père")):
        ok(client.post(f"{API}/guardian-links", json={
            "parent_user_id": user_ids[parent_key], "student_id": student["id"], "relationship_label": label,
        }, headers=direction), what="lien parent")

    # Notes du 1er trimestre, saisies par l'enseignant affecté à chaque matière.
    for class_name, group in by_class.items():
        for student in group:
            level = rng.uniform(8.5, 16.5)  # un niveau propre à l'élève, avec des écarts selon les matières
            for subject_name, _ in SUBJECTS:
                for label in ("Devoir 1", "Devoir 2"):
                    value = round(max(2.0, min(20.0, rng.gauss(level, 2.2))), 2)
                    ok(client.post(f"{API}/grades", json={
                        "student_id": student["id"], "subject_id": subjects[subject_name]["id"], "term": "T1",
                        "evaluation_label": label, "value": value,
                    }, headers=teachers[TEACHER_OF[subject_name]]), what="note")

    # 6ème A : notes verrouillées, bulletins générés et publiés. 5ème B : notes encore en cours de saisie.
    for student in by_class["6ème A"]:
        ok(client.post(f"{API}/students/{student['id']}/grades/lock?term=T1", headers=censor), what="verrouillage")
    ok(client.patch(f"{API}/establishment/settings", json={"bulletin_motto": "Discipline - Travail - Réussite", "bulletin_place": "Cotonou"}, headers=direction), what="réglages")
    ok(client.post(f"{API}/report-cards/generate", json={"class_id": classes["6ème A"]["id"], "term": "T1"}, headers=direction), what="génération")
    cards = ok(client.get(f"{API}/report-cards", headers=direction), what="liste des bulletins").json()
    for card in cards:
        ok(client.patch(f"{API}/report-cards/{card['id']}", json={"principal_comment": "Élève sérieux, poursuivez vos efforts."}, headers=direction), what="appréciation")
        ok(client.post(f"{API}/report-cards/{card['id']}/publish", headers=direction), what="publication")

    # Vie scolaire : un appel, un incident, une annonce.
    for date, absent in (("2026-10-05", {"HOUNKPATIN", "GBEDO"}), ("2026-10-06", {"KAKPO"})):
        ok(client.post(f"{API}/attendance/bulk", json={
            "class_id": classes["6ème A"]["id"], "date": date,
            "entries": [{"student_id": s["id"], "status": "absent" if s["last_name"] in absent else "present"} for s in by_class["6ème A"]],
        }, headers=supervisor), what="appel")
    ok(client.post(f"{API}/incidents", json={
        "student_id": next(s for s in students if s["last_name"] == "GBEDO")["id"],
        "occurred_at": datetime(2026, 10, 7, 9, 30, tzinfo=timezone.utc).isoformat(),
        "category": "behavior", "severity": "minor", "description": "Bavardages répétés pendant le cours de mathématiques.",
    }, headers=supervisor), what="incident")
    ok(client.post(f"{API}/announcements", json={"title": "Réunion des parents", "body": "La réunion du premier trimestre aura lieu samedi à 9 h dans la cour principale."}, headers=direction), what="annonce")

    print("\nÉcole de démonstration créée : Collège Sainte Anne (24 élèves, 2 classes, bulletins T1 de la 6ème A publiés).")
    print(f"Mot de passe commun{' (généré — notez-le maintenant)' if generated else ''} : {password}\n")
    for key, _, full_name in ACCOUNTS:
        print(f"  {key + '@' + DOMAIN:<36} {full_name}")


if __name__ == "__main__":
    main()
