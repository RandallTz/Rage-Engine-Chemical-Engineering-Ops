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

Ideal-gas caloric records of the light gases (F8b, 7 November 2026). The layer always publishes H and U, so a
light gas needs the ideal-gas part of the same reference as every mixture package (core/mezclas_datos: h = 0 and
s = 0 of the pure ideal gas at T0 = 298.15 K, P0 = 1e5 Pa). The record takes the same form and source as the
catalog species: cp_ig/R = a0 + a1 T + a2 T^2 + a3 T^3 + a4 T^4 of Poling, Prausnitz and O'Connell, The Properties
of Gases and Liquids 5th ed., appendix A (chemicals Cp_data_Poling), and h, s, g by the catalog's own integrals
(mezclas_datos.Especie), so there is one reference formula:

  carbon dioxide (124-38-9): a = (3.259, 1.356e-3, 1.502e-5, -2.374e-8, 1.056e-11), 50-1000 K. Checked against
      the NIST-JANAF table C-095 (Chase, J. Phys. Chem. Ref. Data Monograph 9, 1998; standard state 1 bar):
      200-1000 K, cp within 1.7 %, H - H(298.15 K) within 0.16 kJ/mol and S - S(298.15 K) within 0.19 J/(mol K)
      (tests/test_psrk_mixture.py, IdealGasCalorics).

A light gas without a caloric record raises CubicOutOfScope (cause `no_ideal_gas_record`) in caloric operations, and
a temperature outside the record's range raises cause `outside_ideal_gas_range`; neither has a default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from core import mezclas_datos as _datos
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


@dataclass(frozen=True)
class IdealGasRecord:
    """Ideal-gas caloric record of a light gas: cp_ig/R = sum a_k T^k on T_cp, on the reference of mezclas_datos."""
    cas: str
    cp: tuple                       # (a0..a4), cp/R = sum a_k T^k
    T_cp: tuple                     # (T_min, T_max) of the polynomial, K
    source: str

    # the catalog's own integrals (they read only self.cp): one reference formula for every package
    cp_ig = _datos.Especie.cp_ig
    h_ig = _datos.Especie.h_ig
    s_ig0 = _datos.Especie.s_ig0
    g_ig0 = _datos.Especie.g_ig0


@lru_cache(maxsize=None)
def ideal_gas_record(cas):
    """Ideal-gas caloric record of a light gas of this module (Poling appendix A, as for catalog species)."""
    if cas not in LIGHT_GASES:
        raise CubicOutOfScope(f"No ideal-gas caloric record for the light gas {cas}.", cause="no_ideal_gas_record",
                              species=[cas])
    import chemicals.heat_capacity as hc
    with _datos.CARGA_DATOS:
        c = hc.Cp_data_Poling.loc[cas]
    return IdealGasRecord(cas, tuple(float(c[k]) for k in ("a0", "a1", "a2", "a3", "a4")),
                          (float(c.Tmin), float(c.Tmax)),
                          "Poling, Prausnitz and O'Connell, The Properties of Gases and Liquids 5th ed., appendix A "
                          "(chemicals Cp_data_Poling)")


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
