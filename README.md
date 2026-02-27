# Moteur de simulation de portefeuille (Python)

Projet modulaire pour simuler un portefeuille financier (flux de trésorerie, emprunts, immobilier locatif, résidence principale, investissement automatique du restant) avec une architecture extensible orientée modules.

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

Commande minimale (sans argument):

```bash
python -m simulation.cli
```

La CLI applique toujours cet ordre:

1. `parametres.defaut.yaml` (chemin fixe à la racine du repo).
2. `parametres.utilisateur.yaml` (même racine, facultatif).
3. Export automatique dans `sorties/YYYY-MM-DD_HHMMSS` (timezone Europe/Paris).

Vous pouvez aussi garder la commande explicite:

```bash
python -m simulation.cli run
```

Exemples d'override:

```bash
python -m simulation.cli \
  --parametres-defaut /chemin/vers/parametres.defaut.yaml \
  --parametres-utilisateur /chemin/vers/parametres.utilisateur.yaml \
  --sortie /tmp/ma-sortie \
  --nom-run test_rapide
```

> Si `--sortie` est fourni, la CLI écrit directement dans ce dossier (sans sous-dossier horodaté).

Par défaut, la simulation écrit uniquement `rapport.json` dans le dossier de sortie. Pour conserver les exports historiques (`registre.csv`, `synthese_mensuelle.csv`, `etats_module_*.csv`), activez explicitement l'option `--csv`.

Mode diagnostic (invariants stricts + exports de debug):

```bash
python -m simulation.cli run --diagnostic --periode-debug 2030-01 --periode-debug 2030-05
```

En mode `--diagnostic`, toute violation d'invariant provoque un échec immédiat de la simulation.

Mode Monte Carlo (tirages aléatoires des hypothèses macro):

```bash
python -m simulation.cli monte-carlo --tirages 500 --graine 42
```

Cette commande produit:
- `monte_carlo_tirages.csv` (1 ligne par tirage + hypothèses tirées),
- `monte_carlo_resume.csv` (statistiques descriptives),
- et le snapshot de paramétrage (`parametres.*.yaml`).

## Fichiers de configuration

- `parametres.defaut.yaml`: paramètres publics versionnés.
- `parametres.utilisateur.yaml`: surcharge locale simple à éditer (à placer à la racine du repo par défaut).

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

### `portefeuille`

- `tresorerie_initiale`: cash de départ pour la synthèse de trésorerie.
- `taux_investissement_restant`: fraction `[0,1]` du cash disponible investi automatiquement chaque fin de mois.
  - `1.0`: sweep complet du cash positif.
  - `0.0`: désactivé.
- `rendement_annuel_investissement_restant` (optionnel): override du rendement du sweep auto.
  - Si absent, utilise `hypotheses.rendement_marche`.
- `id_module_investissement_restant`: identifiant de module utilisé dans le registre (`investissement_restant` par défaut).
- `compte_investissement_restant`: compte de destination des versements (`courtier` par défaut).
- `loyer_residence_principale`: loyer mensuel de RP tant qu'aucune RP n'est possédée.
- `reste_a_vivre_minimum`: montant minimal conservé sur le compte courant avant sweep d'investissement.
- `reste_a_vivre_mois_depenses`: multiple des sorties de trésorerie mensuelles à conserver en cash.
- `indexer_reste_a_vivre_sur_inflation`: active l'indexation annuelle du `reste_a_vivre_minimum` au 1er janvier.

## Fiscalité

- Un flux annuel `impot_sur_le_revenu` est généré en septembre N+1 (configurable via `simulation.mois_paiement_impot_revenu`).
- Base imposable: salaires (`categorie=salaire`) + 50% des loyers locatifs meublés (`categorie=loyer`, hypothèse micro-BIC).
- Barème progressif français appliqué par tranches, avec indexation annuelle des bornes sur `hypotheses.inflation_annuelle` (sans prélèvements sociaux supplémentaires).

## Structure des résultats

Arborescence par défaut:

```text
sorties/
  2026-02-24_154501/
    rapport.json
```

Avec `--csv`, les fichiers `registre.csv`, `synthese_mensuelle.csv` et `etats_module_*.csv` sont également exportés.

- `registre.csv`:
  - Colonnes: `periode`, `id_module`, `type_module`, `flux_de_tresorerie`, `categorie`, `compte`, `description`.
  - Convention de signe: flux entrant (revenu) positif, flux sortant (dépense/versement) négatif.
  - Catégories fréquentes: `versement_restant`, `loyer`, `charges`, `loyer_residence_principale`, `impot_sur_le_revenu`, `depenses_courantes`, etc.
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

Exports additionnels en mode diagnostic:

- `grand_livre_mensuel.csv`: total des flux, pivot par compte, trésorerie début/fin et états clés (bourse, CRD).
- `details_emprunt_<id>.csv`: détail mensuel de l'échéancier (CRD début/fin, intérêt, principal, mensualité).
- `anomalies.csv`: liste des invariants violés.

## Conventions comptables et ordre d'application

- Les modules écrivent uniquement des flux dans le registre.
- Les états (`capital_restant_du`, `valeur_bourse`, etc.) sont dérivés de manière déterministe.
- Ordre mensuel ciblé:
  1. revenus,
  2. dépenses de vie,
  3. mensualités emprunt,
  4. charges locatives,
  5. impôt sur le revenu annuel (décembre),
  6. investissement automatique du restant (jamais si cash restant <= 0).

Invariants vérifiés mensuellement:

- trésorerie non négative,
- CRD non négatif et monotone,
- principal d'emprunt non négatif,
- valeur bourse non négative,
- détection de doublons de flux (même période/catégorie/description/montant).

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

### Résidence principale

```yaml
- id: "rp"
  type: "residence_principale"
  date_achat: 2025-03
  prix: 320000
  frais_notaire: 22000
  apport: 40000
  emprunt:
    taux_annuel: 0.032
    duree_annees: 25
    assurance_mensuelle: 45
  taxe_fonciere_annuelle: 1400
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
