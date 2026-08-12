# Génération des corrigés à choix courts

## Référence unique

Les corrigés de ce sous-projet reprennent le contrat du QCM HEP. La source
normative et opérationnelle est :

`../analyse_gpt/prompts_pipeline_HEP/05_CORRECTION_PEDAGOGIQUE.md`

Elle est complétée par :

- `../analyse_gpt/production_loop_HEP.py`, fonction
  `_assemble_feedback_explanation` ;
- `../analyse_gpt/pipeline_HEP.py`, fonction `static_lint_feedback` ;
- `../analyse_gpt/pedagogy_HEP.json`, qui fournit la règle et la méthode
  canoniques.

Le présent document ne recopie pas la règle QCM : il fixe uniquement son
adaptation au format de réponse courte.

## Différence de format

Le QCM possède les options fixes `1`, `2`, `3`, `4`, `A` et `T`. Un exercice de
ce site possède deux à quatre formes textuelles et une seule forme correcte.

| Élément | QCM HEP | Choix courts |
| --- | --- | --- |
| Correction générale | `explanation` | `explanation`, même structure |
| Justification par option | `why[1|2|3|4|A|T]` | `why[forme exacte]` |
| Réponse correcte | clé d’option | forme exacte parmi `choices` |
| Aucune / Toutes | analysées | absentes : ne pas les créer |

Les accents et la casse sont significatifs. `Suisse` et `suisse` sont donc deux
clés distinctes et deux formes distinctes.

## Contrat du corrigé

Chaque exercice publié doit recevoir un objet `correction` :

```json
{
  "explanation": "Règle : …\nMéthode : …\nDans cette phrase : …\nDonc : …",
  "why": {
    "forme correcte": "Justification précise de cette forme.",
    "forme fautive": "Erreur visible, règle utile et forme attendue."
  }
}
```

### `explanation`

La structure est identique au QCM, dans cet ordre obligatoire :

1. `Règle :` — issue de la fiche pédagogique canonique ;
2. `Méthode :` — étapes canoniques, numérotées ;
3. `Dans cette phrase :` — application aux mots précis de l’exercice ;
4. `Donc :` — lien explicite avec la forme correcte.

La règle et la méthode sont assemblées depuis `pedagogy_HEP.json`, comme dans le
QCM. L’application provient de la note de phrase déjà validée. Comme la réponse
est un seul mot, la conclusion est assemblée sous la forme « On écrit donc … dans
cette phrase ». Ainsi, deux exercices sur la même règle partagent la même méthode
et aucun texte commun n’est régénéré inutilement.

### `why`

Dans la banque finale, une entrée est obligatoire pour chaque forme de `choices`
et aucune entrée supplémentaire n’est admise. La source
`data/pilot_choice_corrections.json` ne conserve que le diagnostic de chaque
forme fautive ; le constructeur ajoute la justification de la forme correcte et
la réponse attendue.

- forme correcte : expliquer ce qui la rend correcte dans cette phrase ;
- forme fautive : citer l’écart visible, nommer précisément la règle et donner
  la forme attendue ;
- ne jamais écrire seulement « faux », « mauvaise réponse » ou « mauvais
  accord » ;
- une forme fautive citée dans le texte est entourée de backticks.

## Pipeline retenu

1. Générer et valider d’abord les exercices sans corrigé.
2. Produire les corrigés après la validation aveugle des choix.
3. Assembler `Règle` et `Méthode` depuis la pédagogie HEP.
4. Valider la structure, les quatre marqueurs, chaque clé `why`, l’absence de
   gabarit vague et la cohérence avec la réponse.
5. Soumettre les corrigés à Grammalecte et LanguageTool, puis à la revue Sol
   High groupée.
6. Générer `bank.js` seulement avec les exercices et corrigés validés.

## Affichage

Après une réponse, le site montre immédiatement la forme correcte, puis le
résumé `Dans cette phrase` et `Donc`. La règle, la méthode et les justifications
de chaque forme restent accessibles dans un détail repliable. Elles peuvent
dépasser l’écran : aucune explication n’est tronquée.

## Migration de la banque actuelle

Les 42 exercices sources conservent `application_note` comme application validée
à la phrase. Le constructeur publie uniquement l’objet `correction` complet dans
`bank.js` : l’ancien champ n’est plus exposé par l’application.
