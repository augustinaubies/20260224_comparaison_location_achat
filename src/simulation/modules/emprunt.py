from __future__ import annotations

import pandas as pd

from simulation.configuration import ConfigurationModuleEmprunt
from simulation.modules.base import ContexteSimulation, ModuleSimulation, SortieModule



def generer_echeancier(
    capital: float,
    taux_annuel: float,
    duree_mois: int,
    date_debut: str,
    calendrier_global: pd.PeriodIndex,
) -> pd.DataFrame:
    debut = pd.Period(date_debut, freq="M")
    periodes_completes = pd.period_range(debut, periods=duree_mois, freq="M")
    periodes = periodes_completes[periodes_completes.isin(calendrier_global)]

    taux_mensuel = taux_annuel / 12
    if taux_mensuel == 0:
        echeance = capital / duree_mois
    else:
        echeance = capital * (taux_mensuel / (1 - (1 + taux_mensuel) ** (-duree_mois)))

    capital_restant = capital
    lignes = []
    for idx, periode in enumerate(periodes_completes, start=1):
        crd_debut = capital_restant
        interets = capital_restant * taux_mensuel
        amortissement = min(echeance - interets, capital_restant)
        if idx == len(periodes_completes):
            amortissement = capital_restant
        capital_restant = max(capital_restant - amortissement, 0.0)
        if periode in periodes:
            lignes.append(
                {
                    "periode": periode,
                    "crd_debut": crd_debut,
                    "interets_payes": interets,
                    "capital_rembourse": amortissement,
                    "capital_restant_du": capital_restant,
                    "echeance_hors_assurance": interets + amortissement,
                    "taux_mensuel": taux_mensuel,
                }
            )
    return pd.DataFrame(lignes)


class ModuleEmprunt(ModuleSimulation):
    type_module = "emprunt"

    def __init__(self, config: ConfigurationModuleEmprunt) -> None:
        self.config = config
        self.id_module = config.id

    def executer(self, contexte: ContexteSimulation) -> SortieModule:
        echeancier = generer_echeancier(
            capital=self.config.capital,
            taux_annuel=self.config.taux_annuel,
            duree_mois=self.config.duree_mois,
            date_debut=self.config.date_debut,
            calendrier_global=contexte.calendrier,
        )

        lignes: list[dict] = []
        for _, ligne in echeancier.iterrows():
            lignes.append(
                {
                    "periode": ligne["periode"],
                    "id_module": self.id_module,
                    "type_module": self.type_module,
                    "flux_de_tresorerie": -float(ligne["echeance_hors_assurance"]),
                    "categorie": "echeance_emprunt",
                    "compte": self.config.compte,
                    "description": "Mensualité emprunt",
                }
            )
            if self.config.assurance_mensuelle > 0:
                lignes.append(
                    {
                        "periode": ligne["periode"],
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -self.config.assurance_mensuelle,
                        "categorie": "assurance_emprunt",
                        "compte": self.config.compte,
                        "description": "Assurance emprunt",
                    }
                )

        index = pd.PeriodIndex(echeancier["periode"], freq="M") if not echeancier.empty else pd.PeriodIndex([], freq="M")
        etats = {
            "interets_payes": pd.Series(echeancier["interets_payes"].to_numpy(), index=index, name="interets_payes"),
            "capital_rembourse": pd.Series(echeancier["capital_rembourse"].to_numpy(), index=index, name="capital_rembourse"),
            "capital_restant_du": pd.Series(echeancier["capital_restant_du"].to_numpy(), index=index, name="capital_restant_du"),
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
