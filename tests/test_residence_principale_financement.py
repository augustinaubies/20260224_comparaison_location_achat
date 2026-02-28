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
                "comptes_definitions": [{"id": "cash", "type": "cash"}, {"id": "courtier", "type": "cto"}],
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
    categories_achat = {"prix_achat", "frais_notaire", "frais_achat", "travaux", "financement_apport_cash", "financement_apport_bourse"}
    flux_achat_hors_echeance = achat[achat["categorie"].isin(categories_achat)]["flux_de_tresorerie"].sum()
    assert flux_achat_hors_echeance == pytest.approx(-112500)
    assert not achat[achat["categorie"] == "echeance_emprunt"].empty


def test_rapport_contient_bourse_initiale(tmp_path: Path) -> None:
    config = ConfigurationRacine.model_validate(
        {
            "simulation": {"date_debut": "2025-01", "date_fin": "2025-01"},
            "portefeuille": {
                "tresorerie_initiale": 1000,
                "bourse_initiale": 3000,
                "comptes_definitions": [{"id": "cash", "type": "cash"}, {"id": "courtier", "type": "cto"}],
                "taux_investissement_restant": 0.0,
            },
            "modules": [],
        }
    )

    resultat = executer_simulation_depuis_config(config, tmp_path, generer_csv=False)
    assert resultat.metriques["cash_initial"] == 1000
    assert resultat.metriques["bourse_initiale"] == 3000
    assert resultat.metriques["bourse_finale"] == 3000


def test_loyer_residence_principale_revalorise_au_premier_janvier(tmp_path: Path) -> None:
    config = ConfigurationRacine.model_validate(
        {
            "simulation": {"date_debut": "2025-10", "date_fin": "2026-02"},
            "hypotheses": {"indexation_loyers_annuelle": 0.12},
            "portefeuille": {
                "tresorerie_initiale": 10000,
                "comptes_definitions": [{"id": "cash", "type": "cash"}, {"id": "courtier", "type": "cto"}],
                "taux_investissement_restant": 0.0,
                "loyer_residence_principale": 1000,
            },
            "modules": [],
        }
    )

    resultat = executer_simulation_depuis_config(config, tmp_path, generer_csv=False)
    loyers = (
        resultat.registre_df[resultat.registre_df["categorie"] == "loyer_residence_principale"]["flux_de_tresorerie"].tolist()
    )

    assert loyers[:3] == pytest.approx([-1000.0, -1000.0, -1000.0])
    assert loyers[3:] == pytest.approx([-1120.0, -1120.0])


def test_reste_a_vivre_limite_investissement_automatique(tmp_path: Path) -> None:
    config = ConfigurationRacine.model_validate(
        {
            "simulation": {"date_debut": "2025-01", "date_fin": "2025-01"},
            "hypotheses": {"rendement_bourse_annuel": 0.0},
            "portefeuille": {
                "tresorerie_initiale": 0.0,
                "comptes_definitions": [{"id": "cash", "type": "cash"}, {"id": "courtier", "type": "cto"}],
                "taux_investissement_restant": 1.0,
                "reste_a_vivre_minimum": 1000.0,
                "indexer_reste_a_vivre_sur_inflation": False,
            },
            "modules": [
                {
                    "id": "salaire",
                    "type": "flux_fixe",
                    "montant": 3000.0,
                    "sens": "revenu",
                    "categorie": "salaire",
                },
                {
                    "id": "depenses",
                    "type": "flux_fixe",
                    "montant": 1500.0,
                    "sens": "depense",
                    "categorie": "depenses_courantes",
                },
            ],
        }
    )

    resultat = executer_simulation_depuis_config(config, tmp_path, generer_csv=False)
    versements = resultat.registre_df[resultat.registre_df["categorie"] == "versement_restant"]["flux_de_tresorerie"].tolist()

    assert versements == pytest.approx([-500.0])
    assert resultat.synthese_df.iloc[-1]["tresorerie_fin"] == pytest.approx(1000.0)


def test_rp_utilise_pret_pel_si_disponible(tmp_path: Path) -> None:
    config = ConfigurationRacine.model_validate(
        {
            "simulation": {"date_debut": "2025-01", "date_fin": "2025-03"},
            "hypotheses": {"rendement_bourse_annuel": 0.0},
            "portefeuille": {
                "tresorerie_initiale": 0,
                "bourse_initiale": 50000,
                "comptes_definitions": [
                    {"id": "cash", "type": "cash"},
                    {"id": "pel", "type": "pel", "taux_pret_immobilier_annuel": 0.01},
                ],
                "priorites_allocation_investissement": ["pel"],
                "taux_investissement_restant": 0.0,
            },
            "modules": [
                {
                    "id": "rp",
                    "type": "residence_principale",
                    "date_achat": "2025-01",
                    "prix": 100000,
                    "taux_frais_notaire": 0.0,
                    "frais_achat": 0.0,
                    "taux_travaux": 0.0,
                    "apport": 0,
                    "taux_apport_patrimoine_financier": 0.0,
                    "emprunt": {
                        "taux_annuel": 0.05,
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

    lignes_pel = registre[(registre["periode"].astype(str) == "2025-01") & (registre["categorie"] == "financement_pret_pel")]
    assert len(lignes_pel) == 1
    assert float(lignes_pel.iloc[0]["flux_de_tresorerie"]) == pytest.approx(50000.0)

    echeances = registre[registre["categorie"] == "echeance_emprunt"]
    assert not echeances.empty
    assert float(echeances.iloc[0]["flux_de_tresorerie"]) > -660.0
