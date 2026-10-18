"""
Traza completa del desarrollo matematico de una formulacion.

Cada paso es un dato del calculo efectivamente realizado, en su orden: no
es una explicacion generica reconstruida a partir del resultado final. El
formato es el `PasoDesarrollo` propuesto por el cliente
(frontend/app/adimensionalizacion/contrato.ts):

    {id, operacion, regla, justificacion, antes, despues, supuestos, objetosAfectados}

con `antes`/`despues` = {tipo: "expresion", expresion} | {tipo: "igualdad", igualdad}.
Las operaciones separan cambios de variables, identidades algebraicas y la
resolucion de objetivos; este nucleo no introduce hipotesis fisicas (no
desprecia terminos), asi que nunca emite 'hipotesis_fisica'.
"""

from fractions import Fraction

from . import algebra as A
from .dimensional import dim_texto, dimension_de
from .exportar_texto import texto
from .transformacion import presentar_lado, reescribir, termino_ast


def _E(x):
    return {"tipo": "expresion", "expresion": x}


def _I(i, izq, der):
    return {"tipo": "igualdad", "igualdad": {"id": i, "izquierda": izq, "derecha": der}}


def _sim(i):
    return {"tipo": "simbolo", "id": i}


def _num(v):
    return {"tipo": "numero", "valor": v}


def _contiene_derivadas(e):
    if e["tipo"] in ("derivada", "gradiente", "divergencia", "laplaciano"):
        return True
    hijos = list(e.get("argumentos", [])) + [e[k] for k in ("numerador", "denominador", "base", "exponente", "expresion") if k in e]
    return any(_contiene_derivadas(h) for h in hijos)


def construir(prep, d):
    """d: datos de la formulacion (ver formulacion.formular)."""
    pasos = []

    def paso(operacion, regla, justificacion, antes, despues, supuestos=(), objetos=()):
        pasos.append({"id": f"P{len(pasos) + 1}", "operacion": operacion, "regla": regla, "justificacion": justificacion,
                      "antes": antes, "despues": despues, "supuestos": list(supuestos), "objetosAfectados": list(objetos)})

    an = prep.analisis
    origen = {s["id"]: s for s in an["simbolos"]}
    dims = an["dimensiones"]
    escalas_pos = [f"{e['id']} > 0" for e in prep.escalas if e["papel"] == "escala"]
    restr = {r["id"]: r for r in d["restricciones"]}

    def restricciones_de(simbolos):
        return [f"{r['id']}: {r['tipo']} {texto(r['expresion'])}" for r in d["restricciones"]
                if r["tipo"] in ("no_nulo", "positivo", "negativo", "signo") and (_simbolos(r["expresion"]) & simbolos)]

    # 1. Analisis dimensional e inferencia.
    for eq in prep.modelo["ecuaciones"]:
        usados = _simbolos(eq["izquierda"]) | _simbolos(eq["derecha"])
        dim = dimension_de(eq["izquierda"], dims, prep.funciones_dim)
        inferidos = sorted(s for s in usados if origen.get(s, {}).get("origen") in ("inferida", "unidad"))
        detalle = "; ".join(f"[{s}] = {dim_texto(dims[s])} ({origen[s]['origen']})" for s in inferidos)
        paso("analisis_dimensional", "homogeneidad dimensional",
             f"todos los terminos de '{eq['id']}' tienen dimension {dim_texto(dim)}" + (f"; {detalle}" if detalle else ""),
             _I(eq["id"], eq["izquierda"], eq["derecha"]), _I(eq["id"], eq["izquierda"], eq["derecha"]),
             ["dimensiones exactas con exponentes racionales"], [eq["id"]] + inferidos)

    # 2. Cambios de variables (mapas) y su inversa demostrada.
    for m in prep.mapas:
        dom = [f"{x} {'> 0' if s == 'positivo' else '< 0'}" for x, s in ((m["variable"], m["dominio"]["original"]), (m["nuevo"], m["dominio"]["nuevo"])) if s]
        paso("cambio_variables", f"mapa {m['familia']}",
             f"{m['variable']} = g({m['nuevo']}) con inversa h demostrada: h(g({m['nuevo']})) = {m['nuevo']} y g(h({m['variable']})) = {m['variable']} en forma canonica",
             _I(f"mapa:{m['variable']}", _sim(m["variable"]), m["directa"]), _I(f"inversa:{m['variable']}", _sim(m["nuevo"]), m["inversa"]),
             dom + [f"{c} > 0" for c in m["constantes"] if prep.por_id[c]["papel"] == "escala"], [m["variable"], m["nuevo"]] + m["constantes"])
        if m["rol"] in A.INDEPENDIENTES:
            paso("regla_cadena", "derivada respecto de la nueva variable",
                 f"d/d{m['variable']} = (1/g'({m['nuevo']})) d/d{m['nuevo']}" + (" (g' constante)" if m["lineal"] else " (se anida para ordenes superiores)"),
                 _I(f"mapa:{m['variable']}", _sim(m["variable"]), m["directa"]),
                 _I(f"jacobiano:{m['variable']}", {"tipo": "derivada", "expresion": _sim(m["variable"]), "respecto": m["nuevo"], "orden": 1}, m["dphi"]),
                 [] if m["lineal"] else [f"g'({m['nuevo']}) distinto de cero"], [m["variable"], m["nuevo"]])

    def pasos_igualdad(pub, operacion_base=None):
        reg = pub["reg"]
        ambito = reg["id"]
        op = (lambda o: operacion_base or o)
        # Sustitucion y regla de la cadena termino a termino.
        for lado in ("izquierda", "derecha"):
            for t in reg["lados"][lado]:
                pa = reescribir(t["original"], prep.directa_A, {})
                paso(op("sustitucion"), "sustitucion de variables", f"termino {t['id']}", _E(t["original"]), _E(pa),
                     [f"{m['variable']} = {texto(m['directa'])}" for m in prep.mapas if m["variable"] in _simbolos(t["original"]) | _variables(t["original"])],
                     [t["id"]])
                pb = reescribir(pa, {}, prep.directa_B)
                if pb != pa:
                    paso(op("regla_cadena"), "regla de la cadena", f"derivadas de {t['id']} respecto de las nuevas variables", _E(pa), _E(pb),
                         ["escalas y referencias constantes", "coordenadas cartesianas"], [t["id"]])
                col = A.ast_suma([termino_ast(c, n) for n, c in t["partes"]])
                pc = prep.escalar_llamadas(pb, t["id"])
                if pc != pb:
                    paso(op("sustitucion"), "escala declarada de funcion", f"funciones de {t['id']} escritas con su escala declarada",
                         _E(pb), _E(pc), prep.supuestos_funciones(), [t["id"]])
                    pb = pc
                if _contiene_derivadas(pb) and prep.modo_t == "expandir":
                    paso(op("regla_cadena"), "desarrollo de derivadas (producto, potencia y cadena)",
                         f"se desarrollan las derivadas de los mapas no lineales en {t['id']}, incluidos los terminos adicionales", _E(pb), _E(col),
                         ["funciones declaradas sin desarrollar"], [t["id"]])
                elif pb != col:
                    paso(op("factorizacion"), "linealidad: extraccion de factores constantes",
                         f"coeficiente y nucleo de {t['id']}", _E(pb), _E(col), ["escalas y parametros constantes"], [t["id"]])
        for regla, antes, despues, supuestos in reg["pasos"]:
            nombre = {"sustitucion_de_variables": ("sustitucion", "igualdad completa antes de cancelar factores"),
                      "regla_de_la_cadena": ("regla_cadena", "igualdad completa tras la regla de la cadena"),
                      "escala_declarada_de_funciones": ("sustitucion", "igualdad completa con la escala declarada de las funciones"),
                      "linealidad_y_agrupacion": ("agrupacion", "agrupacion de coeficientes por nucleo"),
                      "division_por_factor_global": ("normalizacion", "division por el factor global"),
                      "sustitucion_de_escalas_dadas": ("sustitucion", "sustitucion de escalas dadas por expresion")}[regla]
            sup = list(supuestos)
            if regla == "division_por_factor_global":
                sup += restricciones_de(_simbolos(A.ast(reg["F"]))) or [f"{texto(A.ast(reg['F']))} distinto de cero (producto de escalas positivas y parametros no nulos)"]
            paso(op(nombre[0]), nombre[1], f"{reg['ambito']} '{ambito}'", _I(ambito, antes["izquierda"], antes["derecha"]),
                 _I(ambito, despues["izquierda"], despues["derecha"]), sup, [ambito])

    publicaciones = d["publicaciones"]
    for pub in publicaciones:
        if pub["tipo"] == "ecuacion":
            pasos_igualdad(pub)

    # 3. Objetivos y resolucion exacta de escalas.
    por_termino = {t["id"]: t for t in prep.terminos.values()}
    for est in d["estados"]:
        t = por_termino.get(est.get("terminoId"))
        if t is None or est["estado"] == "conservado":
            paso("normalizacion", "objetivo", f"{est['id']}: {est['estado']} ({est.get('motivo', '')})",
                 _E(t["original"] if t else _num(0)), _E(t["original"] if t else _num(0)), [], [est["id"]] + ([t["id"]] if t else []))
            continue
        coef = A.ast_suma([A.ast(c) for _, c in t["partes_F"]])
        objetivo = est.get("valorObjetivo")
        rel = est.get("relacion")
        just = f"{est['id']}: {est['estado']}; {est.get('motivo', '')}"
        if est.get("responsables"):
            just += f"; responsables: {', '.join(est['responsables'])}"
        antes = _I(est["id"], coef, _num(objetivo)) if objetivo is not None else _E(coef)
        if est["estado"] in ("satisfecho", "dependiente"):
            # Coeficiente con las escalas resueltas sustituidas, antes de simplificar.
            despues = _I(est["id"], A.sustituir(coef, d["mapa_sol"]) if d["mapa_sol"] else est["coeficienteFinal"], _num(objetivo))
        elif rel:
            despues = _I(est["id"], rel["izquierda"], rel["derecha"])
        else:
            despues = antes
        paso("normalizacion", "objetivo: |coeficiente efectivo| = 1 con signo", just, antes, despues,
             escalas_pos + [f"{s} con signo declarado" for s in sorted(d["signos_usados"])], [est["id"], t["id"]])
    for fila in d["filas"]:
        S = fila["piv"]
        izq = A.ast(A.monomio(1, {("s", c): x for c, x in fila["coef"].items()}))
        der = A.ast(A.monomio(1, dict(fila["rhs"])))
        libres = [c for c in fila["coef"] if c != S]
        paso("normalizacion", "resolucion exacta por rango",
             f"rango {d['rango']}; se despeja {S}" + (f" en funcion de las escalas libres {', '.join(libres)}" if libres else "")
             + "; raiz positiva por ser escalas positivas",
             _I(f"fila:{S}", izq, der), _I(f"escala:{S}", _sim(S), d["valor"][S]), escalas_pos, [S] + libres)
    for S in d["libres"]:
        paso("normalizacion", "familia libre", f"{S} no queda determinada: la formulacion es una familia parametrizada por {S}",
             _E(_sim(S)), _E(_sim(S)), [f"{S} > 0"], [S])

    # 4. Sustitucion de escalas determinadas, grupos y presentacion.
    for pub in publicaciones:
        if pub["tipo"] != "ecuacion":
            continue
        reg, ig = pub["reg"], pub["igualdad"]
        if d["mapa_sol"]:
            paso("sustitucion", "sustitucion de escalas determinadas", f"ecuacion '{reg['id']}'",
                 _I(reg["id"], pub["antes"]["izquierda"], pub["antes"]["derecha"]), _I(reg["id"], pub["desarrollada"]["izquierda"], pub["desarrollada"]["derecha"]),
                 ["solucion exacta de los objetivos"], [reg["id"]] + sorted(d["mapa_sol"]))
        if pub["desarrollada"] != {"izquierda": ig["izquierda"], "derecha": ig["derecha"]}:
            paso("simplificacion", "factorizacion de coeficientes comunes", "presentacion factorizada: misma igualdad",
                 _I(reg["id"], pub["desarrollada"]["izquierda"], pub["desarrollada"]["derecha"]), _I(reg["id"], ig["izquierda"], ig["derecha"]), [], [reg["id"]])
    for g in d["grupos"]:
        paso("agrupacion", "definicion de grupo adimensional" if g["adimensional"] else "definicion de coeficiente",
             f"{g['id']} = {texto(g['definicion'])}; dimension {'1' if g['adimensional'] else 'no nula'}; usos: {', '.join(g['usos'])}"
             + ("; coeficiente interno" if g["interno"] else "") + (f"; inverso de {g['inversoDe']}" if g["inversoDe"] else ""),
             _E(g["definicion"]), _E(g["definicion"]), [], [g["id"]] + g["usos"])

    # 5. Geometria y condiciones.
    for dom, pub in zip(prep.dominios, d["dominios"]):
        for lado in ("desde", "hasta"):
            paso("geometria_condiciones", "extremo del dominio", f"{dom['original']['variableId']} -> {pub['variableId']} con la inversa del mapa",
                 _E(dom["original"][lado]), _E(pub[lado]), escalas_pos, [pub["id"]])
    lugares = {c["ecuacion"]["id"]: c["lugar"] for c in d.get("condiciones", []) if "lugar" in c}
    for pub in publicaciones:
        if pub["tipo"] == "condicion":
            lugar = lugares.get(pub["reg"]["id"])
            if lugar:
                paso("geometria_condiciones", "ubicacion de la condicion",
                     f"'{pub['reg']['id']}' se impone en el extremo '{lugar['extremo']}' del dominio, transformado con la inversa del mapa",
                     _I(f"lugar:{pub['reg']['id']}", _sim(lugar["variableOriginal"]), lugar["original"]),
                     _I(f"lugar:{pub['reg']['id']}", _sim(lugar["variableId"]), lugar["valor"]), escalas_pos, [pub["reg"]["id"]])
            pasos_igualdad(pub, "geometria_condiciones")
            if d["mapa_sol"]:
                ig = pub["igualdad"]
                paso("geometria_condiciones", "sustitucion de escalas determinadas", f"condicion '{pub['reg']['id']}'",
                     _I(ig["id"], pub["antes"]["izquierda"], pub["antes"]["derecha"]), _I(ig["id"], ig["izquierda"], ig["derecha"]), [], [pub["reg"]["id"]])

    # 6. Sustitucion inversa hasta recuperar el original.
    for rec in d["reconstrucciones"]:
        paso("verificacion_inversa", "sustitucion inversa y comparacion canonica",
             f"F * h(publicada) frente al original de '{rec['ambito']}': {rec['estado']}",
             _I(rec["ambito"], rec["publicada"]["izquierda"], rec["publicada"]["derecha"]),
             _I(rec["ambito"], rec["izquierda"], rec["derecha"]),
             [f"{r['id']}: {r['tipo']} {texto(r['expresion'])}" for r in restr.values() if r["tipo"] != "igualdad"], [rec["ambito"]])
    return pasos


def _simbolos(e):
    if e["tipo"] == "simbolo":
        return {e["id"]}
    r = set()
    for a in e.get("argumentos", []):
        r |= _simbolos(a)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            r |= _simbolos(e[k])
    return r


def _variables(e):
    r = set()
    if e["tipo"] == "derivada":
        r.add(e["respecto"])
    if e["tipo"] in ("gradiente", "divergencia", "laplaciano"):
        r |= set(e["coordenadas"])
    for a in e.get("argumentos", []):
        r |= _variables(a)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            r |= _variables(e[k])
    return r


_ = (Fraction, presentar_lado)
