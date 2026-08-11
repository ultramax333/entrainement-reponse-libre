# Entraînement d’orthographe à choix

Sous-projet du système HEP consacré à des exercices courts ciblés sur les règles
où l’utilisateur rencontre des difficultés.

## État

Le pipeline local et l’application autonome sont implémentés :

- contrats fermés et normalisation des réponses ;
- mémoire drill séparée, import idempotent, agrégation et bridge de priorités ;
- page autonome dans ce dossier, avec banque de 40 exercices contrôlés ;
- export manuel et file locale de synchronisation ;
- planification, projection canonique, lint, correcteurs locaux et publication
  atomique sur copie de test;
- pilote initial de 20 exercices revu indépendamment, puis extension de 20
  exercices contrôlée localement ;
- deux à quatre formes courtes par exercice, contrôlées avant la génération de
  `bank.js`.

L’application ne dépend pas du site QCM dans le navigateur. Le projet original
reste hors du périmètre de publication.

## Commandes locales

Depuis ce dossier :

```powershell
python pipeline_drills.py bridge data/bridge_audit.json
python pipeline_drills.py plan data/bridge_audit.json data/drill_plan.json --limit 20
python pipeline_drills.py project-context data/drill_plan.json data/prompt_context.json
python pipeline_drills.py lint candidats.json data/lint_report.json
python pipeline_drills.py check-local candidats.json data/checker_report.json
python choice_bank.py
python -m pytest
```

La page locale se lance depuis ce dossier avec un serveur statique, puis s’ouvre
sur sa racine. `index.html`, `app.js`, `choice-engine.js`, `style.css` et
`bank.js` forment le site autonome publiable sur GitHub Pages.

Chaque question possède un champ de feedback facultatif. Les commentaires sont
conservés dans le navigateur, téléchargeables en JSON et sauvegardables ou
restaurables depuis Google Drive. Le site demande un identifiant client OAuth Web
public lors de la première configuration ; aucun jeton Google n’est enregistré
par l’application.

## Démarrage d’un nouveau fil

Ouvrir une nouvelle conversation Codex sur le projet
`C:\Users\maxim\Desktop\examen français`, choisir **Sol High**, puis envoyer :

> Lis entièrement `entrainement_reponse_libre/README.md` et tous les documents
> qu’il impose. Prends ensuite en charge ce sous-projet en suivant
> `IMPLEMENTATION_PLAN.md`. Travaille localement jusqu’au pilote, sans commit,
> push ni déploiement.

Le fil doit lire, dans cet ordre :

1. ce fichier ;
2. `AGENTS.md` ;
3. `ARCHITECTURE.md` ;
4. `DATA_AND_WEIGHTING.md` ;
5. `PIPELINE.md` ;
6. `TESTING.md` ;
7. `IMPLEMENTATION_PLAN.md` ;
8. les sources canoniques du projet principal indiquées ci-dessous.

## Expérience utilisateur visée

La page affiche un exercice à la fois :

- une phrase courte servant de contexte ;
- deux à quatre boutons contenant uniquement les formes proposées ;
- aucune saisie au clavier ;
- aucune indication de la règle avant validation ;
- après validation : la bonne réponse et une explication appliquée à la phrase.

La difficulté est celle d’un utilisateur de niveau bac qui connaît notamment COD
et COI, mais a besoin d’explications grammaticales accessibles et méthodiques.

## Frontières du sous-projet

Le sous-projet possède sa documentation, son bridge statistique, son mini-pipeline,
ses schémas, ses tests et sa banque de drills. Il réutilise les sources officielles
du projet principal au lieu de les recopier.

Le site et son pipeline vivent dans un seul sous-projet :

```text
entrainement_reponse_libre/
  site autonome, banque générée, pipeline, données de travail et tests
```

La publication GitHub de ce dossier reste indépendante du dépôt `quiz-app`.

## Sources canoniques du projet principal

Lire intégralement avant toute modification :

- `../HUB.md` et `../CLAUDE.md` ;
- `../quiz-app/README.md` ;
- `../quiz-app/app.js`, `error-profile.js`, `pedagogy.js`, `config.js`,
  `index.html`, `style.css`, `sw.js` et leurs tests ;
- `../analyse_gpt/README.md` et `erreurs_HEP.md` ;
- `../analyse_gpt/rules_HEP.yaml` ;
- `../analyse_gpt/pedagogy_HEP.json` et `pedagogy_HEP.py` ;
- `../analyse_gpt/error_priorities_HEP.txt` ;
- `../analyse_gpt/error_weighting_HEP.yaml` ;
- `../analyse_gpt/exam_rule_evidence_HEP.json` ;
- `../analyse_gpt/signatures_banque.json` ;
- `../analyse_gpt/aggregate_errors_HEP.py` et `import_feedback_HEP.py` ;
- `../analyse_gpt/pipeline_HEP.py`, `production_loop_HEP.py` et
  `orchestrator_HEP.py` ;
- `../analyse_gpt/correcteurs_HEP.py` ;
- les prompts et tests directement requis par l’étape en cours.

Éviter les anciens benchmarks et rapports historiques sauf besoin démontré.

## État de référence à vérifier

Instantané local relevé le 09.08.2026, à contrôler directement dans les fichiers
et Git à chaque reprise :

- application QCM `1.24` ;
- cache `qcm-op001-v124` ;
- release locale `questions-20260805-d7aeab34` ;
- 1 747 questions QCM uniques ;
- SHA-256 Windows de `questions.js` :
  `D7AEAB344FED1DAFB9F387A1F743822FD63BF5E236CEC87952E278DFE69FBAAD` ;
- mémoire : 10 séances, 200 tentatives, 63 erreurs, 57 erreurs actives et
  4 priorités ;
- commit parent connu `534db82` ;
- commit `quiz-app` connu `f415428`.

Le `HUB.md` peut encore distinguer un état public plus ancien et cet état local
non publié. Le sous-projet doit préserver cette distinction et ne jamais annoncer
qu’une release est en ligne sans contrôler les fichiers réellement servis.

Ces nombres ne sont pas des constantes du sous-projet. Toujours les relire.

## Décisions déjà prises

- Une seule banque QCM : `quiz-app/questions.js`, qui ne sera pas modifiée par ce
  sous-projet.
- Une seule banque publiée pour ce site autonome : `bank.js`, générée depuis le
  pilote contrôlé et `data/pilot_choice_options.json`.
- Taxonomie et pédagogie communes au QCM et aux drills.
- Statistiques QCM et drills séparées ; seul le bridge combine leurs signaux.
- Pas de génération par API dans le navigateur.
- Pas de saisie libre : la réponse est choisie parmi deux à quatre formes.
- Pas de nouveauté grammaticale forcée : phrases neuves, mécanismes éprouvés et
  espacement.
- Contrôles locaux sur tous les drills ; revue IA groupée et ciblée après le pilote.
- Aucun commit, push ou déploiement avant validation du pilote.
