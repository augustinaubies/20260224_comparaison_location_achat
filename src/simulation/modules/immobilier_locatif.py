from __future__ import annotations

import pandas as pd

from simulation.configuration import ConfigurationModuleImmobilierLocatif
from simulation.modules.base import ContexteSimulation, ModuleSimulation, SortieModule
from simulation.modules.emprunt import generer_echeancier


class ModuleImmobilierLocatif(ModuleSimulation):
    type_module = "immobilier_locatif"

    def __init__(self, config: ConfigurationModuleImmobilierLocatif) -> None:
        self.config = config
        self.id_module = config.id

    def executer(self, contexte: ContexteSimulation) -> SortieModule:
        lignes: list[dict] = []

        periode_achat = pd.Period(self.config.date_achat, freq="M")
        for categorie, montant in [
            ("apport", self.config.apport),
            ("frais_notaire", self.config.frais_notaire),
            ("travaux", self.config.budget_travaux),
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
                        "description": f"Décaissement {categorie} achat",
                    }
                )

        debut_location = pd.Period(self.config.date_debut_location, freq="M")
        periodes_location = contexte.calendrier[contexte.calendrier >= debut_location]
        loyers_bruts: list[float] = []
        charges_totales: list[float] = []
        noi_liste: list[float] = []

        for periode in periodes_location:
            loyer = self.config.loyer_mensuel * (1 - self.config.taux_vacance)
            entretien = self.config.loyer_mensuel * self.config.taux_entretien
            gestion = self.config.loyer_mensuel * self.config.taux_gestion
            taxe = self.config.taxe_fonciere_annuelle / 12
            charges = self.config.charges_mensuelles + taxe + entretien + gestion
            noi = loyer - charges
            loyers_bruts.append(loyer)
            charges_totales.append(charges)
            noi_liste.append(noi)

            lignes.extend(
                [
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": loyer,
                        "categorie": "loyer",
                        "compte": self.config.compte,
                        "description": "Loyer mensuel net de vacance",
                    },
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -self.config.charges_mensuelles,
                        "categorie": "charges",
                        "compte": self.config.compte,
                        "description": "Charges mensuelles",
                    },
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -taxe,
                        "categorie": "taxe_fonciere",
                        "compte": self.config.compte,
                        "description": "Taxe foncière mensualisée",
                    },
                ]
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
                    "description": "Mensualité emprunt locatif",
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
                        "description": "Assurance emprunt locatif",
                    }
                )

        index_emprunt = (
            pd.PeriodIndex(echeancier["periode"], freq="M") if not echeancier.empty else pd.PeriodIndex([], freq="M")
        )
        etats = {
            "valeur_bien": pd.Series(
                [self.config.prix] * len(contexte.calendrier), index=contexte.calendrier, name="valeur_bien"
            ),
            "capital_restant_du": pd.Series(
                echeancier["capital_restant_du"].to_numpy(), index=index_emprunt, name="capital_restant_du"
            ),
            "interets_payes": pd.Series(
                echeancier["interets_payes"].to_numpy(), index=index_emprunt, name="interets_payes"
            ),
            "revenu_net_exploitation": pd.Series(
                noi_liste, index=periodes_location, name="revenu_net_exploitation"
            ),
            "loyers_bruts": pd.Series(loyers_bruts, index=periodes_location, name="loyers_bruts"),
            "charges_totales": pd.Series(charges_totales, index=periodes_location, name="charges_totales"),
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
