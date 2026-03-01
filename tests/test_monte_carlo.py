from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from simulation.cli import application
from simulation.configuration import charger_configuration
from simulation.monte_carlo import construire_distributions_initiales, executer_simulations_monte_carlo


def ecrire_parametres_minimaux(chemin: Path) -> None:
    chemin.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-03"
taux_variables:
  inflation_annuelle: 0.02
  croissance_salaire_annuelle: 0.03
  indexation_loyers_annuelle: 0.015
  revalorisation_immobiliere_annuelle: 0.01
  rendement_bourse_annuel: 0.05
monte_carlo:
  distributions:
    inflation_annuelle:
      moyenne: 0.02
      ecart_type: 0.003
      borne_min: -0.02
      borne_max: 0.1
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


def test_distributions_reprennent_moyenne_des_distributions(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    utilisateur = tmp_path / "parametres.utilisateur.yaml"
    ecrire_parametres_minimaux(defaut)
    utilisateur.write_text("{}", encoding="utf-8")
    config = charger_configuration(defaut, utilisateur)

    distributions = construire_distributions_initiales(config)

    assert distributions["inflation_annuelle"].moyenne == 0.02
    assert distributions["rendement_bourse_annuel"].moyenne == 0.06


def test_distributions_personnalisees_depuis_parametres(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    utilisateur = tmp_path / "parametres.utilisateur.yaml"
    ecrire_parametres_minimaux(defaut)
    utilisateur.write_text("{}", encoding="utf-8")
    config = charger_configuration(defaut, utilisateur)

    distributions = construire_distributions_initiales(config)

    assert distributions["inflation_annuelle"].ecart_type == 0.003
    assert distributions["inflation_annuelle"].borne_min == -0.02


def test_monte_carlo_reproductible_et_exports_csv(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    utilisateur = tmp_path / "parametres.utilisateur.yaml"
    ecrire_parametres_minimaux(defaut)
    utilisateur.write_text("{}", encoding="utf-8")
    config = charger_configuration(defaut, utilisateur)

    sortie_a = tmp_path / "sortie_a"
    sortie_b = tmp_path / "sortie_b"

    df_a = executer_simulations_monte_carlo(config=config, dossier_sortie=sortie_a, nombre_tirages=5, graine=123)
    df_b = executer_simulations_monte_carlo(config=config, dossier_sortie=sortie_b, nombre_tirages=5, graine=123)

    assert df_a.equals(df_b)
    assert (sortie_a / "monte_carlo_tirages.csv").exists()
    assert (sortie_a / "monte_carlo_resume.csv").exists()


def test_commande_cli_monte_carlo_genere_fichiers(tmp_path: Path, monkeypatch) -> None:
    ecrire_parametres_minimaux(tmp_path / "parametres.defaut.yaml")
    (tmp_path / "parametres.utilisateur.yaml").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("simulation.cli.obtenir_racine_projet", lambda: tmp_path)

    resultat = CliRunner().invoke(application, ["monte-carlo", "--tirages", "8", "--graine", "7"])

    assert resultat.exit_code == 0
    dossiers = sorted((tmp_path / "sorties").glob("*"))
    assert len(dossiers) == 1
    fichiers = {chemin.name for chemin in dossiers[0].iterdir()}
    assert "monte_carlo_tirages.csv" in fichiers
    assert "monte_carlo_resume.csv" in fichiers
    assert "parametres.fusionnes.yaml" in fichiers
