"""Versioned physical/provider declarations and graph identities, never equations."""
import re
import sympy as sp
from core.mathematics.contract import keys


def read_definition(value, model):
    keys(value,['format','version','volumes'])
    if value['format']!='rage.equilibrium-reactions' or type(value['version']) is not int or value['version']!=1:
        raise ValueError('Expected equilibrium reaction declaration version 1.')
    if not isinstance(value['volumes'],dict) or not value['volumes']:
        raise ValueError('Declare at least one reaction region.')
    selection=model['motores'].get('derivedExecution')
    if selection is not None and selection.get('version')!=4:
        raise ValueError('Equilibrium reactions require the recorded index-one extent selection (version 4); thermal/steady composition is not admitted.')
    volumes={v['id']:v for v in model['volumenes']}
    for owner,entry in value['volumes'].items():
        keys(entry,['provider','species','phaseId','standardState','anchor','temperatureId','pressureId',
                    'amountIds','referenceIds','extentIds','reactions'],['packageId'])
        if owner not in volumes or owner in model['motores'].get('kineticReactions',{}).get('volumes',{}):
            raise ValueError('Reaction region is missing or has competing kinetic declarations.')
        if entry['provider'] not in ('ideal_gas','package') or entry['phaseId'] not in ('vapor','liquido') or entry['anchor'] not in ('gas','liquid'):
            raise ValueError('Declare the physical phase, provider and formation anchor.')
        if entry['standardState'] not in ('ideal_gas_P0','pure_liquid_TP'):
            raise ValueError('Unknown reaction standard state.')
        # Optional since 6 November 2026 (B3): a package provider names the
        # declared thermodynamic package that executes its potentials. Earlier
        # package declarations without it still load; the compiler rejects them.
        if 'packageId' in entry and (entry['provider']!='package' or entry['packageId'] not in [p['id'] for p in model['termodinamica']['paquetes']]):
            raise ValueError('Only a package provider names a packageId, and it must be a declared thermodynamic package.')
        species=entry['species'];components={c['id']:c for c in model['componentes']}
        expected=[components[c].get('identidadQuimica',{}).get('cas') for c in volumes[owner]['componenteIds']]
        if not isinstance(species,list) or not species or species!=expected or len(set(species))!=len(species) or any(not isinstance(c,str) or not c for c in species):
            raise ValueError('Reaction species must match the declared component chemical order.')
        for field in ('amountIds','referenceIds','extentIds'):
            ids=entry[field]
            if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids) or any(not isinstance(q,str) or not q for q in ids):
                raise ValueError('Expected distinct graph quantity identities: '+field)
        if any(len(entry[f])!=len(species) for f in ('amountIds','referenceIds')):
            raise ValueError('Amounts and reference coordinates must cover every species.')
        if any(not isinstance(entry[f],str) or not entry[f] for f in ('temperatureId','pressureId')):
            raise ValueError('Temperature and pressure need graph quantity identities.')
        rows=entry['reactions']
        if not isinstance(rows,list) or not rows or len(rows)>100:
            raise ValueError('Declare between one and 100 reaction rows.')
        seen=set();matrix=[]
        for row in rows:
            keys(row,['id','stoichiometry','equationId'])
            if not isinstance(row['id'],str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,39}',row['id']) or row['id'] in seen:
                raise ValueError('Distinct stable reaction identities are required.')
            seen.add(row['id'])
            if not isinstance(row['equationId'],str) or not row['equationId']:
                raise ValueError('Select the recorded equilibrium equation.')
            stoich=row['stoichiometry']
            if not isinstance(stoich,list) or len(stoich)!=len(species) or any(not isinstance(v,str) or not re.fullmatch(r'(?:0|-?[1-9]\d*)(?:/[1-9]\d*)?',v) for v in stoich):
                raise ValueError('Stoichiometry uses exact rational strings in species order.')
            coefficients=[sp.Rational(v) for v in stoich]
            if any(not v.is_finite for v in coefficients) or not any(v<0 for v in coefficients) or not any(v>0 for v in coefficients):
                raise ValueError('Finite reactant and product coefficients are required.')
            matrix.append(coefficients)
        if sp.Matrix(matrix).rank()!=len(entry['extentIds']):
            raise ValueError('One extent is required per independent reaction.')
    return value
