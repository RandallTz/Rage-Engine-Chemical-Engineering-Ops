"""Prepare a steady selection through the existing dynamic/steady compilers.

No new law or steady solver lives here. Numerical defaults are editable data;
physical validity and zero-rate admission remain the compiler's responsibility.
"""
from copy import deepcopy
import math
import sympy as sp
from core.compilador.derived import DerivedSystem, LoweringError
from core.compilador.steady import SteadySystem, signature
from core.modelo.derived_execution import read_definition
from core import unidades
from core.mathematics.constants import si_magnitude


# Editable placeholder meaning "no bound" (the v5 data must be finite), in SI units of
# any dimension. Recorded domains and positive inventories still set the lower bounds.
DEFAULT_BOUND_REACH = 1e12


def prepare_steady_transform(model):
    selection = read_definition(model.get('motores', {}).get('derivedExecution'), model)
    if selection['version'] == 5:
        raise LoweringError('steady_transform_requires_dynamic', 'Select a dynamic formulation before applying zero accumulation.')
    dynamic = DerivedSystem(deepcopy(model))
    output = deepcopy(model)
    selected = {key: deepcopy(selection[key]) for key in
                ('format', 'sourceSignature', 'timeId', 'states', 'parameters', 'reconstructions', 'checks')}
    selected.update(version=5, algebraic=deepcopy(selection.get('algebraic', [])), invariants={}, unknowns=[])
    config = deepcopy(selection.get('nonlinear', dict(variables={}, residualScales={},
        residualTolerance=1e-10, stepTolerance=1e-12, maxIterations=30, maxBacktracks=20)))
    selected['nonlinear'] = config

    def datum(key, value, unit):
        if not math.isfinite(float(value)):
            raise LoweringError('steady_transform_missing_seed', 'A finite initialized value is required: '+key)
        base = 'steadyTransform.'+key
        identity = base
        index = 1
        while identity in output['datos'] and output['datos'][identity].get('origen') != {'propietarioId': 'estudio', 'ruta': base}:
            identity = base+'.'+str(index); index += 1
        output['datos'][identity] = {'magnitud': key, 'funcion': 'estudio',
            'declaracion': {'texto': str(float(value)), 'unidad': unit},
            'origen': {'propietarioId': 'estudio', 'ruta': 'steadyTransform.'+key}}
        return identity

    def occurring_magnitudes(expression, dimension):
        values = []
        occurring = expression.free_symbols
        for q, parameter in dynamic.parameter_symbols.items():
            if parameter in occurring and parameter in dynamic.parameter_values:
                try:
                    if dynamic._dim(q) == dimension:
                        values.append(abs(float(dynamic.parameter_values[parameter])))
                except (ValueError, LoweringError, TypeError):
                    continue
        return values

    def residual_scale(equation):
        residual = equation.lhs-equation.rhs
        dimension = dynamic._dim(residual)
        candidates = []
        # Keep separate terms so cancellation at the initial state cannot erase
        # the characteristic flow or power. All evaluation remains in Python.
        substitutions = {**dynamic.parameter_values, **dynamic.initial_values,
                         **getattr(dynamic, 'initial_algebraic', {}), **dynamic.initial_closure, dynamic.time: 0}
        expanded = dynamic._expand(residual)
        # Only data that occur in this row can set its scale (RT-6); an unrelated
        # datum of the same dimension never does.
        candidates.extend(occurring_magnitudes(expanded, dimension))
        expanded = expanded.xreplace({d: sp.S.Zero for d in expanded.atoms(sp.Derivative)})
        for term in sp.Add.make_args(sp.expand(expanded)):
            value = si_magnitude(term).subs(substitutions)
            if value.is_number and value.is_real and value.is_finite:
                candidates.append(abs(float(value)))
        scale = max(candidates, default=0.)
        if scale <= 0:
            raise LoweringError('steady_transform_missing_scale', 'Declare a nonzero characteristic magnitude for the residual.', str(equation))
        return scale

    mass_dimension = unidades.interpretar('kg')['dimension']
    mass_flow_dimension = unidades.interpretar('kg/s')['dimension']
    characteristic = {}

    def characteristic_time():
        # tau = declared characteristic inventory / characteristic mass flow, both
        # model data: the check scale of a mass budget and the residual scale of
        # the mass-rate rows. Never the initial state (RT-11).
        if 'tau' not in characteristic:
            inventories = []
            for check in selection['checks']:
                key = check.get('scaleDataId')
                try:
                    inventories.append(abs(float(dynamic._datum(key, mass_dimension))))
                except (KeyError, ValueError, LoweringError, TypeError):
                    continue
            flows = []
            for state_row in selection['states']:
                equation = dynamic._equation(state_row['equationId']).equation
                if dynamic._dim(equation.lhs-equation.rhs) == mass_flow_dimension:
                    flows.append(residual_scale(equation))
            characteristic['tau'] = max(inventories)/max(flows) if inventories and flows and max(inventories) > 0 else None
        return characteristic['tau']

    def variable_scale(q, equation, fallback):
        tau = characteristic_time()
        # A state scale is its row's residual scale times the characteristic time;
        # without declared inventory or flow the seed-based fallback remains.
        return residual_scale(equation)*tau if tau else fallback

    def numerical_bounds(q, seed, scale, equation):
        # The reach never comes from the initial state (RT-7, RT-9): the root of a
        # steady selection must not depend on the initial holdup. It is the
        # documented numerical default DEFAULT_BOUND_REACH (SI units), widened
        # only by data of the quantity's own dimension that occur in its row
        # (RT-10). The result is written as editable lower/upper data, reported in Solve.
        reach = max([DEFAULT_BOUND_REACH, *occurring_magnitudes(dynamic._expand(equation.lhs-equation.rhs), dynamic._dim(q))])
        lower, upper = -reach, reach
        # These names identify inventories emitted by the physical producers;
        # an arbitrary mathematical quantity is never classified by its unit.
        name = q.func.__name__ if q.is_Function else str(q)
        inventory_names = {name for v in model['volumenes'] for name in
            [*(f'm__{v["id"]}__{cid}' for cid in v['componenteIds']),
             *(f'n_{cid}__{v["id"]}' for cid in v['componenteIds']),
             f'm__{v["id"]}', f'n__{v["id"]}', f'T__{v["id"]}', f'P__{v["id"]}', f'V__{v["id"]}']}
        if name in inventory_names or q.is_nonnegative:
            lower = min(seed, scale*1e-8) if seed >= 0 else 0.
        for premise in dynamic.graph.domains.values():
            if premise.quantity != q:
                continue
            allowed = premise.allowed
            if isinstance(allowed, sp.Interval):
                factor = float(si_magnitude(premise.scale))
                if allowed.start.is_finite:
                    lower = max(lower, float(allowed.start)*factor + (scale*1e-8 if allowed.left_open else 0.))
                if allowed.end.is_finite:
                    upper = min(upper, float(allowed.end)*factor - (scale*1e-8 if allowed.right_open else 0.))
        return lower, upper

    for row in selection['states']:
        qid = row['quantityId']; q = dynamic._quantity(qid)
        seed = float(dynamic.initial_values[q]); unit = dynamic._unit(q)
        seed_id = selection['initialValues'].get(qid) or datum(qid+'.seed', seed, unit)
        rate = dynamic.rates[sp.Derivative(q, dynamic.time)].subs(dynamic.parameter_values)
        # Only exact individually conserved states can be bound by v5. Coupled
        # conserved totals still receive the canonical structural rejection.
        if sp.cancel(rate) == 0:
            selected['invariants'][qid] = seed_id
            continue
        equation = dynamic._equation(row['equationId']).equation
        scale = variable_scale(q, equation, max(abs(seed), 1.))
        lower, upper = numerical_bounds(q, seed, scale, equation)
        bounds = selection.get('dae', {}).get('stateBounds', {}).get(qid)
        config['variables'][qid] = {'seedDataId': seed_id,
            'lowerDataId': bounds['lowerDataId'] if bounds else datum(qid+'.lower', lower, unit),
            'upperDataId': bounds['upperDataId'] if bounds else datum(qid+'.upper', upper, unit),
            'scaleDataId': datum(qid+'.scale', scale, unit)}
        equation = dynamic._equation(row['equationId']).equation
        config['residualScales'][row['equationId']] = datum(row['equationId']+'.residualScale', residual_scale(equation), dynamic._unit(equation.lhs-equation.rhs))
    # Affine blocks have no Newton settings; their initialized values seed v5.
    for row in selected['algebraic']:
        qid = row['quantityId']; q = dynamic._quantity(qid)
        if qid not in config['variables']:
            initial = getattr(dynamic, 'initial_algebraic', {}).get(q)
            if initial is None:
                initial = dynamic._expand(q).subs({**dynamic.parameter_values, **dynamic.initial_values, dynamic.time: 0})
            seed = float(initial); scale = max(abs(seed), 1.); unit = dynamic._unit(q)
            lower, upper = numerical_bounds(q, seed, scale, dynamic._equation(row['equationId']).equation)
            config['variables'][qid] = {key: datum(qid+'.'+key, value, unit) for key, value in
                [('seedDataId', seed), ('lowerDataId', lower), ('upperDataId', upper), ('scaleDataId', scale)]}
            equation = dynamic._equation(row['equationId']).equation
            config['residualScales'][row['equationId']] = datum(row['equationId']+'.residualScale', residual_scale(equation), dynamic._unit(equation.lhs-equation.rhs))
    for row in selected['checks']:
        equation = dynamic._equation(row['equationId']).equation
        # A transient budget uses an inventory scale; the steady check is a
        # rate residual. Preserve the original datum and declare a new SI scale.
        row['scaleDataId'] = datum(row['equationId']+'.checkScale', residual_scale(equation), dynamic._unit(equation.lhs-equation.rhs))
    selected['unknowns'] = [r['quantityId'] for r in [*selected['states'], *selected['algebraic']]
                            if r['quantityId'] not in selected['invariants']]
    output['motores']['derivedExecution'] = selected
    output['estudio'] = {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}
    report = SteadySystem(output).report
    return {'format': 'rage.steady-transform', 'version': 1, 'model': output,
            'dynamicSelection': deepcopy(selection), 'dynamicSignature': signature(selection), 'report': report}
