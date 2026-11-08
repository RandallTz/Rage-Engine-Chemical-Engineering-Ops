"""Publish connected samples without substituting independent stage solutions."""
import numpy as np
import sympy as sp
from core.mathematics.numeric_lowering import lambdify_numeric

from core.resultados import conjunto, eje, evento, serie, leer_resultados
from core.solvers import integrar
from .indexed_network import discharge, _failure


def dynamic_result(system):
    study = system.model['estudio']
    trajectory = integrar(system, system.initial(), system.tf, rtol=study['rtol'],
        atol=system.atol, max_step=system.tf/(study['muestras']-1), metodo=system.method)
    times = sorted({float(t) for t in np.linspace(0., system.tf, study['muestras']) if t <= trajectory.t_fin}
                   | {float(trajectory.t_fin)})
    samples = [trajectory.y(t) for t in times]
    events = []
    owners = {closure.owner:f'{system.expansion["indexSetId"]}.stage.{j+1}'
              for j, stage in enumerate(system.stages) for closure in stage.closures}
    for code, t, before, after, message in trajectory.eventos:
        if code == 'cambio_firma':
            for (owner, previous), (_, current) in zip(before, after):
                for phase in sorted(set(current)-set(previous)):
                    events.append(evento('aparicion_fase','t',t,phase+' appears',owners[owner]))
                for phase in sorted(set(previous)-set(current)):
                    events.append(evento('desaparicion_fase','t',t,phase+' disappears',owners[owner]))
        else:
            events.append(evento(code,'t',t,message))
    return _publish(system, times, samples, 'dynamic', events=events,
        status='parcial' if trajectory.detenida else 'resuelto',
        evidence={'steps':trajectory.pasos,'rejections':trajectory.rechazos,
                  'stop':str(trajectory.detenida) if trajectory.detenida else None})


def steady_result(system):
    root, evidence = system.solve()
    return _publish(system.dynamic, [0.], [system.state(root)], 'steady',
                    evidence={'solver':evidence,'balances':system.verifications})


def _publish(system, times, samples, mode, *, events=(), status='resuelto', evidence=None):
    expansion = system.expansion
    identity = expansion['indexSetId']
    dynamic = mode == 'dynamic'
    axes = [eje('t','Time','tiempo','s',times)] if dynamic else [eje('j','Stage j','parametro','1',range(1,len(system.stages)+1))]
    rows, checks, stages, missing = [], [], [], []
    profiles = {}
    samples = np.asarray(samples)
    output_vectors = [system.closure_values(t,y) for t,y in zip(times,samples)]
    def evaluate(j, expression):
        expression = system.connected_expression(j, expression)
        admitted = set(system.variables+system.outputs+[system.time])
        if expression.atoms(sp.core.function.AppliedUndef) or expression.free_symbols-admitted:
            return None
        function = lambdify_numeric([system.time,system.variables,system.outputs],expression,modules='numpy',cse=True)
        with np.errstate(divide='ignore',invalid='ignore'):
            values = [float(function(t,y,c)) for t,y,c in zip(times,samples,output_vectors)]
        return [v if np.isfinite(v) else None for v in values]
    for j, stage in enumerate(system.stages):
        owner = f'{identity}.stage.{j+1}'
        mapping = expansion['stages'][j]['provenance']['identityMap']
        source_quantities = {v:k for k,v in mapping['quantities'].items()}
        source_volumes = {v:k for k,v in mapping['volumes'].items()}
        record = {'index':j+1,'ownerId':owner,'seriesIds':[],'closures':[]}
        local = samples[:,system.offsets[j]:system.offsets[j+1]]
        def add(key, label, unit, values, profile=False):
            key_id = owner+'.'+key
            if values is None:
                values = [None]*len(times)
                missing.append(key_id)
            rows.append(serie(key_id,label,unit,['t'] if dynamic else [], values if dynamic else values[0], propietarioId=owner))
            record['seriesIds'].append(key_id)
            if profile:
                profiles.setdefault(key,[]).append(key_id)
            return key_id
        for k,(quantity,qid) in enumerate(zip(stage.states,stage.state_ids)):
            add('state.'+source_quantities[qid],str(quantity),stage._unit(quantity),local[:,k].tolist(),True)
        for selection, expression in stage.reconstructed:
            qid = selection['quantityId']
            add('observable.'+source_quantities[qid],str(stage.quantities[qid]),stage._unit(stage.quantities[qid]),evaluate(j,expression),True)
        for closure in stage.closures:
            publications = [closure.evaluate(t,y,'publication') for t,y in zip(times,local)]
            volume = owner+'.volume.'+source_volumes[closure.owner]
            verification = 'thermodynamics.closure.'+volume
            certificates = [p[1]['certificate'] for p in publications]
            ratio = max(c['residual']/c['scale'] if closure.single else c['ratio'] if c['certified'] else max(2.,c['ratio']) for c in certificates)
            checks.append({'id':verification,'valor':ratio,'tolerancia':1e-9 if closure.single else 1.,
                           'descripcion':'Package closure certificate at connected-network samples.'})
            record['closures'].append({'volumeId':volume,'mode':'single_phase' if closure.single else 'equilibrium','verificationId':verification})
            for k,quantity in enumerate(closure.outputs):
                add('closure.'+source_volumes[closure.owner]+'.'+source_quantities[stage.ids[quantity]],str(quantity),stage._unit(quantity),
                    [float(p[0][k]) for p in publications],True)
            if closure.owner in (stage.model['motores'].get('kineticReactions') or {}).get('volumes',{}):
                from .derived_closure import reaction_limit
                diagnostic,_ = reaction_limit(stage,closure,times,local)
                diagnostic['id'] = 'reactions.equilibrium_limit.'+volume
                checks.append(diagnostic)
        if dynamic:
            for k,(selection,inventory,_,scale) in enumerate(stage.checks):
                values = evaluate(j,inventory)
                initial = values[0]
                residual = max(abs(v-initial-y[stage.size+k]) for v,y in zip(values,local))/float(scale)
                checks.append({'id':owner+'.conservation.'+selection['equationId'],'valor':residual,'tolerancia':1e-9,
                               'descripcion':'Connected inventory change minus integrated net-rate budget, in declared physical scales.'})
        for published in expansion['ports']:
            if published['endpoint']['stage'] != j+1:
                continue
            port = published['port']
            bindings = {}
            prefix = 'port.'+port['id']+'.'
            if port['kind'] == 'material':
                _,fluxes,enthalpy = discharge(stage,port,getattr(system,'location','indexSet')+'.ports.'+port['id'])
                total = sum(fluxes)
                bindings['flow'] = add(prefix+'flow','Boundary mass flow','kg/s',evaluate(j,total))
                bindings['composition'] = [add(prefix+'fraction.'+str(k),'Boundary mass fraction','1',evaluate(j,q/total)) for k,q in enumerate(fluxes,1)]
                bindings['specificEnthalpy'] = add(prefix+'enthalpy','Boundary specific enthalpy','J/kg',evaluate(j,enthalpy))
                stream = next(s for s in stage.model['corrientes'] if s['id']==port['boundary']['id'])
                inlet = next((c.inlets[stream['id']] for c in stage.closures if stream['id'] in c.inlets),None)
                donor = next((c for c in stage.closures if c.owner==port['volumeId']),None)
                for role,unit,symbol in [('temperature','K','T'),('pressure','Pa','P')]:
                    values = ([inlet[symbol]]*len(times) if inlet is not None else
                              evaluate(j,stage._expand(sp.Function(symbol+'__'+donor.owner)(stage.time))) if donor is not None and port.get('donorPhase') else None)
                    bindings[role] = add(prefix+role,'Boundary '+role,unit,values)
            else:
                volume = next(v for v in stage.model['volumenes'] if v['id']==port['volumeId'])
                data_id = volume.get('terminos',{}).get(port['boundary']['id'])
                if port['kind']=='heat':
                    # A declared heat-transfer law may depend on the current
                    # state; its initial datum is not a constant boundary law.
                    powers = evaluate(j,stage._expand(sp.Function('energy_heat_rate__'+port['volumeId'])(stage.time)))
                else:
                    power = float(stage._datum(data_id,{'M':1,'L':2,'T':-3})) if data_id else None
                    powers = None if power is None else [power]*len(times)
                bindings['power'] = add(prefix+'power','Boundary power','W',powers)
            record.setdefault('_ports',[]).append({'portId':port['id'],'stage':j+1,'kind':port['kind'],
                                                  'direction':port['direction'],'variables':bindings})
        stages.append(record)
    ports = [p for stage in stages for p in stage.pop('_ports',[])]
    profile_rows = []
    if not dynamic:
        by_id = {row['id']:row for row in rows}
        for key,sources in profiles.items():
            if len(sources) != len(stages):
                continue
            source = by_id[sources[0]]
            if any(by_id[k]['unidadSI']!=source['unidadSI'] for k in sources):
                continue
            target = identity+'.profile.'+key
            rows.append(serie(target,source['nombre']+' by stage',source['unidadSI'],['j'],[by_id[k]['valores'] for k in sources],propietarioId=identity))
            profile_rows.append({'seriesId':target,'stageSeriesIds':sources})
        checks.extend({'id':f'{identity}.stage.{r["stage"]}.conservation.{r["equationId"]}',
                       'valor':r['residual'],'tolerancia':r['tolerance'],'descripcion':'Connected zero-rate balance residual.'}
                      for r in evidence['balances'])
    if status == 'resuelto' and any(row['valor']>row['tolerancia'] for row in checks
                                   if not row['id'].startswith('reactions.equilibrium_limit.')):
        raise _failure('index_network_publication_failed','Connected sample verification failed.','indexedNetwork')
    result = conjunto(system.model['id'],system.model['nombre'],status,
        {'motor':getattr(system,'publication_engine','rage.compilador.indexed_network'),'metodo':system.method if dynamic else 'damped_newton',
         'firma':expansion['sourceSignature'],'networkEvidence':{'version':1,'mode':mode,'linearPolicy':system.linear_policy,
         'numerical':evidence,'unresolvedPortSeries':missing}},axes,rows,events,checks,modeloId=system.model['id'])
    result['indexedNetwork'] = {'version':2,'indexSetId':identity,'count':len(stages),'mode':mode,
        'stageAxisId':None if dynamic else 'j','stages':stages,
        'endPorts':[p for p in ports if p['stage'] in (1,len(stages))],
        'sidePorts':[p for p in ports if p['stage'] not in (1,len(stages))],'profiles':profile_rows}
    return leer_resultados(result)
