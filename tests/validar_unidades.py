"""
Servicio único de unidades (core/unidades, docs/SERVICIO_UNIDADES.md).

  1. Equivalencia con los sistemas existentes: la tabla del backend del
     motor (backend/motor_ensamblaje.UNIDADES, copia de unidadesMotor.ts, más
     las ampliaciones de la revisión 2), la interpretación de la
     adimensionalización (core/adimensionalizacion/dimensional) y la del
     laboratorio (core/dimensiones). Mismo factor, mismo desplazamiento y
     misma dimensión. La tabla TS la contrasta frontend/verificar_unidades.mjs.
  2. Generalidad: cualquier unidad con la dimensión correcta es válida; las
     magnitudes se definen solo por dimensión.
  3. Rechazos claros y conversión de ida y vuelta.

Ejecutar desde la raíz:  python tests/validar_unidades.py
"""

import math
import sys
from fractions import Fraction
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core import unidades as un
from core.adimensionalizacion import dimensional as adim
from core import dimensiones as lab
from backend import motor_ensamblaje as me
from backend import motor_ensamblaje_v2  # noqa: F401  (amplía me.UNIDADES con cantidad y conductancia)

fallos, n = [], [0]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:300]) if detalle != '' else ''}")


def cerca(a, b, rel=1e-12):
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-300)


# Magnitudes del motor -> catálogo genérico (mismo concepto, nombre por dimensión).
MOTOR_A_CATALOGO = {"energia": "energia", "energia_especifica": "energia_especifica", "potencia": "potencia",
                    "temperatura": "temperatura", "presion": "presion", "masa": "masa", "tiempo": "tiempo",
                    "volumen": "volumen", "caudal": "caudal_masico", "caudal_molar": "caudal_molar",
                    "cantidad": "cantidad", "conductancia": "conductancia_termica"}

# 1a. Tabla del backend del motor
for mag, tabla in me.UNIDADES.items():
    check(f"magnitud del motor {mag}: tiene equivalente en el catálogo", mag in MOTOR_A_CATALOGO, mag)
    if mag not in MOTOR_A_CATALOGO:
        continue
    dim = un.dimension_de_magnitud(MOTOR_A_CATALOGO[mag])
    for u, (f, d) in tabla.items():
        i = un.interpretar(u)
        check(f"{mag} [{u}]: misma dimensión que la magnitud", i["dimension"] == dim, (i["dimension"], dim))
        check(f"{mag} [{u}]: mismo factor a SI ({f})", cerca(i["factor"], f), (i["factor"], f))
        check(f"{mag} [{u}]: mismo desplazamiento a SI ({d})", cerca(i["desplazamiento"], d, 1e-12) or abs(i["desplazamiento"] - d) < 1e-9, (i["desplazamiento"], d))
        check(f"{mag} [{u}]: la unidad SI de la magnitud es la del motor", un.unidad_SI(dim).replace("^", "") == me.UNIDAD_SI.get(mag, un.unidad_SI(dim)).replace("^", "")
              or mag not in me.UNIDAD_SI, (un.unidad_SI(dim), me.UNIDAD_SI.get(mag)))

# 1b. Adimensionalización y laboratorio
MUESTRA = ["s", "min", "h", "m", "cm", "mm", "kg", "g", "mol", "kmol", "K", "m^2", "m^3", "L", "mol/L", "mol/m^3", "kg/m^3",
           "g/L", "m^2/s", "cm^2/s", "m/s", "Pa", "kPa", "bar", "J", "kJ", "W", "kW", "1/s", "J/mol", "J/(mol*K)", "W/(m*K)",
           "W/(m^2*K)", "mol/(m^2*s)", "kg/(m^3*s)", "1"]
for u in MUESTRA:
    i = un.interpretar(u)
    a = adim.interpretar_unidad(u)
    check(f"[{u}] dimensión = la de la adimensionalización", a is not None and {k: Fraction(v) for k, v in a["dimension"].items()} == i["dimension"], (a, i["dimension"]))
    check(f"[{u}] factor = el de la adimensionalización", a is not None and cerca(a["factorSI"], i["factor"]), (a, i["factor"]))
    q = lab._cantidad(u)
    if q is not None:
        check(f"[{u}] factor = el del laboratorio", cerca(float(q.to_base_units().magnitude), i["factor"]), (q, i["factor"]))

# 2. Generalidad: ninguna lista cerrada
GENERALES = [("psi", "presion"), ("BTU/lb", "energia_especifica"), ("furlong/fortnight", "velocidad"), ("cal/(g*K)", "capacidad_calorifica_especifica"),
             ("lb/h", "caudal_masico"), ("gal/min", "caudal_volumetrico"), ("mmHg", "presion"), ("kmol/m3", "concentracion_molar"),
             ("cP", "viscosidad_dinamica"), ("Btu/(h*ft*degR)", "conductividad_termica"), ("µm", "longitud"), ("m3/kg", "volumen_especifico")]
for u, mag in GENERALES:
    try:
        i = un.interpretar(u)
        check(f"[{u}] aceptada por su dimensión ({mag})", mag in un.magnitudes_de(i["dimension"]), un.magnitudes_de(i["dimension"]))
    except un.ErrorUnidad as e:
        check(f"[{u}] aceptada por su dimensión ({mag})", False, e)
check("presión y densidad de energía comparten dimensión: un nombre no se deduce de la unidad",
      un.magnitudes_de(un.interpretar("Pa")["dimension"]) == ["presion"] and un.interpretar("J/m^3")["dimension"] == un.interpretar("Pa")["dimension"])
check("cada magnitud del catálogo tiene una unidad SI que vuelve a su dimensión",
      all(un.interpretar(un.unidad_SI(d))["dimension"] == d for d in un.MAGNITUDES.values()),
      [(k, un.unidad_SI(d)) for k, d in un.MAGNITUDES.items() if un.interpretar(un.unidad_SI(d))["dimension"] != d])

# 3. Conversión y rechazos
for v, u in [(25.0, "degC"), (77.0, "degF"), (3.0, "kmol/h"), (1.0, "kJ/(kg K)"), (2.5, "bar")]:
    check(f"ida y vuelta {v} {u}", cerca(un.desde_SI(un.a_SI(v, u), u), v, 1e-12))
check("25 °C = 298.15 K", cerca(un.a_SI(25.0, "°C"), 298.15))
tasa = un.interpretar("degC/s")
check("degC/s es una tasa de temperatura (= K/s): sin desplazamiento", tasa["factor"] == 1 and tasa["desplazamiento"] == 0 and not tasa["afin"], tasa)
for u, texto in [("xyz", "no reconocida"), ("", "")]:
    try:
        i = un.interpretar(u)
        check(f"[{u!r}] {'rechazada' if texto else 'adimensional'}", not texto and i["dimension"] == {}, i)
    except un.ErrorUnidad as e:
        check(f"[{u!r}] rechazada con motivo", bool(texto) and texto in str(e), e)
check("compatibles: kg/h y g/s sí; kg/h y mol/s no", un.compatibles("kg/h", "g/s") and not un.compatibles("kg/h", "mol/s"))

print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nServicio de unidades: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
