from __future__ import annotations

from pathlib import Path

import pandas as pd

from simulation.configuration import charger_configuration
from simulation.moteur import executer_simulation_depuis_config


def test_tresorerie_synthese_egale_tresorerie_initiale_plus_flux(tmp_path: Path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    utilisateur = tmp_path / "parametres.utilisateur.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-03"
portefeuille:
  tresorerie_initiale: 1000
  comptes: ["cash", "courtier"]
  taux_investissement_restant: 0.0
modules:
  - id: "salaire"
    type: "flux_fixe"
    montant: 1000
    sens: "revenu"
    categorie: "salaire"
    compte: "cash"
  - id: "depenses"
    type: "flux_fixe"
    montant: 400
    sens: "depense"
    categorie: "vie"
    compte: "cash"
""".strip(),
        encoding="utf-8",
    )
    utilisateur.write_text("{}", encoding="utf-8")
    config = charger_configuration(defaut, utilisateur)

    resultat = executer_simulation_depuis_config(config, tmp_path / "sortie")

    flux = resultat.registre_df.groupby("periode")["flux_de_tresorerie"].sum().sort_index()
    attendu = 1000 + flux.cumsum()
    obtenu = resultat.synthese_df.set_index("periode")["solde_tresorerie"].sort_index()
    pd.testing.assert_series_equal(attendu, obtenu, check_names=False)
