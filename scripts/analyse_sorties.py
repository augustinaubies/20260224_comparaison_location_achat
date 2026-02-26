from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml


def _periode(texte: str) -> pd.Period:
    return pd.Period(texte, freq='M')


def _maturites_emprunt(path_config: Path | None) -> dict[str, pd.Period]:
    if path_config is None:
        return {}
    data = yaml.safe_load(path_config.read_text())
    simulation_fin = _periode(data['simulation']['date_fin'])
    maturites: dict[str, pd.Period] = {}
    for module in data.get('modules', []):
        if module.get('type') == 'emprunt':
            debut = _periode(module['date_debut'])
            maturites[module['id']] = debut + (int(module['duree_mois']) - 1)
        if module.get('type') == 'immobilier_locatif':
            debut = _periode(module['date_achat'])
            duree = int(module['emprunt']['duree_mois'])
            maturites[module['id']] = debut + (duree - 1)
    maturites['__simulation_fin__'] = simulation_fin
    return maturites


def analyser_dossier(dossier: Path, path_config: Path | None = None) -> dict:
    synthese = pd.read_csv(dossier / 'synthese_mensuelle.csv')
    registre = pd.read_csv(dossier / 'registre.csv')
    rapport = json.loads((dossier / 'rapport.json').read_text())
    maturites = _maturites_emprunt(path_config)
    simulation_fin = maturites.get('__simulation_fin__')

    anomalies: list[str] = []

    if (synthese['solde_tresorerie'] < -1e-6).any():
        p = synthese.loc[synthese['solde_tresorerie'] < -1e-6, 'periode'].iloc[0]
        anomalies.append(f"Trésorerie négative dès {p}")

    if (registre['flux_de_tresorerie'].abs() > 1_000_000).any():
        p = registre.loc[registre['flux_de_tresorerie'].abs() > 1_000_000, 'periode'].iloc[0]
        anomalies.append(f"Flux > 1M détecté ({p})")

    doublons = registre.duplicated(subset=['periode', 'categorie', 'description', 'flux_de_tresorerie']).sum()
    if doublons:
        anomalies.append(f"Doublons de flux: {doublons}")

    for fichier in dossier.glob('etats_module_*_capital_restant_du.csv'):
        etat = pd.read_csv(fichier)
        if 'capital_restant_du' not in etat.columns:
            continue
        if (etat['capital_restant_du'] < -1e-6).any():
            p = etat.loc[etat['capital_restant_du'] < -1e-6, 'periode'].iloc[0]
            anomalies.append(f"CRD négatif ({fichier.name}) en {p}")
        diff = etat['capital_restant_du'].diff().fillna(0)
        if (diff > 1e-4).any():
            p = etat.loc[diff > 1e-4, 'periode'].iloc[0]
            anomalies.append(f"CRD non monotone ({fichier.name}) en {p}")

        module_id = fichier.name.replace('etats_module_', '').replace('_capital_restant_du.csv', '')
        maturite = maturites.get(module_id)
        if len(etat) and maturite is not None and simulation_fin is not None and maturite <= simulation_fin:
            if abs(etat['capital_restant_du'].iloc[-1]) > 5:
                anomalies.append(
                    f"CRD final non nul ({fichier.name}): {etat['capital_restant_du'].iloc[-1]:.2f}"
                )

    for fichier in dossier.glob('etats_module_*_valeur_bourse.csv'):
        etat = pd.read_csv(fichier)
        if (etat['valeur_bourse'] < -1e-6).any():
            p = etat.loc[etat['valeur_bourse'] < -1e-6, 'periode'].iloc[0]
            anomalies.append(f"Valeur bourse négative ({fichier.name}) en {p}")

    stats = registre['flux_de_tresorerie'].describe(percentiles=[0.01, 0.5, 0.99]).to_dict()
    return {
        'dossier': str(dossier),
        'solde_final_tresorerie': float(rapport.get('solde_final_tresorerie', 0.0)),
        'flux_net_cumule': float(rapport.get('flux_net_cumule', 0.0)),
        'nb_anomalies': len(anomalies),
        'anomalies': anomalies,
        'stats_flux': stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('dossier_sortie', type=Path)
    parser.add_argument('--config', type=Path, default=None)
    args = parser.parse_args()
    resultat = analyser_dossier(args.dossier_sortie, args.config)
    print(json.dumps(resultat, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
