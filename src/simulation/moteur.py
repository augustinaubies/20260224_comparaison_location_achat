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
from .taux import SourceTaux, facteur_indexation_annuelle_variable, taux_mensuel_compose


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


def calculer_impot_progressif_france(
    revenu_imposable: float,
    inflation_annuelle: object = 0.0,
    annee_imposition: int | None = None,
    annee_reference_bareme: int = 2025,
) -> float:
    if revenu_imposable <= 0:
        return 0.0
    facteur_indexation = 1.0
    if annee_imposition is not None:
        facteur_indexation = facteur_indexation_annuelle_variable(
            annee_reference=annee_reference_bareme,
            annee_cible=annee_imposition,
            source_taux_annuel=inflation_annuelle,
        )
    tranches = [
        (11497.0 * facteur_indexation, 0.0),
        (29315.0 * facteur_indexation, 0.11),
        (83823.0 * facteur_indexation, 0.30),
        (180294.0 * facteur_indexation, 0.41),
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
    inflation_annuelle: object = 0.0,
) -> pd.DataFrame:
    if registre_df.empty:
        return pd.DataFrame(columns=COLONNES_REGISTRE)

    lignes: list[dict] = []
    annees = sorted({p.year for p in calendrier})
    for annee in annees:
        salaires = registre_df[(registre_df["categorie"] == "salaire") & (registre_df["periode"].dt.year == annee)]
        loyers = registre_df[(registre_df["categorie"] == "loyer") & (registre_df["periode"].dt.year == annee)]
        base = float(salaires["flux_de_tresorerie"].clip(lower=0).sum()) + 0.5 * float(loyers["flux_de_tresorerie"].clip(lower=0).sum())
        impot = calculer_impot_progressif_france(base, inflation_annuelle=inflation_annuelle, annee_imposition=annee)
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


def _allouer_versement_selon_priorites(
    montant_a_allouer: float,
    priorites: list[str],
    comptes_definitions: dict[str, object],
    versements_cumules: dict[str, float],
    retraits_effectues: dict[str, bool] | None = None,
) -> dict[str, float]:
    restant = max(float(montant_a_allouer), 0.0)
    allocations: dict[str, float] = {}
    for compte_id in priorites:
        if restant <= 0:
            break
        definition = comptes_definitions.get(compte_id)
        if definition is None or getattr(definition, "type", None) == "cash":
            continue
        if (
            retraits_effectues
            and retraits_effectues.get(compte_id, False)
            and not getattr(definition, "versements_autorises_apres_premier_retrait", True)
        ):
            continue
        plafond = getattr(definition, "plafond_versement", None)
        capacite_restante = restant
        if plafond is not None:
            capacite_restante = max(float(plafond) - float(versements_cumules.get(compte_id, 0.0)), 0.0)
        versement = min(restant, capacite_restante)
        if versement <= 0:
            continue
        allocations[compte_id] = allocations.get(compte_id, 0.0) + versement
        restant -= versement
    return allocations


def _calculer_retrait_et_plus_value(
    compte_id: str,
    montant_brut: float,
    definition: object,
    valeurs_comptes_investissement: dict[str, float],
    couts_revient: dict[str, float],
    lots_cto: dict[str, list[dict[str, float]]],
) -> tuple[float, float]:
    valeur_avant = max(float(valeurs_comptes_investissement.get(compte_id, 0.0)), 0.0)
    retrait_brut = min(max(montant_brut, 0.0), valeur_avant)
    if retrait_brut <= 0:
        return 0.0, 0.0

    principal_retrait = 0.0
    if getattr(definition, "type", None) == "cto":
        restant = retrait_brut
        lots = lots_cto.setdefault(compte_id, [])
        for lot in lots:
            if restant <= 0:
                break
            valeur_lot = max(float(lot.get("valeur", 0.0)), 0.0)
            principal_lot = max(float(lot.get("principal", 0.0)), 0.0)
            if valeur_lot <= 0:
                continue
            prelevement = min(restant, valeur_lot)
            ratio = prelevement / valeur_lot
            principal_retrait += principal_lot * ratio
            lot["valeur"] = max(valeur_lot - prelevement, 0.0)
            lot["principal"] = max(principal_lot - (principal_lot * ratio), 0.0)
            restant -= prelevement
        lots_cto[compte_id] = [lot for lot in lots if lot["valeur"] > 1e-9]
        couts_revient[compte_id] = sum(lot["principal"] for lot in lots_cto[compte_id])
    else:
        cout = max(float(couts_revient.get(compte_id, 0.0)), 0.0)
        ratio = retrait_brut / valeur_avant if valeur_avant > 0 else 0.0
        principal_retrait = min(cout * ratio, retrait_brut)
        couts_revient[compte_id] = max(cout - principal_retrait, 0.0)

    plus_value = max(retrait_brut - principal_retrait, 0.0)
    return retrait_brut, plus_value


def _desinvestir_pour_couvrir_cash_negatif(
    periode: pd.Period,
    besoin_cash: float,
    comptes_definitions: dict[str, object],
    priorites_desinvestissement: list[str],
    valeurs_comptes_investissement: dict[str, float],
    couts_revient: dict[str, float],
    lots_cto: dict[str, list[dict[str, float]]],
    dates_premier_versement: dict[str, pd.Period | None],
    retraits_effectues: dict[str, bool],
) -> tuple[list[dict], float]:
    if besoin_cash <= 0:
        return [], 0.0

    lignes: list[dict] = []
    cash_recupere = 0.0
    restant = besoin_cash

    for compte_id in priorites_desinvestissement:
        if restant <= 0:
            break
        definition = comptes_definitions.get(compte_id)
        if definition is None or getattr(definition, "type", None) == "cash":
            continue
        while restant > 0:
            retrait_brut, plus_value = _calculer_retrait_et_plus_value(
                compte_id=compte_id,
                montant_brut=restant,
                definition=definition,
                valeurs_comptes_investissement=valeurs_comptes_investissement,
                couts_revient=couts_revient,
                lots_cto=lots_cto,
            )
            if retrait_brut <= 0:
                break

            taux_fiscalite = float(getattr(definition, "fiscalite_plus_value_sortie", 0.0) or 0.0)
            if getattr(definition, "type", None) == "pea":
                date_ouverture = dates_premier_versement.get(compte_id)
                anciennete = 0
                if date_ouverture is not None:
                    anciennete = periode.year - date_ouverture.year
                    if periode.month < date_ouverture.month:
                        anciennete -= 1
                taux_fiscalite = 0.17 if anciennete >= 5 else 0.30

            impot_plus_value = plus_value * taux_fiscalite
            net = max(retrait_brut - impot_plus_value, 0.0)
            valeurs_comptes_investissement[compte_id] = max(
                float(valeurs_comptes_investissement.get(compte_id, 0.0)) - retrait_brut,
                0.0,
            )
            retraits_effectues[compte_id] = True

            lignes.append(
                {
                    "periode": periode,
                    "id_module": "investissement_restant",
                    "type_module": "investissement_restant",
                    "flux_de_tresorerie": retrait_brut,
                    "categorie": "desinvestissement_compte",
                    "compte": "cash",
                    "description": f"Retrait depuis {compte_id}",
                }
            )
            if impot_plus_value > 0:
                lignes.append(
                    {
                        "periode": periode,
                        "id_module": "fiscalite_comptes",
                        "type_module": "fiscalite",
                        "flux_de_tresorerie": -impot_plus_value,
                        "categorie": "fiscalite_plus_value_compte",
                        "compte": "cash",
                        "description": f"Fiscalité sur plus-value ({compte_id})",
                    }
                )

            cash_recupere += net
            restant = max(restant - net, 0.0)
            if float(valeurs_comptes_investissement.get(compte_id, 0.0)) <= 0:
                break

    return lignes, cash_recupere


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
        taux_variables=config.taux_variables.model_dump(),
        comptes=config.portefeuille.comptes,
        source_taux=SourceTaux(config.taux_variables.model_dump()),
    )

    modules = [creer_module(config_module) for config_module in config.modules]
    modules_par_ordre: dict[str, list[ModuleSimulation]] = {
        "A": [m for m in modules if m.type_module == "flux_fixe" and getattr(m, "config", None).sens == "revenu"],
        "B": [m for m in modules if m.type_module == "flux_fixe" and getattr(m, "config", None).sens == "depense"],
        "C": [m for m in modules if m.type_module == "immobilier_locatif"],
        "D": [m for m in modules if m.type_module in {"residence_principale", "emprunt"}],
    }

    comptes_definitions = {compte.id: compte for compte in config.portefeuille.comptes_definitions}
    comptes_investissement = {compte.id for compte in config.portefeuille.comptes_definitions if compte.type != "cash"}
    comptes_tresorerie = determiner_comptes_tresorerie(config.portefeuille.comptes, comptes_investissement)

    lignes_registre: list[dict] = []
    lignes_synthese: list[dict] = []
    valeurs_etat_modules: dict[str, dict[str, list[tuple[pd.Period, object]]]] = {}
    etat = EtatSimulation(
        periode_courante=calendrier[0],
        cash=config.portefeuille.tresorerie_initiale,
        bourse=config.portefeuille.bourse_initiale,
    )
    valeurs_comptes_investissement = {compte_id: 0.0 for compte_id in comptes_investissement}
    etat.comptes_investissement = valeurs_comptes_investissement
    etat.comptes_definitions = comptes_definitions
    compte_initial = next(
        (compte for compte in config.portefeuille.priorites_allocation_investissement if compte in valeurs_comptes_investissement),
        None,
    )
    if compte_initial is not None and compte_initial in valeurs_comptes_investissement:
        valeurs_comptes_investissement[compte_initial] = config.portefeuille.bourse_initiale
    versements_cumules = {compte_id: 0.0 for compte_id in comptes_investissement}
    couts_revient_comptes = {compte_id: 0.0 for compte_id in comptes_investissement}
    retraits_effectues = {compte_id: False for compte_id in comptes_investissement}
    dates_premier_versement: dict[str, pd.Period | None] = {compte_id: None for compte_id in comptes_investissement}
    lots_cto: dict[str, list[dict[str, float]]] = {
        compte_id: []
        for compte_id, definition in comptes_definitions.items()
        if getattr(definition, "type", None) == "cto"
    }
    if compte_initial is not None and compte_initial in couts_revient_comptes:
        couts_revient_comptes[compte_initial] = config.portefeuille.bourse_initiale
        dates_premier_versement[compte_initial] = calendrier[0]
        if getattr(comptes_definitions.get(compte_initial), "type", None) == "cto" and config.portefeuille.bourse_initiale > 0:
            lots_cto.setdefault(compte_initial, []).append(
                {"principal": config.portefeuille.bourse_initiale, "valeur": config.portefeuille.bourse_initiale}
            )

    loyer_rp_courant = float(config.portefeuille.loyer_residence_principale)
    reste_a_vivre_minimum_courant = float(config.portefeuille.reste_a_vivre_minimum)

    for idx, periode in enumerate(calendrier):
        etat.periode_courante = periode
        tresorerie_debut = etat.cash
        bourse_debut = etat.bourse

        flux_net_mensuel = 0.0
        sorties_tresorerie_mensuelles = 0.0
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
                            if montant < 0:
                                sorties_tresorerie_mensuelles += -montant
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
                impot = calculer_impot_progressif_france(
                    revenu,
                    inflation_annuelle=config.taux_variables.inflation_annuelle,
                    annee_imposition=annee_reference,
                )
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
                    sorties_tresorerie_mensuelles += impot

        # Loyer de RP si pas propriétaire (revalorisé annuellement au 1er janvier)
        if idx > 0 and periode.month == 1:
            taux_loyer_rp = contexte.taux_variable("indexation_loyers_annuelle", periode)
            loyer_rp_courant *= 1 + taux_loyer_rp
        if config.portefeuille.loyer_residence_principale > 0 and not etat.possessions.get("possede_rp", False):
            loyer_rp = loyer_rp_courant
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
            sorties_tresorerie_mensuelles += loyer_rp

        # F) Sweep investissement restant
        taux_bourse_annuel = contexte.taux_variable("rendement_bourse_annuel", periode)
        taux_bourse_mensuel = taux_mensuel_compose(taux_bourse_annuel)
        for compte_id in valeurs_comptes_investissement:
            valeurs_comptes_investissement[compte_id] *= 1 + taux_bourse_mensuel
            if compte_id in lots_cto:
                for lot in lots_cto[compte_id]:
                    lot["valeur"] *= 1 + taux_bourse_mensuel

        if etat.cash < 0:
            lignes_desinvestissement, _cash_recupere = _desinvestir_pour_couvrir_cash_negatif(
                periode=periode,
                besoin_cash=-etat.cash,
                comptes_definitions=comptes_definitions,
                priorites_desinvestissement=list(reversed(config.portefeuille.priorites_allocation_investissement)),
                valeurs_comptes_investissement=valeurs_comptes_investissement,
                couts_revient=couts_revient_comptes,
                lots_cto=lots_cto,
                dates_premier_versement=dates_premier_versement,
                retraits_effectues=retraits_effectues,
            )
            for ligne in lignes_desinvestissement:
                lignes_registre.append(ligne)
                montant = float(ligne["flux_de_tresorerie"])
                appliquer_flux_cash(etat, montant)
                flux_net_mensuel += montant
                if montant < 0:
                    sorties_tresorerie_mensuelles += -montant

        if config.portefeuille.indexer_reste_a_vivre_sur_inflation and idx > 0 and periode.month == 1:
            taux_inflation_annuel = contexte.taux_variable("inflation_annuelle", periode)
            reste_a_vivre_minimum_courant *= 1 + taux_inflation_annuel
        reste_a_vivre_minimum = reste_a_vivre_minimum_courant
        reste_a_vivre_depenses = config.portefeuille.reste_a_vivre_mois_depenses * sorties_tresorerie_mensuelles
        reste_a_vivre_cible = max(reste_a_vivre_minimum, reste_a_vivre_depenses)
        cash_investissable = max(etat.cash - reste_a_vivre_cible, 0.0)
        versement_total = appliquer_versement_bourse(etat, cash_investissable * config.portefeuille.taux_investissement_restant)
        allocations = _allouer_versement_selon_priorites(
            montant_a_allouer=versement_total,
            priorites=config.portefeuille.priorites_allocation_investissement,
            comptes_definitions=comptes_definitions,
            versements_cumules=versements_cumules,
            retraits_effectues=retraits_effectues,
        )
        montant_alloue = 0.0
        for compte, versement in allocations.items():
            valeurs_comptes_investissement[compte] = valeurs_comptes_investissement.get(compte, 0.0) + versement
            versements_cumules[compte] = versements_cumules.get(compte, 0.0) + versement
            couts_revient_comptes[compte] = couts_revient_comptes.get(compte, 0.0) + versement
            if dates_premier_versement.get(compte) is None:
                dates_premier_versement[compte] = periode
            if compte in lots_cto:
                lots_cto[compte].append({"principal": versement, "valeur": versement})
            montant_alloue += versement
            lignes_registre.append(
                {
                    "periode": periode,
                    "id_module": config.portefeuille.id_module_investissement_restant,
                    "type_module": "investissement_restant",
                    "flux_de_tresorerie": -versement,
                    "categorie": "versement_restant",
                    "compte": compte,
                    "description": "Versement automatique du restant",
                }
            )

        if versement_total > montant_alloue:
            appliquer_flux_cash(etat, versement_total - montant_alloue)

        if montant_alloue > 0:
            flux_net_mensuel -= montant_alloue
        etat.bourse = float(sum(valeurs_comptes_investissement.values()))
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
