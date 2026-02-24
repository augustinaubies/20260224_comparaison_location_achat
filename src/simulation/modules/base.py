from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class ContexteSimulation:
    calendrier: pd.PeriodIndex
    hypotheses: dict[str, float]
    comptes: list[str]


@dataclass(slots=True)
class SortieModule:
    registre_lignes: pd.DataFrame
    etats: dict[str, pd.Series | pd.DataFrame]


class ModuleSimulation(ABC):
    id_module: str
    type_module: str

    @abstractmethod
    def executer(self, contexte: ContexteSimulation) -> SortieModule:
        raise NotImplementedError
