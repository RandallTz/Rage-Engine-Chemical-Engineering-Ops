"""
Validacion del nucleo de adimensionalizacion (A0-A3 y exploracion).

Cubre las pruebas de aceptacion del plan
(docs/history/frontend/plan-nondimensionalization-equations.md, secciones 3 y 8) que
corresponden al alcance implementado: contrato, analisis dimensional,
transformacion por escalas dadas, objetivos y formas multiples, signos,
ceros, condiciones, sistemas de varios campos, grupos Pi y exploracion.

Las expectativas se comparan en FORMA CANONICA (no como texto), con los
signos declarados del modelo: dos expresiones algebraicamente iguales bajo
los supuestos publicados se aceptan aunque se escriban distinto.

Ejecutar desde la raiz del proyecto:
    python tests/validar_adimensionalizacion.py
"""

import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.adimensionalizacion import algebra as A
from core.adimensionalizacion import formulacion as F
from core.adimensionalizacion import capacidades, procesar
from core.adimensionalizacion.exportar_texto import texto
from casos_adimensionalizacion import (FORMAS_SECCION3, OBJ_A, OBJ_D, OBJ_K, TERMINO_A, TERMINO_K, cantidad, coc, d,
                                       dim, div, documento, escala, expresion, forma_seccion3, fun, grad, igualdad, lap, llam, n,
                                       neg, objetivo, pot, prod, reaccion_difusion, s, simbolo, solicitud, suma)

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle and not ok else ''}")
    if not ok:
        fallos.append(nombre)


def transformar(doc):
    return procesar(solicitud(doc))


def ctx_de(doc, r=None):
    simbolos = {x["id"]: {"rol": x["rol"], "constante": x["constante"], "dependeDe": set(x["dependeDe"]), "signo": x["signo"]}
                for x in doc["modelo"]["simbolos"]}
    for x in (r or {}).get("simbolos", []):
        if x["rol"] == "escala":
            simbolos[x["id"]] = {"rol": "escala", "constante": True, "dependeDe": set(), "signo": "positivo"}
        else:
            simbolos[x["id"]] = {"rol": x["rolOrigen"], "constante": False, "dependeDe": set(x["dependeDe"]), "signo": "desconocido"}
    funciones = {f["id"]: {"dependeDe": set(f["dependeDe"])} for f in doc["modelo"]["funciones"]}
    return A.Contexto(simbolos, funciones)


def igual(ctx, a, b):
    return A.canonica(a, ctx, "cartesiano") == A.canonica(b, ctx, "cartesiano")


def igualdad_equivale(ctx, publicada, izq, der):
    """La igualdad publicada es exactamente izq = der (lado a lado)."""
    return igual(ctx, publicada["izquierda"], izq) and igual(ctx, publicada["derecha"], der)


def escala_de(r, variable):
    return next(e for e in r["escalas"] if e["simboloId"] == variable)


def objetivo_de(r, oid):
    return next(o for o in r["objetivos"] if o["id"] == oid)


def certificado(r):
    return r.get("equivalencia", {}).get("estado") == "demostrada"


def diag(r, codigo):
    return [x for x in r["diagnosticos"] if x["codigo"] == codigo]


print("=" * 78)
print("A0 -- contrato, vinculo y capacidades")
print("=" * 78)

doc = forma_seccion3([])
r = transformar(doc)
check("documento de la entrada espacial se transforma", r["estado"] == "correcto")
check("resultado con formato y version", r["formato"] == "adimensionalizacion.resultado" and r["version"] == 1)
check("vinculo: modelo, revision, forma y eleccion completa",
      r["vinculo"]["modeloId"] == "modelo-prueba" and r["vinculo"]["modeloRevision"] == 1 and r["vinculo"]["formaId"] == "forma-1"
      and r["vinculo"]["eleccion"]["escalas"] == doc["formas"][0]["escalas"])
doc2 = copy.deepcopy(doc)
doc2["formas"][0]["escalas"][0]["valor"] = cantidad(2, "s")
r2 = transformar(doc2)
check("la firma cambia al cambiar una escala en la MISMA forma", r2["vinculo"]["firma"] != r["vinculo"]["firma"] and r2["vinculo"]["formaId"] == r["vinculo"]["formaId"])
check("la firma es reproducible", transformar(doc)["vinculo"]["firma"] == r["vinculo"]["firma"])

for nombre, cambiar, ruta in [
    ("version desconocida", lambda x: x["documento"].__setitem__("version", 3), "version"),
    ("campo desconocido", lambda x: x["documento"].__setitem__("resultado", {}), "documento"),
    ("exponente no entero", lambda x: x["documento"]["modelo"]["simbolos"][0]["dimension"]["T"].__setitem__("n", 0.5), "simbolos[0]"),
    ("referencia inexistente", lambda x: x["documento"]["modelo"]["ecuaciones"][0].__setitem__("derecha", s("fantasma")), "ecuaciones[0].derecha"),
    ("operador fuera del contrato", lambda x: x["documento"]["modelo"]["ecuaciones"][0].__setitem__("derecha", {"tipo": "latex", "valor": "c"}), "ecuaciones[0].derecha"),
    ("solicitud con campo extra", lambda x: x.__setitem__("extra", 1), "solicitud"),
]:
    sol = solicitud(doc)
    cambiar(sol)
    rr = procesar(sol)
    check(f"rechaza {nombre} con ruta", rr["estado"] == "rechazado" and "ecuaciones" not in rr and rr["diagnosticos"][0]["ruta"].startswith(ruta),
          json.dumps(rr["diagnosticos"], ensure_ascii=False))

viejo = forma_seccion3([])
viejo["modelo"]["revision"] = 2
rr = transformar(viejo)
check("forma de una revision anterior: rechazada sin ecuaciones", rr["estado"] == "rechazado" and diag(rr, "forma_desactualizada") and "ecuaciones" not in rr)
cap = capacidades()
check("capacidades publicadas con limites", "transformar" in cap["operaciones"] and cap["noSoportado"])

# Dos expresiones distintas con el mismo esquema: temporal pura.
temporal = documento([simbolo("t", "tiempo", dim(T=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t"]),
                      simbolo("k", "parametro", dim(T=-1)), simbolo("a", "parametro", dim(N=-1, L=3, T=-1))],
                     [igualdad("balance", d(s("c"), "t"), suma(TERMINO_K, TERMINO_A))], [escala("t"), escala("c")])
check("entrada temporal con el mismo esquema", transformar(temporal)["estado"] == "correcto")

an = procesar(solicitud(doc, "analizar"))
ids = [t["id"] for t in an["terminos"]]
check("analizar publica terminos con identidades de ruta",
      ids == ["balance:ecuaciones[0].izquierda", "balance:ecuaciones[0].derecha.argumentos[0]",
              "balance:ecuaciones[0].derecha.argumentos[1]", "balance:ecuaciones[0].derecha.argumentos[2]"], str(ids))

print()
print("=" * 78)
print("A1 -- analisis dimensional")
print("=" * 78)

check("modelo compatible", an["dimensional"]["estado"] == "compatible")

simb, ecs, doms = reaccion_difusion()
mal = copy.deepcopy(ecs)
mal[0]["derecha"]["argumentos"].append(s("a"))
rr = procesar(solicitud(documento(simb, mal, [escala("t")]), "analizar"))
check("suma incompatible: estado y ruta del termino",
      rr["dimensional"]["estado"] == "incompatible" and diag(rr, "dimension_incompatible")[0]["ruta"] == "ecuaciones[0].derecha.argumentos[3]",
      json.dumps(rr["diagnosticos"], ensure_ascii=False))
rr = transformar(documento(simb, mal, [escala("t")]))
check("transformar rechaza una suma incompatible sin publicar ecuaciones", rr["estado"] == "rechazado" and "ecuaciones" not in rr)

for nombre, termino, esperado in [
    ("exp de un campo dimensional", prod(s("k"), fun("exp", s("c"))), "incompatible"),
    ("log de un campo dimensional", prod(s("k"), s("c"), fun("log", s("c"))), "incompatible"),
    ("log de un cociente adimensional", prod(s("k"), s("c"), fun("log", coc(s("c"), prod(s("k"), coc(s("a"), pot(s("k"), 2)), pot(s("a"), -1), s("k"))))), "incompatible"),
    ("exponente variable con base dimensional", pot(s("c"), s("k")), "incompatible"),
]:
    e = copy.deepcopy(ecs)
    e[0]["derecha"] = termino
    rr = procesar(solicitud(documento(simb, e, []), "analizar"))
    check(f"{nombre}: {esperado}", rr["dimensional"]["estado"] == esperado, rr["dimensional"]["estado"])

# exp con argumento adimensional: k t es adimensional.
e = copy.deepcopy(ecs)
e[0]["derecha"] = prod(s("k"), s("c"), fun("exp", neg(prod(s("k"), s("t")))))
check("exp(-k t) compatible", procesar(solicitud(documento(simb, e, []), "analizar"))["dimensional"]["estado"] == "compatible")

# Inferencia: k y a pendientes, determinadas por la suma.
sim_inf = copy.deepcopy(simb)
for x in sim_inf:
    if x["id"] in ("k", "a"):
        x["dimension"] = None
rr = procesar(solicitud(documento(sim_inf, ecs, []), "analizar"))
dims = {x["id"]: x for x in rr["dimensional"]["simbolos"]}
check("dimensiones inferidas de k y a", rr["dimensional"]["estado"] == "compatible" and dims["k"]["origen"] == "inferida"
      and dims["k"]["dimension"] == {"T": {"n": -1, "d": 1}} and dims["a"]["dimension"] == {"L": {"n": 3, "d": 1}, "N": {"n": -1, "d": 1}, "T": {"n": -1, "d": 1}})

# Indeterminada: k1 k2 c con ambas pendientes.
sim_ind = copy.deepcopy(simb) + [simbolo("k2", "parametro", None)]
for x in sim_ind:
    if x["id"] == "k":
        x["dimension"] = None
e = copy.deepcopy(ecs)
e[0]["derecha"] = prod(s("k"), s("k2"), s("c"))
rr = procesar(solicitud(documento(sim_ind, e, []), "analizar"))
check("producto de dos pendientes: indeterminado", rr["dimensional"]["estado"] == "indeterminado" and len(diag(rr, "dimension_indeterminada")) == 2)
rr = transformar(documento(sim_ind, e, [escala("t")]))
check("transformar con dimensiones indeterminadas: requiere datos, sin ecuaciones", rr["estado"] == "requiere_datos" and "ecuaciones" not in rr
      and rr["dimensional"]["faltantes"])

# Entrada minima: todas las dimensiones pendientes. Se piden solo los datos
# indispensables y, al darlos, todo queda determinado.
sim_vacio = copy.deepcopy(simb)
for x in sim_vacio:
    x["dimension"] = None
rr = procesar(solicitud(documento(sim_vacio, ecs, [], dominios=doms), "analizar"))
falt = rr["dimensional"]["faltantes"]
check("todo pendiente: indeterminado con datos indispensables (las variables)", rr["dimensional"]["estado"] == "indeterminado"
      and sorted(falt) == ["c", "t", "x"] and diag(rr, "datos_indispensables"), str(falt))
for x in sim_vacio:
    if x["id"] in falt:
        x["dimension"] = next(y for y in simb if y["id"] == x["id"])["dimension"]
rr = procesar(solicitud(documento(sim_vacio, ecs, [], dominios=doms), "analizar"))
check("al declarar solo esos datos, todas las demas se infieren", rr["dimensional"]["estado"] == "compatible"
      and all(x["origen"] in ("declarada", "inferida") for x in rr["dimensional"]["simbolos"])
      and next(x for x in rr["dimensional"]["simbolos"] if x["id"] == "a")["dimension"] == {"L": {"n": 3, "d": 1}, "N": {"n": -1, "d": 1}, "T": {"n": -1, "d": 1}})
sim_cero = [simbolo("t", "tiempo", None), simbolo("c", "campo", None, ["t"])]
rr = procesar(solicitud(documento(sim_cero, [igualdad("e", d(s("c"), "t"), n(0))], []), "analizar"))
check("dc/dt = 0 no aporta datos: se piden c y t", sorted(rr["dimensional"]["faltantes"]) == ["c", "t"], str(rr["dimensional"]["faltantes"]))

# Contradictoria: k pendiente usada con dos dimensiones distintas.
e = copy.deepcopy(ecs)
e[0]["derecha"] = suma(prod(s("k"), s("c")), prod(pot(s("k"), 2), s("c")))
rr = procesar(solicitud(documento(sim_inf, e, []), "analizar"))
check("dimension contradictoria con simbolo implicado", rr["dimensional"]["estado"] == "incompatible"
      and "k" in diag(rr, "dimension_incompatible")[0].get("simbolos", []), json.dumps(rr["diagnosticos"], ensure_ascii=False))

# Unidades equivalentes producen el mismo modelo dimensional.
def con_unidad(u):
    x = copy.deepcopy(simb)
    for y in x:
        if y["id"] == "c":
            y["dimension"], y["unidad"] = None, u
    return procesar(solicitud(documento(x, ecs, []), "analizar"))

u1, u2 = con_unidad("mol/m^3"), con_unidad("mmol/L")
d1 = next(x for x in u1["dimensional"]["simbolos"] if x["id"] == "c")["dimension"]
d2 = next(x for x in u2["dimensional"]["simbolos"] if x["id"] == "c")["dimension"]
check("unidades equivalentes: misma dimension", d1 == d2 == {"L": {"n": -3, "d": 1}, "N": {"n": 1, "d": 1}})
x = copy.deepcopy(simb)
x[2]["unidad"] = "m/s"
rr = procesar(solicitud(documento(x, ecs, []), "analizar"))
check("unidad incompatible con la dimension declarada", diag(rr, "dimension_incompatible") and diag(rr, "dimension_incompatible")[0]["ruta"] == "simbolos[2].unidad")

# Ceros explicitos.
e = [igualdad("balance", d(s("c"), "t"), n(0))]
check("dc/dt = 0 compatible", procesar(solicitud(documento(simb, e, []), "analizar"))["dimensional"]["estado"] == "compatible")
e = [igualdad("balance", d(s("c"), "t"), suma(TERMINO_K, n(0)))]
check("suma con 0 explicito compatible", procesar(solicitud(documento(simb, e, []), "analizar"))["dimensional"]["estado"] == "compatible")
e = [igualdad("balance", d(s("c"), "t"), suma(TERMINO_K, n(1)))]
check("suma con 1 (adimensional) incompatible", procesar(solicitud(documento(simb, e, []), "analizar"))["dimensional"]["estado"] == "incompatible")

print()
print("=" * 78)
print("A2 -- transformacion por escalas dadas")
print("=" * 78)

# Temporal sin espacio: fuente constante, lineal y no lineal, escalas numericas.
sim_t = [simbolo("t", "tiempo", dim(T=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t"]),
         simbolo("r0", "parametro", dim(N=1, L=-3, T=-1)), simbolo("k", "parametro", dim(T=-1)), simbolo("a", "parametro", dim(N=-1, L=3, T=-1))]
for nombre, fuente, esperado in [
    ("fuente constante", s("r0"), lambda C, T: coc(prod(s("r0"), T), C)),
    ("fuente lineal", TERMINO_K, lambda C, T: prod(s("k"), T, s("c_ad"))),
    ("fuente no lineal", TERMINO_A, lambda C, T: prod(n(-1), s("a"), C, T, pot(s("c_ad"), 2))),
]:
    doc_t = documento(sim_t, [igualdad("balance", d(s("c"), "t"), fuente)], [escala("t", cantidad(2, "s")), escala("c", cantidad(0.5, "mol/L"))])
    rr = transformar(doc_t)
    ctx = ctx_de(doc_t, rr)
    ok = rr["estado"] == "correcto" and igualdad_equivale(ctx, rr["ecuaciones"][0]["igualdad"], d(s("c_ad"), "t_ad"), esperado(s("c_ref"), s("t_ref")))
    check(f"temporal, {nombre}: ecuacion y certificado", ok and certificado(rr), texto(rr["ecuaciones"][0]["igualdad"]["derecha"]) if rr["estado"] == "correcto" else rr["diagnosticos"])
check("escala con unidad convertida a SI (0.5 mol/L = 500 mol/m^3)",
      abs(next(x for x in rr["simbolos"] if x["id"] == "c_ref")["cantidad"]["valorSI"] - 500.0) < 1e-9,
      str(next(x for x in rr["simbolos"] if x["id"] == "c_ref")["cantidad"]))

a = transformar(documento(sim_t, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", cantidad(2, "s"))]))
b = transformar(documento(sim_t, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", cantidad(2000, "ms"))]))
check("escalas con unidades equivalentes: mismo valor SI y mismas ecuaciones",
      next(x for x in a["simbolos"] if x["id"] == "t_ref")["cantidad"]["valorSI"] == next(x for x in b["simbolos"] if x["id"] == "t_ref")["cantidad"]["valorSI"] == 2.0
      and a["ecuaciones"] == b["ecuaciones"])

# Normalizacion parcial: solo el tiempo.
rr = a
check("solo tiempo: normalizacion parcial con c conservada", rr["normalizacion"]["estado"] == "parcial"
      and rr["normalizacion"]["motivos"][0]["simbolos"] == ["c"])
check("solo tiempo: c sigue dimensional (no se etiqueta adimensional)",
      not any(x["id"] == "c" for x in rr["simbolos"]) and igualdad_equivale(ctx_de(documento(sim_t, [], []), rr), rr["ecuaciones"][0]["igualdad"], d(s("c"), "t_ad"), prod(s("k"), s("t_ref"), s("c"))))
check("solo tiempo: certificado", certificado(rr))

# Rechazos de escalas.
rr = transformar(documento(sim_t, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", cantidad(2, "m"))]))
check("escala de tiempo en metros: rechazada", rr["estado"] == "rechazado" and diag(rr, "dimension_incompatible"))
sim_T = sim_t + [simbolo("T", "campo", dim(Theta=1), ["t"], unidad="degC")]
rr = transformar(documento(sim_T, [igualdad("balance", d(s("T"), "t"), prod(s("k"), s("T")))], [escala("T", cantidad(300, "K"))]))
check("temperatura absoluta con desplazamiento: sin escala multiplicativa (A5)", rr["estado"] == "rechazado" and diag(rr, "temperatura_afin"))
sim_K = sim_t + [simbolo("T", "campo", dim(Theta=1), ["t"], unidad="K")]
rr = transformar(documento(sim_K, [igualdad("balance", d(s("T"), "t"), prod(s("k"), s("T")))], [escala("T", cantidad(300, "K"))]))
check("temperatura en K: escala multiplicativa admitida", rr["estado"] == "correcto" and certificado(rr))
rr = transformar(documento(sim_t, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", expresion(coc(n(1), s("c"))))]))
check("escala dada por una variable: rechazada", rr["estado"] == "rechazado" and diag(rr, "escala_no_constante"))
rr = transformar(documento(sim_t, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", expresion(s("a")))]))
check("escala por expresion con dimension equivocada: rechazada", rr["estado"] == "rechazado" and diag(rr, "dimension_incompatible"))
sim_neg = copy.deepcopy(sim_t)
sim_neg[3]["signo"] = "negativo"
rr = transformar(documento(sim_neg, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", expresion(coc(n(1), s("k"))))]))
check("escala 1/k con k < 0: rechazada (no se ocultan escalas negativas)", rr["estado"] == "rechazado" and diag(rr, "escala_negativa"))
rr = transformar(documento(sim_neg, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", expresion(coc(n(1), fun("abs", s("k")))))]))
check("escala 1/|k| con k < 0: el signo queda en la ecuacion", rr["estado"] == "correcto"
      and igual(ctx_de(documento(sim_neg, [], []), rr), rr["ecuaciones"][0]["igualdad"]["derecha"], neg(s("c")))
      and certificado(rr), texto(rr["ecuaciones"][0]["igualdad"]["derecha"]) if rr["estado"] == "correcto" else str(rr["diagnosticos"]))
sim_desc = copy.deepcopy(sim_t)
sim_desc[3]["signo"] = "desconocido"
rr = transformar(documento(sim_desc, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", expresion(coc(n(1), s("k"))))]))
check("escala 1/k con signo desconocido: supuesto de positividad publicado",
      rr["estado"] == "correcto" and any(x["tipo"] == "positivo" and "signo no determinado" in x["motivo"] for x in rr["restricciones"]))

# Coeficiente variable D(c): se conserva la divergencia y la funcion.
sim_v = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"])]
fD = {"id": "Dc", "nombre": "D", "entradas": [dim(N=1, L=-3)], "salida": dim(L=2, T=-1), "dependeDe": []}
doc_v = documento(sim_v, [igualdad("balance", d(s("c"), "t"), div(prod(llam("Dc", s("c")), grad(s("c"), "x")), "x"))],
                  [escala("t"), escala("c"), escala("x")], funciones=[fD])
rr = transformar(doc_v)
ctx = ctx_de(doc_v, rr)
pub = rr["ecuaciones"][0]["igualdad"]["derecha"] if rr["estado"] == "correcto" else None
check("D(c): divergencia y llamada conservadas", rr["estado"] == "correcto"
      and A.canonica(pub, ctx) == A.canonica(prod(coc(s("t_ref"), pot(s("x_ref"), 2)), div(prod(llam("Dc", prod(s("c_ref"), s("c_ad"))), grad(s("c_ad"), "x_ad")), "x_ad")), ctx),
      texto(pub) if pub else str(rr["diagnosticos"]))
check("D(c): normalizacion parcial (nucleo dimensional), no completa",
      rr["normalizacion"]["estado"] == "parcial" and rr["normalizacion"]["motivos"][0]["codigo"] == "nucleos_dimensionales")
check("D(c): certificado de equivalencia", certificado(rr))

# Condiciones: inicial, Dirichlet, flujo y mixta; dominio.
simb, ecs, doms = reaccion_difusion()
simb_c = simb + [simbolo("c0", "parametro", dim(N=1, L=-3)), simbolo("q", "parametro", dim(N=1, L=-2, T=-1)),
                 simbolo("h", "parametro", dim(L=1, T=-1)), simbolo("cinf", "parametro", dim(N=1, L=-3)), simbolo("tf", "parametro", dim(T=1))]
doms_c = doms + [{"id": "intervalo-t", "variableId": "t", "desde": n(0), "hasta": s("tf")}]
conds = [{"id": "ci", "tipo": "inicial", "dominioId": "intervalo-t", "ecuacion": igualdad("ci-eq", s("c"), s("c0"))},
         {"id": "izq", "tipo": "dirichlet", "dominioId": "intervalo-x", "ecuacion": igualdad("izq-eq", s("c"), s("cinf"))},
         {"id": "flujo", "tipo": "flujo", "dominioId": "intervalo-x", "ecuacion": igualdad("flujo-eq", neg(prod(s("D"), d(s("c"), "x"))), s("q"))},
         {"id": "robin", "tipo": "mixta", "dominioId": "intervalo-x", "ecuacion": igualdad("robin-eq", neg(prod(s("D"), d(s("c"), "x"))), prod(s("h"), suma(s("c"), neg(s("cinf")))))}]
doc_c = documento(simb_c, ecs, [escala("t"), escala("c"), escala("x")], [OBJ_K, OBJ_A], dominios=doms_c, condiciones=conds)
rr = transformar(doc_c)
ctx = ctx_de(doc_c, rr)
cs = {c["id"]: c for c in rr.get("condiciones", [])}
check("condiciones transformadas conservando su tipo", rr["estado"] == "correcto" and [c["tipo"] for c in rr["condiciones"]] == ["inicial", "dirichlet", "flujo", "mixta"])
check("inicial: u = c0 a/k", igualdad_equivale(ctx, cs["ci"]["ecuacion"], s("c_ad"), coc(prod(s("c0"), s("a")), s("k"))), texto(cs["ci"]["ecuacion"]["derecha"]))
check("flujo: -du/dxi = q a L/(D k)", igualdad_equivale(ctx, cs["flujo"]["ecuacion"], neg(d(s("c_ad"), "x_ad")), coc(prod(s("q"), s("a"), s("x_ref")), prod(s("D"), s("k")))),
      texto(cs["flujo"]["ecuacion"]["izquierda"]) + " = " + texto(cs["flujo"]["ecuacion"]["derecha"]))
check("mixta: conserva la estructura h (c - cinf)", igualdad_equivale(ctx, cs["robin"]["ecuacion"], neg(d(s("c_ad"), "x_ad")),
      prod(coc(prod(s("h"), s("x_ref")), s("D")), suma(s("c_ad"), neg(coc(prod(s("cinf"), s("a")), s("k")))))))
doms_pub = {x["id"]: x for x in rr["dominios"]}
check("dominio temporal: tau en [0, k tf]", igual(ctx, doms_pub["intervalo-t"]["hasta"], prod(s("k"), s("tf"))))
check("ecuacion, condiciones y dominios: certificado completo", certificado(rr) and len(rr["equivalencia"]["comprobaciones"]) >= 8)

# Cinetica racional y exponencial, introducidas como expresiones.
simb_r = simb + [simbolo("K", "parametro", dim(N=1, L=-3)), simbolo("vmax", "parametro", dim(N=1, L=-3, T=-1)), simbolo("Ea", "parametro", dim(M=1, L=2, T=-2, N=-1)),
                 simbolo("R", "constante", dim(M=1, L=2, T=-2, N=-1, Theta=-1)), simbolo("Th", "parametro", dim(Theta=1))]
racional = coc(prod(s("vmax"), s("c")), suma(s("K"), s("c")))
rr = transformar(documento(simb_r, [igualdad("balance", d(s("c"), "t"), racional)], [escala("t"), escala("c")]))
ctx = ctx_de(documento(simb_r, [], []), rr)
check("racional: u/(K/C + u) con grupo interno K/C", rr["estado"] == "correcto"
      and igual(ctx, rr["ecuaciones"][0]["igualdad"]["derecha"], coc(prod(s("vmax"), s("t_ref"), s("c_ad")), prod(s("c_ref"), suma(coc(s("K"), s("c_ref")), s("c_ad")))))
      and any(g["interno"] and igual(ctx, g["definicion"], coc(s("K"), s("c_ref"))) for g in rr["grupos"]) and certificado(rr))
exponencial = prod(s("k"), s("c"), fun("exp", neg(coc(s("Ea"), prod(s("R"), s("Th"))))))
rr = transformar(documento(simb_r, [igualdad("balance", d(s("c"), "t"), exponencial)], [escala("t"), escala("c")]))
check("exponencial (Arrhenius constante): transformada y certificada", rr["estado"] == "correcto" and certificado(rr))

# Dos coordenadas con escalas distintas: laplaciano y divergencia en componentes.
sim2 = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("y", "coordenada", dim(L=1)),
        simbolo("c", "campo", dim(N=1, L=-3), ["t", "x", "y"]), simbolo("D", "parametro", dim(L=2, T=-1))]
doc2d = documento(sim2, [igualdad("balance", d(s("c"), "t"), prod(s("D"), lap(s("c"), "x", "y")))], [escala("t"), escala("c"), escala("x"), escala("y")])
rr = transformar(doc2d)
ctx = ctx_de(doc2d, rr)
check("laplaciano 2D con escalas por coordenada", rr["estado"] == "correcto" and igual(ctx, rr["ecuaciones"][0]["igualdad"]["derecha"],
      suma(prod(coc(prod(s("D"), s("t_ref")), pot(s("x_ref"), 2)), d(s("c_ad"), "x_ad", 2)), prod(coc(prod(s("D"), s("t_ref")), pot(s("y_ref"), 2)), d(s("c_ad"), "y_ad", 2))))
      and certificado(rr))
fD2 = dict(fD)
doc2v = documento(sim2[:4], [igualdad("balance", d(s("c"), "t"), div(prod(llam("Dc", s("c")), grad(s("c"), "x", "y")), "x", "y"))],
                  [escala("t"), escala("c"), escala("x"), escala("y")], funciones=[fD2])
rr = transformar(doc2v)
check("divergencia 2D de D(c) grad c: componentes cartesianas certificadas", rr["estado"] == "correcto" and certificado(rr))
rr = transformar(documento(sim2, [igualdad("balance", d(s("c"), "t"), grad(s("c"), "x", "y"))], [escala("t")]))
check("ecuacion vectorial (gradiente 2D suelto): rechazada", rr["estado"] == "rechazado" and diag(rr, "rango"))

print()
print("=" * 78)
print("A3 -- objetivos y formas multiples (seccion 3)")
print("=" * 78)

esperadas = {
    "general": (suma(prod(coc(prod(s("D"), s("t_ref")), pot(s("x_ref"), 2)), lap(s("c_ad"), "x_ad")), prod(s("k"), s("t_ref"), s("c_ad")), neg(prod(s("a"), s("c_ref"), s("t_ref"), pot(s("c_ad"), 2)))),
                {"t": s("t_ref"), "c": s("c_ref"), "x": s("x_ref")}, ["c_ref", "t_ref", "x_ref"]),
    "tiempo-difusivo": (suma(lap(s("c_ad"), "x_ad"), prod(coc(prod(s("k"), pot(s("x_ref"), 2)), s("D")), s("c_ad")), neg(prod(coc(prod(s("a"), s("c_ref"), pot(s("x_ref"), 2)), s("D")), pot(s("c_ad"), 2)))),
                        {"t": coc(pot(s("x_ref"), 2), s("D")), "c": s("c_ref"), "x": s("x_ref")}, ["c_ref", "x_ref"]),
    "tiempo-reactivo": (suma(prod(coc(s("D"), prod(s("k"), pot(s("x_ref"), 2))), lap(s("c_ad"), "x_ad")), s("c_ad"), neg(prod(coc(prod(s("a"), s("c_ref")), s("k")), pot(s("c_ad"), 2)))),
                        {"t": coc(n(1), s("k")), "c": s("c_ref"), "x": s("x_ref")}, ["c_ref", "x_ref"]),
    "campo-cinetico": (suma(prod(coc(s("D"), prod(s("k"), pot(s("x_ref"), 2))), lap(s("c_ad"), "x_ad")), s("c_ad"), neg(pot(s("c_ad"), 2))),
                       {"t": coc(n(1), s("k")), "c": coc(s("k"), s("a")), "x": s("x_ref")}, ["x_ref"]),
    "longitud-parametrica": (suma(lap(s("c_ad"), "x_ad"), s("c_ad"), neg(pot(s("c_ad"), 2))),
                             {"t": coc(n(1), s("k")), "c": coc(s("k"), s("a")), "x": pot(coc(s("D"), s("k")), n(0.5))}, []),
}
resultados3 = {}
for nombre, objetivos in FORMAS_SECCION3.items():
    doc3 = forma_seccion3(objetivos)
    rr = transformar(doc3)
    resultados3[nombre] = rr
    ctx = ctx_de(doc3, rr)
    der, escalas_esp, libres = esperadas[nombre]
    ok = rr["estado"] == "correcto" and igualdad_equivale(ctx, rr["ecuaciones"][0]["igualdad"], d(s("c_ad"), "t_ad"), der)
    check(f"{nombre}: ecuacion", ok, texto(rr["ecuaciones"][0]["igualdad"]["derecha"]) if rr["estado"] == "correcto" else str(rr["diagnosticos"]))
    check(f"{nombre}: escalas", all(igual(ctx, escala_de(rr, v)["valor"], e) for v, e in escalas_esp.items()),
          str({v: texto(escala_de(rr, v)["valor"]) for v in escalas_esp}))
    check(f"{nombre}: escalas libres (familia)", rr["libres"] == libres, str(rr["libres"]))
    check(f"{nombre}: objetivos satisfechos y comprobados, certificado",
          all(o["estado"] == "satisfecho" and o["comprobado"] for o in rr["objetivos"]) and certificado(rr) and rr["normalizacion"]["estado"] == "completa")
    check(f"{nombre}: grupos adimensionales", all(g["adimensional"] for g in rr["grupos"]))
rr = resultados3["longitud-parametrica"]
check("longitud parametrica: el tamano del dominio pasa a la geometria (ell sqrt(k/D))",
      igual(ctx_de(forma_seccion3([]), rr), rr["dominios"][0]["hasta"], prod(s("ell"), pot(coc(s("k"), s("D")), n(0.5)))))
check("tiempo difusivo: t_ref relacionada con la escala libre x_ref", escala_de(resultados3["tiempo-difusivo"], "t")["estado"] == "relacionada")
check("las cinco formas comparten el mismo modelo original (mismo vinculo de modelo)",
      len({(x["vinculo"]["modeloId"], x["vinculo"]["modeloRevision"]) for x in resultados3.values()}) == 1)

# Objetivo redundante con el factor global: normalizar el termino temporal.
rr = transformar(forma_seccion3([objetivo("temporal", "balance", d(s("c"), "t"), 1), OBJ_K]))
check("objetivo temporal: dependiente del factor global (no es una eleccion nueva)", objetivo_de(rr, "temporal")["estado"] == "dependiente")
# Objetivo dependiente de otros dos: (a^2/k) c^3 con C = k/a, t = 1/k.
simb, ecs, doms = reaccion_difusion()
termino_c3 = prod(coc(pot(s("a"), 2), s("k")), pot(s("c"), 3))
ecs[0]["derecha"]["argumentos"].append(termino_c3)
rr = transformar(documento(simb, ecs, [escala("t"), escala("c"), escala("x")], [OBJ_K, OBJ_A, objetivo("cubico", "balance", termino_c3, 1)]))
o = objetivo_de(rr, "cubico")
check("objetivo dependiente (rango 2 con 3 objetivos), responsables", o["estado"] == "dependiente" and set(o["responsables"]) == {"lineal", "cuadratico"} and rr["rangoObjetivos"] == 2, str(o))
# Longitud fijada antes: imponer tambien el objetivo difusivo es incompatible.
simb, ecs, doms = reaccion_difusion()
rr = transformar(documento(simb, ecs, [escala("t"), escala("c"), escala("x", cantidad(0.01, "m"))], [OBJ_K, OBJ_D], dominios=doms))
o = objetivo_de(rr, "difusion")
check("L fijada + objetivo difusivo: incompatible con relacion y responsables", o["estado"] == "incompatible" and set(o["responsables"]) == {"lineal", "difusion"}
      and igual(ctx_de(documento(simb, [], []), rr), o["relacion"]["izquierda"], coc(s("D"), prod(s("k"), pot(s("x_ref"), 2)))), str(o))
check("objetivo incompatible no se aplica: la ecuacion sigue verificada", certificado(rr))
# Signo: k < 0 no admite k t0 = +1.
rr = transformar(forma_seccion3([OBJ_K], signo_k="negativo"))
o = objetivo_de(rr, "lineal")
check("k < 0 con objetivo +1: incompatible por signo", o["estado"] == "incompatible" and o["codigo"] == "signo", str(o))
rr = transformar(forma_seccion3([objetivo("lineal", "balance", TERMINO_K, -1)], signo_k="negativo"))
ctx = ctx_de(forma_seccion3([], signo_k="negativo"), rr)
check("k < 0 con objetivo -1: t0 = 1/|k| y el signo queda en la ecuacion", objetivo_de(rr, "lineal")["estado"] == "satisfecho"
      and igual(ctx, escala_de(rr, "t")["valor"], coc(n(1), fun("abs", s("k"))))
      and igual(ctx, rr["ecuaciones"][0]["igualdad"]["derecha"], suma(prod(coc(s("D"), prod(fun("abs", s("k")), pot(s("x_ref"), 2))), lap(s("c_ad"), "x_ad")), neg(s("c_ad")), neg(prod(coc(prod(s("a"), s("c_ref")), fun("abs", s("k"))), pot(s("c_ad"), 2)))))
      and certificado(rr), texto(rr["ecuaciones"][0]["igualdad"]["derecha"]))
check("k < 0: restriccion de signo publicada", any(x["tipo"] == "signo" and x["expresion"] == s("k") and x["signo"] == "negativo" for x in rr["restricciones"]))
rr = transformar(forma_seccion3([OBJ_K], signo_k="desconocido"))
check("signo de k desconocido: objetivo pendiente con motivo", objetivo_de(rr, "lineal")["estado"] == "pendiente" and objetivo_de(rr, "lineal")["codigo"] == "signo_desconocido")
# Ceros: k = 0 y D = 0.
rr = transformar(forma_seccion3([OBJ_K], signo_k="cero"))
check("k = 0: objetivo incompatible, sin division por cero, familia libre", objetivo_de(rr, "lineal")["estado"] == "incompatible"
      and objetivo_de(rr, "lineal")["codigo"] == "parametro_nulo" and rr["libres"] == ["c_ref", "t_ref", "x_ref"] and certificado(rr))
rr = transformar(forma_seccion3([OBJ_D, OBJ_K], signo_D="cero"))
check("D = 0: el objetivo difusivo no se impone, el reactivo si", objetivo_de(rr, "difusion")["estado"] == "incompatible" and objetivo_de(rr, "lineal")["estado"] == "satisfecho")
# Objetivo que no esta en la ecuacion y objetivo no monomial.
rr = transformar(forma_seccion3([objetivo("fantasma", "balance", prod(s("k"), pot(s("c"), 3)), 1)]))
check("termino inexistente: pendiente", objetivo_de(rr, "fantasma")["estado"] == "pendiente")
simb, ecs, doms = reaccion_difusion()
ecs[0]["derecha"] = prod(suma(s("k"), s("a")), s("c"))
simb[5]["dimension"] = dim(T=-1)
rr = transformar(documento(simb, ecs, [escala("t"), escala("c")], [objetivo("suma", "balance", prod(suma(s("k"), s("a")), s("c")), 1)]))
check("objetivo sobre (k + a) c: no monomial, pendiente", objetivo_de(rr, "suma")["estado"] == "pendiente", str(objetivo_de(rr, "suma")))
rr = transformar(forma_seccion3([objetivo("grupo", "balance", TERMINO_K, 1, "conservar_grupo")]))
check("conservar grupo: no impone restriccion", objetivo_de(rr, "grupo")["estado"] == "conservado" and rr["libres"] == ["c_ref", "t_ref", "x_ref"])

print()
print("=" * 78)
print("Sistemas de varios campos")
print("=" * 78)

def sistema(nombres, difusividades=True):
    simbolos = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1))]
    ecuaciones = []
    for i, c in enumerate(nombres):
        simbolos.append(simbolo(c, "campo", dim(N=1, L=-3), ["t", "x"]))
        simbolos.append(simbolo(f"D{i + 1}", "parametro", dim(L=2, T=-1)))
        simbolos.append(simbolo(f"k{i + 1}", "parametro", dim(T=-1)))
    for i, c in enumerate(nombres):
        siguiente = nombres[(i + 1) % len(nombres)]
        ecuaciones.append(igualdad(f"eq-{c}", d(s(c), "t"), suma(prod(s(f"D{i + 1}"), lap(s(c), "x")), neg(prod(s(f"k{i + 1}"), s(c))), prod(s(f"k{(i + 1) % len(nombres) + 1}"), s(siguiente)))))
    return simbolos, ecuaciones

simb, ecs = sistema(["u", "v"])
doc_s = documento(simb, ecs, [escala("t"), escala("x"), escala("u"), escala("v")], [objetivo("difu", "eq-u", prod(s("D1"), lap(s("u"), "x")), 1)])
rr = transformar(doc_s)
ctx = ctx_de(doc_s, rr)
coef_v = next(t for t in rr["ecuaciones"][1]["terminos"] if t["id"].endswith("argumentos[0]"))["coeficiente"]
check("dos campos: tiempo comun difusivo de u conserva D2/D1 en v", rr["estado"] == "correcto" and igual(ctx, coef_v, coc(s("D2"), s("D1"))) and certificado(rr), texto(coef_v))
rr = transformar(documento(simb, ecs, [escala("t"), escala("x"), escala("u"), escala("v")],
                           [objetivo("difu", "eq-u", prod(s("D1"), lap(s("u"), "x")), 1), objetivo("difv", "eq-v", prod(s("D2"), lap(s("v"), "x")), 1)]))
o = objetivo_de(rr, "difv")
check("dos tiempos difusivos con un solo tiempo: incompatible salvo D1 = D2", o["estado"] == "incompatible" and set(o["responsables"]) == {"difu", "difv"}, str(o))
simb, ecs = sistema(["p", "q", "r", "w"])
rr = transformar(documento(simb, ecs, [escala("t"), escala("x")] + [escala(c) for c in "pqrw"],
                           [objetivo("o1", "eq-p", neg(prod(s("k1"), s("p"))), -1), objetivo("o2", "eq-p", prod(s("k2"), s("q")), 1),
                            objetivo("o3", "eq-q", prod(s("k3"), s("r")), 1), objetivo("o4", "eq-r", prod(s("k4"), s("w")), 1)]))
check("cuatro campos: mismo algoritmo, escalas de campo determinadas en cadena", rr["estado"] == "correcto" and certificado(rr)
      and [escala_de(rr, c)["estado"] for c in "pqr"] == ["relacionada"] * 3 and escala_de(rr, "w")["estado"] == "libre", str([escala_de(rr, c)["estado"] for c in "pqrw"]))

# Reaccion-difusion de patrones (Schnakenberg), solo como caso del lenguaje.
simb = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)),
        simbolo("u", "campo", dim(N=1, L=-3), ["t", "x"]), simbolo("v", "campo", dim(N=1, L=-3), ["t", "x"]),
        simbolo("Du", "parametro", dim(L=2, T=-1)), simbolo("Dv", "parametro", dim(L=2, T=-1)),
        simbolo("k1", "parametro", dim(N=1, L=-3, T=-1)), simbolo("k2", "parametro", dim(T=-1)),
        simbolo("k3", "parametro", dim(N=-2, L=6, T=-1)), simbolo("k4", "parametro", dim(N=1, L=-3, T=-1))]
uv = prod(s("k3"), pot(s("u"), 2), s("v"))
ecs = [igualdad("eq-u", d(s("u"), "t"), suma(prod(s("Du"), lap(s("u"), "x")), s("k1"), neg(prod(s("k2"), s("u"))), uv)),
       igualdad("eq-v", d(s("v"), "t"), suma(prod(s("Dv"), lap(s("v"), "x")), s("k4"), neg(uv)))]
doc_p = documento(simb, ecs, [escala("t"), escala("x"), escala("u"), escala("v")],
                  [objetivo("lin", "eq-u", neg(prod(s("k2"), s("u"))), -1), objetivo("dif", "eq-u", prod(s("Du"), lap(s("u"), "x")), 1),
                   objetivo("nl", "eq-u", uv, 1), objetivo("nlv", "eq-v", neg(uv), -1)])
rr = transformar(doc_p)
ctx = ctx_de(doc_p, rr)
check("patrones: todas las escalas determinadas, d = Dv/Du conservado", rr["estado"] == "correcto" and rr["libres"] == []
      and any(igual(ctx, g["definicion"], coc(s("Dv"), s("Du"))) for g in rr["grupos"]) and certificado(rr),
      str([texto(g["definicion"]) for g in rr.get("grupos", [])]))

print()
print("=" * 78)
print("Exploracion y grupos Pi")
print("=" * 78)

doc_e = forma_seccion3([])
terminos = procesar(solicitud(doc_e, "analizar"))["terminos"]
tids = [t["id"] for t in terminos]
import itertools
propuestas = [{"id": "propuesta-0", "estado": "sin_evaluar", "objetivos": []}]
for k in range(1, 4):
    for comb in itertools.combinations(tids, k):
        propuestas.append({"id": f"propuesta-{len(propuestas)}", "estado": "sin_evaluar",
                           "objetivos": [{"terminoId": t, "operacion": "normalizar_magnitud_coeficiente", "conservarSigno": True} for t in comb]})
config = {"presupuesto": 200, "maxObjetivos": 3, "respetarEscalasFijadas": True, "incluirGruposPi": True, "maxExponentePi": 4, "maxDenominadorPi": 4}
sol_e = {"formato": "solicitud_exploracion_adimensional", "version": 1, "documentoId": doc_e["id"], "modelo": doc_e["modelo"],
         "formaBase": doc_e["formas"][0], "config": config, "terminos": [], "propuestas": propuestas,
         "cobertura": {}, "politica": {}}
rx = procesar(sol_e)
check("exploracion: evalua todas las propuestas", rx["estado"] == "correcto" and rx["cobertura"]["propuestasEvaluadas"] == len(propuestas) == 15, str(rx.get("cobertura")))
evals = {e["propuestaId"]: e for e in rx["evaluaciones"]}
temporal = next(p for p in propuestas if [o["terminoId"] for o in p["objetivos"]] == [tids[0]])
check("exploracion: objetivo temporal solo = duplicado del representante sin objetivos", evals[temporal["id"]]["estado"] == "duplicada" and evals[temporal["id"]]["formulacionId"] == "F1")
check("exploracion: formulaciones distintas y duplicados contados",
      rx["cobertura"]["formulacionesDistintas"] + rx["cobertura"]["duplicadas"] == 15 and rx["cobertura"]["duplicadas"] >= 7, str(rx["cobertura"]))
check("exploracion: todas las formulaciones certificadas", all(f["equivalencia"]["estado"] == "demostrada" for f in rx["formulaciones"]))
completa = [f for f in rx["formulaciones"] if f["libres"] == []]
check("exploracion: aparece la forma totalmente determinada (u_t = lap u + u - u^2)", len(completa) == 1)
pi = rx["gruposPi"]
check("Pi: rango 3, un grupo (a no puede entrar: unica con N)", pi["rango"] == 3 and pi["numeroGrupos"] == 1, str(pi["rango"]))
check("Pi: bases alternativas distintas y mapa a la referencia", len(pi["bases"]) >= 2 and all(pi["bases"][i]["enReferencia"] for i in range(len(pi["bases"]))))
ctxp = ctx_de(doc_e)
check("Pi: D/(k ell^2) o su potencia aparece como grupo", any(igual(ctxp, b["grupos"][0]["definicion"], coc(prod(s("k"), pot(s("ell"), 2)), s("D"))) or igual(ctxp, b["grupos"][0]["definicion"], coc(s("D"), prod(s("k"), pot(s("ell"), 2)))) for b in pi["bases"]))
config_corta = dict(config, presupuesto=1, maxExponentePi=1, maxDenominadorPi=1)
rx2 = procesar(dict(sol_e, config=config_corta, propuestas=propuestas[:1]))
check("Pi: presupuesto agotado declarado", rx2["gruposPi"]["cobertura"]["limitadoPorPresupuesto"])
mal = dict(sol_e, propuestas=[{"id": "p", "estado": "sin_evaluar", "objetivos": [{"terminoId": tids[1], "operacion": "otra", "conservarSigno": True}]}])
check("exploracion: operacion desconocida rechazada", procesar(mal)["estado"] == "rechazado")

def parametros_publicados(f):
    usados = set()
    for ec in f["ecuaciones"]:
        usados |= F._simbolos(ec["igualdad"]["izquierda"]) | F._simbolos(ec["igualdad"]["derecha"])
    for c in f["condiciones"]:
        usados |= F._simbolos(c["ecuacion"]["izquierda"]) | F._simbolos(c["ecuacion"]["derecha"])
    for x in f["dominios"]:
        usados |= F._simbolos(x["desde"]) | F._simbolos(x["hasta"])
    for e in f["escalas"]:
        usados |= F._simbolos(e["valor"])
    return usados


parametros = {x["id"] for x in doc_e["modelo"]["simbolos"] if x["rol"] == "parametro"}
check("ninguna alternativa pierde parametros (pasan a grupos, escalas o fronteras)",
      all(parametros <= parametros_publicados(f) for f in rx["formulaciones"]),
      str([sorted(parametros - parametros_publicados(f)) for f in rx["formulaciones"]]))

# Cambio entre bases dimensionales equivalentes: concentracion como base 'C'.
simb, ecs, doms = reaccion_difusion()
simb_C = copy.deepcopy(simb)
for x in simb_C:
    if x["id"] == "c":
        x["dimension"] = dim(C=1)
    if x["id"] == "a":
        x["dimension"] = dim(C=-1, T=-1)
for objetivos in FORMAS_SECCION3.values():
    a = transformar(documento(simb, ecs, [escala("t"), escala("c"), escala("x")], objetivos, dominios=doms))
    b = transformar(documento(simb_C, ecs, [escala("t"), escala("c"), escala("x")], objetivos, dominios=doms))
    if a["ecuaciones"] != b["ecuaciones"] or a["escalas"] != b["escalas"]:
        break
else:
    a = b = None
check("base {L,T,N} frente a base {L,T,C}: mismas ecuaciones y escalas en las cinco formas", a is None)

# Escala singular y diferencia de temperatura.
rr = transformar(documento(sim_t, [igualdad("balance", d(s("c"), "t"), TERMINO_K)], [escala("t", expresion(prod(n(0), coc(n(1), s("k")))))]))
check("escala singular (expresion nula): rechazada", rr["estado"] == "rechazado" and diag(rr, "escala_singular"))
sim_dT = sim_t + [simbolo("dT", "campo", None, ["t"], unidad="delta_degC")]
rr = transformar(documento(sim_dT, [igualdad("balance", d(s("dT"), "t"), neg(prod(s("k"), s("dT"))))], [escala("dT", cantidad(5, "K"))]))
check("diferencia de temperatura (delta_degC): escala multiplicativa admitida", rr["estado"] == "correcto" and certificado(rr))

print()
print("=" * 78)
print("Familias generales: mapas afines y no lineales invertibles")
print("=" * 78)


def constante(i, papel="escala", valor=None, dimension=None):
    return {"id": i, "nombre": i, "papel": papel, "dimension": dimension, "valor": valor or {"tipo": "libre"}}


def mapa(v, w, directa, inversa, constantes, original=None, nuevo=None):
    return {"variableId": v, "nuevoId": w, "directa": directa, "inversa": inversa, "constantes": constantes,
            "dominio": {"original": original, "nuevo": nuevo}}


def con_mapas(doc, mapas, operacion="transformar"):
    sol = solicitud(doc, operacion)
    sol["transformaciones"] = mapas
    return procesar(sol)


def familia(r, v):
    return next(t["familia"] for t in r["transformaciones"] if t["variableId"] == v)


simb, ecs, doms = reaccion_difusion()
doc_log = documento(simb, ecs, [escala("t"), escala("x")], dominios=doms)
LOG = mapa("c", "u", prod(s("C"), fun("exp", s("u"))), fun("log", coc(s("c"), s("C"))), [constante("C")], original="positivo")
rr = con_mapas(doc_log, [LOG])
ctx = ctx_de(doc_log, rr)
ctx.simbolos["c"]["signo"] = "positivo"
eu = fun("exp", s("u"))
esperado = suma(prod(coc(prod(s("D"), s("t_ref")), pot(s("x_ref"), 2)), suma(prod(eu, pot(d(s("u"), "x_ad"), 2)), prod(eu, d(s("u"), "x_ad", 2)))),
                prod(s("k"), s("t_ref"), eu), neg(prod(s("a"), s("C"), s("t_ref"), pot(eu, 2))))
check("c = C exp(u): familia no lineal y termino adicional (du/dxi)^2 de la regla de la cadena",
      rr["estado"] == "correcto" and familia(rr, "c") == "no_lineal"
      and igualdad_equivale(ctx, rr["ecuaciones"][0]["igualdad"], prod(eu, d(s("u"), "t_ad")), esperado),
      texto(rr["ecuaciones"][0]["igualdad"]["derecha"]) if rr["estado"] == "correcto" else str(rr["diagnosticos"]))
check("c = C exp(u): certificado y restriccion de dominio c > 0", certificado(rr)
      and any(x["tipo"] == "positivo" and x["expresion"] == s("c") and "dominio" in x["motivo"] for x in rr["restricciones"]))
check("c = C exp(u): directa e inversa publicadas", rr["directa"][-1]["expresion"] == LOG["directa"] and rr["inversa"][-1]["expresion"] == LOG["inversa"])
rr = con_mapas(doc_log, [dict(LOG, dominio={"original": None, "nuevo": None})])
check("log sin dominio c > 0: inversa no demostrada, rechazado", rr["estado"] == "rechazado" and diag(rr, "inversa_no_demostrada"))
rr = con_mapas(doc_log, [dict(LOG, inversa=suma(fun("log", coc(s("c"), s("C"))), n(1)))])
check("inversa equivocada: rechazada", rr["estado"] == "rechazado" and diag(rr, "inversa_no_demostrada"))
POT = mapa("c", "u", prod(s("C"), pot(s("u"), 2)), pot(coc(s("c"), s("C")), n(0.5)), [constante("C")], original="positivo")
rr = con_mapas(doc_log, [POT])
check("c = C u^2 sin dominio de u: no invertible demostrable ((u^2)^(1/2) = |u|)", rr["estado"] == "rechazado" and diag(rr, "inversa_no_demostrada"))
rr = con_mapas(doc_log, [dict(POT, dominio={"original": "positivo", "nuevo": "positivo"})])
check("c = C u^2 con c, u > 0: aceptado, no lineal y certificado", rr["estado"] == "correcto" and familia(rr, "c") == "no_lineal" and certificado(rr))
rr = con_mapas(doc_log, [dict(LOG, directa=prod(s("C"), fun("exp", d(s("u"), "t"))))])
check("mapa con derivadas: rechazado por el contrato", rr["estado"] == "rechazado" and rr["diagnosticos"][0]["codigo"] == "contrato")
rr = con_mapas(forma_seccion3([OBJ_K]), [LOG])
check("A3 sobre un mapa no lineal: t_ref = 1/k", rr["estado"] == "correcto" and igual(ctx_de(forma_seccion3([]), rr), escala_de(rr, "t")["valor"], coc(n(1), s("k"))) and certificado(rr))

# Afin con referencia en degC: la temperatura absoluta deja de rechazarse.
simT = [simbolo("t", "tiempo", dim(T=1)), simbolo("T", "campo", None, ["t"], unidad="degC"), simbolo("k", "parametro", dim(T=-1)),
        simbolo("Ta", "parametro", dim(Theta=1)), simbolo("k0", "parametro", dim(T=-1)), simbolo("E", "parametro", dim(M=1, L=2, T=-2, N=-1)),
        simbolo("R", "constante", dim(M=1, L=2, T=-2, N=-1, Theta=-1))]
AFIN = mapa("T", "theta", suma(s("Tr"), prod(s("dT"), s("theta"))), coc(suma(s("T"), neg(s("Tr"))), s("dT")),
            [constante("Tr", "referencia", cantidad(25, "degC")), constante("dT", "escala", cantidad(10, "K"))])
docT = documento(simT, [igualdad("enfriamiento", d(s("T"), "t"), neg(prod(s("k"), suma(s("T"), neg(s("Ta"))))))], [escala("t")])
rr = con_mapas(docT, [AFIN])
ctx = ctx_de(docT, rr)
check("afin T = Tr + dT theta: familia, referencia 25 degC = 298.15 K",
      rr["estado"] == "correcto" and familia(rr, "T") == "afin" and next(x for x in rr["simbolos"] if x["id"] == "Tr")["cantidad"]["valorSI"] == 298.15)
check("afin: dtheta/dtau = k t (Ta - Tr)/dT - k t theta, certificado", igualdad_equivale(ctx, rr["ecuaciones"][0]["igualdad"], d(s("theta"), "t_ad"),
      suma(coc(prod(s("k"), s("t_ref"), suma(s("Ta"), neg(s("Tr")))), s("dT")), neg(prod(s("k"), s("t_ref"), s("theta"))))) and certificado(rr))
arr = [igualdad("arrhenius", d(s("T"), "t"), prod(s("k0"), s("Ta"), fun("exp", neg(coc(s("E"), prod(s("R"), s("T")))))))]
rr = con_mapas(documento(simT, arr, [escala("t")]), [AFIN])
check("afin dentro de exp(-E/(R T)): se conserva la estructura y se certifica", rr["estado"] == "correcto" and certificado(rr))
rr = transformar(documento(simT, arr, [escala("t"), escala("T", cantidad(300, "K"))]))
check("degC con escala multiplicativa: sigue rechazada", rr["estado"] == "rechazado" and diag(rr, "temperatura_afin"))

# Coordenada y tiempo no lineales (por coordenada, cartesianos).
LOGT = mapa("t", "s", prod(s("t0"), fun("exp", s("s"))), fun("log", coc(s("t"), s("t0"))), [constante("t0")], original="positivo")
simb, ecs, doms = reaccion_difusion()
rr = con_mapas(documento(simb, ecs, [escala("c"), escala("x")], dominios=doms), [LOGT])
check("t = t0 exp(s): jacobiano publicado y certificado", rr["estado"] == "correcto" and familia(rr, "t") == "no_lineal" and certificado(rr)
      and any(x["tipo"] == "no_nulo" and "jacobiano" in x["motivo"] for x in rr["restricciones"]))
onda = [igualdad("onda", d(s("c"), "t", 2), prod(s("D"), s("k"), d(s("c"), "x", 2)))]
rr = con_mapas(documento(simb, onda, [escala("c"), escala("x")]), [LOGT])
check("segunda derivada temporal con t = t0 exp(s): terminos de orden superior certificados", rr["estado"] == "correcto" and certificado(rr)
      and len(rr["ecuaciones"][0]["terminos"]) >= 2, texto(rr["ecuaciones"][0]["igualdad"]["izquierda"]) if rr["estado"] == "correcto" else str(rr["diagnosticos"]))
EXPX = mapa("x", "xi", prod(s("L"), suma(fun("exp", s("xi")), n(-1))), fun("log", suma(n(1), coc(s("x"), s("L")))), [constante("L")], original="positivo")
rr = con_mapas(documento(simb, ecs, [escala("t"), escala("c")], dominios=doms), [EXPX])
check("x = L (exp(xi) - 1): difusion con regla de la cadena y dominio [0, log(1 + ell/L)]", rr["estado"] == "correcto" and certificado(rr)
      and igual(ctx_de(documento(simb, [], []), rr), rr["dominios"][0]["hasta"], fun("log", suma(n(1), coc(s("ell"), s("L"))))))

print()
print("=" * 78)
print("Busqueda automatica desde la entrada simple")
print("=" * 78)


def automatico(doc, **opciones):
    sol = solicitud(doc, "adimensionalizar")
    if opciones:
        sol["opciones"] = opciones
    return procesar(sol)


simb, ecs, doms = reaccion_difusion()
solo = documento(simb, ecs, [], dominios=doms)
ra = automatico(solo)
check("automatico: sin escalas configuradas, 8 formulaciones certificadas y recorrido completo",
      ra["estado"] == "correcto" and ra["cobertura"]["formulacionesDistintas"] == 8 and ra["cobertura"]["completa"]
      and all(f["equivalencia"]["estado"] == "demostrada" for f in ra["formulaciones"]), str(ra.get("cobertura")))
huellas_auto = {F.huella(f) for f in ra["formulaciones"]}
check("automatico: contiene las cinco formas de la seccion 3", all(F.huella(r3) in huellas_auto for r3 in resultados3.values()))
check("automatico: el termino temporal queda excluido (lo fija el factor global)",
      any(x["terminoId"].endswith("izquierda") and "factor global" in x["motivo"] for x in ra["cobertura"]["excluidos"]))
parte1 = automatico(solo, presupuesto=3)
parte2 = automatico(solo, presupuesto=200, desde=parte1["cobertura"]["siguiente"] or 0)
check("presupuesto agotado: continuacion reproducible",
      parte1["cobertura"]["agotado"] == "presupuesto" and parte1["cobertura"]["siguiente"] == 3
      and {F.huella(f) for f in parte1["formulaciones"]} | {F.huella(f) for f in parte2["formulaciones"]} == huellas_auto)
vacio = documento([dict(x, dimension=None) for x in simb], ecs, [], dominios=doms)
rv = automatico(vacio)
check("todo pendiente: requiere_datos con lo indispensable y sin formulaciones",
      rv["estado"] == "requiere_datos" and sorted(rv["dimensional"]["faltantes"]) == ["c", "t", "x"] and "formulaciones" not in rv)
rr = automatico(forma_seccion3([], signo_k="desconocido"))
check("automatico con signo desconocido: el termino se excluye con motivo, sin objetivos condicionales ocultos",
      any("signo" in x["motivo"] for x in rr["cobertura"]["excluidos"]) and rr["estado"] == "correcto")
rr = automatico(documento(simT, arr, []))
check("automatico con temperatura en degC: pide una referencia, no la inventa", any(x["codigo"] == "requiere_referencia" for x in rr["diagnosticos"]))
sol = solicitud(doc_log, "adimensionalizar")
sol["transformaciones"] = [LOG]
del sol["documento"]["formas"][0]["escalas"][:]
rr = procesar(sol)
check("automatico respeta un mapa declarado (log) en todas las formulaciones",
      rr["estado"] == "correcto" and all(familia(f, "c") == "no_lineal" and f["equivalencia"]["estado"] == "demostrada" for f in rr["formulaciones"]))
simb_s, ecs_s = sistema(["u", "v"])
rr = automatico(documento(simb_s, ecs_s, []))
check("automatico en un sistema de dos campos: familias y formas completas, D2/D1 aparece",
      rr["estado"] == "correcto" and rr["cobertura"]["completa"]
      and any(any(igual(ctx_de(documento(simb_s, [], [])), g["definicion"], coc(s("D2"), s("D1"))) for g in f["grupos"]) for f in rr["formulaciones"]))

print()
print("=" * 78)
print("Desarrollo matematico (traza PasoDesarrollo)")
print("=" * 78)

OPERACIONES = {"analisis_dimensional", "cambio_variables", "regla_cadena", "sustitucion", "factorizacion", "normalizacion",
               "agrupacion", "simplificacion", "geometria_condiciones", "verificacion_inversa", "hipotesis_fisica"}


def _refs(e, simbolos, variables):
    """Simbolos y variables de derivacion que referencia un AST."""
    t = e["tipo"]
    if t == "simbolo":
        simbolos.add(e["id"])
    if t == "derivada":
        variables.add(e["respecto"])
    if t in ("gradiente", "divergencia", "laplaciano"):
        variables.update(e["coordenadas"])
    for a in e.get("argumentos", []):
        _refs(a, simbolos, variables)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            _refs(e[k], simbolos, variables)


def problemas_traza(doc, f):
    """Lo que debe comprobar el lector del cliente antes de mostrar la traza."""
    errores = []
    conocidos = {x["id"] for x in doc["modelo"]["simbolos"]} | {x["id"] for x in f["simbolos"]}
    indep = {x["id"] for x in doc["modelo"]["simbolos"] if x["rol"] in ("tiempo", "coordenada")}
    indep |= {x["id"] for x in f["simbolos"] if x.get("rolOrigen") in ("tiempo", "coordenada")}
    ids = set()
    for p in f["desarrollo"]:
        if set(p) != {"id", "operacion", "regla", "justificacion", "antes", "despues", "supuestos", "objetosAfectados"}:
            errores.append(f"{p.get('id')}: campos")
            continue
        if p["id"] in ids or p["operacion"] not in OPERACIONES:
            errores.append(f"{p['id']}: id u operacion")
        ids.add(p["id"])
        for lado in ("antes", "despues"):
            x = p[lado]
            if x["tipo"] == "expresion" and set(x) == {"tipo", "expresion"}:
                asts = [x["expresion"]]
            elif x["tipo"] == "igualdad" and set(x) == {"tipo", "igualdad"} and set(x["igualdad"]) == {"id", "izquierda", "derecha"}:
                asts = [x["igualdad"]["izquierda"], x["igualdad"]["derecha"]]
            else:
                errores.append(f"{p['id']}.{lado}: forma")
                continue
            sims, vars_ = set(), set()
            for a in asts:
                _refs(a, sims, vars_)
            if sims - conocidos or vars_ - indep:
                errores.append(f"{p['id']}.{lado}: referencias {sorted((sims - conocidos) | (vars_ - indep))}")
        if not all(isinstance(z, str) for z in p["supuestos"] + p["objetosAfectados"]):
            errores.append(f"{p['id']}: textos")
    return errores


casos_traza = [(f"seccion 3 {k}", forma_seccion3(v), None) for k, v in FORMAS_SECCION3.items()]
casos_traza += [("condiciones", doc_c, None), ("mapa log", doc_log, [LOG]), ("afin degC", docT, [AFIN]), ("D(c)", doc_v, None)]
for nombre, documento_, mapas in casos_traza:
    rr = con_mapas(documento_, mapas) if mapas else transformar(documento_)
    errores = problemas_traza(documento_, rr)
    check(f"traza {nombre}: formato y referencias validas para el lector", rr["estado"] == "correcto" and not errores and rr["desarrollo"], str(errores[:5]))
for f in ra["formulaciones"]:
    if problemas_traza(solo, f):
        check(f"traza automatica {f['id']}: formato valido", False, str(problemas_traza(solo, f)[:3]))
        break
else:
    check("traza de cada formulacion automatica: formato valido", True)

rr = transformar(forma_seccion3([OBJ_K, OBJ_A]))
ops = [p["operacion"] for p in rr["desarrollo"]]
check("traza: todas las fases en orden (dimensiones, mapas, sustitucion, cadena, agrupacion, normalizacion, geometria, inversa)",
      all(o in ops for o in ("analisis_dimensional", "cambio_variables", "sustitucion", "regla_cadena", "agrupacion", "normalizacion",
                             "geometria_condiciones", "verificacion_inversa"))
      and ops.index("analisis_dimensional") < ops.index("cambio_variables") < ops.index("sustitucion") < ops.index("normalizacion")
      < ops.index("geometria_condiciones") < ops.index("verificacion_inversa") and "hipotesis_fisica" not in ops)
term_ids = {t["id"] for t in rr["terminos"]}
sustituidos = {o for p in rr["desarrollo"] if p["regla"] == "sustitucion de variables" for o in p["objetosAfectados"]}
check("traza: una sustitucion por cada termino del original", term_ids <= sustituidos, str(term_ids - sustituidos))
antes_de_cancelar = [p for p in rr["desarrollo"] if p["regla"] == "igualdad completa antes de cancelar factores"]
check("traza: la igualdad completa antes de cancelar factores", len(antes_de_cancelar) == 1 and antes_de_cancelar[0]["despues"]["tipo"] == "igualdad")
division = next(p for p in rr["desarrollo"] if p["regla"] == "division por el factor global")
check("traza: la division conserva su condicion de no nulidad", any("cero" in x or "positivo" in x for x in division["supuestos"]), str(division["supuestos"]))
check("traza: un paso por objetivo y por escala despejada",
      sum(p["regla"].startswith("objetivo") for p in rr["desarrollo"]) == 2 and sum(p["regla"] == "resolucion exacta por rango" for p in rr["desarrollo"]) == 2
      and sum(p["regla"] == "familia libre" for p in rr["desarrollo"]) == 1)
ctx = ctx_de(forma_seccion3([]), rr)
inversa = [p for p in rr["desarrollo"] if p["operacion"] == "verificacion_inversa"][0]
eq0 = forma_seccion3([])["modelo"]["ecuaciones"][0]
check("traza: la sustitucion inversa recupera la igualdad original", igual(ctx, suma(inversa["despues"]["igualdad"]["izquierda"], neg(inversa["despues"]["igualdad"]["derecha"])),
                                                                         suma(eq0["izquierda"], neg(eq0["derecha"]))))
rr = con_mapas(doc_log, [LOG])
desarrollo_nl = [p for p in rr["desarrollo"] if p["regla"].startswith("desarrollo de derivadas")]
check("traza no lineal: el desarrollo de la cadena muestra los terminos adicionales",
      any("^2" in texto(p["despues"]["expresion"]) and "d(u)/dx_ad" in texto(p["despues"]["expresion"]) for p in desarrollo_nl), str([texto(p["despues"]["expresion"]) for p in desarrollo_nl]))
check("traza no lineal: el mapa y su inversa demostrada", any(p["operacion"] == "cambio_variables" and "demostrada" in p["justificacion"] for p in rr["desarrollo"]))
rr = transformar(doc_c)
check("traza: dominios y condiciones con sus pasos", sum(p["operacion"] == "geometria_condiciones" for p in rr["desarrollo"]) >= 8)

print()
print("=" * 78)
print("Certificado y algebra: poder de deteccion y reglas validas")
print("=" * 78)

original = F.presentar_lado


def quitar_ultimo(items, presentacion):
    return original(items[:-1] if len(items) > 1 else items, presentacion)


F.presentar_lado = quitar_ultimo
try:
    rr = transformar(forma_seccion3([OBJ_K]))
finally:
    F.presentar_lado = original
check("certificado detecta un termino perdido en lo publicado", rr["equivalencia"]["estado"] == "no_demostrada"
      and any(c["tipo"] == "sustitucion_inversa" and c["estado"] == "no_demostrada" for c in rr["equivalencia"]["comprobaciones"]))


def ctx_signo(signo):
    return A.Contexto({"k": {"rol": "parametro", "constante": True, "dependeDe": set(), "signo": signo},
                       "c": {"rol": "campo", "constante": False, "dependeDe": {"t"}, "signo": "desconocido"},
                       "t": {"rol": "tiempo", "constante": False, "dependeDe": set(), "signo": "desconocido"}}, {})


raiz_cuadrado = pot(pot(s("k"), 2), n(0.5))
check("(k^2)^(1/2) != k con signo desconocido", not igual(ctx_signo("desconocido"), raiz_cuadrado, s("k")))
check("(k^2)^(1/2) = k con k > 0", igual(ctx_signo("positivo"), raiz_cuadrado, s("k")))
check("(k^2)^(1/2) = |k| = -k con k < 0", igual(ctx_signo("negativo"), raiz_cuadrado, neg(s("k"))))
check("k^(1/2) k^(1/2) = k para cualquier signo", igual(ctx_signo("desconocido"), prod(pot(s("k"), n(0.5)), pot(s("k"), n(0.5))), s("k")))
check("(k c)^(1/2) no se separa con signos desconocidos", not igual(ctx_signo("desconocido"), pot(prod(s("k"), s("c")), n(0.5)), prod(pot(s("k"), n(0.5)), pot(s("c"), n(0.5)))))
check("8^(1/3) = 2 exacto", igual(ctx_signo("positivo"), pot(n(8), coc(n(1), n(3))), n(2)))
check("d(k c)/dt = k dc/dt (k constante)", igual(ctx_signo("positivo"), d(prod(s("k"), s("c")), "t"), prod(s("k"), d(s("c"), "t"))))
check("no se aplica la regla del producto", not igual(ctx_signo("positivo"), d(pot(s("c"), 2), "t"), prod(n(2), s("c"), d(s("c"), "t"))))
check("d(dc/dt)/dt = d2c/dt2", igual(ctx_signo("positivo"), d(d(s("c"), "t"), "t"), d(s("c"), "t", 2)))
check("d(t)/dt = 1", igual(ctx_signo("positivo"), d(s("t"), "t"), n(1)))
ctxp = ctx_signo("positivo")
P2 = A.canonica(prod(pot(suma(s("k"), s("c")), -1), suma(s("k"), s("c"))), ctxp)
desarrollado = A.canonica(pot(suma(s("k"), s("c")), 2), ctxp)
base = A.canonica(pot(suma(s("k"), s("c")), -2), ctxp)
check("cero por denominadores: (k+c)^2 desarrollado por (k+c)^-2 = 1", A.iguales(A.multiplicar(desarrollado, base), A.UNO))
check("cero por denominadores: no confunde (k+c)^2 (k+c)^-2 con 2", not A.iguales(A.multiplicar(desarrollado, base), A.numero(2)))
check("(k+c)/(k+c) = 1", A.iguales(P2, A.UNO))
try:
    A.canonica(coc(s("k"), suma(s("c"), neg(s("c")))), ctx_signo("positivo"))
    check("division por una suma nula: error explicito", False)
except A.ErrorAlgebraico as e:
    check("division por una suma nula: error explicito", e.codigo == "division_por_cero")

print()
print("=" * 78)
print("Contrato v2 del documento")
print("=" * 78)


def v2(doc):
    x = copy.deepcopy(doc)
    x["version"] = 2
    return x


def contrato_rechaza(sol, ruta):
    rr = procesar(sol)
    return rr["estado"] == "rechazado" and "ecuaciones" not in rr and rr["diagnosticos"][0]["codigo"] == "contrato" and rr["diagnosticos"][0]["ruta"].startswith(ruta)


ID_D, ID_K, ID_A = (f"balance:ecuaciones[0].derecha.argumentos[{i}]" for i in range(3))

# Compatibilidad: un v1 declarado como v2 da exactamente el mismo calculo.
for nombre, objetivos in FORMAS_SECCION3.items():
    r1, r2 = transformar(forma_seccion3(objetivos)), transformar(v2(forma_seccion3(objetivos)))
    if {k: v for k, v in r1.items() if k != "vinculo"} != {k: v for k, v in r2.items() if k != "vinculo"} or r1["vinculo"] != r2["vinculo"]:
        check(f"v2 sin campos nuevos = v1 ({nombre})", False)
        break
else:
    check("v2 sin campos nuevos: mismo resultado que v1 en las cinco formas", True)
doc1 = forma_seccion3([])
doc1["formas"][0]["objetivos"] = [{"id": "o", "ecuacionId": "balance", "terminoId": ID_K, "valor": 1, "accion": "normalizar"}]
check("v1 no admite campos de v2 (terminoId)", contrato_rechaza(solicitud(doc1), "formas[0].objetivos[0]"))
doc1 = forma_seccion3([])
doc1["modelo"]["condiciones"] = []
doc1["formas"][0]["prioridadEscalas"] = ["x"]
check("v1 no admite campos de v2 (prioridadEscalas)", contrato_rechaza(solicitud(doc1), "formas[0]"))
check("capacidades: documentos v1 y v2", capacidades()["versionesDocumento"] == [1, 2] and capacidades()["contratoDocumento"] == 2)

# 1. Objetivos por terminoId.
def con_objetivos(objetivos, base=None):
    x = v2(base or forma_seccion3([]))
    x["formas"][0]["objetivos"] = objetivos
    return x


def obj_id(i, tid, valor=1, termino=None, accion="normalizar"):
    o = {"id": i, "ecuacionId": "balance", "terminoId": tid, "valor": valor, "accion": accion}
    if termino is not None:
        o["termino"] = termino
    return o


por_id = transformar(con_objetivos([obj_id("lineal", ID_K), obj_id("cuadratico", ID_A, -1)]))
por_expr = transformar(forma_seccion3([OBJ_K, OBJ_A]))
check("terminoId: la misma formulacion que el objetivo por expresion (campo cinetico)",
      por_id["estado"] == "correcto" and por_id["ecuaciones"] == por_expr["ecuaciones"] and por_id["escalas"] == por_expr["escalas"] and certificado(por_id))
check("terminoId: el estado del objetivo lo identifica", objetivo_de(por_id, "lineal")["terminoId"] == ID_K and objetivo_de(por_id, "lineal")["estado"] == "satisfecho")
rr = transformar(con_objetivos([obj_id("lineal", ID_K, termino=TERMINO_K)]))
check("terminoId y expresion coherentes: aceptado", objetivo_de(rr, "lineal")["estado"] == "satisfecho")
rr = transformar(con_objetivos([obj_id("lineal", ID_K, termino=TERMINO_A)]))
check("terminoId y expresion contradictorios: pendiente, sin aplicarse", objetivo_de(rr, "lineal")["estado"] == "pendiente"
      and objetivo_de(rr, "lineal")["codigo"] == "termino_contradictorio" and rr["libres"] == ["c_ref", "t_ref", "x_ref"] and certificado(rr))
rr = transformar(con_objetivos([obj_id("fantasma", "balance:ecuaciones[0].derecha.argumentos[9]")]))
check("terminoId inexistente: pendiente con codigo", objetivo_de(rr, "fantasma")["estado"] == "pendiente" and objetivo_de(rr, "fantasma")["codigo"] == "termino_no_encontrado")
simb, ecs, doms = reaccion_difusion()
ec_mixta = [igualdad("balance", d(s("c"), "t"), prod(s("k"), suma(s("c"), neg(prod(s("a"), coc(pot(s("c"), 2), s("k")))))))]
doc_mix = v2(documento(simb, ecs[:0] + ec_mixta, [escala("t"), escala("c")]))
doc_mix["formas"][0]["objetivos"] = [obj_id("o", "balance:ecuaciones[0].derecha")]
rr = transformar(doc_mix)
check("terminoId de un sumando que se divide en #1, #2: pendiente y el motivo nombra las partes",
      objetivo_de(rr, "o")["estado"] == "pendiente" and "#1" in objetivo_de(rr, "o")["motivo"], str(objetivo_de(rr, "o")))
doc_mix["formas"][0]["objetivos"] = [obj_id("o", "balance:ecuaciones[0].derecha#1")]
check("terminoId con sufijo #1: el objetivo encuentra su coeficiente", objetivo_de(transformar(doc_mix), "o")["estado"] in ("satisfecho", "incompatible")
      and objetivo_de(transformar(doc_mix), "o").get("codigo") in (None, "signo"))
x = con_objetivos([obj_id("o", "otra:ecuaciones[0].izquierda")])
check("terminoId de otra ecuacion: rechazo de contrato", contrato_rechaza(solicitud(x), "formas[0].objetivos[0].terminoId"))
x = con_objetivos([{"id": "o", "ecuacionId": "balance", "valor": 1, "accion": "normalizar"}])
check("objetivo v2 sin terminoId ni termino: rechazo de contrato", contrato_rechaza(solicitud(x), "formas[0].objetivos[0]"))

# 2. Ubicacion de las condiciones.
doc_u = v2(doc_c)
lugares = {"ci": ("t", "desde"), "izq": ("x", "desde"), "flujo": ("x", "hasta"), "robin": ("x", "hasta")}
for c in doc_u["modelo"]["condiciones"]:
    v, e = lugares[c["id"]]
    c["ubicacion"] = {"variableId": v, "extremo": e}
ru = transformar(doc_u)
cu = {c["id"]: c for c in ru.get("condiciones", [])}
dom_u = {x["id"]: x for x in ru.get("dominios", [])}
check("ubicacion: cada condicion publica su variable nueva, extremo y valor transformado",
      ru["estado"] == "correcto" and cu["ci"]["lugar"]["variableId"] == "t_ad" and cu["izq"]["lugar"]["valor"] == n(0)
      and cu["flujo"]["lugar"]["valor"] == dom_u["intervalo-x"]["hasta"] and cu["flujo"]["lugar"]["original"] == s("ell")
      and cu["flujo"]["lugar"]["variableOriginal"] == "x", json.dumps(cu.get("flujo", {}).get("lugar"), ensure_ascii=False))
check("ubicacion: texto con el extremo y el mismo calculo de ecuaciones", "hasta" in cu["flujo"]["ubicacion"]
      and ru["ecuaciones"] == transformar(doc_c)["ecuaciones"] and certificado(ru))
check("ubicacion: paso de traza por condicion ubicada y referencias validas",
      sum(p["regla"] == "ubicacion de la condicion" for p in ru["desarrollo"]) == 4 and not problemas_traza(doc_u, ru), str(problemas_traza(doc_u, ru)[:3]))
x = copy.deepcopy(doc_u)
x["modelo"]["condiciones"][0]["ubicacion"] = {"variableId": "x", "extremo": "desde"}
check("ubicacion con otra variable que la del dominio: rechazo de contrato", contrato_rechaza(solicitud(x), "condiciones[0].ubicacion.variableId"))
x = copy.deepcopy(doc_u)
x["modelo"]["condiciones"][1]["dominioId"] = "intervalo-t"
x["modelo"]["condiciones"][1]["ubicacion"] = {"variableId": "t", "extremo": "hasta"}
check("condicion de frontera ubicada en el tiempo: rechazo de contrato", contrato_rechaza(solicitud(x), "condiciones[1].ubicacion.variableId"))
x = copy.deepcopy(doc_u)
x["modelo"]["condiciones"][1]["ubicacion"]["extremo"] = "centro"
check("extremo desconocido: rechazo de contrato", contrato_rechaza(solicitud(x), "condiciones[1].ubicacion.extremo"))

# 3. Escala declarada de una funcion: D(c) = Dstar Dh(u).
fDe = dict(fD, escala={"simboloId": "Dstar", "funcionAdimensional": "Dh"})
TERM_DIV = div(prod(llam("Dc", s("c")), grad(s("c"), "x")), "x")
sim_e = sim_v + [simbolo("Dstar", "parametro", None)]
doc_e = v2(documento(sim_e, [igualdad("balance", d(s("c"), "t"), TERM_DIV)], [escala("t"), escala("c"), escala("x")], funciones=[fDe]))
re_ = transformar(doc_e)
ctx = ctx_de(doc_e, re_)
check("escala de funcion: [Dstar] se infiere de la salida de D", re_["estado"] == "correcto"
      and next(x for x in re_["dimensional"]["simbolos"] if x["id"] == "Dstar") == {"id": "Dstar", "dimension": {"L": {"n": 2, "d": 1}, "T": {"n": -1, "d": 1}}, "origen": "inferida"})
check("escala de funcion: la divergencia queda Dstar t_ref/x_ref^2 div(Dh(u) grad u)",
      igual(ctx, re_["ecuaciones"][0]["igualdad"]["derecha"], prod(coc(prod(s("Dstar"), s("t_ref")), pot(s("x_ref"), 2)), div(prod(llam("Dh", s("c_ad")), grad(s("c_ad"), "x_ad")), "x_ad"))),
      texto(re_["ecuaciones"][0]["igualdad"]["derecha"]) if re_["estado"] == "correcto" else str(re_["diagnosticos"]))
check("escala de funcion: normalizacion completa y certificado", re_["normalizacion"]["estado"] == "completa" and certificado(re_), json.dumps(re_.get("normalizacion"), ensure_ascii=False))
fa = re_["funcionesAdimensionales"][0]
check("escala de funcion: Dh publicada con su definicion Dh(w) = D(c_ref w)/Dstar",
      fa["id"] == "Dh" and fa["funcionId"] == "Dc" and fa["escalaId"] == "Dstar" and fa["entradas"] == [{}] and fa["salida"] == {}
      and fa["argumentos"] == [{"escala": s("c_ref"), "extraida": True}], json.dumps(fa, ensure_ascii=False))
check("escala de funcion: traza con el paso de la escala y referencias validas",
      any(p["regla"] == "escala declarada de funcion" for p in re_["desarrollo"]) and not problemas_traza(doc_e, re_), str(problemas_traza(doc_e, re_)[:3]))
doc_e2 = copy.deepcopy(doc_e)
doc_e2["formas"][0]["objetivos"] = [obj_id("dif", "balance:ecuaciones[0].derecha")]
rr = transformar(doc_e2)
check("escala de funcion: objetivo sobre el termino variable -> t_ref = x_ref^2/Dstar",
      objetivo_de(rr, "dif")["estado"] == "satisfecho" and igual(ctx, escala_de(rr, "t")["valor"], coc(pot(s("x_ref"), 2), s("Dstar"))) and certificado(rr))
ra_e = automatico(doc_e)
check("escala de funcion: la busqueda automatica certifica todas y hay formas completas",
      ra_e["estado"] == "correcto" and all(f["equivalencia"]["estado"] == "demostrada" for f in ra_e["formulaciones"])
      and any(f["normalizacion"]["estado"] == "completa" for f in ra_e["formulaciones"]))
sim_e3 = sim_e + [simbolo("c0", "parametro", dim(N=1, L=-3))]
doc_e3 = v2(documento(sim_e3, [igualdad("balance", d(s("c"), "t"), suma(TERM_DIV, prod(llam("Dc", s("c0")), coc(s("c"), pot(s("ell"), 2)))))],
                      [escala("t"), escala("c"), escala("x")], funciones=[fDe]))
doc_e3["modelo"]["simbolos"].append(simbolo("ell", "parametro", dim(L=1)))
rr = transformar(doc_e3)
check("escala de funcion: D(c) y D(c0) con escalas distintas -> rechazo (Dh no estaria bien definida)",
      rr["estado"] == "rechazado" and diag(rr, "escala_funcion_inconsistente") and "ecuaciones" not in rr)
x = copy.deepcopy(doc_e)
x["modelo"]["funciones"][0]["escala"]["simboloId"] = "c"
check("escala de funcion sobre un campo: rechazo de contrato", contrato_rechaza(solicitud(x), "funciones[0].escala.simboloId"))
x = copy.deepcopy(doc_e)
x["modelo"]["funciones"][0]["escala"]["funcionAdimensional"] = "t"
check("funcion adimensional con identidad ocupada: rechazo de contrato", contrato_rechaza(solicitud(x), "funciones[0].escala.funcionAdimensional"))
x = copy.deepcopy(doc_e)
x["modelo"]["simbolos"][-1]["dimension"] = dim(T=1)
rr = transformar(x)
check("escala de funcion con dimension distinta de la salida: rechazado por dimensiones", rr["estado"] == "rechazado" and diag(rr, "dimension_incompatible"))

# 4. Referencias del factor global.
def con_forma(doc, **campos):
    x = v2(doc)
    x["formas"][0].update(copy.deepcopy(campos))
    return x


rr = transformar(con_forma(forma_seccion3([]), referencias=[{"ecuacionId": "balance", "terminoId": ID_K}]))
ctx = ctx_de(forma_seccion3([]), rr)
check("referencia: se divide por k c_ref, el termino lineal queda u y el temporal 1/(k t_ref)",
      rr["estado"] == "correcto" and igual(ctx, rr["ecuaciones"][0]["factorGlobal"], prod(s("k"), s("c_ref")))
      and igual(ctx, rr["ecuaciones"][0]["igualdad"]["izquierda"], coc(d(s("c_ad"), "t_ad"), prod(s("k"), s("t_ref")))) and certificado(rr),
      texto(rr["ecuaciones"][0]["igualdad"]["izquierda"]) if rr["estado"] == "correcto" else str(rr["diagnosticos"]))
rr = transformar(con_forma(forma_seccion3([]), referencias=[{"ecuacionId": "balance", "terminoId": ID_K}],
                           objetivos=[obj_id("lin", ID_K), obj_id("dif", ID_D)]))
check("referencia: el objetivo sobre el termino de referencia sale dependiente; el de difusion fija x_ref = (D/k)^(1/2)",
      objetivo_de(rr, "lin")["estado"] == "dependiente" and objetivo_de(rr, "dif")["estado"] == "satisfecho"
      and igual(ctx, escala_de(rr, "x")["valor"], pot(coc(s("D"), s("k")), n(0.5))) and "t_ref" in rr["libres"] and certificado(rr))
rr = transformar(con_forma(forma_seccion3([]), referencias=[{"ecuacionId": "balance", "terminoId": "balance:ecuaciones[0].derecha.argumentos[7]"}]))
check("referencia inexistente: rechazada sin ecuaciones", rr["estado"] == "rechazado" and diag(rr, "referencia_no_encontrada") and "ecuaciones" not in rr)
x = con_forma(doc_c, referencias=[{"ecuacionId": "flujo", "terminoId": "flujo:condiciones[2].ecuacion.derecha"}])
rr = transformar(x)
cf = next(c for c in rr["condiciones"] if c["id"] == "flujo") if rr["estado"] == "correcto" else None
check("referencia en una condicion: el flujo se divide por q", cf is not None and igual(ctx_de(doc_c, rr), cf["factorGlobal"], s("q"))
      and igual(ctx_de(doc_c, rr), cf["ecuacion"]["derecha"], n(1)) and certificado(rr), str(rr["diagnosticos"]) if cf is None else texto(cf["ecuacion"]["izquierda"]))
x = con_forma(forma_seccion3([]), referencias=[{"ecuacionId": "balance", "terminoId": ID_K}, {"ecuacionId": "balance", "terminoId": ID_D}])
check("referencia duplicada para la misma igualdad: rechazo de contrato", contrato_rechaza(solicitud(x), "formas[0].referencias[1].ecuacionId"))
sim_cero = [dict(y, signo="cero") if y["id"] == "k" else y for y in reaccion_difusion()[0]]
rr = transformar(con_forma(documento(sim_cero, reaccion_difusion()[1], [escala("t"), escala("c"), escala("x")]), referencias=[{"ecuacionId": "balance", "terminoId": ID_K}]))
check("referencia con parametro nulo: rechazada, no se relaja en silencio", rr["estado"] == "rechazado" and diag(rr, "referencia_nula"))

# 5. Prioridad de escalas.
rr = transformar(forma_seccion3([OBJ_D]))
check("prioridad por defecto: con el objetivo de difusion se despeja t_ref y x_ref queda libre",
      escala_de(rr, "t")["estado"] == "relacionada" and rr["libres"] == ["c_ref", "x_ref"])
rp = transformar(con_forma(forma_seccion3([OBJ_D]), prioridadEscalas=["x"]))
check("prioridadEscalas [x]: se despeja x_ref = (D t_ref)^(1/2) y t_ref queda libre",
      rp["estado"] == "correcto" and escala_de(rp, "x")["estado"] == "relacionada" and rp["libres"] == ["c_ref", "t_ref"]
      and igual(ctx_de(forma_seccion3([]), rp), escala_de(rp, "x")["valor"], pot(prod(s("D"), s("t_ref")), n(0.5))) and certificado(rp),
      str(rp.get("libres")))
check("prioridadEscalas: se publica en la eleccion del vinculo y cambia la firma",
      rp["vinculo"]["eleccion"]["prioridadEscalas"] == ["x"] and rp["vinculo"]["firma"] != transformar(v2(forma_seccion3([OBJ_D])))["vinculo"]["firma"])
rp = transformar(con_forma(forma_seccion3([OBJ_D]), prioridadEscalas=["x_ref"]))
check("prioridadEscalas por id de escala: mismo efecto", rp["estado"] == "correcto" and rp["libres"] == ["c_ref", "t_ref"])
rr = transformar(con_forma(forma_seccion3([OBJ_D]), prioridadEscalas=["k"]))
check("prioridadEscalas con un parametro: rechazada", rr["estado"] == "rechazado" and diag(rr, "prioridad_desconocida"))
check("prioridadEscalas con duplicados: rechazo de contrato", contrato_rechaza(solicitud(con_forma(forma_seccion3([]), prioridadEscalas=["x", "x"])), "formas[0].prioridadEscalas"))
sol = solicitud(v2(solo), "adimensionalizar")
sol["opciones"] = {"prioridadEscalas": ["x", "c"]}
rp = procesar(sol)
uno_d = next((f for f in rp.get("formulaciones", []) if f["objetivosAplicados"] == [ID_D]), None)
check("busqueda automatica con prioridadEscalas: el objetivo de difusion despeja x_ref",
      rp["estado"] == "correcto" and uno_d is not None and escala_de(uno_d, "x")["estado"] != "libre" and escala_de(uno_d, "t")["estado"] == "libre"
      and all(f["equivalencia"]["estado"] == "demostrada" for f in rp["formulaciones"]) and rp["formaBase"]["prioridadEscalas"] == ["x", "c"])
sol = solicitud(v2(solo), "adimensionalizar")
sol["opciones"] = {"referencias": [{"ecuacionId": "balance", "terminoId": ID_K}]}
rp = procesar(sol)
check("busqueda automatica con referencia: todas certificadas y el termino de referencia excluido",
      rp["estado"] == "correcto" and all(f["equivalencia"]["estado"] == "demostrada" for f in rp["formulaciones"])
      and ID_K not in rp["cobertura"]["candidatos"])
sol = solicitud(v2(forma_seccion3([])), "adimensionalizar")
sol["formaId"] = "forma-1"
sol["opciones"] = {"prioridadEscalas": ["x"]}
check("opciones.prioridadEscalas con formaId: rechazo de contrato", contrato_rechaza(sol, "opciones.prioridadEscalas"))

# 6. Forma.transformaciones (documento v2 de Codex).
x = con_forma(doc_log, transformaciones=[LOG])
r_forma, r_sol = transformar(x), con_mapas(doc_log, [LOG])
check("Forma.transformaciones: mismo resultado que enviarlas en la solicitud",
      r_forma["estado"] == "correcto" and r_forma["ecuaciones"] == r_sol["ecuaciones"] and r_forma["vinculo"]["eleccion"]["transformaciones"] == [LOG])
sol = solicitud(x)
sol["transformaciones"] = [LOG]
check("mapas en la forma y en la solicitud a la vez: rechazo de contrato", contrato_rechaza(sol, "transformaciones"))
x2 = copy.deepcopy(x)
x2["formas"][0]["transformaciones"][0]["variableId"] = "D"
check("Forma.transformaciones con un parametro: rechazo de contrato", contrato_rechaza(solicitud(x2), "formas[0].transformaciones[0].variableId"))

print()
print("=" * 78)
print("Regresion: sumas internas ya adimensionales (1 + K c)")
print("=" * 78)

# Antes, 1 + K c_ref u se reescribia c_ref (K u + 1/c_ref): el nucleo quedaba
# dimensional y un objetivo igualaba a 1 un coeficiente con dimensiones
# (t_ref = c_ref/k). El certificado lo detectaba como 'no_demostrada'.
sim_sat = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"]),
           simbolo("De", "parametro", dim(L=2, T=-1)), simbolo("k", "parametro", dim(T=-1)), simbolo("K", "parametro", dim(N=-1, L=3))]
T_SAT = neg(coc(prod(s("k"), s("c")), suma(n(1), prod(s("K"), s("c")))))
doc_sat = documento(sim_sat, [igualdad("balance", d(s("c"), "t"), suma(prod(s("De"), lap(s("c"), "x")), T_SAT))],
                    [escala("t"), escala("c"), escala("x")], [objetivo("reac", "balance", T_SAT, -1)])
rr = transformar(doc_sat)
check("1 + K c: el objetivo de reaccion da t_ref = 1/k (dimensionalmente valido) y se certifica",
      rr["estado"] == "correcto" and igual(ctx_de(doc_sat, rr), escala_de(rr, "t")["valor"], coc(n(1), s("k"))) and certificado(rr),
      texto(escala_de(rr, "t")["valor"]) if rr["estado"] == "correcto" else rr["diagnosticos"])
check("1 + K c: el grupo interno es K c_ref (adimensional)", any(g["interno"] and g["adimensional"] and igual(ctx_de(doc_sat, rr), g["definicion"], prod(s("K"), s("c_ref"))) for g in rr["grupos"]))
ra_sat = automatico(documento(sim_sat, doc_sat["modelo"]["ecuaciones"], []))
check("1 + K c: la busqueda automatica solo publica formulaciones certificadas y completas",
      ra_sat["estado"] == "correcto" and all(f["equivalencia"]["estado"] == "demostrada" and f["normalizacion"]["estado"] == "completa" for f in ra_sat["formulaciones"]))

print()
print("=" * 78)
print("Funciones trascendentes ampliadas (tan, tanh, sinh, cosh, atan, erf)")
print("=" * 78)

for nombre in ("tan", "tanh", "sinh", "cosh", "atan", "erf"):
    rr = transformar(documento(sim_sat, [igualdad("balance", d(s("c"), "t"), prod(s("k"), s("c"), fun(nombre, prod(s("K"), s("c")))))],
                               [escala("t"), escala("c"), escala("x")]))
    check(f"{nombre}(K c): transformado y certificado", rr["estado"] == "correcto" and certificado(rr), rr.get("diagnosticos"))
rr = procesar(solicitud(documento(sim_sat, [igualdad("balance", d(s("c"), "t"), prod(s("k"), fun("tanh", s("c"))))], []), "analizar"))
check("tanh(c) con c dimensional: incompatible", rr["dimensional"]["estado"] == "incompatible")
ctx_t = A.Contexto({"x": {"rol": "coordenada", "constante": False, "dependeDe": set(), "signo": "desconocido"}}, {})
check("d tanh(x)/dx = 1 - tanh(x)^2", A.iguales(A.canonica(d(fun("tanh", s("x")), "x"), ctx_t, "expandir"),
                                                A.canonica(suma(n(1), neg(pot(fun("tanh", s("x")), 2))), ctx_t, "expandir")))
check("d atan(x)/dx = 1/(1 + x^2)", A.iguales(A.canonica(d(fun("atan", s("x")), "x"), ctx_t, "expandir"),
                                             A.canonica(coc(n(1), suma(n(1), pot(s("x"), 2))), ctx_t, "expandir")))

print()
print("=" * 78)
print("Ejemplos canonicos publicados")
print("=" * 78)

from generar_ejemplos_adimensionalizacion import EJEMPLOS, DIRECTORIO
for nombre, construir in EJEMPLOS.items():
    ruta_sol = DIRECTORIO / f"adimensionalizacion-{nombre}-solicitud.json"
    ruta_res = DIRECTORIO / f"adimensionalizacion-{nombre}-resultado.json"
    if not ruta_sol.exists() or not ruta_res.exists():
        check(f"ejemplo {nombre}: existe", False, "falta; ejecute tests/generar_ejemplos_adimensionalizacion.py")
        continue
    sol = json.loads(ruta_sol.read_text(encoding="utf-8"))
    actual = procesar(sol)
    check(f"ejemplo {nombre}: el resultado publicado coincide con el nucleo actual", actual == json.loads(ruta_res.read_text(encoding="utf-8")))

print()
if fallos:
    print(f"FALLAN {len(fallos)} comprobaciones:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todas las comprobaciones pasan.")
