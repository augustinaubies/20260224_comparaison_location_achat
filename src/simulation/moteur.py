from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass

import pandas as pd

from .calendrier import construire_calendrier_mensuel
from .configuration import (
    ConfigurationModuleEmprunt,
    ConfigurationModuleFluxFixe,
    ConfigurationModuleImmobilierLocatif,
    ConfigurationModuleInvestissementDCA,
    ConfigurationRacine,
    charger_configuration,
)
from .metriques import calculer_metriques
from .invariants import AnomalieInvariant, determiner_comptes_tresorerie, verifier_invariants
from .modules import (
    ModuleEmprunt,
    ModuleFluxFixe,
    ModuleImmobilierLocatif,
    ModuleInvestissementDCA,
)
from .modules.base import ContexteSimulation, ModuleSimulation
from .registre import calculer_synthese_mensuelle, normaliser_registre
from .resultat import ResultatSimulation


@dataclass(slots=True)
class OptionsDiagnostic:
    actif: bool = False
    periodes_debug: set[pd.Period] | None = None


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


def generer_investissement_restant(
    calendrier: pd.PeriodIndex,
    registre_df: pd.DataFrame,
    tresorerie_initiale: float,
    taux: float,
    rendement_annuel: float,
    id_module: str,
    compte: str,
) -> tuple[pd.DataFrame, pd.Series]:
    if taux <= 0:
        return pd.DataFrame(columns=registre_df.columns), pd.Series(
            dtype=float, name="valeur_bourse"
        )

    flux_par_periode = (
        registre_df.groupby("periode")["flux_de_tresorerie"].sum()
        if not registre_df.empty
        else None
    )
    taux_mensuel = (1 + rendement_annuel) ** (1 / 12) - 1

    cash = tresorerie_initiale
    valeur_bourse = 0.0
    valeurs: list[float] = []
    lignes: list[dict] = []

    for periode in calendrier:
        flux_periode = (
            float(flux_par_periode.get(periode, 0.0)) if flux_par_periode is not None else 0.0
        )
        cash += flux_periode
        versement = max(cash, 0.0) * taux
        cash -= versement
        valeur_bourse = valeur_bourse * (1 + taux_mensuel) + versement
        valeurs.append(valeur_bourse)

        if versement > 0:
            lignes.append(
                {
                    "periode": periode,
                    "id_module": id_module,
                    "type_module": "investissement_restant",
                    "flux_de_tresorerie": -versement,
                    "categorie": "versement_restant",
                    "compte": compte,
                    "description": "Versement automatique du restant",
                }
            )

    serie_valeur = pd.Series(valeurs, index=calendrier, dtype=float, name="valeur_bourse")
    if not lignes:
        return pd.DataFrame(columns=registre_df.columns), serie_valeur
    return pd.DataFrame(lignes), serie_valeur


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


def exporter_diagnostic(
    dossier_sortie: Path,
    calendrier: pd.PeriodIndex,
    registre_df: pd.DataFrame,
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]],
    comptes_tresorerie: set[str],
    tresorerie_initiale: float,
    anomalies: list[AnomalieInvariant],
    periodes_debug: set[pd.Period] | None,
) -> None:
    flux_total = registre_df.groupby("periode", as_index=True)["flux_de_tresorerie"].sum() if not registre_df.empty else pd.Series(dtype=float)
    pivot_comptes = (
        registre_df.pivot_table(index="periode", columns="compte", values="flux_de_tresorerie", aggfunc="sum", fill_value=0.0)
        if not registre_df.empty
        else pd.DataFrame(index=calendrier)
    )
    flux_cash = (
        registre_df[registre_df["compte"].isin(comptes_tresorerie)].groupby("periode")["flux_de_tresorerie"].sum()
        if not registre_df.empty
        else pd.Series(dtype=float)
    )

    lignes = []
    treso = tresorerie_initiale
    for periode in calendrier:
        flux = float(flux_cash.get(periode, 0.0))
        treso_fin = treso + flux
        ligne = {
            "periode": str(periode),
            "somme_flux_total": float(flux_total.get(periode, 0.0)),
            "tresorerie_debut": treso,
            "tresorerie_fin": treso_fin,
            "valeur_bourse_debut": 0.0,
            "valeur_bourse_fin": 0.0,
        }
        if periode in pivot_comptes.index:
            for compte, valeur in pivot_comptes.loc[periode].to_dict().items():
                ligne[f"flux_compte_{compte}"] = float(valeur)

        valeur_totale = 0.0
        for etats in etats_par_module.values():
            serie = etats.get("valeur_bourse")
            if isinstance(serie, pd.Series):
                valeur_totale += float(serie.get(periode, 0.0))
        ligne["valeur_bourse_fin"] = valeur_totale

        for id_module, etats in etats_par_module.items():
            crd = etats.get("capital_restant_du")
            if isinstance(crd, pd.Series):
                ligne[f"crd_fin_{id_module}"] = float(crd.get(periode, 0.0))

        lignes.append(ligne)
        treso = treso_fin

    grand_livre = pd.DataFrame(lignes)
    grand_livre.to_csv(dossier_sortie / "grand_livre_mensuel.csv", index=False)
    if periodes_debug:
        periodes_debug_str = {str(periode) for periode in periodes_debug}
        grand_livre[grand_livre["periode"].isin(periodes_debug_str)].to_csv(
            dossier_sortie / "grand_livre_debug.csv", index=False
        )

    for id_module, etats in etats_par_module.items():
        if "capital_restant_du" not in etats:
            continue
        crd = etats.get("capital_restant_du")
        interets = etats.get("interets_payes")
        principal = etats.get("capital_rembourse")
        if not isinstance(crd, pd.Series):
            continue
        periodes = crd.index
        details = pd.DataFrame({
            "periode": periodes.astype(str),
            "crd_fin": crd.values,
            "interet": interets.reindex(periodes).values if isinstance(interets, pd.Series) else 0.0,
            "principal": principal.reindex(periodes).values if isinstance(principal, pd.Series) else 0.0,
        })
        details["mensualite"] = details["interet"] + details["principal"]
        details["crd_debut"] = details["crd_fin"] + details["principal"]
        details.to_csv(dossier_sortie / f"details_emprunt_{id_module}.csv", index=False)

    pd.DataFrame([a.__dict__ for a in anomalies]).to_csv(dossier_sortie / "anomalies.csv", index=False)


def executer_simulation_depuis_config(
    config: ConfigurationRacine, dossier_sortie: Path, options_diagnostic: OptionsDiagnostic | None = None
) -> ResultatSimulation:
    options = options_diagnostic or OptionsDiagnostic()
    calendrier = construire_calendrier_mensuel(
        config.simulation.date_debut, config.simulation.date_fin
    )
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

    colonnes = [
        "periode",
        "id_module",
        "type_module",
        "flux_de_tresorerie",
        "categorie",
        "compte",
        "description",
    ]
    if registres:
        registre_initial = normaliser_registre(pd.concat(registres, ignore_index=True))
    else:
        registre_initial = pd.DataFrame(columns=colonnes)

    rendement_restant = config.portefeuille.rendement_annuel_investissement_restant
    rendement_restant = (
        config.hypotheses.rendement_marche if rendement_restant is None else rendement_restant
    )
    lignes_restant, valeur_bourse_restant = generer_investissement_restant(
        calendrier=calendrier,
        registre_df=registre_initial,
        tresorerie_initiale=config.portefeuille.tresorerie_initiale,
        taux=config.portefeuille.taux_investissement_restant,
        rendement_annuel=rendement_restant,
        id_module=config.portefeuille.id_module_investissement_restant,
        compte=config.portefeuille.compte_investissement_restant,
    )

    if not lignes_restant.empty:
        registre_df = normaliser_registre(
            pd.concat([registre_initial, lignes_restant], ignore_index=True)
        )
    else:
        registre_df = registre_initial

    etats_par_module[config.portefeuille.id_module_investissement_restant] = {
        "valeur_bourse": valeur_bourse_restant
    }

    synthese_df = calculer_synthese_mensuelle(registre_df, config.portefeuille.tresorerie_initiale)
    metriques = calculer_metriques(registre_df, synthese_df, etats_par_module)

    comptes_bourse = {config.portefeuille.compte_investissement_restant}
    comptes_tresorerie = determiner_comptes_tresorerie(config.portefeuille.comptes, comptes_bourse)
    anomalies = verifier_invariants(
        calendrier=calendrier,
        registre_df=registre_df,
        etats_par_module=etats_par_module,
        tresorerie_initiale=config.portefeuille.tresorerie_initiale,
        comptes_tresorerie=comptes_tresorerie,
        mode_strict=options.actif,
    )
    metriques["nombre_anomalies_invariants"] = float(len(anomalies))

    resultat = ResultatSimulation(
        registre_df=registre_df,
        synthese_df=synthese_df,
        metriques=metriques,
        etats_par_module=etats_par_module,
    )
    exporter_resultats(resultat, dossier_sortie)
    if options.actif:
        exporter_diagnostic(
            dossier_sortie=dossier_sortie,
            calendrier=calendrier,
            registre_df=registre_df,
            etats_par_module=etats_par_module,
            comptes_tresorerie=comptes_tresorerie,
            tresorerie_initiale=config.portefeuille.tresorerie_initiale,
            anomalies=anomalies,
            periodes_debug=options.periodes_debug,
        )
    return resultat


def executer_simulation(
    chemin_parametres_defaut: Path,
    chemin_parametres_utilisateur: Path,
    dossier_sortie: Path,
) -> ResultatSimulation:
    config = charger_configuration(chemin_parametres_defaut, chemin_parametres_utilisateur)
    return executer_simulation_depuis_config(config, dossier_sortie)
