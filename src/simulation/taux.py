from __future__ import annotations


def taux_mensuel_compose(taux_annuel: float) -> float:
    return (1 + float(taux_annuel)) ** (1 / 12) - 1
