# Scripts utilitaires

## Campagne complète

```bash
python scripts/lancer_campagne.py
```

Sorties:
- `docs/campagne_resultats.json`
- `docs/campagne_top5_ko.json`
- `sorties/campagne/<scenario>/rapport_scenario.md`
- `sorties/campagne/<scenario>/reconstruction_tresorerie.csv`

## Diagnostic d'un scénario

```bash
python scripts/analyse_sorties.py sorties/campagne/S01_sans_immo --config scenarios/parametres.defaut__S01_sans_immo.yaml --write-md
```

Le script lit automatiquement:
- `registre.csv`
- `synthese_mensuelle.csv`
- `rapport.json`
- `etats_module_*_capital_restant_du.csv`
- `etats_module_*_valeur_bourse.csv`

Et calcule:
1. trésorerie recalculée à partir des flux cash,
2. premier mois de cash négatif,
3. top flux positifs/négatifs,
4. doublons suspects du registre,
5. cohérence CRD,
6. cohérence investissements,
7. stats de sanity.
