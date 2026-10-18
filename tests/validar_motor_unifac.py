"""
UNIFAC en el motor generico (frontend/CONTRATO_CLAUDE_UNIFAC_MOTOR.md, hitos U0-U6).

Referencias independientes del motor:
  * thermo.unifac.UNIFAC.from_subgroups (otra implementacion, con las MISMAS tablas fijadas) para ln gamma, h^E
    y, a traves de ella, flash gamma-phi L-V y L-L por isoactividad escritos aqui (sustitucion sucesiva +
    Rachford-Rice); el motor minimiza G con su prueba de plano tangente;
  * identidades: Gibbs-Duhem, g = h - T s = sum x mu, entalpias parciales molares por diferencias;
  * experimento: azeotropo etanol-agua a 1 atm (literatura 78.15 C, x 0.894) y solubilidad mutua agua/1-butanol
    (IUPAC-NIST SDS vol. 15). UNIFAC es una PREDICCION: se publica el error, sin ajustar nada.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_unifac.py [seccion ...]      (secciones 0-7)
"""

import copy
import itertools
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
from scipy.optimize import brentq

from backend import motor_diagramas as mdg
from backend import motor_ensamblaje as me
from backend import motor_ensamblaje_v2 as v2
from backend import motor_termodinamica as mt
from core import mezclas as mz
from core import mezclas_datos as md
from core import unifac
from solicitudes_v2 import CAS, POL, Red

FALLOS, CHECKS = [], [0]
R = mz.R
SECCIONES = sys.argv[1:]
NOM = {v: k for k, v in CAS.items()}
TODAS = [CAS[k] for k in ("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol")]
PAQ = "unifac-original-public"
P = 101325.0


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


def fases(e, tipo):
    return [f for f in e.fases if f.tipo == tipo]


def thermo_unifac(cas, variante, T, x):
    import thermo.unifac as tu
    tu.load_unifac_ip()
    sg, ip = {"original": (tu.UFSG, tu.UFIP), "dortmund": (tu.DOUFSG, tu.DOUFIP2016), "lle": (tu.LLEUFSG, tu.LLEUFIP)}[variante]
    grupos = [unifac.asignacion(c, variante) for c in cas]
    return tu.UNIFAC.from_subgroups(T=T, xs=list(x), chemgroups=grupos, subgroups=sg, interaction_data=ip,
                                    version=1 if variante == "dortmund" else 0)


def rachford_rice(z, K):
    f = lambda b: float(np.sum(z * (K - 1) / (1 + b * (K - 1))))
    if f(0.0) <= 0:
        return 0.0
    if f(1.0) >= 0:
        return 1.0
    return brentq(f, 0.0, 1.0, xtol=1e-15, rtol=1e-15)


def K_ideal(s, T, P):
    return np.array([e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (R * T)) / P for e in s.esp])


def flash_gamma_phi(s, T, P, z, iteraciones=800):
    """Flash L-V independiente con gamma de thermo: K = gamma(x) Psat exp(Poynting)/P."""
    Kp = K_ideal(s, T, P)
    K = Kp.copy()
    for _ in range(iteraciones):
        b = rachford_rice(z, K)
        x = z / (1 + b * (K - 1))
        x = x / x.sum()
        Kn = np.array(thermo_unifac(s.cas, s.liq.variante, T, x).gammas()) * Kp
        if np.max(np.abs(Kn / K - 1)) < 1e-14:
            K = Kn
            break
        K = Kn
    b = rachford_rice(z, K)
    x = z / (1 + b * (K - 1))
    return b, x / x.sum(), (K * x) / (K * x).sum()


def flash_ll(cas, T, z, x1, x2, iteraciones=4000, variante="original"):
    """L-L independiente con gamma de thermo: x^II = K x^I con K = gamma^I/gamma^II."""
    for _ in range(iteraciones):
        K = (np.array(thermo_unifac(cas, variante, T, x1).gammas()) /
             np.array(thermo_unifac(cas, variante, T, x2).gammas()))
        b = rachford_rice(z, K)
        n1 = z / (1 + b * (K - 1))
        x1n, x2n = n1 / n1.sum(), K * n1 / (K * n1).sum()
        if max(np.max(np.abs(x1n - x1)), np.max(np.abs(x2n - x2))) < 1e-14:
            return b, x1n, x2n
        x1, x2 = x1n, x2n
    return b, x1, x2


def comp(cas_lista):
    return [{"id": k + 1, "nombre": NOM[c], "simbolo": NOM[c][:2], "identidadQuimica": {"cas": c}}
            for k, c in enumerate(cas_lista)]


def puntual(cas_lista, esp, modelo=PAQ):
    return {"revision": 1, "solicitudId": "u", "propietarioId": "p", "componentes": comp(cas_lista),
            "declaracion": {"modelo": {"id": modelo, "version": "1"}, "politica": dict(POL), "especificacion": esp}}


def esp_TP(T, P, fr):
    return {"tipo": "TP", "T": {"valor": T, "unidad": "K"}, "P": {"valor": P, "unidad": "Pa"},
            "composicion": {"base": "molar", "fracciones": {str(k + 1): v for k, v in enumerate(fr)}}}


def diagrama(par, corte, modelo=PAQ, perfil="exploratoria"):
    return {"revision": 1, "solicitudId": "u", "componentes": comp([CAS[n] for n in par]),
            "modelo": {"id": modelo, "version": "1"}, "componenteEjeId": 1, "corte": corte,
            "intervaloComposicion": [0.0, 1.0], "resolucion": perfil}


class Parche:
    """Sustituye temporalmente un atributo (monkeypatch) y vacia las caches de tablas/sistemas."""

    def __init__(self, obj, nombre, valor):
        self.obj, self.nombre, self.valor = obj, nombre, valor

    def __enter__(self):
        self.viejo = getattr(self.obj, self.nombre)
        setattr(self.obj, self.nombre, self.valor)
        return self

    def __exit__(self, *a):
        setattr(self.obj, self.nombre, self.viejo)


# ======================================================================
if activa("0"):
    seccion("U0. Cobertura, datos fijados y capacidades")
    for variante in ("original", "dortmund"):           # 'lle' (sin metanol) se audita en U7
        t = unifac.tablas(variante)
        check(all(len(t["ident"][k]) == 64 for k in ("sha256_interacciones", "sha256_asignaciones")),
              f"{variante}: tablas identificadas por sha256 de los archivos distribuidos")
        asig = {c: unifac.asignacion(c, variante) for c in TODAS}
        principales = sorted({t["sub"][k][0] for a in asig.values() for k in a})
        faltan = [(m, n) for m in principales for n in principales if m != n and (m, n) not in t["inter"]]
        check(not faltan, f"{variante}: las 7 especies asignadas y ninguna interaccion dirigida ausente "
                          f"entre los grupos principales {principales}")
    asig = unifac.asignacion(CAS["etanol"], "original")
    check(asig == {1: 1, 2: 1, 14: 1}, f"etanol (original) = CH3 + CH2 + OH: {asig}")
    check(unifac.asignacion(CAS["agua"], "original") == {16: 1} and
          unifac.asignacion(CAS["tolueno"], "original") == {9: 5, 11: 1}, "agua = H2O; tolueno = 5 ACH + ACCH3")
    cap = v2.capacidades_v2()
    paq = next(p for p in cap["paquetes"] if p["modelo"]["id"] == PAQ)
    comb = {c["id"]: c for c in paq["combinaciones"]}
    check(comb["liquido_vapor"]["evidencia"] == comb["liquido_liquido"]["evidencia"] == "cualitativa" and
          comb["liquido_vapor"]["publicada"] and comb["liquido_liquido"]["publicada"],
          "capacidades v2: L-V y L-L publicadas como prediccion ('cualitativa'), nunca 'contrastada'")
    cob = paq["coberturaGrupos"]
    check(cob["tipo"] == "contribucion_de_grupos" and len(cob["especies"]) == len(md.especies_disponibles()) and not cob["especiesSinAsignacion"]
          and not cob["interaccionesDirigidasFaltantes"] and "pares" not in paq,
          "cobertura de grupos publicada por especie; sin lista de pares moleculares")
    check(cap["tamanos"]["contrastados"][PAQ]["estatico"][-1] == 7, "tamanos contrastados de UNIFAC publicados")
    paq_d = next(p for p in mdg.capacidades()["paquetes"] if p["modelo"]["id"] == PAQ)
    check(paq_d["coberturaGrupos"] == cob and paq_d["pares"] is None, "capacidades de diagramas: misma cobertura")
    cob["especies"].clear()
    check(len(v2.cobertura_unifac(PAQ)["especies"]) == len(md.especies_disponibles()),
          "la cobertura publicada es una copia (la cache no se altera)")
    # huella: depende de grupos, variante y datos
    s = mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]])
    h0 = s.huella()
    check(h0 != mz.Sistema("nrtl-chemsep", [CAS["etanol"], CAS["agua"]]).huella(), "huella distinta de NRTL")
    t = unifac.tablas("original")
    ident = dict(t["ident"])
    t["ident"] = dict(ident, sha256_interacciones="0" * 64)
    try:
        check(mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]]).huella() != h0, "huella sensible al sha256 de las tablas")
    finally:
        t["ident"] = ident
    inter = t["inter"]
    t["inter"] = {**inter, (1, 7): (inter[(1, 7)][0] + 1.0, 0.0, 0.0)}
    try:
        s2 = mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]])
        check(s2.huella() != h0, "huella sensible a un valor de interaccion usado")
    finally:
        t["inter"] = inter
    check(mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]]).huella() == h0, "huella restablecida al restaurar las tablas")

# ======================================================================
if activa("1"):
    seccion("U1. Adaptador frente a thermo (otra implementacion); derivadas e identidades")
    rng = np.random.default_rng(5)
    for variante in ("original", "dortmund"):
        peor_g, peor_h = 0.0, 0.0
        for n in (2, 3, 4, 5, 7):
            cas = TODAS[:n] if n != 2 else [CAS["etanol"], CAS["agua"]]
            m = unifac.LiquidoUNIFAC(cas, variante)
            for T in (300.0, 340.0, 370.0):
                x = rng.dirichlet(np.ones(n))
                ref = thermo_unifac(cas, variante, T, x)
                peor_g = max(peor_g, float(np.max(np.abs(m.lngamma(T, x) - np.log(ref.gammas())))))
                hE = -R * T ** 2 * (mz.dgE_dT(m, T, x) / (R * T) - m.gE_RT(T, x) / T)
                peor_h = max(peor_h, abs(hE - ref.HE()) / max(1.0, abs(ref.HE())))
        check(peor_g < 1e-12, f"{variante}: ln gamma frente a thermo, N=2..7, 15 puntos: {peor_g:.1e}")
        check(peor_h < 1e-8, f"{variante}: h^E (paso complejo) frente a HE() de thermo: {peor_h:.1e}")
    m = unifac.LiquidoUNIFAC(TODAS, "original")
    x = np.ones(7) / 7
    T = 340.0
    d = 1e-6
    peor = 0.0
    for _ in range(4):
        u = rng.normal(size=7)
        u -= u.mean()
        peor = max(peor, abs(float(x @ (m.lngamma(T, x + d * u) - m.lngamma(T, x - d * u))) / (2 * d)))
    check(peor < 1e-7, f"Gibbs-Duhem N=7 en direcciones aleatorias: {peor:.1e}")
    dfin = (m.gE_RT(T + 1e-3, x) * (T + 1e-3) - m.gE_RT(T - 1e-3, x) * (T - 1e-3)) * R / 2e-3
    check(abs(mz.dgE_dT(m, T, x) - dfin) < 1e-6 * max(1.0, abs(dfin)), "d g^E/dT por paso complejo frente a diferencias")
    x0 = np.array([0.0, 0.3, 0.3, 0.2, 0.2, 0.0, 0.0])
    lg = m.lngamma(T, x0)
    check(np.all(np.isfinite(lg)), "ln gamma finito a dilucion infinita (especies con x = 0)")
    sub = m.subconjunto([4, 2])
    check(np.max(np.abs(sub.lngamma(T, [0.6, 0.4]) - unifac.LiquidoUNIFAC([TODAS[4], TODAS[2]], "original")
                        .lngamma(T, [0.6, 0.4]))) == 0.0, "subconjunto = modelo construido con esas especies")
    try:
        m._A[0, 1] = 1.0
        check(False, "las matrices del adaptador debian ser de solo lectura")
    except ValueError:
        check(True, "adaptador inmutable (arrays de solo lectura)")
    pure = [m.lngamma(T, np.eye(7)[i])[i] for i in range(7)]
    check(max(abs(v) for v in pure) < 1e-13, "ln gamma_i = 0 en la especie pura")

# ======================================================================
if activa("2"):
    seccion("U2. TP, estabilidad y reparto frente a flash independiente; negativos")
    s = mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]])
    for T, z in ((355.0, np.array([0.5, 0.5])), (352.0, np.array([0.2, 0.8])), (351.3, np.array([0.85, 0.15]))):
        e = s.equilibrio_TP(T, P, z)
        b, x, y = flash_gamma_phi(s, T, P, z)
        v, l = fases(e, "vapor"), fases(e, "liquido")
        if 0 < b < 1:
            ok = len(v) == 1 and len(l) == 1 and abs(v[0].n - b) < 1e-8 and np.max(np.abs(l[0].x - x)) < 1e-8 \
                and np.max(np.abs(v[0].x - y)) < 1e-8
        else:
            ok = len(e.fases) == 1
        check(ok and e.verificaciones["estabilidad"][0] <= mz.TOL_TM,
              f"etanol-agua T={T} z={z.tolist()}: beta {b:.8f} frente a flash gamma-phi con thermo")
    for S, T in ((TODAS[:4], 346.0), (TODAS[:5], 344.0), (TODAS, 351.0)):
        s = mz.Sistema(PAQ, S)
        z = np.ones(len(S)) / len(S)
        t0 = time.perf_counter()
        e = s.equilibrio_TP(T, P, z)
        dt = time.perf_counter() - t0
        b, x, y = flash_gamma_phi(s, T, P, z)
        v, l = fases(e, "vapor"), fases(e, "liquido")
        check(len(v) == 1 and len(l) == 1 and abs(v[0].n - b) < 1e-8 and np.max(np.abs(l[0].x - x)) < 1e-8 and
              e.verificaciones["estabilidad"][0] <= mz.TOL_TM,
              f"N={len(S)} T={T}: L-V frente a flash con thermo, beta {b:.6f} ({dt:.2f} s)")
    s5 = mz.Sistema(PAQ, TODAS[:5])
    e = s5.equilibrio_TP(341.0, P, np.ones(5) / 5)
    check(sorted(f.tipo for f in e.fases) == ["liquido", "liquido", "vapor"] and
          e.verificaciones["estabilidad"][0] <= mz.TOL_TM and e.verificaciones["equilibrio"][0] <= mz.TOL_MU,
          f"N=5 (benceno, tolueno, etanol, metanol, agua) a 341 K: L-L-V certificado ({[f.id for f in e.fases]})")
    # L-L binario agua/1-butanol frente a isoactividad con thermo y frente a IUPAC (prediccion)
    cas = [CAS["agua"], CAS["butanol"]]
    s = mz.Sistema(PAQ, cas)
    Mw, Mb = 18.015, 74.12
    tabla = []
    for T, w_aq, w_org in ((293.15, 7.8, 20.0), (298.15, 7.4, 20.3), (323.15, 6.4, 22.4), (353.15, 7.0, 27.5)):
        e = s.equilibrio_TP(T, P, np.array([0.75, 0.25]))
        l = sorted(fases(e, "liquido"), key=lambda f: -f.x[0])
        if len(l) != 2:
            check(False, f"agua/butanol {T} K: se esperaban dos liquidos ({[f.id for f in e.fases]})")
            continue
        b, x1, x2 = flash_ll(cas, T, np.array([0.75, 0.25]), l[0].x.copy(), l[1].x.copy())
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8,
              f"agua/butanol {T} K: L-L frente a isoactividad independiente (thermo)")
        wb = lambda f: 100 * f.x[1] * Mb / (f.x[1] * Mb + f.x[0] * Mw)
        tabla.append((T, w_aq, wb(l[0]), w_org, 100 - wb(l[1])))
    for T, a, pa, o, po in tabla:
        print(f"    {T:.2f} K  butanol en fase acuosa {pa:5.2f} (IUPAC {a}) | agua en fase organica {po:5.2f} (IUPAC {o}) g/100 g")
    if tabla:
        check(abs(tabla[0][2] - tabla[0][1]) < 1.0 and abs(tabla[0][4] - tabla[0][3]) < 1.0,
              "agua/butanol a 293 K: solubilidades mutuas predichas a menos de 1 g/100 g de IUPAC (prediccion)")
    # cuaternario L-L (agua, etanol, acetato, metanol) frente a isoactividad independiente
    cas4 = [CAS[k] for k in ("agua", "etanol", "acetato", "metanol")]
    s4 = mz.Sistema(PAQ, cas4)
    z4 = np.array([0.7, 0.04, 0.24, 0.02])
    e = s4.equilibrio_TP(300.0, P, z4)
    l = sorted(fases(e, "liquido"), key=lambda f: -f.x[0])
    check(len(l) == 2 and e.verificaciones["estabilidad"][0] <= mz.TOL_TM,
          f"N=4 agua-etanol-acetato-metanol a 300 K: dos liquidos ({[f.id for f in e.fases]})")
    if len(l) == 2:
        b, x1, x2 = flash_ll(cas4, 300.0, z4, l[0].x.copy(), l[1].x.copy())
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8 and abs(b - l[1].n) < 1e-8,
              "L-L de 4 especies frente a isoactividad independiente (thermo)")
    mu = s4.mu("liquido", 300.0, P, z4, [0, 1, 2, 3])
    p1 = s4._estabilidad_general(300.0, P, mu, [0, 1, 2, 3])
    p2 = s4._estabilidad_general(300.0, P, mu, [0, 1, 2, 3])
    check([q[2] for q in p1] == [q[2] for q in p2] and min(q[2] for q in p1) < -1e-6,
          "estabilidad general determinista; el homogeneo L-L se rechaza por tm < 0")
    # ausencias, trazas, escala, permutaciones, semillas
    s7 = mz.Sistema(PAQ, TODAS)
    s4b = mz.Sistema(PAQ, TODAS[:4])
    z7 = np.array([0.3, 0.2, 0.3, 0.2, 0.0, 0.0, 0.0])
    a, b_ = s7.equilibrio_TP(352.0, P, z7), s4b.equilibrio_TP(352.0, P, z7[:4])
    check(abs(a.G - b_.G) < 1e-9 * abs(a.G) and len(a.fases) == len(b_.fases) and
          all(np.all(f.x[4:] == 0) and np.all(np.isnan(f.mu[4:])) for f in a.fases),
          "especies exactamente ausentes: mismo estado que el sistema reducido, x = 0 y mu indefinida")
    for traza in (1e-6, 1e-9, 1e-12):
        z = np.array([0.3, 0.2, 0.3, 0.2 - traza, traza, 0, 0])
        e = s7.equilibrio_TP(352.0, P, z)
        rec = max(abs(sum(f.n * f.x[i] for f in e.fases) - z[i]) / z[i] for i in range(5))
        check(rec < 1e-9 and e.verificaciones["equilibrio"][0] <= mz.TOL_MU,
              f"traza {traza:g}: reconstruccion por especie {rec:.1e}")
    for escala in (1e-6, 1e6):
        e = s7.equilibrio_TP(352.0, P, escala * z7)
        check(abs(e.G - escala * a.G) <= 1e-9 * abs(escala * a.G), f"extensividad x{escala:g}")
    rng = np.random.default_rng(3)
    ref4 = mz.Sistema(PAQ, cas4)
    er = ref4.equilibrio_TP(300.0, P, z4)
    for _ in range(3):
        perm = rng.permutation(4)
        sp = mz.Sistema(PAQ, [cas4[k] for k in perm])
        ep = sp.equilibrio_TP(300.0, P, z4[perm])
        check(abs(er.G - ep.G) < 1e-9 * abs(er.G) and len(er.fases) == len(ep.fases) and sp.huella() == ref4.huella(),
              f"permutacion {perm.tolist()}: mismo equilibrio L-L y misma huella")
    for sem in (ref4.equilibrio_TP(300.0, P, np.array([0.6, 0.05, 0.3, 0.05])), ref4.equilibrio_TP(330.0, P, z4)):
        e = ref4.flash_rapido("TP", 300.0, P, z4, sem)
        check(abs(e.G - er.G) < 1e-9 * abs(er.G) and len(e.fases) == len(er.fases),
              f"semilla {[f.tipo for f in sem.fases]}: mismo minimo que el flash completo")
    viejo = mz.MAX_FASES
    mz.MAX_FASES = 1
    try:
        ref4.equilibrio_TP(300.0, P, z4)
        check(False, "con tope de 1 fase el L-L debia rechazarse")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "no_soportado" and x.datos.get("tope_fases"), "tope de fases: rechazo explicito")
    finally:
        mz.MAX_FASES = viejo
    try:
        mz.Sistema(PAQ, cas4).equilibrio_TP(290.0, P, z4)
        check(False, "290 K fuera del dominio comun")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "fuera_de_dominio", "T fuera de la interseccion de dominios: rechazada")

# ======================================================================
if activa("3"):
    seccion("U3. Energia: identidades, inversiones PH/UP/UV y no identificabilidad")
    s = mz.Sistema(PAQ, [CAS[k] for k in ("agua", "etanol", "acetato", "metanol")])
    x = np.array([0.3, 0.2, 0.3, 0.2])
    T = 330.0
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
    check(peor < 1e-6, f"entalpias parciales molares frente a h_i - R T^2 d ln gamma_i/dT: {peor:.1e}")
    hE = f.h - float(x @ hp)
    ref = thermo_unifac(s.cas, "original", T, x).HE()
    check(abs(hE - ref) < 1e-7 * max(1.0, abs(ref)), f"h^E de la fase frente a thermo: {hE:.6f} / {ref:.6f} J/mol")
    sE = (f.s - float(x @ np.array([s.fase("p", "liquido", T, P, np.array([1.0]), [i]).s for i in range(4)]))
          + R * float(np.sum(x * np.log(x))))
    sE_ref = thermo_unifac(s.cas, "original", T, x).SE()
    check(abs(sE - sE_ref) < 1e-7 * max(1.0, abs(sE_ref)), f"s^E frente a thermo: {sE:.6f} / {sE_ref:.6f} J/(mol K)")
    cpE = (mz.dgE_dT(s.liq, T + 0.01, x) - mz.dgE_dT(s.liq, T - 0.01, x)) / 0.02 * (-T)
    cpE_ref = thermo_unifac(s.cas, "original", T, x).CpE()
    check(abs(cpE - cpE_ref) < 1e-5 * max(1.0, abs(cpE_ref)), f"Cp^E = -T d2gE/dT2 frente a thermo: {cpE:.5f} / {cpE_ref:.5f}")
    for S, T in (([CAS["etanol"], CAS["agua"]], 355.0), (TODAS[:5], 341.0), (TODAS, 351.0)):
        s = mz.Sistema(PAQ, S)
        z = np.ones(len(S)) / len(S)
        e = s.equilibrio_TP(T, P, z)
        for nombre, fn in (("PH", lambda: s.equilibrio_PH(P, e.H, z)), ("UP", lambda: s.equilibrio_UP(P, e.U, z)),
                           ("UV", lambda: s.equilibrio_UV(e.U, e.V, z))):
            t0 = time.perf_counter()
            q = fn()
            dt = time.perf_counter() - t0
            rec = max(abs(sum(fa.n * fa.x[i] for fa in q.fases) - z[i]) for i in range(len(S)))
            check(abs(q.T - T) < 1e-6 and abs(q.H - e.H) < 1e-8 * abs(e.H) + 1e-6 and abs(q.V - e.V) < 1e-9 * e.V and
                  rec < 1e-12 and len(q.fases) == len(e.fases),
                  f"N={len(S)} {nombre}: T, H, V y un unico reparto ({dt:.2f} s)")
    # L-L-V (meseta) en agua/butanol por PH: la entalpia fija la fraccion de vapor a T del heteroazeotropo
    s = mz.Sistema(PAQ, [CAS["agua"], CAS["butanol"]])
    z = np.array([0.75, 0.25])
    e_l = s.equilibrio_TP(360.0, P, z)
    e_v = s.equilibrio_TP(380.0, P, z)
    q = s.equilibrio_PH(P, 0.5 * (e_l.H + e_v.H), z)
    check(abs(q.H - 0.5 * (e_l.H + e_v.H)) < 1e-8 * abs(q.H) and q.verificaciones["estabilidad"][0] <= mz.TOL_TM,
          f"agua/butanol PH entre 360 y 380 K: {[f.id for f in q.fases]} a {q.T:.3f} K, H exacta y estable")
    s = mz.Sistema(PAQ, TODAS[:5])
    z = np.ones(5) / 5
    e = s.equilibrio_TP(320.0, P, z)
    try:
        s.equilibrio_UV(e.U, e.V, z)
        check(False, "UV de liquido incompresible debia rechazarse")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "no_soportado", "UV de liquido incompresible lleno: no identificable, rechazado")

# ======================================================================
if activa("4"):
    seccion("U4. Dinamica y redes con UNIFAC")

    def calentar(par, tf, Q, T0="330", muestras=6, politica=None):
        n0 = {k: (str(round(1.0 / len(par), 12)), "mol") for k in par}
        return (Red("u-cal", par, tf=(tf, "s"), muestras=muestras).paquete("p", PAQ)
                .volumen("A", "p", n0, ("T", T0, "K"), P=("101325", "Pa"), base="molar", politica=politica)
                .calor("q", None, "A", Q=(Q, "W"), Tfrontera=("700", "K")))

    for par in (("etanol", "agua"), ("agua", "etanol", "acetato", "metanol"), ("benceno", "tolueno", "etanol", "metanol", "agua")):
        t0 = time.perf_counter()
        r = me.resolver(calentar(par, "300", "100").solicitud())
        dt = time.perf_counter() - t0
        if not r["resultados"]:
            check(False, f"calentamiento N={len(par)}: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
            continue
        s = mz.Sistema(PAQ, [CAS[k] for k in par])
        z = np.ones(len(par)) / len(par)
        H0 = s.equilibrio_TP(330.0, P, z).H
        H = serie(r, "volumen.A.H")
        ts = r["resultados"]["tiempos"]
        check(max(abs(H[k] - H0 - 100.0 * ts[k]) for k in range(len(ts))) < 1e-6 * abs(H0) + 1e-6,
              f"N={len(par)}: H = H0 + Q t ({dt:.1f} s)")
        lo, hi = 330.0, 400.0
        for _ in range(60):
            m = 0.5 * (lo + hi)
            if fases(s.equilibrio_TP(m, P, z), "vapor"):
                hi = m
            else:
                lo = m
        tb = (s.equilibrio_TP(hi, P, z).H - H0) / 100.0
        ev = [e for e in r["resultados"]["eventos"] if e["codigo"] == "aparicion_fase" and "vapor-1" in e["faseIds"]]
        check(len(ev) >= 1 and abs(ev[0]["tiempo"] - tb) < 1e-5 * tb,
              f"N={len(par)}: aparicion de vapor a {ev[0]['tiempo'] if ev else None} s frente a {tb:.6f} s (estatico)")
        cert = r["resultados"]["certificacion"]
        check(cert["estado"] == "cumple" and all(x["maximoEscalado"] <= x["tolerancia"] for x in r["resultados"]["residuos"]),
              f"N={len(par)}: certificacion {cert['estado']}")
        proc = r["resultados"].get("procedenciaModelo") or []
        check(any(p.get("huella") == s.huella() for p in proc) if proc else False,
              f"N={len(par)}: procedenciaModelo publica la huella UNIFAC del paquete")
    # rigido con vapor
    par = ("agua", "etanol", "acetato", "metanol")
    s = mz.Sistema(PAQ, [CAS[k] for k in par])
    z = np.ones(4) / 4
    e0 = s.equilibrio_TP(350.0, P, z)
    red = (Red("u-rig", par, tf=("100", "s"), muestras=5).paquete("p", PAQ)
           .volumen("A", "p", {k: ("0.25", "mol") for k in par}, ("U", repr(e0.U), "J"), V=(repr(e0.V), "m3"), base="molar")
           .calor("q", None, "A", Q=("20", "W"), Tfrontera=("700", "K")))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        U, V = serie(r, "volumen.A.U"), serie(r, "volumen.A.V")
        ts = r["resultados"]["tiempos"]
        check(max(abs(U[k] - e0.U - 20 * ts[k]) for k in range(len(ts))) < 1e-6 * abs(e0.U) + 1e-6 and
              max(abs(v - e0.V) for v in V) < 1e-12 * e0.V and r["resultados"]["certificacion"]["estado"] == "cumple",
              f"N=4 rigido con {[f.id for f in e0.fases]}: U = U0 + Q t, V constante, certificado")
    else:
        check(False, f"rigido N=4: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
    # dos volumenes: corriente con inversion de signo, contacto termico, especie que entra desde cero
    par = ("benceno", "tolueno", "etanol", "metanol", "agua")
    red = (Red("u-red", par, tf=("200", "s"), muestras=5).paquete("p", PAQ)
           .volumen("A", "p", {"benceno": ("0.3", "mol"), "tolueno": ("0.3", "mol"), "etanol": ("0.2", "mol"),
                               "metanol": ("0.2", "mol"), "agua": ("0", "mol")}, ("T", "335", "K"), P=("101325", "Pa"),
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
        check(nA[4][0] == 0.0 and abs(nA[4][-1] - 0.3 * 0.001 * ts[-1]) < 1e-9,
              f"el agua entra en A desde cero: {nA[4][-1]:.9f} mol")
        check(r["resultados"]["certificacion"]["estado"] == "cumple" and r["resultados"]["segundaLey"]["estado"] == "cumple",
              "red certificada y segunda ley cumplida")
    else:
        check(False, f"red N=5: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
    # mezcla adiabatica: dos volumenes a P, solo corriente; H total constante
    par = ("etanol", "agua")
    red = (Red("u-mez", par, tf=("100", "s"), muestras=4).paquete("p", PAQ)
           .volumen("A", "p", {"etanol": ("0.8", "mol"), "agua": ("0.2", "mol")}, ("T", "300", "K"), P=("101325", "Pa"),
                    base="molar", adiabatico=True)
           .volumen("B", "p", {"etanol": ("0.1", "mol"), "agua": ("0.9", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                    base="molar", adiabatico=True)
           .corriente("s", "A", "B", par, ("0.005", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "mezcla_homogenea"}}))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        H = [a + b for a, b in zip(serie(r, "volumen.A.H"), serie(r, "volumen.B.H"))]
        check(max(abs(h - H[0]) for h in H) < 1e-8 * abs(H[0]) and r["resultados"]["segundaLey"]["estado"] == "cumple",
              "mezcla adiabatica isobara: H total constante y produccion de entropia >= 0")
        TB = serie(r, "volumen.B.T")
        check(TB[-1] != TB[0], f"el calor de mezcla UNIFAC cambia T de B: {TB[0]:.3f} -> {TB[-1]:.3f} K")
    else:
        check(False, f"mezcla adiabatica: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
    # extraccion por fase (vapor) hasta agotarlo
    par = ("etanol", "agua")
    s = mz.Sistema(PAQ, [CAS[k] for k in par])
    T_m = 355.0                                      # L-V a 1 atm con z = (0.5, 0.5)
    red = (Red("u-ext", par, tf=("4000", "s"), muestras=6).paquete("p", PAQ)
           .volumen("A", "p", {k: ("0.5", "mol") for k in par}, ("T", repr(T_m), "K"), P=("101325", "Pa"), base="molar",
                    adiabatico=True)
           .corriente("o", "A", None, par, ("0.0005", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "fase", "fase": "vapor"}}))
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        ev = [e["codigo"] for e in r["resultados"]["eventos"]]
        check(ev[-1:] == ["fase_ausente"] and r["estado"] == "parcial" and
              any(d["codigo"] == "MOTOR_ENS_DETENIDO_FASE_AUSENTE" for d in r["validacion"]["diagnosticos"]),
              f"extraccion de vapor (T0 {T_m:.2f} K) hasta agotarlo: detencion por fase ausente ({ev})")
    else:
        check(False, f"extraccion: {r['estado']} {[d['mensaje'][:150] for d in r['validacion']['diagnosticos']]}")
    # politica restringida: monofasico; la integracion se detiene en la burbuja. El estado terminal es la
    # arista (fase naciente con ~1e-10 mol) y el trabajo integrado cierra con [P V] (lado de la diferencia).
    s = mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]])
    H0 = s.equilibrio_TP(330.0, P, np.array([0.5, 0.5])).H
    lo, hi = 330.0, 400.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if fases(s.equilibrio_TP(m, P, np.array([0.5, 0.5])), "vapor"):
            hi = m
        else:
            lo = m
    tb = (s.equilibrio_TP(hi, P, np.array([0.5, 0.5])).H - H0) / 100.0
    r = me.resolver(calentar(("etanol", "agua"), "300", "100",
                             politica={"cantidad": "monofasico", "cambioInterno": "permitido",
                                       "evaluacion": "equilibrio_estable"}).solicitud())
    ult = r["resultados"]["estados"]["A"][-1]["evaluacion"]["fases"] if r["resultados"] else []
    beta_v = next((f["fraccionMolar"] for f in ult if f["tipo"] == "vapor"), 0.0)
    check(r["estado"] == "parcial" and abs(r["resultados"]["tiempos"][-1] - tb) < 1e-6 * tb and beta_v < 1e-8 and
          any(d["codigo"] == "MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO" for d in r["validacion"]["diagnosticos"]) and
          r["resultados"]["certificacion"]["estado"] == "cumple",
          f"politica monofasica: detencion en la burbuja ({r['resultados']['tiempos'][-1] if r['resultados'] else None} s "
          f"frente a {tb:.6f} s), vapor naciente {beta_v:.1e}, certificada")
    # datos incompletos: asignacion ausente simulada
    original = unifac.asignacion

    def sin_acetato(cas, variante):
        if cas == CAS["acetato"]:
            raise unifac.FaltaDatoUNIFAC("simulada", {"tipo": "asignacion_ausente", "cas": cas, "variante": variante})
        return original(cas, variante)
    with Parche(unifac, "asignacion", sin_acetato):
        r = me.resolver(calentar(("agua", "etanol", "acetato", "metanol"), "100", "100").solicitud())
    check(r["estado"] == "no_soportado" and not r["resultados"] and
          any(d["codigo"] == "MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE" for d in r["validacion"]["diagnosticos"]),
          f"asignacion ausente: rechazo con codigo propio, sin resultados ({r['estado']})")

# ======================================================================
if activa("5"):
    seccion("U5. Servicio puntual, diagramas, negativos con codigo y concurrencia")
    r = mt.evaluar(puntual([CAS["etanol"], CAS["agua"]], esp_TP(355.0, P, [0.5, 0.5])))
    check(r["estado"] == "evaluado" and len(r["evaluacion"]["fases"]) == 2 and
          all(v["estado"] != "no_cumple" for v in r["evaluacion"]["verificaciones"]), "servicio puntual: etanol-agua L-V")
    cas4 = [CAS[k] for k in ("agua", "etanol", "acetato", "metanol")]
    r = mt.evaluar(puntual(cas4, esp_TP(300.0, P, [0.7, 0.04, 0.24, 0.02])))
    check(r["estado"] == "evaluado" and [f["id"] for f in r["evaluacion"]["fases"]] == ["liquido-1", "liquido-2"],
          "servicio puntual: L-L de 4 especies")
    r = mt.evaluar(puntual(TODAS, esp_TP(351.0, P, [1 / 7] * 7)))
    check(r["estado"] == "evaluado", f"servicio puntual: 7 especies ({r['estado']})")
    # diagrama Txy etanol-agua: azeotropo frente a la literatura (prediccion)
    t0 = time.perf_counter()
    d = mdg.trazar(diagrama(("etanol", "agua"), {"tipo": "Txy", "P": {"valor": P, "unidad": "Pa"}}))
    dt = time.perf_counter() - t0
    az = [p for p in d.get("puntosEspeciales", []) if p["tipo"] == "azeotropo"]
    check(d["estado"] in ("completo", "parcial") and len(az) == 1 and abs(az[0]["T"] - 351.30) < 0.5 and
          abs(az[0]["xEje"] - 0.894) < 0.02,
          f"Txy etanol-agua: azeotropo {az[0]['T'] - 273.15 if az else None} C, x {az[0]['xEje'] if az else None} "
          f"(literatura 78.15 C, 0.894; {dt:.1f} s)")
    check(d["evidencia"]["nivel"] == "cualitativa" and
          d["identidad"]["huellaModelo"] == mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]]).huella(),
          "diagrama: evidencia 'cualitativa' y huella del paquete UNIFAC")
    # negativos con codigo en los tres servicios (simulados con monkeypatch, sin cambiar datos reales)
    original = unifac.asignacion
    t = unifac.tablas("original")

    def sin_agua(cas, variante):
        if cas == CAS["agua"]:
            raise unifac.FaltaDatoUNIFAC("simulada", {"tipo": "asignacion_ausente", "cas": cas, "variante": variante})
        return original(cas, variante)

    def asig_mal(cas, variante):
        if cas == CAS["agua"]:
            raise unifac.FaltaDatoUNIFAC("simulada", {"tipo": "grupo_desconocido", "cas": cas, "subgrupo": 9999,
                                                      "variante": variante})
        return original(cas, variante)
    inter_sin = {k: v for k, v in t["inter"].items() if k != (1, 7)}
    for codigo, ctx in (("UNIFAC_ASIGNACION_AUSENTE", Parche(unifac, "asignacion", sin_agua)),
                        ("UNIFAC_GRUPO_DESCONOCIDO", Parche(unifac, "asignacion", asig_mal)),
                        ("UNIFAC_INTERACCION_AUSENTE", None)):
        viejo_inter = t["inter"]
        if ctx is None:
            t["inter"] = inter_sin
            ctx = Parche(mz, "MAX_FASES", mz.MAX_FASES)          # sin efecto: solo para usar el mismo with
        try:
            with ctx:
                rp = mt.evaluar(puntual([CAS["etanol"], CAS["agua"]], esp_TP(352.0, P, [0.5, 0.5])))
                rd = mdg.trazar(diagrama(("etanol", "agua"), {"tipo": "Txy", "P": {"valor": P, "unidad": "Pa"}}))
        finally:
            t["inter"] = viejo_inter
        check(rp["estado"] == "no_soportado" and any(x["codigo"] == f"MOTOR_ESTADO_{codigo}" for x in rp["diagnosticos"]),
              f"servicio puntual: MOTOR_ESTADO_{codigo}")
        check(rd["estado"] == "no_soportado" and any(x["codigo"] == f"MOTOR_DIAG_{codigo}" for x in rd["diagnosticos"]),
              f"diagramas: MOTOR_DIAG_{codigo}")
    so_h = mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]]).huella()
    # unidades equivalentes y nombres/orden: mismo estado y misma huella fisica
    ra = mt.evaluar(puntual([CAS["etanol"], CAS["agua"]], esp_TP(355.0, P, [0.5, 0.5])))
    eb = esp_TP(355.0, P, [0.5, 0.5])
    eb["P"] = {"valor": P / 1e5, "unidad": "bar"}
    rb = mt.evaluar(puntual([CAS["etanol"], CAS["agua"]], eb))
    fa, fb = ra["evaluacion"]["fases"], rb["evaluacion"]["fases"]
    check(rb["estado"] == "evaluado" and len(fa) == len(fb) and
          all(abs(x["fraccionMolar"] - y["fraccionMolar"]) < 1e-12 for x, y in zip(fa, fb)),
          "misma peticion con P en bar: mismo reparto")
    sn = puntual([CAS["etanol"], CAS["agua"]], esp_TP(355.0, P, [0.5, 0.5]))
    for k, cmp_ in enumerate(sn["componentes"]):
        cmp_["nombre"], cmp_["simbolo"] = f"especie {k}", f"S{k}"
    rn = mt.evaluar(sn)
    check(rn["estado"] == "evaluado" and
          all(abs(x["fraccionMolar"] - y["fraccionMolar"]) < 1e-15 for x, y in zip(fa, rn["evaluacion"]["fases"])),
          "nombres y simbolos distintos: mismo estado (la identidad es el CAS)")
    check(mz.Sistema(PAQ, [CAS["agua"], CAS["etanol"]]).huella() == mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]]).huella(),
          "orden de especies distinto: misma huella fisica")
    # cero explicito valido: a_mn = 0 publicado no es una interaccion ausente
    vieja = t["inter"]
    t["inter"] = {**vieja, (1, 7): (0.0, 0.0, 0.0)}
    try:
        s0 = mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]])
        ok = np.all(np.isfinite(s0.liq.lngamma(330.0, np.array([0.5, 0.5])))) and s0.huella() != so_h
    except Exception as x:
        ok = False
        print("   ", x)
    finally:
        t["inter"] = vieja
    check(ok, "a_mn = 0 explicito en la tabla: se usa como dato (no se rechaza) y cambia la huella")
    # especie con grupos UNIFAC pero sin datos puros en el catalogo (n-hexano): rechazo, sin estado
    sp_ = puntual([CAS["etanol"], CAS["agua"]], esp_TP(355.0, P, [0.5, 0.5]))
    sp_["componentes"][1]["identidadQuimica"]["cas"] = "110-54-3"
    sp_["componentes"][1]["nombre"] = "n-hexano"
    unifac.asignacion("110-54-3", "original")
    rp = mt.evaluar(sp_)
    check(rp["estado"] != "evaluado" and not rp.get("evaluacion") and rp["diagnosticos"],
          f"n-hexano (con grupos DDBST, sin datos puros): {rp['estado']} {[d['codigo'] for d in rp['diagnosticos']][:2]}")
    try:
        unifac.LiquidoUNIFAC([CAS["etanol"], CAS["agua"]], "2.0")
        check(False, "variante desconocida debia rechazarse")
    except ValueError:
        check(True, "variante no admitida (p. ej. UNIFAC 2.0): ValueError, sin sustitucion silenciosa")
    # concurrencia en frio: proceso nuevo, 12 hilos simultaneos sobre UNIFAC y NRTL con mezclas y T distintas;
    # despues, cada caso aislado en el mismo proceso: deben coincidir bit a bit
    codigo = r'''
import sys, json, concurrent.futures as cf
sys.path.insert(0, ".")
from core import mezclas as mz
CASOS = [("unifac-original-public", ["64-17-5", "7732-18-5"], 352.0 + k, [0.3 + 0.03 * k, 0.7 - 0.03 * k]) for k in range(6)]
CASOS += [("nrtl-chemsep", ["64-17-5", "7732-18-5"], 352.0 + k, [0.3 + 0.03 * k, 0.7 - 0.03 * k]) for k in range(6)]
def una(c):
    paq, cas, T, z = c
    return mz.Sistema(paq, cas).equilibrio_TP(T, 101325.0, z).G
with cf.ThreadPoolExecutor(12) as ex:
    conc = list(ex.map(una, CASOS))
aisl = [una(c) for c in CASOS]
print(json.dumps([conc, aisl]))
'''
    malos = 0
    iguales = True
    for _ in range(2):
        p = subprocess.run([sys.executable, "-c", codigo], cwd=str(RAIZ), capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            malos += 1
            print(p.stderr[-800:])
            continue
        conc, aisl = json.loads(p.stdout.strip().splitlines()[-1])
        iguales = iguales and conc == aisl
    vistos = {1, 2} if iguales else set()
    check(malos == 0 and iguales, f"arranque en frio con 12 hilos (UNIFAC y NRTL, 12 mezclas), 2 rondas: {malos} fallos; "
                                  f"resultados concurrentes {'iguales' if iguales else 'DISTINTOS'} a los aislados")

# ======================================================================
if activa("6"):
    seccion("U6. Dortmund: variante propia de extremo a extremo")
    DO = "unifac-dortmund-public"
    rng = np.random.default_rng(9)
    m = unifac.LiquidoUNIFAC(TODAS, "dortmund")
    o = unifac.LiquidoUNIFAC(TODAS, "original")
    x = rng.dirichlet(np.ones(7))
    nombres = lambda var, a: sorted(unifac.tablas(var)["sub"][k][3] for k in a)
    check(m.identidad()["datos"]["sha256_interacciones"] != o.identidad()["datos"]["sha256_interacciones"] and
          nombres("dortmund", m.asignaciones[CAS["etanol"]]) == ["CH2", "CH3", "OH(P)"] and
          nombres("original", o.asignaciones[CAS["etanol"]]) == ["CH2", "CH3", "OH"],
          "Dortmund usa sus propias tablas y asignaciones (etanol con OH(P), alcohol primario)")
    check(np.max(np.abs(m.lngamma(340.0, x) - o.lngamma(340.0, x))) > 1e-3, "y da otro resultado (no es un alias)")
    sd, so = mz.Sistema(DO, [CAS["etanol"], CAS["agua"]]), mz.Sistema(PAQ, [CAS["etanol"], CAS["agua"]])
    check(sd.huella() != so.huella(), "huella distinta de la variante original con las mismas especies")
    for S, T in (([CAS["etanol"], CAS["agua"]], 355.0), (TODAS[:4], 346.0), (TODAS, 351.0)):
        s = mz.Sistema(DO, S)
        z = np.ones(len(S)) / len(S)
        e = s.equilibrio_TP(T, P, z)
        b, xl, y = flash_gamma_phi(s, T, P, z)
        v, l = fases(e, "vapor"), fases(e, "liquido")
        check(len(v) == 1 and len(l) == 1 and abs(v[0].n - b) < 1e-8 and np.max(np.abs(l[0].x - xl)) < 1e-8 and
              e.verificaciones["estabilidad"][0] <= mz.TOL_TM,
              f"Dortmund N={len(S)} T={T}: L-V frente a flash con thermo (version=1), beta {b:.6f}")
    cas = [CAS["agua"], CAS["butanol"]]
    s = mz.Sistema(DO, cas)
    e = s.equilibrio_TP(298.15, P, np.array([0.75, 0.25]))
    l = sorted(fases(e, "liquido"), key=lambda f: -f.x[0])
    if len(l) == 2:
        b, x1, x2 = flash_ll(cas, 298.15, np.array([0.75, 0.25]), l[0].x.copy(), l[1].x.copy(), variante="dortmund")
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8,
              "Dortmund agua/butanol 298 K: L-L frente a isoactividad independiente (prediccion pobre, ver informe)")
    else:
        check(False, f"Dortmund agua/butanol 298 K: se esperaban dos liquidos ({[f.id for f in e.fases]})")
    d = mdg.trazar(diagrama(("etanol", "agua"), {"tipo": "Txy", "P": {"valor": P, "unidad": "Pa"}}, modelo=DO))
    az = [q for q in d.get("puntosEspeciales", []) if q["tipo"] == "azeotropo"]
    check(len(az) == 1 and abs(az[0]["T"] - 351.30) < 0.5 and abs(az[0]["xEje"] - 0.894) < 0.02 and
          d["evidencia"]["nivel"] == "cualitativa",
          f"Dortmund Txy etanol-agua: azeotropo {az[0]['T'] - 273.15 if az else None} C, x {az[0]['xEje'] if az else None}")
    r = mt.evaluar(puntual([CAS[k] for k in ("agua", "etanol", "acetato", "metanol")], esp_TP(346.0, P, [0.25] * 4),
                           modelo=DO))
    check(r["estado"] == "evaluado", f"Dortmund: servicio puntual N=4 ({r['estado']})")
    for par in (("etanol", "agua"), ("agua", "etanol", "acetato", "metanol")):
        n0 = {k: (str(round(1.0 / len(par), 12)), "mol") for k in par}
        red = (Red("d-cal", par, tf=("300", "s"), muestras=6).paquete("p", DO)
               .volumen("A", "p", n0, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
               .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K")))
        t0 = time.perf_counter()
        r = me.resolver(red.solicitud())
        dt = time.perf_counter() - t0
        if not r["resultados"]:
            check(False, f"Dortmund calentamiento N={len(par)}: {r['estado']}")
            continue
        s = mz.Sistema(DO, [CAS[k] for k in par])
        H0 = s.equilibrio_TP(330.0, P, np.ones(len(par)) / len(par)).H
        H = serie(r, "volumen.A.H")
        ts = r["resultados"]["tiempos"]
        check(max(abs(H[k] - H0 - 100.0 * ts[k]) for k in range(len(ts))) < 1e-6 * abs(H0) + 1e-6 and
              r["resultados"]["certificacion"]["estado"] == "cumple" and
              any(e["codigo"] == "aparicion_fase" for e in r["resultados"]["eventos"]),
              f"Dortmund calentamiento N={len(par)}: H = H0 + Q t, burbuja detectada, certificado ({dt:.1f} s)")

if activa("7"):
    seccion("U7. Tabla dedicada a ELL (Magnussen 1981): traduccion de asignaciones, dominio y evidencia")
    LE = "unifac-original-lle-public"
    import thermo.unifac as tu
    tu.load_unifac_ip()
    S6 = [CAS[k] for k in ("agua", "etanol", "benceno", "tolueno", "butanol", "acetato")]
    t_o, t_l = unifac.tablas("original"), unifac.tablas("lle")
    ok = True
    for c in S6:
        a_o, a_l = unifac.asignacion(c, "original"), unifac.asignacion(c, "lle")
        ok = ok and sorted((t_o["sub"][k][3], t_o["sub"][k][1], t_o["sub"][k][2], n) for k, n in a_o.items()) == \
            sorted((t_l["sub"][k][3], t_l["sub"][k][1], t_l["sub"][k][2], n) for k, n in a_l.items())
    check(ok, "traduccion: mismos subgrupos (nombre, R, Q, cuenta) que la asignacion DDBST original, con IDs de la tabla LLE")
    check(unifac.asignacion(CAS["agua"], "lle") == {17: 1} and unifac.asignacion(CAS["agua"], "original") == {16: 1},
          "no se reutilizan IDs por coincidencia numerica (H2O es 16 en la original y 17 en la LLE)")
    try:
        unifac.asignacion(CAS["metanol"], "lle")
        check(False, "metanol no tiene grupo CH3OH en la tabla LLE")
    except unifac.FaltaDatoUNIFAC as x:
        check(x.detalle["tipo"] == "asignacion_ausente" and x.detalle["nombre"] == "CH3OH",
              "metanol: asignacion ausente (CH3OH no existe en la tabla LLE), sin aproximarlo por CH3 + OH")
    m = unifac.LiquidoUNIFAC(S6, "lle")
    rng = np.random.default_rng(4)
    peor = 0.0
    for T in (283.15, 298.15, 313.15):
        x = rng.dirichlet(np.ones(6))
        ref = tu.UNIFAC.from_subgroups(T=T, xs=list(x), chemgroups=[unifac.asignacion(c, "lle") for c in S6],
                                       subgroups=tu.LLEUFSG, interaction_data=tu.LLEUFIP, version=0)
        peor = max(peor, float(np.max(np.abs(m.lngamma(T, x) - np.log(ref.gammas())))))
    check(peor < 1e-12, f"ln gamma (LLE) frente a thermo con LLEUFSG/LLEUFIP, N=6: {peor:.1e}")
    s = mz.Sistema(LE, [CAS["agua"], CAS["butanol"]])
    check(s.T_rango == (283.15, 313.15), f"dominio en T = intervalo de ajuste de la tabla: {s.T_rango}")
    try:
        s.equilibrio_TP(330.0, P, np.array([0.75, 0.25]))
        check(False, "330 K fuera del dominio de la tabla LLE")
    except mz.FueraDeAlcance as x:
        check(x.motivo == "fuera_de_dominio", "T fuera del intervalo de la tabla LLE: rechazada")
    check(s.huella() != mz.Sistema(PAQ, [CAS["agua"], CAS["butanol"]]).huella(), "huella propia, distinta de la original")
    Mw, Mb = 18.015, 74.12
    tabla = []
    for T, w_aq, w_org in ((293.15, 7.8, 20.0), (298.15, 7.4, 20.3), (313.15, 6.6, 21.4)):
        e = s.equilibrio_TP(T, P, np.array([0.75, 0.25]))
        l = sorted(fases(e, "liquido"), key=lambda f: -f.x[0])
        if len(l) != 2:
            check(False, f"LLE agua/butanol {T} K: dos liquidos ({[f.id for f in e.fases]})")
            continue
        b_, x1, x2 = flash_ll([CAS["agua"], CAS["butanol"]], T, np.array([0.75, 0.25]), l[0].x.copy(), l[1].x.copy(),
                              variante="lle")
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8,
              f"LLE agua/butanol {T} K: L-L frente a isoactividad independiente (thermo)")
        wb = lambda f: 100 * f.x[1] * Mb / (f.x[1] * Mb + f.x[0] * Mw)
        tabla.append((T, w_aq, wb(l[0]), w_org, 100 - wb(l[1])))
    for T, a, pa, o, po in tabla:
        print(f"    {T:.2f} K  butanol en fase acuosa {pa:5.2f} (IUPAC {a}) | agua en fase organica {po:5.2f} (IUPAC {o}) g/100 g")
    cas4 = [CAS[k] for k in ("agua", "etanol", "acetato", "butanol")]
    s4 = mz.Sistema(LE, cas4)
    z4 = np.array([0.6, 0.05, 0.2, 0.15])
    e = s4.equilibrio_TP(300.0, P, z4)
    l = sorted(fases(e, "liquido"), key=lambda f: -f.x[0])
    if len(l) == 2:
        b_, x1, x2 = flash_ll(cas4, 300.0, z4, l[0].x.copy(), l[1].x.copy(), variante="lle")
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8,
              "LLE N=4 (agua, etanol, acetato, butanol) a 300 K: L-L frente a isoactividad independiente")
    else:
        check(False, f"LLE N=4: dos liquidos esperados ({[f.id for f in e.fases]})")
    s6 = mz.Sistema(LE, S6)
    e = s6.equilibrio_TP(300.0, P, np.ones(6) / 6)
    l = sorted(fases(e, "liquido"), key=lambda f: f.n)
    check(len(l) == 2 and e.verificaciones["estabilidad"][0] <= mz.TOL_TM and e.verificaciones["equilibrio"][0] <= mz.TOL_MU,
          f"LLE N=6 equimolar a 300 K: fase acuosa incipiente ({l[0].n:.4f} del inventario) separada y certificada")
    if len(l) == 2:
        b_, x1, x2 = flash_ll(S6, 300.0, np.ones(6) / 6, l[0].x.copy(), l[1].x.copy(), variante="lle")
        check(np.max(np.abs(x1 - l[0].x)) < 1e-8 and np.max(np.abs(x2 - l[1].x)) < 1e-8,
              "LLE N=6: composiciones frente a isoactividad independiente")
    d = mdg.trazar(diagrama(("etanol", "agua"), {"tipo": "Pxy", "T": {"valor": 298.15, "unidad": "K"}}, modelo=LE))
    do = mdg.trazar(diagrama(("etanol", "agua"), {"tipo": "Pxy", "T": {"valor": 298.15, "unidad": "K"}}))
    Pd = lambda r, x: min(r["puntos"], key=lambda q: abs(q["xEje"] - x))["P"]
    rel = [Pd(d, x) / Pd(do, x) - 1 for x in (0.1, 0.3, 0.5, 0.7, 0.9)]
    print(f"    Pxy etanol-agua 298.15 K, LLE frente a original: {[round(100 * v, 1) for v in rel]} %")
    check(d["estado"] == "completo" and d["evidencia"]["nivel"] == "cualitativa" and
          not any(q["tipo"] == "azeotropo" for q in d["puntosEspeciales"]),
          "LV medido en el dominio: Pxy etanol-agua a 298.15 K completo, sin azeotropo (la original lo predice)")
    r = mt.evaluar(puntual([CAS["etanol"], CAS["metanol"]], esp_TP(300.0, P, [0.5, 0.5]), modelo=LE))
    check(r["estado"] == "no_soportado" and any(x["codigo"] == "MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE" for x in r["diagnosticos"]),
          "servicio puntual: metanol con la tabla LLE rechazado con MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE")
    # dinamica en el dominio: mezcla adiabatica de agua y 1-butanol a P constante; aparece el segundo liquido
    par = ("agua", "butanol")
    red = (Red("u-lle", par, tf=("200", "s"), muestras=5).paquete("p", LE)
           .volumen("A", "p", {"agua": ("1.0", "mol"), "butanol": ("0.001", "mol")}, ("T", "298.15", "K"),
                    P=("101325", "Pa"), base="molar", adiabatico=True)
           .volumen("B", "p", {"agua": ("0.001", "mol"), "butanol": ("0.5", "mol")}, ("T", "298.15", "K"),
                    P=("101325", "Pa"), base="molar", adiabatico=True)
           .corriente("s", "B", "A", par, ("0.001", "mol/s"), base="molar",
                      extraccion={"B": {"tipo": "mezcla_homogenea"}}))
    t0 = time.perf_counter()
    r = me.resolver(red.solicitud())
    if r["resultados"]:
        H = [a + b for a, b in zip(serie(r, "volumen.A.H"), serie(r, "volumen.B.H"))]
        ev = [(e["codigo"], round(e["tiempo"], 4)) for e in r["resultados"]["eventos"]]
        check(any(c == "aparicion_fase" for c, _ in ev) and max(abs(h - H[0]) for h in H) < 1e-8 * abs(H[0]) and
              r["resultados"]["certificacion"]["estado"] == "cumple" and r["resultados"]["segundaLey"]["estado"] == "cumple",
              f"LLE dinamica: butanol que entra en agua forma el segundo liquido {ev}; H constante, certificada "
              f"({time.perf_counter() - t0:.1f} s)")
    else:
        check(False, f"LLE dinamica: {r['estado']} {[d_['mensaje'][:150] for d_ in r['validacion']['diagnosticos']]}")

print(f"\n{'OK' if not FALLOS else 'FALLOS: ' + str(len(FALLOS))}: {CHECKS[0]} comprobaciones")
sys.exit(1 if FALLOS else 0)
