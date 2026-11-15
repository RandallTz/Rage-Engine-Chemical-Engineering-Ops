"""Frozen revision-2 inputs and explicit comparison policy; never rewrite archives."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from core import unifac

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = '0931e2c77e83011aead32888d78239fc08e66dabc8dad9cb9fa20a6ea1c9657d'
RELATIVE_SERIES = 1e-6
EVENT_SECONDS = 1e-6


# Shard of each of the 25 archives (by index in `archives()`) when CI splits them in three. Solve seconds per
# archive were measured locally on 14 Nov 2026 (native + adapter): unifac-red-5 (17) 2708, heteroazeotropo (1) 1510,
# nrtl-4 heating (9) 350, then twenty-two archives of at most 204 s (1479 s together). Longest-processing-time
# assignment gives shard loads of 2708, 1510 and 1479 s (largest 47 % of the total), against 746, 1808 and 3144 s
# for archive index modulo 3, whose three CI shards took 7, 34 and 91 minutes (the same ratio, 1.37). Archive 17
# alone bounds any split at 47 %, so more shards would not help. Re-measure (cache records in
# .tmp/codex-v2-parity hold nativeSeconds and adapterSeconds) when archives change.
SHARD_TABLE_OF_3 = [2, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 2, 2, 2, 2, 2, 2, 2]


def shard_selected(index, shard, count):
    """Whether archive number `index` belongs to shard `shard` of `count` (CI splits the 25 archives this way;
    tools/ci/check_tiers.py proves the shards of tools/ci/test_tiers.json cover each archive exactly once)."""
    if count == 3 and len(SHARD_TABLE_OF_3) == 25:
        return SHARD_TABLE_OF_3[index] == shard
    return index % count == shard


def shard_from_env(shard_var, count_var):
    shard, count = int(os.environ.get(shard_var, '0')), int(os.environ.get(count_var, '1'))
    assert count >= 1 and 0 <= shard < count, (shard_var, shard, count)
    return shard, count


def archives():
    rows, manifest = [], []
    for path in sorted((ROOT/'docs/ejemplos').rglob('*-peticion.json')):
        request = json.loads(path.read_text(encoding='utf-8-sig'))
        if request.get('revision') != 2 or 'volumenes' not in request or 'paquetes' not in request:
            continue
        sibling = path.with_name(path.name.replace('-peticion', '-respuesta'))
        for source in (path, sibling):
            if source.exists():
                manifest.append([source.relative_to(ROOT).as_posix(), hashlib.sha256(source.read_bytes()).hexdigest()])
        rows.append((path, request, json.loads(sibling.read_text(encoding='utf-8')) if sibling.exists() else None))
    digest = hashlib.sha256(json.dumps(sorted(manifest), ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
    assert len(rows) == 25 and len(manifest) == 49 and digest == MANIFEST, digest
    return rows


@contextlib.contextmanager
def archive_context(path):
    original = unifac.asignacion
    def missing_assignment(cas, variant='original'):
        if cas == '141-78-6':
            raise unifac.FaltaDatoUNIFAC('Simulated missing acetate assignment, as in the archive generator.',
                                       {'tipo': 'asignacion_ausente', 'cas': cas, 'variante': variant})
        return original(cas, variant)
    context = patch.object(unifac, 'asignacion', missing_assignment) if 'simulado' in path.name else contextlib.nullcontext()
    with context:
        yield


def execution_digest():
    files = sorted([*ROOT.glob('core/**/*.py'), *ROOT.glob('backend/**/*.py')])
    return hashlib.sha256(b''.join(p.relative_to(ROOT).as_posix().encode()+p.read_bytes() for p in files)).hexdigest()


def event_tolerance(path, final_time):
    # Existing independent UNIFAC network reference, not an adaptive relaxation.
    return 1e-6*final_time if 'unifac-red-5' in path.name else EVENT_SECONDS


def zero_tolerance(series, request):
    # Predeclared absolute floors for identically-zero reference quantities.
    return {'mol': request['estudio']['atol']['cantidad'], 'J': request['estudio']['atol']['energia'],
            'J/K': 1e-9, 'kg': 1e-12, 'W': 1e-12, 'mol/s': 1e-12,
            'K': 1e-9, 'Pa': 1e-6, 'm3': 1e-12, 'm^3': 1e-12}.get(series['unidadSI'], 1e-12)


# Independent physical references accepted in the 27 October step-(e) review.
# These apply only to the immutable requests checked by MANIFEST, not to an
# arbitrary small series. In particular, numerical near-zero is not a proof.
ZERO_REFERENCES = {
    ('motor-ensamblaje-v2-resolver-decantador-agua-butanol-peticion.json', 'red.Sgen'):
        'Reversible adiabatic withdrawal of an equilibrium liquid at its own T/P: Sgen = 0.',
    ('motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json', 'volumen.A.W'):
        'Constant pressure and temperature-independent liquid volume: W = -P(V-V0) = 0.',
}
EVENT_REFERENCES = {
    'demostracion-heteroazeotropo-agua-butanol-peticion.json':
        (70.48187264652807, 479.75847727360076, 498.94412891556277),
}


def series_limit(path, series, request, reference):
    """Return the predeclared limit and its physical basis, in SI units."""
    scale = max(map(abs, series['valores']))
    limit = RELATIVE_SERIES*scale if scale else zero_tolerance(series, request)
    basis = 'Relative series limit' if scale else 'Exactly zero reference: absolute floor'
    zero = ZERO_REFERENCES.get((path.name, series['variableId']))
    if zero:
        return max(limit, zero_tolerance(series, request)), zero
    from core.unidades import a_SI
    for heat in request['intercambiosTermicos']:
        if heat['ley']['tipo'] != 'conductancia' or series['variableId'] != 'calor.'+heat['id']+'.Q':
            continue
        datum = request['datos'][heat['ley']['conductanciaId']]['declaracion']
        conductance = a_SI(float(datum['texto']), datum['unidad'])
        temperatures = {s['variableId']: s['valores'] for s in reference['series']}
        operands = [max(map(abs, temperatures['volumen.'+heat[side]+'.T'])) for side in ('desde', 'hasta')]
        return abs(conductance)*RELATIVE_SERIES*sum(operands), 'Q = G(T_a-T_b): propagated operand limits'
    return limit, basis
