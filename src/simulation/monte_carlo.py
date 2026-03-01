from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .configuration import ConfigurationRacine
from .moteur import executer_simulation_depuis_config


CLES_HYPOTHESES_MONTE_CARLO = (
    "inflation_annuelle",
    "croissance_salaire_annuelle",
    "indexation_loyers_annuelle",
    "revalorisation_immobiliere_annuelle",
    "rendement_bourse_annuel",
)


@dataclass(frozen=True, slots=True)
class DistributionNormale:
    moyenne: float
    ecart_type: float
    borne_min: float | None = None
    borne_max: float | None = None

    def tirer(self, rng: np.random.Generator) -> float:
        valeur = float(rng.normal(self.moyenne, self.ecart_type))
        if self.borne_min is not None:
            valeur = max(self.borne_min, valeur)
        if self.borne_max is not None:
            valeur = min(self.borne_max, valeur)
        return valeur


def construire_distributions_initiales(config: ConfigurationRacine) -> dict[str, DistributionNormale]:
    return {
        cle: DistributionNormale(
            moyenne=distribution.moyenne,
            ecart_type=distribution.ecart_type,
            borne_min=distribution.borne_min,
            borne_max=distribution.borne_max,
        )
        for cle, distribution in config.monte_carlo.distributions.items()
        if cle in CLES_HYPOTHESES_MONTE_CARLO
    }


def executer_simulations_monte_carlo(
    config: ConfigurationRacine,
    dossier_sortie: Path,
    nombre_tirages: int,
    graine: int,
) -> pd.DataFrame:
    if nombre_tirages <= 0:
        raise ValueError("Le nombre de tirages doit etre strictement positif")

    distributions = construire_distributions_initiales(config)
    rng = np.random.default_rng(graine)
    lignes: list[dict[str, float | int]] = []

    for indice in range(1, nombre_tirages + 1):
        config_tirage = config.model_copy(deep=True)
        tirage_hypotheses: dict[str, float] = {}
        for cle, distribution in distributions.items():
            tirage_hypotheses[cle] = distribution.tirer(rng)

        config_tirage.taux_variables = config_tirage.taux_variables.model_copy(update=tirage_hypotheses)

        dossier_tirage = dossier_sortie / "_runs" / f"tirage_{indice:04d}"
        resultat = executer_simulation_depuis_config(config_tirage, dossier_sortie=dossier_tirage)
        lignes.append(
            {
                "tirage": indice,
                **tirage_hypotheses,
                "patrimoine_total_final": float(resultat.metriques.get("patrimoine_total_final", 0.0)),
                "cash_final": float(resultat.metriques.get("cash_final", 0.0)),
                "bourse_finale": float(resultat.metriques.get("bourse_finale", 0.0)),
            }
        )

    resume_df = pd.DataFrame(lignes)
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    resume_df.to_csv(dossier_sortie / "monte_carlo_tirages.csv", index=False)
    resume_df.describe().to_csv(dossier_sortie / "monte_carlo_resume.csv")
    return resume_df
