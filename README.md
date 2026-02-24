# Moteur de simulation de portefeuille (Python)

Projet modulaire pour simuler un portefeuille financier (flux de trésorerie, emprunts, immobilier locatif, investissement progressif) avec une architecture extensible orientée modules.

## Points clés

- Calendrier mensuel partagé (`PeriodIndex`) pour tous les modules.
- Configuration centralisée avec surcharge **défaut + utilisateur**.
- Registre central des flux + synthèse mensuelle + rapport de métriques.
- Architecture extensible: ajouter un module nécessite une nouvelle classe et son enregistrement dans la factory.

## Installation rapide

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Exécution CLI

```bash
python -m simulation.cli run \
  --defaut parametres.defaut.yaml \
  --utilisateur parametres.utilisateur.yaml \
  --sortie resultats/run1
```

## Fichiers de configuration

- `parametres.defaut.yaml`: paramètres publics versionnés.
- `parametres.utilisateur.yaml`: surcharge locale simple à éditer.

Règle de chargement:
1. Chargement des valeurs de `parametres.defaut.yaml`.
2. Fusion profonde avec `parametres.utilisateur.yaml`.
3. Si le fichier utilisateur est vide (ou `{}`), aucun impact.

## Structure des résultats

- `registre.csv`: registre détaillé des flux (`periode`, `id_module`, `type_module`, `flux_de_tresorerie`, `categorie`, `compte`, `description`).
- `synthese_mensuelle.csv`: `flux_net`, `solde_tresorerie`.
- `etats_module_<id>_<etat>.csv`: états exportés par module.
- `rapport.json`: métriques clés.

## Ajouter un nouveau module

1. Créer une config pydantic dans `configuration.py` (avec discriminateur `type`).
2. Implémenter une classe dans `src/simulation/modules/` héritant de `ModuleSimulation`.
3. Retourner `SortieModule` (`registre_lignes` + `etats`).
4. Enregistrer la classe dans `creer_module` (`moteur.py`).

## Tests

```bash
pytest
```
