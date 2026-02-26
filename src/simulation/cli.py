from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from .configuration import charger_configuration
from .moteur import OptionsDiagnostic, executer_simulation_depuis_config
from pdb import set_trace as breakpoint

application = typer.Typer(
    help="CLI du moteur de simulation de portefeuille.", invoke_without_command=True
)
console = Console()


def obtenir_racine_projet() -> Path:
    return Path(__file__).resolve().parents[2]


def chemin_parametres_defaut() -> Path:
    return obtenir_racine_projet() / "parametres.defaut.yaml"


def chemin_parametres_utilisateur() -> Path:
    return obtenir_racine_projet() / "parametres.utilisateur.yaml"


def _formater_montant_terminal(montant: float) -> str:
    couleur = "red" if montant < 0 else "green"
    return f"[{couleur}]{montant:,.2f} EUR[/{couleur}]".replace(",", " ")


def creer_dossier_sortie(
    sortie: Path | None,
    nom_run: str | None,
    horodatage: datetime | None = None,
) -> Path:
    if sortie is not None:
        return sortie

    instant = horodatage or datetime.now(ZoneInfo("Europe/Paris"))
    dossier = obtenir_racine_projet() / "sorties" / instant.strftime("%Y-%m-%d_%H%M%S")
    if nom_run:
        dossier = dossier.with_name(f"{dossier.name}_{nom_run}")
    return dossier


def lancer_simulation(
    parametres_defaut: Path | None,
    parametres_utilisateur: Path | None,
    sortie: Path | None,
    nom_run: str | None,
    diagnostic: bool,
    periode_debug: list[str] | None,
    csv: bool,
) -> None:
    chemin_defaut = parametres_defaut or chemin_parametres_defaut()
    chemin_utilisateur = parametres_utilisateur or chemin_parametres_utilisateur()

    try:
        if not chemin_defaut.exists():
            raise FileNotFoundError(
                f"Fichier de parametres par defaut introuvable: {chemin_defaut}"
            )

        dossier_sortie = creer_dossier_sortie(sortie=sortie, nom_run=nom_run)
        config = charger_configuration(chemin_defaut, chemin_utilisateur)
        periodes_debug = {pd.Period(p, freq="M") for p in (periode_debug or [])}
        resultat = executer_simulation_depuis_config(
            config,
            dossier_sortie,
            options_diagnostic=OptionsDiagnostic(actif=diagnostic, periodes_debug=periodes_debug),
            generer_csv=csv,
        )

        patrimoine = resultat.metriques.get("patrimoine_par_categorie", {})
        table = Table(title="Patrimoine final")
        table.add_column("Categorie")
        table.add_column("Montant", justify="right")
        table.add_row("Cash", _formater_montant_terminal(float(patrimoine.get("cash", 0.0))))
        table.add_row("Bourse", _formater_montant_terminal(float(patrimoine.get("bourse", 0.0))))
        table.add_row("Immobilier", _formater_montant_terminal(float(patrimoine.get("immobilier", 0.0))))
        table.add_row("Dettes", _formater_montant_terminal(float(patrimoine.get("dettes", 0.0))))
        table.add_section()
        table.add_row(
            "[bold]Total[/bold]",
            _formater_montant_terminal(float(resultat.metriques.get("patrimoine_total_final", 0.0))),
        )

        console.print(table)
        console.print("[green]Statut: OK[/green]")
    except Exception as erreur:  # noqa: BLE001
        console.print(f"[red]Statut: ERREUR - {erreur}[/red]")
        raise typer.Exit(code=1) from erreur


@application.callback(invoke_without_command=True)
def commande_principale(
    ctx: typer.Context,
    parametres_defaut: Path = typer.Option(None, "--parametres-defaut", "--defaut"),
    parametres_utilisateur: Path = typer.Option(None, "--parametres-utilisateur", "--utilisateur"),
    sortie: Path | None = typer.Option(None, "--sortie"),
    nom_run: str | None = typer.Option(None, "--nom-run"),
    diagnostic: bool = typer.Option(False, "--diagnostic"),
    periode_debug: list[str] = typer.Option([], "--periode-debug"),
    csv: bool = typer.Option(False, "--csv", help="Genere aussi les exports CSV (desactive par defaut)."),
) -> None:
    """Execute une simulation complete avec fusion defaut + utilisateur."""
    if ctx.invoked_subcommand is None:
        lancer_simulation(parametres_defaut, parametres_utilisateur, sortie, nom_run, diagnostic, periode_debug, csv)


@application.command("run")
def commande_run(
    parametres_defaut: Path = typer.Option(None, "--parametres-defaut", "--defaut"),
    parametres_utilisateur: Path = typer.Option(None, "--parametres-utilisateur", "--utilisateur"),
    sortie: Path | None = typer.Option(None, "--sortie"),
    nom_run: str | None = typer.Option(None, "--nom-run"),
    diagnostic: bool = typer.Option(False, "--diagnostic"),
    periode_debug: list[str] = typer.Option([], "--periode-debug"),
    csv: bool = typer.Option(False, "--csv", help="Genere aussi les exports CSV (desactive par defaut)."),
) -> None:
    """Alias explicite pour lancer la simulation."""
    lancer_simulation(parametres_defaut, parametres_utilisateur, sortie, nom_run, diagnostic, periode_debug, csv)


if __name__ == "__main__":
    application()
