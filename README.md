# GESCOLA — Gestion scolaire multi-établissements

Plateforme de gestion scolaire pour établissements ouest-africains — socle backend sécurisé et testé, avec une interface web couvrant l'essentiel du flux quotidien de chaque intervenant.

**⚠️ Lire avant tout : périmètre réel**

Ce dépôt est un produit en construction, pas un produit fini. **Tout ce qui reste à faire — sans exception — est tenu dans [`ROADMAP.md`](./ROADMAP.md)** (registre unique, statut et priorité de chaque point). Ce README décrit ce qui est *livré*, et la section « Périmètre et limites assumées » ce qui ne l'est pas encore. Une application mobile native, l'intégration de paiement mobile money réel, l'envoi réel de SMS/e-mails et la conformité réglementaire multi-pays ne sont **pas** livrés (projets ou partenariats distincts) : je n'en simule aucun.

**Numérotation :** les sections ci-dessous sont des *livraisons* successives (Livraison 1 à N). Elles ne correspondent ni aux « phases » du cahier des charges initial, ni aux 5 étapes du plan convenu — la table de correspondance est en tête de `ROADMAP.md`.

## Ce qui est inclus

**Livraison 1 — Socle**
- **Backend FastAPI + PostgreSQL** : authentification JWT (access + refresh avec rotation), RBAC à 10 rôles couvrant chaque intervenant d'un établissement, isolation multi-tenant en défense en profondeur (filtrage applicatif **et** Row-Level Security PostgreSQL forcée), verrouillage de compte après échecs répétés, hachage Argon2, rate limiting, en-têtes de sécurité HTTP, journal d'audit inviolable.
- **Matrice de rôles complète** (`app/core/roles.py`), un point unique de vérité pour les permissions :

  | Rôle | Peut |
  |---|---|
  | Super administrateur | Gérer les établissements et les réseaux (hors périmètre d'un établissement) |
  | Promoteur de réseau (`network_admin`) | Vue consolidée en lecture seule sur les établissements de son réseau — effectifs, encaissé/dû, taux de recouvrement — sans accès aux données opérationnelles de chaque école |
  | Fondateur (`founder`) | Propriétaire de l'établissement, au-dessus de la Direction (facultatif) : hérite de tous ses pouvoirs, crée/gère le compte Direction, porte l'abonnement |
  | Direction (`school_admin`) | Tout sur son établissement : comptes, élèves, notes (y compris déverrouillage tracé), présences, finances, rapports, audit |
  | Censeur (`censor`) | Vie scolaire : présences, consultation des notes, verrouillage des notes en fin de période (validation des bulletins) |
  | Surveillant (`supervisor`) | Présences et discipline uniquement — pas les notes, pas les finances |
  | Comptable (`accountant`) | Facturation, paiements, cantine (génère des factures) |
  | Secrétariat (`staff`) | Inscriptions et référentiel (élèves, classes, matières, bibliothèque) — pas les notes, pas les finances |
  | Enseignant (`teacher`) | Saisie des notes et des présences |
  | Parent (`parent`) | Lecture seule, strictement limitée aux enfants pour lesquels un rattachement vérifié existe |

- **Portail parent fonctionnel** : table `GuardianLink` (rattachement vérifié, créé uniquement par la direction/secrétariat — jamais en libre-service), endpoints dédiés qui vérifient le rattachement avant toute réponse (404, jamais 403).
- Élèves, classes, matières, notes (moyennes pondérées + verrouillage post-validation), présences, finances (factures/paiements).

**Livraison 2 — Extension fonctionnelle**
- **Authentification à deux facteurs (TOTP)** : activation/désactivation par l'utilisateur, connexion en deux étapes, compatible avec toute application d'authentification standard (Google Authenticator, Authy…) — aucune dépendance à un service tiers.
- **Centre de notifications internes + relances de factures** : un accountant/school_admin peut relancer une facture impayée en un clic, chaque parent rattaché reçoit une notification consultable dans son portail. *(Notifications in-app uniquement — voir limites ci-dessous pour le SMS/e-mail réel.)*
- **Tableau de bord de reporting avancé** : indicateurs consolidés (effectifs, encaissé/restant dû, taux de présence, moyenne par classe) avec graphiques réels, réservé à la direction.
- **Journal d'audit consultable** depuis l'interface (direction uniquement).

**Livraison 3 — Expansion (partielle, honnêtement scopée)**
- **Module Cantine** : formules tarifaires + abonnements, chaque abonnement générant automatiquement sa facture dans le module finance (un seul système de facturation, pas deux parallèles).
- **Module Bibliothèque** : catalogue d'ouvrages, emprunts avec gestion des exemplaires disponibles, retours.
- Application mobile native, intégration mobile money réelle, conformité multi-pays : **non livrées** — voir limites.

**Livraison 4 — Produit SaaS complet (inscription en libre-service + facturation plateforme)**
- **Inscription en libre-service** (`POST /auth/signup`, page `/inscription`) : un directeur crée son établissement, son compte Direction et démarre son essai gratuit de 14 jours en une seule étape, sans intervention du Super Admin — connexion automatique ensuite. Limité à 3 inscriptions/heure/IP (pas de CAPTCHA réel intégré, voir limites).
- **Création d'établissement par le Super Admin** (`POST /tenants`, console `/`) : crée l'établissement **et** son premier compte Direction en une seule action (identifiant + mot de passe saisis directement dans le formulaire), avec le même essai gratuit automatique que l'inscription en libre-service — plus besoin de script Python pour créer les identifiants d'une école.
- **Facturation plateforme** (GESCOLA → établissements, à distinguer du module finance école → parents) : plans tarifaires, abonnement par établissement (essai → actif → retard → suspendu → résilié), factures mensuelles générées à partir du plan, paiements enregistrés manuellement. **La suspension bloque réellement l'accès** (`402 Payment Required` sur tous les endpoints scoped-tenant), pas seulement un badge visuel — et se lève automatiquement dès qu'un paiement couvre le montant dû.
- **Console Super Admin** (enfin une vraie interface, pas seulement `/docs`) : liste des établissements avec statut d'abonnement, création d'établissement, gestion des plans, et par établissement : changement de plan/statut, génération de facture, encaissement de paiement.
- **Identité légale de l'établissement** (page « Paramètres établissement », Direction uniquement) : nom commercial, RCCM, IFU, localisation, logo — destinés à l'en-tête des documents officiels (bulletins, attestations) une fois leur génération construite.
- **Signature et tampon personnels** (page « Profil », tous rôles) : chaque utilisateur renseigne sa propre signature et son propre tampon depuis son interface, une fois connecté — jamais rempli par un tiers, y compris la Direction.
- Les établissements créés avant cette fonctionnalité (ou manuellement sans abonnement) restent **non restreints** (grandfathering) — la facturation est additive, jamais rétroactive.

**Livraison 5 — Organisation pédagogique complète (classes, affectations, emploi du temps)**
- **Gestion des classes et matières** (page « Classes & Matières », Direction/secrétariat) : le backend existait déjà, l'écran manquait — désormais construit, avec les classes regroupées par cycle (maternelle/primaire/secondaire), fidèle à la structure réelle d'un établissement ouest-africain.
- **Affectations enseignant ↔ classe ↔ matière** (page « Affectations », Direction/Censeur) : reflète l'organisation réelle (« M. Dupont enseigne les Mathématiques en 6ème A »). **Referme une vraie faille de sécurité** : un enseignant ayant au moins une affectation enregistrée ne peut désormais noter que ses classes et matières assignées (`403` sinon) — les enseignants sans aucune affectation restent non restreints (grandfathering), pour ne pas bloquer un établissement en cours de configuration.
- **Emploi du temps** (page « Emploi du temps » pour la Direction/Censeur, « Mon emploi du temps » en lecture seule pour chaque enseignant) : créneaux hebdomadaires récurrents avec **détection réelle des conflits d'horaire** — impossible d'assigner deux matières à la même classe sur un créneau qui se chevauche, ni un même enseignant sur deux classes en même temps.
- **Rôle Censeur étendu** plutôt qu'un nouveau rôle redondant : la coordination pédagogique (affectations, emploi du temps) a été confiée au Censeur existant, cohérent avec son rôle réel de « censeur des études » dans un lycée francophone, plutôt que d'ajouter un « Directeur des études » qui aurait fait doublon.

**Livraison 6 — Audit complet et fermeture des manques (activation de fonctionnalités déjà construites, complétion côté élèves/enseignants)**
- **Rattachement d'un élève à sa classe** : le formulaire de création d'élève n'exposait pas ce champ (pourtant supporté par le backend depuis le début), et rien ne permettait de le modifier après coup. **Corrigé** : sélecteur de classe à la création, modification depuis la fiche élève (`PATCH /students/{id}`, nouveau). Ce manque bloquait en pratique toute la chaîne « affectation enseignant → emploi du temps → saisie de notes » construite en Livraison 5, puisque aucun élève n'était jamais rattaché à une classe.
- **« Mes classes »** (nouvel écran enseignant) : liste des affectations personnelles avec **saisie groupée des notes** pour toute une classe en une seule action, plutôt que devoir ouvrir chaque fiche élève une par une — le vrai flux de travail d'un enseignant.
- **Rattachements parents consultables et révocables** : `GET`/`DELETE /guardian-links` (n'existaient pas — on pouvait créer un rattachement mais jamais le voir ni le retirer).
- **Activation de fonctionnalités déjà construites mais invisibles dans l'interface** : « Mon abonnement » côté Direction (statut d'essai, jours restants, historique des factures — jusque-là visible seulement par le Super Admin), gestion complète des réseaux dans la console Super Admin (création de réseau, rattachement d'un établissement, création de compte promoteur — jusque-là accessible uniquement via `/docs`), relance de facture impayée, retour de livre et historique d'emprunts, liste des abonnements cantine, modification d'une note déjà verrouillée.
- **Décision assumée : pas de compte élève.** Seuls les parents ont un accès en lecture (déjà construit). Ajouter un rôle Élève à part entière — avec sa propre authentification, ses propres écrans et ses propres tests de sécurité — est un chantier comparable en ampleur à la facturation plateforme ou à l'emploi du temps, pas une case à cocher en passant. Vu que les établissements ouest-africains ciblés font très majoritairement transiter l'information par les parents plutôt que par un accès direct de l'élève, ce n'est pas priorisé dans ce livrable — mais c'est une extension naturelle si un client le demande.

**Livraison 7 — Audit complet des rôles (frontend) et tableaux de bord spécifiques**
- **Bug trouvé et corrigé** : un enseignant voyait les boutons de création de classe/élève dans l'interface, alors que le backend les refusait déjà (`403`) — aucune donnée n'a jamais pu être créée par un rôle non habilité, mais l'expérience était trompeuse. Audit systématique des 24 pages du frontend contre la restriction réelle de chaque endpoint backend : **9 pages** présentaient ce même défaut (Rapports, Journal d'audit, Personnel, Mon abonnement, Facturation d'un établissement, Bibliothèque, Cantine, Affectations, Emploi du temps). Corrigées avec un composant `RequireRole` réutilisable (accès direct par URL désormais bloqué proprement, avec un message clair, plutôt qu'une page à moitié cassée) et un masquage ciblé des actions de création/modification sur les pages à lecture large (Classes & Matières, Élèves, Paramètres établissement).
- **Bug bloquant trouvé en creusant, plus grave que celui signalé** : le comptable n'avait **aucun moyen de lister les élèves** (`GET /students` renvoyait `403`), donc aucun moyen de retrouver un élève pour le facturer ou encaisser un paiement — le rôle était inutilisable en pratique malgré des droits corrects sur les finances elles-mêmes. Corrigé en l'ajoutant à `CAN_READ_REGISTRY` côté backend (lecture seule ; la création/modification d'élèves reste réservée à Direction/secrétariat), avec un test dédié qui protège cette correction contre toute régression future.
- **Tableaux de bord spécifiques par rôle** : l'écran d'accueil générique, identique pour Direction/secrétariat/enseignant/censeur/surveillant/comptable, a été remplacé par **6 tableaux de bord distincts** — chacun avec ses propres indicateurs et raccourcis pertinents à son métier réel (l'enseignant est orienté vers « Mes classes », le censeur vers les affectations et l'emploi du temps, le comptable vers la facturation et la cantine, le surveillant est explicitement informé que son accès se limite aux présences).

**Livraison 8 — Hiérarchie Fondateur / Direction**
- **Nouveau rôle `founder`** (Fondateur), au-dessus de la Direction dans un même établissement — reflète la réalité des écoles privées ouest-africaines : un propriétaire/investisseur souvent en retrait du quotidien, mais avec l'autorité ultime, et un Directeur opérationnel qui lui rend compte. **Facultatif** : un établissement peut toujours n'avoir qu'un Directeur, sans Fondateur au-dessus (rétrocompatible avec tous les établissements déjà créés).
- **Le flux de création change de nature** : `POST /tenants` (Super Admin) et l'inscription en libre-service (`POST /auth/signup`) créent désormais un compte **Fondateur**, plus un compte Direction directement — c'est ensuite au Fondateur de créer le compte Direction (et le reste du personnel) depuis Personnel, exactement comme décrit dans le flux validé : « Super Admin → crée l'établissement + le compte Fondateur → le Fondateur configure l'établissement et crée le personnel ».
- **Hiérarchie à sens unique, vérifiée par des tests dédiés** : le Fondateur hérite de tous les pouvoirs de la Direction (registre, notes, finances, personnel, rapports, audit — vérifié sur un échantillon représentatif, pas par duplication exhaustive de chaque test déjà existant). En sens inverse, la Direction ne peut ni créer un autre compte Direction, ni créer un Fondateur — seul le Fondateur peut créer un compte Direction. Le Fondateur lui-même n'est jamais créé via Personnel, uniquement à la création de l'établissement, pour qu'il n'y ait jamais d'ambiguïté sur qui est LE fondateur d'un établissement donné.
- **L'abonnement GESCOLA devient l'exclusivité du Fondateur dès qu'il existe** : la Direction y avait accès par défaut (établissement à un seul niveau) ; dès qu'un Fondateur est créé pour cet établissement, l'accès de la Direction à cette page est automatiquement retiré (`403`) — vérifié dynamiquement à chaque requête, pas figé au moment de la création du Fondateur.
- **Identité visuelle par rôle** (barre latérale) : chaque fonction a désormais sa propre couleur d'accent — vert pour la Direction/Fondateur, violet pour le Censeur, orange pour le Surveillant, cyan pour l'Enseignant, rose pour le Parent — fidèle à la maquette de référence fournie. Seule la barre latérale change ; le contenu (cartes, tableaux) garde la même mise en page neutre partout, cohérent avec ce que montre la maquette elle-même. Les rôles absents de la maquette (Comptable, Secrétariat, Super Admin, Promoteur de réseau) restent dans l'identité bleu marine par défaut plutôt que de se voir attribuer une couleur inventée sans base dans ce qui a été demandé.

**Livraison 9 — Cahier de texte et devoirs**
- **Cahier de texte** : ce qui a été fait en classe, séance par séance — distinct de l'emploi du temps (qui dit *quand* un cours a lieu) et des notes (qui évaluent l'élève) : répond à « qu'est-ce qui a été enseigné ? », un document souvent contrôlé par l'inspection pédagogique en Afrique francophone. Écriture par l'enseignant (avec la même restriction par affectation que les notes — un enseignant configuré ne peut renseigner que ses classes/matières assignées), lecture élargie à la Direction/Fondateur/Censeur/secrétariat.
- **Devoirs** : titre, description, échéance, rattachés à une classe et une matière — visibles par les parents des élèves de la classe concernée (affichés directement dans « Mes enfants », triés par échéance). Pas de remise en ligne : GESCOLA n'a pas de compte élève (décision assumée en Livraison 6), ce module sert à informer, pas à collecter des rendus.
- **Un seul point d'entrée pour l'enseignant** (page « Mes classes », onglets Notes / Cahier de texte / Devoirs) plutôt que des écrans séparés à naviguer un par un — la Direction, le Fondateur, le Censeur et le secrétariat disposent d'un écran dédié (« Cahier de texte ») pour consulter n'importe quelle classe, avec un sélecteur, pas seulement les leurs.

**Livraison 10 — Discipline / Incidents**
- **Journal d'incidents** en texte libre (comportement, violence, dégradation de matériel, triche, retards répétés, autre), avec gravité (mineur / modéré / grave) et cycle de traitement **Signalé → En cours de traitement → Clos**. Distinct du simple statut de présence (absent / retard) déjà existant : un incident est un fait disciplinaire décrit, horodaté, attribué à un élève et à celui qui l'a signalé.
- **Séparation stricte signaler / sanctionner**, conforme aux fonctions réelles : enseignant et surveillant *signalent* ; seuls le Censeur, la Direction et le Fondateur *prennent en charge, clôturent et posent les sanctions* (avertissement, retenue, travail supplémentaire, convocation des parents, exclusion temporaire). Celui qui signale ne sanctionne jamais lui-même.
- **Confidentialité** : un enseignant ne voit que les incidents qu'il a lui-même signalés (pas le dossier disciplinaire complet d'un élève) ; comptable, secrétariat et parents n'y ont aucun accès.
- **Traçabilité** : signalement, changement de statut et sanction sont inscrits au journal d'audit. Historique disciplinaire consultable par élève (fiche élève) et compteur « incidents à traiter » sur les tableaux de bord Censeur et Surveillant.

**Livraison 11 — Bulletins de notes (PDF)**
- **Bulletin A4 imprimable**, calqué sur la maquette de référence : en-tête (logo, nom, devise, autorité de tutelle), cadre d'identité (matricule, sexe, date de naissance, redoublement), tableau *Résultats scolaires* (coefficient, note, moyenne de classe, rang, appréciation), *Synthèse générale* (moyenne, rang, moyenne de classe, notes extrêmes), *Vie scolaire*, appréciation générale, décision du conseil de classe, signatures et cachets. Une page ; filigrane « BROUILLON » tant que le bulletin n'est pas publié.
- **Configurable par établissement** (Paramètres → Bulletin de notes) : afficher ou non les **appréciations**, la **vie scolaire**, la **signature du professeur principal** (facultative) ; devise, en-tête officiel, lieu, année scolaire, dates des trimestres. **Signature et cachet du Directeur *et* du Censeur** : chacun est posé avec son propre cachet ; un espace vierge est laissé si l'image n'est pas enregistrée (signature manuscrite possible).
- **Une seule définition de la moyenne, dans toute l'application** : moyenne de matière = Σ(note × coef. évaluation)/Σ coef. ; **moyenne générale = Σ(moyenne × coefficient de la matière)/Σ coefficients** ; rangs avec ex æquo (1, 2, 2, 4). ⚠️ Changement de comportement assumé : l'ancienne règle pondérait chaque matière par la *somme des coefficients de ses évaluations* ; la fiche élève, le portail parent et les rapports appliquent désormais la règle du bulletin, pour qu'un même élève n'ait jamais deux moyennes différentes.
- **Cycle de vie et garde-fous** : génération par classe/période → brouillon → **publication, refusée tant que toutes les notes de l'élève ne sont pas verrouillées** (le verrouillage = validation des bulletins) et qui **recalcule** avant de figer (jamais de chiffres périmés) ; un bulletin publié n'est jamais écrasé par une régénération ; dépublier pour corriger ; tout est journalisé.
- **Qui voit quoi** : Direction/Censeur/Fondateur génèrent, publient et saisissent la décision du conseil ; le **professeur principal** (désigné par classe) rédige l'appréciation générale de SA classe ; le secrétariat imprime les bulletins publiés ; les **parents** téléchargent les bulletins publiés de leurs enfants ; les enseignants saisissent l'appréciation de leur matière (restreinte à leurs affectations).
- **Compléments nécessaires découverts en construisant** : matricule/sexe/redoublement de l'élève ; **modification du coefficient d'une matière** (`PATCH /subjects/{id}` — il n'existait aucun moyen de le corriger) ; **le Censeur ne pouvait pas choisir un enseignant** dans Affectations/Emploi du temps (l'écran appelait `/users`, réservé à la Direction : listes vides) → nouveau `GET /teachers`.
- Polices DejaVu embarquées : les noms d'Afrique de l'Ouest (ɖ, ɛ, ɔ…) s'impriment correctement.

**Livraison 12 — Bulletins : durcissement (ROADMAP BU-01, BU-02, BU-03)**
- **Un bulletin publié se réimprime toujours à l'identique.** À la publication on fige non seulement les chiffres mais aussi l'identité de l'établissement (nom, devise, lieu, en-tête officiel…), les réglages d'affichage et **les images** (logo, signature et cachet de chaque signataire, rangés par empreinte SHA-256 : une seule copie par image et par établissement). Renommer l'école, changer une signature ou masquer une section n'altère plus un bulletin publié ; un brouillon reflète l'état courant ; dépublier puis republier fige le nouvel état. *Vérifié par un test de mutation : les tests échouent si le gel est désactivé.*
- **Signataires désignés explicitement** (Paramètres → Bulletin de notes) : Directeur (Direction ou Fondateur) et Censeur, avec repli automatique sur le plus ancien compte actif du rôle si aucun n'est désigné ou si le désigné est désactivé. Un compte d'un autre établissement, d'un mauvais rôle ou désactivé est refusé.
- **Images refusées dès l'envoi si elles ne sont pas imprimables** : seuls PNG, JPEG, WebP et GIF sont acceptés ; le fichier est réellement décodé (SVG, base64 corrompu ou faux fichier image rejetés) et ses dimensions plafonnées (16 millions de pixels, contre les « bombes de décompression »). Auparavant, un SVG était accepté puis disparaissait silencieusement du bulletin.
- **Registre de suivi unique** : [`ROADMAP.md`](./ROADMAP.md) recense *tout* ce qui reste (limites, écarts avec la maquette, manques découverts à l'audit du code, production), avec statut et priorité. Il est mis à jour à chaque livraison. Les mentions périmées de ce README (numérotation, « bulletins non implémentés », « 8 rôles »…) ont été corrigées.

**Transverse**
- **168 tests automatisés, 96 % de couverture**, exécutés contre une vraie base PostgreSQL (RLS forcée sur chaque table sensible).
- **Frontend React + Vite + Tailwind** couvrant : connexion (avec étape MFA), tableau de bord par rôle, fiche élève (notes/présences/finances), personnel, portail parent, rapports, sécurité, notifications, audit, cantine, bibliothèque — connecté au vrai backend, testé de bout en bout avec un navigateur automatisé (captures ci-dessous). **Design aligné sur la maquette de référence fournie** (`gescola-maquette.html`) : palette navy/cream/sky/emerald/coral, typographie Lora + Inter, sidebar à icônes, pastilles de statut à point coloré, avatars à initiales.
- Migrations Alembic, Dockerfile, docker-compose, configuration par variables d'environnement (aucun secret en dur).



## Mettre à jour un déploiement déjà en ligne (Railway/Vercel)

Si vous avez déjà déployé une version antérieure : poussez simplement ce code sur votre dépôt GitHub (`git add . && git commit && git push`). Railway redéploie automatiquement et exécute `alembic upgrade head` au démarrage (déjà intégré au `Dockerfile`) — la nouvelle migration de facturation plateforme s'applique donc sans action manuelle. Aucune nouvelle variable d'environnement n'est requise. Côté Vercel, rien à faire si vous n'avez pas modifié le frontend en parallèle.

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
| Restriction enseignant par classe assignée | **Implémentée pour la saisie des notes** (voir Livraison 5) : un enseignant avec au moins une affectation ne peut noter que ses classes/matières assignées. Le nouvel écran « Mes classes » (Livraison 6) oriente naturellement l'enseignant vers ses seules classes en pratique, mais **la restriction technique ne s'étend pas à la lecture** : via `/eleves`, un enseignant voit toujours tous les élèves de l'établissement, pas seulement les siens. |
| **Conflits de salle sur l'emploi du temps** | **Non vérifiés.** La détection de conflit couvre la classe et l'enseignant (pas deux cours en même temps pour l'un ou l'autre), mais pas la salle — deux cours peuvent actuellement être planifiés dans la même salle au même moment sans avertissement. |
| Rôles configurables par établissement | **Non implémenté.** Les 10 rôles sont fixes (enum), pas un système de permissions composables où chaque établissement définirait ses propres intitulés/droits. |
| Auto-inscription parent | **Volontairement absente.** Un parent ne peut jamais se rattacher lui-même à un élève — c'est toujours un acte administratif (direction/secrétariat). C'est un choix de sécurité, pas un oubli. |
| Mobile money (MoMo, Moov, Wave) | **Non intégré.** Le champ `method` du paiement accepte `mobile_money` mais aucun appel à une passerelle réelle n'est fait — c'est un enregistrement manuel. Une vraie intégration nécessite un partenariat et des identifiants API réels. |
| **SMS / e-mail réels** | **Non implémenté.** Les « relances de factures » (Livraison 2) sont des notifications **internes à l'application** (consultables dans le portail parent), pas des SMS ni des e-mails envoyés hors de GESCOLA — cela nécessiterait un partenariat avec un opérateur télécom ou un service d'e-mailing transactionnel, avec des identifiants réels que je ne peux pas fabriquer. |
| Synchronisation offline Electron | **Non implémentée.** L'architecture (PostgreSQL + API stateless) le permet, mais c'est un chantier à part entière. |
| Bulletins | **Livrés** (Livraison 11-12) : PDF configurable (en-tête officiel, devise, signatures/cachets Directeur et Censeur). Restent : coefficients par classe, semestres, bulletin annuel, formats primaire/maternelle — voir ROADMAP BU-04 à BU-08. |
| Vie scolaire / discipline | **Livrée** (Livraison 10) : incidents, sanctions, historique par élève. Reste : prévenir les parents (dépend de la messagerie et des SMS/e-mails) — ROADMAP AU-18. |
| **Application mobile native** | **Non livrée.** Prévue en Phase 3 du cahier des charges initial (voir ROADMAP CC-01) ; nécessite un projet séparé (React Native ou équivalent, publication App Store/Play Store) — hors de portée d'un livrable produit dans cet environnement. L'API REST existante pourrait servir de base à une telle application sans modification. |
| **Paiement par carte bancaire / mobile money réel pour l'inscription** | **Non livré.** L'inscription en libre-service ne demande aucune carte (« sans carte bancaire » assumé comme argument commercial), et les paiements de factures plateforme sont enregistrés manuellement par le Super Admin — aucune passerelle de paiement réelle (Stripe, CinetPay, etc.) n'est intégrée. |
| **CAPTCHA / protection anti-bot sur l'inscription** | **Non implémenté.** `POST /auth/signup` est protégé uniquement par un rate limit (3/heure/IP) — un vrai CAPTCHA (hCaptcha, Turnstile) nécessite des clés de service réelles. |
| **Facturation plateforme automatique (tâche planifiée)** | **Semi-manuelle.** La génération de facture et le passage en retard/suspension sont déclenchés par le Super Admin depuis la console, pas par une tâche planifiée (cron) qui le ferait automatiquement chaque mois. Le calcul du statut d'un essai expiré, lui, est bien automatique (recalculé à la lecture, sans tâche planifiée nécessaire). |
| **Documents officiels** | Bulletin **livré**. Attestations/certificats de scolarité et reçus de paiement : **non livrés** — ROADMAP AU-10. |
| **Stockage des images (logo, signature, tampon)** | Encodées en base64 dans PostgreSQL (≈ 1 Mo max, formats PNG/JPEG/WebP/GIF) plutôt que sur un stockage de fichiers dédié : suffisant à ce volume, à revoir à l'échelle — ROADMAP PR-08. |
| **Discipline : pas de notification aux parents** | Aucun parent n'est prévenu automatiquement d'un incident ou d'une sanction, et les parents n'ont pas de vue sur le dossier disciplinaire de leur enfant : c'est volontairement laissé à la future messagerie (Communication), pour ne pas exposer des informations sensibles sans canal de communication encadré. |
| **Coefficients par classe/série** | Le coefficient est propre à la matière, pour tout l'établissement. En pratique il varie parfois selon la classe ou la série (lycée) : un coefficient par classe n'est pas pris en charge. |
| **Bulletins publiés avant la Livraison 12** | Ils n'ont pas de données figées : ils se réimpriment avec l'état courant. Les dépublier puis les republier les fige (ROADMAP BU-11). |
| **Bulletin : périodes et formats** | Trimestres T1/T2/T3 uniquement (pas de semestres) ; sans dates de trimestre configurées, la vie scolaire est comptée depuis le 1er septembre. Le rang est calculé parmi les élèves actifs de la classe ayant une moyenne. Les images SVG ne sont pas imprimées (PNG/JPEG/WebP/GIF). Pas de bulletin de fin d'année (moyenne annuelle). |
| **Manques découverts à l'audit du code** | Changement/réinitialisation de mot de passe, modification et désactivation de compte, appel de classe en une fois, import en masse d'élèves, passage d'année, pagination, vue financière globale, reçus, exports, modification d'un créneau d'emploi du temps… **Tous inscrits, priorisés et suivis dans ROADMAP section 5 (AU-01 à AU-18).** |
| **Tests automatisés frontend** | **Absents.** Les 168 tests automatisés couvrent exclusivement le backend (API + base de données). Chaque vérification frontend dans ce livrable (garde d'accès par rôle, formulaires, tableaux de bord) a été faite manuellement avec un navigateur automatisé au moment de la construction, pas intégrée dans une suite rejouable en continu (Vitest, Playwright Test) qui détecterait automatiquement une régression future. |
| **Vue « groupe » multi-établissements** | **Implémentée.** Nouveau rôle `network_admin` (promoteur), modèle `SchoolNetwork`, tableau de bord consolidé (`GET /network/overview`) agrégeant effectifs, encaissé/dû et taux de recouvrement par établissement — provisionné exclusivement par le Super Admin (`POST /networks`, `/networks/{id}/tenants/{tenant_id}`, `/networks/{id}/admins`). Lecture établissement par établissement en basculant le contexte RLS, jamais de requête cross-tenant : aucune policy RLS existante n'a été affaiblie pour livrer cette fonctionnalité. |
| **Cycles scolaires** (maternelle/primaire/secondaire) | **Implémenté.** Champ `cycle` sur les classes (`POST /classes`), utilisé pour segmenter les effectifs — pas encore affiché en agrégat par cycle dans la vue groupe (seulement par établissement pour l'instant). |
| **Écarts avec la maquette de référence** | Emploi du temps, discipline, bulletins, cahier de texte et tableaux de bord par rôle sont livrés. Restent la messagerie et plusieurs écrans par rôle — liste complète et priorisée : ROADMAP section 4 (MQ-01 à MQ-08). |
| **Conformité réglementaire multi-pays** | **Non livrée.** Le champ pays/devise n'existe pas encore sur `Tenant` ; une expansion réelle vers d'autres pays nécessite un conseil juridique local par pays, pas seulement du code. |
| Frontend | Couvre l'essentiel du flux quotidien de chaque rôle : connexion (avec étape MFA), tableau de bord, fiche élève (notes/présences/finances), personnel, portail parent, **rapports avec graphiques, sécurité (MFA), notifications, journal d'audit, cantine, bibliothèque**. |
| Stockage du token côté frontend | `localStorage`, par simplicité de ce MVP. Un cookie `httpOnly` + `Secure` serait préférable en production pour réduire l'exposition en cas de XSS — voir `SECURITY.md`. |
| Déploiement production | Aucun hébergement réel n'a été mis en place (ceci reste un environnement de développement/démonstration). |

Le détail des mesures de sécurité effectivement en place, et leurs limites, est dans [`SECURITY.md`](./SECURITY.md).
