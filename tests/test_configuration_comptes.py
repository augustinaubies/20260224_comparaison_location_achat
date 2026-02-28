from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from simulation.configuration import charger_configuration


def test_configuration_comptes_definitions_applique_regles_par_type(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes_definitions:
    - id: cash
      type: cash
    - id: pea_perso
      type: pea
    - id: cto_perso
      type: cto
    - id: pel_perso
      type: pel
modules: []
""".strip(),
        encoding="utf-8",
    )

    config = charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")

    comptes = {compte.id: compte for compte in config.portefeuille.comptes_definitions}
    assert config.portefeuille.comptes == ["cash", "pea_perso", "cto_perso", "pel_perso"]
    assert comptes["pea_perso"].plafond_versement == 150000.0
    assert comptes["pea_perso"].versements_autorises_apres_premier_retrait is False
    assert comptes["cto_perso"].fiscalite_plus_value_sortie == pytest.approx(0.30)
    assert comptes["pel_perso"].pret_immobilier_autorise is True


def test_configuration_comptes_definitions_rejette_ids_dupliques(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes_definitions:
    - id: livret
      type: livret
    - id: livret
      type: livret
modules: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ids de comptes"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")


def test_configuration_livrets_reglementes_defaut_plafonds_et_fiscalite(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes_definitions:
    - id: livret_a
      type: livret
      livret_reglemente: livret_a
    - id: ldds
      type: livret
      livret_reglemente: ldds
modules: []
""".strip(),
        encoding="utf-8",
    )

    config = charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")
    comptes = {compte.id: compte for compte in config.portefeuille.comptes_definitions}

    assert comptes["livret_a"].plafond_versement == 22950.0
    assert comptes["livret_a"].fiscalite_plus_value_sortie == 0.0
    assert comptes["ldds"].plafond_versement == 12000.0
    assert comptes["ldds"].fiscalite_plus_value_sortie == 0.0


def test_configuration_rejette_fiscalite_livret_non_nulle(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes_definitions:
    - id: livret_a
      type: livret
      livret_reglemente: livret_a
      fiscalite_plus_value_sortie: 0.15
modules: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non fiscalisés"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")


def test_configuration_priorites_allocation_rejette_compte_inconnu(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes_definitions:
    - id: cash
      type: cash
    - id: pea
      type: pea
  priorites_allocation_investissement: [pea, inconnu]
modules: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="comptes inconnus"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")


def test_configuration_rejette_champ_legacy_comptes(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes: [cash, courtier]
modules: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="portefeuille.comptes"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")


def test_configuration_rejette_duree_mois_legacy_module_emprunt(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-12"
modules:
  - id: credit
    type: emprunt
    date_debut: "2025-01"
    capital: 100000
    taux_annuel: 0.03
    duree_mois: 240
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="modules.0.emprunt.duree_mois"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")


def test_configuration_rejette_duree_mois_legacy_emprunt_integre(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-12"
modules:
  - id: rp
    type: residence_principale
    date_achat: "2025-01"
    prix: 200000
    taux_frais_notaire: 0.08
    apport: 20000
    emprunt:
      taux_annuel: 0.03
      duree_mois: 300
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="modules.0.residence_principale.emprunt.duree_mois"):
        charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")
