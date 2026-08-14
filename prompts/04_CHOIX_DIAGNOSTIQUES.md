# Choix et diagnostics

Travaille uniquement sur les exercices dont la phrase, la réponse et
`application_note` ont déjà passé le lint déterministe.

Pour chaque exercice, produis exactement quatre formes courtes : la bonne forme
et trois distracteurs plausibles. Les distracteurs doivent être difficiles à
départager et représenter, autant que possible, trois raisonnements erronés
distincts. N’ajoute jamais une faute gratuite uniquement pour atteindre quatre
choix : signale plutôt l’exercice `REVISE`.

Pour chaque distracteur, fournis :

- un `mechanism_id` déjà présent dans `DIAGNOSTIC_CATALOG` ;
- un `reasoning_break` appliqué exactement à la forme et à la phrase ;
- aucune règle générale recopiée ;
- aucune affirmation certaine sur la pensée de l’utilisateur.

La différence entre deux distracteurs doit être linguistiquement utile. Les
accents, la casse, la catégorie grammaticale, l’accord, la contraction et la
segmentation peuvent être significatifs selon le chemin canonique.

Retourne seulement les documents JSON `hep-drill-choice-options/1.0` et
`hep-choice-corrections/2.0` demandés, sans commentaire.
