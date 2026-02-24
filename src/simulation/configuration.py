from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field, PositiveInt, field_validator, model_validator


class ConfigurationSimulation(BaseModel):
    date_debut: str
    date_fin: str
    devise: str = "EUR"
    pas_de_temps: Literal["M"] = "M"


class ConfigurationHypotheses(BaseModel):
    inflation: float = 0.0
    croissance_salaire: float = 0.0
    rendement_marche: float = 0.05


class ConfigurationPortefeuille(BaseModel):
    tresorerie_initiale: float = 0.0
    comptes: list[str] = Field(default_factory=lambda: ["cash", "courtier"])


class ConfigurationModuleBase(BaseModel):
    id: str
    type: str


class ConfigurationModuleFluxFixe(ConfigurationModuleBase):
    type: Literal["flux_fixe"]
    debut: str
    fin: str
    montant: float
    frequence: Literal["mensuelle"] = "mensuelle"
    sens: Literal["revenu", "depense"]
    categorie: str
    compte: str = "cash"


class ConfigurationModuleInvestissementDCA(ConfigurationModuleBase):
    type: Literal["investissement_dca"]
    debut: str
    fin: str
    versement_mensuel: float
    rendement_annuel_attendu: float = Field(ge=0.0)
    compte: str = "courtier"


class ConfigurationModuleEmprunt(ConfigurationModuleBase):
    type: Literal["emprunt"]
    date_debut: str
    capital: float = Field(gt=0.0)
    taux_annuel: float = Field(ge=0.0)
    duree_mois: PositiveInt
    assurance_mensuelle: float = Field(default=0.0, ge=0.0)
    compte: str = "cash"


class ConfigurationEmpruntIntegree(BaseModel):
    capital: float = Field(gt=0.0)
    taux_annuel: float = Field(ge=0.0)
    duree_mois: PositiveInt
    assurance_mensuelle: float = Field(default=0.0, ge=0.0)


class ConfigurationModuleImmobilierLocatif(ConfigurationModuleBase):
    type: Literal["immobilier_locatif"]
    date_achat: str
    prix: float = Field(gt=0.0)
    frais_notaire: float = Field(ge=0.0)
    budget_travaux: float = Field(default=0.0, ge=0.0)
    apport: float = Field(ge=0.0)
    emprunt: ConfigurationEmpruntIntegree
    loyer_mensuel: float = Field(ge=0.0)
    date_debut_location: str
    taux_vacance: float = Field(default=0.0, ge=0.0, le=1.0)
    charges_mensuelles: float = Field(default=0.0, ge=0.0)
    taxe_fonciere_annuelle: float = Field(default=0.0, ge=0.0)
    taux_entretien: float = Field(default=0.0, ge=0.0)
    taux_gestion: float = Field(default=0.0, ge=0.0)
    compte: str = "cash"

    @model_validator(mode="after")
    def valider_apport(self) -> "ConfigurationModuleImmobilierLocatif":
        if self.apport > self.prix:
            raise ValueError("L'apport ne peut pas dépasser le prix")
        return self


ConfigurationModule = Annotated[
    ConfigurationModuleFluxFixe
    | ConfigurationModuleInvestissementDCA
    | ConfigurationModuleEmprunt
    | ConfigurationModuleImmobilierLocatif,
    Field(discriminator="type"),
]


class ConfigurationRacine(BaseModel):
    simulation: ConfigurationSimulation
    hypotheses: ConfigurationHypotheses = Field(default_factory=ConfigurationHypotheses)
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
    return ConfigurationRacine.model_validate(donnees_fusionnees)
