"""
Compilador del modelo común a un sistema numérico temporal.

Ejecuta las relaciones estructurales del modelo (core/modelo/relaciones.py),
sin ramas por equipo, operación ni sustancia:

  por volumen v y componente i:   dn_vi/dt = sum_s B_vs ndot_s x_si
  por volumen v (energía):        dE_v/dt  = sum_s B_vs ndot_s h_s + sum_q B_vq Q_q  [+ V_v dP_v/dt]
      E = U con frontera rígida (cierre UV con V dato)
      E = H con presión prescrita (cierre PH con P(t) dato)
  cierre: el de la capa termodinámica, en cada evaluación (fases como resultado)
  corriente s: caudal dato; composición y entalpía del DONANTE según el signo
      actual del caudal (volumen: mezcla o fase extraída; exterior: estado TP declarado)
  intercambio q: Q dato (impuesto) o G (T_desde - T_hasta) (conductancia)

Integrales auxiliares para verificar la conservación global: materia por
componente y energía intercambiadas con el exterior.

Datos: textos del modelo (número o expresión en t) con su unidad, pasados a SI
por el servicio único de unidades; expresiones con core/expresiones_motor.

Fuera de esta versión (NoSoportado con motivo): fuentes materiales
(reacción), caudal volumétrico, volúmenes con estado supuesto, momento.
"""

from dataclasses import dataclass

import numpy as np

from core import expresiones_motor as ex
from core import unidades as un
from core.modelo import leer_modelo_comun, relaciones
from core.resultados import conjunto, eje, evento, serie
from core.solvers import Detencion, integrar
from core.termodinamica import capa
from core.termodinamica.volumen import CierreVolumen


class NoSoportado(Exception):
    pass


class _Dato:
    """Un dato del modelo como función del tiempo en SI, con su derivada."""

    def __init__(self, d, ruta):
        texto, unidad = d["declaracion"]["texto"], d["declaracion"]["unidad"]
        if not texto.strip():
            raise NoSoportado(f"{ruta}: dato pendiente")
        try:
            i = un.interpretar(unidad)
        except un.ErrorUnidad as e:
            raise NoSoportado(f"{ruta}: {e}") from e
        self.factor, self.desp = i["factor"], i["desplazamiento"]
        self.arbol = ex.analizar(texto, ["t"])
        self.derivada = ex.derivada(self.arbol, "t") if ex.depende_de(self.arbol, "t") else None
        self.unidad = unidad

    def __call__(self, t):
        return self.factor * ex.evaluar(self.arbol, {"t": t}) + self.desp

    def d_dt(self, t):
        return 0.0 if self.derivada is None else self.factor * ex.evaluar(self.derivada, {"t": t})


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
        self.relaciones = relaciones(m)
        self.datos = {k: d for k, d in m["datos"].items()}
        self._cache_dato = {}
        self.componentes = [c["id"] for c in m["componentes"]]
        self.vols, k = [], 0
        for v in m["volumenes"]:
            if v["termodinamica"]["tipo"] != "equilibrio":
                raise NoSoportado(f"volumen {v['id']}: su estado es un supuesto ({v['termodinamica']['supuesto']}); el compilador necesita el cierre de equilibrio")
            campo = v["supuestos"]["materia"].get("campo", {})
            if not (campo.get("sinReaccion") or (campo.get("sinGeneracion") and campo.get("sinConsumo"))):
                raise NoSoportado(f"volumen {v['id']}: fuentes materiales (reacción): pendientes del motor de constitutivas")
            if not (v["balances"]["materia"] and v["balances"]["energia"]) or v["balances"]["momento"]:
                raise NoSoportado(f"volumen {v['id']}: esta versión ejecuta materia + energía, sin momento")
            rigida = v["frontera"]["tipo"] == "rigida"
            nc = len(v["componenteIds"])
            self.vols.append(_Vol(v["id"], list(v["componenteIds"]), rigida,
                                  None if rigida else self.dato(v["frontera"]["presionId"]),
                                  self.dato(v["frontera"]["datoId"]) if rigida else None,
                                  CierreVolumen(m, v["id"]), slice(k, k + nc), k + nc))
            k += nc + 1
        self.n_estado = k
        self.i_aux_n = {c: k + j for j, c in enumerate(self.componentes)}
        self.i_aux_E = k + len(self.componentes)
        self.tam = self.i_aux_E + 1
        self.por_id = {v.id: v for v in self.vols}
        for s in m["corrientes"]:
            if s["materia"]["base"] == "volumetrica":
                raise NoSoportado(f"corriente {s['id']}: caudal volumétrico: pendiente")
        self._ultimo_estado = {}

    def dato(self, id_):
        if id_ not in self._cache_dato:
            self._cache_dato[id_] = _Dato(self.datos[id_], f"datos.{id_}")
        return self._cache_dato[id_]

    # --- estado inicial -------------------------------------------------------------
    def inicial(self):
        y = np.zeros(self.tam)
        for v, mv in zip(self.vols, self.modelo["volumenes"]):
            ini = mv["inicial"]
            cant = ini["cantidades"]
            M = v.cierre.M
            n = np.array([self.dato(cant["datoIds"][str(c)])(0.0) for c in v.comp])
            if cant["base"] == "masica":
                n = n / M
            y[v.i_n] = n
            en = ini["energia"]
            val = self.dato(en["datoId"])(0.0)
            if en["tipo"] == "T":
                e = v.cierre.estado(n, "TV", val, v.dato_V(0.0), rapido=False) if v.rigida else v.cierre.estado(n, "TP", val, v.dato_P(0.0), rapido=False)
                y[v.i_E] = e.U if v.rigida else e.H
            elif v.rigida:
                y[v.i_E] = val
            else:
                raise NoSoportado(f"volumen {v.id}: U inicial con presión prescrita: pendiente (declara T inicial)")
        return y

    # --- evaluación -------------------------------------------------------------------
    def _estados(self, t, y, rapido=True):
        sal = {}
        for v in self.vols:
            n = np.maximum(y[v.i_n], 0.0)
            if not n.sum() > 0:
                raise Detencion("agotamiento", f"el volumen {v.id} se ha vaciado")
            if v.rigida:
                sal[v.id] = v.cierre.estado(n, "UV", y[v.i_E], v.dato_V(t), rapido)
            else:
                sal[v.id] = v.cierre.estado(n, "PH", v.dato_P(t), y[v.i_E], rapido)
        return sal

    def firma(self, t, y):
        return tuple((vid, e.firma) for vid, e in self._estados(t, y).items())

    def _donante_volumen(self, s, v, e):
        """(x, h, M) de lo que sale de un volumen: mezcla o una fase."""
        ext = (s.get("extraccion") or {}).get(v.id, {"tipo": "mezcla_homogenea"})
        if ext["tipo"] == "mezcla_homogenea":
            nt = sum(f.n for f in e.fases)
            x = sum(f.n * f.x for f in e.fases) / nt
            return x, e.H / nt, float(np.dot(x, v.cierre.M))
        fases = [f for f in e.fases if f.tipo == ext["fase"]]
        if not fases:
            raise Detencion("fase_ausente", f"la corriente {s['id']} extrae {ext['fase']} del volumen {v.id}, que no la tiene")
        if len(fases) > 1:
            crit = ext.get("criterio")
            if crit is None:
                raise Detencion("fase_ambigua", f"la corriente {s['id']}: hay {len(fases)} fases {ext['fase']}; declara un criterio")
            fases.sort(key=lambda f: f.M / f.v, reverse=(crit == "mayor_densidad"))
        f = fases[0]
        return f.x, f.h, f.M

    def _donante_exterior(self, s, t, receptor):
        ee = s.get("estadoExterior")
        if not ee:
            raise NoSoportado(f"corriente {s['id']}: entra del exterior sin estado exterior declarado")
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
                    raise NoSoportado(f"corriente {s['id']}: caudales por componente con signos opuestos")
                sentido = 1.0 if ni.sum() >= 0 else -1.0
                origen, destino = (de, ha) if sentido > 0 else (ha, de)
                ndot = float(abs(ni.sum()))
                x = np.abs(ni) / ndot if ndot > 0 else np.zeros(len(ni))
                if origen is not None:
                    if len(origen.comp) > 1:
                        raise NoSoportado(f"corriente {s['id']}: caudales por componente desde un volumen de varias especies sobreespecifican la composición")
                    _, h, _ = self._donante_volumen(s, origen, est[origen.id])
                else:
                    _, h, _ = self._donante_exterior(s, t, destino) if ndot > 0 else (None, 0.0, None)
                comp_ids = ref.comp
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
        for v in self.vols:
            if not v.rigida:
                w = est[v.id].V * v.dato_P.d_dt(t)
                dy[v.i_E] += w
                dy[self.i_aux_E] += w
        return dy


def compilar(modelo):
    return SistemaCompilado(modelo)


def resolver(modelo):
    """Modelo común -> conjunto de resultados en el formato común (core/resultados)."""
    sis = compilar(modelo)
    est = modelo["estudio"]
    if est is None or est["tipo"] != "temporal":
        raise NoSoportado("el modelo no pide un estudio temporal")
    tf = sis.dato(est["tiempoId"])(0.0)
    muestras = int(est["muestras"])
    y0 = sis.inicial()
    atol = np.full(sis.tam, est["atol"]["cantidad"])
    for v in sis.vols:
        atol[v.i_E] = est["atol"].get("energia", 1e-6)
    atol[sis.i_aux_E] = est["atol"].get("energia", 1e-6)
    tray = integrar(sis, y0, tf, rtol=est["rtol"], atol=atol, max_step=tf / (muestras - 1))
    t_fin = tray.t_fin
    ts = [x for x in np.linspace(0.0, tf, muestras) if x <= t_fin * (1 + 1e-12)]
    ts = sorted(set(ts) | {e[1] for e in tray.eventos if e[1] <= t_fin} | {t_fin})
    filas = [tray.y(t) for t in ts]
    return _publicar(sis, ts, filas, tray, y0)


def _publicar(sis, ts, filas, tray, y0):
    m = sis.modelo
    series = []
    datos = {}
    for v in sis.vols:
        p = f"volumen.{v.id}"
        cert = []
        for t, y in zip(ts, filas):
            n = {c: float(y[v.i_n][k]) for k, c in enumerate(v.comp)}
            espec = ("UV", float(y[v.i_E]), v.dato_V(t)) if v.rigida else ("PH", v.dato_P(t), float(y[v.i_E]))
            cert.append(capa.cierre(m, v.id, n, espec))
        for k, c in enumerate(v.comp):
            series.append(serie(f"{p}.n.{c}", f"n {c}", "mol", ["t"], [float(y[v.i_n][k]) for y in filas], propietarioId=f"volumen:{v.id}", componenteId=c))
        for clave, unidad in (("T", "K"), ("P", "Pa"), ("V", "m^3"), ("H", "J"), ("U", "J")):
            series.append(serie(f"{p}.{clave}", clave, unidad, ["t"], [e[clave] for e in cert], propietarioId=f"volumen:{v.id}"))
        # Todas las fases candidatas, presentes o no, en cada muestra.
        for j, k in enumerate(v.cierre.candidatas):
            series.append(serie(f"{p}.fase.{k}.beta", f"beta {k}", "1", ["t"], [e["fases"][j]["beta"] for e in cert], propietarioId=f"volumen:{v.id}", faseId=k))
            series.append(serie(f"{p}.fase.{k}.tm", f"tm {k}", "1", ["t"], [e["fases"][j]["tm"] for e in cert], propietarioId=f"volumen:{v.id}", faseId=k))
            for c in v.comp:
                series.append(serie(f"{p}.fase.{k}.x.{c}", f"x {c} en {k}", "1", ["t"],
                                    [(e["fases"][j].get("composicion") or e["fases"][j].get("composicionIncipiente") or {}).get(c) for e in cert],
                                    propietarioId=f"volumen:{v.id}", faseId=k, componenteId=c))
        datos[v.id] = cert
    # Conservación global con las integrales auxiliares.
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
                    eventos.append(evento("aparicion_fase", "t", t, f"aparece {f}", f"volumen:{vid}"))
                for f in sorted(set(fa) - set(fd)):
                    eventos.append(evento("desaparicion_fase", "t", t, f"desaparece {f}", f"volumen:{vid}"))
        else:
            eventos.append(evento(codigo, "t", t, msg))
    estado = "parcial" if tray.detenida else "resuelto"
    verif = [{"id": "conservacion.materia", "valor": resid_n, "tolerancia": 1e-9, "descripcion": "max |sum n - n0 - intercambio exterior| / n0 por componente"},
             {"id": "conservacion.energia", "valor": resid_E, "tolerancia": 1e-9, "descripcion": "max |sum E - E0 - intercambio exterior| / |E|"},
             {"id": "complementariedad", "valor": max(e["complementariedad"] for cert in datos.values() for e in cert), "tolerancia": 1e-8,
              "descripcion": "max |beta tm|, -beta, -tm en las muestras"}]
    return conjunto(m["id"], m["nombre"], estado,
                    {"motor": "rage.compilador", "metodo": "RK45 con eventos de firma (core/solvers)", "firma": None,
                     **({"mensaje": tray.detenida.mensaje} if tray.detenida else {})},
                    [eje("t", "tiempo", "tiempo", "s", ts)], series, eventos, verif, modeloId=m["id"])
