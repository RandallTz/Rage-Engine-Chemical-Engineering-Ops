"""Versioned numerical selection of a replayed graph; never stores an RHS."""
from core.mathematics.contract import keys

FORMAT = 'rage.derived-execution'


def read_definition(value, model=None):
    keys(value, ['format', 'version', 'sourceSignature', 'timeId', 'states',
                 'parameters', 'initialValues', 'initialEquations', 'reconstructions', 'checks'], ['scaling'])
    import re
    if value['format'] != FORMAT or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported derived execution version.')
    if not isinstance(value['sourceSignature'], str) or not re.fullmatch('[0-9a-f]{64}', value['sourceSignature']):
        raise ValueError('A pinned Transform source signature is required.')

    def identity(text):
        if not isinstance(text, str) or not text.strip() or len(text) > 160:
            raise ValueError('A derived execution identity must be a nonempty string.')

    identity(value['timeId'])
    for name in ('parameters', 'initialValues', 'scaling'):
        if name not in value:
            continue
        mapping = value[name]
        if not isinstance(mapping, dict) or len(mapping) > 200 or name == 'scaling' and not mapping:
            raise ValueError('Invalid derived execution data bindings: ' + name)
        for quantity, datum in mapping.items():
            identity(quantity); identity(datum)
            if model is not None and datum not in model['datos']:
                raise ValueError('Unknown derived execution datum: ' + datum)
    for name, fields in [('states', ['quantityId', 'equationId']),
                         ('reconstructions', ['quantityId', 'equationId']),
                         ('checks', ['equationId', 'scaleDataId'])]:
        rows = value[name]
        if not isinstance(rows, list) or len(rows) > 200 or name == 'states' and not rows:
            raise ValueError('Invalid derived execution selection: ' + name)
        seen = set()
        for row in rows:
            keys(row, fields)
            for field in fields:
                identity(row[field])
            if row[fields[0]] in seen:
                raise ValueError('Duplicate derived execution selection: ' + row[fields[0]])
            seen.add(row[fields[0]])
            if name == 'checks' and model is not None and row['scaleDataId'] not in model['datos']:
                raise ValueError('Unknown conservation scale datum: ' + row['scaleDataId'])
    initial = value['initialEquations']
    if not isinstance(initial, list) or len(initial) > 200:
        raise ValueError('Select distinct initialization equations.')
    for equation in initial:
        identity(equation)
    if len(set(initial)) != len(initial):
        raise ValueError('Select distinct initialization equations.')
    states = {row['quantityId'] for row in value['states']}
    rebuilt = {row['quantityId'] for row in value['reconstructions']}
    if states & rebuilt or (states | rebuilt) & set(value['parameters']) or value['timeId'] in states | rebuilt | set(value['parameters']):
        raise ValueError('State, reconstruction, parameter and time ownership must be distinct.')
    if 'scaling' in value and set(value['scaling']) != states | {value['timeId']}:
        raise ValueError('Scaling requires exactly the time and retained states.')
    return value
