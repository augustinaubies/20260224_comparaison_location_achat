from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from simulation.configuration import charger_configuration


def test_module_dca_legacy_declenche_erreur_validation(tmp_path: Path) -> None:
    defaut = tmp_path / "defaut.yaml"
    utilisateur = tmp_path / "utilisateur.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes: ["cash", "courtier"]
modules:
  - id: "dca"
    type: "investissement_dca"
    versement_mensuel: 100
    rendement_annuel_attendu: 0.05
""".strip(),
        encoding="utf-8",
    )
    utilisateur.write_text("{}", encoding="utf-8")

    with pytest.raises(ValidationError, match="investissement_dca"):
        charger_configuration(defaut, utilisateur)


def test_champ_legacy_ville_declenche_erreur_validation(tmp_path: Path) -> None:
    defaut = tmp_path / "defaut.yaml"
    utilisateur = tmp_path / "utilisateur.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
portefeuille:
  comptes: ["cash", "courtier"]
modules:
  - id: "locatif"
    type: "immobilier_locatif"
    date_achat: "2025-01"
    prix: 100000
    taux_frais_notaire: 0.08
    taux_travaux: 0
    apport: 10000
    emprunt:
      taux_annuel: 0.03
      duree_annees: 20
    loyer_mensuel_initial: 700
    date_debut_location: "2025-01"
    ville: "Paris"
""".strip(),
        encoding="utf-8",
    )
    utilisateur.write_text("{}", encoding="utf-8")

    with pytest.raises(ValidationError, match="ville"):
        charger_configuration(defaut, utilisateur)
