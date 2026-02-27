from __future__ import annotations

import pandas as pd
import pytest

from simulation.configuration import ConfigurationModuleFluxFixe
from simulation.modules.base import ContexteSimulation
from simulation.modules.flux_fixe import ModuleFluxFixe


def test_flux_fixe_non_indexe_constant() -> None:
    config = ConfigurationModuleFluxFixe(
        id="depense_test",
        type="flux_fixe",
        debut="2025-01",
        fin="2025-03",
        montant=1000,
        sens="depense",
        categorie="depenses",
        compte="cash",
    )
    contexte = ContexteSimulation(
        calendrier=pd.period_range("2025-01", "2025-03", freq="M"),
        hypotheses={"inflation_annuelle": 0.12},
        comptes=["cash"],
    )

    sortie = ModuleFluxFixe(config).executer(contexte)

    assert sortie.registre_lignes["flux_de_tresorerie"].tolist() == [-1000.0, -1000.0, -1000.0]


def test_flux_fixe_indexation_inflation() -> None:
    config = ConfigurationModuleFluxFixe(
        id="depense_indexee",
        type="flux_fixe",
        montant=1200,
        sens="depense",
        categorie="depenses",
        compte="cash",
        indexation="inflation",
    )
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    contexte = ContexteSimulation(
        calendrier=calendrier,
        hypotheses={"inflation_annuelle": 0.12},
        comptes=["cash"],
    )

    sortie = ModuleFluxFixe(config).executer(contexte)
    flux = sortie.registre_lignes["flux_de_tresorerie"].tolist()

    assert flux[0] == pytest.approx(-1200.0)
    assert flux[1] == pytest.approx(-(1200 * (1.12 ** (1 / 12))))
    assert flux[2] == pytest.approx(-(1200 * (1.12 ** (2 / 12))))


def test_flux_fixe_croissance_salaire_revalorisee_au_premier_janvier() -> None:
    config = ConfigurationModuleFluxFixe(
        id="salaire_indexe",
        type="flux_fixe",
        debut="2025-10",
        fin="2026-02",
        montant=3000,
        sens="revenu",
        categorie="salaire",
        compte="cash",
        indexation="croissance_salaire",
    )
    calendrier = pd.period_range("2025-10", "2026-02", freq="M")
    contexte = ContexteSimulation(
        calendrier=calendrier,
        hypotheses={"croissance_salaire_annuelle": 0.12},
        comptes=["cash"],
    )

    sortie = ModuleFluxFixe(config).executer(contexte)
    flux = sortie.registre_lignes["flux_de_tresorerie"].tolist()

    assert flux[:3] == pytest.approx([3000.0, 3000.0, 3000.0])
    assert flux[3:] == pytest.approx([3360.0, 3360.0])


def test_flux_fixe_indexation_loyer_revalorisee_au_premier_janvier() -> None:
    config = ConfigurationModuleFluxFixe(
        id="loyer_indexe",
        type="flux_fixe",
        debut="2025-11",
        fin="2026-02",
        montant=1000,
        sens="depense",
        categorie="loyer",
        compte="cash",
        indexation="indexation_loyer",
    )
    calendrier = pd.period_range("2025-11", "2026-02", freq="M")
    contexte = ContexteSimulation(
        calendrier=calendrier,
        hypotheses={"indexation_loyers_annuelle": 0.03},
        comptes=["cash"],
    )

    sortie = ModuleFluxFixe(config).executer(contexte)
    flux = sortie.registre_lignes["flux_de_tresorerie"].tolist()

    assert flux[:2] == pytest.approx([-1000.0, -1000.0])
    assert flux[2:] == pytest.approx([-1030.0, -1030.0])


def test_flux_fixe_sans_bornes_utilise_calendrier_global() -> None:
    config = ConfigurationModuleFluxFixe(
        id="salaire",
        type="flux_fixe",
        montant=100,
        sens="revenu",
        categorie="salaire",
    )
    contexte = ContexteSimulation(
        calendrier=pd.period_range("2025-01", "2025-04", freq="M"),
        hypotheses={},
        comptes=["cash"],
    )

    sortie = ModuleFluxFixe(config).executer(contexte)

    assert len(sortie.registre_lignes) == 4


def test_flux_fixe_indexation_variable_par_periode() -> None:
    config = ConfigurationModuleFluxFixe(
        id="salaire_variable",
        type="flux_fixe",
        debut="2025-12",
        fin="2027-02",
        montant=2000,
        sens="revenu",
        categorie="salaire",
        compte="cash",
        indexation="croissance_salaire",
    )
    calendrier = pd.period_range("2025-12", "2027-02", freq="M")
    contexte = ContexteSimulation(
        calendrier=calendrier,
        hypotheses={"croissance_salaire_annuelle": {"2026": 0.10, "2027": 0.20}},
        comptes=["cash"],
    )

    sortie = ModuleFluxFixe(config).executer(contexte)
    flux = sortie.registre_lignes["flux_de_tresorerie"].tolist()

    assert flux[0] == pytest.approx(2000.0)
    assert flux[1] == pytest.approx(2200.0)
    assert flux[-1] == pytest.approx(2640.0)
