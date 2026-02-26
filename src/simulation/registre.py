from __future__ import annotations

import pandas as pd

COLONNES_REGISTRE = [
    "periode",
    "id_module",
    "type_module",
    "flux_de_tresorerie",
    "categorie",
    "compte",
    "description",
]



def normaliser_registre(df: pd.DataFrame) -> pd.DataFrame:
    resultat = df.copy()
    if "periode" not in resultat.columns:
        resultat = resultat.reset_index().rename(columns={"index": "periode"})
    resultat = resultat[COLONNES_REGISTRE]
    resultat["montant_abs"] = resultat["flux_de_tresorerie"].abs().round(6)
    resultat = resultat.sort_values(["periode", "id_module", "categorie"]).reset_index(drop=True)
    return resultat



def calculer_synthese_mensuelle(
    registre_df: pd.DataFrame,
    tresorerie_initiale: float,
    comptes_tresorerie: set[str] | None = None,
) -> pd.DataFrame:
    if registre_df.empty:
        return pd.DataFrame(columns=["periode", "flux_net", "solde_tresorerie"])
    flux_source = registre_df
    if comptes_tresorerie is not None:
        flux_source = registre_df[registre_df["compte"].isin(comptes_tresorerie)]
    flux = (
        flux_source.groupby("periode", as_index=True)["flux_de_tresorerie"]
        .sum()
        .rename("flux_net")
        .to_frame()
    )
    flux["solde_tresorerie"] = tresorerie_initiale + flux["flux_net"].cumsum()
    return flux.reset_index()
