# Données du sous-projet

- `drill_observations.json` sera le journal canonique append-only des séances
  importées, distinct de toute observation QCM.
- `manual_review_rules.json` conserve les règles demandées volontairement par
  l’utilisateur. Elles deviennent éligibles sans être enregistrées comme de
  fausses erreurs ; `ou_ou` y est actuellement inscrit.
- Les plans, rapports de lint, rapports des correcteurs et paquets de revue sont
  des artefacts générés, pas des sources.
- `pilot_candidates.json` contient les 42 exercices de la banque initiale ;
  `pilot_readable.md` conserve la fiche lisible du pilote initial de 20 exercices
  revu indépendamment. Ils restent les artefacts de calibration et d’audit de la
  banque autonome générée dans `../bank.js`.
- `pilot_choice_options.json` contient les deux à quatre formes proposées pour
  chaque exercice ; la bonne réponse reste celle du pilote validé.
- `pilot_lint_report.json` et `pilot_checker_report.json` conservent les contrôles
  automatiques du pilote.
- `pilot_review_input.json` est le paquet de revue aveugle, sans solution;
  `pilot_review_independent.json` consigne la relecture indépendante exhaustive
  et sa contre-vérification ciblée. `pilot_review.json` conserve la seconde passe
  réalisée dans le contexte de production.
- `production_request.json` est la demande source validée pour les 106 prochains
  exercices. `drill_plan.json` et `prompt_context.json` sont ses artefacts
  reproductibles et restent ignorés par Git.
- `production_candidates.json`, `production_choice_options.json` et
  `production_choice_corrections.json` contiennent les 106 exercices produits,
  leurs 412 choix et leurs 306 diagnostics.
- `production_review.json` est la revue exhaustive des onze lots.
  `production_checker_review.json` classe les deux alertes des 100 exercices
  initiaux ; `ou_ou_checker_review.json` classe les deux alertes de style du
  supplément `ou/où`.
  `production_bank_test.js` est la banque JavaScript de démonstration, distincte
  de la banque publique `../bank.js`.
- `bank_manifest.json` déclare les deux lots validés assemblés dans la banque
  publique de 148 exercices. Il empêche une régénération accidentelle limitée au
  seul pilote de 42 exercices.
