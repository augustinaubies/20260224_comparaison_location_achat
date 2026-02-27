from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
import warnings

import yaml
from pydantic import BaseModel, Field, PositiveInt, field_validator, model_validator


class ConfigurationSimulation(BaseModel):
    date_debut: str
    date_fin: str
    devise: str = "EUR"
    pas_de_temps: Literal["M"] = "M"
    mois_paiement_impot_revenu: int = Field(default=9, ge=1, le=12)


class ConfigurationHypotheses(BaseModel):
    inflation_annuelle: float = 0.0
    croissance_salaire_annuelle: float = 0.0
    indexation_loyers_annuelle: float = 0.0
    revalorisation_immobiliere_annuelle: float = 0.0
    rendement_bourse_annuel: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def normaliser_cles_legacy(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalise = dict(data)
        correspondances = {
            "inflation": "inflation_annuelle",
            "croissance_salaire": "croissance_salaire_annuelle",
            "rendement_marche": "rendement_bourse_annuel",
        }
        for cle_legacy, cle_nouvelle in correspondances.items():
            if cle_legacy in normalise and cle_nouvelle not in normalise:
                normalise[cle_nouvelle] = normalise.pop(cle_legacy)
        return normalise


class ConfigurationPortefeuille(BaseModel):
    tresorerie_initiale: float = 0.0
    bourse_initiale: float = 0.0
    comptes: list[str] = Field(default_factory=lambda: ["cash", "courtier"])
    taux_investissement_restant: float = Field(default=1.0, ge=0.0, le=1.0)
    id_module_investissement_restant: str = "investissement_restant"
    compte_investissement_restant: str = "courtier"
    loyer_residence_principale: float = Field(default=0.0, ge=0.0)
    reste_a_vivre_minimum: float = Field(default=0.0, ge=0.0)
    reste_a_vivre_mois_depenses: float = Field(default=0.0, ge=0.0)
    indexer_reste_a_vivre_sur_inflation: bool = True


class ConfigurationModuleBase(BaseModel):
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
    modules = donnees_fusionnees.get("modules")
    if isinstance(modules, list):
        modules_filtres: list[dict] = []
        for module in modules:
            if not isinstance(module, dict):
                modules_filtres.append(module)
                continue
            if module.get("type") == "investissement_dca":
                warnings.warn(
                    "Le module 'investissement_dca' est déprécié et ignoré: utilisez uniquement l'investissement du restant.",
                    stacklevel=2,
                )
                continue
            if "ville" in module:
                warnings.warn(
                    f"Le champ 'ville' du module '{module.get('id', 'sans_id')}' est déprécié et ignoré.",
                    stacklevel=2,
                )
                module = dict(module)
                module.pop("ville", None)
            modules_filtres.append(module)
        donnees_fusionnees["modules"] = modules_filtres
    return ConfigurationRacine.model_validate(donnees_fusionnees)
