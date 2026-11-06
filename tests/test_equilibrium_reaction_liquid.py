"""B3 part 1 (claude-b, 6 November 2026): liquid-phase equilibrium extent constraints.

The Model records mu_i = mu_i*(T,P) + R T log(x_i gamma_i) for each reacting
species as a thermodynamic constitutive relation of the declared package liquid,
substitutes it into the stationary-Gibbs affinity, and the compiler matches it
to the executed PackagePhase (R, standard state, functional form, package).

References are independent of core.mezclas/core.unifac/core.reactions: thermo's
UNIFAC for ln gamma and a 50-digit mpmath pure-liquid potential for ln K
(tests/equilibrium_reaction_liquid_inputs.py).
"""
import copy
import mpmath as mp
import numpy as np
import pytest
from sympy.core.function import AppliedUndef
from chemicals.elements import simple_formula_parser
from chemicals.identifiers import search_chemical
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.derived_graph import LoweringError, source_signature
from core.modelo import leer_modelo_comun
from equilibrium_reaction_liquid_inputs import (SPECIES, NU, ACETONE, TEMPERATURE, PRESSURE, esterification,
                                                reference_extent)

OWNER = 'liquid'
LOCATED = 'motores.equilibriumReactions.volumes.' + OWNER


@pytest.fixture(scope='module')
def model():
    return esterification()


@pytest.fixture(scope='module')
def ideal_form():
    """The same Model with an ideal-solution relation (no activity coefficient);
    its ideal-solution root is 0.7702 (gamma = 1)."""
    return esterification(form='ideal', extent_box=(.75, .79), seed=.77)


@pytest.fixture(scope='module')
def inert_model():
    return esterification(inert=True, extent_box=(.65, .68), seed=.66)


def _resign(changed):
    changed['motores']['derivedExecution']['sourceSignature'] = source_signature(changed)
    return changed


def _with_package(model, package):
    changed = copy.deepcopy(model)
    changed['termodinamica']['paquetes'][0]['modelo']['id'] = package
    return _resign(changed)


def _rejected(changed):
    with pytest.raises(LoweringError) as caught:
        DerivedSystem(changed)
    return caught.value.diagnostics[0]


def _solve(model):
    system = DerivedSystem(model)
    result = resolve_system(system)
    assert result['estado'] == 'resuelto'
    rows = {r['id']: r['valores'] for r in result['series']}
    entry = model['motores']['equilibriumReactions']['volumes'][OWNER]
    extent = rows['observable.' + entry['extentIds'][0]][-1]
    amounts = [rows['observable.' + q][-1] for q in entry['amountIds']]
    return system, extent, amounts


def _element_residual(species, initial, amounts):
    atoms = [simple_formula_parser(search_chemical(c).formula) for c in species]
    elements = sorted({e for a in atoms for e in a})
    return max(abs(sum(a.get(e, 0) * (n - n0) for a, n, n0 in zip(atoms, amounts, initial))) for e in elements)


def test_liquid_potential_is_a_recorded_constitutive_relation_of_the_package(model):
    system = DerivedSystem(model)
    block = system.algebraic_block
    assert block.activity == 'activity' and sorted(block.potential_rows) == [0, 1, 2, 3]
    operations = model['motores']['equationWorkbench']['operations']
    for key in block.potential_rows.values():
        operation = operations[int(key.split('.')[1]) - 1]
        assert (operation['kind'], operation['relationKind'], operation['family']) == ('declare_relation', 'constitutive', 'thermodynamics')
        names = {f.func.__name__ for f in system.graph.nodes[key].equation.rhs.atoms(AppliedUndef)}
        assert any(n.startswith('activityCoefficient') for n in names) and any(n.startswith('pureLiquidPotential') for n in names)
    # Each x_i gamma_i > 0 premise is discharged by the provider, with its relation as source.
    discharged = {c['sourceEquationId'] for c in system.proof_conditions if 'activityCoefficient' in c['latex']}
    assert discharged == set(block.potential_rows.values())
    proof = block.extent_proof
    assert proof['certified'] and proof['provider']['fingerprints']['activityModel']
    assert 'package reactionLiquid liquid (unifac-original-public, activity model LiquidoUNIFAC' in system.dae.proof['proof']


@pytest.mark.parametrize('package,variant', [('unifac-original', 'original'), ('unifac-dortmund', 'dortmund')])
def test_compiled_extent_matches_independent_unifac_root(model, package, variant):
    """|xi - xi_ref| <= 1e-10 xi_ref with thermo's UNIFAC and mpmath ln K."""
    _, extent, amounts = _solve(_with_package(model, package))
    root = reference_extent(SPECIES, NU, (1, 1, 0, 0), TEMPERATURE, PRESSURE, variant, extent)
    assert abs(extent - float(root)) <= 1e-10 * float(root)
    assert _element_residual(SPECIES, (1, 1, 0, 0), amounts) <= 1e-12
    assert all(n > 0 for n in amounts)


def test_inert_solvent_needs_no_potential_and_enters_the_mole_fractions(inert_model):
    """B1-F5-4 for liquids: acetone's zero column needs no mu relation, but it
    dilutes x_i and changes gamma_i, hence the extent (0.634 without it)."""
    system, extent, amounts = _solve(inert_model)
    assert sorted(system.algebraic_block.potential_rows) == [0, 1, 2, 3]
    species = SPECIES + [ACETONE]
    root = reference_extent(species, NU + [0], (1, 1, 0, 0, 2), TEMPERATURE, PRESSURE, 'original', extent)
    assert abs(extent - float(root)) <= 1e-10 * float(root)
    assert abs(extent - .634) > .02
    assert abs(amounts[4] - 2) <= 1e-12
    assert _element_residual(species, (1, 1, 0, 0, 2), amounts) <= 1e-12


def test_ideal_solution_package_accepts_only_the_ideal_relation(model, ideal_form):
    """The package's liquid model fixes the form: an ideal-solution package runs
    the ideal relation (independent root with gamma = 1) and rejects gamma_i."""
    _, extent, _ = _solve(_with_package(ideal_form, 'mezcla-ideal'))
    root = reference_extent(SPECIES, NU, (1, 1, 0, 0), TEMPERATURE, PRESSURE, None, extent)
    assert abs(extent - float(root)) <= 1e-10 * float(root)
    diagnostic = _rejected(_with_package(model, 'mezcla-ideal'))
    assert diagnostic['code'] == 'reaction_chemical_potential_provider_mismatch'
    assert diagnostic['path'].startswith('operation.')


def test_relation_without_activity_coefficient_is_rejected_for_unifac(ideal_form):
    diagnostic = _rejected(ideal_form)
    assert diagnostic['code'] == 'reaction_chemical_potential_provider_mismatch'
    assert diagnostic['path'].startswith('operation.') and 'gamma_i' in diagnostic['message']


def test_nrtl_package_is_unsupported_and_located(model):
    diagnostic = _rejected(_with_package(model, 'nrtl-chemsep'))
    assert diagnostic['code'] == 'PROVIDER_UNSUPPORTED' and diagnostic['path'] == LOCATED + '.packageId'
    assert 'NRTL is not extended' in diagnostic['message']


def test_liquid_relation_must_use_the_provider_gas_constant(model):
    changed = copy.deepcopy(model)
    changed['datos']['R']['declaracion']['texto'] = '8.314'
    diagnostic = _rejected(_resign(changed))
    assert diagnostic['code'] == 'reaction_gas_constant_mismatch' and diagnostic['path'].startswith('operation.')


@pytest.mark.parametrize('field,value,code,suffix', [
    ('anchor', 'gas', 'LIQUID_ANCHOR_REQUIRED', '.anchor'),
    ('phaseId', 'vapor', 'STANDARD_STATE_MISMATCH', ''),
    ('standardState', 'ideal_gas_P0', 'STANDARD_STATE_MISMATCH', '')])
def test_declaration_must_match_the_liquid_provider(model, field, value, code, suffix):
    changed = copy.deepcopy(model)
    changed['motores']['equilibriumReactions']['volumes'][OWNER][field] = value
    diagnostic = _rejected(_resign(changed))
    assert diagnostic['code'] == code and diagnostic['path'] == LOCATED + suffix


@pytest.mark.parametrize('mutate', [
    lambda e: e.update(packageId='missing'),
    lambda e: e.update(provider='ideal_gas')])
def test_reader_binds_package_identity_to_the_package_provider(model, mutate):
    from core.modelo.lector import ErrorModelo
    changed = copy.deepcopy(model)
    mutate(changed['motores']['equilibriumReactions']['volumes'][OWNER])
    with pytest.raises(ErrorModelo) as caught:
        leer_modelo_comun(changed)
    assert caught.value.ruta == 'motores.equilibriumReactions'


def test_package_declaration_without_package_loads_but_is_rejected_located(model):
    """Package declarations saved before packageId existed still load."""
    changed = copy.deepcopy(model)
    changed['motores']['equilibriumReactions']['volumes'][OWNER].pop('packageId')
    changed = _resign(changed)
    assert leer_modelo_comun(changed) == changed
    diagnostic = _rejected(changed)
    assert diagnostic['code'] == 'reaction_package_missing' and diagnostic['path'] == LOCATED + '.packageId'
