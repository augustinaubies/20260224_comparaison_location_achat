# Diagnostic des paramètres potentiellement legacy

## Périmètre

Audit ciblé sur les champs de configuration définis dans `simulation` et leur utilisation réelle dans le code moteur.

## Commandes utilisées

- `rg -n "pas_de_temps|devise|mois_paiement_impot_revenu" src tests README.md parametres.defaut.yaml`
- `rg -n "config\.simulation" src`

## Résultats

### `simulation.mois_paiement_impot_revenu`

- **Statut : utilisé**.
- Le champ pilote explicitement le mois de débit de l'impôt sur le revenu dans le moteur stateful.

### `simulation.devise`

- **Statut : non utilisé dans le calcul**.
- Le champ est présent dans le schéma et les fichiers YAML, mais aucune logique de calcul ne s'y branche actuellement.
- Il peut néanmoins rester pertinent à court terme pour l'affichage / export (métadonnée de sortie).

### `simulation.pas_de_temps`

- **Statut : non utilisé dans le calcul**.
- Le moteur fonctionne en mensuel (index `Period[M]`) de manière structurelle.
- Le schéma force déjà implicitement cette valeur à `"M"`.

## Recommandation

Avant suppression de `devise` et/ou `pas_de_temps`, il faut trancher la stratégie de compatibilité configuration :

1. suppression stricte immédiate (erreur de validation si champ présent),
2. maintien temporaire avec dépréciation explicite,
3. maintien comme métadonnées non bloquantes.

Ce choix impacte la compatibilité des scénarios existants et doit donc être validé via une question utilisateur dédiée dans la TODO.
