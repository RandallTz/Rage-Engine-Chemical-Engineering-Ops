"""Heat connection between two flowsheet instances (F4, J-2): reactor <-> cooling jacket.

Two separately recorded equipment templates replace the single jacketed-reactor
document of tests/jacketed_reactor_inputs.py:

- `duty-cstr`: the accepted Demo 0.2 continuous reactor deduced through the same
  shared author, whose boundary heat is a prescribed duty datum (`heatDuty`,
  datum `solve.Q`) on its `jacket` heat port, instead of the Demo 0.2 reservoir law;
- `jacket-service`: the standalone jacket service volume, whose `wall` heat port
  carries the recorded wall law wallHeat = wallConductance (processTemperature - T_jacket)
  with the declared exterior temperature datum `service.Tprocess`.

The flowsheet connects R.jacket to J.wall (a rage.flowsheet v1 connection with the optional `heat` key). The
assembly replaces the jacket's exterior temperature datum by the reactor
temperature and the reactor's prescribed duty datum by minus the jacket's
resolved boundary heat: one duty, equal and opposite in the two first laws.
Nothing here writes a balance, a closure value or the coupled term.

Fresh test sources, never product-library examples. Authoring replays the whole
history per operation (J-4), so `authored()` caches the two documents under
.tmp/flowsheet_heat keyed by the input sources and data.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.modelo.equation_workbench import build  # noqa: E402
from core.mathematics.dimensions import catalog  # noqa: E402
from core.compilador.derived import source_signature  # noqa: E402
from derived_momentum_inputs import author_outlet, select_outlet  # noqa: E402
from derived_reactor_inputs import OWNER as REACTOR  # noqa: E402
from jacketed_reactor_inputs import SERVICE, JACKETED, jacketed_data, T  # noqa: E402
import demo02_cstr  # noqa: E402

CACHE = ROOT / '.tmp' / 'flowsheet_heat'
SOURCES = ['tests/flowsheet_heat_inputs.py', 'tests/jacketed_reactor_inputs.py', 'tests/demo02_cstr.py',
           'tests/derived_momentum_inputs.py', 'tests/derived_reactor_inputs.py', 'tests/derived_closure_inputs.py',
           'tests/m1_acceptance.py']


def duty_template():
    """The Demo 0.2 reactor template whose `jacket` heat port names the retained boundary heat term."""
    template = demo02_cstr.template()
    template.update(id='duty-cstr', templateVersion='1')
    return template


def record_premises(author, out):
    """The Demo 0.2 validity premises (demo02_cstr.record_premises), attached where their quantity occurs.

    With a prescribed duty the energy row no longer contains T (only the reservoir law did), so the
    liquid-only premise on T is attached to the first recorded kinetic row that contains it.
    """
    q = author.quantity
    temperature = sp.Function('T__' + REACTOR)(T)
    from core.mathematics.errors import MathematicsError
    graph = author.result.graph
    # Prefer the reactor's own kinetic rows (the rate law holds T), then any row of this volume holding T.
    candidates = sorted((k for k, node in graph.nodes.items() if node.equation.has(temperature)),
                        key=lambda k: (not k.startswith('reaction.' + REACTOR), not k.startswith('operation.'), k))
    for hosting in candidates:
        try:
            author.append('declare_domain', graph.nodes[hosting].family, sources=[hosting], symbol=q(temperature), domain='real',
                          reason='Liquid-only premise of the thermodynamic journal: the temperature must stay below the bubble temperature of the '
                                 'liquid at the volume pressure. Not monitored at run time; the lowest-boiling azeotrope of the four species is near 343 K at 101.3 kPa')
            break
        except MathematicsError:
            continue
    else:
        raise RuntimeError('No selected row of the reactor holds its temperature: ' + ', '.join(candidates))
    for symbol, reason in [(sp.Function('P__' + REACTOR)(T),
                            'Uniform-pressure premise: energy, closure and kinetics use the uniform vapour-space pressure; the hydrostatic increase in '
                            'the liquid (a few kPa, about 2e-3 K on the caloric state) is neglected'),
                           (sp.Function('phase_v__' + REACTOR + '__L')(T),
                            'Constant-molar-volume premise of the package: pure-component liquid molar volumes at 298.15 K with ideal mixing; about 4-5 % '
                            'density error at 335-340 K in the control volume, concentrations and holdup')]:
        author.append('declare_domain', 'momentum', sources=[out['flow']], symbol=q(symbol), domain='positive', reason=reason)


def author_duty_reactor(data=None, method='bdf'):
    """The Demo 0.2 continuous reactor with a prescribed boundary duty (`heatDuty`, datum solve.Q)."""
    data = dict(jacketed_data(), Q=0.0) if data is None else data
    author, out = author_outlet(data, prepare=lambda model: demo02_cstr.prepare(model, data),
                                source_factory=demo02_cstr.continuous_source, owner=REACTOR, vapour=False,
                                heat_builder=None, reactive=True)
    for i in (1, 2, 3, 4):
        out[f'reactionAmount.{i}'] = author.append('isolate', sources=[f'reaction.{REACTOR}.amount.{i}'],
                                                  symbol=author.quantity(sp.Function(f'amount_{i}__{REACTOR}')(T)))
    record_premises(author, out)
    author.model['template'] = duty_template()
    model = select_outlet(author, out, data, method, owner=REACTOR)
    replayed = build(model)
    model.update(id='duty-reactor', nombre='Continuous liquid reactor with a prescribed boundary duty (test)')
    model['motores']['derivedExecution']['sourceSignature'] = source_signature(model, replayed)
    return model


def service_data():
    """The jacket of the accepted jacketed reactor: its UA, coolant and initial state; Tprocess is replaced when connected."""
    return dict(SERVICE, **{k: v for k, v in JACKETED.items() if k in SERVICE and k != 'tf'})


MOMENTUM_PREMISE = {'kind': 'prescribed_flows',
                    'reason': 'The coolant pump outside the jacket sets the supply flow and the rigid filled jacket returns it; '
                              'no flow of this equipment is set by its own momentum balance (finding J-1)'}


def author_service_jacket(data=None, method='bdf'):
    """The jacket service template for the flowsheet: no momentum balance, under the recorded prescribed-flow
    premise (J-1), and the single coolant species recorded (J-6), so the return equals the supply exactly.
    The process-side temperature is the wall port's exterior datum `service.Tprocess`."""
    from core.modelo import leer_modelo_comun
    from core.mathematics.dimensions import catalog
    from m1_acceptance import SharedAuthor
    from derived_closure_inputs import _datum
    from jacketed_reactor_inputs import JACKET, jacket_shell, add_jacket_volume, author_jacket, jacket_template, _jacket_selection
    data = service_data() if data is None else data
    author = SharedAuthor(leer_modelo_comun(add_jacket_volume(jacket_shell(data), data, momentum_balance=False)))
    out = author_jacket(author, JACKET, 1, None, None, single_species=True)
    template = jacket_template()
    template['recipe']['journals'] = [k for k in template['recipe']['journals'] if k != 'momentumDerivation']
    template['momentumPremise'] = copy.deepcopy(MOMENTUM_PREMISE)
    author.model['template'] = template
    model, _, _ = author.finish({})
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    sel = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': None,
           'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
           'reconstructions': [], 'checks': []}
    _jacket_selection(sel, model, quantities, out, data, JACKET, 1)
    sel['parameters'][named('processTemperature')] = _datum(model, 'service.Tprocess', data['Tprocess'], 'K')
    # No transient mass-budget check: the jacket mass rate is identically zero (J-6), so the budget is the
    # recorded invariant itself and has no characteristic residual scale in the steady mode.
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'solve.tf', data['tf'], 's', 'estudio'),
                        'metodoSolicitado': method, 'muestras': 61, 'rtol': 1e-9, 'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    model['motores']['derivedExecution'] = sel
    sel['sourceSignature'] = source_signature(model, replayed)
    return model


def _key(name):
    """Each document is cached on what it is authored from: its author functions in this module, the shared
    input modules and the data. Editing the other document's author does not invalidate it."""
    import inspect
    own = {'reactor': (duty_template, record_premises, author_duty_reactor),
           'jacket': (author_service_jacket,)}[name]
    digest = hashlib.sha256()
    for function in own:
        digest.update(inspect.getsource(function).encode())
    shared = [p for p in SOURCES if p != 'tests/flowsheet_heat_inputs.py']
    for path in shared if name == 'jacket' else [p for p in shared if p != 'tests/jacketed_reactor_inputs.py']:
        digest.update((ROOT / path).read_bytes())
    digest.update(json.dumps([name, jacketed_data(), service_data(), MOMENTUM_PREMISE], sort_keys=True, default=str).encode())
    return digest.hexdigest()[:16]


def _cached(name, factory):
    path = CACHE / (name + '-' + _key(name) + '.json')
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    document = factory()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    return document


def authored():
    """(reactor, jacket) recorded documents, authored once per input revision."""
    return _cached('reactor', author_duty_reactor), _cached('jacket', author_service_jacket)


def _study_datum(model, key, value, unit):
    model['datos'][key] = {'magnitud': key, 'funcion': 'estudio', 'declaracion': {'texto': repr(float(value)), 'unidad': unit},
                           'origen': {'propietarioId': 'estudio', 'ruta': key}}
    return key


def heat_flowsheet(reactor, jacket, tf=None, samples=81, method='bdf', law='to'):
    """Shell model: R.jacket <-> J.wall heat connection; material ports exposed.

    law: which endpoint's recorded heat law resolves the duty ('to' = the jacket wall).
    """
    tf = jacketed_data()['tf'] if tf is None else tf
    model = {'formato': 'rage.modelo', 'version': 0, 'id': 'jacketed-flowsheet', 'nombre': 'Reactor and cooling jacket as two instances (test)',
             'componentes': [], 'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [], 'intercambios': [],
             'datos': {}, 'matematico': None, 'estudio': None, 'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _study_datum(model, 'flowsheet.tf', tf, 's'),
                        'metodoSolicitado': method, 'muestras': samples, 'rtol': 1e-9,
                        'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    connection = {'id': 'wall', 'from': {'instance': 'R', 'port': 'jacket'}, 'to': {'instance': 'J', 'port': 'wall'},
                  'heat': {'law': law, 'exteriorTemperature': 'service.Tprocess'}}
    model['flowsheet'] = {
        'format': 'rage.flowsheet', 'version': 1, 'id': 'jacketed',
        'templates': {'reactor': copy.deepcopy(reactor), 'jacket': copy.deepcopy(jacket)},
        'instances': [{'id': 'R', 'template': 'reactor', 'data': {}}, {'id': 'J', 'template': 'jacket', 'data': {}}],
        'connections': [connection],
        'exposures': [{'id': 'feed', 'instance': 'R', 'port': 'feed'}, {'id': 'product', 'instance': 'R', 'port': 'product'},
                      {'id': 'supply', 'instance': 'J', 'port': 'supply'}, {'id': 'return', 'instance': 'J', 'port': 'return'}],
        'recycles': []}
    return model


if __name__ == '__main__':
    import time
    started = time.time()
    documents = authored()
    print('authored in %.0f s' % (time.time() - started), [d['id'] for d in documents])
