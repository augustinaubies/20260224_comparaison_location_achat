from __future__ import annotations

import pandas as pd


def taux_mensuel_compose(taux_annuel: float) -> float:
    return (1 + float(taux_annuel)) ** (1 / 12) - 1


def facteur_revalorisation_annuelle(
    periode: pd.Period,
    periode_reference: pd.Period,
    taux_annuel: float,
) -> float:
    """Applique une revalorisation par palier annuel au 1er janvier."""
    ecart_annees = periode.year - periode_reference.year
    return (1 + float(taux_annuel)) ** ecart_annees
