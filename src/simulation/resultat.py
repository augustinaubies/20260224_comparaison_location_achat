from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class ResultatSimulation:
    registre_df: pd.DataFrame
    synthese_df: pd.DataFrame
    metriques: dict[str, float | dict[str, float]]
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]]
