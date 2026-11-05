"""Headless timings on shared-authored, currently admitted thermal volumes."""
import json
from pathlib import Path
import sys
import time
import statistics
import platform
import scipy
from scipy.linalg import expm

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sparse_chain_inputs import thermal_chain
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.steady import SteadySystem
from core.modelo.steady_transform import prepare_steady_transform
from core.resultados import leer_resultados


def compare(a, b, tolerance):
    assert a['estado'] == b['estado'] == 'resuelto'
    assert [s['id'] for s in a['series']] == [s['id'] for s in b['series']]
    maximum = 0.
    for left, right in zip(a['series'], b['series']):
        x, y = np.asarray(left['valores']), np.asarray(right['valores'])
        error = float(np.max(np.abs(x-y)/np.maximum(1.,np.abs(x))))
        maximum = max(maximum,error)
        assert error <= tolerance, (left['id'],error,tolerance)
    for result in (a,b):
        leer_resultados(result)
        assert all(v['valor'] <= v['tolerancia'] for v in result['verificaciones'])
    return maximum


def benchmark(count):
    directory = Path('.tmp/sparse-chains'); directory.mkdir(exist_ok=True,parents=True)
    path = directory / ('model-'+str(count)+'.json')
    # Cache only the shared-author publication, never a manufactured RHS.
    if path.exists(): model = json.loads(path.read_text(encoding='utf8'))
    else:
        model = thermal_chain(count)
        path.write_text(json.dumps(model),encoding='utf8')
    print('Compiling dynamic chain n='+str(count),file=sys.stderr,flush=True)
    system = DerivedSystem(model)
    row = {'volumes':count, 'dynamicStates':len(system.states)}
    row.update(trials=3, python=platform.python_version(), scipy=scipy.__version__,
               timingScope='Solve and publication; excludes authoring, compilation and Transform preparation')
    samples = {mode:[] for mode in ('dense','sparse')}
    errors = []
    for _ in range(3):
        publications = []
        for mode in ('dense','sparse'):
            system.configure_jacobian(mode)
            system.report = system._report()
            start = time.perf_counter(); result = resolve_system(system)
            samples[mode].append(time.perf_counter()-start)
            publications.append(result)
        errors.append(compare(*publications, 1e-7))
    row.update({ 'dynamic_'+mode:statistics.median(samples[mode]) for mode in samples })
    row['dynamicAgreement'] = max(errors)
    # Independent constant-capacity first-law chain: dU/dt=(G/c) L U.
    # Bath and energy reference are both 300 K, with m=1 kg and c=300 J/(kg K).
    laplacian = np.diag(np.full(count,-2.)) + np.diag(np.ones(count-1),1) + np.diag(np.ones(count-1),-1)
    initial_energy = 300*(30+np.arange(count)/count)
    times = publications[0]['ejes'][0]['valores']
    expected = np.array([expm((10/300)*laplacian*t) @ initial_energy for t in times])
    for result in publications:
        energy = [s for s in result['series'] if s['id'].startswith('campo.') and s['unidadSI']=='J']
        actual = np.array([s['valores'] for s in energy]).T
        np.testing.assert_allclose(actual,expected,rtol=1e-6,atol=1e-5)
    print('Preparing steady Transform n='+str(count),file=sys.stderr,flush=True)
    steady = SteadySystem(prepare_steady_transform(model)['model'])
    row['steadyUnknowns'] = len(steady.unknowns)
    samples = {mode:[] for mode in ('dense','sparse')}
    errors = []
    for _ in range(3):
        publications = []
        for mode in ('dense','sparse'):
            start = time.perf_counter(); result = steady.solve(linear_solver=mode)
            samples[mode].append(time.perf_counter()-start)
            publications.append(result)
        errors.append(compare(*publications, 1e-9))
    row.update({ 'steady_'+mode:statistics.median(samples[mode]) for mode in samples })
    row['steadyAgreement'] = max(errors)
    for result in publications:
        for series in result['series']:
            if series['id'].startswith('steady.') and not series['id'].startswith('steady.residual.') and series['unidadSI']=='K':
                assert abs(series['valores']-300) < 1e-7
    (directory/('timing-'+str(count)+'.json')).write_text(json.dumps(row,indent=2),encoding='utf8')
    print(json.dumps(row),flush=True)
    return row


if __name__ == '__main__':
    for count in map(int,sys.argv[1:] or [5,10,20,40]): benchmark(count)
