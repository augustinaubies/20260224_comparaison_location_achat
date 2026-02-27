from __future__ import annotations

import pandas as pd

from simulation.configuration import ConfigurationModuleEmprunt
from simulation.modules.base import ContexteSimulation
from simulation.modules.emprunt import ModuleEmprunt


def test_emprunt_amortissement_et_capital_restant() -> None:
    config = ConfigurationModuleEmprunt(
        id="pret_test",
        type="emprunt",
        date_debut="2025-01",
        capital=12000,
        taux_annuel=0.03,
        duree_annees=2,
        taux_assurance_annuel=0,
        compte="cash",
    )
    contexte = ContexteSimulation(
        calendrier=pd.period_range("2025-01", "2026-12", freq="M"), hypotheses={}, comptes=["cash"]
    )

    sortie = ModuleEmprunt(config).executer(contexte)
    capital_rembourse = sortie.etats["capital_rembourse"]
    capital_restant = sortie.etats["capital_restant_du"]

    assert abs(float(capital_rembourse.sum()) - config.capital) < 1e-6
    assert abs(float(capital_restant.iloc[-1])) < 1e-6
