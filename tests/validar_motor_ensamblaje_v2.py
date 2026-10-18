"""
Validacion del motor de equilibrio multifasico y del ensamblaje v2 (M0-M6,
frontend/CONTRATO_CLAUDE_MOTOR_EQUILIBRIO_MULTIFASICO.md).

Referencias independientes del codigo que se prueba:
  * M1 (mezcla ideal): Raoult con Poynting escrito aqui, K_i = Psat_i exp(vL_i (P - Psat_i)/RT)/P;
    limites puros frente al sistema de un componente; trazas; orden de componentes.
  * M2 (NRTL ChemSep): ln gamma frente a thermo.nrtl (otra implementacion); Gibbs-Duhem;
    h^E = -R T^2 d(g^E/RT)/dT frente a diferencias centradas; azeotropo etanol-agua a 1 atm
    frente a la literatura (78.15 C, x_EtOH ~ 0.894; Gmehling et al., Azeotropic Data);
    tiempos de burbuja y rocio de un calentamiento cerrado frente a flashes estaticos.
  * M3: dos volumenes de agua en contacto (U total constante, S creciente, T final comun),
    corriente interna (materia global), control negativo que corrompe una transferencia interna.
  * M4 (LLE agua/1-butanol): solubilidades mutuas IUPAC-NIST SDS vol. 15 (valores recomendados,
    tambien a temperaturas NO usadas en el ajuste); heteroazeotropo a 1 atm frente a la literatura
    (93.0 C, tabla de azeotropos de Edinburgh; 92.6-93.5 C segun la fuente) +-2 K; la raiz monofasica
    rechazada por estabilidad; meseta LLV en PH y UV; decantador con extraccion por fase.
  * M5 (hielo Ih): Tabla 6 de IAPWS R10-06(2009); curvas de fusion y sublimacion frente a IAPWS
    R14-08(2011) (ecuaciones independientes del cierre); triple; recorridos TP -> PH/UV -> TP.
  * M6: segunda ley con y sin temperatura de frontera; eventos dentro de un paso frente al
    tiempo calculado con flashes estaticos.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_ensamblaje_v2.py [seccion ...]
"""

import asyncio
import copy
import math
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warnings

warnings.filterwarnings("ignore")

import httpx
import numpy as np

from backend import motor_ensamblaje as me
from backend import motor_ensamblaje_v2 as v2
from backend import motor_termodinamica as mt
from backend.main import app
from core import agua_iapws95 as agua
from core import agua_slv as slv
from core import ensamblaje_red as er
from core import hielo_ih
from core import mezclas as mz
from core import mezclas_datos as md
from solicitudes_v2 import CAS, POL, Red

FALLOS, CHECKS = [], [0]
R = mz.R


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def seccion(t):
    print(f"\n{t}")


def serie(r, vid):
    return next(s["valores"] for s in r["resultados"]["series"] if s["variableId"] == vid)


def residuos_ok(r):
    return all(x["maximoEscalado"] <= x["tolerancia"] for x in r["resultados"]["residuos"])


def diag_codigos(r):
    v = r.get("validacion", r)
    return {d["codigo"] for d in v["diagnosticos"]}


SECCIONES = sys.argv[1:]


def activa(n):
    return not SECCIONES or n in SECCIONES


# ======================================================================
if activa("0"):
    seccion("0. Capacidades v2 y compatibilidad de la revision 1")
    c2 = v2.capacidades_v2()
    check(c2["revision"] == 2 and c2["revisionesAdmitidas"] == [1, 2], "capacidades v2: revisiones")
    ids_paq = [p["modelo"]["id"] for p in c2["paquetes"]]
    check({"agua-iapws95", "mezcla-ideal", "nrtl-chemsep", "nrtl-lle-agua-butanol"} <= set(ids_paq),
          f"capacidades v2: paquetes {ids_paq}")
    # ampliacion N (docs/MOTOR_TERMODINAMICA_N_COMPONENTES.md): 7 componentes declarados por volumen; los tamanos
    # contrastados por paquete estan en `tamanos`
    check(c2["volumenesMaximos"] == 3 and c2["componentesMaximos"] == 7 == c2["tamanos"]["componentesMaximosPorVolumen"],
          "capacidades v2: limites verificados")
    check("agua-iapws95-hielo-ih" not in ids_paq, "el hielo no se declara en la dinamica (sin pruebas dinamicas)")
    c1 = me.capacidades()
    check(c1.get("revision", 1) == 1, "capacidades v1 por omision siguen siendo la revision 1")

    async def http():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://v") as cl:
            a = (await cl.get("/motor/ensamblajes/capacidades")).json()
            b = (await cl.get("/motor/ensamblajes/capacidades", params={"revision": 2})).json()
            d = (await cl.get("/motor/termodinamica/diagrama")).json()
            t = (await cl.get("/motor/termodinamica/capacidades")).json()
            return a, b, d, t
    a, b, d, t = asyncio.run(http())
    check(a == c1, "HTTP capacidades sin parametro = revision 1 intacta")
    check(b["revision"] == 2, "HTTP capacidades?revision=2")
    check(d["estado"] == "evaluado" and len(d["diagrama"]["lineas"]) == 3, "HTTP diagrama P-T del hielo")
    check([m["id"] for m in t["modelos"]] == ["agua-iapws95", "mezcla-ideal", "nrtl-chemsep",
                                               "nrtl-lle-agua-butanol", "unifac-original-public",
                                               "unifac-dortmund-public", "unifac-original-lle-public",
                                               "agua-iapws95-hielo-ih"],
          "catalogo termodinamico: el agua sigue primero; las ampliaciones son aditivas")
    lle = next(m for m in t["modelos"] if m["id"] == "nrtl-lle-agua-butanol")
    check(lle["componentesCAS"] == [CAS["agua"], CAS["butanol"]] and lle["dominio"]["T"] == [293.0, 373.0],
          "paquete LLE: solo agua/1-butanol y solo el intervalo con datos")

# ======================================================================
if activa("1"):
    seccion("1. M1 mezcla ideal: Raoult+Poynting, limites, trazas, orden, extensividad")
    s = mz.Sistema("mezcla-ideal", [CAS["benceno"], CAS["tolueno"]])
    P = 101325.0
    peor = 0.0
    for T in (360.0, 365.0, 370.0, 375.0):
        e = s.equilibrio_TP(T, P, np.array([0.5, 0.5]))
        if len(e.fases) == 2:
            fv = next(f for f in e.fases if f.tipo == "vapor")
            fl = next(f for f in e.fases if f.tipo == "liquido")
            for i, esp in enumerate(s.esp):
                K = esp.Psat(T) * math.exp(esp.vL * (P - esp.Psat(T)) / (R * T)) / P
                peor = max(peor, abs(fv.x[i] / fl.x[i] / K - 1))
    check(peor < 1e-9, f"K_i = Psat exp(vL (P-Psat)/RT)/P (Raoult con Poynting): {peor:.2e}")
    # estabilidad: el liquido ideal nunca se separa
    tm_min = min(min(q[2] for q in s.prueba_estabilidad(330.0, 5e5, s.mu("liquido", 330.0, 5e5, np.array([x, 1 - x]), [0, 1]),
                                                         [0, 1], incluir_vapor=False)) for x in (0.1, 0.3, 0.5, 0.7, 0.9))
    check(tm_min >= -1e-12, f"liquido ideal sin separacion liquido-liquido (min tm {tm_min:.2e})")
    # limite puro y trazas
    T = 350.0
    e1 = mz.Sistema("mezcla-ideal", [CAS["benceno"]]).equilibrio_TP(T, P, np.array([1.0]))
    e2 = s.equilibrio_TP(T, P, np.array([1.0, 0.0]))
    check(abs(e1.H - e2.H) <= 1e-9 * abs(e1.H) and abs(e1.V - e2.V) <= 1e-12 * e1.V and abs(e1.S - e2.S) < 1e-9,
          "especie ausente (n = 0) = sistema puro")
    e3 = s.equilibrio_TP(T, P, np.array([1.0, 1e-10]))
    check(abs(e3.H - e1.H) < 1e-5 and e3.fases[0].x[1] > 0, "traza 1e-10: continua con el puro y la especie presente")
    # orden de componentes
    sr = mz.Sistema("mezcla-ideal", [CAS["tolueno"], CAS["benceno"]])
    for T in (360.0, 372.0):
        a, b = s.equilibrio_TP(T, P, np.array([0.3, 0.7])), sr.equilibrio_TP(T, P, np.array([0.7, 0.3]))
        check(abs(a.H - b.H) <= 1e-8 * abs(a.H) and abs(a.S - b.S) <= 1e-8 * abs(a.S) and len(a.fases) == len(b.fases),
              f"cambio de orden de componentes a {T} K")
    # extensividad
    a, b = s.equilibrio_TP(365.0, P, np.array([0.4, 0.6])), s.equilibrio_TP(365.0, P, 7 * np.array([0.4, 0.6]))
    check(abs(b.H - 7 * a.H) <= 1e-9 * abs(b.H) and abs(b.V - 7 * a.V) <= 1e-9 * b.V and abs(b.S - 7 * a.S) <= 1e-9 * abs(b.S),
          "extensividad: H, V, S escalan con n")
    # identidades y recorrido TP -> PH -> UV
    e = s.equilibrio_TP(372.0, P, np.array([0.4, 0.6]))
    check(len(e.fases) == 2, "372 K: liquido + vapor")
    for f in e.fases:
        check(abs(f.g - (f.h - e.T * f.s)) <= 1e-9 * R * e.T, f"g = h - T s en {f.id}")
    ph = s.equilibrio_PH(P, e.H, np.array([0.4, 0.6]))
    uv = s.equilibrio_UV(e.U, e.V, np.array([0.4, 0.6]))
    check(abs(ph.T - e.T) < 1e-7 and abs(uv.T - e.T) < 1e-6 and abs(uv.P / P - 1) < 1e-7,
          f"TP -> PH -> UV: dT {ph.T - e.T:.2e}, {uv.T - e.T:.2e}, dP/P {uv.P / P - 1:.2e}")
    # cambio consistente de referencia: las diferencias de H entre estados no dependen del cero
    e_a, e_b = s.equilibrio_TP(340.0, P, np.array([0.4, 0.6])), s.equilibrio_TP(380.0, P, np.array([0.4, 0.6]))
    dH = e_b.H - e_a.H
    # integral independiente: liquido ideal 340 -> burbuja; aqui basta el orden de magnitud firmado y la
    # identidad dH = int T dS a P cte por cuadratura sobre estados de equilibrio
    Ts = np.linspace(340.0, 380.0, 801)
    Ss = [s.equilibrio_TP(T, P, np.array([0.4, 0.6])).S for T in Ts]
    dH_TdS = float(np.sum(0.5 * (Ts[1:] + Ts[:-1]) * np.diff(Ss)))
    check(abs(dH_TdS / dH - 1) < 2e-4, f"dH = int T dS a P constante: {dH:.6g} frente a {dH_TdS:.6g} J")

    # API estatica
    sol = {"revision": 1, "solicitudId": "m1", "propietarioId": "p",
           "componentes": [{"id": 1, "nombre": "benceno", "simbolo": "B", "identidadQuimica": {"cas": CAS["benceno"]}},
                           {"id": 2, "nombre": "tolueno", "simbolo": "T", "identidadQuimica": {"cas": CAS["tolueno"]}}],
           "declaracion": {"modelo": {"id": "mezcla-ideal", "version": "1"}, "politica": dict(POL),
                           "especificacion": {"tipo": "TP", "T": {"valor": 365, "unidad": "K"},
                                              "P": {"valor": 101325, "unidad": "Pa"},
                                              "composicion": {"base": "molar", "fracciones": {"1": 0.4, "2": 0.6}}}}}
    r = mt.evaluar(sol)
    check(r["estado"] == "evaluado" and all(v["estado"] != "no_cumple" for v in r["evaluacion"]["verificaciones"]),
          "API estatica: mezcla ideal TP evaluada con verificaciones")
    sol2 = copy.deepcopy(sol)
    sol2["componentes"][1]["identidadQuimica"]["cas"] = "50-00-0"
    r = mt.evaluar(sol2)
    check(r["estado"] == "no_soportado" and any(d["codigo"] == "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO" for d in r["diagnosticos"]),
          "API estatica: componente sin datos -> no_soportado")
    sol3 = copy.deepcopy(sol)
    sol3["declaracion"]["modelo"]["id"] = "nrtl-chemsep"
    sol3["componentes"][1]["identidadQuimica"]["cas"] = CAS["acetato"]
    sol3["componentes"][0]["identidadQuimica"]["cas"] = CAS["butanol"]
    r = mt.evaluar(sol3)
    check(r["estado"] in ("no_soportado", "evaluado"), f"API estatica: par NRTL (con o sin parametros) -> {r['estado']}")

# ======================================================================
if activa("2"):
    seccion("2. M2 NRTL etanol-agua: thermo, Gibbs-Duhem, h^E, azeotropo, recorridos")
    s = mz.Sistema("nrtl-chemsep", [CAS["etanol"], CAS["agua"]])
    try:
        from thermo.nrtl import NRTL
        peor = 0.0
        for T in (300.0, 340.0, 360.0):
            for x1 in (0.05, 0.3, 0.7, 0.95):
                x = [x1, 1 - x1]
                tau = (s.liq.a + s.liq.b / T).tolist()
                G = np.exp(-s.liq.alpha * (s.liq.a + s.liq.b / T))
                ref = NRTL(T=T, xs=x, tau_coeffs=None, alpha_coeffs=None, ABEFGHCD=(s.liq.a.tolist(), s.liq.b.tolist(),
                           [[0, 0], [0, 0]], [[0, 0], [0, 0]], [[0, 0], [0, 0]], [[0, 0], [0, 0]],
                           s.liq.alpha.tolist(), [[0, 0], [0, 0]]))
                peor = max(peor, float(np.max(np.abs(np.log(ref.gammas()) - s.liq.lngamma(T, np.array(x))))))
        check(peor < 1e-12, f"ln gamma frente a thermo.nrtl: {peor:.2e}")
    except ImportError:
        check(False, "thermo no disponible para el contraste NRTL")
    # Gibbs-Duhem: sum x_i d ln gamma_i / dx1 = 0
    peor = 0.0
    for x1 in (0.1, 0.4, 0.8):
        d = 1e-6
        gp, gm = s.liq.lngamma(350.0, np.array([x1 + d, 1 - x1 - d])), s.liq.lngamma(350.0, np.array([x1 - d, 1 - x1 + d]))
        peor = max(peor, abs(x1 * (gp[0] - gm[0]) / (2 * d) + (1 - x1) * (gp[1] - gm[1]) / (2 * d)))
    check(peor < 1e-7, f"Gibbs-Duhem: {peor:.2e}")
    # h^E = -R T^2 d(g^E/RT)/dT (complex step del codigo frente a diferencia centrada aqui)
    x = np.array([0.3, 0.7])
    T = 340.0
    d = 1e-3
    hE_fd = -R * T ** 2 * (s.liq.gE_RT(T + d, x) - s.liq.gE_RT(T - d, x)) / (2 * d)
    hE = R * T * float(np.real(s.liq.gE_RT(T, x))) - T * mz.dgE_dT(s.liq, T, x)     # g^E - T d(g^E)/dT
    check(abs(hE - hE_fd) < 1e-5 * max(abs(hE), 1.0), f"h^E: {hE:.6g} frente a {hE_fd:.6g} J/mol")
    # h del liquido de mezcla = sum x h_puro + h^E
    f = s.fase("l", "liquido", T, 101325.0, x, [0, 1])
    hp = [s.fase("l", "liquido", T, 101325.0, np.array([1.0]), [i]).h for i in (0, 1)]
    check(abs(f.h - (x @ np.array(hp) + hE)) < 1e-6 * abs(f.h), "h_mezcla = sum x h_puro + h^E")
    # azeotropo a 1 atm: burbuja con x = y
    P = 101325.0

    # azeotropo: volatilidad relativa 1 en la burbuja, con las funciones del paquete (gamma, Psat, Poynting)
    from scipy.optimize import brentq

    def K(T, x1):
        x = np.array([x1, 1 - x1])
        lg = s.liq.lngamma(T, x)
        return [math.exp(lg[i]) * esp.Psat(T) * math.exp(esp.vL * (P - esp.Psat(T)) / (R * T)) / P
                for i, esp in enumerate(s.esp)]

    def T_burbuja(x1):
        return brentq(lambda T: x1 * K(T, x1)[0] + (1 - x1) * K(T, x1)[1] - 1, 330.0, 380.0, xtol=1e-12)

    def alfa_menos_1(x1):
        T = T_burbuja(x1)
        k = K(T, x1)
        return k[0] / k[1] - 1
    xaz = brentq(alfa_menos_1, 0.6, 0.99, xtol=1e-12)
    Taz = T_burbuja(xaz)
    check(abs(Taz - 351.30) < 0.6 and abs(xaz - 0.894) < 0.04,
          f"azeotropo etanol-agua 1 atm: {Taz - 273.15:.2f} C, x {xaz:.3f} (lit. 78.15 C, 0.894)")
    # el flash completo lo confirma a ambos lados: por debajo de Taz liquido, por encima vapor
    e_lo, e_hi = s.equilibrio_TP(Taz - 0.05, P, np.array([xaz, 1 - xaz])), s.equilibrio_TP(Taz + 0.05, P, np.array([xaz, 1 - xaz]))
    check([f.tipo for f in e_lo.fases] == ["liquido"] and [f.tipo for f in e_hi.fases] == ["vapor"],
          "composicion azeotropica: liquido a Taz - 0.05 K y vapor a Taz + 0.05 K (sin region bifasica)")
    # recorridos
    n = np.array([0.4, 0.6])
    for T in (340.0, 355.0, 362.0, 375.0):
        e = s.equilibrio_TP(T, P, n)
        a = s.equilibrio_PH(P, e.H, n)
        b = s.equilibrio_UP(P, e.U, n)
        check(abs(a.T - T) < 1e-7 and abs(b.T - T) < 1e-7 and len(a.fases) == len(e.fases),
              f"TP -> PH/UP -> TP a {T} K ({len(e.fases)} fases)")
        if [f.tipo for f in e.fases] == ["liquido"]:
            try:
                s.equilibrio_UV(e.U, e.V, n)
                check(False, "UV de un liquido incompresible debia rechazarse")
            except mz.FueraDeAlcance as x:
                check(x.motivo == "no_soportado", f"UV solo liquido a {T} K: P indeterminada, no_soportado")
            continue
        c = s.equilibrio_UV(e.U, e.V, n)
        check(abs(c.T - T) < 1e-6 and abs(c.P / P - 1) < 1e-7 and len(c.fases) == len(e.fases),
              f"TP -> UV -> TP a {T} K: dT {c.T - T:.1e}, dP/P {c.P / P - 1:.1e}")

# ======================================================================
if activa("3"):
    seccion("3. M2/M6 calentamiento cerrado etanol-agua v2: eventos frente a flashes estaticos")
    s = mz.Sistema("nrtl-chemsep", [CAS["etanol"], CAS["agua"]])
    red = (Red("eq", ("etanol", "agua"), tf=("600", "s"), muestras=7)
           .paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {"etanol": ("0.4", "mol"), "agua": ("0.6", "mol")}, ("T", "330", "K"), P=("101325", "Pa"),
                    base="molar")
           .calor("q", None, "A", Q=("100", "W"), Tfrontera=("600", "K")))
    t0 = time.perf_counter()
    r = me.resolver(red.solicitud())
    dt = time.perf_counter() - t0
    check(r["estado"] in ("resuelto", "parcial"), f"calentamiento etanol-agua: {r['estado']} ({dt:.1f} s)")
    if r["resultados"]:
        n = np.array([0.4, 0.6])
        P = 101325.0
        H0 = s.equilibrio_TP(330.0, P, n).H
        # burbuja y rocio estaticos: T donde aparece / desaparece el vapor
        def frontera(aparece):
            lo, hi = 340.0, 380.0
            for _ in range(60):
                m = 0.5 * (lo + hi)
                e = s.equilibrio_TP(m, P, n)
                hay = any(f.tipo == "vapor" for f in e.fases)
                liq = any(f.tipo == "liquido" for f in e.fases)
                if (hay if aparece else not liq):
                    hi = m
                else:
                    lo = m
            return s.equilibrio_TP(hi, P, n).H
        tb = (frontera(True) - H0) / 100.0
        tr_ = (frontera(False) - H0) / 100.0
        ev = r["resultados"]["eventos"]
        tiempos = sorted(e["tiempo"] for e in ev)
        check(len(tiempos) >= 2, f"eventos de burbuja y rocio: {tiempos}")
        if len(tiempos) >= 2:
            check(abs(tiempos[0] - tb) < 1e-5 * tb and abs(tiempos[1] - tr_) < 1e-5 * tr_,
                  f"t burbuja {tiempos[0]:.6f} vs {tb:.6f}; t rocio {tiempos[1]:.6f} vs {tr_:.6f} s")
        check(residuos_ok(r), "residuos globales dentro de tolerancia")
        H = serie(r, "volumen.A.H")
        ts = r["resultados"]["tiempos"]
        check(max(abs(H[k] - (H0 + 100.0 * ts[k])) for k in range(len(ts))) < 1e-6 * abs(H0) + 1e-6,
              "H = H0 + Q t (solucion exacta a P constante)")
        sl = r["resultados"]["segundaLey"]
        check(sl["estado"] == "cumple", f"segunda ley con T de frontera 600 K: {sl['estado']} {sl['generacionMinima']}")
        Tf = serie(r, "volumen.A.T")
        check(max(Tf) < 600.0, "el fluido no supera la T de frontera")
        # control negativo: frontera a 400 K, el vapor sobrecalentado la supera y sigue recibiendo calor
        red4 = copy.deepcopy(red)
        red4.s["datos"]["calor.q.Tf"]["declaracion"]["texto"] = "400"
        r4 = me.resolver(red4.solicitud())
        T4 = serie(r4, "volumen.A.T")
        check(max(T4) > 400.0 and r4["resultados"]["segundaLey"]["estado"] == "no_cumple",
              f"segunda ley detecta calor de 400 K entrando a un fluido a {max(T4):.1f} K")
        # pocas muestras: los eventos caen dentro de pasos; mismo tiempo
        red2 = copy.deepcopy(red)
        red2.s["estudio"]["muestras"] = 2
        r2 = me.resolver(red2.solicitud())
        t2 = sorted(e["tiempo"] for e in r2["resultados"]["eventos"]) if r2["resultados"] else []
        check(len(t2) >= 2 and abs(t2[0] - tb) < 1e-5 * tb and abs(t2[1] - tr_) < 1e-5 * tr_,
              f"eventos dentro de un paso (2 muestras): {t2}")
        # sin temperatura de frontera -> segunda ley no evaluable
        red3 = (Red("eq3", ("etanol", "agua"), tf=("50", "s"), muestras=3)
                .paquete("p", "nrtl-chemsep")
                .volumen("A", "p", {"etanol": ("0.4", "mol"), "agua": ("0.6", "mol")}, ("T", "330", "K"),
                         P=("101325", "Pa"), base="molar")
                .calor("q", None, "A", Q=("100", "W")))
        r3 = me.resolver(red3.solicitud())
        check(r3["resultados"] and r3["resultados"]["segundaLey"]["estado"] == "no_evaluable",
              "sin T de frontera: segunda ley no evaluable (no se sustituye por la T del fluido)")

# ======================================================================
if activa("4"):
    seccion("4. M3 volumenes acoplados: contacto, corriente interna, control negativo")
    red = (Red("c2", ("agua",), tf=("2000", "s"), muestras=6)
           .paquete("w", "agua-iapws95")
           .volumen("A", "w", {"agua": ("10", "kg")}, ("T", "350", "K"), V=("0.0105", "m3"))
           .volumen("B", "w", {"agua": ("5", "kg")}, ("T", "300", "K"), V=("0.0052", "m3"))
           .calor("c", "A", "B", G=("200", "W/K")))
    r = me.resolver(red.solicitud())
    check(r["estado"] == "resuelto", f"contacto termico: {r['estado']}")
    if r["resultados"]:
        UA, UB = serie(r, "volumen.A.U"), serie(r, "volumen.B.U")
        TA, TB = serie(r, "volumen.A.T"), serie(r, "volumen.B.T")
        S = [a + b for a, b in zip(serie(r, "volumen.A.S"), serie(r, "volumen.B.S"))]
        check(max(abs(UA[k] + UB[k] - UA[0] - UB[0]) for k in range(len(UA))) < 1e-6 * abs(UA[0] + UB[0]) + 1e-3,
              "U_A + U_B constante (contacto aislado)")
        check(all(S[k + 1] >= S[k] - 1e-9 for k in range(len(S) - 1)), "S total no decreciente")
        check(abs(TA[0] - 350) < 1e-6 and abs(TB[0] - 300) < 1e-6 and abs(TA[-1] - TB[-1]) < 0.05,
              f"T se igualan: {TA[-1]:.4f} / {TB[-1]:.4f}")
        check(r["resultados"]["segundaLey"]["estado"] == "cumple", "segunda ley del contacto cerrado")
        check(residuos_ok(r), "residuos globales (contacto)")
    # corriente interna A -> B
    red = (Red("c3", ("agua",), tf=("100", "s"), muestras=6)
           .paquete("w", "agua-iapws95")
           .volumen("A", "w", {"agua": ("10", "kg")}, ("T", "330", "K"), V=("0.0102", "m3"), adiabatico=True)
           .volumen("B", "w", {"agua": ("5", "kg")}, ("T", "330", "K"), V=("0.02", "m3"), adiabatico=True)
           .corriente("s", "A", "B", ("agua",), ("0.01", "kg/s"), extraccion={"A": {"tipo": "mezcla_homogenea"}}))
    sol = red.solicitud()
    r = me.resolver(sol)
    check(r["estado"] == "resuelto" and residuos_ok(r), f"corriente interna: {r['estado']}")
    if r["resultados"]:
        mA, mB = serie(r, "volumen.A.masa"), serie(r, "volumen.B.masa")
        ts = r["resultados"]["tiempos"]
        check(max(abs(mA[k] - (10 - 0.01 * ts[k])) for k in range(len(ts))) < 1e-9 and
              max(abs(mB[k] - (5 + 0.01 * ts[k])) for k in range(len(ts))) < 1e-9, "m_A = m0 - F t, m_B = m0 + F t")
    # control negativo: la transferencia que recibe B se corrompe 1e-6 relativo
    orig_call = er.Sistema.__call__

    def rhs_corrupto(self, t, y):
        d = orig_call(self, t, y)
        d = np.array(d, dtype=float)
        o = self.offs[1]
        d[o] += 1e-5 * 0.01 / agua.M      # B recibe un 1e-5 de mas: la red ya no conserva materia
        return d
    er.Sistema.__call__ = rhs_corrupto
    try:
        rc = me.resolver(copy.deepcopy(sol))
    finally:
        er.Sistema.__call__ = orig_call
    rm = next((x for x in (rc["resultados"] or {}).get("residuos", []) if x["ecuacionId"] == "global.materia.1"), None)
    check(rm is not None and rm["maximoEscalado"] > rm["tolerancia"],
          f"control negativo: transferencia interna corrupta detectada ({rm and rm['maximoEscalado']:.3g})")
    # rechazos de topologia y paquetes
    mal = red.solicitud()
    mal["corrientes"][0]["hasta"] = "X"
    rv = me.validar(mal)[0]
    check(any(d["codigo"] == "MOTOR_ENS_TOPOLOGIA" and d["estado"] == "invalido" for d in rv["diagnosticos"]),
          "corriente a un volumen inexistente: MOTOR_ENS_TOPOLOGIA")
    mal = red.solicitud()
    mal["paquetes"][0]["modelo"]["version"] = "9"
    rv = me.validar(mal)[0]
    check(any("PAQUETE" in c or "MODELO" in c or "CATALOGO" in c for c in diag_codigos(rv)), "paquete no publicado: rechazado")
    # binario acoplado: etanol-agua de A a B con contacto
    red = (Red("c4", ("etanol", "agua"), tf=("200", "s"), muestras=5)
           .paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {"etanol": ("0.3", "mol"), "agua": ("0.7", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                    base="molar")
           .volumen("B", "p", {"etanol": ("0.1", "mol"), "agua": ("0.9", "mol")}, ("T", "300", "K"), P=("101325", "Pa"),
                    base="molar")
           .corriente("s", "A", "B", ("etanol", "agua"), ("0.001", "mol/s"), base="molar",
                      extraccion={"A": {"tipo": "mezcla_homogenea"}})
           .calor("c", "A", "B", G=("0.5", "W/K")))
    t0 = time.perf_counter()
    r = me.resolver(red.solicitud())
    check(r["estado"] == "resuelto" and residuos_ok(r), f"binario acoplado: {r['estado']} ({time.perf_counter() - t0:.1f} s)")
    if r["resultados"]:
        nA = [serie(r, f"volumen.A.n.{c}") for c in (1, 2)]
        nB = [serie(r, f"volumen.B.n.{c}") for c in (1, 2)]
        check(max(abs(nA[i][k] + nB[i][k] - nA[i][0] - nB[i][0]) for i in (0, 1) for k in range(len(nA[0]))) < 1e-10,
              "binario: n_A,i + n_B,i constante por especie")
        xA = nA[0][-1] / (nA[0][-1] + nA[1][-1])
        check(abs(xA - 0.3) < 1e-9, f"el donante conserva su composicion al extraer mezcla homogenea: {xA:.12f}")
        check(r["resultados"]["segundaLey"]["estado"] == "cumple", "segunda ley del binario acoplado")

# ======================================================================
if activa("5"):
    seccion("5. M4 LLE agua/1-butanol: IUPAC SDS-15, heteroazeotropo, estabilidad, mesetas, decantador")
    from ajuste_nrtl_lle_agua_butanol import DATOS, AJUSTE, VALIDACION, w_agua_de_x
    s = mz.Sistema("nrtl-lle-agua-butanol", [CAS["agua"], CAS["butanol"]])
    P = 3e5        # sin vapor en todo el intervalo de datos
    peor = {"ajuste": 0.0, "validacion": 0.0}
    for T, (w_bu_aq, w_ag_org) in DATOS.items():
        e = s.equilibrio_TP(float(T), P, np.array([0.75, 0.25]))
        liqs = [f for f in e.fases if f.tipo == "liquido"]
        if len(liqs) != 2:
            check(False, f"LL a {T} K: {[f.tipo for f in e.fases]}")
            continue
        aq, org = sorted(liqs, key=lambda f: -f.x[0])
        d = max(abs(100 * (1 - w_agua_de_x(aq.x[0])) - w_bu_aq), abs(100 * w_agua_de_x(org.x[0]) - w_ag_org))
        clave = "ajuste" if T in AJUSTE else "validacion"
        peor[clave] = max(peor[clave], d)
        check(e.verificaciones["estabilidad"][0] <= mz.TOL_TM and e.verificaciones["equilibrio"][0] <= mz.TOL_MU,
              f"LL certificado a {T} K")
    check(peor["ajuste"] < 0.7 and peor["validacion"] < 0.7,
          f"solubilidad mutua frente a IUPAC (g/100 g): ajuste {peor['ajuste']:.2f}, validacion {peor['validacion']:.2f}")
    # la raiz monofasica (liquido homogeneo) es inestable
    x = np.array([0.75, 0.25])
    pr = s.prueba_estabilidad(320.0, P, s.mu("liquido", 320.0, P, x, [0, 1]), [0, 1], incluir_vapor=True)
    check(min(q[2] for q in pr) < -1e-3, "liquido homogeneo z = (0.75, 0.25) a 320 K rechazado por tm < 0")
    # orden de componentes
    sr = mz.Sistema("nrtl-lle-agua-butanol", [CAS["butanol"], CAS["agua"]])
    a, b = s.equilibrio_TP(330.0, P, np.array([0.75, 0.25])), sr.equilibrio_TP(330.0, P, np.array([0.25, 0.75]))
    check(abs(a.G - b.G) < 1e-9 * abs(a.G) and sorted(f.x[0] for f in a.fases) == sorted(f.x[1] for f in b.fases)
          or abs(sorted(f.x[0] for f in a.fases)[0] - sorted(f.x[1] for f in b.fases)[0]) < 1e-9,
          "LL: cambio de orden de componentes")
    # heteroazeotropo a 1 atm
    P = 101325.0
    lo, hi = 360.0, 372.0
    n = np.array([0.75, 0.25])
    for _ in range(45):
        m = 0.5 * (lo + hi)
        if any(f.tipo == "vapor" for f in s.equilibrio_TP(m, P, n).fases):
            hi = m
        else:
            lo = m
    check(abs(lo - 366.15) < 2.0, f"heteroazeotropo agua/1-butanol 1 atm: {lo - 273.15:.2f} C (lit. 93.0 C, +-2 K)")
    eL, eV = s.equilibrio_TP(lo, P, n), s.equilibrio_TP(hi * (1 + 1e-6), P, n)
    for fr in (0.25, 0.75):
        H = eL.H + fr * (eV.H - eL.H)
        e = s.equilibrio_PH(P, H, n)
        check(len(e.fases) == 3 and abs(e.H - H) < 1e-9 * abs(H) + 1e-6 and e.verificaciones["equilibrio"][0] < 1e-10
              and e.verificaciones["estabilidad"][0] <= mz.TOL_TM, f"meseta LLV por PH ({fr}): {[f.id for f in e.fases]}")
        u = s.equilibrio_UV(e.U, e.V, n)
        check(len(u.fases) == 3 and abs(u.T - e.T) < 1e-7 and abs(u.U - e.U) < 1e-8 * abs(e.U) + 1e-6,
              f"LLV por UV ({fr}): dT {u.T - e.T:.2e}")
    # API estatica: LL con IDs por densidad y masas reconstruidas
    sol = {"revision": 1, "solicitudId": "m4", "propietarioId": "p",
           "componentes": [{"id": 1, "nombre": "agua", "simbolo": "W", "identidadQuimica": {"cas": CAS["agua"]}},
                           {"id": 2, "nombre": "butanol", "simbolo": "B", "identidadQuimica": {"cas": CAS["butanol"]}}],
           "declaracion": {"modelo": {"id": "nrtl-lle-agua-butanol", "version": "1"}, "politica": dict(POL),
                           "especificacion": {"tipo": "TP", "T": {"valor": 25, "unidad": "degC"},
                                              "P": {"valor": 1, "unidad": "bar"},
                                              "composicion": {"base": "molar", "fracciones": {"1": 0.75, "2": 0.25}}}}}
    r = mt.evaluar(sol)
    check(r["estado"] == "evaluado" and [f["id"] for f in r["evaluacion"]["fases"]] == ["liquido-1", "liquido-2"],
          f"API estatica LL: {r['estado']} {[f['id'] for f in (r['evaluacion'] or {}).get('fases', [])]}")
    sol["componentes"][1]["identidadQuimica"]["cas"] = CAS["etanol"]
    r = mt.evaluar(sol)
    check(r["estado"] == "no_soportado", "paquete LLE con un componente sin parametros: no_soportado")
    # decantador: volumen LL con extraccion de la fase organica (menor densidad)
    def decantador(criterio):
        extr = {"tipo": "fase", "fase": "liquido"}
        if criterio:
            extr["criterio"] = criterio
        red = (Red("dec", ("agua", "butanol"), tf=("100", "s"), muestras=5)
               .paquete("p", "nrtl-lle-agua-butanol")
               .volumen("D", "p", {"agua": ("0.75", "mol"), "butanol": ("0.25", "mol")}, ("T", "300", "K"),
                        P=("101325", "Pa"), base="molar", adiabatico=True)
               .corriente("o", "D", None, ("agua", "butanol"), ("0.001", "mol/s"), base="molar",
                          extraccion={"D": extr}))
        return me.resolver(red.solicitud())
    t0 = time.perf_counter()
    r = decantador("menor_densidad")
    check(r["estado"] in ("resuelto", "parcial") and r["resultados"] is not None,
          f"decantador con criterio: {r['estado']} ({time.perf_counter() - t0:.1f} s)")
    if r["resultados"]:
        check(residuos_ok(r), "decantador: residuos")
        est = r["resultados"]["estados"]["D"]
        ids = [[f["id"] for f in m["evaluacion"]["fases"]] for m in est]
        comp = [{f["id"]: f["composicionMolar"]["1"] for f in m["evaluacion"]["fases"]} for m in est]
        check(all(set(i) == {"liquido-1", "liquido-2"} for i in ids), f"IDs de fase continuos: {ids}")
        cont = all(abs(comp[k][fid] - comp[k + 1][fid]) < 0.02 for k in range(len(comp) - 1) for fid in comp[k]
                   if fid in comp[k + 1])
        check(cont, "cada ID sigue a la misma fase (composicion continua)")
        nW, nB = serie(r, "volumen.D.n.1"), serie(r, "volumen.D.n.2")
        xs_ext = (nW[0] - nW[-1]) / ((nW[0] - nW[-1]) + (nB[0] - nB[-1]))
        org = min(comp[0].items(), key=lambda kv: kv[1])[1]
        check(abs(xs_ext - org) < 0.01, f"se extrae la fase organica: x_agua extraida {xs_ext:.4f} ~ {org:.4f}")
    r = decantador(None)
    check(r["estado"] in ("invalido", "parcial", "no_convergente") or
          any("EXTRACCION" in c or "AMBIGUA" in c.upper() for c in diag_codigos(r)),
          f"decantador sin criterio con dos liquidos: no se elige una fase ({r['estado']})")

# ======================================================================
if activa("6"):
    seccion("6. M5 hielo Ih: R10-06, R14-08, triple, estados, API")
    peor, _ = hielo_ih.verificar()
    check(peor < 1e-9, f"Tabla 6 de R10-06: {peor:.2e}")
    th = lambda T: T / 273.16
    pm = lambda T: 611.657 * (1 + 1.19539337e6 * (1 - th(T) ** 3) + 8.08183159e4 * (1 - th(T) ** 25.75)
                              + 3.33826860e3 * (1 - th(T) ** 103.75))
    ps = lambda T: 611.657 * math.exp((-21.2144006 * th(T) ** 0.00333333333 + 27.3203819 * th(T) ** 1.20666667
                                       - 6.10598130 * th(T) ** 1.70333333) / th(T))
    check(abs(pm(260.0) / 1e6 - 138.268) < 1e-3 and abs(ps(230.0) / 8.94735e-6 / 1e6 - 1) < 1e-5,
          "ecuaciones R14-08 transcritas: Tabla 3")
    d_sub = max(abs(slv.P_sublimacion(T) / ps(T) - 1) for T in (200.0, 220.0, 240.0, 260.0, 273.0))
    d_fus = max(abs(pm(slv.T_fusion(P)) / P - 1) for P in (1e4, 1e6, 1e7, 5e7, 1e8))
    check(d_sub < 1e-3 and d_fus < 0.02, f"curvas del cierre frente a R14-08: sublimacion {d_sub:.1e}, fusion {d_fus:.1e}")
    Ttr, Ptr = slv.triple()
    check(abs(Ttr - 273.16) < 1e-6 and abs(Ptr / 611.657 - 1) < 1e-5, f"triple del cierre {Ttr:.9g} K, {Ptr:.9g} Pa")
    check(abs(slv.T_fusion(101325.0) - 273.152519) < 2e-6, "fusion normal: 273.152519 K (R10-06, Tabla 6)")
    for T, P, tipo in ((260.0, 1e5, "solido"), (250.0, 10.0, "vapor"), (290.0, 1e5, "liquido"), (230.0, 5e7, "solido")):
        e = slv.evaluar_TP(T, P)
        check(e.fases[0][0].tipo == tipo and e.residuos["estabilidad"][0] <= slv.TOL_G, f"TP {T} K {P} Pa: {tipo}")
        u = slv.evaluar_UV(e.u, e.v)
        check(abs(u.T - T) < 1e-8 and abs(u.P / P - 1) < 1e-8, f"UV -> TP {tipo}: dT {u.T - T:.1e}")
    for args in ((Ttr, Ptr), (250.0, slv.P_sublimacion(250.0))):
        try:
            slv.evaluar_TP(*args)
            check(False, f"TP en coexistencia {args} debia ser indeterminado")
        except slv.FueraDeAlcance as x:
            check(x.motivo == "saturacion", "TP sobre una curva o el triple: indeterminado")
    P = 101325.0
    Tm = slv.T_fusion(P)
    hs, hl = slv.fase("solido", Tm, P).h, slv.fase("liquido", Tm, P).h
    check(abs((hl - hs) / 1e3 - 333.4) < 0.5, f"calor de fusion a 1 atm {(hl - hs) / 1e3:.2f} kJ/kg (~333.4)")
    e = slv.evaluar_PH(P, hs + 0.3 * (hl - hs))
    check([f.tipo for f, _ in e.fases] == ["solido", "liquido"] and abs(e.fases[1][1] - 0.3) < 1e-12, "meseta SL por PH")
    u = slv.evaluar_UV(e.u, e.v)
    check(abs(u.fases[1][1] - 0.3) < 1e-9 and abs(u.T - Tm) < 1e-9, "SL por UV")
    fs = [slv.fase(t, Ttr, Ptr) for t in slv.FASES]
    u3 = sum(w * f.u for w, f in zip((0.3, 0.3, 0.4), fs))
    v3 = sum(w * f.v for w, f in zip((0.3, 0.3, 0.4), fs))
    e = slv.evaluar_UV(u3, v3)
    check(len(e.fases) == 3 and max(abs(b - w) for (_, b), w in zip(e.fases, (0.3, 0.3, 0.4))) < 1e-9,
          "triple por UV: fracciones 0.3/0.3/0.4 recuperadas")
    try:
        slv.evaluar_PH(Ptr, sum(w * f.h for w, f in zip((0.3, 0.3, 0.4), fs)))
        check(False, "PH en el triple debia ser indeterminado")
    except slv.FueraDeAlcance as x:
        check(x.motivo == "saturacion", "PH en el triple: tres fases y dos ecuaciones, indeterminado")
    # liquido sobreenfriado metastable: UV con su u, v no lo publica si hay un estado de mayor S
    q = slv.fase("liquido", 268.0, 1e5)
    e = slv.evaluar_UV(q.u, q.v)
    check(e.s > q.s and any(f.tipo == "solido" for f, _ in e.fases),
          f"liquido sobreenfriado (268 K) con su U, V: se publica el estado de mayor S ({[f.tipo for f, _ in e.fases]})")
    # API
    base = {"revision": 1, "solicitudId": "m5", "propietarioId": "p",
            "componentes": [{"id": 1, "nombre": "agua", "simbolo": "A", "identidadQuimica": {"cas": CAS["agua"]}}],
            "declaracion": {"modelo": {"id": "agua-iapws95-hielo-ih", "version": "1"}, "politica": dict(POL)}}
    sol = copy.deepcopy(base)
    sol["declaracion"]["especificacion"] = {"tipo": "TP", "T": {"valor": -10, "unidad": "degC"},
                                            "P": {"valor": 1, "unidad": "bar"},
                                            "composicion": {"base": "molar", "fracciones": {"1": 1}}}
    r = mt.evaluar(sol)
    check(r["estado"] == "evaluado" and r["evaluacion"]["fases"][0]["tipo"] == "solido", "API: hielo a -10 C")
    sol["declaracion"]["especificacion"]["T"] = {"valor": Ttr, "unidad": "K"}
    sol["declaracion"]["especificacion"]["P"] = {"valor": Ptr, "unidad": "Pa"}
    r = mt.evaluar(sol)
    check(r["estado"] == "incompleto" and r["diagnosticos"][0]["alternativas"] == [["U", "V", "cantidades"]],
          "API: TP en el triple pide U y V")
    sol = copy.deepcopy(base)
    sol["declaracion"]["especificacion"] = {"tipo": "UV", "U": {"valor": u3, "unidad": "J"}, "V": {"valor": v3, "unidad": "m3"},
                                            "cantidades": {"base": "masica", "valores": {"1": {"valor": 1, "unidad": "kg"}}}}
    r = mt.evaluar(sol)
    check(r["estado"] == "evaluado" and [f["tipo"] for f in r["evaluacion"]["fases"]] == ["solido", "liquido", "vapor"],
          "API: UV en el triple, tres fases")
    sol["componentes"].append({"id": 2, "nombre": "etanol", "simbolo": "E", "identidadQuimica": {"cas": CAS["etanol"]}})
    r = mt.evaluar(sol)
    check(r["estado"] == "no_soportado", "API: el hielo no se extiende a mezclas")

# ======================================================================
print(f"\n{'OK' if not FALLOS else 'FALLOS: ' + str(len(FALLOS))}: {CHECKS[0]} comprobaciones")
sys.exit(1 if FALLOS else 0)
