# Plan d’implémentation

Le sous-projet doit avancer partie par partie. Chaque partie est testée avant la
suivante. Les parties 01 à 06 sont autorisées localement ; la partie 07 exige une
validation explicite de l’utilisateur.

## Partie 01 — Audit et contrats

Objectif : confirmer les briques réutilisables et figer les contrats sans toucher
à l’application publique.

Travail :

- lire les sources imposées ;
- vérifier l’état Git et les versions courantes ;
- confirmer les imports réellement réutilisables ;
- créer les schémas `hep-drill/1.0` et `hep-drill-feedback/1.0` ;
- créer les tests de schéma et de normalisation ;
- documenter toute divergence indispensable avec `DATA_AND_WEIGHTING.md`.

Acceptation : contrats fermés, chemins officiels vérifiés, tests verts, aucune
modification de `quiz-app`.

## Partie 02 — Bridge et maîtrise

Objectif : produire une priorité déterministe sans mélanger les historiques.

Travail :

- import append-only/idempotent des feedbacks drills ;
- agrégation par chemin canonique ;
- calcul du taux lissé et de la confiance ;
- lecture de `error_priorities_HEP.txt` ;
- calcul du facteur combiné, stock et espacement ;
- sortie compacte et audit machine ;
- tests de tous les scénarios de `TESTING.md`.

Acceptation : même entrée = même sortie, aucune mutation des observations QCM,
aucun double comptage.

## Partie 03 — Page locale minimale

Objectif : permettre une séance locale sans Drive ni publication.

Travail :

- créer `quiz-app/entrainement/` ;
- afficher un drill et valider la saisie ;
- masquer les catégories avant réponse ;
- réutiliser `pedagogy.js` après réponse ;
- enregistrer progression, erreurs, séries et exercices vus ;
- afficher les statistiques utiles ;
- fournir une petite banque de fixtures clairement non publiables ;
- ajouter les tests JS.

Acceptation : fonctionnement mobile/clavier, aucune régression de l’application
QCM, aucune modification de `questions.js`.

## Partie 04 — Synchronisation

Objectif : rendre les résultats utilisables par le bridge.

Travail :

- export compact `hep-drill-feedback/1.0` ;
- téléchargement manuel fonctionnel ;
- intégration Drive seulement si une couche partagée sûre est démontrée ;
- file de séances à synchroniser ;
- import idempotent côté pipeline.

Acceptation : deux imports du même fichier ne doublent rien ; réussites et erreurs
sont conservées ; aucune donnée drill dans les fichiers QCM.

## Partie 05 — Mini-pipeline

Objectif : générer, contrôler et préparer des drills sans pipeline QCM complet.

Travail :

- planification déterministe depuis le bridge ;
- projection compacte des règles et pédagogies nécessaires ;
- prompts minimaux ;
- génération groupée ;
- lint, recomposition et signatures ;
- correcteurs locaux ;
- revue IA et correction ciblée ;
- publication atomique sur une copie de test.

Acceptation : toutes les branches et pannes testées, aucune publication si un
contrôle est incomplet.

## Partie 06 — Pilote de 20 exercices

Objectif : mesurer la qualité réelle et calibrer la revue ciblée.

Travail :

- recalculer les priorités courantes ;
- produire 20 drills ;
- appliquer tous les contrôles ;
- effectuer une revue indépendante exhaustive ;
- classer PASS/REVISE/REJECT ;
- comparer revue exhaustive et revue ciblée simulée ;
- fournir le fichier lisible par l’utilisateur et l’audit machine.

Acceptation : aucune intégration publique ; rapport complet dans la conversation.

## Partie 07 — Intégration et publication

**Bloquée jusqu’à validation explicite de l’utilisateur.**

Après validation seulement :

- intégrer les drills approuvés dans l’unique `drills.js` ;
- ajouter le lien depuis l’accueil ;
- brancher la synchronisation définitive ;
- mettre à jour le cache et la version ;
- exécuter toutes les régressions ;
- mettre à jour `HUB.md`, `CLAUDE.md` et les README concernés ;
- créer des commits ciblés ;
- pousser/déployer uniquement sur demande explicite ;
- contrôler les fichiers réellement servis en ligne.

## Livrable final du fil responsable

Le fil rend dans la conversation :

- résumé de l’architecture livrée ;
- liste des fichiers ;
- formule réellement implémentée ;
- tests et résultats ;
- emplacement du pilote ;
- rendement et coût du pipeline ;
- décisions encore ouvertes ;
- confirmation que `questions.js` et le site public sont inchangés.
