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
| PL-5 | Communication / messagerie | ⏳ | — |

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
| MQ-08 | Messagerie | Communication parents ↔ personnel (« Communication », « Messages ») → **c'est PL-5** | P0 | ⏳ |

## 5. Manques découverts à l'audit du code (AU) — tous *vérifiés*

| ID | Manque | Prio | Statut |
|---|---|---|---|
| AU-01 | **Aucun changement de mot de passe** : un compte créé avec un « mot de passe provisoire » ne peut jamais le changer. Prévoir : changer son mot de passe, obligation de le changer à la première connexion, réinitialisation par la Direction | **P0** | ⏳ recommandé juste après PL-4b |
| AU-02 | **Aucune modification / désactivation / réactivation de compte** (seuls création et liste existent) ; un membre parti garde son accès | **P0** | ⏳ recommandé juste après PL-4b |
| AU-03 | « Mot de passe oublié » en libre-service (nécessite CC-03, l'envoi d'e-mail) | P0 | ⏳ |
| AU-04 | **Appel en masse** : la présence s'enregistre élève par élève ; pas d'écran « faire l'appel » d'une classe, pas de liste des présences par classe/jour | **P0** | ⏳ |
| AU-05 | Impossible de **modifier/justifier une présence** après coup (POST seul) | P0 | ⏳ |
| AU-06 | **Import en masse des élèves** (CSV/Excel) : inscrire 600 élèves un par un est irréaliste | **P0** | ⏳ |
| AU-07 | **Passage d'année / réinscription** : clôture de l'année, promotion des élèves vers la classe supérieure, archivage. Aujourd'hui l'année n'est qu'un libellé | **P0** | ⏳ |
| AU-08 | **Pagination et recherche côté serveur** : toutes les listes (élèves, etc.) renvoient tout | P0 | ⏳ |
| AU-09 | **Vue financière globale** : aucune liste de factures/impayés à l'échelle de l'établissement (le comptable ne voit que fiche par fiche) ; pas d'échéancier ni de barème de frais par classe | **P0** | ⏳ |
| AU-10 | **Reçu de paiement** (PDF) ; attestation / certificat de scolarité (le README les annonçait) | P1 | ⏳ |
| AU-11 | Exports (Excel/PDF) : listes de classe, présences, finances | P1 | ⏳ |
| AU-12 | Emploi du temps : **modifier** un créneau (création/suppression seulement) ; conflits de salle ; impression | P1 | ⏳ |
| AU-13 | Photo de l'élève ; cartes scolaires | P2 | ⏳ |
| AU-14 | Règlement intérieur (stockage/consultation) ; rapports d'absentéisme (élèves fréquemment absents) | P2 | ⏳ |
| AU-15 | Restriction de **lecture** de l'enseignant à ses seules classes (l'écriture l'est déjà) | P1 | ⏳ |
| AU-16 | Bibliothèque : modifier/supprimer un ouvrage, liste des retards ; cantine : résilier un abonnement ; cahier de texte : suppression | P2 | ⏳ |
| AU-17 | Pas d'agenda/calendrier d'établissement (conseils de classe, réunions, vacances) | P2 | ⏳ |
| AU-18 | Discipline : prévenir les parents d'un incident/sanction (dépend de PL-5 et CC-03) | P1 | ⏳ |

## 6. Production et sécurité (PR)

| ID | Point | Prio | Statut |
|---|---|---|---|
| PR-01 | Déploiement réel : environnements staging/production, CI/CD, migrations contrôlées | P0 | ⏳ |
| PR-02 | Vérification d'e-mail à l'inscription + service d'e-mail transactionnel | P0 | ⏳ (avec CC-03) |
| PR-03 | Protection anti-robot (CAPTCHA) sur l'inscription | P1 | ⏳ (clés de service) |
| PR-04 | Jetons en cookie `httpOnly`+`Secure` au lieu de `localStorage` | P0 | ⏳ |
| PR-05 | Limitation de débit partagée (Redis) pour plusieurs instances | P1 | ⏳ |
| PR-06 | Codes de secours MFA (récupération de compte) | P1 | ⏳ |
| PR-07 | Facturation plateforme automatique (tâche planifiée) | P1 | ⏳ |
| PR-08 | Stockage des images/fichiers hors base (S3-compatible) ; supports de cours (MQ-05) en dépendent | P1 | ⏳ |
| PR-09 | Sauvegardes, restauration testée, supervision, journalisation centralisée, suivi d'erreurs | P0 | ⏳ |
| PR-10 | Protection des données personnelles : droits d'accès/suppression, durée de conservation, mentions légales, CGU, politique de confidentialité (loi locale applicable) | P0 | ⏳ |
| PR-11 | **Tests automatisés de l'interface** (parcours + accès par rôle) ; aujourd'hui vérifications manuelles seulement | P1 | ⏳ en continu |
| PR-12 | Test de charge et de performance (600+ élèves par établissement, pics de fin de trimestre) | P1 | ⏳ |
| PR-13 | Accessibilité (clavier, contrastes, lecteurs d'écran) et adaptation mobile de l'interface | P1 | ⏳ |

## 7. Décisions produit assumées (DP) — pas des oublis

| ID | Décision | Statut |
|---|---|---|
| DP-01 | Pas de compte élève (les parents relaient l'information). Extension possible si un client le demande | ✅ assumée |
| DP-02 | Pas d'auto-rattachement parent↔élève (acte administratif) | ✅ assumée |
| DP-03 | Moyenne générale = Σ(moyenne × coefficient de la matière) / Σ coefficients (règle unique dans toute l'application) | ✅ assumée |
| DP-04 | 10 rôles fixes, pas de permissions composables | ❓ à confirmer (CC-06) |
| DP-05 | Le Fondateur est le propriétaire au-dessus du Directeur ; la maquette lui prête un menu « vie scolaire » | ❓ à trancher (MQ-01) |

---

## 8. Ordre de traitement recommandé

1. ~~**PL-4b** (BU-01/02/03)~~ — ✅ livré (v12).
2. **Comptes et accès** (AU-01, AU-02) — un utilisateur réel ne peut pas aujourd'hui changer son mot de passe.
3. **PL-5 Messagerie** (MQ-08, puis AU-18).
4. **Exploitation quotidienne** : appel en masse (AU-04/05), pagination (AU-08), import d'élèves (AU-06), vue financière (AU-09), passage d'année (AU-07).
5. **Compléter la maquette** (MQ-02 à MQ-07) ; reçus/attestations/exports (AU-10/11).
6. **Bulletins étendus** (BU-04 à BU-08).
7. **Production** (PR-*, CC-02/03/04) avant le premier établissement réel.

## 9. Historique des livraisons

Voir le README (« Ce qui est inclus », Livraisons 1 à 11+) et `SECURITY.md`.
