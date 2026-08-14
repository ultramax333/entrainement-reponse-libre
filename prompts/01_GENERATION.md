# Génération groupée

Complète chaque slot une fois, dans le même ordre. Vise le niveau bac et une
phrase naturelle. Cherche activement si une autre réponse courte serait
défendable; si oui, ajoute-la seulement si elle teste exactement le même
mécanisme, sinon signale le slot au lieu de forcer une clé unique.

Retourne uniquement le JSON demandé. Ne joins ni commentaire ni auto-évaluation.

Cette passe produit seulement la phrase, la réponse admise et
`application_note`. Elle ne produit aucun choix ni diagnostic : ceux-ci sont
créés après le lint, dans une passe séparée.
