from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class AnomalieInvariant:
    periode: str
    invariant: str
    valeur: float
    attendu: str
    details: str


def determiner_comptes_tresorerie(comptes: list[str], comptes_bourse: set[str]) -> set[str]:
    comptes_tresorerie = {compte for compte in comptes if compte not in comptes_bourse}
    if not comptes_tresorerie and comptes:
        return {comptes[0]}
    return comptes_tresorerie


def verifier_invariants(
    calendrier: pd.PeriodIndex,
    registre_df: pd.DataFrame,
    etats_par_module: dict[str, dict[str, pd.Series | pd.DataFrame]],
    tresorerie_initiale: float,
    comptes_tresorerie: set[str],
    mode_strict: bool = False,
) -> list[AnomalieInvariant]:
    anomalies: list[AnomalieInvariant] = []

    flux_cash = (
        registre_df[registre_df["compte"].isin(comptes_tresorerie)]
        .groupby("periode", as_index=True)["flux_de_tresorerie"]
        .sum()
        if not registre_df.empty
        else pd.Series(dtype=float)
    )

    tresorerie = tresorerie_initiale
    for periode in calendrier:
        flux = float(flux_cash.get(periode, 0.0))
        tresorerie_fin = tresorerie + flux
        if tresorerie_fin < -1e-6:
            anomalies.append(
                AnomalieInvariant(
                    periode=str(periode),
                    invariant="tresorerie_non_negative",
                    valeur=tresorerie_fin,
                    attendu=">= 0",
                    details="La trésorerie de fin de mois est négative.",
                )
            )
        tresorerie = tresorerie_fin

    duplicats = (
        registre_df.groupby(["periode", "categorie", "description", "montant_abs"], as_index=False)
        .size()
        .query("size > 1")
        if not registre_df.empty
        else pd.DataFrame()
    )
    for _, duplicat in duplicats.iterrows():
        anomalies.append(
            AnomalieInvariant(
                periode=str(duplicat["periode"]),
                invariant="doublon_flux",
                valeur=float(duplicat["size"]),
                attendu="1",
                details=(
                    f"Doublon détecté pour {duplicat['categorie']} / {duplicat['description']} "
                    f"(montant absolu {duplicat['montant_abs']})."
                ),
            )
        )

    for id_module, etats in etats_par_module.items():
        if "capital_restant_du" in etats:
            crd = etats["capital_restant_du"]
            principal = etats.get("capital_rembourse")
            if isinstance(crd, pd.Series):
                if (crd < -1e-6).any():
                    periode = str(crd[crd < -1e-6].index[0])
                    anomalies.append(
                        AnomalieInvariant(
                            periode=periode,
                            invariant="crd_non_negatif",
                            valeur=float(crd[crd < -1e-6].iloc[0]),
                            attendu=">= 0",
                            details=f"CRD négatif pour le module {id_module}.",
                        )
                    )
                if not crd.empty:
                    variations = crd.diff().dropna()
                    if (variations > 1e-6).any():
                        periode = str(variations[variations > 1e-6].index[0])
                        anomalies.append(
                            AnomalieInvariant(
                                periode=periode,
                                invariant="crd_monotone",
                                valeur=float(variations[variations > 1e-6].iloc[0]),
                                attendu="<= 0",
                                details=f"CRD augmente pour le module {id_module}.",
                            )
                        )
            if isinstance(principal, pd.Series) and (principal < -1e-6).any():
                periode = str(principal[principal < -1e-6].index[0])
                anomalies.append(
                    AnomalieInvariant(
                        periode=periode,
                        invariant="principal_non_negatif",
                        valeur=float(principal[principal < -1e-6].iloc[0]),
                        attendu=">= 0",
                        details=f"Amortissement négatif pour le module {id_module}.",
                    )
                )

        if "valeur_bourse" in etats:
            valeur = etats["valeur_bourse"]
            if isinstance(valeur, pd.Series) and (valeur < -1e-6).any():
                periode = str(valeur[valeur < -1e-6].index[0])
                anomalies.append(
                    AnomalieInvariant(
                        periode=periode,
                        invariant="valeur_bourse_non_negative",
                        valeur=float(valeur[valeur < -1e-6].iloc[0]),
                        attendu=">= 0",
                        details=f"Valeur bourse négative pour le module {id_module}.",
                    )
                )

    if mode_strict and anomalies:
        messages = "; ".join(f"{a.periode}:{a.invariant}" for a in anomalies[:5])
        raise ValueError(f"Invariants violés: {messages}")

    return anomalies
