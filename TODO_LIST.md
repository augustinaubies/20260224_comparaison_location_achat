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
[X] Ajouter un reste à vivre suffisant, dépendant des dépenses mensuelles et loyer (mensualités etc) qui fait que l'on ne met pas en bourse l'intégralité du cash (aujourd'hui j'aime bien avoir environ 1000 euros sur mon compte courant, à potentiellement indexer sur l'inflation également).
  - Implémenté via `portefeuille.reste_a_vivre_minimum`, `portefeuille.reste_a_vivre_mois_depenses` et `portefeuille.indexer_reste_a_vivre_sur_inflation` : le sweep d'investissement n'utilise que le cash au-dessus du coussin cible.
[X] Le capital emprunté ne doit plus être un paramètre, il est calculé automatiquement.
  - Implémenté pour les modules immobiliers (RP et locatif) : capital d'emprunt calculé automatiquement depuis le coût finançable et l'apport, puis suppression du champ `capital` dans les exemples/configs.
[X] Paramètre de durée d'emprunt en années et non mois.
   - Implémenté via `duree_annees` dans la configuration, avec compatibilité legacy `duree_mois` (conversion uniquement si multiple de 12).
[] Modéliser les comptes PEA, PEL, livrets, CTO avec pour le moment chacun leur valeur limite et leur fonctionnement propre (plus de versements après le premier retrait du PEA, Emprunt possible lors d'achat avec le PEL, rien de particulier pour les livrets). Il faut que chacun soit imposé de la bonne manière (rien sur PEA et livrets, 30% flat sur le CTO). Il faut avoir un système de priorité sur les allocations : le reste à investir est alloué en fonction de ça. Et si rien n'est possible alors ça reste sur le compte courant.
[X] Faire en sorte que tous les facteurs (inflation, croissance des salaires, loyers, logements etc) ne soient pas considérés comme des constantes dans le code. En effet, l'objectif sera plus tard de faire des tirages aléatoires de tous ces paramètres. Il faut donc utiliser dans toutes les fonctions utilisatrices le facteur actuel. Et il faut donc corriger les fonctions qui calculent leur valeur actuelle en fonction de la valeur intiale avec un facteur constant : en effet on doit calculer la prochaine valeur à partir uniquement de la précédente et du facteur actuel à appliquer.
  - Implémenté via des hypothèses scalaires ou pilotées par période (`YYYY`/`YYYY-MM`) et des mises à jour incrémentales dans les modules (flux fixes, immobilier, bourse, loyer RP, IR indexé).
[X] Les tranches d'impôts doivent être indexés sur l'inflation.
  - Implémenté dans le calcul d'IR progressif avec indexation annuelle des bornes de tranches selon `hypotheses.inflation_annuelle`.
[] Une fois le moteur et les modules validés, il faudra faire un gros travail de modélisation sur les distributions de chacun des paramètres, afin de pouvoir faire des tirages aléatoires. Beaucoup de variables seront corrélées entre elles (surtout autour de l'inflation). Il faudra faire un travail important de data science sur ce sujet.
  [X] On peut commencer par définir des valeurs du bon ordre de grandeur pour des distributions des paramètres (par exemple inflation = N(mu=2%, sigma=0.2%)) afin de tester si tout fonctionne correctement.
    - Implémenté via `simulation.monte_carlo.DISTRIBUTIONS_PAR_DEFAUT` (normales tronquées) avec moyennes alignées sur la config et bornes de sécurité.
  [X] Tester de faire des tirages MC : définir le nombre à tirer, la graine initiale également.
    - Implémenté via la commande CLI `monte-carlo` (`--tirages`, `--graine`) et exports `monte_carlo_tirages.csv` / `monte_carlo_resume.csv`.
  [X] Mettre en place les tirages MC dans le paramétrage par défaut, et remplacer les paramètres constants par les distributions. Retirer les hypothèses en dur sur les distributions pour tout centraliser dans le fichier de paramètres.
    - Implémenté via `monte_carlo.distributions` (schéma typé dans la configuration) et consommation de ces distributions par le moteur Monte Carlo; le fichier `parametres.defaut.yaml` centralise désormais les lois.
  [] Il faut que les fonctions qui utilisent les paramètres variables n'aient pas l'information de comment les valeurs ont été obtenues. En effet, il faudra plus tard que les variables puissent suivre des lois de probabilités complexes, avec des correlations etc donc il faut que le workflow soit propre.