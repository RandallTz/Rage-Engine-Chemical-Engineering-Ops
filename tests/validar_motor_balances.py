"""
Motor de balances (core/balances): de las ecuaciones fundamentales y los
supuestos de cada volumen a las ecuaciones explícitas, resueltas por el
compilador común. Modelos escritos a mano (sin el cliente ni el Engine
actual), contra soluciones analíticas independientes:

  Materia
    1. Dos volúmenes en serie con caudales constantes: rectas.
    2. Cascada de tres volúmenes con salida 0.1 m: solución de Bateman.
    3. Recirculación cerrada de tres volúmenes con caudal k m: la masa total se
       conserva y el primero sigue 1 + 2 e^(-3kt/2) cos(sqrt(3) k t / 2).
    4. Conversión A -> B por fuentes integradas en un volumen: exponenciales.
    5. Fuente uniforme por volumen (tasa · V, con V dato) y caudal molar (· M).
    6. Caudal total con fracciones.
    7. Agotamiento: se detiene en el instante exacto.
    8. Corriente convectiva cuyos componentes cambian de sentido: se detiene.
  Energía con u(T) declarada (u_lineal)
    9. Recipiente cerrado calentado: T = T0 + Q t / (m c).
   10. Entrada caliente con cantidad constante: T se acerca a T_in con e^(-mdot t / m).
   11. Llenado con entrada caliente (frontera móvil, p impuesta, trabajo p dV/dt):
       T_in - T = (T_in - T0) (m0/m)^(in/(in-out)).
   12. Calentamiento hasta T_max: se detiene donde el supuesto deja de valer,
       t = m c (T_max - T0) / Q.
  Rechazos con motivo, y comprobación estática (ningún equipo ni sustancia).

Ejecutar desde la raíz:  python tests/validar_motor_balances.py
"""

import copy
import json
import math
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core.balances import NoGenerable, generar  # noqa: E402
from core.compilador import NoSoportado, resolver  # noqa: E402
from core.modelo import leer_modelo_comun  # noqa: E402
from core.resultados import leer_resultados  # noqa: E402

n, fallos = [0], []


def check(nombre, cond, detalle=""):
    n[0] += 1
    if not cond:
        fallos.append(nombre)
        print(f"FALLO {nombre} {detalle}")


SIMB = "ABCDEFGH"
MATERIA = {"campo": {"sinReaccion": True, "sinDifusion": False, "sinConveccion": False, "estacionario": False, "difusion": "flujo"},
           "coordenadas": "cartesianas", "vista": "cantidad", "fija": False, "cantidadVolumen": False, "restoImpermeable": True,
           "invariantes": [False, False, False], "generacionUniforme": False, "consumoUniforme": False, "sinAcumulacion": False}
ENERGIA = {"forma": "total", "separarPresion": True, "entalpia": True, "sinCinetica": True, "sinTrabajoViscoso": True,
           "sinFuerzasVolumen": True, "sinFuenteVolumetrica": True, "sinConduccionLocal": False, "adiabatico": False,
           "estacionario": False, "sinAcumulacionTotal": False, "uniforme": True, "monofasico": True, "sinCambioFase": True}


class Modelo:
    def __init__(self, ncomp=1, tf=("10", "s"), muestras=101):
        self.m = {"formato": "rage.modelo", "version": 0, "id": "prueba", "nombre": "prueba",
                  "componentes": [{"id": k + 1, "nombre": SIMB[k], "simbolo": SIMB[k]} for k in range(ncomp)],
                  "termodinamica": {"paquetes": []}, "volumenes": [], "corrientes": [], "intercambios": [], "datos": {},
                  "matematico": None, "estudio": {"tipo": "temporal", "tiempoId": "tf", "metodoSolicitado": "rk45", "muestras": muestras,
                                                   "rtol": 1e-10, "atol": {"cantidad": 1e-12, "energia": 1e-9}},
                  "motores": {}, "procedencia": {"tipo": "nuevo"}}
        self.dato("tf", *tf)

    def dato(self, k, texto, unidad):
        self.m["datos"][k] = {"magnitud": "x", "funcion": "parametro", "declaracion": {"texto": str(texto), "unidad": unidad},
                              "origen": {"propietarioId": "prueba", "ruta": k}}
        return k

    def volumen(self, vid, m0, materia=None, energia=None, terminos=None, V=None, frontera=None, inicial_energia=None, parametros=None):
        comp = [c["id"] for c in self.m["componentes"]]
        v = {"id": vid, "componenteIds": comp, "balances": {"materia": True, "energia": energia is not None, "momento": False},
             "supuestos": {"materia": {**MATERIA, **(materia or {})}, "energia": energia},
             "frontera": frontera or {"tipo": "sin_relacion"},
             "inicial": {"cantidades": {"base": "masica", "datoIds": {str(c): self.dato(f"{vid}.m0.{c}", m0[i], "kg") for i, c in enumerate(comp)}},
                         **({"energia": inicial_energia} if inicial_energia else {})},
             "termodinamica": {"tipo": "supuesto", "supuesto": "u_lineal" if energia is not None else "fase_no_evaluada", "motivo": "prueba",
                               **({"parametros": parametros} if parametros else {})}}
        if terminos:
            v["terminos"] = terminos
        if V:
            v["volumenDatoId"] = self.dato(f"{vid}.V", *V)
        self.m["volumenes"].append(v)

    def corriente(self, sid, desde, hasta, caudales, base="masica", mecanismo=None, exterior=None):
        comp = [c["id"] for c in self.m["componentes"]]
        unidad = "kg/s" if base == "masica" else "mol/s"
        self.m["corrientes"].append({"id": sid, "desde": desde, "hasta": hasta, "componenteIds": comp, "mecanismo": mecanismo,
                                     "materia": {"modo": "por_componente", "base": base,
                                                 "caudalIds": {str(c): self.dato(f"{sid}.q.{c}", caudales[i], unidad) for i, c in enumerate(comp) if caudales[i] is not None}},
                                     **({"estadoExterior": {"temperaturaId": self.dato(f"{sid}.T", *exterior)}} if exterior else {})})


def series(c):
    return {s["id"]: s["valores"] for s in c["series"]}


def err(xs, f):
    return max(abs(a - b) for a, b in zip(xs, f))


# 1. Serie con caudales constantes
M = Modelo(tf=("60", "s"))
M.volumen("v1", [100]); M.volumen("v2", [200])
M.corriente("s1", None, "v1", [3]); M.corriente("s2", "v1", "v2", [2]); M.corriente("s3", "v2", None, [1])
c = resolver(M.m); leer_resultados(c); S, t = series(c), c["ejes"][0]["valores"]
check("serie: m1 = 100 + t", err(S["campo.m_A_v1"], [100 + x for x in t]) < 1e-9)
check("serie: m2 = 200 + t", err(S["campo.m_A_v2"], [200 + x for x in t]) < 1e-9)
gen = generar(M.m)
leer_modelo_comun(gen)
check("serie: las ecuaciones generadas son un modelo común válido, con una ecuación por estado",
      [e["id"] for e in gen["matematico"]["ecuaciones"] if e["id"].startswith("materia.")] == ["materia.v1.1", "materia.v2.1"])

# 2. Cascada (Bateman)
M = Modelo(tf=("20", "s"))
for v, m0 in (("v1", 1), ("v2", 0), ("v3", 0)):
    M.volumen(v, [m0])
M.corriente("s1", "v1", "v2", ["0.1*m_A_v1"]); M.corriente("s2", "v2", "v3", ["0.1*m_A_v2"]); M.corriente("s3", "v3", None, ["0.1*m_A_v3"])
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
k = 0.1
check("cascada: Bateman en los tres volúmenes (1e-8)",
      max(err(S["campo.m_A_v1"], [math.exp(-k * x) for x in t]), err(S["campo.m_A_v2"], [k * x * math.exp(-k * x) for x in t]),
          err(S["campo.m_A_v3"], [(k * x) ** 2 / 2 * math.exp(-k * x) for x in t])) < 1e-8)

# 3. Recirculación cerrada
M = Modelo(tf=("20", "s"))
for v, m0 in (("v1", 3), ("v2", 0), ("v3", 0)):
    M.volumen(v, [m0])
k = 0.2
M.corriente("s1", "v1", "v2", [f"{k}*m_A_v1"]); M.corriente("s2", "v2", "v3", [f"{k}*m_A_v2"]); M.corriente("s3", "v3", "v1", [f"{k}*m_A_v3"])
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
tot = [a + b + d for a, b, d in zip(S["campo.m_A_v1"], S["campo.m_A_v2"], S["campo.m_A_v3"])]
check("recirculación: la masa total se conserva (1e-10)", max(abs(x - 3) for x in tot) < 1e-10)
V_ = {v["id"]: v["valor"] for v in c["verificaciones"]}
check("recirculación: cierres de presupuesto por estado y global publicados y < 1e-9",
      {"estado.m_A_v1", "global.materia.1"} <= set(V_) and max(V_.values()) < 1e-9, V_)
check("recirculación: m1 = 1 + 2 e^(-3kt/2) cos(sqrt3 k t/2) (1e-8)",
      err(S["campo.m_A_v1"], [1 + 2 * math.exp(-1.5 * k * x) * math.cos(math.sqrt(3) / 2 * k * x) for x in t]) < 1e-8)

# 4. Conversión A -> B por fuentes integradas
M = Modelo(ncomp=2, tf=("20", "s"))
M.volumen("v1", [1, 0], materia={"campo": {**MATERIA["campo"], "sinReaccion": False}},
          terminos={"generacion.1": M.dato("g1", "0", "kg/s"), "consumo.1": M.dato("c1", "0.2*m_A", "kg/s"),
                    "generacion.2": M.dato("g2", "0.2*m_A", "kg/s"), "consumo.2": M.dato("c2", "0", "kg/s")})
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
check("conversión: A = e^(-0.2t), B = 1 - A (1e-8)",
      max(err(S["campo.m_A_v1"], [math.exp(-.2 * x) for x in t]), err(S["campo.m_B_v1"], [1 - math.exp(-.2 * x) for x in t])) < 1e-8)

# 5. Fuente uniforme por volumen y caudal molar
M = Modelo(tf=("10", "s"))
M.m["componentes"][0]["masaMolar"] = {"cantidad": {"valor": 18, "unidad": "g/mol"}, "fuente": "prueba"}
M.volumen("v1", [1], materia={"campo": {**MATERIA["campo"], "sinReaccion": False, "sinConsumo": True}, "generacionUniforme": True},
          V=("2", "L"), terminos={"generacion.1": M.dato("g", "0.5", "kg/(m^3*s)")})
M.corriente("s1", None, "v1", [2], base="molar")
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
rate = 0.5 * 0.002 + 2 * 0.018
check("fuente por volumen (0.5 kg/m3/s · 2 L) y caudal molar (2 mol/s · 18 g/mol): recta", err(S["campo.m_A_v1"], [1 + rate * x for x in t]) < 1e-9)

# 6. Caudal total con fracciones
M = Modelo(ncomp=2, tf=("10", "s"))
M.volumen("v1", [0, 0])
M.m["corrientes"].append({"id": "s1", "desde": None, "hasta": "v1", "componenteIds": [1, 2], "mecanismo": "convectivo",
                          "materia": {"modo": "total_y_composicion", "base": "masica", "caudalId": M.dato("F", "1", "kg/s"), "fracciones": {"1": 0.25, "2": 0.75}}})
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
check("caudal total por fracciones: 0.25 t y 0.75 t", max(err(S["campo.m_A_v1"], [.25 * x for x in t]), err(S["campo.m_B_v1"], [.75 * x for x in t])) < 1e-9)

# 7. Agotamiento
M = Modelo(tf=("60", "s"))
M.volumen("v1", [100]); M.corriente("s", "v1", None, [2])
c = resolver(M.m); t = c["ejes"][0]["valores"]
check("agotamiento: se detiene en t = 50 s (1e-9) con estado parcial", c["estado"] == "parcial" and abs(t[-1] - 50) < 1e-9, t[-1])

# 8. Corriente convectiva con componentes en sentidos opuestos
M = Modelo(ncomp=2, tf=("20", "s"))
M.volumen("v1", [10, 10]); M.volumen("v2", [10, 10])
M.corriente("s", "v1", "v2", ["0.1", "0.1*(5-t)"], mecanismo="convectivo")
c = resolver(M.m)
check("convectiva con un componente que se invierte: se detiene en t = 5 s",
      c["estado"] == "parcial" and abs(c["ejes"][0]["valores"][-1] - 5) < 1e-6 and "mismo sentido" in c["procedencia"]["mensaje"], c["procedencia"].get("mensaje"))


# Energía
def con_energia(M, vid, m0, T0, extra=None, frontera=None, entalpia=True, rho=None):
    par = {"cId": M.dato("c", "4000", "J/(kg*K)"), "uRefId": M.dato("uref", "0", "J/kg"), "TRefId": M.dato("Tref", "293.15", "K"),
           "TMinId": M.dato("Tmin", "273.15", "K"), "TMaxId": M.dato("Tmax", "373.15", "K")}
    if rho:
        par["rhoId"] = M.dato("rho", rho, "kg/m^3")
    M.volumen(vid, [m0], energia={**ENERGIA, "entalpia": entalpia}, frontera=frontera, parametros=par,
              inicial_energia={"tipo": "T", "datoId": M.dato("T0", T0, "K")}, **(extra or {}))


# 9. Recipiente cerrado calentado
M = Modelo(tf=("300", "s"))
con_energia(M, "v1", 10, "293.15", extra={"materia": {"fija": True}, "terminos": {"calor": M.dato("Q", "1000", "W")}})
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
T = [293.15 + (U / 10) / 4000 for U in S["campo.U_v1"]]
check("cerrado calentado: T = T0 + Q t/(m c) (1e-9 K)", err(T, [293.15 + 1000 * x / (10 * 4000) for x in t]) < 1e-9)

# 10. Entrada caliente, cantidad constante (frontera móvil con p impuesta y rho)
M = Modelo(tf=("120", "s"))
fr = {"tipo": "presion_prescrita", "presionId": M.dato("p", "100000", "Pa")}
con_energia(M, "v1", 100, "293.15", frontera=fr, rho="1000", extra={"terminos": {"calor": M.dato("Q", "0", "W")}})
M.corriente("s1", None, "v1", [2], exterior=("333.15", "K")); M.corriente("s2", "v1", None, [2])
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
T = [293.15 + (U / m) / 4000 for U, m in zip(S["campo.U_v1"], S["campo.m_A_v1"])]
check("entrada caliente: T_in - T = (T_in - T0) e^(-mdot t/m) (1e-8 K)", err(T, [333.15 - 40 * math.exp(-2 * x / 100) for x in t]) < 1e-8)

# 11. Llenado con entrada caliente (frontera móvil, trabajo p dV/dt)
M = Modelo(tf=("100", "s"))
fr = {"tipo": "presion_prescrita", "presionId": M.dato("p", "100000", "Pa")}
con_energia(M, "v1", 100, "293.15", frontera=fr, rho="1000", extra={"terminos": {"calor": M.dato("Q", "0", "W")}})
M.corriente("s1", None, "v1", [2], exterior=("333.15", "K")); M.corriente("s2", "v1", None, [1])
c = resolver(M.m); S, t = series(c), c["ejes"][0]["valores"]
m_ = S["campo.m_A_v1"]
T = [293.15 + (U / m) / 4000 for U, m in zip(S["campo.U_v1"], m_)]
check("llenado: m = m0 + (in - out) t", err(m_, [100 + x for x in t]) < 1e-9)
V_ = {v["id"]: v["valor"] for v in c["verificaciones"]}
check("llenado: cierre global de energía (lo que cruza la frontera: corrientes, calor y trabajo p dV/dt) < 1e-9", V_["global.energia"] < 1e-9, V_)
check("llenado: T publicada como observable del servidor", err(S["observable.volumen.v1.T"], T) < 1e-9)
check("llenado: T_in - T = (T_in - T0)(m0/m)^(in/(in-out)) (1e-8 K)", err(T, [333.15 - 40 * (100 / (100 + x)) ** 2 for x in t]) < 1e-8)

# 12. Hasta T_max
M = Modelo(tf=("4000", "s"))
con_energia(M, "v1", 10, "293.15", extra={"materia": {"fija": True}, "terminos": {"calor": M.dato("Q", "1000", "W")}})
c = resolver(M.m)
t_lim = 10 * 4000 * (373.15 - 293.15) / 1000
check("hasta T_max: se detiene donde u(T) deja de valer, t = m c (T_max - T0)/Q (1e-6 s)",
      c["estado"] == "parcial" and abs(c["ejes"][0]["valores"][-1] - t_lim) < 1e-6 and "T_max" in c["procedencia"]["mensaje"],
      (c["ejes"][0]["valores"][-1], t_lim, c["procedencia"].get("mensaje")))


# Rechazos
def rechaza(nombre, m, fragmento):
    try:
        generar(m)
        check(nombre, False, "no lo rechazó")
    except NoGenerable as e:
        check(nombre, fragmento in str(e), str(e))


M = Modelo(); M.volumen("v1", [1]); M.corriente("s", "v1", None, ["step(t-1)"])
rechaza("función escalón: sin traducción al árbol común", M.m, "step")
M = Modelo(); M.volumen("v1", [1], materia={"campo": {**MATERIA["campo"], "sinReaccion": False}})
rechaza("término conservado por los supuestos y sin dato", M.m, "no tiene dato")
M = Modelo(); M.volumen("v1", [1], materia={"campo": {**MATERIA["campo"], "sinReaccion": False, "sinConsumo": True}, "generacionUniforme": True},
                       terminos={"generacion.1": M.dato("g", "1", "kg/(m^3*s)")})
rechaza("fuente uniforme sin el volumen como dato", M.m, "volumen del dominio")
M = Modelo(); M.volumen("v1", [1], materia={"fija": True, "campo": {**MATERIA["campo"], "sinConveccion": True}}); M.corriente("s", "v1", None, ["1"])
rechaza("supuestos que eliminan el transporte con una corriente que lo atraviesa", M.m, "eliminan el transporte")
M = Modelo(); M.volumen("v1", [1]); M.corriente("s", None, "v1", ["1"], base="molar")
rechaza("caudal molar sin masa molar", M.m, "masa molar")
M = Modelo(); M.volumen("v1", [1]); M.corriente("s", None, "v1", ["1"]); M.m["datos"]["s.q.1"]["declaracion"]["unidad"] = "kg"
rechaza("unidad que no es la de la magnitud del término", M.m, "no es de caudal_masico")
M = Modelo(); con_energia(M, "v1", 1, "293.15", extra={"materia": {"fija": True}, "terminos": {"calor": M.dato("Q", "1", "W")}})
M.m["volumenes"][0]["supuestos"]["energia"]["monofasico"] = False
rechaza("u(T) lineal sin declarar régimen monofásico", M.m, "monofásico")
M = Modelo(); con_energia(M, "v1", 1, "293.15", extra={"terminos": {"calor": M.dato("Q", "1", "W")}}); M.corriente("s", None, "v1", ["1"], exterior=("300", "K"))
rechaza("corrientes con energía sin presión ni densidad", M.m, "presión impuesta y densidad")
M = Modelo(); M.volumen("v1", [1]); M.m["volumenes"][0]["supuestos"]["materia"]["cantidadVolumen"] = True
rechaza("sustitución por volumen: la lleva su propio camino", M.m, "forma total")
try:
    M = Modelo(); M.volumen("v1", [1], materia={"campo": {**MATERIA["campo"], "sinReaccion": False}})
    resolver(M.m)
    check("la ruta de resolución convierte el rechazo en NoSoportado con su motivo", False)
except NoSoportado as e:
    check("la ruta de resolución convierte el rechazo en NoSoportado con su motivo", str(e).startswith("motor de balances:"), str(e))

# Sin sesgo
PROHIBIDAS = re.compile(r"\b(tanque|columna|reactor|destilaci|evaporador|caldera|intercambiador|decantador|condensador|hervidor|"
                        r"benceno|tolueno|etanol|butanol|metanol|acetona|agua)\b", re.IGNORECASE)
codigo = "\n".join(l for l in (RAIZ / "core/balances/generador.py").read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
codigo = re.sub(r'"""[\s\S]*?"""', "", codigo)
hallado = sorted(set(x.group(0).lower() for x in PROHIBIDAS.finditer(codigo)))
check("core/balances: ningún equipo, operación ni sustancia en el código", not hallado, hallado)

ej = RAIZ / "docs" / "ejemplos" / "modelo-comun" / "balances-llenado-entrada-caliente.json"
M = Modelo(tf=("100", "s"), muestras=11)
fr = {"tipo": "presion_prescrita", "presionId": M.dato("p", "100000", "Pa")}
con_energia(M, "v1", 100, "293.15", frontera=fr, rho="1000", extra={"terminos": {"calor": M.dato("Q", "0", "W")}})
M.corriente("s1", None, "v1", [2], exterior=("333.15", "K")); M.corriente("s2", "v1", None, [1])
ej.write_text(json.dumps({"modelo": M.m, "generado": generar(M.m), "resultados": resolver(M.m)}, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nMotor de balances: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
