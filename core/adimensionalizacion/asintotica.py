"""
Balanza dominante de una formulacion con valores numericos.

Metodo (Kruskal; poligono de Newton). Con un estiramiento local
xi = xi_0 + delta X, un termino con derivada espacial de orden p y
coeficiente de magnitud m escala como m delta^(-p). Con s = ln delta, su
logaritmo es la recta ln m - p s. Para cada escala delta dominan los
terminos de la envolvente superior de esas rectas; los cortes de la
envolvente son los limites distinguidos (dos o mas terminos del mismo
orden de magnitud). Lo mismo en el tiempo con tau = delta T y el orden
temporal.

  - A escala unidad (delta = 1) se publica que terminos dominan y cuales son
    despreciables frente a un umbral relativo (0.01 por defecto).
  - Si el termino de mayor orden espacial es despreciable a escala unidad,
    la reduccion baja el orden: perturbacion singular. La capa tiene el
    espesor del corte donde ese termino entra en la envolvente.
  - Si la derivada temporal es despreciable a escala unidad, hay una capa
    inicial de duracion igual al corte temporal (dinamica rapida seguida de
    un regimen cuasiestacionario).
  - La ubicacion de una capa solo se publica cuando el balance interior es
    lineal con coeficientes constantes: a u'' + b u' = 0 decae hacia el
    interior desde la izquierda si b/a > 0 (y desde la derecha si b/a < 0);
    a u'' + c u = 0 da capas en ambos extremos si c/a < 0 y oscilacion (sin
    capa) si c/a > 0.

Nada de esto resuelve la ecuacion: identifica escalas y balances.
"""

import math

from . import algebra as A
from .estudio import estado, requiere
from .transformacion import termino_ast


def _envolvente(puntos):
    """puntos: [(id, lnm, p)]. Devuelve los cortes de la envolvente superior
    de lnm - p s para s <= 0, de s = 0 hacia s -> -inf: [(s, ids)]."""
    if not puntos:
        return []
    # Para s muy negativo domina el mayor p (y, a igual p, el mayor lnm).
    cortes = []
    s = 0.0
    actual = max(puntos, key=lambda x: (x[1] - x[2] * s, x[2]))
    visitados = 0
    while visitados < len(puntos) + 2:
        visitados += 1
        mejor_s, entrantes = None, []
        for pid, lnm, p in puntos:
            if p <= actual[2]:
                continue
            # corte: lnm_a - p_a s = lnm - p s -> s = (lnm - lnm_a)/(p - p_a)
            sc = (lnm - actual[1]) / (p - actual[2])
            if sc > s + 1e-12:
                continue
            if mejor_s is None or sc > mejor_s + 1e-12:
                mejor_s, entrantes = sc, [(pid, lnm, p)]
            elif abs(sc - mejor_s) <= 1e-12:
                entrantes.append((pid, lnm, p))
        if mejor_s is None:
            break
        nivel = actual[1] - actual[2] * mejor_s
        empatados = [pid for pid, lnm, p in puntos if abs((lnm - p * mejor_s) - nivel) <= 1e-9 * max(1.0, abs(nivel))]
        cortes.append((mejor_s, empatados))
        actual = max(entrantes, key=lambda x: x[2])
        s = mejor_s
    return cortes


def _balance_escala_unidad(terminos, umbral):
    mags = {t.id: abs(t.coef) for t in terminos}
    maximo = max(mags.values()) if mags else 0.0
    dominantes = [tid for tid, m in mags.items() if m >= umbral * maximo]
    despreciables = [tid for tid, m in mags.items() if m < umbral * maximo]
    return dominantes, despreciables, mags, maximo


def _lineal_en(t, campo, coordenada, orden):
    """True si el nucleo es exactamente d^orden(campo)/dcoordenada^orden
    (orden 0: el propio campo)."""
    u = t.P.monomio_unico()
    if not u or u[0] != 1 or len(u[1]) != 1 or u[1][0][1] != 1:
        return False
    a = u[1][0][0]
    if orden == 0:
        return a == ("s", campo)
    if a[0] != "d" or a[2] != coordenada or a[3] != orden:
        return False
    i = a[1].monomio_unico()
    return bool(i) and i[0] == 1 and len(i[1]) == 1 and i[1][0] == (("s", campo), 1)


def _ubicacion(terminos_balance, campo, coordenada):
    por = {}
    for t in terminos_balance:
        for orden in (2, 1, 0):
            if _lineal_en(t, campo, coordenada, orden):
                por[orden] = por.get(orden, 0.0) + t.signo * t.coef
                break
        else:
            return None
    if 2 not in por:
        return None
    a = por[2]
    if set(por) == {2, 1}:
        b = por[1]
        return {"lado": "desde" if b / a > 0 else "hasta", "balance": "difusión-convección",
                "criterio": f"a u'' + b u' = 0 con b/a = {b / a:.6g}: la solución interior exp(-(b/a) X) decae hacia el interior desde el extremo indicado"}
    if set(por) == {2, 0}:
        c = por[0]
        if c / a < 0:
            return {"lado": "ambos", "balance": "difusión-reacción",
                    "criterio": f"a u'' + c u = 0 con c/a = {c / a:.6g} < 0: soluciones exponenciales; capas posibles en ambos extremos según las condiciones"}
        return {"lado": "ninguno", "balance": "difusión-reacción",
                "criterio": f"a u'' + c u = 0 con c/a = {c / a:.6g} > 0: soluciones oscilatorias de longitud de onda delta; no es una capa"}
    return None


def _reducida(cx, ecuacion, conservar):
    pub = next(e for e in cx.cuerpo["ecuaciones"] if e["igualdad"]["id"] == ecuacion["id"])
    lados = {"izquierda": [], "derecha": []}
    for t in pub["terminos"]:
        if t["id"] in conservar:
            lados[t["lado"]].append(_producto(t["coeficiente"], t["nucleo"]))
    return {"id": ecuacion["id"], "izquierda": A.ast_suma(lados["izquierda"]), "derecha": A.ast_suma(lados["derecha"])}


def _producto(c, n):
    if c.get("tipo") == "numero" and c.get("valor") == 1:
        return n
    if n.get("tipo") == "numero" and n.get("valor") == 1:
        return c
    return {"tipo": "producto", "argumentos": [c, n]}


def analizar(cx, sistema):
    faltan = requiere(sistema)
    if faltan:
        return faltan
    umbral = cx.opciones.get("umbralAsintotico", 0.01)
    ecuaciones = []
    for e in sistema.ecuaciones:
        ts = [t for t in e["terminos"] if t.coef != 0 and math.isfinite(t.coef)]
        dominantes, despreciables, mags, maximo = _balance_escala_unidad(ts, umbral)
        r = {"id": e["id"], "magnitudes": {k: v for k, v in mags.items()}, "dominantes": dominantes, "despreciables": despreciables}
        if despreciables:
            r["reducida"] = _reducida(cx, e, set(dominantes))
        # Espacio.
        orden_max = max((t.clase["ordenEspacial"] for t in ts), default=0)
        espacial = None
        if orden_max:
            puntos = [(t.id, math.log(abs(t.coef)), t.clase["ordenEspacial"]) for t in ts]
            cortes = _envolvente(puntos)
            altos = [t for t in ts if t.clase["ordenEspacial"] == orden_max]
            alto_despreciable = all(t.id in despreciables for t in altos)
            orden_dom = max((t.clase["ordenEspacial"] for t in ts if t.id in dominantes), default=0)
            espacial = {"ordenMaximo": orden_max, "ordenReducido": orden_dom,
                        "balances": [{"delta": math.exp(s), "terminos": ids} for s, ids in cortes]}
            if alto_despreciable and orden_dom < orden_max:
                entrada = next(((s, ids) for s, ids in cortes if any(t.id in ids for t in altos)), None)
                capa = {"tipo": "perturbacion_singular", "condicionesPerdidas": orden_max - orden_dom,
                        "espesor": math.exp(entrada[0]) if entrada else None, "balanceInterior": entrada[1] if entrada else []}
                coords = sorted({v for t in ts for v, o, _ in _derivs(t) if v in set(cx.coordenadas)})
                campos = sorted({c for t in altos for c in t.clase["campos"]})
                if entrada and len(coords) == 1 and len(campos) == 1:
                    interior = [t for t in ts if t.id in entrada[1]]
                    capa["ubicacion"] = _ubicacion(interior, campos[0], coords[0])
                    dom = sistema.dominios.get(coords[0])
                    if dom and capa["ubicacion"] and capa["ubicacion"]["lado"] in ("desde", "hasta"):
                        capa["ubicacion"]["en"] = {"variableId": coords[0], "valor": dom[capa["ubicacion"]["lado"]]}
                espacial["capa"] = capa
            elif alto_despreciable:
                espacial["capa"] = {"tipo": "regular", "nota": "el término de mayor orden es pequeño pero el orden se conserva"}
        r["espacial"] = espacial
        # Tiempo.
        temporales = [t for t in ts if t.clase["ordenTemporal"]]
        if temporales:
            puntos = [(t.id, math.log(abs(t.coef)), t.clase["ordenTemporal"]) for t in ts]
            cortes = _envolvente(puntos)
            t_desprec = all(t.id in despreciables for t in temporales)
            temporal = {"balances": [{"delta": math.exp(s), "terminos": ids} for s, ids in cortes]}
            if t_desprec:
                entrada = next(((s, ids) for s, ids in cortes if any(t.id in ids for t in temporales)), None)
                temporal["capaInicial"] = {"duracion": math.exp(entrada[0]) if entrada else None,
                                           "balanceInterior": entrada[1] if entrada else [],
                                           "nota": "la acumulación es despreciable a escala unidad: tras un transitorio de esa duración el campo sigue el balance cuasiestacionario"}
            r["temporal"] = temporal
        ecuaciones.append(r)
    return {"estado": "calculado",
            "motivo": f"envolvente de Kruskal sobre |coeficiente| delta^(-orden) con los valores dados; umbral relativo {umbral}",
            "umbral": umbral, "ecuaciones": ecuaciones}


def _derivs(t):
    from .estudio import _atomos_derivada
    return [(v, o, p) for v, o, p in _atomos_derivada(t.P) if v != "operador" and t.clase["ordenEspacial"]]


_ = termino_ast
