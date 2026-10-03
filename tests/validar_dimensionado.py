"""
Validacion del DIMENSIONADO: de etapas teoricas a hardware.

Por que esto necesita literatura y el resto del proyecto no tanto. Las
correlaciones de aqui NO se derivan de nada: son ajustes empiricos a datos
de plantas reales. No hay invariante interno que las valide -- no se puede
comprobar que un diametro "cierre un balance". La unica forma de saber si
estan bien transcritas es reproducir un caso resuelto por la fuente.

Fuente: Perry's Chemical Engineers' Handbook, seccion 14, Ejemplo 9
("Flooding of a Distillation Tray"), una separacion etilbenceno/estireno
en una columna de platos de tamiz de 2.5 m. Perry's publica los numeros
intermedios, asi que se puede comparar paso a paso en vez de solo el
resultado -- y si uno se desvia, se sabe cual.

Ejecutar desde la raiz del proyecto:
    python tests/validar_dimensionado.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import math

from core.dimensionado import (
    parametro_de_flujo,
    capacidad_sin_corregir,
    velocidad_de_inundacion,
    diametro_columna,
    fraccion_de_inundacion_de,
    diferencia_media_logaritmica,
    area_intercambiador,
    coeficiente_global_tipico,
    COEFICIENTES_GLOBALES_TIPICOS,
)

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


# ======================================================================
print("\n" + "=" * 74)
print("1. PERRY'S EJEMPLO 9: ETILBENCENO/ESTIRENO")
print("=" * 74)
# ======================================================================
# Datos del plato superior, tal y como los da Perry's:
#   T = 78 C, P = 100 torr
#   vapor  25 500 kg/h,  rho = 0.481 kg/m3
#   liquido 22 000 kg/h, rho = 841 kg/m3
#   tension superficial 25 mN/m
#   plato de un paso: seccion 4.91 m2, bajantes 0.25, area neta 4.66,
#   activa 4.41, agujeros 0.617 m2 de 4.76 mm, vertedero 1.50 m y 38 mm
#   de alto, espaciado 500 mm.

G = 25500.0 / 3600.0        # kg/s
L = 22000.0 / 3600.0        # kg/s
RHO_G, RHO_L = 0.481, 841.0
SIGMA, TS = 25.0, 500.0
AREA_NETA, AREA_TOTAL, DIAMETRO = 4.66, 4.91, 2.5

# --- paso 1: el parametro de flujo
F_LG = parametro_de_flujo(L, G, RHO_L, RHO_G)
check("1.1 El parámetro de flujo reproduce el de Perry's",
      abs(F_LG - 0.021) < 0.0005,
      f"{F_LG:.6f} frente a 0.021 que publica Perry's (Eq. 14-89)")

# --- paso 2: el factor de capacidad, que Perry's LEE de una grafica
C_sbf = capacidad_sin_corregir(F_LG, TS)
check("1.2 La ecuación reproduce el valor que Perry's lee de la gráfica",
      abs(C_sbf - 0.095) < 0.002,
      f"{C_sbf:.6f} m/s frente a 0.095 leído de la Fig. 14-31 "
      f"({100*abs(C_sbf-0.095)/0.095:.1f} %)")

# --- paso 3: corregido por tension superficial
C_SB = C_sbf * (SIGMA / 20.0) ** 0.2
check("1.3 Y corregido por tensión superficial, el C_SB de Perry's",
      abs(C_SB - 0.0993) < 0.002,
      f"{C_SB:.6f} frente a 0.0993")

# --- paso 4: el C-factor de operacion, que es EL numero del ejemplo
operacion = fraccion_de_inundacion_de(G, L, RHO_G, RHO_L, AREA_NETA, TS, SIGMA)
check("1.4 El factor C de operación sale el de Perry's, a cuatro cifras",
      abs(operacion["factor_C"] - 0.0756) < 0.0001,
      f"{operacion['factor_C']:.6f} frente a 0.0756")

# --- paso 5: la fraccion de inundacion
#
# Perry's dice "about 80 percent of flood", pero sus PROPIOS numeros dan
# 0.0756/0.0993 = 76.1 %. El valor calculado aqui, 76.6 %, concuerda con
# su aritmetica mejor que con su redondeo -- y eso es lo que se comprueba,
# porque comparar contra el "about 80" seria comparar contra una frase.
suyo = 0.0756 / 0.0993
print(f"     Perry's dice «about 80 percent»; sus propios números dan {100*suyo:.1f} %")
check("1.5 La fracción de inundación concuerda con la aritmética de Perry's",
      abs(operacion["fraccion_de_inundacion"] - suyo) < 0.01,
      f"{100*operacion['fraccion_de_inundacion']:.2f} % calculado frente a "
      f"{100*suyo:.1f} % de sus números")
check("1.6 Y queda por debajo del 80 %, que es la conclusión del ejemplo",
      operacion["fraccion_de_inundacion"] < 0.80,
      "«the proposed column is entirely adequate for the service required»")

# --- paso 6: la inversa. Si el ejemplo opera al 76.6 %, el diametro que
# haria falta justo al 80 % tiene que salir muy cerca de los 2.5 m que la
# columna ya tiene.
d = diametro_columna(G, L, RHO_G, RHO_L, TS, SIGMA, fraccion_de_inundacion=0.80)
check("1.7 Al revés: el diámetro necesario al 80 % cae junto a los 2.5 m reales",
      abs(d["diametro"] - DIAMETRO) < 0.1,
      f"{d['diametro']:.4f} m frente a los {DIAMETRO} m de la columna "
      f"({100*(d['diametro']-DIAMETRO)/DIAMETRO:+.1f} %)")
check("1.8 Y la ida y vuelta es consistente: el área neta se recupera",
      abs(d["area_neta"] - AREA_NETA) < 0.5,
      f"{d['area_neta']:.4f} m² frente a {AREA_NETA} m²")

# El area neta NO es la seccion total, y confundirlas da una columna un
# 12 % mas estrecha. Se comprueba que la relacion sea la declarada.
check("1.9 El área neta es la total menos los bajantes, no la total",
      abs(d["area_neta"] / d["area_total"] - 0.88) < 1e-9,
      f"neta/total = {d['area_neta']/d['area_total']:.4f} con 12 % de bajantes")


# ======================================================================
print("\n" + "=" * 74)
print("2. COMO SE COMPORTA, Y POR QUE TIENE SENTIDO")
print("=" * 74)
# ======================================================================
# Lo anterior comprueba la transcripcion. Esto comprueba que el modelo
# responde como debe a lo que se le cambia -- que es lo que decide si se
# puede usar para explorar un diseno.

# Mas espacio entre platos -> mas sitio para que el liquido arrastrado
# caiga -> mas velocidad admisible -> columna mas estrecha. Es el
# compromiso clasico: columna estrecha y alta, o ancha y baja.
diametros = {}
for ts in (300.0, 450.0, 600.0, 900.0):
    diametros[ts] = diametro_columna(G, L, RHO_G, RHO_L, ts, SIGMA)["diametro"]
    print(f"     espaciado {ts:5.0f} mm  ->  D = {diametros[ts]:.4f} m")
check("2.1 Más espaciado entre platos, columna más estrecha",
      all(b < a for a, b in zip(diametros.values(), list(diametros.values())[1:])),
      "el compromiso clásico: estrecha y alta, o ancha y baja")

# Mas presion -> vapor mas denso -> menos volumen a mover -> columna mas
# estrecha. Es la razon por la que las columnas de vacio son enormes.
D_vacio = diametro_columna(G, L, 0.481, RHO_L, TS, SIGMA)["diametro"]
D_presion = diametro_columna(G, L, 10.0, RHO_L, TS, SIGMA)["diametro"]
check("2.2 Vapor más denso, columna más estrecha",
      D_presion < D_vacio,
      f"con ρ_V = 0.481 kg/m³ hacen falta {D_vacio:.3f} m; con 10 kg/m³, "
      f"{D_presion:.3f} m. Por eso las columnas de vacío son enormes")

# Y al 60 % de inundacion (el extremo conservador del rango de Perry's)
# la columna sale mas ancha que al 80 %.
D60 = diametro_columna(G, L, RHO_G, RHO_L, TS, SIGMA, fraccion_de_inundacion=0.60)["diametro"]
D80 = diametro_columna(G, L, RHO_G, RHO_L, TS, SIGMA, fraccion_de_inundacion=0.80)["diametro"]
check("2.3 Diseñar al 60 % en vez de al 80 % cuesta diámetro",
      D60 > D80,
      f"{D60:.3f} m al 60 % frente a {D80:.3f} m al 80 % "
      f"({100*(D60/D80-1):.1f} % más de diámetro, "
      f"{100*((D60/D80)**2-1):.0f} % más de sección)")


# ======================================================================
print("\n" + "=" * 74)
print("3. LO QUE EL DIMENSIONADO DEBE RECHAZAR")
print("=" * 74)
# ======================================================================

rechazos = [
    ("espaciado fuera del rango del ajuste (1200 mm)",
     lambda: capacidad_sin_corregir(0.02, 1200.0), "fuera del rango"),
    ("espaciado en metros en vez de milímetros (0.5)",
     lambda: capacidad_sin_corregir(0.02, 0.5), "fuera del rango"),
    ("sin caudal de vapor",
     lambda: diametro_columna(0.0, L, RHO_G, RHO_L), "Sin caudal de vapor"),
    ("vapor más denso que el líquido",
     lambda: parametro_de_flujo(L, G, 0.481, 841.0), "no puede ser mayor"),
    ("fracción de inundación mayor que 1",
     lambda: diametro_columna(G, L, RHO_G, RHO_L, fraccion_de_inundacion=1.2),
     "inundada"),
    ("tensión superficial negativa",
     lambda: velocidad_de_inundacion(0.02, 500.0, RHO_L, RHO_G, -1.0), "positiva"),
]
for nombre, accion, esperado in rechazos:
    try:
        accion()
        check(f"3.x {nombre} -> error", False, "no reventó")
    except ValueError as e:
        check(f"3.x {nombre} -> error", esperado.lower() in str(e).lower(), str(e)[:90])

# El espaciado en metros es el error mas probable de todos, porque no
# revienta por si solo: 0.5 es un numero perfectamente razonable. Lo que
# lo caza es el rango del ajuste. Que el mensaje lo diga importa.
try:
    capacidad_sin_corregir(0.02, 0.5)
except ValueError as e:
    check("3.7 Y el mensaje de los milímetros explica por qué no vale el número",
          "ajustada" in str(e) or "respaldado" in str(e), str(e)[:110])


# ======================================================================
print("\n" + "=" * 74)
print("4. INTERCAMBIADORES: LA DIFERENCIA MEDIA LOGARITMICA")
print("=" * 74)
# ======================================================================

# Un caso comprobable a mano: 100->60 contra 20->50, contracorriente.
#   dT_1 = 100 - 50 = 50 ; dT_2 = 60 - 20 = 40
#   LMTD = (50-40)/ln(50/40) = 10/0.22314 = 44.8142
lmtd = diferencia_media_logaritmica(100.0, 60.0, 20.0, 50.0, contracorriente=True)
exacto = 10.0 / math.log(50.0 / 40.0)
check("4.1 La LMTD coincide con el cálculo a mano",
      abs(lmtd - exacto) < 1e-12, f"{lmtd:.6f} K frente a {exacto:.6f}")
check("4.2 Y queda entre la diferencia menor y la mayor, como debe",
      40.0 < lmtd < 50.0, f"40 < {lmtd:.4f} < 50")
check("4.3 Por debajo de la media aritmética: eso es la media logarítmica",
      lmtd < 45.0, f"{lmtd:.4f} < 45.0")

# El caso 0/0: los dos extremos iguales. La formula da NaN; el limite
# existe y vale dT.
# dT_1 = 100 - 50 = 50 y dT_2 = 80 - 30 = 50. La primera version de esta
# linea pasaba (100, 80, 50, 30) y daba dT_1 = 70, dT_2 = 30: el 47.21 K que
# salia era CORRECTO para esos extremos, y el fallo estaba en el orden de los
# argumentos de la prueba, no en la funcion.
plana = diferencia_media_logaritmica(100.0, 80.0, 30.0, 50.0, contracorriente=True)
check("4.4 Con los dos extremos iguales devuelve el límite, no NaN",
      abs(plana - 50.0) < 1e-9, f"{plana:.6f} K (dT_1 = dT_2 = 50)")

# Contracorriente aprovecha mejor que paralelo: su LMTD es mayor para las
# mismas cuatro temperaturas, y por eso hace falta menos area.
contra = diferencia_media_logaritmica(150.0, 90.0, 30.0, 80.0, contracorriente=True)
paralelo = diferencia_media_logaritmica(150.0, 90.0, 30.0, 80.0, contracorriente=False)
check("4.5 Contracorriente da más LMTD que paralelo, con las mismas temperaturas",
      contra > paralelo,
      f"{contra:.4f} K contracorriente frente a {paralelo:.4f} K en paralelo")

# Un cruce de temperaturas no se calcula: se explica.
try:
    diferencia_media_logaritmica(100.0, 40.0, 30.0, 90.0, contracorriente=False)
    check("4.6 Un cruce de temperaturas se rechaza", False, "no reventó")
except ValueError as e:
    check("4.6 Un cruce de temperaturas se rechaza",
          "cruzan" in str(e) and "frio a caliente" in str(e), str(e)[:100])


# ======================================================================
print("\n" + "=" * 74)
print("5. INTERCAMBIADORES: EL AREA")
print("=" * 74)
# ======================================================================

# A = Q/(U dT F). Caso a mano: 500 kW, U = 500, LMTD = 44.8142
A = area_intercambiador(500_000.0, 500.0, lmtd)
esperado_A = 500_000.0 / (500.0 * lmtd)
check("5.1 El área sale de A = Q/(U·LMTD·F)",
      abs(A - esperado_A) < 1e-9, f"{A:.4f} m²")

# Un condensador tiene Q < 0 y su area NO es negativa. Sin el valor
# absoluto, ese numero se cuela en una hoja de calculo sin que se note.
A_cond = area_intercambiador(-500_000.0, 500.0, lmtd)
check("5.2 Un Q negativo (condensador) da la misma área, no una negativa",
      abs(A_cond - A) < 1e-12, f"{A_cond:.4f} m²")

# El factor de correccion solo puede empeorar: F <= 1.
A_F = area_intercambiador(500_000.0, 500.0, lmtd, factor_correccion_F=0.85)
check("5.3 Un factor de corrección menor que 1 exige MÁS área",
      A_F > A, f"{A_F:.4f} m² con F = 0.85 frente a {A:.4f} con F = 1")
try:
    area_intercambiador(500_000.0, 500.0, lmtd, factor_correccion_F=1.3)
    check("5.4 Un factor mayor que 1 se rechaza", False, "no reventó")
except ValueError as e:
    check("5.4 Un factor mayor que 1 se rechaza",
          "contracorriente pura" in str(e), str(e)[:100])

# Y los coeficientes tabulados vienen con su RANGO, no como un número
# suelto: el área hereda la incertidumbre del U, y esconderla sería
# presentar como dato lo que es un tanteo.
u = coeficiente_global_tipico("condensador_organico-agua")
check("5.5 Los coeficientes tabulados traen su rango, no un valor suelto",
      u["minimo"] < u["tipico"] < u["maximo"],
      f"U = {u['tipico']:.0f} W/m²K, entre {u['minimo']:.0f} y {u['maximo']:.0f}")
A_min = area_intercambiador(500_000.0, u["maximo"], lmtd)
A_max = area_intercambiador(500_000.0, u["minimo"], lmtd)
check("5.6 Y ese rango se traduce en un rango de área, que es lo honesto",
      A_max / A_min > 2.0,
      f"de {A_min:.2f} a {A_max:.2f} m² — un factor {A_max/A_min:.1f} "
      "solo por la incertidumbre del coeficiente")

try:
    coeficiente_global_tipico("no-existe")
    check("5.7 Un servicio sin tabular se rechaza listando los que hay", False, "no reventó")
except ValueError as e:
    check("5.7 Un servicio sin tabular se rechaza listando los que hay",
          "agua-agua" in str(e), f"{len(COEFICIENTES_GLOBALES_TIPICOS)} servicios tabulados")


print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
