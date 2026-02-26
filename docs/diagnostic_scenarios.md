# Diagnostic des scénarios (basé sur `rapport.json`)

## Démarche

- Exécution du scénario par défaut puis de tous les scénarios `scenarios/*.yaml` avec le runner CLI.
- Analyse systématique de `rapport.json` (patrimoine final + composantes cash/bourse/immobilier/dettes).
- Application d'heuristiques simples pour signaler des cas KO (cash très négatif, CRD négatif, dette négative, etc.).

## KO initiaux observés

### KO systémique identifié

- **Symptôme**: patrimoine immobilier final sous-évalué dans tous les scénarios avec immobilier (valeur figée au `prix` d'achat dans `rapport.json`).
- **Cause racine**: agrégation des métriques qui utilisait `module.prix` au lieu de l'état module `valeur_bien` en fin de simulation.
- **Correction appliquée**: calcul de la valeur immobilière finale à partir du dernier état `valeur_bien` (fallback sur `prix` si absent).

## Validation après correction

- **Statut final**: OK sur la cohérence structurelle du patrimoine (`cash + bourse + immobilier - dettes`) et des composantes (pas de dettes/CRD négatifs, pas de bourse négative).
- Les scénarios encore marqués KO par heuristique le sont sur le seul critère `cash_final très négatif alors que la bourse est positive`, ce qui est **explicable par le modèle courant** (investissement automatique du cash disponible sans mécanisme de désinvestissement en cas de déficit futur).

## Exemples avant/après (impact de la correction)

- `default_run`: immobilier total **150000.00 → 181066.14**.
- `S02_rp`: immobilier total **320000.00 → 363285.02**.
- `S04_rp_puis_locatif`: immobilier total **480000.00 → 537469.81**.

