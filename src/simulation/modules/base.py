from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..etat import EtatSimulation
from ..registre import COLONNES_REGISTRE
from ..taux import SourceTaux


@dataclass(slots=True)
class ContexteSimulation:
    calendrier: pd.PeriodIndex
    hypotheses: dict[str, object]
    comptes: list[str]
    source_taux: SourceTaux | None = None

    def taux_variable(self, cle: str, periode: pd.Period) -> float:
        if self.source_taux is not None:
            return self.source_taux.taux_annuel(cle, periode)
        return SourceTaux(self.hypotheses).taux_annuel(cle, periode)


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
                valeur = serie.get(periode, 0.0)
                if pd.api.types.is_bool_dtype(serie.dtype):
                    etats_incrementaux[nom] = bool(valeur)
                else:
                    etats_incrementaux[nom] = float(valeur)
        return SortieMensuelle(lignes_registre=lignes, etats_incrementaux=etats_incrementaux)

    def executer_batch(self, contexte: ContexteSimulation) -> SortieModule:
        raise NotImplementedError
