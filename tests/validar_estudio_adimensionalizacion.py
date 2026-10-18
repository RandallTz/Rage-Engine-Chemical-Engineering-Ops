"""
Validacion de los estudios de una formulacion (operacion `estudiar`).

Cada analisis se contrasta con un resultado analitico conocido e
independiente del codigo:

  - calor 1D: modo exacto sin(pi xi) e^(-pi^2 tau) (Dirichlet) y
    cos(pi xi / 2) e^(-pi^2 tau / 4) (flujo nulo + Dirichlet); EDO u' = -u;
  - semejanza del calor: F'' + (eta/2) F' = 0 con eta = xi / tau^(1/2);
  - Fisher-KPP: sin dilataciones; onda viajera F'' + c F' + F - F^2 = 0;
  - conveccion-difusion con 1/Pe = 1e-3: perturbacion singular, capa de
    espesor 1e-3 en el extremo de salida y malla de Peclet de celda <= 2;
  - Brusselator: Turing para B > (1 + A/sqrt(d))^2, Hopf en B = 1 + A^2;
  - pliegues de p + u - u^3 en p = +-2/(3 sqrt 3).

Ejecutar desde la raiz:  python tests/validar_estudio_adimensionalizacion.py
"""

import copy
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

from core.adimensionalizacion import algebra as A
from core.adimensionalizacion import procesar
from casos_adimensionalizacion import (OBJ_A, OBJ_D, OBJ_K, coc, d, dim, documento, escala, forma_seccion3, fun, igualdad, lap, n,
                                       neg, objetivo, pot, prod, reaccion_difusion, s, simbolo, solicitud, suma)

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + str(detalle)) if detalle and not ok else ''}")
    if not ok:
        fallos.append(nombre)


def estudiar(doc, estudio=None, forma=True, transformaciones=None, opciones=None):
    sol = {"formato": "adimensionalizacion.solicitud", "version": 1, "operacion": "estudiar", "documento": copy.deepcopy(doc)}
    if forma:
        sol["formaId"] = doc["activaId"]
    if estudio is not None:
        sol["estudio"] = estudio
    if transformaciones:
        sol["transformaciones"] = transformaciones
    if opciones:
        sol["opciones"] = opciones
    r = procesar(sol)
    if r["estado"] != "correcto":
        # Para que una prueba falle con el motivo, no con un KeyError.
        r["estudio"] = {k: {"estado": "solicitud_" + r["estado"], "motivo": r["diagnosticos"]} for k in
                        ("estructura", "sensibilidad", "valores", "asintotica", "escalas", "simetrias", "estabilidad", "continuacion", "simulacion")}
    return r


def v2(doc):
    x = copy.deepcopy(doc)
    x["version"] = 2
    return x


def obj_id(i, tid, valor=1, ecuacion="balance"):
    return {"id": i, "ecuacionId": ecuacion, "terminoId": tid, "valor": valor, "accion": "normalizar"}


def ctx_simple(ids):
    return A.Contexto({i: {"rol": r, "constante": r == "parametro", "dependeDe": set(dep), "signo": sg} for i, r, dep, sg in ids}, {})


PI = math.pi

print("=" * 78)
print("Contrato de la operacion estudiar")
print("=" * 78)

doc3 = forma_seccion3([OBJ_K, OBJ_A, OBJ_D])
r = estudiar(doc3)
check("estudiar sin valores: correcto, con formulacion y estudio", r["estado"] == "correcto" and "formulacion" in r and "estudio" in r, r.get("diagnosticos"))
check("estudiar: la formulacion es la misma que transformar", r["formulacion"]["ecuaciones"] == procesar(solicitud(doc3))["ecuaciones"])
check("sin valores: valores en requiere_datos con los que faltan", r["estudio"]["valores"]["estado"] == "requiere_datos"
      and set(r["estudio"]["valores"]["faltan"]) >= {"D", "k", "a"}, r["estudio"]["valores"].get("faltan"))
rr = estudiar(doc3, {"valores": [{"simboloId": "D", "valor": 1, "unidad": "s"}]})
check("valor con unidad de otra dimension: rechazado", rr["estado"] == "rechazado" and any(x["codigo"] == "dimension_incompatible" for x in rr["diagnosticos"]))
rr = estudiar(doc3, {"valores": [{"simboloId": "c", "valor": 1}]})
check("valor para una variable: rechazado", rr["estado"] == "rechazado" and any(x["codigo"] == "valor_no_admitido" for x in rr["diagnosticos"]))
rr = estudiar(doc3, {"valores": [{"simboloId": "k", "valor": -1, "unidad": "1/s"}]})
check("valor que contradice el signo declarado: rechazado", rr["estado"] == "rechazado" and any(x["codigo"] == "signo_contradictorio" for x in rr["diagnosticos"]))
rr = procesar({**solicitud(doc3), "operacion": "estudiar", "estudio": {"analisis": ["magia"]}})
check("analisis desconocido: rechazo de contrato", rr["estado"] == "rechazado" and rr["diagnosticos"][0]["codigo"] == "contrato")
solo = documento(reaccion_difusion()[0], reaccion_difusion()[1], [], dominios=reaccion_difusion()[2])
auto = procesar({**solicitud(solo, "adimensionalizar")})
iguales = True
for f in auto["formulaciones"]:
    e = estudiar(solo, {"objetivos": f["objetivosAplicados"], "analisis": ["estructura"]}, forma=False)
    if e["estado"] != "correcto" or e["formulacion"]["ecuaciones"] != f["ecuaciones"] or e["formulacion"]["escalas"] != f["escalas"]:
        iguales = False
check("estudiar con los objetivos de cada formulacion automatica la reproduce exactamente (8 de 8)", iguales and len(auto["formulaciones"]) == 8)
from core.adimensionalizacion import capacidades
check("capacidades: operacion estudiar y lista de estudios", "estudiar" in capacidades()["operaciones"] and "simulacion" in capacidades()["estudios"])

print()
print("=" * 78)
print("Estructura, sensibilidad y valores (seccion 3)")
print("=" * 78)

VAL3 = [{"simboloId": "D", "valor": 1e-9, "unidad": "m^2/s"}, {"simboloId": "k", "valor": 0.1, "unidad": "1/s"},
        {"simboloId": "a", "valor": 2e-4, "unidad": "m^3/(mol*s)"}, {"simboloId": "ell", "valor": 1, "unidad": "cm"}]
r = estudiar(forma_seccion3([OBJ_K]), {"valores": VAL3 + [{"simboloId": "c_ref", "valor": 100, "unidad": "mol/m^3"},
                                                         {"simboloId": "x_ref", "valor": 1, "unidad": "mm"}]})
est = r["estudio"]
tipos = {t["id"]: t["tipo"] for t in est["estructura"]["ecuaciones"][0]["terminos"]}
check("estructura: acumulacion, difusion, reaccion lineal y no lineal",
      list(tipos.values()) == ["acumulacion", "difusion", "reaccion", "reaccion"], tipos)
lin = {t["id"]: t["lineal"] for t in est["estructura"]["ecuaciones"][0]["terminos"]}
check("estructura: k u lineal, a u^2 no lineal", lin["balance:ecuaciones[0].derecha.argumentos[1]"] is True and lin["balance:ecuaciones[0].derecha.argumentos[2]"] is False)
grupos = {g["grupoId"]: g for g in est["estructura"]["grupos"]}
dif = next(g for g in est["estructura"]["grupos"] if any(l.get("tipoTermino") == "difusion" for l in g["lecturas"]))
check("estructura: el grupo de la difusion es un numero de Fourier (difusion frente a acumulacion)",
      dif["nombreClasico"] == "número de Fourier (Fo)", dif)
check("estructura: el objetivo normaliza la reaccion lineal", any(x["tipo"] == "reaccion" for x in est["estructura"]["normalizados"]))
sens = {g["grupoId"]: g["exponentes"] for g in est["sensibilidad"]["grupos"]}
check("sensibilidad: exponentes exactos del Fourier D/(k x_ref^2)", sens[dif["grupoId"]] == {"D": {"n": 1, "d": 1}, "k": {"n": -1, "d": 1}, "x_ref": {"n": -2, "d": 1}},
      sens[dif["grupoId"]])
vg = {g["grupoId"]: g["valor"] for g in est["valores"]["grupos"]}
check("valores: Fo = D/(k x_ref^2) = 1e-9/(0.1 * 1e-6) = 0.01", abs(vg[dif["grupoId"]] - 0.01) < 1e-12, vg)
vesc = {e["escalaId"]: e for e in est["valores"]["escalas"]}
check("valores: t_ref = 1/k = 10 s en SI", abs(vesc["t_ref"]["valorSI"] - 10.0) < 1e-12 and vesc["t_ref"]["unidadSI"] == "s")
check("valores: escala libre con unidad convertida (1 mm = 0.001 m)", abs(vesc["x_ref"]["valorSI"] - 1e-3) < 1e-15)
check("valores: dispersion de magnitudes publicada", est["valores"]["dispersionMaxima"] is not None)

print()
print("=" * 78)
print("Simetrias")
print("=" * 78)

sim_calor = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"]),
             simbolo("D", "parametro", dim(L=2, T=-1)), simbolo("ell", "parametro", dim(L=1)), simbolo("c0", "parametro", dim(N=1, L=-3))]
ec_calor = igualdad("balance", d(s("c"), "t"), prod(s("D"), lap(s("c"), "x")))
doc_calor = documento(sim_calor, [ec_calor], [escala("t"), escala("c"), escala("x")], [objetivo("dif", "balance", prod(s("D"), lap(s("c"), "x")))],
                      dominios=[{"id": "ix", "variableId": "x", "desde": n(0), "hasta": s("ell")}])
r = estudiar(doc_calor, {"analisis": ["simetrias"]})
simet = r["estudio"]["simetrias"]
gens = [g["exponentes"] for g in simet["generadores"]]
check("calor: dos generadores (dilatacion difusiva y escalado lineal del campo)", len(gens) == 2, gens)
red = [x for x in simet["reducciones"] if x["tipo"] == "semejanza"]
check("calor: reduccion de semejanza con eta = xi/tau^(1/2), comprobada", len(red) >= 1 and red[0]["estado"] == "calculado", red)
if red:
    eta, F = red[0]["variable"]["id"], red[0]["perfiles"][0]["id"]
    ctx = ctx_simple([(eta, "coordenada", [], "desconocido"), (F, "campo", [eta], "desconocido")])
    ode = A.canonica(red[0]["ecuaciones"][0]["ecuacion"]["izquierda"], ctx, "expandir")
    esperado = A.canonica(suma(d(s(F), eta, 2), prod(coc(s(eta), n(2)), d(s(F), eta))), ctx, "expandir")
    proporcional = any(A.iguales(A.multiplicar(ode, A.numero(f)), esperado) for f in (1, -1))
    check("calor: la EDO reducida es F'' + (eta/2) F' = 0", proporcional, json.dumps(red[0]["ecuaciones"][0]["ecuacion"]["izquierda"])[:300])
check("calor: traslaciones en tau y xi; onda viajera publicada", set(simet["traslaciones"]) == {"t_ad", "x_ad"}
      and any(x["tipo"] == "onda_viajera" for x in simet["reducciones"]))

simb, ecs, doms = reaccion_difusion()
r = estudiar(forma_seccion3([OBJ_K, OBJ_A, OBJ_D]), {"analisis": ["simetrias"]})
simet = r["estudio"]["simetrias"]
check("Fisher-KPP: sin dilataciones (la reaccion fija las escalas)", simet["generadores"] == [], simet["generadores"])
onda = next((x for x in simet["reducciones"] if x["tipo"] == "onda_viajera"), None)
check("Fisher-KPP: reduccion de onda viajera publicada", onda is not None and onda["estado"] == "calculado")
if onda:
    z, F, c = onda["variable"]["id"], onda["perfiles"][0]["id"], onda["velocidad"]
    ctx = ctx_simple([(z, "coordenada", [], "desconocido"), (F, "campo", [z], "desconocido"), (c, "parametro", [], "desconocido")])
    ode = A.canonica(onda["ecuaciones"][0]["ecuacion"]["izquierda"], ctx, "expandir")
    # Residuo publicado: izquierda - derecha de u_tau = u_xixi + u - u^2  ->  -c F' - F'' - F + F^2.
    esperado = A.canonica(suma(neg(prod(s(c), d(s(F), z))), neg(d(s(F), z, 2)), neg(s(F)), pot(s(F), 2)), ctx, "expandir")
    check("Fisher-KPP: EDO de onda  F'' + c F' + F - F^2 = 0", A.iguales(ode, esperado) or A.iguales(A.negar(ode), esperado),
          json.dumps(onda["ecuaciones"][0]["ecuacion"]["izquierda"])[:300])

print()
print("=" * 78)
print("Asintotica y escalas: conveccion-difusion con 1/Pe = 1e-3")
print("=" * 78)

sim_cd = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"]),
          simbolo("v", "parametro", dim(L=1, T=-1)), simbolo("D", "parametro", dim(L=2, T=-1)), simbolo("ell", "parametro", dim(L=1))]
TERM_V = prod(s("v"), d(s("c"), "x"))
ec_cd = igualdad("balance", suma(d(s("c"), "t"), TERM_V), prod(s("D"), lap(s("c"), "x")))
doc_cd = v2(documento(sim_cd, [ec_cd], [escala("t"), escala("c"), escala("x")],
                      [objetivo("conv", "balance", TERM_V)], dominios=[{"id": "ix", "variableId": "x", "desde": n(0), "hasta": s("ell")}]))
# Dos terminos a la izquierda: se divide por el temporal (referencia v2) y el
# objetivo de conveccion fija t_ref = x_ref / v.
doc_cd["formas"][0]["referencias"] = [{"ecuacionId": "balance", "terminoId": "balance:ecuaciones[0].izquierda.argumentos[0]"}]
VAL_CD = [{"simboloId": "v", "valor": 1, "unidad": "m/s"}, {"simboloId": "D", "valor": 1e-3, "unidad": "m^2/s"},
          {"simboloId": "ell", "valor": 1, "unidad": "m"}, {"simboloId": "x_ref", "valor": 1, "unidad": "m"},
          {"simboloId": "c_ref", "valor": 1, "unidad": "mol/m^3"}]
r = estudiar(doc_cd, {"valores": VAL_CD, "analisis": ["asintotica", "escalas", "estructura"]})
asin = r["estudio"]["asintotica"]
e0 = asin["ecuaciones"][0] if asin.get("ecuaciones") else {}
capa = (e0.get("espacial") or {}).get("capa", {})
check("asintotica: la difusion es despreciable a escala unidad", asin["estado"] == "calculado" and any("derecha" in x for x in e0.get("despreciables", [])), asin)
check("asintotica: perturbacion singular que pierde una condicion", capa.get("tipo") == "perturbacion_singular" and capa.get("condicionesPerdidas") == 1, capa)
check("asintotica: espesor de capa delta = 1/Pe = 1e-3", capa.get("espesor") is not None and abs(capa["espesor"] - 1e-3) < 1e-12, capa.get("espesor"))
check("asintotica: la capa esta en el extremo de salida (hasta, xi = 1)", (capa.get("ubicacion") or {}).get("lado") == "hasta"
      and abs(capa["ubicacion"]["en"]["valor"] - 1.0) < 1e-12, capa.get("ubicacion"))
check("asintotica: ecuacion reducida publicada sin la difusion", "reducida" in e0 and e0["reducida"]["derecha"] == {"tipo": "numero", "valor": 0})
estr = {g["grupoId"]: g for g in r["estudio"]["estructura"]["grupos"]}
check("estructura: el grupo de la difusion es Fo frente a la acumulacion y 1/Pe frente a la conveccion (ambas con coeficiente 1)",
      any(g["nombreClasico"] == "número de Fourier (Fo)" and "inverso del número de Péclet (1/Pe)" in g["nombresClasicos"] for g in estr.values()), estr)
esc = r["estudio"]["escalas"]
c0 = esc["coordenadas"][0] if esc.get("coordenadas") else {}
check("escalas: difusividad efectiva 1e-3 y velocidad 1", abs(c0.get("difusividad", 0) - 1e-3) < 1e-12 and abs(c0.get("velocidad", 0) - 1) < 1e-12, c0)
check("escalas: nodos por Peclet de celda <= 2 = ceil(1/(2e-3)) + 1 = 501", c0.get("malla", {}).get("nodosPeclet") == 501, c0.get("malla"))
check("escalas: longitud interna D/v = 1e-3", any(abs(x["longitud"] - 1e-3) < 1e-12 for x in c0.get("longitudesInternas", [])))
check("escalas: rigidez del operador discreto publicada", "rigidez" in c0 and c0["rigidez"]["cociente"] > 1, c0.get("rigidez"))

print()
print("=" * 78)
print("Simulacion contra soluciones exactas")
print("=" * 78)

sim_cal = sim_calor
conds = [{"id": "ci", "tipo": "inicial", "dominioId": "it", "ecuacion": igualdad("ci-eq", s("c"), prod(s("c0"), fun("sin", prod(n(PI), coc(s("x"), s("ell"))))))},
         {"id": "izq", "tipo": "dirichlet", "dominioId": "ix", "ecuacion": igualdad("izq-eq", s("c"), n(0)), "ubicacion": {"variableId": "x", "extremo": "desde"}},
         {"id": "der", "tipo": "dirichlet", "dominioId": "ix", "ecuacion": igualdad("der-eq", s("c"), n(0)), "ubicacion": {"variableId": "x", "extremo": "hasta"}}]
doms_cal = [{"id": "ix", "variableId": "x", "desde": n(0), "hasta": s("ell")}, {"id": "it", "variableId": "t", "desde": n(0), "hasta": prod(n(1), s("tf"))}]
sim_cal2 = sim_cal + [simbolo("tf", "parametro", dim(T=1))]
doc_sim = v2(documento(sim_cal2, [ec_calor], [escala("t"), escala("c"), escala("x")], [objetivo("dif", "balance", prod(s("D"), lap(s("c"), "x")))],
                       dominios=doms_cal, condiciones=conds))
VAL_SIM = [{"simboloId": "D", "valor": 1e-9, "unidad": "m^2/s"}, {"simboloId": "ell", "valor": 1, "unidad": "cm"}, {"simboloId": "c0", "valor": 50, "unidad": "mol/m^3"},
           {"simboloId": "tf", "valor": 1, "unidad": "s"}, {"simboloId": "x_ref", "valor": 1, "unidad": "cm"}, {"simboloId": "c_ref", "valor": 50, "unidad": "mol/m^3"}]
r = estudiar(doc_sim, {"valores": VAL_SIM, "analisis": ["simulacion"], "simulacion": {"tFinal": 0.2, "nodos": 81, "muestras": 11}})
simr = r["estudio"]["simulacion"]
if simr["estado"] == "calculado":
    xi = np.array(simr["xi"])
    tau = simr["tiempos"][-1]
    num = np.array(simr["campos"]["c_ad"][-1])
    exacta = np.sin(PI * xi) * math.exp(-PI ** 2 * tau)
    err = float(np.max(np.abs(num - exacta)))
    check("calor Dirichlet: error maximo frente a sin(pi xi) e^(-pi^2 tau) < 2e-4", err < 2e-4, err)
    check("calor Dirichlet: verificacion de malla publicada y pequena", simr["verificacionMalla"]["diferenciaRelativa"] < 1e-3, simr.get("verificacionMalla"))
    ns = {"__name__": "exportado"}
    try:
        exec(simr["codigoPython"], ns)
        exp_final = np.array(ns["perfiles"](ns["sol"])["c_ad"][-1])
        err_exp = float(np.max(np.abs(exp_final - exacta)))
    except Exception as ex:  # el script exportado debe ejecutarse solo
        err_exp = repr(ex)
    check("calor Dirichlet: el script de Python exportado se ejecuta y reproduce la solucion exacta (< 2e-4)",
          isinstance(err_exp, float) and err_exp < 2e-4, err_exp)
    fis = simr["fisico"]
    check("calor: restitucion a SI (x en m, t en s, c en mol/m^3)", abs(fis["coordenada"]["valoresSI"][-1] - 0.01) < 1e-15
          and abs(fis["tiempo"]["valoresSI"][-1] - tau * 1e-4 / 1e-9) < 1e-6 * tau * 1e5
          and abs(max(fis["campos"]["c"][0]) - 50) < 1e-6, (fis["coordenada"]["valoresSI"][-1], fis["tiempo"]["valoresSI"][-1]))
else:
    check("calor Dirichlet: simulacion calculada", False, simr)

conds_n = copy.deepcopy(conds)
conds_n[0]["ecuacion"] = igualdad("ci-eq", s("c"), prod(s("c0"), fun("cos", prod(n(PI / 2), coc(s("x"), s("ell"))))))
conds_n[1] = {"id": "izq", "tipo": "flujo", "dominioId": "ix", "ecuacion": igualdad("izq-eq", neg(prod(s("D"), d(s("c"), "x"))), n(0)),
              "ubicacion": {"variableId": "x", "extremo": "desde"}}
doc_n = v2(documento(sim_cal2, [ec_calor], [escala("t"), escala("c"), escala("x")], [objetivo("dif", "balance", prod(s("D"), lap(s("c"), "x")))],
                     dominios=doms_cal, condiciones=conds_n))
r = estudiar(doc_n, {"valores": VAL_SIM, "analisis": ["simulacion"], "simulacion": {"tFinal": 0.4, "nodos": 81, "muestras": 5}})
simr = r["estudio"]["simulacion"]
if simr["estado"] == "calculado":
    xi = np.array(simr["xi"])
    tau = simr["tiempos"][-1]
    err = float(np.max(np.abs(np.array(simr["campos"]["c_ad"][-1]) - np.cos(PI * xi / 2) * math.exp(-PI ** 2 * tau / 4))))
    check("calor flujo nulo + Dirichlet: error frente a cos(pi xi/2) e^(-pi^2 tau/4) < 2e-4", err < 2e-4, err)
else:
    check("calor flujo nulo: simulacion calculada", False, simr)

r = estudiar(doc_sim, {"valores": VAL_SIM, "analisis": ["estabilidad"]})
st = r["estudio"]["estabilidad"]
check("calor: todo valor constante es estado (continuo); se publica un representante estable",
      st["estado"] == "calculado" and st.get("continuo") is True and len(st["estados"]) == 1
      and st["estados"][0]["espacial"][0]["clase"] == "estable", {k: st.get(k) for k in ("continuo", "notaContinuo")})

sin_ubic = copy.deepcopy(doc_n)
for c in sin_ubic["modelo"]["condiciones"]:
    c.pop("ubicacion", None)
r = estudiar(sin_ubic, {"valores": VAL_SIM, "analisis": ["simulacion"], "simulacion": {"tFinal": 0.1, "nodos": 21}})
check("simulacion sin ubicacion de las fronteras: requiere datos y lo dice", r["estudio"]["simulacion"]["estado"] == "requiere_datos"
      and "ubicacion" in r["estudio"]["simulacion"]["motivo"])
r = estudiar(sin_ubic, {"valores": VAL_SIM, "analisis": ["simulacion"],
                        "simulacion": {"tFinal": 0.4, "nodos": 81, "muestras": 3, "fronteras": [{"condicionId": "izq", "extremo": "desde"}, {"condicionId": "der", "extremo": "hasta"}]}})
check("simulacion con simulacion.fronteras en lugar de la ubicacion v2", r["estudio"]["simulacion"]["estado"] == "calculado")

# Frontera periodica: c(x, 0) = c0 (1 + sin(2 pi x / ell) / 2) en [0, ell); el
# modo decae como e^(-4 pi^2 tau) y la media se conserva. Tiempo final dado en
# segundos: con t_ref = ell^2 / D = 1e5 s, tFinalSI = 5000 s es tau = 0.05.
conds_p = [{"id": "ci", "tipo": "inicial", "dominioId": "it", "ecuacion": igualdad("ci-eq", s("c"), prod(s("c0"), suma(n(1), prod(n(0.5), fun("sin", prod(n(2 * PI), coc(s("x"), s("ell"))))))))}]
doc_p = v2(documento(sim_cal2, [ec_calor], [escala("t"), escala("c"), escala("x")], [objetivo("dif", "balance", prod(s("D"), lap(s("c"), "x")))],
                     dominios=doms_cal, condiciones=conds_p))
r = estudiar(doc_p, {"valores": VAL_SIM, "analisis": ["simulacion"], "simulacion": {"tFinalSI": 5000, "nodos": 64, "muestras": 3, "periodica": True}})
simr = r["estudio"]["simulacion"]
if simr["estado"] == "calculado":
    xi = np.array(simr["xi"])
    tau = simr["tiempos"][-1]
    num = np.array(simr["campos"]["c_ad"][-1])
    exacta = 1 + 0.5 * np.sin(2 * PI * xi) * math.exp(-4 * PI ** 2 * tau)
    check("periodica: tFinalSI = 5000 s se convierte en tau = 0.05 con la inversa del mapa", abs(tau - 0.05) < 1e-12, tau)
    check("periodica: 64 nodos en [0, 1), sin repetir el extremo", len(xi) == 64 and abs(xi[0]) < 1e-15 and abs(xi[-1] - 63 / 64) < 1e-12, (len(xi), xi[-1]))
    err = float(np.max(np.abs(num - exacta)))
    check("periodica: error frente a 1 + sin(2 pi xi) e^(-4 pi^2 tau) / 2 < 2e-3", err < 2e-3, err)
    check("periodica: la media se conserva (1e-10)", abs(float(np.mean(num)) - 1) < 1e-10, float(np.mean(num)))
    check("periodica: el metodo lo declara y la malla refinada usa 2N nodos", simr["metodo"].get("frontera") == "periodica"
          and simr["verificacionMalla"].get("nodosRefinados") == 128, (simr["metodo"], simr.get("verificacionMalla")))
    ns = {"__name__": "exportado"}
    try:
        exec(simr["codigoPython"], ns)
        err_exp = float(np.max(np.abs(np.array(ns["perfiles"](ns["sol"])["c_ad"][-1]) - num)))
    except Exception as ex:
        err_exp = repr(ex)
    check("periodica: el script exportado repite la simulacion del nucleo (< 1e-6)", isinstance(err_exp, float) and err_exp < 1e-6, err_exp)
else:
    check("periodica: simulacion calculada", False, simr)
r = estudiar(doc_sim, {"valores": VAL_SIM, "analisis": ["simulacion"], "simulacion": {"tFinal": 0.05, "nodos": 21, "periodica": True}})
check("periodica con condiciones de extremo declaradas: requiere datos y las nombra", r["estudio"]["simulacion"]["estado"] == "requiere_datos"
      and "izq" in r["estudio"]["simulacion"]["motivo"], r["estudio"]["simulacion"])
r = estudiar(doc_p, {"valores": VAL_SIM, "analisis": ["simulacion"], "simulacion": {"tFinal": 0.05, "tFinalSI": 5000}})
check("tFinal y tFinalSI a la vez: solicitud rechazada", r["estado"] != "correcto")

sim_ode = [simbolo("t", "tiempo", dim(T=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t"]), simbolo("k", "parametro", dim(T=-1)),
           simbolo("c0", "parametro", dim(N=1, L=-3)), simbolo("tf", "parametro", dim(T=1))]
doc_ode = documento(sim_ode, [igualdad("balance", d(s("c"), "t"), neg(prod(s("k"), s("c"))))], [escala("t"), escala("c")],
                    [objetivo("k", "balance", neg(prod(s("k"), s("c"))), -1)],
                    dominios=[{"id": "it", "variableId": "t", "desde": n(0), "hasta": s("tf")}],
                    condiciones=[{"id": "ci", "tipo": "inicial", "dominioId": "it", "ecuacion": igualdad("ci-eq", s("c"), s("c0"))}])
r = estudiar(doc_ode, {"valores": [{"simboloId": "k", "valor": 2, "unidad": "1/s"}, {"simboloId": "c0", "valor": 3, "unidad": "mol/m^3"},
                                   {"simboloId": "tf", "valor": 1, "unidad": "s"}, {"simboloId": "c_ref", "valor": 3, "unidad": "mol/m^3"}],
                       "analisis": ["simulacion"], "simulacion": {"tFinal": 2.0, "muestras": 5}})
simr = r["estudio"]["simulacion"]
check("EDO u' = -u: u(2) = e^-2", simr["estado"] == "calculado" and abs(simr["campos"]["c_ad"][-1][0] - math.exp(-2)) < 1e-5, simr.get("campos") or simr)
if simr["estado"] == "calculado":
    ns = {"__name__": "exportado"}
    try:
        exec(simr["codigoPython"], ns)
        v = float(ns["perfiles"](ns["sol"])["c_ad"][-1][0])
    except Exception as ex:
        v = repr(ex)
    check("EDO: el script exportado da e^-2", isinstance(v, float) and abs(v - math.exp(-2)) < 1e-5, v)

print()
print("=" * 78)
print("Estabilidad y continuacion")
print("=" * 78)


def brusselator(B, A_=2.0, d_=10.0, analisis=("estabilidad",), extra=None):
    sim = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)),
           simbolo("u", "campo", {}, ["t", "x"], signo="positivo"), simbolo("w", "campo", {}, ["t", "x"], signo="positivo"),
           simbolo("k", "parametro", dim(T=-1)), simbolo("A", "parametro", {}), simbolo("B", "parametro", {}),
           simbolo("Du", "parametro", dim(L=2, T=-1)), simbolo("Dw", "parametro", dim(L=2, T=-1))]
    T_UUW = prod(s("k"), pot(s("u"), 2), s("w"))
    T_DU = prod(s("Du"), lap(s("u"), "x"))
    ecu = igualdad("u", d(s("u"), "t"), suma(prod(s("k"), s("A")), neg(prod(s("k"), suma(s("B"), n(1)), s("u"))), T_UUW, T_DU))
    ecw = igualdad("w", d(s("w"), "t"), suma(prod(s("k"), s("B"), s("u")), neg(T_UUW), prod(s("Dw"), lap(s("w"), "x"))))
    doc = documento(sim, [ecu, ecw], [escala("t"), escala("x"), escala("u", transformar=False), escala("w", transformar=False)],
                    [objetivo("reac", "u", T_UUW), objetivo("dif", "u", T_DU)])
    vals = [{"simboloId": "k", "valor": 1, "unidad": "1/s"}, {"simboloId": "A", "valor": A_}, {"simboloId": "B", "valor": B},
            {"simboloId": "Du", "valor": 1e-9, "unidad": "m^2/s"}, {"simboloId": "Dw", "valor": d_ * 1e-9, "unidad": "m^2/s"}]
    est = {"valores": vals, "analisis": list(analisis), "cajaEstados": 10.0}
    est.update(extra or {})
    return estudiar(doc, est)


A_, d_ = 2.0, 10.0
B_turing = (1 + A_ / math.sqrt(d_)) ** 2
B_hopf = 1 + A_ ** 2
r = brusselator(3.0)
st = r["estudio"]["estabilidad"]
e0 = st["estados"][0] if st.get("estados") else None
check("Brusselator: un estado homogeneo (A, B/A) = (2, 1.5)", e0 is not None and len(st["estados"]) == 1
      and abs(e0["u"]["u"] - 2) < 1e-9 and abs(e0["u"]["w"] - 1.5) < 1e-9, st if e0 is None else e0["u"])
if e0:
    esp = e0["espacial"][0]
    check(f"Brusselator B = 3 > B_T = {B_turing:.4f}: homogeneamente estable e inestable de Turing", e0["homogeneo"] == "estable" and esp["clase"] == "turing", (e0["homogeneo"], esp["clase"]))
    kc_exacto = math.sqrt(A_ / math.sqrt(d_))
    check(f"Brusselator: numero de onda critico cerca de sqrt(A/sqrt(d)) = {kc_exacto:.4f}", abs(esp["kCritico"] - kc_exacto) < 0.15, esp["kCritico"])
r = brusselator(2.5)
st = r["estudio"]["estabilidad"]
check("Brusselator B = 2.5 < B_T: estable", st["estados"][0]["espacial"][0]["clase"] == "estable", st["estados"][0]["espacial"][0]["clase"])
r = brusselator(6.0)
st = r["estudio"]["estabilidad"]
check("Brusselator B = 6 > 1 + A^2: inestabilidad oscilatoria homogenea (Hopf)", st["estados"][0]["homogeneo"] == "inestable"
      and st["estados"][0]["espacial"][0]["clase"] == "oscilatoria_homogenea", (st["estados"][0]["homogeneo"], st["estados"][0]["espacial"][0]["clase"]))
r = brusselator(3.0, analisis=("continuacion",), extra={"continuacion": {"parametroId": "B", "desde": 1.0, "hasta": 8.0}})
co = r["estudio"]["continuacion"]
hopf = [x for x in co.get("especiales", []) if x["tipo"] == "hopf"]
check("continuacion Brusselator en B: Hopf en B = 1 + A^2 = 5", len(hopf) >= 1 and abs(hopf[0]["p"] - B_hopf) < 0.02, co.get("especiales") or co)
if hopf:
    check("continuacion: frecuencia de Hopf = sqrt(det J) = A", abs(hopf[0]["frecuencia"] - A_) < 0.05, hopf[0]["frecuencia"])

sim_p = [simbolo("t", "tiempo", dim(T=1)), simbolo("u", "campo", {}, ["t"]), simbolo("k", "parametro", dim(T=-1)),
         simbolo("p", "parametro", {}, signo="desconocido")]
T_KU = prod(s("k"), s("u"))
doc_p = documento(sim_p, [igualdad("e", d(s("u"), "t"), suma(prod(s("k"), s("p")), T_KU, neg(prod(s("k"), pot(s("u"), 3)))))],
                  [escala("t"), escala("u", transformar=False)], [objetivo("k", "e", T_KU)])
r = estudiar(doc_p, {"valores": [{"simboloId": "k", "valor": 1, "unidad": "1/s"}, {"simboloId": "p", "valor": 0.0}],
                     "analisis": ["estabilidad", "continuacion"], "continuacion": {"parametroId": "p", "desde": -1, "hasta": 1}, "cajaEstados": 3})
st = r["estudio"]["estabilidad"]
check("u' = p + u - u^3 con p = 0: tres estados (-1, 0, 1), dos estables", st["estado"] == "calculado" and len(st["estados"]) == 3
      and sorted(round(x["u"]["u"], 9) for x in st["estados"]) == [-1.0, 0.0, 1.0]
      and sum(x["homogeneo"] == "estable" for x in st["estados"]) == 2, [x["u"] for x in st.get("estados", [])])
co = r["estudio"]["continuacion"]
pl = sorted(x["p"] for x in co.get("especiales", []) if x["tipo"] == "pliegue")
exacto = 2 / (3 * math.sqrt(3))
check(f"continuacion: dos pliegues en p = +-{exacto:.6f}", len(pl) == 2 and abs(pl[0] + exacto) < 2e-3 and abs(pl[1] - exacto) < 2e-3, co.get("especiales") or co)
r = estudiar(doc_p, {"valores": [{"simboloId": "k", "valor": 1, "unidad": "1/s"}, {"simboloId": "p", "valor": 0.0}],
                     "analisis": ["continuacion"], "continuacion": {"parametroId": "k", "desde": 0.5, "hasta": 2}})
check("continuacion en un parametro que no esta en la formulacion: no aplicable", r["estudio"]["continuacion"]["estado"] == "no_aplicable",
      r["estudio"]["continuacion"])

print()
if fallos:
    print(f"FALLAN {len(fallos)} comprobaciones:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todas las comprobaciones pasan.")
