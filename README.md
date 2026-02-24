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

## Paramétrage des modules

### `flux_fixe`

- `montant`: montant de base mensuel.
- `debut` / `fin` (optionnels): si absents, le module utilise automatiquement les bornes de la simulation.
- `indexation` (optionnel): `"aucune"` (défaut) ou `"inflation"`.
- `periode_reference` (optionnel): période de référence (`YYYY-MM`) du `montant`.
  - Si absente, la référence est `debut` effectif du module.
  - En indexation inflation, la formule appliquée est: `montant(t) = montant_ref * (1+inflation)^(delta_mois/12)`.

### `investissement_dca`

- `debut` / `fin` (optionnels): si absents, le DCA s'applique sur tout le calendrier de simulation.
- `versement_mensuel`: montant investi chaque mois.
- `rendement_annuel_attendu`: rendement annualisé converti en rendement mensuel composé.

### `portefeuille`

- `tresorerie_initiale`: cash de départ pour la synthèse de trésorerie.
- `taux_investissement_restant`: fraction `[0,1]` du cash disponible investi automatiquement chaque fin de mois.
  - `1.0`: sweep complet du cash positif.
  - `0.0`: désactivé.
- `rendement_annuel_investissement_restant` (optionnel): override du rendement du sweep auto.
  - Si absent, utilise `hypotheses.rendement_marche`.
- `id_module_investissement_restant`: identifiant de module utilisé dans le registre (`investissement_restant` par défaut).
- `compte_investissement_restant`: compte de destination des versements (`courtier` par défaut).

## Structure des résultats

- `registre.csv`:
  - Colonnes: `periode`, `id_module`, `type_module`, `flux_de_tresorerie`, `categorie`, `compte`, `description`.
  - Catégories fréquentes: `versement_dca`, `versement_restant`, `loyer`, `charges`, `depenses_courantes`, etc.
  - Le sweep automatique ajoute des lignes avec `categorie=versement_restant`.
- `synthese_mensuelle.csv`:
  - `flux_net`: somme des flux du mois.
  - `solde_tresorerie`: cumul de trésorerie à partir de `tresorerie_initiale`.
  - Le solde inclut l'effet du versement automatique du restant.
- `etats_module_<id>_<etat>.csv`:
  - Export des états de chaque module (ex: `valeur_bourse`, `capital_restant_du`, `interets_payes`).
  - Le sweep auto exporte `etats_module_investissement_restant_valeur_bourse.csv`.
- `rapport.json`:
  - Métriques globales (`solde_final_tresorerie`, `flux_net_cumule`, `flux_cumule_par_module`).
  - Métriques spécifiques modules quand disponibles (ex: intérêts totaux d'emprunt, NOI locatif).

## Exemples de paramétrage

### Dépense de vie indexée inflation

```yaml
- id: "depenses_vie"
  type: "flux_fixe"
  montant: 1800
  sens: "depense"
  categorie: "depenses_courantes"
  indexation: "inflation"
```

### DCA sur toute la simulation (sans `debut` / `fin`)

```yaml
- id: "dca_monde"
  type: "investissement_dca"
  versement_mensuel: 500
  rendement_annuel_attendu: 0.06
```

### Sweep auto activé / désactivé

```yaml
portefeuille:
  taux_investissement_restant: 1.0 # activé
```

```yaml
portefeuille:
  taux_investissement_restant: 0.0 # désactivé
```

## Ajouter un nouveau module

1. Créer une config pydantic dans `configuration.py` (avec discriminateur `type`).
2. Implémenter une classe dans `src/simulation/modules/` héritant de `ModuleSimulation`.
3. Retourner `SortieModule` (`registre_lignes` + `etats`).
4. Enregistrer la classe dans `creer_module` (`moteur.py`).

## Tests

```bash
pytest
```
