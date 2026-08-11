# Qualité et tests

## Tests Python

### Contrats

- schémas JSON valides ;
- propriétés supplémentaires rejetées ;
- un seul blanc ;
- réponses admises non vides et uniques après normalisation ;
- chemin canonique existant ;
- fiche pédagogique résolue ;
- identifiants et releases valides.
- deux à quatre choix courts par exercice ;
- une seule réponse correcte parmi les choix ;
- aucun champ de saisie dans l’application publiée.

### Bridge

Tester au minimum :

1. aucune donnée ;
2. priorité QCM seule ;
3. échecs drills seuls ;
4. deux signaux concordants sans double comptage ;
5. réussite insuffisante pour réduire le QCM ;
6. récupération fiable ;
7. stock déjà suffisant ;
8. stock vide ;
9. espacement récent ;
10. import répété de la même séance ;
11. question en revue/supprimée côté QCM ;
12. chemin inconnu ou fiche pédagogique absente.

### Production

- écriture atomique ;
- correction ciblée sans régénération globale ;
- aucun candidat publié après statut partiel/indéterminé ;
- comparaison avec signatures drills et QCM ;
- `questions.js` inchangé après publication de drills.

Sous Windows, exécuter Pytest avec un `--basetemp` placé dans le projet si le
temporaire utilisateur privé est inaccessible. Une permission du dossier temporaire
ne doit pas être présentée comme un échec fonctionnel du code.

## Tests JavaScript

- normalisation des apostrophes et espaces ;
- conservation des accents ;
- politique de casse ;
- validation correcte/incorrecte ;
- absence de règle avant réponse ;
- affichage de la règle, méthode et application après réponse ;
- progression et série correcte ;
- sélection pondérée des mécanismes ;
- priorité aux exercices non vus ;
- stockage versionné ;
- export de séance ;
- aucune mutation des clés QCM existantes ;
- navigation mobile et clavier Entrée.

## Contrôle linguistique

Pour chaque réponse admise :

1. recomposer la phrase complète ;
2. vérifier que la chaîne est naturelle ;
3. conserver les alertes de chaque moteur ;
4. distinguer erreur, alerte acceptable, indisponibilité et indétermination.

## Banque de 40 exercices

Le pilote initial et son extension alimentent la banque autonome `bank.js`,
générée après validation des choix orthographiques.

Critères individuels :

- règle officielle ;
- mécanisme exact ;
- phrase naturelle et utile ;
- une seule réponse défendable ;
- niveau bac ;
- aucune indication prématurée ;
- application pédagogique courte et exacte ;
- aucune proximité excessive avec la banque QCM.

Critères de calibration :

- 20/20 revus indépendamment ;
- faux négatifs du lint identifiés ;
- faux positifs des moteurs identifiés ;
- comparaison entre revue exhaustive et future revue ciblée ;
- aucune publication automatique.

## Régression du projet principal

Avant livraison locale :

- tests Python HEP complets ;
- `quiz-app/test_pedagogy.js` ;
- `quiz-app/test_error_profile.js` ;
- syntaxe de `quiz-app/app.js`, `config.js` et `sw.js` ;
- empreinte de `quiz-app/questions.js` inchangée ;
- `git diff --check` limité aux fichiers concernés si les anciens benchmarks sont
  inaccessibles.
