from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.table import Table

from simulation.configuration import charger_configuration
from simulation.moteur import executer_simulation_depuis_config

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
) -> None:
    chemin_defaut = parametres_defaut or chemin_parametres_defaut()
    chemin_utilisateur = parametres_utilisateur or chemin_parametres_utilisateur()

    try:
        if not chemin_defaut.exists():
            raise FileNotFoundError(
                f"Fichier de paramètres par défaut introuvable: {chemin_defaut}"
            )

        dossier_sortie = creer_dossier_sortie(sortie=sortie, nom_run=nom_run)
        config = charger_configuration(chemin_defaut, chemin_utilisateur)
        resultat = executer_simulation_depuis_config(config, dossier_sortie)

        table = Table(title="Simulation terminée")
        table.add_column("Métrique")
        table.add_column("Valeur", justify="right")
        table.add_row(
            "Solde final trésorerie", f"{resultat.metriques['solde_final_tresorerie']:.2f}"
        )
        table.add_row("Flux net cumulé", f"{resultat.metriques['flux_net_cumule']:.2f}")

        console.print(f"Paramètres par défaut : [bold]{chemin_defaut}[/bold]")
        if chemin_utilisateur.exists():
            console.print(f"Paramètres utilisateur : [bold]{chemin_utilisateur}[/bold]")
        else:
            console.print(
                "Paramètres utilisateur : "
                f"[yellow]absent ({chemin_utilisateur}), utilisation des défauts uniquement[/yellow]"
            )
        console.print(f"Dossier de sortie : [bold]{dossier_sortie}[/bold]")
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
) -> None:
    """Exécute une simulation complète avec fusion défaut + utilisateur."""
    if ctx.invoked_subcommand is None:
        lancer_simulation(parametres_defaut, parametres_utilisateur, sortie, nom_run)


@application.command("run")
def commande_run(
    parametres_defaut: Path = typer.Option(None, "--parametres-defaut", "--defaut"),
    parametres_utilisateur: Path = typer.Option(None, "--parametres-utilisateur", "--utilisateur"),
    sortie: Path | None = typer.Option(None, "--sortie"),
    nom_run: str | None = typer.Option(None, "--nom-run"),
) -> None:
    """Alias explicite pour lancer la simulation."""
    lancer_simulation(parametres_defaut, parametres_utilisateur, sortie, nom_run)


if __name__ == "__main__":
    application()
