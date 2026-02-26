from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiagnosticScenario:
    nom: str
    chemin: Path
    patrimoine_total_final: float
    cash_final: float
    bourse_finale: float
    immobilier_total: float
    dettes_totales: float
    crd_modules: dict[str, float]
    biens: list[dict]
    versements_bourse: float
    plus_value_bourse: float
    drapeaux_ko: list[str]


def _float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def charger_rapport(rapport_path: Path) -> DiagnosticScenario:
    contenu = json.loads(rapport_path.read_text(encoding="utf-8"))
    modules = contenu.get("modules", {}) if isinstance(contenu.get("modules"), dict) else {}
    resume = contenu.get("resume", {}) if isinstance(contenu.get("resume"), dict) else {}

    crd_modules = {
        module_id: _float(module_data.get("crd_final"))
        for module_id, module_data in modules.items()
        if isinstance(module_data, dict) and "crd_final" in module_data
    }

    flux_bourse = contenu.get("flux_cumules", {}).get("bourse", {})
    versements_bourse = _float(flux_bourse.get("versements_totaux"))
    plus_value_bourse = _float(flux_bourse.get("plus_value"))

    diagnostic = DiagnosticScenario(
        nom=rapport_path.parent.name,
        chemin=rapport_path,
        patrimoine_total_final=_float(contenu.get("patrimoine_total_final")),
        cash_final=_float(contenu.get("cash_final")),
        bourse_finale=_float(contenu.get("bourse_finale")),
        immobilier_total=_float(contenu.get("immobilier_valeur_totale")),
        dettes_totales=_float(contenu.get("dettes_totales")),
        crd_modules=crd_modules,
        biens=resume.get("immobilier", []) if isinstance(resume.get("immobilier"), list) else [],
        versements_bourse=versements_bourse,
        plus_value_bourse=plus_value_bourse,
        drapeaux_ko=[],
    )

    if diagnostic.dettes_totales < -1e-6:
        diagnostic.drapeaux_ko.append("dettes_totales négatives")
    if any(crd < -1e-6 for crd in diagnostic.crd_modules.values()):
        diagnostic.drapeaux_ko.append("CRD module négatif")
    if diagnostic.bourse_finale < -1e-6:
        diagnostic.drapeaux_ko.append("bourse_finale négative")
    if diagnostic.plus_value_bourse > diagnostic.bourse_finale + 1e-6:
        diagnostic.drapeaux_ko.append("plus_value bourse > valeur finale")
    if diagnostic.cash_final < -50000 and diagnostic.bourse_finale > 0:
        diagnostic.drapeaux_ko.append("cash_final très négatif alors que la bourse est positive")
    if diagnostic.patrimoine_total_final < -1e-6 and diagnostic.dettes_totales <= 0:
        diagnostic.drapeaux_ko.append("patrimoine total négatif sans dette explicite")

    return diagnostic


def trouver_rapports(racine_sorties: Path) -> list[Path]:
    return sorted(racine_sorties.glob("**/rapport.json"))


def imprimer_tableau(diagnostics: list[DiagnosticScenario]) -> None:
    entete = (
        f"{'Scénario':<30} {'Patrimoine':>12} {'Cash':>12} {'Bourse':>12} "
        f"{'Immobilier':>12} {'Dettes':>10}  Statut"
    )
    print(entete)
    print("-" * len(entete))
    for d in diagnostics:
        statut = "OK" if not d.drapeaux_ko else f"KO ({'; '.join(d.drapeaux_ko)})"
        print(
            f"{d.nom:<30} {d.patrimoine_total_final:>12.2f} {d.cash_final:>12.2f} "
            f"{d.bourse_finale:>12.2f} {d.immobilier_total:>12.2f} {d.dettes_totales:>10.2f}  {statut}"
        )


def ecrire_markdown(diagnostics: list[DiagnosticScenario], output: Path) -> None:
    lignes = [
        "# Diagnostic des rapports de simulation",
        "",
        "| Scénario | Patrimoine final | Cash final | Bourse finale | Immobilier total | Dettes totales | CRD par module | Statut |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for d in diagnostics:
        crd = ", ".join(f"{k}: {v:.2f}" for k, v in sorted(d.crd_modules.items())) or "-"
        statut = "OK" if not d.drapeaux_ko else "KO: " + "; ".join(d.drapeaux_ko)
        lignes.append(
            f"| {d.nom} | {d.patrimoine_total_final:.2f} | {d.cash_final:.2f} | {d.bourse_finale:.2f} | "
            f"{d.immobilier_total:.2f} | {d.dettes_totales:.2f} | {crd} | {statut} |"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse rapide des rapport.json")
    parser.add_argument("--sorties", default="sorties", help="Dossier racine contenant les rapport.json")
    parser.add_argument("--output-md", default="docs/diagnostic_rapports_auto.md", help="Fichier Markdown de synthèse")
    args = parser.parse_args()

    rapports = trouver_rapports(Path(args.sorties))
    if not rapports:
        raise SystemExit("Aucun rapport.json trouvé")

    diagnostics = [charger_rapport(path) for path in rapports]
    imprimer_tableau(diagnostics)
    ecrire_markdown(diagnostics, Path(args.output_md))


if __name__ == "__main__":
    main()
