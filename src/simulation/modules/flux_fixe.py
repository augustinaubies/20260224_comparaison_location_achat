from __future__ import annotations

import pandas as pd

from ..configuration import ConfigurationModuleFluxFixe
from ..taux import taux_mensuel_compose
from .base import ContexteSimulation, ModuleSimulation, SortieModule


class ModuleFluxFixe(ModuleSimulation):
    type_module = "flux_fixe"

    def __init__(self, config: ConfigurationModuleFluxFixe) -> None:
        self.config = config
        self.id_module = config.id

    def executer_batch(self, contexte: ContexteSimulation) -> SortieModule:
        debut_effectif = pd.Period(self.config.debut, freq="M") if self.config.debut else contexte.calendrier[0]
        fin_effectif = pd.Period(self.config.fin, freq="M") if self.config.fin else contexte.calendrier[-1]
        periodes = contexte.calendrier[(contexte.calendrier >= debut_effectif) & (contexte.calendrier <= fin_effectif)]
        signe = 1.0 if self.config.sens == "revenu" else -1.0
        flux_de_base = self._calculer_flux_mensuel(periodes, debut_effectif, contexte)
        flux = pd.DataFrame(
            {
                "periode": periodes,
                "id_module": self.id_module,
                "type_module": self.type_module,
                "flux_de_tresorerie": signe * flux_de_base,
                "categorie": self.config.categorie,
                "compte": self.config.compte,
                "description": f"Flux fixe {self.config.categorie}",
            }
        )
        return SortieModule(registre_lignes=flux, etats={})

    def _calculer_flux_mensuel(
        self,
        periodes: pd.PeriodIndex,
        debut_effectif: pd.Period,
        contexte: ContexteSimulation,
    ) -> pd.Series:
        indexation = self.config.indexation
        if indexation == "aucune":
            return pd.Series(self.config.montant, index=periodes, dtype=float)

        cle_hypothese = {
            "inflation": "inflation_annuelle",
            "croissance_salaire": "croissance_salaire_annuelle",
            "indexation_loyer": "indexation_loyers_annuelle",
        }[indexation]

        periode_reference = pd.Period(self.config.periode_reference, freq="M") if self.config.periode_reference else debut_effectif
        montant_courant = float(self.config.montant)
        resultats: list[float] = []
        for i, periode in enumerate(periodes):
            if i > 0:
                if indexation in {"croissance_salaire", "indexation_loyer"}:
                    if periode.month == 1:
                        taux_annuel = contexte.taux_variable(cle_hypothese, periode)
                        montant_courant *= 1 + taux_annuel
                else:
                    taux_annuel = contexte.taux_variable(cle_hypothese, periode)
                    montant_courant *= 1 + taux_mensuel_compose(taux_annuel)
            if periode < periode_reference:
                resultats.append(float(self.config.montant))
            else:
                resultats.append(montant_courant)
        return pd.Series(resultats, index=periodes, dtype=float)
