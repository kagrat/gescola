# GESCOLA — Registre de suivi (source unique du reste à faire)

> **Règle d'or : rien ne disparaît de ce fichier.** Un point terminé est *coché* (✅) avec la version qui l'a livré ;
> un point écarté est marqué ❌ avec sa raison. Ce fichier est relu et mis à jour à **chaque** livraison, avant de
> livrer. Les listes ne vivent plus dans des messages de conversation.
>
> Statuts : ✅ fait · 🔧 en cours · ⏳ planifié · ❓ décision du propriétaire requise · ❌ hors périmètre (raison donnée)
> Priorités : **P0** avant tout établissement réel · **P1** avant un lancement large · **P2** souhaitable
> Mention « *vérifié* » : l'absence a été constatée dans le code (liste des routes / recherche), pas supposée.

---

## 0. Trois numérotations existent — voici la correspondance

| Source | Numérotation | Signification |
|---|---|---|
| Cahier des charges initial | **Phases CC-1 à CC-3** | Socle · Extension · Expansion (mobile, mobile money, multi-pays) — section 3 |
| Plan convenu ensemble | **Étapes PL-1 à PL-5** | Fondateur+couleurs · Cahier de texte/devoirs · Discipline · Bulletins · Messagerie — section 1 |
| Journal du README | **Livraisons 1 à 11** | Chronologie de ce qui a été livré (l'ancien libellé « Phase N » du README était ambigu) |

---

## 1. Plan convenu (PL)

| ID | Étape | Statut | Livraison |
|---|---|---|---|
| PL-1 | Hiérarchie Fondateur/Direction + identité visuelle par rôle | ✅ | 8 |
| PL-2 | Cahier de texte + devoirs | ✅ | 9 |
| PL-3 | Discipline / incidents | ✅ | 10 |
| PL-4 | Bulletins PDF (base) | ✅ | 11 |
| PL-4b | Bulletins : durcissement (BU-01, BU-02, BU-03) | ✅ | 12 |
| PL-5 | Communication / messagerie | ✅ | 14 |

## 2. Bulletins — limites à traiter

| ID | Point | Prio | Statut |
|---|---|---|---|
| BU-01 | **Figer aussi identité, réglages d'affichage et images** (logo, signatures, cachets) à la publication, pour qu'un bulletin publié se réimprime à l'identique | P0 | ✅ v12 |
| BU-02 | **Désigner explicitement** le Directeur et le Censeur signataires (au lieu de « le plus ancien compte actif ») | P0 | ✅ v12 |
| BU-03 | **Refuser à l'envoi** les images non imprimables (SVG, base64 corrompu) au lieu de les ignorer en silence à l'impression | P0 | ✅ v12 |
| BU-04 | **Coefficients par classe / série** (Maths ≠ coefficient en série A et en série C) | P1 | ⏳ |
| BU-05 | **Semestres** (régime trimestres *ou* semestres, au choix de l'établissement) | P1 | ⏳ |
| BU-06 | **Bulletin annuel** : moyenne de l'année, décision de passage | P1 | ⏳ |
| BU-07 | **Bulletins primaire et maternelle** : le bulletin actuel est celui du secondaire. Le primaire (compositions, moyenne sur 10, rang) et la maternelle (évaluation par compétences, sans note) ont des formats différents | P1 | ⏳ |
| BU-08 | **Barème d'évaluation configurable** : les notes sont validées sur 20 uniquement (dictée sur 10, contrôle sur 40 impossibles) ; évaluation comme objet (date, barème, coefficient) plutôt qu'un simple libellé | P1 | ⏳ |
| BU-09 | Bulletin d'un seul élève à la demande (« Créer un bulletin » de la maquette) et pagination de la liste | P2 | ⏳ |
| BU-10 | Conseil de classe : procès-verbal, dates, mentions (tableau d'honneur…) automatiques selon la moyenne | P2 | ⏳ |
| BU-11 | Bulletins publiés *avant* la livraison 12 : ils n'ont pas de données figées (ils se réimpriment avec l'état courant). Les dépublier puis republier les fige | P2 | ⏳ (note d'exploitation) |
| BU-12 | Images figées orphelines : à la dépublication, les images restent en base (quelques centaines d'octets à quelques dizaines de Ko chacune). Prévoir un nettoyage périodique | P2 | ⏳ |

## 2 bis. Messagerie — limites du module

| ID | Point | Prio | Statut |
|---|---|---|---|
| MS-01 | Pas de pièces jointes (photo d'un carnet, certificat médical…) : texte seul | P2 | ⏳ |
| MS-02 | Pas de brouillon enregistré : un message non envoyé est perdu si la fenêtre se ferme | P2 | ⏳ |
| MS-03 | Pas de notification temps réel (WebSocket) : le compteur de non-lus se rafraîchit toutes les 45 s, pas instantanément | P2 | ⏳ |
| MS-04 | Un fil ne peut pas changer d'élève ni fusionner avec un autre une fois créé | P2 | ⏳ |
| MS-05 | Convocation : pas de rappel automatique la veille (dépend de CC-03, l'envoi réel de SMS/e-mails) | P2 | ⏳ |
| MS-06 | Pas de recherche dans l'historique des messages (par mot-clé, par élève) | P2 | ⏳ |
| MS-07 | Annonce : pas de champ « valable jusqu'au » (une annonce reste visible indéfiniment tant qu'elle n'est pas retirée à la main) | P2 | ⏳ |

## 3. Cahier des charges initial — ce qui n'est pas livré (CC)

| ID | Point | Prio | Statut |
|---|---|---|---|
| CC-01 | Application mobile native (projet séparé : React Native, App Store/Play Store). L'API REST peut la servir telle quelle | P1 | ❌ projet distinct |
| CC-02 | Paiement mobile money réel (MTN MoMo, Moov, Wave) : nécessite partenariat et clés API réelles | P0 pour la facturation réelle | ⏳ dépend du partenaire |
| CC-03 | SMS / e-mails réels (les relances sont des notifications *internes* uniquement) | P0 (prérequis de PR-02, AU-03) | ⏳ dépend du fournisseur |
| CC-04 | Conformité multi-pays : champ pays/devise sur l'établissement + avis juridique local par pays | P1 | ⏳ |
| CC-05 | Synchronisation hors-ligne (postes à connexion instable) | P2 | ❌ chantier à part |
| CC-06 | Rôles/permissions configurables par établissement (aujourd'hui : 10 rôles fixes) | P2 | ❓ voir DP-04 |

## 4. Écarts avec la maquette de référence (MQ)

| ID | Rôle | Manque | Prio | Statut |
|---|---|---|---|---|
| MQ-01 | Fondateur | Le tableau de bord « Fondé » de la maquette est centré vie scolaire ; notre Fondateur est le propriétaire (vue Direction). **À trancher** | P1 | ❓ DP-05 |
| MQ-02 | Direction | Graphique d'évolution des effectifs ; indicateurs clés (moyenne générale, taux de réussite, élèves en difficulté, paiements en attente) ; encart « À noter » (agenda des conseils de classe) | P1 | ⏳ |
| MQ-03 | Censeur | Écran « Statistiques » (répartition des résultats), « Enseignants » (liste en lecture), accès aux Rapports, « Dernières activités » | P1 | ⏳ |
| MQ-04 | Surveillant | « Surveillance quotidienne » (présences du jour par classe), pages Présences / Absences / Retards, Rapports | P1 | ⏳ |
| MQ-05 | Enseignant | « Cours & Supports » (dépôt de documents), « Évaluations », « Présences » (appel), « Aujourd'hui » (emploi du temps du jour sur l'accueil), « Dernières évaluations », Rapports | P1 | ⏳ |
| MQ-06 | Parent | Emploi du temps de l'enfant, pages détaillées Notes & moyennes / Absences / Paiements, prochaines échéances, annonces | P1 | ⏳ |
| MQ-07 | Tous | Recherche globale (barre du haut), cloche de notifications pour le personnel (aujourd'hui : parents uniquement), date du jour | P2 | ⏳ |
| MQ-08 | Messagerie | Communication parents ↔ personnel (« Communication », « Messages ») → **c'est PL-5** | P0 | ✅ v14 |

## 5. Manques découverts à l'audit du code (AU) — tous *vérifiés*

| ID | Manque | Prio | Statut |
|---|---|---|---|
| AU-01 | **Aucun changement de mot de passe** : un compte créé avec un « mot de passe provisoire » ne peut jamais le changer. Prévoir : changer son mot de passe, obligation de le changer à la première connexion, réinitialisation par la Direction | **P0** | ✅ v13 |
| AU-02 | **Aucune modification / désactivation / réactivation de compte** (seuls création et liste existent) ; un membre parti garde son accès | **P0** | ✅ v13 (modifier, désactiver, réactiver, réinitialiser mot de passe et 2FA ; voir aussi PR-06) |
| AU-03 | « Mot de passe oublié » en libre-service (nécessite CC-03, l'envoi d'e-mail) | P0 | ⏳ (la réinitialisation *par un administrateur* est livrée en v13 ; reste le libre-service, qui exige CC-03) |
| AU-04 | **Appel en masse** : la présence s'enregistre élève par élève ; pas d'écran « faire l'appel » d'une classe, pas de liste des présences par classe/jour | **P0** | ✅ v20 |
| AU-05 | Impossible de **modifier/justifier une présence** après coup (POST seul) | P0 | ✅ v20 |
| AU-06 | **Import en masse des élèves** (CSV/Excel) : inscrire 600 élèves un par un est irréaliste | **P0** | ✅ v21 (aperçu sans écriture, import tout-ou-rien, doublons, fichiers hostiles, verrou anti double clic, journal ; voir AU-26/AU-27 pour les limites) |
| AU-07 | **Passage d'année / réinscription** : clôture de l'année, promotion vers la classe supérieure, redoublement, sortie des terminales | **P0** | ✅ v22 : aperçu sans écriture puis exécution atomique et non rejouable (verrou d'établissement, 409 au 2ᵉ envoi), plan refusé si une classe active est oubliée, historique par élève (`student_enrollments`), notes rattachées à leur année (`grades.academic_year`, rattrapage de l'existant testé sous RLS), anciennes notes consultables et corrigeables par la Direction seule (journal `grade.override_closed_year`), année non modifiable à la main une fois des notes saisies. Voir AU-28 à AU-30 pour les limites |
| AU-23 | **(Entrée initiale inexacte, corrigée en v21 : `PATCH /students/{id}` acceptait déjà `status`, mais sans motif, sans journal, sans règle et sans écran.)** ~~Aucun moyen de changer le statut d'un élève~~ : **ce qui manquait réellement** — **Aucun moyen *contrôlé* de changer le statut d'un élève** (actif/transféré/diplômé/archivé) : `StudentStatus` existe et sert déjà à filtrer les élèves actifs (rapports, moyennes, registre de présence) mais ancienne formulation : « rien dans l'API ne permet jamais de le faire évoluer ». Trouvé en écrivant les tests de présence (AU-04) | **P0** | ✅ v21 : `POST /students/{id}/status` (motif obligatoire, journal `student.status_changed`, 409 si inchangé, classe conservée, réservé à la gestion du référentiel) ; `PATCH` refuse désormais `status` ; écran « Changer le statut » |
| AU-08 | **Pagination et recherche côté serveur** : toutes les listes (élèves, etc.) renvoient tout | P0 | 🔧 **élèves ✅ v21** (pages bornées à 500, tri stable, recherche multi-mots, filtres classe/statut, total en en-tête). **Restent non paginées** : journal d'audit, incidents, notifications, comptes du personnel, factures, bulletins, messages — à traiter liste par liste |
| AU-09 | **Vue financière globale** : aucune liste de factures/impayés à l'échelle de l'établissement (le comptable ne voit que fiche par fiche) ; pas d'échéancier ni de barème de frais par classe | **P0** | ⏳ |
| AU-10 | **Reçu de paiement** (PDF) ; attestation / certificat de scolarité (le README les annonçait) | P1 | ⏳ |
| AU-11 | Exports (Excel/PDF) : listes de classe, présences, finances | P1 | ⏳ |
| AU-12 | Emploi du temps : **modifier** un créneau (création/suppression seulement) ; conflits de salle ; impression | P1 | ⏳ |
| AU-13 | Photo de l'élève ; cartes scolaires | P2 | ⏳ |
| AU-14 | Règlement intérieur (stockage/consultation) ; rapports d'absentéisme (élèves fréquemment absents) | P2 | ⏳ |
| AU-15 | Restriction de **lecture** de l'enseignant à ses seules classes (l'écriture l'est déjà) | P1 | ⏳ |
| AU-16 | Bibliothèque : modifier/supprimer un ouvrage, liste des retards ; cantine : résilier un abonnement ; cahier de texte : suppression | P2 | ⏳ |
| AU-17 | Pas d'agenda/calendrier d'établissement (conseils de classe, réunions, vacances) | P2 | ⏳ |
| AU-19 | Voir et fermer ses sessions actives (appareils connectés) | P2 | ⏳ |
| AU-20 | Politique de mot de passe renforcée : expiration/historique, refus des mots de passe courants ou déjà compromis | P2 | ⏳ |
| AU-21 | Prévenir la personne par e-mail d'un changement ou d'une réinitialisation de son mot de passe (alerte de sécurité) | P1 | ⏳ (dépend de CC-03) |
| AU-22 | Import en masse des comptes du personnel (CSV) — même besoin que l'import d'élèves (AU-06) | P1 | ⏳ |
| AU-24 | **La limite d'élèves du plan d'abonnement (`max_students`) n'est appliquée nulle part** (vérifié : elle existe sur le plan, mais ni la création ni l'import d'élèves ne la contrôlent) — un établissement en essai gratuit (100 élèves) peut en inscrire sans limite | **P0** pour la facturation réelle | ⏳ |
| AU-25 | Recherche d'élèves sensible aux accents (« Aicha » ne trouve pas « Aïcha ») : nécessite l'extension PostgreSQL `unaccent` ou une colonne normalisée | P2 | ⏳ |
| AU-26 | Les écrans de sélection (cantine, bibliothèque, discipline, messages, mes classes, personnel) chargent *tous* les élèves par blocs de 500 : correct mais lourd au-delà de ~2 000 élèves. À remplacer par une recherche à la volée | P1 | ⏳ |
| AU-27 | Import : ne crée pas les classes manquantes (volontaire), ne crée pas les comptes parents à partir des colonnes tuteur, n'importe pas le personnel (voir AU-22), n'accepte que la 1ʳᵉ feuille d'un classeur Excel | P2 | ⏳ |
| AU-28 | **Années sur factures et assiduité** : les factures portent leur année (par défaut l'année en cours ; l'année suivante ou une année passée sont possibles, une année lointaine est refusée ; une facture de cantine prend l'année de son mois). Les Rapports et la vue réseau comptent le dû/encaissé de l'année en cours et affichent à part les **arriérés des années précédentes** ; le passage d'année prévient du montant qui deviendra arriéré. Le taux d'assiduité est borné à l'année scolaire (1ᵉʳ sept. → 31 août). L'historique d'un élève (fiche) garde toutes les années. **Choix assumé** : les incidents de discipline ne sont pas rattachés à une année (un incident non traité doit rester visible) ✅ v23 |
| AU-29 | **Le passage d'année n'est pas annulable.** Garde-fous : aperçu obligatoire, confirmation par saisie de la nouvelle année, historique par élève. Une erreur se corrige élève par élève (classe, statut). Un « annuler le dernier passage » n'a pas été construit : il serait risqué une fois de nouvelles notes saisies | P2 | ⏳ décision |
| AU-30 | Passage d'année : ne rouvre pas automatiquement les affectations enseignants/emploi du temps (conservés, à revérifier), ne recrée pas de classes (la Direction crée « 4ème A » avant), ne propose pas de décision automatique de redoublement (suggestion = moyenne annuelle < 10/20, modifiable) ; la suggestion de classe d'accueil connaît les niveaux CI→Tle, pas la maternelle | P2 | ⏳ |
| DM-01 | **Jeu de démonstration en ligne** : le script `backend/scripts/seed_demo.py` est prêt et testé (v21) mais **n'a pas été exécuté sur l'instance Railway** (action propriétaire : voir README). Tant qu'il ne l'est pas, l'instance en ligne n'a aucune école | P0 pour toute présentation | ⏳ action propriétaire |
| AU-18 | Discipline : prévenir les parents d'un incident/sanction (dépend de PL-5 et CC-03) | P1 | ✅ v14 : lien « Informer les parents » depuis un incident, qui ouvre la messagerie préremplie (élève, objet, parents destinataires) — un acte volontaire du personnel, jamais un envoi automatique |

## 6. Production et sécurité (PR)

| ID | Point | Prio | Statut |
|---|---|---|---|
| PR-01 | Déploiement réel : environnements staging/production, CI/CD, migrations contrôlées | P0 | ⏳ |
| PR-02 | Vérification d'e-mail à l'inscription + service d'e-mail transactionnel | P0 | ⏳ (avec CC-03) |
| PR-03 | Protection anti-robot (CAPTCHA) sur l'inscription | P1 | ⏳ (clés de service) |
| PR-04 | Jetons en cookie `httpOnly`+`Secure` au lieu de `localStorage` | P0 | ⏳ |
| PR-05 | Limitation de débit partagée (Redis) pour plusieurs instances | P1 | ⏳ |
| PR-06 | Codes de secours MFA (récupération de compte) | P1 | 🔧 partiel v13 : la Direction/Fondateur peut réinitialiser la 2FA d'un compte ; restent les codes de secours en libre-service |
| PR-07 | Facturation plateforme automatique (tâche planifiée) | P1 | ⏳ |
| PR-08 | Stockage des images/fichiers hors base (S3-compatible) ; supports de cours (MQ-05) en dépendent | P1 | ⏳ |
| PR-09 | Sauvegardes, restauration testée, supervision, journalisation centralisée, suivi d'erreurs | P0 | ⏳ |
| PR-10 | Protection des données personnelles : droits d'accès/suppression, durée de conservation, mentions légales, CGU, politique de confidentialité (loi locale applicable) | P0 | ⏳ |
| PR-11 | **Tests automatisés de l'interface** (parcours + accès par rôle) ; aujourd'hui vérifications manuelles seulement | P1 | ⏳ en continu |
| PR-12 | Test de charge et de performance (600+ élèves par établissement, pics de fin de trimestre) | P1 | ⏳ |
| PR-14 | Nettoyage périodique : jetons de rafraîchissement expirés/révoqués (la table grossit à chaque connexion) et images figées orphelines (BU-12) | P1 | ⏳ |
| PR-15 | Le contrôle du compte à chaque requête (activité, version de session) ajoute une lecture en base par requête : à mesurer avec PR-12 | P1 | ⏳ |
| PR-13 | Accessibilité (clavier, contrastes, lecteurs d'écran) et adaptation mobile de l'interface | P1 | ⏳ |

## 7. Décisions produit assumées (DP) — pas des oublis

| ID | Décision | Statut |
|---|---|---|
| DP-01 | Pas de compte élève (les parents relaient l'information). Extension possible si un client le demande | ✅ assumée |
| DP-02 | Pas d'auto-rattachement parent↔élève (acte administratif) | ✅ assumée |
| DP-03 | Moyenne générale = Σ(moyenne × coefficient de la matière) / Σ coefficients (règle unique dans toute l'application) | ✅ assumée |
| DP-04 | 10 rôles fixes, pas de permissions composables | ❓ à confirmer (CC-06) |
| DP-05 | Le Fondateur est le propriétaire au-dessus du Directeur ; la maquette lui prête un menu « vie scolaire » | ❓ à trancher (MQ-01) |
| DP-06 | Un fil de messagerie n'est visible que par ses participants explicites — la Direction ne voit pas automatiquement les fils d'un enseignant avec un parent, sauf si elle y est ajoutée. Décision cohérente avec le reste de l'application (un enseignant ne voit que ses propres signalements disciplinaires, Livraison 10) : la supervision par la Direction se fait par la confiance et, en cas de litige, par l'historique immuable des messages — pas par une lecture systématique. **À confirmer avec l'exploitant** : certains établissements voudront une supervision plus étroite (la Direction ajoutée d'office à tout fil impliquant tel rôle, par exemple) | ❓ à confirmer |

---

## 8. Ordre de traitement recommandé

1. ~~**PL-4b** (BU-01/02/03)~~ — ✅ livré (v12).
2. ~~**Comptes et accès** (AU-01, AU-02)~~ — ✅ livré (v13).
3. ~~**PL-5 Messagerie** (MQ-08, puis AU-18)~~ — ✅ livré (v14).
4. ~~**Appel en masse et correction après coup** (AU-04/05)~~ — ✅ livré (v20).
4 bis. ~~**Socle élèves** : statut (AU-23), pagination/recherche des élèves (AU-08, partiel), import (AU-06)~~ — ✅ livré (v21).
4 ter. ~~**Passage d'année** (AU-07)~~ — ✅ livré (v22) ; ~~années sur présences et factures (AU-28)~~ — ✅ livré (v23). Prochain : limite du plan (AU-24), vue financière (AU-09), reçus/attestations (AU-10).
5. **Compléter la maquette** (MQ-02 à MQ-07) ; reçus/attestations/exports (AU-10/11).
6. **Bulletins étendus** (BU-04 à BU-08).
7. **Production** (PR-*, CC-02/03/04) avant le premier établissement réel.

## 9. Journal des défauts corrigés (ce qui a été trouvé *en vérifiant*, pas signalé)

| ID | Défaut | Gravité | Corrigé |
|---|---|---|---|
| DEF-01 | **Deux établissements pouvaient créer le même e-mail ; la connexion plantait ensuite (erreur serveur) pour les deux comptes.** Vecteur de déni de service : la Direction d'une école pouvait bloquer un utilisateur d'une autre en créant un compte avec son adresse. Correction : e-mail unique dans toute la plateforme, insensible à la casse, garanti par un index en base | **Haute** | v13 |
| DEF-02 | Un jeton d'accès restait valable jusqu'à son expiration même après désactivation du compte, changement de mot de passe ou changement de rôle (la docstring affirmait le contraire). Correction : le compte est relu à chaque requête ; version de session ; rôle lu en base | **Haute** | v13 |
| DEF-03 | Le Censeur avait des listes d'enseignants vides dans Affectations et Emploi du temps (écran appelant une route réservée à la Direction) | Moyenne | v12 |
| DEF-04 | Aucun moyen de corriger le coefficient d'une matière | Moyenne | v12 |
| DEF-05 | README périmé : annonçait « bulletins/discipline non implémentés » et « 8 rôles » | Moyenne | v12 |
| DEF-06 | **Le frontend ne compilait plus du tout** : `App.tsx` importait et routait `AnnouncementsPage`, un fichier qui n'existait pas sur le disque — trouvé en tentant `npm run build`, pas signalé par avance | **Haute** | v14 |
| DEF-07 | `?nouveau=1&eleve=…&sujet=…` : la messagerie prévoyait déjà ce préremplissage pour « informer les parents » depuis un incident, mais rien dans Discipline n'y renvoyait — fonctionnalité à moitié câblée | Moyenne | v14 |
| DEF-08 | Fenêtre de composition d'un message : quand un élève n'a réellement aucun parent (actif) rattaché, le message « Chargement… » restait affiché indéfiniment au lieu de dire qu'il n'y a personne à qui écrire — l'état « chargement » et l'état « liste vide » n'étaient pas distingués | Basse | v14 |
| DEF-10 | **Hooks React appelés dans un ordre variable** : `RequireAuth` appelait `useLocation()` après un `return` anticipé (état « chargement ») — avertissement React à chaque chargement de page, risque de plantage. Trouvé en vérifiant la page Élèves dans un navigateur (v21), présent depuis longtemps | Moyenne | v21 |
| DEF-11 | L'en-tête de total de pagination (`X-Total-Count`) n'aurait **pas été lisible par le navigateur** (CORS sans `expose_headers`) : le serveur l'aurait envoyé pour rien et les pages affichées « 0 élève ». Trouvé avant la livraison grâce à un test dédié | Haute (évitée) | v21 |
| DEF-12 | **Année scolaire « flottante »** : un établissement qui n'avait jamais réglé son année voyait son année courante se déduire de la date du jour ; une fois les notes rattachées à une année, elle aurait basculé toute seule au 1ᵉʳ septembre et **fait disparaître les notes des écrans**. Repéré en concevant AU-07 ; évité en figeant l'année dès la 1ʳᵉ note et dans la migration | Haute (évitée) | v22 |
| DEF-09 | **Aucune contrainte n'empêchait deux enregistrements de présence pour le même élève le même jour** — deux appels distincts, ou un double clic, créaient des lignes contradictoires. Corrigé par une contrainte d'unicité en base (`uq_attendance_student_date`) et un upsert systématique | Moyenne | v20 |

## 10. Historique des livraisons

Voir le README (« Ce qui est inclus », Livraisons 1 à 11+) et `SECURITY.md`.

- **v23** : factures et assiduité rattachées à l'année (AU-28), arriérés séparés dans les Rapports et la vue réseau, avertissement au passage d'année ; 278 tests.
- **v22** : passage d'année scolaire (AU-07) : notes rattachées à leur année, clôture/promotion/redoublement/sortie, historique des parcours, 272 tests ; limites AU-28 à AU-30.
- **v21** : statut d'élève contrôlé (AU-23), pagination et recherche des élèves (AU-08 partiel), import CSV/Excel (AU-06), script de démonstration (DM-01), DEF-10, DEF-11. 257 tests.
