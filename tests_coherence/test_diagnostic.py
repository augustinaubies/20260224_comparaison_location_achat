from __future__ import annotations

from pathlib import Path

import pandas as pd

from simulation.configuration import charger_configuration
from simulation.moteur import OptionsDiagnostic, executer_simulation_depuis_config


def test_mode_diagnostic_exporte_fichiers(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    utilisateur = tmp_path / "parametres.utilisateur.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2028-01"
  date_fin: "2032-12"
portefeuille:
  tresorerie_initiale: 100000
  comptes: ["cash", "courtier"]
  taux_investissement_restant: 0.0
modules:
  - id: "salaire"
    type: "flux_fixe"
    montant: 3000
    sens: "revenu"
    categorie: "salaire"
    compte: "cash"
  - id: "pret"
    type: "emprunt"
    date_debut: "2025-01"
    capital: 120000
    taux_annuel: 0.03
    duree_mois: 240
    compte: "cash"
""".strip(),
        encoding="utf-8",
    )
    utilisateur.write_text("{}", encoding="utf-8")

    config = charger_configuration(defaut, utilisateur)
    sortie = tmp_path / "sortie"
    executer_simulation_depuis_config(
        config,
        sortie,
        options_diagnostic=OptionsDiagnostic(actif=True, periodes_debug={pd.Period("2030-01", freq="M")}),
    )

    assert (sortie / "grand_livre_mensuel.csv").exists()
    assert (sortie / "grand_livre_debug.csv").exists()
    assert (sortie / "details_emprunt_pret.csv").exists()
    assert (sortie / "anomalies.csv").exists()
