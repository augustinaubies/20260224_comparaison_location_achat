from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from simulation.cli import application
from simulation.configuration import charger_configuration


def ecrire_parametres_defaut(chemin: Path) -> None:
    chemin.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-02"
taux_variables:
  inflation_annuelle: 0.02
  rendement_bourse_annuel: 0.05
portefeuille:
  tresorerie_initiale: 1000
  comptes_definitions:
    - id: cash
      type: cash
    - id: courtier
      type: cto
modules:
  - id: "salaire"
    type: "flux_fixe"
    montant: 100
    sens: "revenu"
    categorie: "salaire"
""".strip(),
        encoding="utf-8",
    )


def test_cli_sans_arguments_cree_sortie_horodatee_et_rapport_json_seul(tmp_path: Path, monkeypatch) -> None:
    ecrire_parametres_defaut(tmp_path / "parametres.defaut.yaml")
    (tmp_path / "parametres.utilisateur.yaml").write_text("{}", encoding="utf-8")
    (tmp_path / "ailleurs").mkdir()
    monkeypatch.chdir(tmp_path / "ailleurs")
    monkeypatch.setattr("simulation.cli.obtenir_racine_projet", lambda: tmp_path)

    resultat = CliRunner().invoke(application, [])

    assert resultat.exit_code == 0
    assert "Statut: OK" in resultat.stdout

    dossiers = sorted((tmp_path / "sorties").glob("*"))
    assert len(dossiers) == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}", dossiers[0].name)

    fichiers = {chemin.name for chemin in dossiers[0].iterdir()}
    assert fichiers == {
        "rapport.json",
        "parametres.defaut.yaml",
        "parametres.utilisateur.yaml",
        "parametres.fusionnes.yaml",
    }




def test_cli_option_csv_reactive_les_exports_csv(tmp_path: Path, monkeypatch) -> None:
    ecrire_parametres_defaut(tmp_path / "parametres.defaut.yaml")
    (tmp_path / "parametres.utilisateur.yaml").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("simulation.cli.obtenir_racine_projet", lambda: tmp_path)

    resultat = CliRunner().invoke(application, ["--csv"])

    assert resultat.exit_code == 0
    dossiers = sorted((tmp_path / "sorties").glob("*"))
    fichiers = {chemin.name for chemin in dossiers[0].iterdir()}
    assert "rapport.json" in fichiers
    assert "registre.csv" in fichiers
    assert "synthese_mensuelle.csv" in fichiers
    assert "parametres.defaut.yaml" in fichiers
    assert "parametres.utilisateur.yaml" in fichiers
    assert "parametres.fusionnes.yaml" in fichiers
    assert any(nom.startswith("etats_module_") for nom in fichiers)

def test_cli_absence_parametres_utilisateur_nest_pas_une_erreur(
    tmp_path: Path, monkeypatch
) -> None:
    ecrire_parametres_defaut(tmp_path / "parametres.defaut.yaml")
    monkeypatch.setattr("simulation.cli.obtenir_racine_projet", lambda: tmp_path)

    resultat = CliRunner().invoke(application, [])

    assert resultat.exit_code == 0
    assert "Statut: OK" in resultat.stdout


def test_cli_exporte_parametres_fusionnes(tmp_path: Path, monkeypatch) -> None:
    ecrire_parametres_defaut(tmp_path / "parametres.defaut.yaml")
    (tmp_path / "parametres.utilisateur.yaml").write_text(
        """
portefeuille:
  tresorerie_initiale: 2500
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("simulation.cli.obtenir_racine_projet", lambda: tmp_path)

    resultat = CliRunner().invoke(application, [])

    assert resultat.exit_code == 0
    dossier = sorted((tmp_path / "sorties").glob("*"))[0]
    fusionnes = (dossier / "parametres.fusionnes.yaml").read_text(encoding="utf-8")
    assert "tresorerie_initiale: 2500.0" in fusionnes



def test_fusion_configuration_utilisateur_ecrase_defaut(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    utilisateur = tmp_path / "parametres.utilisateur.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
taux_variables:
  inflation_annuelle: 0.02
portefeuille:
  tresorerie_initiale: 1000
  comptes_definitions:
    - id: cash
      type: cash
    - id: courtier
      type: cto
modules: []
""".strip(),
        encoding="utf-8",
    )
    utilisateur.write_text(
        """
portefeuille:
  tresorerie_initiale: 2500
""".strip(),
        encoding="utf-8",
    )

    config = charger_configuration(defaut, utilisateur)

    assert config.portefeuille.tresorerie_initiale == 2500
    assert config.portefeuille.comptes == ["cash", "courtier"]
    assert config.taux_variables.inflation_annuelle == 0.02


def test_configuration_rejette_anciennes_cles_taux_variables(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
taux_variables:
  inflation: 0.02
modules: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"taux_variables\.inflation"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")


def test_configuration_rejette_section_hypotheses_legacy(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
hypotheses:
  inflation_annuelle: 0.02
modules: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"hypotheses"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")
