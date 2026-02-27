from __future__ import annotations

import pandas as pd

from ..configuration import ConfigurationModuleResidencePrincipale
from ..etat import EtatSimulation
from ..taux import taux_annuel_pour_periode, taux_mensuel_compose
from .base import ContexteSimulation, ModuleSimulation, SortieMensuelle, SortieModule
from .emprunt import generer_echeancier


class ModuleResidencePrincipale(ModuleSimulation):
    type_module = "residence_principale"

    def __init__(self, config: ConfigurationModuleResidencePrincipale) -> None:
        self.config = config
        self.id_module = config.id
        self._echeancier: pd.DataFrame | None = None
        self._capital_emprunte: float = 0.0

    def _cout_total_financable(self) -> float:
        frais_notaire = self.config.prix * self.config.taux_frais_notaire
        travaux = self.config.prix * self.config.taux_travaux
        return self.config.prix + frais_notaire + self.config.frais_achat + travaux

    def _preparer_financement(self, etat: EtatSimulation, contexte: ContexteSimulation) -> tuple[list[dict], float]:
        lignes: list[dict] = []
        periode_achat = pd.Period(self.config.date_achat, freq="M")
        if periode_achat not in contexte.calendrier:
            return lignes, 0.0

        cout_total = self._cout_total_financable()
        patrimoine_financier = max(etat.cash, 0.0) + max(etat.bourse, 0.0)
        apport_cible = self.config.apport
        if self.config.taux_apport_patrimoine_financier > 0:
            apport_cible = patrimoine_financier * self.config.taux_apport_patrimoine_financier
        apport_effectif = min(cout_total, max(apport_cible, 0.0))

        apport_cash = min(max(etat.cash, 0.0), apport_effectif)
        apport_bourse = min(max(etat.bourse, 0.0), max(apport_effectif - apport_cash, 0.0))
        apport_effectif = apport_cash + apport_bourse
        self._capital_emprunte = max(cout_total - apport_effectif, 0.0)

        frais_notaire = self.config.prix * self.config.taux_frais_notaire
        travaux = self.config.prix * self.config.taux_travaux
        for categorie, montant in [
            ("prix_achat", self.config.prix),
            ("frais_notaire", frais_notaire),
            ("frais_achat", self.config.frais_achat),
            ("travaux", travaux),
        ]:
            if montant > 0:
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

        if apport_cash > 0:
            lignes.append(
                {
                    "periode": periode_achat,
                    "id_module": self.id_module,
                    "type_module": self.type_module,
                    "flux_de_tresorerie": apport_cash,
                    "categorie": "financement_apport_cash",
                    "compte": self.config.compte,
                    "description": "Financement achat RP par apport cash",
                }
            )
        if apport_bourse > 0:
            lignes.append(
                {
                    "periode": periode_achat,
                    "id_module": self.id_module,
                    "type_module": self.type_module,
                    "flux_de_tresorerie": apport_bourse,
                    "categorie": "financement_apport_bourse",
                    "compte": self.config.compte,
                    "description": "Financement achat RP par désinvestissement bourse",
                }
            )
        if apport_bourse > 0:
            etat.bourse = max(etat.bourse - apport_bourse, 0.0)

        return lignes, apport_effectif

    def generer_flux_mensuel(self, periode: pd.Period, etat: EtatSimulation, contexte: ContexteSimulation) -> SortieMensuelle:
        periode_achat = pd.Period(self.config.date_achat, freq="M")
        lignes: list[dict] = []
        etats_incrementaux: dict[str, float | bool] = {
            "possede_residence_principale": periode >= periode_achat,
            "valeur_bien": 0.0,
            "capital_restant_du": 0.0,
            "interets_payes": 0.0,
            "capital_rembourse": 0.0,
        }

        if periode >= periode_achat:
            valeur_bien = float(self.config.prix)
            periode_courante = periode_achat
            while periode_courante < periode:
                periode_courante += 1
                taux_revalo = taux_annuel_pour_periode(contexte.hypotheses, "revalorisation_immobiliere_annuelle", periode_courante)
                valeur_bien *= 1 + taux_mensuel_compose(taux_revalo)
            etats_incrementaux["valeur_bien"] = valeur_bien

        if periode == periode_achat and self._echeancier is None:
            lignes_achat, _ = self._preparer_financement(etat, contexte)
            lignes.extend(lignes_achat)
            if self._capital_emprunte > 0:
                self._echeancier = generer_echeancier(
                    capital=self._capital_emprunte,
                    taux_annuel=self.config.emprunt.taux_annuel,
                    duree_mois=self.config.emprunt.duree_annees * 12,
                    date_debut=self.config.date_achat,
                    calendrier_global=contexte.calendrier,
                )
            else:
                self._echeancier = pd.DataFrame()

        if self._echeancier is not None and not self._echeancier.empty:
            lignes_periode = self._echeancier[self._echeancier["periode"] == periode]
            if not lignes_periode.empty:
                ligne = lignes_periode.iloc[0]
                lignes.append(
                    {
                        "periode": periode,
                        "id_module": self.id_module,
                        "type_module": self.type_module,
                        "flux_de_tresorerie": -float(ligne["echeance_hors_assurance"]),
                        "categorie": "echeance_emprunt",
                        "compte": self.config.compte,
                        "description": "Mensualité emprunt RP",
                    }
                )
                assurance_mensuelle = self._capital_emprunte * self.config.emprunt.taux_assurance_annuel / 12
                if assurance_mensuelle > 0:
                    lignes.append(
                        {
                            "periode": periode,
                            "id_module": self.id_module,
                            "type_module": self.type_module,
                            "flux_de_tresorerie": -assurance_mensuelle,
                            "categorie": "assurance_emprunt",
                            "compte": self.config.compte,
                            "description": "Assurance emprunt RP",
                        }
                    )
                etats_incrementaux["capital_restant_du"] = float(ligne["capital_restant_du"])
                etats_incrementaux["interets_payes"] = float(ligne["interets_payes"])
                etats_incrementaux["capital_rembourse"] = float(ligne["capital_rembourse"])

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
        return SortieMensuelle(lignes_registre=lignes, etats_incrementaux=etats_incrementaux)

    def executer_batch(self, contexte: ContexteSimulation) -> SortieModule:
        lignes: list[dict] = []
        periode_achat = pd.Period(self.config.date_achat, freq="M")
        frais_notaire = self.config.prix * self.config.taux_frais_notaire

        for categorie, montant in [("apport", self.config.apport), ("frais_notaire", frais_notaire)]:
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

        cout_total = self._cout_total_financable()
        capital_emprunte = max(cout_total - self.config.apport, 0.0)
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
                    "description": "Mensualité emprunt RP",
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
        valeur_bien = pd.Series(index=contexte.calendrier, dtype=float, name="valeur_bien")
        valeur_courante = float(self.config.prix)
        for idx, periode in enumerate(contexte.calendrier):
            if idx > 0:
                taux_revalo = taux_annuel_pour_periode(contexte.hypotheses, "revalorisation_immobiliere_annuelle", periode)
                valeur_courante *= 1 + taux_mensuel_compose(taux_revalo)
            valeur_bien.loc[periode] = 0.0 if periode < periode_achat else valeur_courante
        etats = {
            "capital_restant_du": pd.Series(echeancier["capital_restant_du"].to_numpy(), index=index_emprunt, name="capital_restant_du"),
            "interets_payes": pd.Series(echeancier["interets_payes"].to_numpy(), index=index_emprunt, name="interets_payes"),
            "capital_rembourse": pd.Series(echeancier["capital_rembourse"].to_numpy(), index=index_emprunt, name="capital_rembourse"),
            "possede_residence_principale": possede,
            "valeur_bien": valeur_bien,
        }
        return SortieModule(registre_lignes=pd.DataFrame(lignes), etats=etats)
