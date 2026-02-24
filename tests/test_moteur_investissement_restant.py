from __future__ import annotations

import pandas as pd

from simulation.moteur import generer_investissement_restant


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
        tresorerie_initiale=0.0,
        taux=0.0,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes.empty
