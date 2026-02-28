# Règles PEL minimales (version simplifiée)

Ce document fixe le cadre **minimal** à respecter pour la modélisation du PEL avant d'implémenter un prêt bonifié complet.

## 1) Objectif de la modélisation PEL (phase actuelle)

Le PEL est modélisé comme un compte d'épargne plafonné, non fiscalisé à la sortie dans cette simulation simplifiée, et identifié comme source potentielle d'un prêt immobilier ultérieur.

## 2) Règles minimales retenues

1. **Plafond de versement**
   - Le plafond de versement est fixé à **61 200 €** par défaut.
   - Aucun versement ne doit pouvoir dépasser ce plafond cumulé.

2. **Éligibilité prêt immobilier (drapeau simplifié)**
   - Le compte PEL expose `pret_immobilier_autorise = true`.
   - En phase actuelle, ce drapeau sert uniquement à exprimer la capacité théorique de mobiliser un prêt adossé au PEL.

3. **Fiscalité simplifiée de sortie**
   - La fiscalité des sorties PEL est fixée à **0.0** dans le modèle actuel.
   - Cette hypothèse est volontairement simplifiée pour éviter d'introduire un modèle fiscal incomplet tant que les règles de retrait détaillées ne sont pas implémentées.

## 3) Hors périmètre explicite (prochaine itération)

Les points suivants sont identifiés mais non implémentés à ce stade :

- calcul des droits à prêt à partir de la phase d'épargne ;
- taux du prêt PEL selon la génération du plan ;
- conditions d'ancienneté et de maintien des versements ;
- interaction détaillée avec les financements RP/locatif.

## 4) Impact attendu sur la TODO

Cette clarification permet de lancer ensuite une tâche dédiée « prêt bonifié PEL » avec un périmètre explicite et testable, sans ambiguïté fonctionnelle.
