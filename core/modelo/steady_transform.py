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

    def declared_magnitudes(dimension):
        values = []
        for key, entry in model['datos'].items():
            if entry.get('origen', {}).get('ruta', '').startswith('steadyTransform.'):
                continue
            try:
                if unidades.interpretar(entry['declaracion']['unidad'])['dimension'] == dimension:
                    values.append(abs(float(dynamic._datum(key, dimension))))
            except (ValueError, LoweringError):
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
        occurring = expanded.free_symbols
        for q, parameter in dynamic.parameter_symbols.items():
            if parameter in occurring and parameter in dynamic.parameter_values:
                try:
                    if dynamic._dim(q) == dimension:
                        candidates.append(abs(float(dynamic.parameter_values[parameter])))
                except (ValueError, LoweringError, TypeError):
                    continue
        expanded = expanded.xreplace({d: sp.S.Zero for d in expanded.atoms(sp.Derivative)})
        for term in sp.Add.make_args(sp.expand(expanded)):
            value = si_magnitude(term).subs(substitutions)
            if value.is_number and value.is_real and value.is_finite:
                candidates.append(abs(float(value)))
        scale = max(candidates, default=0.)
        if scale <= 0:
            raise LoweringError('steady_transform_missing_scale', 'Declare a nonzero characteristic magnitude for the residual.', str(equation))
        return scale

    def numerical_bounds(q, seed, scale):
        # The reach comes from declared magnitudes of the quantity's dimension and
        # a wide factor, never from the initial state alone (RT-7): the root of a
        # steady selection must not depend on the initial holdup.
        reach = 1e3*max([scale, *declared_magnitudes(dynamic._dim(q))])
        lower, upper = seed-reach, seed+reach
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
        scale = max(abs(seed), 1.)
        lower, upper = numerical_bounds(q, seed, scale)
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
            lower, upper = numerical_bounds(q, seed, scale)
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
