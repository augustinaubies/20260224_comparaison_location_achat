from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


def taux_mensuel_compose(taux_annuel: float) -> float:
    return (1 + float(taux_annuel)) ** (1 / 12) - 1


def taux_annuel_depuis_source(source: object, periode: pd.Period) -> float:
    if isinstance(source, (int, float)):
        return float(source)
    if not isinstance(source, Mapping):
        return 0.0

    cles = (str(periode), str(periode.year), "defaut", "default")
    for cle in cles:
        if cle in source:
            return float(source[cle])
    if periode.year in source:
        return float(source[periode.year])
    return 0.0


def taux_annuel_pour_periode(taux_variables: Mapping[str, object], cle: str, periode: pd.Period) -> float:
    return taux_annuel_depuis_source(taux_variables.get(cle, 0.0), periode)


@dataclass(frozen=True, slots=True)
class SourceTaux:
    taux_variables: Mapping[str, object]

    def taux_annuel(self, cle: str, periode: pd.Period) -> float:
        return taux_annuel_depuis_source(self.taux_variables.get(cle, 0.0), periode)


def facteur_indexation_annuelle_variable(
    annee_reference: int,
    annee_cible: int,
    source_taux_annuel: object,
) -> float:
    facteur = 1.0
    if annee_cible >= annee_reference:
        for annee in range(annee_reference + 1, annee_cible + 1):
            facteur *= 1 + taux_annuel_depuis_source(source_taux_annuel, pd.Period(f"{annee}-01", freq="M"))
        return facteur

    for annee in range(annee_reference, annee_cible, -1):
        facteur /= 1 + taux_annuel_depuis_source(source_taux_annuel, pd.Period(f"{annee}-01", freq="M"))
    return facteur


def facteur_revalorisation_annuelle(
    periode: pd.Period,
    periode_reference: pd.Period,
    taux_annuel: float,
) -> float:
    """Applique une revalorisation par palier annuel au 1er janvier."""
    ecart_annees = periode.year - periode_reference.year
    return (1 + float(taux_annuel)) ** ecart_annees
