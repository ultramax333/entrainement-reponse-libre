# Architecture

## Vue d’ensemble

```text
historique QCM local ───────────────┐
feedback QCM Drive → agrégateur HEP ├─→ bridge de besoins ─→ mini-planificateur
demande manuelle de règle ──────────┤                         │
feedback drills Drive → agrégateur ─┘                         ▼
                                                   génération de drills
                                                             │
                                         lint + correcteurs + revue ciblée
                                                             │
                                                             ▼
                                             banque canonique drills.js
                                                             │
                                                             ▼
                                            page /entrainement/
```

## Réutiliser sans changement de source

| Source existante | Usage dans le sous-projet |
|---|---|
| `rules_HEP.yaml` | familles et mécanismes autorisés |
| `pedagogy_HEP.json` | règle, exemple, méthode et références |
| `pedagogy_HEP.py` | validation et résolution des fiches |
| `pedagogy.js` | affichage pédagogique côté navigateur |
| `error-profile.js` | lecture immédiate des erreurs QCM locales |
| `error_priorities_HEP.txt` | signal QCM compact synchronisé |
| `exam_rule_evidence_HEP.json` | importance officielle des règles |
| `correcteurs_HEP.py` | Grammalecte et LanguageTool locaux |
| signatures QCM | contrôle de proximité avec la banque existante |

## Adapter

| Brique HEP | Adaptation minimale |
|---|---|
| projection de contexte | seulement les chemins choisis et leur pédagogie |
| boucle de production | trois sorties : candidat, contrôle, publication |
| signatures | index drills distinct + comparaison QCM en lecture seule |
| feedback/import | nouveau schéma drill, même idempotence |
| Drive | petite couche partagée seulement si la rétrocompatibilité est testée |
| PWA | ajouter la route et les fichiers après validation du pilote |

## Créer

```text
entrainement_reponse_libre/
  README.md
  AGENTS.md
  ARCHITECTURE.md
  DATA_AND_WEIGHTING.md
  PIPELINE.md
  TESTING.md
  IMPLEMENTATION_PLAN.md
  pipeline_drills.py              # futur point d’entrée CLI
  bridge_priorities.py            # futur agrégateur/bridge
  schemas/                         # schémas drill et feedback
  prompts/                         # prompts courts par étape
  data/                            # observations et sorties canoniques
  tests/                           # tests Python

quiz-app/entrainement/
  index.html
  app.js
  style.css
  drills.js                       # banque publiée unique
  drill-profile.js
  test_drills.js
```

Les noms précis peuvent être ajustés avant création si une convention existante
rend un autre nom clairement meilleur. Ne pas multiplier les fichiers.

## Séparation des responsabilités

### Projet HEP principal

- conserve la banque QCM ;
- importe et agrège les séances QCM ;
- produit `error_priorities_HEP.txt` ;
- reste responsable des déploiements.

### Sous-projet drills

- importe les séances de réponse libre ;
- calcule une maîtrise séparée ;
- combine des signaux déjà agrégés ;
- conserve séparément les demandes volontaires de règles à revoir ;
- génère et contrôle des exercices courts ;
- publie uniquement `bank.js` et la page dédiée.

## Navigateur et stockage

La page se trouve sur la même origine que le QCM. Elle peut donc lire l’historique
QCM local pour choisir immédiatement les règles à travailler, sans recopier les
séances.

Stockages séparés et versionnés :

```text
hep-drill-seen/1.0
hep-drill-progress/1.0
hep-drill-history/1.0
hep-drill-sync/1.0
```

Le choix final des clés doit être centralisé dans un seul module.

## Absence de double comptage

- Le tableau local sert à personnaliser immédiatement la page.
- Le pipeline hors navigateur utilise seulement les séances synchronisées et
  importées.
- Une séance importée est identifiée par un `session_id` stable.
- Une tentative drill ne modifie jamais le journal QCM.
- Le bridge lit les deux résumés, pas les historiques bruts dans les prompts.
