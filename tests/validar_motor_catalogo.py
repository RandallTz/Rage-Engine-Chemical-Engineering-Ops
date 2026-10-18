"""
Catalogo y regla unica de admision (F2.1-F2.3 de frontend/ROADMAP_MOTOR_MULTIFISICO.md).

Comprueba:
  0. registro unico e inmutable; la vista de core/mezclas_datos y las huellas de paquete NO cambian;
  1. la misma regla de admision en el Sistema, en las capacidades de las tres rutas y en el catalogo publicado;
     F9-R3 (especie pura sin grupos con la tabla UNIFAC ELL) y especies no registradas, por ruta;
  2. extensibilidad: registrar una especie (SIMULADO en este proceso) la admite donde hay datos, sin codigo nuevo,
     y un dato puro ausente se diagnostica por propiedad;
  3. contenido publicado: unidades, fuentes, coeficientes que reproducen las propiedades usadas, huellas; contraste
     independiente de Psat (agua frente a IAPWS-95; temperaturas normales de ebullicion de la literatura);
  4. concurrencia en frio e HTTP.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_catalogo.py [seccion ...]
"""

import asyncio
import copy
import json
import math
import subprocess
import sys
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

from backend import motor_catalogo as mc
from backend import motor_diagramas as mdg
from backend import motor_ensamblaje as me
from backend import motor_ensamblaje_v2 as v2
from backend import motor_mezclas as mm
from backend import motor_termodinamica as mt
from core import catalogo
from core import mezclas as mz
from core import mezclas_datos as md
from solicitudes_v2 import CAS, POL, Red

FALLOS, CHECKS = [], [0]
N_SUST = 8                  # 7 de la base + acetona (F2.6)
HEXANO = "110-54-3"
SECCIONES = sys.argv[1:]
EJ = RAIZ / "docs" / "ejemplos"


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def seccion(t):
    print(f"\n{t}")


def activa(n):
    return not SECCIONES or n in SECCIONES


def comp(cas_lista):
    return [{"id": k + 1, "nombre": f"c{k}", "simbolo": f"c{k}", "identidadQuimica": {"cas": c}}
            for k, c in enumerate(cas_lista)]


def puntual(cas_lista, modelo, T=300.0):
    return {"revision": 1, "solicitudId": "c", "propietarioId": "p", "componentes": comp(cas_lista),
            "declaracion": {"modelo": {"id": modelo, "version": "1"}, "politica": dict(POL),
                            "especificacion": {"tipo": "TP", "T": {"valor": T, "unidad": "K"},
                                               "P": {"valor": 101325, "unidad": "Pa"},
                                               "composicion": {"base": "molar", "fracciones": {
                                                   str(k + 1): 1 / len(cas_lista) for k in range(len(cas_lista))}}}}}


def codigos(r):
    return [d["codigo"] for d in r.get("diagnosticos") or (r.get("validacion") or {}).get("diagnosticos", [])]


# ======================================================================
if activa("0"):
    seccion("0. Registro unico e inmutable; nada publicado cambia")
    try:
        catalogo.REGISTRO["x"] = None
        check(False, "el registro debia ser de solo lectura")
    except TypeError:
        check(True, "REGISTRO es de solo lectura (MappingProxyType)")
    r = catalogo.REGISTRO[CAS["agua"]]
    try:
        r.M = 1.0
        check(False, "los registros debian ser inmutables")
    except Exception:
        check(True, "RegistroSustancia inmutable (dataclass congelada)")
    check(list(catalogo.REGISTRO) == md.especies_disponibles() and len(set(catalogo.REGISTRO)) == N_SUST,
          f"mezclas_datos lee el mismo registro, en el mismo orden ({N_SUST} sustancias)")
    # huellas publicadas en ejemplos anteriores siguen identicas (la refactorizacion no cambia datos)
    pares = [("motor-unifac/motor-diagramas-txy-etanol-agua-unifac-respuesta.json", "unifac-original-public",
              [CAS["etanol"], CAS["agua"]]),
             ("motor-diagramas/motor-diagramas-txy-etanol-agua-nrtl-respuesta.json", "nrtl-chemsep",
              [CAS["etanol"], CAS["agua"]]),
             ("motor-diagramas/motor-diagramas-txy-benceno-tolueno-ideal-respuesta.json", "mezcla-ideal",
              [CAS["benceno"], CAS["tolueno"]])]
    for f, paq, cas in pares:
        h = json.loads((EJ / f).read_text(encoding="utf-8"))["identidad"]["huellaModelo"]
        check(mz.Sistema(paq, cas).huella() == h, f"huella de {paq} igual a la publicada en {f.split('/')[0]}")
    caps = json.loads((EJ / "motor-unifac" / "motor-termodinamica-capacidades.json").read_text(encoding="utf-8"))
    nuevas = mt.capacidades()
    sin_ace = copy.deepcopy(nuevas["modelos"])
    for m in sin_ace:
        if CAS["acetona"] in m["componentesCAS"]:
            m["componentesCAS"].remove(CAS["acetona"])
    check(caps["modelos"] == sin_ace and all(CAS["acetona"] in m["componentesCAS"] for m in nuevas["modelos"]
                                             if m["id"] != "nrtl-lle-agua-butanol" and not m["id"].startswith("agua")),
          "capacidades puntuales = las de F1 + la acetona (F2.6), sin otro cambio (dominios incluidos)")

# ======================================================================
if activa("1"):
    seccion("1. Una sola regla de admision: Sistema, rutas y catalogo; F9-R3")
    cat = mc.catalogo_publico()
    est = {m["id"]: m for m in mt.capacidades()["modelos"]}
    ens = {p["modelo"]["id"]: p for p in v2.capacidades_v2()["paquetes"]}
    dia = {p["modelo"]["id"]: p for p in mdg.capacidades()["paquetes"]}
    for p in cat["paquetes"]:
        mid = p["modelo"]["id"]
        adm = sorted(e["cas"] for e in p["especies"] if e["admitida"])
        ok = adm == sorted(est[mid]["componentesCAS"])
        if mid in ens:
            ok = ok and adm == sorted(ens[mid]["componentesCAS"])
        if mid in dia:
            ok = ok and adm == sorted(dia[mid]["componentesCAS"])
        check(ok, f"{mid}: especies admitidas = componentesCAS de estado, ensamblaje y diagramas ({len(adm)})")
        if mid in mz.PAQUETES:
            for e in p["especies"]:
                try:
                    mz.Sistema(mid, [e["cas"]])
                    construye = True
                except mz.FaltaParametro as x:
                    construye = False
                    codigo = x.codigo
                check(construye == e["admitida"] and (construye or codigo == e["faltantes"][0]["codigo"]),
                      f"{mid} / {e['cas']} puro: el Sistema aplica la misma regla que el catalogo")
    # F9-R3: metanol puro con la tabla ELL, en estado puntual y en ensamblaje
    r = mt.evaluar(puntual([CAS["metanol"]], "unifac-original-lle-public"))
    check(r["estado"] == "no_soportado" and "MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE" in codigos(r) and not r.get("evaluacion"),
          "F9-R3 cerrado: metanol puro con UNIFAC ELL rechazado como en mezcla (MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE)")
    red = (Red("c-met", ("metanol",), tf=("10", "s"), muestras=3).paquete("p", "unifac-original-lle-public")
           .volumen("A", "p", {"metanol": ("1", "mol")}, ("T", "300", "K"), P=("101325", "Pa"), base="molar",
                    adiabatico=True))
    r = me.resolver(red.solicitud())
    check(not r.get("resultados") and "MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE" in codigos(r),
          "ensamblaje: volumen de metanol puro con UNIFAC ELL rechazado con el mismo codigo")
    r = mt.evaluar(puntual([CAS["etanol"]], "nrtl-lle-agua-butanol"))
    check(r["estado"] == "no_soportado" and "MOTOR_ESTADO_PARAMETRO_AUSENTE" in codigos(r),
          "etanol puro con el paquete NRTL-LLE agua/butanol: rechazado (misma regla que en mezcla)")
    r = mt.evaluar(puntual([CAS["metanol"]], "unifac-original-public"))
    check(r["estado"] == "evaluado", "metanol puro con UNIFAC original (tiene grupos): evaluado")
    # sustancia no registrada (n-hexano tiene grupos DDBST: tener grupos no basta)
    ace = HEXANO
    r = mt.evaluar(puntual([CAS["agua"], ace], "unifac-original-public"))
    check(r["estado"] == "no_soportado" and "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO" in codigos(r),
          "n-hexano (con grupos, sin registro): estado puntual lo rechaza por componente no soportado")
    d = mdg.trazar({"revision": 1, "solicitudId": "c", "componentes": comp([CAS["agua"], ace]),
                    "modelo": {"id": "unifac-original-public", "version": "1"}, "componenteEjeId": 1,
                    "corte": {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}, "intervaloComposicion": [0, 1],
                    "resolucion": "exploratoria"})
    check(d["estado"] == "no_soportado" and any("COMPONENTE_NO_SOPORTADO" in c for c in codigos(d)),
          f"n-hexano en diagramas: rechazado ({codigos(d)[:2]})")
    p = next(p for p in cat["paquetes"] if p["modelo"]["id"] == "unifac-original-lle-public")
    met = next(e for e in p["especies"] if e["cas"] == CAS["metanol"])
    check(not met["admitida"] and met["faltantes"][0]["dato"] == "asignacion_grupos_lle" and
          met["faltantes"][0]["codigo"] == "UNIFAC_ASIGNACION_AUSENTE",
          "catalogo: metanol no admitido en ELL, con dato y codigo del faltante")
    p = next(p for p in cat["paquetes"] if p["modelo"]["id"] == "agua-iapws95")
    check([e["cas"] for e in p["especies"] if e["admitida"]] == [CAS["agua"]] and
          p["requisitos"]["porEspecie"] == ["formulacion_iapws95"],
          "IAPWS-95: solo agua y sin exigir los datos de una correlacion de liquido incompresible")
    p = next(p for p in cat["paquetes"] if p["modelo"]["id"] == "nrtl-chemsep")
    check(p["requisitos"]["porPar"] == ["nrtl_bij_alphaij"] and all(e["admitida"] for e in p["especies"]),
          "NRTL: requisito por par declarado; las especies se admiten y los pares se diagnostican al evaluar")

# ======================================================================
if activa("2"):
    seccion("2. Extensibilidad (SIMULADO en este proceso) y dato puro ausente")
    ace = "67-63-0"                     # 2-propanol: NO registrado; se registra solo en este proceso
    from thermo import VolumeLiquid
    vl = VolumeLiquid(CASRN=ace)
    vl.method = "DIPPR_PERRY_8E"
    reg = catalogo.RegistroSustancia(ace, "2-propanol", 60.09502e-3, "thermo (IUPAC)", "WagnerPoling",
                                     float(vl.T_dependent_property(298.15)), "DIPPR_PERRY_8E")
    viejo_reg, viejo_esp = catalogo.REGISTRO, md._ESPECIES

    def limpiar():
        md.especie.cache_clear()
        md._faltantes_puros.cache_clear()
        mc._catalogo.cache_clear()
        v2._cobertura_unifac.cache_clear()

    try:
        catalogo.REGISTRO = catalogo.MappingProxyType({**viejo_reg, ace: reg})
        md._ESPECIES = {**viejo_esp, ace: (reg.nombre, reg.psat_tabla, reg.vL, reg.metodo_vL, reg.M)}
        limpiar()
        check(not catalogo.faltantes("ideal", ace) and not catalogo.faltantes("unifac_original", ace),
              "2-propanol registrado (simulado): datos puros completos y grupos DDBST; admitido en ideal y UNIFAC")
        check(catalogo.faltantes("nrtl_lle", ace) and catalogo.faltantes("iapws95", ace),
              "y no admitida en NRTL-LLE agua/butanol ni en IAPWS-95")
        s = mz.Sistema("unifac-original-public", [CAS["agua"], ace])
        e = s.equilibrio_TP(340.0, 101325.0, np.array([0.5, 0.5]))
        check(e.verificaciones["estabilidad"][0] <= mz.TOL_TM and e.verificaciones["equilibrio"][0] <= mz.TOL_MU,
              f"agua-2-propanol con UNIFAC original: TP certificado sin codigo nuevo ({[f.id for f in e.fases]})")
        try:
            mz.Sistema("nrtl-chemsep", [CAS["benceno"], ace])
            nrtl = "construido"
        except mz.FaltaParametro as x:
            nrtl = x.codigo
        print(f"    benceno-2-propanol con NRTL ChemSep: {nrtl}")
        check(nrtl in ("construido", "PARAMETRO_AUSENTE"), "NRTL: el par se resuelve por sus datos, no por el registro")
        cat = mc.catalogo_publico()
        su = next(x for x in cat["sustancias"] if x["cas"] == ace)
        check(su["datosPuros"]["estado"] == "completos" and su["datosPuros"]["huella"].startswith("sha256:"),
              "el catalogo publica la nueva sustancia con datos y huella")
        # dato puro ausente: una sustancia registrada sin polinomio de cp en la tabla
        falsa = "99999-99-2"           # CAS con digito de control valido e inexistente en las tablas
        catalogo.REGISTRO = catalogo.MappingProxyType({**viejo_reg, falsa: catalogo.RegistroSustancia(
            falsa, "sin datos", 0.1, "prueba", "WagnerPoling", 1e-4, "prueba")})
        md._ESPECIES = {**viejo_esp, falsa: ("sin datos", "WagnerPoling", 1e-4, "prueba", 0.1)}
        limpiar()
        f = catalogo.faltantes("ideal", falsa)
        check({x["dato"] for x in f} == {"presion_vapor", "cp_gas_ideal"} and all(x["codigo"] == "DATO_PURO_AUSENTE" for x in f),
              "registrada sin tablas: DATO_PURO_AUSENTE por propiedad (presion_vapor, cp_gas_ideal)")
        try:
            mz.Sistema("mezcla-ideal", [CAS["agua"], falsa])
            check(False, "debia rechazarse")
        except mz.FaltaParametro as x:
            check(x.codigo == "DATO_PURO_AUSENTE" and x.detalle["cas"] == falsa,
                  "el Sistema la rechaza con DATO_PURO_AUSENTE, identificando especie y dato")
        r = mt.evaluar(puntual([CAS["agua"], falsa], "mezcla-ideal"))
        check(r["estado"] == "no_soportado" and "MOTOR_ESTADO_DATO_PURO_AUSENTE" in codigos(r),
              "servicio puntual: MOTOR_ESTADO_DATO_PURO_AUSENTE")
    finally:
        catalogo.REGISTRO, md._ESPECIES = viejo_reg, viejo_esp
        limpiar()
    check(md.especies_disponibles() == list(viejo_reg) and len(mc.catalogo_publico()["sustancias"]) == N_SUST,
          f"registro restaurado: {N_SUST} sustancias")

# ======================================================================
if activa("3"):
    seccion("3. Contenido publicado y contraste independiente de Psat")
    cat = mc.catalogo_publico()
    for su in cat["sustancias"]:
        e = md.especie(su["cas"])
        pr = {p["id"]: p for p in su["datosPuros"]["propiedades"]}
        ps, cp = pr["presion_vapor"], pr["cp_gas_ideal"]
        T = 0.5 * (su["datosPuros"]["dominioLiquido"]["T"][0] + su["datosPuros"]["dominioLiquido"]["T"][1])
        c = ps["coeficientes"]
        tau = 1 - T / c["Tc"]
        if "Poling" in ps["forma"]:
            ln = (c["A"] * tau + c["B"] * tau ** 1.5 + c["C"] * tau ** 2.5 + c["D"] * tau ** 5) / (1 - tau)
        else:
            ln = (c["A"] * tau + c["B"] * tau ** 1.5 + c["C"] * tau ** 3 + c["D"] * tau ** 6) / (1 - tau)
        cpT = mz.R * sum(cp["coeficientes"][f"a{k}"] * T ** k for k in range(5))
        check(abs(c["Pc"] * math.exp(ln) / e.Psat(T) - 1) < 1e-12 and abs(cpT / e.cp_ig(T) - 1) < 1e-12 and
              pr["volumen_liquido"]["valor"] == e.vL and su["masaMolar"]["valor"] == e.M and
              su["datosPuros"]["huella"] == mc.huella_datos_puros(su["cas"]),
              f"{su['nombre']}: los coeficientes publicados reproducen Psat y cp usados; v_L, M y huella")
    # agua: Wagner-McGarry frente a IAPWS-95 (formulacion independiente)
    from core import agua_iapws95 as ag
    e = md.especie(CAS["agua"])
    peor = max(abs(e.Psat(T) / ag.coexistencia(T).P - 1) for T in np.linspace(280.0, 0.9 * e.Tc, 12))
    check(peor < 2e-3, f"Psat del agua (Wagner-McGarry) frente a IAPWS-95, 280 K-0.9 Tc: {100 * peor:.3f} %")
    # temperatura normal de ebullicion frente a la literatura (NIST Chemistry WebBook, valores redondeados)
    Tb_lit = {"agua": 373.12, "etanol": 351.39, "benceno": 353.24, "tolueno": 383.75, "butanol": 390.88,
              "acetato": 350.26, "metanol": 337.85}
    from scipy.optimize import brentq
    filas = []
    for k, Tb in Tb_lit.items():
        e = md.especie(CAS[k])
        T = brentq(lambda t: e.Psat(t) - 101325.0, 250.0, 0.89 * e.Tc)
        filas.append((k, T, Tb))
    for k, T, Tb in filas:
        print(f"    {k:8s} Tb {T:.2f} K (literatura {Tb})")
    check(all(abs(T - Tb) < 0.5 for _, T, Tb in filas), "Tb de las 7 especies a menos de 0.5 K de la literatura")

# ======================================================================
if activa("4"):
    seccion("4. Concurrencia en frio e HTTP")
    codigo = r"""
import sys, json, concurrent.futures as cf
sys.path.insert(0, ".")
from backend import motor_catalogo as mc
with cf.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(lambda _: json.dumps(mc.catalogo_publico(), sort_keys=True), range(8)))
print(len(set(res)))
"""
    p = subprocess.run([sys.executable, "-c", codigo], cwd=str(RAIZ), capture_output=True, text=True, timeout=600)
    check(p.returncode == 0 and p.stdout.strip().splitlines()[-1] == "1",
          f"8 hilos en frio construyen el mismo catalogo ({p.stderr[-300:] if p.returncode else 'ok'})")
    import httpx
    from backend.main import app

    async def http():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://c") as c:
            return (await c.get("/motor/catalogo")).json()
    h = asyncio.run(http())
    check(h == mc.catalogo_publico(), "GET /motor/catalogo = catalogo_publico()")
    a = mc.catalogo_publico()
    a["sustancias"].clear()
    check(len(mc.catalogo_publico()["sustancias"]) == N_SUST, "la respuesta es una copia: mutarla no altera el catalogo")

if activa("5"):
    seccion("5. F2.6: acetona incorporada por registro y contrastada")
    from scipy.optimize import brentq
    ace = CAS["acetona"]
    cat = mc.catalogo_publico()
    adm = sorted(p["modelo"]["id"] for p in cat["paquetes"] if any(e["cas"] == ace and e["admitida"] for e in p["especies"]))
    check(adm == sorted(["mezcla-ideal", "nrtl-chemsep", "unifac-original-public", "unifac-dortmund-public",
                         "unifac-original-lle-public"]),
          f"acetona admitida en ideal, NRTL, UNIFAC original/Dortmund/ELL (CH3 + CH3CO), no en IAPWS ni NRTL-LLE: {adm}")
    # Tb y entalpia de vaporizacion en Tb (CRC Handbook) para las 8 especies
    lit = {"agua": (373.12, 40.65), "etanol": (351.39, 38.56), "benceno": (353.24, 30.72), "tolueno": (383.75, 33.18),
           "butanol": (390.88, 43.29), "acetato": (350.26, 31.94), "metanol": (337.85, 35.21), "acetona": (329.22, 29.10)}
    filas = []
    for k, (Tb, dh) in lit.items():
        e = md.especie(CAS[k])
        T = brentq(lambda t: e.Psat(t) - 101325.0, 200.0, 0.89 * e.Tc)
        filas.append((k, T, Tb, (e.h_ig(T) - e.h_L(T, e.Psat(T))) / 1000, dh))
    for k, T, Tb, dH, dh in filas:
        print(f"    {k:8s} Tb {T:7.2f} K ({Tb})   dHvap {dH:6.2f} kJ/mol ({dh}, {100 * (dH / dh - 1):+.1f} %)")
    check(abs(filas[-1][1] - 329.22) < 0.5, "acetona: Tb a menos de 0.5 K de la literatura")
    check(all(0.0 < dH / dh - 1 < 0.07 for *_, dH, dh in filas),
          "dHvap en Tb: +1.6 a +5.8 % sobre la literatura en las 8 especies (vapor ideal en Clapeyron, Z = 1: "
          "sesgo sistematico declarado del paquete)")
    # azeotropo acetona-metanol a 1 atm (literatura: 55.5 C, x_acetona ~ 0.80; Horsley, Azeotropic Data)
    for paq in ("unifac-original-public", "unifac-dortmund-public", "nrtl-chemsep"):
        d = mdg.trazar({"revision": 1, "solicitudId": "c", "componentes": comp([ace, CAS["metanol"]]),
                        "modelo": {"id": paq, "version": "1"}, "componenteEjeId": 1,
                        "corte": {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}, "intervaloComposicion": [0, 1],
                        "resolucion": "exploratoria"})
        az = [q for q in d["puntosEspeciales"] if q["tipo"] == "azeotropo"]
        check(len(az) == 1 and abs(az[0]["T"] - 328.65) < 1.0 and abs(az[0]["xEje"] - 0.80) < 0.05,
              f"{paq}: azeotropo acetona-metanol {az[0]['T'] - 273.15 if az else None:.2f} C, x {az[0]['xEje'] if az else 0:.3f} "
              "(literatura 55.5 C, 0.80)")
    # dinamica con la especie nueva, sin codigo nuevo
    red = (Red("c-ace", ("acetona", "agua"), tf=("200", "s"), muestras=5).paquete("p", "unifac-original-public")
           .volumen("A", "p", {"acetona": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                    base="molar")
           .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K")))
    r = me.resolver(red.solicitud())
    check(bool(r.get("resultados")) and r["resultados"]["certificacion"]["estado"] == "cumple" and
          any(e["codigo"] == "aparicion_fase" for e in r["resultados"]["eventos"]),
          f"acetona-agua UNIFAC: calentamiento con burbuja, certificado ({r['estado']})")

if activa("6"):
    seccion("6. F2.5: referencias entre paquetes y conservacion")
    cap = v2.capacidades_v2()
    check(cap["corrientes"].get("entrePaquetes") == "misma_referencia", "capacidad publicada: entrePaquetes = misma_referencia")
    par = ("etanol", "agua")
    red = (Red("c-25", par, tf=("200", "s"), muestras=5).paquete("pn", "nrtl-chemsep").paquete("pu", "unifac-original-public")
           .volumen("A", "pn", {"etanol": ("0.7", "mol"), "agua": ("0.3", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                    base="molar")
           .volumen("B", "pu", {"etanol": ("0.2", "mol"), "agua": ("0.8", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                    base="molar")
           .corriente("s", "A", "B", par, ("0.002", "mol/s"), base="molar", extraccion={"A": {"tipo": "mezcla_homogenea"}})
           .calor("c", "A", "B", G=("0.5", "W/K")))
    r = me.resolver(red.solicitud())
    res = r.get("resultados") or {}
    ok = bool(res)
    if ok:
        nA = [next(x["valores"] for x in res["series"] if x["variableId"] == f"volumen.A.n.{k}") for k in (1, 2)]
        nB = [next(x["valores"] for x in res["series"] if x["variableId"] == f"volumen.B.n.{k}") for k in (1, 2)]
        ok = max(abs(nA[i][k] + nB[i][k] - nA[i][0] - nB[i][0]) for i in range(2) for k in range(len(nA[0]))) < 1e-12
    check(ok and res["certificacion"]["estado"] == "cumple" and res["segundaLey"]["estado"] == "cumple" and
          sorted(p["modelo"]["id"] for p in res["procedenciaModelo"]) == ["nrtl-chemsep", "unifac-original-public"],
          "corriente NRTL -> UNIFAC (misma referencia): materia por especie, energia y segunda ley certificadas")
    # agua IAPWS-95 frente a mezcla: la diferencia de h del agua entre modelos no es constante
    from core import agua_iapws95 as ag
    s1 = mz.Sistema("mezcla-ideal", [CAS["agua"]])
    M = md.especie(CAS["agua"]).M
    dif = [s1.equilibrio_TP(T, P_, np.array([1.0])).H - ag.evaluar_TP(T, P_).propiedades.h * M
           for T, P_ in ((280, 1e5), (300, 1e5), (350, 1e5), (370, 1e5), (380, 1e5), (450, 1e5), (450, 3e5), (500, 1e5))]
    print(f"    h_mezcla - h_IAPWS del agua: {min(dif):.0f} a {max(dif):.0f} J/mol")
    check(max(dif) - min(dif) > 100, f"no hay conversion constante IAPWS <-> mezcla (varia {max(dif) - min(dif):.0f} J/mol)")
    red = (Red("c-25b", ("agua",), tf=("50", "s"), muestras=3).paquete("pa", "agua-iapws95").paquete("pm", "mezcla-ideal")
           .volumen("A", "pa", {"agua": ("1", "mol")}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
           .volumen("B", "pm", {"agua": ("1", "mol")}, ("T", "320", "K"), P=("101325", "Pa"), base="molar")
           .corriente("s", "A", "B", ("agua",), ("0.001", "mol/s"), base="molar", extraccion={"A": {"tipo": "mezcla_homogenea"}}))
    r = me.resolver(red.solicitud())
    check(not r.get("resultados") and "MOTOR_ENS_REFERENCIAS_INCOMPATIBLES" in codigos(r),
          "corriente IAPWS-95 -> mezcla: rechazada (MOTOR_ENS_REFERENCIAS_INCOMPATIBLES)")
    red = (Red("c-25c", ("agua",), tf=("50", "s"), muestras=3).paquete("pa", "agua-iapws95").paquete("pm", "mezcla-ideal")
           .volumen("A", "pa", {"agua": ("1", "mol")}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
           .volumen("B", "pm", {"agua": ("1", "mol")}, ("T", "320", "K"), P=("101325", "Pa"), base="molar")
           .calor("c", "A", "B", G=("0.5", "W/K")))
    r = me.resolver(red.solicitud())
    res = r.get("resultados") or {}
    check(bool(res) and res["certificacion"]["estado"] == "cumple" and res["segundaLey"]["estado"] == "cumple",
          f"contacto termico IAPWS-95 / mezcla (el calor no depende de la referencia): certificado ({r['estado']})")

if activa("7"):
    seccion("7. F2.4: sustitucion de datos puros con coherencia del potencial")
    from core import catalogo as cg
    et, ag_ = CAS["etanol"], CAS["agua"]
    base = mz.Sistema("nrtl-chemsep", [et, ag_])
    e_et = md.especie(et)
    sust = cg.leer_sustituciones({et: {"volumen_liquido": {"valor": 60.0, "unidad": "cm3/mol", "fuente": "prueba F2.4"}}},
                                 "d", [et, ag_])
    sv = mz.Sistema("nrtl-chemsep", [et, ag_], sust)
    check(md.especie(et) is e_et and md.especie(et).vL == e_et.vL, "sustituir no altera el registro ni la cache global")
    check(sv.huella() != base.huella() and mz.Sistema("nrtl-chemsep", [et, ag_]).huella() == base.huella(),
          "la sustitucion cambia la huella; sin sustitucion la huella es la de siempre")
    s2 = mz.Sistema("nrtl-chemsep", [et, ag_], cg.leer_sustituciones(
        {et: {"volumen_liquido": {"valor": 60.0, "unidad": "cm3/mol", "fuente": "otra fuente"}}}, "d", [et, ag_]))
    check(s2.huella() != sv.huella(), "mismo valor con otra fuente: otra huella (la procedencia es parte del dato)")
    x = np.array([0.4, 0.6])
    T, P_ = 320.0, 2e5
    f0, f1 = base.fase("l", "liquido", T, P_, x, [0, 1]), sv.fase("l", "liquido", T, P_, x, [0, 1])
    check(abs((f1.v - f0.v) - 0.4 * (60e-6 - e_et.vL)) < 1e-15, "v de la fase liquida cambia exactamente x_i (v_L' - v_L)")
    dP = 1.0
    dgdP = (sv.fase("l", "liquido", T, P_ + dP, x, [0, 1]).g - sv.fase("l", "liquido", T, P_ - dP, x, [0, 1]).g) / (2 * dP)
    check(abs(dgdP - f1.v) < 1e-9 * abs(f1.v) + 1e-12 and abs(f1.g - (f1.h - T * f1.s)) < 1e-9 * abs(f1.h),
          "potencial coherente con v_L sustituido: dg/dP = v y g = h - T s")
    # cp del gas ideal: h del vapor coherente (dh/dT = cp sustituido)
    a = tuple(1.1 * c for c in e_et.cp)
    sc = mz.Sistema("nrtl-chemsep", [et, ag_], cg.leer_sustituciones(
        {et: {"cp_gas_ideal": {"coeficientes": {f"a{k}": a[k] for k in range(5)}, "dominio": {"T": [200, 1000]},
                               "fuente": "prueba: cp x 1.1"}}}, "d", [et, ag_]))
    y = np.array([1.0])
    dh = (sc.fase("v", "vapor", 400.001, 1e5, y, [0]).h - sc.fase("v", "vapor", 399.999, 1e5, y, [0]).h) / 0.002
    check(abs(dh / (1.1 * e_et.cp_ig(400.0)) - 1) < 1e-7, "cp del gas ideal sustituido: dh/dT del vapor puro = cp nuevo")
    # Psat: Clapeyron con la Psat sustituida (Tc, Pc iguales; A distinto) y burbuja desplazada
    ps = dict(zip(("A", "B", "C", "D", "Tc", "Pc"), e_et.psat))
    ps["A"] *= 1.02
    sp = mz.Sistema("mezcla-ideal", [et], cg.leer_sustituciones(
        {et: {"presion_vapor": {"forma": e_et.psat_forma, "coeficientes": ps, "dominio": {"T": list(e_et.T_psat)},
                                "fuente": "prueba: A x 1.02"}}}, "d", [et]))
    ee = sp.esp[0]
    Tb_n = brentq(lambda t: ee.Psat(t) - 101325.0, 250.0, 450.0)
    Tb_o = brentq(lambda t: e_et.Psat(t) - 101325.0, 250.0, 450.0)
    clap = Tb_n * (mz.R * Tb_n / ee.Psat(Tb_n) - ee.vL) * ee.Psat(Tb_n) * ee.dlnPsat_dT(Tb_n)
    check(abs((ee.h_ig(Tb_n) - ee.h_L(Tb_n, ee.Psat(Tb_n))) - clap) < 1e-6 * clap and abs(Tb_n - Tb_o) > 0.5,
          f"Psat sustituida: Clapeyron se cumple con la nueva Psat; Tb {Tb_o:.2f} -> {Tb_n:.2f} K")
    e = sp.equilibrio_TP(Tb_n + 0.01, 101325.0, np.array([1.0]))
    check([f.tipo for f in e.fases] == ["vapor"], "y el estado a Tb' + 0.01 K es vapor (la operacion usa la Psat sustituida)")
    # rechazos estructurados
    casos = [({et: {"masa_molar": {"valor": 0.05}}}, "SUSTITUCION_NO_ADMITIDA", "masa molar"),
             ({et: {"entalpia": {"valor": 1.0}}}, "SUSTITUCION_NO_ADMITIDA", "propiedad del estado"),
             ({et: {"volumen_liquido": {"valor": 1e-4, "unidad": "m3/mol"}}}, "SUSTITUCION_INVALIDA", "sin fuente"),
             ({et: {"cp_gas_ideal": {"coeficientes": {"a0": -1, "a1": 0, "a2": 0, "a3": 0, "a4": 0}, "dominio": {"T": [200, 500]},
                                     "fuente": "x"}}}, "SUSTITUCION_INVALIDA", "cp negativo"),
             ({et: {"presion_vapor": {"forma": "WagnerPoling", "coeficientes": dict(ps, A=8.0), "dominio": {"T": [200, 500]},
                                      "fuente": "x"}}}, "SUSTITUCION_INVALIDA", "Psat no fisica"),
             ({CAS["benceno"]: {"volumen_liquido": {"valor": 1e-4, "unidad": "m3/mol", "fuente": "x"}}},
              "SUSTITUCION_INVALIDA", "especie que no esta en la peticion")]
    for d, codigo, nombre in casos:
        try:
            cg.leer_sustituciones(d, "d", [et, ag_])
            check(False, f"{nombre}: debia rechazarse")
        except cg.SustitucionRechazada as x:
            check(x.codigo == codigo, f"{nombre}: {x.codigo} en {x.ruta}")
    # las tres rutas
    def pt(sust_, modelo="nrtl-chemsep"):
        c = puntual([et, ag_], modelo, T=355.0)
        if sust_ is not None:
            c["declaracion"]["datosPuros"] = sust_
        return c
    vl = {et: {"volumen_liquido": {"valor": 60.0, "unidad": "cm3/mol", "fuente": "prueba"}}}
    r0, r1 = mt.evaluar(pt(None)), mt.evaluar(pt(vl))
    check(r0["estado"] == r1["estado"] == "evaluado" and r1["evaluacion"]["mezcla"]["v"] != r0["evaluacion"]["mezcla"]["v"],
          "servicio puntual: datosPuros aceptado y el estado cambia")
    r = mt.evaluar(pt({et: {"masa_molar": {"valor": 1}}}))
    check(r["estado"] == "no_soportado" and "MOTOR_ESTADO_SUSTITUCION_NO_ADMITIDA" in codigos(r), "puntual: masa molar rechazada")
    c = puntual([ag_], "agua-iapws95", T=330.0)
    c["declaracion"]["datosPuros"] = {ag_: {"volumen_liquido": {"valor": 18.0, "unidad": "cm3/mol", "fuente": "x"}}}
    r = mt.evaluar(c)
    check(r["estado"] == "no_soportado" and "MOTOR_ESTADO_SUSTITUCION_NO_ADMITIDA" in codigos(r),
          "puntual: IAPWS-95 no admite sustituciones")
    def dg(sust_):
        c = {"revision": 1, "solicitudId": "c", "componentes": comp([et, ag_]), "modelo": {"id": "nrtl-chemsep", "version": "1"},
             "componenteEjeId": 1, "corte": {"tipo": "Pxy", "T": {"valor": 350, "unidad": "K"}}, "intervaloComposicion": [0, 1],
             "resolucion": "exploratoria"}
        if sust_ is not None:
            c["datosPuros"] = sust_
        return mdg.trazar(c)
    psd = {et: {"presion_vapor": {"forma": e_et.psat_forma, "coeficientes": ps, "dominio": {"T": list(e_et.T_psat)},
                                  "fuente": "prueba"}}}
    d0, d1 = dg(None), dg(psd)
    Pe = lambda d: max(p_["P"] for p_ in d["puntos"] if p_["xEje"] == 1.0)
    check(d1["estado"] == "completo" and d1["identidad"]["huellaModelo"] != d0["identidad"]["huellaModelo"] and
          abs(Pe(d1) / sp.esp[0].Psat(350.0) - 1) < 1e-9,
          "diagramas: con Psat sustituida el extremo puro es la nueva Psat y la huella cambia")
    def ens(sust_, modelo="nrtl-chemsep"):
        red = (Red("c-24", ("etanol", "agua"), tf=("100", "s"), muestras=3).paquete("p", modelo)
               .volumen("A", "p", {"etanol": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("T", "330", "K"), P=("101325", "Pa"),
                        base="molar")
               .calor("q", None, "A", Q=("20", "W"), Tfrontera=("700", "K")))
        sol = red.solicitud()
        if sust_ is not None:
            sol["paquetes"][0]["datosPuros"] = sust_
        return me.resolver(sol)
    e0, e1 = ens(None), ens(vl)
    h0 = e0["resultados"]["procedenciaModelo"][0]["huella"]
    h1 = e1["resultados"]["procedenciaModelo"][0]["huella"]
    V0 = next(x["valores"] for x in e0["resultados"]["series"] if x["variableId"] == "volumen.A.V")
    V1 = next(x["valores"] for x in e1["resultados"]["series"] if x["variableId"] == "volumen.A.V")
    check(h1 != h0 and abs((V1[0] - V0[0]) - 0.5 * (60e-6 - e_et.vL)) < 1e-15 and
          e1["resultados"]["certificacion"]["estado"] == "cumple",
          "ensamblaje: paquete con datosPuros; huella propia, V inicial con el v_L sustituido, certificado")
    r = ens({et: {"volumen_liquido": {"valor": 60.0, "unidad": "cm3/mol", "fuente": "x"}}}, "mezcla-ideal")
    check(r["resultados"]["certificacion"]["estado"] == "cumple", "y con otro paquete de mezcla")

print(f"\n{'OK' if not FALLOS else 'FALLOS: ' + str(len(FALLOS))}: {CHECKS[0]} comprobaciones")
sys.exit(1 if FALLOS else 0)
