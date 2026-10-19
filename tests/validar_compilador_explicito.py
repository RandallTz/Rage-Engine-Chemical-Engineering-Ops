"""
Compilador del modelo común, entrada de ecuaciones explícitas (paso 5.1 de
ARQUITECTURA_MOTOR.md §10; core/compilador/explicito.py).

Modelos escritos a mano, sin volúmenes ni componentes ni nada del motor: el
compilador ejecuta lo que dicen sus ecuaciones. Contra soluciones analíticas
independientes:

  1. Crecimiento logístico, con la tasa en 1/min (conversión a SI por el
     servicio único de unidades).
  2. Oscilador armónico como sistema de primer orden (x, v).
  3. Agotamiento: dm/dt = -k con restricción no negativa. Se detiene en el
     instante exacto m0/k; sin la restricción, la ecuación sigue (el dominio
     es una declaración del modelo, no una regla escondida).
  4. Valor nulo en t = 0 con derivada negativa: se detiene en t = 0.
  5. Sistema rígido y' = -a (y - cos t), a = 1e4, con BDF: misma solución
     analítica y muchos menos pasos que RK45.
  6. Rechazos con motivo: unidad incompatible con la dimensión del símbolo,
     dato pendiente, ecuación algebraica, coordenada espacial, función
     declarada, orden dos, condición inicial que depende de variables.
  7. La ruta POST /modelo/resolver devuelve el mismo conjunto y 422 con motivo.
  8. Comprobación estática: ningún equipo, operación ni sustancia en el código.

Ejecutar desde la raíz:  python tests/validar_compilador_explicito.py
"""

import copy
import json
import math
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from fastapi import HTTPException  # noqa: E402

from backend.api_modelo import resolver_modelo  # noqa: E402
from core.compilador import NoSoportado, SistemaExplicito, resolver  # noqa: E402
from core.resultados import leer_resultados  # noqa: E402

n, fallos = [0], []


def check(nombre, cond, detalle=""):
    n[0] += 1
    if not cond:
        fallos.append(nombre)
        print(f"FALLO {nombre} {detalle}")


D = lambda **k: {b: {"n": v, "d": 1} for b, v in k.items()}  # noqa: E731
num = lambda v: {"tipo": "numero", "valor": v}  # noqa: E731
s = lambda i: {"tipo": "simbolo", "id": i}  # noqa: E731
prod = lambda *a: {"tipo": "producto", "argumentos": list(a)}  # noqa: E731
suma = lambda *a: {"tipo": "suma", "argumentos": list(a)}  # noqa: E731
der = lambda u, orden=1: {"tipo": "derivada", "expresion": s(u), "respecto": "t", "orden": orden}  # noqa: E731


def simbolo(id_, rol, dim, unidad=None):
    return {"id": id_, "nombre": id_, "rol": rol, "dimension": dim, "unidad": unidad, "constante": rol in ("parametro", "constante"),
            "dependeDe": ["t"] if rol == "campo" else [], "signo": "desconocido"}


def modelo(campos, parametros, ecuaciones, iniciales, valores, tf=("10", "s"), metodo="rk45", restricciones=None, muestras=101,
           rtol=1e-9, atol=1e-12):
    """campos/parametros: [(id, dim)]; ecuaciones: {u: expr}; iniciales: {u: expr}; valores: {param: (texto, unidad)}."""
    sims = [simbolo("t", "tiempo", D(T=1))] + [simbolo(u, "campo", d) for u, d in campos] + \
           [simbolo(p, "parametro", d) for p, d in parametros] + [simbolo("tf", "parametro", D(T=1))]
    datos = {f"matematico.{p}": {"magnitud": "parametro", "funcion": "parametro", "declaracion": {"texto": v[0], "unidad": v[1]},
                                 "origen": {"propietarioId": "matematico", "ruta": f"matematico.simbolos.{p}"}} for p, v in valores.items()}
    datos["estudio.tf"] = {"magnitud": "tiempo", "funcion": "estudio", "declaracion": {"texto": tf[0], "unidad": tf[1]},
                           "origen": {"propietarioId": "estudio", "ruta": "estudio.tf"}}
    m = {"formato": "rage.modelo", "version": 0, "id": "prueba", "nombre": "prueba", "componentes": [], "termodinamica": {"paquetes": []},
         "volumenes": [], "corrientes": [], "intercambios": [], "datos": datos,
         "matematico": {"id": "mat", "revision": 1, "simbolos": sims, "funciones": [],
                        "ecuaciones": [{"id": f"ec_{u}", "izquierda": der(u), "derecha": e} for u, e in ecuaciones.items()],
                        "dominios": [{"id": "it", "variableId": "t", "desde": num(0), "hasta": s("tf")}],
                        "condiciones": [{"id": f"ini_{u}", "tipo": "inicial", "dominioId": "it",
                                         "ecuacion": {"id": f"ini_{u}-eq", "izquierda": s(u), "derecha": e}} for u, e in iniciales.items()]},
         "estudio": {"tipo": "temporal", "tiempoId": "estudio.tf", "metodoSolicitado": metodo, "muestras": muestras, "rtol": rtol, "atol": {"cantidad": atol}},
         "motores": {}, "procedencia": {"tipo": "nuevo"}}
    if restricciones:
        m["restricciones"] = [{"simboloId": u, "tipo": "no_negativo"} for u in restricciones]
    return m


def serie(c, id_):
    return next(x for x in c["series"] if x["id"] == id_)["valores"]


# --- 1. Logístico, tasa en 1/min ---------------------------------------------------------
r_min, K, N0 = 0.6, 50.0, 2.0
log = modelo([("N", {})], [("r", D(T=-1)), ("K", {}), ("N0", {})],
             {"N": prod(s("r"), s("N"), suma(num(1), prod(num(-1), {"tipo": "cociente", "numerador": s("N"), "denominador": s("K")})))},
             {"N": s("N0")}, {"r": (str(r_min), "1/min"), "K": (str(K), ""), "N0": (str(N0), "1")}, tf=("30", "min"))
c = resolver(log)
leer_resultados(c)
t = c["ejes"][0]["valores"]
ana = [K / (1 + (K / N0 - 1) * math.exp(-r_min / 60 * x)) for x in t]
err = max(abs(a - b) / K for a, b in zip(serie(c, "campo.N"), ana))
check("logístico: igual a la solución analítica (1e-7)", err < 1e-7, err)
check("logístico: el tiempo final de 30 min es 1800 s (servicio de unidades)", abs(t[-1] - 1800) < 1e-9 and c["ejes"][0]["unidadSI"] == "s", t[-1])
check("logístico: resuelto, formato común válido", c["estado"] == "resuelto" and c["procedencia"]["motor"] == "rage.compilador.explicito")

# --- 2. Oscilador como sistema de primer orden ----------------------------------------
w, x0 = 2.0, 0.1
osc = modelo([("x", D(L=1)), ("v", D(L=1, T=-1))], [("w", D(T=-1)), ("x0", D(L=1))],
             {"x": s("v"), "v": prod(num(-1), {"tipo": "potencia", "base": s("w"), "exponente": num(2)}, s("x"))},
             {"x": s("x0"), "v": num(0)}, {"w": (str(w), "1/s"), "x0": ("10", "cm")}, tf=("10", "s"))
c = resolver(osc)
t = c["ejes"][0]["valores"]
ex_ = max(abs(a - x0 * math.cos(w * x)) for a, x in zip(serie(c, "campo.x"), t))
ev = max(abs(a + x0 * w * math.sin(w * x)) for a, x in zip(serie(c, "campo.v"), t))
check("oscilador: x(t) = x0 cos(wt) con x0 = 10 cm (1e-8 m)", ex_ < 1e-8, ex_)
check("oscilador: v(t) = -x0 w sin(wt) (1e-8 m/s)", ev < 1e-8, ev)
check("oscilador: unidades SI de cada serie (m, m/s)", [x["unidadSI"] for x in c["series"]] == ["m", "m/s"], [x["unidadSI"] for x in c["series"]])

# --- 3. Agotamiento ------------------------------------------------------------------------
ago = modelo([("m", D(M=1))], [("k", D(M=1, T=-1)), ("m0", D(M=1))], {"m": prod(num(-1), s("k"))}, {"m": s("m0")},
             {"k": ("1", "kg/h"), "m0": ("2", "kg")}, tf=("3", "h"), restricciones=["m"])
c = resolver(ago)
t = c["ejes"][0]["valores"]
check("agotamiento: se detiene en t = m0/k = 7200 s (1e-6 s)", abs(t[-1] - 7200) < 1e-6, t[-1])
check("agotamiento: estado parcial con evento 'agotamiento' en ese instante",
      c["estado"] == "parcial" and [e["codigo"] for e in c["eventos"]] == ["agotamiento"] and abs(c["eventos"][0]["valor"] - 7200) < 1e-6)
check("agotamiento: ningún valor negativo publicado; el último es ~0",
      min(serie(c, "campo.m")) >= 0 and serie(c, "campo.m")[-1] < 1e-9, serie(c, "campo.m")[-1])
check("agotamiento: las muestras anteriores siguen la recta m0 - k t (1e-10)",
      max(abs(a - (2 - x / 3600)) for a, x in zip(serie(c, "campo.m"), t)) < 1e-10)
libre = copy.deepcopy(ago)
del libre["restricciones"]
c = resolver(libre)
check("sin restricción declarada la ecuación continúa hasta tf (el dominio es del modelo)",
      c["estado"] == "resuelto" and abs(c["ejes"][0]["valores"][-1] - 10800) < 1e-9 and abs(serie(c, "campo.m")[-1] + 1) < 1e-9)

# --- 4. Cero en t = 0 con derivada negativa ------------------------------------------
cero = copy.deepcopy(ago)
cero["datos"]["matematico.m0"]["declaracion"]["texto"] = "0"
c = resolver(cero)
check("vacío en t = 0 y saliendo: se detiene en t = 0", c["estado"] == "parcial" and c["ejes"][0]["valores"] == [0.0] and c["eventos"][0]["codigo"] == "agotamiento")

# --- 5. Rígido con BDF -------------------------------------------------------------------
a = 1e4
rig = modelo([("y", {})], [("a", D(T=-1))],
             {"y": prod(num(-1), s("a"), suma(s("y"), prod(num(-1), {"tipo": "funcion", "nombre": "cos", "argumentos": [s("t")]})))},
             {"y": num(0)}, {"a": (str(a), "1/s")}, tf=("5", "s"), metodo="bdf", rtol=1e-8, atol=1e-10, muestras=11)
c_bdf = resolver(rig)
t = c_bdf["ejes"][0]["valores"]
C = -a * a / (a * a + 1)
ana = [(a * a * math.cos(x) + a * math.sin(x)) / (a * a + 1) + C * math.exp(-a * x) for x in t]
e = max(abs(p - q) for p, q in zip(serie(c_bdf, "campo.y"), ana))
check("rígido: BDF igual a la analítica (1e-6)", e < 1e-6, e)
r_rk = copy.deepcopy(rig)
r_rk["estudio"]["metodoSolicitado"] = "rk45"
c_rk = resolver(r_rk)
check("rígido: BDF necesita muchos menos pasos que RK45", c_bdf["procedencia"]["pasos"] * 20 < c_rk["procedencia"]["pasos"],
      (c_bdf["procedencia"]["pasos"], c_rk["procedencia"]["pasos"]))
check("rígido: el método publicado es el pedido", "BDF" in c_bdf["procedencia"]["metodo"] and "RK45" in c_rk["procedencia"]["metodo"])


# --- 6. Rechazos con motivo -------------------------------------------------------------
def rechaza(nombre, m, fragmento):
    try:
        SistemaExplicito(m)
        check(nombre, False, "no lo rechazó")
    except NoSoportado as e:
        check(nombre, fragmento in str(e), str(e))


m = copy.deepcopy(ago)
m["datos"]["matematico.k"]["declaracion"]["unidad"] = "kg"
rechaza("unidad incompatible con la dimensión del símbolo", m, "no corresponde a la dimensión")
m = copy.deepcopy(ago)
m["datos"]["matematico.k"]["declaracion"]["texto"] = " "
rechaza("dato pendiente", m, "dato pendiente")
m = copy.deepcopy(ago)
del m["datos"]["matematico.k"]
rechaza("valor de parámetro ausente", m, "falta el valor")
m = copy.deepcopy(ago)
m["matematico"]["ecuaciones"][0]["izquierda"] = s("m")
rechaza("ecuación algebraica (DAE): pendiente", m, "algebraicas")
m = copy.deepcopy(ago)
m["matematico"]["simbolos"].append(simbolo("x", "coordenada", D(L=1)))
rechaza("coordenada espacial: motor de discretización", m, "discretización")
m = copy.deepcopy(ago)
m["matematico"]["ecuaciones"][0]["izquierda"] = der("m", 2)
rechaza("derivada de orden dos", m, "orden 2")
m = copy.deepcopy(ago)
m["matematico"]["condiciones"][0]["ecuacion"]["derecha"] = s("m")
rechaza("condición inicial que depende de variables", m, "no puede depender")
m = copy.deepcopy(ago)
m["matematico"]["funciones"] = [{"id": "h", "nombre": "h", "entradas": [D(M=1)], "salida": D(M=1, T=-1), "dependeDe": []}]
m["matematico"]["ecuaciones"][0]["derecha"] = {"tipo": "llamada", "funcionId": "h", "argumentos": [s("m")]}
rechaza("función declarada sin definición", m, "sin definición")

# --- 7. Ruta HTTP ------------------------------------------------------------------------
check("POST /modelo/resolver: el mismo conjunto que el compilador", resolver_modelo({"modelo": log}) == resolver(log))
try:
    resolver_modelo({"modelo": m})
    check("POST /modelo/resolver: 422 con motivo", False)
except HTTPException as e:
    check("POST /modelo/resolver: 422 con motivo", e.status_code == 422 and e.detail["codigo"] == "no_soportado")

# --- 8. Sin sesgo -------------------------------------------------------------------------
PROHIBIDAS = re.compile(r"\b(tanque|columna|reactor|destilaci|evaporador|caldera|intercambiador|decantador|condensador|hervidor|"
                        r"benceno|tolueno|etanol|butanol|metanol|acetona|agua)\b", re.IGNORECASE)
for ruta in ["core/compilador/explicito.py", "core/solvers/integrador.py"]:
    codigo = "\n".join(l for l in (RAIZ / ruta).read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
    codigo = re.sub(r'"""[\s\S]*?"""', "", codigo)
    hallado = sorted(set(x.group(0).lower() for x in PROHIBIDAS.finditer(codigo)))
    check(f"{ruta}: ningún equipo, operación ni sustancia en el código", not hallado, hallado)

salida = RAIZ / "docs" / "ejemplos" / "modelo-comun" / "explicito-agotamiento.json"
salida.write_text(json.dumps({"modelo": ago, "resultados": resolver(ago)}, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nCompilador explícito: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
