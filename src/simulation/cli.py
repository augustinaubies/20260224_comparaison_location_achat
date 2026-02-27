from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import typer
import yaml
from rich.console import Console
from rich.table import Table

from .configuration import ConfigurationRacine, charger_configuration
from .moteur import OptionsDiagnostic, executer_simulation_depuis_config
from .monte_carlo import executer_simulations_monte_carlo

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
        exporter_parametrage_simulation(
            dossier_sortie=dossier_sortie,
            chemin_parametres_defaut=chemin_defaut,
            chemin_parametres_utilisateur=chemin_utilisateur,
            config=config,
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


def exporter_parametrage_simulation(
    dossier_sortie: Path,
    chemin_parametres_defaut: Path,
    chemin_parametres_utilisateur: Path,
    config: ConfigurationRacine,
) -> None:
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    if chemin_parametres_defaut.exists():
        (dossier_sortie / "parametres.defaut.yaml").write_text(
            chemin_parametres_defaut.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    if chemin_parametres_utilisateur.exists():
        (dossier_sortie / "parametres.utilisateur.yaml").write_text(
            chemin_parametres_utilisateur.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    (dossier_sortie / "parametres.fusionnes.yaml").write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


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


@application.command("monte-carlo")
def commande_monte_carlo(
    parametres_defaut: Path = typer.Option(None, "--parametres-defaut", "--defaut"),
    parametres_utilisateur: Path = typer.Option(None, "--parametres-utilisateur", "--utilisateur"),
    sortie: Path | None = typer.Option(None, "--sortie"),
    nom_run: str | None = typer.Option("monte-carlo", "--nom-run"),
    tirages: int = typer.Option(200, "--tirages", min=1),
    graine: int = typer.Option(42, "--graine"),
) -> None:
    """Lance plusieurs simulations avec des hypothèses tirées aléatoirement."""
    chemin_defaut = parametres_defaut or chemin_parametres_defaut()
    chemin_utilisateur = parametres_utilisateur or chemin_parametres_utilisateur()

    try:
        if not chemin_defaut.exists():
            raise FileNotFoundError(f"Fichier de parametres par defaut introuvable: {chemin_defaut}")

        dossier_sortie = creer_dossier_sortie(sortie=sortie, nom_run=nom_run)
        config = charger_configuration(chemin_defaut, chemin_utilisateur)
        resume_df = executer_simulations_monte_carlo(
            config=config,
            dossier_sortie=dossier_sortie,
            nombre_tirages=tirages,
            graine=graine,
        )
        exporter_parametrage_simulation(
            dossier_sortie=dossier_sortie,
            chemin_parametres_defaut=chemin_defaut,
            chemin_parametres_utilisateur=chemin_utilisateur,
            config=config,
        )

        moyenne = float(resume_df["patrimoine_total_final"].mean())
        p10 = float(resume_df["patrimoine_total_final"].quantile(0.10))
        p90 = float(resume_df["patrimoine_total_final"].quantile(0.90))

        table = Table(title=f"Monte Carlo ({tirages} tirages)")
        table.add_column("Métrique")
        table.add_column("Valeur", justify="right")
        table.add_row("Patrimoine moyen", _formater_montant_terminal(moyenne))
        table.add_row("Patrimoine P10", _formater_montant_terminal(p10))
        table.add_row("Patrimoine P90", _formater_montant_terminal(p90))
        console.print(table)
        console.print("[green]Statut: OK[/green]")
    except Exception as erreur:  # noqa: BLE001
        console.print(f"[red]Statut: ERREUR - {erreur}[/red]")
        raise typer.Exit(code=1) from erreur


if __name__ == "__main__":
    application()
