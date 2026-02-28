from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class EtatSimulation:
    """État global mutable de la simulation (source de vérité comptable)."""

    periode_courante: pd.Period
    cash: float
    bourse: float = 0.0
    dettes: dict[str, float] = field(default_factory=dict)
    possessions: dict[str, bool] = field(default_factory=dict)
    revenu_imposable_annee_en_cours: float = 0.0
    loyers_imposables_annee_en_cours: float = 0.0
    bases_annuelles_impot: dict[int, dict[str, float]] = field(default_factory=dict)
    etats_modules: dict[str, dict[str, Any]] = field(default_factory=dict)
    comptes_investissement: dict[str, float] = field(default_factory=dict)
    comptes_definitions: dict[str, Any] = field(default_factory=dict)


def appliquer_flux_cash(etat: EtatSimulation, montant: float) -> None:
    etat.cash += float(montant)


def appliquer_versement_bourse(etat: EtatSimulation, versement: float) -> float:
    montant = max(0.0, min(float(versement), etat.cash))
    etat.cash -= montant
    etat.bourse += montant
    return montant


def appliquer_rendement_bourse(etat: EtatSimulation, taux_mensuel: float) -> None:
    etat.bourse *= 1 + float(taux_mensuel)


def accumuler_base_imposable(etat: EtatSimulation, categorie: str, flux: float) -> None:
    if flux <= 0:
        return
    if categorie == "salaire":
        etat.revenu_imposable_annee_en_cours += float(flux)
    if categorie == "loyer":
        etat.loyers_imposables_annee_en_cours += float(flux)


def cloturer_annee_fiscale_si_necessaire(etat: EtatSimulation, periode_suivante: pd.Period | None) -> None:
    if periode_suivante is not None and periode_suivante.year == etat.periode_courante.year:
        return
    etat.bases_annuelles_impot[etat.periode_courante.year] = {
        "revenu_imposable": etat.revenu_imposable_annee_en_cours,
        "loyers_imposables": etat.loyers_imposables_annee_en_cours,
    }
    etat.revenu_imposable_annee_en_cours = 0.0
    etat.loyers_imposables_annee_en_cours = 0.0
