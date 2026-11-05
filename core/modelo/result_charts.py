"""Presentation-only conversion of selected values through the shared units service."""
import math
from core import unidades
from core.unidades.servicio import dimension_json


def chart_data(request):
    if not isinstance(request, dict) or set(request) != {'format', 'version', 'resultId', 'requests'} or request['format'] != 'rage.chart-data.request' or type(request['version']) is not int or request['version'] != 1:
        raise ValueError('Expected rage.chart-data.request version 1.')
    if not isinstance(request['resultId'], str) or not request['resultId']:
        raise ValueError('A result identity is required.')
    if not isinstance(request['requests'], list) or len(request['requests']) > 500:
        raise ValueError('Expected at most 500 chart data selections.')
    rows = []; seen = set()
    for item in request['requests']:
        if not isinstance(item, dict) or set(item) != {'kind', 'id', 'unit', 'sourceUnit', 'values', 'events'} or item['kind'] not in ('axis', 'series'):
            raise ValueError('Expected a typed selection, source/display units, values and events.')
        if any(not isinstance(item[k], str) or not item[k] for k in ('id', 'unit', 'sourceUnit')):
            raise ValueError('Chart identities and units must be nonempty text.')
        key = (item['kind'], item['id'], item['unit'])
        if key in seen: raise ValueError('Duplicate chart data selection.')
        seen.add(key)
        interpreted = unidades.interpretar(item['unit'])
        source = unidades.interpretar(item['sourceUnit'])
        if interpreted['dimension'] != source['dimension']:
            raise ValueError('Incompatible chart axis unit: ' + item['unit'])
        def convert(value):
            if value is None: return None
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError('Chart values must be finite scalars or null, never meshes.')
            return unidades.desde_SI(unidades.a_SI(value, item['sourceUnit']), item['unit'])
        values = [convert(v) for v in item['values']] if isinstance(item['values'], list) else convert(item['values'])
        if not isinstance(item['events'], list) or item['kind'] == 'series' and item['events']:
            raise ValueError('Only axis selections carry events.')
        events = []
        for event in item['events']:
            if not isinstance(event, dict) or not {'codigo','ejeId','valor','descripcion'} <= event.keys() or event.keys() - {'codigo','ejeId','valor','descripcion','propietarioId'} or event['ejeId'] != item['id']:
                raise ValueError('Invalid axis event.')
            if any(not isinstance(event[k], str) for k in event if k != 'valor') or event['valor'] is None:
                raise ValueError('Invalid event metadata.')
            events.append({**event, 'valor': convert(event['valor'])})
        rows.append({'kind':item['kind'],'id':item['id'],'unit':item['unit'],'dimension':dimension_json(interpreted['dimension']),'values':values,'events':events})
    return {'format':'rage.chart-data','version':1,'resultId':request['resultId'],'rows':rows}
