# Sécurité — état des lieux

## Mesures en place et vérifiées par des tests

| Mesure | Où | Test associé |
|---|---|---|
| Hachage Argon2id des mots de passe | `app/core/security.py` | — |
| Politique de mot de passe (longueur + complexité) | `app/core/security.py` | `test_rbac.py::test_weak_password_rejected_on_user_creation` |
| JWT access (15 min) + refresh (7 jours) avec rotation à l'usage | `app/services/auth_service.py` | `test_auth.py::test_refresh_token_rotates_and_old_one_is_rejected` |
| Refresh tokens stockés hachés en base (jamais en clair) | `app/models/refresh_token.py` | — |
| Verrouillage de compte après 5 échecs (15 min) | `app/services/auth_service.py` | `test_auth.py::test_account_locks_after_repeated_failures` |
| Rate limiting réseau sur `/auth/login` et `/auth/refresh` (5/minute par défaut) | `app/core/limiter.py` | `test_auth.py::test_default_login_rate_limit_is_strict_in_absence_of_override` |
| Messages d'erreur d'authentification génériques (pas d'énumération de comptes) | `app/services/auth_service.py` | `test_auth.py::test_login_unknown_email_returns_same_generic_401` |
| RBAC à 8 rôles (matrice centralisée dans `app/core/roles.py`, une seule source de vérité pour les permissions — direction, censeur, surveillant, comptable, secrétariat, enseignant, parent, super admin) | `app/core/deps.py`, `app/core/roles.py` | `test_rbac.py`, `test_roles_matrix.py` (9 tests) |
| **Authentification à deux facteurs (TOTP, RFC 6238)** — compatible Google Authenticator/Authy, secret jamais exposé après confirmation, jeton `MFA_PENDING` (5 min) qui ne permet rien d'autre que de compléter la connexion avec un code valide | `app/core/security.py`, `app/services/mfa_service.py`, `app/services/auth_service.py` | `test_mfa.py` (5 tests, dont la vérification qu'un jeton MFA_PENDING est rejeté par tout autre endpoint) |
| **Isolation des notifications par destinataire** : un parent ne voit jamais les notifications d'un autre compte | `app/services/notification_service.py` | `test_notifications.py` (5 tests) |
| **Reporting et audit réservés à la direction** : agrégation finances/notes/présences n'est exposée qu'au rôle ayant individuellement accès à ces trois domaines | `app/api/v1/reports.py`, `app/api/v1/audit.py` | `test_reporting_and_audit.py` (5 tests) |
| **Vue groupe multi-établissements sans affaiblissement du RLS** : le promoteur de réseau ne consulte que SON réseau (jamais un `network_id` passé en paramètre) ; chaque agrégat est lu établissement par établissement en basculant le contexte RLS, jamais via une requête cross-tenant | `app/services/network_reporting_service.py` | `test_network.py` (7 tests, dont l'isolation entre deux réseaux distincts) |
| **Isolation multi-tenant — défense en profondeur** : filtrage applicatif systématique + Row-Level Security PostgreSQL **forcée** (`FORCE ROW LEVEL SECURITY`, s'applique même au propriétaire de la table) | `app/db/session.py`, migration `3c234b5d9d72` | `test_tenant_isolation.py` (5 tests, dont 2 qui contournent volontairement la couche applicative) |
| **Isolation du portail parent** : un compte Parent n'accède qu'aux élèves pour lesquels un rattachement `GuardianLink` vérifié existe, créé exclusivement par la direction/le secrétariat — jamais en libre-service par le parent lui-même | `app/services/guardian_service.py`, migration `b7e388e822f9` | `test_guardian_portal.py` (7 tests, dont l'accès refusé — 404 — à un enfant non rattaché) |
| 404 (jamais 403) sur une ressource d'un autre établissement — ne confirme pas son existence | services `academic_service.py`, etc. | `test_tenant_isolation.py::test_school_admin_cannot_list_students_of_another_tenant` |
| Journal d'audit inviolable (pas d'endpoint de modification) sur les actions sensibles (connexion, verrouillage de compte, override d'une note verrouillée) | `app/models/audit.py`, `app/services/audit_service.py` | `test_grades.py::test_locked_grade_cannot_be_edited_by_teacher` |
| Verrouillage des notes après validation direction, avec traçabilité de tout override | `app/services/grade_service.py` | `test_grades.py` |
| En-têtes de sécurité HTTP (`X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, HSTS conditionnel) | `app/middleware/security_headers.py` | — |
| CORS restreint à une liste blanche d'origines configurée | `app/main.py` | — |
| Validation stricte des entrées (Pydantic : bornes de notes 0–20, montants positifs, format e-mail, etc.) | `app/schemas/*.py` | `test_grades.py::test_grade_value_out_of_range_is_rejected`, `test_finance.py::test_negative_amount_rejected` |
| Aucun secret en dur ; refus de démarrer en production avec la clé JWT par défaut | `app/main.py` | — |
| Pas de fuite de stack trace au client (exception handler générique + logging serveur) | `app/main.py` | — |
| Utilisateur non-root dans le conteneur Docker | `Dockerfile` | — |

## Hypothèses et limites assumées

- **Stockage du token côté frontend en `localStorage`.** Choix de simplicité pour ce MVP. En cas de faille XSS ailleurs dans l'application, un token en `localStorage` est accessible en JavaScript — un cookie `httpOnly` + `Secure` + `SameSite=Strict` réduirait cette surface. À corriger avant une mise en production réelle.
- **Rate limiting en mémoire (pas Redis).** Suffisant pour une instance unique ; derrière un load balancer multi-instances, chaque instance aurait son propre compteur — prévoir un backend Redis partagé avant scale-out.
- **MFA disponible mais non imposé.** N'importe quel rôle peut l'activer (`/auth/mfa/setup`), mais rien n'empêche un compte Direction ou Super Admin de s'en passer — pas de politique organisationnelle qui l'imposerait par rôle. Pas de codes de secours (backup codes) en cas de perte du téléphone : la seule voie de récupération actuelle est une intervention manuelle en base par un opérateur technique, à formaliser avant production.
- **Pas d'audit de sécurité externe / test d'intrusion.** Ce livrable a été testé par son propre auteur avec des tests automatisés ciblés — cela ne remplace pas une revue de sécurité indépendante avant un déploiement réel avec des données réelles d'élèves.
- **Restriction enseignant par classe assignée non implémentée** (voir `README.md`) — un enseignant a accès en lecture à tous les élèves de son établissement, pas seulement sa classe. À corriger avant production si ce niveau de cloisonnement est requis.
- **Rôles fixes, pas configurables par établissement** — les 8 rôles sont un enum, pas un système de permissions composables (voir `README.md`).
- **Politique de mot de passe non testée contre des listes de mots de passe compromis** (type `Have I Been Pwned`) — seulement longueur + complexité de caractères.
- **Pas de chiffrement applicatif au repos** des données sensibles (au-delà du chiffrement disque éventuel fourni par l'hébergeur PostgreSQL) — à évaluer selon les exigences réglementaires locales (loi n°2017-20, Bénin) avant production.

## Bugs trouvés et corrigés pendant la construction

Documentés ici par transparence — trouvés par les tests automatisés, pas en production :

1. **Double comptage d'un paiement** dans le recalcul du solde d'une facture (`finance_service.py`) — le nouveau paiement était compté deux fois si la relation SQLAlchemy était déjà chargée.
2. **Perte du contexte tenant après `commit()`** (`db/session.py`) — `SET LOCAL app.current_tenant` ne survit pas à une transaction validée ; un `db.refresh()` juste après un `commit()` (motif utilisé dans tous les services) se retrouvait sans contexte RLS, cassant potentiellement l'isolation sur la requête suivante. Corrigé par un event listener SQLAlchemy qui réapplique le contexte à chaque nouvelle transaction de la session.
3. **Incohérence de casse des types enum PostgreSQL** — SQLAlchemy stocke par défaut le NOM Python des membres d'enum (majuscules) plutôt que leur VALEUR (minuscules) sauf si `values_callable` est fourni. Les 5 enums du schéma (rôles, statuts) étaient ainsi stockés en majuscules alors qu'une migration ultérieure ajoutait de nouveaux rôles en minuscules — incohérence qui aurait empêché la création de tout censeur/surveillant/comptable. Corrigé par une migration de renormalisation et l'ajout de `values_callable` sur les 5 colonnes concernées.
