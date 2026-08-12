# Import des règles à revoir depuis le QCM

## Principe

Le transfert est unidirectionnel. Le QCM produit un résumé JSON ; ce site le lit
et ne renvoie rien au QCM. Le fichier ne contient ni réponse, ni texte de
question, ni historique de séance.

Le contrat machine est
`schemas/hep-qcm-review-priorities.schema.json`. Un exemple se trouve dans
`data/qcm_review_priorities.example.json`.

Le contrat est fermé : tout champ supplémentaire, notamment une réponse ou un
texte de question, fait rejeter le fichier.

## Contenu minimal

Chaque ligne contient uniquement le chemin canonique de la règle et son facteur
personnel :

```json
{
  "family": "pronoms_relatifs",
  "mechanism_id": "possession_dont",
  "detail_id": null,
  "tense_id": null,
  "priority": 1.23
}
```

Une valeur `1` est neutre. Une valeur supérieure à `1` augmente la priorité. Le
site accepte les valeurs de `1` à `4` et ignore proprement une règle pour laquelle
sa banque ne possède encore aucun exercice.

Côté QCM, `priority` doit recevoir le facteur personnel `errf`, pas le poids HEP
final : l’importance dans l’examen ne doit pas être multipliée une seconde fois.

## Import dans le site

Le bouton **Importer les règles du QCM** lit le fichier sur l’appareil. Le dernier
instantané valide remplace le précédent. Le même `export_id` n’est pas réimporté.
Le document est conservé dans le stockage local du navigateur.

## Poids local

Chaque réponse de ce site actualise un profil séparé : tentatives, réussites,
erreurs, série correcte et dates. Le besoin local utilise :

```text
failure_rate = (errors + 1) / (attempts + 4)
confidence = min(1, attempts / 6)
local_factor = 1 + 1.5 × failure_rate × confidence × recovery
```

`recovery` vaut `1`, `0.8` ou `0.6` selon que la série correcte actuelle contient
zéro, une ou au moins deux réussites. Le facteur QCM ne diminue qu’après six
réponses locales. Le poids effectif est le maximum du signal QCM ajusté et du
signal local : la même faiblesse n’est donc pas comptée deux fois.

## Portée en ligne

Sur GitHub Pages, le profil et le dernier import restent dans le navigateur et
sur l’appareil utilisés. La synchronisation entre appareils sera traitée plus
tard avec la sauvegarde Google Drive.
