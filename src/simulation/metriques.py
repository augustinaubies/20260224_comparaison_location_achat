from __future__ import annotations

import pandas as pd

from .configuration import ConfigurationRacine


def _somme_flux(registre_df: pd.DataFrame, categorie: str, signe: str | None = None) -> float:
    if registre_df.empty:
        return 0.0
    flux = registre_df[registre_df["categorie"] == categorie]["flux_de_tresorerie"]
    if signe == "positif":
        return float(flux.clip(lower=0).sum())
    if signe == "negatif":
        return float((-flux.clip(upper=0)).sum())
    return float(flux.sum())


def _dernier_etat(serie_ou_df: pd.Series | pd.DataFrame | None) -> float:
    if isinstance(serie_ou_df, pd.Series) and not serie_ou_df.empty:
        return float(serie_ou_df.iloc[-1])
    return 0.0


def _neutraliser_id_modules(config: ConfigurationRacine) -> dict[str, str]:
    compteurs: dict[str, int] = {}
    correspondance: dict[str, str] = {}
    for module in config.modules:
        prefixe = {
            "immobilier_locatif": "locatif",
            "residence_principale": "rp",
            "emprunt": "emprunt",
            "flux_fixe": "flux",
        }.get(module.type, "module")
        compteurs[prefixe] = compteurs.get(prefixe, 0) + 1
        correspondance[module.id] = f"{prefixe}_{compteurs[prefixe]}"
    correspondance[config.portefeuille.id_module_investissement_restant] = "bourse_1"
    return correspondance


def calculer_metriques(
    registre_df: pd.DataFrame,
    synthese_df: pd.DataFrame,
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]],
    config: ConfigurationRacine,
) -> dict[str, float | dict[str, float]]:
    ids_neutres = _neutraliser_id_modules(config)
    solde_final = float(synthese_df["solde_tresorerie"].iloc[-1]) if not synthese_df.empty else 0.0
    flux_cumule = float(synthese_df["flux_net"].sum()) if not synthese_df.empty else 0.0
    bourse_finale = sum(_dernier_etat(etats.get("valeur_bourse")) for etats in etats_par_module.values())
    dettes_totales = sum(_dernier_etat(etats.get("capital_restant_du")) for etats in etats_par_module.values())

    immobilier: list[dict[str, float | str]] = []
    immobilier_valeur_totale = 0.0
    for module in config.modules:
        if module.type not in {"immobilier_locatif", "residence_principale"}:
            continue
        valeur = float(module.prix)
        immobilier_valeur_totale += valeur
        crd = _dernier_etat(etats_par_module.get(module.id, {}).get("capital_restant_du"))
        flux_module = registre_df[registre_df["id_module"] == module.id]["flux_de_tresorerie"] if not registre_df.empty else pd.Series(dtype=float)
        cashflow_mensuel = float(flux_module.sum() / len(synthese_df)) if len(synthese_df) > 0 else 0.0
        immobilier.append(
            {
                "id_module": ids_neutres.get(module.id, module.id),
                "type": "locatif" if module.type == "immobilier_locatif" else "rp",
                "valeur": valeur,
                "dette_associee": crd,
                "cashflow_mensuel": cashflow_mensuel,
                "cashflow_annuel": cashflow_mensuel * 12,
            }
        )

    patrimoine_par_categorie = {
        "cash": solde_final,
        "bourse": bourse_finale,
        "immobilier": immobilier_valeur_totale,
        "dettes": -dettes_totales,
    }
    patrimoine_total_final = sum(patrimoine_par_categorie.values())

    modules: dict[str, dict[str, float | str]] = {}
    for module in config.modules:
        id_neutre = ids_neutres.get(module.id, module.id)
        etats = etats_par_module.get(module.id, {})
        module_registre = registre_df[registre_df["id_module"] == module.id] if not registre_df.empty else pd.DataFrame(columns=registre_df.columns)
        if module.type == "immobilier_locatif":
            modules[id_neutre] = {
                "type": "immobilier_locatif",
                "loyers": _somme_flux(module_registre, "loyer", "positif"),
                "charges": _somme_flux(module_registre, "charges", "negatif") + _somme_flux(module_registre, "taxe_fonciere", "negatif"),
                "noi": float(etats.get("revenu_net_exploitation", pd.Series(dtype=float)).sum()) if isinstance(etats.get("revenu_net_exploitation"), pd.Series) else 0.0,
                "crd_final": _dernier_etat(etats.get("capital_restant_du")),
            }
        elif module.type in {"residence_principale", "emprunt"}:
            modules[id_neutre] = {
                "type": module.type,
                "interets": float(etats.get("interets_payes", pd.Series(dtype=float)).sum()) if isinstance(etats.get("interets_payes"), pd.Series) else 0.0,
                "assurance": _somme_flux(module_registre, "assurance_emprunt", "negatif"),
                "crd_final": _dernier_etat(etats.get("capital_restant_du")),
            }
        elif module.type == "flux_fixe":
            modules[id_neutre] = {
                "type": "flux_fixe",
                "total": float(module_registre["flux_de_tresorerie"].sum()) if not module_registre.empty else 0.0,
            }

    versements_bourse = _somme_flux(registre_df, "versement_restant", "negatif")
    modules["bourse_1"] = {
        "type": "investissement_restant",
        "versements": versements_bourse,
        "valeur_finale": bourse_finale,
        "plus_value": bourse_finale - versements_bourse,
    }

    metriques: dict[str, float | dict[str, float] | dict[str, object]] = {
        "solde_final_tresorerie": solde_final,
        "flux_net_cumule": flux_cumule,
        "resume": {
            "date_debut": config.simulation.date_debut,
            "date_fin": config.simulation.date_fin,
            "valeur_finale_comptes": {
                "cash": solde_final,
                "courtier": bourse_finale,
            },
            "immobilier": immobilier,
            "patrimoine_total_final": patrimoine_total_final,
        },
        "patrimoine_total_final": patrimoine_total_final,
        "cash_final": solde_final,
        "bourse_finale": bourse_finale,
        "immobilier_valeur_totale": immobilier_valeur_totale,
        "dettes_totales": dettes_totales,
        "patrimoine_par_categorie": patrimoine_par_categorie,
        "flux_cumules": {
            "revenus": {
                "salaire": _somme_flux(registre_df, "salaire", "positif"),
                "loyers": _somme_flux(registre_df, "loyer", "positif"),
                "autres": float(
                    registre_df[(registre_df["flux_de_tresorerie"] > 0) & (~registre_df["categorie"].isin(["salaire", "loyer"]))]["flux_de_tresorerie"].sum()
                ) if not registre_df.empty else 0.0,
            },
            "depenses_courantes": _somme_flux(registre_df, "depenses_courantes", "negatif") + _somme_flux(registre_df, "loyer_residence_principale", "negatif"),
            "emprunt": {
                "interets_payes_totaux": sum(
                    float(etats.get("interets_payes", pd.Series(dtype=float)).sum())
                    for etats in etats_par_module.values()
                    if isinstance(etats.get("interets_payes"), pd.Series)
                ),
                "assurance_totale": _somme_flux(registre_df, "assurance_emprunt", "negatif"),
                "frais_notaire_totaux": _somme_flux(registre_df, "frais_notaire", "negatif"),
                "frais_banque_totaux": _somme_flux(registre_df, "frais_banque", "negatif"),
            },
            "immobilier": {
                "charges_totales": _somme_flux(registre_df, "charges", "negatif") + _somme_flux(registre_df, "taxe_fonciere", "negatif"),
                "entretien_total": _somme_flux(registre_df, "entretien", "negatif"),
                "gestion_total": _somme_flux(registre_df, "gestion_locative", "negatif"),
            },
            "bourse": {
                "versements_totaux": versements_bourse,
                "valeur_finale": bourse_finale,
                "plus_value": bourse_finale - versements_bourse,
            },
        },
        "modules": modules,
    }
    return metriques
