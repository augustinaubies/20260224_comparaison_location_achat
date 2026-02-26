from __future__ import annotations

import pandas as pd

from simulation.modules.emprunt import generer_echeancier


def test_crd_reste_coherent_si_la_simulation_demarre_apres_le_pret() -> None:
    calendrier = pd.period_range("2028-01", "2032-12", freq="M")

    echeancier_filtre = generer_echeancier(
        capital=120000,
        taux_annuel=0.03,
        duree_mois=240,
        date_debut="2025-01",
        calendrier_global=calendrier,
    )

    echeancier_complet = generer_echeancier(
        capital=120000,
        taux_annuel=0.03,
        duree_mois=240,
        date_debut="2025-01",
        calendrier_global=pd.period_range("2025-01", periods=240, freq="M"),
    )

    crd_reference = float(
        echeancier_complet.loc[echeancier_complet["periode"] == pd.Period("2028-01", freq="M"), "crd_debut"].iloc[0]
    )
    assert abs(float(echeancier_filtre.iloc[0]["crd_debut"]) - crd_reference) < 1e-6


def test_crd_monotone_et_final_presque_nul() -> None:
    calendrier = pd.period_range("2025-01", "2044-12", freq="M")
    echeancier = generer_echeancier(
        capital=180000,
        taux_annuel=0.035,
        duree_mois=240,
        date_debut="2025-01",
        calendrier_global=calendrier,
    )

    assert (echeancier["capital_restant_du"] >= -1e-9).all()
    assert (echeancier["capital_restant_du"].diff().dropna() <= 1e-9).all()
    assert abs(float(echeancier.iloc[-1]["capital_restant_du"])) < 1e-6
