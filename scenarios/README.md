# Scénarios de validation CLI

Chaque fichier `parametres.defaut__*.yaml` est une variante complète de paramètres.

## Exécution d'un scénario

```bash
python -m src.simulation.cli --parametres-defaut scenarios/parametres.defaut__S01_sans_immo.yaml
```

## Lancer la campagne complète

```bash
python scripts/lancer_campagne.py
```

Les sorties sont écrites dans `sorties/campagne/<nom_scenario>/` et le récapitulatif dans `docs/campagne_resultats.json`.
