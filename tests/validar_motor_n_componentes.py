"""
Termodinamica de N componentes y ensamblaje dinamico (docs/history/frontend/assignment-claude-thermodynamics-n-components.md).

Referencias independientes del motor (que minimiza G con su prueba de plano tangente):
  * mezcla ideal: Raoult con Poynting y Rachford-Rice escritos aqui;
  * NRTL L-V: flash gamma-phi por sustitucion sucesiva + Rachford-Rice con thermo.nrtl.NRTL (otra
    implementacion de NRTL) y los MISMOS parametros ChemSep; mismas Psat y Poynting del paquete;
  * NRTL L-L: isoactividad por sustitucion sucesiva (K_i = gamma_i^II / gamma_i^I) + Rachford-Rice con thermo;
  * identidades: Gibbs-Duhem, G = sum n mu, g = h - T s, entalpias parciales molares por diferencias.
Los parametros ChemSep proceden de ajustes a datos binarios de VLE: los conjuntos de 4 especies son
predicciones del modelo, sin contraste experimental propio (evidencia 'cualitativa').

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_n_componentes.py [seccion ...]
"""

import copy
import itertools
import math
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
from scipy.optimize import brentq

from backend import motor_ensamblaje as me
from backend import motor_ensamblaje_v2 as v2
from backend import motor_termodinamica as mt
from core import mezclas as mz
from core import mezclas_datos as md
from solicitudes_v2 import CAS, POL, Red

FALLOS, CHECKS = [], [0]
R = mz.R
SECCIONES = sys.argv[1:]
NOM = {v: k for k, v in CAS.items()}
TODAS = [CAS[k] for k in ("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol")]
NRTL4_A = [CAS[k] for k in ("etanol", "benceno", "tolueno", "metanol")]
NRTL4_B = [CAS[k] for k in ("agua", "etanol", "acetato", "metanol")]


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def seccion(t):
    print(f"\n{t}")


def activa(n):
    return not SECCIONES or n in SECCIONES


def serie(r, vid):
    return next(s["valores"] for s in r["resultados"]["series"] if s["variableId"] == vid)


def rachford_rice(z, K):
    f = lambda b: float(np.sum(z * (K - 1) / (1 + b * (K - 1))))
    if f(0.0) <= 0:
        return 0.0
    if f(1.0) >= 0:
        return 1.0
    return brentq(f, 0.0, 1.0, xtol=1e-15, rtol=1e-15)


def K_ideal(s, T, P):
    return np.array([e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (R * T)) / P for e in s.esp])


def nrtl_thermo(s, T, x):
    from thermo.nrtl import NRTL
    n = len(x)
    z = [[0.0] * n for _ in range(n)]
    return np.array(NRTL(T=T, xs=list(x), ABEFGHCD=(s.liq.a.tolist(), s.liq.b.tolist(), z, z, z, z,
                                                     s.liq.alpha.tolist(), z)).gammas())


def flash_gamma_phi(s, T, P, z, iteraciones=500):
    """Flash L-V independiente: K = gamma(x) Psat exp(Poynting)/P, sustitucion sucesiva + Rachford-Rice."""
    Kp = K_ideal(s, T, P)
    K = Kp.copy()
    x = z.copy()
    for _ in range(iteraciones):
        b = rachford_rice(z, K)
        x = z / (1 + b * (K - 1))
        x = x / x.sum()
        Kn = nrtl_thermo(s, T, x) * Kp
        if np.max(np.abs(Kn / K - 1)) < 1e-14:
            K = Kn
            break
        K = Kn
    b = rachford_rice(z, K)
    x = z / (1 + b * (K - 1))
    return b, x / x.sum(), (K * x) / (K * x).sum()


def flash_ll(s, T, z, x1, x2, iteraciones=2000):
    """L-L independiente: K = gamma^I / gamma^II (x^II = K x^I), sustitucion sucesiva + Rachford-Rice."""
    for _ in range(iteraciones):
        K = nrtl_thermo(s, T, x1) / nrtl_thermo(s, T, x2)
        b = rachford_rice(z, K)
        n1 = z / (1 + b * (K - 1))
        x1n, x2n = n1 / n1.sum(), K * n1 / (K * n1).sum()
        if max(np.max(np.abs(x1n - x1)), np.max(np.abs(x2n - x2))) < 1e-14:
            return b, x1n, x2n
        x1, x2 = x1n, x2n
    return b, x1, x2


def fases(e, tipo):
    return [f for f in e.fases if f.tipo == tipo]


# ======================================================================
if activa("0"):
    seccion("N0. Auditoria: pares, dominios y capacidades")
    from thermo.interaction_parameters import IPDB
    # Auditoria N0 sobre las 7 especies de esa entrega; la acetona (F2.6) se informa aparte
    es = TODAS
    completos = {k: [] for k in (4, 5, 6, 7)}
    for k in completos:
        for S in itertools.combinations(es, k):
            if all(IPDB.has_ip_specific("ChemSep NRTL", list(p), "bij") and
                   IPDB.has_ip_specific("ChemSep NRTL", list(p), "alphaij") for p in itertools.combinations(S, 2)):
                completos[k].append(S)
    con_ace = [S for k in (4, 5) for S in itertools.combinations(md.especies_disponibles(), k) if "67-64-1" in S and all(
        IPDB.has_ip_specific("ChemSep NRTL", list(p), "bij") and IPDB.has_ip_specific("ChemSep NRTL", list(p), "alphaij")
        for p in itertools.combinations(S, 2))]
    print(f"    con la acetona (F2.6): {sum(len(S) == 4 for S in con_ace)} conjuntos NRTL completos de 4 especies y "
          f"{sum(len(S) == 5 for S in con_ace)} de 5 (sin contraste dinamico propio)")
    check(sorted(map(sorted, completos[4])) == sorted(map(sorted, [NRTL4_A, NRTL4_B])) and not completos[5],
          f"NRTL ChemSep: dos conjuntos completos de 4 especies (bij y alphaij), ninguno de 5 ({[len(v) for v in completos.values()]})")
    for S in (NRTL4_A, NRTL4_B):
        s = mz.Sistema("nrtl-chemsep", S)
        check(np.allclose(s.liq.alpha, s.liq.alpha.T) and np.all(np.diag(s.liq.b) == 0) and
              all(s.liq.b[i, j] != 0 or s.liq.b[j, i] != 0 for i, j in itertools.combinations(range(4), 2)),
              f"{[NOM[c] for c in S]}: b_ij en ambas direcciones y alpha simetrica")
    s7 = mz.Sistema("mezcla-ideal", TODAS)
    lo = max(md.especie(c).T_rango[0] for c in TODAS)
    hi = min(md.especie(c).T_rango[1] for c in TODAS)
    check(s7.T_rango == (lo, hi) and lo < hi, f"dominio comun de las 7 especies = interseccion [{lo:.2f}, {hi:.2f}] K")
    cap = v2.capacidades_v2()
    t = cap["tamanos"]
    check(cap["componentesMaximos"] == t["componentesMaximosPorVolumen"] == 7 and t["fasesMaximas"] == mz.MAX_FASES,
          "capacidades v2: componentesMaximos coherente con tamanos y con el tope de fases del nucleo")
    check(t["contrastados"]["nrtl-chemsep"]["estatico"][-1] == 4 and t["contrastados"]["mezcla-ideal"]["estatico"][-1] == 7,
          "tamanos contrastados publicados por paquete (NRTL hasta 4, ideal hasta 7)")
    try:
        mz.Sistema("nrtl-chemsep", [CAS["agua"], CAS["benceno"], CAS["etanol"], CAS["metanol"]])
        check(False, "conjunto con un par ausente debia rechazarse")
    except mz.FaltaParametro as x:
        check(set(x.args[1]) == {CAS["agua"], CAS["benceno"]} if len(x.args) > 1 else True,
              "par ausente: FaltaParametro identifica el par, sin rellenar con cero ni caer a ideal")

# ======================================================================
if activa("1"):
    seccion("N1. Estabilidad general: contraste con las rutas especializadas y reproducibilidad")
    sb = mz.Sistema("nrtl-lle-agua-butanol", [CAS["agua"], CAS["butanol"]])
    for x in ([0.75, 0.25], [0.4, 0.6], [0.99, 0.01]):
        mu = sb.mu("liquido", 320.0, 1e5, np.array(x), [0, 1])
        a = min(q[2] for q in sb.prueba_estabilidad(320.0, 1e5, mu, [0, 1], False))
        b = min(q[2] for q in sb._estabilidad_general(320.0, 1e5, mu, [0, 1]))
        check(abs(a - b) < 1e-9 and (a < -1e-9) == (b < -1e-9), f"binario {x}: malla {a:.3e} frente a general {b:.3e}")
    s3 = mz.Sistema("nrtl-chemsep", [CAS["agua"], CAS["etanol"], CAS["acetato"]])
    for x in ([0.7, 0.05, 0.25], [0.3, 0.3, 0.4], [0.85, 0.05, 0.10]):
        mu = s3.mu("liquido", 300.0, 1e5, np.array(x), [0, 1, 2])
        qa = min(s3.prueba_estabilidad(300.0, 1e5, mu, [0, 1, 2], False), key=lambda q: q[2])
        qb = min(s3._estabilidad_general(300.0, 1e5, mu, [0, 1, 2]), key=lambda q: q[2])
        check(abs(qa[2] - qb[2]) < 1e-9 and (qa[2] >= -1e-9 or np.max(np.abs(qa[1] - qb[1])) < 1e-5),
              f"ternario {x}: simplex {qa[2]:.3e} frente a general {qb[2]:.3e}")
    s4 = mz.Sistema("nrtl-chemsep", NRTL4_B)
    x = np.array([0.7, 0.04, 0.24, 0.02])
    mu = s4.mu("liquido", 300.0, 101325.0, x, [0, 1, 2, 3])
    p1 = s4._estabilidad_general(300.0, 101325.0, mu, [0, 1, 2, 3])
    p2 = s4._estabilidad_general(300.0, 101325.0, mu, [0, 1, 2, 3])
    check([q[2] for q in p1] == [q[2] for q in p2], "general: determinista con la semilla fija")
    check(min(q[2] for q in p1) < -1e-6, "cuaternario homogeneo en la zona L-L: rechazado por tm < 0")
    # caras del simplex: una especie de prueba ausente se alcanza (W_i = 0 en el dominio)
    xf = np.array([0.5, 0.0, 0.5, 0.0])
    mu_f = s4.mu("liquido", 300.0, 101325.0, xf[[0, 2]], [0, 2])
    pr = s4._estabilidad_general(300.0, 101325.0, mu_f, [0, 2])
    check(all(np.isfinite(q[2]) for q in pr), "estabilidad sobre una cara (especies ausentes retiradas): finita")

# ======================================================================
if activa("2"):
    seccion("N2. TP frente a referencias independientes; ausencias, trazas, permutaciones")
    P = 101325.0
    for S, T in ((TODAS[:4], 352.0), (TODAS[:5], 355.0), (TODAS, 360.0)):
        s = mz.Sistema("mezcla-ideal", S)
        rng = np.random.default_rng(7)
        for _ in range(3):
            z = rng.dirichlet(np.ones(len(S)))
            K = K_ideal(s, T, P)
            b = rachford_rice(z, K)
            t0 = time.perf_counter()
            e = s.equilibrio_TP(T, P, z)
            dt = time.perf_counter() - t0
            v = fases(e, "vapor")
            bv = v[0].n if v else 0.0
            ok = abs(bv - b) < 1e-9
            if 0 < b < 1 and v:
                l = fases(e, "liquido")[0]
                x = z / (1 + b * (K - 1))
                ok = ok and np.max(np.abs(l.x - x)) < 1e-9 and np.max(np.abs(v[0].x - K * x)) < 1e-9
            check(ok and e.verificaciones["estabilidad"][0] <= mz.TOL_TM,
                  f"ideal N={len(S)} T={T}: beta {bv:.9f} frente a Rachford-Rice {b:.9f} ({dt:.2f} s)")
    for S, T, z in ((NRTL4_A, 345.0, np.array([0.25, 0.25, 0.25, 0.25])), (NRTL4_A, 350.0, np.array([0.1, 0.4, 0.3, 0.2])),
                    (NRTL4_B, 345.0, np.array([0.25, 0.25, 0.25, 0.25]))):
        s = mz.Sistema("nrtl-chemsep", S)
        e = s.equilibrio_TP(T, P, z)
        b, x, y = flash_gamma_phi(s, T, P, z)
        v = fases(e, "vapor")
        l = fases(e, "liquido")
        check(len(v) == 1 and len(l) == 1 and abs(v[0].n - b) < 1e-8 and np.max(np.abs(l[0].x - x)) < 1e-8 and
              np.max(np.abs(v[0].x - y)) < 1e-8,
              f"NRTL N=4 {[NOM[c] for c in S]} T={T}: flash gamma-phi independiente (thermo) beta {b:.8f}")
    s = mz.Sistema("nrtl-chemsep", NRTL4_B)
    z = np.array([0.7, 0.04, 0.24, 0.02])
    e = s.equilibrio_TP(300.0, P, z)
    l = sorted(fases(e, "liquido"), key=lambda f: -f.x[0])
    check(len(l) == 2, f"NRTL N=4 agua-etanol-acetato-metanol a 300 K: dos liquidos ({[f.id for f in e.fases]})")
    if len(l) == 2:
        b, x1, x2 = flash_ll(s, 300.0, z, l[0].x.copy(), l[1].x.copy())
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8 and abs(b - l[1].n) < 1e-8,
              "L-L de 4 especies frente a isoactividad independiente (thermo): composiciones y reparto")
    # ausencias: catalogo de 7 con 3 especies exactamente cero = sistema de 4
    s7 = mz.Sistema("mezcla-ideal", TODAS)
    s4 = mz.Sistema("mezcla-ideal", TODAS[:4])
    z7 = np.array([0.3, 0.2, 0.3, 0.2, 0.0, 0.0, 0.0])
    a, b = s7.equilibrio_TP(352.0, P, z7), s4.equilibrio_TP(352.0, P, z7[:4])
    check(abs(a.G - b.G) < 1e-9 * abs(a.G) and len(a.fases) == len(b.fases) and
          all(np.all(f.x[4:] == 0) and np.all(np.isnan(f.mu[4:])) for f in a.fases),
          "especies exactamente ausentes: mismo estado que el sistema reducido; x = 0 y mu indefinida, IDs conservados")
    # trazas: residuo por especie y reconstruccion relativa a cada inventario
    for traza in (1e-6, 1e-9, 1e-12):
        z = np.array([0.3, 0.2, 0.3, 0.2 - traza, traza, 0, 0])
        e = s7.equilibrio_TP(352.0, P, z)
        rec = max(abs(sum(f.n * f.x[i] for f in e.fases) - z[i]) / z[i] for i in range(5))
        r_mu = e.verificaciones["equilibrio"][0]
        check(rec < 1e-9 and r_mu <= mz.TOL_MU, f"traza {traza:g}: reconstruccion por especie {rec:.1e}, mu {r_mu:.1e}")
    for escala in (1e-6, 1.0, 1e6):
        e = s7.equilibrio_TP(352.0, P, escala * z7)
        check(abs(e.G - escala * a.G) <= 1e-9 * abs(escala * a.G), f"extensividad x{escala:g}")
    # permutaciones
    rng = np.random.default_rng(3)
    for _ in range(3):
        perm = rng.permutation(4)
        sp = mz.Sistema("nrtl-chemsep", [NRTL4_A[k] for k in perm])
        z = np.array([0.25, 0.25, 0.25, 0.25])
        ea, eb = mz.Sistema("nrtl-chemsep", NRTL4_A).equilibrio_TP(345.0, P, z), sp.equilibrio_TP(345.0, P, z[perm])
        check(abs(ea.G - eb.G) < 1e-9 * abs(ea.G) and abs(ea.H - eb.H) < 1e-9 * abs(ea.H) and
              sp.huella() == mz.Sistema("nrtl-chemsep", NRTL4_A).huella(), f"permutacion {perm.tolist()}: mismo equilibrio y huella")
    # semillas distintas (flash con semilla) -> mismo minimo
    s = mz.Sistema("nrtl-chemsep", NRTL4_B)
    z = np.array([0.7, 0.04, 0.24, 0.02])
    ref = s.equilibrio_TP(300.0, P, z)
    for sem in (s.equilibrio_TP(300.0, P, np.array([0.6, 0.05, 0.3, 0.05])), s.equilibrio_TP(345.0, P, z),
                mz.Sistema("nrtl-chemsep", NRTL4_B).equilibrio_TP(300.0, P, np.array([0.75, 0.03, 0.2, 0.02]))):
        e = s.flash_rapido("TP", 300.0, P, z, sem)
        check(abs(e.G - ref.G) < 1e-9 * abs(ref.G) and len(e.fases) == len(ref.fases),
              f"semilla {[f.tipo for f in sem.fases]}: mismo minimo que el flash completo")

# ======================================================================
if activa("3"):
    seccion("N2. Inversiones, identidades y controles negativos")
    P = 101325.0
    for paq, S, T in (("mezcla-ideal", TODAS[:5], 355.0), ("mezcla-ideal", TODAS, 360.0), ("nrtl-chemsep", NRTL4_A, 345.0)):
        s = mz.Sistema(paq, S)
        z = np.ones(len(S)) / len(S)
        e = s.equilibrio_TP(T, P, z)
        for nombre, f in (("PH", lambda: s.equilibrio_PH(P, e.H, z)), ("UP", lambda: s.equilibrio_UP(P, e.U, z)),
                          ("UV", lambda: s.equilibrio_UV(e.U, e.V, z))):
            t0 = time.perf_counter()
            q = f()
            dt = time.perf_counter() - t0
            rec = max(abs(sum(fa.n * fa.x[i] for fa in q.fases) - z[i]) for i in range(len(S)))
            check(abs(q.T - T) < 1e-6 and abs(q.H - e.H) < 1e-8 * abs(e.H) + 1e-6 and abs(q.V - e.V) < 1e-9 * e.V
                  and rec < 1e-12 and len(q.fases) == len(e.fases),
                  f"{paq} N={len(S)} {nombre}: T, H, V y composicion de un unico reparto ({dt:.2f} s)")
    s = mz.Sistema("mezcla-ideal", TODAS[:5])
    z = np.ones(5) / 5
    e = s.equilibrio_TP(320.0, P, z)
    try:
        s.equilibrio_UV(e.U, e.V, z)
        check(False, "UV de liquido incompresible debia rechazarse")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "no_soportado", "UV de liquido incompresible lleno con 5 especies: no identificable")
    # identidades NRTL N=4
    s = mz.Sistema("nrtl-chemsep", NRTL4_B)
    x = np.array([0.3, 0.2, 0.3, 0.2])
    T = 330.0
    d = 1e-6
    rng = np.random.default_rng(11)
    peor = 0.0
    for _ in range(3):
        u = rng.normal(size=4)
        u -= u.mean()
        gp, gm = s.liq.lngamma(T, x + d * u), s.liq.lngamma(T, x - d * u)
        peor = max(peor, abs(float(x @ (gp - gm)) / (2 * d)))
    check(peor < 1e-7, f"Gibbs-Duhem N=4 en direcciones aleatorias: {peor:.1e}")
    f = s.fase("l", "liquido", T, P, x, [0, 1, 2, 3])
    check(abs(f.g - (f.h - T * f.s)) < 1e-9 * abs(f.h) and abs(f.g - float(np.sum(x * f.mu))) < 1e-9 * abs(f.g),
          "g = h - T s = sum x mu")
    hp = np.array([s.fase("p", "liquido", T, P, np.array([1.0]), [i]).h for i in range(4)])
    dlg = (s.liq.lngamma(T + 1e-4, x) - s.liq.lngamma(T - 1e-4, x)) / 2e-4
    peor = 0.0
    for i in range(4):
        npl, nmi = x.copy(), x.copy()
        npl[i] += 1e-6
        nmi[i] -= 1e-6
        Hp = npl.sum() * s.fase("m", "liquido", T, P, npl, [0, 1, 2, 3]).h
        Hm = nmi.sum() * s.fase("m", "liquido", T, P, nmi, [0, 1, 2, 3]).h
        peor = max(peor, abs((Hp - Hm) / 2e-6 - (hp[i] - R * T ** 2 * dlg[i])) / abs(hp[i]))
    check(peor < 1e-6, f"entalpias parciales molares N=4 frente a h_i - R T^2 d ln gamma_i/dT: {peor:.1e}")
    # negativos
    s = mz.Sistema("nrtl-chemsep", NRTL4_B)
    try:
        s.equilibrio_TP(290.0, P, np.ones(4) / 4)
        check(False, "290 K esta fuera del dominio comun (acetato desde 298 K)")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "fuera_de_dominio", "T fuera de la interseccion de dominios: rechazada aunque otras especies la admitan")
    viejo = mz.MAX_FASES
    mz.MAX_FASES = 1
    try:
        s.equilibrio_TP(300.0, P, np.array([0.7, 0.04, 0.24, 0.02]))
        check(False, "con tope de 1 fase el estado L-L debia rechazarse")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "no_soportado" and x.datos.get("tope_fases"), "tope de fases alcanzado: rechazo, nunca estable")
    finally:
        mz.MAX_FASES = viejo
    # servicio puntual
    base = {"revision": 1, "solicitudId": "n", "propietarioId": "p",
            "componentes": [{"id": k + 1, "nombre": NOM[c], "simbolo": NOM[c][:2], "identidadQuimica": {"cas": c}}
                            for k, c in enumerate(TODAS[:5])],
            "declaracion": {"modelo": {"id": "mezcla-ideal", "version": "1"}, "politica": dict(POL),
                            "especificacion": {"tipo": "TP", "T": {"valor": 355, "unidad": "K"},
                                               "P": {"valor": 101325, "unidad": "Pa"},
                                               "composicion": {"base": "molar",
                                                               "fracciones": {str(k + 1): 0.2 for k in range(5)}}}}}
    r = mt.evaluar(base)
    check(r["estado"] == "evaluado" and len(r["evaluacion"]["fases"]) == 2 and
          all(v["estado"] != "no_cumple" for v in r["evaluacion"]["verificaciones"]), "servicio puntual: 5 especies TP evaluado")
    sb = copy.deepcopy(base)
    sb["declaracion"]["modelo"]["id"] = "nrtl-chemsep"
    sb["componentes"] = [{"id": k + 1, "nombre": NOM[c], "simbolo": NOM[c][:2], "identidadQuimica": {"cas": c}}
                         for k, c in enumerate(NRTL4_B)]
    sb["declaracion"]["especificacion"] = {"tipo": "TP", "T": {"valor": 300, "unidad": "K"}, "P": {"valor": 101325, "unidad": "Pa"},
                                           "composicion": {"base": "molar", "fracciones": {"1": 0.7, "2": 0.04, "3": 0.24, "4": 0.02}}}
    mz.MAX_FASES = 1
    try:
        r = mt.evaluar(sb)
    finally:
        mz.MAX_FASES = viejo
    check(r["estado"] == "no_soportado" and any(d["codigo"] == "MOTOR_ESTADO_TOPE_FASES" for d in r["diagnosticos"]),
          "servicio puntual: tope de fases con codigo propio")
    r = mt.evaluar(sb)
    check(r["estado"] == "evaluado" and [f["id"] for f in r["evaluacion"]["fases"]] == ["liquido-1", "liquido-2"],
          "servicio puntual: L-L de 4 especies evaluado")

# ======================================================================
if activa("4"):
    seccion("N3. Ensamblaje dinamico con mas de tres componentes")
    nombres5 = ("benceno", "tolueno", "etanol", "metanol", "agua")
    nrtl4 = ("etanol", "benceno", "tolueno", "metanol")
    P = 101325.0

    def calentar(par, paq, tf, Q, T0="330", muestras=6, rtol=1e-8):
        n0 = {k: (str(round(1.0 / len(par), 12)), "mol") for k in par}
        return (Red("n-cal", par, tf=(tf, "s"), muestras=muestras, rtol=rtol).paquete("p", paq)
                .volumen("A", "p", n0, ("T", T0, "K"), P=("101325", "Pa"), base="molar")
                .calor("q", None, "A", Q=(Q, "W"), Tfrontera=("700", "K")))
    for par, paq, tf in ((nombres5, "mezcla-ideal", "300"), (nrtl4, "nrtl-chemsep", "300"),
                         (("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol"), "mezcla-ideal", "300")):
        t0 = time.perf_counter()
        red = calentar(par, paq, tf, "100")
        r = me.resolver(red.solicitud())
        dt = time.perf_counter() - t0
        if not r["resultados"]:
            check(False, f"calentamiento N={len(par)} {paq}: {r['estado']} {[d['mensaje'][:120] for d in r['validacion']['diagnosticos']]}")
            continue
        s = mz.Sistema(paq, [CAS[k] for k in par])
        z = np.ones(len(par)) / len(par)
        H0 = s.equilibrio_TP(330.0, P, z).H
        H = serie(r, "volumen.A.H")
        ts = r["resultados"]["tiempos"]
        check(max(abs(H[k] - H0 - 100.0 * ts[k]) for k in range(len(ts))) < 1e-6 * abs(H0) + 1e-6,
              f"N={len(par)} {paq}: H = H0 + Q t ({dt:.1f} s, {len(ts)} muestras)")
        lo, hi = 330.0, 400.0
        for _ in range(60):
            m = 0.5 * (lo + hi)
            if fases(s.equilibrio_TP(m, P, z), "vapor"):
                hi = m
            else:
                lo = m
        tb = (s.equilibrio_TP(hi, P, z).H - H0) / 100.0
        ev = [e for e in r["resultados"]["eventos"] if e["codigo"] == "aparicion_fase"]
        check(len(ev) >= 1 and abs(ev[0]["tiempo"] - tb) < 1e-5 * tb and ev[0]["faseIds"] == ["vapor-1"],
              f"N={len(par)}: burbuja a {ev[0]['tiempo'] if ev else None} s frente a {tb:.6f} s (flash estatico)")
        cert = r["resultados"]["certificacion"]
        check(cert["estado"] == "cumple" and all(x["maximoEscalado"] <= x["tolerancia"] for x in r["resultados"]["residuos"]),
              f"N={len(par)}: certificacion {cert['estado']}")
        nser = [serie(r, f"volumen.A.n.{k + 1}") for k in range(len(par))]
        check(all(max(abs(v - nser[k][0]) for v in nser[k]) < 1e-12 for k in range(len(par))), f"N={len(par)}: cada especie constante")
    # sensibilidad a tolerancia y muestreo (N=5 ideal)
    ra = me.resolver(calentar(nombres5, "mezcla-ideal", "300", "100", rtol=1e-6, muestras=3).solicitud())
    rb = me.resolver(calentar(nombres5, "mezcla-ideal", "300", "100", rtol=1e-10, muestras=9).solicitud())
    ta = [e["tiempo"] for e in ra["resultados"]["eventos"]]
    tb_ = [e["tiempo"] for e in rb["resultados"]["eventos"]]
    check(len(ta) == len(tb_) >= 1 and max(abs(x - y) for x, y in zip(ta, tb_)) < 1e-5 * 300,
          f"N=5: eventos con rtol 1e-6/3 muestras y 1e-10/9 muestras: {ta} / {tb_}")
    # rigido con vapor: U = U0 + Q t, V constante (4 especies NRTL)
    s = mz.Sistema("nrtl-chemsep", [CAS[k] for k in nrtl4])
    z = np.ones(4) / 4
    e0 = s.equilibrio_TP(352.0, P, z)
    red = (Red("n-rig", nrtl4, tf=("100", "s"), muestras=5).paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {k: ("0.25", "mol") for k in nrtl4}, ("U", repr(e0.U), "J"), V=(repr(e0.V), "m3"), base="molar")
           .calor("q", None, "A", Q=("20", "W"), Tfrontera=("700", "K")))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        U = serie(r, "volumen.A.U")
        V = serie(r, "volumen.A.V")
        ts = r["resultados"]["tiempos"]
        check(max(abs(U[k] - e0.U - 20 * ts[k]) for k in range(len(ts))) < 1e-6 * abs(e0.U) + 1e-6 and
              max(abs(v - e0.V) for v in V) < 1e-12 * e0.V and r["resultados"]["certificacion"]["estado"] == "cumple",
              "N=4 rigido con vapor: U = U0 + Q t, V constante, certificado")
    else:
        check(False, f"rigido N=4: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
    # dos volumenes: corriente interna (con inversion de signo) y contacto termico; especie inicialmente cero
    par = ("benceno", "tolueno", "etanol", "metanol", "agua")
    red = (Red("n-red", par, tf=("200", "s"), muestras=5).paquete("p", "mezcla-ideal")
           .volumen("A", "p", {"benceno": ("0.3", "mol"), "tolueno": ("0.3", "mol"), "etanol": ("0.2", "mol"),
                               "metanol": ("0.2", "mol"), "agua": ("0", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                    base="molar")
           .volumen("B", "p", {"benceno": ("0.1", "mol"), "tolueno": ("0.4", "mol"), "etanol": ("0.1", "mol"),
                               "metanol": ("0.1", "mol"), "agua": ("0.3", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                    base="molar")
           .corriente("s", "A", "B", par, ("-0.001", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "mezcla_homogenea"}, "B": {"tipo": "mezcla_homogenea"}})
           .calor("c", "A", "B", G=("0.5", "W/K")))
    t0 = time.perf_counter()
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        nA = [serie(r, f"volumen.A.n.{k + 1}") for k in range(5)]
        nB = [serie(r, f"volumen.B.n.{k + 1}") for k in range(5)]
        ts = r["resultados"]["tiempos"]
        check(max(abs(nA[i][k] + nB[i][k] - nA[i][0] - nB[i][0]) for i in range(5) for k in range(len(ts))) < 1e-10,
              f"N=5 dos volumenes: conservacion por especie ({time.perf_counter() - t0:.1f} s)")
        xB0 = [nB[i][0] / sum(nB[j][0] for j in range(5)) for i in range(5)]
        check(all(abs(nB[i][-1] / sum(nB[j][-1] for j in range(5)) - xB0[i]) < 1e-9 for i in range(5)),
              "caudal negativo: el donante es B y conserva su composicion")
        check(nA[4][0] == 0.0 and nA[4][-1] > 0 and abs(nA[4][-1] - 0.3 * 0.001 * ts[-1]) < 1e-9,
              f"el agua entra en A desde cero sin inventario ficticio: {nA[4][-1]:.9f} mol")
        ids = [{f["id"] for f in m["evaluacion"]["fases"]} for m in r["resultados"]["estados"]["A"]]
        comp0 = r["resultados"]["estados"]["A"][0]["evaluacion"]["fases"][0]["composicionMolar"]["5"]
        check(comp0 == 0.0 and r["resultados"]["certificacion"]["estado"] == "cumple" and
              all(x["maximoEscalado"] <= x["tolerancia"] for x in r["resultados"]["residuos"]),
              "especie ausente con ID conservado (x = 0) y red certificada")
        check(r["resultados"]["segundaLey"]["estado"] == "cumple", "segunda ley de la red cerrada")
    else:
        check(False, f"red N=5: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
    # extraccion de vapor de un volumen L-V: cambia la composicion global; al agotarse el vapor, evento terminal
    s = mz.Sistema("mezcla-ideal", [CAS[k] for k in nombres5])
    z = np.ones(5) / 5
    red = (Red("n-ext", nombres5, tf=("2000", "s"), muestras=6).paquete("p", "mezcla-ideal")
           .volumen("A", "p", {k: ("0.2", "mol") for k in nombres5}, ("T", "357", "K"), P=("101325", "Pa"), base="molar",
                    adiabatico=True)
           .corriente("o", "A", None, nombres5, ("0.0005", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "fase", "fase": "vapor"}}))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        ev = [e["codigo"] for e in r["resultados"]["eventos"]]
        nn = [serie(r, f"volumen.A.n.{k + 1}") for k in range(5)]
        x_fin = np.array([v[-1] for v in nn]) / sum(v[-1] for v in nn)
        # El vapor se agota en tiempo finito: mas alla no hay vapor que extraer, asi que ningun paso cruza esa
        # frontera; el evento terminal es la detencion fase_ausente, con el vapor ya residual en la ultima muestra.
        ult = r["resultados"]["estados"]["A"][-1]["evaluacion"]["fases"]
        beta_v = next((f["fraccionMolar"] for f in ult if f["tipo"] == "vapor"), 0.0)
        check(ev[-1:] == ["fase_ausente"] and r["estado"] == "parcial" and beta_v < 1e-8 and
              any(d["codigo"] == "MOTOR_ENS_DETENIDO_FASE_AUSENTE" for d in r["validacion"]["diagnosticos"]),
              f"extraccion de vapor hasta agotarlo: detencion terminal por fase ausente con vapor residual {beta_v:.1e}")
        check(np.max(np.abs(x_fin - 0.2)) > 1e-3 and r["resultados"]["certificacion"]["estado"] in ("cumple", "no_evaluable"),
              "la composicion global cambia al extraer solo vapor; trayectoria publicada certificada")
    else:
        check(False, f"extraccion N=5: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")

print(f"\n{'OK' if not FALLOS else 'FALLOS: ' + str(len(FALLOS))}: {CHECKS[0]} comprobaciones")
sys.exit(1 if FALLOS else 0)
