"""
Bloque A de ARQUITECTURA_MOTOR.md §10 (orden vigente): la capa termodinámica y
el compilador común con los tres paquetes UNIFAC (decisión §9.1: UNIFAC con
prioridad completa; NRTL no se trata).

    unifac-original-public · unifac-dortmund-public · unifac-original-lle-public

Para las siete solicitudes dinámicas UNIFAC que publica el motor
(docs/ejemplos/motor-unifac/), llevadas al modelo común y resueltas por el
compilador común (core/compilador), con el mismo código y sin ramas por caso:

  1. Comunes: formato común válido, conservación global de materia y energía,
     complementariedad beta·tm y TODAS las candidatas (vapor-1, liquido-1,
     liquido-2) publicadas en cada muestra, con beta 0 antes de aparecer.
  2. Frente al motor existente: mismo estado y mismos eventos de fase.
  3. Frente a referencias INDEPENDIENTES del paquete (gamma de `thermo`, otra
     implementación de UNIFAC con las mismas tablas):
       - el vapor aparece a la T de burbuja de un cálculo gamma-phi
         independiente a la composición de la carga (original y Dortmund);
       - la segunda fase líquida aparece cuando la carga alcanza la binodal
         por isoactividad con thermo (agua-butanol, tabla ELL), con la fase
         conjugada; en la red de cinco especies, cuando la distancia al plano
         tangente líquido-líquido calculada con thermo cruza cero.
  4. La política de fases declarada es un supuesto: «monofásico» detiene el
     cálculo cuando aparece otra fase, en el instante del motor.
  5. Red de cinco especies con agua entrante: el compilador común detecta la
     segunda fase líquida en el límite de estabilidad independiente
     (113,586 s). Hasta el 18 de octubre de 2026 el motor existente la
     publicaba a 141,41 s: tras localizar el cambio, si no lo reencontraba en
     el estado reintegrado aceptaba el paso entero sin evento. Corregido en
     core/ensamblaje_red.py; ahora coincide (1e-6 de tf) y el ejemplo publicado
     se regeneró.

Ejecutar desde la raíz:  python tests/validar_capa_unifac.py   (~5 min; la red de 5 especies tarda ~4)
"""

import copy
import json
import math
import re
import sys
import time
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
warnings.filterwarnings("ignore")

import numpy as np
from scipy.optimize import brentq, minimize

from core import mezclas_datos as md
from core import unifac
from core.compilador import resolver
from core.modelo import desde_ensamblaje_v2
from core.resultados import leer_resultados
from core.termodinamica import candidatas

EJ = RAIZ / "docs" / "ejemplos" / "motor-unifac"
fallos, n = [], [0]
CANDIDATAS = ["vapor-1", "liquido-1", "liquido-2"]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:400]) if detalle != '' else ''}")


# --- Referencia independiente: UNIFAC de thermo -------------------------------------------
def _thermo(variante):
    import thermo.unifac as tu
    tu.load_unifac_ip()
    return tu, {"original": (tu.UFSG, tu.UFIP, 0), "dortmund": (tu.DOUFSG, tu.DOUFIP2016, 1), "lle": (tu.LLEUFSG, tu.LLEUFIP, 0)}[variante]


def lngamma(cas, variante, T, x):
    tu, (sg, ip, ver) = _thermo(variante)
    m = tu.UNIFAC.from_subgroups(T=T, xs=list(x), chemgroups=[unifac.asignacion(c, variante) for c in cas],
                                 subgroups=sg, interaction_data=ip, version=ver)
    return np.log(np.array(m.gammas()))


def burbuja(cas, variante, z, P):
    """T con sum_i z_i gamma_i(T, z) Psat_i(T) Poynting_i / P = 1 (vapor ideal, como el paquete)."""
    esp = [md.especie(c) for c in cas]
    def f(T):
        K = np.exp(lngamma(cas, variante, T, z)) * np.array([e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (md.R * T)) / P for e in esp])
        return float(np.sum(z * K)) - 1.0
    return brentq(f, 250, 500, xtol=1e-10)


def tpd_ll(cas, variante, T, z):
    """Mínimo de la distancia al plano tangente para una fase líquida de prueba (adimensional, por RT)."""
    d = np.log(z) + lngamma(cas, variante, T, z)
    N = len(z)
    semillas = [np.eye(N)[i] * 0.98 + 0.02 / N for i in range(N)]
    mejor = np.inf
    for w0 in semillas:
        f = lambda a: (lambda w: float(np.sum(w * (np.log(w) + lngamma(cas, variante, T, w) - d))))(np.exp(a) / np.exp(a).sum())
        r = minimize(f, np.log(w0), method="Nelder-Mead", options={"xatol": 1e-10, "fatol": 1e-14, "maxiter": 6000})
        mejor = min(mejor, r.fun)
    return mejor


# --- Comparaciones ----------------------------------------------------------------------
def series(c):
    return {s["id"]: s for s in c["series"]}


def comunes(nombre, modelo, c):
    leer_resultados(c)
    check(f"{nombre}: resultado válido en el formato común", True)
    ver = {v["id"]: v["valor"] for v in c["verificaciones"]}
    check(f"{nombre}: conservación global de materia (1e-12)", ver["conservacion.materia"] < 1e-12, ver["conservacion.materia"])
    check(f"{nombre}: conservación global de energía (1e-12)", ver["conservacion.energia"] < 1e-12, ver["conservacion.energia"])
    check(f"{nombre}: complementariedad beta·tm en todas las muestras (1e-8)", ver["complementariedad"] < 1e-8, ver["complementariedad"])
    S, nt = series(c), len(c["ejes"][0]["valores"])
    for v in modelo["volumenes"]:
        cand = candidatas(modelo, v["id"])
        check(f"{nombre}: {v['id']} tiene las tres candidatas de un modelo de actividad", cand == CANDIDATAS, cand)
        for k in cand:
            b = S.get(f"volumen.{v['id']}.fase.{k}.beta")
            check(f"{nombre}: la candidata {v['id']}/{k} se publica en todas las muestras",
                  b is not None and len(b["valores"]) == nt and all(x is not None and x >= 0 for x in b["valores"]))
    for e in c["eventos"]:
        if e["codigo"] == "aparicion_fase":
            vid, k = e["propietarioId"].split(":")[1], e["descripcion"].split()[-1]
            b, t = S[f"volumen.{vid}.fase.{k}.beta"]["valores"], c["ejes"][0]["valores"]
            check(f"{nombre}: antes de aparecer, {vid}/{k} está con beta = 0 (las ecuaciones no cambian)",
                  all(b[i] == 0 for i, x in enumerate(t) if x < e["valor"] - 1e-9))


def comparar(nombre, c, pub, rel=1e-8, hasta=None):
    S, P = series(c), {s["variableId"]: s for s in pub["series"]}
    tt, tp = np.array(c["ejes"][0]["valores"]), np.array(pub["tiempos"])
    sel = tp <= (hasta if hasta is not None else np.inf)
    peor, cual = 0.0, None
    for k, s in P.items():
        if k in S and re.search(r"\.(n\.\d+|T|H|U)$", k):
            a = np.interp(tp[sel], tt, np.array(S[k]["valores"], dtype=float))
            b = np.array(s["valores"], dtype=float)[sel]
            d = float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))
            if d > peor:
                peor, cual = d, k
    check(f"{nombre}: estado igual al del motor existente{'' if hasta is None else f' hasta t = {hasta:g} s'} ({rel:g})", peor < rel, (cual, peor))
    return peor


def eventos_fase(c):
    return [(e["codigo"], e["valor"]) for e in c["eventos"] if e["codigo"] in ("aparicion_fase", "desaparicion_fase")]


def eventos_pub(pub):
    return [(e["codigo"], e["tiempo"]) for e in pub["eventos"] if e["codigo"] in ("aparicion_fase", "desaparicion_fase")]


def caso(nom):
    pet = json.loads((EJ / f"motor-ensamblaje-v2-resolver-{nom}-peticion.json").read_text(encoding="utf-8"))
    resp = json.loads((EJ / f"motor-ensamblaje-v2-resolver-{nom}-respuesta.json").read_text(encoding="utf-8"))
    pub = dict(resp["resultados"], estado=resp["estado"])
    m = desde_ensamblaje_v2(pet)
    t0 = time.time()
    c = resolver(copy.deepcopy(m))
    print(f"  {nom}: {time.time() - t0:.1f} s, {len(c['ejes'][0]['valores'])} muestras, eventos {[(e['codigo'], round(e['valor'], 6)) for e in c['eventos']]}")
    return pet, pub, m, c


def cas_de(m, vid):
    comps = {x["id"]: x for x in m["componentes"]}
    v = next(x for x in m["volumenes"] if x["id"] == vid)
    return [comps[i]["identidadQuimica"]["cas"] for i in v["componenteIds"]], v


def estado_en(c, vid, comp_ids, t):
    S, tt = series(c), c["ejes"][0]["valores"]
    nn = np.array([np.interp(t, tt, S[f"volumen.{vid}.n.{i}"]["valores"]) for i in comp_ids])
    return float(np.interp(t, tt, S[f"volumen.{vid}.T"]["valores"])), nn / nn.sum()


VARIANTE = {"unifac-original-public": "original", "unifac-dortmund-public": "dortmund", "unifac-original-lle-public": "lle"}


def variante_de(m, v):
    paq = next(p for p in m["termodinamica"]["paquetes"] if p["id"] == v["termodinamica"]["paqueteId"])
    return VARIANTE[paq["modelo"]["id"]]


# --- 1-3. Calentamiento hasta hervir: original (2 y 4 especies) y Dortmund (4) ------------
for nom in ("unifac-calentamiento-2", "unifac-calentamiento-4", "unifac-dortmund-calentamiento-4"):
    pet, pub, m, c = caso(nom)
    comunes(nom, m, c)
    comparar(nom, c, pub)
    ec, ep = eventos_fase(c), eventos_pub(pub)
    check(f"{nom}: mismos eventos de fase que el motor y en el mismo instante (1e-6 s)",
          [a for a, _ in ec] == [a for a, _ in ep] and all(abs(x - y) < 1e-6 for (_, x), (_, y) in zip(ec, ep)), (ec, ep))
    cas, v = cas_de(m, "A")
    var = variante_de(m, v)
    ap = next(t for k, t in ec if k == "aparicion_fase")
    T_ap, z = estado_en(c, "A", v["componenteIds"], ap)
    P = float(m["datos"][v["frontera"]["presionId"]]["declaracion"]["texto"])
    Tb = burbuja(cas, var, z, P)
    check(f"{nom}: el vapor aparece a la T de burbuja gamma-phi independiente (thermo, {var}) (1e-4 K)", abs(T_ap - Tb) < 1e-4, (T_ap, Tb))

# --- 4. Segunda fase líquida con la tabla ELL ----------------------------------------------
nom = "unifac-lle-mezcla-agua-butanol"
pet, pub, m, c = caso(nom)
comunes(nom, m, c)
comparar(nom, c, pub)
ec, ep = eventos_fase(c), eventos_pub(pub)
check(f"{nom}: mismos eventos de fase que el motor y en el mismo instante (1e-6 s)",
      [a for a, _ in ec] == [a for a, _ in ep] and all(abs(x - y) < 1e-6 for (_, x), (_, y) in zip(ec, ep)), (ec, ep))
e_ap = next(e for e in c["eventos"] if e["codigo"] == "aparicion_fase")
vid = e_ap["propietarioId"].split(":")[1]
cas, v = cas_de(m, vid)
# Binodal binaria por isoactividad con thermo (la entrada es tan lenta que el plano tangente,
# justo después del evento, queda por debajo del ruido de la minimización: se usa la binodal).
T_e, z_e = estado_en(c, vid, v["componenteIds"], e_ap["valor"])
sg = lambda u: 1 / (1 + math.exp(-u))  # noqa: E731
def iso(u):
    a, b = sg(u[0]), sg(u[1])
    la, lb = lngamma(cas, "lle", T_e, [1 - a, a]), lngamma(cas, "lle", T_e, [1 - b, b])
    return [math.log(1 - a) + la[0] - math.log(1 - b) - lb[0], math.log(a) + la[1] - math.log(b) - lb[1]]
from scipy.optimize import fsolve  # noqa: E402
u = fsolve(iso, [math.log(0.02 / 0.98), math.log(0.4 / 0.6)], xtol=1e-14)
x_rica_agua, x_rica_butanol = sg(u[0]), sg(u[1])
S_ = series(c)
k_ap = e_ap["descripcion"].split()[-1]
x_inc = S_[f"volumen.{vid}.fase.{k_ap}.x.{v['componenteIds'][1]}"]["valores"][c["ejes"][0]["valores"].index(e_ap["valor"])]
check(f"{nom}: aparece cuando la carga alcanza la binodal independiente (thermo, lle; isoactividad) (1e-8)",
      abs(z_e[1] - x_rica_agua) < 1e-8, (z_e[1], x_rica_agua))
check(f"{nom}: la fase que aparece tiene la composición conjugada de esa binodal (1e-5)",
      abs(x_inc - x_rica_butanol) < 1e-5, (x_inc, x_rica_butanol))

# --- 5. Política monofásica ----------------------------------------------------------------
nom = "unifac-monofasico-detenido"
pet, pub, m, c = caso(nom)
comunes(nom, m, c)
comparar(nom, c, pub)
check(f"{nom}: estado parcial, como el motor", c["estado"] == "parcial" and pub["estado"] == "parcial")
pol = [e for e in c["eventos"] if e["codigo"] == "politica_incumplida"]
check(f"{nom}: se detiene con 'politica_incumplida' en el instante del motor (1e-6 s)",
      len(pol) == 1 and abs(pol[0]["valor"] - pub["tiempos"][-1]) < 1e-6 and abs(c["ejes"][0]["valores"][-1] - pub["tiempos"][-1]) < 1e-6,
      ([(e["codigo"], e["valor"]) for e in c["eventos"]], pub["tiempos"][-1]))

# --- 6. Red de cinco especies con agua entrante ---------------------------------------------
nom = "unifac-red-5-especie-entrante"
pet, pub, m, c = caso(nom)
comunes(nom, m, c)
ec, ep = eventos_fase(c), eventos_pub(pub)
check(f"{nom}: una sola aparición de fase en cada cálculo", len(ec) == 1 and len(ep) == 1, (ec, ep))
t_ap = ec[0][1]
comparar(nom, c, pub, rel=1e-6)
e_ap = next(e for e in c["eventos"] if e["codigo"] == "aparicion_fase")
vid = e_ap["propietarioId"].split(":")[1]
cas, v = cas_de(m, vid)
d = 1e-5 * t_ap
antes, despues = (tpd_ll(cas, "original", *estado_en(c, vid, v["componenteIds"], t_ap + s)) for s in (-d, d))
check(f"{nom}: la segunda fase líquida aparece donde el plano tangente LL independiente (thermo) cruza cero",
      antes > -1e-9 and despues < -1e-12, (antes, despues))
check(f"{nom}: el motor (corregido el 18-10-2026) publica la fase en el mismo instante (1e-6 de tf)",
      abs(ep[0][1] - t_ap) < 1e-6 * float(m["datos"][m["estudio"]["tiempoId"]]["declaracion"]["texto"]), (t_ap, ep[0][1]))

print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nCapa y compilador con UNIFAC: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
