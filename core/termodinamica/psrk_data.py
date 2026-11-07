"""
Pure-component records of the PSRK package (F8b, 6 November 2026).

PSRK needs, per species, the critical temperature and pressure, a vapour-pressure record on which its
Mathias-Copeman alpha function is regressed (core/termodinamica/psrk.py), and a PSRK UNIFAC group assignment.

Catalog species (core/catalogo via core/mezclas_datos) take T_c, P_c and the vapour-pressure record of the common
catalog, so the PSRK package and every other package of the layer share one pure-component basis. Their group
assignment is the DDBST PSRK assignment distributed with thermo 0.6.1 (identical to the original UNIFAC one for
every catalog species).

Light gases are not in the common catalog (core/catalogo.py is not Claude-owned) and the PSRK package is the
route by which they enter elevated-pressure equilibria. A record here serves only this package (like the solid
records of core/termodinamica/solid_data.py serve only the SLE operation):

  carbon dioxide (124-38-9): T_c = 304.1282 K, P_c = 7.3773 MPa and the vapour-pressure ancillary equation
      ln(P/P_c) = (T_c/T) sum_i a_i (1 - T/T_c)^t_i,  a = (-7.0602087, 1.9391218, -1.6463597, -3.2995634),
      t = (1, 1.5, 2, 4), valid from the triple point 216.592 K to T_c
      (Span and Wagner, J. Phys. Chem. Ref. Data 25 (1996) 1509, eq. 3.13 and Table 3). Checked here at the
      triple point (517.96 kPa against the reference 517.95 kPa). The DDBST PSRK assignment table has no entry
      for CO2 (the gas is its own group): the PSRK subgroup 117 'CO2' (main group 56) is declared.

A species with no record raises CubicOutOfScope (cause `no_pure_record`), never a default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from core.termodinamica.cubic_eos import CubicOutOfScope


@dataclass(frozen=True)
class PurePSRKRecord:
    cas: str
    name: str
    Tc: float                       # K
    Pc: float                       # Pa
    psat: Callable[[float], float]  # Pa, on [T_min, Tc]
    T_min: float                    # lowest temperature of the vapour-pressure record (K)
    groups: dict | None             # PSRK subgroup counts; None: DDBST PSRK assignment
    source: str


def _co2_psat(T):
    Tc, Pc = 304.1282, 7.3773e6
    tau = 1.0 - T / Tc
    a = (-7.0602087, 1.9391218, -1.6463597, -3.2995634)
    t = (1.0, 1.5, 2.0, 4.0)
    return Pc * math.exp(Tc / T * sum(ai * tau ** ti for ai, ti in zip(a, t)))


LIGHT_GASES = {
    "124-38-9": PurePSRKRecord(
        "124-38-9", "carbon dioxide", 304.1282, 7.3773e6, _co2_psat, 216.592, {117: 1},
        "Span and Wagner, J. Phys. Chem. Ref. Data 25 (1996) 1509: critical point and vapour-pressure "
        "ancillary eq. 3.13 (triple point 216.592 K to T_c); PSRK subgroup 117 (CO2) declared"),
}


def record(cas):
    """The PSRK pure-component record of `cas`: a light-gas record of this module or a catalog species."""
    if cas in LIGHT_GASES:
        return LIGHT_GASES[cas]
    from core import catalogo
    from core import mezclas_datos as datos
    if cas not in catalogo.REGISTRO:
        raise CubicOutOfScope(
            f"No PSRK pure-component record for {cas}: it is neither a light gas of psrk_data nor a catalog species.",
            cause="no_pure_record", cas=cas)
    e = datos.especie(cas)
    return PurePSRKRecord(cas, e.nombre, float(e.Tc), float(e.psat[5]), e.Psat, float(e.T_psat[0]), None,
                          f"common catalog ({e.psat_forma} vapour-pressure record, {e.T_psat[0]}-{e.T_psat[1]} K)")
