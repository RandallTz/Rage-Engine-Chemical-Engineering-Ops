"""
Validacion de la TRAZABILIDAD: calculo, diagnosticos y convergencia.

Que se comprueba aqui y por que no se puede comprobar en otro sitio.

Los tres bloques nuevos de la respuesta existen para contestar preguntas
que el contrato anterior no contestaba:

  calculo       con que motor y sobre que entradas se calculo esto
  diagnosticos  que le pasa, en forma de DATOS y no de texto
  convergencia  de donde sale cada numero y cuanto me puedo fiar

Y las tres tienen una forma de fallar que no se ve mirando un resultado
concreto:

  1. Una huella que cambie cuando no deberia (o que no cambie cuando si)
     es peor que no tener huella: da una falsa sensacion de
     reproducibilidad. Se comprueba contra reordenamientos que NO cambian
     la fisica y contra cambios que SI.
  2. Una categoria deducida del texto del mensaje funciona hasta que
     alguien reescribe una frase, y entonces falla en silencio. Se
     comprueba que cada categoria venga de su origen estructural.
  3. Un residuo fabricado para una construccion geometrica o una
     correlacion es una mentira con cara de precision. Se comprueba que
     los bloques que NO iteran no traigan residuo, y que los que SI
     iteran lo traigan con su escala.

Ejecutar desde la raiz del proyecto:
    python tests/validar_trazabilidad.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import re

from backend.nucleo_diagrama import resolver_diagrama
from backend.schemas import ResolverDiagramaRequest, ResolverDiagramaResponse
from backend.trazabilidad import (
    construir_calculo, entradas_normalizadas, huella, VERSION_MOTOR,
)
from core import errores as codigos

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


BT = ["benzene", "toluene"]
ATM = 101325.0


def peticion_bomba(s2_P=None, factor=3.0, orden_invertido=False):
    """Una bomba, el caso del contrato."""
    corrientes = ["s2", "s1"] if orden_invertido else ["s1", "s2"]
    valores = {"s1.F": 100.0, "s1.T": 350.0, "s1.P": ATM,
               "s1.x0": 0.5, "s1.x1": 0.5, "b1.factor_P": factor}
    if s2_P is not None:
        valores["s2.P"] = s2_P
    return ResolverDiagramaRequest(
        componentes=BT, corrientes=corrientes,
        operaciones=[{"tipo": "bomba", "nombre": "b1",
                      "corrientes": {"entrada": "s1", "salida": "s2"}}],
        valores=valores,
    )


def peticion_columna():
    return ResolverDiagramaRequest(
        componentes=BT, corrientes=["alim", "dest", "fondo"],
        operaciones=[{"tipo": "columna", "nombre": "col1",
                      "corrientes": {"alimentacion": "alim", "destilado": "dest",
                                     "fondos": "fondo"},
                      "metodo": "mccabe_thiele"}],
        valores={"alim.F": 100.0, "alim.P": ATM, "alim.x0": 0.5,
                 "dest.x0": 0.95, "fondo.x0": 0.05, "col1.q": 1.0, "col1.R": 3.0},
    )


# ======================================================================
print("\n" + "=" * 74)
print("1. CALCULO: con que se calculo")
print("=" * 74)
# ======================================================================

c = construir_calculo(peticion_columna())
check("1.1 Trae la version del motor", c["motor"]["version"] == VERSION_MOTOR,
      f"version {c['motor']['version']}")
check("1.2 Y el commit de git, o None si no se puede saber",
      c["motor"]["commit"] is None or re.fullmatch(r"[0-9a-f]{40}(-sucio)?", c["motor"]["commit"]),
      str(c["motor"]["commit"]))
# None es una respuesta legitima: un despliegue sin .git no tiene commit, e
# inventarlo seria peor -- un identificador falso se propaga a los informes.
if c["motor"]["commit"] is None:
    print("     (sin commit: no hay .git o no hay git; es una respuesta valida)")

check("1.3 La fecha es UTC y del servidor",
      c["instante_utc"].endswith("+00:00"), c["instante_utc"])

# La version del PROVEEDOR es la de las librerias que deciden los numeros.
# Decir 'v1' seria inventar un numero que no cambia cuando los resultados
# si: requirements.txt las tiene fijas por este motivo exacto.
versiones = c["proveedor_termodinamico"]["versiones"]
check("1.4 La versión del proveedor son las de thermo, chemicals y fluids",
      all(versiones.get(p) for p in ("thermo", "chemicals", "fluids")),
      ", ".join(f"{p} {versiones[p]}" for p in ("thermo", "chemicals", "fluids")))
check("1.5 Y el identificador del modelo",
      c["proveedor_termodinamico"]["identificador"] == "unifac_raoult")
check("1.6 La huella es un sha256 completo, no truncado",
      c["algoritmo_huella"] == "sha256"
      and re.fullmatch(r"[0-9a-f]{64}", c["huella_entradas"]) is not None,
      f"{c['huella_entradas'][:16]}… ({len(c['huella_entradas'])} caracteres)")


# ======================================================================
print("\n" + "=" * 74)
print("2. LA HUELLA: igual cuando debe, distinta cuando debe")
print("=" * 74)
# ======================================================================
# Una huella que cambie cuando no deberia es PEOR que no tenerla: da una
# falsa sensacion de reproducibilidad.

a = construir_calculo(peticion_columna())
b = construir_calculo(peticion_columna())
check("2.1 Dos peticiones idénticas dan la MISMA huella",
      a["huella_entradas"] == b["huella_entradas"])
check("2.2 Y distinto identificador de ejecución",
      a["identificador"] != b["identificador"],
      "la huella dice «mismas entradas»; el identificador, «esta ejecución»")

# Lo que NO es fisica no debe cambiarla.
directo = construir_calculo(peticion_bomba(s2_P=303975.0))
invertido = construir_calculo(peticion_bomba(s2_P=303975.0, orden_invertido=True))
check("2.3 Reordenar las corrientes NO cambia la huella",
      directo["huella_entradas"] == invertido["huella_entradas"],
      "el solver es de punto fijo: el orden en que lleguen no cambia el diagrama")

# Y lo que SI es fisica, si.
otro_factor = construir_calculo(peticion_bomba(s2_P=303975.0, factor=4.0))
check("2.4 Cambiar el factor de compresión SÍ la cambia",
      directo["huella_entradas"] != otro_factor["huella_entradas"])

sin_s2 = construir_calculo(peticion_bomba())
check("2.5 Y quitar un dato también",
      directo["huella_entradas"] != sin_s2["huella_entradas"])

# El formato canonico de los floats: 1 y 1.0 son el mismo dato fisico, y
# sin normalizar darian huellas distintas.
e1 = entradas_normalizadas(peticion_bomba(s2_P=303975.0, factor=3))
e2 = entradas_normalizadas(peticion_bomba(s2_P=303975.0, factor=3.0))
check("2.6 Un entero y su float dan la misma huella",
      huella(e1) == huella(e2), "3 y 3.0 son el mismo dato")

# El orden de los COMPONENTES sí importa: define cuál es x0.
otros = ResolverDiagramaRequest(
    componentes=["toluene", "benzene"], corrientes=["s1", "s2"],
    operaciones=[{"tipo": "bomba", "nombre": "b1",
                  "corrientes": {"entrada": "s1", "salida": "s2"}}],
    valores={"s1.F": 100.0, "s1.T": 350.0, "s1.P": ATM,
             "s1.x0": 0.5, "s1.x1": 0.5, "b1.factor_P": 3.0, "s2.P": 303975.0})
check("2.7 Invertir los componentes SÍ cambia la huella: define cuál es x0",
      construir_calculo(otros)["huella_entradas"] != directo["huella_entradas"])

# La huella se calcula sobre texto JSON estricto: sin NaN, que no es JSON
# valido y reventaria al serializarla.
texto = json.dumps(entradas_normalizadas(peticion_columna()),
                   sort_keys=True, allow_nan=False)
check("2.8 Las entradas normalizadas serializan a JSON estricto",
      isinstance(texto, str) and len(texto) > 0)


# ======================================================================
print("\n" + "=" * 74)
print("3. DIAGNOSTICOS: la categoria no sale del texto")
print("=" * 74)
# ======================================================================
# El caso del contrato: bomba con las dos presiones Y el factor dados.

r = resolver_diagrama(peticion_bomba(s2_P=100000.0))
por_codigo = {d.codigo: d for d in r.diagnosticos}

check("3.1 La incompatibilidad de la bomba se reporta",
      codigos.DATOS_INCOMPATIBLES in por_codigo,
      ", ".join(sorted(por_codigo)))

inc = por_codigo.get(codigos.DATOS_INCOMPATIBLES)
if inc:
    check("3.2 Con categoría 'datos' y severidad de error",
          inc.categoria == "datos" and inc.severidad == "error")
    check("3.3 Señalando la variable y el equipo, no solo un mensaje",
          inc.variables == ["s2.P"] and inc.equipo == "s2",
          f"variables={inc.variables}, equipo={inc.equipo}")
    check("3.4 Y con los DOS números, para no tener que parsear el mensaje",
          inc.dado == 100000.0 and abs(inc.implicado - 303975.0) < 1e-6,
          f"dado {inc.dado:.0f}, implicado {inc.implicado:.0f}")

# La separacion que el contrato pide explicitamente.
check("3.5 'completo' es True y 'hay_errores' también: NO son lo mismo",
      r.completo is True and r.resumen_diagnosticos.hay_errores is True,
      "completo dice que todo se determinó; hay_errores, que algo lo invalida")

# Las redundancias son ADVERTENCIA, no error: los datos de mas no son
# necesariamente erroneos, se comprueban por consistencia.
redundancias = [d for d in r.diagnosticos if d.codigo == codigos.REDUNDANCIA]
check("3.6 Las redundancias son advertencia, no error",
      redundancias and all(d.severidad == "advertencia" for d in redundancias),
      f"{len(redundancias)} redundancia(s)")

# Ordenadas por severidad: quien lea la primera ya tiene lo mas grave.
severidades = [d.severidad for d in r.diagnosticos]
orden = {"error": 0, "advertencia": 1, "informacion": 2}
check("3.7 Ordenados por severidad",
      severidades == sorted(severidades, key=lambda s: orden[s]),
      " → ".join(severidades))

# --- un fallo FISICO, que es otra categoria
#
# Un reflujo por debajo del minimo: el numero existe y la situacion no.
# La categoria viene de la EXCEPCION (ErrorFisico con su codigo), no de
# buscar "etapas infinitas" en el mensaje.
bajo_minimo = peticion_columna()
bajo_minimo.valores["col1.R"] = 0.5
rf = resolver_diagrama(bajo_minimo)
fisicos = [d for d in rf.diagnosticos if d.categoria == "fisica"]
check("3.8 Un reflujo bajo el mínimo se clasifica como FÍSICA",
      fisicos and fisicos[0].codigo == codigos.REFLUJO_BAJO_MINIMO,
      fisicos[0].codigo if fisicos else "no apareció")
if fisicos:
    check("3.9 Y no es 'datos': cambiar un dato no lo arregla, hay que cambiar R",
          fisicos[0].categoria == "fisica" and fisicos[0].severidad == "error",
          fisicos[0].mensaje[:80])

# La falta de especificacion se agrupa por elemento, no una por variable:
# quince diagnosticos identicos no informan mas que uno que diga "a col1
# le faltan estas quince".
faltan = peticion_columna()
del faltan.valores["col1.R"]
rfa = resolver_diagrama(faltan)
fs = [d for d in rfa.diagnosticos
      if d.codigo == codigos.FALTA_ESPECIFICACION and d.severidad == "error"]
check("3.10 Las variables sin determinar se agrupan por elemento",
      fs and all(len(d.variables) >= 1 for d in fs),
      f"{len(fs)} diagnóstico(s) para "
      f"{sum(len(d.variables) for d in fs)} variable(s)")
causas = [d for d in rfa.diagnosticos
          if d.codigo == codigos.FALTA_ESPECIFICACION and d.severidad == "informacion"]
check("3.11 Y los bloques que no arrancaron van como INFORMACIÓN: son la causa",
      bool(causas), f"{len(causas)} bloque(s) sin disparar")

# Un caso limpio no debe inventar diagnosticos de error.
limpio = resolver_diagrama(peticion_columna())
errores_limpio = [d for d in limpio.diagnosticos if d.severidad == "error"]
check("3.12 Un diagrama bien planteado no tiene diagnósticos de error",
      limpio.completo and not errores_limpio
      and limpio.resumen_diagnosticos.hay_errores is False,
      f"{len(limpio.diagnosticos)} diagnóstico(s), ninguno de error")


# ======================================================================
print("\n" + "=" * 74)
print("4. CONVERGENCIA: sin residuos fabricados")
print("=" * 74)
# ======================================================================
# La parte que el contrato pide con mas insistencia: no inventar residuos
# para construcciones graficas o correlaciones.

# Se reportan TODOS, no solo los iterativos: "este número sale de una
# fórmula cerrada" es informacion, no una ausencia. (`diagnostico` no
# sirve de referencia: solo lista los bloques con algun problema, y en un
# caso limpio esta vacio.)
no_iteran = [c for c in limpio.convergencia if not c.metodo.itera]
check("4.1 Se reportan todos los bloques, también los que no iteran",
      len(limpio.convergencia) == 12 and len(no_iteran) > 0,
      f"{len(limpio.convergencia)} bloques, {len(no_iteran)} de ellos sin iterar")

# `ejecutado` distingue "no corrio" de "no hacia falta que corriera": la
# presion de operacion de la alimentacion no se dispara porque alim.P
# venia dada, y el solver solo rellena huecos. Es informacion util --
# dice que ese numero es un DATO y no un resultado.
sin_correr = [c for c in limpio.convergencia if not c.ejecutado]
check("4.2 'ejecutado' distingue el bloque que no hizo falta disparar",
      len(sin_correr) == 1 and "Presion de operacion (alim)" in sin_correr[0].bloque,
      f"{sin_correr[0].bloque}: alim.P venia dada" if sin_correr
      else "todos se dispararon")
check("4.3 Ninguno queda 'sin_declarar'",
      all(c.metodo.familia != "sin_declarar" for c in limpio.convergencia),
      ", ".join(sorted({c.metodo.familia for c in limpio.convergencia})))

mt = next((c for c in limpio.convergencia if "McCabe-Thiele" in c.bloque), None)
check("4.4 McCabe-Thiele se declara GEOMÉTRICO, no iterativo",
      mt is not None and mt.metodo.familia == "geometrico" and mt.metodo.itera is False)
if mt:
    check("4.5 Sin residuo, y diciendo POR QUÉ no lo hay",
          mt.metodo.residuo is None and mt.medido is None
          and mt.metodo.motivo and "construccion" in mt.metodo.motivo,
          mt.metodo.motivo[:88])

burbuja = next((c for c in limpio.convergencia if "Punto de burbuja" in c.bloque), None)
check("4.6 Un punto de burbuja SÍ es iterativo, y dice con qué tolerancia",
      burbuja is not None and burbuja.metodo.itera is True
      and burbuja.metodo.tolerancia is not None,
      f"{burbuja.metodo.metodo} / {burbuja.metodo.tolerancia}" if burbuja else "")
if burbuja:
    check("4.7 Y qué MIDE su residuo, con su escala",
          burbuja.metodo.residuo is not None, burbuja.metodo.residuo)

balance = next((c for c in limpio.convergencia if "balance de materia" in c.bloque), None)
check("4.8 Un balance algebraico no trae residuo: se cumple por construcción",
      balance is not None and balance.metodo.familia == "algebraico"
      and balance.medido is None)

# --- y uno que SI mide: el decantador, con su residuo real
#
# Se monta contra el MOTOR y no contra la API porque el decantador no
# esta expuesto como tipo de operacion en el esquema de la peticion:
# existe en core/diagrama_corrientes.py y no se puede pedir por HTTP.
# Esa es una laguna real del backend, anotada en docs/history/build-log.md; lo que aqui
# se valida es que cuando el bloque corre, reporta lo que midio.
from core.diagrama_corrientes import DiagramaCorrientes
from thermodynamics.proveedor import ProveedorTermodinamico

prov = ProveedorTermodinamico(["water", "1-butanol"])
d = DiagramaCorrientes(["water", "1-butanol"], proveedor=prov)
d.agregar_corriente("alim")
d.agregar_corriente("org")
d.agregar_corriente("acu")
d.agregar_decantador("dec1", "alim", "org", "acu")
rd = d.resolver(**{"alim.F": 100.0, "alim.T": 298.15, "alim.P": ATM,
                   "alim.x0": 0.75, "alim.x1": 0.25})

ell = next((c for c in rd["convergencia"] if "liquido-liquido" in c["bloque"]), None)
medido = (ell or {}).get("medido")
check("4.9 El decantador reporta el residuo que de verdad midió",
      medido is not None and medido.get("residuo") is not None,
      f"residuo {medido['residuo']:.3e} en {medido.get('iteraciones')} iteraciones"
      if medido and medido.get("residuo") is not None else str(medido))
if medido and medido.get("residuo") is not None:
    check("4.10 Con la ESCALA del residuo, sin la cual el número no se interpreta",
          "escala_residuo" in medido, medido.get("escala_residuo", "")[:70])
    check("4.11 Y el criterio que decidió que hubiera dos fases",
          medido.get("distancia_plano_tangente") is not None,
          f"tpd = {medido.get('distancia_plano_tangente'):.4e} "
          "(negativa: la fase única era inestable)")

# Fuera de la laguna de miscibilidad NO hay reparto que converger, y el
# bloque lo dice en vez de reportar un residuo de cero.
d2 = DiagramaCorrientes(["water", "1-butanol"], proveedor=prov)
for c in ("a2", "o2", "w2"):
    d2.agregar_corriente(c)
d2.agregar_decantador("dec2", "a2", "o2", "w2")
rd2 = d2.resolver(**{"a2.F": 100.0, "a2.T": 298.15, "a2.P": ATM,
                     "a2.x0": 0.999, "a2.x1": 0.001})
ell2 = next((c for c in rd2["convergencia"] if "liquido-liquido" in c["bloque"]), None)
m2 = (ell2 or {}).get("medido") or {}
check("4.12 Con una sola fase líquida no inventa un residuo: dice que no hubo reparto",
      m2.get("residuo") is None and bool(m2.get("nota")),
      m2.get("nota", str(m2))[:80])


# ======================================================================
print("\n" + "=" * 74)
print("5. EL CONTRATO ANTERIOR NO SE TOCA")
print("=" * 74)
# ======================================================================
# Todo lo nuevo es opcional y aditivo. Un cliente que no conozca los
# campos nuevos tiene que seguir funcionando igual.

for campo in ("completo", "pool", "incognitas_restantes", "resueltos_por",
              "diagnostico", "inconsistencias", "variables", "diagramas",
              "masas_molares_mezcla"):
    check(f"5.x '{campo}' sigue presente", hasattr(limpio, campo))

check("5.10 Y los campos nuevos son opcionales en el esquema",
      all(not ResolverDiagramaResponse.model_fields[c].is_required()
          for c in ("calculo", "diagnosticos", "resumen_diagnosticos", "convergencia")))

# La respuesta entera tiene que serializar a JSON estricto: un float32 de
# NumPy o un NaN pasan los tipos de Pydantic y revientan al serializar.
try:
    json.dumps(limpio.model_dump(), allow_nan=False)
    check("5.11 La respuesta completa serializa a JSON estricto", True)
except (TypeError, ValueError) as e:
    check("5.11 La respuesta completa serializa a JSON estricto", False, str(e)[:110])


print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
