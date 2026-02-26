# Diagnostic des rapports de simulation

| Scénario | Patrimoine final | Cash final | Bourse finale | Immobilier total | Dettes totales | CRD par module | Statut |
|---|---:|---:|---:|---:|---:|---|---|
| default_run | -86067.94 | -251047.20 | 27746.58 | 181066.14 | 43833.47 | rp_1: 43833.47 | KO: cash_final très négatif alors que la bourse est positive |
| B01_bug2030_derniere_echeance | 1793365.03 | -45925.21 | 1577660.80 | 261629.44 | 0.00 | locatif_1: 0.00 | OK |
| B02_bug2030_taux_capital | 1637647.29 | -119752.72 | 1504725.28 | 252674.72 | 0.00 | locatif_1: 0.00 | KO: cash_final très négatif alors que la bourse est positive |
| B03_bug2030_decalage_debut | 1538075.74 | -252903.95 | 1669842.11 | 238228.48 | 117090.90 | locatif_1: 117090.90 | KO: cash_final très négatif alors que la bourse est positive |
| E01_6_mois | 833471.77 | 0.00 | 833471.77 | 0.00 | 0.00 | - | OK |
| E02_40_ans | 6389694.60 | -277627.08 | 6343283.53 | 324038.15 | 0.00 | locatif_1: 0.00 | KO: cash_final très négatif alors que la bourse est positive |
| E03_debut_milieu_annee | 1162120.16 | -25356.55 | 1096034.42 | 231605.99 | 140163.71 | locatif_1: 140163.71 | OK |
| E04_inflation_zero | 1641699.37 | -28504.43 | 1670203.81 | 0.00 | 0.00 | - | OK |
| E05_inflation_10 | 1390705.82 | -403532.62 | 1574238.44 | 220000.00 | 0.00 | locatif_1: 0.00 | KO: cash_final très négatif alors que la bourse est positive |
| E06_inflation_negative | 1645584.00 | -24974.71 | 1670558.71 | 0.00 | 0.00 | - | OK |
| E07_rendement_zero | 862775.46 | -32646.99 | 895422.45 | 0.00 | 0.00 | - | OK |
| E08_crash_marche | 142862.29 | -32646.99 | 175509.28 | 0.00 | 0.00 | - | OK |
| E09_emprunt_cher_apport_zero | 1335297.17 | -250352.40 | 1458503.95 | 250172.99 | 123027.38 | locatif_1: 123027.38 | KO: cash_final très négatif alors que la bourse est positive |
| E10_pas_invest | 862775.46 | 862775.46 | 0.00 | 0.00 | 0.00 | - | OK |
| E11_salaire_nul_periode | 1745087.33 | -25915.16 | 1771002.49 | 0.00 | 0.00 | - | OK |
| E12_depenses_sup_salaire | 948636.95 | -550944.41 | 1499581.36 | 0.00 | 0.00 | - | KO: cash_final très négatif alors que la bourse est positive |
| E13_loyer_nul_vacance_100 | 1385570.20 | -295743.40 | 1507656.75 | 249965.64 | 76308.79 | locatif_1: 76308.79 | KO: cash_final très négatif alors que la bourse est positive |
| E14_emprunt_5_ans | 1517650.87 | -102674.58 | 1370152.45 | 250172.99 | 0.00 | locatif_1: 0.00 | KO: cash_final très négatif alors que la bourse est positive |
| E15_emprunt_30_ans | 1513659.24 | -105523.06 | 1489701.62 | 250172.99 | 120692.32 | locatif_1: 120692.32 | KO: cash_final très négatif alors que la bourse est positive |
| S01_sans_immo | 1233605.14 | 1233605.14 | 0.00 | 0.00 | 0.00 | - | OK |
| S02_rp | 823630.83 | 624287.24 | 0.00 | 363285.02 | 163941.43 | rp_1: 163941.43 | OK |
| S03_locatif_seul | 1136955.79 | 963298.94 | 0.00 | 249965.64 | 76308.79 | locatif_1: 76308.79 | OK |
| S04_rp_puis_locatif | 1614523.52 | 1242333.63 | 0.00 | 537469.81 | 165279.92 | locatif_1: 73976.58, rp_1: 91303.35 | OK |
| S05_inflation_moderee | 1384294.17 | 1221472.29 | 0.00 | 247696.03 | 84874.15 | locatif_1: 84874.15 | OK |
