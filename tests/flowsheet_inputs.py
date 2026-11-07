"""Heterogeneous Demo 0.2 flowsheet inputs: reactor -> heated liquid drum -> reactor.

Fresh test sources, never product-library examples. The continuous reactor is
the frozen recorded Demo 0.2 template. The drum is authored here through the
same shared fundamental-law author as the Demo 0.2 drum
(tests/derived_momentum_inputs.author_outlet), with the reactor's four species
and the same recorded liquid formation reference, so that the transported
specific enthalpy has one energy reference on both sides of every connection.
Acetic acid is admitted by the package only in a liquid phase (no vapour
association model), so this drum records the liquid-only assumption and has
no vapour withdrawal: it is a heated liquid holdup with a level-driven outlet.
No terminal formula, RHS or closure value is written here.
"""
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from m1_acceptance import thermal_source  # noqa: E402
from core.balances import material_derivation as material, energy_derivation as energy  # noqa: E402
from core.termodinamica import derivation as thermodynamics  # noqa: E402
from core.modelo import leer_modelo_comun  # noqa: E402
from core.modelo.operation_journal import replay  # noqa: E402
from derived_closure_inputs import OWNER, PACKAGE_ID, _datum  # noqa: E402
from derived_reactor_inputs import LIQUID_POLICY, SPECIES  # noqa: E402
from derived_momentum_inputs import PIPE, author_outlet, select_outlet  # noqa: E402

NAMES = ('ethanol', 'acetic acid', 'ethyl acetate', 'water')
# Small heated drum sized for the reactor product (1e-3 kg/s), with the
# reactor's own outlet hydraulics (the same local-loss-dominated path and its
# recorded friction premise, review CR-1). Initial holdup: a liquid close to the
# reactor product.
from demo02_cstr import DEMO as _REACTOR_DATA  # noqa: E402
DRUM4 = {'P': 101325.0, 'm0': (0.12, 0.15, 0.12, 0.025), 'T0': 335.0, 'feed': 1e-3,
         'zF': (0.33, 0.33, 0.17, 0.17), 'TF': 335.0, 'PF': 101325.0, 'Q': 25.0, 'vent': 0.0,
         'area': 0.003, 'length': _REACTOR_DATA['length'], 'pipeArea': _REACTOR_DATA['pipeArea'],
         'loss': _REACTOR_DATA['loss'], 'friction': _REACTOR_DATA['friction'], 'floor': 0.0,
         'Pout': 101325.0, 'F0': 1e-3, 'g': 9.80665, 'tf': 20000.0}


def drum4_source(data=DRUM4):
    """Heated liquid drum: prescribed-pressure package volume, four species, liquid formation reference.

    Liquid-only, because the package admits acetic acid only in a liquid phase,
    so it is not a flash. It records no_reaction: the esterification kinetics
    belong to the reactor's catalyst, which the drum does not contain.
    """
    model = thermal_source((OWNER,))
    model.update(id='flowsheet-package-drum', nombre='Heated liquid drum, four species (test)')
    model['componentes'] = [{'id': i, 'nombre': name, 'simbolo': 'C%d' % i, 'identidadQuimica': {'cas': cas}}
                            for i, (name, cas) in enumerate(zip(NAMES, SPECIES), 1)]
    volume = model['volumenes'][0]
    volume['componenteIds'] = [1, 2, 3, 4]
    base = model['datos'][OWNER + '.mass']
    ids = {}
    for i, value in enumerate(data['m0'], 1):
        key = OWNER + ('.mass' if i == 1 else '.mass' + str(i))
        model['datos'][key] = copy.deepcopy(base)
        model['datos'][key]['declaracion']['texto'] = repr(float(value))
        ids[str(i)] = key
    volume['inicial']['cantidades']['datoIds'] = ids
    model['datos'][OWNER + '.temperature']['declaracion']['texto'] = repr(data['T0'])
    model['termodinamica'] = {'paquetes': [{'id': 'pkg', 'modelo': {'id': PACKAGE_ID, 'version': '1'}}]}
    volume['termodinamica'] = {'tipo': 'equilibrio', 'paqueteId': 'pkg', 'politica': copy.deepcopy(LIQUID_POLICY)}
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'no_reaction', 'integrate', 'total', 'impermeable_remainder'):
        journal = material.edit_journal(journal, OWNER, {'kind': action})
    model['motores']['materialDerivation'] = journal
    volume['supuestos']['materia'] = material.replay_volume(journal['volumes'][OWNER])[-1]
    ej = {'format': 'rage.energy-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source',
                   'integrate', 'reynolds', 'total', 'enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure'):
        ej = energy.edit_journal(ej, OWNER, {'kind': action})
    model['motores']['energyDerivation'] = ej
    tj = {'format': thermodynamics.FORMAT, 'version': 1, 'volumes': {}}
    tj = thermodynamics.edit_journal(tj, OWNER, {'kind': 'start'})
    tj = thermodynamics.edit_journal(tj, OWNER, {'kind': 'select_closure'}, thermodynamics.expected_closure(model, volume))
    for kind in ('liquid_only', 'liquid_formation_reference'):
        tj = thermodynamics.edit_journal(tj, OWNER, {'kind': kind})
    model['motores']['thermodynamicDerivation'] = tj
    es = replay(ej['volumes'][OWNER], energy.fundamental, energy.normalize)[-1]
    ts = replay(tj['volumes'][OWNER], thermodynamics.fundamental, thermodynamics.normalize)[-1]
    volume['supuestos']['energia'] = {**es, **{k: v for k, v in ts.items() if k != 'closure'}}
    _datum(model, OWNER + '.pressure', data['P'], 'Pa', 'frontera')
    volume['frontera'] = {'tipo': 'presion_prescrita', 'presionId': OWNER + '.pressure'}
    _datum(model, 'feed.T', data['TF'], 'K', 'frontera')
    _datum(model, 'feed.P', data['PF'], 'Pa', 'frontera')
    model['corrientes'] = []
    for name in ('feed', 'liquid'):
        stream = {'id': name, 'desde': None if name == 'feed' else OWNER, 'hasta': OWNER if name == 'feed' else None,
                  'componenteIds': [1, 2, 3, 4], 'mecanismo': 'convectivo', 'constante': False,
                  'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}}}
        if name == 'feed':
            stream['estadoExterior'] = {'temperaturaId': 'feed.T', 'presion': {'tipo': 'dato', 'datoId': 'feed.P'},
                                        'composicion': {'base': 'molar', 'fracciones': {str(i): z for i, z in enumerate(data['zF'], 1)}}}
        model['corrientes'].append(stream)
    return leer_modelo_comun(model)


def _prepare(model, data):
    for stream in model['corrientes']:
        if stream['id'] == 'liquid':
            stream['extraccion'] = {OWNER: {'tipo': 'fase', 'fase': 'liquido'}}
    _datum(model, 'solve.Q', data['Q'], 'W')
    model['volumenes'][0]['terminos'] = {'calor': 'solve.Q'}
    path = next(v for v in model['volumenes'] if v['id'] == PIPE)
    path['termodinamica']['motivo'] = 'The path transports the drawn liquid phase without separate storage or a separate thermodynamic closure.'
    next(s for s in model['corrientes'] if s['id'] == 'discharge')['extraccion'] = {PIPE: {'tipo': 'fase', 'fase': 'liquido'}}


def drum4_template():
    from demo02_drum import MATERIAL
    return {'format': 'rage.model-template', 'version': 1, 'id': 'flowsheet-drum4', 'templateVersion': '1', 'equipment': True,
            'recipe': {'journals': ['materialDerivation', 'energyDerivation', 'momentumDerivation', 'thermodynamicDerivation', 'equationWorkbench']},
            'ports': [
                {'id': 'feed', 'volumeId': OWNER, 'direction': 'inlet', 'kind': 'material', 'boundary': {'type': 'stream', 'id': 'feed'},
                 'exteriorState': 'estadoExterior', 'variables': copy.deepcopy(MATERIAL)},
                {'id': 'liquid', 'volumeId': PIPE, 'direction': 'outlet', 'kind': 'material', 'boundary': {'type': 'stream', 'id': 'discharge'},
                 'donorPhase': 'liquido', 'variables': copy.deepcopy(MATERIAL)},
                {'id': 'heat', 'volumeId': OWNER, 'direction': 'inlet', 'kind': 'heat', 'boundary': {'type': 'term', 'id': 'calor'},
                 'variables': {'power': {'unitSI': 'W'}}}]}


def author_drum4(data=DRUM4, method='bdf'):
    author, out = author_outlet(data, prepare=lambda model: _prepare(model, data), source_factory=drum4_source, vapour=False)
    author.model['template'] = drum4_template()
    model = select_outlet(author, out, data, method)
    model['motores']['derivedExecution']['checks'][0]['scaleDataId'] = _datum(model, 'scale.mass', 1, 'kg')
    from core.modelo.equation_workbench import build
    from core.compilador.derived import source_signature
    model.update(id='flowsheet-drum4', nombre='Heated liquid drum, four species, with outlet momentum (equipment)')
    model['motores']['derivedExecution']['sourceSignature'] = source_signature(model, build(model))
    return model, out


_AUTHORED = {}
CACHE = ROOT / '.tmp' / 'flowsheet'


def drum4_model():
    """Authored through the shared operations; cached by the authoring sources.

    The cache only saves authoring time. Every use replays and re-verifies the
    signed history through the template-instance service.
    """
    if 'drum' not in _AUTHORED:
        import hashlib
        sources = [ROOT / 'tests' / name for name in ('flowsheet_inputs.py', 'derived_momentum_inputs.py',
                   'derived_closure_inputs.py', 'derived_reactor_inputs.py', 'm1_acceptance.py', 'demo02_drum.py', 'demo02_cstr.py')]
        key = hashlib.sha256(b''.join(p.read_bytes() for p in sources)).hexdigest()[:16]
        path = CACHE / f'drum4-{key}.json'
        if path.exists():
            _AUTHORED['drum'] = json.loads(path.read_text(encoding='utf-8'))
        else:
            _AUTHORED['drum'] = author_drum4()[0]
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_AUTHORED['drum']), encoding='utf-8')
    return copy.deepcopy(_AUTHORED['drum'])


# R2 runs with a warmer jacket than R1; the drum heats the intermediate liquid.
R2_DATA = {'jacket.T': ('345.0', 'K'), 'jacket.UA': ('8.0', 'W/K')}
STUDY = {'tf': 20000.0, 'muestras': 41, 'method': 'bdf'}


def _study_datum(model, key, value, unit):
    model['datos'][key] = {'magnitud': key, 'funcion': 'estudio', 'declaracion': {'texto': repr(float(value)), 'unidad': unit},
                           'origen': {'propietarioId': 'estudio', 'ruta': key}}
    return key


def flowsheet_model(reactor, drum, study=STUDY, layout=True):
    """Shell model: R1.product -> D.feed, D.liquid -> R2.feed; boundaries exposed explicitly."""
    model = {'formato': 'rage.modelo', 'version': 0, 'id': 'demo-0.2-flowsheet', 'nombre': 'Demo 0.2 · Reactor, heated drum, reactor',
             'componentes': [], 'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [], 'intercambios': [],
             'datos': {}, 'matematico': None, 'estudio': None, 'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _study_datum(model, 'flowsheet.tf', study['tf'], 's'),
                        'metodoSolicitado': study['method'], 'muestras': study['muestras'], 'rtol': 1e-9,
                        'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    model['flowsheet'] = {
        'format': 'rage.flowsheet', 'version': 1, 'id': 'plant',
        'templates': {'reactor': copy.deepcopy(reactor), 'drum': copy.deepcopy(drum)},
        'instances': [{'id': 'R1', 'template': 'reactor', 'data': {}},
                      {'id': 'D1', 'template': 'drum', 'data': {}},
                      {'id': 'R2', 'template': 'reactor', 'data': {k: {'texto': v, 'unidad': u} for k, (v, u) in R2_DATA.items()}}],
        'connections': [{'id': 's1', 'from': {'instance': 'R1', 'port': 'product'}, 'to': {'instance': 'D1', 'port': 'feed'}},
                        {'id': 's2', 'from': {'instance': 'D1', 'port': 'liquid'}, 'to': {'instance': 'R2', 'port': 'feed'}}],
        'exposures': [{'id': 'feed', 'instance': 'R1', 'port': 'feed'}, {'id': 'jacket1', 'instance': 'R1', 'port': 'jacket'},
                      {'id': 'heater', 'instance': 'D1', 'port': 'heat'}, {'id': 'jacket2', 'instance': 'R2', 'port': 'jacket'},
                      {'id': 'product', 'instance': 'R2', 'port': 'product'}],
        'recycles': []}
    if layout:
        model['flowsheetLayout'] = {'format': 'rage.flowsheet-layout', 'version': 1, 'flowsheetId': 'plant',
            'blocks': {'R1': {'position': [0, 0]}, 'D1': {'position': [200, 0]}, 'R2': {'position': [400, 0]}},
            'streams': {'s1': {'points': [[60, 0], [140, 0]]}}}
    return model


def _value(model, key):
    return float(model['datos'][key]['declaracion']['texto'])


def chain_data(reactor, drum):
    """Plain numbers read from the documents' declared data: the shared input of the reference."""
    def vessel(source, overrides=None, reactive=True):
        value = lambda key: float((overrides or {}).get(key, (None,))[0] or _value(source, key))
        row = {k: value(k) for k in ('solve.A', 'solve.pipeArea', 'solve.length', 'solve.K', 'solve.Pout', 'solve.g', 'solve.F0', 'solve.F')}
        row['P'] = value('cell.pressure' if reactive else OWNER + '.pressure')
        row['T0'] = value('cell.temperature' if reactive else OWNER + '.temperature')
        if reactive:
            row.update(UA=value('jacket.UA'), Tj=value('jacket.T'), m0=[value(k) for k in ('cell.mass', 'cell.mass2', 'cell.mass3', 'cell.mass4')],
                       kf=value('forwardRate'), kr=value('reverseRate'), E=value('activation'), Er=value('reverseActivation'), Tref=value('rateTemperature'),
                       TF=value('feed.T'), PF=value('feed.P'))
        else:
            row.update(Q=value('solve.Q'), m0=[value(OWNER + k) for k in ('.mass', '.mass2', '.mass3', '.mass4')])
        return row
    composition = reactor['corrientes'][[s['id'] for s in reactor['corrientes']].index('feed')]['estadoExterior']['composicion']['fracciones']
    r1 = vessel(reactor)
    r1['zF'] = [composition[str(i)] for i in (1, 2, 3, 4)]
    return [r1, vessel(drum, reactive=False), vessel(reactor, R2_DATA)]
