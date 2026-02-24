from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from simulation.moteur import executer_simulation

application = typer.Typer(help="CLI du moteur de simulation de portefeuille.")
console = Console()


@application.command("run")
def commande_run(
    defaut: Path = typer.Option(Path("parametres.defaut.yaml"), help="Fichier paramètres par défaut."),
    utilisateur: Path = typer.Option(
        Path("parametres.utilisateur.yaml"), help="Fichier paramètres utilisateur."
    ),
    sortie: Path = typer.Option(Path("resultats/run1"), help="Dossier de sortie des résultats."),
) -> None:
    """Exécute une simulation complète avec fusion défaut + utilisateur."""
    resultat = executer_simulation(defaut, utilisateur, sortie)
    table = Table(title="Simulation terminée")
    table.add_column("Métrique")
    table.add_column("Valeur", justify="right")
    table.add_row("Solde final trésorerie", f"{resultat.metriques['solde_final_tresorerie']:.2f}")
    table.add_row("Flux net cumulé", f"{resultat.metriques['flux_net_cumule']:.2f}")
    console.print(table)
    console.print(f"Résultats exportés dans : [bold]{sortie}[/bold]")


if __name__ == "__main__":
    application()
