"""
Estudio de una formulacion adimensional: lo que se puede deducir de ella
con rigor, y con los valores fisicos que da el usuario.

Cada analisis se calcula a partir del modelo publicado por el nucleo (sus
terminos, coeficientes y grupos), nunca de nombres de simbolos ni de
plantillas. Cada uno publica su estado:

  - "calculado": resultado obtenido con el metodo que se declara;
  - "requiere_datos": faltan valores (se dice cuales);
  - "no_aplicable": la estructura del modelo no corresponde (p. ej. no hay
    coordenada espacial para una capa limite);
  - "no_soportado": la estructura esta fuera del alcance implementado (se
    dice por que).

Analisis:
  estructura    clasificacion de cada termino por sus operadores y lectura
                de cada grupo como cociente de dos terminos (exacta).
  sensibilidad  exponentes racionales de cada parametro en cada grupo
                monomial: d ln G / d ln p (exacta).
  valores       valores numericos de escalas, grupos y coeficientes con los
                datos del usuario en SI; dispersion de magnitudes.
  asintotica    balanza dominante (envolvente de Kruskal / poligono de
                Newton) y deteccion de capas limite y de tiempo inicial.
  escalas       tiempos caracteristicos, Peclet de celda, limites de paso
                explicitos y rigidez de la discretizacion.
  simetrias     grupos de escala (dilataciones) y traslaciones; reduccion
                exacta a EDO de semejanza y de onda viajera.
  estabilidad   estados homogeneos, jacobiano, relacion de dispersion y
                clasificacion (estable, Hopf, Turing, homogenea).
  continuacion  ramas de estados homogeneos frente a un parametro, con
                pliegues (puntos limite) y cambios de estabilidad.
  simulacion    metodo de lineas en una coordenada con BDF, condiciones
                declaradas y estimacion del error de malla.
"""

import copy
import math
from fractions import Fraction

import numpy as np

from . import algebra as A
from .dimensional import cantidad_SI, dim_a_json, interpretar_unidad, limpiar
from .numerico import NoEvaluable, evaluar_poli, numero_json

ANALISIS = ("estructura", "sensibilidad", "valores", "asintotica", "escalas", "simetrias",
            "estabilidad", "continuacion", "simulacion")
UMBRAL_ASINTOTICO = 0.01


def _sim(i):
    return {"tipo": "simbolo", "id": i}


def _q(x):
    x = Fraction(x)
    return {"n": x.numerator, "d": x.denominator}


def estado(nombre, motivo, **extra):
    r = {"estado": nombre, "motivo": motivo}
    r.update(extra)
    return r


# --- Contexto del estudio ------------------------------------------------------

class Contexto:
    """Formulacion publicada + preparacion + valores numericos."""

    def __init__(self, prep, cuerpo, opciones):
        self.prep = prep
        self.cuerpo = cuerpo
        self.opciones = opciones
        self.ctx = prep.ctx_t
        self.simbolos_modelo = prep.simbolos_modelo
        nuevos = {m["nuevo"]: m for m in prep.mapas}
        self.tiempo = next((m["nuevo"] for m in prep.mapas if m["rol"] == "tiempo"), None)
        if self.tiempo is None:
            self.tiempo = next((s["id"] for s in prep.modelo["simbolos"] if s["rol"] == "tiempo"), None)
        self.coordenadas = [m["nuevo"] for m in prep.mapas if m["rol"] == "coordenada"]
        self.coordenadas += [s["id"] for s in prep.modelo["simbolos"] if s["rol"] == "coordenada" and s["id"] not in prep.por_variable]
        self.campos = [m["nuevo"] for m in prep.mapas if m["rol"] == "campo"]
        self.campos += [s["id"] for s in prep.modelo["simbolos"] if s["rol"] == "campo" and s["id"] not in prep.por_variable]
        self.mapa_nuevo = nuevos
        self.diagnosticos = []
        self.valores, self.faltan_valores = self._valores()

    # --- valores con unidades ---------------------------------------------
    def _dimension_de(self, sid):
        if sid in self.prep.dims_t:
            return self.prep.dims_t[sid]
        return None

    def _valores(self):
        """Valores SI de parametros, constantes y escalas libres; despues,
        las escalas determinadas se evaluan con sus expresiones."""
        valores, faltan = {}, []
        libres = set(self.cuerpo["libres"])
        dados = {}
        for i, v in enumerate(self.opciones.get("valores", [])):
            ruta = f"estudio.valores[{i}]"
            sid = v["simboloId"]
            dim = self._dimension_de(sid)
            if sid in self.simbolos_modelo:
                s = self.simbolos_modelo[sid]
                if s["rol"] not in ("parametro", "constante"):
                    self.diagnosticos.append({"ruta": ruta, "codigo": "valor_no_admitido", "severidad": "error",
                                              "mensaje": f"{sid} es una variable ({s['rol']}); solo se dan valores de parametros, constantes y escalas libres"})
                    continue
                unidad = v.get("unidad") or s["unidad"]
            elif sid in libres:
                unidad = v.get("unidad")
            elif sid in self.prep.por_id:
                self.diagnosticos.append({"ruta": ruta, "codigo": "escala_no_libre", "severidad": "error",
                                          "mensaje": f"{sid} no es una escala libre en esta formulacion; su valor lo fijan los objetivos"})
                continue
            else:
                self.diagnosticos.append({"ruta": ruta, "codigo": "simbolo_desconocido", "severidad": "error",
                                          "mensaje": f"{sid} no es un parametro ni una escala libre de esta formulacion"})
                continue
            x = v["valor"]
            if unidad:
                u = interpretar_unidad(unidad)
                if u is None:
                    self.diagnosticos.append({"ruta": ruta + ".unidad", "codigo": "unidad_no_reconocida", "severidad": "error",
                                              "mensaje": f"unidad '{unidad}' no reconocida"})
                    continue
                if dim is not None and set(limpiar(dim)) <= {"L", "M", "T", "I", "Theta", "N", "J"} and u["dimension"] != limpiar(dim):
                    self.diagnosticos.append({"ruta": ruta + ".unidad", "codigo": "dimension_incompatible", "severidad": "error",
                                              "mensaje": f"la unidad '{unidad}' no tiene la dimension de {sid}"})
                    continue
                if dim is not None and not set(limpiar(dim)) <= {"L", "M", "T", "I", "Theta", "N", "J"}:
                    self.diagnosticos.append({"ruta": ruta + ".unidad", "codigo": "unidad_no_comparable", "severidad": "error",
                                              "mensaje": f"{sid} usa bases no SI; de su valor sin unidad o en la unidad declarada"})
                    continue
                x, _ = cantidad_SI(x, unidad)
            signo = self.simbolos_modelo[sid]["signo"] if sid in self.simbolos_modelo else "positivo"
            if (signo == "positivo" and x <= 0) or (signo == "negativo" and x >= 0) or (signo == "cero" and x != 0):
                self.diagnosticos.append({"ruta": ruta + ".valor", "codigo": "signo_contradictorio", "severidad": "error",
                                          "mensaje": f"el valor de {sid} contradice su signo declarado ({signo})"})
                continue
            dados[sid] = float(x)
        for s in self.prep.modelo["simbolos"]:
            if s["rol"] in ("parametro", "constante") and s["signo"] == "cero":
                dados.setdefault(s["id"], 0.0)
        valores.update(dados)
        # Escalas: libres (dadas), dadas con cantidad, por expresion o resueltas.
        for e in self.cuerpo["escalas"]:
            sid = e["escalaId"]
            info = self.prep.por_id[sid]
            if e["estado"] == "dada" and "cantidad" in info:
                valores[sid] = info["cantidad"]["valorSI"]
        pendientes = [e for e in self.cuerpo["escalas"] if e["escalaId"] not in valores]
        for _ in range(len(pendientes) + 1):
            for e in pendientes:
                sid = e["escalaId"]
                if sid in valores or e["estado"] == "libre":
                    continue
                try:
                    valores[sid] = float(numero_json(evaluar_poli(A.canonica(e["valor"], self.ctx), valores)) or float("nan"))
                except NoEvaluable:
                    pass
        for e in self.cuerpo["escalas"]:
            if e["escalaId"] not in valores:
                if e["estado"] == "libre":
                    faltan.append(e["escalaId"])
                else:
                    # Una escala resuelta falta porque faltan sus datos: se nombran.
                    faltan.extend(s for s in _simbolos(e["valor"]) if s not in valores)
        usados = set()
        for ec in self.cuerpo["ecuaciones"]:
            for t in ec["terminos"]:
                usados |= _simbolos(t["coeficiente"])
        for c in self.cuerpo["condiciones"]:
            for t in c["terminos"]:
                usados |= _simbolos(t["coeficiente"])
        for d in self.cuerpo["dominios"]:
            usados |= _simbolos(d["desde"]) | _simbolos(d["hasta"])
        for sid in sorted(usados):
            if sid not in valores and (sid in self.simbolos_modelo or sid in self.prep.por_id) and sid not in faltan:
                faltan.append(sid)
        return valores, sorted(set(faltan))

    def numero(self, ast):
        """Valor numerico de una expresion de parametros y escalas, o None."""
        try:
            return numero_json(evaluar_poli(A.canonica(ast, self.ctx), self.valores))
        except (NoEvaluable, A.ErrorAlgebraico, ZeroDivisionError, OverflowError, ValueError, FloatingPointError):
            return None

    def faltan_en(self, ast):
        return sorted(s for s in _simbolos(ast) if s not in self.valores and (s in self.simbolos_modelo and self.simbolos_modelo[s]["rol"] in ("parametro", "constante") or s in self.prep.por_id))


def _simbolos(e):
    if e is None:
        return set()
    if e["tipo"] == "simbolo":
        return {e["id"]}
    r = set()
    for a in e.get("argumentos", []):
        r |= _simbolos(a)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            r |= _simbolos(e[k])
    return r


# --- Clasificacion de terminos -------------------------------------------------

def _atomos_derivada(P):
    """Lista de (variable, orden, poli_interior) de las derivadas de P."""
    r = []
    for m in P.t:
        for a, _ in m:
            r.extend(_derivadas_atomo(a))
    return r


def _derivadas_atomo(a):
    if a[0] == "d":
        interior = _atomos_derivada(a[1])
        return [(a[2], a[3], a[1])] + interior
    if a[0] in ("f", "c"):
        return [x for p in a[2] for x in _atomos_derivada(p)]
    if a[0] in ("b",):
        return _atomos_derivada(a[1])
    if a[0] == "p":
        return _atomos_derivada(a[1]) + _atomos_derivada(a[2])
    if a[0] == "o":
        return [("operador", 2 if a[1] == "laplaciano" else 1, a[2])]
    return []


def _campos_en(P, campos):
    r = set()
    for m in P.t:
        for a, _ in m:
            r |= _campos_atomo(a, campos)
    return r


def _campos_atomo(a, campos):
    if a[0] == "s":
        return {a[1]} if a[1] in campos else set()
    if a[0] in ("f", "c"):
        return {x for p in a[2] for x in _campos_en(p, campos)}
    if a[0] in ("b", "d"):
        return _campos_en(a[1], campos)
    if a[0] == "p":
        return _campos_en(a[1], campos) | _campos_en(a[2], campos)
    if a[0] == "o":
        return _campos_en(a[2], campos)
    return set()


def clasificar_nucleo(P, ctx, campos, tiempo, coordenadas):
    """Tipo de un termino segun sus operadores (forma canonica cartesiana)."""
    derivadas = _atomos_derivada(P)
    orden_t = max((o for v, o, _ in derivadas if v == tiempo), default=0)
    orden_x = max((o for v, o, _ in derivadas if v in coordenadas or v == "operador"), default=0)
    fuera = set()
    for m in P.t:
        for a, e in m:
            if a[0] != "d":
                fuera |= _campos_atomo(a, campos)
    presentes = _campos_en(P, campos)
    no_lineal = False
    for m in P.t:
        grado = sum(e for a, e in m if a[0] == "s" and a[1] in campos) + sum(1 for a, _ in m if a[0] == "d")
        funciones = any(a[0] in ("f", "c", "b", "p") and _campos_atomo(a, campos) for a, _ in m)
        if grado != 1 or funciones:
            no_lineal = True
    if orden_t and orden_x:
        tipo = "mixto"
    elif orden_t == 1:
        tipo = "acumulacion"
    elif orden_t >= 2:
        tipo = "inercia_temporal"
    elif orden_x >= 3:
        tipo = "orden_superior"
    elif orden_x == 2:
        tipo = "difusion"
    elif orden_x == 1:
        tipo = "conveccion"
    elif presentes:
        tipo = "reaccion"
    else:
        tipo = "fuente"
    return {"tipo": tipo, "ordenTemporal": orden_t, "ordenEspacial": orden_x, "campos": sorted(presentes),
            "lineal": not no_lineal if presentes else None}


def clasificar_condicion(P, campos):
    derivadas = _atomos_derivada(P)
    if derivadas:
        return "flujo"
    if _campos_en(P, campos):
        return "valor"
    return "dato"


NOMBRES_PAR = {
    ("acumulacion", "difusion"): ("número de Fourier (Fo)", "tiempo de referencia frente al tiempo de difusión"),
    ("acumulacion", "conveccion"): ("inverso del número de Strouhal", "tiempo de referencia frente al tiempo de tránsito convectivo"),
    ("acumulacion", "reaccion"): ("número de Damköhler temporal", "tiempo de referencia frente al tiempo de reacción"),
    ("acumulacion", "fuente"): ("fuente relativa", "aporte de la fuente en el tiempo de referencia frente a la escala del campo"),
    ("conveccion", "difusion"): ("inverso del número de Péclet (1/Pe)", "difusión frente a convección"),
    ("conveccion", "reaccion"): ("número de Damköhler de primera especie (Da_I)", "reacción frente a convección"),
    ("difusion", "conveccion"): ("número de Péclet (Pe)", "convección frente a difusión"),
    ("difusion", "reaccion"): ("número de Damköhler de segunda especie (Da_II, módulo de Thiele al cuadrado)", "reacción frente a difusión"),
    ("reaccion", "difusion"): ("inverso del Damköhler de segunda especie", "difusión frente a reacción"),
    ("reaccion", "conveccion"): ("inverso del Damköhler de primera especie", "convección frente a reacción"),
    ("reaccion", "reaccion"): ("cociente de velocidades de reacción", "una reacción frente a otra"),
    ("difusion", "difusion"): ("cociente de difusividades", "una difusión frente a otra"),
    ("conveccion", "conveccion"): ("cociente de velocidades", "una convección frente a otra"),
    ("flujo", "valor"): ("número de Biot (o de Sherwood másico)", "transferencia en la frontera frente al transporte interno"),
    ("flujo", "dato"): ("flujo impuesto adimensional", "flujo de frontera frente a la escala del gradiente"),
    ("valor", "dato"): ("valor de frontera relativo", "dato de frontera frente a la escala del campo"),
    ("valor", "valor"): ("coeficiente de frontera", "un valor frente a otro en la frontera"),
}
TIPO_TEXTO = {"acumulacion": "acumulación", "inercia_temporal": "inercia temporal", "difusion": "difusión", "conveccion": "convección",
              "reaccion": "reacción", "fuente": "fuente", "orden_superior": "orden superior", "mixto": "derivada mixta",
              "flujo": "flujo", "valor": "valor", "dato": "dato"}


def estructura(cx):
    prep, cuerpo = cx.prep, cx.cuerpo
    tipos, por_termino = {}, {}
    ecuaciones = []
    for reg, ec in zip(prep.ecuaciones, cuerpo["ecuaciones"]):
        terminos = []
        for t in ec["terminos"]:
            P = A.canonica(t["nucleo"], cx.ctx, "cartesiano")
            c = clasificar_nucleo(P, cx.ctx, set(cx.campos), cx.tiempo, set(cx.coordenadas))
            terminos.append({"id": t["id"], "lado": t["lado"], **c, "grupoId": t["grupoId"]})
            tipos.setdefault(t["id"], c["tipo"])
            por_termino[t["id"]] = c
        ref = reg.get("referencia")
        if ref is None and len(reg["lados"]["izquierda"]) == 1:
            ref = reg["lados"]["izquierda"][0]["id"]
        hay_factor = not (ec["factorGlobal"].get("tipo") == "numero" and ec["factorGlobal"].get("valor") == 1)
        ecuaciones.append({"id": ec["igualdad"]["id"], "referencia": ref if hay_factor else None, "terminos": terminos})
    condiciones = []
    for reg, c in zip(prep.condiciones, cuerpo["condiciones"]):
        terminos = []
        for t in c["terminos"]:
            P = A.canonica(t["nucleo"], cx.ctx, "cartesiano")
            tipo = clasificar_condicion(P, set(cx.campos))
            terminos.append({"id": t["id"], "lado": t["lado"], "tipo": tipo, "grupoId": t["grupoId"]})
            tipos.setdefault(t["id"], tipo)
        ref = reg.get("referencia") or (reg["lados"]["izquierda"][0]["id"] if len(reg["lados"]["izquierda"]) == 1 else None)
        hay_factor = not (c["factorGlobal"].get("tipo") == "numero" and c["factorGlobal"].get("valor") == 1)
        condiciones.append({"id": c["id"], "referencia": ref if hay_factor else None, "terminos": terminos})
    # Lectura de cada grupo: cociente de su termino entre el de referencia
    # (factor global) y, como equivalencias, entre cada otro termino que haya
    # quedado con coeficiente +-1 en la misma igualdad (tienen la misma escala).
    referencia_de, unitarios_de = {}, {}
    publicadas = list(cuerpo["ecuaciones"]) + list(cuerpo["condiciones"])
    for e, pub in zip(ecuaciones + condiciones, publicadas):
        unitarios = [t["id"] for t in pub["terminos"] if t["coeficiente"].get("tipo") == "numero" and abs(t["coeficiente"].get("valor")) == 1]
        for t in e["terminos"]:
            referencia_de[t["id"]] = e["referencia"]
            unitarios_de[t["id"]] = unitarios

    def leer(t_tipo, r_id):
        r_tipo = tipos.get(r_id)
        x = {"termino": r_id, "tipo": r_tipo}
        tt, rt = TIPO_TEXTO.get(t_tipo, t_tipo), TIPO_TEXTO.get(r_tipo, r_tipo)
        if (r_tipo, t_tipo) in NOMBRES_PAR:
            nombre, significado = NOMBRES_PAR[(r_tipo, t_tipo)]
            x.update(nombreClasico=nombre, lectura=f"{tt} frente a {rt}: {significado}")
        else:
            x["lectura"] = f"{tt} frente a {rt}"
        return x
    grupos = []
    for g in cuerpo["grupos"]:
        lecturas = []
        for uso in g["usos"]:
            ref = referencia_de.get(uso)
            if g["interno"]:
                lecturas.append({"termino": uso, "lectura": "coeficiente interno de una funcion o suma del termino (por ejemplo, una constante frente a la escala del campo)"})
                continue
            t_tipo = tipos.get(uso)
            item = {"termino": uso, "tipoTermino": t_tipo, "referencia": ref, "tipoReferencia": tipos.get(ref) if ref else None}
            if ref is None:
                item["lectura"] = "coeficiente del termino (la igualdad no se dividio por un factor global)"
            else:
                principal = leer(t_tipo, ref)
                item.update({k: v for k, v in principal.items() if k in ("nombreClasico", "lectura")})
                item["equivalentes"] = [leer(t_tipo, u) for u in unitarios_de.get(uso, []) if u not in (uso, ref)]
            lecturas.append(item)
        principales = [x["nombreClasico"] for x in lecturas if "nombreClasico" in x]
        todos = principales + [y["nombreClasico"] for x in lecturas for y in x.get("equivalentes", []) if "nombreClasico" in y]
        unicos = list(dict.fromkeys(todos))
        grupos.append({"grupoId": g["id"], "lecturas": lecturas,
                       "nombreClasico": principales[0] if len(set(principales)) == 1 else None,
                       "nombresClasicos": unicos,
                       "nota": None if len(set(principales)) <= 1 else "el grupo aparece en terminos de tipos distintos: " + "; ".join(sorted(set(principales)))})
    # Regimen: que terminos quedaron con coeficiente 1 por objetivos.
    normalizados = []
    for o in cuerpo["objetivos"]:
        if o["estado"] in ("satisfecho", "dependiente") and o.get("terminoId") in por_termino:
            normalizados.append({"objetivo": o["id"], "terminoId": o["terminoId"], "tipo": por_termino[o["terminoId"]]["tipo"], "estado": o["estado"]})
    return {"estado": "calculado", "motivo": "clasificacion por operadores de la forma canonica cartesiana de cada nucleo; cada grupo se lee como el cociente entre su termino y el de referencia (factor global)",
            "ecuaciones": ecuaciones, "condiciones": condiciones, "grupos": grupos, "normalizados": normalizados}


# --- Sensibilidad ---------------------------------------------------------------

def sensibilidad(cx):
    filas, omitidos = [], []
    parametros = set()
    for g in cx.cuerpo["grupos"]:
        P = A.canonica(g["definicion"], cx.ctx)
        u = P.monomio_unico()
        if u is None:
            omitidos.append({"grupoId": g["id"], "motivo": "definicion no monomial: la elasticidad depende del punto"})
            continue
        exps = {}
        for a, e in u[1]:
            if a[0] == "s":
                exps[a[1]] = exps.get(a[1], 0) + e
            elif a[0] == "f" and a[1] == "abs" and a[2][0].monomio_unico() and len(a[2][0].monomio_unico()[1]) == 1 and a[2][0].monomio_unico()[1][0][0][0] == "s":
                sid = a[2][0].monomio_unico()[1][0][0][1]
                exps[sid] = exps.get(sid, 0) + e
            elif a[0] == "n":
                continue
            else:
                exps = None
                break
        if exps is None:
            omitidos.append({"grupoId": g["id"], "motivo": "contiene factores que no son simbolos (funciones)"})
            continue
        parametros |= set(exps)
        filas.append({"grupoId": g["id"], "exponentes": {k: _q(v) for k, v in sorted(exps.items())}})
    libres = set(cx.cuerpo["libres"])
    return {"estado": "calculado",
            "motivo": "cada grupo es un monomio: d ln G / d ln p es exactamente el exponente de p (racional); no depende de los valores",
            "parametros": sorted(parametros), "escalasLibres": sorted(parametros & libres), "grupos": filas, "omitidos": omitidos}


# --- Valores numericos -----------------------------------------------------------

def valores(cx):
    prep, cuerpo = cx.prep, cx.cuerpo
    escalas = []
    for e in cuerpo["escalas"]:
        sid = e["escalaId"]
        v = cx.valores.get(sid)
        dim = prep.por_id[sid]["dimension"]
        escalas.append({"escalaId": sid, "estado": e["estado"], "valorSI": numero_json(v) if v is not None else None,
                        "dimension": dim_a_json(dim), "unidadSI": _unidad_si(dim)})
    grupos = []
    for g in cuerpo["grupos"]:
        v = cx.numero(g["definicion"])
        grupos.append({"grupoId": g["id"], "valor": v, "faltan": [] if v is not None else cx.faltan_en(g["definicion"]),
                       "log10": math.log10(abs(v)) if v not in (None, 0) else None})
    ecuaciones = []
    for ec in cuerpo["ecuaciones"]:
        coef = []
        for t in ec["terminos"]:
            v = cx.numero(t["coeficiente"])
            coef.append({"terminoId": t["id"], "lado": t["lado"], "valor": v})
        mags = [abs(c["valor"]) for c in coef if c["valor"] not in (None, 0)]
        disp = math.log10(max(mags) / min(mags)) if len(mags) >= 2 and len(mags) == len(coef) else None
        ecuaciones.append({"id": ec["igualdad"]["id"], "coeficientes": coef, "dispersionLog10": disp})
    completos = not cx.faltan_valores
    return {"estado": "calculado" if completos else "requiere_datos",
            "motivo": "valores en SI evaluados sobre las expresiones exactas publicadas" if completos else "faltan valores: " + ", ".join(cx.faltan_valores),
            "faltan": cx.faltan_valores, "escalas": escalas, "grupos": grupos, "ecuaciones": ecuaciones,
            "dispersionMaxima": max((e["dispersionLog10"] for e in ecuaciones if e["dispersionLog10"] is not None), default=None)}


def _unidad_si(dim):
    if dim is None:
        return None
    nombres = {"L": "m", "M": "kg", "T": "s", "I": "A", "Theta": "K", "N": "mol", "J": "cd"}
    d = limpiar(dim)
    if not set(d) <= set(nombres):
        return None
    if not d:
        return "1"
    partes = []
    for k in ("M", "N", "L", "T", "Theta", "I", "J"):
        if k in d:
            e = d[k]
            partes.append(nombres[k] if e == 1 else f"{nombres[k]}^{e}")
    return " ".join(partes)


# --- Sistema numerico (comun a los analisis dinamicos) ----------------------------

class Termino:
    """coef: valor con los datos del usuario; C: coeficiente exacto (Poli en
    parametros y escalas libres) para reevaluarlo al variar un parametro."""

    def __init__(self, tid, signo, coef, C, P, clase):
        self.id, self.signo, self.coef, self.C, self.P, self.clase = tid, signo, coef, C, P, clase

    def valor(self, valores=None):
        if valores is None:
            return self.coef
        return evaluar_poli(self.C, valores)


class SistemaNumerico:
    """Igualdades publicadas como residuo sum(signo coef nucleo) = 0, con
    coeficientes numericos y nucleos en forma canonica 'expandir' (las
    derivadas actuan solo sobre los campos)."""

    def __init__(self, cx, incluir_condiciones=False):
        self.cx = cx
        self.ecuaciones, self.faltan, self.problemas = [], set(), []
        for ec in cx.cuerpo["ecuaciones"]:
            self.ecuaciones.append(self._igualdad(ec["igualdad"]["id"], ec["terminos"]))
        self.condiciones = []
        for c in cx.cuerpo["condiciones"]:
            self.condiciones.append({"id": c["id"], "tipo": c["tipo"], "lugar": c.get("lugar"), "dominioId": c["dominioId"],
                                     **self._igualdad(c["id"], c["terminos"])})
        self.dominios = {}
        for d in cx.cuerpo["dominios"]:
            a, b = cx.numero(d["desde"]), cx.numero(d["hasta"])
            if a is None or b is None:
                self.faltan |= set(cx.faltan_en(d["desde"])) | set(cx.faltan_en(d["hasta"]))
            self.dominios[d["variableId"]] = {"id": d["id"], "desde": a, "hasta": b}
        self.evolucion = self._evolucion()

    def _igualdad(self, iid, terminos):
        lista = []
        for t in terminos:
            coef = self.cx.numero(t["coeficiente"])
            if coef is None:
                self.faltan |= set(self.cx.faltan_en(t["coeficiente"])) or {f"coeficiente de {t['id']}"}
                coef = float("nan")
            try:
                P = A.canonica(t["nucleo"], self.cx.ctx, "expandir")
            except (A.ErrorAlgebraico, A.NoSoportado) as e:
                self.problemas.append(f"{t['id']}: {e.mensaje}")
                P = A.canonica(t["nucleo"], self.cx.ctx, "cartesiano")
            clase = clasificar_nucleo(P, self.cx.ctx, set(self.cx.campos), self.cx.tiempo, set(self.cx.coordenadas))
            C = A.canonica(t["coeficiente"], self.cx.ctx)
            lista.append(Termino(t["id"], 1 if t["lado"] == "izquierda" else -1, coef, C, P, clase))
        return {"id": iid, "terminos": lista}

    def _evolucion(self):
        """Forma de evolucion m du_i/dtau = F_i: un unico termino temporal de
        orden 1 por ecuacion, sobre un campo distinto en cada una."""
        cx = self.cx
        if cx.tiempo is None:
            return None
        sistema = []
        usados = set()
        for e in self.ecuaciones:
            temporales = [t for t in e["terminos"] if t.clase["ordenTemporal"]]
            if len(temporales) != 1:
                self.problemas.append(f"{e['id']}: se necesita exactamente un termino con derivada temporal (hay {len(temporales)})")
                return None
            t = temporales[0]
            u = t.P.monomio_unico()
            campo = None
            if u and len(u[1]) == 1 and u[1][0][1] == 1 and u[1][0][0][0] == "d":
                a = u[1][0][0]
                interior = a[1].monomio_unico()
                if a[2] == cx.tiempo and a[3] == 1 and interior and interior[0] == 1 and len(interior[1]) == 1 and interior[1][0][1] == 1 \
                        and interior[1][0][0][0] == "s" and interior[1][0][0][1] in cx.campos:
                    campo = interior[1][0][0][1]
            if campo is None or campo in usados:
                self.problemas.append(f"{e['id']}: el termino temporal no es (constante) d{{campo}}/dtau sobre un campo propio")
                return None
            usados.add(campo)
            resto = [x for x in e["terminos"] if x is not t]
            for x in resto:
                if x.clase["tipo"] == "mixto":
                    self.problemas.append(f"{x.id}: derivada mixta en tiempo y espacio")
                    return None
            sistema.append({"ecuacion": e["id"], "campo": campo, "temporal": t, "factor": float(u[0]), "resto": resto})
        return sistema

    def explicitas(self):
        """Coordenadas o tiempo que aparecen fuera de una derivada (el sistema
        no es autonomo en ellas)."""
        indep = set(self.cx.coordenadas) | ({self.cx.tiempo} if self.cx.tiempo else set())
        r = set()
        for item in self.evolucion or []:
            for t in item["resto"]:
                r |= _explicitos(t.P, indep)
        return sorted(r)

    def masa(self, item, valores=None):
        t = item["temporal"]
        return t.signo * t.valor(valores) * item["factor"]

    def rhs(self, campos, derivadas, valores=None):
        """F_i = du_i/dtau. campos: id -> valor o arreglo; derivadas(atomo)
        aporta el valor de cada derivada espacial; valores sustituye a los
        del usuario (continuacion)."""
        base = self.cx.valores if valores is None else valores
        vals = dict(base)
        vals.update(campos)
        r = []
        for item in self.evolucion:
            total = 0.0
            for t in item["resto"]:
                total = total - t.signo * t.valor(valores) * evaluar_poli(t.P, vals, derivadas)
            r.append(total / self.masa(item, valores))
        return r

    def rhs_homogeneo(self, u, valores=None):
        """F(u) con todas las derivadas espaciales nulas (estado homogeneo)."""
        coords = set(self.cx.coordenadas)

        def derivadas(a):
            if a[0] == "o" or a[2] in coords:
                return 0.0
            raise NoEvaluable("derivada", "derivada temporal en el miembro derecho")
        campos = {item["campo"]: u[i] for i, item in enumerate(self.evolucion)}
        r = self.rhs(campos, derivadas, valores)
        return np.array(r, dtype=complex if any(np.iscomplexobj(np.asarray(x)) for x in r) else float)


def clave_derivada(a, campos):
    """(campo, variable, orden) de una derivada de un campo; None si es de
    otra expresion (funcion declarada, derivada mixta)."""
    if a[0] != "d":
        return None
    i = a[1].monomio_unico()
    if i and i[0] == 1 and len(i[1]) == 1 and i[1][0][1] == 1 and i[1][0][0][0] == "s" and i[1][0][0][1] in campos:
        return i[1][0][0][1], a[2], a[3]
    return None


def _explicitos(P, indep):
    r = set()
    for m in P.t:
        for a, _ in m:
            if a[0] == "s" and a[1] in indep:
                r.add(a[1])
            elif a[0] in ("f", "c"):
                for p in a[2]:
                    r |= _explicitos(p, indep)
            elif a[0] == "b":
                r |= _explicitos(a[1], indep)
            elif a[0] == "p":
                r |= _explicitos(a[1], indep) | _explicitos(a[2], indep)
    return r


def estudiar(prep, cuerpo, opciones):
    cx = Contexto(prep, cuerpo, opciones)
    pedidos = opciones.get("analisis") or list(ANALISIS)
    r = {}
    from . import asintotica, dinamica, simetrias, simulacion
    funciones = {"estructura": estructura, "sensibilidad": sensibilidad, "valores": valores,
                 "asintotica": asintotica.analizar, "escalas": dinamica.escalas, "simetrias": simetrias.analizar,
                 "estabilidad": dinamica.estabilidad, "continuacion": dinamica.continuacion, "simulacion": simulacion.simular}
    sistema = None
    for nombre in ANALISIS:
        if nombre not in pedidos:
            continue
        try:
            if nombre in ("asintotica", "escalas", "estabilidad", "continuacion", "simulacion"):
                if sistema is None:
                    sistema = SistemaNumerico(cx)
                r[nombre] = funciones[nombre](cx, sistema)
            else:
                r[nombre] = funciones[nombre](cx)
        except NoEvaluable as e:
            r[nombre] = estado("no_soportado", e.mensaje, codigo=e.codigo)
        except (A.ErrorAlgebraico, A.NoSoportado) as e:
            r[nombre] = estado("no_soportado", e.mensaje, codigo=e.codigo)
    return r, cx.diagnosticos


def requiere(sistema, extra=()):
    """Estado 'requiere_datos' si faltan valores para el sistema numerico."""
    faltan = sorted(set(sistema.faltan) | set(extra))
    if faltan:
        return estado("requiere_datos", "faltan valores numericos: " + ", ".join(faltan), faltan=faltan)
    return None


_ = (copy, _sim)
