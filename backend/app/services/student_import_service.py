"""Import en masse des élèves depuis un fichier CSV ou Excel (AU-06).

Principes :

* **Aperçu d'abord, écriture ensuite.** Le même code valide le fichier dans les deux
  cas ; l'aperçu n'écrit rien. L'import réel est *tout ou rien* : une seule ligne
  invalide et rien n'est enregistré, pour ne jamais laisser une école avec la moitié
  de ses élèves sans savoir lesquels.
* **Le fichier est une entrée hostile.** Taille, nombre de lignes, bombe de
  décompression (xlsx = zip), encodage, séparateur, formats de date, longueurs, et
  valeurs commençant par `=` ou `@` (formules interprétées par un tableur à
  l'export) sont contrôlés avant toute écriture.
* **Aucune création implicite.** Une classe inconnue est une erreur : l'import ne
  crée jamais de classe à partir d'une faute de frappe.
* **Doublons.** Matricule déjà pris (dans la base ou dans le fichier) = erreur.
  Même nom + même date de naissance = erreur. Même nom sans date = avertissement
  (des homonymes existent).
* **Un import à la fois par établissement** (verrou consultatif), pour qu'un double
  clic ou deux onglets ne créent pas deux fois les mêmes élèves.
"""
import csv
import hashlib
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass
from app.models.audit import AuditLog
from app.models.student import Student, StudentGender
from app.services.audit_service import log_action

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
MAX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024
MAX_REPORTED_ERRORS = 200
PREVIEW_ROWS = 20

TEMPLATE_HEADERS = [
    "Nom", "Prénom", "Classe", "Matricule", "Sexe", "Date de naissance",
    "Redoublant", "Tuteur", "Téléphone du tuteur", "E-mail du tuteur",
]
TEMPLATE_EXAMPLE = [
    "KAKPO", "Jean", "6ème A", "MAT-0001", "M", "14/03/2014", "non", "Mme KAKPO Fatou", "+229 97 00 00 00", "parent@exemple.bj",
]

_ALIASES = {
    "last_name": {"nom", "nomdefamille", "nomeleve", "nomdeleleve"},
    "first_name": {"prenom", "prenoms", "prenomeleve"},
    "class": {"classe"},
    "matricule": {"matricule", "nmatricule", "numeromatricule", "nomatricule"},
    "gender": {"sexe", "genre"},
    "date_of_birth": {"datedenaissance", "naissance", "nele", "neele", "datenaissance"},
    "is_repeater": {"redoublant", "redoublante", "redoublement"},
    "guardian_name": {"tuteur", "tutrice", "parent", "nomdututeur", "tuteurtutrice", "responsable"},
    "guardian_phone": {"telephone", "teldututeur", "telephonedututeur", "telephonetuteur", "tel", "contact", "telephoneparent"},
    "guardian_email": {"email", "emaildututeur", "emailtuteur", "courriel", "mail", "emailparent"},
}
_ALIAS_LOOKUP = {alias: field_name for field_name, aliases in _ALIASES.items() for alias in aliases}
_FORMULA_START = ("=", "@")
_PHONE_RE = re.compile(r"^[0-9+().\s-]{6,30}$")
_EMAIL = TypeAdapter(EmailStr)


@dataclass
class RowIssue:
    row: int
    message: str
    field: str | None = None


@dataclass
class ImportReport:
    total_rows: int = 0
    valid_rows: int = 0
    errors: list[RowIssue] = field(default_factory=list)
    warnings: list[RowIssue] = field(default_factory=list)
    ignored_columns: list[str] = field(default_factory=list)
    preview: list[dict] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0

    def error(self, row: int, message: str, fld: str | None = None) -> None:
        self.error_count += 1
        if len(self.errors) < MAX_REPORTED_ERRORS:
            self.errors.append(RowIssue(row, message, fld))

    def warn(self, row: int, message: str) -> None:
        self.warning_count += 1
        if len(self.warnings) < MAX_REPORTED_ERRORS:
            self.warnings.append(RowIssue(row, message))


# ----------------------------------------------------------------- lecture du fichier

def _fail(message: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _normalize_header(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", raw.lower())


def _decode_csv(content: bytes) -> str:
    if b"\x00" in content:
        raise _fail("Ce fichier n'est pas un CSV lisible (contenu binaire). Enregistrez-le au format CSV ou Excel (.xlsx).")
    for encoding in ("utf-8-sig", "cp1252"):  # Excel (FR) enregistre souvent en Windows-1252
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _read_csv(content: bytes) -> list[list[object]]:
    text_content = _decode_csv(content)
    first_line = text_content.split("\n", 1)[0]
    delimiter = max((";", ",", "\t", "|"), key=first_line.count)
    if first_line.count(delimiter) == 0:
        raise _fail("Impossible de reconnaître les colonnes : utilisez le séparateur « ; » ou « , » (voir le modèle).")
    rows: list[list[object]] = []
    try:
        for record in csv.reader(io.StringIO(text_content, newline=""), delimiter=delimiter):
            rows.append(list(record))
            if len(rows) > MAX_ROWS + 1:
                break
    except csv.Error as exc:
        raise _fail(f"Fichier CSV invalide : {exc}")
    return rows


def _read_xlsx(content: bytes) -> list[list[object]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
                raise _fail("Fichier Excel trop volumineux une fois décompressé.")
            if any(info.filename.lower().endswith("vbaproject.bin") for info in archive.infolist()):
                raise _fail("Les classeurs avec macros ne sont pas acceptés. Enregistrez au format .xlsx ou CSV.")
    except zipfile.BadZipFile:
        raise _fail("Fichier Excel illisible ou corrompu.")
    from openpyxl import load_workbook  # import tardif : dépendance chargée uniquement ici

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.worksheets[0]
        rows: list[list[object]] = []
        for record in sheet.iter_rows(values_only=True):
            rows.append(list(record))
            if len(rows) > MAX_ROWS + 1:
                break
        workbook.close()
    except HTTPException:
        raise
    except Exception:
        raise _fail("Fichier Excel illisible ou corrompu.")
    return rows


def read_table(content: bytes, filename: str) -> list[list[object]]:
    if len(content) > MAX_FILE_BYTES:
        raise _fail(f"Fichier trop volumineux (maximum {MAX_FILE_BYTES // (1024 * 1024)} Mo).", 413)
    if not content.strip():
        raise _fail("Le fichier est vide.")
    if content[:4] == b"PK\x03\x04":
        return _read_xlsx(content)
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise _fail("Le format Excel ancien (.xls) n'est pas pris en charge. Enregistrez le fichier au format .xlsx ou CSV.")
    if filename.lower().endswith((".xlsx", ".xlsm")):
        raise _fail("Fichier Excel illisible ou corrompu.")
    return _read_csv(content)


# ----------------------------------------------------------------- validation des cellules

def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # un téléphone saisi comme nombre dans Excel
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return re.sub(r"\s+", " ", str(value)).strip()


def _parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = _cell_text(value)
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    raise ValueError("date non reconnue (format attendu : JJ/MM/AAAA)")


def _plausible_birth(value: date) -> None:
    today = date.today()
    if value > today:
        raise ValueError("la date de naissance est dans le futur")
    if value < today - timedelta(days=366 * 40) or value > today - timedelta(days=366 * 2):
        raise ValueError("date de naissance invraisemblable pour un élève")


def _bool(raw: str) -> bool:
    low = raw.lower()
    if low in ("", "non", "n", "no", "0", "false", "faux"):
        return False
    if low in ("oui", "o", "yes", "y", "1", "true", "vrai", "x"):
        return True
    raise ValueError("valeur attendue : oui ou non")


def _gender(raw: str) -> StudentGender | None:
    low = _normalize_header(raw)
    if low == "":
        return None
    if low in ("m", "masculin", "garcon", "h", "homme"):
        return StudentGender.MALE
    if low in ("f", "feminin", "fille", "femme"):
        return StudentGender.FEMALE
    raise ValueError("valeur attendue : M ou F")


def _checked_text(raw: str, *, label: str, max_len: int, required: bool = False) -> str | None:
    if not raw:
        if required:
            raise ValueError(f"{label} obligatoire")
        return None
    if len(raw) > max_len:
        raise ValueError(f"{label} trop long ({max_len} caractères maximum)")
    if raw.startswith(_FORMULA_START):
        raise ValueError(f"{label} : un texte ne peut pas commencer par « {raw[0]} »")
    return raw


# ----------------------------------------------------------------- traitement

def _map_columns(header: list[object], report: ImportReport) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        label = _cell_text(cell)
        if not label:
            continue
        key = _ALIAS_LOOKUP.get(_normalize_header(label))
        if key is None:
            report.ignored_columns.append(label[:60])
        elif key not in mapping:
            mapping[key] = index
        else:
            report.ignored_columns.append(f"{label[:60]} (colonne en double)")
    missing = [name for key, name in (("last_name", "Nom"), ("first_name", "Prénom")) if key not in mapping]
    if missing:
        raise _fail("Colonne obligatoire absente : " + ", ".join(missing) + ". Utilisez le modèle fourni.")
    return mapping


def _identity(last: str, first: str, born: date | None) -> tuple[str, str, date | None]:
    return (last.casefold(), first.casefold(), born)


def process_import(
    db: Session, *, tenant_id, actor_id, content: bytes, filename: str, commit: bool,
) -> tuple[ImportReport, int]:
    table = read_table(content, filename)
    if not table:
        raise _fail("Le fichier est vide.")
    report = ImportReport()
    mapping = _map_columns(table[0], report)
    data_rows = [(number, row) for number, row in enumerate(table[1:], start=2) if any(_cell_text(c) for c in row)]
    if len(data_rows) > MAX_ROWS:
        raise _fail(f"Trop de lignes (maximum {MAX_ROWS} par import). Découpez le fichier.", 413)
    if not data_rows:
        raise _fail("Le fichier ne contient aucun élève (seulement l'en-tête).")
    report.total_rows = len(data_rows)

    if commit:
        # Un seul import à la fois par établissement ; le verrou est libéré au commit/rollback.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"student-import:{tenant_id}"})
        # Même fichier déjà importé (double clic, deux onglets, nouvel essai après coup) : les élèves sans date de
        # naissance ni matricule ne se distinguent pas des homonymes, donc on refuse par l'empreinte du fichier.
        fingerprint = hashlib.sha256(content).hexdigest()
        already = db.execute(
            select(AuditLog.created_at).where(
                AuditLog.tenant_id == tenant_id, AuditLog.action == "students.imported",
                AuditLog.metadata_json["sha256"].as_string() == fingerprint,
            ).limit(1)
        ).first()
        if already is not None:
            db.rollback()
            raise _fail(
                f"Ce fichier a déjà été importé le {already[0]:%d/%m/%Y à %H:%M}. Pour éviter les doublons, "
                "il ne peut pas être importé deux fois : modifiez-le (ou ajoutez seulement les nouveaux élèves).",
                status.HTTP_409_CONFLICT,
            )

    classes = {
        _normalize_header(c.name): c.id
        for c in db.execute(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id)).scalars()
    }
    existing_matricules = {
        m.casefold() for m in db.execute(
            select(Student.matricule).where(Student.tenant_id == tenant_id, Student.matricule.is_not(None))
        ).scalars()
    }
    existing_identities: set[tuple] = set()
    existing_names: set[tuple[str, str]] = set()
    for last, first, born in db.execute(
        select(Student.last_name, Student.first_name, Student.date_of_birth).where(Student.tenant_id == tenant_id)
    ):
        existing_identities.add(_identity(last, first, born))
        existing_names.add((last.casefold(), first.casefold()))

    seen_matricules: dict[str, int] = {}
    seen_identities: dict[tuple, int] = {}
    seen_names: dict[tuple[str, str], int] = {}
    to_insert: list[Student] = []

    def cell(row: list[object], key: str) -> object:
        index = mapping.get(key)
        return row[index] if index is not None and index < len(row) else None

    for number, row in data_rows:
        row_errors = 0

        def fail(fld: str, message: str) -> None:
            nonlocal row_errors
            row_errors += 1
            report.error(number, message, fld)

        values: dict[str, object] = {}
        for key, label, limit, required in (
            ("last_name", "Nom", 100, True), ("first_name", "Prénom", 100, True),
            ("matricule", "Matricule", 30, False), ("guardian_name", "Tuteur", 200, False),
        ):
            try:
                values[key] = _checked_text(_cell_text(cell(row, key)), label=label, max_len=limit, required=required)
            except ValueError as exc:
                fail(key, str(exc))

        class_id = None
        class_label = _cell_text(cell(row, "class"))
        if class_label:
            class_id = classes.get(_normalize_header(class_label))
            if class_id is None:
                fail("class", f"Classe introuvable : « {class_label[:40]} » (créez-la d'abord ou corrigez l'orthographe)")

        try:
            values["gender"] = _gender(_cell_text(cell(row, "gender")))
        except ValueError as exc:
            fail("gender", f"Sexe : {exc}")
        try:
            values["is_repeater"] = _bool(_cell_text(cell(row, "is_repeater")))
        except ValueError as exc:
            fail("is_repeater", f"Redoublant : {exc}")

        born: date | None = None
        raw_birth = cell(row, "date_of_birth")
        if _cell_text(raw_birth):
            try:
                born = _parse_date(raw_birth)
                _plausible_birth(born)
            except ValueError as exc:
                born = None
                fail("date_of_birth", f"Date de naissance : {exc}")

        phone = _cell_text(cell(row, "guardian_phone"))
        if phone and not _PHONE_RE.match(phone):
            fail("guardian_phone", "Téléphone : caractères non valides (chiffres, espaces, +, -, . et parenthèses seulement)")
        email = _cell_text(cell(row, "guardian_email"))
        if email:
            try:
                email = str(_EMAIL.validate_python(email)).lower()
            except ValidationError:
                fail("guardian_email", "Adresse e-mail non valide")

        # --- doublons ---
        matricule = values.get("matricule")
        if matricule:
            lowered = str(matricule).casefold()
            if lowered in existing_matricules:
                fail("matricule", f"Matricule « {matricule} » déjà utilisé dans l'établissement")
            elif lowered in seen_matricules:
                fail("matricule", f"Matricule « {matricule} » déjà présent à la ligne {seen_matricules[lowered]} du fichier")
            else:
                seen_matricules[lowered] = number
        if values.get("last_name") and values.get("first_name"):
            last, first = str(values["last_name"]), str(values["first_name"])
            if born is not None:
                ident = _identity(last, first, born)
                if ident in existing_identities:
                    fail("last_name", f"{first} {last} (né(e) le {born:%d/%m/%Y}) existe déjà dans l'établissement")
                elif ident in seen_identities:
                    fail("last_name", f"{first} {last} (né(e) le {born:%d/%m/%Y}) déjà présent à la ligne {seen_identities[ident]}")
                else:
                    seen_identities[ident] = number
            else:
                name_key = (last.casefold(), first.casefold())
                if name_key in existing_names or name_key in seen_names:
                    report.warn(number, f"Un élève nommé {first} {last} existe déjà : vérifiez qu'il ne s'agit pas d'un doublon")
                seen_names.setdefault(name_key, number)

        if row_errors:
            continue
        report.valid_rows += 1
        student = Student(
            tenant_id=tenant_id, first_name=str(values["first_name"]), last_name=str(values["last_name"]),
            date_of_birth=born, matricule=values.get("matricule"), gender=values.get("gender"),
            is_repeater=bool(values.get("is_repeater")), class_id=class_id,
            guardian_name=values.get("guardian_name"), guardian_phone=phone or None, guardian_email=email or None,
        )
        to_insert.append(student)
        if len(report.preview) < PREVIEW_ROWS:
            report.preview.append({
                "row": number, "last_name": student.last_name, "first_name": student.first_name,
                "class": class_label or None, "matricule": student.matricule,
            })

    imported = 0
    if commit:
        if report.error_count:
            db.rollback()  # libère le verrou ; rien n'a été écrit
            raise _fail(
                f"Import refusé : {report.error_count} erreur(s) dans le fichier. Aucun élève n'a été enregistré. "
                "Corrigez le fichier (utilisez l'aperçu) puis recommencez.", 422,
            )
        db.add_all(to_insert)
        log_action(
            db, tenant_id=tenant_id, actor_user_id=actor_id, action="students.imported", target_type="Student",
            metadata={
                "count": len(to_insert), "filename": filename[:100], "sha256": hashlib.sha256(content).hexdigest(),
                "warnings": report.warning_count,
            },
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise _fail("Conflit de matricule détecté pendant l'enregistrement : aucun élève n'a été importé, recommencez.", status.HTTP_409_CONFLICT)
        imported = len(to_insert)
    return report, imported


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow(TEMPLATE_EXAMPLE)
    return "﻿" + buffer.getvalue()  # BOM : Excel (FR) ouvre correctement les accents
