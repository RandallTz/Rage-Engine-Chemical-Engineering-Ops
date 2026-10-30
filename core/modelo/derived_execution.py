"""Versioned numerical selection of a replayed graph; never stores an RHS."""
from core.mathematics.contract import keys

FORMAT = 'rage.derived-execution'


def read_definition(value, model=None):
    if isinstance(value, dict) and value.get('version') == 5:
        return read_steady_definition(value, model)
    keys(value, ['format', 'version', 'sourceSignature', 'timeId', 'states',
                 'parameters', 'initialValues', 'initialEquations', 'reconstructions', 'checks'], ['scaling', 'algebraic', 'nonlinear', 'dae'])
    import re
    if value['format'] != FORMAT or type(value['version']) is not int or value['version'] not in (1, 2, 3, 4):
        raise ValueError('Unsupported derived execution version.')
    if (value['version'] == 1 and 'algebraic' in value or
            value['version'] in (2, 3, 4) and not value.get('algebraic')):
        raise ValueError('Versions 2, 3 and 4 require a nonempty coupled algebraic block.')
    if (value['version'] in (3, 4)) != ('nonlinear' in value):
        raise ValueError('Versions 3 and 4 require nonlinear settings.')
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
    for name, fields in [('algebraic', ['quantityId', 'equationId']),
                         ('states', ['quantityId', 'equationId']),
                         ('reconstructions', ['quantityId', 'equationId']),
                         ('checks', ['equationId', 'scaleDataId'])]:
        rows = value.get(name, [])
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
        if name == 'algebraic' and len({row['equationId'] for row in rows}) != len(rows):
            raise ValueError('Algebraic block equations must be distinct.')
    initial = value['initialEquations']
    if not isinstance(initial, list) or len(initial) > 200:
        raise ValueError('Select distinct initialization equations.')
    for equation in initial:
        identity(equation)
    if len(set(initial)) != len(initial):
        raise ValueError('Select distinct initialization equations.')
    states = {row['quantityId'] for row in value['states']}
    rebuilt = {row['quantityId'] for row in value['reconstructions']}
    algebraic = {row['quantityId'] for row in value.get('algebraic', [])}
    if algebraic & (states | rebuilt | set(value['parameters']) | {value['timeId']}):
        raise ValueError('Algebraic unknowns must have distinct ownership.')
    if states & rebuilt or (states | rebuilt) & set(value['parameters']) or value['timeId'] in states | rebuilt | set(value['parameters']):
        raise ValueError('State, reconstruction, parameter and time ownership must be distinct.')
    if 'scaling' in value and set(value['scaling']) != states | {value['timeId']}:
        raise ValueError('Scaling requires exactly the time and retained states.')
    if value['version'] in (3, 4):
        import math
        config = value['nonlinear']
        keys(config, ['variables', 'residualScales', 'residualTolerance', 'stepTolerance', 'maxIterations', 'maxBacktracks'])
        if set(config['variables']) != algebraic or set(config['residualScales']) != {r['equationId'] for r in value['algebraic']}:
            raise ValueError('Nonlinear settings must cover exactly the selected unknowns and rows.')
        for item in config['variables'].values():
            keys(item, ['seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId'])
            for data in item.values():
                identity(data)
                if model is not None and data not in model['datos']:
                    raise ValueError('Unknown nonlinear datum: '+data)
        for data in config['residualScales'].values():
            identity(data)
            if model is not None and data not in model['datos']:
                raise ValueError('Unknown nonlinear residual scale: '+data)
        for name in ('residualTolerance', 'stepTolerance'):
            if type(config[name]) not in (int, float) or not math.isfinite(config[name]) or config[name] <= 0:
                raise ValueError('Nonlinear tolerances must be finite and positive.')
        for name, limit in [('maxIterations', 30), ('maxBacktracks', 20)]:
            if type(config[name]) is not int or not 1 <= config[name] <= limit:
                raise ValueError('Nonlinear iteration budgets exceed the admitted bounds.')
    if (value['version'] == 4) != ('dae' in value):
        raise ValueError('Only version 4 requires DAE settings.')
    if value['version'] == 4:
        config = value['dae']
        keys(config, ['stateBounds', 'driftTolerance'])
        if not isinstance(config['stateBounds'], dict) or set(config['stateBounds']) != states:
            raise ValueError('DAE state bounds must cover exactly the differential states.')
        for item in config['stateBounds'].values():
            keys(item, ['lowerDataId', 'upperDataId'])
            for data in item.values():
                identity(data)
                if model is not None and data not in model['datos']:
                    raise ValueError('Unknown DAE bound datum: '+data)
        tolerance = config['driftTolerance']
        if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 < tolerance <= 1e-9:
            raise ValueError('DAE drift tolerance must be positive and at most 1e-9.')
        if value['nonlinear']['residualTolerance'] > tolerance:
            raise ValueError('Newton residual tolerance cannot exceed the DAE drift tolerance.')
    return value


def read_steady_definition(value, model=None):
    """Steady seeds and individual invariants are separate from initial data."""
    import math
    import re
    keys(value, ['format', 'version', 'sourceSignature', 'timeId', 'states', 'algebraic',
                 'unknowns', 'parameters', 'invariants', 'reconstructions', 'checks', 'nonlinear'])
    if value['format'] != FORMAT or type(value['version']) is not int or value['version'] != 5:
        raise ValueError('Expected derived execution version 5.')
    if not isinstance(value['sourceSignature'], str) or not re.fullmatch('[a-f0-9]{64}', value['sourceSignature']):
        raise ValueError('A pinned Transform source signature is required.')
    def identity(text):
        if not isinstance(text, str) or not text.strip() or len(text) > 160:
            raise ValueError('A selection identity must be a nonempty string.')
    def datum(text):
        identity(text)
        if model is not None and text not in model['datos']:
            raise ValueError('Unknown steady datum: '+text)
    identity(value['timeId'])
    for field in ('parameters', 'invariants'):
        if not isinstance(value[field], dict) or len(value[field]) > 200:
            raise ValueError('Invalid steady data bindings.')
        for key, data in value[field].items():
            identity(key); datum(data)
    for field in ('states', 'algebraic', 'reconstructions', 'checks'):
        rows = value[field]
        if not isinstance(rows, list) or len(rows) > 200:
            raise ValueError('Invalid steady row selection.')
        fields = ['equationId', 'scaleDataId'] if field == 'checks' else ['quantityId', 'equationId']
        for row in rows:
            keys(row, fields)
            for item in row.values(): identity(item)
            if field == 'checks': datum(row['scaleDataId'])
        if len({row[fields[0]] for row in rows}) != len(rows):
            raise ValueError('Steady row selections must be distinct.')
    unknowns = value['unknowns']
    if not isinstance(unknowns, list) or not 1 <= len(unknowns) <= 200:
        raise ValueError('Select a nonempty steady unknown block.')
    for item in unknowns: identity(item)
    states = {row['quantityId'] for row in value['states']}
    algebraic = {row['quantityId'] for row in value['algebraic']}
    rebuilt = {row['quantityId'] for row in value['reconstructions']}
    parameters = set(value['parameters']); invariants = set(value['invariants'])
    groups = [states, algebraic, rebuilt, parameters, {value['timeId']}]
    if any(a & b for i, a in enumerate(groups) for b in groups[i+1:]) or not invariants <= states:
        raise ValueError('State, algebraic, reconstructed, parameter and time ownership must be distinct; invariants bind states only.')
    if len(set(unknowns)) != len(unknowns) or set(unknowns) != (states-invariants) | algebraic:
        raise ValueError('Free unknowns must cover exactly the unbound states and algebraic quantities.')
    equation_ids = [row['equationId'] for field in ('states', 'algebraic', 'reconstructions') for row in value[field]]
    if len(set(equation_ids)) != len(equation_ids):
        raise ValueError('Steady equation rows must be distinct.')
    config = value['nonlinear']
    keys(config, ['variables', 'residualScales', 'residualTolerance', 'stepTolerance', 'maxIterations', 'maxBacktracks'])
    if not isinstance(config['variables'], dict) or set(config['variables']) != set(unknowns):
        raise ValueError('Newton variable data must cover exactly the free steady unknowns.')
    if not isinstance(config['residualScales'], dict):
        raise ValueError('Steady residual scales must be a mapping.')
    expected_rows = {row['equationId'] for row in value['states'] if row['quantityId'] not in invariants} | {row['equationId'] for row in value['algebraic']}
    if set(config['residualScales']) != expected_rows:
        raise ValueError('Residual scales must cover exactly the unbound-state and algebraic rows.')
    for item in config['variables'].values():
        keys(item, ['seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId'])
        for data in item.values(): datum(data)
    for data in config['residualScales'].values(): datum(data)
    for key in ('residualTolerance', 'stepTolerance'):
        if type(config[key]) not in (int, float) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError('Newton tolerances must be positive and finite.')
    for key, limit in [('maxIterations', 30), ('maxBacktracks', 20)]:
        if type(config[key]) is not int or not 1 <= config[key] <= limit:
            raise ValueError('Newton iteration limits cannot exceed 30/20.')
    return value
