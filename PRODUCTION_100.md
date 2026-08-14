# Production de 106 nouveaux exercices

## État au 14 août 2026

La production est terminée et intégrée à la banque publique initiale de 42
questions :

- 106 phrases, 412 choix et 306 diagnostics matérialisés ;
- 11 lots sur 11 publiables dans `data/production_review.json` ;
- 106 exercices sur 106 sans défaut de lint ni collision détectée ;
- double contrôle local complet : Grammalecte 2.3.0 et LanguageTool 6.6 ;
- 4 alertes brutes, toutes classées comme faux positifs autorisés, 0 alerte non
  résolue ;
- banque de démonstration `data/production_bank_test.js` chargée par Node avec
  106 questions : 100 à quatre choix et 6 à deux choix ;
- les 6 exercices `ou/où` sont équilibrés : 3 réponses `ou` et 3 réponses `où` ;
- 45 tests Python et le test fonctionnel JavaScript réussis.

La fusion contrôlée dans `bank.js` est réalisée par `data/bank_manifest.json`.
Aucun commit, push ou déploiement n’a été effectué.

## Résultat attendu

Produire 100 nouvelles questions avec quatre choix et trois corrections
diagnostiques chacune, puis ajouter 6 questions `ou/où` avec les deux seules
graphies pertinentes. La banque contient maintenant 148 questions.

Le fichier source de la demande est `data/production_request.json`. Le plan et
le contexte générés sont `data/drill_plan.json` et `data/prompt_context.json` ;
ce sont des artefacts reproductibles, ignorés par Git.

## Répartition

Les cinq règles initiales reçoivent chacune 20 nouvelles questions :

- graphie lexicale d’usage : 20 ;
- construction avec `à` et forme de `lequel` : 20 ;
- `dont` complément du nom : 20 ;
- adjectif verbal ou participe présent : 20, réparties 10/10 ;
- nom de peuple ou adjectif de nationalité : 20, réparties 10/10.
- `ou` conjonction ou `où` relatif de lieu ou de temps : 6, réparties 3/3.

Une nouvelle règle peut compléter ces quotas seulement si son chemin est déjà
résolu par `pedagogy_HEP.json`. Une règle absente bloque la préparation avant
toute génération.

## Découpage

La production comporte dix lots de dix exercices et un dernier lot de six. Chaque
lot suit quatre passes :

1. phrase, réponse et application à la phrase ;
2. lint déterministe et contrôle des signatures ;
3. trois distracteurs et leurs diagnostics ;
4. revue indépendante exhaustive, puis correction ciblée des seuls rejets.

La séparation des deux générations empêche une mauvaise réponse initiale de
contaminer automatiquement tous ses distracteurs et toutes ses corrections.

## Critères bloquants par exercice

- chemin grammatical canonique et fiche pédagogique résolue ;
- phrase naturelle de niveau bac avec un seul blanc ;
- une seule réponse défendable ;
- de deux à quatre choix selon la contrainte du quota ;
- un distracteur plausible pour `ou/où`, trois pour les autres règles ;
- diagnostic connu et précis pour chaque distracteur ;
- aucune proximité interdite avec la banque QCM ou les 42 exercices existants ;
- règle et famille masquées avant la réponse ;
- contrôle local enregistré en mode `REPORT_ONLY` ;
- verdict indépendant `PASS` après toute correction ciblée.

Un lot n’est jamais fusionné si un contrôle est partiel ou si un exercice reste
`REVISE` ou `REJECT`.

## Commandes de production et d’audit

```powershell
python choice_production.py prepare
python production_content.py
python choice_production.py audit-all data/drill_plan.json `
  data/production_candidates.json data/production_choice_options.json `
  data/production_choice_corrections.json data/production_review.json
```

La première commande réserve les 106 slots, valide les quotas contre la pédagogie
HEP et construit le contexte compact. La deuxième matérialise la source
éditoriale. La troisième audite les onze lots, les choix et les diagnostics.

## Rendement observé

- lot étalon : 10 produits, 10 acceptés ;
- production complète : 106 produits, 106 acceptés après la passe éditoriale ;
- lint et assemblage : 106/106 ;
- correcteurs : 106 phrases vérifiées, 4 faux positifs autorisés, 0 modification
  appliquée et 0 alerte non résolue ;
- rendement final : 100 % des candidats conservés.

Le modèle de référence est Sol High pour la génération, les diagnostics et la
revue linguistique. Une tâche purement mécanique de fusion ou de publication
peut être confiée à Terra Medium après validation des 106 éléments.
