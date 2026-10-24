"""The retired revision-1 assembly cases, re-expressed as revision-2 requests (dec-r5-legacy-v1, 23 October 2026).

Revision 1 described one water volume closed by agua-iapws95 and was solved by the legacy core/ensamblaje_dinamico.py.
Each frozen revision-1 request in docs/ejemplos/motor-ensamblaje-*-peticion.json is translated field by field into
the equivalent revision-2 request: the same species, formulations, policy, boundary, initial data, streams, heat and
study; nothing is recomputed or simplified. The revision-2 request is then solved by the common compiler
(core.modelo.desde_ensamblaje_v2 -> core.compilador.resolver). The frozen revision-1 responses remain the reference.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'docs' / 'ejemplos'
RESOLVE_CASES = ('abierta-presion-constante', 'cambio-fase-prohibido', 'condensacion-rigida',
                 'ebullicion-presion-constante', 'extraccion-liquido', 'llenado-rigido',
                 'presion-suave-adiabatica', 'rigida-calentamiento', 'vaciado-con-ebullicion')


def frozen(case, kind='resolver'):
    """(revision-1 request, frozen revision-1 response)."""
    base = EXAMPLES / f'motor-ensamblaje-{kind}-{case}'
    return (json.loads(Path(f'{base}-peticion.json').read_text(encoding='utf-8')),
            json.loads(Path(f'{base}-respuesta.json').read_text(encoding='utf-8')))


def to_v2(request):
    """The revision-2 request equivalent to a revision-1 request."""
    r1 = copy.deepcopy(request)
    v = r1['volumen']
    vid = v['id']
    extractions = (v['cierre'].get('extracciones') or {})
    streams = []
    for c in r1.get('corrientes', []):
        c = copy.deepcopy(c)
        c['mecanismo'] = c.get('mecanismo') or 'convectivo'
        # revision 1 gives one extraction rule per stream (on the stream or in the closure); revision 2 keys it by
        # the donor volume
        rule = c.pop('extraccion', None) or extractions.get(str(c['id']))
        if rule is not None:
            c['extraccion'] = {vid: rule}
        streams.append(c)
    heat = []
    q = (r1.get('transferencias') or {}).get('calor')
    if q:
        heat.append({'id': 'q', 'desde': None, 'hasta': vid, 'ley': {'tipo': 'impuesto', 'potenciaId': q}})
    study = copy.deepcopy(r1['estudio'])
    study['atol'] = {'cantidad': study['atol'].get('masa', 1e-11), 'energia': study['atol'].get('energia', 1e-6)}
    volume = {'id': vid, 'componenteIds': v['componenteIds'], 'balances': v['balances'],
              'formulacionMateria': v['formulacionMateria'], 'formulacionEnergia': v['formulacionEnergia'],
              'paqueteId': 'p', 'politica': v['cierre']['politica'], 'frontera': v['frontera'],
              'inicial': {'cantidades': {'base': 'masica', 'datoIds': v['inicial']['masaIds']},
                          'energia': v['inicial']['energia']}}
    return {'revision': 2, 'solicitudId': r1['solicitudId'] + '-v2', 'componentes': r1['componentes'],
            'paquetes': [{'id': 'p', 'modelo': v['cierre']['modelo']}], 'volumenes': [volume],
            'corrientes': streams, 'intercambiosTermicos': heat, 'datos': r1['datos'], 'estudio': study}


def solve_common(request_v2):
    """Solve a revision-2 request with the common compiler."""
    from core.compilador import resolver
    from core.modelo import desde_ensamblaje_v2
    return resolver(desde_ensamblaje_v2(request_v2))
