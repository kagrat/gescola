# GESCOLA — Phases 1, 2 et 3

Plateforme de gestion scolaire pour établissements ouest-africains — socle backend sécurisé et testé, avec une interface web couvrant l'essentiel du flux quotidien de chaque intervenant.

**⚠️ Lire avant tout : périmètre réel de ce livrable**

Le cahier des charges complet prévoit, en Phase 3, une application mobile native et une conformité réglementaire multi-pays. Ceci **n'est pas** dans ce livrable : une application mobile nécessite un tout autre projet (Xcode/Play Store) et une conformité multi-pays nécessite un conseil juridique local par pays — je ne simule aucun des deux. En revanche, l'essentiel des Phases 1, 2 et 3 fonctionnellement atteignables dans ce format (backend + web) est construit, testé contre une vraie base PostgreSQL, et vérifié de bout en bout avec un navigateur automatisé. Voir [Périmètre et limites assumées](#périmètre-et-limites-assumées) pour la liste précise de ce qui manque avant une mise en production.

## Ce qui est inclus

**Phase 1 — Socle**
- **Backend FastAPI + PostgreSQL** : authentification JWT (access + refresh avec rotation), RBAC à 8 rôles couvrant chaque intervenant d'un établissement, isolation multi-tenant en défense en profondeur (filtrage applicatif **et** Row-Level Security PostgreSQL forcée), verrouillage de compte après échecs répétés, hachage Argon2, rate limiting, en-têtes de sécurité HTTP, journal d'audit inviolable.
- **Matrice de rôles complète** (`app/core/roles.py`), un point unique de vérité pour les permissions :

  | Rôle | Peut |
  |---|---|
  | Super administrateur | Gérer les établissements et les réseaux (hors périmètre d'un établissement) |
  | Promoteur de réseau (`network_admin`) | Vue consolidée en lecture seule sur les établissements de son réseau — effectifs, encaissé/dû, taux de recouvrement — sans accès aux données opérationnelles de chaque école |
  | Direction (`school_admin`) | Tout sur son établissement : comptes, élèves, notes (y compris déverrouillage tracé), présences, finances, rapports, audit |
  | Censeur (`censor`) | Vie scolaire : présences, consultation des notes, verrouillage des notes en fin de période (validation des bulletins) |
  | Surveillant (`supervisor`) | Présences et discipline uniquement — pas les notes, pas les finances |
  | Comptable (`accountant`) | Facturation, paiements, cantine (génère des factures) |
  | Secrétariat (`staff`) | Inscriptions et référentiel (élèves, classes, matières, bibliothèque) — pas les notes, pas les finances |
  | Enseignant (`teacher`) | Saisie des notes et des présences |
  | Parent (`parent`) | Lecture seule, strictement limitée aux enfants pour lesquels un rattachement vérifié existe |

- **Portail parent fonctionnel** : table `GuardianLink` (rattachement vérifié, créé uniquement par la direction/secrétariat — jamais en libre-service), endpoints dédiés qui vérifient le rattachement avant toute réponse (404, jamais 403).
- Élèves, classes, matières, notes (moyennes pondérées + verrouillage post-validation), présences, finances (factures/paiements).

**Phase 2 — Extension fonctionnelle**
- **Authentification à deux facteurs (TOTP)** : activation/désactivation par l'utilisateur, connexion en deux étapes, compatible avec toute application d'authentification standard (Google Authenticator, Authy…) — aucune dépendance à un service tiers.
- **Centre de notifications internes + relances de factures** : un accountant/school_admin peut relancer une facture impayée en un clic, chaque parent rattaché reçoit une notification consultable dans son portail. *(Notifications in-app uniquement — voir limites ci-dessous pour le SMS/e-mail réel.)*
- **Tableau de bord de reporting avancé** : indicateurs consolidés (effectifs, encaissé/restant dû, taux de présence, moyenne par classe) avec graphiques réels, réservé à la direction.
- **Journal d'audit consultable** depuis l'interface (direction uniquement).

**Phase 3 — Expansion (partielle, honnêtement scopée)**
- **Module Cantine** : formules tarifaires + abonnements, chaque abonnement générant automatiquement sa facture dans le module finance (un seul système de facturation, pas deux parallèles).
- **Module Bibliothèque** : catalogue d'ouvrages, emprunts avec gestion des exemplaires disponibles, retours.
- Application mobile native, intégration mobile money réelle, conformité multi-pays : **non livrées** — voir limites.

**Transverse**
- **70 tests automatisés, 96 % de couverture**, exécutés contre une vraie base PostgreSQL (RLS forcée sur chaque table sensible).
- **Frontend React + Vite + Tailwind** couvrant : connexion (avec étape MFA), tableau de bord par rôle, fiche élève (notes/présences/finances), personnel, portail parent, rapports, sécurité, notifications, audit, cantine, bibliothèque — connecté au vrai backend, testé de bout en bout avec un navigateur automatisé (captures ci-dessous). **Design aligné sur la maquette de référence fournie** (`gescola-maquette.html`) : palette navy/cream/sky/emerald/coral, typographie Lora + Inter, sidebar à icônes, pastilles de statut à point coloré, avatars à initiales.
- Migrations Alembic, Dockerfile, docker-compose, configuration par variables d'environnement (aucun secret en dur).



## Démarrage rapide (Docker)

```bash
cd backend
cp .env.example .env   # puis éditer JWT_SECRET_KEY au minimum
docker compose up --build
```

L'API est disponible sur `http://localhost:8000` (documentation interactive sur `/docs` hors production).

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Le frontend est disponible sur `http://localhost:5173`.

## Démarrage sans Docker (développement)

```bash
# PostgreSQL doit être installé et démarré localement
createuser gescola_app --pwprompt
createdb gescola_dev --owner gescola_app
createdb gescola_test --owner gescola_app

cd backend
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

### Lancer les tests

```bash
cd backend
DATABASE_URL="postgresql+psycopg2://gescola_app:<motdepasse>@localhost:5432/gescola_test" \
JWT_SECRET_KEY="test-secret" \
pytest -v --cov=app
```

## Créer le premier compte (Super Administrateur)

Aucun endpoint public de création de Super Admin n'existe (volontairement — un tel endpoint serait une porte dérobée). Créez le premier compte via un script :

```python
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password

db = SessionLocal()
db.add(User(tenant_id=None, email="admin@votre-domaine.bj",
            hashed_password=hash_password("UnMotDePasseFort#123"),
            full_name="Super Admin", role=UserRole.SUPER_ADMIN))
db.commit()
```

Le Super Admin crée ensuite un établissement (`POST /api/v1/tenants`) puis un compte Direction pour cet établissement (`POST /api/v1/users`, en s'authentifiant avec un compte Direction créé manuellement de la même façon, scoped au tenant).

## Périmètre et limites assumées

Cette section documente honnêtement ce qui **n'est pas** couvert par ce livrable, pour éviter toute fausse impression de complétude :

| Sujet | État |
|---|---|
| Restriction enseignant par classe assignée | **Simplifiée.** Un enseignant voit actuellement tous les élèves/classes/matières de son établissement, pas seulement les siens. Nécessite une table d'affectation enseignant↔classe/matière avant mise en production. |
| Rôles configurables par établissement | **Non implémenté.** Les 8 rôles sont fixes (enum), pas un système de permissions composables où chaque établissement définirait ses propres intitulés/droits. |
| Auto-inscription parent | **Volontairement absente.** Un parent ne peut jamais se rattacher lui-même à un élève — c'est toujours un acte administratif (direction/secrétariat). C'est un choix de sécurité, pas un oubli. |
| Mobile money (MoMo, Moov, Wave) | **Non intégré.** Le champ `method` du paiement accepte `mobile_money` mais aucun appel à une passerelle réelle n'est fait — c'est un enregistrement manuel. Une vraie intégration nécessite un partenariat et des identifiants API réels. |
| **SMS / e-mail réels** | **Non implémenté.** Les « relances de factures » (Phase 2) sont des notifications **internes à l'application** (consultables dans le portail parent), pas des SMS ni des e-mails envoyés hors de GESCOLA — cela nécessiterait un partenariat avec un opérateur télécom ou un service d'e-mailing transactionnel, avec des identifiants réels que je ne peux pas fabriquer. |
| Synchronisation offline Electron | **Non implémentée.** L'architecture (PostgreSQL + API stateless) le permet, mais c'est un chantier à part entière. |
| Bulletins au format ministériel | **Non implémenté.** Le calcul de moyenne existe (`GET /students/{id}/average`), pas la génération PDF au format officiel. |
| Vie scolaire / discipline (incidents, sanctions) | **Non implémenté.** Le rôle Surveillant existe et gère les présences, mais aucun module de suivi disciplinaire (incidents, sanctions, carnet de correspondance numérique) n'a été construit. |
| **Application mobile native** | **Non livrée.** Prévue en Phase 3 du cahier des charges ; nécessite un projet séparé (React Native ou équivalent, publication App Store/Play Store) — hors de portée d'un livrable produit dans cet environnement. L'API REST existante pourrait servir de base à une telle application sans modification. |
| **Vue « groupe » multi-établissements** | **Implémentée.** Nouveau rôle `network_admin` (promoteur), modèle `SchoolNetwork`, tableau de bord consolidé (`GET /network/overview`) agrégeant effectifs, encaissé/dû et taux de recouvrement par établissement — provisionné exclusivement par le Super Admin (`POST /networks`, `/networks/{id}/tenants/{tenant_id}`, `/networks/{id}/admins`). Lecture établissement par établissement en basculant le contexte RLS, jamais de requête cross-tenant : aucune policy RLS existante n'a été affaiblie pour livrer cette fonctionnalité. |
| **Cycles scolaires** (maternelle/primaire/secondaire) | **Implémenté.** Champ `cycle` sur les classes (`POST /classes`), utilisé pour segmenter les effectifs — pas encore affiché en agrégat par cycle dans la vue groupe (seulement par établissement pour l'instant). |
| **Écrans présents dans la maquette de référence mais non construits** | La maquette (`gescola-maquette.html`) illustre aussi : un **emploi du temps / classes** (aucun modèle `Course`/`Schedule` n'existe côté backend), une **messagerie interne** parent↔personnel (aucun modèle `Message`/`Thread`), et une **connexion parent par téléphone + code SMS** (le parent se connecte par e-mail + mot de passe dans ce livrable — un vrai OTP SMS nécessite une passerelle télécom réelle, voir plus haut). Le design visuel de ces écrans a été vu et compris mais aucun n'a été implémenté : je préfère le dire explicitement plutôt que de laisser croire que la maquette est entièrement couverte. |
| **Conformité réglementaire multi-pays** | **Non livrée.** Le champ pays/devise n'existe pas encore sur `Tenant` ; une expansion réelle vers d'autres pays nécessite un conseil juridique local par pays, pas seulement du code. |
| Frontend | Couvre l'essentiel du flux quotidien de chaque rôle : connexion (avec étape MFA), tableau de bord, fiche élève (notes/présences/finances), personnel, portail parent, **rapports avec graphiques, sécurité (MFA), notifications, journal d'audit, cantine, bibliothèque**. |
| Stockage du token côté frontend | `localStorage`, par simplicité de ce MVP. Un cookie `httpOnly` + `Secure` serait préférable en production pour réduire l'exposition en cas de XSS — voir `SECURITY.md`. |
| Déploiement production | Aucun hébergement réel n'a été mis en place (ceci reste un environnement de développement/démonstration). |

Le détail des mesures de sécurité effectivement en place, et leurs limites, est dans [`SECURITY.md`](./SECURITY.md).
"# gescola" 
