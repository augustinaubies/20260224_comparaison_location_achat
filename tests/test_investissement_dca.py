from __future__ import annotations

from pathlib import Path

from simulation.configuration import charger_configuration


def test_module_dca_est_ignore_sans_erreur(tmp_path: Path) -> None:
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

    config = charger_configuration(defaut, utilisateur)

    assert config.modules == []
