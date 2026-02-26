# Validation manuelle CLI - campagne de robustesse

## Grille de contrôle appliquée

- Trésorerie: détection de solde négatif et cohérence flux/cumul.
- Emprunt: CRD non négatif, monotone, nul à maturité si échéancier complet.
- Immobilier: cohérence achat/location, pas de double comptage détecté dans le registre.
- Investissement: valeur bourse non négative, versements non négatifs.
- Sanity checks: stats min/max/quantiles et doublons de flux.

## Anomalies initiales détectées puis corrigées

1. **Impossible de lancer `python -m src.simulation.cli`**: imports absolus `simulation.*` non résolus hors installation package. Correction: imports relatifs dans tout `src/simulation`.

2. **Crash `KeyError: capital_restant_du`** quand un emprunt est hors horizon. Cause: DataFrame vide sans colonnes dans `generer_echeancier`. Correction: retour d'un DataFrame vide avec schéma explicite.

3. **Incohérence métier immobilière** (location possible avant achat). Cause: absence de validation date achat/location. Correction: validation Pydantic `date_debut_location >= date_achat` + défaut YAML corrigé.

## Résultats de campagne

| Scénario | Statut CLI | Anomalies |
|---|---|---|
| B01_bug2030_derniere_echeance | OK | Trésorerie négative dès 2028-01 |
| B02_bug2030_taux_capital | OK | Trésorerie négative dès 2028-01 |
| B03_bug2030_decalage_debut | OK | Trésorerie négative dès 2028-01 |
| E01_6_mois | OK | Aucune |
| E02_40_ans | OK | Trésorerie négative dès 2027-01 |
| E03_debut_milieu_annee | OK | Trésorerie négative dès 2026-03 |
| E04_inflation_zero | OK | Trésorerie négative dès 2028-01 |
| E05_inflation_10 | OK | Trésorerie négative dès 2028-01 |
| E06_inflation_negative | OK | Trésorerie négative dès 2028-01 |
| E07_rendement_zero | OK | Trésorerie négative dès 2028-01 |
| E08_crash_marche | OK | Trésorerie négative dès 2028-01 |
| E09_emprunt_cher_apport_zero | OK | Trésorerie négative dès 2028-01 |
| E10_pas_invest | OK | Aucune |
| E11_salaire_nul_periode | OK | Trésorerie négative dès 2027-01 |
| E12_depenses_sup_salaire | OK | Trésorerie négative dès 2025-02 |
| E13_loyer_nul_vacance_100 | OK | Trésorerie négative dès 2025-02 |
| E14_emprunt_5_ans | OK | Trésorerie négative dès 2025-02 |
| E15_emprunt_30_ans | OK | Trésorerie négative dès 2028-01 |
| S01_sans_immo | OK | Aucune |
| S02_rp | OK | Aucune |
| S03_locatif_seul | OK | Aucune |
| S04_rp_puis_locatif | OK | Aucune |
| S05_inflation_moderee | OK | Aucune |

## Analyse spécifique bug 2030

- Scénarios `B01`, `B02`, `B03` exécutés pour forcer des maturités proches/loin de 2030.
- Aucun CRD négatif ni non-monotonicité observé après correction du schéma d'échéancier.
- Le seul signal restant est la trésorerie négative (comportement attendu quand flux sortants > entrants sans garde de découvert).

## Limites restantes et recommandations

- Plusieurs scénarios de bord gardent une trésorerie négative: le moteur autorise implicitement le découvert.
- Recommandation: ajouter un mode optionnel `interdire_decouvert` pour bloquer/réduire automatiquement les versements d'investissement quand cash insuffisant.
