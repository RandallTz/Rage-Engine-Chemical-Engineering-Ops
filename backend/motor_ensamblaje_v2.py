"""
Revision 2 del protocolo de ensamblaje del motor (aditiva y discriminada por
`revision`). Tipos: docs/contratos/contratoEnsamblajeV2.ts. Documento:
docs/MOTOR_EQUILIBRIO_MULTIFASICO.md.

Lo que anade a la revision 1: catalogo de paquetes configurados, varios
volumenes con su paquete, politica, frontera e iniciales; corrientes internas
y exteriores con una sola identidad; intercambios termicos (impuesto o por
conductancia); paquetes de mezcla; evidencia de potenciales quimicos y
verificacion de la segunda ley cuando hay datos para ella.

Las rutas son las de la revision 1; backend/motor_ensamblaje.py despacha a
este modulo cuando revision == 2. La revision 1 se retiro (dec-r5-legacy-v1,
23 de octubre de 2026): recibe MOTOR_ENS_REVISION_RETIRADA.
"""

import functools
import hashlib
import json
import math

import numpy as np
import scipy

from backend import motor_ensamblaje as v1
from backend import motor_mezclas
from backend import motor_termodinamica as mt
from core import agua_iapws95 as agua
from core import ensamblaje_red as er
from core import expresiones_motor as ex
from core import mezclas as mz
from core import paquetes_volumen as pv
from core.dynamic_common import Funcion, Detencion

REVISION = 2
VOLUMENES_VERIFICADOS = 3
# Componentes DECLARADOS por volumen admitidos: el catalogo completo de especies de los paquetes de mezcla (7).
# La estabilidad y el reparto son de dimension general (core/mezclas._estabilidad_general para N >= 4); los
# tamanos realmente contrastados se publican aparte en `tamanos` (tests/validar_motor_n_componentes.py).
COMPONENTES_VERIFICADOS = 7
TAMANOS = {
    "cuenta": "componentes declarados por volumen (las especies con cantidad exactamente cero se retiran del "
              "problema activo y conservan su ID)",
    "componentesMaximosPorVolumen": 7,
    "fasesMaximas": 3,
    "contrastados": {
        "mezcla-ideal": {"estatico": [2, 3, 4, 5, 7], "dinamico": [2, 4, 5, 7]},
        "nrtl-chemsep": {"estatico": [2, 3, 4], "dinamico": [2, 4]},
        "nrtl-lle-agua-butanol": {"estatico": [2], "dinamico": [2]},
        "unifac-original-public": {"estatico": [2, 3, 4, 5, 7], "dinamico": [2, 4, 5]},
        "unifac-dortmund-public": {"estatico": [2, 3, 4, 5, 7], "dinamico": [2, 4]},
        "unifac-original-lle-public": {"estatico": [2, 4, 6], "dinamico": [2]},
        "agua-iapws95": {"estatico": [1], "dinamico": [1]}},
    "estabilidad": {"N <= 3": "malla especializada (binaria en logit, ternaria en el simplex) con refinamiento",
                    "N >= 4": "Michelsen multisemilla (vertices, ideal y Sobol con semilla 12345) con L-BFGS-B en "
                              "beta = 2 sqrt(W); caras del simplex incluidas",
                    "alcance": "busqueda finita: no demuestra el minimo global"},
    "presupuesto": "por estado: 3 fases como maximo; la busqueda de estabilidad usa N + 1 + 2^ceil(log2(8N)) "
                   "arranques; un estado con una fase competidora que no cabe en el tope se rechaza (tope_fases)"}

v1.UNIDADES.setdefault("cantidad", {"mol": (1, 0), "kmol": (1e3, 0)})
v1.UNIDADES.setdefault("conductancia", {"W/K": (1, 0), "kW/K": (1e3, 0)})
v1.UNIDAD_SI.setdefault("cantidad", "mol")
v1.UNIDAD_SI.setdefault("conductancia", "W/K")


# Nivel de evidencia de cada combinacion publicada (campo aditivo `evidencia`):
#   contrastada      - comparada con datos experimentales o referencias primarias en las pruebas
#   cualitativa      - el algoritmo la resuelve y certifica, pero los parametros no se ajustaron a ese
#                      tipo de equilibrio (p. ej. LL con parametros NRTL de VLE)
#   imposible_en_el_modelo - el modelo no puede producirla (solucion ideal: g^E = 0, nunca LL)
#   sin_modelo       - falta un modelo verificado para esa fase o region
#   excluida         - region retirada a proposito del dominio
def _comb(id_, nombre, publicada, evidencia, motivo):
    return {"id": id_, "nombre": nombre, "publicada": publicada, "evidencia": evidencia, "motivo": motivo}


@functools.lru_cache(maxsize=1)
def _pares_nrtl():
    with motor_mezclas.md.CARGA_DATOS:
        return _pares_nrtl_sin_cerrojo()


def _pares_nrtl_sin_cerrojo():
    from thermo.interaction_parameters import IPDB
    es = motor_mezclas.md.especies_disponibles()
    pares = []
    for a in range(len(es)):
        for b in range(a + 1, len(es)):
            if IPDB.has_ip_specific("ChemSep NRTL", [es[a], es[b]], "bij"):
                contrastado = {es[a], es[b]} == {"64-17-5", "7732-18-5"}
                pares.append({"componentesCAS": [es[a], es[b]], "procedencia": "ChemSep NRTL (thermo IPDB)",
                              "evidencia": "contrastada" if contrastado else "cualitativa",
                              "motivo": ("azeotropo a 1 atm frente a la literatura (tests/validar_motor_ensamblaje_v2.py "
                                         "seccion 2); ln gamma frente a thermo.nrtl") if contrastado else
                                        "parametros publicados sin contraste propio en estas pruebas"})
    return pares


# Evidencia medida de cada paquete UNIFAC (tests/validar_motor_unifac.py, docs/MOTOR_UNIFAC.md). Son
# PREDICCIONES por contribucion de grupos: nivel 'cualitativa' aunque algun punto coincida con la literatura.
EVIDENCIA_UNIFAC = {
    "unifac-original-public": (
        "prediccion por contribucion de grupos; azeotropo etanol-agua a 1 atm 78.04 C, x 0.896 frente a 78.15 C, "
        "0.894 de la literatura (docs/MOTOR_UNIFAC.md)",
        "prediccion con parametros de VLE: agua/1-butanol a 293-298 K dentro de 0.6 g/100 g de IUPAC-NIST SDS-15, "
        "con error creciente con T (agua en la fase organica 22.4 frente a 27.5 g/100 g a 353 K)"),
    "unifac-dortmund-public": (
        "prediccion por contribucion de grupos; azeotropo etanol-agua a 1 atm 78.13 C, x 0.899 frente a 78.15 C, "
        "0.894 de la literatura (docs/MOTOR_UNIFAC.md)",
        "prediccion pobre para agua/1-butanol: solubilidades mutuas 11.2 y 11.7 g/100 g a 293 K frente a 7.8 y 20.0 "
        "de IUPAC-NIST SDS-15 (docs/MOTOR_UNIFAC.md)"),
    "unifac-original-lle-public": (
        "sin contraste experimental en su dominio (10-40 C); Pxy etanol-agua a 298.15 K entre 3 y 8 % por debajo "
        "de UNIFAC original y sin el azeotropo que predicen la original y NRTL (docs/MOTOR_UNIFAC.md)",
        "tabla ajustada a ELL (Magnussen 1981); agua/1-butanol a 293 K: 6.9 y 21.6 g/100 g frente a 7.8 y 20.0 de "
        "IUPAC-NIST SDS-15 (prediccion: el par no se reajusto; docs/MOTOR_UNIFAC.md)"),
}


@functools.lru_cache(maxsize=None)
def _cobertura_unifac(mid):
    """Cobertura de contribucion de grupos del paquete sobre el catalogo: asignacion por especie e interacciones
    dirigidas entre todos los grupos principales presentes en el catalogo. No son pares moleculares."""
    from core import unifac
    variante = mz.PAQUETES[mid].liquido.split("_", 1)[1]
    t = unifac.tablas(variante)
    especies, sin_asignar = [], []
    for c in motor_mezclas.md.especies_disponibles():
        try:
            a = unifac.asignacion(c, variante)
            especies.append({"cas": c, "subgrupos": [{"id": k, "nombre": t["sub"][k][3], "grupoPrincipal": t["sub"][k][0],
                                                      "cuenta": n} for k, n in sorted(a.items())],
                             "procedencia": t["ident"]["fuente_asignaciones"]})
        except unifac.FaltaDatoUNIFAC:
            sin_asignar.append(c)
    principales = sorted({g["grupoPrincipal"] for e in especies for g in e["subgrupos"]})
    faltan = [[m, n] for m in principales for n in principales if m != n and (m, n) not in t["inter"]]
    return {"tipo": "contribucion_de_grupos", "variante": variante, "datos": dict(t["ident"]),
            "especies": especies, "especiesSinAsignacion": sin_asignar,
            "interaccionesDirigidasFaltantes": faltan,
            "nota": "cualquier subconjunto de 'especies' esta cubierto si 'interaccionesDirigidasFaltantes' esta vacia; "
                    "no se publican pares moleculares porque el modelo no los usa"}


def cobertura_unifac(mid):
    import copy as _copy
    return _copy.deepcopy(_cobertura_unifac(mid))


def capacidades_v2():
    publicable, motivo = mt._verificacion_modelo()
    paquetes = [{
        "modelo": dict(mt.MODELO_AGUA), "operaciones": ["TP", "PH", "UP", "UV", "TV"],
        "fases": ["liquido", "vapor", "fluido"],
        "combinaciones": [
            _comb("una_fase", "una fase (liquido, vapor o fluido supercritico)", True, "contrastada",
                  "H1: IAPWS-95 frente a sus valores publicados e IF97"),
            _comb("liquido_vapor", "liquido-vapor puro", True, "contrastada", "H3: coexistencia de Maxwell verificada"),
            _comb("solido", "solido (hielo Ih) en volumenes dinamicos", False, "sin_modelo",
                  "el hielo Ih existe solo como modelo estatico agua-iapws95-hielo-ih en /motor/termodinamica "
                  "(TP, PH, UP, UV, triple); no esta habilitado en volumenes dinamicos"),
            _comb("region_critica", "region critica", False, "excluida", "banda critica excluida (H1)")],
        "componentesCAS": [agua.CAS],
        "dominio": {"T": [agua.T_MIN, agua.T_MAX], "P": [agua.P_MIN, agua.P_MAX]},
        "limites": ["sin hielo: T >= 273.16 K y P <= 100 MPa", "banda critica excluida",
                    "coexistencia solo con Tsat <= 0.995 Tc"],
        "dinamica": True}]
    T_env = motor_mezclas.capacidades_mezcla()
    dominios = {c["id"]: c for c in T_env}
    for mid, ver in motor_mezclas.MODELOS.items():
        cap = dominios[mid]
        if mid == "mezcla-ideal":
            ll = _comb("liquido_liquido", "liquido-liquido y liquido-liquido-vapor", False, "imposible_en_el_modelo",
                       "la solucion ideal (g^E = 0) es siempre estable frente a separacion liquida: no es falta de datos")
            lv = _comb("liquido_vapor", "liquido-vapor", True, "contrastada",
                       "Raoult con Poynting frente a la expresion analitica (seccion 1)")
            pares = None
        elif mid == "nrtl-chemsep":
            ll = _comb("liquido_liquido", "liquido-liquido y liquido-liquido-vapor", True, "cualitativa",
                       "mismo algoritmo de estabilidad que el paquete LLE; los parametros ChemSep estan ajustados a "
                       "VLE: la solubilidad mutua predicha no esta contrastada")
            lv = _comb("liquido_vapor", "liquido-vapor", True, "cualitativa",
                       "contrastada solo para etanol-agua (azeotropo a 1 atm); la evidencia de cada par esta en `pares`")
            pares = _pares_nrtl()
        elif mid in EVIDENCIA_UNIFAC:
            lv_m, ll_m = EVIDENCIA_UNIFAC[mid]
            ll = _comb("liquido_liquido", "liquido-liquido y liquido-liquido-vapor", True, "cualitativa", ll_m)
            lv = _comb("liquido_vapor", "liquido-vapor", True, "cualitativa", lv_m)
            pares = None
        else:
            ll = _comb("liquido_liquido", "liquido-liquido y liquido-liquido-vapor", True, "contrastada",
                       "solubilidad mutua frente a IUPAC-NIST SDS vol. 15 en 293-373 K (ajuste y validacion), "
                       "meseta LLV por PH y UV (M4)")
            lv = _comb("liquido_vapor", "liquido-vapor", True, "cualitativa",
                       "los parametros se ajustaron solo a LLE; heteroazeotropo ~1.1 K sobre la literatura")
            pares = [{"componentesCAS": list(mz.NRTL_LLE_AGUA_BUTANOL["cas"]),
                      "procedencia": mz.NRTL_LLE_AGUA_BUTANOL["procedencia"], "evidencia": "contrastada",
                      "motivo": "LLE frente a IUPAC (incluidas temperaturas no usadas en el ajuste)"}]
        paq = {
            "modelo": {"id": mid, "version": ver}, "operaciones": ["TP", "PH", "UP", "UV", "TV"],
            "fases": ["liquido", "vapor"],
            "combinaciones": [
                _comb("una_fase", "una fase liquida o vapor", True, "contrastada", "M1/M2"),
                lv, ll,
                _comb("liquido_rigido_lleno", "liquido incompresible llenando un volumen rigido", False, "sin_modelo",
                      "presion indeterminada con liquido incompresible"),
                _comb("solido", "solido", False, "sin_modelo",
                      "sin modelo de solidos en mezclas (solubilidad, SLE, eutecticos)")],
            "componentesCAS": list(cap["componentesCAS"]),
            "dominio": dict(cap["dominio"]),
            "limites": [f"vapor ideal: P <= {mz.P_MAX:g} Pa", "liquido incompresible (v_L a 298.15 K)",
                        "T <= 0.9 Tc de cada especie"],
            "dinamica": True}
        if pares is not None:
            paq["pares"] = pares
        if mid.startswith("unifac-"):
            paq["coberturaGrupos"] = cobertura_unifac(mid)
        paquetes.append(paq)
    return {
        "revision": REVISION, "revisionesAdmitidas": [2], "disponible": publicable,
        "motivo": None if publicable else motivo,
        "paquetes": paquetes if publicable else [],
        "volumenesMaximos": VOLUMENES_VERIFICADOS, "componentesMaximos": COMPONENTES_VERIFICADOS,
        "tamanos": TAMANOS,
        "fronteras": ["rigida", "presion_prescrita"],
        "corrientes": {"mecanismos": ["convectivo"], "materia": ["por_componente", "total_desde_donante"],
                       "internas": True, "inversion": True, "entrePaquetes": "misma_referencia"},
        "intercambiosTermicos": ["impuesto", "conductancia"], "extracciones": ["mezcla_homogenea", "fase"],
        "segundaLey": True, "integradores": [{"id": "rk45", "nombre": "Dormand-Prince 5(4) con eventos de fase"}],
        "muestrasMaximas": v1.MUESTRAS_MAX,
        "noSoportado": [
            {"elemento": "transferencia selectiva", "motivo": "sin ley energetica propia"},
            {"elemento": "reaccion, electrolitos, membranas, nucleacion, capilaridad, momento", "motivo": "fuera de la primera ampliacion"},
            {"elemento": "corriente entre volumenes con paquetes de referencia distinta (agua IAPWS-95 frente a mezcla)",
             "motivo": "los modelos del agua difieren hasta ~700 J/mol entre estados: ninguna constante conserva la "
                       "energia; entre paquetes de mezcla (misma referencia) si se admite"},
            {"elemento": "presion con escalones", "motivo": "sin regla de salto"},
            {"elemento": "fase solida (hielo Ih) en volumenes dinamicos",
             "motivo": "agua-iapws95-hielo-ih es solo estatico (sin pruebas dinamicas); solidos en mezclas "
                       "(solubilidad, SLE, eutecticos) necesitan paquetes y datos propios"}],
    }


# ----------------------------------------------------------------------
def _comprobar_formulacion(diag, fm, fe, pol, tipo_fr, fr, base, pv_):
    if fm.get("vista") != "cantidad" or fm.get("cantidadVolumen") or fe.get("forma") != "total":
        diag("MOTOR_ENS_FORMA", "no_soportado", "Formas totales de cantidades y energía requeridas.",
             f"{base}/formulacionMateria/vista", propietario=pv_)
    if fe.get("modelo") == "u_lineal":
        diag("MOTOR_ENS_DOS_CIERRES", "conflicto", "La relación manual u(T) y el paquete determinarían el mismo "
             "estado.", f"{base}/formulacionEnergia/modelo", propietario=pv_)
    dens = (fm.get("reglasEstado") or {}).get("densidades") or []
    if fe.get("densidadConstante") or fm.get("densidadMediaConstante") or fm.get("densidadComunPuertos") or any(
            isinstance(x, dict) and x.get("constanciaTemporal") not in (None, "sin_restriccion") for x in dens):
        diag("MOTOR_ENS_DENSIDAD", "conflicto", "Densidad declarada constante frente a un paquete de densidad "
             "variable.", f"{base}/formulacionEnergia/densidadConstante", propietario=pv_)
    if pol and ((fe.get("monofasico") is True) != (pol.get("cantidad") == "monofasico")
                or (fe.get("sinCambioFase") is True) != (pol.get("cambioInterno") == "prohibido")):
        diag("MOTOR_ENS_POLITICA", "conflicto", "Hipótesis de fase de energía y política del volumen discrepan.",
             f"{base}/formulacionEnergia", propietario=pv_)
    fases_mat = (fm.get("reglasEstado") or {}).get("fases")
    if isinstance(fases_mat, dict) and pol and (
            (fases_mat.get("cantidad") == "monofasico") != (pol.get("cantidad") == "monofasico")):
        diag("MOTOR_ENS_POLITICA", "conflicto", "Hipótesis de fase de materia y política del volumen discrepan.",
             f"{base}/formulacionMateria/reglasEstado/fases", propietario=pv_)
    if not all(fe.get(k) is True for k in ("uniforme", "sinCinetica", "separarPresion", "sinTrabajoViscoso",
                                            "sinFuerzasVolumen", "sinFuenteVolumetrica")) or fe.get("trabajoTotalHeredado"):
        diag("MOTOR_ENS_TERMINOS", "no_soportado", "Estado uniforme y primera ley sin cinética, viscosos, fuerzas "
             "de volumen ni fuentes sin modelo.", f"{base}/formulacionEnergia", propietario=pv_)
    if fe.get("estacionario") or fe.get("sinAcumulacionTotal") or fm.get("sinAcumulacion"):
        diag("MOTOR_ENS_ESTACIONARIO", "no_soportado", "Contrato temporal.", f"{base}/formulacionEnergia",
             propietario=pv_)
    if (fm.get("campo") or {}).get("sinReaccion") is False or fm.get("generacionUniforme") or fm.get("consumoUniforme"):
        diag("MOTOR_ENS_FUENTES", "no_soportado", "Sin reacción ni fuentes de materia.", f"{base}/formulacionMateria",
             propietario=pv_)
    if tipo_fr == "rigida" and fm.get("fija") is False:
        diag("MOTOR_ENS_FRONTERA", "conflicto", "Frontera rígida con volumen móvil declarado.",
             f"{base}/formulacionMateria/fija", propietario=pv_)
    if tipo_fr == "presion_prescrita":
        if fe.get("presionUniforme") is not True:
            diag("MOTOR_ENS_FRONTERA", "conflicto", "Presión prescrita sin presión uniforme.",
                 f"{base}/formulacionEnergia/presionUniforme", propietario=pv_)
        if fm.get("fija") is True:
            diag("MOTOR_ENS_FRONTERA", "conflicto", "Presión prescrita con volumen fijo declarado.",
                 f"{base}/formulacionMateria/fija", propietario=pv_)
    pp = fe.get("presionPrescrita")
    if pp is False and tipo_fr == "presion_prescrita" or pp is True and (
            tipo_fr == "sin_relacion" or tipo_fr == "rigida" and fr.get("presionRestriccionId") is None):
        diag("MOTOR_ENS_PRESION_PRESCRITA", "conflicto",
             "formulacionEnergia.presionPrescrita no concuerda con la frontera declarada.",
             f"{base}/formulacionEnergia/presionPrescrita", propietario=pv_)


def validar_v2(cuerpo):
    diag = v1._Diag()
    sid = cuerpo.get("solicitudId") if isinstance(cuerpo.get("solicitudId"), str) else ""
    vacio_rec = {"estado": "no_evaluable", "analisis": "no_evaluable", "variables": None,
                 "ecuacionesIndependientes": None, "datosDefinidos": None, "datosFaltantes": None,
                 "inicialesFaltantes": None, "gradosLibertad": None}

    def respuesta(rec, variables, ecuaciones, ini, modelo_id=None):
        return {"revision": REVISION, "solicitudId": sid, "modeloId": modelo_id, "recuento": rec,
                "variables": variables, "ecuaciones": ecuaciones, "diagnosticos": diag.lista, "inicializacion": ini}
    ini_vacia = {"estado": "pendiente", "volumenes": {}}
    claves = {"revision", "solicitudId", "componentes", "paquetes", "volumenes", "corrientes", "intercambiosTermicos",
              "datos", "estudio", "derivacion"}
    for k in cuerpo:
        if k not in claves:
            diag("MOTOR_ENS_CAMPO_NO_ADMITIDO", "invalido", f"Campo «{k}» no admitido en la revisión 2.", f"/{k}")
    for k in claves - {"derivacion"}:
        if k not in cuerpo:
            diag("MOTOR_ENS_FALTA", "invalido", f"Falta «{k}».", f"/{k}")
    if not sid:
        diag("MOTOR_ENS_FORMA", "invalido", "solicitudId debe ser un texto no vacío.", "/solicitudId")
    if not all(isinstance(cuerpo.get(k), t) for k, t in (("componentes", list), ("paquetes", list),
                                                         ("volumenes", list), ("corrientes", list),
                                                         ("intercambiosTermicos", list), ("datos", dict),
                                                         ("estudio", dict))):
        diag("MOTOR_ENS_FORMA", "invalido", "Estructura incompatible con SolicitudEnsamblajeV2.", "/")
        return respuesta(dict(vacio_rec, motivo="Estructura ilegible."), [], [], ini_vacia), None
    lec = v1._Lector(cuerpo, diag)

    # --- catalogo de componentes ------------------------------------------------
    comps, cas_de, M_decl = [], {}, {}
    for i, c in enumerate(cuerpo["componentes"]):
        if not isinstance(c, dict) or isinstance(c.get("id"), bool) or not isinstance(c.get("id"), int) or c["id"] < 1:
            diag("MOTOR_ENS_FORMA", "invalido", "Componente con id entero positivo.", f"/componentes/{i}")
            continue
        cid = c["id"]
        if cid in cas_de:
            diag("MOTOR_ENS_FORMA", "invalido", f"ID de componente {cid} repetido.", f"/componentes/{i}")
            continue
        ident = c.get("identidadQuimica") or {}
        ruta = f"/componentes/{cid}/identidadQuimica"
        cas = ident.get("cas") if isinstance(ident, dict) else None
        if not cas and not (isinstance(ident, dict) and ident.get("proveedorId")):
            diag("MOTOR_ENS_IDENTIDAD", "incompleto", "Identidad química sin declarar.", ruta)
        elif isinstance(ident, dict) and ident.get("proveedorId"):
            diag("MOTOR_ENS_IDENTIDAD_NO_VERIFICABLE", "no_soportado", "Solo se verifica CAS.", ruta)
        elif not isinstance(cas, str) or not mt._cas_valido(cas):
            diag("MOTOR_ENS_CAS_INVALIDO", "invalido", f"{cas!r} no es un CAS válido.", ruta)
        else:
            if cas in cas_de.values():
                diag("MOTOR_ENS_IDENTIDAD_DUPLICADA", "invalido", f"CAS {cas} en dos componentes.", ruta)
            cas_de[cid] = cas
            comps.append(cid)
        mm = c.get("masaMolar")
        if isinstance(mm, dict) and isinstance(mm.get("cantidad"), dict) and mm["cantidad"].get("valor") is not None:
            q = mm["cantidad"]
            f = {"kg/mol": 1.0, "g/mol": 1e-3}.get(q.get("unidad"))
            if f is None or not isinstance(q.get("valor"), (int, float)) or not q["valor"] > 0:
                diag("MOTOR_ENS_MASA_MOLAR", "invalido", "Masa molar positiva en kg/mol o g/mol.",
                     f"/componentes/{cid}/masaMolar")
            else:
                M_decl[cid] = q["valor"] * f
    comp_idx = {cid: k for k, cid in enumerate(comps)}

    # --- paquetes -------------------------------------------------------------
    paquetes = {}
    sust_paq = {}           # F2.4: datosPuros por paquete configurado (se validan por volumen, con sus especies)
    for i, p in enumerate(cuerpo["paquetes"]):
        if not isinstance(p, dict) or not isinstance(p.get("id"), str) or p["id"] in paquetes:
            diag("MOTOR_ENS_PAQUETE", "invalido", "Paquete con id único.", f"/paquetes/{i}")
            continue
        mod = p.get("modelo")
        ok = isinstance(mod, dict) and (mod == mt.MODELO_AGUA or motor_mezclas.es_modelo_mezcla(mod))
        if not ok:
            diag("MOTOR_ENS_MODELO", "no_soportado", f"Modelo {mod!r} no publicado.", f"/paquetes/{i}/modelo")
        paquetes[p["id"]] = mod if ok else None
        if ok and p.get("datosPuros") is not None:
            sust_paq[p["id"]] = (p["datosPuros"], f"/paquetes/{i}/datosPuros")
        extra = sorted(set(p) - {"id", "modelo", "datosPuros"})
        if extra:
            diag("MOTOR_ENS_CAMPO_NO_ADMITIDO", "invalido", f"Campo «{extra[0]}» no admitido en un paquete.",
                 f"/paquetes/{i}/{extra[0]}")

    # --- estudio --------------------------------------------------------------
    est = cuerpo["estudio"]
    tfd = lec.dato(est.get("tiempoId"), ("tiempo",), "estudio", False, "/estudio/tiempoId", "estudio")
    if tfd is not None and tfd.estado == "ok":
        lec.comprobar_valores(tfd, None)
        lec.tf = tfd.funcion(0.0) if tfd.estado == "ok" else None
    mu_ = est.get("muestras")
    if isinstance(mu_, bool) or not isinstance(mu_, int) or not 2 <= mu_ <= v1.MUESTRAS_MAX:
        diag("MOTOR_ENS_ESTUDIO", "invalido", f"muestras: entero en [2, {v1.MUESTRAS_MAX}].", "/estudio/muestras",
             propietario="estudio")
    rtol = est.get("rtol")
    if not isinstance(rtol, (int, float)) or isinstance(rtol, bool) or not 1e-12 <= rtol <= 1e-2:
        diag("MOTOR_ENS_ESTUDIO", "invalido", "rtol en [1e-12, 1e-2].", "/estudio/rtol", propietario="estudio")
    atol = est.get("atol") or {}
    for k in ("cantidad", "energia"):
        v_ = atol.get(k) if isinstance(atol, dict) else None
        if not isinstance(v_, (int, float)) or isinstance(v_, bool) or not v_ > 0:
            diag("MOTOR_ENS_ESTUDIO", "invalido", f"atol.{k} positiva (mol o J).", f"/estudio/atol/{k}",
                 propietario="estudio")
    if est.get("metodoSolicitado") not in (None, "rk45"):
        diag("MOTOR_ENS_METODO", "no_soportado", "Integrador disponible: rk45.", "/estudio/metodoSolicitado",
             propietario="estudio")

    # --- volumenes --------------------------------------------------------------
    vols, vol_idx = [], {}
    if not cuerpo["volumenes"]:
        diag("MOTOR_ENS_VOLUMENES", "invalido", "Declara al menos un volumen.", "/volumenes")
    if len(cuerpo["volumenes"]) > VOLUMENES_VERIFICADOS:
        diag("MOTOR_ENS_VOLUMENES", "no_soportado", f"Verificado hasta {VOLUMENES_VERIFICADOS} volúmenes; no se omite "
             "ninguno.", "/volumenes")
    for i, v in enumerate(cuerpo["volumenes"]):
        base = f"/volumenes/{i}"
        if not isinstance(v, dict) or not isinstance(v.get("id"), str) or not v["id"] or v["id"] in vol_idx:
            diag("MOTOR_ENS_FORMA", "invalido", "Volumen con id único.", base)
            continue
        vid = v["id"]
        pv_ = f"volumen:{vid}"
        vc = v.get("componenteIds")
        if not isinstance(vc, list) or not vc or len(set(vc)) != len(vc) or any(c not in comp_idx for c in vc):
            diag("MOTOR_ENS_CATALOGO", "invalido", "componenteIds: IDs únicos del catálogo.", f"{base}/componenteIds",
                 propietario=pv_)
            continue
        if len(vc) > COMPONENTES_VERIFICADOS:
            diag("MOTOR_ENS_COMPONENTES", "no_soportado", f"Verificado hasta {COMPONENTES_VERIFICADOS} componentes "
                 "por volumen.", f"{base}/componenteIds", propietario=pv_)
        bal = v.get("balances") or {}
        if not (bal.get("materia") is True and bal.get("energia") is True) or bal.get("momento") is not False:
            diag("MOTOR_ENS_BALANCES", "no_soportado", "Materia y energía activas, momento desactivado.",
                 f"{base}/balances", propietario=pv_)
        pol = v.get("politica") if isinstance(v.get("politica"), dict) else {}
        if pol.get("cantidad") not in ("sin_restriccion", "monofasico") or pol.get("cambioInterno") not in (
                "permitido", "prohibido") or pol.get("evaluacion") != "equilibrio_estable":
            diag("MOTOR_ENS_POLITICA_INVALIDA", "invalido", "Política de fase inválida.", f"{base}/politica",
                 propietario=pv_)
        fr = v.get("frontera") or {}
        tipo_fr = fr.get("tipo")
        _comprobar_formulacion(diag, v.get("formulacionMateria") or {}, v.get("formulacionEnergia") or {}, pol,
                               tipo_fr, fr, base, pv_)
        paq, mod = None, paquetes.get(v.get("paqueteId"), "falta")
        if mod == "falta":
            diag("MOTOR_ENS_PAQUETE", "invalido", f"paqueteId {v.get('paqueteId')!r} no declarado.",
                 f"{base}/paqueteId", propietario=pv_)
        elif mod is not None and all(c in cas_de for c in vc):
            from core import catalogo
            sust, crudo = None, sust_paq.get(v.get("paqueteId"))
            try:
                if crudo is not None:
                    if mod == mt.MODELO_AGUA:
                        raise catalogo.SustitucionRechazada(
                            "SUSTITUCION_NO_ADMITIDA", crudo[1],
                            "IAPWS-95 es una formulacion completa sin datos de entrada sustituibles.")
                    # las sustituciones de un paquete valen para las especies que cada volumen declara
                    todas = [cas_de[c] for c in cas_de]
                    sust = catalogo.leer_sustituciones(crudo[0], crudo[1], todas)
                paq = pv.crear(mod, [cas_de[c] for c in vc], sust)
            except catalogo.SustitucionRechazada as x:
                diag(f"MOTOR_ENS_{x.codigo}", "invalido" if x.codigo == "SUSTITUCION_INVALIDA" else "no_soportado",
                     x.mensaje, x.ruta, propietario=pv_)
            except pv.PaqueteNoAplicable as x:
                diag("MOTOR_ENS_PAQUETE_NO_APLICABLE", "no_soportado", str(x), f"{base}/paqueteId", propietario=pv_)
            except mz.FaltaParametro as x:
                diag(f"MOTOR_ENS_{x.codigo}", "no_soportado", x.mensaje, f"{base}/paqueteId", propietario=pv_)
            if paq is not None:
                for c in vc:
                    if c in M_decl:
                        M = float(paq.M[vc.index(c)])
                        if abs(M_decl[c] - M) > 1e-7 * M:
                            diag("MOTOR_ENS_MASA_MOLAR_CONTRADICTORIA", "invalido",
                                 f"Masa molar declarada del componente {c} contradice la del paquete "
                                 f"{mod['id']} ({M * 1e3:.6f} g/mol).", f"/componentes/{c}/masaMolar")
        V = P = None
        if tipo_fr == "rigida":
            V = lec.dato(fr.get("datoId"), ("volumen",), "geometria", False, f"{base}/frontera/datoId", pv_)
            if fr.get("presionRestriccionId") is not None:
                diag("MOTOR_ENS_SOBREDETERMINADO", "conflicto", "Presión adicional en un volumen rígido: restricción "
                     "sobre la misma variable que fija el cierre UV.", f"{base}/frontera/presionRestriccionId",
                     [fr["presionRestriccionId"], f"volumen.{vid}.V"], pv_)
        elif tipo_fr == "presion_prescrita":
            P = lec.dato(fr.get("presionId"), ("presion",), "frontera", True, f"{base}/frontera/presionId", pv_)
        elif tipo_fr == "sin_relacion":
            diag("MOTOR_ENS_MECANICA", "incompleto", "Frontera sin relación mecánica.", f"{base}/frontera",
                 propietario=pv_)
        else:
            diag("MOTOR_ENS_FRONTERA", "invalido", "Frontera rigida | presion_prescrita | sin_relacion.",
                 f"{base}/frontera", propietario=pv_)
        ini = v.get("inicial") or {}
        cant = ini.get("cantidades") or {}
        n0 = {}
        b0 = cant.get("base")
        if b0 not in ("masica", "molar"):
            diag("MOTOR_ENS_BASE", "invalido", "Cantidades iniciales en base masica o molar.",
                 f"{base}/inicial/cantidades/base", propietario=pv_)
        else:
            ids0 = cant.get("datoIds") or {}
            for c in vc:
                if str(c) not in ids0:
                    diag("MOTOR_ENS_INICIAL", "incompleto", f"Falta la cantidad inicial del componente {c} (una "
                         "especie ausente se declara con cero).", f"{base}/inicial/cantidades/datoIds/{c}",
                         propietario=pv_)
                else:
                    n0[c] = lec.dato(ids0[str(c)], ("masa",) if b0 == "masica" else ("cantidad",), "inicial", False,
                                     f"{base}/inicial/cantidades/datoIds/{c}", pv_, signo="no_negativo")
        en = ini.get("energia") or {}
        E0 = None
        if en.get("tipo") not in ("U", "T"):
            diag("MOTOR_ENS_INICIAL", "invalido", "Energía inicial U o T.", f"{base}/inicial/energia", propietario=pv_)
        else:
            E0 = lec.dato(en.get("datoId"), ("energia",) if en["tipo"] == "U" else ("temperatura",), "inicial", False,
                          f"{base}/inicial/energia/datoId", pv_)
        vol_idx[vid] = len(vols)
        vols.append({"id": vid, "comp": vc, "pol": pol, "tipo": tipo_fr, "V": V, "P": P, "paq": paq, "mod": mod,
                     "n0": n0, "b0": b0, "E0": E0, "en": en.get("tipo"), "fe": v.get("formulacionEnergia") or {},
                     "intercambia_calor": False})

    # --- corrientes --------------------------------------------------------------
    cors, vistos = [], set()
    for i, c in enumerate(cuerpo["corrientes"]):
        base = f"/corrientes/{i}"
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"] or c["id"] in vistos:
            diag("MOTOR_ENS_FORMA", "invalido", "Corriente con id de texto único.", base)
            continue
        cid_ = c["id"]
        vistos.add(cid_)
        pc = f"corriente:{cid_}"
        de, ha = c.get("desde"), c.get("hasta")
        if de == ha or any(x is not None and x not in vol_idx for x in (de, ha)):
            diag("MOTOR_ENS_TOPOLOGIA", "invalido", "Extremos: dos volúmenes distintos o un volumen y el exterior.",
                 base, propietario=pc)
            continue
        cc = c.get("componenteIds")
        extremos = [vols[vol_idx[x]] for x in (de, ha) if x is not None]
        if not isinstance(cc, list) or not cc or any(x not in comp_idx for x in cc) or any(
                set(cc) - set(e_["comp"]) for e_ in extremos):
            diag("MOTOR_ENS_CATALOGO", "invalido", "Componentes de la corriente: subconjunto de los de cada extremo.",
                 f"{base}/componenteIds", propietario=pc)
            continue
        if c.get("mecanismo") == "selectivo":
            diag("MOTOR_ENS_SELECTIVO", "no_soportado", "Transferencia selectiva sin ley energética.", base,
                 propietario=pc)
        if de is not None and ha is not None:
            m1, m2 = vols[vol_idx[de]]["mod"], vols[vol_idx[ha]]["mod"]
            p1, p2 = vols[vol_idx[de]]["paq"], vols[vol_idx[ha]]["paq"]
            r1 = p1.referencia["id"] if p1 is not None else None
            r2 = p2.referencia["id"] if p2 is not None else None
            # F2.5: paquetes distintos con la MISMA referencia por especie (todos los de mezcla: gas ideal a
            # 298.15 K y 1 bar con h = s = 0, y la misma M del registro) transportan h y s coherentes; se admiten.
            # Agua IAPWS-95 frente a mezcla: h_mez - h_IAPWS del agua varia ~700 J/mol entre estados (los modelos
            # difieren), asi que una constante no conserva la energia: se rechaza (docs/MOTOR_CATALOGO_PROPIEDADES.md).
            if m1 != m2 and (r1 is None or r1 != r2):
                diag("MOTOR_ENS_REFERENCIAS_INCOMPATIBLES", "no_soportado",
                     f"La corriente une volúmenes con paquetes de referencia distinta ({m1}: {r1} / {m2}: {r2}): "
                     "no hay una conversión que conserve energía y entropía entre esos modelos.", base, propietario=pc)
        mat = c.get("materia") or {}
        bm = mat.get("base")
        mag = ("caudal_molar",) if bm == "molar" else ("caudal",) if bm == "masica" else ()
        F, Fc, modo = None, None, mat.get("modo")
        if not mag:
            diag("MOTOR_ENS_BASE", "invalido", "Base masica o molar.", f"{base}/materia/base", propietario=pc)
        elif modo == "total_desde_donante":
            F = lec.dato(mat.get("caudalId"), mag, "frontera", True, f"{base}/materia/caudalId", pc)
        elif modo == "por_componente":
            ids_ = mat.get("caudalIds") or {}
            if set(ids_) != {str(x) for x in cc}:
                diag("MOTOR_ENS_CATALOGO", "invalido", "Un caudal por componente de la corriente.",
                     f"{base}/materia/caudalIds", propietario=pc)
            else:
                Fc = {x: lec.dato(ids_[str(x)], mag, "frontera", True, f"{base}/materia/caudalIds/{x}", pc) for x in cc}
            if len(cc) > 1 and any(len(e_["comp"]) > 1 for e_ in extremos):
                diag("MOTOR_ENS_COMPOSICION_SOBREESPECIFICADA", "conflicto",
                     "Caudales por componente con un volumen de varias especies en un extremo: la composición "
                     "transportada la fija la fase o mezcla extraída; declarar cada caudal añade restricciones "
                     "contradictorias. Usa total_desde_donante.", f"{base}/materia/modo", propietario=pc)
        else:
            diag("MOTOR_ENS_MATERIA", "invalido", "Modo por_componente o total_desde_donante.",
                 f"{base}/materia/modo", propietario=pc)
        # ¿puede entrar materia desde el exterior?
        ext_extremo = "desde" if de is None else "hasta" if ha is None else None
        fs = [F] if F is not None else list((Fc or {}).values())
        constantes = all(d is not None and d.estado == "ok" and not d.depende_t for d in fs) and fs

        def signo_cte():
            vals = [d.funcion(0.0) for d in fs]
            return 1 if all(x > 0 for x in vals) else -1 if all(x < 0 for x in vals) else 0
        entra_ext = ext_extremo is not None and (not constantes or (signo_cte() > 0) == (ext_extremo == "desde")
                                                 and signo_cte() != 0)
        ext = c.get("estadoExterior")
        Text = Pext = None
        x_ext = None
        continuidad = None
        if entra_ext and not isinstance(ext, dict):
            diag("MOTOR_ENS_DONANTE_PENDIENTE", "incompleto", "Puede entrar materia desde el exterior: declara su "
                 "estado TP (y su composición si hay varias especies).", f"{base}/estadoExterior",
                 [f"corriente.{cid_}.Text", f"corriente.{cid_}.Pext"], pc)
        if isinstance(ext, dict):
            if ext_extremo is None:
                diag("MOTOR_ENS_DONANTE", "invalido", "Una corriente interna no tiene estado exterior.",
                     f"{base}/estadoExterior", propietario=pc)
            Text = lec.dato(ext.get("temperaturaId"), ("temperatura",), "frontera", True,
                            f"{base}/estadoExterior/temperaturaId", pc)
            pres = ext.get("presion") or {}
            if pres.get("tipo") == "dato":
                Pext = lec.dato(pres.get("datoId"), ("presion",), "frontera", True,
                                f"{base}/estadoExterior/presion/datoId", pc)
            elif pres.get("tipo") == "continuidad":
                if pres.get("volumenId") not in (de, ha) or pres.get("volumenId") is None:
                    diag("MOTOR_ENS_DONANTE", "invalido", "Continuidad con un volumen que no es extremo.",
                         f"{base}/estadoExterior/presion/volumenId", propietario=pc)
                else:
                    continuidad = vol_idx[pres["volumenId"]]
                if pres.get("restriccionAdicionalId") is not None:
                    diag("MOTOR_ENS_P_DUPLICADA", "conflicto", "Continuidad y dato de presión a la vez.",
                         f"{base}/estadoExterior/presion/restriccionAdicionalId",
                         [pres["restriccionAdicionalId"]], pc)
            else:
                diag("MOTOR_ENS_DONANTE", "invalido", "Presión exterior dato o continuidad.",
                     f"{base}/estadoExterior/presion", propietario=pc)
            comp_e = ext.get("composicion")
            if modo == "total_desde_donante" and (len(cc) > 1 or comp_e is not None):
                fr_ = (comp_e or {}).get("fracciones") if isinstance(comp_e, dict) else None
                if not isinstance(fr_, dict) or set(fr_) != {str(x) for x in cc} or any(
                        not isinstance(fr_[str(x)], (int, float)) or fr_[str(x)] < 0 for x in cc) or abs(
                        sum(fr_[str(x)] for x in cc) - 1) > 1e-10 or comp_e.get("base") not in ("masica", "molar"):
                    diag("MOTOR_ENS_COMPOSICION_EXTERIOR", "incompleto" if comp_e is None else "invalido",
                         "Composición del donante exterior: fracciones de cada componente de la corriente que sumen 1.",
                         f"{base}/estadoExterior/composicion", propietario=pc)
                else:
                    x_ext = (comp_e["base"], {x: float(fr_[str(x)]) for x in cc})
            elif modo == "total_desde_donante":
                x_ext = ("molar", {cc[0]: 1.0})
        extr = {}
        for vid_, e_ in (c.get("extraccion") or {}).items():
            if vid_ not in (de, ha):
                diag("MOTOR_ENS_EXTRACCION", "invalido", f"Extracción para {vid_!r}, que no es extremo.",
                     f"{base}/extraccion/{vid_}", propietario=pc)
                continue
            if e_ == {"tipo": "mezcla_homogenea"}:
                extr[vol_idx[vid_]] = ("mezcla_homogenea", None, None)
            elif isinstance(e_, dict) and e_.get("tipo") == "fase" and e_.get("fase") in ("liquido", "vapor", "fluido") \
                    and e_.get("criterio") in (None, "mayor_densidad", "menor_densidad") and set(e_) <= {
                    "tipo", "fase", "criterio"}:
                extr[vol_idx[vid_]] = ("fase", e_["fase"], e_.get("criterio"))
            else:
                diag("MOTOR_ENS_EXTRACCION", "invalido", "Extracción mezcla_homogenea o fase (con criterio opcional).",
                     f"{base}/extraccion/{vid_}", propietario=pc)
        for x in (de, ha):
            if x is None or vol_idx[x] in extr:
                continue
            vv = vols[vol_idx[x]]
            puede_extraer = not constantes or (signo_cte() > 0) == (x == de) and signo_cte() != 0
            if vv["pol"].get("cantidad") != "monofasico" and puede_extraer:
                diag("MOTOR_ENS_EXTRACCION", "incompleto", f"Con varias fases posibles en {x}, declara cómo se "
                     "extrae por esta corriente.", f"{base}/extraccion/{x}", propietario=pc)
        cors.append({"id": cid_, "de": de, "ha": ha, "comp": cc, "modo": modo, "base": bm, "F": F, "Fc": Fc,
                     "Text": Text, "Pext": Pext, "cont": continuidad, "x_ext": x_ext, "extr": extr,
                     "entra_ext": entra_ext})

    # --- intercambios termicos ---------------------------------------------------
    ints, vistos_q = [], set()
    for i, q in enumerate(cuerpo["intercambiosTermicos"]):
        base = f"/intercambiosTermicos/{i}"
        if not isinstance(q, dict) or not isinstance(q.get("id"), str) or q["id"] in vistos_q:
            diag("MOTOR_ENS_FORMA", "invalido", "Intercambio con id único.", base)
            continue
        vistos_q.add(q["id"])
        pq = f"calor:{q['id']}"
        de, ha = q.get("desde"), q.get("hasta")
        if de == ha or any(x is not None and x not in vol_idx for x in (de, ha)):
            diag("MOTOR_ENS_TOPOLOGIA", "invalido", "Extremos del intercambio inválidos.", base, propietario=pq)
            continue
        for x in (de, ha):
            if x is not None:
                vols[vol_idx[x]]["intercambia_calor"] = True
        ley = q.get("ley") or {}
        Qd = G = Te = None
        if ley.get("tipo") == "impuesto":
            Qd = lec.dato(ley.get("potenciaId"), ("potencia",), "frontera", True, f"{base}/ley/potenciaId", pq)
        elif ley.get("tipo") == "conductancia":
            G = lec.dato(ley.get("conductanciaId"), ("conductancia",), "parametro", False,
                         f"{base}/ley/conductanciaId", pq)
            if de is None or ha is None:
                Te = lec.dato(ley.get("temperaturaExteriorId"), ("temperatura",), "frontera", True,
                              f"{base}/ley/temperaturaExteriorId", pq)
        else:
            diag("MOTOR_ENS_LEY_CALOR", "invalido", "Ley impuesto o conductancia.", f"{base}/ley", propietario=pq)
        Tf = None
        if q.get("temperaturaFronteraId") is not None:
            Tf = lec.dato(q["temperaturaFronteraId"], ("temperatura",), "frontera", True,
                          f"{base}/temperaturaFronteraId", pq)
        ints.append({"id": q["id"], "de": de, "ha": ha, "ley": ley.get("tipo"), "Q": Qd, "G": G, "Te": Te, "Tf": Tf})
    for vv in vols:
        ad = vv["fe"].get("adiabatico")
        if ad is True and vv["intercambia_calor"]:
            diag("MOTOR_ENS_Q_ADIABATICO", "conflicto", f"Volumen {vv['id']} adiabático con un intercambio térmico.",
                 "/intercambiosTermicos", propietario=f"volumen:{vv['id']}")
        if ad is not True and not vv["intercambia_calor"]:
            diag("MOTOR_ENS_Q_PENDIENTE", "incompleto", f"Volumen {vv['id']} no adiabático sin intercambio térmico: "
                 "un calor ausente no es cero.", "/intercambiosTermicos", propietario=f"volumen:{vv['id']}")

    for d in lec.referenciados.values():
        if d is not tfd:
            lec.comprobar_valores(d, lec.tf)
    for q in ints:
        if q["G"] is not None and q["G"].estado == "ok" and not q["G"].funcion(0.0) > 0:
            p_, r_ = q["G"].origen
            diag("MOTOR_ENS_FUERA_DE_MAGNITUD", "invalido", "Conductancia positiva.", r_, [q["G"].id], p_)

    variables, ecuaciones, recuento = _ensamblar(vols, cors, ints, lec, comps)
    ini = {"estado": "pendiente", "volumenes": {}}
    modelo_id = None if diag.hay("invalido") else _modelo_id(vols, cors, ints, cas_de, paquetes)
    ctx = None
    if not diag.hay("invalido", "no_soportado"):
        ini, listos = _inicializar(vols, diag)
        if listos:
            ctx = {"vols": vols, "cors": cors, "ints": ints, "comps": comps, "cas": cas_de, "est": est, "lec": lec,
                   "ini": listos}
    return respuesta(recuento, variables, ecuaciones, ini, modelo_id), ctx


# ----------------------------------------------------------------------
def _ensamblar(vols, cors, ints, lec, comps):
    vars_, ecs, incid = [], [], []
    pend = set()

    def var(id_, prop, mag, uni, papel, dato=None, comp=None, fase=None):
        v = {"id": id_, "propietarioId": prop, "magnitud": mag, "unidadSI": uni, "papel": papel}
        if comp is not None:
            v["componenteId"] = comp
        if fase is not None:
            v["faseId"] = fase
        if dato is not None:
            v["datoId"] = dato.id
        vars_.append(v)
        return id_

    def dvar(id_, prop, d, mag, uni):
        falta = not (d is not None and d.estado == "ok")
        var(id_, prop, mag, uni, "algebraica" if falta else ("parametro" if mag == "conductancia" else "dato"), d)
        if falta:
            pend.add(id_)
        return id_, falta

    def ec(id_, prop, fam, vids, inc, latex, uni, dim, tipo, rel, tid=None, paquete=None):
        e = {"id": id_, "propietarioId": prop, "familia": fam, "variableIds": list(vids), "incognitas": sorted(inc),
             "dimension": dim, "latex": latex, "unidadResiduo": uni,
             "procedencia": {"tipo": tipo, "relacion": rel}}
        if tid:
            e["procedencia"]["transferenciaId"] = tid
        if paquete:
            e["procedencia"]["paquete"] = dict(paquete)
        ecs.append(e)
        if fam != "verificacion":
            incid.append((id_, set(inc)))
    vol_ids = [v["id"] for v in vols]
    for v in vols:
        p_ = f"volumen:{v['id']}"
        pref = f"volumen.{v['id']}"
        for c in v["comp"]:
            var(f"{pref}.n.{c}", p_, "cantidad", "mol", "diferencial", comp=c)
        rig = v["tipo"] == "rigida"
        E = var(f"{pref}.{'U' if rig else 'H'}", p_, "energia", "J", "diferencial")
        var(f"{pref}.T", p_, "temperatura", "K", "algebraica")
        if rig:
            var(f"{pref}.P", p_, "presion", "Pa", "algebraica")
            Vv, _ = dvar(f"{pref}.V", p_, v["V"], "volumen", "m3")
            inc_c = {f"{pref}.T", f"{pref}.P", f"{pref}.fases"} | ({Vv} & pend)
        else:
            var(f"{pref}.U", p_, "energia", "J", "algebraica")
            var(f"{pref}.V", p_, "volumen", "m3", "algebraica")
            var(f"{pref}.W", p_, "energia", "J", "algebraica")
            Pv, _ = dvar(f"{pref}.P", p_, v["P"], "presion", "Pa")
            inc_c = {f"{pref}.T", f"{pref}.V", f"{pref}.fases"} | ({Pv} & pend)
        var(f"{pref}.fases", p_, "reparto_de_fases", "mol", "algebraica")
        mod = v["mod"]
        nombre = "UV" if rig else "PH"
        ec(f"estado.{v['id']}.energia", p_, "estado", [E, f"{pref}.T"], inc_c,
           r"U=\sum_\alpha n^\alpha\bar u^\alpha(T,P,x^\alpha)" if rig else r"H=\sum_\alpha n^\alpha\bar h^\alpha(T,P,x^\alpha)",
           "J", "energia", "constitutiva", f"cierre {nombre} del paquete", paquete=mod)
        ec(f"estado.{v['id']}.volumen", p_, "estado", [f"{pref}.V"], inc_c,
           r"V=\sum_\alpha n^\alpha\bar v^\alpha(T,P,x^\alpha)", "m3", "volumen", "constitutiva",
           f"cierre {nombre} del paquete", paquete=mod)
        ec(f"equilibrio.{v['id']}", p_, "equilibrio", [f"{pref}.fases", f"{pref}.T"], inc_c,
           r"\mu_i^\alpha=\mu_i^\beta,\ \sum_\alpha n_i^\alpha=n_i,\ \mathrm{tm}\ge0\ (\text{estabilidad})",
           "J/mol", "potencial quimico", "constitutiva",
           "reparto de equilibrio: " + ("máximo de S a (U, V, n)" if rig else "estable en G a la (T, P) obtenida"),
           paquete=mod)
        if not rig:
            ec(f"estado.{v['id']}.U", p_, "estado", [f"{pref}.U", E, f"{pref}.P", f"{pref}.V"], {f"{pref}.U"},
               r"U=H-PV", "J", "energia", "constitutiva", "transformación H = U + PV")
            ec(f"mecanica.{v['id']}.trabajo", p_, "mecanica", [f"{pref}.W"], {f"{pref}.W"},
               r"\dot W=P\,\frac{dV}{dt}\ \text{(derivada total de }V(H,P,n))", "W", "potencia", "verificacion",
               "comprobación de la forma en U")
    terms = {(v["id"], c): [] for v in vols for c in v["comp"]}
    termsE = {v["id"]: [] for v in vols}
    incM = {(v["id"], c): {f"d/dt volumen.{v['id']}.n.{c}"} for v in vols for c in v["comp"]}
    incE = {v["id"]: {f"d/dt volumen.{v['id']}.{'U' if v['tipo'] == 'rigida' else 'H'}"} for v in vols}
    for s in cors:
        pc = f"corriente:{s['id']}"
        cp = f"corriente.{s['id']}"
        fs = [s["F"]] if s["F"] is not None else list((s["Fc"] or {}).values())
        f_ids = []
        for k, d in enumerate(fs):
            fid, falta = dvar(f"{cp}.F" + ("" if s["F"] is not None else f".{s['comp'][k]}"), pc, d,
                              "caudal" if s["base"] == "masica" else "caudal_molar",
                              "kg/s" if s["base"] == "masica" else "mol/s")
            f_ids.append(fid)
        nd = var(f"{cp}.ndot", pc, "caudal_molar", "mol/s", "algebraica")
        h = var(f"{cp}.h", pc, "entalpia_molar", "J/mol", "algebraica")
        x = var(f"{cp}.x", pc, "composicion", "1", "algebraica")
        inc_d = {h, x}
        if s["Text"] is not None or s["entra_ext"]:
            t_id, falta = dvar(f"{cp}.Text", pc, s["Text"], "temperatura", "K")
            if falta:
                inc_d.add(t_id)
            if s["cont"] is not None:
                pd = var(f"{cp}.P", pc, "presion", "Pa", "algebraica")
                inc_d.add(pd)
                ec(f"mecanica.continuidad.{s['id']}", pc, "mecanica", [pd], {pd}, r"P_{\mathrm{donante}}=P_{\mathrm{vol}}",
                   "Pa", "presion", "restriccion", "continuidad de presión declarada")
            else:
                p_id, falta = dvar(f"{cp}.Pext", pc, s["Pext"], "presion", "Pa")
                if falta:
                    inc_d.add(p_id)
        fases_ext = [f"volumen.{v}.fases" for v in (s["de"], s["ha"]) if v]
        ec(f"transferencia.{s['id']}.composicion", pc, "transferencia", [x] + fases_ext, {x},
           r"x_s=\begin{cases}x\ \text{de la fase o mezcla extraída del volumen de origen}\\ x_{ext}\ \text{declarada (exterior)}\end{cases}",
           "1", "composicion", "constitutiva", "donante según el signo actual del caudal")
        ec(f"transferencia.{s['id']}.entalpia", pc, "transferencia", [h] + fases_ext, inc_d - {x},
           r"\bar h_s=\begin{cases}\bar h\ \text{de lo extraído}\\ \bar h_{eq}(T_{ext},P_{donante},x_{ext})\end{cases}",
           "J/mol", "entalpia molar", "constitutiva", "donante según el signo actual del caudal")
        ec(f"transferencia.{s['id']}.caudal", pc, "transferencia", [nd] + f_ids, {nd} | ({*f_ids} & pend),
           r"\dot n_s=|F_s|/\bar M(x_s)" if s["base"] == "masica" else r"\dot n_s=|F_s|", "mol/s", "caudal molar",
           "transferencia", "conversión de base con las masas molares del paquete")
        for v_, sg in ((s["de"], "-"), (s["ha"], "+")):
            if v_ is None:
                continue
            for c in s["comp"]:
                terms[(v_, c)].append(f"{sg}\\dot n_{{{s['id']}}}x_{{{s['id']},{c}}}")
                incM[(v_, c)] |= {nd} | ({*f_ids} & pend)
            termsE[v_].append(f"{sg}\\dot n_{{{s['id']}}}\\bar h_{{{s['id']}}}")
            incE[v_] |= {nd, h}
    for q in ints:
        pq = f"calor:{q['id']}"
        if q["ley"] == "impuesto":
            qid, falta = dvar(f"calor.{q['id']}.Q", pq, q["Q"], "potencia", "W")
            incq = {qid} & pend
        else:
            qid = var(f"calor.{q['id']}.Q", pq, "potencia", "W", "algebraica")
            gid, falta = dvar(f"calor.{q['id']}.G", pq, q["G"], "conductancia", "W/K")
            extra = set()
            if q["de"] is None or q["ha"] is None:
                te, f2 = dvar(f"calor.{q['id']}.Text", pq, q["Te"], "temperatura", "K")
                if f2:
                    extra.add(te)
            ec(f"transferencia.calor.{q['id']}", pq, "transferencia", [qid, gid], {qid} | ({gid} & pend) | extra,
               r"\dot Q=G\,(T_{\mathrm{desde}}-T_{\mathrm{hasta}})", "W", "potencia", "transferencia",
               "ley de conductancia declarada", tid=f"calor:{q['id']}")
            incq = {qid}
        for v_, sg in ((q["de"], "-"), (q["ha"], "+")):
            if v_ is not None:
                termsE[v_].append(f"{sg}\\dot Q_{{{q['id']}}}")
                incE[v_] |= incq
        if q["Tf"] is not None:
            dvar(f"calor.{q['id']}.Tfrontera", pq, q["Tf"], "temperatura", "K")
    for v in vols:
        p_ = f"volumen:{v['id']}"
        rig = v["tipo"] == "rigida"
        for c in v["comp"]:
            rhs = " ".join(terms[(v["id"], c)]) or "0"
            ec(f"materia.{v['id']}.{c}", p_, "materia", [f"volumen.{v['id']}.n.{c}"], incM[(v["id"], c)],
               rf"\frac{{dn_{{{c}}}}}{{dt}}={rhs}", "mol/s", "cantidad/tiempo", "balance",
               "conservación por componente sin reacción")
        rhs = " ".join(termsE[v["id"]]) or "0"
        if rig:
            ec(f"energia.{v['id']}", p_, "energia", [f"volumen.{v['id']}.U"], incE[v["id"]],
               rf"\frac{{dU}}{{dt}}={rhs},\ \frac{{dV}}{{dt}}=0", "W", "potencia", "balance", "primera ley, frontera rígida")
        else:
            ec(f"energia.{v['id']}", p_, "energia", [f"volumen.{v['id']}.H"], incE[v["id"]] | {f"volumen.{v['id']}.V"},
               rf"\frac{{dH}}{{dt}}={rhs}+V\frac{{dP}}{{dt}}", "W", "potencia", "balance",
               "primera ley con H = U + PV a presión prescrita")
    for c in comps:
        if any(c in v["comp"] for v in vols):
            ec(f"global.materia.{c}", "red", "verificacion", [f"volumen.{v['id']}.n.{c}" for v in vols if c in v["comp"]],
               set(), r"\sum_v n_{v,%d}-n^0_{%d}=\int\dot n^{ext}_{%d}\,dt" % (c, c, c), "mol", "cantidad", "verificacion",
               "cancelación de transferencias internas por identidad")
    ec("global.energia", "red", "verificacion", [f"volumen.{v['id']}.U" for v in vols], set(),
       r"\sum_v U_v-U^0=\int(\dot E^{ext}+\dot Q^{ext})\,dt-\sum_v W_v", "J", "energia", "verificacion",
       "conservación global de energía")
    incognitas = set().union(*[s for _, s in incid]) if incid else set()
    pareja = v1._emparejar(incid, pend)
    sin_ec = sorted(incognitas - set(pareja.values()))
    sobrantes = [e for e, _ in incid if e not in pareja]
    datos_ref = list(lec.referenciados.values())
    ini_falt = sum(1 for v in vols for d in list(v["n0"].values()) + [v["E0"]] if d is None or d.estado != "ok") + \
        sum(len(set(v["comp"]) - set(v["n0"])) for v in vols)
    if any(d.estado == "invalido" for d in datos_ref):
        estado = "no_evaluable"
    elif sobrantes:
        estado = "conflicto"
    elif sin_ec or any(d.estado == "pendiente" for d in datos_ref) or ini_falt:
        estado = "incompleto"
    else:
        estado = "listo"
    rec = {"estado": estado, "analisis": "estructural", "variables": len(vars_),
           "ecuacionesIndependientes": len(pareja) if estado != "no_evaluable" else None,
           "datosDefinidos": sum(1 for d in datos_ref if d.estado == "ok"),
           "datosFaltantes": sum(1 for d in datos_ref if d.estado == "pendiente"), "inicialesFaltantes": ini_falt,
           "gradosLibertad": (len(incognitas) - len(incid)) if estado not in ("conflicto", "no_evaluable") else None,
           "motivo": ((f"Incógnitas sin ecuación: {', '.join(sin_ec)}. " if sin_ec else "")
                      + (f"Ecuaciones sin incógnita propia: {', '.join(sobrantes)}. " if sobrantes else "")
                      + "Emparejamiento máximo entre ecuaciones (balances por componente y energía de cada volumen, "
                        "transferencias, cierres y equilibrio de cada paquete) e incógnitas (derivadas de los estados, "
                        "algebraicas y datos pendientes). Las verificaciones globales no se cuentan como ecuaciones.")}
    return vars_, ecs, rec


def _canon(d):
    return v1._canon(d)


def _modelo_id(vols, cors, ints, cas_de, paquetes):
    ident = {
        "componentes": {str(k): v for k, v in sorted(cas_de.items())},
        "volumenes": [[v["id"], v["comp"], v["mod"], v["pol"], v["tipo"], _canon(v["V"]), _canon(v["P"]),
                       v["b0"], {str(c): _canon(d) for c, d in v["n0"].items()}, v["en"], _canon(v["E0"])]
                      for v in sorted(vols, key=lambda v: v["id"])],
        "corrientes": [[s["id"], s["de"], s["ha"], s["comp"], s["modo"], s["base"], _canon(s["F"]),
                        {str(k): _canon(d) for k, d in (s["Fc"] or {}).items()}, _canon(s["Text"]), _canon(s["Pext"]),
                        s["cont"], s["x_ext"], sorted((str(k), list(map(str, v))) for k, v in s["extr"].items())]
                       for s in sorted(cors, key=lambda s: s["id"])],
        "intercambios": [[q["id"], q["de"], q["ha"], q["ley"], _canon(q["Q"]), _canon(q["G"]), _canon(q["Te"]),
                          _canon(q["Tf"])] for q in sorted(ints, key=lambda q: q["id"])],
    }
    return "ens2-" + hashlib.sha256(json.dumps(ident, sort_keys=True, default=str).encode()).hexdigest()[:32]


# ----------------------------------------------------------------------
# Estados, potenciales e inicializacion
# ----------------------------------------------------------------------
def _ids_fases(e):
    return [f.id for f in e.fases]


def potenciales(e, paq, ids):
    """PotencialesV2 de un EstadoMezcla del paquete."""
    fases = []
    for f in e.fases:
        mu = {}
        for k, i in enumerate(ids):
            mu[str(i)] = float(f.mu[k]) if (f.x[k] > 0 and math.isfinite(f.mu[k])) else None
        fases.append({"faseId": f.id, "mu": mu})
    res = e.verificaciones.get("equilibrio", (None,))[0]
    tm = (e.estabilidad or {}).get("tm_min")
    # `base` y `unidad` describen mu (molar, J/mol). G, A y S son EXTENSIVOS del volumen (J, J, J/K):
    # `unidades` lo declara de forma explicita (erratum aditivo; los valores no cambian).
    return {"base": "molar", "unidad": "J/mol", "unidades": {"mu": "J/mol", "G": "J", "A": "J", "S": "J/K"},
            "referencia": dict(paq.referencia),
            "estadoEstandar": ("sustancia pura con la referencia IAPWS-95 (mu = g molar del agua)"
                               if isinstance(paq, pv.PaqueteAgua) else
                               "gas ideal puro de cada especie a T y P0 = 1e5 Pa, con h = s = 0 a 298.15 K"),
            "T": e.T, "P": e.P, "G": float(e.G), "A": float(e.G - e.P * e.V), "S": float(e.S),
            "fases": fases, "residuoIgualdadMu": float(res) if res is not None and math.isfinite(res) else None,
            "candidatasExploradas": list((e.estabilidad or {}).get("candidatas") or []),
            "tmMinimo": float(tm) if tm is not None and math.isfinite(tm) else None,
            "metodo": ("TPD de sustancia pura sobre las ramas monofásicas de IAPWS-95" if isinstance(paq, pv.PaqueteAgua)
                       else "mínimo de G con prueba de distancia al plano tangente frente a vapor y líquido")}


def evaluacion_volumen(paq, e, ids, pol):
    """EvaluacionEstado certificada (revision 1) del estado de un volumen."""
    if isinstance(paq, pv.PaqueteAgua):
        n = float(np.sum(e.n))
        m = n * agua.M
        r = v1.evaluar_certificado("UV", ids[0], agua.CAS,
                                   {"cantidad": "sin_restriccion", "cambioInterno": "permitido",
                                    "evaluacion": "equilibrio_estable"}, m, E=e.U, V=e.V)
        if r["estado"] != "evaluado":
            raise mz.FueraDeAlcance("no_convergente", "; ".join(d["mensaje"] for d in r["diagnosticos"]))
        return r["evaluacion"]
    return motor_mezclas.evaluacion_desde_estado(e, ids, paq.sistema, None, {})


def _inicializar(vols, diag):
    sal = {"estado": "pendiente", "volumenes": {}}
    listos = {}
    estados = []
    for v in vols:
        vid = v["id"]
        pv_ = f"volumen:{vid}"
        r = {"estado": "pendiente", "variables": {}, "estadoTermodinamico": None}
        sal["volumenes"][vid] = r
        datos_ok = v["paq"] is not None and all(d is not None and d.estado == "ok" for d in v["n0"].values()) and \
            len(v["n0"]) == len(v["comp"]) and v["E0"] is not None and v["E0"].estado == "ok" and (
                (v["tipo"] == "rigida" and v["V"] is not None and v["V"].estado == "ok") or
                (v["tipo"] == "presion_prescrita" and v["P"] is not None and v["P"].estado == "ok"))
        if not datos_ok:
            estados.append("pendiente")
            continue
        paq = v["paq"]
        q = np.array([v["n0"][c].funcion(0.0) for c in v["comp"]])
        n = q / paq.M if v["b0"] == "masica" else q
        prop_e, ruta_e = v["E0"].origen
        if not n.sum() > 0:
            diag("MOTOR_ENS_INICIAL_VACIO", "invalido", f"Volumen {vid} sin materia inicial.", ruta_e,
                 [v["E0"].id], prop_e)
            r["estado"] = "incompatible"
            estados.append("incompatible")
            continue
        try:
            if v["tipo"] == "rigida":
                Vv = v["V"].funcion(0.0)
                e = paq.estado("UV", v["E0"].funcion(0.0), Vv, n, certificar=True) if v["en"] == "U" else \
                    paq.estado("TV", v["E0"].funcion(0.0), Vv, n, certificar=True)
            else:
                P0 = v["P"].funcion(0.0)
                e = paq.estado("UP", P0, v["E0"].funcion(0.0), n, certificar=True) if v["en"] == "U" else \
                    paq.estado("TP", v["E0"].funcion(0.0), P0, n, certificar=True)
            pol = v["pol"]
            tipos = [f.tipo for f in e.fases]
            if pol.get("cantidad") == "monofasico" and len(e.fases) > 1 or pol.get("tiposPermitidos") and any(
                    t not in pol["tiposPermitidos"] for t in tipos):
                raise mz.FueraDeAlcance("politica", f"El estado inicial de {vid} ({', '.join(_ids_fases(e))}) "
                                        "incumple la política de fases.")
            ev = evaluacion_volumen(paq, e, v["comp"], pol)
        except mz.FueraDeAlcance as x:
            estado = {"saturacion": "pendiente", "region_critica": "no_soportada",
                      "no_soportado": "no_soportada"}.get(x.motivo, "incompatible")
            diag(f"MOTOR_ENS_INICIAL_{x.motivo.upper()}", {"pendiente": "incompleto", "no_soportada": "no_soportado"}
                 .get(estado, "invalido"), f"Volumen {vid}: {x.mensaje}", ruta_e, [v["E0"].id], prop_e)
            r["estado"] = estado
            estados.append(estado)
            continue
        pref = f"volumen.{vid}"
        variables = {f"{pref}.n.{c}": float(n[k]) for k, c in enumerate(v["comp"])}
        variables.update({f"{pref}.U": e.U, f"{pref}.T": e.T, f"{pref}.P": e.P, f"{pref}.V": e.V})
        if v["tipo"] != "rigida":
            variables[f"{pref}.H"] = e.H
        r.update(estado="compatible", variables=variables,
                 estadoTermodinamico={"volumenId": vid, "evaluacion": ev, "potenciales": potenciales(e, paq, v["comp"])})
        estados.append("compatible")
        listos[vid] = {"n": n, "E": e.U if v["tipo"] == "rigida" else e.H, "T": e.T, "estado": e, "U": e.U}
    for est_ in ("incompatible", "no_soportada", "pendiente"):
        if est_ in estados:
            sal["estado"] = est_
            break
    else:
        sal["estado"] = "compatible" if estados else "pendiente"
    return sal, (listos if sal["estado"] == "compatible" else None)


# ----------------------------------------------------------------------
# Resolucion
# ----------------------------------------------------------------------
def _funcion_molar(d, base, M):
    f = d.funcion
    return f if base == "molar" else Funcion(f.f, f.df, f.factor / M, f.desplazamiento / M, f.constante)


def resolver_v2(cuerpo):
    val, ctx = validar_v2(cuerpo)
    diags = val["diagnosticos"]

    def rechazo(estado):
        return {"revision": REVISION, "validacion": val, "estado": estado, "resultados": None}
    if ctx is None or val["recuento"]["estado"] != "listo" or val["inicializacion"]["estado"] != "compatible" or any(
            d["estado"] in ("invalido", "conflicto", "incompleto", "no_soportado") for d in diags):
        return rechazo("no_soportado" if any(d["estado"] == "no_soportado" for d in diags) else "invalido")
    vols, cors, ints, comps, est = ctx["vols"], ctx["cors"], ctx["ints"], ctx["comps"], ctx["est"]
    tf = ctx["lec"].tf
    gidx = {c: k for k, c in enumerate(comps)}
    # masa molar global por componente: la del paquete del primer volumen que lo contiene
    Mg = np.zeros(len(comps))
    for v in reversed(vols):
        for k, c in enumerate(v["comp"]):
            Mg[gidx[c]] = v["paq"].M[k]
    vidx = {v["id"]: j for j, v in enumerate(vols)}
    vsi = []
    for v in vols:
        li = ctx["ini"][v["id"]]
        vsi.append(er.VolumenSI(id=v["id"], paquete=v["paq"], comp=[gidx[c] for c in v["comp"]],
                                frontera="rigida" if v["tipo"] == "rigida" else "presion",
                                V=v["V"].funcion(0.0) if v["tipo"] == "rigida" else None,
                                P=v["P"].funcion if v["tipo"] != "rigida" else None, politica=v["pol"],
                                n0=li["n"], E0=li["E"], T0=li["T"]))
    csi = []
    for s in cors:
        comp_g = [gidx[c] for c in s["comp"]]
        x_ext = None
        if s["x_ext"] is not None:
            b_, fr_ = s["x_ext"]
            w = np.zeros(len(comps))
            for c, val_ in fr_.items():
                w[gidx[c]] = val_
            if b_ == "masica":
                w = np.where(w > 0, w / np.where(Mg > 0, Mg, 1), 0)
            x_ext = w / w.sum()
        Fc = None
        if s["Fc"] is not None:
            Fc = {gidx[c]: d.funcion for c, d in s["Fc"].items()}
        csi.append(er.CorrienteRed(
            id=s["id"], desde=vidx.get(s["de"]), hasta=vidx.get(s["ha"]), comp=comp_g,
            modo="total" if s["modo"] == "total_desde_donante" else "por_componente", base=s["base"],
            F=s["F"].funcion if s["F"] is not None else None, Fc=Fc,
            T_ext=s["Text"].funcion if s["Text"] is not None else None,
            P_ext=s["Pext"].funcion if s["Pext"] is not None else None, continuidad=s["cont"], x_ext=x_ext,
            extraccion=dict(s["extr"])))
    isi = [er.IntercambioRed(id=q["id"], desde=vidx.get(q["de"]), hasta=vidx.get(q["ha"]), ley=q["ley"],
                             Q=q["Q"].funcion if q["Q"] is not None else None,
                             G=q["G"].funcion(0.0) if q["G"] is not None else None,
                             T_ext=q["Te"].funcion if q["Te"] is not None else None,
                             T_frontera=q["Tf"].funcion if q["Tf"] is not None else None) for q in ints]
    red = er.Red(volumenes=vsi, corrientes=csi, intercambios=isi, M=Mg, tf=tf, muestras=est["muestras"],
                 rtol=est["rtol"], atol_n=est["atol"]["cantidad"], atol_E=est["atol"]["energia"])
    sis = er.Sistema(red)
    y0 = np.zeros(sis.n_total)
    for j, v in enumerate(vsi):
        o = sis.offs[j]
        y0[o:o + len(v.comp)] = v.n0
        y0[o + len(v.comp)] = v.E0
    try:
        tray = er.integrar(red, y0)
    except (mz.FueraDeAlcance, Detencion) as x:
        diags.append({"codigo": "MOTOR_ENS_NO_CONVERGENTE", "estado": "invalido", "mensaje": getattr(x, "mensaje", str(x)),
                      "variableIds": [], "origen": {"propietarioId": "red", "ruta": "/volumenes"}})
        return rechazo("no_convergente")
    # muestras certificadas
    tiempos, filas, estados = [], [], {v.id: [] for v in vsi}
    detenida = tray.detenida
    semillas = [ctx["ini"][v.id]["estado"] for v in vsi]
    ids_previos = [None] * len(vsi)
    ids_usados = [set() for _ in vsi]
    ids_muestra = {v.id: [] for v in vsi}
    for t, y in er.muestras(red, tray):
        try:
            evs = []
            for j, v in enumerate(vsi):
                e = sis.estado_vol(t, y, j, certificar=True, semilla=semillas[j])
                evs.append(e)
            evals = []
            for j, v in enumerate(vsi):
                e = evs[j]
                _seguir_ids(e, ids_previos, j, ids_usados[j])
                ev = evaluacion_volumen(v.paquete, e, vols[j]["comp"], v.politica)
                if any(x["estado"] == "no_cumple" for x in ev["verificaciones"]):
                    raise mz.FueraDeAlcance("no_convergente", f"Volumen {v.id}: verificación no cumplida.")
                evals.append({"volumenId": v.id, "evaluacion": ev, "potenciales": potenciales(e, v.paquete, vols[j]["comp"])})
            fl = sis.flujos(t, y, evs)
        except (mz.FueraDeAlcance, Detencion) as x:
            diags.append({"codigo": "MOTOR_ENS_MUESTRA_NO_CERTIFICADA", "estado": "invalido",
                          "mensaje": f"t = {t:.9g} s: {getattr(x, 'mensaje', str(x))}", "variableIds": [],
                          "origen": {"propietarioId": "red", "ruta": "/estudio"}})
            detenida = detenida or Detencion("muestra_no_certificada", "", t)
            break
        semillas = evs
        tiempos.append(t)
        filas.append((t, y, evs, fl))
        for j, v in enumerate(vsi):
            estados[v.id].append(evals[j])
            ids_muestra[v.id].append([f.id for f in evs[j].fases])
    if not filas:
        d = tray.detenida
        if d is not None and d.t == 0.0:
            # la red no puede arrancar (p. ej. extraer una fase ausente): el motivo es la detencion, no una
            # falta de convergencia; se publica como tal y la respuesta es invalida, sin muestras
            diags.append({"codigo": f"MOTOR_ENS_DETENIDO_{d.codigo.upper()}", "estado": "invalido",
                          "mensaje": f"La red no puede arrancar en t = 0: {d.mensaje}", "variableIds": [],
                          "origen": {"propietarioId": "red", "ruta": "/corrientes"}})
            return rechazo("invalido")
        return rechazo("no_convergente")
    series = []
    catalogo = []
    vars_val = {x["id"] for x in val.get("variables") or []}

    def serie(id_, uni, vals, magnitud, papel, propietario, procedencia):
        series.append({"variableId": id_, "unidadSI": uni, "valores": [float(x) for x in vals]})
        catalogo.append({"variableId": id_, "propietarioId": propietario, "unidadSI": uni, "magnitud": magnitud,
                         "papel": papel, "variableEnsamblajeId": id_ if id_ in vars_val else None,
                         "procedencia": procedencia})
    for j, v in enumerate(vsi):
        pref = f"volumen.{v.id}"
        pv_ = f"volumen:{v.id}"
        o = sis.offs[j]
        for k, c in enumerate(vols[j]["comp"]):
            serie(f"{pref}.n.{c}", "mol", [f[1][o + k] for f in filas], "cantidad", "estado_integrado", pv_,
                  f"estado diferencial: balance de materia del componente {c} en {v.id}")
        if v.frontera == "rigida":
            serie(f"{pref}.U", "J", [f[2][j].U for f in filas], "energia", "estado_integrado", pv_,
                  "estado diferencial (frontera rigida); valor del estado certificado de la muestra")
        else:
            serie(f"{pref}.U", "J", [f[2][j].U for f in filas], "energia", "algebraica", pv_,
                  "U = H - P V del estado certificado")
            serie(f"{pref}.H", "J", [f[1][o + len(v.comp)] for f in filas], "energia", "estado_integrado", pv_,
                  "estado diferencial (presion prescrita): dH/dt = J_E + V dP/dt")
            serie(f"{pref}.W", "J", [f[1][sis.i_W + j] for f in filas], "energia", "integral_auxiliar", pv_,
                  "trabajo de frontera acumulado int P dV/dt dt (no es un estado del sistema fisico)")
        serie(f"{pref}.T", "K", [f[2][j].T for f in filas], "temperatura", "algebraica", pv_,
              "cierre de equilibrio del paquete (estado certificado)")
        serie(f"{pref}.P", "Pa", [f[2][j].P for f in filas], "presion", "algebraica" if v.frontera == "rigida" else "dato",
              pv_, "cierre de equilibrio del paquete" if v.frontera == "rigida" else "presion prescrita (dato)")
        serie(f"{pref}.V", "m3", [f[2][j].V for f in filas], "volumen", "dato" if v.frontera == "rigida" else "algebraica",
              pv_, "volumen geometrico (dato)" if v.frontera == "rigida" else "cierre de equilibrio del paquete")
        serie(f"{pref}.masa", "kg", [f[2][j].masa for f in filas], "masa", "derivada", pv_,
              "sum_i n_i M_i con las masas molares del paquete; presentacion, sin ecuacion propia")
        serie(f"{pref}.S", "J/K", [f[2][j].S for f in filas], "entropia", "derivada", pv_,
              "entropia del estado certificado (referencia del paquete); presentacion, sin ecuacion propia")
    for s_ in csi:
        serie(f"corriente.{s_.id}.ndot", "mol/s",
              [next((ndot if (o_ == s_.desde) else -ndot) for c_, ndot, o_, d_, *_ in f[3] if c_ is s_) for f in filas],
              "caudal_molar", "algebraica", f"corriente:{s_.id}",
              "caudal molar total en el sentido declarado desde -> hasta (negativo: invertido)")
    for q in isi:
        serie(f"calor.{q.id}.Q", "W", [next(Q for q_, Q in sis.calores(f[0], f[2]) if q_ is q) for f in filas],
              "potencia", "dato" if q.ley == "impuesto" else "algebraica", f"calor:{q.id}",
              "potencia impuesta (dato)" if q.ley == "impuesto" else "Q = G (T_desde - T_hasta)")
    # residuos (max sobre la trayectoria) y su valor por muestra, para la certificacion
    U0 = sum(ctx["ini"][v.id]["U"] for v in vsi)
    escala_n = est["atol"]["cantidad"] + est["rtol"] * max(
        float(sum(np.sum(f[1][sis.offs[j]:sis.offs[j] + len(v.comp)]) for j, v in enumerate(vsi))) for f in filas)
    P0V0 = [filas[0][2][j].P * filas[0][2][j].V for j in range(len(vsi))]

    def W_partes(f, j):
        # trabajo de frontera por partes: int P dV = [P V] - int V dP/dt dt (sin derivar V)
        return 0.0 if vsi[j].frontera == "rigida" else f[2][j].P * f[2][j].V - P0V0[j] - f[1][sis.i_VdP + j]
    # escala de energia: la mayor de |U|, |int E_ext| y |W| a lo largo de la trayectoria (no solo |U|, que
    # depende del cero de la referencia y puede pasar por 0)
    escala_E = est["atol"]["energia"] + est["rtol"] * max(
        max(abs(sum(e.U for e in f[2])) for f in filas), max(abs(f[1][sis.i_E]) for f in filas),
        max(abs(sum(W_partes(f, j) for j in range(len(vsi)))) for f in filas), 1.0)
    residuos, por_muestra = [], {}

    def residuo(id_, valores, tol, definicion):
        por_muestra[id_] = (valores, tol)
        residuos.append({"ecuacionId": id_, "maximoEscalado": float(max(valores)), "tolerancia": tol,
                         "definicion": definicion})
    for c in comps:
        g = gidx[c]
        n0 = sum(v.n0[v.comp.index(g)] for v in vsi if g in v.comp)
        residuo(f"global.materia.{c}",
                [abs(sum(f[1][sis.offs[j] + v.comp.index(g)] for j, v in enumerate(vsi) if g in v.comp)
                     - n0 - f[1][sis.i_mat + g]) / escala_n for f in filas], 10.0,
                "max_t |sum_v n_v,i - n_i(0) - int ndot_ext,i dt| / (atol + rtol max_t sum_v,i n); las "
                "transferencias internas se suman y restan como el mismo número")
    residuo("global.energia",
            [abs(sum(e.U for e in f[2]) - U0 - (f[1][sis.i_E] - sum(W_partes(f, j) for j in range(len(vsi)))))
             / escala_E for f in filas], 10.0,
            "max_t |sum U_v - U(0) - (int E_ext dt - sum W_v)| / (atol + rtol max_t(|sum U|, |int E_ext|, |sum W|)), "
            "con W_v = [P V] - int V dP/dt dt: U de los estados certificados frente a la contabilidad de "
            "transferencias exteriores y trabajo")
    for j, v in enumerate(vsi):
        if v.frontera == "rigida":
            continue
        escala_W = est["atol"]["energia"] + 1e-5 * max(max(abs(W_partes(f, j)) for f in filas),
                                                       max(abs(f[2][j].P * f[2][j].V) for f in filas) * 1e-3)
        residuo(f"mecanica.{v.id}.trabajo", [abs(f[1][sis.i_W + j] - W_partes(f, j)) / escala_W for f in filas], 1.0,
                "max_t |int P dV/dt dt (dV/dt total de V(H, P, n) por diferencia centrada) - ([P V] - int V dP)| / "
                "(atol + 1e-5 max|W|): verifica la derivada total de V (diferencia centrada, integrada a traves de "
                "las aristas de cambio de fase; acuerdo medido ~2e-6 relativo, tolerancia 1e-5 declarada)")
    for j, v in enumerate(vsi):
        o = sis.offs[j]
        m = len(v.comp)
        residuo(f"estado.{v.id}.energia",
                [abs((f[2][j].U if v.frontera == "rigida" else f[2][j].H) - f[1][o + m]) / escala_E for f in filas], 1.0,
                "max |E del estado certificado - E integrada| / escala de energia")
        if v.frontera == "rigida":
            residuo(f"estado.{v.id}.volumen", [abs(f[2][j].V - v.V) / v.V / 1e-9 for f in filas], 1.0,
                    "max |V del estado - V geométrico| / V / 1e-9")
    # segunda ley
    S0 = sum(e.S for e in filas[0][2])
    gen = [sum(e.S for e in f[2]) - S0 - f[1][sis.i_S] for f in filas]
    tol_S = est["atol"]["energia"] / 300.0 + est["rtol"] * max(abs(S0), 1.0) * 10
    primera_S = None
    if not sis.segunda_ley_evaluable:
        sl = {"estado": "no_evaluable", "motivo": "Hay intercambios de calor con el exterior sin temperatura de frontera "
              "(temperaturaFronteraId): no se sustituye por la T del fluido.", "generacionMinima": None,
              "tolerancia": None, "unidad": "J/K"}
    else:
        dif = [gen[k] - gen[k - 1] for k in range(1, len(gen))]
        mn = min([0.0] + gen + dif)
        sl = {"estado": "cumple" if mn >= -tol_S else "no_cumple",
              "motivo": "S_gen(t) = sum_v S_v(t) - S(0) - int (sum ndot s + Q/T_frontera)_ext dt evaluada en las "
                        "muestras certificadas: debe ser >= 0 y no decreciente. Contactos internos y mezcla de "
                        "corrientes generan entropía dentro del conjunto; no se exige que cada volumen abierto la aumente.",
              "generacionMinima": float(mn), "tolerancia": float(tol_S), "unidad": "J/K"}
        primera_S = next((k for k in range(len(gen)) if gen[k] < -tol_S or (k > 0 and gen[k] - gen[k - 1] < -tol_S)),
                         None)
        serie("red.Sgen", "J/K", gen, "entropia", "derivada", "red",
              "S_gen(t) de la segunda ley (ver segundaLey); presentacion, sin ecuacion propia")
    # eventos con los IDs reales de las fases que aparecen o desaparecen
    eventos = []
    for c, t, j, msj in tray.eventos:
        ev_ = {"codigo": c, "tiempo": t, "volumenId": vsi[j].id if j is not None else None, "faseIds": [],
               "variableIds": [f"volumen.{vsi[j].id}.fases"] if j is not None else []}
        if j is not None:
            k = next((k for k, tk in enumerate(tiempos) if abs(tk - t) <= 1e-12 * max(tf, 1.0)), None)
            if k is not None and k > 0:
                antes, despues = ids_muestra[vsi[j].id][k - 1], ids_muestra[vsi[j].id][k]
                ev_["faseIds"] = sorted(set(antes) ^ set(despues))
                ev_["faseIdsAntes"], ev_["faseIdsDespues"] = list(antes), list(despues)
        ev_["descripcion"] = _DESCRIPCION_EVENTO.get(c, msj)
        eventos.append(ev_)
    if tray.detenida is not None:
        d = tray.detenida
        diags.append({"codigo": f"MOTOR_ENS_DETENIDO_{d.codigo.upper()}", "estado": "invalido",
                      "mensaje": f"Trayectoria detenida en t = {d.t:.9g} s: {d.mensaje}", "variableIds": [],
                      "origen": {"propietarioId": "red", "ruta": "/volumenes"}})
    cert = _certificacion(por_muestra, sl, primera_S, tiempos, tf, detenida, estados)
    if cert["estado"] == "no_cumple":
        diags.append({"codigo": "MOTOR_ENS_CERTIFICACION_NO_CUMPLE", "estado": "invalido",
                      "mensaje": "La trayectoria se calculó, pero no está físicamente certificada: " + cert["motivo"],
                      "variableIds": [], "origen": {"propietarioId": "red", "ruta": "/resultados/certificacion"}})
    metodo = (f"RK45 Dormand-Prince 5(4) (scipy {scipy.__version__}), rtol {est['rtol']:g}, atol cantidad "
              f"{est['atol']['cantidad']:g} mol, atol energía {est['atol']['energia']:g} J; {tray.pasos} pasos, "
              f"{tray.reintentos} reintentos. Estados por volumen: n_i y U (rígido) o H (presión prescrita). Etapas "
              "con flashes con semilla; muestras certificadas con prueba de estabilidad completa. Eventos de fase "
              "vigilados en 3 puntos interiores y el extremo de cada paso aceptado (vigilancia puntual, no continua).")
    return {"revision": REVISION, "validacion": val, "estado": "parcial" if detenida is not None else "resuelto",
            "resultados": {"metodo": metodo, "tiempos": [float(t) for t in tiempos], "series": series,
                           "estados": estados, "eventos": eventos, "residuos": residuos, "segundaLey": sl,
                           "catalogoSeries": catalogo, "certificacion": cert,
                           "procedenciaModelo": _procedencia(vols)}}


def _procedencia(vols):
    """Aditivo (diagramas, 5.3): que datos y parametros produjeron los estados de cada paquete, para que un
    diagrama solo se compare con una trayectoria si la huella coincide (no basta con modelo.id)."""
    grupos = {}
    for v in vols:
        paq = v["paq"]
        clave = (paq.id, paq.version, paq.huella())
        g = grupos.setdefault(clave, {"volumenIds": [], "modelo": {"id": paq.id, "version": paq.version},
                                      "componentesCAS": list(paq.especies), "huella": clave[2]})
        g["volumenIds"].append(v["id"])
    return list(grupos.values())


_DESCRIPCION_EVENTO = {
    "aparicion_fase": "aparece una fase (transición de primer orden del conjunto de fases)",
    "desaparicion_fase": "desaparece una fase (transición de primer orden del conjunto de fases)",
    "sustitucion_fase": "una fase desaparece y otra aparece en el mismo instante con el mismo número de fases "
                        "(p. ej. dos líquidos -> líquido y vapor en un heteroazeótropo); transición de primer orden",
    "cambio_denominacion": "cambio de denominación por régimen (vapor o líquido <-> fluido supercrítico): las "
                           "propiedades son continuas; NO es evaporación, condensación ni transición de primer orden",
}


def _certificacion(por_muestra, sl, primera_S, tiempos, tf, detenida, estados):
    """Certificacion fisica de la trayectoria publicada, separada del resultado numerico (`estado`).
    Aspectos: estados termodinamicos de las muestras, conservacion global, cierre constitutivo (estado
    integrado frente a estado certificado y trabajo) y segunda ley. Global: no_cumple si algun aspecto no
    cumple; si no, no_evaluable si alguno no es evaluable; si no, cumple. No recorta la trayectoria: publica la
    primera muestra que incumple y la ultima certificada."""
    def aspecto(id_, prefijos, motivo_ok):
        ids = [k for k in por_muestra if any(k.startswith(p) for p in prefijos)]
        malos = [k for k in ids if max(por_muestra[k][0]) > por_muestra[k][1]]
        primera = None
        for k in malos:
            vals, tol = por_muestra[k]
            m = next(i for i, x in enumerate(vals) if x > tol)
            primera = m if primera is None else min(primera, m)
        return {"id": id_, "estado": "no_cumple" if malos else "cumple",
                "motivo": (f"residuo(s) sobre su tolerancia: {', '.join(malos)}" if malos else motivo_ok),
                "referencias": malos or ids, "primeraMuestraNoCumple": primera}
    n_est = sum(len(v) for v in estados.values())
    aspectos = [
        {"id": "estados_termodinamicos", "estado": "cumple",
         "motivo": f"{n_est} estados por volumen publicados, cada uno con sus verificaciones cumplidas (una muestra "
                   "que no se certifica detiene la publicación y queda en diagnósticos)",
         "referencias": ["estados"], "primeraMuestraNoCumple": None},
        aspecto("conservacion", ("global.",), "materia por componente y energía global dentro de tolerancia"),
        aspecto("cierre_constitutivo", ("estado.", "mecanica."),
                "energía y volumen del estado certificado frente a los integrados, y trabajo de frontera"),
    ]
    if sl["estado"] == "no_evaluable":
        aspectos.append({"id": "segunda_ley", "estado": "no_evaluable", "motivo": sl["motivo"],
                         "referencias": ["segundaLey"], "primeraMuestraNoCumple": None})
    else:
        aspectos.append({"id": "segunda_ley", "estado": sl["estado"],
                         "motivo": ("S_gen >= 0 y no decreciente" if sl["estado"] == "cumple" else
                                    f"S_gen mínima {sl['generacionMinima']:.6g} J/K bajo -{sl['tolerancia']:.3g}"),
                         "referencias": ["segundaLey", "red.Sgen"], "primeraMuestraNoCumple": primera_S})
    estados_a = [a["estado"] for a in aspectos]
    glob = "no_cumple" if "no_cumple" in estados_a else "no_evaluable" if "no_evaluable" in estados_a else "cumple"
    primeras = [a["primeraMuestraNoCumple"] for a in aspectos if a["primeraMuestraNoCumple"] is not None]
    ultima = (min(primeras) - 1 if primeras else len(tiempos) - 1)
    motivo = {"cumple": "conservación, cierre constitutivo, estados y segunda ley comprobados en todas las muestras",
              "no_evaluable": "sin incumplimientos comprobados, pero no todo es evaluable: " + "; ".join(
                  f"{a['id']}: {a['motivo']}" for a in aspectos if a["estado"] == "no_evaluable"),
              "no_cumple": "; ".join(f"{a['id']}: {a['motivo']}" for a in aspectos if a["estado"] == "no_cumple")}[glob]
    return {"estado": glob, "motivo": motivo, "aspectos": aspectos,
            "alcance": {"tInicial": float(tiempos[0]), "tFinal": float(tiempos[-1]), "muestras": len(tiempos),
                        "completa": detenida is None},
            "ultimaMuestraCertificada": ultima if ultima >= 0 else None}


def _seguir_ids(e, previos, j, usados_hist):
    """IDs de los liquidos entre muestras por continuidad de composicion, no por densidad. Con dos o tres
    liquidos se elige la asignacion de menor distancia total; un liquido nuevo recibe un numero nunca usado
    antes en el volumen (no hereda el ID de una fase que desaparecio)."""
    import itertools
    liqs = [f for f in e.fases if f.tipo == "liquido"]
    prev = previos[j] or {}
    if prev and liqs:
        ids_prev = list(prev)
        k = min(len(liqs), len(ids_prev))
        mejor = None
        # todas las parejas (k liquidos actuales, k IDs previos): con menos liquidos que IDs previos hay que
        # elegir tambien QUE IDs sobreviven, no solo los primeros
        for actuales in itertools.permutations(range(len(liqs)), k):
            for previos_ in itertools.combinations(ids_prev, k):
                d = sum(float(np.sum(np.abs(liqs[li].x - prev[pid]))) for li, pid in zip(actuales, previos_))
                if mejor is None or d < mejor[0]:
                    mejor = (d, list(zip(actuales, previos_)))
        asignados = set()
        for li, pid in mejor[1]:
            liqs[li].id = pid
            asignados.add(li)
        libres = [li for li in range(len(liqs)) if li not in asignados]
    else:
        # sin liquidos previos: valen los IDs del paquete (densidad decreciente), salvo que ya se usaran
        # para una fase que desaparecio
        libres = [li for li in range(len(liqs)) if liqs[li].id in usados_hist]
    for li in libres:
        k = 1
        tomados = usados_hist | {f.id for f in liqs}
        while f"liquido-{k}" in tomados:
            k += 1
        liqs[li].id = f"liquido-{k}"
    for f in e.fases:
        usados_hist.add(f.id)
    previos[j] = {f.id: f.x.copy() for f in liqs}
