from __future__ import annotations

from pathlib import Path

import pytest

from simulation.configuration import ConfigurationRacine
from simulation.moteur import executer_simulation_depuis_config


def test_rp_financement_inclut_travaux_et_apport_depuis_cash_puis_bourse(tmp_path: Path) -> None:
    config = ConfigurationRacine.model_validate(
        {
            "simulation": {"date_debut": "2025-02", "date_fin": "2025-04"},
            "hypotheses": {"rendement_bourse_annuel": 0.0},
            "portefeuille": {
                "tresorerie_initiale": 5000,
                "bourse_initiale": 10000,
                "comptes": ["cash", "courtier"],
                "taux_investissement_restant": 0.0,
            },
            "modules": [
                {
                    "id": "rp",
                    "type": "residence_principale",
                    "date_achat": "2025-02",
                    "prix": 100000,
                    "taux_frais_notaire": 0.08,
                    "frais_achat": 2000,
                    "taux_travaux": 0.1,
                    "apport": 0,
                    "taux_apport_patrimoine_financier": 0.5,
                    "emprunt": {
                        "capital": 1,
                        "taux_annuel": 0.03,
                        "duree_annees": 20,
                        "taux_assurance_annuel": 0.0,
                    },
                    "taxe_fonciere_annuelle": 0,
                    "compte": "cash",
                }
            ],
        }
    )

    resultat = executer_simulation_depuis_config(config, tmp_path, generer_csv=False)
    registre = resultat.registre_df

    achat = registre[registre["periode"].astype(str) == "2025-02"]
    assert achat[achat["categorie"] == "travaux"]["flux_de_tresorerie"].iloc[0] == -10000
    assert achat[achat["categorie"] == "financement_apport_cash"]["flux_de_tresorerie"].iloc[0] == pytest.approx(5000)
    assert achat[achat["categorie"] == "financement_apport_bourse"]["flux_de_tresorerie"].iloc[0] == pytest.approx(2500)

    # Coût finançable = 120000 ; apport 7500 ; emprunt attendu = 112500
    flux_achat_hors_echeance = achat[achat["categorie"] != "echeance_emprunt"]["flux_de_tresorerie"].sum()
    assert flux_achat_hors_echeance == pytest.approx(-112500)
    assert not achat[achat["categorie"] == "echeance_emprunt"].empty


def test_rapport_contient_bourse_initiale(tmp_path: Path) -> None:
    config = ConfigurationRacine.model_validate(
        {
            "simulation": {"date_debut": "2025-01", "date_fin": "2025-01"},
            "portefeuille": {
                "tresorerie_initiale": 1000,
                "bourse_initiale": 3000,
                "comptes": ["cash", "courtier"],
                "taux_investissement_restant": 0.0,
            },
            "modules": [],
        }
    )

    resultat = executer_simulation_depuis_config(config, tmp_path, generer_csv=False)
    assert resultat.metriques["cash_initial"] == 1000
    assert resultat.metriques["bourse_initiale"] == 3000
    assert resultat.metriques["bourse_finale"] == 3000
