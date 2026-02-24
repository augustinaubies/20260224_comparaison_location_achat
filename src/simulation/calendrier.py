from __future__ import annotations

import pandas as pd



def construire_calendrier_mensuel(date_debut: str, date_fin: str) -> pd.PeriodIndex:
    """Construit un calendrier mensuel fermé entre deux dates incluses."""
    debut = pd.Period(date_debut, freq="M")
    fin = pd.Period(date_fin, freq="M")
    if fin < debut:
        raise ValueError("date_fin doit être postérieure ou égale à date_debut")
    return pd.period_range(start=debut, end=fin, freq="M")
