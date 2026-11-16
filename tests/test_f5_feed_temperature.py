"""F5 item 2 (claude-b, 15 November 2026): the feed-temperature initialization primitive of a coupled region.

A thermally coupled equilibrium region (B3 part 2) is initialized by its enthalpy inventory H(0). For a closed,
adiabatic, isobaric region fed with the unreacted inventory n_ref at the feed temperature T_f, the recorded energy
balance dH/dt = 0 carries H(0) = H(T_f, P, n_ref) unchanged into the equilibrated state at t0, where the extents
and T follow from {g(xi) = 0, H(T, P, n_ref + N xi) = H(0)}. The region's own package closure already provides
H(T_f, P, n) (PackageClosure.initial_energy, the routine that reproduces a temperature datum). This test checks
that primitive at the unreacted feed against the independent 50-digit enthalpy of
tests/equilibrium_reaction_liquid_inputs.py (mpmath pure liquid + thermo UNIFAC H^E) and the ideal-gas mixture.

Admitting a feed-temperature datum in the selection needs a hook in core/compilador/derived.py
(_initial_conditions), which is recorded in docs/engine/multiphysics-roadmap.md (F5) and not edited here.
"""
import copy

import mpmath as mp
import pytest

from core.compilador.derived import DerivedSystem
import equilibrium_reaction_liquid_inputs as L

LIQUID_P, GAS_P = 101325., 2e4
LIQUID_N0 = (1, 1, 0, 0)


@pytest.fixture(scope='module')
def liquid_closure():
    H0 = float(L.liquid_enthalpy(L.SPECIES, LIQUID_N0, 340., LIQUID_P, 'original'))
    xi, _ = L.coupled_liquid_reference(L.SPECIES, L.NU, LIQUID_N0, H0, LIQUID_P, 'original', (.63, 350))
    model = L.thermal_author('liquid', L.SPECIES, L.NU, LIQUID_N0, 'unifac-original', 'liquid', 'liquid', LIQUID_P, H0,
                             (330, 370), (float(xi) - .02, float(xi) + .02), float(xi) + .005)
    system = DerivedSystem(copy.deepcopy(model))
    return system.closures[0]


@pytest.fixture(scope='module')
def gas_closure():
    H0 = float(L.gas_enthalpy(L.VAPOUR, L.VAPOUR_REFERENCE, 360.))
    xi, _ = L.coupled_gas_reference(L.VAPOUR, L.VAPOUR_NU, L.VAPOUR_REFERENCE, H0, GAS_P, (.99, 400))
    model = L.thermal_author('gas', L.VAPOUR, L.VAPOUR_NU, L.VAPOUR_REFERENCE, 'unifac-original', 'vapor', 'gas', GAS_P, H0,
                             (370, 430), (float(xi) - 5e-4, float(xi) + 4e-4), float(xi), state_width=1e-6, step_tolerance=1e-15)
    system = DerivedSystem(copy.deepcopy(model))
    return system.closures[0]


@pytest.mark.parametrize('feed_T', [335., 340., 345.])
def test_liquid_feed_enthalpy_matches_the_independent_reference(liquid_closure, feed_T):
    """UNIFAC liquid acetic acid + ethanol (1:1, unreacted), 1 atm: H(T_f, P, n_ref) of the region's closure."""
    H = liquid_closure.initial_energy([float(v) for v in LIQUID_N0], LIQUID_P, feed_T)
    reference = L.liquid_enthalpy(L.SPECIES, LIQUID_N0, feed_T, LIQUID_P, 'original')
    assert abs(mp.mpf(H) - reference) <= 1e-9 * abs(reference)


@pytest.mark.parametrize('feed_T', [350., 360.])
def test_vapour_feed_enthalpy_matches_the_independent_reference(gas_closure, feed_T):
    """Package vapour (ideal gas) ethanol + toluene feed at 20 kPa: H(T_f, P, n_ref) against Poling cp and Hfg."""
    n = [float(v) for v in L.VAPOUR_REFERENCE]
    H = gas_closure.initial_energy(n, GAS_P, feed_T)
    reference = L.gas_enthalpy(L.VAPOUR, L.VAPOUR_REFERENCE, feed_T)
    assert abs(mp.mpf(H) - reference) <= 1e-9 * abs(reference)
