from __future__ import annotations

import pandas as pd

from ..configuration import ConfigurationModuleResidencePrincipale
from .base import ContexteSimulation, ModuleSimulation, SortieModule
from .emprunt import generer_echeancier


class ModuleResidencePrincipale(ModuleSimulation):
    type_module = "residence_principale"

    def __init__(self, config: ConfigurationModuleResidencePrincipale) -> None:
        self.config = config
        self.id_module = config.id

    def executer(self, contexte: ContexteSimulation) -> SortieModule:
        lignes: list[dict] = []
        periode_achat = pd.Period(self.config.date_achat, freq="M")

        for categorie, montant in [
            ("apport", self.config.apport),
            ("frais_notaire", self.config.frais_notaire),
        ]:
            if montant > 0 and periode_achat in contexte.calendrier:
                lignes.append(
                    {
                        "periode": periode_achat,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -montant,
                        "categorie": categorie,
                        "compte": self.config.compte,
                        "description": f"Décaissement {categorie} achat RP",
                    }
                )

        echeancier = generer_echeancier(
            capital=self.config.emprunt.capital,
            taux_annuel=self.config.emprunt.taux_annuel,
            duree_mois=self.config.emprunt.duree_mois,
            date_debut=self.config.date_achat,
            calendrier_global=contexte.calendrier,
        )
        for _, ligne in echeancier.iterrows():
            lignes.append(
                {
                    "periode": ligne["periode"],
                    "id_module": self.id_module,
                    "type_module": self.type_module,
                    "flux_de_tresorerie": -float(ligne["echeance_hors_assurance"]),
                    "categorie": "echeance_emprunt",
                    "compte": self.config.compte,
                    "description": "Mensualité emprunt RP",
                }
            )
            if self.config.emprunt.assurance_mensuelle > 0:
                lignes.append(
                    {
                        "periode": ligne["periode"],
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -self.config.emprunt.assurance_mensuelle,
                        "categorie": "assurance_emprunt",
                        "compte": self.config.compte,
                        "description": "Assurance emprunt RP",
                    }
                )

        for periode in contexte.calendrier:
            if periode >= periode_achat and self.config.taxe_fonciere_annuelle > 0:
                lignes.append(
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -(self.config.taxe_fonciere_annuelle / 12),
                        "categorie": "taxe_fonciere",
                        "compte": self.config.compte,
                        "description": "Taxe foncière RP mensualisée",
                    }
                )

        index_emprunt = pd.PeriodIndex(echeancier["periode"], freq="M") if not echeancier.empty else pd.PeriodIndex([], freq="M")
        possede = pd.Series([periode >= periode_achat for periode in contexte.calendrier], index=contexte.calendrier, name="possede_residence_principale")
        etats = {
            "capital_restant_du": pd.Series(echeancier["capital_restant_du"].to_numpy(), index=index_emprunt, name="capital_restant_du"),
            "interets_payes": pd.Series(echeancier["interets_payes"].to_numpy(), index=index_emprunt, name="interets_payes"),
            "capital_rembourse": pd.Series(echeancier["capital_rembourse"].to_numpy(), index=index_emprunt, name="capital_rembourse"),
            "possede_residence_principale": possede,
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
