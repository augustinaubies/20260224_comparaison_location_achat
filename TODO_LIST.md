# TODO_LIST.md

> Règles d’usage (résumé) :
> - Une tâche n’est cochée `[X]` que si elle est **totalement** terminée et qu’il ne reste **aucune** sous-tâche ouverte.
> - Si une tâche nécessite une décision / hypothèse structurante : **pas de code**, ajouter une sous-tâche `[] Question utilisateur : ...`.

---

[X] Faire en sorte de sauvegarder le paramétrage avec les résultats.
  - Implémenté dans la CLI: export automatique de `parametres.defaut.yaml`, `parametres.utilisateur.yaml` (si présent) et `parametres.fusionnes.yaml` dans chaque dossier de sortie.
[X] Vérifier que les paramètres qui varient dans le temps ont des temps de variations cohérents (annuels pour le salaire et les loyers, mensuels pour le prix de l'immobilier l'inflation etc).
  [X] Considérer que les augmentations annuelles sont effectuées au 1er janvier.
  - Implémenté via une revalorisation par palier annuel pour les salaires et loyers (`flux_fixe`, locatif, loyer de RP), en conservant une composition mensuelle pour l'inflation, la revalorisation immobilière et la bourse.
[] Ajouter un reste à vivre suffisant, dépendant des dépenses mensuelles et loyer (mensualités etc) qui fait que l'on ne met pas en bourse l'intégralité du cash (aujourd'hui j'aime bien avoir environ 1000 euros sur mon compte courant, à potentiellement indexer sur l'inflation également).
[] Le capital emprunté ne doit plus être un paramètre, il est calculé automatiquement.
[X] Paramètre de durée d'emprunt en années et non mois.
   - Implémenté via `duree_annees` dans la configuration, avec compatibilité legacy `duree_mois` (conversion uniquement si multiple de 12).
[] Modéliser les comptes PEA, PEL, livrets, CTO avec pour le moment chacun leur valeur limite et leur fonctionnement propre (plus de versements après le premier retrait du PEA, Emprunt possible lors d'achat avec le PEL, rien de particulier pour les livrets). Il faut que chacun soit imposé de la bonne manière (rien sur PEA et livrets, 30% flat sur le CTO). Il faut avoir un système de priorité sur les allocations : le reste à investir est alloué en fonction de ça. Et si rien n'est possible alors ça reste sur le compte courant.
[] Les tranches d'impôts doivent être indexés sur l'inflation.
[] Une fois le moteur et les modules validés, il faudra faire un gros travail de modélisation sur les distributions de chacun des paramètres, afin de pouvoir faire des tirages aléatoires. Beaucoup de variables seront corrélées entre elles (surtout autour de l'inflation). Il faudra faire un travail important de data science sur ce sujet.
