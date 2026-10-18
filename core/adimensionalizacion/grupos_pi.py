"""
Grupos Pi: espacio nulo racional de la matriz dimensional de los
parametros y constantes del modelo.

Esto es un INVENTARIO de productos adimensionales, separado de los
coeficientes efectivos de las ecuaciones (que salen de la transformacion).
Una base no es unica: cada eleccion de "cantidades repetidas" independientes
da otra. Se recorren esas elecciones bajo un presupuesto explicito, se
descartan las bases cuyos exponentes superan las cotas pedidas y se
eliminan duplicados (una base es la misma si tiene los mismos grupos salvo
inversion). Nunca se afirma exhaustividad de una familia infinita: las
combinaciones racionales de una base son otras bases validas.
"""

import itertools
from fractions import Fraction

from . import algebra as A
from .dimensional import dim_texto
from .racional import espacio_nulo


def _exponentes_json(v):
    return {k: {"n": x.numerator, "d": x.denominator} for k, x in v.items()}


def _definicion(v):
    return A.ast(A.monomio(1, {("s", k): x for k, x in v.items()}))


def _clave_grupo(v):
    # Un grupo y su inverso son el mismo grupo para comparar bases.
    primero = sorted(v)[0]
    signo = 1 if v[primero] > 0 else -1
    return tuple(sorted((k, signo * x) for k, x in v.items()))


def grupos_pi(modelo, analisis, max_exponente, max_denominador, presupuesto=60):
    usados = {s["id"] for s in analisis["simbolos"] if s["origen"] != "sin_uso"}
    dims = analisis["dimensiones"]
    cantidades, excluidas = [], []
    for s in modelo["simbolos"]:
        if s["rol"] not in ("parametro", "constante"):
            continue
        if s["id"] not in usados:
            excluidas.append({"id": s["id"], "motivo": "no aparece en el modelo"})
        elif not s["constante"]:
            excluidas.append({"id": s["id"], "motivo": "coeficiente variable: no es una cantidad caracteristica"})
        elif dims.get(s["id"]) is None:
            excluidas.append({"id": s["id"], "motivo": "dimension no determinada"})
        elif s["signo"] == "cero":
            excluidas.append({"id": s["id"], "motivo": "declarado nulo: no puede formar parte de un producto adimensional"})
        else:
            cantidades.append(s["id"])
    bases = sorted({b for q in cantidades for b in dims[q]})
    matriz = [{q: dims[q].get(b, Fraction(0)) for q in cantidades if dims[q].get(b)} for b in bases]
    referencia, rango = espacio_nulo(matriz, cantidades)
    n_grupos = len(cantidades) - rango
    def dentro_de_cotas(base):
        return all(abs(x.numerator) <= max_exponente * x.denominator and x.denominator <= max_denominador
                   for v in base for x in v.values())

    vistas = set()
    alternativas, omitidas, duplicadas, revisadas, total = [], 0, 0, 0, 0
    limitado = False
    if n_grupos > 0:
        for repetidas in itertools.combinations(cantidades, rango):
            total += 1
            if revisadas >= presupuesto:
                limitado = True
                continue
            revisadas += 1
            orden = list(repetidas) + [q for q in cantidades if q not in repetidas]
            base, _ = espacio_nulo(matriz, orden)
            if set(_libres(base, orden)) & set(repetidas):
                continue  # repetidas dependientes: no forman base
            clave = frozenset(_clave_grupo(v) for v in base)
            if clave in vistas:
                duplicadas += 1
                continue
            if not dentro_de_cotas(base):
                omitidas += 1
                continue
            vistas.add(clave)
            alternativas.append((repetidas, base, _libres(base, orden)))
    libres_ref = alternativas[0][2] if alternativas else []
    ref_base = alternativas[0][1] if alternativas else []
    publicadas = []
    for i, (repetidas, base, _) in enumerate(alternativas):
        bid = f"B{i + 1}"
        grupos = [{"id": f"{bid}.P{j + 1}", "exponentes": _exponentes_json(v), "definicion": _definicion(v)} for j, v in enumerate(base)]
        mapa = {}
        for g, v in zip(grupos, base):
            # La base de referencia B1 vale 1 en su columna libre y 0 en las
            # demas libres: las coordenadas se leen directamente y se verifican.
            coords = {j: v.get(f, Fraction(0)) for j, f in enumerate(libres_ref)}
            recon = {}
            for j, x in coords.items():
                for q, y in ref_base[j].items():
                    recon[q] = recon.get(q, 0) + x * y
            assert {q: x for q, x in recon.items() if x} == v, "cambio de base inconsistente"
            mapa[g["id"]] = {f"B1.P{j + 1}": {"n": x.numerator, "d": x.denominator} for j, x in coords.items() if x}
        publicadas.append({"id": bid, "repetidas": list(repetidas), "grupos": grupos, "enReferencia": mapa})
    return {
        "estado": "calculado" if cantidades else "sin_cantidades",
        "cantidades": cantidades,
        "excluidas": excluidas,
        "matriz": {"bases": bases, "filas": [{q: {"n": x.numerator, "d": x.denominator} for q, x in fila.items()} for fila in matriz],
                   "dimensiones": {q: dim_texto(dims[q]) for q in cantidades}},
        "rango": rango,
        "numeroGrupos": n_grupos,
        "bases": publicadas,
        "cobertura": {"eleccionesDeRepetidas": total, "revisadas": revisadas, "basesDistintas": len(publicadas),
                      "omitidasPorCotas": omitidas, "duplicadas": duplicadas, "limitadoPorPresupuesto": limitado,
                      "cotas": {"maxExponente": max_exponente, "maxDenominador": max_denominador},
                      "nota": "cualquier producto de potencias racionales de los grupos de una base es otro grupo valido; la lista no es exhaustiva"},
    }, libres_ref


def _libres(base, orden):
    """Columna libre de cada vector de una base de espacio nulo (la que vale 1
    y no aparece en los demas)."""
    libres = []
    for v in base:
        for q in reversed(orden):
            if v.get(q) == 1 and all(w.get(q, 0) == 0 for w in base if w is not v):
                libres.append(q)
                break
    return libres


def expresar_en_referencia(coef, cantidades, libres_ref, referencia_ids):
    """Coordenadas de un grupo (Poli monomial solo en cantidades) en la base
    de referencia, o None si no es expresable."""
    u = coef.monomio_unico()
    if u is None:
        return None
    _, m = u
    v = {}
    for a, e in m:
        if a[0] == "s" and a[1] in cantidades:
            v[a[1]] = e
        elif a[0] == "f" and a[1] == "abs":
            inner = a[2][0].monomio_unico()
            if not inner or len(inner[1]) != 1 or inner[1][0][0][0] != "s" or inner[1][0][0][1] not in cantidades:
                return None
            v[inner[1][0][0][1]] = v.get(inner[1][0][0][1], 0) + e
        else:
            return None
    return {rid: {"n": v.get(f, Fraction(0)).numerator, "d": v.get(f, Fraction(0)).denominator}
            for rid, f in zip(referencia_ids, libres_ref) if v.get(f, 0) != 0}, v
