"""Write a deduction script (rage.deduction-script v1) from a recorded authoring sequence.

The recorded Demo 0.2 equipment (tests/demo02_drum.py, tests/demo02_cstr.py) is authored by Python calls to
the family journals and the equation workbench. This converter runs that authoring once, captures the journal
actions that survive into the recorded model, and rewrites every workbench operation with readable names:
quantity ids become engine quantity names, operation ids become step ids, and source balances become
balance selectors. Hashed ids and input signatures are dropped; the replay tool recomputes them. While
converting, each readable step is replayed through the engine and must give back the recorded operation
exactly (fields and input signatures), so a script that is written is already a proven round trip.

    python tools/research/script_from_recorded.py drum|cstr [--out PATH]
"""
import argparse
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (ROOT, ROOT / 'tests', HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import replay_deduction_script as rds  # noqa: E402

RECORDED = {
    'drum': {'module': 'demo02_drum', 'author': 'author_demo_drum', 'fixture': 'frontend/testing/demo02/flashDrum.ts',
             'operation': 'demo02-drum', 'title': 'Demo 0.2 heated flash drum with outlet momentum (recorded equipment)'},
    'cstr': {'module': 'demo02_cstr', 'author': 'author_demo_cstr', 'fixture': 'frontend/testing/demo02/continuousReactor.ts',
             'operation': 'demo02-cstr', 'title': 'Demo 0.2 continuous jacketed liquid reactor with outlet momentum (recorded equipment)'},
}
EMPTY = lambda journal: isinstance(journal, dict) and not journal.get('volumes')


def capture_journals(author):
    """Run the authoring with every family journal's edit_journal wrapped; return (model, calls)."""
    calls, originals = [], {}
    for family, (_, module, _, _) in rds.JOURNALS.items():
        originals[family] = module.edit_journal

        def wrapped(journal, owner, action, *rest, _family=family, _original=module.edit_journal):
            result = _original(journal, owner, action, *rest)
            calls.append({'family': _family, 'before': copy.deepcopy(journal), 'owner': owner,
                          'action': copy.deepcopy(action), 'after': copy.deepcopy(result)})
            return result
        module.edit_journal = wrapped
    try:
        model = author()[0]
    finally:
        for family, (_, module, _, _) in rds.JOURNALS.items():
            module.edit_journal = originals[family]
    return model, calls


def surviving_actions(model, calls):
    """The chain of journal edits whose result is the recorded journal, per family, in authoring order."""
    chosen = []
    for family, (namespace, _, _, _) in rds.JOURNALS.items():
        target = model['motores'].get(namespace)
        if target is None:
            continue
        chain, index = [], len(calls)
        while not EMPTY(target):
            index = next(i for i in range(index - 1, -1, -1)
                         if calls[i]['family'] == family and calls[i]['after'] == target)
            chain.append(index)
            target = calls[index]['before']
        chosen.extend(chain)
    return [calls[i] for i in sorted(chosen)]


def assumption_entry(number, call, model):
    namespace = rds.JOURNALS[call['family']][0]
    entry = {'id': 'A%d' % number, 'family': call['family'], 'volume': call['owner'], 'action': call['action']['kind']}
    entry.update({k: v for k, v in call['action'].items() if k != 'kind'})
    if call['action']['kind'] != 'start':
        operations = call['after']['volumes'][call['owner']]['operations']
        entry['reason'] = operations[-1]['title'] if operations else ''
    else:
        entry['reason'] = 'Fundamental law of the control volume'
    return entry


def reference(value, step_of, names, rows):
    if value in step_of:
        return step_of[value]
    row = next((r for r in rows if r['id'] == value), None)
    if row and row.get('current') and row['_rhs'] != '0' and row['_lhs'].startswith('Derivative('):
        family, owner = value.split('.')[:2]
        quantity = row['_lhs'][len('Derivative('):-len(', t)')]
        selector = 'balance:%s.%s:%s' % (family, owner, quantity)
        candidates = [r for r in rows if r['id'].startswith(family + '.' + owner + '.') and r.get('current')
                      and r['_lhs'] == row['_lhs'] and r['_rhs'] != '0']
        if len(candidates) == 1:
            return selector
    return 'eq:' + value


def readable_step(number, operation, step_of, names, rows):
    step = {'id': 's%d' % number}
    for field, value in operation.items():
        if field == 'sourceSignatures':
            continue
        if field in ('sources', 'domains'):
            step[field] = [reference(v, step_of, names, rows) for v in value]
        elif field == 'relation':
            step[field] = reference(value, step_of, names, rows)
        elif field == 'symbol':
            step[field] = names.to_readable_quantity(value)
        elif field == 'dependencies':
            step[field] = [names.to_readable_quantity(v) for v in value]
        elif field in rds.EXPRESSIONS and isinstance(value, str):
            step[field] = names.to_readable_expression(value)
        else:
            step[field] = copy.deepcopy(value)
    return step


def convert(name):
    spec = RECORDED[name]
    module = __import__(spec['module'])
    recorded, calls = capture_journals(getattr(module, spec['author']))
    fixture = rds.load_document(spec['fixture'], ROOT)
    if fixture != recorded:
        raise SystemExit('The recorded fixture %s is stale against %s; regenerate it first.' % (spec['fixture'], spec['module']))
    assumptions = [assumption_entry(i, call, recorded) for i, call in enumerate(surviving_actions(recorded, calls), 1)]
    script = {'format': rds.FORMAT, 'version': rds.VERSION, 'operation': spec['operation'], 'title': spec['title'],
              'note': ('Converted by tools/research/script_from_recorded.py from %s.%s. The system document is the recorded '
                       'fixture with every deduction removed (journals, workbench, Solve selection); the replay rebuilds them.'
                       % (spec['module'], spec['author'])),
              'system': {'document': spec['fixture'], 'base': 'repository'},
              'fundamentalAssumptions': assumptions, 'steps': [], 'results': [], 'findings': [], 'validation': []}
    # Replay the assumptions with the tool itself, then convert and check each operation against the recording.
    session = rds.DocumentSession(rds.strip_system(fixture))
    for entry in assumptions:
        session.assume(entry['family'], entry['volume'], rds.assumption_action(entry))
    session.close_assumptions()
    report = session.report()
    plain = rds.plain_rows(session)
    rows = [{**row, '_lhs': plain[row['id']]['lhs'], '_rhs': plain[row['id']]['rhs']} for row in report['equations']]
    session.source_rows = rows
    names = rds.Names.from_report(report)
    step_of, ids = {}, {}
    for number, operation in enumerate(recorded['motores']['equationWorkbench']['operations'], 1):
        step = readable_step(number, operation, step_of, names, rows)
        translated = rds.translate(step, ids, session, names)
        replayed = session.append(translated)
        produced = replayed['definition']['operations'][-1]
        if produced != operation:
            raise SystemExit('Step s%d does not reproduce the recorded operation:\n%s\n%s' % (number, produced, operation))
        script['steps'].append(step)
        step_of['operation.%d' % number] = step['id']
        ids[step['id']] = 'operation.%d' % number
        names = rds.Names.from_report(replayed)
        if number % 20 == 0:
            print('%d operations converted' % number, file=sys.stderr)
    session.finish()
    selection = recorded['motores'].get('derivedExecution', {})
    for index, state in enumerate(selection.get('states', []), 1):
        key = state['equationId']
        script['results'].append({'id': 'r%d' % index, 'fromStep': step_of.get(key, 'eq:' + key),
                                  'statement': 'State equation of %s' % names.readable.get(state['quantityId'], state['quantityId'])})
    script['validation'] = VALIDATION[name](script)
    return script


def _state_step(script, quantity):
    return next(r['fromStep'] for r in script['results'] if r['statement'] == 'State equation of ' + quantity)


def _outlet_momentum(owner, data):
    """Independent hand formula of the outlet path: (L/A) dF/dt = P + rho g V_L/A_c - p_out - (K + f_D L/D_h) F|F|/(2 rho A^2)."""
    rho = data['M_L'] / data['v_L']
    hydraulic = math.sqrt(4 * data['A'] / math.pi)
    loss = (data['K'] + data['fD'] * data['L'] / hydraulic) * data['F'] * abs(data['F']) / (2 * rho * data['A'] ** 2)
    expected = data['A'] / data['L'] * (data['P'] + rho * data['g'] * data['V_L'] / data['Ac'] - data['Pout'] - loss)
    inputs = {'A__pipe': data['A'], 'L__pipe': data['L'], 'K__pipe': data['K'], 'outletPressure': data['Pout'],
              'P__%s(t)' % owner: data['P'], 'g__%s' % owner: data['g'], 'crossSectionArea': data['Ac'],
              'liquid_volume__%s(t)' % owner: data['V_L'], 'phase_M__%s__L(t)' % owner: data['M_L'],
              'phase_v__%s__L(t)' % owner: data['v_L'], 'liquidMassFlow(t)': data['F']}
    if data['fD']:
        inputs['darcyFriction'] = data['fD']
    return inputs, expected


def drum_validation(script):
    flow = dict(A=7e-4, L=5.0, K=8.0, fD=0.024, Pout=101325.0, P=101325.0, g=9.80665, Ac=0.5, V_L=0.08,
                M_L=0.0194, v_L=2.1e-5, F=0.4)
    inputs, expected = _outlet_momentum('drum', flow)
    mass = dict(feed=0.5, wF=0.15, M1=0.04607, F=0.4, xL=0.05, ML=0.0194, beta=1.0, xV=0.3, V=2.0)
    return [
        {'case': 'V1', 'equation': _state_step(script, 'liquidMassFlow(t)'), 'solveFor': 'Derivative(liquidMassFlow(t), t)',
         'inputs': inputs, 'expected': expected, 'tolerance': {'relative': 1e-12},
         'cite': 'Independent hand formula of the outlet momentum balance (tests/derived_momentum_inputs.py reference_outlet), '
                 'with D_h = (4 A/pi)^(1/2); closure values are inputs, not package evaluations'},
        {'case': 'V2', 'equation': _state_step(script, 'm__drum__1(t)'), 'solveFor': 'Derivative(m__drum__1(t), t)',
         'inputs': {'feedRate': mass['feed'], 'inlet_mass_fraction_1__feed(t)': mass['wF'], 'molar_mass_1__drum': mass['M1'],
                    'liquidMassFlow(t)': mass['F'], 'phase_x_1__drum__L(t)': mass['xL'], 'phase_M__drum__L(t)': mass['ML'],
                    'phase_present__drum__V(t)': mass['beta'], 'phase_x_1__drum__V(t)': mass['xV'], 'vapourMolarOutflow(t)': mass['V']},
         'expected': mass['feed'] * mass['wF'] - mass['F'] * mass['xL'] * mass['M1'] / mass['ML'] - mass['M1'] * mass['beta'] * mass['xV'] * mass['V'],
         'tolerance': {'relative': 1e-12},
         'cite': 'Independent hand formula: feed w_F F minus the liquid donor F x_1 M_1/M_L minus the vapour donor M_1 x_1V n_V'},
    ]


def cstr_validation(script):
    flow = dict(A=1.25e-5, L=0.4, K=1250.0, fD=0.0, Pout=101325.0, P=101325.0, g=9.80665, Ac=0.003, V_L=6.5e-4,
                M_L=0.06, v_L=7.0e-5, F=1e-3)
    inputs, expected = _outlet_momentum('cell', flow)
    return [
        {'case': 'V1', 'equation': _state_step(script, 'liquidMassFlow(t)'), 'solveFor': 'Derivative(liquidMassFlow(t), t)',
         'inputs': inputs, 'expected': expected, 'tolerance': {'relative': 1e-12},
         'cite': 'Independent hand formula of the outlet momentum balance with negligible distributed friction (f_D = 0) and the '
                 'local loss K = 1250; closure values are inputs, not package evaluations'},
    ]


VALIDATION = {'drum': drum_validation, 'cstr': cstr_validation}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('name', choices=sorted(RECORDED))
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    script = convert(args.name)
    out = Path(args.out) if args.out else HERE / 'scripts' / (RECORDED[args.name]['operation'] + '.deduction.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(script, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print('wrote', out)


if __name__ == '__main__':
    main()
