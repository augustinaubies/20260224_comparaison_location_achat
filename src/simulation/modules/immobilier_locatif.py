from __future__ import annotations

import pandas as pd

from ..configuration import ConfigurationModuleImmobilierLocatif
from ..taux import taux_mensuel_compose
from .base import ContexteSimulation, ModuleSimulation, SortieModule
from .emprunt import generer_echeancier


class ModuleImmobilierLocatif(ModuleSimulation):
    type_module = "immobilier_locatif"

    def __init__(self, config: ConfigurationModuleImmobilierLocatif) -> None:
        self.config = config
        self.id_module = config.id

    def executer_batch(self, contexte: ContexteSimulation) -> SortieModule:
        lignes: list[dict] = []

        periode_achat = pd.Period(self.config.date_achat, freq="M")
        frais_notaire = self.config.prix * self.config.taux_frais_notaire
        budget_travaux = self.config.prix * self.config.taux_travaux
        for categorie, montant in [
            ("apport", self.config.apport),
            ("frais_notaire", frais_notaire),
            ("travaux", budget_travaux),
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
        valeurs_bien: list[float] = []

        taux_mensuel_loyer = taux_mensuel_compose(float(contexte.hypotheses.get("indexation_loyers_annuelle", 0.0)))
        taux_mensuel_revalo = taux_mensuel_compose(float(contexte.hypotheses.get("revalorisation_immobiliere_annuelle", 0.0)))

        for periode in periodes_location:
            mois_depuis_achat = max(0, periode.ordinal - periode_achat.ordinal)
            valeur_bien = self.config.prix * ((1 + taux_mensuel_revalo) ** mois_depuis_achat)
            mois_depuis_debut_loc = max(0, periode.ordinal - debut_location.ordinal)
            loyer_base = self.config.loyer_mensuel_initial * ((1 + taux_mensuel_loyer) ** mois_depuis_debut_loc)
            loyer = loyer_base * (1 - self.config.taux_vacance)
            entretien = valeur_bien * (self.config.taux_entretien_annuel / 12)
            gestion = loyer * self.config.taux_gestion_locative
            taxe = self.config.taxe_fonciere_annuelle / 12
            charges = self.config.charges_mensuelles + taxe + entretien + gestion
            noi = loyer - charges
            loyers_bruts.append(loyer)
            charges_totales.append(charges)
            noi_liste.append(noi)
            valeurs_bien.append(valeur_bien)

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
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -entretien,
                        "categorie": "entretien",
                        "compte": self.config.compte,
                        "description": "Entretien mensualisé (% valeur bien)",
                    },
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -gestion,
                        "categorie": "gestion_locative",
                        "compte": self.config.compte,
                        "description": "Gestion locative (% loyers)",
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
        assurance_mensuelle = self.config.emprunt.capital * self.config.emprunt.taux_assurance_annuel / 12
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
            if assurance_mensuelle > 0:
                lignes.append(
                    {
                        "periode": ligne["periode"],
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -assurance_mensuelle,
                        "categorie": "assurance_emprunt",
                        "compte": self.config.compte,
                        "description": "Assurance emprunt locatif",
                    }
                )

        index_emprunt = pd.PeriodIndex(echeancier["periode"], freq="M") if not echeancier.empty else pd.PeriodIndex([], freq="M")
        valeur_bien = pd.Series(index=contexte.calendrier, dtype=float, name="valeur_bien")
        if len(contexte.calendrier) > 0:
            for periode in contexte.calendrier:
                if periode < periode_achat:
                    valeur_bien.loc[periode] = 0.0
                else:
                    mois_depuis_achat = periode.ordinal - periode_achat.ordinal
                    valeur_bien.loc[periode] = self.config.prix * ((1 + taux_mensuel_revalo) ** mois_depuis_achat)

        etats = {
            "valeur_bien": valeur_bien,
            "capital_restant_du": pd.Series(echeancier["capital_restant_du"].to_numpy(), index=index_emprunt, name="capital_restant_du"),
            "interets_payes": pd.Series(echeancier["interets_payes"].to_numpy(), index=index_emprunt, name="interets_payes"),
            "revenu_net_exploitation": pd.Series(noi_liste, index=periodes_location, name="revenu_net_exploitation"),
            "loyers_bruts": pd.Series(loyers_bruts, index=periodes_location, name="loyers_bruts"),
            "charges_totales": pd.Series(charges_totales, index=periodes_location, name="charges_totales"),
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
