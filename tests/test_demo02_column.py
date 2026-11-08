"""Recorded countercurrent column (demo-02-column) against an independent steady MESH solution.

The reference below is written from the textbook equilibrium-stage equations, not
from the engine: modified Raoult's law y P = x gamma Psat exp(vL (P - Psat)/(R T))
with UNIFAC (Dortmund) activity coefficients implemented here from the published
group parameters, the Wagner (Poling) vapour pressure, ideal-gas heat capacities,
the liquid enthalpy implied by the same vapour pressure (h = g - T dg/dT) and the
excess enthalpy -R T^2 sum x_i d ln gamma_i/dT. Only pure-component coefficients
are read from core.mezclas_datos; the group parameters are written below and
compared, as data, to the package tables. No closure, bridge, compiled expression
or model residual is used.
"""
import time

import numpy as np
import pytest
from scipy.optimize import root

from demo02_column import (BENZENE, TOLUENE, CONDENSER_Q, REBOILER_Q, REBOILER, FEED, DEMO, author_stage,
                           column_model, frozen_model)
from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_steady import IndexedSteadySystem
from core.compilador.indexed_publication import dynamic_result, steady_result
from core.compilador.derived_graph import LoweringError
from core.modelo.lector import ErrorModelo

R = 8.31446261815324
T_REF = 298.15
# UNIFAC (Dortmund) groups: benzene 6 ACH; toluene 5 ACH + 1 ACCH3 (DDBST assignments).
GROUPS = {'ACH': (3, 0.3763, 0.4321), 'ACCH3': (4, 0.91, 0.949)}       # main group, R_k, Q_k
NU = np.array([[6., 0.], [5., 1.]])
INTERACTION = {(3, 4): (139.2, -0.65, 0.0), (4, 3): (-45.33, 0.4223, 0.0)}   # a, b, c (K, 1, 1/K)


class Pure:
    def __init__(self, cas):
        from core.mezclas_datos import especie
        e = especie(cas)
        assert e.psat_forma == 'WagnerPoling' and e.cp_L is None
        self.M, self.vL, self.psat, self.cp = e.M, e.vL, e.psat, e.cp

    def ln_psat(self, T):
        A, B, C, D, Tc, Pc = self.psat
        tau = 1 - T / Tc
        poly = A * tau + B * tau**1.5 + C * tau**2.5 + D * tau**5
        slope = -Tc / T**2 * poly - (A + 1.5 * B * tau**.5 + 2.5 * C * tau**1.5 + 5 * D * tau**4) / T
        return np.log(Pc) + Tc / T * poly, slope

    def h_gas(self, T):
        return R * sum(a * (T**(k + 1) - T_REF**(k + 1)) / (k + 1) for k, a in enumerate(self.cp))

    def h_liquid(self, T, P):
        lnp, slope = self.ln_psat(T)
        ps = np.exp(lnp)
        return self.h_gas(T) - R * T * T * slope + self.vL * (P - ps + T * ps * slope)

    def fugacity_ratio(self, T, P):
        ps = np.exp(self.ln_psat(T)[0])
        return ps * np.exp(self.vL * (P - ps) / (R * T)) / P


def ln_gamma(T, x):
    """UNIFAC (Dortmund) for the binary; x is the light (benzene) mole fraction."""
    X = np.array([x, 1 - x])
    main = [g[0] for g in GROUPS.values()]
    Rk = np.array([g[1] for g in GROUPS.values()]); Qk = np.array([g[2] for g in GROUPS.values()])
    psi = np.ones((2, 2))
    for a in range(2):
        for b in range(2):
            if main[a] != main[b]:
                A, B, C = INTERACTION[main[a], main[b]]
                psi[a, b] = np.exp(-(A + B * T + C * T * T) / T)
    r, q = NU @ Rk, NU @ Qk

    def group_ln(counts):
        fraction = counts / counts.sum()
        theta = Qk * fraction / (Qk * fraction).sum()
        S = theta @ psi
        return Qk * (1 - np.log(S) - psi @ (theta / S))

    mixture = group_ln(X @ NU)
    residual = np.array([NU[i] @ (mixture - group_ln(NU[i])) for i in range(2)])
    V, Vp, F = r / (X @ r), r**.75 / (X @ r**.75), q / (X @ q)
    combinatorial = 1 - Vp + np.log(Vp) - 5 * q * (1 - V / F + np.log(V / F))
    return combinatorial + residual


def liquid_enthalpy(pure, T, P, x):
    X = np.array([x, 1 - x]); d = 1e-3
    slope = (ln_gamma(T + d, x) - ln_gamma(T - d, x)) / (2 * d)
    return X @ np.array([p.h_liquid(T, P) for p in pure]) - R * T * T * (X @ slope)


def mesh(n, P, duties, feeds, guess=None):
    """Steady simultaneous MESH: stage 1 partial condenser (no liquid inlet), stage n reboiler (no vapour inlet).

    duties[j] in W; feeds[j] = (mol/s, light mole fraction, T, P) of a liquid feed or None.
    Unknowns per stage: T, x (light), L, V (mol/s).
    """
    pure = (Pure(BENZENE), Pure(TOLUENE))
    hfeed = [f[0] * liquid_enthalpy(pure, f[2], f[3], f[1]) if f else 0. for f in feeds]

    def properties(Tj, x):
        K = np.array([[pure[i].fugacity_ratio(t, P) * np.exp(ln_gamma(t, xi)[i]) for i in range(2)] for t, xi in zip(Tj, x)])
        y = K[:, 0] * x
        hL = np.array([liquid_enthalpy(pure, t, P, xi) for t, xi in zip(Tj, x)])
        hV = y * pure[0].h_gas(Tj) + (1 - y) * pure[1].h_gas(Tj)
        return K, y, hL, hV

    def residual(u):
        Tj, x, L, V = np.asarray(u).reshape(n, 4).T
        K, y, hL, hV = properties(Tj, x)
        out = []
        for j in range(n):
            Lin, xin, hLin = (L[j - 1], x[j - 1], hL[j - 1]) if j > 0 else (0., 0., 0.)
            Vin, yin, hVin = (V[j + 1], y[j + 1], hV[j + 1]) if j < n - 1 else (0., 0., 0.)
            F, z = (feeds[j][0], feeds[j][1]) if feeds[j] else (0., 0.)
            out += [Lin * xin + Vin * yin + F * z - L[j] * x[j] - V[j] * y[j],
                    Lin + Vin + F - L[j] - V[j],
                    (Lin * hLin + Vin * hVin + hfeed[j] + duties[j] - L[j] * hL[j] - V[j] * hV[j]) / 3e4,
                    K[j, 0] * x[j] + K[j, 1] * (1 - x[j]) - 1]
        return np.asarray(out)

    if guess is None:
        guess = np.column_stack([np.linspace(358, 382, n), np.linspace(.8, .05, n), np.full(n, 1.), np.full(n, 1.4)]).ravel()
    solution = root(residual, guess, method='hybr', options={'xtol': 1e-13})
    norm = float(np.max(np.abs(residual(solution.x))))
    assert norm < 1e-10, solution.message
    Tj, x, L, V = solution.x.reshape(n, 4).T
    K, y, hL, hV = properties(Tj, x)
    return dict(T=Tj, x=x, y=y, L=L, V=V, residual=norm, M=np.array([p.M for p in pure]), hfeed=hfeed)


def reference(count, feed_stage=None):
    feed_stage = feed_stage or (count + 1) // 2
    M = np.array([Pure(BENZENE).M, Pure(TOLUENE).M])
    z = np.array(FEED['zF'])
    feeds = [None] * count
    feeds[feed_stage - 1] = (FEED['feed'] / float(z @ M), z[0], FEED['TF'], DEMO['PF'])
    duties = [0.] * count; duties[0] = CONDENSER_Q; duties[-1] = REBOILER_Q
    return mesh(count, DEMO['P'], duties, feeds)


@pytest.fixture(scope='module')
def stage():
    return frozen_model()


def stage_rows(system, state):
    """Per-stage closure temperature, liquid/vapour composition and molar flows from the connected state."""
    rows = []
    for j, stage in enumerate(system.stages):
        local = state[system.offsets[j]:system.offsets[j + 1]]
        closure = stage.closures[0]
        values = dict(zip([key for _, key in closure.output_map], closure.evaluate(0., local)[0]))
        rows.append(dict(T=values[('T',)], x=values[('x', 'L', 0)], y=values[('x', 'V', 0)],
                         nV=values[('amount', 'V')], ML=values[('M', 'L')], flow=local[3]))
    return rows


def test_reference_group_parameters_match_the_published_package_tables():
    from core import unifac
    tables = unifac.tablas('dortmund')
    assert unifac.asignacion(BENZENE, 'dortmund') == {9: 6} and unifac.asignacion(TOLUENE, 'dortmund') == {9: 5, 11: 1}
    assert tables['sub'][9][:3] == GROUPS['ACH'] and tables['sub'][11][:3] == GROUPS['ACCH3']
    assert tables['inter'][3, 4] == INTERACTION[3, 4] and tables['inter'][4, 3] == INTERACTION[4, 3]
    # The independent activity model agrees with the package implementation (cross-check, not the reference).
    liquid = unifac.LiquidoUNIFAC([BENZENE, TOLUENE], 'dortmund')
    for T, x in [(355., .9), (370., .4), (383., .02)]:
        np.testing.assert_allclose(ln_gamma(T, x), liquid.lngamma(T, [x, 1 - x]), rtol=0, atol=1e-13)


def test_fixture_matches_fresh_shared_authoring(stage):
    model, out = author_stage()
    assert model == stage
    # Every inlet enters the component and energy balances through recorded substitutions.
    rules = [op['kind'] for op in model['motores']['equationWorkbench']['operations']]
    assert rules.count('substitute') >= 3 * 2 * 2


def test_countercurrent_topology_expands_with_located_variants(stage):
    from core.modelo.index_sets import expand_index_set
    expansion = expand_index_set(column_model(stage, 5))
    assert [row['template'] for row in expansion['stages']] == ['condenser', 'generic', 'feed', 'generic', 'reboiler']
    links = [(c['from']['stage'], c['to']['stage']) for c in expansion['connections']]
    assert sorted(links) == sorted([(j, j + 1) for j in range(1, 5)] + [(j + 1, j) for j in range(1, 5)])
    assert {p['port']['id'] for p in expansion['ports']} >= {'distillate.1', 'bottoms.5', 'reflux.1', 'boilup.5', 'feed.3'}


TIMINGS = {}


@pytest.fixture(scope='module')
def column5(stage):
    """n = 5: one connected system shared by the dynamic and steady checks (lowering is expensive)."""
    model = column_model(stage, 5)
    clock = time.perf_counter()
    dynamic = IndexedDerivedSystem(model)
    TIMINGS['n5.lowering'] = time.perf_counter() - clock
    clock = time.perf_counter()
    transient = dynamic_result(dynamic)
    TIMINGS['n5.dynamic'] = time.perf_counter() - clock
    clock = time.perf_counter()
    steady = IndexedSteadySystem(model, dynamic=dynamic)
    TIMINGS['n5.steadyTransform'] = time.perf_counter() - clock
    clock = time.perf_counter()
    publication = steady_result(steady)
    TIMINGS['n5.steadySolve'] = time.perf_counter() - clock
    print('\ncolumn n=5 timings (s):', {k: round(v, 1) for k, v in TIMINGS.items()})
    return dict(model=model, dynamic=dynamic, transient=transient, steady=steady, publication=publication)


def state_from_series(system, series):
    """The connected state vector from published per-stage state series (last sample)."""
    state = system.initial()
    for j, stage in enumerate(system.stages):
        inverse = {v: k for k, v in system.expansion['stages'][j]['provenance']['identityMap']['quantities'].items()}
        for k, qid in enumerate(stage.state_ids):
            values = series[f'column.stage.{j + 1}.state.' + inverse[qid]]
            state[system.offsets[j] + k] = values[-1] if isinstance(values, list) else values
    return state


def check_against_mesh(system, state, count):
    expected = reference(count)
    rows = stage_rows(system, state)
    np.testing.assert_allclose([r['T'] for r in rows], expected['T'], rtol=0, atol=1e-6)
    np.testing.assert_allclose([r['x'] for r in rows], expected['x'], rtol=0, atol=1e-8)
    np.testing.assert_allclose([r['y'] for r in rows], expected['y'], rtol=0, atol=1e-8)
    liquid = np.array([r['flow'] / r['ML'] for r in rows])          # mol/s from the momentum state
    vapour = np.array([DEMO['vent'] * r['nV'] for r in rows])       # mol/s from the vapour withdrawal law
    np.testing.assert_allclose(liquid, expected['L'], rtol=1e-7)
    np.testing.assert_allclose(vapour, expected['V'], rtol=1e-7)
    # Column envelope: total, light-component and energy balances with the independent properties.
    pure = (Pure(BENZENE), Pure(TOLUENE))
    z = np.array(FEED['zF']); F = FEED['feed'] / float(z @ expected['M'])
    D, B = vapour[0], liquid[-1]
    top, bottom = rows[0], rows[-1]
    assert abs(F - D - B) < 1e-9 * F
    assert abs(F * z[0] - D * top['y'] - B * bottom['x']) < 1e-9 * F
    hD = top['y'] * pure[0].h_gas(top['T']) + (1 - top['y']) * pure[1].h_gas(top['T'])
    hB = liquid_enthalpy(pure, bottom['T'], DEMO['P'], bottom['x'])
    hF = liquid_enthalpy(pure, FEED['TF'], DEMO['PF'], z[0])
    assert abs(F * hF + CONDENSER_Q + REBOILER_Q - D * hD - B * hB) < 1e-6 * abs(REBOILER_Q)
    return rows, expected


def test_steady_transform_column_against_independent_mesh(column5):
    steady, publication = column5['steady'], column5['publication']
    assert publication['estado'] == 'resuelto'
    evidence = publication['procedencia']['networkEvidence']['numerical']['solver']
    # Newton starts from the steady Transform defaults (the template initial data), not from the transient.
    assert evidence['residualNorm'] < 1e-9 and evidence['iterations'] > 0
    for check in publication['verificaciones']:
        assert check['valor'] <= check['tolerancia'], check
    series = {row['id']: row['valores'] for row in publication['series'] if '.state.' in row['id']}
    check_against_mesh(column5['dynamic'], state_from_series(column5['dynamic'], series), 5)
    assert publication['indexedNetwork']['count'] == 5


def test_dynamic_column_approaches_the_steady_state(column5):
    dynamic, transient = column5['dynamic'], column5['transient']
    assert transient['estado'] == 'resuelto'
    for check in transient['verificaciones']:
        if 'conservation' in check['id'] or check['id'].startswith('thermodynamics.closure.'):
            assert check['valor'] <= check['tolerancia'], check
    states = {row['id']: row['valores'] for row in transient['series'] if '.state.' in row['id']}
    stationary = {row['id']: row['valores'] for row in column5['publication']['series']
                  if row['id'].startswith('column.stage.') and '.state.' in row['id']}
    assert stationary and set(stationary) <= set(states)
    for key, value in stationary.items():
        np.testing.assert_allclose(states[key][-1], value, rtol=1e-6, atol=1e-9)
    # The final dynamic state itself reproduces the independent MESH solution.
    check_against_mesh(dynamic, state_from_series(dynamic, states), 5)
    assert np.asarray(transient['ejes'][0]['valores'])[-1] == pytest.approx(DEMO['tf'])


def test_larger_column_steady_with_block_sparse_jacobian(stage):
    count = 10
    model = column_model(stage, count)
    clock = time.perf_counter()
    dynamic = IndexedDerivedSystem(model, linear_solver='sparse')
    steady = IndexedSteadySystem(model, dynamic=dynamic)
    root_values, evidence = steady.solve()
    print(f'\ncolumn n={count} sparse steady (lowering + Transform + solve): {time.perf_counter() - clock:.1f} s,'
          f' iterations={evidence["iterations"]}')
    assert evidence['networkJacobian']['selected'] == 'sparse'
    assert evidence['residualNorm'] < 1e-9 and evidence['iterations'] > 0
    check_against_mesh(dynamic, steady.state(root_values), count)


def test_unequal_stage_pressure_is_a_located_rejection(stage):
    model = column_model(stage, 5)
    model['indexSet']['templates']['reboiler']['datos']['stage.pressure']['declaracion']['texto'] = '120000.0'
    with pytest.raises(LoweringError) as error:
        IndexedDerivedSystem(model)
    diagnostic = error.value.diagnostics[0]
    assert diagnostic['code'] == 'index_network_pressure_mismatch'
    # CR-2: a liquid discharge port is coupled to the receiving stage pressure, so the liquid connection 4 (stage 4 -> 5) is
    # accepted; the vapour connection 8 (stage 5 -> 4) draws a phase directly and stays fail-closed at the located connection.
    assert diagnostic['path'] == 'indexSet.connections.column.connection.8'


@pytest.mark.parametrize('mutation,path', [
    (lambda r: r['connections'].__setitem__(1, {'outlet': 'vapour', 'inlet': 'vapourIn', 'offset': 2}), 'indexSet.connections[1]'),
    (lambda r: r['connections'].append({'outlet': 'vapour', 'inlet': 'vapourIn', 'offset': 1}), 'indexSet.connections[2]'),
    (lambda r: r['exposures'].pop(2), 'indexSet.connections'),
    (lambda r: r['exposures'].append({'id': 'extra', 'port': 'vapourIn', 'at': 2}), 'indexSet.exposures[6]'),
    (lambda r: r['variants'].append({'at': 'last', 'template': 'feed'}), 'indexSet.variants[3]'),
])
def test_unsupported_topologies_are_located(stage, mutation, path):
    from core.modelo.index_sets import read_index_set
    model = column_model(stage, 5)
    mutation(model['indexSet'])
    with pytest.raises(ErrorModelo) as error:
        read_index_set(model)
    assert error.value.ruta == path
