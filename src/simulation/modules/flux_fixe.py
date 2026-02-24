from __future__ import annotations

import pandas as pd

from simulation.configuration import ConfigurationModuleFluxFixe
from simulation.modules.base import ContexteSimulation, ModuleSimulation, SortieModule


class ModuleFluxFixe(ModuleSimulation):
    type_module = "flux_fixe"

    def __init__(self, config: ConfigurationModuleFluxFixe) -> None:
        self.config = config
        self.id_module = config.id

    def executer(self, contexte: ContexteSimulation) -> SortieModule:
        debut = pd.Period(self.config.debut, freq="M")
        fin = pd.Period(self.config.fin, freq="M")
        periodes = contexte.calendrier[(contexte.calendrier >= debut) & (contexte.calendrier <= fin)]
        signe = 1.0 if self.config.sens == "revenu" else -1.0
        flux = pd.DataFrame(
            {
                "periode": periodes,
                "id_module": self.id_module,
                "type_module": self.type_module,
                "flux_de_tresorerie": signe * self.config.montant,
                "categorie": self.config.categorie,
                "compte": self.config.compte,
                "description": f"Flux fixe {self.config.categorie}",
            }
        )
        return SortieModule(registre_lignes=flux, etats={})
