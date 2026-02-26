from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml


TOLERANCE = 1e-6


def _periode(texte: str) -> pd.Period:
    return pd.Period(texte, freq="M")


def _charger_comptes(path_config: Path | None) -> tuple[list[str], set[str], float, dict[str, pd.Period]]:
    if path_config is None:
        return ["cash"], set(), 0.0, {}
    data = yaml.safe_load(path_config.read_text(encoding="utf-8"))
    portefeuille = data.get("portefeuille", {})
    comptes = portefeuille.get("comptes", ["cash"])
    compte_bourse_auto = portefeuille.get("compte_investissement_restant", "courtier")
    comptes_bourse = {compte_bourse_auto}
    for module in data.get("modules", []):
        if module.get("type") == "investissement_dca":
            comptes_bourse.add(module.get("compte", "courtier"))
    comptes_tresorerie = {c for c in comptes if c not in comptes_bourse} or ({comptes[0]} if comptes else {"cash"})

    maturites: dict[str, pd.Period] = {}
    for module in data.get("modules", []):
        if module.get("type") == "emprunt":
            debut = _periode(module["date_debut"])
            maturites[module["id"]] = debut + (int(module["duree_mois"]) - 1)
        if module.get("type") == "immobilier_locatif":
            debut = _periode(module["date_achat"])
            duree = int(module["emprunt"]["duree_mois"])
            maturites[module["id"]] = debut + (duree - 1)
    return list(comptes_tresorerie), comptes_bourse, float(portefeuille.get("tresorerie_initiale", 0.0)), maturites


def _top_flux(registre: pd.DataFrame, positif: bool) -> list[dict[str, float | str]]:
    if registre.empty:
        return []
    masque = registre["flux_de_tresorerie"] > 0 if positif else registre["flux_de_tresorerie"] < 0
    agg = (
        registre[masque]
        .groupby(["categorie", "id_module"], as_index=False)["flux_de_tresorerie"]
        .sum()
        .sort_values("flux_de_tresorerie", ascending=not positif)
        .head(20)
    )
    return [
        {
            "categorie": str(row["categorie"]),
            "id_module": str(row["id_module"]),
            "montant_cumule": float(row["flux_de_tresorerie"]),
        }
        for _, row in agg.iterrows()
    ]


def _analyser_emprunts(dossier: Path, maturites: dict[str, pd.Period]) -> list[dict]:
    rapports: list[dict] = []
    for fichier in sorted(dossier.glob("etats_module_*_capital_restant_du.csv")):
        etat = pd.read_csv(fichier)
        if etat.empty or "capital_restant_du" not in etat.columns:
            continue
        etat["periode"] = etat["periode"].astype(str)
        crd = etat["capital_restant_du"].astype(float)
        deltas = crd.diff().fillna(0.0)
        module_id = fichier.name.replace("etats_module_", "").replace("_capital_restant_du.csv", "")
        rapport = {
            "module": module_id,
            "crd_min": float(crd.min()),
            "mois_crd_min": str(etat.loc[crd.idxmin(), "periode"]),
            "delta_crd_max": float(deltas.max()),
            "delta_crd_min": float(deltas.min()),
            "crd_final": float(crd.iloc[-1]),
            "maturite_theorique": str(maturites[module_id]) if module_id in maturites else None,
            "anomalies": [],
        }
        if (crd < -TOLERANCE).any():
            idx = crd[crd < -TOLERANCE].index[0]
            rapport["anomalies"].append(f"CRD négatif dès {etat.loc[idx, 'periode']}")
        if (deltas > TOLERANCE).any():
            idx = deltas[deltas > TOLERANCE].index[0]
            rapport["anomalies"].append(f"CRD augmente en {etat.loc[idx, 'periode']}")
        rapports.append(rapport)
    return rapports


def _analyser_bourse(dossier: Path, registre: pd.DataFrame, comptes_bourse: set[str]) -> dict:
    versements_bourse = registre[registre["compte"].isin(comptes_bourse)].copy() if not registre.empty else pd.DataFrame()
    incoherences = []
    if not versements_bourse.empty and (versements_bourse["flux_de_tresorerie"] > TOLERANCE).any():
        idx = versements_bourse[versements_bourse["flux_de_tresorerie"] > TOLERANCE].index[0]
        incoherences.append(f"Flux positif sur compte bourse ({registre.loc[idx, 'periode']})")

    valeurs = []
    for fichier in sorted(dossier.glob("etats_module_*_valeur_bourse.csv")):
        etat = pd.read_csv(fichier)
        if etat.empty:
            continue
        colonne = [c for c in etat.columns if c != "periode"]
        if not colonne:
            continue
        col = colonne[0]
        min_val = float(etat[col].min())
        if min_val < -TOLERANCE:
            p = str(etat.loc[etat[col].idxmin(), "periode"])
            incoherences.append(f"Valeur bourse négative ({fichier.name}) en {p}")
        valeurs.append({"fichier": fichier.name, "min": min_val, "max": float(etat[col].max())})

    return {
        "flux_bourse_cumules": float(versements_bourse["flux_de_tresorerie"].sum()) if not versements_bourse.empty else 0.0,
        "valeurs": valeurs,
        "incoherences": incoherences,
    }


def analyser_dossier(dossier: Path, path_config: Path | None = None) -> dict:
    synthese = pd.read_csv(dossier / "synthese_mensuelle.csv")
    registre = pd.read_csv(dossier / "registre.csv")
    rapport_json = json.loads((dossier / "rapport.json").read_text(encoding="utf-8"))

    comptes_tresorerie, comptes_bourse, treso_initiale, maturites = _charger_comptes(path_config)

    if not registre.empty:
        registre["periode"] = registre["periode"].astype(str)
    if not synthese.empty:
        synthese["periode"] = synthese["periode"].astype(str)

    flux_cash = (
        registre[registre["compte"].isin(comptes_tresorerie)].groupby("periode", as_index=True)["flux_de_tresorerie"].sum()
        if not registre.empty else pd.Series(dtype=float)
    )
    flux_total = registre.groupby("periode", as_index=True)["flux_de_tresorerie"].sum() if not registre.empty else pd.Series(dtype=float)

    periodes = sorted(set(synthese.get("periode", [])) | set(flux_cash.index.astype(str)) | set(flux_total.index.astype(str)))
    treso = treso_initiale
    reconstruction = []
    rupture = None
    for periode in periodes:
        cash_debut = treso
        flux_mois = float(flux_cash.get(periode, 0.0))
        treso += flux_mois
        synthese_treso = float(synthese.loc[synthese["periode"] == periode, "solde_tresorerie"].iloc[0]) if (not synthese.empty and (synthese["periode"] == periode).any()) else None
        ecart = None if synthese_treso is None else float(treso - synthese_treso)
        if rupture is None and treso < -TOLERANCE:
            rupture = periode
        reconstruction.append({
            "periode": periode,
            "cash_debut": cash_debut,
            "flux_cash": flux_mois,
            "cash_fin_recalcule": treso,
            "solde_tresorerie_synthese": synthese_treso,
            "ecart_recalc_vs_synthese": ecart,
            "flux_total_registre": float(flux_total.get(periode, 0.0)),
        })

    recon_df = pd.DataFrame(reconstruction)
    if not recon_df.empty:
        recon_df.to_csv(dossier / "reconstruction_tresorerie.csv", index=False)

    doublons = (
        registre.groupby(["periode", "categorie", "flux_de_tresorerie", "description"], as_index=False)
        .size().query("size > 1") if not registre.empty else pd.DataFrame()
    )

    emprunts = _analyser_emprunts(dossier, maturites)
    bourse = _analyser_bourse(dossier, registre, comptes_bourse)

    anomalies: list[str] = []
    if rupture:
        anomalies.append(f"Trésorerie cash négative dès {rupture}")
    if not recon_df.empty and recon_df["ecart_recalc_vs_synthese"].abs().fillna(0.0).max() > 0.01:
        p = recon_df.loc[recon_df["ecart_recalc_vs_synthese"].abs().idxmax(), "periode"]
        anomalies.append(f"Synthèse trésorerie incohérente avec flux cash (écart max en {p})")
    if not doublons.empty:
        anomalies.append(f"Doublons suspects registre: {int(doublons['size'].sum() - len(doublons))}")
    for emp in emprunts:
        anomalies.extend(emp["anomalies"])
    anomalies.extend(bourse["incoherences"])

    verdict = "OK" if not anomalies else ("KO" if any("négative" in a or "incohérente" in a for a in anomalies) else "suspect")

    resultat = {
        "dossier": str(dossier),
        "verdict": verdict,
        "solde_final_tresorerie_rapport": float(rapport_json.get("solde_final_tresorerie", 0.0)),
        "solde_final_cash_recalcule": float(recon_df["cash_fin_recalcule"].iloc[-1]) if not recon_df.empty else treso_initiale,
        "mois_rupture_tresorerie": rupture,
        "anomalies": anomalies,
        "top_flux_negatifs": _top_flux(registre, positif=False),
        "top_flux_positifs": _top_flux(registre, positif=True),
        "doublons_suspects": doublons.to_dict(orient="records"),
        "emprunts": emprunts,
        "investissements": bourse,
        "sanity_stats_flux": registre["flux_de_tresorerie"].describe(percentiles=[0.01, 0.5, 0.99]).to_dict() if not registre.empty else {},
    }
    return resultat


def ecrire_rapport_markdown(resultat: dict, path_md: Path) -> None:
    lignes = [
        f"# Rapport scénario - {Path(resultat['dossier']).name}",
        "",
        f"**Verdict:** {resultat['verdict']}",
        f"**Mois de rupture trésorerie:** {resultat['mois_rupture_tresorerie'] or 'Aucun'}",
        f"**Solde final trésorerie (rapport):** {resultat['solde_final_tresorerie_rapport']:.2f}",
        f"**Solde final cash recalculé:** {resultat['solde_final_cash_recalcule']:.2f}",
        "",
        "## Anomalies",
    ]
    if resultat["anomalies"]:
        lignes.extend([f"- {a}" for a in resultat["anomalies"]])
    else:
        lignes.append("- Aucune anomalie détectée.")

    lignes.extend(["", "## Top flux négatifs (cumulés)"])
    for item in resultat["top_flux_negatifs"][:20]:
        lignes.append(f"- {item['categorie']} / {item['id_module']}: {item['montant_cumule']:.2f}")
    lignes.extend(["", "## Top flux positifs (cumulés)"])
    for item in resultat["top_flux_positifs"][:20]:
        lignes.append(f"- {item['categorie']} / {item['id_module']}: {item['montant_cumule']:.2f}")

    lignes.extend(["", "## Emprunts"])
    if resultat["emprunts"]:
        for emp in resultat["emprunts"]:
            lignes.append(
                f"- {emp['module']}: CRD min={emp['crd_min']:.2f} ({emp['mois_crd_min']}), "
                f"delta max={emp['delta_crd_max']:.2f}, CRD final={emp['crd_final']:.2f}"
            )
    else:
        lignes.append("- Aucun état emprunt détecté.")

    lignes.extend(["", "## Investissements"])
    lignes.append(f"- Flux cumulés comptes bourse: {resultat['investissements']['flux_bourse_cumules']:.2f}")
    for val in resultat["investissements"]["valeurs"]:
        lignes.append(f"- {val['fichier']}: min={val['min']:.2f}, max={val['max']:.2f}")

    lignes.extend(["", "## Hypothèse de cause"])
    if any("Synthèse trésorerie incohérente" in a for a in resultat["anomalies"]):
        lignes.append("- Bug moteur probable: agrégation de la trésorerie avec des flux non-cash (compte bourse).")
    elif resultat["mois_rupture_tresorerie"]:
        lignes.append("- Rupture principalement portée par les flux négatifs dominants listés ci-dessus.")
    else:
        lignes.append("- Aucune cause racine évidente détectée.")

    path_md.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dossier_sortie", type=Path)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--write-md", action="store_true")
    args = parser.parse_args()
    resultat = analyser_dossier(args.dossier_sortie, args.config)
    if args.write_md:
        ecrire_rapport_markdown(resultat, args.dossier_sortie / "rapport_scenario.md")
    print(json.dumps(resultat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
