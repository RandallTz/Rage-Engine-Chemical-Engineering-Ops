"""B3 part 2 (claude-b, 6 November 2026): thermally coupled chemical equilibrium.

The region's caloric closure is the reaction package itself (select_closure with the formation reference of the
declaration anchor). The energy balance is the recorded enthalpy balance of a closed, prescribed-pressure,
adiabatic region with no volumetric source: the formation-referenced enthalpy carries the reaction heat exactly
once. T = T(H, P, n_ref + N xi) is the closure output, and the extent block is certified over the declared extent
box times the recorded closure-temperature interval with
    dg/dxi|_{H,P} = (dg/dn) N + R T^2 (dg/dT)(dg/dT)^T / C_p,   C_p > 0 proved.

References are independent of core.mezclas/core.unifac/core.reactions/core.termodinamica
(tests/equilibrium_reaction_liquid_inputs.py): a 50-digit mpmath pure-liquid enthalpy and potential from the
published coefficient tuples and `chemicals` liquid formation data, thermo's UNIFAC for ln gamma and H^E, and a
50-digit mpmath ideal-gas mixture (Poling cp, `chemicals` Hfg and S0g).
"""
import copy
import math

import mpmath as mp
import numpy as np
import pytest
import sympy as sp

from core import mezclas
from core.balances import energy_derivation as energy
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.derived_graph import LoweringError, source_signature
from core.compilador.reaction_extent import certify_extent
from core.modelo.operation_journal import replay
from core.reactions import chemical_equilibrium as ce
from core.termodinamica import derivation as thermodynamics
import equilibrium_reaction_liquid_inputs as L

LIQUID_FEED_T, GAS_FEED_T = 340., 360.
LIQUID_P, GAS_P = 101325., 2e4
LIQUID_N0 = (1, 1, 0, 0)


def _series(result, name):
    return next(s['valores'] for s in result['series'] if s['nombre'] == name)


def _verification(result, key):
    return next(v for v in result['verificaciones'] if v['id'] == key)


def _resign(model):
    model['motores']['derivedExecution']['sourceSignature'] = source_signature(model)
    return model


def _rejected(model):
    with pytest.raises(LoweringError) as caught:
        DerivedSystem(model)
    return caught.value.diagnostics[0]


@pytest.fixture(scope='module')
def liquid():
    H0 = float(L.liquid_enthalpy(L.SPECIES, LIQUID_N0, LIQUID_FEED_T, LIQUID_P, 'original'))
    xi, T = L.coupled_liquid_reference(L.SPECIES, L.NU, LIQUID_N0, H0, LIQUID_P, 'original', (.63, 350))
    model = L.thermal_author('liquid', L.SPECIES, L.NU, LIQUID_N0, 'unifac-original', 'liquid', 'liquid', LIQUID_P, H0,
                             (330, 370), (float(xi) - .02, float(xi) + .02), float(xi) + .005)
    system = DerivedSystem(copy.deepcopy(model))
    return {'model': model, 'system': system, 'result': resolve_system(system), 'H0': H0, 'xi': xi, 'T': T}


@pytest.fixture(scope='module')
def gas():
    H0 = float(L.gas_enthalpy(L.VAPOUR, L.VAPOUR_REFERENCE, GAS_FEED_T))
    xi, T = L.coupled_gas_reference(L.VAPOUR, L.VAPOUR_NU, L.VAPOUR_REFERENCE, H0, GAS_P, (.99, 400))
    model = L.thermal_author('gas', L.VAPOUR, L.VAPOUR_NU, L.VAPOUR_REFERENCE, 'unifac-original', 'vapor', 'gas', GAS_P, H0,
                             (370, 430), (float(xi) - 5e-4, float(xi) + 4e-4), float(xi), state_width=1e-6, step_tolerance=1e-15)
    system = DerivedSystem(copy.deepcopy(model))
    return {'model': model, 'system': system, 'result': resolve_system(system), 'H0': H0, 'xi': xi, 'T': T}


# --- positive cases against independent references --------------------------------------------------------
def test_adiabatic_isobaric_liquid_esterification_matches_independent_solution(liquid):
    """UNIFAC liquid, 1 atm, feed 1:1 acid/ethanol at 340 K: the coupled {equilibrium, H = H0} root."""
    result = liquid['result']
    assert result['estado'] == 'resuelto'
    extent = _series(result, 'extent(t)'); T = _series(result, 'T__liquid(t)')
    # Reference: xi = 0.6340065654906902, T = 350.0730196114034 K (thermo is binary64: ~1e-13 attainable).
    assert all(abs(v - float(liquid['xi'])) < 1e-12 for v in extent)
    assert all(abs(v - float(liquid['T'])) < 1e-8 for v in T)
    assert T[-1] - LIQUID_FEED_T > 9.5   # the reaction heat is carried: exothermic liquid esterification
    # Energy conservation: the integrated inventory stays H0 and the independent enthalpy of the published state is H0.
    assert all(v == liquid['H0'] for v in _series(result, 'H__liquid(t)'))
    n = [_series(result, 'n_' + str(i) + '__liquid(t)')[-1] for i in range(1, 5)]
    independent = L.liquid_enthalpy(L.SPECIES, n, T[-1], LIQUID_P, 'original')
    assert abs(float(independent) - liquid['H0']) <= 1e-10 * abs(liquid['H0'])
    assert _verification(result, 'thermodynamics.closure.liquid')['valor'] < 1e-12
    assert _verification(result, 'algebraic.scaled_residual')['valor'] < 1e-11


def test_adiabatic_isobaric_ideal_gas_reaction_matches_independent_solution(gas):
    """Package vapour (ideal gas), 20 kPa: 2 ethanol = 1-butanol + water with toluene inert, feed at 360 K."""
    result = gas['result']
    assert result['estado'] == 'resuelto'
    extent = _series(result, 'extent(t)'); T = _series(result, 'T__gas(t)')
    # Reference (50 digits): xi = 0.99907160049291652, T = 408.44792615227112 K.
    assert all(abs(v - float(gas['xi'])) < 1e-13 for v in extent)
    assert all(abs(v - float(gas['T'])) < 1e-9 for v in T)
    assert T[-1] - GAS_FEED_T > 45
    assert all(v == gas['H0'] for v in _series(result, 'H__gas(t)'))
    n = [_series(result, 'n_' + str(i) + '__gas(t)')[-1] for i in range(1, 5)]
    assert abs(float(L.gas_enthalpy(L.VAPOUR, n, T[-1])) - gas['H0']) <= 1e-12 * abs(gas['H0'])
    assert _verification(result, 'thermodynamics.closure.gas')['valor'] < 1e-12


def test_reaction_heat_is_carried_once_without_a_source_term(liquid):
    """The selected energy row is dH/dt = 0 (adiabatic, isobaric, no volumetric source): no reaction-heat term.
    The temperature rise equals the formation-referenced enthalpy balance: H(T, n(xi)) = H(T_feed, n_ref)."""
    system = liquid['system']
    H = sp.Function('H__liquid')(system.time)
    assert sp.simplify(system.rates[sp.Derivative(H, system.time)]) == 0
    result = liquid['result']
    T = _series(result, 'T__liquid(t)')[-1]
    # Independent bookkeeping: heating the unreacted feed to T costs exactly -xi Delta_r h at T (both formation
    # referenced): H(T, n_ref) - H0 + [H(T, n) - H(T, n_ref)] = 0.
    n = [_series(result, 'n_' + str(i) + '__liquid(t)')[-1] for i in range(1, 5)]
    sensible = L.liquid_enthalpy(L.SPECIES, LIQUID_N0, T, LIQUID_P, 'original') - mp.mpf(liquid['H0'])
    reaction = L.liquid_enthalpy(L.SPECIES, n, T, LIQUID_P, 'original') - L.liquid_enthalpy(L.SPECIES, LIQUID_N0, T, LIQUID_P, 'original')
    assert sensible > 2000 and reaction < -2000          # J: both terms are large and they cancel
    assert abs(float(sensible + reaction)) < 1e-6


def test_coupled_certificate_records_temperature_box_and_positive_heat_capacity(liquid, gas):
    for case, box in ((liquid, [330., 370.]), (gas, [370., 430.])):
        proof = case['system'].dae.proof
        assert proof['temperatureBox'] == box
        assert proof['heatCapacityBounds'][0] > 0
        low, high = map(float, proof['determinantBounds'])
        assert low > 0 or high < 0
        assert 'C_p' in proof['determinant'] and 'Thermal coupling' in proof['proof']


def _independent_liquid_affinity(xi, H0):
    """g(xi, T(H0, n(xi))) with T from the independent enthalpy (secant)."""
    n = [mp.mpf(a) + v * mp.mpf(xi) for a, v in zip(LIQUID_N0, L.NU)]
    T = mp.findroot(lambda t: (L.liquid_enthalpy(L.SPECIES, n, t, LIQUID_P, 'original') - mp.mpf(H0)) / 1000,
                    (mp.mpf(349), mp.mpf(351)), solver='secant', tol=mp.mpf('1e-24'), verify=False)
    x = [v / mp.fsum(n) for v in n]
    lg = L.ln_gamma(L.SPECIES, x, T, 'original')
    return mp.fsum(v * (mp.log(xv) + g) for v, xv, g in zip(L.NU, x, lg)) - L.ln_k(L.SPECIES, L.NU, T, LIQUID_P)


def test_runtime_and_certified_coupled_jacobian_against_independent_difference(liquid):
    """dg/dxi at fixed H: engine runtime value = independent central difference of g(xi, T(H0, xi)), and it lies
    inside the certified whole-box enclosure; the temperature path changes the slope (it is not (dg/dn) N)."""
    system = liquid['system']; block = system.algebraic_block
    state = list(system.initial_state[:len(system.states)])
    bounds = block.extent_proof['jacobianBounds'][0][0]
    for xi in (float(liquid['xi']) - .01, float(liquid['xi']), float(liquid['xi']) + .015):
        runtime = float(block._jacobian(0., *state, xi)[0][0])
        h = 1e-5
        independent = float((_independent_liquid_affinity(xi + h, liquid['H0']) - _independent_liquid_affinity(xi - h, liquid['H0'])) / (2 * h))
        assert abs(runtime - independent) <= 2e-6 * abs(independent)
        assert bounds[0] <= runtime <= bounds[1]
        isothermal = block.state([0., *state, xi])
        rows = np.asarray(block.nu[block.independent, :], dtype=float)
        prescribed = float((rows @ np.asarray(isothermal['dmu_dn']) @ np.asarray(block.N, dtype=float))[0][0] / (ce.R * isothermal['T']))
        assert runtime - prescribed > 1e-3 * abs(runtime)


# --- certification units (no Model authoring) ----------------------------------------------------------------
def _liquid_provider():
    return ce.PackagePhase(mezclas.Sistema('unifac-original-public', L.SPECIES, solo_liquido=True), 'liquido', anchor='liquid')


def _vapour_provider():
    return ce.PackagePhase(mezclas.Sistema('unifac-original-public', L.VAPOUR), 'vapor', anchor='gas')


def test_heat_capacity_enclosure_contains_independent_heat_capacity():
    n = [.36, .36, .64, .64]
    T = 350.
    independent = mp.diff(lambda t: L.liquid_enthalpy(L.SPECIES, n, t, LIQUID_P, 'original'), mp.mpf(T), h=mp.mpf('1e-3'))
    wide = ce.heat_capacity_bounds(_liquid_provider(), {'T': [T - .5, T + .5], 'P': [LIQUID_P] * 2, 'n': [[v, v] for v in n]},
                                   phase_id='liquido', standard_state='pure_liquid_TP')
    assert wide['certified'] and wide['bounds']['Cp'][0] <= float(independent) <= wide['bounds']['Cp'][1]
    point = ce.heat_capacity_bounds(_liquid_provider(), {'T': [T, T], 'P': [LIQUID_P] * 2, 'n': [[v, v] for v in n]},
                                    phase_id='liquido', standard_state='pure_liquid_TP')
    assert abs(point['bounds']['Cp'][0] - float(independent)) < 1e-6 * float(independent)
    # Ideal-gas vapour: C_p = sum n_i R sum_k a_ik T^k exactly (the same Poling polynomial, 50 digits).
    nv = [.002, 6., .999, .999]
    exact = mp.fsum(mp.mpf(v) * L.R * mp.fsum(a * mp.mpf(408)**k for k, a in enumerate(L._poling(c))) for c, v in zip(L.VAPOUR, nv))
    vapour = ce.heat_capacity_bounds(_vapour_provider(), {'T': [408., 408.], 'P': [GAS_P] * 2, 'n': [[v, v] for v in nv]},
                                     phase_id='vapor', standard_state='ideal_gas_P0')
    assert vapour['certified'] and vapour['bounds']['Cp'][0] <= float(exact) <= vapour['bounds']['Cp'][1]


def test_heat_capacity_outside_the_package_domain_is_located():
    out = ce.heat_capacity_bounds(_vapour_provider(), {'T': [450., 480.], 'P': [GAS_P] * 2, 'n': [[1, 1]] * 4},
                                  phase_id='vapor', standard_state='ideal_gas_P0')
    assert not out['certified'] and out['bounds'] is None
    assert (out['diagnostics'][0]['code'], out['diagnostics'][0]['path']) == ('OUT_OF_DOMAIN', 'box.T')


def test_package_vapour_extent_proof_needs_its_caloric_closure():
    """The prescribed-T package-vapour gate stays; the coupled (thermal) proof admits it and splits T if needed."""
    reference = [[2, 2], [6, 6], [0, 0], [0, 0]]
    with pytest.raises(LoweringError) as caught:
        certify_extent(_vapour_provider(), [L.VAPOUR_NU], reference, [[.998, .9995]], [408, 408], [GAS_P] * 2,
                       phase_id='vapor', standard_state='ideal_gas_P0')
    assert (caught.value.diagnostics[0]['code'], caught.value.diagnostics[0]['path']) == ('PROVIDER_UNSUPPORTED', 'equilibriumReactions.provider')
    proof = certify_extent(_vapour_provider(), [L.VAPOUR_NU], reference, [[.998, .9995]], [370, 430], [GAS_P] * 2,
                           phase_id='vapor', standard_state='ideal_gas_P0', thermal=True)
    assert proof['thermal'] and proof['heatCapacityBounds'][0] > 0 and proof['temperatureBox'] == [370., 430.]
    with pytest.raises(LoweringError) as caught:
        certify_extent(_vapour_provider(), [L.VAPOUR_NU], reference, [[.998, .9995]], [440, 480], [GAS_P] * 2,
                       phase_id='vapor', standard_state='ideal_gas_P0', thermal=True)
    assert (caught.value.diagnostics[0]['code'], caught.value.diagnostics[0]['path']) == ('OUT_OF_DOMAIN', 'equilibriumReactions.box.T')


# --- negative controls: located rejections ----------------------------------------------------------------
def _rejournal(model, owner, thermo=None, energy_actions=None, package=None):
    """Re-record the region journals through the journal APIs (no workbench change) and re-sign."""
    model = copy.deepcopy(model)
    v = next(x for x in model['volumenes'] if x['id'] == owner)
    if package is not None:
        v['termodinamica']['paqueteId'] = package
    ej = model['motores']['energyDerivation']
    if energy_actions is not None:
        ej = {'format': 'rage.energy-derivation', 'version': 1, 'volumes': {}}
        for action in energy_actions:
            ej = energy.edit_journal(ej, owner, {'kind': action})
        model['motores']['energyDerivation'] = ej
    tj = model['motores']['thermodynamicDerivation']
    if thermo is not None or package is not None:
        tj = {'format': thermodynamics.FORMAT, 'version': 1, 'volumes': {}}
        tj = thermodynamics.edit_journal(tj, owner, {'kind': 'start'})
        tj = thermodynamics.edit_journal(tj, owner, {'kind': 'select_closure'}, thermodynamics.expected_closure(model, v))
        for kind in thermo or ():
            tj = thermodynamics.edit_journal(tj, owner, {'kind': kind})
        model['motores']['thermodynamicDerivation'] = tj
    es = replay(ej['volumes'][owner], energy.fundamental, energy.normalize)[-1]
    ts = replay(tj['volumes'][owner], thermodynamics.fundamental, thermodynamics.normalize)[-1]
    v['supuestos']['energia'] = {**es, **{k: val for k, val in ts.items() if k != 'closure'}}
    return _resign(model)


PH = ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source',
      'integrate', 'reynolds', 'total', 'enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure')


def test_missing_formation_reference_is_rejected_as_lost_heat(liquid):
    diagnostic = _rejected(_rejournal(liquid['model'], 'liquid', thermo=('liquid_only',)))
    assert diagnostic['code'] == 'reaction_caloric_reference_missing'
    assert diagnostic['path'] == 'motores.thermodynamicDerivation.volumes.liquid' and 'lose the reaction heat' in diagnostic['message']


def _liquid_control(liquid, **source):
    """The liquid case authored again through the shared operations with one changed premise (a journal
    edit behind saved operation IDs is refused by replay, so controls are re-authored, not mutated)."""
    xi = float(liquid['xi'])
    return L.thermal_author('liquid', L.SPECIES, L.NU, LIQUID_N0, 'unifac-original', 'liquid', 'liquid', LIQUID_P, liquid['H0'],
                            (330, 370), (xi - .02, xi + .02), xi + .005, **source)


def test_volumetric_energy_source_is_rejected_as_double_counting(liquid):
    diagnostic = _rejected(_liquid_control(liquid, volume_source=True))
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_heat_double_counted', 'motores.energyDerivation.volumes.liquid')


def test_closure_package_other_than_the_reaction_package_is_rejected(liquid):
    diagnostic = _rejected(_liquid_control(liquid, closure_package='otherPackage'))
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_caloric_provider_mismatch', 'volumenes.liquid.termodinamica.paqueteId')


def test_temperature_datum_initialization_is_rejected(liquid):
    model = copy.deepcopy(liquid['model'])
    selection = model['motores']['derivedExecution']
    H = next(k for k, v in selection['initialValues'].items() if v == 'initialEnergy')
    del selection['initialValues'][H]
    system = liquid['system']
    temperature = next(k for k, q in system.quantities.items() if q == system.closures[0].T)
    model['datos']['initialTemperature'] = copy.deepcopy(model['datos']['initialEnergy'])
    model['datos']['initialTemperature']['declaracion'] = {'texto': '340.0', 'unidad': 'K'}
    selection['initialValues'][temperature] = 'initialTemperature'
    diagnostic = _rejected(model)
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_initial_energy_required', 'motores.derivedExecution.initialValues')


def test_rigid_incompressible_liquid_is_rejected_as_ill_posed(liquid):
    """UV with a rigid boundary: v = sum x_i v_L,i with Delta_r v != 0 cannot determine P (R3 of the B3 review)."""
    nu_v = sum(v * mezclas.Sistema('unifac-original-public', L.SPECIES, solo_liquido=True).esp[i].vL for i, v in enumerate(L.NU))
    assert abs(nu_v) > 1e-7          # m3/mol: the reaction changes the liquid volume
    model = L.thermal_author('liquid', L.SPECIES, L.NU, LIQUID_N0, 'unifac-original', 'liquid', 'liquid', LIQUID_P, liquid['H0'],
                             (330, 370), (.61, .65), .64, rigid=True)
    diagnostic = _rejected(model)
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_rigid_liquid_ill_posed', 'volumenes.liquid.frontera')


def test_missing_temperature_box_is_rejected(gas):
    model = L.thermal_author('gas', L.VAPOUR, L.VAPOUR_NU, L.VAPOUR_REFERENCE, 'unifac-original', 'vapor', 'gas', GAS_P, gas['H0'],
                             (370, 430), (float(gas['xi']) - 5e-4, float(gas['xi']) + 4e-4), float(gas['xi']), state_width=1e-6,
                             step_tolerance=1e-15, record_box=False)
    diagnostic = _rejected(model)
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_temperature_box_missing', 'volumenes.gas.termodinamica')


def test_u_lineal_volume_stays_rejected_with_the_lost_heat_reason():
    """The B3 part 1 region (declared u_lineal caloric law) with its energy balance switched on."""
    model = L.esterification()
    model['volumenes'][0]['balances']['energia'] = True
    diagnostic = _rejected(_resign(model))
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_thermal_coupling_unsupported', 'volumenes.liquid.termodinamica')
    assert "'u_lineal'" in diagnostic['message'] and 'reaction heat would be lost' in diagnostic['message']


def test_temperature_leaving_the_recorded_interval_is_located(gas):
    """The proof covers the extent box times the recorded T interval only; a state whose closure temperature
    (408.45 K here) lies outside that interval is refused by name, not as a generic nonlinear domain failure."""
    model = L.thermal_author('gas', L.VAPOUR, L.VAPOUR_NU, L.VAPOUR_REFERENCE, 'unifac-original', 'vapor', 'gas', GAS_P, gas['H0'],
                             (370, 400), (float(gas['xi']) - 5e-4, float(gas['xi']) + 4e-4), float(gas['xi']), state_width=1e-6,
                             step_tolerance=1e-15)
    diagnostic = _rejected(model)
    assert (diagnostic['code'], diagnostic['path']) == ('reaction_temperature_out_of_interval', 'volumenes.gas.termodinamica')
    assert diagnostic['temperatureInterval'] == [370., 400.] and diagnostic['temperature'] > 400
    assert '[370.0, 400.0] K' in diagnostic['message']
