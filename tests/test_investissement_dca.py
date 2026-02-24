from __future__ import annotations

import pandas as pd

from simulation.configuration import ConfigurationModuleInvestissementDCA
from simulation.modules.base import ContexteSimulation
from simulation.modules.investissement_dca import ModuleInvestissementDCA


def test_dca_evolution_valeur_simple() -> None:
    config = ConfigurationModuleInvestissementDCA(
        id="dca_test",
        type="investissement_dca",
        debut="2025-01",
        fin="2025-03",
        versement_mensuel=100,
        rendement_annuel_attendu=0.0,
        compte="courtier",
    )
    contexte = ContexteSimulation(
        calendrier=pd.period_range("2025-01", "2025-03", freq="M"), hypotheses={}, comptes=["courtier"]
    )

    sortie = ModuleInvestissementDCA(config).executer(contexte)
    valeur = sortie.etats["valeur_bourse"]

    assert float(valeur.iloc[-1]) == 300.0
    assert len(sortie.registre_lignes) == 3



def test_dca_sans_bornes_utilise_calendrier_global() -> None:
    config = ConfigurationModuleInvestissementDCA(
        id="dca_global",
        type="investissement_dca",
        versement_mensuel=50,
        rendement_annuel_attendu=0.0,
        compte="courtier",
    )
    contexte = ContexteSimulation(
        calendrier=pd.period_range("2025-01", "2025-04", freq="M"),
        hypotheses={},
        comptes=["courtier"],
    )

    sortie = ModuleInvestissementDCA(config).executer(contexte)

    assert len(sortie.registre_lignes) == 4
    assert float(sortie.etats["valeur_bourse"].iloc[-1]) == 200.0
