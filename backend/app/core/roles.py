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
  FOUNDER       Fondateur/promoteur — propriétaire de l'établissement. Hérite
                de TOUS les pouvoirs de la Direction (voir plus bas, chaque
                regroupement l'inclut systématiquement aux côtés de
                SCHOOL_ADMIN), plus deux pouvoirs qui lui sont EXCLUSIFS :
                créer/gérer le compte Direction, et porter l'abonnement
                GESCOLA de l'établissement. Rôle facultatif : un établissement
                peut très bien n'avoir qu'un Directeur, sans Fondateur
                au-dessus (voir signup_service, tenant_service, user_service).
  SCHOOL_ADMIN  Directeur/directrice. Accès complet à son établissement :
                utilisateurs, élèves, classes, matières, notes (y compris
                déverrouillage exceptionnel tracé), présences, finances —
                mais rend compte au Fondateur s'il existe, et ne peut ni le
                créer, ni le modifier, ni créer un autre compte Direction.
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

# Le Fondateur est ajouté systématiquement partout où SCHOOL_ADMIN apparaît
# dans ce fichier : il hérite de tous les pouvoirs de la Direction, sans
# exception. Les deux pouvoirs qui lui sont exclusifs (créer/gérer la
# Direction, abonnement) sont vérifiés directement dans les services
# concernés (user_service.create_user, api/v1/billing.py), pas ici.

# Gestion des comptes utilisateurs de l'établissement : direction + fondateur.
CAN_MANAGE_USERS = (UserRole.SCHOOL_ADMIN, UserRole.FOUNDER)

# Inscriptions et référentiel (élèves, classes, matières) : direction + secrétariat + fondateur.
CAN_MANAGE_REGISTRY = (UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.FOUNDER)

# Lecture du référentiel élèves/classes/matières : tout le personnel encadrant.
# Le comptable y est inclus : sans cet accès, il n'a aucun moyen de retrouver
# un élève pour consulter ou encaisser ses factures (bug réel trouvé et
# corrigé — voir SECURITY.md).
CAN_READ_REGISTRY = (
    UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.TEACHER, UserRole.CENSOR, UserRole.SUPERVISOR,
    UserRole.ACCOUNTANT, UserRole.FOUNDER,
)

# Saisie des notes : enseignants + direction (la direction peut saisir en cas de besoin) + fondateur.
CAN_WRITE_GRADES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.FOUNDER)

# Lecture des notes : personnel encadrant pédagogique (pas le surveillant, dont le rôle est disciplinaire).
CAN_READ_GRADES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.CENSOR, UserRole.FOUNDER)

# Verrouillage des notes en fin de période (validation des bulletins) : direction + censeur + fondateur.
CAN_LOCK_GRADES = (UserRole.SCHOOL_ADMIN, UserRole.CENSOR, UserRole.FOUNDER)

# Modification d'une note déjà verrouillée (override exceptionnel, tracé) : direction + censeur + fondateur.
CAN_OVERRIDE_LOCKED_GRADES = (UserRole.SCHOOL_ADMIN, UserRole.CENSOR, UserRole.FOUNDER)

# Présences : tout le personnel encadrant (y compris discipline).
CAN_MANAGE_ATTENDANCE = (
    UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.CENSOR, UserRole.SUPERVISOR, UserRole.FOUNDER,
)

# Finances : direction + comptable + fondateur uniquement.
CAN_MANAGE_FINANCE = (UserRole.SCHOOL_ADMIN, UserRole.ACCOUNTANT, UserRole.FOUNDER)

# Rattachement d'un compte parent à un élève : direction + secrétariat + fondateur (acte administratif).
CAN_MANAGE_GUARDIAN_LINKS = (UserRole.SCHOOL_ADMIN, UserRole.STAFF, UserRole.FOUNDER)

# Coordination pédagogique : affectations enseignant/classe/matière et emploi
# du temps — rôle traditionnellement porté par le censeur (« censeur des
# études ») en plus de la direction et du fondateur.
CAN_MANAGE_TEACHING = (UserRole.SCHOOL_ADMIN, UserRole.CENSOR, UserRole.FOUNDER)

# Rôles à portée "direction" utilisés directement dans certains routers
# (rapports, journal d'audit, paramètres établissement — écriture, facturation
# établissement) plutôt que via un regroupement métier dédié.
CAN_ACT_AS_DIRECTION = (UserRole.SCHOOL_ADMIN, UserRole.FOUNDER)

# Rôles internes à l'établissement pouvant être créés via /users. FOUNDER n'y
# figure jamais : il n'est créé qu'à la création de l'établissement (voir
# tenant_service, signup_service) — jamais via cet endpoint, même par
# lui-même, pour ne jamais avoir d'ambiguïté sur "qui est LE fondateur" d'un
# établissement. La création d'un compte SCHOOL_ADMIN via cet endpoint est en
# outre réservée au FOUNDER (vérifié dans user_service.create_user, pas ici) :
# la Direction ne peut pas se cloner ni créer un autre compte Direction.
TENANT_INTERNAL_ROLES = (
    UserRole.SCHOOL_ADMIN, UserRole.CENSOR, UserRole.SUPERVISOR,
    UserRole.ACCOUNTANT, UserRole.STAFF, UserRole.TEACHER, UserRole.PARENT,
)
