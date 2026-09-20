"""
Matrice des rôles et de leurs responsabilités.

Chaque intervenant d'un établissement correspond à un rôle précis. Ce module
centralise les regroupements utilisés par les endpoints (`require_roles(...)`)
pour qu'une même liste de rôles autorisés ne soit jamais dupliquée à la main
dans plusieurs fichiers (source d'incohérences si l'un d'eux est oublié lors
d'une évolution future).

Résumé des responsabilités par rôle :

  SUPER_ADMIN   Éditeur SaaS. Gère les établissements eux-mêmes (hors périmètre
                d'un établissement en particulier).
  SCHOOL_ADMIN  Directeur/directrice. Accès complet à son établissement :
                utilisateurs, élèves, classes, matières, notes (y compris
                déverrouillage exceptionnel tracé), présences, finances.
  CENSOR        Censeur / surveillant général. Vie scolaire : présences,
                consultation des notes, verrouillage des notes en fin de
                période (validation des bulletins) — mais pas de gestion des
                comptes utilisateurs ni des finances.
  SUPERVISOR    Surveillant. Présences et discipline uniquement — pas d'accès
                aux notes ni aux finances.
  ACCOUNTANT    Comptable. Facturation et paiements uniquement.
  STAFF         Secrétariat. Inscriptions et administratif général : élèves,
                classes, matières — pas les notes, pas les finances.
  TEACHER       Enseignant·e. Saisie des notes et des présences.
  PARENT        Parent/tuteur. Lecture seule, strictement limitée aux enfants
                pour lesquels un lien vérifié existe (voir guardian_service).
"""
from app.models.user import UserRole

# Gestion des comptes utilisateurs de l'établissement : réservé à la direction.
CAN_MANAGE_USERS = (UserRole.SCHOOL_ADMIN,)

# Inscriptions et référentiel (élèves, classes, matières) : direction + secrétariat.
CAN_MANAGE_REGISTRY = (UserRole.SCHOOL_ADMIN, UserRole.STAFF)

# Lecture du référentiel élèves/classes/matières : tout le personnel encadrant.
CAN_READ_REGISTRY = (
    UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.TEACHER, UserRole.CENSOR, UserRole.SUPERVISOR,
)

# Saisie des notes : enseignants + direction (la direction peut saisir en cas de besoin).
CAN_WRITE_GRADES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN)

# Lecture des notes : personnel encadrant pédagogique (pas le surveillant, dont le rôle est disciplinaire).
CAN_READ_GRADES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.CENSOR)

# Verrouillage des notes en fin de période (validation des bulletins) : direction + censeur.
CAN_LOCK_GRADES = (UserRole.SCHOOL_ADMIN, UserRole.CENSOR)

# Modification d'une note déjà verrouillée (override exceptionnel, tracé) : direction + censeur.
CAN_OVERRIDE_LOCKED_GRADES = (UserRole.SCHOOL_ADMIN, UserRole.CENSOR)

# Présences : tout le personnel encadrant (y compris discipline).
CAN_MANAGE_ATTENDANCE = (
    UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.CENSOR, UserRole.SUPERVISOR,
)

# Finances : direction + comptable uniquement.
CAN_MANAGE_FINANCE = (UserRole.SCHOOL_ADMIN, UserRole.ACCOUNTANT)

# Rattachement d'un compte parent à un élève : direction + secrétariat (acte administratif).
CAN_MANAGE_GUARDIAN_LINKS = (UserRole.SCHOOL_ADMIN, UserRole.STAFF)

# Rôles internes à l'établissement pouvant être créés par la direction via /users
# (le Super Admin n'est jamais créé depuis un établissement — voir user_service).
TENANT_INTERNAL_ROLES = (
    UserRole.SCHOOL_ADMIN, UserRole.CENSOR, UserRole.SUPERVISOR,
    UserRole.ACCOUNTANT, UserRole.STAFF, UserRole.TEACHER, UserRole.PARENT,
)
