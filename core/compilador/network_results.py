"""Compatibility-neutral publication bridge; integration stays on common RK45/BDF.

Reuse the existing network's auxiliary accounting and publication operations.
No call to validar_v2, resolver_v2 or ensamblaje_red.integrar is allowed here.
"""
import copy
from types import SimpleNamespace
import numpy as np
from core import ensamblaje_red as network, paquetes_volumen as packages
from core import mezclas, agua_iapws95, catalogo
from core.dynamic_common import Detencion as NetworkStop
from core.solvers import integrar, Detencion
from core.termodinamica import capa
from core.resultados import conjunto
from core.resultados.adaptadores import desde_ensamblaje_v2


class BoundaryFunction:
    def __init__(self, datum):
        self.datum = datum
    def __call__(self, t):
        return self.datum(t)
    def derivada(self, t):
        return self.datum.d_dt(t)


class NetworkExecution:
    def __init__(self, compiled, initial, final_time, samples):
        self.compiled = compiled
        model = compiled.modelo
        self.ids = list(compiled.componentes)
        global_index = {identity: k for k, identity in enumerate(self.ids)}
        owners = {v.id: k for k, v in enumerate(compiled.vols)}
        self.packages = []
        volumes, native_volumes = [], []
        masses = np.zeros(len(self.ids))
        initialization = {}
        for v, source in zip(compiled.vols, model['volumenes']):
            _, declaration = capa._volumen(model, v.id)
            cas = capa._cas(model, source)
            substitutions = (catalogo.leer_sustituciones(declaration['datosPuros'], 'datosPuros', set(cas))
                             if declaration.get('datosPuros') else None)
            package = (packages.PaqueteAgua(cas) if v.cierre.agua else
                       packages.PaqueteMezcla(declaration['modelo']['id'], cas, substitutions))
            self.packages.append(package)
            n = initial[v.i_n].copy()
            state = compiled.initialization[v.id]['state']
            volumes.append(network.VolumenSI(v.id, package, [global_index[c] for c in v.comp],
                'rigida' if v.rigida else 'presion', v.dato_V(0) if v.rigida else None,
                None if v.rigida else BoundaryFunction(v.dato_P), compiled.politicas[v.id], n,
                initial[v.i_E], state.T))
            masses[[global_index[c] for c in v.comp]] = package.M
            native_volumes.append({'id': v.id, 'paq': package, 'comp': v.comp})
            initialization[v.id] = {'U': state.U, 'estado': self.native_state(state, package, n)}
        streams = []
        for source in model['corrientes']:
            matter = source['materia']; exterior = source.get('estadoExterior') or {}
            pressure = exterior.get('presion') or {}
            composition = exterior.get('composicion')
            fractions = None
            if exterior:
                fractions = np.zeros(len(self.ids))
                if composition:
                    for identity, value in composition['fracciones'].items():
                        fractions[global_index[int(identity)]] = value
                    if composition['base'] == 'masica':
                        fractions /= np.where(masses > 0, masses, 1)
                else:
                    fractions[global_index[source['componenteIds'][0]]] = 1
                fractions /= fractions.sum()
            extraction = {owners[owner]: (rule['tipo'], rule.get('fase'), rule.get('criterio'))
                          for owner, rule in (source.get('extraccion') or {}).items()}
            streams.append(network.CorrienteRed(
                source['id'], owners.get(source['desde']), owners.get(source['hasta']),
                [global_index[c] for c in source['componenteIds']],
                'total' if matter['modo'] == 'total_desde_donante' else 'por_componente', matter['base'],
                compiled.dato(matter['caudalId']) if matter['modo'] == 'total_desde_donante' else None,
                {global_index[int(c)]: compiled.dato(identity) for c, identity in matter.get('caudalIds', {}).items()} or None,
                compiled.dato(exterior['temperaturaId']) if exterior else None,
                compiled.dato(pressure['datoId']) if pressure.get('tipo') == 'dato' else None,
                owners.get(pressure.get('volumenId')), fractions, extraction))
        heat = []
        for source in model['intercambios']:
            law = source['ley']
            heat.append(network.IntercambioRed(source['id'], owners.get(source['desde']), owners.get(source['hasta']), law['tipo'],
                compiled.dato(law['potenciaId']) if law['tipo'] == 'impuesto' else None,
                compiled.dato(law['conductanciaId'])(0) if law['tipo'] == 'conductancia' else None,
                compiled.dato(law['temperaturaExteriorId']) if law.get('temperaturaExteriorId') else None,
                compiled.dato(source['temperaturaFronteraId']) if source.get('temperaturaFronteraId') else None))
        study = model['estudio']
        self.red = network.Red(volumes, streams, heat, masses, final_time, samples, study['rtol'],
                               study['atol']['cantidad'], study['atol'].get('energia', 1e-6))
        self.accounting = network.Sistema(self.red)
        self.accounting.firmas_tramo = [network.firma(initialization[v.id]['estado']) for v in volumes]
        self.context = {'vols': native_volumes, 'comps': self.ids, 'est': study, 'ini': initialization}
        self.initial = np.zeros(self.accounting.n_total)
        self.initial[:compiled.n_estado] = initial[:compiled.n_estado]

    @staticmethod
    def native_state(state, package, amounts):
        if isinstance(package, packages.PaqueteAgua):
            # UP initialization already returns the package's native state.
            if isinstance(state, mezclas.EstadoMezcla):
                return copy.deepcopy(state)
            return package._envolver(state.nativo, float(sum(amounts)), 'PH')
        return copy.deepcopy(getattr(state, 'nativo', state))

    def rhs(self, t, y):
        # Existing shared science supplies work and entropy integrals. Keep the
        # compiled physical equations, including lowered energy-journal terms.
        try:
            rates = self.accounting(t, y)
            physical = self.compiled.rhs(t, y[:self.compiled.tam])
        except Exception as error:
            stop = self.stop_from_exception(error)
            if stop is None:
                raise
            raise stop from error
        rates[:self.compiled.n_estado] = physical[:self.compiled.n_estado]
        return rates

    def event_state(self, t, y):
        return self.compiled.event_state(t, y)

    def capture_event_context(self, t, y):
        probe_time, states = self.compiled._event_context
        if probe_time != t:
            raise ValueError('The event context must belong to the accepted event probe.')
        result = [self.native_state(states[v.id], package, y[v.i_n])
                  for v, package in zip(self.compiled.vols, self.packages)]
        self.accounting.firmas_tramo = [network.firma(state) for state in result]
        return result

    def admite(self, signature):
        return self.compiled.admite(signature)

    def stop_from_exception(self, error):
        if isinstance(error, NetworkStop):
            return Detencion(error.codigo, error.mensaje)
        return self.compiled.stop_from_exception(error)


def execute(compiled, initial, final_time, samples):
    from .compilador import _publicar, AdmissionError
    from backend.assembly_results import publish
    execution = NetworkExecution(compiled, initial, final_time, samples)
    accounting = execution.accounting
    atol = np.full(accounting.n_total, execution.red.atol_n)
    for v in compiled.vols:
        atol[v.i_E] = execution.red.atol_E
    # Preserve the native absolute tolerances, including entropy auxiliaries.
    atol[accounting.i_E:] = execution.red.atol_E
    trajectory = integrar(execution, execution.initial, final_time, rtol=execution.red.rtol, atol=atol,
                         max_step=final_time/(samples-1), metodo=compiled.metodo)
    events = []
    owners = {v.id: k for k, v in enumerate(compiled.vols)}
    phase_signatures = {v.id: network.firma(execution.context['ini'][v.id]['estado']) for v in compiled.vols}
    for code, t, before, after, message in trajectory.eventos:
        if code == 'cambio_firma':
            for (owner, a), (_, b) in zip(before, after):
                if a != b:
                    # Candidate IDs can represent several physical denominations
                    # (water's gaseous candidate includes supercritical fluid).
                    # Classify the typed event-side states with the shared rule.
                    current = network.firma(trajectory.event_contexts[t][owners[owner]])
                    events.append((network.clasificar_evento(phase_signatures[owner], current), t, owners[owner], message))
                    phase_signatures[owner] = current
        else:
            events.append((code, t, None, message))
    stopped = trajectory.detenida
    native_stop = NetworkStop(stopped.codigo, stopped.mensaje, trajectory.t_fin) if stopped else None
    native_trajectory = SimpleNamespace(t_fin=trajectory.t_fin, y=trajectory.y, detenida=native_stop, eventos=events,
        phase_event_states=trajectory.event_contexts, pasos=trajectory.pasos, reintentos=trajectory.rechazos)
    validation = {'solicitudId': compiled.modelo['id'], 'modeloId': compiled.modelo['id'],
                  'diagnosticos': [], 'variables': []}
    certificates = {}
    def capture(t, y, states):
        current = {}
        try:
            for v in compiled.vols:
                n = {c: float(y[v.i_n][k]) for k, c in enumerate(v.comp)}
                spec = ('UV', float(y[v.i_E]), v.dato_V(t)) if v.rigida else ('PH', v.dato_P(t), float(y[v.i_E]))
                current[v.id] = capa.cierre(compiled.modelo, v.id, n, spec)
        except capa.NoSoportado as error:
            raise mezclas.FueraDeAlcance('no_convergente', str(error)) from error
        certificates[t] = current
    response = publish(execution.context, validation, execution.red, accounting, native_trajectory,
                       capture_sample=capture, method=compiled.metodo,
                       expected_failures=(AdmissionError, Detencion, agua_iapws95.FueraDeAlcance))
    details = response['resultados']
    if not details:
        return conjunto(compiled.modelo['id'], compiled.modelo['nombre'], 'fallido',
            {'motor': 'rage.compilador', 'metodo': compiled.metodo, 'firma': None,
             'diagnostics': validation['diagnosticos'], 'physicalCertification': None}, [], [], modeloId=compiled.modelo['id'])
    times = details['tiempos']
    rows = []
    for t in times:
        extended = trajectory.y(t)
        row = extended[:compiled.tam].copy()
        # Legacy common conservation uses sum(U/H); the network ledger uses U.
        row[compiled.i_aux_E] += sum(extended[accounting.i_VdP:accounting.i_S])
        rows.append(row)
    published_trajectory = copy.copy(trajectory)
    if response['estado'] == 'parcial' and published_trajectory.detenida is None:
        published_trajectory.detenida = Detencion('muestra_no_certificada', 'Publication stopped before an uncertified sample.')
    published_trajectory.eventos = [event for event in trajectory.eventos if event[1] <= times[-1]]
    result = _publicar(compiled, times, rows, published_trajectory, initial,
                      certified={v.id: [certificates[t][v.id] for t in times] for v in compiled.vols})
    adapted = desde_ensamblaje_v2(response)
    catalog = {row['variableId']: row for row in details['catalogoSeries']}
    for series in adapted['series']:
        series['propietarioId'] = catalog[series['id']]['propietarioId']
    shared = {s['id']: s for s in adapted['series']}
    result['series'] = [{**s, **{k: v for k, v in shared.pop(s['id']).items() if v is not None}}
                        if s['id'] in shared else s for s in result['series']]
    result['series'].extend(shared.values())
    result['eventos'] = [e for e in adapted['eventos'] if e['valor'] <= times[-1]]
    result['verificaciones'].extend(adapted['verificaciones'])
    result['procedencia'].update(physicalCertification=details['certificacion'],
        equilibrium=details, diagnostics=validation['diagnosticos'])
    return result
