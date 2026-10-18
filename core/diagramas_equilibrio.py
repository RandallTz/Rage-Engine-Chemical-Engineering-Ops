"""
Trazador generico de diagramas binarios T-xy (P fija) y P-xy (T fija).

Usa SOLO la operacion compartida de coexistencia (core/coexistencia_lv.py) sobre el paquete dado. No hay
ramas por paquete, especie ni ejemplo: el algoritmo es el mismo para cualquier adaptador con la interfaz de
core/mezclas.Sistema.

Algoritmo (variable de continuacion: x0, fraccion molar en el liquido de la especie 0 del sistema):
  1. Malla de Chebyshev en el intervalo pedido (densa junto a los extremos).
  2. Dos recorridos, ascendente y descendente. Cada uno arranca en su extremo: saturacion del puro del mismo
     paquete si el extremo es 0 o 1, o semilla por flash TP certificado si no. Continua con el punto anterior
     como semilla; si el Newton falla, subdivide el paso; si sigue fallando, busca una semilla nueva por flash.
  3. Cada punto se certifica (igualdad de mu, normalizacion, condicion fija, distincion de fases y
     estabilidad frente a vapor y liquido de prueba). Solo los certificados y estables forman segmentos.
  4. Refinamiento adaptativo donde salta T (o ln P) o la composicion del vapor.
  5. Singularidades: azeotropos (cambio de signo o minimo de |y - x|, refinados con x = y), encuentro con
     otra fase (frontera entre punto estable e inestable localizada por biseccion; se publica la fase
     competidora), limite de dominio (biseccion) y extremos puros.
  6. Cobertura: tramos publicados, huecos con su motivo (sin LV estable, sin convergencia, dominio,
     presupuesto) y reproducibilidad entre los dos sentidos.
Una linea entre puntos es interpolacion visual; los segmentos nunca cruzan un hueco.
"""

import math
import time

import numpy as np

from core import coexistencia_lv as co
from core import mezclas as mz

TRAZADOR = {"id": "trazador-lv-binario", "version": "1"}
PERFILES = {
    "exploratoria": {"id": "exploratoria", "puntosBase": 41, "refinamientoMaximo": 3, "saltoMaximoT": 2.0,
                     "saltoMaximoLnP": 0.1, "saltoMaximoComposicion": 0.05, "limiteEvaluaciones": 6000, "limiteSegundos": 60.0,
                     "toleranciaMu": co.TOL_MU, "toleranciaEstabilidad": co.TOL_TM},
    "refinada": {"id": "refinada", "puntosBase": 121, "refinamientoMaximo": 5, "saltoMaximoT": 0.5,
                 "saltoMaximoLnP": 0.025, "saltoMaximoComposicion": 0.015, "limiteEvaluaciones": 30000, "limiteSegundos": 240.0,
                 "toleranciaMu": co.TOL_MU, "toleranciaEstabilidad": co.TOL_TM},
}
BISECCIONES_FRONTERA = 14


class _Presupuesto:
    def __init__(self, perfil):
        self.lim_ev, self.lim_s = perfil["limiteEvaluaciones"], perfil["limiteSegundos"]
        self.ev, self.t0 = 0, time.perf_counter()

    def gastar(self, n=1):
        self.ev += n

    @property
    def agotado(self):
        return self.ev >= self.lim_ev or time.perf_counter() - self.t0 >= self.lim_s

    def resumen(self):
        return {"evaluaciones": self.ev, "limiteEvaluaciones": self.lim_ev,
                "segundos": round(time.perf_counter() - self.t0, 3), "limiteSegundos": self.lim_s}


def _malla(a, b, n):
    k = np.arange(n)
    return list(a + (b - a) * (1 - np.cos(np.pi * k / (n - 1))) / 2)


class _Intento:
    """Resultado en un x0: 'cumple' (certificado y estable), 'inestable', 'fallo' o 'dominio'."""

    def __init__(self, x0, estado, var=None, y0=None, cert=None, motivo="", origen="continuacion"):
        self.x0, self.estado, self.var, self.y0, self.cert, self.motivo, self.origen = \
            x0, estado, var, y0, cert, motivo, origen


def trazar(sis, corte, fijo, intervalo, perfil_id):
    """Diagrama en terminos del sistema (x0 = especie 0). Devuelve un dict interno que el servicio traduce."""
    perfil = PERFILES[perfil_id]
    pres = _Presupuesto(perfil)
    a, b = intervalo
    malla = _malla(a, b, perfil["puntosBase"])
    escala_var = (lambda v: v) if corte == "Txy" else math.log     # salto en K (Txy) o en ln P (Pxy)

    def evaluar(x0, semilla):
        """Resuelve y certifica en x0 desde la semilla (var, y0). _Intento."""
        if x0 <= 0.0 or x0 >= 1.0:
            i = 1 if x0 <= 0.0 else 0
            pres.gastar()
            var = co.extremo_puro(sis, corte, fijo, i)
            if var is None:
                return _Intento(x0, "dominio", motivo=f"el componente puro {sis.cas[i]} no satura en el dominio",
                                origen="extremo_puro")
            xl = np.array([1.0, 0.0]) if i == 0 else np.array([0.0, 1.0])
            cert = co.certificar(sis, corte, fijo, *co._TP(corte, fijo, var), xl, xl, idx=[i])
            return _Intento(x0, "cumple" if cert["estado"] == "cumple" else "inestable", var, float(xl[0]), cert,
                            origen="extremo_puro")
        pres.gastar()
        try:
            var, y0 = co.resolver_punto(sis, corte, fijo, x0, semilla)
        except co.SinConvergencia as x:
            return _Intento(x0, "dominio" if x.motivo == "fuera_de_dominio" else "fallo", motivo=x.mensaje)
        cert = co.certificar(sis, corte, fijo, *co._TP(corte, fijo, var), (x0, 1 - x0), (y0, 1 - y0))
        mu_ok = cert["residuos"][0]["estado"] == "cumple"
        if cert["estado"] == "cumple":
            return _Intento(x0, "cumple", var, y0, cert)
        if mu_ok and cert["estabilidad"]["estado"] == "inestable":
            return _Intento(x0, "inestable", var, y0, cert, motivo="otra fase es mas estable")
        return _Intento(x0, "fallo", var, y0, cert, motivo="certificado no cumplido")

    fuera = {}

    def semilla_flash(x0):
        """(semilla o None, motivo). Cada flash TP cuenta como una evaluacion."""
        if x0 in fuera:
            return None, fuera[x0]
        pres.gastar(45)
        try:
            return co.semilla_por_flash(sis, corte, fijo, x0), None
        except co.SinConvergencia as x:
            fuera[x0] = x.mensaje
            return None, x.mensaje
        except (mz.FueraDeAlcance, ValueError, FloatingPointError):
            return None, None

    def recorrer(xs):
        res = {}
        prev = None
        for x0 in xs:
            if pres.agotado:
                break
            if x0 in (0.0, 1.0):
                it = evaluar(x0, None)
            else:
                it = None
                if prev is not None and prev.var is not None:
                    # continuacion: paso completo y, si falla, subdivisiones hacia x0
                    it = evaluar(x0, (prev.var, prev.y0))
                    if it.estado in ("fallo",):
                        base = prev
                        for k in (2, 4, 8):
                            ok = True
                            for j in range(1, k + 1):
                                xm = base.x0 + (x0 - base.x0) * j / k
                                im = evaluar(xm, (base.var, base.y0))
                                if im.var is None:
                                    ok = False
                                    break
                                base = im
                            if ok:
                                it = base
                                it.origen = "continuacion"
                                break
                            base = prev
                if it is None or it.var is None:
                    s, motivo_fuera = semilla_flash(x0)
                    if s is not None:
                        it2 = evaluar(x0, s)
                        it2.origen = "semilla_por_flash"
                        if it2.var is not None or it is None:
                            it = it2
                    elif motivo_fuera is not None and (it is None or it.estado != "dominio"):
                        it = _Intento(x0, "dominio", motivo=motivo_fuera)
                if it is None:
                    it = _Intento(x0, "fallo", motivo="sin semilla: ni continuacion ni flash TP dieron un punto")
            res[x0] = it
            if it.var is not None and it.estado in ("cumple", "inestable"):
                prev = it
        return res

    asc = recorrer(malla)
    desc = recorrer(list(reversed(malla)))
    # fusion y reproducibilidad entre sentidos
    intentos, dif_c, dif_y, n_cmp = {}, [], [], 0
    for x0 in malla:
        p, q = asc.get(x0), desc.get(x0)
        cand = [r for r in (p, q) if r is not None]
        if not cand:
            continue
        buenos = [r for r in cand if r.estado == "cumple"]
        if len(buenos) == 2:
            n_cmp += 1
            dif_c.append(abs(escala_var(p.var) - escala_var(q.var)))
            dif_y.append(abs(p.y0 - q.y0))
        intentos[x0] = buenos[0] if buenos else next((r for r in cand if r.estado == "inestable"), cand[0])
    ambiguas = []
    if dif_c and max(dif_c) > 1e-6:
        ambiguas.append(max(dif_c))

    # refinamiento adaptativo entre puntos certificados consecutivos
    for _ in range(perfil["refinamientoMaximo"]):
        if pres.agotado:
            break
        xs = sorted(intentos)
        nuevos = []
        for u, v in zip(xs, xs[1:]):
            p, q = intentos[u], intentos[v]
            if p.estado == q.estado == "cumple" and (
                    abs(escala_var(q.var) - escala_var(p.var)) > perfil["saltoMaximoT" if corte == "Txy" else "saltoMaximoLnP"]
                    or abs(q.y0 - p.y0) > perfil["saltoMaximoComposicion"]):
                nuevos.append((0.5 * (u + v), p))
        if not nuevos:
            break
        for xm, p in nuevos:
            if pres.agotado:
                break
            it = evaluar(xm, (p.var, p.y0))
            it.origen = "refinamiento"
            intentos[xm] = it

    # fronteras entre estable e inestable / dominio: biseccion en x
    especiales = []
    xs = sorted(intentos)
    for u, v in zip(xs, xs[1:]):
        p, q = intentos[u], intentos[v]
        if pres.agotado:
            break
        if {p.estado, q.estado} in ({"cumple", "inestable"}, {"cumple", "dominio"}, {"cumple", "fallo"}):
            bueno, malo = (p, q) if p.estado == "cumple" else (q, p)
            tipo_malo = malo.estado
            for _ in range(BISECCIONES_FRONTERA):
                if pres.agotado:
                    break
                xm = 0.5 * (bueno.x0 + malo.x0)
                im = evaluar(xm, (bueno.var, bueno.y0))
                im.origen = "refinamiento"
                if im.estado == "cumple":
                    bueno = im
                elif im.estado == tipo_malo:
                    malo = im
                else:
                    break
            intentos[bueno.x0] = bueno
            intentos[malo.x0] = malo
            if tipo_malo == "inestable":
                especiales.append(("encuentro_otra_fase", bueno, malo))
            elif tipo_malo == "dominio":
                especiales.append(("limite_dominio", bueno, malo))

    # azeotropos dentro de los tramos certificados
    xs = sorted(intentos)
    azeos = []
    for k in range(len(xs) - 1):
        p, q = intentos[xs[k]], intentos[xs[k + 1]]
        if p.estado != "cumple" or q.estado != "cumple" or p.x0 in (0.0, 1.0) or q.x0 in (0.0, 1.0):
            continue
        dp, dq = p.y0 - p.x0, q.y0 - q.x0
        cruce = dp * dq < 0
        minimo = False
        if not cruce and k + 2 < len(xs):
            r = intentos[xs[k + 2]]
            if r.estado == "cumple" and r.x0 not in (0.0, 1.0):
                dr = r.y0 - r.x0
                minimo = abs(dq) < abs(dp) and abs(dq) < abs(dr) and abs(dq) < 0.02 and dp * dr > 0
        if not (cruce or minimo):
            continue
        if pres.agotado:
            break
        semilla = (0.5 * (p.var + q.var), 0.5 * (p.x0 + q.x0)) if cruce else (q.var, q.x0)
        pres.gastar()
        try:
            var, xa = co.resolver_azeotropo(sis, corte, fijo, semilla)
        except co.SinConvergencia:
            continue
        lo_, hi_ = (p.x0, q.x0) if cruce else (p.x0, intentos[xs[k + 2]].x0)
        if not lo_ - 1e-9 <= xa <= hi_ + 1e-9:
            continue
        cert = co.certificar(sis, corte, fijo, *co._TP(corte, fijo, var), (xa, 1 - xa), (xa, 1 - xa))
        it = _Intento(xa, "cumple" if cert["estado"] == "cumple" else "inestable", var, xa, cert, origen="singular")
        vecinos = [p.var, q.var]
        clase = ("tangente" if not cruce else
                 ("minimo" if var <= min(vecinos) else "maximo" if var >= max(vecinos) else "inflexion"))
        if corte == "Pxy" and clase in ("minimo", "maximo"):
            pass   # en Pxy minimo/maximo se refiere a P
        azeos.append((it, clase))
        if it.estado == "cumple":
            intentos[xa] = it

    return {"intentos": intentos, "especiales": especiales, "azeotropos": azeos, "malla": malla,
            "presupuesto": pres, "agotado": pres.agotado,
            "reproducibilidad": {"puntosComparados": n_cmp, "maxDiferenciaCondicion": max(dif_c) if dif_c else None,
                                 "maxDiferenciaComposicion": max(dif_y) if dif_y else None},
            "ambiguas": ambiguas}
