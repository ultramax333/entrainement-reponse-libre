# Instructions des agents

Ces instructions s’appliquent à tout le sous-projet
`entrainement_reponse_libre` et à sa partie web `quiz-app/entrainement`.

## Mission

Construire un entraînement à réponse libre qui réutilise les règles, la pédagogie,
la mémoire d’erreurs et les contrôles du projet HEP, tout en restant nettement plus
simple que le pipeline QCM.

## Principes obligatoires

1. Lire tous les documents imposés par `README.md` avant d’agir.
2. Rechercher d’abord la fonction existante qui peut être réutilisée ; ne pas
   copier un module entier pour quelques fonctions.
3. Maintenir une seule taxonomie : `analyse_gpt/rules_HEP.yaml`.
4. Maintenir une seule pédagogie : `analyse_gpt/pedagogy_HEP.json`.
5. Ne jamais modifier ou remplacer `quiz-app/questions.js`.
6. Ne jamais injecter une tentative de drill dans
   `analyse_gpt/error_observations_HEP.json`.
7. Ne jamais inventer un mécanisme grammatical. Une règle ciblée doit être
   officielle, atomique et résolue par le catalogue pédagogique.
8. Masquer la règle et la famille avant la réponse.
9. Conserver les accents comme éléments significatifs par défaut.
10. Aucune suggestion de correcteur local n’est appliquée automatiquement.

## Simplicité

- Préférer une fonction pure à une classe lorsqu’aucun état complexe n’est requis.
- Préférer un petit adaptateur à un fork du pipeline HEP.
- Les prompts sont courts, chargés étape par étape et ne contiennent que les
  chemins pédagogiques nécessaires au lot.
- Aucun plafond artificiel d’appels ou de tokens, mais mesurer les coûts et grouper
  les appels pour rendre les gros lots viables.
- Sol High est le modèle de référence pour la génération et les contrôles
  linguistiques exigeants. Ne pas utiliser xhigh par défaut.

## Autonomie et validations

L’agent peut réaliser localement les parties 01 à 06 du plan, exécuter les tests et
préparer le pilote sans demander à l’utilisateur d’effectuer les étapes
intermédiaires.

Il doit s’arrêter avant :

- l’ajout du lien à l’accueil public ;
- l’intégration définitive du pilote dans la banque de drills ;
- un commit ;
- un push ;
- un déploiement.

## Git et fichiers

- Les dépôts parent et `quiz-app` peuvent contenir du travail utilisateur non lié.
- Préserver tous les changements, temporaires et benchmarks hors périmètre.
- Ne jamais utiliser `git reset --hard` ou un checkout destructif.
- Utiliser `apply_patch` pour les éditions manuelles.
- Ne pas créer de fichiers suffixés `v2`, `final`, `new`, `copy` ou datés lorsqu’un
  nom canonique existe.
- Les artefacts générés doivent être explicitement distingués des sources.

## Rapports

Le rapport final est envoyé dans la conversation. Ne jamais le coller dans
`HUB.md`, `CLAUDE.md` ou un fichier de mémoire du projet principal.

Le rapport doit indiquer :

- architecture réellement livrée ;
- fichiers créés ou modifiés ;
- fonctions effectivement réutilisées ;
- formule exacte de pondération ;
- résultats des tests ;
- pilote de 20 exercices ;
- rendement des contrôles automatiques ;
- risques et décisions restantes.
