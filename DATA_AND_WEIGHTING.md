# Contrats de données et pondération

## Drill publié — `hep-drill/1.0`

Contrat minimal fermé :

```json
{
  "schema_version": "hep-drill/1.0",
  "id": "hep-d1-20260809-0001",
  "source_batch_id": "hep-db1-20260809-0001",
  "family": "accord_participe_passe",
  "mechanism_id": "avoir_cvd_avant",
  "detail_id": "core",
  "tense_id": "passe_compose",
  "prompt": "Les lettres qu’elle a ___ sont arrivées.",
  "accepted_answers": ["envoyées"],
  "display_answer": "envoyées",
  "application_note": "Le COD « qu’ », qui reprend « les lettres », est placé avant le participe.",
  "pedagogy_dict_version": "hep-pedagogy-dict/2.0"
}
```

Contraintes :

- exactement un `___` ;
- une réponse courte ;
- `accepted_answers` non vide et sans doublon après normalisation ;
- `display_answer` appartient aux réponses admises ;
- chemin canonique validé contre les règles et la pédagogie ;
- `detail_id` et `tense_id` peuvent être `null` ;
- aucun texte général de règle dupliqué dans le drill ;
- `application_note` explique uniquement l’application à cette phrase.

## Normalisation des réponses

Ordre déterministe :

1. Unicode NFC ;
2. espaces périphériques supprimés ;
3. suites d’espaces ramenées à un espace ;
4. apostrophes courbes et droites rendues équivalentes ;
5. casse neutralisée seulement si `case_sensitive=false` dans la politique du
   mécanisme ;
6. accents toujours conservés par défaut.

Pas de correction floue, pas de suppression générale de ponctuation et aucune
distance de Levenshtein automatique.

## Feedback — `hep-drill-feedback/1.0`

Une séance conserve les réussites comme les erreurs :

```json
{
  "schema_version": "hep-drill-feedback/1.0",
  "session_id": "hep-ds1-...",
  "started_at": "...",
  "completed_at": "...",
  "bank_release": "drills-...",
  "attempts": [
    {
      "drill_id": "hep-d1-...",
      "family": "...",
      "mechanism_id": "...",
      "detail_id": null,
      "tense_id": null,
      "correct": false,
      "answered_at": "..."
    }
  ]
}
```

La réponse brute saisie n’est pas exportée en V1 : elle n’est pas nécessaire au
poids de génération et augmenterait la sensibilité des données. Elle peut rester
localement le temps d’afficher la correction.

## Agrégat de maîtrise

Clé :

```text
family + mechanism_id + detail_id + tense_id
```

Valeurs minimales :

- tentatives ;
- réussites ;
- erreurs ;
- séances distinctes ;
- séances avec erreur ;
- série correcte actuelle ;
- dernière exposition ;
- dernière erreur.

## Activation d’un signal drill

Reprendre la prudence du système QCM :

- au moins 2 tentatives ;
- au moins 2 erreurs ;
- au moins 2 séances distinctes ;
- confiance minimale `.25`.

Une erreur isolée reste visible mais ne pilote pas une génération.

## Taux d’échec lissé

Réutiliser le prior Beta(1,3) :

```text
failure_rate = (errors + 1) / (attempts + 4)

confidence =
  min(1, attempts / 6)
  × min(1, sessions / 2)

drill_failure_need = failure_rate × confidence
```

La confiance évite qu’un petit échantillon domine le bridge.

## Signal QCM

Lire les colonnes déjà calculées de `error_priorities_HEP.txt`. Ne pas réinjecter
l’historique et ne pas remultiplier les facteurs d’examen déjà présents.

Pour le bridge, utiliser le facteur personnel `errf`, pas le poids final HEP :

```text
qcm_factor = errf
```

Si aucune ligne active n’existe pour le chemin, `qcm_factor = 1`.

## Récupération par les drills

Le signal QCM ne commence à diminuer que si le chemin possède au moins
6 tentatives de drill sur 2 séances.

```text
reliable_success = (1 - failure_rate) × confidence
recovery_factor = max(0.60, 1 - 0.40 × reliable_success)

adjusted_qcm_factor =
  1 + (qcm_factor - 1) × recovery_factor
```

Une réussite fiable peut donc réduire le bonus QCM de 40 % au maximum, jamais
effacer brutalement l’erreur historique.

## Facteur personnel combiné

Mettre le signal drill sur la même échelle que le `error_gain` actuel :

```text
drill_factor = 1 + error_gain × drill_failure_need

personal_factor = max(adjusted_qcm_factor, drill_factor)
```

Prendre le maximum évite de compter deux fois le même besoin.

## Stock et espacement

Stock cible V1 : 5 drills non vus par chemin actif.

```text
stock_gap = clamp((5 - unseen_available) / 5, 0, 1)
```

Réutiliser la fenêtre actuelle de 48 questions pour l’espacement, avec un facteur
compris entre `.72` et `1`. Le compteur drill est séparé du compteur QCM.

## Poids final de génération

```text
generation_weight =
  exam_factor
  × personal_factor
  × stock_gap
  × spacing_factor
```

Éligibilité :

- priorité QCM active ; ou
- signal drill actif ; ou
- demande utilisateur explicite conservée dans `data/manual_review_rules.json`.

Une règle sans preuve d’examen peut rester accessible par erreur personnelle ou
demande explicite, mais ne reçoit pas artificiellement une forte importance.
