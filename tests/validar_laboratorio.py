"""
Validacion del ensamblador del laboratorio (/laboratorio/*).

LA REGLA DE ESTE PROYECTO, APLICADA AQUI
----------------------------------------
"Que un metodo corra no es que funcione." Los numeros de esta suite NO
estan escritos a mano: se comparan contra LLAMADAS INDEPENDIENTES al mismo
proveedor termodinamico. Si escribiera "Q1 = 147842.85 W" y manana
'thermo' cambiara una correlacion, la prueba fallaria sin que nada este
roto; y peor, si el ensamblador tuviera un error y yo hubiera copiado su
salida como valor esperado, la prueba lo bendeciria para siempre.

Asi que el patron es: el ensamblador calcula por su camino, y la prueba
calcula por el camino corto -- flash isotermico directo al proveedor -- y
se comparan. Lo unico que se afirma a priori son las IDENTIDADES fisicas,
que no dependen de ningun dato: que F se conserva, que duplicar F duplica
Q, que Q1+Q2 = F dh, y que imponer el Q calculado recupera la T de la que
salio.

QUE SE COMPRUEBA, POR GRUPOS
----------------------------
1. Uno y dos volumenes; continuidad de F, x, T, p y h en la corriente
   compartida, y conservacion global de energia.
2. Los modos T y Q son excluyentes: ambos impuestos, ninguno impuesto, y
   datos contradictorios sobre la misma variable.
3. Montajes mal formados: ids duplicados, referencias inexistentes,
   puertos incompatibles, piezas aisladas, ciclos, NaN/Inf, fracciones
   fuera de [0,1], unidades incompatibles y modelo/componente no
   disponibles.
4. No convergencia y estado fuera del dominio: diagnostico SIN presentar
   resultados como resueltos.
5. Los diagnosticos citan ids que existen en la peticion, y las
   ecuaciones marcadas como ejecutadas se corresponden con el calculo
   real.
6. No regresion de /diagrama/resolver ni del CSTR actual.

Ejecutar desde la raiz del proyecto:
    python tests/validar_laboratorio.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio
import copy
import json

import httpx
import numpy as np

from backend.main import app
from core import errores as codigos
from core import laboratorio as lab
from core.flash import EvaluadorFlash
from thermodynamics.elv import CalculadoraELV
from thermodynamics.proveedor import ProveedorTermodinamico

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


class ClienteASGI:
    """Cliente sincrono contra la app, sin abrir puerto (ver validar_api.py)."""

    def __init__(self, app, base_url="http://validacion"):
        self.app, self.base_url = app, base_url

    def _pedir(self, metodo, ruta, **kw):
        async def hacer():
            transporte = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transporte, base_url=self.base_url,
                                         timeout=600.0) as c:
                return await c.request(metodo, ruta, **kw)
        return asyncio.run(hacer())

    def get(self, ruta, **kw):
        return self._pedir("GET", ruta, **kw)

    def post(self, ruta, json=None):
        return self._pedir("POST", ruta, json=json)

    def post_crudo(self, ruta, texto):
        """
        Un cuerpo ya serializado, para mandar lo que httpx no serializaria.

        Hace falta porque `NaN` no es JSON valido y httpx se niega -- con
        razon -- a ponerlo en el cuerpo. Pero el parser de Python SI lo
        acepta, asi que un cliente descuidado puede colarlo y la guarda
        del nucleo tiene que estar probada contra ese camino.
        """
        return self._pedir("POST", ruta, content=texto.encode("utf-8"),
                           headers={"Content-Type": "application/json"})


cliente = ClienteASGI(app)

# ---------------------------------------------------------------------
# La referencia independiente: el proveedor por el camino corto.
# ---------------------------------------------------------------------
ATM = 101325.0
COMPONENTES = ["benzene", "toluene"]
_proveedor = ProveedorTermodinamico(COMPONENTES)
_flash = EvaluadorFlash(CalculadoraELV(_proveedor), P_sistema=ATM)


def h_ref(T, x=0.5, P=ATM):
    """h molar en (T, P, x) pedida DIRECTAMENTE al proveedor."""
    return _flash.isotermico(float(T), P, np.array([x, 1.0 - x]))["h"]


def fase_ref(T, x=0.5, P=ATM):
    return _flash.isotermico(float(T), P, np.array([x, 1.0 - x]))["fase"]


# ---------------------------------------------------------------------
# El montaje del caso de aceptacion.
# ---------------------------------------------------------------------
def montaje_dos_volumenes():
    return {
        "version": 1,
        "componentes": list(COMPONENTES),
        "modelo_termodinamico": "unifac_raoult",
        "referencia_entalpia": "sensible_liquido_298.15K",
        "presion_sistema": {"valor": ATM, "unidad": "Pa"},
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion"},
            {"id": "cv1", "tipo": "recipiente", "nombre": "Primer volumen"},
            {"id": "heat1", "tipo": "calor", "nombre": "Primer aporte"},
            {"id": "medio", "tipo": "corriente", "nombre": "Corriente compartida"},
            {"id": "cv2", "tipo": "recipiente", "nombre": "Segundo volumen"},
            {"id": "heat2", "tipo": "calor", "nombre": "Segundo aporte"},
            {"id": "out", "tipo": "salida", "nombre": "Salida final"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "cv1", "tipo": "materia"},
            {"id": "c2", "desde": "heat1", "hacia": "cv1", "tipo": "calor"},
            {"id": "c3", "desde": "cv1", "hacia": "medio", "tipo": "materia"},
            {"id": "c4", "desde": "medio", "hacia": "cv2", "tipo": "materia"},
            {"id": "c5", "desde": "heat2", "hacia": "cv2", "tipo": "calor"},
            {"id": "c6", "desde": "cv2", "hacia": "out", "tipo": "materia"},
        ],
        "supuestos": {"estacionario": True, "adiabatico": False, "sinTrabajo": True,
                      "sinReaccion": True, "sinMovimiento": True},
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 300.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x", "valor": 0.5, "unidad": "mol/mol"},
            {"bloque_id": "cv1", "variable": "T", "valor": 310.0, "unidad": "K"},
            {"bloque_id": "cv2", "variable": "T", "valor": 320.0, "unidad": "K"},
        ],
    }


def montaje_un_volumen():
    m = montaje_dos_volumenes()
    m["bloques"] = [b for b in m["bloques"] if b["id"] not in ("medio", "cv2", "heat2")]
    m["conexiones"] = [c for c in m["conexiones"] if c["id"] in ("c1", "c2")]
    m["conexiones"].append({"id": "c3", "desde": "cv1", "hacia": "out",
                            "tipo": "materia"})
    m["especificaciones"] = [e for e in m["especificaciones"]
                             if e["bloque_id"] != "cv2"]
    return m


def sin_spec(m, bloque, variable):
    m = copy.deepcopy(m)
    m["especificaciones"] = [e for e in m["especificaciones"]
                             if not (e["bloque_id"] == bloque
                                     and e["variable"] == variable)]
    return m


def con_spec(m, **kw):
    m = copy.deepcopy(m)
    m["especificaciones"] = m["especificaciones"] + [kw]
    return m


def var(resultado, vid):
    return next((v for v in resultado["variables"] if v["id"] == vid), None)


def valor(resultado, vid):
    v = var(resultado, vid)
    return None if v is None else v["valor"]


def errores_de(resultado):
    return [d for d in resultado["diagnosticos"] if d["severidad"] == "error"]


def resolver(m):
    r = cliente.post("/laboratorio/resolver", json=m)
    assert r.status_code == 200, (r.status_code, r.text[:400])
    return r.json()


def validar(m):
    r = cliente.post("/laboratorio/validar", json=m)
    assert r.status_code == 200, (r.status_code, r.text[:400])
    return r.json()


# =====================================================================
print("\n" + "=" * 76)
print("1. UNO Y DOS VOLUMENES: continuidad y conservacion")
print("=" * 76)
# =====================================================================

r2 = resolver(montaje_dos_volumenes())
check("1.1 El caso de aceptación se resuelve", r2["estado"] == "resuelto",
      f"estado={r2['estado']}, "
      f"{r2['resumen_diagnosticos']['por_severidad']}")

# --- contra el proveedor, NO contra numeros escritos a mano
h300, h310, h320 = h_ref(300.0), h_ref(310.0), h_ref(320.0)
Q1_esperado = 100.0 * (h310 - h300)
Q2_esperado = 100.0 * (h320 - h310)
Q1, Q2 = valor(r2, "heat1.Q"), valor(r2, "heat2.Q")

check("1.2 Q₁ coincide con F(h₃₁₀−h₃₀₀) pedida al proveedor por separado",
      abs(Q1 - Q1_esperado) < 1e-9 * abs(Q1_esperado),
      f"{Q1:.6f} W frente a {Q1_esperado:.6f} W")
check("1.3 Q₂ coincide con F(h₃₂₀−h₃₁₀)",
      abs(Q2 - Q2_esperado) < 1e-9 * abs(Q2_esperado),
      f"{Q2:.6f} W frente a {Q2_esperado:.6f} W")

# Y la identidad que no depende de ningun dato.
Q_total = 100.0 * (h320 - h300)
check("1.4 Q₁+Q₂ = F(h₃₂₀−h₃₀₀): el cierre global",
      abs(Q1 + Q2 - Q_total) < 1e-6,
      f"{Q1 + Q2:.6f} W frente a {Q_total:.6f} W")
check("1.5 Y el motor lo MIDE, no lo supone",
      r2["convergencia"]["cierre_global"]["residuo_relativo"] is not None
      and r2["convergencia"]["cierre_global"]["residuo_relativo"] < 1e-12,
      f"residuo relativo {r2['convergencia']['cierre_global']['residuo_relativo']:.3e}")

# Cp NO es constante, y aqui se ve: el mismo salto de 10 K cuesta distinto.
check("1.6 Q₂ ≠ Q₁ para el mismo salto de 10 K: Cp no es constante",
      abs(Q2 - Q1) / Q1 > 0.01,
      f"{100 * (Q2 - Q1) / Q1:.2f} % más caro el segundo tramo")

# --- la corriente compartida es UN estado
estados = r2["estados_por_bloque"]
check("1.7 F se conserva en toda la cadena",
      estados["in"]["F"] == estados["medio"]["F"] == estados["out"]["F"] == 100.0)
check("1.8 x se conserva: no hay reacción ni segunda alimentación",
      estados["in"]["x"] == estados["medio"]["x"] == estados["out"]["x"] == 0.5)
check("1.9 p es uniforme", {estados[b]["p"] for b in ("in", "medio", "out")} == {ATM})
check("1.10 La T intermedia es la que impuso el primer volumen",
      estados["medio"]["T"] == 310.0)
check("1.11 Y su h es la del proveedor en ese estado",
      abs(estados["medio"]["h"] - h310) < 1e-12,
      f"{estados['medio']['h']:.9f} J/mol")

compartidas = [v for v in r2["variables"] if v["compartida"]]
check("1.12 Las seis variables de la corriente intermedia son compartidas",
      len(compartidas) == 6
      and {v["id"] for v in compartidas}
      == {"medio.F", "medio.T", "medio.p", "medio.h", "medio.x0", "medio.x1"},
      ", ".join(sorted(v["id"] for v in compartidas)))
check("1.13 Y cada una referencia LOS DOS volúmenes y LAS DOS conexiones",
      all(set(v["bloque_ids"]) == {"medio", "cv1", "cv2"}
          and set(v["conexion_ids"]) == {"c3", "c4"} for v in compartidas),
      "un solo estado, no dos que haya que igualar")
check("1.14 No hay variables duplicadas para el mismo estado",
      len({v["id"] for v in r2["variables"]}) == len(r2["variables"]),
      f"{len(r2['variables'])} variables")

# --- un solo volumen
r1 = resolver(montaje_un_volumen())
check("1.15 Un solo volumen también se resuelve", r1["estado"] == "resuelto")
check("1.16 Con su Q igual al del primer tramo del caso de dos",
      abs(valor(r1, "heat1.Q") - Q1_esperado) < 1e-9 * abs(Q1_esperado),
      f"{valor(r1, 'heat1.Q'):.6f} W")
check("1.17 Y con GL = 0: 7 incógnitas y 7 ecuaciones",
      r1["analisis"]["grados_libertad"] == 0
      and r1["analisis"]["incognitas"] == 7
      and r1["analisis"]["ecuaciones_independientes"] == 7,
      f"{r1['analisis']['incognitas']} incógnitas / "
      f"{r1['analisis']['ecuaciones_independientes']} ecuaciones")

# Con un volumen el cierre global ES el balance de ese volumen, así que no
# se mide: medirlo daría el error de redondeo de la ecuación de la que se
# despejó Q, y presentarlo como verificación sería una tautología.
global1 = next(e for e in r1["ecuaciones"] if e["id"] == "global:energia")
check("1.18 Con un volumen el cierre global NO se mide: sería una tautología",
      global1["ejecutada"] is False and global1["residuo"] is None
      and "tautologia" in global1["nota"],
      global1["nota"][:92])

check("1.19 Dos volúmenes: GL = 0 con 12 incógnitas y 12 ecuaciones",
      r2["analisis"]["grados_libertad"] == 0
      and r2["analisis"]["incognitas"] == 12
      and r2["analisis"]["ecuaciones_independientes"] == 12,
      f"{r2['analisis']['incognitas']} / "
      f"{r2['analisis']['ecuaciones_independientes']}")

# --- duplicar F duplica los calores: identidad exacta, sin datos
doble = copy.deepcopy(montaje_dos_volumenes())
for e in doble["especificaciones"]:
    if e["bloque_id"] == "in" and e["variable"] == "F":
        e["valor"] = 200.0
rd = resolver(doble)
check("1.20 Duplicar F duplica Q₁ y Q₂ exactamente",
      abs(valor(rd, "heat1.Q") - 2 * Q1) < 1e-9 * abs(Q1)
      and abs(valor(rd, "heat2.Q") - 2 * Q2) < 1e-9 * abs(Q2),
      f"Q₁ {valor(rd, 'heat1.Q'):.4f} W, Q₂ {valor(rd, 'heat2.Q'):.4f} W")
check("1.21 Y afecta a las dos etapas, conservando la identidad de la intermedia",
      rd["estados_por_bloque"]["medio"]["F"] == 200.0
      and rd["estados_por_bloque"]["medio"]["T"] == 310.0,
      "el caudal cambia; el estado sigue siendo uno")

# --- la fase se DETERMINA, no se supone
check("1.22 La fase se determina con burbuja y rocío, y coincide con el proveedor",
      all(estados[b]["fase"] == fase_ref(estados[b]["T"])
          for b in ("in", "medio", "out")),
      ", ".join(f"{b}:{estados[b]['fase']}" for b in ("in", "medio", "out")))
check("1.23 Y trae beta, que es el dato que lo respalda",
      all(estados[b]["beta"] == 0.0 for b in ("in", "medio", "out")),
      "beta = 0 en los tres: líquido subenfriado a 1 atm")


# =====================================================================
print("\n" + "=" * 76)
print("2. MODOS T Y Q: excluyentes, y por una razón estructural")
print("=" * 76)
# =====================================================================

# El segundo caso de aceptación: imponer el Q calculado y recuperar la T.
caso2 = con_spec(sin_spec(montaje_dos_volumenes(), "cv1", "T"),
                 bloque_id="heat1", variable="Q", valor=Q1, unidad="W")
rq = resolver(caso2)
check("2.1 Imponiendo Q₁ se recupera la T intermedia",
      rq["estado"] == "resuelto"
      and abs(rq["estados_por_bloque"]["medio"]["T"] - 310.0) < 1e-9,
      f"{rq['estados_por_bloque']['medio']['T']!r} K "
      f"(error {abs(rq['estados_por_bloque']['medio']['T'] - 310.0):.2e} K)")
check("2.2 Y el segundo tramo sigue dando el mismo Q₂",
      abs(valor(rq, "heat2.Q") - Q2_esperado) < 1e-9 * abs(Q2_esperado))
check("2.3 Ese modo es una INVERSIÓN ESCALAR, no un sistema acoplado",
      rq["convergencia"]["alcance"] == "mixto"
      and "brentq" in rq["convergencia"]["metodo"],
      rq["convergencia"]["metodo"][:88])
check("2.4 Con su residuo medido y su escala",
      rq["convergencia"]["residuo_escalado"] is not None
      and rq["convergencia"]["escala_residuo"] is not None,
      f"residuo {rq['convergencia']['residuo_escalado']:.3e} — "
      f"{rq['convergencia']['escala_residuo']}")

# Las mismas unidades, otra escala.
caso2k = con_spec(sin_spec(montaje_dos_volumenes(), "cv1", "T"),
                  bloque_id="heat1", variable="Q", valor=Q1 / 1000.0, unidad="kW")
check("2.5 El mismo calor en kW da la misma temperatura",
      abs(resolver(caso2k)["estados_por_bloque"]["medio"]["T"] - 310.0) < 1e-9)

# --- los tres fallos de especificación
ambos = con_spec(montaje_dos_volumenes(), bloque_id="heat1", variable="Q",
                 valor=1000.0, unidad="W")
ra = resolver(ambos)
ea = errores_de(ra)
check("2.6 Imponer T y Q a la vez se rechaza",
      ra["estado"] != "resuelto" and ea
      and ea[0]["codigo"] == codigos.LAB_ESPECIFICACION_EXCLUYENTE,
      ea[0]["codigo"] if ea else "no se rechazó")
check("2.7 Y el motivo es estructural, no una regla arbitraria",
      ea and "una ecuacion" in (ea[0]["accion_sugerida"] or ""),
      (ea[0]["accion_sugerida"] or "")[:92] if ea else "")

ninguno = sin_spec(montaje_dos_volumenes(), "cv1", "T")
rn = resolver(ninguno)
en = errores_de(rn)
check("2.8 No imponer ninguno se detecta como falta de especificación",
      rn["estado"] != "resuelto" and en
      and en[0]["codigo"] == codigos.LAB_FALTA_ESPECIFICACION,
      en[0]["codigo"] if en else "no se detectó")

dup = con_spec(montaje_dos_volumenes(), bloque_id="cv2", variable="T",
               valor=330.0, unidad="K")
rdup = resolver(dup)
edup = errores_de(rdup)
check("2.9 Dos valores distintos para la misma variable se rechazan",
      edup and edup[0]["codigo"] == codigos.LAB_ESPECIFICACION_DUPLICADA,
      edup[0]["mensaje"][:95] if edup else "no se rechazó")

igual = con_spec(montaje_dos_volumenes(), bloque_id="cv2", variable="T",
                 valor=320.0, unidad="K")
eig = errores_de(resolver(igual))
check("2.10 Y también cuando COINCIDEN: una variable se fija una sola vez",
      eig and eig[0]["codigo"] == codigos.LAB_ESPECIFICACION_DUPLICADA,
      "si mañana una cambia, el conflicto aparece sin que nadie la toque")

# Dato local contra especificación explícita: la contradicción que el
# contrato pide no ignorar.
local = copy.deepcopy(montaje_dos_volumenes())
for b in local["bloques"]:
    if b["id"] == "cv1":
        b["datos"] = {"T": 315.0}
el = errores_de(resolver(local))
check("2.11 Un dato local que contradice una especificación se denuncia",
      el and el[0]["codigo"] == codigos.LAB_ESPECIFICACION_DUPLICADA
      and "datos locales" in el[0]["mensaje"]
      and "no coinciden" in el[0]["mensaje"],
      el[0]["mensaje"][:100] if el else "se ignoró (!)")

# Y el montaje que exporta la mesa hoy: SOLO datos locales.
solo_datos = copy.deepcopy(montaje_dos_volumenes())
solo_datos["especificaciones"] = []
for b in solo_datos["bloques"]:
    if b["id"] == "in":
        b["datos"] = {"F": 100.0, "T": 300.0, "p": ATM, "x": 0.5}
    if b["id"] == "cv1":
        b["datos"] = {"T": 310.0}
    if b["id"] == "cv2":
        b["datos"] = {"T": 320.0}
rsd = resolver(solo_datos)
check("2.12 El montaje con solo datos locales da el MISMO resultado",
      rsd["estado"] == "resuelto"
      and abs(valor(rsd, "heat1.Q") - Q1) < 1e-9 * abs(Q1),
      f"Q₁ = {valor(rsd, 'heat1.Q'):.6f} W")
check("2.13 Y la procedencia dice que llegó sin unidad escrita",
      "dato local" in (var(rsd, "in.T")["procedencia"] or ""),
      var(rsd, "in.T")["procedencia"])

# Q local se lee en kW: es la unidad que documenta la mesa.
q_local = copy.deepcopy(solo_datos)
for b in q_local["bloques"]:
    if b["id"] == "cv1":
        b.pop("datos")
    if b["id"] == "heat1":
        b["datos"] = {"Q": Q1 / 1000.0}
check("2.14 Un Q local se interpreta en kW, como documenta la mesa",
      abs(resolver(q_local)["estados_por_bloque"]["medio"]["T"] - 310.0) < 1e-8,
      "mismo número en kW, misma temperatura")


# =====================================================================
print("\n" + "=" * 76)
print("3. MONTAJES MAL FORMADOS")
print("=" * 76)
# =====================================================================

def caso_malo(nombre, montaje, codigo_esperado, estado_esperado=None):
    r = validar(montaje)
    errs = errores_de(r)
    codigos_vistos = [d["codigo"] for d in errs]
    ok = codigo_esperado in codigos_vistos
    if estado_esperado:
        ok = ok and r["estado"] == estado_esperado
    check(nombre, ok,
          f"estado={r['estado']}, códigos={', '.join(codigos_vistos[:3]) or 'ninguno'}")
    return r


m = copy.deepcopy(montaje_dos_volumenes())
m["bloques"].append({"id": "in", "tipo": "salida", "nombre": "Duplicada"})
caso_malo("3.1 Id de bloque duplicado", m, codigos.LAB_ID_DUPLICADO, "invalido")

m = copy.deepcopy(montaje_dos_volumenes())
m["conexiones"].append({"id": "c1", "desde": "cv2", "hacia": "out",
                        "tipo": "materia"})
caso_malo("3.2 Id de conexión duplicado", m, codigos.LAB_ID_DUPLICADO)

m = copy.deepcopy(montaje_dos_volumenes())
m["conexiones"][0]["desde"] = "pieza_fantasma"
r = caso_malo("3.3 Referencia a un bloque inexistente", m,
              codigos.LAB_REFERENCIA_INEXISTENTE)
check("3.4 Y el diagnóstico señala la CONEXIÓN, no una pieza al azar",
      errores_de(r)[0]["conexion_ids"] == ["c1"],
      f"conexion_ids={errores_de(r)[0]['conexion_ids']}")

m = copy.deepcopy(montaje_dos_volumenes())
m["conexiones"][0] = {"id": "c1", "desde": "in", "hacia": "out", "tipo": "materia"}
caso_malo("3.5 Puerto incompatible: alimentación directa a salida", m,
          codigos.LAB_PUERTO_INCOMPATIBLE)

m = copy.deepcopy(montaje_dos_volumenes())
m["conexiones"].append({"id": "mala", "desde": "heat1", "hacia": "out",
                        "tipo": "calor"})
caso_malo("3.6 Puerto incompatible: calor a una salida", m,
          codigos.LAB_PUERTO_INCOMPATIBLE)

m = copy.deepcopy(montaje_dos_volumenes())
m["bloques"].append({"id": "suelta", "tipo": "calor", "nombre": "Sin conectar"})
r = caso_malo("3.7 Pieza aislada", m, codigos.LAB_PIEZA_AISLADA)
check("3.8 Señalando la pieza concreta",
      "suelta" in errores_de(r)[0]["bloque_ids"])

m = copy.deepcopy(montaje_dos_volumenes())
m["bloques"].append({"id": "medio2", "tipo": "corriente", "nombre": "Vuelta"})
m["conexiones"].append({"id": "r1", "desde": "cv2", "hacia": "medio2",
                        "tipo": "materia"})
m["conexiones"].append({"id": "r2", "desde": "medio2", "hacia": "cv1",
                        "tipo": "materia"})
r = caso_malo("3.9 Ciclo: se diagnostica como ciclo, no como síntoma", m,
              codigos.LAB_CICLO, "no_soportado")
check("3.10 Y dice POR DÓNDE pasa el lazo",
      "->" in errores_de(r)[0]["mensaje"],
      errores_de(r)[0]["mensaje"][:88])

# --- NaN, Inf y null: tres caminos, y solo dos son alcanzables por HTTP
#
# httpx se niega a serializar un NaN, y tiene razon: NaN e Infinity NO son
# JSON valido. Asi que un cliente bien educado no puede mandarlos. Lo que
# SI llega:
#
#   * null, porque `JSON.stringify` de JavaScript convierte NaN e Infinity
#     en null. Es EL caso realista de una interfaz web, y el que pasa si
#     el usuario deja un campo vacio.
#   * el token desnudo `NaN` en el cuerpo, que algunos serializadores
#     emiten y que el parser de Python acepta.
#
# Y el NaN de Python se prueba contra el nucleo directamente, que es donde
# puede aparecer: un script que use core/laboratorio.py sin pasar por HTTP.

m = con_spec(sin_spec(montaje_dos_volumenes(), "in", "T"),
             bloque_id="in", variable="T", valor=None, unidad="K")
r = caso_malo("3.11 Un valor null se diagnostica, no se toma por cero", m,
              codigos.LAB_FALTA_ESPECIFICACION)
check("3.12 Y el mensaje dice que null no es cero",
      "null no es cero" in errores_de(r)[0]["mensaje"],
      errores_de(r)[0]["mensaje"][:88])

m = con_spec(sin_spec(montaje_dos_volumenes(), "in", "F"),
             bloque_id="in", variable="F", valor=100.0, unidad=None)
caso_malo("3.13 Una especificación sin unidad se rechaza", m,
          codigos.LAB_UNIDAD_INCOMPATIBLE)

# El token desnudo `NaN` en el cuerpo: no es JSON valido, pero el parser de
# Python lo acepta, asi que la guarda tiene que estar y hay que probarla.
cuerpo_nan = json.dumps(
    con_spec(sin_spec(montaje_dos_volumenes(), "in", "T"),
             bloque_id="in", variable="T", valor=1.0, unidad="K")
).replace('"valor": 1.0, "unidad": "K"', '"valor": NaN, "unidad": "K"')
rn_ = cliente.post_crudo("/laboratorio/resolver", cuerpo_nan)
check("3.14 Un NaN desnudo en el cuerpo tampoco pasa",
      rn_.status_code == 200
      and any(d["codigo"] == codigos.LAB_VALOR_NO_FINITO
              for d in errores_de(rn_.json())),
      f"{rn_.status_code}: "
      + ", ".join(d["codigo"] for d in errores_de(rn_.json()))[:70])

# Y el NaN de Python, contra el nucleo: es donde puede llegar de verdad,
# desde un script que no pase por HTTP.
m_nan = con_spec(sin_spec(montaje_dos_volumenes(), "in", "T"),
                 bloque_id="in", variable="T", valor=float("nan"), unidad="K")
d_nan = errores_de(lab.resolver(m_nan))
check("3.15 Y el núcleo rechaza un NaN de Python directamente",
      d_nan and d_nan[0]["codigo"] == codigos.LAB_VALOR_NO_FINITO,
      d_nan[0]["mensaje"][:80] if d_nan else "lo aceptó (!)")

m_inf = con_spec(sin_spec(montaje_dos_volumenes(), "in", "F"),
                 bloque_id="in", variable="F", valor=float("inf"), unidad="mol/s")
d_inf = errores_de(lab.resolver(m_inf))
check("3.16 Igual que un infinito",
      d_inf and d_inf[0]["codigo"] == codigos.LAB_VALOR_NO_FINITO,
      d_inf[0]["mensaje"][:80] if d_inf else "lo aceptó (!)")

m = con_spec(sin_spec(montaje_dos_volumenes(), "in", "x"),
             bloque_id="in", variable="x", valor=1.5, unidad="mol/mol")
caso_malo("3.17 Fracción molar fuera de [0,1]", m, codigos.LAB_FRACCION_INVALIDA)

m = con_spec(sin_spec(montaje_dos_volumenes(), "in", "F"),
             bloque_id="in", variable="F", valor=-10.0, unidad="mol/s")
caso_malo("3.18 Caudal negativo", m, codigos.LAB_VALOR_FUERA_DE_DOMINIO)

m = con_spec(sin_spec(montaje_dos_volumenes(), "in", "F"),
             bloque_id="in", variable="F", valor=100.0, unidad="gal/min")
r = caso_malo("3.19 Unidad incompatible", m, codigos.LAB_UNIDAD_INCOMPATIBLE)
check("3.20 Y el mensaje LISTA las unidades que sí valen",
      "mol/s" in errores_de(r)[0]["mensaje"],
      errores_de(r)[0]["mensaje"][:95])

m = con_spec(sin_spec(montaje_dos_volumenes(), "in", "T"),
             bloque_id="in", variable="T", valor=26.85, unidad="degC")
rc = resolver(m)
check("3.21 En cambio degC sí se admite, y es AFÍN (no solo un factor)",
      rc["estado"] == "resuelto"
      and abs(rc["estados_por_bloque"]["in"]["T"] - 300.0) < 1e-9,
      f"26.85 °C → {rc['estados_por_bloque']['in']['T']} K")

m = copy.deepcopy(montaje_dos_volumenes())
m["modelo_termodinamico"] = "peng_robinson"
caso_malo("3.22 Modelo termodinámico no disponible", m,
          codigos.LAB_MODELO_NO_DISPONIBLE, "no_soportado")

m = copy.deepcopy(montaje_dos_volumenes())
m["referencia_entalpia"] = "formacion_298K"
caso_malo("3.23 Referencia de entalpía no disponible", m,
          codigos.LAB_MODELO_NO_DISPONIBLE)

m = copy.deepcopy(montaje_dos_volumenes())
m["componentes"] = ["benzene", "componente_que_no_existe_xyz"]
caso_malo("3.24 Componente que el proveedor no conoce", m,
          codigos.LAB_COMPONENTE_NO_DISPONIBLE, "no_soportado")

m = copy.deepcopy(montaje_dos_volumenes())
m["componentes"] = ["benzene", "toluene", "water"]
r = caso_malo("3.25 Con tres componentes, 'x' a secas ya no identifica ninguna", m,
              codigos.LAB_VARIABLE_DESCONOCIDA)
check("3.25b Y el mensaje dice cómo nombrarlas",
      "x0, x1, x2" in (errores_de(r)[0]["accion_sugerida"] or ""),
      (errores_de(r)[0]["accion_sugerida"] or "")[:95])

m = copy.deepcopy(montaje_dos_volumenes())
m["componentes"] = ["benzene"]
caso_malo("3.25c Un solo componente no es una mezcla", m,
          codigos.LAB_NUMERO_DE_COMPONENTES, "no_soportado")

m = copy.deepcopy(montaje_dos_volumenes())
m["componentes"] = ["benzene", "benzene"]
caso_malo("3.25d Un componente repetido", m,
          codigos.LAB_NUMERO_DE_COMPONENTES, "no_soportado")

m = copy.deepcopy(montaje_dos_volumenes())
m["supuestos"]["adiabatico"] = True
r = caso_malo("3.26 Fuente de calor conectada con supuesto adiabático", m,
              codigos.LAB_SUPUESTO_INCOHERENTE)
check("3.27 El supuesto anula el término que la pieza existe para aportar",
      set(errores_de(r)[0]["conexion_ids"]) & {"c2", "c5"},
      errores_de(r)[0]["mensaje"][:90])

# La otra mitad, y la que el contrato subraya: NO inferir adiabaticidad
# por ausencia de la pieza.
m = copy.deepcopy(montaje_dos_volumenes())
m["bloques"] = [b for b in m["bloques"] if b["id"] != "heat1"]
m["conexiones"] = [c for c in m["conexiones"] if c["id"] != "c2"]
r = caso_malo("3.28 Volumen sin fuente térmica y sin supuesto adiabático", m,
              codigos.LAB_FALTA_ESPECIFICACION)
check("3.29 No se infiere Q = 0 por la ausencia de la pieza",
      "no significa Q = 0" in (errores_de(r)[0]["accion_sugerida"] or ""),
      (errores_de(r)[0]["accion_sugerida"] or "")[:100])

for supuesto in ("estacionario", "sinTrabajo", "sinMovimiento"):
    m = copy.deepcopy(montaje_dos_volumenes())
    m["supuestos"][supuesto] = not m["supuestos"][supuesto]
    caso_malo(f"3.30 Supuesto no soportado: {supuesto} invertido", m,
              codigos.LAB_SUPUESTO_NO_SOPORTADO, "no_soportado")

# 'sinReaccion' ya NO es uno de ellos: ahora hay reacción. Quitarlo sin
# declarar ninguna reacción no invalida el cálculo --un recipiente no
# lleva término de transformación-- pero el montaje declara una intención
# que su topología no recoge, y callarlo dejaría al usuario creyendo que
# algo reacciona.
m = copy.deepcopy(montaje_dos_volumenes())
m["supuestos"]["sinReaccion"] = False
rsr = validar(m)
avisos = [d for d in rsr["diagnosticos"] if d["severidad"] == "advertencia"]
check("3.30b Quitar 'sinReaccion' sin ningún reactor avisa, pero no invalida",
      rsr["estado"] == "valido"
      and any(d["codigo"] == codigos.LAB_SIN_REACCION_DECLARADA for d in avisos),
      f"estado={rsr['estado']}, "
      + (avisos[0]["mensaje"][:80] if avisos else "sin aviso (!)"))

m = copy.deepcopy(montaje_dos_volumenes())
del m["supuestos"]["sinMovimiento"]
caso_malo("3.31 Un supuesto que falta no se da por supuesto", m,
          codigos.LAB_SUPUESTO_NO_SOPORTADO)

m = copy.deepcopy(montaje_dos_volumenes())
for b in m["bloques"]:
    if b["id"] == "cv1":
        b["tipo"] = "reactor"
m["supuestos"]["sinReaccion"] = False
r = caso_malo("3.32 Un reactor que no declara su reacción se rechaza", m,
              codigos.LAB_SIN_REACCION_DECLARADA)
check("3.32b Y el motivo es el mismo que con el calor: la ausencia no es un supuesto",
      "no significa que no haya reaccion"
      in (errores_de(r)[0]["accion_sugerida"] or ""),
      (errores_de(r)[0]["accion_sugerida"] or "")[-95:])

m = copy.deepcopy(montaje_dos_volumenes())
m["bloques"].append({"id": "in2", "tipo": "entrada", "nombre": "Segunda"})
m["conexiones"].append({"id": "c7", "desde": "in2", "hacia": "cv1",
                        "tipo": "materia"})
caso_malo("3.33 Dos alimentaciones a un volumen se rechazan con diagnóstico", m,
          codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "no_soportado")

m = copy.deepcopy(montaje_dos_volumenes())
m["bloques"].append({"id": "trab", "tipo": "trabajo", "nombre": "Eje"})
m["conexiones"].append({"id": "c8", "desde": "trab", "hacia": "cv1",
                        "tipo": "trabajo"})
m["supuestos"]["sinTrabajo"] = False
caso_malo("3.34 Trabajo de eje: formulación sí, cálculo no", m,
          codigos.LAB_SUPUESTO_NO_SOPORTADO, "no_soportado")

m = copy.deepcopy(montaje_dos_volumenes())
for b in m["bloques"]:
    if b["id"] == "heat1":
        b["datos"] = {"T": 350.0}
caso_malo("3.35 Un dato local que la pieza no puede tener", m,
          codigos.LAB_VARIABLE_DESCONOCIDA)

m = copy.deepcopy(montaje_dos_volumenes())
m["presion_sistema"] = {"valor": -5.0, "unidad": "bar"}
caso_malo("3.36 Presión negativa", m, codigos.LAB_VALOR_FUERA_DE_DOMINIO)

m = con_spec(montaje_dos_volumenes(), bloque_id="out", variable="p",
             valor=2.0, unidad="bar")
caso_malo("3.37 Una presión por bloque que contradice la uniforme", m,
          codigos.LAB_ESPECIFICACION_EXCLUYENTE)


# =====================================================================
print("\n" + "=" * 76)
print("4. FUERA DEL DOMINIO: diagnóstico, no resultados a medias")
print("=" * 76)
# =====================================================================

enorme = con_spec(sin_spec(montaje_dos_volumenes(), "cv1", "T"),
                  bloque_id="heat1", variable="Q", valor=1e9, unidad="W")
re_ = resolver(enorme)
ee = errores_de(re_)
check("4.1 Un calor absurdo cae fuera del dominio y se dice",
      re_["estado"] != "resuelto" and ee
      and ee[0]["codigo"] == codigos.LAB_FUERA_DE_DOMINIO_TERMODINAMICO,
      ee[0]["codigo"] if ee else "se resolvió (!)")
check("4.2 Y la categoría es FÍSICA: no se arregla iterando más",
      ee and ee[0]["categoria"] == "fisica",
      ee[0]["categoria"] if ee else "")
check("4.3 Los valores parciales NO se presentan como resueltos",
      re_["estados_por_bloque"].get("medio", {}).get("T") is None
      and re_["convergencia"] is None,
      "T intermedia null y convergencia null")
check("4.4 Y el estado lo dice sin ambigüedad",
      re_["estado"] in ("invalido", "no_convergente"), re_["estado"])

# El caso bifásico: beta en (0,1), balances y energía coherentes.
bif = con_spec(sin_spec(montaje_dos_volumenes(), "cv1", "T"),
               bloque_id="heat1", variable="Q", valor=2.0e6, unidad="W")
rb = resolver(bif)
med = rb["estados_por_bloque"]["medio"]
check("4.5 Un caso bifásico se resuelve y declara su fase",
      rb["estado"] == "resuelto" and med["fase"] == "bifasico",
      f"T = {med['T']:.3f} K, fase {med['fase']}")
check("4.6 Con beta estrictamente dentro de (0,1)",
      0.0 < med["beta"] < 1.0, f"beta = {med['beta']:.6f}")
check("4.7 Y la h del estado coincide con h_entrada + Q/F",
      abs(med["h"] - (h300 + 2.0e6 / 100.0)) < 1e-6,
      f"{med['h']:.6f} frente a {h300 + 2.0e6 / 100.0:.6f} J/mol")
check("4.8 La fase bifásica concuerda con el flash independiente",
      fase_ref(med["T"]) == "bifasico", f"a {med['T']:.3f} K")
# En la laguna bifásica, el calor va casi todo a vapor y la T apenas sube:
# es el contraste que hace falsa cualquier Cp constante.
bif2 = con_spec(sin_spec(montaje_dos_volumenes(), "cv1", "T"),
                bloque_id="heat1", variable="Q", valor=3.0e6, unidad="W")
med2 = resolver(bif2)["estados_por_bloque"]["medio"]
dT_bifasico = med2["T"] - med["T"]
check("4.9 Un millón de watts más sube la T muy poco: va a calor latente",
      0.0 < dT_bifasico < 3.0,
      f"+1 MW → +{dT_bifasico:.3f} K (en la zona líquida fueron ~10 K por 0.15 MW)")

# Calor negativo: la convención de signo lo cubre y el motor lo advierte.
check("4.10 El segundo volumen RETIRA calor, y se avisa",
      valor(rb, "heat2.Q") < 0
      and any("RETIRA" in d["mensaje"] for d in rb["diagnosticos"]),
      f"Q₂ = {valor(rb, 'heat2.Q'):.1f} W")


# =====================================================================
print("\n" + "=" * 76)
print("5. DIAGNÓSTICOS Y METADATOS CORRESPONDEN AL CÁLCULO REAL")
print("=" * 76)
# =====================================================================

# Todos los ids citados tienen que EXISTIR en la peticion.
def ids_validos(montaje, resultado):
    bloques = {b["id"] for b in montaje["bloques"]}
    conexiones = {c["id"] for c in montaje["conexiones"]}
    variables = {v["id"] for v in resultado["variables"]}
    malos = []
    for d in resultado["diagnosticos"]:
        malos += [b for b in d["bloque_ids"] if b not in bloques]
        malos += [c for c in d["conexion_ids"] if c not in conexiones]
        malos += [v for v in d["variable_ids"] if v not in variables]
    return malos


montajes_muestra = {
    "caso de aceptación": montaje_dos_volumenes(),
    "un volumen": montaje_un_volumen(),
    "Q impuesto": caso2,
    "T y Q a la vez": ambos,
    "sin especificación térmica": ninguno,
    "fuera del dominio": enorme,
    "bifásico": bif,
}
malos_totales = {}
for nombre, mm in montajes_muestra.items():
    rr = resolver(mm)
    malos = ids_validos(mm, rr)
    if malos:
        malos_totales[nombre] = malos
check("5.1 Todos los ids citados por los diagnósticos existen en la petición",
      not malos_totales,
      f"{len(montajes_muestra)} montajes revisados"
      if not malos_totales else json.dumps(malos_totales)[:140])

# En /validar NADA esta ejecutado, porque nada se ejecuto.
v2 = validar(montaje_dos_volumenes())
check("5.2 En /validar ninguna ecuación está marcada como ejecutada",
      not any(e["ejecutada"] for e in v2["ecuaciones"]),
      f"{len(v2['ecuaciones'])} relaciones, 0 ejecutadas")
check("5.3 Ni hay residuos, ni convergencia, ni método inventado",
      all(e["residuo"] is None for e in v2["ecuaciones"])
      and v2["convergencia"] is None
      and v2["analisis"]["metodo"] is None,
      "no se ejecutó ningún algoritmo, así que no hay nada que declarar")
check("5.4 Pero el análisis estructural sí está: GL = 0",
      v2["analisis"]["grados_libertad"] == 0
      and v2["estado"] == "valido")
check("5.5 Y los valores calculados siguen en null",
      v2["estados_por_bloque"]["medio"]["h"] is None
      and v2["estados_por_bloque"]["out"]["T"] == 320.0,
      "la T impuesta sí; la h, que es un resultado, no")

# En /resolver, ejecutadas son las que de verdad corrieron.
ejecutadas = {e["id"] for e in r2["ecuaciones"] if e["ejecutada"]}
cuentan = {e["id"] for e in r2["ecuaciones"] if e["cuenta_como_ecuacion"]}
check("5.6 En /resolver se ejecutan las 12 ecuaciones del sistema",
      cuentan <= ejecutadas and len(cuentan) == 12,
      f"{len(cuentan)} cuentan, {len(ejecutadas)} ejecutadas "
      "(las verificaciones ejecutan además)")

no_ecuaciones = [e for e in r2["ecuaciones"] if not e["cuenta_como_ecuacion"]]
check("5.7 Las convenciones de signo NO cuentan como ecuación",
      all(not e["cuenta_como_ecuacion"]
          for e in r2["ecuaciones"] if e["tipo"] == "convencion"),
      f"{sum(1 for e in r2['ecuaciones'] if e['tipo'] == 'convencion')} convenciones")
check("5.8 Ni las especificaciones: son datos, no leyes",
      all(not e["cuenta_como_ecuacion"]
          for e in r2["ecuaciones"] if e["tipo"] == "condicion"))
# El cierre SÍ cuenta cuando determina la fracción que falta, y NO cuando
# se dieron todas: ahí comprueba en vez de calcular. El criterio no ha
# cambiado -- una relación cuenta si y solo si determina algo -- lo que
# cambió es que ahora las n fracciones son variables explícitas.
cierres = [e for e in r2["ecuaciones"] if e["tipo"] == "cierre"]
check("5.9 El cierre cuenta cuando determina la fracción que falta",
      len(cierres) == 3 and all(e["cuenta_como_ecuacion"] for e in cierres),
      f"{len(cierres)} cierres, todos determinan una fracción")

# Y con las n fracciones dadas, deja de contar.
m_todas = con_spec(montaje_dos_volumenes(), bloque_id="in", variable="x1",
                   valor=0.5, unidad="mol/mol")
r_todas = resolver(m_todas)
cierre_in = next(e for e in r_todas["ecuaciones"] if e["id"] == "in:cierre")
check("5.9b Y deja de contar si se dan todas: entonces comprueba, no calcula",
      r_todas["estado"] == "resuelto"
      and cierre_in["cuenta_como_ecuacion"] is False
      and cierre_in["residuo"] is not None
      and r_todas["analisis"]["grados_libertad"] == 0,
      f"residuo medido {cierre_in['residuo']:.1e}, GL = "
      f"{r_todas['analisis']['grados_libertad']}")

# Y una suma que no da 1 es un dato contradictorio.
m_mal = con_spec(montaje_dos_volumenes(), bloque_id="in", variable="x1",
                 valor=0.4, unidad="mol/mol")
e_mal = errores_de(resolver(m_mal))
check("5.9c Unas fracciones que no suman 1 se rechazan",
      e_mal and e_mal[0]["codigo"] == codigos.LAB_DATOS_COMPOSICION_INCOMPATIBLE,
      e_mal[0]["mensaje"][:95] if e_mal else "se aceptó (!)")
check("5.10 Ni la verificación global, que es suma de los otros balances",
      all(not e["cuenta_como_ecuacion"]
          for e in r2["ecuaciones"] if e["tipo"] == "verificacion"),
      "contarla regalaría una ecuación y los GL saldrían mal")

# Residuos: solo donde se midieron.
# Lo que el solver RESUELVE no trae residuo: se satisface por
# construcción. Lo que COMPRUEBA sí lo trae, y eso es una medida y no una
# fabricación -- la diferencia está en si la relación determinó algo o se
# limitó a verificarlo.
resueltas = [e for e in r2["ecuaciones"]
             if e["cuenta_como_ecuacion"]
             and e["alcance"] in ("algebraico_directo", "evaluacion_directa")]
check("5.11 Ninguna relación RESUELTA de evaluación directa trae residuo",
      resueltas and all(e["residuo"] is None for e in resueltas),
      f"{len(resueltas)} relaciones resueltas directamente, 0 residuos fabricados")

verificaciones = [e for e in r2["ecuaciones"] if e["tipo"] == "verificacion"]
check("5.11b Y las verificaciones SÍ lo traen: ahí el residuo se mide",
      verificaciones and all(e["residuo"] is not None for e in verificaciones),
      ", ".join(f"{e['id']}={e['residuo']:.1e}" for e in verificaciones))
check("5.12 Y el balance de energía explica por qué no lo tiene",
      "no hay residuo que medir"
      in next(e for e in r2["ecuaciones"] if e["id"] == "cv1:energia")["nota"],
      next(e for e in r2["ecuaciones"]
           if e["id"] == "cv1:energia")["nota"][:92])
check("5.13 En modo T no se declara convergencia: no hubo nada que converger",
      r2["convergencia"]["convergio"] is None
      and r2["convergencia"]["itera"] is False
      and r2["convergencia"]["iteraciones"] is None,
      r2["convergencia"]["motivo_sin_convergencia"][:88])
check("5.14 Y lo que se cuenta en modo Q son INVERSIONES, no iteraciones",
      rq["convergencia"]["inversiones_escalares"] == 1
      and rq["convergencia"]["iteraciones"] is None
      and "brentq" in rq["convergencia"]["motivo_sin_iteraciones"],
      rq["convergencia"]["motivo_sin_iteraciones"][:92])

# Términos descartados: cada uno con su supuesto.
energia_cv1 = next(e for e in r2["ecuaciones"] if e["id"] == "cv1:energia")
descartados = {t["supuesto"] for t in energia_cv1["terminos_descartados"]}
check("5.15 El balance de energía trae su forma general y su forma activa",
      "dE_{CV}}{dt}" in energia_cv1["latex_general"]
      and "dE" not in energia_cv1["latex_activo"],
      energia_cv1["latex_activo"])
check("5.16 Y dice qué término cayó por qué supuesto",
      descartados == {"estacionario", "sinTrabajo", "sinMovimiento"},
      ", ".join(sorted(descartados)))
check("5.17 El calor NO está entre los descartados: hay fuente y no es adiabático",
      "adiabatico" not in descartados
      and r"\dot Q_{3}" in energia_cv1["latex_activo"],
      "el término se conserva porque la pieza lo aporta")

m_adi = copy.deepcopy(montaje_dos_volumenes())
m_adi["supuestos"]["adiabatico"] = True
m_adi["bloques"] = [b for b in m_adi["bloques"] if not b["id"].startswith("heat")]
m_adi["conexiones"] = [c for c in m_adi["conexiones"] if c["id"] not in ("c2", "c5")]
v_adi = validar(m_adi)
e_adi = next(e for e in v_adi["ecuaciones"] if e["id"] == "cv1:energia")
check("5.18 Con adiabático y sin fuente, el calor SÍ figura como descartado",
      "adiabatico" in {t["supuesto"] for t in e_adi["terminos_descartados"]},
      e_adi["latex_activo"])

# Metadatos.
check("5.19 La respuesta trae modelo_id completo y la versión del motor",
      len(r2["modelo_id"]) == 64
      and r2["schema_version"] == lab.SCHEMA_VERSION
      and bool(r2["calculo"]["motor"]["version"]),
      f"modelo_id {r2['modelo_id'][:16]}…, motor {r2['calculo']['motor']['version']}")
check("5.20 Y las versiones del proveedor, que son su versión real",
      all(r2["calculo"]["proveedor_termodinamico"]["versiones"].get(p)
          for p in ("thermo", "chemicals", "fluids")),
      ", ".join(f"{p} {r2['calculo']['proveedor_termodinamico']['versiones'][p]}"
                for p in ("thermo", "chemicals")))

# El modelo_id identifica el MONTAJE; no cambia con el nombre de una pieza
# ni con el orden en que lleguen, y sí cambia con la física.
renombrado = copy.deepcopy(montaje_dos_volumenes())
for b in renombrado["bloques"]:
    b["nombre"] = "Otro nombre cualquiera"
desordenado = copy.deepcopy(montaje_dos_volumenes())
desordenado["bloques"].reverse()
desordenado["conexiones"].reverse()
desordenado["especificaciones"].reverse()
otra_T = copy.deepcopy(montaje_dos_volumenes())
for e in otra_T["especificaciones"]:
    if e["bloque_id"] == "cv1":
        e["valor"] = 311.0
check("5.21 modelo_id no cambia al renombrar una pieza",
      validar(renombrado)["modelo_id"] == r2["modelo_id"],
      "la etiqueta no es física")
check("5.22 Ni al reordenar bloques, conexiones y especificaciones",
      validar(desordenado)["modelo_id"] == r2["modelo_id"],
      "el orden de llegada no cambia el sistema; el de resolución lo decide el motor")
check("5.23 Pero sí al cambiar una temperatura impuesta",
      validar(otra_T)["modelo_id"] != r2["modelo_id"])
check("5.24 Y dos ejecuciones del mismo montaje tienen distinto identificador",
      resolver(montaje_dos_volumenes())["calculo"]["identificador"]
      != r2["calculo"]["identificador"],
      "modelo_id dice «mismo sistema»; identificador, «esta ejecución»")

# Las relaciones en LaTeX del cliente se ignoran como entrada ejecutable.
con_latex = copy.deepcopy(montaje_dos_volumenes())
con_latex["relaciones"] = [{"id": "x", "latex": r"\dot Q = 0", "titulo": "Falsa"}]
con_latex["solver"] = "lo que sea"
rl = resolver(con_latex)
check("5.25 El LaTeX que manda el cliente se IGNORA como entrada ejecutable",
      rl["estado"] == "resuelto" and abs(valor(rl, "heat1.Q") - Q1) < 1e-9 * abs(Q1),
      "una relación que dijera Q = 0 no cambia nada: el motor ensambla desde los tipos")
check("5.26 Y el motor emite su propio LaTeX",
      all(e["latex_general"] for e in rl["ecuaciones"]),
      f"{len(rl['ecuaciones'])} relaciones, todas con fórmula generada")

# El endpoint unico, y su lado seguro por omision.
ru = cliente.post("/laboratorio/calcular", json=montaje_dos_volumenes())
check("5.27 /calcular sin acción VALIDA, no resuelve",
      ru.status_code == 200 and ru.json()["estado"] == "valido"
      and ru.json()["convergencia"] is None,
      "el lado seguro es el que no gasta cálculo si no se lo pidieron")
mu = copy.deepcopy(montaje_dos_volumenes())
mu["accion"] = "resolver"
check("5.28 Y con acción explícita resuelve",
      cliente.post("/laboratorio/calcular", json=mu).json()["estado"] == "resuelto")

# Capacidades: lo admitido Y lo no admitido.
cap = cliente.get("/laboratorio/capacidades").json()
check("5.29 /capacidades declara también lo que NO soporta",
      len(cap["capacidades"]["no_soportado"]) >= 8,
      f"{len(cap['capacidades']['no_soportado'])} limitaciones declaradas")
check("5.30 Y avisa de que un Q local se lee en kW",
      "kW" in cap["capacidades"]["especificaciones"]["aviso"],
      "misma letra, dos escalas según de dónde venga")

# Serializacion estricta: un NaN o un float32 pasan Pydantic y revientan.
for nombre, rr in (("resuelto", r2), ("inválido", ra), ("bifásico", rb),
                   ("fuera de dominio", re_), ("validar", v2)):
    try:
        json.dumps(rr, allow_nan=False)
        ok, detalle = True, ""
    except (TypeError, ValueError) as e:
        ok, detalle = False, str(e)[:80]
    check(f"5.31 La respuesta «{nombre}» serializa a JSON estricto", ok, detalle)

# Una peticion que no tiene la FORMA de un montaje sí es 4xx.
mal_formada = cliente.post("/laboratorio/resolver",
                           json={"componentes": "no es una lista"})
check("5.32 Lo que no tiene forma de montaje sí devuelve 4xx",
      mal_formada.status_code == 422, str(mal_formada.status_code))
check("5.33 Pero un montaje imposible devuelve 200 con diagnósticos",
      cliente.post("/laboratorio/resolver", json=ambos).status_code == 200,
      "un 422 de Pydantic no lleva código estable ni id de bloque")


# =====================================================================
print("\n" + "=" * 76)
print("6. NO REGRESIÓN")
print("=" * 76)
# =====================================================================

# El calentador del laboratorio, tal como lo pide hoy el frontend.
peticion_termica = {
    "componentes": ["benzene", "toluene"],
    "corrientes": ["entrada", "salida"],
    "operaciones": [{
        "nombre": "calentador", "tipo": "intercambiador",
        "corrientes": {"entrada": "entrada", "salida": "salida"},
        "P_sistema": ATM, "con_balance_energia": True, "T_salida": 310.0,
    }],
    "valores": {"entrada.F": 100.0, "entrada.T": 300.0, "entrada.P": ATM,
                "entrada.x0": 0.5},
    "caudales_masicos": {},
}
rt = cliente.post("/diagrama/resolver", json=peticion_termica)
check("6.1 /diagrama/resolver sigue respondiendo al calentador",
      rt.status_code == 200 and rt.json()["completo"] is True,
      f"{rt.status_code}")
Q_diagrama = rt.json()["pool"]["calentador.Q"]
check("6.2 Y da EL MISMO calor que el laboratorio para el mismo problema",
      abs(Q_diagrama - Q1) < 1e-6 * abs(Q1),
      f"{Q_diagrama:.6f} W frente a {Q1:.6f} W — dos caminos, un número")

# El CSTR demostrativo, con su balance de energía desactivado.
peticion_cstr = {
    "componentes": ["isobutene", "methanol", "mtbe"],
    "corrientes": ["s1", "s2"],
    "operaciones": [{
        "nombre": "r1", "tipo": "reactor_cstr",
        "corrientes": {"entrada": "s1", "salida": "s2"},
        "P_sistema": ATM, "con_balance_energia": False, "con_cinetica": True,
        "modo_energia": "isotermo",
        "reaccion": {"nu": [-1, -1, 1], "A": 10000, "Ea": 45000,
                     "componente_referencia": 0},
    }],
    "valores": {"s1.F": 100.0, "s1.x0": 0.5, "s1.x1": 0.5, "s1.T": 330.0,
                "s1.P": ATM, "r1.T": 340.0, "r1.X": 0.6},
    "caudales_masicos": {},
}
rcstr = cliente.post("/diagrama/resolver", json=peticion_cstr)
check("6.3 El CSTR demostrativo sigue resolviendo",
      rcstr.status_code == 200 and rcstr.json()["pool"].get("r1.V") is not None,
      f"V = {rcstr.json()['pool'].get('r1.V')} m³" if rcstr.status_code == 200
      else str(rcstr.status_code))
check("6.4 Con su balance de energía desactivado, como estaba",
      rcstr.json()["pool"].get("r1.Q") is None,
      "no se activó nada por el camino: su acoplamiento sigue pendiente")

# El laboratorio no toca el contrato del diagrama.
for campo in ("completo", "pool", "diagnostico", "inconsistencias",
              "calculo", "diagnosticos", "convergencia"):
    check(f"6.5 /diagrama/resolver conserva «{campo}»", campo in rt.json())

check("6.6 Y /laboratorio no interfiere con la trazabilidad del diagrama",
      rt.json()["calculo"]["motor"]["version"]
      == r2["calculo"]["motor"]["version"],
      "los dos servicios declaran el mismo motor")

for ruta in ("/salud", "/unidades", "/modelos-termodinamicos", "/ejemplos"):
    check(f"6.7 {ruta} sigue en pie",
          cliente.get(ruta).status_code == 200)


# =====================================================================
print("\n" + "=" * 76)
print("7. LOS PRESETS SE REENVIAN AL ENDPOINT")
print("=" * 76)
# =====================================================================
# La idea que ya funciono en validar_api.py: encadenar en vez de inventar
# cargas. Los ejemplos de /laboratorio/ejemplos SON peticiones validas de
# /laboratorio/resolver, asi que se piden y se reenvian. Eso prueba dos
# endpoints de una, y prueba algo que una carga escrita a mano no puede
# probar: que el preset que la interfaz le ofrece al usuario de verdad se
# pueda resolver. Un preset roto es un fallo que se encuentra en el primer
# clic.

ejemplos = cliente.get("/laboratorio/ejemplos")
check("7.1 /laboratorio/ejemplos responde", ejemplos.status_code == 200,
      f"{len(ejemplos.json())} montajes")

for ejemplo in ejemplos.json():
    rr = cliente.post("/laboratorio/resolver", json=ejemplo["modelo"])
    estado = rr.json().get("estado") if rr.status_code == 200 else rr.status_code
    check(f"7.2 El preset «{ejemplo['id']}» da el estado que promete",
          rr.status_code == 200 and estado == ejemplo["estado_esperado"],
          f"{estado} (esperado {ejemplo['estado_esperado']})")

# Y uno de ellos espera 'invalido' A PROPOSITO: la interfaz necesita poder
# probar su camino de error contra un error de verdad, no contra uno
# inventado.
check("7.3 Hay un preset que se rechaza a propósito",
      any(e["estado_esperado"] == "invalido" for e in ejemplos.json()),
      "para que la interfaz pueda probar su camino de error")

check("7.4 Un id de ejemplo que no existe da 404 y LISTA los que sí",
      cliente.get("/laboratorio/ejemplos/no-existe").status_code == 404
      and "dos-volumenes-temperatura"
      in cliente.get("/laboratorio/ejemplos/no-existe").json()["detail"])

# El preset de un volumen tiene que dar el mismo numero que el servicio
# viejo para el mismo problema. Es el puente entre los dos adaptadores.
preset1 = cliente.get("/laboratorio/ejemplos/un-volumen-temperatura").json()
check("7.5 Y el preset de un volumen cuadra con /diagrama/resolver",
      abs(valor(cliente.post("/laboratorio/resolver",
                             json=preset1["modelo"]).json(), "heat1.Q")
          - Q_diagrama) < 1e-6 * abs(Q_diagrama),
      f"{Q_diagrama:.6f} W por los dos caminos")

# El caso bifasico del preset, que es el que saca al simulador de la fase
# liquida: se comprueba contra el flash independiente, no contra numeros
# escritos aqui.
rbif = cliente.post("/laboratorio/resolver",
                    json=cliente.get("/laboratorio/ejemplos/"
                                     "dos-volumenes-bifasico").json()["modelo"]).json()
med_p = rbif["estados_por_bloque"]["medio"]
check("7.6 El preset bifásico llega a la laguna, y el flash lo confirma",
      med_p["fase"] == "bifasico" and fase_ref(med_p["T"]) == "bifasico"
      and 0.0 < med_p["beta"] < 1.0,
      f"T = {med_p['T']:.3f} K, beta = {med_p['beta']:.4f}")


# =====================================================================
print("\n" + "=" * 76)
print("8. REACCION: estequiometria, fuentes brutas y conservacion")
print("=" * 76)
# =====================================================================
# Los numeros tampoco están escritos a mano aquí: la estequiometría y las
# tasas son datos, así que los avances y las fuentes se comparan contra lo
# que la estequiometría OBLIGA -- nu_i por el avance -- y la conservación
# de elementos y masa contra la matriz atómica que da 'thermo'.

# Dos sistemas reales, los dos con propiedades completas y balance
# elemental exacto:
#   n-butano  -> isobutano        isomerización, sum(nu) = 0
#   2 isobuteno <-> diisobutileno dimerización,  sum(nu) = -1
ISO = ["n-butane", "isobutane"]
DIM = ["isobutene", "diisobutylene"]
_prov_iso = ProveedorTermodinamico(ISO)
_prov_dim = ProveedorTermodinamico(DIM)


def montaje_reactor(componentes, reacciones, x_entrada, T_entrada=300.0,
                    T_salida=310.0, presion=5e5, F=100.0, extra=()):
    especificaciones = [
        {"bloque_id": "in", "variable": "F", "valor": F, "unidad": "mol/s"},
        {"bloque_id": "in", "variable": "T", "valor": T_entrada, "unidad": "K"},
        {"bloque_id": "rx", "variable": "T", "valor": T_salida, "unidad": "K"},
    ] + [
        {"bloque_id": "in", "variable": f"x{i}", "valor": v, "unidad": "mol/mol"}
        for i, v in enumerate(x_entrada[:-1])
    ] + list(extra)
    return {
        "version": 1,
        "componentes": list(componentes),
        "presion_sistema": {"valor": presion, "unidad": "Pa"},
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion"},
            {"id": "rx", "tipo": "reactor", "nombre": "Reactor"},
            {"id": "heat", "tipo": "calor", "nombre": "Aporte termico"},
            {"id": "out", "tipo": "salida", "nombre": "Salida"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "rx", "tipo": "materia"},
            {"id": "c2", "desde": "heat", "hacia": "rx", "tipo": "calor"},
            {"id": "c3", "desde": "rx", "hacia": "out", "tipo": "materia"},
        ],
        "supuestos": {"estacionario": True, "adiabatico": False,
                      "sinTrabajo": True, "sinReaccion": False,
                      "sinMovimiento": True},
        "especificaciones": especificaciones,
        "reacciones": reacciones,
    }


def flujos(resultado, bloque):
    """{componente: F_i} de una corriente."""
    return {e["componente"]: e["F_i"]
            for e in resultado["estados_por_bloque"][bloque]["por_especie"]}


def masa_de(proveedor, flujos_por_componente):
    """Caudal masico [g/s] a partir de los caudales molares."""
    return sum(float(c.MW) * flujos_por_componente[c.name if hasattr(c, "name") else n]
               for c, n in zip(proveedor.componentes, flujos_por_componente))


# --- 8.1 A -> B: la isomerizacion
r_iso = resolver(montaje_reactor(
    ISO, [{"id": "iso", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 20.0, "unidad": "mol/s"}}],
    [1.0, 0.0]))
check("8.1 A → B se resuelve con GL = 0",
      r_iso["estado"] == "resuelto" and r_iso["analisis"]["grados_libertad"] == 0,
      f"estado={r_iso['estado']}, GL={r_iso['analisis']['grados_libertad']}")

f_in, f_out = flujos(r_iso, "in"), flujos(r_iso, "out")
check("8.2 Consume de A exactamente el avance, y genera lo mismo de B",
      abs(f_in["n-butane"] - f_out["n-butane"] - 20.0) < 1e-12
      and abs(f_out["isobutane"] - f_in["isobutane"] - 20.0) < 1e-12,
      f"A: {f_in['n-butane']:.4f} → {f_out['n-butane']:.4f}; "
      f"B: {f_in['isobutane']:.4f} → {f_out['isobutane']:.4f}")

fuentes = r_iso["fuentes_por_volumen"]["rx"]["por_especie"]
por_comp = {e["componente"]: e for e in fuentes}
check("8.3 Y las fuentes lo dicen: G de B = C de A = el avance",
      por_comp["isobutane"]["generacion_bruta"] == 20.0
      and por_comp["n-butane"]["consumo_bruto"] == 20.0
      and por_comp["isobutane"]["consumo_bruto"] == 0.0
      and por_comp["n-butane"]["generacion_bruta"] == 0.0,
      "una reacción irreversible solo va en un sentido")
check("8.4 Con sum(nu) = 0, el caudal molar NO cambia",
      r_iso["estados_por_bloque"]["out"]["F"]
      == r_iso["estados_por_bloque"]["in"]["F"] == 100.0)

cons = r_iso["conservacion"]["rx"]
check("8.5 Elementos conservados, medidos sobre los caudales resueltos",
      cons["residuo_elemental_maximo"] < 1e-12,
      ", ".join(f"{e}: {d['entra']:.4f} → {d['sale']:.4f}"
                for e, d in cons["elementos"].items()))
check("8.6 Y la masa también",
      cons["masa"]["residuo_relativo"] < 1e-12,
      f"{cons['masa']['entra_g_s']:.6f} → {cons['masa']['sale_g_s']:.6f} g/s")

# El calor de reacción, contra el proveedor por el camino corto.
Hf_iso = np.asarray(_prov_iso.entalpias_formacion_liquido(), dtype=float)
dH_iso = float(np.array([-1.0, 1.0]) @ Hf_iso)
rxn_iso = r_iso["reacciones"][0]
check("8.7 El avance que reporta es el que se pidió",
      rxn_iso["avance_neto"] == 20.0 and rxn_iso["modo_tasa"] == "irreversible")
check("8.8 Y el calor de reacción sale de ν·Hf del proveedor",
      abs(dH_iso - (-9510.0)) < 1.0,
      f"ΔH = {dH_iso:.1f} J/mol (exotérmica: la isomerización libera calor)")

# --- 8.9 A -> 2B: el caudal molar cambia y la masa no
r_crack = resolver(montaje_reactor(
    DIM, [{"id": "crack", "bloque_id": "rx", "nu": [2, -1],
           "tasa": {"valor": 10.0, "unidad": "mol/s"}}],
    [0.0, 1.0], T_entrada=320.0, T_salida=330.0, presion=1e6))
check("8.9 A → 2B se resuelve",
      r_crack["estado"] == "resuelto"
      and r_crack["analisis"]["grados_libertad"] == 0, r_crack["estado"])
check("8.10 El caudal molar SÍ cambia: +10 mol/s por un avance de 10 con sum(ν)=+1",
      r_crack["estados_por_bloque"]["out"]["F"] == 110.0,
      f"100 → {r_crack['estados_por_bloque']['out']['F']} mol/s")
cc = r_crack["conservacion"]["rx"]
check("8.11 Y la masa NO cambia, aunque el caudal molar sí",
      cc["masa"]["residuo_relativo"] < 1e-12 and cc["caudal_molar"]["cambia"] is True,
      f"masa {cc['masa']['entra_g_s']:.4f} g/s constante; "
      f"molar {cc['caudal_molar']['entra_mol_s']:.0f} → "
      f"{cc['caudal_molar']['sale_mol_s']:.0f} mol/s")
fc = {e["componente"]: e for e in r_crack["fuentes_por_volumen"]["rx"]["por_especie"]}
check("8.12 Se generan 2 de B por cada A consumido",
      fc["isobutene"]["generacion_bruta"] == 20.0
      and fc["diisobutylene"]["consumo_bruto"] == 10.0,
      "ν = [+2, −1] con avance 10")

# --- 8.13 reversible: la dirección inversa intercambia producción y consumo
r_rev = resolver(montaje_reactor(
    DIM, [{"id": "dim", "bloque_id": "rx", "nu": [-2, 1],
           "tasa_directa": {"valor": 2.0, "unidad": "mol/s"},
           "tasa_inversa": {"valor": 8.0, "unidad": "mol/s"}}],
    [0.5, 0.5], T_entrada=320.0, T_salida=330.0, presion=1e6))
fr = {e["componente"]: e for e in r_rev["fuentes_por_volumen"]["rx"]["por_especie"]}
check("8.13 Reversible con la inversa dominante: el avance neto es negativo",
      r_rev["estado"] == "resuelto"
      and r_rev["reacciones"][0]["avance_neto"] == -6.0,
      f"ξ = r⁺ − r⁻ = 2 − 8 = {r_rev['reacciones'][0]['avance_neto']}")
check("8.14 Y la inversa intercambia producción y consumo correctamente",
      fr["isobutene"]["generacion_bruta"] == 16.0      # 2 × r⁻ = 2 × 8
      and fr["isobutene"]["consumo_bruto"] == 4.0      # 2 × r⁺ = 2 × 2
      and fr["diisobutylene"]["generacion_bruta"] == 2.0   # 1 × r⁺
      and fr["diisobutylene"]["consumo_bruto"] == 8.0,     # 1 × r⁻
      "el evento directo produce lo que tiene ν>0; el inverso, lo que tiene ν<0")
check("8.15 El neto es la diferencia de las brutas, especie por especie",
      all(abs(e["fuente_neta"]
              - (e["generacion_bruta"] - e["consumo_bruto"])) < 1e-12
          for e in fr.values()),
      "+12 y −6, que es ν·ξ")

# --- 8.16 EL CASO QUE EL CONTRATO EXIGE: equilibrio dinámico
#
# r⁺ = r⁻ > 0. La fuente neta es CERO y las brutas son POSITIVAS. Es el
# caso que desmonta la tentación de derivar las brutas del neto: un neto
# de cero es compatible con una reacción parada y con una funcionando a
# toda velocidad, y hay que distinguirlas.
r_eq = resolver(montaje_reactor(
    DIM, [{"id": "dim", "bloque_id": "rx", "nu": [-2, 1],
           "tasa_directa": {"valor": 5.0, "unidad": "mol/s"},
           "tasa_inversa": {"valor": 5.0, "unidad": "mol/s"}}],
    [0.5, 0.5], T_entrada=320.0, T_salida=330.0, presion=1e6))
fe = {e["componente"]: e for e in r_eq["fuentes_por_volumen"]["rx"]["por_especie"]}
check("8.16 Equilibrio r⁺ = r⁻ = 5: la fuente neta es CERO",
      r_eq["estado"] == "resuelto"
      and all(e["fuente_neta"] == 0.0 for e in fe.values())
      and r_eq["reacciones"][0]["avance_neto"] == 0.0)
check("8.17 Y las brutas son POSITIVAS: las moléculas no están quietas",
      fe["isobutene"]["generacion_bruta"] == 10.0
      and fe["isobutene"]["consumo_bruto"] == 10.0
      and fe["diisobutylene"]["generacion_bruta"] == 5.0
      and fe["diisobutylene"]["consumo_bruto"] == 5.0,
      "G = C = |ν|·r > 0 con neto cero")
check("8.18 La composición no cambia, pero la reacción está funcionando",
      flujos(r_eq, "in") == flujos(r_eq, "out")
      and r_eq["reacciones"][0]["brutas_disponibles"] is True,
      "misma salida que entrada, y 5 mol/s en cada dirección")
check("8.19 Y la descomposición del neto da cero en las dos casillas",
      all(e["descomposicion_neta"]["aparente_generacion"] == 0.0
          and e["descomposicion_neta"]["aparente_consumo"] == 0.0
          for e in fe.values()),
      "por eso NO es el intercambio bruto, y va en un campo aparte")
check("8.20 Con ξ = 0 el calor de reacción es cero, aunque haya 5 mol/s en cada sentido",
      abs(valor(r_eq, "heat.Q")
          - (r_eq["estados_por_bloque"]["out"]["F"]
             * r_eq["estados_por_bloque"]["out"]["h"]
             - r_eq["estados_por_bloque"]["in"]["F"]
             * r_eq["estados_por_bloque"]["in"]["h"])) < 1e-6,
      "el calor lo mueve el avance NETO, no las brutas")

# --- 8.21 solo el neto: las brutas NO están disponibles
r_net = resolver(montaje_reactor(
    DIM, [{"id": "dim", "bloque_id": "rx", "nu": [-2, 1],
           "tasa_neta": {"valor": 0.0, "unidad": "mol/s"}}],
    [0.5, 0.5], T_entrada=320.0, T_salida=330.0, presion=1e6))
fn = r_net["fuentes_por_volumen"]["rx"]
check("8.21 Con solo la tasa neta, las brutas salen NULL",
      r_net["estado"] == "resuelto"
      and fn["brutas_disponibles"] is False
      and all(e["generacion_bruta"] is None and e["consumo_bruto"] is None
              for e in fn["por_especie"]),
      "null, no cero: el dato no está")
# Dos motivos distintos y los dos necesarios: el del VOLUMEN explica que
# G_i es una suma con un término desconocido y nombra la reacción
# culpable; el de la REACCIÓN explica por qué la tasa neta no determina
# las brutas.
check("8.22 El motivo del volumen nombra la reacción y explica la suma",
      "SUMA" in (fn["motivo_brutas_no_disponibles"] or "")
      and "dim" in (fn["motivo_brutas_no_disponibles"] or ""),
      (fn["motivo_brutas_no_disponibles"] or "")[:100])
motivo_rxn = r_net["reacciones"][0]["motivo_brutas_no_disponibles"] or ""
check("8.22b Y el de la reacción explica que un neto de cero es ambiguo",
      "equilibrio dinamico" in motivo_rxn and "parada" in motivo_rxn,
      motivo_rxn[:110])
check("8.23 Nunca se rellenan con max(neto, 0)",
      r_net["reacciones"][0]["generacion_bruta"] is None
      if "generacion_bruta" in r_net["reacciones"][0] else True,
      "daría cero generación en una reacción que puede ir a toda velocidad")
check("8.24 Pero la fuente neta sí, y la descomposición del neto también",
      all(e["fuente_neta"] == 0.0
          and e["descomposicion_neta"]["aparente_generacion"] == 0.0
          for e in fn["por_especie"]),
      "lo que se sabe se da; lo que no, se dice que no")

# Y mezclar una reacción con brutas y otra sin ellas deja el volumen sin
# brutas: G_i es una suma y un término desconocido la hace desconocida.
r_mix = resolver(montaje_reactor(
    DIM, [{"id": "a", "bloque_id": "rx", "nu": [-2, 1],
           "tasa": {"valor": 3.0, "unidad": "mol/s"}},
          {"id": "b", "bloque_id": "rx", "nu": [2, -1],
           "tasa_neta": {"valor": 1.0, "unidad": "mol/s"}}],
    [0.5, 0.5], T_entrada=320.0, T_salida=330.0, presion=1e6))
check("8.25 Una reacción sin brutas deja al VOLUMEN sin brutas",
      r_mix["estado"] == "resuelto"
      and r_mix["fuentes_por_volumen"]["rx"]["brutas_disponibles"] is False
      and r_mix["reacciones"][0]["brutas_disponibles"] is True,
      "la reacción 'a' sí las tiene; la suma del volumen, no")
check("8.26 Y el motivo nombra la reacción culpable",
      "b" in (r_mix["fuentes_por_volumen"]["rx"]["motivo_brutas_no_disponibles"]
              or ""),
      "para saber qué declarar mejor")

# --- 8.27 la base: integrada frente a volumétrica
r_vol = resolver(montaje_reactor(
    ISO, [{"id": "iso", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 4.0, "unidad": "mol/(m3*s)"}}],
    [1.0, 0.0],
    extra=[{"bloque_id": "rx", "variable": "V", "valor": 5.0, "unidad": "m3"}]))
check("8.27 Una tasa volumétrica se integra con el volumen del reactor",
      r_vol["estado"] == "resuelto"
      and r_vol["reacciones"][0]["avance_neto"] == 20.0
      and r_vol["reacciones"][0]["base_tasa"] == "volumetrica",
      "4 mol/(m³·s) × 5 m³ = 20 mol/s")
check("8.28 Y da el MISMO resultado que la integrada equivalente",
      flujos(r_vol, "out") == flujos(r_iso, "out"),
      "dos formas de declarar el mismo dato")
check("8.29 La respuesta declara la base y el volumen usado",
      r_vol["reacciones"][0]["volumen_m3"] == 5.0
      and r_vol["reacciones"][0]["unidad_declarada"] == "mol/(m3*s)",
      "la unidad es la que decide la base, y queda escrita")

# --- 8.30 dos volúmenes con reacción, compartiendo la corriente
def montaje_dos_reactores():
    return {
        "version": 1,
        "componentes": list(DIM),
        "presion_sistema": {"valor": 1e6, "unidad": "Pa"},
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion"},
            {"id": "rx1", "tipo": "reactor", "nombre": "Primer reactor"},
            {"id": "h1", "tipo": "calor", "nombre": "Aporte 1"},
            {"id": "medio", "tipo": "corriente", "nombre": "Corriente compartida"},
            {"id": "rx2", "tipo": "reactor", "nombre": "Segundo reactor"},
            {"id": "h2", "tipo": "calor", "nombre": "Aporte 2"},
            {"id": "out", "tipo": "salida", "nombre": "Salida"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "rx1", "tipo": "materia"},
            {"id": "c2", "desde": "h1", "hacia": "rx1", "tipo": "calor"},
            {"id": "c3", "desde": "rx1", "hacia": "medio", "tipo": "materia"},
            {"id": "c4", "desde": "medio", "hacia": "rx2", "tipo": "materia"},
            {"id": "c5", "desde": "h2", "hacia": "rx2", "tipo": "calor"},
            {"id": "c6", "desde": "rx2", "hacia": "out", "tipo": "materia"},
        ],
        "supuestos": {"estacionario": True, "adiabatico": False,
                      "sinTrabajo": True, "sinReaccion": False,
                      "sinMovimiento": True},
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 320.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x0", "valor": 1.0, "unidad": "mol/mol"},
            {"bloque_id": "rx1", "variable": "T", "valor": 330.0, "unidad": "K"},
            {"bloque_id": "rx2", "variable": "T", "valor": 340.0, "unidad": "K"},
        ],
        "reacciones": [
            {"id": "dim1", "bloque_id": "rx1", "nu": [-2, 1],
             "tasa": {"valor": 10.0, "unidad": "mol/s"}},
            {"id": "dim2", "bloque_id": "rx2", "nu": [-2, 1],
             "tasa": {"valor": 15.0, "unidad": "mol/s"}},
        ],
    }


r_dos = resolver(montaje_dos_reactores())
check("8.30 Dos reactores en serie se resuelven",
      r_dos["estado"] == "resuelto"
      and r_dos["analisis"]["grados_libertad"] == 0, r_dos["estado"])
check("8.31 El caudal baja en los dos: 100 → 90 → 75",
      r_dos["estados_por_bloque"]["in"]["F"] == 100.0
      and r_dos["estados_por_bloque"]["medio"]["F"] == 90.0
      and r_dos["estados_por_bloque"]["out"]["F"] == 75.0,
      "un avance de 10 y otro de 15, con sum(ν) = −1")

compartidas_rxn = [v for v in r_dos["variables"] if v["compartida"]]
check("8.32 Y el estado intermedio NO se duplica: sigue siendo uno",
      len(compartidas_rxn) == 6
      and {v["id"] for v in compartidas_rxn}
      == {"medio.F", "medio.T", "medio.p", "medio.h", "medio.x0", "medio.x1"}
      and all(set(v["bloque_ids"]) == {"medio", "rx1", "rx2"}
              for v in compartidas_rxn),
      "seis variables compartidas por los dos reactores")
check("8.33 Sin variables repetidas para el mismo estado",
      len({v["id"] for v in r_dos["variables"]}) == len(r_dos["variables"]))

for bid in ("rx1", "rx2"):
    c = r_dos["conservacion"][bid]
    check(f"8.34 Elementos y masa conservados en {bid}",
          c["residuo_elemental_maximo"] < 1e-12
          and c["masa"]["residuo_relativo"] < 1e-12,
          f"masa {c['masa']['entra_g_s']:.6f} g/s constante")

# El cierre global CON reacción: la suma de los calores tiene que dar el
# transporte MÁS el calor de reacción de todo el montaje.
Hf_dim = np.asarray(_prov_dim.entalpias_formacion_liquido(), dtype=float)
dH_dim = float(np.array([-2.0, 1.0]) @ Hf_dim)
calor_rxn_total = 25.0 * dH_dim
suma_Q = sum(v["valor"] for v in r_dos["variables"] if v["magnitud"] == "Q")
e_in_dos = r_dos["estados_por_bloque"]["in"]
e_out_dos = r_dos["estados_por_bloque"]["out"]
transporte = (e_out_dos["F"] * e_out_dos["h"] - e_in_dos["F"] * e_in_dos["h"])
check("8.35 El cierre global incluye el calor de reacción de TODO el montaje",
      abs(suma_Q - (transporte + calor_rxn_total)) < 1e-6 * abs(suma_Q),
      f"ΣQ = {suma_Q:.3f} W = transporte {transporte:.3f} + reacción "
      f"{calor_rxn_total:.3f}")
check("8.36 Y el motor lo mide, con residuo por debajo de la tolerancia",
      r_dos["convergencia"]["cierre_global"]["residuo_relativo"] < 1e-12,
      f"residuo {r_dos['convergencia']['cierre_global']['residuo_relativo']:.2e}")
check("8.37 La dimerización es exotérmica, así que hay que RETIRAR calor",
      suma_Q < 0 and dH_dim < 0,
      f"ΔH = {dH_dim:.0f} J/mol, ΣQ = {suma_Q:.0f} W")

# --- 8.38 sin reacción recupera el balance no reactivo
sin_rxn = montaje_dos_reactores()
sin_rxn["reacciones"] = []
sin_rxn["supuestos"]["sinReaccion"] = True
for b in sin_rxn["bloques"]:
    if b["tipo"] == "reactor":
        b["tipo"] = "recipiente"
r_sin = resolver(sin_rxn)
check("8.38 Sin reacción se recupera el balance no reactivo",
      r_sin["estado"] == "resuelto"
      and r_sin["estados_por_bloque"]["out"]["F"] == 100.0
      and flujos(r_sin, "in") == flujos(r_sin, "out"),
      "F y composición se propagan sin cambio")
check("8.39 Y el término de reacción figura como DESCARTADO por el supuesto",
      any(t["supuesto"] == "sinReaccion"
          for e in r_sin["ecuaciones"] if e["id"] == "rx1:materia_especie_0"
          for t in e["terminos_descartados"])
      or any(t["supuesto"] == "sinReaccion"
             for e in r_sin["ecuaciones"]
             if e["id"].endswith(":materia_especie_0")
             for t in e["terminos_descartados"]),
      "elimina a la vez producción, consumo y cierres cinéticos")
check("8.40 Sin reacción no hay bloque de reacciones ni de fuentes",
      r_sin["reacciones"] == [] and r_sin["fuentes_por_volumen"] == {},
      "no se inventan ceros donde no hay química")

# --- 8.41 los rechazos
def caso_rxn(nombre, montaje, codigo_esperado):
    r = resolver(montaje)
    errs = errores_de(r)
    vistos = [d["codigo"] for d in errs]
    check(nombre, codigo_esperado in vistos,
          f"estado={r['estado']}, códigos={', '.join(vistos[:2]) or 'ninguno'}")
    return r


r = caso_rxn("8.41 Estequiometría que no conserva los elementos", montaje_reactor(
    ISO, [{"id": "mala", "bloque_id": "rx", "nu": [-1, 2],
           "tasa": {"valor": 1.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_ELEMENTOS_NO_CONSERVADOS)
check("8.42 Y el mensaje dice QUÉ elemento descuadra y en cuánto",
      "C:" in errores_de(r)[0]["mensaje"] and "H:" in errores_de(r)[0]["mensaje"],
      errores_de(r)[0]["mensaje"][:100])

caso_rxn("8.43 Una tasa bruta negativa", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": -5.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_TASA_NEGATIVA)

caso_rxn("8.44 Una reversible con una sola de las dos tasas", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa_directa": {"valor": 5.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_TASA_AMBIGUA)

caso_rxn("8.45 Dos formas de declarar la tasa a la vez", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/s"},
           "tasa_neta": {"valor": 1.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_TASA_AMBIGUA)

r = caso_rxn("8.46 Base volumétrica sin declarar el volumen", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/(m3*s)"}}], [1.0, 0.0]),
    codigos.LAB_FALTA_VOLUMEN_REACTOR)
check("8.47 No se supone 1 m³: se diagnostica",
      "no declara su volumen" in errores_de(r)[0]["mensaje"],
      errores_de(r)[0]["mensaje"][:95])

r = caso_rxn("8.48 Una tasa que consume más de lo que entra", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 500.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_CAUDAL_ESPECIE_NEGATIVO)
check("8.49 Y es FÍSICA: el avance no cabe en la alimentación",
      errores_de(r)[0]["categoria"] == "fisica"
      and r["estados_por_bloque"]["out"]["F"] is None,
      "no se presentan composiciones negativas como resultado")

caso_rxn("8.50 Cinética: se rechaza con nombre en vez de ignorarse", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1], "A": 1e4, "Ea": 45000.0}],
    [1.0, 0.0]),
    codigos.LAB_CINETICA_NO_SOPORTADA)

caso_rxn("8.51 Una ν sin reactivos y productos a la vez", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_ESTEQUIOMETRIA_INVALIDA)

caso_rxn("8.52 Una ν con el número de coeficientes equivocado", montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/s"}}], [1.0, 0.0]),
    codigos.LAB_ESTEQUIOMETRIA_INVALIDA)

mal_bloque = montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/s"}}], [1.0, 0.0])
for b in mal_bloque["bloques"]:
    if b["id"] == "rx":
        b["tipo"] = "recipiente"
caso_rxn("8.53 Una reacción en una pieza que no es un reactor", mal_bloque,
         codigos.LAB_REACCION_EN_NO_REACTOR)

con_supuesto = montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/s"}}], [1.0, 0.0])
con_supuesto["supuestos"]["sinReaccion"] = True
caso_rxn("8.54 Una reacción declarada con el supuesto que la anula", con_supuesto,
         codigos.LAB_SUPUESTO_INCOHERENTE)

sin_declarar = montaje_reactor(ISO, [], [1.0, 0.0])
caso_rxn("8.55 Un reactor que no declara su reacción", sin_declarar,
         codigos.LAB_SIN_REACCION_DECLARADA)

unidad_mala = montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa": {"valor": 5.0, "unidad": "mol/min"}}], [1.0, 0.0])
r = caso_rxn("8.56 Una unidad de tasa no admitida", unidad_mala,
             codigos.LAB_UNIDAD_INCOMPATIBLE)
check("8.57 Y el mensaje separa las integradas de las volumétricas",
      "Integradas" in errores_de(r)[0]["mensaje"]
      and "Volumetricas" in errores_de(r)[0]["mensaje"],
      "la unidad es la que declara la base")

bases_mezcladas = montaje_reactor(
    ISO, [{"id": "r", "bloque_id": "rx", "nu": [-1, 1],
           "tasa_directa": {"valor": 5.0, "unidad": "mol/s"},
           "tasa_inversa": {"valor": 1.0, "unidad": "mol/(m3*s)"}}], [1.0, 0.0],
    extra=[{"bloque_id": "rx", "variable": "V", "valor": 2.0, "unidad": "m3"}])
caso_rxn("8.58 Tasas directa e inversa en bases distintas", bases_mezcladas,
         codigos.LAB_UNIDAD_INCOMPATIBLE)

# --- 8.59 la referencia química y el calor de reacción
energia_rx = next(e for e in r_iso["ecuaciones"] if e["id"] == "rx:energia")
check("8.59 El balance reactivo lleva el calor de reacción EXPLÍCITO",
      "Delta H_{rxn" in energia_rx["latex_activo"],
      energia_rx["latex_activo"])
check("8.60 Y NO figura como descartado: la referencia es sensible",
      not any("formacion" in (t["termino"] or "")
              for t in energia_rx["terminos_descartados"]),
      "la referencia no incluye las entalpías de formación, así que el término va")
info_rxn = [d for d in r_iso["diagnosticos"]
            if d["codigo"] == codigos.LAB_INFO_CALOR_REACCION]
check("8.61 Se informa de cuánto aporta y de que no está duplicado",
      info_rxn and "no esta duplicado" in info_rxn[0]["mensaje"],
      info_rxn[0]["mensaje"][:110] if info_rxn else "no se informó")
cap_rxn = cliente.get("/laboratorio/capacidades").json()["capacidades"]
check("8.62 Las capacidades declaran si la referencia incluye formación",
      cap_rxn["referencias_entalpia"]["sensible_liquido_298.15K"]["incluye_formacion"]
      is False,
      "y de ahí cuelga la decisión de sumar el término, no de un comentario")
check("8.63 Y declaran la distinción bruto/neto",
      "equilibrio" in cap_rxn["reaccion"]["brutas_frente_a_neto"],
      "para que el cliente no derive las brutas del neto por su cuenta")

# --- 8.64 serialización y trazabilidad
for nombre, rr in (("isomerización", r_iso), ("equilibrio", r_eq),
                   ("dos reactores", r_dos), ("solo neta", r_net)):
    try:
        json.dumps(rr, allow_nan=False)
        ok, detalle = True, ""
    except (TypeError, ValueError) as e:
        ok, detalle = False, str(e)[:70]
    check(f"8.64 La respuesta «{nombre}» serializa a JSON estricto", ok, detalle)

otra_tasa = montaje_dos_reactores()
otra_tasa["reacciones"][0]["tasa"]["valor"] = 11.0
check("8.65 Cambiar una tasa cambia el modelo_id",
      validar(otra_tasa)["modelo_id"] != r_dos["modelo_id"],
      "la tasa es física: entra en la huella")
otro_nu = montaje_dos_reactores()
otro_nu["reacciones"][0]["nu"] = [-3.0, 1.5]
check("8.66 Y cambiar un coeficiente estequiométrico, también",
      validar(otro_nu)["modelo_id"] != r_dos["modelo_id"])
reordenadas = montaje_dos_reactores()
reordenadas["reacciones"].reverse()
check("8.67 Pero reordenar las reacciones NO lo cambia",
      validar(reordenadas)["modelo_id"] == r_dos["modelo_id"],
      "el orden en que lleguen no cambia la química")


print("\n" + "=" * 76)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
