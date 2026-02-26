from __future__ import annotations

import pandas as pd

from simulation.moteur import generer_impot_revenu, generer_investissement_restant


def test_investissement_restant_tresorerie_initiale_uniquement() -> None:
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    registre_df = pd.DataFrame(
        columns=[
            "periode",
            "id_module",
            "type_module",
            "flux_de_tresorerie",
            "categorie",
            "compte",
            "description",
        ]
    )

    lignes, valeur_bourse = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_df,
        comptes_tresorerie={"cash"},
        tresorerie_initiale=1000,
        taux=1.0,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes["flux_de_tresorerie"].tolist() == [-1000.0]
    assert float(valeur_bourse.iloc[-1]) == 1000.0


def test_investissement_restant_avec_flux_positifs() -> None:
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": calendrier,
            "id_module": ["salaire", "salaire", "salaire"],
            "type_module": ["flux_fixe", "flux_fixe", "flux_fixe"],
            "flux_de_tresorerie": [100.0, 100.0, 100.0],
            "categorie": ["salaire", "salaire", "salaire"],
            "compte": ["cash", "cash", "cash"],
            "description": ["Salaire", "Salaire", "Salaire"],
        }
    )

    lignes, valeur_bourse = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_df,
        comptes_tresorerie={"cash"},
        tresorerie_initiale=0.0,
        taux=0.5,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes["flux_de_tresorerie"].tolist() == [-50.0, -75.0, -87.5]
    assert float(valeur_bourse.iloc[-1]) == 212.5


def test_investissement_restant_taux_zero_aucune_ligne() -> None:
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": calendrier,
            "id_module": ["salaire", "salaire", "salaire"],
            "type_module": ["flux_fixe", "flux_fixe", "flux_fixe"],
            "flux_de_tresorerie": [100.0, 100.0, 100.0],
            "categorie": ["salaire", "salaire", "salaire"],
            "compte": ["cash", "cash", "cash"],
            "description": ["Salaire", "Salaire", "Salaire"],
        }
    )

    lignes, _ = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_df,
        comptes_tresorerie={"cash"},
        tresorerie_initiale=0.0,
        taux=0.0,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes.empty


def test_impot_revenu_salaire_seul() -> None:
    calendrier = pd.period_range("2025-01", "2025-12", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": calendrier,
            "id_module": ["salaire"] * len(calendrier),
            "type_module": ["flux_fixe"] * len(calendrier),
            "flux_de_tresorerie": [3000.0] * len(calendrier),
            "categorie": ["salaire"] * len(calendrier),
            "compte": ["cash"] * len(calendrier),
            "description": ["Salaire"] * len(calendrier),
        }
    )

    impot = generer_impot_revenu(calendrier, registre_df, compte="cash")

    assert len(impot) == 1
    assert float(impot.iloc[0]["flux_de_tresorerie"]) == -3965.48


def test_impot_revenu_avec_abattement_micro_bic() -> None:
    calendrier = pd.period_range("2025-01", "2025-12", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": list(calendrier) + list(calendrier),
            "id_module": ["salaire"] * len(calendrier) + ["locatif"] * len(calendrier),
            "type_module": ["flux_fixe"] * len(calendrier) + ["immobilier_locatif"] * len(calendrier),
            "flux_de_tresorerie": [3000.0] * len(calendrier) + [1000.0] * len(calendrier),
            "categorie": ["salaire"] * len(calendrier) + ["loyer"] * len(calendrier),
            "compte": ["cash"] * (2 * len(calendrier)),
            "description": ["Salaire"] * len(calendrier) + ["Loyer"] * len(calendrier),
        }
    )

    impot = generer_impot_revenu(calendrier, registre_df, compte="cash")

    assert len(impot) == 1
    assert float(impot.iloc[0]["flux_de_tresorerie"]) == -5765.48
