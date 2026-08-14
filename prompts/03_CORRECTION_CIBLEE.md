# Correction ciblée

Corrige uniquement les identifiants et les défauts fournis. Conserve le slot, le
chemin et toutes les parties non concernées. Si la correction exige un autre
mécanisme ou laisse plusieurs réponses incompatibles, rends `REJECT`.

Retourne uniquement les objets corrigés et la liste des codes résolus.

Si le défaut vise un distracteur, conserve la phrase et la bonne réponse. Corrige
uniquement la forme fautive, son `mechanism_id` ou son `reasoning_break`. Ne
régénère jamais les neuf autres exercices du lot pour une correction isolée.
