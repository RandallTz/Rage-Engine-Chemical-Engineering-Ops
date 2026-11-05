"""A thermal chain recorded through the same physical journals and workbench as Model."""
import copy
from unittest.mock import patch

import sympy as sp

from m1_acceptance import SharedAuthor, thermal_source, THERMAL_REFERENCE
from core.compilador.derived_graph import source_signature
from core.mathematics.dimensions import catalog



class ChainRecipeAuthor(SharedAuthor):
    """Batch a known recipe, then pin actual shared replay receipts and replay again.

    This avoids replaying every prefix three times when building forty volumes.
    It is deliberately limited to this recipe's pre-existing quantity identities;
    no terminal equation is supplied, and every algebra step is replayed twice.
    """
    def append(self, kind, family='matter', **fields):
        self.definition['operations'].append({'kind':kind,'family':family,**fields})
        self.definition['cursor'] += 1
        return 'operation.'+str(self.definition['cursor'])

    def finish(self, outputs):
        self.refresh()
        for operation, receipt in zip(self.definition['operations'], self.result.receipts):
            if receipt.calculated_input_signatures:
                operation['sourceSignatures'] = dict(receipt.calculated_input_signatures)
        self.refresh()
        assert all(r.signature_status != 'legacy/unsigned' for r in self.result.receipts)
        return super().finish(outputs)


def thermal_chain(count, *, author_class=ChainRecipeAuthor):
    owners = ['region_'+str(i) for i in range(count)]
    data = {'mass': [1.]*count, 'initialTemperature': [330.+i/count for i in range(count)],
            'specificCapacity': [300.]*count}
    with patch.dict(THERMAL_REFERENCE, data):
        model = thermal_source(owners)
    model['id'] = 'internal-sparse-thermal-chain-'+str(count)
    model['nombre'] = 'Recorded thermal chain'
    author = author_class(model)
    q = author.quantity
    t = sp.Symbol('t', real=True)
    author.append('declare_symbol', 'energy', name='chainConductance', unit='W/K')
    author.append('declare_symbol', 'energy', name='bathTemperature', unit='K')
    # Subsequent steps introduce equations only; reuse this exact quantity catalog.
    quantity_ids = {v:k for k,v in {**catalog(author.result.graph, author.result.units), **author.result.introduced}.items()}
    q = quantity_ids.__getitem__
    rates = []
    for i, owner in enumerate(owners):
        temperature = sp.Function('T__'+owner)(t)
        left = q(sp.Function('T__'+owners[i-1])(t)) if i else 'bathTemperature'
        right = q(sp.Function('T__'+owners[i+1])(t)) if i+1<count else 'bathTemperature'
        law = author.relation(q(sp.Function('energy_heat_rate__'+owner)(t)),
            'chainConductance*('+left+'-2*'+q(temperature)+'+'+right+')',
            'Exhaustive linear heat exchanges with adjacent regions; each internal exchange has equal and opposite signs; end regions exchange with a prescribed bath.',
            'energy', 'constitutive')
        energy = sp.Function('U__'+owner)(t)
        row = next(k for k in author.selected if k.startswith('energy.'+owner+'.')
                   and author.source.nodes[k].equation.lhs == sp.diff(energy,t))
        rates.append(author.substitute(row, law, sp.Function('energy_heat_rate__'+owner)(t), 'energy'))
        caloric = 'thermodynamics.'+owner+'.caloric-inventory'
        author.append('declare_domain', 'thermodynamics', sources=[caloric],
                      symbol=q(sp.Function('m__'+owner+'__1')(t)), domain='positive', reason='Positive closed inventory')
    model, replayed, _ = author.finish({})
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    identity = lambda name: next(k for k,v in quantities.items() if str(v)==name)
    def datum(name,value,unit):
        model['datos'][name] = {'magnitud':name,'funcion':'parametro',
            'declaracion':{'texto':str(value),'unidad':unit},'origen':{'propietarioId':'estudio','ruta':name}}
        return name
    selection = {'format':'rage.derived-execution','version':1,'sourceSignature':source_signature(model,replayed),
        'timeId':identity('t'),'states':[],'parameters':{},'initialValues':{},'initialEquations':[],
        'reconstructions':[],'checks':[]}
    for i, owner in enumerate(owners):
        mass = sp.Function('m__'+owner+'__1')(t)
        mass_row = next(k for k in replayed.selected if k.startswith('matter.'+owner+'.')
                        and replayed.graph.nodes[k].equation.lhs==sp.diff(mass,t))
        for name,row,key in [(str(mass),mass_row,owner+'.mass'),
                ('U__'+owner+'(t)',rates[i],datum(owner+'.initialEnergy',300*(30+i/count),'J'))]:
            selection['states'].append({'quantityId':identity(name),'equationId':row})
            selection['initialValues'][identity(name)] = key
        selection['reconstructions'] += [
            {'quantityId':identity('T__'+owner+'(t)'), 'equationId':'thermodynamics.'+owner+'.caloric-inventory'},
            {'quantityId':identity('m_total__'+owner+'(t)'), 'equationId':'matter.'+owner+'.total-definition'}]
        for name,field in [('caloric_capacity','capacity'),('T_reference','referenceTemperature'),('u_reference','referenceEnergy')]:
            selection['parameters'][identity(name+'__'+owner)] = owner+'.'+field
    selection['parameters'][identity('chainConductance')] = datum('chain.conductance',10,'W/K')
    selection['parameters'][identity('bathTemperature')] = datum('chain.bath',300,'K')
    model['motores']['derivedExecution'] = selection
    model['estudio'] = {'tipo':'temporal','tiempoId':datum('chain.horizon',1000,'s'),
        'metodoSolicitado':'bdf','muestras':21,'rtol':1e-8,'atol':{'cantidad':1e-10,'energia':1e-6}}
    return copy.deepcopy(model)

