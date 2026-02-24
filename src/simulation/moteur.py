from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from simulation.calendrier import construire_calendrier_mensuel
from simulation.configuration import (
    ConfigurationModuleEmprunt,
    ConfigurationModuleFluxFixe,
    ConfigurationModuleImmobilierLocatif,
    ConfigurationModuleInvestissementDCA,
    charger_configuration,
)
from simulation.metriques import calculer_metriques
from simulation.modules import (
    ModuleEmprunt,
    ModuleFluxFixe,
    ModuleImmobilierLocatif,
    ModuleInvestissementDCA,
)
from simulation.modules.base import ContexteSimulation, ModuleSimulation
from simulation.registre import calculer_synthese_mensuelle, normaliser_registre
from simulation.resultat import ResultatSimulation



def creer_module(config_module: object) -> ModuleSimulation:
    if isinstance(config_module, ConfigurationModuleFluxFixe):
        return ModuleFluxFixe(config_module)
    if isinstance(config_module, ConfigurationModuleInvestissementDCA):
        return ModuleInvestissementDCA(config_module)
    if isinstance(config_module, ConfigurationModuleEmprunt):
        return ModuleEmprunt(config_module)
    if isinstance(config_module, ConfigurationModuleImmobilierLocatif):
        return ModuleImmobilierLocatif(config_module)
    raise ValueError(f"Type de module non supporté: {type(config_module)}")



def exporter_resultats(resultat: ResultatSimulation, dossier_sortie: Path) -> None:
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    resultat.registre_df.to_csv(dossier_sortie / "registre.csv", index=False)
    resultat.synthese_df.to_csv(dossier_sortie / "synthese_mensuelle.csv", index=False)
    for id_module, etats in resultat.etats_par_module.items():
        for nom_etat, serie_ou_df in etats.items():
            if isinstance(serie_ou_df, pd.Series):
                etat_df = serie_ou_df.reset_index()
                etat_df.columns = ["periode", nom_etat]
            else:
                etat_df = serie_ou_df.reset_index()
            etat_df.to_csv(dossier_sortie / f"etats_module_{id_module}_{nom_etat}.csv", index=False)

    with (dossier_sortie / "rapport.json").open("w", encoding="utf-8") as fichier:
        json.dump(resultat.metriques, fichier, ensure_ascii=False, indent=2)



def executer_simulation(
    chemin_parametres_defaut: Path,
    chemin_parametres_utilisateur: Path,
    dossier_sortie: Path,
) -> ResultatSimulation:
    config = charger_configuration(chemin_parametres_defaut, chemin_parametres_utilisateur)
    calendrier = construire_calendrier_mensuel(config.simulation.date_debut, config.simulation.date_fin)
    contexte = ContexteSimulation(
        calendrier=calendrier,
        hypotheses=config.hypotheses.model_dump(),
        comptes=config.portefeuille.comptes,
    )

    registres: list[pd.DataFrame] = []
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]] = {}

    for config_module in config.modules:
        module = creer_module(config_module)
        sortie = module.executer(contexte)
        if not sortie.registre_lignes.empty:
            registres.append(sortie.registre_lignes)
        etats_par_module[module.id_module] = sortie.etats

    if registres:
        registre_df = normaliser_registre(pd.concat(registres, ignore_index=True))
    else:
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
    synthese_df = calculer_synthese_mensuelle(registre_df, config.portefeuille.tresorerie_initiale)
    metriques = calculer_metriques(registre_df, synthese_df, etats_par_module)

    resultat = ResultatSimulation(
        registre_df=registre_df,
        synthese_df=synthese_df,
        metriques=metriques,
        etats_par_module=etats_par_module,
    )
    exporter_resultats(resultat, dossier_sortie)
    return resultat
