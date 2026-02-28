from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator


class ConfigurationSimulation(BaseModel):
    date_debut: str
    date_fin: str
    devise: str = "EUR"
    pas_de_temps: Literal["M"] = "M"
    mois_paiement_impot_revenu: int = Field(default=9, ge=1, le=12)


class ConfigurationHypotheses(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inflation_annuelle: float | dict[str, float] = 0.0
    croissance_salaire_annuelle: float | dict[str, float] = 0.0
    indexation_loyers_annuelle: float | dict[str, float] = 0.0
    revalorisation_immobiliere_annuelle: float | dict[str, float] = 0.0
    rendement_bourse_annuel: float | dict[str, float] = 0.0




def distributions_monte_carlo_par_defaut() -> dict[str, dict[str, float | None]]:
    return {
        "inflation_annuelle": {
            "moyenne": 0.02,
            "ecart_type": 0.002,
            "borne_min": -0.03,
            "borne_max": 0.15,
        },
        "croissance_salaire_annuelle": {
            "moyenne": 0.025,
            "ecart_type": 0.005,
            "borne_min": -0.05,
            "borne_max": 0.2,
        },
        "indexation_loyers_annuelle": {
            "moyenne": 0.018,
            "ecart_type": 0.006,
            "borne_min": -0.05,
            "borne_max": 0.2,
        },
        "revalorisation_immobiliere_annuelle": {
            "moyenne": 0.015,
            "ecart_type": 0.01,
            "borne_min": -0.15,
            "borne_max": 0.2,
        },
        "rendement_bourse_annuel": {
            "moyenne": 0.06,
            "ecart_type": 0.15,
            "borne_min": -0.9,
            "borne_max": 0.9,
        },
    }

class ConfigurationDistributionNormale(BaseModel):
    moyenne: float
    ecart_type: float = Field(ge=0.0)
    borne_min: float | None = None
    borne_max: float | None = None


class ConfigurationMonteCarlo(BaseModel):
    distributions: dict[str, ConfigurationDistributionNormale] = Field(
        default_factory=lambda: {
            cle: ConfigurationDistributionNormale(**distribution)
            for cle, distribution in distributions_monte_carlo_par_defaut().items()
        }
    )

    @model_validator(mode="before")
    @classmethod
    def completer_distributions_manquantes(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        defaults = distributions_monte_carlo_par_defaut()
        distributions = data.get("distributions")
        if not isinstance(distributions, dict):
            return {**data, "distributions": defaults}
        return {
            **data,
            "distributions": {
                **defaults,
                **distributions,
            },
        }


class ConfigurationComptePortefeuille(BaseModel):
    id: str
    type: Literal["cash", "pea", "cto", "pel", "livret"]
    livret_reglemente: Literal["livret_a", "ldds", "lep"] | None = None
    plafond_versement: float | None = Field(default=None, ge=0.0)
    fiscalite_plus_value_sortie: float | None = Field(default=None, ge=0.0, le=1.0)
    versements_autorises_apres_premier_retrait: bool = True
    pret_immobilier_autorise: bool = False

    @model_validator(mode="after")
    def appliquer_regles_par_type(self) -> "ConfigurationComptePortefeuille":
        if self.type != "livret" and self.livret_reglemente is not None:
            raise ValueError("Le champ 'livret_reglemente' est réservé aux comptes de type 'livret'")

        if self.type == "pea":
            if self.plafond_versement is None:
                self.plafond_versement = 150000.0
            if self.fiscalite_plus_value_sortie is None:
                self.fiscalite_plus_value_sortie = 0.0
            self.versements_autorises_apres_premier_retrait = False
        elif self.type == "cto":
            if self.fiscalite_plus_value_sortie is None:
                self.fiscalite_plus_value_sortie = 0.30
        elif self.type == "pel":
            if self.plafond_versement is None:
                self.plafond_versement = 61200.0
            self.pret_immobilier_autorise = True
            if self.fiscalite_plus_value_sortie is None:
                self.fiscalite_plus_value_sortie = 0.0
        elif self.type == "livret":
            if self.livret_reglemente is None:
                if self.id == "livret_a":
                    self.livret_reglemente = "livret_a"
                elif self.id == "ldds":
                    self.livret_reglemente = "ldds"

            if self.livret_reglemente == "livret_a" and self.plafond_versement is None:
                self.plafond_versement = 22950.0
            elif self.livret_reglemente == "ldds" and self.plafond_versement is None:
                self.plafond_versement = 12000.0
            elif self.livret_reglemente == "lep" and self.plafond_versement is None:
                self.plafond_versement = 10000.0

            if self.fiscalite_plus_value_sortie is None:
                self.fiscalite_plus_value_sortie = 0.0
            if self.fiscalite_plus_value_sortie != 0.0:
                raise ValueError("Les livrets réglementés doivent rester non fiscalisés en sortie")
        elif self.type == "cash":
            if self.fiscalite_plus_value_sortie is None:
                self.fiscalite_plus_value_sortie = 0.0
        return self


class ConfigurationPortefeuille(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tresorerie_initiale: float = 0.0
    bourse_initiale: float = 0.0
    comptes_definitions: list[ConfigurationComptePortefeuille] = Field(
        default_factory=lambda: [
            ConfigurationComptePortefeuille(id="cash", type="cash"),
            ConfigurationComptePortefeuille(id="courtier", type="cto"),
        ]
    )
    taux_investissement_restant: float = Field(default=1.0, ge=0.0, le=1.0)
    id_module_investissement_restant: str = "investissement_restant"
    compte_investissement_restant: str = "courtier"
    priorites_allocation_investissement: list[str] = Field(default_factory=list)
    loyer_residence_principale: float = Field(default=0.0, ge=0.0)
    reste_a_vivre_minimum: float = Field(default=0.0, ge=0.0)
    reste_a_vivre_mois_depenses: float = Field(default=0.0, ge=0.0)
    indexer_reste_a_vivre_sur_inflation: bool = True

    @field_validator("comptes_definitions")
    @classmethod
    def valider_ids_comptes_uniques(
        cls,
        comptes_definitions: list[ConfigurationComptePortefeuille],
    ) -> list[ConfigurationComptePortefeuille]:
        ids = [compte.id for compte in comptes_definitions]
        if len(ids) != len(set(ids)):
            raise ValueError("Les ids de comptes doivent être uniques")
        return comptes_definitions

    @model_validator(mode="after")
    def valider_coherence_comptes(self) -> "ConfigurationPortefeuille":
        comptes_connus = {compte.id for compte in self.comptes_definitions}
        if not self.priorites_allocation_investissement:
            non_cash = [compte.id for compte in self.comptes_definitions if compte.type != "cash"]
            self.priorites_allocation_investissement = non_cash or [self.compte_investissement_restant]

        inconnus = [compte for compte in self.priorites_allocation_investissement if compte not in comptes_connus]
        if inconnus:
            raise ValueError(
                "Les priorités d'allocation référencent des comptes inconnus: "
                + ", ".join(sorted(inconnus))
            )
        return self

    @property
    def comptes(self) -> list[str]:
        return [compte.id for compte in self.comptes_definitions]


class ConfigurationModuleBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str


class ConfigurationModuleFluxFixe(ConfigurationModuleBase):
    type: Literal["flux_fixe"]
    debut: str | None = None
    fin: str | None = None
    montant: float
    frequence: Literal["mensuelle"] = "mensuelle"
    sens: Literal["revenu", "depense"]
    categorie: str
    compte: str = "cash"
    indexation: Literal["aucune", "inflation", "croissance_salaire", "indexation_loyer"] = "aucune"
    periode_reference: str | None = None


class ConfigurationModuleEmprunt(ConfigurationModuleBase):
    type: Literal["emprunt"]
    date_debut: str
    capital: float = Field(gt=0.0)
    taux_annuel: float = Field(ge=0.0)
    duree_annees: PositiveInt
    taux_assurance_annuel: float = Field(default=0.0, ge=0.0)
    compte: str = "cash"

    @model_validator(mode="before")
    @classmethod
    def normaliser_duree_legacy(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalise = dict(data)
        if "duree_annees" not in normalise and "duree_mois" in normalise:
            duree_mois = normalise.pop("duree_mois")
            if int(duree_mois) % 12 != 0:
                raise ValueError("La durée legacy en mois doit être un multiple de 12")
            normalise["duree_annees"] = int(duree_mois) // 12
        return normalise


class ConfigurationEmpruntIntegree(BaseModel):
    taux_annuel: float = Field(ge=0.0)
    duree_annees: PositiveInt
    taux_assurance_annuel: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="before")
    @classmethod
    def normaliser_duree_legacy(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalise = dict(data)
        if "duree_annees" not in normalise and "duree_mois" in normalise:
            duree_mois = normalise.pop("duree_mois")
            if int(duree_mois) % 12 != 0:
                raise ValueError("La durée legacy en mois doit être un multiple de 12")
            normalise["duree_annees"] = int(duree_mois) // 12
        return normalise


class ConfigurationModuleImmobilierLocatif(ConfigurationModuleBase):
    type: Literal["immobilier_locatif"]
    date_achat: str
    prix: float = Field(gt=0.0)
    taux_frais_notaire: float = Field(default=0.0, ge=0.0)
    taux_travaux: float = Field(default=0.0, ge=0.0)
    apport: float = Field(ge=0.0)
    emprunt: ConfigurationEmpruntIntegree
    loyer_mensuel_initial: float = Field(ge=0.0)
    date_debut_location: str
    taux_vacance: float = Field(default=0.0, ge=0.0, le=1.0)
    charges_mensuelles: float = Field(default=0.0, ge=0.0)
    taxe_fonciere_annuelle: float = Field(default=0.0, ge=0.0)
    taux_entretien_annuel: float = Field(default=0.0, ge=0.0)
    taux_gestion_locative: float = Field(default=0.0, ge=0.0)
    compte: str = "cash"

    @model_validator(mode="after")
    def valider_apport(self) -> "ConfigurationModuleImmobilierLocatif":
        cout_total = self.prix + (self.prix * self.taux_frais_notaire) + (self.prix * self.taux_travaux)
        if self.apport > cout_total:
            raise ValueError("L'apport ne peut pas dépasser le coût total finançable")
        date_achat = datetime.strptime(self.date_achat, "%Y-%m")
        date_debut_location = datetime.strptime(self.date_debut_location, "%Y-%m")
        if date_debut_location < date_achat:
            raise ValueError("La date de début de location doit être postérieure ou égale à la date d'achat")
        return self


class ConfigurationModuleResidencePrincipale(ConfigurationModuleBase):
    type: Literal["residence_principale"]
    date_achat: str
    prix: float = Field(gt=0.0)
    taux_frais_notaire: float = Field(default=0.0, ge=0.0)
    frais_achat: float = Field(default=0.0, ge=0.0)
    taux_travaux: float = Field(default=0.0, ge=0.0)
    apport: float = Field(ge=0.0)
    taux_apport_patrimoine_financier: float = Field(default=0.0, ge=0.0, le=1.0)
    emprunt: ConfigurationEmpruntIntegree
    taxe_fonciere_annuelle: float = Field(default=0.0, ge=0.0)
    compte: str = "cash"

    @model_validator(mode="after")
    def valider_apport(self) -> "ConfigurationModuleResidencePrincipale":
        cout_total = self.prix + (self.prix * self.taux_frais_notaire) + self.frais_achat + (self.prix * self.taux_travaux)
        if self.apport > cout_total:
            raise ValueError("L'apport ne peut pas dépasser le coût total finançable")
        return self


ConfigurationModule = Annotated[
    ConfigurationModuleFluxFixe
    | ConfigurationModuleEmprunt
    | ConfigurationModuleImmobilierLocatif
    | ConfigurationModuleResidencePrincipale,
    Field(discriminator="type"),
]


class ConfigurationRacine(BaseModel):
    simulation: ConfigurationSimulation
    hypotheses: ConfigurationHypotheses = Field(default_factory=ConfigurationHypotheses)
    monte_carlo: ConfigurationMonteCarlo = Field(default_factory=ConfigurationMonteCarlo)
    portefeuille: ConfigurationPortefeuille = Field(default_factory=ConfigurationPortefeuille)
    modules: list[ConfigurationModule] = Field(default_factory=list)

    @field_validator("modules")
    @classmethod
    def valider_id_unique(cls, modules: list[ConfigurationModule]) -> list[ConfigurationModule]:
        ids = [module.id for module in modules]
        if len(ids) != len(set(ids)):
            raise ValueError("Chaque module doit avoir un id unique")
        return modules



def fusion_profonde(base: dict, surcharge: dict) -> dict:
    resultat = dict(base)
    for cle, valeur in surcharge.items():
        if cle in resultat and isinstance(resultat[cle], dict) and isinstance(valeur, dict):
            resultat[cle] = fusion_profonde(resultat[cle], valeur)
        else:
            resultat[cle] = valeur
    return resultat


def _obtenir_par_chemin_insensible_casse(donnees: object, chemin: str) -> object:
    courant = donnees
    for segment in chemin.split("."):
        if not isinstance(courant, dict):
            raise KeyError(chemin)
        correspondance = next((cle for cle in courant.keys() if str(cle).lower() == segment.lower()), None)
        if correspondance is None:
            raise KeyError(chemin)
        courant = courant[correspondance]
    return courant


def _resoudre_references_config(valeur: object, racine: dict) -> object:
    if isinstance(valeur, dict):
        return {cle: _resoudre_references_config(v, racine) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [_resoudre_references_config(v, racine) for v in valeur]
    if isinstance(valeur, str) and "." in valeur and valeur.strip() == valeur:
        try:
            cible = _obtenir_par_chemin_insensible_casse(racine, valeur)
        except KeyError:
            return valeur
        if isinstance(cible, (dict, list)):
            return valeur
        return cible
    return valeur



def charger_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    contenu = path.read_text(encoding="utf-8").strip()
    if not contenu:
        return {}
    data = yaml.safe_load(contenu)
    return data or {}



def charger_configuration(path_defaut: Path, path_utilisateur: Path) -> ConfigurationRacine:
    donnees_defaut = charger_yaml(path_defaut)
    donnees_utilisateur = charger_yaml(path_utilisateur)
    donnees_fusionnees = fusion_profonde(donnees_defaut, donnees_utilisateur)
    donnees_fusionnees = _resoudre_references_config(donnees_fusionnees, donnees_fusionnees)
    return ConfigurationRacine.model_validate(donnees_fusionnees)
