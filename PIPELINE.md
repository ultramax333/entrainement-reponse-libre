# Mini-pipeline de production

## Objectif

Produire des drills fiables en gros lots sans transporter la complexité du format
QCM HEP.

## Étapes

### 0. Rafraîchir les entrées

- vérifier la fraîcheur de `error_priorities_HEP.txt` ;
- vérifier l’empreinte de la banque QCM ;
- importer idempotemment les feedbacks drills ;
- agréger la maîtrise ;
- calculer le bridge et le stock disponible.

### 1. Planifier

Sortie compacte : un slot par drill demandé avec seulement :

- chemin canonique ;
- poids et facteurs déjà calculés ;
- type `single_blank_short_answer` ;
- politique de casse ;
- difficulté bac ;
- contraintes de surface nécessaires ;
- empreinte du lot.

Le planificateur ne reçoit aucun historique brut ni anciennes phrases complètes.

### 2. Générer en groupe

Sol High reçoit :

- le contrat commun court ;
- les slots ;
- la projection de règles autorisées ;
- les fiches pédagogiques nécessaires ;
- quelques signatures interdites compactes.

Il produit le candidat complet, sauf la règle et la méthode générales qui restent
dans la base pédagogique.

Pour une production à choix diagnostiques, cette étape est scindée : la phrase,
la réponse et l’application passent d’abord le lint ; les trois distracteurs et
leurs diagnostics sont générés seulement ensuite. La première série de 100 est
découpée en dix lots de dix et soumise à une revue exhaustive.

### 3. Lint déterministe

Pour chaque candidat :

- schéma fermé ;
- identifiant unique ;
- exactement un blanc ;
- réponses admises valides ;
- chemin taxonomique et pédagogique résolu ;
- réponse recomposée dans la phrase ;
- absence d’indice avant réponse ;
- longueur raisonnable ;
- absence de doublon exact ou signature interdite.

Un candidat qui échoue revient en correction ciblée. Ne pas régénérer le lot entier.

### 4. Contrôle linguistique local

Recomposer la phrase avec chaque réponse admise et lancer :

- Grammalecte ;
- LanguageTool local.

Le résultat reste `REPORT_ONLY` :

- une alerte n’est pas automatiquement une faute ;
- aucune alerte n’est pas une validation ;
- panne, indisponibilité ou résultat partiel restent explicites.

### 5. Revue IA

Pendant le pilote : revue indépendante de tous les drills.

Après calibration : revue groupée seulement pour :

- alertes locales non résolues ;
- plusieurs réponses plausibles ;
- accord ou construction complexe ;
- norme variable ;
- incohérence entre chemin et phrase ;
- proximité de signature ;
- demande explicite du lint.

La revue vérifie la clé, l’unicité, la norme, le niveau bac, l’authenticité de la
phrase et l’application pédagogique. Elle ne réécrit pas la fiche générale.

### 6. Publier

Seuls les drills entièrement validés rejoignent
`quiz-app/entrainement/drills.js`.

La publication doit :

- refuser les collisions d’identifiants ;
- être atomique ;
- mettre à jour une release de banque ;
- régénérer les signatures drills ;
- préserver `quiz-app/questions.js` ;
- ne créer aucun fichier parallèle suffixé.

## Prompts minimaux à créer

```text
prompts/00_CONTRAT.md
prompts/01_GENERATION.md
prompts/02_REVUE.md
prompts/03_CORRECTION_CIBLEE.md
```

Le bridge et la planification sont déterministes : aucun prompt distinct n’est
nécessaire pour recalculer des poids.

## Coût

- un appel groupé de génération ;
- aucun appel IA pour le lint ;
- un appel groupé de revue ciblée ;
- correction uniquement des items rejetés ;
- jamais de règle pédagogique longue répétée dans chaque sortie.

Le pilote doit mesurer : nombre de candidats, taux accepté par le lint, taux
signalé par les moteurs locaux, défauts trouvés uniquement par la revue IA et
coût approximatif par drill publié.
