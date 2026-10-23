"""
Consolidacion de la entrega multifasica (docs/history/frontend/assignment-claude-consolidation-multiphase-2026-10-15.md).

  C0  capacidades coherentes con lo que ejecutan los ejemplos reales y con los modelos estaticos;
  C1  certificacion fisica separada del resultado numerico: controles negativos de materia, energia y
      segunda ley; T de frontera ausente; escala de residuos al cambiar ordenes de magnitud;
  C2  catalogo de series, IDs de fase en eventos (aparicion, desaparicion, sustitucion, reordenamiento de
      densidades, extraccion de una de dos fases liquidas) y cambio de denominacion supercritico;
  C3  contrastes fisicos independientes: referencias desplazadas, calor de mezcla y entalpias parciales por
      otra via, controles de estabilidad, mesetas, red invertida, convergencia y limites.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_consolidacion_v2.py [seccion ...]
"""

import copy
import json
import math
import subprocess
import sys
import time
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
warnings.filterwarnings("ignore")

import numpy as np

from backend import motor_ensamblaje as me
from backend import motor_ensamblaje_v2 as v2
from backend import motor_termodinamica as mt
from core import agua_iapws95 as agua
from core import ensamblaje_red as er
from core import mezclas as mz
from solicitudes_v2 import CAS, Red

FALLOS, CHECKS = [], [0]
R = mz.R
EJ = RAIZ / "docs" / "ejemplos" / "motor-v2"


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def seccion(t):
    print(f"\n{t}")


def serie(r, vid):
    return next(s["valores"] for s in r["resultados"]["series"] if s["variableId"] == vid)


def residuo(r, eid):
    return next(x for x in r["resultados"]["residuos"] if x["ecuacionId"] == eid)


def aspecto(r, aid):
    return next(a for a in r["resultados"]["certificacion"]["aspectos"] if a["id"] == aid)


def codigos(r):
    v = r.get("validacion", r)
    return {d["codigo"] for d in v["diagnosticos"]}


SECCIONES = sys.argv[1:]


def activa(n):
    return not SECCIONES or n in SECCIONES


def combinacion_observada(tipos):
    if len(tipos) == 1:
        return "una_fase"
    if tipos.count("liquido") >= 2:
        return "liquido_liquido"
    return "liquido_vapor"


def contacto_agua(escala=1.0, tf="2000"):
    m = lambda x: str(x * escala)
    return (Red("cert", ("agua",), tf=(tf, "s"), muestras=6)
            .paquete("w", "agua-iapws95")
            .volumen("A", "w", {"agua": (m(10), "kg")}, ("T", "350", "K"), V=(m(0.0105), "m3"))
            .volumen("B", "w", {"agua": (m(5), "kg")}, ("T", "300", "K"), V=(m(0.0052), "m3"))
            .calor("c", "A", "B", G=(m(200), "W/K")))


def corrida_corrupta(sol, j_vol, d_mat=0.0, d_E=0.0):
    """Resuelve con el lado derecho corrompido en el volumen j: d_mat mol/s en su primer componente y
    d_E W en su energia. La red deja de conservar; el resto del codigo no se toca."""
    orig = er.Sistema.__call__

    def rhs(self, t, y):
        d = np.array(orig(self, t, y), dtype=float)
        o = self.offs[j_vol]
        d[o] += d_mat
        d[o + len(self.red.volumenes[j_vol].comp)] += d_E
        return d
    er.Sistema.__call__ = rhs
    try:
        return me.resolver(copy.deepcopy(sol))
    finally:
        er.Sistema.__call__ = orig


# ======================================================================
if activa("0"):
    seccion("C0. Capacidades coherentes con la implementacion y los ejemplos")
    cap = v2.capacidades_v2()
    paq = {p["modelo"]["id"]: p for p in cap["paquetes"]}
    comb = {mid: {c["id"]: c for c in p["combinaciones"]} for mid, p in paq.items()}
    lle = comb["nrtl-lle-agua-butanol"]["liquido_liquido"]
    check(lle["publicada"] and lle["evidencia"] == "contrastada" and "IUPAC" in lle["motivo"],
          "C0.1: LL/LLV del paquete agua-butanol publicada y contrastada")
    check(comb["mezcla-ideal"]["liquido_liquido"]["evidencia"] == "imposible_en_el_modelo"
          and not comb["mezcla-ideal"]["liquido_liquido"]["publicada"], "solucion ideal: LL imposible en el modelo")
    check(comb["nrtl-chemsep"]["liquido_liquido"]["evidencia"] == "cualitativa"
          and comb["nrtl-chemsep"]["liquido_vapor"]["evidencia"] == "cualitativa",
          "ChemSep: LL y LV cualitativas a nivel de paquete (sin el mismo nivel de evidencia para todo binario)")
    pares = paq["nrtl-chemsep"]["pares"]
    ev = {frozenset(x["componentesCAS"]): x["evidencia"] for x in pares}
    check(ev.get(frozenset([CAS["etanol"], CAS["agua"]])) == "contrastada" and
          sum(1 for e in ev.values() if e == "contrastada") == 1, "pares ChemSep: solo etanol-agua contrastado")
    check(frozenset([CAS["agua"], CAS["benceno"]]) not in ev, "pares ChemSep: agua-benceno no se anuncia (sin datos)")
    sol_ = comb["agua-iapws95"]["solido"]
    check(not sol_["publicada"] and "estatico" in sol_["motivo"] and "M5 pendiente" not in json.dumps(cap),
          "C0.2: el hielo existe como estatico y no se habilita en volumenes (sin texto 'M5 pendiente')")
    check(any("hielo" in x["elemento"] for x in cap["noSoportado"]), "noSoportado: hielo en volumenes dinamicos")
    t_cap = {m["id"]: m for m in mt.capacidades()["modelos"]}
    check(t_cap["agua-iapws95-hielo-ih"]["dinamica"] is False and "agua-iapws95-hielo-ih" not in paq,
          "capacidad puntual del hielo: dinamica false y ausente de los paquetes del ensamblaje")
    for mid in ("mezcla-ideal", "nrtl-chemsep", "nrtl-lle-agua-butanol"):
        check(paq[mid]["dominio"] == t_cap[mid]["dominio"] and paq[mid]["componentesCAS"] == t_cap[mid]["componentesCAS"]
              and paq[mid]["dominio"]["P"][1] == 5e5, f"{mid}: dominio y especies iguales en ambos catalogos (P <= 5 bar)")
    # cada ejemplo ejecutado debe caer en combinaciones publicadas de su paquete
    n_ej = 0
    for f in sorted(EJ.glob("motor-ensamblaje-v2-resolver-*-respuesta.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        s = json.loads(f.with_name(f.name.replace("-respuesta", "-peticion")).read_text(encoding="utf-8"))
        for vid, lista in (r["resultados"] or {}).get("estados", {}).items():
            vol = next(v for v in s["volumenes"] if v["id"] == vid)
            mid = next(p for p in s["paquetes"] if p["id"] == vol["paqueteId"])["modelo"]["id"]
            for m in lista:
                c = combinacion_observada([x["tipo"] for x in m["evaluacion"]["fases"]])
                n_ej += 1
                check(comb[mid][c]["publicada"] and paq[mid]["dinamica"],
                      f"{f.name}: {vid} usa {c} con {mid}, que debe estar publicada")
    check(n_ej > 20, f"coherencia contra {n_ej} estados de ejemplos reales")
    for f in sorted(EJ.glob("motor-termodinamica-*-respuesta.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r["estado"] == "evaluado":
            m = t_cap[r["modelo"]["id"]]
            check(all(x["tipo"] in m["fases"] for x in r["evaluacion"]["fases"]), f"{f.name}: fases en la capacidad")
    # el borrador C4 (frontera abierta, caudal por restriccion) no esta implementado: se rechaza entero
    b = json.loads((RAIZ / "docs" / "ejemplos" / "borrador-frontera-abierta" / "olla-abierta-peticion.json")
                   .read_text(encoding="utf-8"))
    rb = me.resolver(b)
    check(rb["resultados"] is None and rb["estado"] in ("invalido", "no_soportado"),
          f"borrador de frontera abierta: rechazado por el servicio actual ({rb['estado']}, "
          f"{sorted(codigos(rb))[:4]})")
    # el hielo no se acepta como paquete de un volumen
    red = (Red("hielo-din", ("agua",), tf=("10", "s"), muestras=3).paquete("w", "agua-iapws95-hielo-ih")
           .volumen("A", "w", {"agua": ("1", "kg")}, ("T", "260", "K"), V=("0.0011", "m3"), adiabatico=True))
    rv = me.validar(red.solicitud())[0]
    check(any(d["estado"] in ("no_soportado", "invalido") for d in rv["diagnosticos"]) and
          me.resolver(red.solicitud())["resultados"] is None, "hielo en un volumen dinamico: rechazado")

# ======================================================================
if activa("1"):
    seccion("C1. Certificacion fisica separada del resultado numerico")
    sol = contacto_agua().solicitud()
    r = me.resolver(sol)
    c = r["resultados"]["certificacion"]
    check(r["estado"] == "resuelto" and c["estado"] == "cumple" and c["ultimaMuestraCertificada"] == len(r["resultados"]["tiempos"]) - 1
          and aspecto(r, "segunda_ley")["estado"] == "cumple", "red cerrada nominal: certificacion cumple")
    check("MOTOR_ENS_CERTIFICACION_NO_CUMPLE" not in codigos(r), "nominal: sin diagnostico de certificacion")
    # materia corrupta en B: 1e-5 de la escala de la transferencia de calor no aplica; se usa n
    nB = 5 / agua.M
    rc = corrida_corrupta(sol, 1, d_mat=1e-5 * nB / 2000)
    a = aspecto(rc, "conservacion")
    check(rc["estado"] == "resuelto" and rc["resultados"]["certificacion"]["estado"] == "no_cumple"
          and a["estado"] == "no_cumple" and "global.materia.1" in a["referencias"],
          f"materia corrupta: estado numerico 'resuelto', certificacion no_cumple ({a['motivo']})")
    check("MOTOR_ENS_CERTIFICACION_NO_CUMPLE" in codigos(rc), "materia corrupta: diagnostico publicado")
    check(a["primeraMuestraNoCumple"] is not None and
          rc["resultados"]["certificacion"]["ultimaMuestraCertificada"] == a["primeraMuestraNoCumple"] - 1,
          "materia corrupta: primera muestra que incumple y ultima certificada coherentes; trayectoria no recortada")
    check(len(rc["resultados"]["tiempos"]) == len(r["resultados"]["tiempos"]), "la evidencia se conserva entera")
    # energia corrupta en B: 1 W espurio
    re_ = corrida_corrupta(sol, 1, d_E=1.0)
    a = aspecto(re_, "conservacion")
    check(re_["resultados"]["certificacion"]["estado"] == "no_cumple" and "global.energia" in a["referencias"],
          f"energia corrupta: detectada en global.energia ({residuo(re_, 'global.energia')['maximoEscalado']:.3g})")
    # calor desde una frontera mas fria
    red = (Red("frio", ("agua",), tf=("100", "s"), muestras=4).paquete("w", "agua-iapws95")
           .volumen("A", "w", {"agua": ("1", "kg")}, ("T", "350", "K"), V=("0.00105", "m3"))
           .calor("q", None, "A", Q=("1000", "W"), Tfrontera=("300", "K")))
    rf = me.resolver(red.solicitud())
    check(rf["resultados"]["segundaLey"]["estado"] == "no_cumple" and
          rf["resultados"]["certificacion"]["estado"] == "no_cumple" and aspecto(rf, "conservacion")["estado"] == "cumple"
          and aspecto(rf, "segunda_ley")["primeraMuestraNoCumple"] == 1,
          "calor de 1 kW desde 300 K a agua a 350 K: segunda ley no_cumple, conservacion si cumple")
    # sin temperatura de frontera
    red = (Red("sinT", ("agua",), tf=("100", "s"), muestras=4).paquete("w", "agua-iapws95")
           .volumen("A", "w", {"agua": ("1", "kg")}, ("T", "350", "K"), V=("0.00105", "m3"))
           .calor("q", None, "A", Q=("1000", "W")))
    rn = me.resolver(red.solicitud())
    check(rn["resultados"]["segundaLey"]["estado"] == "no_evaluable" and
          rn["resultados"]["certificacion"]["estado"] == "no_evaluable" and
          aspecto(rn, "conservacion")["estado"] == "cumple" and "MOTOR_ENS_CERTIFICACION_NO_CUMPLE" not in codigos(rn),
          "sin T de frontera: no_evaluable (no cumple ni invalida un balance de energia correcto)")
    check(not any(cat["variableId"] == "red.Sgen" for cat in rn["resultados"]["catalogoSeries"]),
          "sin T de frontera: no se publica S_gen con una T inventada")
    # escala: la misma red x1000 en materia y energia
    rg = me.resolver(contacto_agua(1000.0).solicitud())
    for eid in ("global.materia.1", "global.energia"):
        a1, a2 = residuo(r, eid)["maximoEscalado"], residuo(rg, eid)["maximoEscalado"]
        check(a2 <= residuo(rg, eid)["tolerancia"] and abs(math.log10(max(a1, 1e-12)) - math.log10(max(a2, 1e-12))) < 3,
              f"{eid}: escalado {a1:.2e} (x1) frente a {a2:.2e} (x1000)")
    rgc = corrida_corrupta(contacto_agua(1000.0).solicitud(), 1, d_mat=1e-5 * 1000 * nB / 2000)
    check(rgc["resultados"]["certificacion"]["estado"] == "no_cumple", "x1000: la misma corrupcion relativa se detecta")
    TA, TAg = serie(r, "volumen.A.T"), serie(rg, "volumen.A.T")
    check(max(abs(a - b) for a, b in zip(TA, TAg)) < 1e-6, "x1000 con G x1000: misma evolucion de T (intensiva)")

# ======================================================================
if activa("2"):
    seccion("C2. Catalogo de series, IDs de fase en eventos, denominacion supercritica")
    for f in sorted(EJ.glob("motor-ensamblaje-v2-resolver-*-respuesta.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if not r["resultados"]:
            continue
        cat = {x["variableId"]: x for x in r["resultados"].get("catalogoSeries", [])}
        vars_ = {x["id"]: x for x in r["validacion"]["variables"]}
        ok = all(s["variableId"] in cat and cat[s["variableId"]]["unidadSI"] == s["unidadSI"]
                 for s in r["resultados"]["series"]) and len(cat) == len(r["resultados"]["series"])
        check(ok, f"{f.name}: cada serie tiene una entrada de catalogo con su unidad")
        check(all((x["variableEnsamblajeId"] is None) == (x["variableId"] not in vars_) for x in cat.values()),
              f"{f.name}: variableEnsamblajeId apunta a validacion.variables o es null")
        check(all(x["papel"] == "derivada" for k, x in cat.items() if k.endswith((".masa", ".S")) or k == "red.Sgen"),
              f"{f.name}: masa, S y S_gen son derivadas de presentacion")
        check(r["validacion"]["recuento"]["gradosLibertad"] == 0, f"{f.name}: el catalogo no altera los grados de libertad")
    # IDs: extraer el liquido denso hasta agotarlo; el que queda conserva su ID aunque pase a ser el unico
    red = (Red("dec", ("agua", "butanol"), tf=("700", "s"), muestras=8).paquete("p", "nrtl-lle-agua-butanol")
           .volumen("D", "p", {"agua": ("0.75", "mol"), "butanol": ("0.25", "mol")}, ("T", "300", "K"),
                    P=("101325", "Pa"), base="molar", adiabatico=True)
           .corriente("o", "D", None, ("agua", "butanol"), ("0.001", "mol/s"), base="molar",
                      extraccion={"D": {"tipo": "fase", "fase": "liquido", "criterio": "mayor_densidad"}}))
    t0 = time.perf_counter()
    r = me.resolver(red.solicitud())
    check(r["resultados"] is not None, f"decantador (extraccion de la fase densa): {r['estado']} ({time.perf_counter() - t0:.0f} s)")
    if r["resultados"]:
        evs = [e for e in r["resultados"]["eventos"] if e["codigo"] == "desaparicion_fase"]
        check(len(evs) == 1 and evs[0]["faseIdsAntes"] == ["liquido-1", "liquido-2"] or
              (len(evs) == 1 and set(evs[0]["faseIdsAntes"]) == {"liquido-1", "liquido-2"}),
              f"desaparece una de dos fases liquidas: {evs}")
        if evs:
            e = evs[0]
            est = r["resultados"]["estados"]["D"]
            k = r["resultados"]["tiempos"].index(e["tiempo"])
            despues = est[k]["evaluacion"]["fases"][0]
            antes = {f_["id"]: f_["composicionMolar"]["1"] for f_ in est[k - 1]["evaluacion"]["fases"]}
            check(e["faseIds"] == ["liquido-1"] and e["faseIdsDespues"] == ["liquido-2"] and despues["id"] == "liquido-2",
                  "se agota liquido-1 (acuosa, densa); la organica conserva liquido-2 aunque ahora sea la unica")
            check(abs(despues["composicionMolar"]["1"] - antes["liquido-2"]) < 0.02,
                  "el ID superviviente sigue la composicion de la fase organica")
            check(all("liquido-1" not in [f_["id"] for f_ in m["evaluacion"]["fases"]] for m in est[k:]),
                  "una fase ausente no se publica (ni con composicion cero)")
            nW, nB = serie(r, "volumen.D.n.1"), serie(r, "volumen.D.n.2")
            xs = (nW[0] - nW[k - 1]) / ((nW[0] - nW[k - 1]) + (nB[0] - nB[k - 1]))
            check(abs(xs - antes["liquido-1"]) < 0.02, f"antes del agotamiento se extrae la fase densa (x_agua {xs:.3f})")
        check(r["resultados"]["certificacion"]["estado"] in ("cumple", "no_evaluable"), "decantador: sin incumplimientos")
    # aparicion de una segunda fase liquida: el nuevo liquido recibe un ID nuevo
    red = (Red("apar", ("agua", "butanol"), tf=("300", "s"), muestras=7).paquete("p", "nrtl-lle-agua-butanol")
           .volumen("D", "p", {"agua": ("0.3", "mol"), "butanol": ("0.9", "mol")}, ("T", "300", "K"),
                    P=("101325", "Pa"), base="molar", adiabatico=True)
           .corriente("e", None, "D", ("agua", "butanol"), ("0.003", "mol/s"), base="molar", T=("300", "K"),
                      P=("101325", "Pa"), composicion=("molar", {"agua": 1.0, "butanol": 0.0})))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        evs = [e for e in r["resultados"]["eventos"] if e["codigo"] == "aparicion_fase"]
        check(len(evs) >= 1 and len(evs[0]["faseIds"]) == 1 and evs[0]["faseIds"][0] not in evs[0]["faseIdsAntes"]
              and len(evs[0]["faseIdsDespues"]) == 2, f"aparece un segundo liquido con ID propio: {evs[:1]}")
    else:
        check(False, f"aparicion LL: {r['estado']} {[d['mensaje'][:120] for d in r['validacion']['diagnosticos']]}")
    # incidencia de Codex: binario editado (0.002 mol/s) publicaba una fraccion 1.0000000000000002
    red = (Red("binario-editado", ("etanol", "agua"), tf=("200", "s"), muestras=5).paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {"etanol": ("0.3", "mol"), "agua": ("0.7", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                    base="molar")
           .volumen("B", "p", {"etanol": ("0.1", "mol"), "agua": ("0.9", "mol")}, ("T", "300", "K"), P=("101325", "Pa"),
                    base="molar")
           .corriente("s", "A", "B", ("etanol", "agua"), ("0.002", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "mezcla_homogenea"}})
           .calor("c", "A", "B", G=("0.5", "W/K")))
    r = me.resolver(red.solicitud())
    fases = [f_ for v_ in r["resultados"]["estados"].values() for m in v_ for f_ in m["evaluacion"]["fases"]]
    check(all(0 < f_[k] <= 1.0 for f_ in fases for k in ("fraccionMolar", "fraccionMasica", "fraccionVolumen")),
          "fracciones de fase nunca por encima de 1")
    check(all(f_[k] == 1.0 for v_ in r["resultados"]["estados"].values() for m in v_ if len(m["evaluacion"]["fases"]) == 1
              for f_ in m["evaluacion"]["fases"] for k in ("fraccionMolar", "fraccionMasica", "fraccionVolumen")),
          "una sola fase: fracciones exactamente 1 (identidad)")
    pot = r["resultados"]["estados"]["A"][0]["potenciales"]
    check(pot["unidades"] == {"mu": "J/mol", "G": "J", "A": "J", "S": "J/K"}, "potenciales: G, A, S extensivos declarados")
    # clasificacion de eventos
    check(er.clasificar_evento((2, "liquido", "liquido"), (2, "liquido", "vapor")) == "sustitucion_fase",
          "LL -> LV con el mismo numero de fases: sustitucion, no cambio de denominacion")
    check(er.clasificar_evento((1, "liquido"), (1, "fluido")) == "cambio_denominacion"
          and er.clasificar_evento((1, "fluido"), (1, "vapor")) == "cambio_denominacion", "liquido/vapor <-> fluido: denominacion")
    red = (Red("super", ("agua",), tf=("200", "s"), muestras=5).paquete("w", "agua-iapws95")
           .volumen("A", "w", {"agua": ("1", "kg")}, ("T", "630", "K"), P=("300", "bar"))
           .calor("q", None, "A", Q=("2", "kW"), Tfrontera=("1000", "K")))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        ev = r["resultados"]["eventos"]
        check(len(ev) == 1 and ev[0]["codigo"] == "cambio_denominacion" and "NO es" in ev[0]["descripcion"]
              and ev[0]["faseIdsAntes"] != ev[0]["faseIdsDespues"],
              f"agua a 30 MPa cruzando Tc: cambio de denominacion liquido -> fluido ({[e['codigo'] for e in ev]})")
        T = serie(r, "volumen.A.T")
        H = serie(r, "volumen.A.H")
        ts = r["resultados"]["tiempos"]
        check(all(abs(H[k] - H[0] - 2000 * ts[k]) < 1e-6 * abs(H[0]) + 1e-3 for k in range(len(ts))) and
              all(T[k + 1] > T[k] for k in range(len(T) - 1)), "supercritico: H = H0 + Q t y T monotona (sin meseta)")
    else:
        check(False, f"supercritico: {r['estado']} {[d['mensaje'][:160] for d in r['validacion']['diagnosticos']]}")

# ======================================================================
if activa("3"):
    seccion("C3. Contrastes fisicos independientes")
    # 1. referencias desplazadas por especie (proceso aparte con h_ig y s_ig0 desplazados)
    guion = r'''
import sys, json, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, r"%s"); sys.path.insert(0, r"%s")
from core import mezclas_datos as md
DH = {"64-17-5": 12345.0, "7732-18-5": -6789.0}; DS = {"64-17-5": 17.0, "7732-18-5": -3.0}
if sys.argv[1] == "1":
    hi, si = md.Especie.h_ig, md.Especie.s_ig0
    md.Especie.h_ig = lambda self, T: hi(self, T) + DH.get(self.cas, 0.0)
    md.Especie.s_ig0 = lambda self, T: si(self, T) + DS.get(self.cas, 0.0)
from solicitudes_v2 import Red
from backend import motor_ensamblaje as me
red = (Red("ref", ("etanol", "agua"), tf=("450", "s"), muestras=5).paquete("p", "nrtl-chemsep")
       .volumen("A", "p", {"etanol": ("0.4", "mol"), "agua": ("0.6", "mol")}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
       .calor("q", None, "A", Q=("100", "W"), Tfrontera=("600", "K")))
r = me.resolver(red.solicitud())
s = {x["variableId"]: x["valores"] for x in r["resultados"]["series"]}
print(json.dumps({"T": s["volumen.A.T"], "H": s["volumen.A.H"], "S": s["volumen.A.S"], "t": r["resultados"]["tiempos"],
                  "ev": [e["tiempo"] for e in r["resultados"]["eventos"]], "cert": r["resultados"]["certificacion"]["estado"]}))
''' % (RAIZ, RAIZ / "tests")
    res = []
    for k in ("0", "1"):
        p = subprocess.run([sys.executable, "-c", guion, k], capture_output=True, text=True, timeout=2400)
        res.append(json.loads(p.stdout.strip().splitlines()[-1]))
    a, b = res
    dH = 0.4 * 12345.0 + 0.6 * -6789.0
    dS = 0.4 * 17.0 + 0.6 * -3.0
    # las muestras de evento se excluyen: su instante sale de una biseccion con tolerancia 1e-9 tf
    reg = [k for k, t in enumerate(a["t"]) if all(abs(t - te) > 1e-6 for te in a["ev"])]
    check(len(a["t"]) == len(b["t"]) and max(abs(a["T"][k] - b["T"][k]) for k in reg) < 1e-9 and
          max(abs(x - y) for x, y in zip(a["ev"], b["ev"])) < 2e-9 * 450,
          "referencias desplazadas por especie: misma T(t); eventos dentro de la tolerancia de la biseccion")
    check(max(abs(b["H"][k] - a["H"][k] - dH) for k in reg) < 1e-6 and
          max(abs(b["S"][k] - a["S"][k] - dS) for k in reg) < 1e-9 and a["cert"] == b["cert"] == "cumple",
          "H y S se desplazan exactamente sum n_i dh_i y sum n_i ds_i; certificacion igual")
    # 2. calor de mezcla y entalpias parciales por otra via (ln gamma y su derivada en T)
    s = mz.Sistema("nrtl-chemsep", [CAS["etanol"], CAS["agua"]])
    P, T = 101325.0, 330.0
    peor_hE = peor_par = 0.0
    for x1 in (0.1, 0.35, 0.6, 0.9):
        x = np.array([x1, 1 - x1])
        d = 1e-4
        dlg = (s.liq.lngamma(T + d, x) - s.liq.lngamma(T - d, x)) / (2 * d)
        hE_gamma = -R * T ** 2 * float(x @ dlg)                     # Gibbs-Helmholtz con ln gamma
        hp = np.array([s.fase("p", "liquido", T, P, np.array([1.0]), [i]).h for i in (0, 1)])
        f = s.fase("m", "liquido", T, P, x, [0, 1])
        peor_hE = max(peor_hE, abs((f.h - x @ hp) - hE_gamma) / max(abs(hE_gamma), 1.0))
        # entalpia parcial molar: d(n h)/dn_i a T, P por diferencias, frente a h_i^puro - R T^2 d ln gamma_i/dT
        for i in (0, 1):
            dn = 1e-6
            n_p, n_m = x.copy(), x.copy()
            n_p[i] += dn
            n_m[i] -= dn
            Hp = n_p.sum() * s.fase("m", "liquido", T, P, n_p, [0, 1]).h
            Hm = n_m.sum() * s.fase("m", "liquido", T, P, n_m, [0, 1]).h
            parc = (Hp - Hm) / (2 * dn)
            peor_par = max(peor_par, abs(parc - (hp[i] - R * T ** 2 * dlg[i])) / abs(hp[i]))
    check(peor_hE < 1e-5, f"h^E del cierre frente a -R T^2 sum x d ln gamma/dT: {peor_hE:.1e} relativo")
    check(peor_par < 1e-6, f"entalpias parciales molares (termino composicional): {peor_par:.1e} relativo")
    # 3. estabilidad: estados homogeneos inestables/metastables y semillas distintas
    x = np.array([0.4, 0.6])
    for T in (360.0, 370.0):
        mu = s.mu("liquido", T, P, x, [0, 1])
        pr = s.prueba_estabilidad(T, P, mu, [0, 1], incluir_vapor=True)
        check(min(q[2] for q in pr if q[0] == "vapor") < -1e-6,
              f"liquido sobrecalentado homogeneo a {T} K: la prueba de vapor lo rechaza (tm < 0)")
    sb = mz.Sistema("nrtl-lle-agua-butanol", [CAS["agua"], CAS["butanol"]])
    ref = sb.equilibrio_TP(320.0, P, np.array([0.75, 0.25]))
    semillas = [sb.equilibrio_TP(T_, P, np.array([0.75, 0.25])) for T_ in (300.0, 340.0)] + \
               [sb.equilibrio_TP(320.0, P, np.array([0.6, 0.4])), sb.equilibrio_TP(372.0, P, np.array([0.75, 0.25]))]
    for k, sem in enumerate(semillas):
        try:
            e = sb.flash_rapido("TP", 320.0, P, np.array([0.75, 0.25]), sem)
        except mz.FueraDeAlcance as x_:
            e = None
        check(e is not None and abs(e.G - ref.G) < 1e-9 * abs(ref.G) and len(e.fases) == len(ref.fases),
              f"TP con semilla {k} ({[f.tipo for f in sem.fases]}): mismo minimo que el flash completo")
    check(ref.estabilidad.get("pruebas", 0) > 0 and set(ref.estabilidad.get("candidatas", [])) == {"liquido", "vapor"},
          f"alcance explorado publicado: {ref.estabilidad.get('pruebas')} pruebas, candidatas {ref.estabilidad.get('candidatas')}")
    # 4. mesetas: reconstruccion por componente, energia y volumen; burbuja/rocio a +-1e-9 K
    n = np.array([0.75, 0.25])
    P = 101325.0
    lo, hi = 360.0, 372.0
    for _ in range(45):
        m_ = 0.5 * (lo + hi)
        if any(f.tipo == "vapor" for f in sb.equilibrio_TP(m_, P, n).fases):
            hi = m_
        else:
            lo = m_
    eL, eV = sb.equilibrio_TP(lo, P, n), sb.equilibrio_TP(hi * (1 + 1e-6), P, n)
    for fr in (1e-6, 0.5, 1 - 1e-6):
        H = eL.H + fr * (eV.H - eL.H)
        e = sb.equilibrio_PH(P, H, n)
        rec = max(abs(sum(f.n * f.x[i] for f in e.fases) - n[i]) for i in (0, 1))
        check(rec < 1e-12 and abs(e.H - H) < 1e-9 * abs(H) + 1e-6 and abs(e.V - sum(f.n * f.v for f in e.fases)) < 1e-15,
              f"meseta LLV fraccion {fr}: componentes {rec:.1e}, energia y volumen reconstruidos ({len(e.fases)} fases)")
    sc = mz.Sistema("nrtl-chemsep", [CAS["etanol"], CAS["agua"]])
    n2 = np.array([0.4, 0.6])
    lo, hi = 340.0, 380.0
    for _ in range(60):
        m_ = 0.5 * (lo + hi)
        if any(f.tipo == "vapor" for f in sc.equilibrio_TP(m_, P, n2).fases):
            hi = m_
        else:
            lo = m_
    for T_ in (lo - 1e-9 * lo, hi + 1e-9 * hi):
        e = sc.equilibrio_TP(T_, P, n2)
        check(e.verificaciones["estabilidad"][0] <= mz.TOL_TM, f"burbuja +-1e-9 relativo ({len(e.fases)} fases) certificada")
    # 5. red invertida: el donante pasa a ser B
    red = (Red("inv", ("etanol", "agua"), tf=("200", "s"), muestras=5).paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {"etanol": ("0.3", "mol"), "agua": ("0.7", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                    base="molar")
           .volumen("B", "p", {"etanol": ("0.1", "mol"), "agua": ("0.9", "mol")}, ("T", "300", "K"), P=("101325", "Pa"),
                    base="molar")
           .corriente("s", "A", "B", ("etanol", "agua"), ("-0.001", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "mezcla_homogenea"}, "B": {"tipo": "mezcla_homogenea"}})
           .calor("c", "A", "B", G=("0.5", "W/K")))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        nA = [serie(r, f"volumen.A.n.{c}") for c in (1, 2)]
        nB = [serie(r, f"volumen.B.n.{c}") for c in (1, 2)]
        xB = [nB[0][k] / (nB[0][k] + nB[1][k]) for k in range(len(nB[0]))]
        check(max(abs(v - 0.1) for v in xB) < 1e-9, "caudal negativo: el donante es B y conserva su composicion")
        check(max(abs(nA[i][k] + nB[i][k] - nA[i][0] - nB[i][0]) for i in (0, 1) for k in range(len(nA[0]))) < 1e-10,
              "una sola transferencia por especie con signos opuestos")
        nd = serie(r, "corriente.s.ndot")
        check(all(abs(v + 0.001) < 1e-12 for v in nd), "ndot publicado en el sentido declarado (negativo)")
        check(r["resultados"]["certificacion"]["estado"] == "cumple", "red invertida certificada")
    else:
        check(False, f"red invertida: {r['estado']} {[d['mensaje'][:160] for d in r['validacion']['diagnosticos']]}")
    # 6. convergencia: tolerancias y muestras distintas
    def calentar(rtol, muestras):
        red = (Red("conv", ("etanol", "agua"), tf=("450", "s"), muestras=muestras, rtol=rtol).paquete("p", "nrtl-chemsep")
               .volumen("A", "p", {"etanol": ("0.4", "mol"), "agua": ("0.6", "mol")}, ("T", "330", "K"),
                        P=("101325", "Pa"), base="molar")
               .calor("q", None, "A", Q=("100", "W"), Tfrontera=("600", "K")))
        return me.resolver(red.solicitud())
    ra, rb = calentar(1e-6, 3), calentar(1e-10, 10)
    ta = [e["tiempo"] for e in ra["resultados"]["eventos"]]
    tb = [e["tiempo"] for e in rb["resultados"]["eventos"]]
    check(len(ta) == len(tb) == 2 and max(abs(x - y) for x, y in zip(ta, tb)) < 1e-5 * 450,
          f"eventos con rtol 1e-6/3 muestras frente a 1e-10/10 muestras: {ta} / {tb}")
    check(abs(serie(ra, "volumen.A.T")[-1] - serie(rb, "volumen.A.T")[-1]) < 1e-4, "T final independiente de la tolerancia")
    # 7. limites
    def valida(red):
        return me.validar(red.solicitud())[0]
    rv = valida(Red("par", ("agua", "benceno"), tf=("10", "s"), muestras=3).paquete("p", "nrtl-chemsep")
                .volumen("A", "p", {"agua": ("0.5", "mol"), "benceno": ("0.5", "mol")}, ("T", "300", "K"),
                         P=("101325", "Pa"), base="molar", adiabatico=True))
    check(rv["inicializacion"]["estado"] != "compatible" and any("PARAMETRO" in c_ or "PAQUETE" in c_ for c_ in codigos(rv)),
          f"par binario sin parametros: rechazado ({sorted(codigos(rv))})")
    rv = valida(Red("Palta", ("etanol", "agua"), tf=("10", "s"), muestras=3).paquete("p", "nrtl-chemsep")
                .volumen("A", "p", {"etanol": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("T", "300", "K"),
                         P=("10", "bar"), base="molar", adiabatico=True))
    check(rv["inicializacion"]["estado"] != "compatible", f"P = 10 bar fuera del dominio de mezclas: {rv['inicializacion']['estado']}")
    rv = valida(Red("lleno", ("etanol", "agua"), tf=("10", "s"), muestras=3).paquete("p", "nrtl-chemsep")
                .volumen("A", "p", {"etanol": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("U", "-1e5", "J"),
                         V=("3.0e-5", "m3"), base="molar", adiabatico=True))
    check(rv["inicializacion"]["estado"] != "compatible", "liquido incompresible que llena un volumen rigido: no compatible")
    rv = valida(Red("frio", ("etanol", "agua"), tf=("10", "s"), muestras=3).paquete("p", "nrtl-chemsep")
                .volumen("A", "p", {"etanol": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("T", "150", "K"),
                         P=("101325", "Pa"), base="molar", adiabatico=True))
    check(rv["inicializacion"]["estado"] != "compatible", "estado inicial fuera de dominio (150 K): incompatible")
    red = (Red("vapor-aus", ("etanol", "agua"), tf=("10", "s"), muestras=3).paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {"etanol": ("0.4", "mol"), "agua": ("0.6", "mol")}, ("T", "300", "K"),
                    P=("101325", "Pa"), base="molar", adiabatico=True)
           .corriente("o", "A", None, ("etanol", "agua"), ("0.001", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "fase", "fase": "vapor"}}))
    r = me.resolver(red.solicitud())
    check(r["estado"] == "invalido" and "MOTOR_ENS_DETENIDO_FASE_AUSENTE" in codigos(r),
          f"extraer vapor de un volumen sin vapor: detenido ({r['estado']}, {sorted(codigos(r))})")

# ======================================================================
print(f"\n{'OK' if not FALLOS else 'FALLOS: ' + str(len(FALLOS))}: {CHECKS[0]} comprobaciones")
sys.exit(1 if FALLOS else 0)
