"""Fresh matter journals and shared authoring operations, never terminal ODEs."""
from core.balances import material_derivation as material
from core.compilador.derived import source_signature
from core.modelo.equation_workbench import build, edit
from core.mathematics.dimensions import catalog


def matter_case(case, owner='region', component=7):
    model = {'formato': 'rage.modelo', 'version': 0, 'id': 'matter-'+case,
        'nombre': 'Matter lowering '+case, 'componentes': [{'id': component, 'nombre': 'Material', 'simbolo': 'M'}],
        'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [], 'intercambios': [],
        'datos': {}, 'matematico': None, 'estudio': None, 'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'integrate', 'total', 'impermeable_remainder'):
        journal = material.edit_journal(journal, owner, {'kind': action})
    if case != 'decay':
        journal = material.edit_journal(journal, owner, {'kind': 'no_reaction'})
    if case == 'decay':
        journal = material.edit_journal(journal, owner, {'kind': 'fixed_boundary'})
    entry = journal['volumes'][owner]
    # The same granular journal change protocol used by the Model controls.
    for name, changes in [('mean', {'cantidadVolumen': True}), ('product', {'expandirProducto': True})]:
        entry['operations'].append({'id': name, 'title': name, 'changes': changes})
    if case == 'filling':
        for name, changes in [('density', {'densidadMediaConstante': True}), ('ports', {'densidadComunPuertos': True})]:
            entry['operations'].append({'id': name, 'title': name, 'changes': changes})
    model['motores']['materialDerivation'] = journal

    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role,
            'declaracion': {'texto': str(value), 'unidad': unit},
            'origen': {'propietarioId': 'volumen:'+owner, 'ruta': key}}
        return key
    volume = {'id': owner, 'componenteIds': [component],
        'balances': {'materia': True, 'energia': False, 'momento': False},
        'supuestos': {'materia': material.replay_volume(entry)[-1], 'energia': None},
        'frontera': {'tipo': 'sin_relacion'},
        'inicial': {'cantidades': {'base': 'masica', 'datoIds': {str(component): datum('mass', 6, 'kg', 'inicial')}}},
        'termodinamica': {'tipo': 'supuesto', 'supuesto': 'fase_no_evaluada',
            'motivo': 'Explicit nonspatial matter approximation; no caloric or equilibrium closure is asserted.'}}
    if case == 'decay':
        volume['frontera'] = {'tipo': 'rigida', 'datoId': datum('volume', 2, 'm3', 'geometria')}
    model['volumenes'].append(volume)
    if case != 'decay':
        model['corrientes'].append({'id': 'feed', 'desde': None, 'hasta': owner, 'componenteIds': [component],
            'mecanismo': 'convectivo', 'materia': {'modo': 'por_componente', 'base': 'masica',
                'caudalIds': {str(component): datum('flow', 0.6, 'kg/s', 'frontera')}}})

    def append(kind, **fields):
        report = edit(model, {'kind': 'append', 'operation': {'kind': kind, 'family': 'matter', **fields}})
        model['motores']['equationWorkbench'] = report['definition']
        return 'operation.'+str(report['definition']['cursor'])
    def named(name):
        result = build(model)
        return next(key for key, q in {**catalog(result.graph, result.units), **result.introduced}.items() if str(q) == name)
    prefix = f'matter.{owner}.{component}'
    density = named(f'rho_mean__{owner}__{component}'+('' if case == 'filling' else '(t)'))
    geometric = named(f'V__{owner}'+('' if case == 'decay' else '(t)'))
    parameters = {}; reconstructions = []
    if case == 'decay':
        append('declare_symbol', name='coefficient', unit='m3/(kg*s)')
        # Constitutive sink, independently declared; conservation supplies the ODE.
        append('declare_relation', left=named(f'G__{owner}__{component}(t)'), right='0', reason='No generation', relationKind='constitutive')
        append('declare_relation', left=named(f'C__{owner}__{component}(t)'), right=f'coefficient*{geometric}*{density}^2', reason='Quadratic volumetric consumption', relationKind='constitutive')
        parameters[named('coefficient')] = datum('coefficient', 0.1, 'm3/(kg*s)')
        parameters[geometric] = 'volume'
        reconstructions.append({'quantityId': named(f'V__{owner}(t)'), 'equationId': prefix+'.fixed-volume'})
        state = density; initial = datum('density.initial', 3, 'kg/m3', 'inicial')
    elif case == 'filling':
        parameters[density] = datum('density', 3, 'kg/m3')
        parameters[named('Q__feed(t)')] = datum('volumeFlow', 0.2, 'm3/s')
        state = geometric; initial = datum('volume.initial', 2, 'm3', 'inicial')
    else:
        for name, value, unit in [('initialVolume', 2, 'm3'), ('expansionRate', 0.2, 'm3/s')]:
            append('declare_symbol', name=name, unit=unit)
            parameters[named(name)] = datum(name, value, unit)
        relation = append('declare_relation', left=geometric, right='initialVolume+expansionRate*'+named('t'),
            reason='Prescribed expanding control volume', relationKind='constitutive')
        reconstructions.append({'quantityId': geometric, 'equationId': relation})
        parameters[named(f'q__feed__{component}(t)')] = 'flow'
        state = density; initial = datum('density.initial', 3, 'kg/m3', 'inicial')
        model['datos']['flow']['declaracion']['texto'] = '0.3'
    # Explicit regular regime; the compiler must retain and enforce this domain.
    rate = next(key for key in reversed(build(model).selected) if key.startswith(prefix) and build(model).graph.nodes[key].kind == 'balance')
    append('declare_domain', sources=[rate], symbol=geometric, domain='positive', reason='Positive control volume')
    append('declare_domain', sources=[rate], symbol=density, domain='positive', reason='Positive mean density')
    reconstructions.append({'quantityId': named(f'm__{owner}__{component}(t)'), 'equationId': prefix+'.mean-inventory'})
    reconstructions.append({'quantityId': named(f'm_total__{owner}(t)'), 'equationId': f'matter.{owner}.total-definition'})
    if case == 'filling':
        reconstructions.append({'quantityId': named(f'rho_mean__{owner}__{component}(t)'), 'equationId': prefix+'.constant-density'})
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': datum('horizon', 5, 's', 'estudio'),
        'metodoSolicitado': 'rk45', 'muestras': 31, 'rtol': 1e-9, 'atol': {'cantidad': 1e-11}}
    model['motores']['derivedExecution'] = {'format': 'rage.derived-execution', 'version': 1,
        'sourceSignature': source_signature(model), 'timeId': named('t'),
        'states': [{'quantityId': state, 'equationId': rate}], 'parameters': parameters,
        'initialValues': {state: initial, named(f'm__{owner}__{component}(t)'): 'mass'},
        'initialEquations': [], 'reconstructions': reconstructions, 'checks': []}
    return model
