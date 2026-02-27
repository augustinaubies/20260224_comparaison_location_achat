from __future__ import annotations

import pandas as pd

from simulation.configuration import ConfigurationEmpruntIntegree, ConfigurationModuleImmobilierLocatif
from simulation.modules.base import ContexteSimulation
from simulation.modules.immobilier_locatif import ModuleImmobilierLocatif


def test_locatif_registre_et_colonnes() -> None:
    config = ConfigurationModuleImmobilierLocatif(
        id="loc_test",
        type="immobilier_locatif",
        date_achat="2025-01",
        prix=100000,
        taux_frais_notaire=0.08,
        taux_travaux=0.02,
        apport=20000,
        emprunt=ConfigurationEmpruntIntegree(
            capital=80000,
            taux_annuel=0.02,
            duree_annees=10,
            taux_assurance_annuel=10,
        ),
        loyer_mensuel_initial=700,
        date_debut_location="2025-02",
        taux_vacance=0.05,
        charges_mensuelles=80,
        taxe_fonciere_annuelle=900,
        taux_entretien_annuel=0.02,
        taux_gestion_locative=0.03,
        compte="cash",
    )
    contexte = ContexteSimulation(
        calendrier=pd.period_range("2025-01", "2026-12", freq="M"), hypotheses={}, comptes=["cash"]
    )

    sortie = ModuleImmobilierLocatif(config).executer(contexte)

    assert not sortie.registre_lignes.empty
    colonnes_attendues = {
        "periode",
        "id_module",
        "type_module",
        "flux_de_tresorerie",
        "categorie",
        "compte",
        "description",
    }
    assert colonnes_attendues.issubset(set(sortie.registre_lignes.columns))
