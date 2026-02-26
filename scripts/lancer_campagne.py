from __future__ import annotations

import json
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SCENARIOS = sorted((RACINE / 'scenarios').glob('*.yaml'))
SORTIE_CAMPAGNE = RACINE / 'sorties' / 'campagne'
SORTIE_CAMPAGNE.mkdir(parents=True, exist_ok=True)


def executer() -> None:
    resume = []
    for scenario in SCENARIOS:
        nom = scenario.stem.replace('parametres.defaut__', '')
        dossier = SORTIE_CAMPAGNE / nom
        if dossier.exists():
            for f in dossier.glob('*'):
                f.unlink()
        else:
            dossier.mkdir(parents=True)

        commande = [
            'python', '-m', 'src.simulation.cli',
            '--parametres-defaut', str(scenario),
            '--sortie', str(dossier),
        ]
        proc = subprocess.run(commande, cwd=RACINE, capture_output=True, text=True)
        statut = 'OK' if proc.returncode == 0 else 'ERREUR'
        entree = {
            'scenario': nom,
            'statut': statut,
            'commande': ' '.join(commande),
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
        }
        if statut == 'OK':
            analyse = subprocess.run(
                ['python', 'scripts/analyse_sorties.py', str(dossier), '--config', str(scenario), '--write-md'],
                cwd=RACINE,
                capture_output=True,
                text=True,
                check=True,
            )
            entree['analyse'] = json.loads(analyse.stdout)
        resume.append(entree)
        print(f"{nom}: {statut}")

    (RACINE / 'docs' / 'campagne_resultats.json').write_text(
        json.dumps(resume, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    kos = [
        r for r in resume
        if r.get('analyse', {}).get('verdict') == 'KO'
    ]
    top5 = sorted(
        kos,
        key=lambda r: abs(r.get('analyse', {}).get('solde_final_cash_recalcule', 0.0)),
        reverse=True,
    )[:5]
    (RACINE / 'docs' / 'campagne_top5_ko.json').write_text(
        json.dumps(top5, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print('Résultats: docs/campagne_resultats.json')
    print('Top5 KO: docs/campagne_top5_ko.json')


if __name__ == '__main__':
    executer()
