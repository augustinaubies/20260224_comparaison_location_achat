# AGENTS.md

## 1. Rôle de l’agent

L'agent agit comme un agent d’exécution technique dans ce dépôt.  
Son objectif est de :

- Implémenter les tâches définies dans la to-do list.
- Corriger les bugs identifiés.
- Améliorer le code lorsque cela est justifié et traçable.

Il ne modifie pas l’architecture globale sans validation explicite via la to-do list.


---

## 2. Règles générales de travail

1. Toujours respecter la structure existante du projet.
2. Ne modifier que les fichiers strictement nécessaires à la tâche.
3. Ne jamais introduire de refactor massif non demandé.
4. Produire du code lisible, cohérent avec les conventions du dépôt.
5. Éviter les hypothèses implicites : toute hypothèse structurante doit être explicitée dans la to-do list.

Si une tâche ne peut pas être terminée proprement, ne pas forcer une implémentation partielle fragile.


---

## 3. Gestion de la to-do list

Lorsque l'agent n'est pas appelé spécifiquement pour réaliser une tâche non présente dans la TODO list, elle devient la source principale des tâches à réaliser par l’agent.

### 3.1 Sélection et exécution

- L'agent peut sélectionner librement une tâche qu’il estime faisable.
- Si la tâche est peu claire ou demande un travail important, il est intéressant de la diviser en sous-tâches, et donc d'en créer de nouvelles pour traiter le problème petit à petit.
- Les livrables d'une tâche ne sont pas forcément du code, tout dépend de la tâche.
- Une fois terminée complètement, il la coche comme terminée '[X]'. S'il identifie une tâche qui est déjà réalisée mais qui n'est pas notée comme terminée, alors il faut bien vérifier que tout est réspecté, et si c'est le cas, alors on peut la cocher comme terminée.
- Un court commentaire technique peut être ajouté sous la tâche pour résumer l’implémentation.
- Un setup complet de validation n'est pas nécessaire pour justifier la réalisation de tâches simples.

Une tâche n’est marquée '[X]' que si :
- L’implémentation est complète.
- Le code est cohérent et intégrable.
- Aucun point bloquant n’est laissé ouvert.
- Il n'y a pas de sous tâche non encore effectuée.

---

## 4. Ajout de nouvelles tâches

L'agent peut et doit ajouter des tâches dans la to-do list si :

- Il identifie un bug.
- Il détecte un point bloquant.
- Il repère une amélioration nécessaire mais non critique.
- Il constate une dette technique à traiter ultérieurement.

Les nouvelles tâches doivent être clairement décrites et autonomes.


---

## 5. Cas nécessitant des hypothèses ou décisions structurantes

Si la résolution d’une tâche nécessite :

- De nouvelles hypothèses impactant l’architecture,
- Une modification structurante de la logique métier,
- Un choix technique ayant plusieurs options significatives,

Alors :

1. Aucun code ne doit être modifié.
2. La tâche doit être annotée avec une section :
   - Hypothèses nécessaires
   - Questions à clarifier
3. Une nouvelle sous-tâche est alors créée : '[] Question utilisateur : choix technique...'

L’agent attend alors des réponses avant toute implémentation.


---

## 6. Discipline de modification

- Ne jamais modifier la to-do list pour masquer un problème.
- Ne jamais simplifier artificiellement une tâche pour la marquer comme terminée.
- Toute décision non triviale doit être explicitée.

La priorité est la robustesse et la traçabilité, pas la vitesse.