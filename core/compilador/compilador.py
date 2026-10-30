"""
Compile the common model into a numerical time-dependent system.

Execute the model's structural relations (core/modelo/relaciones.py),
without branches for particular equipment, operations or substances:

  per volume v and component i:   dn_vi/dt = sum_s B_vs ndot_s x_si
  per volume v (energy):          dE_v/dt  = sum_s B_vs ndot_s h_s + sum_q B_vq Q_q  [+ V_v dP_v/dt]
      E = U for a rigid boundary (UV closure with given V)
      E = H for prescribed pressure (PH closure with given P(t))
  closure: the thermodynamic layer at each evaluation (phases are outputs)
  stream s: given flow; DONOR composition and enthalpy follow its current sign
      (volume: mixture or extracted phase; exterior: declared TP state)
  exchange q: given Q (imposed) or G (T_desde - T_hasta) (conductance)

Auxiliary integrals verify global conservation of each component and energy
exchanged with the exterior.

Data: model text (number or expression in t) with its unit, converted to SI
by the shared units service; expressions use core/expresiones_motor.

Outside this entry point's scope (NoSoportado with a reason): material sources
(reaction), volumetric flow, volumes with assumed states, and momentum.

Models with assumed volume states and authored equations (`matematico`)
use the other entry point, explicito.py.
"""

from dataclasses import dataclass

import numpy as np

from core import expresiones_motor as ex
from core import unidades as un
from core.mezclas import FueraDeAlcance
from core.modelo import leer_modelo_comun, relaciones
from core.resultados import conjunto, eje, evento, serie
from core.solvers import Detencion, integrar
from core.termodinamica import capa
from core.termodinamica.volumen import CierreVolumen


class NoSoportado(Exception):
    pass


class AdmissionError(NoSoportado):
    """Located, expected input rejection shared by compilation and Solve."""
    def __init__(self, code, message, path, *, native_code=None, diagnostics=None):
        self.diagnostics = diagnostics or [{'code': code, 'message': message, 'path': path,
                                            **({'nativeCode': native_code} if native_code else {})}]
        super().__init__('; '.join(row['message'] for row in self.diagnostics))


def temporal_method(requested):
    methods = {None: 'RK45', 'rk45': 'RK45', 'bdf': 'BDF'}
    if requested not in methods:
        message = ('Implicit Euler is not implemented by the common compiler. Select BDF explicitly; variable-order BDF is not implicit Euler.'
                   if requested == 'euler_implicito' else f'Unsupported temporal method: {requested}')
        error = NoSoportado(message)
        error.diagnostics = [{'code': 'unsupported_method', 'message': message}]
        raise error
    return methods[requested]


class _Dato:
    """A model datum as an SI function of time, with its derivative."""

    def __init__(self, d, ruta, expected_unit=None):
        self.path = ruta
        texto, unidad = d["declaracion"]["texto"], d["declaracion"]["unidad"]
        if not texto.strip():
            raise AdmissionError('missing_data', 'A numerical datum is pending.', ruta, native_code='MOTOR_ENS_DATO_PENDIENTE')
        try:
            i = un.interpretar(unidad)
        except un.ErrorUnidad as e:
            raise AdmissionError('incompatible_dimension', str(e), ruta, native_code='MOTOR_ENS_UNIDAD') from e
        if expected_unit is not None and i['dimension'] != un.interpretar(expected_unit)['dimension']:
            raise AdmissionError('incompatible_dimension',
                f'{ruta}: the consuming role requires {expected_unit}, but the declared unit is {unidad}.',
                ruta, native_code='MOTOR_ENS_UNIDAD')
        self.factor, self.desp = i["factor"], i["desplazamiento"]
        try:
            self.arbol = ex.analizar(texto, ["t"])
            self.derivada = ex.derivada(self.arbol, "t") if ex.depende_de(self.arbol, "t") else None
        except ex.ErrorExpresion as error:
            raise AdmissionError('invalid_data', str(error), ruta, native_code='MOTOR_ENS_EXPRESION') from error
        self.unidad = unidad
        self(0.0)

    def __call__(self, t):
        try:
            value = self.factor * ex.evaluar(self.arbol, {"t": t}) + self.desp
            if not np.isfinite(value):
                raise ex.ErrorExpresion('The evaluated datum is not finite.')
            return value
        except (ex.ErrorExpresion, ArithmeticError) as error:
            raise AdmissionError('invalid_data', f'{self.path} at t={t}: {error}', self.path,
                                 native_code='MOTOR_ENS_EXPRESION') from error

    def d_dt(self, t):
        try:
            value = 0.0 if self.derivada is None else self.factor * ex.evaluar(self.derivada, {"t": t})
            if not np.isfinite(value):
                raise ex.ErrorExpresion('The required datum derivative is not finite.')
            return value
        except (ex.ErrorExpresion, ArithmeticError) as error:
            raise AdmissionError('invalid_data', f'{self.path} derivative at t={t}: {error}', self.path,
                                 native_code='MOTOR_ENS_EXPRESION') from error


@dataclass
class _Vol:
    id: str
    comp: list
    rigida: bool
    dato_P: object
    dato_V: object
    cierre: CierreVolumen
    i_n: slice
    i_E: int


class SistemaCompilado:
    def __init__(self, modelo):
        self.modelo = leer_modelo_comun(modelo)
        m = self.modelo
        from .admission import validate
        self._cache_dato, closures = validate(m)
        self.relaciones = relaciones(m)
        self.datos = {k: d for k, d in m["datos"].items()}
        self.componentes = [c["id"] for c in m["componentes"]]
        self.vols, k = [], 0
        for v in m["volumenes"]:
            rigida = v["frontera"]["tipo"] == "rigida"
            nc = len(v["componenteIds"])
            self.vols.append(_Vol(v["id"], list(v["componenteIds"]), rigida,
                                  None if rigida else self.dato(v["frontera"]["presionId"]),
                                  self.dato(v["frontera"]["datoId"]) if rigida else None,
                                  closures[v['id']], slice(k, k + nc), k + nc))
            k += nc + 1
        self.n_estado = k
        self.i_aux_n = {c: k + j for j, c in enumerate(self.componentes)}
        self.i_aux_E = k + len(self.componentes)
        self.tam = self.i_aux_E + 1
        self.por_id = {v.id: v for v in self.vols}
        for s in m["corrientes"]:
            if s["mecanismo"] == "selectivo":
                raise NoSoportado(f"Stream {s['id']}: selective transfer needs a coupled material and energy law.")
            if s["materia"]["base"] == "volumetrica":
                raise NoSoportado(f"Stream {s['id']}: volumetric flow is not yet supported")
        self._ultimo_estado = {}
        from core.balances.energy_equations import lower_equilibrium_rate
        from core.modelo.operation_journal import JournalError
        self.energy_graph_terms={}
        for volume in m['volumenes']:
            # Legacy inputs remain explicitly unrecorded. A recorded model
            # always lowers its current proof; failed lowering never falls back.
            if volume['id'] in m.get('motores',{}).get('energyDerivation',{}).get('volumes',{}):
                try:self.energy_graph_terms[volume['id']]=lower_equilibrium_rate(m,volume['id'])
                except JournalError as error:raise NoSoportado(str(error)) from error
        self.politicas = {v["id"]: v["termodinamica"]["politica"] for v in m["volumenes"]}
        self.firma_inicial = None

    def admite(self, firma):
        """Each volume's phase policy is a declared assumption: a phase set
        that violates it stops the calculation and is never ignored."""
        for vid, fases in firma:
            pol = self.politicas[vid]
            tipos = [f.rsplit("-", 1)[0] for f in fases]
            if pol["cantidad"] == "monofasico" and len(fases) > 1:
                return f"Volume {vid}: the policy requires a single phase, but the state has {len(fases)} phases ({', '.join(fases)})"
            if pol["cambioInterno"] == "prohibido" and self.firma_inicial is not None and fases != dict(self.firma_inicial)[vid]:
                return f"Volume {vid}: internal phase changes are forbidden, but the phase set changes to ({', '.join(fases)})"
            tp = pol.get("tiposPermitidos")
            if tp is not None and any(x not in tp for x in tipos):
                return f"Volume {vid}: a phase appears outside the allowed types ({', '.join(tp)})"
        return None

    def dato(self, id_):
        if id_ not in self._cache_dato:
            raise AdmissionError('unbound_data_role', 'No admitted physical role for datum: '+id_, 'datos.'+id_)
        return self._cache_dato[id_]

    def stop_from_exception(self, error):
        """Only expected physical/data failures become a structured stop."""
        from core import agua_iapws95
        if isinstance(error, (FueraDeAlcance, agua_iapws95.FueraDeAlcance)):
            return Detencion(error.motivo, str(error))
        if isinstance(error, AdmissionError):
            return Detencion(error.diagnostics[0]['code'], str(error))
        if isinstance(error, Detencion):
            return error
        return None

    # --- initial state -------------------------------------------------------------
    def inicial(self):
        y = np.zeros(self.tam)
        from core import agua_iapws95, paquetes_volumen
        self.initialization = {}
        errors = []
        for index, (v, mv) in enumerate(zip(self.vols, self.modelo["volumenes"])):
            ini = mv["inicial"]
            cant = ini["cantidades"]
            M = v.cierre.M
            n = np.array([self.dato(cant["datoIds"][str(c)])(0.0) for c in v.comp])
            if cant["base"] == "masica":
                n = n / M
            y[v.i_n] = n
            en = ini["energia"]
            val = self.dato(en["datoId"])(0.0)
            try:
                def evaluate(specification, a, b, amounts):
                    if specification != 'UP':
                        return v.cierre.estado(amounts, specification, a, b, rapido=False)
                    if v.cierre.agua:
                        return paquetes_volumen.PaqueteAgua(capa._cas(self.modelo, mv)).estado(
                            'UP', a, b, amounts, certificar=True)
                    return v.cierre.sis.equilibrio_UP(a, b, amounts)
                from .initialization import initialize_state
                e = initialize_state(n, en['tipo'], val, v.rigida,
                                     v.dato_V(0.0) if v.rigida else v.dato_P(0.0), evaluate)
                y[v.i_E] = e.U if v.rigida else e.H
                phases = tuple(sorted(f.id for f in e.fases))
                reason = self.admite(((v.id, phases),))
                if reason:
                    raise FueraDeAlcance('politica_incumplida', reason)
                self.initialization[v.id] = {'status': 'compatible', 'state': e, 'amounts': n.copy()}
            except (FueraDeAlcance, agua_iapws95.FueraDeAlcance) as error:
                status = {'saturacion': 'pendiente', 'region_critica': 'no_soportada',
                          'no_soportado': 'no_soportada'}.get(error.motivo, 'incompatible')
                self.initialization[v.id] = {'status': status, 'state': None}
                errors.append({'code': 'initialization_'+error.motivo, 'message': str(error),
                               'path': f'volumenes[{index}].inicial', 'initializationStatus': status,
                               'nativeCode': 'MOTOR_ENS_INICIAL_'+error.motivo.upper()})
        if errors:
            raise AdmissionError('', '', '', diagnostics=errors)
        return y

    # --- evaluation -------------------------------------------------------------------
    def _estados(self, t, y, rapido=True):
        sal = {}
        for v in self.vols:
            n = np.maximum(y[v.i_n], 0.0)
            if not n.sum() > 0:
                raise Detencion("agotamiento", f"Volume {v.id} is empty")
            if v.rigida:
                sal[v.id] = v.cierre.estado(n, "UV", y[v.i_E], v.dato_V(t), rapido)
            else:
                sal[v.id] = v.cierre.estado(n, "PH", v.dato_P(t), y[v.i_E], rapido)
        return sal

    def firma(self, t, y):
        return tuple((vid, e.firma) for vid, e in self._estados(t, y).items())

    def event_state(self, t, y):
        """Prefer certified regimes; retry unavailable probes with RHS seeds.

        The generic solver sees only a discrete identity and scalar margins.
        Appearance uses the package's existing candidate stability margin;
        disappearance uses the smallest present phase fraction. Event probes
        restore the numerical closures' seeds rather than altering integration.
        A cold closure can fail near a phase boundary despite a valid seeded
        state. Its failure alone is neither a physical stop nor a phase event.
        """
        seeds = [volume.cierre.semilla for volume in self.vols]
        try:
            try:
                states = self._estados(t, y, rapido=False)
            except FueraDeAlcance:
                # Earlier volumes in the failed probe may have changed seeds.
                # Retry from the integration context, not that partial probe.
                for volume, seed in zip(self.vols, seeds):
                    volume.cierre.semilla = seed
                states = self._estados(t, y, rapido=True)
            margins = []
            for state in states.values():
                stability = getattr(state.nativo, 'estabilidad', None)
                appearance = stability.get('tm_nueva') if isinstance(stability, dict) else None
                margins.append(float(appearance) if appearance is not None and np.isfinite(appearance) and appearance > 0 else None)
                amounts = [phase.n for phase in state.fases]
                margins.append(min(amounts)/sum(amounts) if len(amounts) > 1 else None)
            self._event_context = (t, states)
            return tuple((owner, state.firma) for owner, state in states.items()), tuple(margins)
        finally:
            for volume, seed in zip(self.vols, seeds):
                volume.cierre.semilla = seed

    def _donante_volumen(self, s, v, e):
        """(x, h, M) of the material leaving a volume: mixture or a single phase."""
        ext = (s.get("extraccion") or {}).get(v.id)
        if ext is None:
            # Under an explicit monophase policy, the sole phase is the whole
            # mixture. Multiphase extraction is never inferred from a default.
            if self.politicas[v.id]['cantidad'] != 'monofasico':
                raise AdmissionError('missing_extraction', 'Declare extraction for the actual donor.',
                                     f'corrientes.{s["id"]}.extraccion.{v.id}', native_code='MOTOR_ENS_EXTRACCION')
            ext = {'tipo': 'mezcla_homogenea'}
        if ext["tipo"] == "mezcla_homogenea":
            nt = sum(f.n for f in e.fases)
            x = sum(f.n * f.x for f in e.fases) / nt
            return x, e.H / nt, float(np.dot(x, v.cierre.M))
        fases = [f for f in e.fases if f.tipo == ext["fase"]]
        if not fases:
            raise Detencion("fase_ausente", f"Stream {s['id']} extracts {ext['fase']} from volume {v.id}, where that phase is absent")
        if len(fases) > 1:
            crit = ext.get("criterio")
            if crit is None:
                raise Detencion("fase_ambigua", f"Stream {s['id']}: there are {len(fases)} phases of type {ext['fase']}; declare a selection criterion")
            fases.sort(key=lambda f: f.M / f.v, reverse=(crit == "mayor_densidad"))
        f = fases[0]
        return f.x, f.h, f.M

    def _donante_exterior(self, s, t, receptor):
        ee = s.get("estadoExterior")
        if not ee:
            raise NoSoportado(f"Stream {s['id']}: external inflow has no declared exterior state")
        T = self.dato(ee["temperaturaId"])(t)
        pres = ee["presion"]
        P = self.dato(pres["datoId"])(t) if pres["tipo"] == "dato" else self._ultimo_estado[pres["volumenId"]].P
        comp = ee.get("composicion") or {"base": "molar", "fracciones": {str(receptor.comp[0]): 1.0}}
        w = np.array([float(comp["fracciones"].get(str(c), 0.0)) for c in receptor.comp])
        x = w / receptor.cierre.M if comp["base"] == "masica" else w
        x = x / x.sum()
        e = receptor.cierre.estado(x, "TP", T, P, rapido=False)
        return x, e.H, float(np.dot(x, receptor.cierre.M))

    def rhs(self, t, y):
        est = self._estados(t, y)
        self._ultimo_estado = est
        dy = np.zeros(self.tam)
        stream_powers={};heat_powers={v.id:0.0 for v in self.vols}
        for s in self.modelo["corrientes"]:
            mat = s["materia"]
            de, ha = (self.por_id.get(s["desde"]), self.por_id.get(s["hasta"]))
            if mat["modo"] == "total_desde_donante":
                F = self.dato(mat["caudalId"])(t)
                donante = de if F >= 0 else ha
                if donante is not None:
                    x, h, M = self._donante_volumen(s, donante, est[donante.id])
                else:
                    x, h, M = self._donante_exterior(s, t, ha if F >= 0 else de)
                ndot = abs(F) / M if mat["base"] == "masica" else abs(F)
                comp_ids = (donante or (ha if F >= 0 else de)).comp
                origen, destino = (de, ha) if F >= 0 else (ha, de)
            else:
                ref = de or ha
                Fi = np.array([self.dato(mat["caudalIds"][str(c)])(t) if str(c) in mat["caudalIds"] else 0.0 for c in ref.comp])
                ni = Fi / ref.cierre.M if mat["base"] == "masica" else Fi
                if np.any(ni > 0) and np.any(ni < 0):
                    raise NoSoportado(f"Stream {s['id']}: component flows have opposite signs")
                sentido = 1.0 if ni.sum() >= 0 else -1.0
                origen, destino = (de, ha) if sentido > 0 else (ha, de)
                ndot = float(abs(ni.sum()))
                x = np.abs(ni) / ndot if ndot > 0 else np.zeros(len(ni))
                if origen is not None:
                    if len(origen.comp) > 1:
                        raise NoSoportado(f"Stream {s['id']}: component flows from a multispecies volume overspecify the composition")
                    _, h, _ = self._donante_volumen(s, origen, est[origen.id])
                else:
                    _, h, _ = self._donante_exterior(s, t, destino) if ndot > 0 else (None, 0.0, None)
                comp_ids = ref.comp
            orientation=1.0 if (origen.id if origen else None)==s['desde'] else -1.0
            stream_powers[s['id']]=orientation*ndot*h
            for v, sg in ((origen, -1.0), (destino, 1.0)):
                if v is None:
                    for j, c in enumerate(comp_ids):
                        dy[self.i_aux_n[c]] -= sg * ndot * x[j]
                    dy[self.i_aux_E] -= sg * ndot * h
                    continue
                pos = {c: k for k, c in enumerate(v.comp)}
                for j, c in enumerate(comp_ids):
                    dy[v.i_n.start + pos[c]] += sg * ndot * x[j]
                dy[v.i_E] += sg * ndot * h
        for q in self.modelo["intercambios"]:
            de, ha = self.por_id.get(q["desde"]), self.por_id.get(q["hasta"])
            ley = q["ley"]
            if ley["tipo"] == "impuesto":
                Q = self.dato(ley["potenciaId"])(t)
            else:
                Text = self.dato(ley["temperaturaExteriorId"])(t) if ley.get("temperaturaExteriorId") else None
                Td = est[de.id].T if de else Text
                Th = est[ha.id].T if ha else Text
                Q = self.dato(ley["conductanciaId"])(t) * (Td - Th)
            for v, sg in ((de, -1.0), (ha, 1.0)):
                if v is None:
                    dy[self.i_aux_E] -= sg * Q
                else:
                    dy[v.i_E] += sg * Q
                    heat_powers[v.id]+=sg*Q
        for v in self.vols:
            if not v.rigida:
                w = est[v.id].V * v.dato_P.d_dt(t)
                dy[v.i_E] += w
                dy[self.i_aux_E] += w
        for v in self.vols:
            if v.id in self.energy_graph_terms:
                values={'stream':stream_powers,'heat':heat_powers,
                        'pressure':{v.id:0.0 if v.rigida else est[v.id].V*v.dato_P.d_dt(t)}}
                dy[v.i_E]=sum(factor*values[kind][key] for kind,key,factor in self.energy_graph_terms[v.id])
        return dy


def compilar(modelo):
    if modelo.get('motores', {}).get('derivedExecution', {}).get('version') == 5:
        from .steady import SteadySystem
        return SteadySystem(modelo)
    if modelo.get('motores', {}).get('derivedExecution') is not None:
        from .derived import DerivedSystem
        return DerivedSystem(modelo)
    _check_inventory_execution(modelo)
    if modelo.get('motores',{}).get('hydraulicNetwork') is not None:
        from .hydraulics import HydraulicSystem
        return HydraulicSystem(modelo)
    return SistemaCompilado(modelo)


def _check_inventory_execution(modelo):
    from core.modelo.dynamic_definition import ensure_executable
    from core.balances.momentum_derivation import ensure_executable as ensure_momentum
    from core.modelo.equation_workbench import ensure_executable as ensure_equations
    try:
        ensure_executable(leer_modelo_comun(modelo))
        ensure_momentum(modelo)
        ensure_equations(modelo)
    except ValueError as error:
        raise NoSoportado(str(error)) from error


def resolver(modelo):
    """Common model -> result set in the common format (core/resultados).

    Two entry points: structural (volumes with equilibrium closures, this
    file) and explicit equations (`matematico`, explicito.py)."""
    from .explicito import es_explicito, resolver_explicito
    from .transformed import selected_execution, resolve_transformed
    if modelo.get('motores', {}).get('derivedExecution', {}).get('version') == 5:
        from .steady import resolve
        return resolve(modelo)
    if modelo.get('motores', {}).get('derivedExecution') is not None:
        from .derived import resolve
        return resolve(modelo)
    _check_inventory_execution(modelo)
    if modelo.get('motores',{}).get('hydraulicNetwork') is not None:
        from .hydraulics import resolve
        return resolve(modelo)
    if selected_execution(leer_modelo_comun(modelo)) is not None:
        return resolve_transformed(modelo)
    if es_explicito(leer_modelo_comun(modelo)):
        return resolver_explicito(modelo)
    sis = compilar(modelo)
    est = modelo["estudio"]
    if est is None or est["tipo"] != "temporal":
        raise NoSoportado("The model does not request a time-dependent study")
    requested = est.get("metodoSolicitado")
    sis.metodo = temporal_method(requested)
    tf = sis.dato(est["tiempoId"])(0.0)
    muestras = int(est["muestras"])
    y0 = sis.inicial()
    try:
        sis.firma_inicial = sis.event_state(0.0, y0)[0]
    except Exception as error:
        stop = sis.stop_from_exception(error)
        if stop is None:
            raise
        raise AdmissionError('initialization_'+stop.codigo, stop.mensaje, 'volumenes',
                             native_code='MOTOR_ENS_INICIAL_'+stop.codigo.upper()) from error
    motivo = sis.admite(sis.firma_inicial)
    if motivo:
        raise NoSoportado(f"The initial state violates the phase policy: {motivo}")
    from .network_results import execute
    return execute(sis, y0, tf, muestras)


def _publicar(sis, ts, filas, tray, y0, certified=None):
    m = sis.modelo
    series = []
    datos = {}
    for v in sis.vols:
        p = f"volumen.{v.id}"
        cert = certified[v.id] if certified is not None else []
        if certified is None:
            for t, y in zip(ts, filas):
                n = {c: float(y[v.i_n][k]) for k, c in enumerate(v.comp)}
                espec = ("UV", float(y[v.i_E]), v.dato_V(t)) if v.rigida else ("PH", v.dato_P(t), float(y[v.i_E]))
                cert.append(capa.cierre(m, v.id, n, espec))
        for k, c in enumerate(v.comp):
            series.append(serie(f"{p}.n.{c}", f"n {c}", "mol", ["t"], [float(y[v.i_n][k]) for y in filas], propietarioId=f"volumen:{v.id}", componenteId=c))
        for clave, unidad in (("T", "K"), ("P", "Pa"), ("V", "m^3"), ("H", "J"), ("U", "J")):
            series.append(serie(f"{p}.{clave}", clave, unidad, ["t"], [e[clave] for e in cert], propietarioId=f"volumen:{v.id}"))
        # All candidate phases, present or absent, at each sample.
        for j, k in enumerate(v.cierre.candidatas):
            series.append(serie(f"{p}.fase.{k}.beta", f"beta {k}", "1", ["t"], [e["fases"][j]["beta"] for e in cert], propietarioId=f"volumen:{v.id}", faseId=k))
            series.append(serie(f"{p}.fase.{k}.tm", f"tm {k}", "1", ["t"], [e["fases"][j]["tm"] for e in cert], propietarioId=f"volumen:{v.id}", faseId=k))
            for c in v.comp:
                series.append(serie(f"{p}.fase.{k}.x.{c}", f"x {c} in {k}", "1", ["t"],
                                    [(e["fases"][j].get("composicion") or e["fases"][j].get("composicionIncipiente") or {}).get(c) for e in cert],
                                    propietarioId=f"volumen:{v.id}", faseId=k, componenteId=c))
        datos[v.id] = cert
    # Global conservation using the auxiliary integrals.
    resid_n, resid_E = 0.0, 0.0
    for t, y in zip(ts, filas):
        for c in sis.componentes:
            tot = sum(y[v.i_n][v.comp.index(c)] for v in sis.vols if c in v.comp)
            tot0 = sum(y0[v.i_n][v.comp.index(c)] for v in sis.vols if c in v.comp)
            resid_n = max(resid_n, abs(tot - tot0 - y[sis.i_aux_n[c]]) / max(abs(tot0), 1e-300))
        E = sum(y[v.i_E] for v in sis.vols)
        E0 = sum(y0[v.i_E] for v in sis.vols)
        resid_E = max(resid_E, abs(E - E0 - y[sis.i_aux_E]) / max(abs(E0), abs(E), 1.0))
    eventos = []
    for codigo, t, antes, despues, msg in tray.eventos:
        if codigo == "cambio_firma":
            for (vid, fa), (_, fd) in zip(antes, despues):
                for f in sorted(set(fd) - set(fa)):
                    eventos.append(evento("aparicion_fase", "t", t, f"{f} appears", f"volumen:{vid}"))
                for f in sorted(set(fa) - set(fd)):
                    eventos.append(evento("desaparicion_fase", "t", t, f"{f} disappears", f"volumen:{vid}"))
        else:
            eventos.append(evento(codigo, "t", t, msg))
    estado = "parcial" if tray.detenida else "resuelto"
    verif = [{"id": "conservacion.materia", "valor": resid_n, "tolerancia": 1e-9, "descripcion": "max |sum n - n0 - external exchange| / n0 per component"},
             {"id": "conservacion.energia", "valor": resid_E, "tolerancia": 1e-9, "descripcion": "max |sum E - E0 - external exchange| / |E|"},
             {"id": "complementariedad", "valor": max(e["complementariedad"] for cert in datos.values() for e in cert), "tolerancia": 1e-8,
              "descripcion": "max |beta tm|, -beta, -tm over the samples"}]
    provenance = {}
    if any(m.get("motores", {}).get(key) for key in ("materialDerivation", "energyDerivation", "thermodynamicDerivation")):
        from .report import compilation_report
        provenance["compilation"] = compilation_report(m)
    return conjunto(m["id"], m["nombre"], estado,
                    {"motor": "rage.compilador", "metodo": f"{sis.metodo} with signature events (core/solvers)", "firma": None,
                     **provenance,
                     **({"mensaje": tray.detenida.mensaje} if tray.detenida else {})},
                    [eje("t", "Time", "tiempo", "s", ts)], series, eventos, verif, modeloId=m["id"])
