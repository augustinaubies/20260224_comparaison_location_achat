from __future__ import annotations

from pathlib import Path

import pytest

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
