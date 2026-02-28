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

- **Statut : legacy supprimé**.
- Le champ a été retiré du schéma `ConfigurationSimulation` et des fichiers YAML de paramètres/scénarios.
- Toute présence résiduelle déclenche désormais une erreur de validation (`extra=forbid`).

### `simulation.pas_de_temps`

- **Statut : legacy supprimé**.
- Le moteur restant structurellement mensuel, le champ a été retiré du schéma de configuration.
- Toute présence résiduelle déclenche désormais une erreur de validation (`extra=forbid`).

## Recommandation

Décision utilisateur appliquée : suppression stricte des deux champs non utilisés, sans phase de dépréciation.
