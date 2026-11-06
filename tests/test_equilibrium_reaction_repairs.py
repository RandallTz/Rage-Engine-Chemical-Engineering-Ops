"""F5-C1 review repairs (claude-b, 5 November 2026): F1, F2, F2b regressions.

References are independent of the compiler: analytic ideal-gas Jacobians,
exact rational box areas and a 50-digit mpmath root.
"""
import copy
from fractions import Fraction
import numpy as np
import pytest
from core.reactions import chemical_equilibrium as ce
from core.compilador.reaction_extent import certify_extent
from core.compilador.derived_graph import LoweringError, source_signature
from core.compilador.derived import DerivedSystem, resolve_system
from core.modelo import leer_modelo_comun
from equilibrium_reaction_inputs import author, SPECIES, NU


@pytest.fixture(scope='module')
def model():
    return author()


def _resign(changed):
    changed['motores']['derivedExecution']['sourceSignature'] = source_signature(changed)
    return changed


def test_ideal_gas_potential_is_a_recorded_constitutive_relation(model):
    """F1: each mu_i enters the affinity through a recorded thermodynamic
    constitutive row that the compiler matches to the executed provider."""
    system = DerivedSystem(model)
    block = system.algebraic_block
    assert sorted(block.potential_rows) == [0, 1, 2, 3]
    operations = model['motores']['equationWorkbench']['operations']
    for key in block.potential_rows.values():
        operation = operations[int(key.split('.')[1]) - 1]
        assert (operation['kind'], operation['relationKind'], operation['family']) == ('declare_relation', 'constitutive', 'thermodynamics')
        assert system.graph.nodes[key].equation.lhs.func.__name__.startswith('mu_')
    # The substituted affinity, not a generic mu row, is the selected equation.
    selected = model['motores']['equilibriumReactions']['volumes']['gas']['reactions'][0]['equationId']
    assert operations[int(selected.split('.')[1]) - 1]['kind'] == 'substitute'


def _unrecorded(model):
    # Persisted F5-C1 documents (before these repairs) stop at the generic
    # affinity: move the cursor back to that row and select it.
    changed = copy.deepcopy(model)
    workbench = changed['motores']['equationWorkbench']
    divide = max(i for i, op in enumerate(workbench['operations'][:workbench['cursor']], 1) if op['kind'] == 'divide')
    workbench['cursor'] = divide
    entry = changed['motores']['equilibriumReactions']['volumes']['gas']
    selection = changed['motores']['derivedExecution']
    entry['reactions'][0]['equationId'] = selection['algebraic'][0]['equationId'] = 'operation.' + str(divide)
    nonlinear = selection['nonlinear']
    nonlinear['residualScales'] = {'operation.' + str(divide): next(iter(nonlinear['residualScales'].values()))}
    selection['parameters'].pop('standardPressure')
    return _resign(changed)


def test_unrecorded_potential_is_a_located_migration_rejection(model):
    changed = _unrecorded(model)
    assert leer_modelo_comun(changed) == changed  # the persisted document still loads
    with pytest.raises(LoweringError) as caught:
        DerivedSystem(changed)
    diagnostic = caught.value.diagnostics[0]
    assert diagnostic['code'] == 'reaction_chemical_potential_not_recorded'
    assert diagnostic['path'] == 'motores.equilibriumReactions.volumes.gas.reactions.0'


@pytest.mark.parametrize('failure,code', [
    ('P0', 'reaction_standard_pressure_mismatch'),
    ('definition', 'reaction_chemical_potential_not_constitutive'),
    ('R', 'reaction_gas_constant_mismatch')])
def test_potential_relation_must_match_the_executed_provider(model, failure, code):
    changed = copy.deepcopy(model)
    if failure == 'P0':
        changed['datos']['P0']['declaracion']['texto'] = '200000'
    elif failure == 'R':
        changed['datos']['R']['declaracion']['texto'] = '8.314'
    else:
        # Editing a saved operation in place is refused by replay (source
        # signatures); author the chain with a non-constitutive mu row instead.
        changed = author(potential_kind='definition')
    with pytest.raises(LoweringError) as caught:
        DerivedSystem(_resign(changed))
    diagnostic = caught.value.diagnostics[0]
    assert diagnostic['code'] == code and diagnostic['path'].startswith('operation.')


def test_thermal_coupling_names_the_caloric_conflict(model):
    """F2: the u_lineal/provider caloric conflict is an explicit precondition."""
    changed = copy.deepcopy(model)
    changed['volumenes'][0]['balances']['energia'] = True
    with pytest.raises(LoweringError) as caught:
        DerivedSystem(_resign(changed))
    diagnostic = caught.value.diagnostics[0]
    assert diagnostic['code'] == 'reaction_thermal_coupling_unsupported'
    assert diagnostic['path'] == 'volumenes.gas.termodinamica' and 'u_lineal' in diagnostic['message']
    assert 'u_lineal' in DerivedSystem(model).algebraic_block.caloric_limitation


def _leaves(node):
    if 'split' not in node:
        assert node['certified'] and node['determinantBounds'][0] > 0
        return [node]
    return [leaf for child in node['split']['children'] for leaf in _leaves(child)]


def test_two_reaction_wide_box_certifies_by_sound_exact_cover():
    """F2b: steam reforming + water-gas shift on the reviewer's wide box."""
    species = ['630-08-0', '7732-18-5', '124-38-9', '1333-74-0', '74-82-8']
    nu = np.array([[1, -1, 0, 3, -1], [-1, -1, 1, 1, 0]])
    reference = np.array([1, 3, 0, 0, 1.])
    proof = certify_extent(ce.IdealGasPhase(species), nu, [[v, v] for v in reference], [[.01, .95], [.001, .5]],
                           [800, 800], [1e5, 1e5], phase_id='vapor', standard_state='ideal_gas_P0')
    leaves = _leaves(proof)
    assert len(leaves) > 1
    # Exact cover: leaves lie in the box and their exact areas sum to its area.
    area = lambda b: (Fraction(b[0][1]) - Fraction(b[0][0])) * (Fraction(b[1][1]) - Fraction(b[1][0]))
    assert sum(area(leaf['extentBox']) for leaf in leaves) == area(proof['extentBox'])
    for leaf in leaves:
        for (lo, hi), (LO, HI) in zip(leaf['extentBox'], proof['extentBox']):
            assert LO <= lo < hi <= HI
    # Soundness: analytic J = nu (diag(1/n) - 1/n_t) N lies in each leaf hull.
    rng = np.random.default_rng(20261105)
    N = nu.T
    for leaf in leaves:
        for _ in range(12):
            xi = np.array([rng.uniform(*p) for p in leaf['extentBox']])
            n = reference + N @ xi
            J = nu @ (np.diag(1 / n) - np.ones((5, 5)) / n.sum()) @ N
            for i in range(2):
                for j in range(2):
                    assert leaf['jacobianBounds'][i][j][0] <= J[i, j] <= leaf['jacobianBounds'][i][j][1]
            assert leaf['determinantBounds'][0] <= np.linalg.det(J) <= leaf['determinantBounds'][1]


def test_subdivision_depth_limit_is_a_located_rejection(monkeypatch):
    import core.compilador.reaction_extent as extent
    def never(matrix):
        extent.reject('reaction_index_not_certified', 'forced', 'equilibriumReactions.extentJacobian')
    monkeypatch.setattr(extent, 'nonsingular', never)
    with pytest.raises(LoweringError) as caught:
        certify_extent(ce.IdealGasPhase(['7727-37-9', '1333-74-0', '7664-41-7']), [[-1, -3, 2]],
                       [[1, 1], [3, 3], [0, 0]], [[.05, .9]], [700, 700], [1e7, 1e7],
                       phase_id='vapor', standard_state='ideal_gas_P0')
    diagnostic = caught.value.diagnostics[0]
    assert diagnostic['code'] == 'reaction_index_not_certified' and 'depth limit 20' in diagnostic['message']
    assert diagnostic['path'] == 'equilibriumReactions.extentJacobian'


def test_compiled_extent_matches_independent_mpmath_root(model):
    """50-digit root of ln K = sum nu ln(y) (dnu = 0), ln K read once from the provider."""
    import mpmath as mp
    mp.mp.dps = 50
    result = resolve_system(DerivedSystem(model))
    assert result['estado'] == 'resuelto'
    rows = {r['id']: r['valores'] for r in result['series']}
    extent = rows['observable.' + model['motores']['equilibriumReactions']['volumes']['gas']['extentIds'][0]][-1]
    probe = np.array([1., 2., 3., 4.])
    affinity = ce.evaluate_reactions(ce.IdealGasPhase(SPECIES), np.array([NU], float), T=800., P=1e5, n=probe,
                                     phase_id='vapor', standard_state='ideal_gas_P0')['affinity_RT'][0]
    lnK = mp.fsum(nu * mp.log(mp.mpf(v) / mp.mpf(probe.sum())) for nu, v in zip(NU, probe)) - mp.mpf(affinity)
    root = mp.findroot(lambda x: mp.log(x * x / ((2 - x) * (2 - x))) - lnK, 1)
    assert abs(extent - float(root)) <= 1e-10 * float(root)


# N2, H2, NH3 and methane as a nonreacting species (argon has no Poling cp
# range in the provider and is rejected, located, with OUT_OF_DOMAIN).
INERT_SPECIES = ['7727-37-9', '1333-74-0', '7664-41-7', '74-82-8']
INERT_NU = [-1, -3, 2, 0]


@pytest.fixture(scope='module')
def inert_model():
    return author(species=INERT_SPECIES, nu=INERT_NU, molar_masses=(.028, .002, .017, .016),
                  reference=(1, 3, 0, 1), temperature=700, pressure=1e7, extent_box=(.05, .9), seed=.3)


def test_inert_species_needs_no_potential_and_matches_mpmath_root(inert_model):
    """Re-review B1-F5-4: a zero stoichiometric column never enters the
    affinity, so only reacting species need a recorded mu relation."""
    import mpmath as mp
    mp.mp.dps = 50
    system = DerivedSystem(inert_model)
    assert sorted(system.algebraic_block.potential_rows) == [0, 1, 2]
    result = resolve_system(system)
    assert result['estado'] == 'resuelto'
    entry = inert_model['motores']['equilibriumReactions']['volumes']['gas']
    rows = {r['id']: r['valores'] for r in result['series']}
    extent = rows['observable.' + entry['extentIds'][0]][-1]
    # Independent reference: ln K read once from the provider at an unrelated
    # composition, then a 50-digit root of sum nu ln(y P/P0) = ln K with the
    # inert in the total amount.
    P, P0 = mp.mpf(10)**7, mp.mpf(10)**5
    def log_activity(n):
        total = mp.fsum(n)
        return mp.fsum(nu * mp.log(v / total * P / P0) for nu, v in zip(INERT_NU, n))
    probe = [mp.mpf(v) for v in ('0.7', '2.1', '0.6', '1')]
    affinity = ce.evaluate_reactions(ce.IdealGasPhase(INERT_SPECIES), np.array([INERT_NU], float), T=700., P=1e7,
                                     n=np.array([float(v) for v in probe]), phase_id='vapor', standard_state='ideal_gas_P0')['affinity_RT'][0]
    lnK = log_activity(probe) - mp.mpf(affinity)
    root = mp.findroot(lambda x: log_activity([1 - x, 3 - 3 * x, 2 * x, mp.mpf(1)]) - lnK, mp.mpf('0.3'))
    assert .05 < root < .9
    assert abs(extent - float(root)) <= 1e-9 * float(root)
    amounts = [rows['observable.' + q][-1] for q in entry['amountIds']]
    assert abs(amounts[3] - 1) <= 1e-12  # the inert is conserved
