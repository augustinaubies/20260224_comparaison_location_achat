from __future__ import annotations

import pandas as pd

from ..configuration import ConfigurationModuleInvestissementDCA
from .base import ContexteSimulation, ModuleSimulation, SortieModule


class ModuleInvestissementDCA(ModuleSimulation):
    type_module = "investissement_dca"

    def __init__(self, config: ConfigurationModuleInvestissementDCA) -> None:
        self.config = config
        self.id_module = config.id

    def executer_batch(self, contexte: ContexteSimulation) -> SortieModule:
        debut_effectif = (
            pd.Period(self.config.debut, freq="M") if self.config.debut else contexte.calendrier[0]
        )
        fin_effectif = (
            pd.Period(self.config.fin, freq="M") if self.config.fin else contexte.calendrier[-1]
        )
        periodes = contexte.calendrier[
            (contexte.calendrier >= debut_effectif) & (contexte.calendrier <= fin_effectif)
        ]
        taux_mensuel = (1 + self.config.rendement_annuel_attendu) ** (1 / 12) - 1

        valeur = 0.0
        valeurs: list[float] = []
        lignes: list[dict] = []
        for periode in periodes:
            valeur = valeur * (1 + taux_mensuel) + self.config.versement_mensuel
            valeurs.append(valeur)
            lignes.append(
                {
                    "periode": periode,
                    "id_module": self.id_module,
                    "type_module": self.type_module,
                    "flux_de_tresorerie": -self.config.versement_mensuel,
                    "categorie": "versement_dca",
                    "compte": self.config.compte,
                    "description": "Versement DCA mensuel",
                }
            )

        etats = {
            "valeur_bourse": pd.Series(valeurs, index=periodes, name="valeur_bourse"),
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
