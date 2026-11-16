"""F5 item 5 (claude-b, 16 November 2026): mu_i0(T) deduced from cp through the shared Model operations.

The F5-C1 water-gas-shift region (CO + H2O = CO2 + H2, ideal gas, 800 K, 1 bar) records, for CO, G = H - T S,
dH = T dS at P0, cp = dh/dT, the published Poling cp polynomial, two integrations with constants fixed at the
formation reference (Hf, S0 at 298.15 K), and evaluation at the region temperature
(tests/standard_potential_inputs.py). The reaction block admits the resulting g_i(T/Tref) only when it is
coefficient-identical to the executed provider mu_i0(T).

Independent references: a 50-digit mpmath evaluation of the cp integrals from the published data; the NIST
WebBook Shomate route of `thermo` (a different cp correlation and the same formation data) for Delta_r G0(T);
and the closed-form equimolar extent xi = (sqrt K - 1)/(sqrt K + 1).
"""
import copy

import mpmath as mp
import numpy as np
import pytest
import sympy as sp

from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.derived_graph import LoweringError
from core.mathematics.constants import si_magnitude
from core.reactions import chemical_equilibrium as ce
import standard_potential_inputs as S
from equilibrium_reaction_inputs import SPECIES, NU

mp.mp.dps = 50
R = mp.mpf('8.314462618')
T0 = mp.mpf('298.15')


def mu0_mp(cas, T):
    """Hf + R int_T0^T cp/R dT - T (S0 + R int_T0^T cp/(R T) dT) at 50 digits (published Poling and formation data)."""
    a = [mp.mpf(repr(v)) for v in S.poling(cas)]
    Hf, S0 = (mp.mpf(repr(v)) for v in S.formation(cas))
    T = mp.mpf(T)
    h = R * mp.fsum(c * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k, c in enumerate(a))
    s = R * (a[0] * mp.log(T / T0) + mp.fsum(c * (T**k - T0**k) / k for k, c in enumerate(a) if k))
    return Hf + h - T * (S0 + s)


@pytest.fixture(scope='module')
def deduced():
    model = S.deduced_author()
    system = DerivedSystem(copy.deepcopy(model))
    return {'model': model, 'system': system, 'result': resolve_system(system)}


def _rejected(model):
    with pytest.raises(LoweringError) as caught:
        DerivedSystem(model)
    return caught.value.diagnostics[0]


def test_deduced_standard_potentials_are_admitted_and_recorded(deduced):
    block = deduced['system'].algebraic_block
    assert sorted(block.deduced_standard) == [0]      # CO deduced from cp; H2O, CO2, H2 keep the F5-C1 form
    graph = deduced['system'].graph
    for key in block.deduced_standard.values():
        assert graph.nodes[key].rule == 'substitution'      # an operation output, never a declared formula


@pytest.mark.parametrize('T', [400., 600., 800., 1000.])
def test_recorded_relation_matches_the_50_digit_cp_integral(deduced, T):
    """The Model's own deduced relation, with its recorded data, evaluated at T against mpmath."""
    system = deduced['system']
    block = system.algebraic_block
    temperature = system._quantity(block.declaration['temperatureId'])
    data = {q: system.parameter_values[s] for q, s in system.parameter_symbols.items() if q != temperature}
    for i, key in block.deduced_standard.items():
        value = si_magnitude(system.graph.nodes[key].equation.rhs.xreplace({temperature: sp.Float(T)})).xreplace(data)
        assert abs(mp.mpf(str(sp.N(value, 30))) - mu0_mp(SPECIES[i], T)) <= mp.mpf('1e-9') * abs(mu0_mp(SPECIES[i], T))


@pytest.mark.parametrize('T', [400., 600., 800., 1000.])
def test_reaction_gibbs_energy_agrees_with_the_nist_shomate_route(T):
    """Delta_r G0(T) from the deduced form vs thermo's NIST WebBook Shomate cp (same formation data): the
    difference is the cp-correlation difference only (8 J/mol at 400 K, 125 J/mol at 1000 K)."""
    from chemicals import reaction as rx
    from thermo import HeatCapacityGas
    shomate = 0.
    for cas, nu in zip(SPECIES, NU):
        cp = HeatCapacityGas(CASRN=cas)
        cp.method = 'WEBBOOK_SHOMATE'
        shomate += nu * (rx.Hfg(cas) + cp.T_dependent_property_integral(298.15, T)
                         - T * (rx.S0g(cas) + cp.T_dependent_property_integral_over_T(298.15, T)))
    deduced_g = float(mp.fsum(nu * mu0_mp(cas, T) for cas, nu in zip(SPECIES, NU)))
    assert abs(deduced_g - shomate) <= 150.


def test_equilibrium_extent_matches_the_closed_form_root(deduced):
    """Equimolar feed, Delta n = 0: xi = (sqrt K - 1)/(sqrt K + 1), K = exp(-Delta_r G0 / R T) from mpmath."""
    result = deduced['result']
    assert result['estado'] == 'resuelto'
    K = mp.exp(-mp.fsum(nu * mu0_mp(cas, 800) for cas, nu in zip(SPECIES, NU)) / (R * 800))
    xi = (mp.sqrt(K) - 1) / (mp.sqrt(K) + 1)
    rows = {r['id']: r['valores'] for r in result['series']}
    entry = deduced['model']['motores']['equilibriumReactions']['volumes']['gas']
    amounts = np.array([rows['observable.' + qid][-1] for qid in entry['amountIds']])
    expected = np.array([float(1 + nu * xi) for nu in NU])
    np.testing.assert_allclose(amounts, expected, rtol=1e-9, atol=1e-10)
    gas = ce.IdealGasPhase(SPECIES)
    A, _ = ce.element_matrix(SPECIES)
    reference = ce.solve_extents(gas, [NU], [1, 1, 1, 1], 800, 1e5, A)['moles']
    np.testing.assert_allclose(amounts, reference, rtol=1e-8, atol=1e-9)


def _mutated(deduced, key, factor):
    model = copy.deepcopy(deduced['model'])
    declaration = model['datos']['standard.' + key]['declaracion']
    declaration['texto'] = repr(float(declaration['texto']) * factor)
    return model


def test_wrong_cp_coefficient_is_rejected_as_a_provider_mismatch(deduced):
    """A recorded cp coefficient 1 % off the published Poling value no longer equals the executed provider mu_i0(T)."""
    diagnostic = _rejected(_mutated(deduced, 'heatCapacityCoefficient1_1', 1.01))
    assert diagnostic['code'] == 'reaction_standard_potential_mismatch'


def test_wrong_formation_enthalpy_is_rejected_as_a_provider_mismatch(deduced):
    diagnostic = _rejected(_mutated(deduced, 'formationEnthalpy1', 1.001))
    assert diagnostic['code'] == 'reaction_standard_potential_mismatch'
