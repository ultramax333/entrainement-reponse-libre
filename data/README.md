# Données du sous-projet

- `drill_observations.json` sera le journal canonique append-only des séances
  importées, distinct de toute observation QCM.
- Les plans, rapports de lint, rapports des correcteurs et paquets de revue sont
  des artefacts générés, pas des sources.
- `pilot_candidates.json` et `pilot_readable.md` contiennent le pilote local de
  20 exercices produit et revu. Ils restent les artefacts de calibration et
  d’audit de la banque autonome générée dans `../bank.js`.
- `pilot_choice_options.json` contient les deux à quatre formes proposées pour
  chaque exercice ; la bonne réponse reste celle du pilote validé.
- `pilot_lint_report.json` et `pilot_checker_report.json` conservent les contrôles
  automatiques du pilote.
- `pilot_review_input.json` est le paquet de revue aveugle, sans solution;
  `pilot_review_independent.json` consigne la relecture indépendante exhaustive
  et sa contre-vérification ciblée. `pilot_review.json` conserve la seconde passe
  réalisée dans le contexte de production.
