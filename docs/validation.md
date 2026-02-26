# Validation CLI - cohérence physique/maths/financière

## Méthode appliquée

Cycle itératif suivi:
1. Exécution complète de la campagne (`python scripts/lancer_campagne.py`).
2. Diagnostic automatique scénario par scénario via `scripts/analyse_sorties.py` (sorties: `rapport_scenario.md` + `reconstruction_tresorerie.csv`).
3. Identification des KO avec mois de rupture et flux dominants.
4. Localisation de cause racine dans le moteur (agrégation flux cash vs non-cash).
5. Correction, puis relance subset + campagne complète.

## Grille de cohérence non négociable

- **Trésorerie**: cash recalculé mois par mois depuis `registre.csv`, détection du premier mois négatif.
- **Conservation cash**: comparaison `cash_fin_recalcule` vs `solde_tresorerie` de `synthese_mensuelle.csv`.
- **Registre**: top flux ± par `(categorie, id_module)`, doublons suspects (`periode/categorie/montant/description`).
- **Emprunts**: CRD min, monotonicité, CRD négatif, deltas mensuels.
- **Investissements**: flux sur comptes bourse, signe des versements, valeur bourse non négative.
- **Sanity stats**: min/max/quantiles des flux.

## 5 KO initiaux les plus évidents (avant correction)

| Scénario | Mois rupture | Solde final trésorerie (rapport) | Flux responsables dominants |
|---|---|---:|---|
| E12_depenses_sup_salaire | 2025-02 | -626205.64 | depenses_courantes, versement_restant |
| E05_inflation_10 | 2028-01 | -459028.19 | depenses_courantes indexées + versement_dca |
| E02_40_ans | 2027-01 | -375752.42 | charges long terme + investissements |
| E13_loyer_nul_vacance_100 | 2025-02 | -273190.35 | achat/charges locatives, mensualités emprunt |
| B03_bug2030_decalage_debut | 2028-01 | -256415.75 | mensualités locatif + versements investissement |

## Chaîne causale et cause racine

- Symptôme observé: plusieurs scénarios affichaient un `solde_tresorerie` fortement négatif alors que le cash réel restait compatible avec les flux de trésorerie.
- Preuve: la reconstruction cash depuis `registre.csv` (en ne gardant que les comptes de trésorerie) divergeait de `synthese_mensuelle.csv`.
- Cause racine: le moteur calculait la synthèse de trésorerie et l'investissement "restant" sur **tous** les flux du registre (y compris comptes bourse), au lieu des seuls comptes cash.
- Effet: les versements bourse (DCA / restant) étaient comptés comme destruction nette de trésorerie agrégée, provoquant des soldes artificiellement négatifs.

## Correctifs appliqués

1. `calculer_synthese_mensuelle` accepte désormais `comptes_tresorerie` et agrège uniquement ces comptes.
2. `generer_investissement_restant` calcule le cash disponible uniquement à partir des flux des comptes de trésorerie.
3. Les comptes cash sont déterminés en amont dans le moteur et réutilisés de manière cohérente pour synthèse + invariant + investissement restant.
4. Le script d'analyse a été enrichi pour générer un rapport markdown par scénario et exporter une reconstruction cash détaillée.

## Validation après correction

- Relance complète campagne: **23/23 scénarios en verdict OK**.
- Plus de divergence `cash_recalculé` vs `synthese_mensuelle` sur les scénarios de campagne.
- Les 5 KO initiaux disparaissent avec la correction moteur globale.

## Anomalies restantes

- Aucune anomalie bloquante détectée dans la campagne existante.
- Limite connue: absence de mode explicite `interdire_decouvert` au niveau produit (non nécessaire pour la campagne actuelle, mais amélioration future possible).
