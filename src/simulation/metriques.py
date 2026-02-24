from __future__ import annotations

import pandas as pd



def calculer_metriques(
    registre_df: pd.DataFrame,
    synthese_df: pd.DataFrame,
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]],
) -> dict[str, float | dict[str, float]]:
    flux_par_module = (
        registre_df.groupby("id_module", as_index=True)["flux_de_tresorerie"].sum().to_dict()
    )
    solde_final = float(synthese_df["solde_tresorerie"].iloc[-1]) if not synthese_df.empty else 0.0
    flux_cumule = float(synthese_df["flux_net"].sum()) if not synthese_df.empty else 0.0
    metriques: dict[str, float | dict[str, float]] = {
        "solde_final_tresorerie": solde_final,
        "flux_net_cumule": flux_cumule,
        "flux_cumule_par_module": {k: float(v) for k, v in flux_par_module.items()},
    }

    for id_module, etats in etats_par_module.items():
        if "interets_payes" in etats:
            interets = etats["interets_payes"]
            if isinstance(interets, pd.Series):
                metriques[f"{id_module}.interets_totaux"] = float(interets.sum())
        if "loyers_bruts" in etats and "charges_totales" in etats and "revenu_net_exploitation" in etats:
            loyers = etats["loyers_bruts"]
            charges = etats["charges_totales"]
            noi = etats["revenu_net_exploitation"]
            if isinstance(loyers, pd.Series) and isinstance(charges, pd.Series) and isinstance(noi, pd.Series):
                metriques[f"{id_module}.loyers_bruts_totaux"] = float(loyers.sum())
                metriques[f"{id_module}.charges_totales"] = float(charges.sum())
                metriques[f"{id_module}.noi_total"] = float(noi.sum())

    return metriques
