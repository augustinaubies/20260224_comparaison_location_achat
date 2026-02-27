from __future__ import annotations

import pandas as pd

from ..configuration import ConfigurationModuleImmobilierLocatif
from ..taux import taux_annuel_pour_periode, taux_mensuel_compose
from .base import ContexteSimulation, ModuleSimulation, SortieModule
from .emprunt import generer_echeancier


class ModuleImmobilierLocatif(ModuleSimulation):
    type_module = "immobilier_locatif"

    def __init__(self, config: ConfigurationModuleImmobilierLocatif) -> None:
        self.config = config
        self.id_module = config.id

    def _capital_emprunte(self) -> float:
        frais_notaire = self.config.prix * self.config.taux_frais_notaire
        budget_travaux = self.config.prix * self.config.taux_travaux
        cout_total = self.config.prix + frais_notaire + budget_travaux
        return max(cout_total - self.config.apport, 0.0)

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

        valeur_bien_courante = float(self.config.prix)
        loyer_base_courant = float(self.config.loyer_mensuel_initial)
        derniere_periode_calculee = periodes_location[0] if len(periodes_location) > 0 else None

        for idx, periode in enumerate(periodes_location):
            if idx > 0 and derniere_periode_calculee is not None:
                taux_revalo = taux_annuel_pour_periode(contexte.hypotheses, "revalorisation_immobiliere_annuelle", periode)
                valeur_bien_courante *= 1 + taux_mensuel_compose(taux_revalo)
                if periode.month == 1:
                    taux_loyer = taux_annuel_pour_periode(contexte.hypotheses, "indexation_loyers_annuelle", periode)
                    loyer_base_courant *= 1 + taux_loyer
            valeur_bien = valeur_bien_courante if periode >= periode_achat else 0.0
            loyer_base = loyer_base_courant
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

        capital_emprunte = self._capital_emprunte()
        echeancier = generer_echeancier(
            capital=capital_emprunte,
            taux_annuel=self.config.emprunt.taux_annuel,
            duree_mois=self.config.emprunt.duree_annees * 12,
            date_debut=self.config.date_achat,
            calendrier_global=contexte.calendrier,
        )
        assurance_mensuelle = capital_emprunte * self.config.emprunt.taux_assurance_annuel / 12
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
            valeur_courante = float(self.config.prix)
            for idx, periode in enumerate(contexte.calendrier):
                if idx > 0:
                    taux_revalo = taux_annuel_pour_periode(contexte.hypotheses, "revalorisation_immobiliere_annuelle", periode)
                    valeur_courante *= 1 + taux_mensuel_compose(taux_revalo)
                valeur_bien.loc[periode] = 0.0 if periode < periode_achat else valeur_courante

        etats = {
            "valeur_bien": valeur_bien,
            "capital_restant_du": pd.Series(echeancier["capital_restant_du"].to_numpy(), index=index_emprunt, name="capital_restant_du"),
            "interets_payes": pd.Series(echeancier["interets_payes"].to_numpy(), index=index_emprunt, name="interets_payes"),
            "revenu_net_exploitation": pd.Series(noi_liste, index=periodes_location, name="revenu_net_exploitation"),
            "loyers_bruts": pd.Series(loyers_bruts, index=periodes_location, name="loyers_bruts"),
            "charges_totales": pd.Series(charges_totales, index=periodes_location, name="charges_totales"),
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
