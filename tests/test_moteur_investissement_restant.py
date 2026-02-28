from __future__ import annotations

import pandas as pd

from simulation.moteur import generer_impot_revenu, generer_investissement_restant


def test_investissement_restant_tresorerie_initiale_uniquement() -> None:
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    registre_df = pd.DataFrame(
        columns=[
            "periode",
            "id_module",
            "type_module",
            "flux_de_tresorerie",
            "categorie",
            "compte",
            "description",
        ]
    )

    lignes, valeur_bourse = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_df,
        comptes_tresorerie={"cash"},
        tresorerie_initiale=1000,
        taux=1.0,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes["flux_de_tresorerie"].tolist() == [-1000.0]
    assert float(valeur_bourse.iloc[-1]) == 1000.0


def test_investissement_restant_avec_flux_positifs() -> None:
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": calendrier,
            "id_module": ["salaire", "salaire", "salaire"],
            "type_module": ["flux_fixe", "flux_fixe", "flux_fixe"],
            "flux_de_tresorerie": [100.0, 100.0, 100.0],
            "categorie": ["salaire", "salaire", "salaire"],
            "compte": ["cash", "cash", "cash"],
            "description": ["Salaire", "Salaire", "Salaire"],
        }
    )

    lignes, valeur_bourse = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_df,
        comptes_tresorerie={"cash"},
        tresorerie_initiale=0.0,
        taux=0.5,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes["flux_de_tresorerie"].tolist() == [-50.0, -75.0, -87.5]
    assert float(valeur_bourse.iloc[-1]) == 212.5


def test_investissement_restant_taux_zero_aucune_ligne() -> None:
    calendrier = pd.period_range("2025-01", "2025-03", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": calendrier,
            "id_module": ["salaire", "salaire", "salaire"],
            "type_module": ["flux_fixe", "flux_fixe", "flux_fixe"],
            "flux_de_tresorerie": [100.0, 100.0, 100.0],
            "categorie": ["salaire", "salaire", "salaire"],
            "compte": ["cash", "cash", "cash"],
            "description": ["Salaire", "Salaire", "Salaire"],
        }
    )

    lignes, _ = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_df,
        comptes_tresorerie={"cash"},
        tresorerie_initiale=0.0,
        taux=0.0,
        rendement_annuel=0.0,
        id_module="investissement_restant",
        compte="courtier",
    )

    assert lignes.empty


def test_impot_revenu_salaire_seul() -> None:
    calendrier = pd.period_range("2025-01", "2026-12", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": list(pd.period_range("2025-01", "2025-12", freq="M")),
            "id_module": ["salaire"] * 12,
            "type_module": ["flux_fixe"] * 12,
            "flux_de_tresorerie": [3000.0] * 12,
            "categorie": ["salaire"] * 12,
            "compte": ["cash"] * 12,
            "description": ["Salaire"] * 12,
        }
    )

    impot = generer_impot_revenu(calendrier, registre_df, compte="cash")

    assert len(impot) == 1
    assert float(impot.iloc[0]["flux_de_tresorerie"]) == -3965.48


def test_impot_revenu_avec_abattement_micro_bic() -> None:
    calendrier = pd.period_range("2025-01", "2026-12", freq="M")
    periode_imposable = list(pd.period_range("2025-01", "2025-12", freq="M"))
    registre_df = pd.DataFrame(
        {
            "periode": periode_imposable + periode_imposable,
            "id_module": ["salaire"] * 12 + ["locatif"] * 12,
            "type_module": ["flux_fixe"] * 12 + ["immobilier_locatif"] * 12,
            "flux_de_tresorerie": [3000.0] * 12 + [1000.0] * 12,
            "categorie": ["salaire"] * 12 + ["loyer"] * 12,
            "compte": ["cash"] * 24,
            "description": ["Salaire"] * 12 + ["Loyer"] * 12,
        }
    )

    impot = generer_impot_revenu(calendrier, registre_df, compte="cash")

    assert len(impot) == 1
    assert float(impot.iloc[0]["flux_de_tresorerie"]) == -5765.48


def test_impot_revenu_tranches_indexees_sur_inflation() -> None:
    calendrier = pd.period_range("2025-01", "2027-12", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": list(pd.period_range("2026-01", "2026-12", freq="M")),
            "id_module": ["salaire"] * 12,
            "type_module": ["flux_fixe"] * 12,
            "flux_de_tresorerie": [3000.0] * 12,
            "categorie": ["salaire"] * 12,
            "compte": ["cash"] * 12,
            "description": ["Salaire"] * 12,
        }
    )

    impot_sans_indexation = generer_impot_revenu(calendrier, registre_df, compte="cash", inflation_annuelle=0.0)
    impot_avec_indexation = generer_impot_revenu(calendrier, registre_df, compte="cash", inflation_annuelle=0.10)

    assert len(impot_sans_indexation) == 1
    assert len(impot_avec_indexation) == 1
    assert float(impot_avec_indexation.iloc[0]["flux_de_tresorerie"]) > float(impot_sans_indexation.iloc[0]["flux_de_tresorerie"])


def test_impot_revenu_tranches_indexees_sur_inflation_variable() -> None:
    calendrier = pd.period_range("2025-01", "2028-12", freq="M")
    registre_df = pd.DataFrame(
        {
            "periode": list(pd.period_range("2027-01", "2027-12", freq="M")),
            "id_module": ["salaire"] * 12,
            "type_module": ["flux_fixe"] * 12,
            "flux_de_tresorerie": [3000.0] * 12,
            "categorie": ["salaire"] * 12,
            "compte": ["cash"] * 12,
            "description": ["Salaire"] * 12,
        }
    )

    impot_constant = generer_impot_revenu(calendrier, registre_df, compte="cash", inflation_annuelle=0.05)
    impot_variable = generer_impot_revenu(
        calendrier,
        registre_df,
        compte="cash",
        inflation_annuelle={"2026": 0.02, "2027": 0.03},
    )

    assert len(impot_constant) == 1
    assert len(impot_variable) == 1
    assert float(impot_variable.iloc[0]["flux_de_tresorerie"]) < float(impot_constant.iloc[0]["flux_de_tresorerie"])

from simulation.configuration import charger_configuration
from simulation.moteur import executer_simulation_depuis_config


def test_investissement_restant_allocation_par_priorite_et_plafond(tmp_path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
hypotheses:
  rendement_bourse_annuel: 0.0
portefeuille:
  tresorerie_initiale: 1000
  taux_investissement_restant: 1.0
  comptes_definitions:
    - id: cash
      type: cash
    - id: livret_a
      type: livret
      livret_reglemente: livret_a
      plafond_versement: 200
    - id: courtier
      type: cto
  priorites_allocation_investissement: [livret_a, courtier]
modules: []
""".strip(),
        encoding="utf-8",
    )

    config = charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")
    resultat = executer_simulation_depuis_config(config, dossier_sortie=tmp_path / "sortie")

    versements = resultat.registre_df[resultat.registre_df["categorie"] == "versement_restant"]
    assert versements["compte"].tolist() == ["livret_a", "courtier"]
    assert versements["flux_de_tresorerie"].tolist() == [-200.0, -800.0]


def test_investissement_restant_reste_en_cash_si_aucune_allocation_possible(tmp_path) -> None:
    defaut = tmp_path / "parametres.defaut.yaml"
    defaut.write_text(
        """
simulation:
  date_debut: "2025-01"
  date_fin: "2025-01"
hypotheses:
  rendement_bourse_annuel: 0.0
portefeuille:
  tresorerie_initiale: 500
  taux_investissement_restant: 1.0
  comptes_definitions:
    - id: cash
      type: cash
    - id: livret_a
      type: livret
      livret_reglemente: livret_a
      plafond_versement: 0
  priorites_allocation_investissement: [livret_a]
modules: []
""".strip(),
        encoding="utf-8",
    )

    config = charger_configuration(defaut, tmp_path / "parametres.utilisateur.yaml")
    resultat = executer_simulation_depuis_config(config, dossier_sortie=tmp_path / "sortie")

    assert resultat.registre_df[resultat.registre_df["categorie"] == "versement_restant"].empty
    assert float(resultat.synthese_df.iloc[-1]["tresorerie_fin"]) == 500.0
