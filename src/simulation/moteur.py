from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .calendrier import construire_calendrier_mensuel
from .configuration import (
    ConfigurationModuleEmprunt,
    ConfigurationModuleFluxFixe,
    ConfigurationModuleImmobilierLocatif,
    ConfigurationModuleResidencePrincipale,
    ConfigurationRacine,
    charger_configuration,
)
from .etat import (
    EtatSimulation,
    accumuler_base_imposable,
    appliquer_flux_cash,
    appliquer_rendement_bourse,
    appliquer_versement_bourse,
    cloturer_annee_fiscale_si_necessaire,
)
from .invariants import AnomalieInvariant, determiner_comptes_tresorerie, verifier_invariants
from .metriques import calculer_metriques
from .modules import (
    ModuleEmprunt,
    ModuleFluxFixe,
    ModuleImmobilierLocatif,
    ModuleResidencePrincipale,
)
from .modules.base import ContexteSimulation, ModuleSimulation
from .registre import COLONNES_REGISTRE, normaliser_registre
from .resultat import ResultatSimulation
from .taux import facteur_revalorisation_annuelle


@dataclass(slots=True)
class OptionsDiagnostic:
    actif: bool = False
    periodes_debug: set[pd.Period] | None = None


def creer_module(config_module: object) -> ModuleSimulation:
    if isinstance(config_module, ConfigurationModuleFluxFixe):
        return ModuleFluxFixe(config_module)
    if isinstance(config_module, ConfigurationModuleEmprunt):
        return ModuleEmprunt(config_module)
    if isinstance(config_module, ConfigurationModuleImmobilierLocatif):
        return ModuleImmobilierLocatif(config_module)
    if isinstance(config_module, ConfigurationModuleResidencePrincipale):
        return ModuleResidencePrincipale(config_module)
    raise ValueError(f"Type de module non supporté: {type(config_module)}")


def calculer_impot_progressif_france(revenu_imposable: float) -> float:
    if revenu_imposable <= 0:
        return 0.0
    tranches = [
        (11497.0, 0.0),
        (29315.0, 0.11),
        (83823.0, 0.30),
        (180294.0, 0.41),
        (float("inf"), 0.45),
    ]
    impot = 0.0
    borne_precedente = 0.0
    for borne, taux in tranches:
        base = min(revenu_imposable, borne) - borne_precedente
        if base > 0:
            impot += base * taux
        if revenu_imposable <= borne:
            break
        borne_precedente = borne
    return impot




def generer_investissement_restant(
    calendrier: pd.PeriodIndex,
    registre_df: pd.DataFrame,
    comptes_tresorerie: set[str],
    tresorerie_initiale: float,
    taux: float,
    rendement_annuel: float,
    id_module: str,
    compte: str,
) -> tuple[pd.DataFrame, pd.Series]:
    if taux <= 0:
        return pd.DataFrame(columns=COLONNES_REGISTRE), pd.Series(dtype=float, name="valeur_bourse")

    flux_par_periode = (
        registre_df[registre_df["compte"].isin(comptes_tresorerie)].groupby("periode")["flux_de_tresorerie"].sum()
        if not registre_df.empty
        else pd.Series(dtype=float)
    )
    taux_mensuel = (1 + rendement_annuel) ** (1 / 12) - 1

    cash = tresorerie_initiale
    valeur_bourse = 0.0
    lignes: list[dict] = []
    valeurs: list[float] = []
    for periode in calendrier:
        cash += float(flux_par_periode.get(periode, 0.0))
        valeur_bourse *= 1 + taux_mensuel
        versement = max(cash, 0.0) * taux
        cash -= versement
        valeur_bourse += versement
        valeurs.append(valeur_bourse)
        if versement > 0:
            lignes.append({
                "periode": periode,
                "id_module": id_module,
                "type_module": "investissement_restant",
                "flux_de_tresorerie": -versement,
                "categorie": "versement_restant",
                "compte": compte,
                "description": "Versement automatique du restant",
            })
    return pd.DataFrame(lignes, columns=COLONNES_REGISTRE), pd.Series(valeurs, index=calendrier, name="valeur_bourse")


def generer_impot_revenu(
    calendrier: pd.PeriodIndex,
    registre_df: pd.DataFrame,
    compte: str,
    mois_paiement: int = 12,
) -> pd.DataFrame:
    if registre_df.empty:
        return pd.DataFrame(columns=COLONNES_REGISTRE)

    lignes: list[dict] = []
    annees = sorted({p.year for p in calendrier})
    for annee in annees:
        salaires = registre_df[(registre_df["categorie"] == "salaire") & (registre_df["periode"].dt.year == annee)]
        loyers = registre_df[(registre_df["categorie"] == "loyer") & (registre_df["periode"].dt.year == annee)]
        base = float(salaires["flux_de_tresorerie"].clip(lower=0).sum()) + 0.5 * float(loyers["flux_de_tresorerie"].clip(lower=0).sum())
        impot = calculer_impot_progressif_france(base)
        if impot <= 0:
            continue
        periode_paiement = pd.Period(f"{annee + 1}-{mois_paiement:02d}", freq="M")
        if periode_paiement not in calendrier:
            continue
        lignes.append({
            "periode": periode_paiement,
            "id_module": "fiscalite",
            "type_module": "fiscalite",
            "flux_de_tresorerie": -impot,
            "categorie": "impot_sur_le_revenu",
            "compte": compte,
            "description": f"IR année {annee} payé en N+1",
        })
    return pd.DataFrame(lignes, columns=COLONNES_REGISTRE)
def _est_impot_revenu_a_payer(periode: pd.Period, mois_paiement_ir: int) -> bool:
    return periode.month == mois_paiement_ir


def _construire_etat_module_series(
    valeurs_etat_modules: dict[str, dict[str, list[tuple[pd.Period, object]]]],
) -> dict[str, dict[str, pd.Series | pd.DataFrame]]:
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]] = {}
    for id_module, etats in valeurs_etat_modules.items():
        etats_par_module[id_module] = {}
        for nom_etat, points in etats.items():
            if not points:
                continue
            index = pd.PeriodIndex([periode for periode, _ in points], freq="M")
            valeurs = [valeur for _, valeur in points]
            etats_par_module[id_module][nom_etat] = pd.Series(valeurs, index=index, name=nom_etat)
    return etats_par_module


def _calculer_synthese_stateful(lignes_synthese: list[dict]) -> pd.DataFrame:
    if not lignes_synthese:
        return pd.DataFrame(columns=["periode", "flux_net", "solde_tresorerie", "tresorerie_debut", "tresorerie_fin", "valeur_bourse_fin"])
    df = pd.DataFrame(lignes_synthese)
    return df[["periode", "flux_net", "solde_tresorerie", "tresorerie_debut", "tresorerie_fin", "valeur_bourse_fin"]]


def exporter_resultats(resultat: ResultatSimulation, dossier_sortie: Path, generer_csv: bool = False) -> None:
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    if generer_csv:
        resultat.registre_df.to_csv(dossier_sortie / "registre.csv", index=False)
        resultat.synthese_df.to_csv(dossier_sortie / "synthese_mensuelle.csv", index=False)
        ids_csv = {id_module: f"module_{idx}" for idx, id_module in enumerate(sorted(resultat.etats_par_module.keys()), start=1)}
        for id_module, etats in resultat.etats_par_module.items():
            for nom_etat, serie_ou_df in etats.items():
                if isinstance(serie_ou_df, pd.Series):
                    etat_df = serie_ou_df.reset_index()
                    etat_df.columns = ["periode", nom_etat]
                else:
                    etat_df = serie_ou_df.reset_index()
                etat_df.to_csv(dossier_sortie / f"etats_module_{ids_csv[id_module]}_{nom_etat}.csv", index=False)

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
    config: ConfigurationRacine,
    dossier_sortie: Path,
    options_diagnostic: OptionsDiagnostic | None = None,
    generer_csv: bool = False,
) -> ResultatSimulation:
    """Moteur mensuel stateful.

    Cycle mensuel (ordre déterministe A→G):
    A) revenus primaires (modules flux_fixe/revenu),
    B) dépenses de vie (modules flux_fixe/depense),
    C) immobilier locatif,
    D) résidence principale,
    E) impôts mensuels (non utilisés ici),
    F) clôture investissement: sweep du cash restant vers la bourse,
    G) mise à jour état/invariants + clôture fiscale annuelle.

    Conventions de signe: flux de trésorerie positif = entrée de cash, négatif = sortie.
    """
    options = options_diagnostic or OptionsDiagnostic()
    calendrier = construire_calendrier_mensuel(config.simulation.date_debut, config.simulation.date_fin)
    contexte = ContexteSimulation(
        calendrier=calendrier,
        hypotheses=config.hypotheses.model_dump(),
        comptes=config.portefeuille.comptes,
    )

    modules = [creer_module(config_module) for config_module in config.modules]
    modules_par_ordre: dict[str, list[ModuleSimulation]] = {
        "A": [m for m in modules if m.type_module == "flux_fixe" and getattr(m, "config", None).sens == "revenu"],
        "B": [m for m in modules if m.type_module == "flux_fixe" and getattr(m, "config", None).sens == "depense"],
        "C": [m for m in modules if m.type_module == "immobilier_locatif"],
        "D": [m for m in modules if m.type_module in {"residence_principale", "emprunt"}],
    }

    comptes_bourse = {config.portefeuille.compte_investissement_restant}
    comptes_tresorerie = determiner_comptes_tresorerie(config.portefeuille.comptes, comptes_bourse)

    lignes_registre: list[dict] = []
    lignes_synthese: list[dict] = []
    valeurs_etat_modules: dict[str, dict[str, list[tuple[pd.Period, object]]]] = {}
    etat = EtatSimulation(
        periode_courante=calendrier[0],
        cash=config.portefeuille.tresorerie_initiale,
        bourse=config.portefeuille.bourse_initiale,
    )

    taux_mensuel_restant = (
        (1 + config.hypotheses.rendement_bourse_annuel) ** (1 / 12) - 1
    )

    for idx, periode in enumerate(calendrier):
        etat.periode_courante = periode
        tresorerie_debut = etat.cash
        bourse_debut = etat.bourse

        flux_net_mensuel = 0.0
        for etape in ["A", "B", "C", "D"]:
            for module in modules_par_ordre[etape]:
                sortie = module.generer_flux_mensuel(periode, etat, contexte)
                if sortie.lignes_registre:
                    for ligne in sortie.lignes_registre:
                        lignes_registre.append(ligne)
                        montant = float(ligne["flux_de_tresorerie"])
                        if ligne.get("compte") in comptes_tresorerie:
                            appliquer_flux_cash(etat, montant)
                            flux_net_mensuel += montant
                        accumuler_base_imposable(etat, str(ligne.get("categorie", "")), montant)
                if sortie.etats_incrementaux:
                    mod_states = valeurs_etat_modules.setdefault(module.id_module, {})
                    for nom, valeur in sortie.etats_incrementaux.items():
                        if isinstance(valeur, bool):
                            mod_states.setdefault(nom, []).append((periode, valeur))
                            if nom == "possede_residence_principale":
                                etat.possessions["possede_rp"] = bool(valeur)
                        elif isinstance(valeur, (int, float)):
                            mod_states.setdefault(nom, []).append((periode, float(valeur)))
                            if nom == "capital_restant_du":
                                etat.dettes[module.id_module] = float(valeur)

        # E) impôts mensuels éventuels: non modélisé

        # Impôt annuel payé en septembre N+1 (configurable)
        mois_paiement_ir = config.simulation.mois_paiement_impot_revenu
        if _est_impot_revenu_a_payer(periode, mois_paiement_ir):
            annee_reference = periode.year - 1
            base = etat.bases_annuelles_impot.get(annee_reference)
            if base:
                revenu = float(base.get("revenu_imposable", 0.0)) + 0.5 * float(base.get("loyers_imposables", 0.0))
                impot = calculer_impot_progressif_france(revenu)
                if impot > 0:
                    ligne_impot = {
                        "periode": periode,
                        "id_module": "fiscalite",
                        "type_module": "fiscalite",
                        "flux_de_tresorerie": -impot,
                        "categorie": "impot_sur_le_revenu",
                        "compte": "cash",
                        "description": f"IR année {annee_reference} payé en septembre N+1",
                    }
                    lignes_registre.append(ligne_impot)
                    appliquer_flux_cash(etat, -impot)
                    flux_net_mensuel -= impot

        # Loyer de RP si pas propriétaire (revalorisé annuellement au 1er janvier)
        if config.portefeuille.loyer_residence_principale > 0 and not etat.possessions.get("possede_rp", False):
            loyer_rp = config.portefeuille.loyer_residence_principale * facteur_revalorisation_annuelle(
                periode,
                calendrier[0],
                config.hypotheses.indexation_loyers_annuelle,
            )
            ligne_loyer_rp = {
                "periode": periode,
                "id_module": "loyer_residence_principale",
                "type_module": "flux_global",
                "flux_de_tresorerie": -loyer_rp,
                "categorie": "loyer_residence_principale",
                "compte": "cash",
                "description": "Loyer résidence principale",
            }
            lignes_registre.append(ligne_loyer_rp)
            appliquer_flux_cash(etat, -loyer_rp)
            flux_net_mensuel -= loyer_rp

        # F) Sweep investissement restant
        appliquer_rendement_bourse(etat, taux_mensuel_restant)
        versement = appliquer_versement_bourse(etat, max(etat.cash, 0.0) * config.portefeuille.taux_investissement_restant)
        if versement > 0:
            lignes_registre.append(
                {
                    "periode": periode,
                    "id_module": config.portefeuille.id_module_investissement_restant,
                    "type_module": "investissement_restant",
                    "flux_de_tresorerie": -versement,
                    "categorie": "versement_restant",
                    "compte": "cash",
                    "description": "Versement automatique du restant",
                }
            )
            flux_net_mensuel -= versement
        valeurs_etat_modules.setdefault(config.portefeuille.id_module_investissement_restant, {}).setdefault("valeur_bourse", []).append((periode, etat.bourse))

        # G) Clôture et invariants simples
        periode_suivante = calendrier[idx + 1] if idx + 1 < len(calendrier) else None
        cloturer_annee_fiscale_si_necessaire(etat, periode_suivante)

        lignes_synthese.append(
            {
                "periode": periode,
                "flux_net": flux_net_mensuel,
                "solde_tresorerie": etat.cash,
                "tresorerie_debut": tresorerie_debut,
                "tresorerie_fin": etat.cash,
                "valeur_bourse_debut": bourse_debut,
                "valeur_bourse_fin": etat.bourse,
            }
        )

    registre_df = normaliser_registre(pd.DataFrame(lignes_registre, columns=COLONNES_REGISTRE)) if lignes_registre else pd.DataFrame(columns=COLONNES_REGISTRE)
    etats_par_module = _construire_etat_module_series(valeurs_etat_modules)
    synthese_df = _calculer_synthese_stateful(lignes_synthese)

    metriques = calculer_metriques(registre_df, synthese_df, etats_par_module, config)
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
    exporter_resultats(resultat, dossier_sortie, generer_csv=generer_csv)
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
