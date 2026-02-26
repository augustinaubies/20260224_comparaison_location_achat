from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..etat import EtatSimulation
from ..registre import COLONNES_REGISTRE


@dataclass(slots=True)
class ContexteSimulation:
    calendrier: pd.PeriodIndex
    hypotheses: dict[str, float]
    comptes: list[str]


@dataclass(slots=True)
class SortieModule:
    registre_lignes: pd.DataFrame
    etats: dict[str, pd.Series | pd.DataFrame]


@dataclass(slots=True)
class SortieMensuelle:
    lignes_registre: list[dict] = field(default_factory=list)
    etats_incrementaux: dict[str, Any] = field(default_factory=dict)


class ModuleSimulation(ABC):
    id_module: str
    type_module: str

    def executer(self, contexte: ContexteSimulation) -> SortieModule:
        """Compatibilité legacy: conserve l'API batch existante."""
        return self.executer_batch(contexte)

    def generer_flux_mensuel(
        self,
        periode: pd.Period,
        etat: EtatSimulation,
        contexte: ContexteSimulation,
    ) -> SortieMensuelle:
        """Interface mensuelle (par défaut: adaptateur batch stateless)."""
        if not hasattr(self, "_batch_cache"):
            self._batch_cache = self.executer_batch(contexte)
        sortie_batch: SortieModule = self._batch_cache
        if sortie_batch.registre_lignes.empty:
            lignes: list[dict] = []
        else:
            mask = sortie_batch.registre_lignes["periode"] == periode
            lignes = sortie_batch.registre_lignes[mask].to_dict("records")

        etats_incrementaux: dict[str, Any] = {}
        for nom, serie in sortie_batch.etats.items():
            if isinstance(serie, pd.Series):
                etats_incrementaux[nom] = float(serie.get(periode, 0.0))
        return SortieMensuelle(lignes_registre=lignes, etats_incrementaux=etats_incrementaux)

    def executer_batch(self, contexte: ContexteSimulation) -> SortieModule:
        raise NotImplementedError
