"""
Validación del modelo común v0 (docs/contracts/common-model.md).

  1. Documentos de adimensionalización: documento -> modelo -> documento idéntico.
  2. Solicitudes de ensamblaje v2: solicitud -> modelo -> solicitud idéntica, y
     relaciones(modelo) igual (id, familia, propietario, orden) a las ecuaciones
     que publica el backend, en los ejemplos y en vivo con validar_v2.
  3. La termodinámica siempre presente: en el calentamiento etanol-agua el
     vapor aparece y el líquido desaparece con el mismo conjunto de relaciones.
  4. Rechazos: volumen sin cierre, referencias inexistentes, claves desconocidas.
  5. Ejemplos canónicos en docs/ejemplos/modelo-comun/ (la hoja del motor TS la
     escribe frontend/verificar_modelo_comun.mjs).

Ejecutar desde la raíz:  python tests/validar_modelo_comun.py
"""

import copy
import glob
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.modelo import (ErrorModelo, a_documento_adimensional, a_ensamblaje_v2, desde_documento_adimensional,
                         desde_ensamblaje_v2, leer_modelo_comun, relaciones)
from backend import motor_ensamblaje_v2 as v2

EJ = RAIZ / "docs" / "ejemplos"
SALIDA = EJ / "modelo-comun"
fallos, n = [], [0]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:400]) if detalle else ''}")


def clave(rs):
    return [(r["id"], r["familia"], r["propietarioId"]) for r in rs]


def rechaza(nombre, m, texto):
    try:
        leer_modelo_comun(m)
        check(nombre, False, "se aceptó")
    except ErrorModelo as e:
        check(nombre, texto in str(e), str(e))


# 1. Documentos de adimensionalización
docs = 0
for f in sorted(glob.glob(str(EJ / "adimensionalizacion-*-solicitud.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    if "documento" not in d:      # solicitudes de exploración: no llevan documento
        continue
    doc = d["documento"]
    m = desde_documento_adimensional(doc)
    try:
        leer_modelo_comun(m)
        ok = True
    except ErrorModelo as e:
        ok = str(e)
    check(f"{Path(f).name}: el modelo es válido", ok is True, ok)
    check(f"{Path(f).name}: documento -> modelo -> documento idéntico", a_documento_adimensional(m) == doc)
    check(f"{Path(f).name}: sin volúmenes no hay relaciones físicas", relaciones(m) == [])
    docs += 1
check("se recorrieron los 20 documentos de ejemplo", docs == 20, docs)

# 2. Ensamblajes v2
ens = 0
for f in sorted(glob.glob(str(EJ / "motor-v2" / "motor-ensamblaje-v2-*-peticion.json"))):
    nombre = Path(f).name
    sol = json.loads(Path(f).read_text(encoding="utf-8"))
    m = desde_ensamblaje_v2(sol)
    try:
        leer_modelo_comun(m)
        ok = True
    except ErrorModelo as e:
        ok = str(e)
    check(f"{nombre}: el modelo es válido", ok is True, ok)
    check(f"{nombre}: solicitud -> modelo -> solicitud idéntica", a_ensamblaje_v2(m) == sol)
    publicado = json.loads(Path(f.replace("peticion", "respuesta")).read_text(encoding="utf-8"))
    publicado = publicado.get("validacion", publicado)
    check(f"{nombre}: relaciones = ecuaciones del ejemplo publicado", clave(relaciones(m)) == clave(publicado["ecuaciones"]),
          (clave(relaciones(m)), clave(publicado["ecuaciones"])))
    vivo, _ = v2.validar_v2(copy.deepcopy(sol))
    check(f"{nombre}: relaciones = ecuaciones del backend en vivo", clave(relaciones(m)) == clave(vivo["ecuaciones"]),
          (clave(relaciones(m)), clave(vivo["ecuaciones"])))
    ens += 1
check("se recorrieron los 6 ensamblajes de ejemplo", ens == 6, ens)

# 3. Termodinámica siempre presente
cal = json.loads((EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-respuesta.json").read_text(encoding="utf-8"))
eventos = [e["codigo"] for e in cal["resultados"]["eventos"]]
m_cal = desde_ensamblaje_v2(json.loads((EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-peticion.json").read_text(encoding="utf-8")))
rel = relaciones(m_cal)
check("calentamiento: parte de un líquido, aparece el vapor y desaparece el líquido",
      eventos[:2] == ["aparicion_fase", "desaparicion_fase"], eventos)
check("calentamiento: el cierre PH y el reparto de equilibrio están en el modelo desde el principio",
      {"estado.A.energia", "estado.A.volumen", "equilibrio.A"} <= {r["id"] for r in rel})
check("calentamiento: el número de relaciones no depende del número de fases (es estructura, no estado)",
      clave(relaciones(m_cal)) == clave(cal["validacion"]["ecuaciones"]))

# 4. Rechazos
sin_cierre = copy.deepcopy(m_cal)
del sin_cierre["volumenes"][0]["termodinamica"]
rechaza("volumen sin cierre termodinámico: rechazado", sin_cierre, "faltan termodinamica")
cierre_vacio = copy.deepcopy(m_cal)
cierre_vacio["volumenes"][0]["termodinamica"] = {}
rechaza("cierre vacío: rechazado con el principio", cierre_vacio, "todo volumen declara su cierre")
supuesto_sin_motivo = copy.deepcopy(m_cal)
supuesto_sin_motivo["volumenes"][0]["termodinamica"] = {"tipo": "supuesto", "supuesto": "fase_no_evaluada", "motivo": " "}
rechaza("supuesto sin motivo: rechazado", supuesto_sin_motivo, "motivo")
paq = copy.deepcopy(m_cal)
paq["volumenes"][0]["termodinamica"]["paqueteId"] = "inexistente"
rechaza("paquete inexistente: rechazado", paq, "referencia inexistente (paquete")
dat = copy.deepcopy(m_cal)
dat["volumenes"][0]["frontera"]["presionId"] = "no.existe"
rechaza("dato inexistente: rechazado", dat, "referencia inexistente (dato")
clave_extra = copy.deepcopy(m_cal)
clave_extra["inventado"] = 1
rechaza("clave desconocida: rechazada", clave_extra, "campos desconocidos")
eq_sin_frontera = copy.deepcopy(m_cal)
eq_sin_frontera["volumenes"][0]["frontera"] = {"tipo": "sin_relacion"}
rechaza("equilibrio sin frontera UV/PH: rechazado", eq_sin_frontera, "cierre de equilibrio necesita")
mal_mat = desde_documento_adimensional(json.loads((EJ / "adimensionalizacion-estudio-calor-solicitud.json").read_text(encoding="utf-8"))["documento"])
mal_mat["matematico"]["ecuaciones"][0]["izquierda"] = {"tipo": "simbolo", "id": "no_declarado"}
rechaza("expresión con un símbolo no declarado: rechazada por el lector matemático común", mal_mat, "referencia")
motor_ajeno = copy.deepcopy(m_cal)
motor_ajeno["motores"]["graficas"] = {}
rechaza("configuración de un motor desconocido: rechazada", motor_ajeno, "valor no admitido")
supuesto = copy.deepcopy(m_cal)
supuesto["volumenes"][0]["termodinamica"] = {"tipo": "supuesto", "supuesto": "fase_no_evaluada", "motivo": "prueba"}
leer_modelo_comun(supuesto)
rs = relaciones(supuesto)
check("un supuesto explícito se acepta y aparece como relación supuesta, sin cierre ni equilibrio",
      any(r["id"] == "estado.A.supuesto" and r.get("supuesta") for r in rs) and not any(r["familia"] == "equilibrio" for r in rs))

# 5. Ejemplos canónicos
SALIDA.mkdir(exist_ok=True)
calor = desde_documento_adimensional(json.loads((EJ / "adimensionalizacion-estudio-calor-solicitud.json").read_text(encoding="utf-8"))["documento"])
for nombre, m in (("modelo-comun-documento-adimensional.json", calor), ("modelo-comun-ensamblaje-calentamiento.json", m_cal)):
    texto = json.dumps(m, ensure_ascii=False, indent=1) + "\n"
    ruta = SALIDA / nombre
    if "--regenerar" in sys.argv or not ruta.exists():
        ruta.write_text(texto, encoding="utf-8")
    check(f"ejemplo {nombre} vigente", ruta.read_text(encoding="utf-8") == texto)
rel_ruta = SALIDA / "modelo-comun-ensamblaje-calentamiento-relaciones.json"
texto = json.dumps(rel, ensure_ascii=False, indent=1) + "\n"
if "--regenerar" in sys.argv or not rel_ruta.exists():
    rel_ruta.write_text(texto, encoding="utf-8")
check("ejemplo de relaciones vigente", rel_ruta.read_text(encoding="utf-8") == texto)

print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nModelo común: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
