"""Strict kinetic declarations. No balance, caloric model or equilibrium solver."""
import re
import sympy as sp
from core.mathematics.contract import keys
from core.unidades import exact_conversion, ErrorUnidad

FORMAT = 'rage.kinetic-reactions'


def coefficient(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,8}(?:/\d{1,8})?', value):
        raise ValueError('Stoichiometric coefficients must be exact rational strings.')
    try:result = sp.Rational(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError('A stoichiometric coefficient must have a nonzero denominator.') from error
    if not result.is_finite:
        raise ValueError('A stoichiometric coefficient must be finite.')
    return result


def datum(model, key, unit):
    if key not in model['datos']:
        raise ValueError('Missing kinetic datum: '+str(key))
    declaration = model['datos'][key]['declaracion']
    try:conversion = exact_conversion(declaration['unidad'])
    except ErrorUnidad as error:
        raise ValueError('Invalid kinetic datum unit: '+key) from error
    if conversion['afin'] or conversion['dimension'] != exact_conversion(unit)['dimension']:
        raise ValueError('Incompatible kinetic datum unit: '+key+'; expected '+unit)
    # Declarations are finite numerical constants, never executable text.
    text = declaration['texto']
    if not isinstance(text, str) or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text.strip()):
        raise ValueError('A kinetic datum must be a finite real constant: '+key)
    return sp.Rational(text.strip()) * sp.Rational(conversion['factor'])


def read_definition(value, model):
    keys(value, ['format', 'version', 'volumes'])
    if value['format'] != FORMAT or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported kinetic reaction format/version.')
    volumes = value['volumes']
    if not isinstance(volumes, dict) or len(volumes) > 160:
        raise ValueError('Kinetic volumes must be an object with at most 160 entries.')
    owners = {v['id']: v for v in model['volumenes']}
    for owner, entry in volumes.items():
        if owner not in owners:
            raise ValueError('Unknown kinetic volume: '+owner)
        volume = owners[owner]
        if not volume['balances']['materia']:
            raise ValueError('Kinetic reactions require active component balances.')
        keys(entry, ['volumeDataId', 'molarMassDataIds', 'elements', 'reactions'])
        components = {str(c) for c in volume['componenteIds']}
        masses = entry['molarMassDataIds']
        if not isinstance(masses, dict) or set(masses) != components:
            raise ValueError('Declare a molar mass for every component of the kinetic volume.')
        if datum(model, entry['volumeDataId'], 'm3') <= 0:
            raise ValueError('The reacting volume must be positive.')
        if volume['frontera']['tipo'] == 'rigida' and datum(model, volume['frontera']['datoId'], 'm3') != datum(model, entry['volumeDataId'], 'm3'):
            raise ValueError('The reacting volume must match the declared rigid control volume.')
        if 'volumenDatoId' in volume and datum(model, volume['volumenDatoId'], 'm3') != datum(model, entry['volumeDataId'], 'm3'):
            raise ValueError('The reacting volume must match the declared material-volume datum.')
        molar_masses = {c: datum(model, d, 'kg/mol') for c, d in masses.items()}
        if any(m <= 0 for m in molar_masses.values()):
            raise ValueError('Molar masses must be positive.')
        elements = entry['elements']
        if not isinstance(elements, dict) or not elements or len(elements) > 120:
            raise ValueError('Declare elemental composition (and charge where applicable).')
        for name, row in elements.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(row, dict) or set(row) != components:
                raise ValueError('Each elemental/charge row must cover exactly the components.')
            if any(type(n) is not int or abs(n) > 100000 or name != 'charge' and n < 0 for n in row.values()):
                raise ValueError('Element counts must be nonnegative integers; charge may be signed.')
        reactions = entry['reactions']
        if not isinstance(reactions, list) or not 1 <= len(reactions) <= 100:
            raise ValueError('Declare between one and 100 kinetic reactions.')
        ids = set()
        for reaction in reactions:
            keys(reaction, ['id', 'stoichiometry', 'orders', 'rateConstantDataId'], ['arrhenius'])
            rid = reaction['id']
            if not isinstance(rid, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}', rid) or rid in ids:
                raise ValueError('Reaction identities must be unique stable identifiers.')
            ids.add(rid)
            nu = reaction['stoichiometry']
            if not isinstance(nu, dict) or set(nu) != components:
                raise ValueError('Stoichiometry must cover exactly the volume components.')
            nu = {c: coefficient(n) for c, n in nu.items()}
            if not any(n < 0 for n in nu.values()) or not any(n > 0 for n in nu.values()):
                raise ValueError('A reaction needs both reactants and products.')
            if any(sum(row[c]*nu[c] for c in components) != 0 for row in elements.values()):
                raise ValueError('Reaction violates declared elemental or charge conservation: '+rid)
            if sum(molar_masses[c]*nu[c] for c in components) != 0:
                raise ValueError('Reaction violates total mass conservation with the declared molar masses: '+rid)
            orders = reaction['orders']
            if not isinstance(orders, dict) or set(orders) - components or any(type(n) is not int or not 0 <= n <= 6 for n in orders.values()):
                raise ValueError('Concentration orders must be integers from zero to six.')
            order = sum(orders.values())
            unit = f'(mol/m3)^{1-order}/s'
            if datum(model, reaction['rateConstantDataId'], unit) < 0:
                raise ValueError('The forward rate constant must be nonnegative; declare reverse reactions separately.')
            if 'arrhenius' in reaction:
                activation = reaction['arrhenius']
                keys(activation, ['energyDataId', 'temperatureDataId'])
                datum(model, activation['energyDataId'], 'J/mol')
                if datum(model, activation['temperatureDataId'], 'K') <= 0:
                    raise ValueError('The Arrhenius reference temperature must be positive.')
    return value
