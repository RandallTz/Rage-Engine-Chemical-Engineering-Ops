"""Shared admission of nonspatial equilibrium networks, before integration.

The strict model reader owns syntax and references. This module owns physical
roles and executable scope. It never calls the legacy assembly validator/solver.
"""
import numpy as np

from core import expresiones_motor as ex
from core import catalogo, mezclas, paquetes_volumen, unifac
from core import unidades as units
from chemicals.identifiers import check_CAS
from core.termodinamica import capa
from core.termodinamica.volumen import CierreVolumen
from .compilador import AdmissionError, _Dato, temporal_method


def _liquid_only_volume(model, volume, path, owner, reject):
    _, package = capa._volumen(model, owner)
    cas = capa._cas(model, volume)
    if package['modelo']['id'] in capa.EOS_PAQUETES:
        reject('unsupported_package', 'The cubic EOS packages have no liquid-only phase set: a liquid-only species '
               'needs a mixture package with that phase set.', path+'.termodinamica', 'MOTOR_ENS_ESPECIE_SOLO_LIQUIDO')
        return
    try:
        substitutions = catalogo.leer_sustituciones(package['datosPuros'], 'datosPuros', set(cas)) if package.get('datosPuros') else None
        mezclas.Sistema(package['modelo']['id'], cas, sustituciones=substitutions, solo_liquido=True)
    except (mezclas.FaltaParametro, catalogo.SustitucionRechazada, unifac.FaltaDatoUNIFAC) as error:
        reject('unsupported_package', str(error), path+'.termodinamica', 'MOTOR_ENS_'+getattr(error, 'codigo', 'PAQUETE'))
        return
    except KeyError as error:
        reject('unsupported_package', 'Unknown thermodynamic package: '+str(error), path+'.termodinamica', 'MOTOR_ENS_PAQUETE')
        return
    reject('liquid_only_vapour_operation', 'Volume '+owner+' declares a liquid-only phase set (fase_vapor not modelled): this compiler '
           'evaluates every state with a UV/PH flash, which needs the vapour phase. Use the derived execution of the '
           'single-phase liquid package closure.', path+'.termodinamica', 'MOTOR_ENS_ESPECIE_SOLO_LIQUIDO')
    for index, stream in enumerate(model['corrientes']):
        extraction = (stream.get('extraccion') or {}).get(owner)
        if isinstance(extraction, dict) and extraction.get('fase') == 'vapor':
            reject('liquid_only_vapour_operation', 'Stream '+stream['id']+' draws vapour from the liquid-only volume '+owner+'.',
                   f'corrientes[{index}].extraccion.'+owner, 'MOTOR_ENS_ESPECIE_SOLO_LIQUIDO')


def validate(model, *, initialization=True):
    errors, data, closures = [], {}, {}
    final_time = None

    def reject(code, message, path, native='MOTOR_ENS_FORMA'):
        errors.append({'code': code, 'message': message, 'path': path, 'nativeCode': native})

    def datum(identity, unit, path, *, constant=False, positive=False, nonnegative=False, derivative_required=False):
        if identity not in model['datos']:
            reject('missing_data', 'Missing datum: '+str(identity), path, 'MOTOR_ENS_REFERENCIA')
            return None
        try:
            value = _Dato(model['datos'][identity], 'datos.'+identity, unit)
            if constant and value.derivada is not None:
                reject('time_dependent_initial_data', 'This role requires a constant datum.', path, 'MOTOR_ENS_DEBE_SER_CONSTANTE')
            if value.derivada is not None and ex.no_suaves(value.arbol):
                reject('nonsmooth_boundary', 'This boundary requires a smooth time function.', path, 'MOTOR_ENS_NO_SUAVE')
            if value.derivada is not None and final_time:
                from .datum_bounds import certify
                certify(value, final_time, positive=positive, nonnegative=nonnegative)
                if derivative_required:
                    certify(value, final_time, derivative=True)
            minimum = value(0)
            if positive and minimum <= 0 or nonnegative and minimum < 0:
                reject('invalid_inventory' if nonnegative else 'invalid_physical_value',
                       'The declared physical value is outside its admitted range.', path, 'MOTOR_ENS_FUERA_DE_MAGNITUD')
            # Re-evaluate every consuming role, even when two roles share an ID.
            # A cache hit must never hide a conflicting dimension.
            data[identity] = value
            return value
        except AdmissionError as error:
            errors.extend(error.diagnostics)
            return None

    volumes = {v['id']: v for v in model['volumenes']}
    if not volumes or len(volumes) > 3:
        reject('invalid_network_size', 'Equilibrium networks require 1 to 3 volumes.', 'volumenes', 'MOTOR_ENS_VOLUMENES')
    if not model['componentes']:
        reject('empty_components', 'Declare the chemical components.', 'componentes', 'MOTOR_ENS_CATALOGO')
    identities, identified_components = set(), set()
    molar_masses = {}
    for index, component in enumerate(model['componentes']):
        cas = component.get('identidadQuimica', {}).get('cas')
        if not isinstance(cas, str) or not cas:
            reject('missing_chemical_identity', 'Each component requires a CAS string.',
                   f'componentes[{index}].identidadQuimica', 'MOTOR_ENS_IDENTIDAD')
        elif cas in identities:
            reject('duplicate_chemical_identity', 'Each component requires a distinct CAS identity.',
                   f'componentes[{index}].identidadQuimica', 'MOTOR_ENS_IDENTIDAD_DUPLICADA')
        if isinstance(cas, str) and cas:
            identities.add(cas)
            if not check_CAS(cas):
                reject('invalid_chemical_identity', 'The CAS identifier is invalid.', f'componentes[{index}].identidadQuimica', 'MOTOR_ENS_CAS_INVALIDO')
            else:
                identified_components.add(component['id'])
        if component.get('identidadQuimica', {}).get('proveedorId'):
            reject('unsupported_chemical_identity', 'Only CAS identities can be verified.', f'componentes[{index}].identidadQuimica', 'MOTOR_ENS_IDENTIDAD_NO_VERIFICABLE')
        if 'masaMolar' in component:
            mass = component['masaMolar'].get('cantidad') if isinstance(component['masaMolar'], dict) else None
            if not isinstance(mass, dict) or mass.get('valor') is None:
                continue
            try:
                if not isinstance(mass, dict) or not units.compatibles(mass['unidad'], 'kg/mol'):
                    raise ValueError('Declare molar mass with mass/amount units.')
                value = units.a_SI(mass['valor'], mass['unidad'])
                if not np.isfinite(value) or value <= 0:
                    raise ValueError('Molar mass must be positive and finite.')
                molar_masses[component['id']] = value
            except (KeyError, TypeError, ValueError, units.ErrorUnidad) as error:
                reject('invalid_molar_mass', str(error), f'componentes[{index}].masaMolar', 'MOTOR_ENS_MASA_MOLAR')
    study = model['estudio']
    if study is None:
        reject('missing_study', 'Declare a temporal study.', 'estudio', 'MOTOR_ENS_ESTUDIO')
    else:
        horizon = datum(study['tiempoId'], 's', 'estudio.tiempoId', constant=True)
        if horizon is not None and horizon(0) <= 0:
            reject('invalid_horizon', 'The final time must be positive.', 'estudio.tiempoId', 'MOTOR_ENS_FUERA_DE_MAGNITUD')
        elif horizon is not None:
            final_time = horizon(0)
        if study['muestras'] > 1001:
            reject('invalid_samples', 'At most 1001 requested samples are admitted.', 'estudio.muestras', 'MOTOR_ENS_ESTUDIO')
        if not np.isfinite(study['rtol']) or not 1e-12 <= study['rtol'] <= 1e-2:
            reject('invalid_tolerance', 'Relative tolerance must be finite and in [1e-12, 1e-2].', 'estudio.rtol', 'MOTOR_ENS_ESTUDIO')
        for key, value in study['atol'].items():
            if not np.isfinite(value) or value <= 0:
                reject('invalid_tolerance', 'Absolute tolerances must be finite and positive.', 'estudio.atol.'+key, 'MOTOR_ENS_ESTUDIO')
        temporal_method(study['metodoSolicitado'])

    references = {}
    for index, volume in enumerate(model['volumenes']):
        path = f'volumenes[{index}]'; owner = volume['id']
        if not 1 <= len(volume['componenteIds']) <= 7:
            reject('invalid_component_count', 'A volume requires 1 to 7 declared species.', path+'.componenteIds', 'MOTOR_ENS_CATALOGO')
            continue
        if volume['termodinamica']['tipo'] != 'equilibrio':
            reject('unsupported_closure', 'This compiler requires an equilibrium closure.', path+'.termodinamica')
            continue
        matter = volume['supuestos']['materia']
        energy = volume['supuestos']['energia'] or {}
        field = matter.get('campo') or {}
        policy = volume['termodinamica']['politica']
        rules = matter.get('reglasEstado') or {}
        density_rules = rules.get('densidades') or []
        phase_rule = rules.get('fases')
        checks = [
            (matter.get('vista') != 'cantidad' or matter.get('cantidadVolumen') or energy.get('forma') != 'total',
             'FORMA', 'Use total component inventories and total energy.'),
            (matter.get('sinAcumulacion') or matter.get('fija') and field.get('estacionario') or energy.get('estacionario') or energy.get('sinAcumulacionTotal'),
             'ESTACIONARIO', 'Algebraic accumulation constraints require a steady-state/DAE solver.'),
            (not matter.get('restoImpermeable'), 'MATERIAL_REMAINDER', 'The unclosed boundary remainder requires a flux law.'),
            (matter.get('fija') != (volume['frontera']['tipo'] == 'rigida'), 'FRONTERA', 'Material and mechanical boundary assumptions disagree.'),
            (field.get('sinConveccion') and any(owner in (s['desde'], s['hasta']) for s in model['corrientes']),
             'MATERIAL_TRANSPORT', 'Declared streams require convective transport.'),
            (not (field.get('sinReaccion') or field.get('sinGeneracion') and field.get('sinConsumo')) or matter.get('generacionUniforme') or matter.get('consumoUniforme'),
             'FUENTES', 'Material sources require an executable constitutive law.'),
            (not (volume['balances']['materia'] and volume['balances']['energia']) or volume['balances']['momento'],
             'BALANCES', 'This equilibrium compiler executes matter and energy balances without momentum.'),
            (energy.get('modelo') == 'u_lineal', 'DOS_CIERRES', 'A manual caloric law conflicts with the equilibrium closure.'),
            (energy.get('densidadConstante') or matter.get('densidadMediaConstante') or matter.get('densidadComunPuertos') or any(
                isinstance(row, dict) and row.get('constanciaTemporal') not in (None, 'sin_restriccion') for row in density_rules),
             'DENSIDAD', 'A constant density assumption conflicts with the equilibrium density closure.'),
            (bool(energy.get('monofasico')) != (policy['cantidad'] == 'monofasico') or bool(energy.get('sinCambioFase')) != (policy['cambioInterno'] == 'prohibido') or
                isinstance(phase_rule, dict) and ((phase_rule.get('cantidad') == 'monofasico') != (policy['cantidad'] == 'monofasico')),
             'POLITICA', 'Declared phase assumptions disagree with the closure policy.'),
            (not all(energy.get(key) is True for key in ('uniforme', 'sinCinetica', 'separarPresion', 'sinTrabajoViscoso', 'sinFuerzasVolumen', 'sinFuenteVolumetrica')) or energy.get('trabajoTotalHeredado'),
             'TERMINOS', 'The first law requires the supported uniform pressure-work formulation.'),
            (volume['frontera']['tipo'] == 'presion_prescrita' and energy.get('presionUniforme') is not True,
             'FRONTERA', 'A prescribed-pressure boundary requires uniform pressure.'),
            (energy.get('presionPrescrita') is False and volume['frontera']['tipo'] == 'presion_prescrita' or
                energy.get('presionPrescrita') is True and volume['frontera']['tipo'] == 'rigida',
             'PRESION_PRESCRITA', 'The energy pressure assumption disagrees with the mechanical boundary.'),
        ]
        for failed, native, message in checks:
            if failed:
                reject('formulation_'+native.lower(), message, path+'.supuestos', 'MOTOR_ENS_'+native)
        if energy.get('soloLiquido'):
            # F5-C4: the recorded liquid-only phase set admits a liquid-only species
            # (Sistema(..., solo_liquido=True)), but each evaluation of this compiler is a
            # UV/PH flash and each extraction may draw vapour: both need the vapour phase.
            _liquid_only_volume(model, volume, path, owner, reject)
            continue
        _, package = capa._volumen(model, owner)
        package_id = package['modelo']['id']
        if package_id == capa.AGUA and package.get('datosPuros'):
            reject('unsupported_substitution', 'IAPWS-95 does not accept pure-data substitutions.', path+'.termodinamica', 'MOTOR_ENS_SUSTITUCION_NO_ADMITIDA')
        version = ('1' if package_id == capa.AGUA or package_id in capa.EOS_PAQUETES
                   else getattr(mezclas.PAQUETES.get(package_id), 'version', None))
        if version is None or str(version) != package['modelo']['version']:
            reject('unsupported_package', 'The requested package version is unavailable.', path+'.termodinamica', 'MOTOR_ENS_PAQUETE')
        elif set(volume['componenteIds']) <= identified_components:
            references[owner] = (paquetes_volumen.PaqueteAgua.referencia if package_id == capa.AGUA else mezclas.REFERENCIA)['id']
            try:
                closures[owner] = CierreVolumen(model, owner)
            except capa.NoSoportado as error:
                cause = error.__cause__
                native = ('MOTOR_ENS_'+cause.codigo if isinstance(cause, (mezclas.FaltaParametro, catalogo.SustitucionRechazada))
                          else 'MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE' if isinstance(cause, unifac.FaltaDatoUNIFAC)
                          else 'MOTOR_ENS_PAQUETE')
                reject('unsupported_package', str(error), path+'.termodinamica', native)
            if owner in closures:
                for component, mass in zip(volume['componenteIds'], closures[owner].M):
                    if component in molar_masses and abs(molar_masses[component]-mass) > 1e-7*mass:
                        reject('inconsistent_molar_mass', 'Declared molar mass contradicts the thermodynamic package.',
                               path+'.componenteIds', 'MOTOR_ENS_MASA_MOLAR_CONTRADICTORIA')
        boundary = volume['frontera']; kind = boundary['tipo']
        if kind == 'rigida':
            datum(boundary['datoId'], 'm3', path+'.frontera.datoId', constant=True, positive=True)
            if boundary.get('presionRestriccionId'):
                reject('unsupported_boundary', 'A rigid volume cannot also prescribe pressure.', path+'.frontera', 'MOTOR_ENS_FRONTERA')
        elif kind == 'presion_prescrita':
            datum(boundary['presionId'], 'Pa', path+'.frontera.presionId', positive=True, derivative_required=True)
        else:
            reject('unsupported_boundary', 'Select a rigid or prescribed-pressure boundary.', path+'.frontera', 'MOTOR_ENS_FRONTERA')
        if initialization:
            initial = volume['inicial']
            if 'cantidades' not in initial or 'energia' not in initial:
                reject('missing_initial_data', 'Declare initial component amounts and energy or temperature.', path+'.inicial', 'MOTOR_ENS_INICIAL')
                continue
            amounts = initial['cantidades']
            if set(amounts['datoIds']) != {str(c) for c in volume['componenteIds']}:
                reject('invalid_inventory', 'Declare exactly one inventory per volume component.', path+'.inicial.cantidades', 'MOTOR_ENS_INICIAL')
            values = [datum(identity, 'kg' if amounts['base'] == 'masica' else 'mol', path+'.inicial.cantidades',
                            constant=True, nonnegative=True) for identity in amounts['datoIds'].values()]
            if values and all(value is not None for value in values) and sum(value(0) for value in values) <= 0:
                reject('invalid_inventory', 'The initial total inventory must be positive.', path+'.inicial.cantidades', 'MOTOR_ENS_INICIAL_VACIO')
            energy = initial['energia']
            datum(energy['datoId'], 'K' if energy['tipo'] == 'T' else 'J', path+'.inicial.energia',
                  constant=True, positive=energy['tipo'] == 'T')
        heat_links = [q for q in model['intercambios'] if owner in (q['desde'], q['hasta'])]
        assumptions = volume['supuestos']['energia'] or {}
        adiabatic = assumptions.get('adiabatico') or assumptions.get('sinConduccionLocal')
        if not heat_links and not adiabatic:
            reject('missing_heat', 'Declare heat exchange or an adiabatic boundary.', path+'.supuestos.energia', 'MOTOR_ENS_Q_PENDIENTE')
        if heat_links and adiabatic:
            reject('conflicting_heat', 'An adiabatic volume declares heat exchange.', path+'.supuestos.energia', 'MOTOR_ENS_Q_ADIABATICO')

    for index, stream in enumerate(model['corrientes']):
        path = f'corrientes[{index}]'; source, target = stream['desde'], stream['hasta']
        if source == target:
            reject('invalid_topology', 'A stream must connect distinct endpoints.', path, 'MOTOR_ENS_TOPOLOGIA')
        if source in references and target in references and references[source] != references[target]:
            reject('incompatible_references', 'Material transport requires compatible thermodynamic references.', path,
                   'MOTOR_ENS_REFERENCIAS_INCOMPATIBLES')
        matter = stream['materia']
        endpoints = [volumes[key] for key in (source, target) if key in volumes]
        if not stream['componenteIds'] or any(set(stream['componenteIds']) - set(v['componenteIds']) for v in endpoints):
            reject('invalid_stream_components', 'Stream species must belong to both endpoints.', path+'.componenteIds', 'MOTOR_ENS_CATALOGO')
        if matter['modo'] not in ('total_desde_donante', 'por_componente'):
            reject('unsupported_stream', 'Select total donor or component flow.', path+'.materia', 'MOTOR_ENS_MATERIA')
            continue
        if matter['modo'] == 'por_componente' and set(matter['caudalIds']) != {str(c) for c in stream['componenteIds']}:
            reject('invalid_stream_components', 'Declare one flow for each stream component.', path+'.materia.caudalIds', 'MOTOR_ENS_CATALOGO')
        for owner, extraction in (stream.get('extraccion') or {}).items():
            valid = isinstance(extraction, dict) and (extraction == {'tipo': 'mezcla_homogenea'} or
                extraction.get('tipo') == 'fase' and extraction.get('fase') in ('liquido', 'vapor', 'fluido')
                and extraction.get('criterio') in (None, 'mayor_densidad', 'menor_densidad')
                and set(extraction) <= {'tipo', 'fase', 'criterio'})
            if owner not in (source, target) or not valid:
                reject('invalid_extraction', 'Declare a valid extraction rule on a stream endpoint.', path+'.extraccion', 'MOTOR_ENS_EXTRACCION')
        if stream['mecanismo'] != 'convectivo' or matter['base'] not in ('masica', 'molar'):
            reject('unsupported_stream', 'Only declared convective mass or molar flow is admitted.', path, 'MOTOR_ENS_SELECTIVO')
            continue
        ids = [matter['caudalId']] if matter['modo'] == 'total_desde_donante' else list(matter.get('caudalIds', {}).values())
        flows = [datum(identity, 'kg/s' if matter['base'] == 'masica' else 'mol/s', path+'.materia') for identity in ids]
        if not flows or any(flow is None for flow in flows):
            continue
        dynamic = any(flow.derivada is not None for flow in flows)
        signs = [flow(0) for flow in flows]
        if min(signs) < 0 < max(signs):
            reject('mixed_flow_signs', 'Component flow directions must agree.', path+'.materia', 'MOTOR_ENS_MATERIA')
        if matter['modo'] == 'por_componente' and len(stream['componenteIds']) > 1 and any(
                endpoint in volumes and len(volumes[endpoint]['componenteIds']) > 1 for endpoint in (source, target)):
            reject('overspecified_composition', 'The donor determines composition; select total donor flow.', path+'.materia',
                   'MOTOR_ENS_COMPOSICION_SOBREESPECIFICADA')
        donors = [source, target] if dynamic else [source] if max(signs) > 0 else [target] if min(signs) < 0 else []
        # Validate a supplied exterior state even when the current flow is zero
        # or outward. It must not hide malformed data until a later edit.
        if stream.get('estadoExterior') is not None:
            if None not in (source, target):
                reject('invalid_external_state', 'An internal stream has no exterior donor.', path+'.estadoExterior', 'MOTOR_ENS_DONANTE')
            elif None not in donors:
                donors.append(None)
        for donor in donors:
            if donor is None:
                exterior = stream.get('estadoExterior')
                if not exterior:
                    reject('missing_external_state', 'Declare the exterior donor state.', path+'.estadoExterior', 'MOTOR_ENS_DONANTE_PENDIENTE')
                    continue
                datum(exterior['temperaturaId'], 'K', path+'.estadoExterior.temperaturaId', positive=True)
                pressure = exterior.get('presion') or {}
                if pressure.get('tipo') == 'dato':
                    datum(pressure.get('datoId'), 'Pa', path+'.estadoExterior.presion', positive=True)
                elif pressure.get('tipo') == 'continuidad' and pressure.get('volumenId') in (source, target) and pressure.get('volumenId') is not None:
                    if pressure.get('restriccionAdicionalId'):
                        reject('conflicting_pressure', 'Pressure continuity cannot add another pressure datum.', path+'.estadoExterior.presion', 'MOTOR_ENS_P_DUPLICADA')
                else:
                    reject('invalid_external_state', 'Declare pressure or continuity with the attached volume.', path+'.estadoExterior.presion', 'MOTOR_ENS_DONANTE')
                recipient = volumes[target if source is None else source]
                composition = exterior.get('composicion')
                if len(recipient['componenteIds']) > 1 and not composition:
                    reject('missing_external_composition', 'Declare the exterior mixture composition.', path+'.estadoExterior', 'MOTOR_ENS_COMPOSICION_EXTERIOR')
                if composition:
                    fractions = composition.get('fracciones', {}) if isinstance(composition, dict) else {}
                    if (not isinstance(fractions, dict) or set(fractions) != {str(c) for c in stream['componenteIds']}
                            or not all(isinstance(x, (int, float)) and np.isfinite(x) and x >= 0 for x in fractions.values())
                            or not np.isclose(sum(fractions.values()), 1, rtol=0, atol=1e-10)
                            or composition.get('base') not in ('masica', 'molar')):
                        reject('invalid_composition', 'Exterior fractions must cover stream species, be finite, nonnegative and sum to one.', path+'.estadoExterior.composicion', 'MOTOR_ENS_COMPOSICION_EXTERIOR')
            elif donor in volumes and donor not in (stream.get('extraccion') or {}) and volumes[donor]['termodinamica']['politica']['cantidad'] != 'monofasico':
                reject('missing_extraction', 'Declare extraction for each possible donor.', path+'.extraccion.'+donor, 'MOTOR_ENS_EXTRACCION')

    for index, heat in enumerate(model['intercambios']):
        path = f'intercambios[{index}]'; law = heat['ley']
        if heat['desde'] == heat['hasta']:
            reject('invalid_topology', 'Heat exchange must connect distinct endpoints.', path, 'MOTOR_ENS_TOPOLOGIA')
        if law['tipo'] == 'impuesto':
            datum(law['potenciaId'], 'W', path+'.ley.potenciaId')
        else:
            datum(law['conductanciaId'], 'W/K', path+'.ley.conductanciaId', constant=True, positive=True)
            if None in (heat['desde'], heat['hasta']):
                datum(law.get('temperaturaExteriorId'), 'K', path+'.ley.temperaturaExteriorId', positive=True)
        if heat.get('temperaturaFronteraId'):
            datum(heat['temperaturaFronteraId'], 'K', path+'.temperaturaFronteraId', positive=True)
    if errors:
        raise AdmissionError('', '', '', diagnostics=errors)
    return data, closures
