"""
Ensamblaje dinamico del motor independiente, revision 1 del protocolo HTTP
de ensamblaje (independiente de la revision 1 de la API puntual).

    GET  /motor/ensamblajes/capacidades
    POST /motor/ensamblajes/validar     ensamblaje, recuento, inicializacion; no integra
    POST /motor/ensamblajes/resolver    lo mismo y, si esta listo, integra

Esquema: frontend/app/motor/contratoEnsamblajeTermodinamico.ts
(SolicitudEnsamblajeDinamico, RespuestaValidacionDinamica,
RespuestaResolucionDinamica). Decisiones, ecuaciones, metodos y limites:
docs/MOTOR_ENSAMBLAJE_DINAMICO.md.

El cuerpo se lee como JSON libre, igual que la API puntual: todo problema
conocido sale como diagnostico con su origen (propietario y ruta) en vez
de como un 422. Nada se rellena por omision: un dato en blanco es
pendiente, un cero explicito es un dato.
"""

import hashlib
import json
import math

import numpy as np
import scipy

from backend import motor_termodinamica as mt
from core import agua_iapws95 as agua
from core import ensamblaje_dinamico as dyn
from core import expresiones_motor as ex

REVISION = 1
MUESTRAS_MAX = 1001

# Unidades: la tabla de frontend/app/motor/unidadesMotor.ts, (factor, desplazamiento).
UNIDADES = {
    "energia": {"J": (1, 0), "kJ": (1e3, 0)},
    "energia_especifica": {"J/kg": (1, 0), "kJ/kg": (1e3, 0)},
    "potencia": {"W": (1, 0), "kW": (1e3, 0)},
    "temperatura": {"K": (1, 0), "degC": (1, 273.15), "degF": (5 / 9, 273.15 - 32 * 5 / 9)},
    "presion": {"Pa": (1, 0), "kPa": (1e3, 0), "bar": (1e5, 0)},
    "masa": {"kg": (1, 0), "g": (1e-3, 0)},
    "tiempo": {"s": (1, 0), "min": (60, 0), "h": (3600, 0)},
    "volumen": {"m3": (1, 0), "L": (1e-3, 0)},
    "caudal": {"kg/s": (1, 0), "g/s": (1e-3, 0), "kg/h": (1 / 3600, 0), "g/h": (1e-3 / 3600, 0)},
    "caudal_molar": {"mol/s": (1, 0), "mol/h": (1 / 3600, 0), "kmol/h": (1e3 / 3600, 0)},
}
UNIDAD_SI = {"energia": "J", "potencia": "W", "temperatura": "K", "presion": "Pa", "masa": "kg", "tiempo": "s",
             "volumen": "m3", "caudal": "kg/s", "caudal_molar": "mol/s", "energia_especifica": "J/kg"}
POSITIVAS = {"temperatura", "presion", "volumen", "tiempo"}


def capacidades():
    publicable, motivo = mt._verificacion_modelo()
    return {
        "revision": REVISION,
        "disponible": publicable,
        "motivo": None if publicable else motivo,
        "modelos": [dict(mt.MODELO_AGUA)] if publicable else [],
        "componentesCAS": [agua.CAS],
        "volumenes": 1,
        "componentes": 1,
        "balances": {"materia": True, "energia": True, "momento": False},
        "formas": {"materia": "cantidad", "energia": "total"},
        "fronteras": ["rigida", "presion_prescrita"],
        "inicializaciones": {"rigida": ["U", "T"], "presion_prescrita": ["U", "T"]},
        "presionPrescrita": {"constante": True, "funcionSuave": True, "discontinua": False},
        "corrientes": {"mecanismos": ["convectivo"], "materia": ["por_componente", "total_y_composicion"],
                       "presionExterior": ["dato", "continuidad"], "inversion": True},
        "extracciones": ["mezcla_homogenea", "fase"],
        "fases": {"monofasico": True, "coexistenciaLiquidoVapor": True, "eventos": True},
        "transferencias": ["calor"],
        "expresiones": {"variables": ["t"], "unidadTiempo": "s", "suaves": ["+", "-", "*", "/", "^", "sin", "cos",
                                                                              "exp", "log", "sqrt"],
                        "noAdmitidas": sorted(ex.NO_SUAVES)},
        "integradores": [{"id": "rk45", "nombre": "Dormand-Prince 5(4) con eventos de fase",
                          "tolerancias": ["rtol", "atol.masa", "atol.energia"]}],
        "muestrasMaximas": MUESTRAS_MAX,
        "dinamicaApiPuntual": False,
    }


# ----------------------------------------------------------------------
# Diagnosticos y lectura
# ----------------------------------------------------------------------
class _Diag:
    def __init__(self):
        self.lista = []

    def __call__(self, codigo, estado, mensaje, ruta, variables=(), propietario="solicitud"):
        self.lista.append({"codigo": codigo, "estado": estado, "mensaje": mensaje, "variableIds": list(variables),
                           "origen": {"propietarioId": propietario, "ruta": ruta}})

    def hay(self, *estados):
        return any(d["estado"] in estados for d in self.lista)


class _Dato:
    """Un dato referenciado y validado. valor(t) en SI; None si pendiente/invalido."""

    def __init__(self, id_, crudo):
        self.id, self.crudo = id_, crudo
        self.funcion = None         # dyn.Funcion
        self.arbol = None
        self.estado = "pendiente"   # pendiente | ok | invalido
        self.depende_t = False

    @property
    def origen(self):
        o = self.crudo.get("origen") if isinstance(self.crudo, dict) else None
        if isinstance(o, dict) and isinstance(o.get("propietarioId"), str) and isinstance(o.get("ruta"), str):
            return o["propietarioId"], o["ruta"]
        return "solicitud", f"/datos/{self.id}"


class _Lector:
    def __init__(self, cuerpo, diag):
        self.c, self.diag = cuerpo, diag
        self.datos = cuerpo.get("datos") if isinstance(cuerpo.get("datos"), dict) else {}
        self.referenciados = {}
        self.tf = None

    def dato(self, id_, magnitudes, funcion_esperada, temporal, ruta_ref, propietario="solicitud",
             signo=None, suave=True):
        """Lee y valida el dato id_. magnitudes: tupla admitida. temporal:
        admite t. signo: 'positivo' | 'no_negativo' | None."""
        if not isinstance(id_, str) or id_ not in self.datos:
            self.diag("MOTOR_ENS_REFERENCIA", "invalido", f"La referencia {id_!r} no existe en «datos».",
                      ruta_ref, [str(id_)], propietario)
            return None
        if id_ in self.referenciados:
            return self.referenciados[id_]
        d = _Dato(id_, self.datos[id_])
        self.referenciados[id_] = d
        prop, ruta = d.origen
        crudo = d.crudo
        if not isinstance(crudo, dict) or not isinstance(crudo.get("declaracion"), dict):
            self.diag("MOTOR_ENS_DATO_FORMA", "invalido", "Dato sin «declaracion» {texto, unidad}.", ruta, [id_], prop)
            d.estado = "invalido"
            return d
        mag = crudo.get("magnitud")
        if mag not in magnitudes:
            self.diag("MOTOR_ENS_MAGNITUD", "invalido",
                      f"Magnitud {mag!r}; aquí se espera {' o '.join(magnitudes)}.", ruta, [id_], prop)
            d.estado = "invalido"
            return d
        if funcion_esperada and crudo.get("funcion") != funcion_esperada:
            self.diag("MOTOR_ENS_FUNCION_DATO", "invalido",
                      f"Función {crudo.get('funcion')!r}; aquí se espera {funcion_esperada!r}.", ruta, [id_], prop)
            d.estado = "invalido"
            return d
        texto, unidad = crudo["declaracion"].get("texto"), crudo["declaracion"].get("unidad")
        if not isinstance(texto, str) or not texto.strip():
            self.diag("MOTOR_ENS_DATO_PENDIENTE", "incompleto",
                      "Dato sin declarar: en blanco es pendiente, nunca cero.", ruta, [id_], prop)
            return d
        if unidad not in UNIDADES[mag]:
            self.diag("MOTOR_ENS_UNIDAD", "invalido",
                      f"Unidad {unidad!r} incompatible con {mag}; usa {', '.join(UNIDADES[mag])}.", ruta, [id_], prop)
            d.estado = "invalido"
            return d
        try:
            arbol = ex.analizar(texto, ["t"] if temporal else [])
        except ex.ErrorExpresion as x:
            codigo = "MOTOR_ENS_DEBE_SER_CONSTANTE" if (not temporal and "Variable no admitida: t" in str(x)) \
                else "MOTOR_ENS_EXPRESION"
            self.diag(codigo, "invalido", f"«{texto}»: {x}", ruta, [id_], prop)
            d.estado = "invalido"
            return d
        malas = ex.no_suaves(arbol)
        if malas and suave:
            self.diag("MOTOR_ENS_NO_SUAVE", "no_soportado",
                      f"«{texto}» usa {', '.join(sorted(malas))}: discontinuidad o derivada discontinua. Esta "
                      "entrega integra constantes y funciones temporales suaves; un salto necesita su regla física "
                      "de reinicialización.", ruta, [id_], prop)
            d.estado = "invalido"
            return d
        factor, desp = UNIDADES[mag][unidad]
        d.arbol, d.depende_t = arbol, ex.depende_de(arbol, "t")
        df = None
        if d.depende_t:
            darbol = ex.derivada(arbol, "t")
            df = (lambda a: (lambda t: ex.evaluar(a, {"t": t})))(darbol)
        d.funcion = dyn.Funcion((lambda a: (lambda t: ex.evaluar(a, {"t": t})))(arbol), df, factor, desp,
                                not d.depende_t)
        d.estado = "ok"
        d.signo = signo
        return d

    def comprobar_valores(self, d, tf):
        """Evalua el dato en 0 y, si depende de t, en 401 puntos de [0, tf]."""
        if d is None or d.estado != "ok":
            return
        prop, ruta = d.origen
        ts = [0.0] if not d.depende_t or not tf else [tf * k / 400 for k in range(401)]
        try:
            vals = [d.funcion(t) for t in ts]
        except ex.ErrorExpresion as x:
            self.diag("MOTOR_ENS_EXPRESION", "invalido", f"No evaluable en [0, tf]: {x}", ruta, [d.id], prop)
            d.estado = "invalido"
            return
        mag = d.crudo["magnitud"]
        if mag in POSITIVAS and min(vals) <= 0:
            self.diag("MOTOR_ENS_FUERA_DE_MAGNITUD", "invalido",
                      f"{mag} debe ser positiva (absoluta) en todo [0, tf]; mínimo {min(vals):.6g} "
                      f"{UNIDAD_SI[mag]}.", ruta, [d.id], prop)
            d.estado = "invalido"
        elif d.signo == "no_negativo" and min(vals) < 0:
            self.diag("MOTOR_ENS_FUERA_DE_MAGNITUD", "invalido", "Cantidad negativa.", ruta, [d.id], prop)
            d.estado = "invalido"


def _bool(obj, clave):
    return isinstance(obj, dict) and obj.get(clave) is True


# ----------------------------------------------------------------------
# Validacion: lectura + ensamblaje + recuento + inicializacion
# ----------------------------------------------------------------------
def validar(cuerpo):
    """(respuesta de validacion, contexto interno para resolver o None)."""
    if isinstance(cuerpo, dict) and cuerpo.get("revision") == 2 and not isinstance(cuerpo.get("revision"), bool):
        from backend.motor_ensamblaje_v2 import validar_v2      # revision 2: aditiva, despacho por revision
        return validar_v2(cuerpo)
    diag = _Diag()
    sid = cuerpo.get("solicitudId") if isinstance(cuerpo, dict) else None
    sid = sid if isinstance(sid, str) else ""
    vacio = {"revision": REVISION, "solicitudId": sid, "modeloId": None,
             "recuento": {"estado": "no_evaluable", "analisis": "no_evaluable", "variables": None,
                          "ecuacionesIndependientes": None, "datosDefinidos": None, "datosFaltantes": None,
                          "inicialesFaltantes": None, "gradosLibertad": None},
             "variables": [], "ecuaciones": [], "diagnosticos": diag.lista,
             "inicializacion": {"estado": "pendiente", "variables": {}, "estadoTermodinamico": None}}
    if not isinstance(cuerpo, dict):
        diag("MOTOR_ENS_FORMA", "invalido", "El cuerpo debe ser un objeto JSON.", "/")
        vacio["recuento"]["motivo"] = "Solicitud ilegible."
        return vacio, None
    claves = {"revision", "solicitudId", "componentes", "volumen", "corrientes", "datos", "transferencias",
              "estudio", "derivacion"}
    for k in cuerpo:
        if k not in claves:
            diag("MOTOR_ENS_CAMPO_NO_ADMITIDO", "invalido", f"Campo «{k}» no admitido; no se ignoran datos.", f"/{k}")
    for k in claves:
        if k not in cuerpo:
            diag("MOTOR_ENS_FALTA", "invalido", f"Falta «{k}».", f"/{k}")
    if cuerpo.get("revision") != REVISION or isinstance(cuerpo.get("revision"), bool):
        diag("MOTOR_ENS_REVISION", "invalido", f"Revisión {cuerpo.get('revision')!r}; se admite {REVISION}.",
             "/revision")
    if not sid:
        diag("MOTOR_ENS_FORMA", "invalido", "solicitudId debe ser un texto no vacío.", "/solicitudId")
    vol = cuerpo.get("volumen") if isinstance(cuerpo.get("volumen"), dict) else None
    if vol is None or not all(isinstance(cuerpo.get(k), t) for k, t in
                              (("componentes", list), ("corrientes", list), ("datos", dict),
                               ("transferencias", dict), ("estudio", dict), ("derivacion", dict))):
        diag("MOTOR_ENS_FORMA", "invalido", "Estructura de la solicitud incompatible con SolicitudEnsamblajeDinamico.",
             "/")
        vacio["recuento"]["motivo"] = "Estructura ilegible: no se ensambla."
        return vacio, None
    lec = _Lector(cuerpo, diag)
    vid = vol.get("id") if isinstance(vol.get("id"), str) and vol.get("id") else "dominio"
    pv = f"volumen:{vid}"

    # --- componentes ------------------------------------------------------
    comps = cuerpo["componentes"]
    cid, cas = None, None
    if len(comps) != 1:
        diag("MOTOR_ENS_COMPONENTES", "no_soportado",
             f"Esta entrega integra un componente; hay {len(comps)}. No se omite ninguno.", "/componentes")
    for i, c in enumerate(comps):
        if not isinstance(c, dict) or isinstance(c.get("id"), bool) or not isinstance(c.get("id"), int) or c["id"] < 1:
            diag("MOTOR_ENS_FORMA", "invalido", "Componente con id entero positivo.", f"/componentes/{i}")
            continue
        ident = c.get("identidadQuimica") or {}
        ruta = f"/componentes/{c['id']}/identidadQuimica"
        if not isinstance(ident, dict) or not (ident.get("cas") or ident.get("proveedorId")):
            diag("MOTOR_ENS_IDENTIDAD", "incompleto", "Identidad química sin declarar; no se deduce del nombre.", ruta)
        elif ident.get("proveedorId"):
            diag("MOTOR_ENS_IDENTIDAD_NO_VERIFICABLE", "no_soportado",
                 "El modelo identifica solo por CAS; el proveedorId no es verificable aquí.", ruta)
        elif not isinstance(ident.get("cas"), str) or not mt._cas_valido(ident["cas"]):
            diag("MOTOR_ENS_CAS_INVALIDO", "invalido", f"{ident.get('cas')!r} no es un CAS válido.", ruta)
        elif ident["cas"] != agua.CAS:
            diag("MOTOR_ENS_COMPONENTE_NO_SOPORTADO", "no_soportado",
                 f"El modelo publicado describe agua pura (CAS {agua.CAS}); no {ident['cas']}.", ruta)
        else:
            cid, cas = c["id"], ident["cas"]
        mm = c.get("masaMolar")
        if isinstance(mm, dict) and isinstance(mm.get("cantidad"), dict) and mm["cantidad"].get("valor") is not None:
            q = mm["cantidad"]
            f = {"kg/mol": 1.0, "g/mol": 1e-3}.get(q.get("unidad"))
            v = q.get("valor")
            if f is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0:
                diag("MOTOR_ENS_MASA_MOLAR", "invalido", "Masa molar: número positivo en kg/mol o g/mol.",
                     f"/componentes/{c['id']}/masaMolar")
            elif abs(v * f - agua.M) > mt.TOL_MASA_MOLAR * agua.M:
                diag("MOTOR_ENS_MASA_MOLAR_CONTRADICTORIA", "invalido",
                     f"Masa molar declarada {v} {q.get('unidad')} contradice la del modelo (18.015268 g/mol); "
                     "no se elimina la declaración para aceptar la petición.", f"/componentes/{c['id']}/masaMolar")
    if vol.get("componenteIds") != ([cid] if cid is not None else vol.get("componenteIds")):
        diag("MOTOR_ENS_CATALOGO", "invalido", "El volumen debe referenciar el componente del catálogo por ID.",
             "/volumen/componenteIds", propietario=pv)

    # --- balances y formulaciones ------------------------------------------
    bal = vol.get("balances") or {}
    if not (_bool(bal, "materia") and _bool(bal, "energia")) or bal.get("momento") is not False:
        diag("MOTOR_ENS_BALANCES", "no_soportado",
             "Esta entrega ejecuta materia y energía activas con momento desactivado; no se afirma ejecutar un "
             "balance desactivado.", "/volumen/balances", propietario=pv)
    fm = vol.get("formulacionMateria") or {}
    fe = vol.get("formulacionEnergia") or {}
    ctx = vol.get("contextoEnergia") or {}
    cierre = vol.get("cierre") or {}
    pol = cierre.get("politica") if isinstance(cierre.get("politica"), dict) else {}
    if fm.get("vista") != "cantidad" or fm.get("cantidadVolumen") or fe.get("forma") != "total":
        diag("MOTOR_ENS_FORMA", "no_soportado",
             "Se necesitan las formas totales (cantidades y energía total); no se reducen campos automáticamente.",
             "/volumen/formulacionMateria/vista", propietario=pv)
    if fe.get("modelo") == "u_lineal":
        diag("MOTOR_ENS_DOS_CIERRES", "conflicto",
             "La relación manual u(T) y el cierre IAPWS determinarían el mismo estado: son dos cierres. Retira uno; "
             "no se elige por omisión.", "/volumen/formulacionEnergia/modelo", propietario=pv)
    densidades = (fm.get("reglasEstado") or {}).get("densidades") or []
    if fe.get("densidadConstante") or fm.get("densidadMediaConstante") or fm.get("densidadComunPuertos") or any(
            isinstance(x, dict) and x.get("constanciaTemporal") not in (None, "sin_restriccion") for x in densidades):
        diag("MOTOR_ENS_DENSIDAD", "conflicto",
             "Una densidad declarada constante es una restricción adicional a la EOS de densidad variable; no se "
             "convierte en propiedad del modelo ni se descarta.", "/volumen/formulacionEnergia/densidadConstante",
             propietario=pv)
    fases_mat = (fm.get("reglasEstado") or {}).get("fases")
    if isinstance(fases_mat, dict) and pol:
        if (fases_mat.get("cantidad") == "monofasico") != (pol.get("cantidad") == "monofasico") or \
                (fases_mat.get("cambioInterno") == "sin_cambio_de_fase") != (pol.get("cambioInterno") == "prohibido"):
            diag("MOTOR_ENS_POLITICA", "conflicto", "Las hipótesis de fase de materia y del cierre discrepan; no se "
                 "aplica un OR.", "/volumen/formulacionMateria/reglasEstado/fases", propietario=pv)
    if pol and ((fe.get("monofasico") is True) != (pol.get("cantidad") == "monofasico")
                or (fe.get("sinCambioFase") is True) != (pol.get("cambioInterno") == "prohibido")):
        diag("MOTOR_ENS_POLITICA", "conflicto", "Las hipótesis de fase de energía y del cierre discrepan; no se "
             "aplica un OR.", "/volumen/formulacionEnergia", propietario=pv)
    if not all(fe.get(k) is True for k in ("uniforme", "sinCinetica", "separarPresion", "sinTrabajoViscoso",
                                            "sinFuerzasVolumen", "sinFuenteVolumetrica")) or fe.get("trabajoTotalHeredado"):
        diag("MOTOR_ENS_TERMINOS", "no_soportado",
             "El régimen admitido es estado uniforme y primera ley sin energía cinética, esfuerzos viscosos, fuerzas "
             "de volumen ni fuentes sin modelo.", "/volumen/formulacionEnergia", propietario=pv)
    if fe.get("estacionario") or fe.get("sinAcumulacionTotal") or fm.get("sinAcumulacion") or \
            (fm.get("campo") or {}).get("estacionario"):
        diag("MOTOR_ENS_ESTACIONARIO", "no_soportado", "Contrato temporal: un estacionario no es condición inicial.",
             "/volumen/formulacionEnergia/estacionario", propietario=pv)
    if (fm.get("campo") or {}).get("sinReaccion") is False or fm.get("generacionUniforme") or \
            fm.get("consumoUniforme") or ctx.get("restoCerrado") is False or fm.get("restoImpermeable") is False:
        diag("MOTOR_ENS_FUENTES", "no_soportado",
             "Sin reacción, generación/consumo ni intercambio restante en esta entrega.", "/volumen/formulacionMateria",
             propietario=pv)
    if ctx.get("volumenId") not in (None, vid):
        diag("MOTOR_ENS_CONTEXTO", "conflicto", "El contexto energético no corresponde a este volumen.",
             "/volumen/contextoEnergia/volumenId", propietario=pv)

    # --- cierre -------------------------------------------------------------
    publicable, motivo = mt._verificacion_modelo()
    if cierre.get("modelo") != mt.MODELO_AGUA or not publicable:
        diag("MOTOR_ENS_MODELO", "no_soportado",
             f"Modelo {cierre.get('modelo')!r} no publicado"
             + (f" ({motivo})" if not publicable else f"; disponible {mt.MODELO_AGUA}") + ".",
             "/volumen/cierre/modelo", propietario=pv)
    if pol.get("cantidad") not in ("sin_restriccion", "monofasico") or pol.get("cambioInterno") not in (
            "permitido", "prohibido") or pol.get("evaluacion") != "equilibrio_estable" or any(
            k not in ("cantidad", "cambioInterno", "evaluacion", "tiposPermitidos") for k in pol):
        diag("MOTOR_ENS_POLITICA_INVALIDA", "invalido", "Política de fase inválida.", "/volumen/cierre/politica",
             propietario=pv)
    tp = pol.get("tiposPermitidos")
    if tp is not None and (not isinstance(tp, list) or not tp or any(x not in mt.FASES for x in tp)):
        diag("MOTOR_ENS_POLITICA_INVALIDA", "invalido", "tiposPermitidos inválido.",
             "/volumen/cierre/politica/tiposPermitidos", propietario=pv)
    monofasico = pol.get("cantidad") == "monofasico"

    # --- frontera mecanica ----------------------------------------------------
    fr = vol.get("frontera") or {}
    tipo_fr = fr.get("tipo")
    V = P = Prestr = None
    if tipo_fr == "rigida":
        V = lec.dato(fr.get("datoId"), ("volumen",), "geometria", False, "/volumen/frontera/datoId", pv)
        if fr.get("presionRestriccionId") is not None:
            Prestr = lec.dato(fr["presionRestriccionId"], ("presion",), "frontera", True,
                              "/volumen/frontera/presionRestriccionId", pv)
        if fm.get("fija") is False or ctx.get("fija") is False:
            diag("MOTOR_ENS_FRONTERA", "conflicto", "Frontera rígida pero la formulación declara volumen móvil.",
                 "/volumen/formulacionMateria/fija", propietario=pv)
    elif tipo_fr == "presion_prescrita":
        P = lec.dato(fr.get("presionId"), ("presion",), "frontera", True, "/volumen/frontera/presionId", pv)
        if fe.get("presionUniforme") is not True:
            diag("MOTOR_ENS_FRONTERA", "conflicto",
                 "Presión prescrita sin la hipótesis de presión uniforme en la formulación de energía.",
                 "/volumen/formulacionEnergia/presionUniforme", propietario=pv)
        if fm.get("fija") is True or ctx.get("fija") is True:
            diag("MOTOR_ENS_FRONTERA", "conflicto", "Presión prescrita pero la formulación declara volumen fijo.",
                 "/volumen/formulacionMateria/fija", propietario=pv)
    elif tipo_fr == "sin_relacion":
        diag("MOTOR_ENS_MECANICA", "incompleto", "La frontera móvil necesita su relación mecánica.",
             "/volumen/frontera", propietario=pv)
    else:
        diag("MOTOR_ENS_FRONTERA", "invalido", "Frontera rigida | presion_prescrita | sin_relacion.",
             "/volumen/frontera", propietario=pv)

    # formulacionEnergia.presionPrescrita (opcional, añadido por el frontend): si se declara debe
    # concordar con la frontera; si falta se conserva el comportamiento v1. No se ignora.
    pp = fe.get("presionPrescrita")
    if pp is not None and not isinstance(pp, bool):
        diag("MOTOR_ENS_FORMA", "invalido", "presionPrescrita debe ser booleano.",
             "/volumen/formulacionEnergia/presionPrescrita", propietario=pv)
    elif pp is False and tipo_fr == "presion_prescrita":
        diag("MOTOR_ENS_PRESION_PRESCRITA", "conflicto",
             "La frontera es de presión prescrita pero la formulación de energía declara presionPrescrita: false.",
             "/volumen/formulacionEnergia/presionPrescrita", propietario=pv)
    elif pp is True and tipo_fr == "rigida" and fr.get("presionRestriccionId") is None:
        diag("MOTOR_ENS_PRESION_PRESCRITA", "conflicto",
             "La formulación declara presión prescrita y la frontera rígida no referencia ningún dato de presión: "
             "la declaración no se ignora.", "/volumen/formulacionEnergia/presionPrescrita", propietario=pv)
    elif pp is True and tipo_fr == "sin_relacion":
        diag("MOTOR_ENS_PRESION_PRESCRITA", "conflicto",
             "La formulación declara presión prescrita pero la frontera no tiene relación mecánica.",
             "/volumen/formulacionEnergia/presionPrescrita", propietario=pv)

    # --- iniciales ------------------------------------------------------------
    ini = vol.get("inicial") or {}
    masa_ids = ini.get("masaIds") or {}
    m0 = None
    if cid is not None:
        if str(cid) not in masa_ids:
            diag("MOTOR_ENS_INICIAL", "incompleto", "Falta la cantidad inicial del componente.",
                 f"/volumen/inicial/masaIds/{cid}", propietario=pv)
        else:
            m0 = lec.dato(masa_ids[str(cid)], ("masa",), "inicial", False, f"/volumen/inicial/masaIds/{cid}", pv,
                          signo="no_negativo")
    en = ini.get("energia") or {}
    E0 = None
    if en.get("tipo") not in ("U", "T"):
        diag("MOTOR_ENS_INICIAL", "invalido", "Energía inicial: tipo U o T (una sola elección activa).",
             "/volumen/inicial/energia", propietario=pv)
    else:
        E0 = lec.dato(en.get("datoId"), ("energia",) if en["tipo"] == "U" else ("temperatura",), "inicial", False,
                      "/volumen/inicial/energia/datoId", pv)

    # --- estudio --------------------------------------------------------------
    est = cuerpo["estudio"]
    tfd = lec.dato(est.get("tiempoId"), ("tiempo",), "estudio", False, "/estudio/tiempoId", "estudio")
    if tfd is not None and tfd.estado == "ok":
        lec.comprobar_valores(tfd, None)
        lec.tf = tfd.funcion(0.0) if tfd.estado == "ok" else None
    mu = est.get("muestras")
    if isinstance(mu, bool) or not isinstance(mu, int) or not 2 <= mu <= MUESTRAS_MAX:
        diag("MOTOR_ENS_ESTUDIO", "invalido", f"muestras: entero en [2, {MUESTRAS_MAX}].", "/estudio/muestras",
             propietario="estudio")
    rtol = est.get("rtol")
    atol = est.get("atol") or {}
    if not isinstance(rtol, (int, float)) or isinstance(rtol, bool) or not 1e-12 <= rtol <= 1e-2:
        diag("MOTOR_ENS_ESTUDIO", "invalido", "rtol en [1e-12, 1e-2].", "/estudio/rtol", propietario="estudio")
    for k in ("masa", "energia"):
        v = atol.get(k) if isinstance(atol, dict) else None
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not v > 0:
            diag("MOTOR_ENS_ESTUDIO", "invalido", f"atol.{k} positiva (kg o J).", f"/estudio/atol/{k}",
                 propietario="estudio")
    if est.get("metodoSolicitado") not in (None, "rk45"):
        diag("MOTOR_ENS_METODO", "no_soportado",
             f"Método {est.get('metodoSolicitado')!r} no verificado con el cierre IAPWS; disponible rk45.",
             "/estudio/metodoSolicitado", propietario="estudio")

    # --- calor ----------------------------------------------------------------
    trans = cuerpo["transferencias"]
    Qd = None
    for k in trans:
        if k != "calor":
            diag("MOTOR_ENS_TRANSFERENCIA", "no_soportado", f"Transferencia {k!r} sin ley admitida.",
                 f"/transferencias/{k}", propietario=pv)
    if "calor" in trans:
        Qd = lec.dato(trans["calor"], ("potencia",), "frontera", True, "/transferencias/calor", pv)
        if fe.get("adiabatico") is True:
            diag("MOTOR_ENS_Q_ADIABATICO", "conflicto", "Adiabático y con calor declarado a la vez.",
                 "/transferencias/calor", [trans["calor"]], pv)
    elif fe.get("adiabatico") is not True:
        diag("MOTOR_ENS_Q_PENDIENTE", "incompleto",
             "No adiabático y sin término de calor: un Q ausente no se interpreta como cero.", "/transferencias",
             propietario=pv)

    # --- corrientes -----------------------------------------------------------
    puertos = {p.get("id"): p.get("sentido") for p in (ctx.get("puertos") or []) if isinstance(p, dict)}
    extr_cierre = cierre.get("extracciones") or {}
    pres_cierre = cierre.get("presionesCorrientes") or {}
    corrientes, vistos = [], set()
    for i, c in enumerate(cuerpo["corrientes"]):
        if not isinstance(c, dict) or isinstance(c.get("id"), bool) or not isinstance(c.get("id"), int):
            diag("MOTOR_ENS_FORMA", "invalido", "Corriente con id entero.", f"/corrientes/{i}")
            continue
        sidc = c["id"]
        pc = f"corriente:{sidc}"
        base_r = f"/corrientes/{i}"
        if sidc in vistos:
            diag("MOTOR_ENS_FORMA", "invalido", f"Corriente {sidc} repetida.", base_r, propietario=pc)
            continue
        vistos.add(sidc)
        if c.get("desde") == vid and c.get("hasta") is None:
            signo = -1
        elif c.get("hasta") == vid and c.get("desde") is None:
            signo = +1
        else:
            diag("MOTOR_ENS_TOPOLOGIA", "invalido", "Corriente sin conexión válida al volumen (un extremo es el "
                 "volumen y el otro el exterior).", base_r, propietario=pc)
            continue
        sentido = "entrada" if signo > 0 else "salida"
        if puertos and puertos.get(sidc) != sentido:
            diag("MOTOR_ENS_CONTEXTO", "conflicto",
                 f"El puerto {sidc} del contexto energético no coincide con la corriente ({sentido}).",
                 "/volumen/contextoEnergia/puertos", propietario=pc)
        if c.get("mecanismo") == "selectivo":
            diag("MOTOR_ENS_SELECTIVO", "no_soportado", "La transferencia selectiva requiere su ley energética.",
                 base_r, propietario=pc)
        if cid is not None and c.get("componenteIds") != [cid]:
            diag("MOTOR_ENS_CATALOGO", "invalido", "La corriente debe referenciar el componente del catálogo.",
                 f"{base_r}/componenteIds", propietario=pc)
        mat = c.get("materia") or {}
        F, base_m = None, mat.get("base")
        mag = ("caudal_molar",) if base_m == "molar" else ("caudal",) if base_m == "masica" else ()
        if not mag:
            diag("MOTOR_ENS_BASE", "invalido", "Base del caudal masica o molar.", f"{base_r}/materia/base",
                 propietario=pc)
        elif mat.get("modo") == "por_componente":
            ids = mat.get("caudalIds") or {}
            if cid is not None and set(ids) != {str(cid)}:
                diag("MOTOR_ENS_CATALOGO", "invalido", "Un caudal por componente del catálogo.",
                     f"{base_r}/materia/caudalIds", propietario=pc)
            elif cid is not None:
                F = lec.dato(ids[str(cid)], mag, "frontera", True, f"{base_r}/materia/caudalIds/{cid}", pc)
        elif mat.get("modo") == "total_y_composicion":
            comp = mat.get("composicion") or {}
            fr_ = comp.get("fracciones") or {}
            if comp.get("base") not in ("masica", "molar") or (cid is not None and (
                    set(map(str, fr_)) != {str(cid)} or not isinstance(fr_.get(str(cid), fr_.get(cid)), (int, float))
                    or abs(fr_.get(str(cid), fr_.get(cid)) - 1.0) > 1e-10)):
                diag("MOTOR_ENS_COMPOSICION", "invalido",
                     "Composición con base propia y fracción 1 del único componente; no se inventa.",
                     f"{base_r}/materia/composicion", propietario=pc)
            F = lec.dato(mat.get("caudalId"), mag, "frontera", True, f"{base_r}/materia/caudalId", pc)
        else:
            diag("MOTOR_ENS_MATERIA", "invalido", "Modo por_componente o total_y_composicion (exclusivos).",
                 f"{base_r}/materia/modo", propietario=pc)
        # donante exterior: obligatorio salvo caudal constante que nunca entra al volumen
        entra_posible = True
        if F is not None and F.estado == "ok" and not F.depende_t:
            try:
                entra_posible = signo * F.funcion(0.0) > 0
            except ex.ErrorExpresion:
                entra_posible = True
        extrae_posible = F is None or F.estado != "ok" or F.depende_t or (signo * F.funcion(0.0) < 0)
        ext = c.get("estadoExterior")
        Text = Pext = None
        continuidad = False
        if entra_posible and not isinstance(ext, dict):
            diag("MOTOR_ENS_DONANTE_PENDIENTE", "incompleto",
                 "Puede entrar materia por esta corriente: declara el estado exterior TP del donante. No se usa el "
                 "estado del volumen ni uno ficticio.", f"{base_r}/estadoExterior",
                 [f"corriente.{sidc}.Text", f"corriente.{sidc}.Pext"], pc)
        if isinstance(ext, dict):
            if ext.get("tipo") != "TP":
                diag("MOTOR_ENS_DONANTE", "invalido", "Estado exterior de tipo TP.", f"{base_r}/estadoExterior/tipo",
                     propietario=pc)
            Text = lec.dato(ext.get("temperaturaId"), ("temperatura",), "frontera", True,
                            f"{base_r}/estadoExterior/temperaturaId", pc)
            pres = ext.get("presion") or {}
            if pres.get("tipo") == "dato":
                Pext = lec.dato(pres.get("datoId"), ("presion",), "frontera", True,
                                f"{base_r}/estadoExterior/presion/datoId", pc)
                if pres_cierre.get(str(sidc)) == "continuidad":
                    diag("MOTOR_ENS_P_DUPLICADA", "conflicto", "El cierre elige continuidad y la corriente trae un "
                         "dato de presión.", f"{base_r}/estadoExterior/presion", [pres.get("datoId")], pc)
            elif pres.get("tipo") == "continuidad":
                continuidad = True
                if pres.get("volumenId") != vid:
                    diag("MOTOR_ENS_DONANTE", "invalido", "Continuidad con un volumen inexistente.",
                         f"{base_r}/estadoExterior/presion/volumenId", propietario=pc)
                if pres.get("restriccionAdicionalId") is not None:
                    lec.dato(pres["restriccionAdicionalId"], ("presion",), "frontera", True,
                             f"{base_r}/estadoExterior/presion/restriccionAdicionalId", pc)
                    diag("MOTOR_ENS_P_DUPLICADA", "conflicto",
                         "Continuidad de presión y además un dato de presión: restricción adicional sobre la misma "
                         "variable. Se conserva y se rechaza con referencia a ambos.",
                         f"{base_r}/estadoExterior/presion/restriccionAdicionalId",
                         [pres["restriccionAdicionalId"], f"corriente.{sidc}.P"], pc)
            else:
                diag("MOTOR_ENS_DONANTE", "invalido", "Presión exterior: dato o continuidad.",
                     f"{base_r}/estadoExterior/presion", propietario=pc)
        ex_c = c.get("extraccion")
        ex_k = extr_cierre.get(str(sidc))
        if ex_c is not None and ex_k is not None and ex_c != ex_k:
            diag("MOTOR_ENS_EXTRACCION", "conflicto", "Extracción distinta en la corriente y en el cierre.",
                 f"{base_r}/extraccion", propietario=pc)
        extr = ex_c if ex_c is not None else ex_k
        extraccion = ("mezcla_homogenea", None)
        if extr is not None:
            if extr == {"tipo": "mezcla_homogenea"}:
                pass
            elif isinstance(extr, dict) and extr.get("tipo") == "fase" and extr.get("fase") in ("liquido", "vapor",
                                                                                                "fluido"):
                extraccion = ("fase", extr["fase"])
            elif isinstance(extr, dict) and extr.get("fase") == "solido":
                diag("MOTOR_ENS_EXTRACCION", "no_soportado", "No hay fase sólida en el modelo.",
                     f"{base_r}/extraccion", propietario=pc)
            else:
                diag("MOTOR_ENS_EXTRACCION", "invalido", "Extracción mezcla_homogenea o fase.",
                     f"{base_r}/extraccion", propietario=pc)
        elif not monofasico and extrae_posible:
            diag("MOTOR_ENS_EXTRACCION", "incompleto",
                 "Con varias fases posibles, declara cómo se extrae materia por esta corriente (mezcla homogénea o "
                 "una fase).", f"/volumen/cierre/extracciones/{sidc}", propietario=pc)
        corrientes.append({"id": sidc, "signo": signo, "F": F, "Text": Text, "Pext": Pext,
                           "continuidad": continuidad, "extraccion": extraccion, "base": base_m,
                           "entra_posible": entra_posible})
    for pid in puertos:
        if pid not in vistos:
            diag("MOTOR_ENS_CONTEXTO", "conflicto", f"El contexto energético declara el puerto {pid} sin corriente.",
                 "/volumen/contextoEnergia/puertos", propietario=pv)

    # --- valores en [0, tf] ---------------------------------------------------
    for d in lec.referenciados.values():
        if d is not tfd:
            lec.comprobar_valores(d, lec.tf)

    # --- ensamblaje, recuento -------------------------------------------------
    variables, ecuaciones, recuento = _ensamblar(vid, cid, tipo_fr, V, P, Prestr, Qd, corrientes, m0, E0, en,
                                                 lec, fe)
    resp = {"revision": REVISION, "solicitudId": sid, "modeloId": None, "recuento": recuento,
            "variables": variables, "ecuaciones": ecuaciones, "diagnosticos": diag.lista,
            "inicializacion": {"estado": "pendiente", "variables": {}, "estadoTermodinamico": None}}
    if not diag.hay("invalido"):
        resp["modeloId"] = _modelo_id(cas, cierre, tipo_fr, V, P, Prestr, Qd, corrientes, m0, E0, en, bal, fe, fm)

    # --- inicializacion -------------------------------------------------------
    ctx_int = None
    if not diag.hay("invalido", "no_soportado") and cid is not None and tipo_fr in ("rigida", "presion_prescrita"):
        ok_datos = all(d is not None and d.estado == "ok" for d in
                       ([m0, E0] + ([V] if tipo_fr == "rigida" else [P])))
        if ok_datos:
            resp["inicializacion"], estado_ini = _inicializar(vid, cid, tipo_fr, V, P, m0, E0, en, pol, diag, pv)
            if estado_ini is not None:
                ctx_int = {"vid": vid, "cid": cid, "cas": cas, "tipo": tipo_fr, "V": V, "P": P, "Q": Qd,
                           "corrientes": corrientes, "m0": m0, "pol": pol, "ini": estado_ini, "lec": lec,
                           "est": est, "fe": fe}
    if resp["inicializacion"]["estado"] == "pendiente" and not resp["inicializacion"]["variables"]:
        faltan = [d for d in (m0, E0) if d is None or d.estado != "ok"]
        if faltan and not diag.hay("invalido", "no_soportado"):
            pass        # ya diagnosticados como pendientes
    return resp, ctx_int


# ----------------------------------------------------------------------
# Catalogo, ecuaciones y recuento estructural
# ----------------------------------------------------------------------
def _ensamblar(vid, cid, tipo_fr, V, P, Prestr, Qd, corrientes, m0, E0, en, lec, fe):
    vars_, ecs = [], []
    pv = f"volumen:{vid}"
    pref = f"volumen.{vid}"
    m_id = f"{pref}.m.{cid if cid is not None else '?'}"
    rig = tipo_fr == "rigida"

    def var(id_, prop, mag, uni, papel, dato=None, comp=None):
        v = {"id": id_, "propietarioId": prop, "magnitud": mag, "unidadSI": uni, "papel": papel}
        if comp is not None:
            v["componenteId"] = comp
        if dato is not None:
            v["datoId"] = dato.id
        vars_.append(v)
        return id_

    def dato_var(id_, prop, d, mag, uni):
        """Variable fijada por un dato; si el dato falta es una incognita mas."""
        papel = "dato" if d is not None and d.estado == "ok" else "algebraica"
        return var(id_, prop, mag, uni, papel, d), papel == "algebraica"

    pendientes = set()
    var(m_id, pv, "masa", "kg", "diferencial", comp=cid)
    if rig:
        var(f"{pref}.U", pv, "energia", "J", "diferencial")
        E_id = f"{pref}.U"
        var(f"{pref}.P", pv, "presion", "Pa", "algebraica")
        vid_V, falta = dato_var(f"{pref}.V", pv, V, "volumen", "m3")
        if falta:
            pendientes.add(vid_V)
    else:
        var(f"{pref}.H", pv, "energia", "J", "diferencial")
        E_id = f"{pref}.H"
        var(f"{pref}.U", pv, "energia", "J", "algebraica")
        var(f"{pref}.V", pv, "volumen", "m3", "algebraica")
        vid_V = f"{pref}.V"
        vid_P, falta = dato_var(f"{pref}.P", pv, P, "presion", "Pa")
        if falta:
            pendientes.add(vid_P)
    var(f"{pref}.T", pv, "temperatura", "K", "algebraica")
    var(f"{pref}.q", pv, "fraccion_masica_vapor", "1", "algebraica")
    if Qd is not None:
        q_id, falta = dato_var(f"{pref}.Q", pv, Qd, "potencia", "W")
        if falta:
            pendientes.add(q_id)
    if not rig:
        var(f"{pref}.W", pv, "energia", "J", "algebraica")
    incid = []      # (ecuacion id, incognitas)
    terms_m, terms_e, inc_m, inc_e = [], [], {f"d/dt {m_id}"}, {f"d/dt {E_id}"}
    for c in corrientes:
        pc = f"corriente:{c['id']}"
        cp = f"corriente.{c['id']}"
        f_id, falta = dato_var(f"{cp}.F", pc, c["F"], "caudal", "kg/s")
        if falta:
            pendientes.add(f_id)
            inc_m.add(f_id)
            inc_e.add(f_id)
        h_id = var(f"{cp}.h", pc, "energia_especifica", "J/kg", "algebraica")
        inc_e.add(h_id)
        s = "+" if c["signo"] > 0 else "-"
        terms_m.append(f"{s}F_{{{c['id']}}}")
        terms_e.append(f"{s}F_{{{c['id']}}}h_{{{c['id']}}}")
        inc_h = {h_id}
        if c["Text"] is not None or c["entra_posible"]:
            t_id, falta = dato_var(f"{cp}.Text", pc, c["Text"], "temperatura", "K")
            if falta:
                pendientes.add(t_id)
                inc_h.add(t_id)
            if c["continuidad"]:
                pd = var(f"{cp}.P", pc, "presion", "Pa", "algebraica")
                inc_h.add(pd)
                ecs.append(_ec(f"mecanica.continuidad.{c['id']}", pc, "mecanica", [pd, f"{pref}.P"],
                               rf"P_{{{c['id']}}}=P", "Pa"))
                incid.append((ecs[-1]["id"], {pd} | ({f"{pref}.P"} if rig else ({vid_P} & pendientes))))
            else:
                p_id, falta = dato_var(f"{cp}.Pext", pc, c["Pext"], "presion", "Pa")
                if falta:
                    pendientes.add(p_id)
                    inc_h.add(p_id)
        donante = (r"h_{%s}=\begin{cases}h(T_{%s},P_{%s}) & s_{%s}F_{%s}>0\\ h_{\mathrm{extr}}(\text{volumen}) "
                   r"& s_{%s}F_{%s}<0\end{cases}" % ((c["id"],) * 7))
        extr = c["extraccion"]
        donante += (r",\ h_{\mathrm{extr}}=h" if extr[0] == "mezcla_homogenea" else
                    r",\ h_{\mathrm{extr}}=h_{\mathrm{%s}}" % extr[1])
        ecs.append(_ec(f"estado.donante.{c['id']}", pc, "estado",
                       sorted(inc_h | {f"{pref}.T"}), donante, "J/kg"))
        incid.append((ecs[-1]["id"], inc_h))
    ent = fe.get("entalpia") is not False
    flujo = "h" if ent else r"(u+Pv)"
    mat_rhs = " ".join(terms_m) or "0"
    ecs.insert(0, _ec(f"materia.{cid}", pv, "materia", [m_id] + [f"corriente.{c['id']}.F" for c in corrientes],
                      rf"\frac{{dm_{{{cid}}}}}{{dt}}={mat_rhs}", "kg/s"))
    incid.insert(0, (ecs[0]["id"], inc_m))
    qterm = "+Q" if Qd is not None else ""
    if Qd is not None and f"{pref}.Q" in pendientes:
        inc_e.add(f"{pref}.Q")
    e_rhs = (" ".join(terms_e) or "0").replace("h_", flujo + "_" if not ent else "h_")
    if rig:
        ec_e = _ec("energia", pv, "energia", [E_id, m_id] + [f"corriente.{c['id']}.h" for c in corrientes]
                   + ([f"{pref}.Q"] if Qd else []),
                   rf"\frac{{dU}}{{dt}}={e_rhs}{qterm}-P\frac{{dV}}{{dt}},\quad V=V_{{\mathrm{{geom}}}}"
                   r"\Rightarrow\frac{dV}{dt}=0", "W")
    else:
        ec_e = _ec("energia", pv, "energia", [E_id, vid_V, f"{pref}.P"] + [f"corriente.{c['id']}.h" for c in corrientes]
                   + ([f"{pref}.Q"] if Qd else []),
                   rf"\frac{{dH}}{{dt}}=J_E+V\frac{{dP}}{{dt}},\quad J_E={e_rhs}{qterm},\quad H=U+PV", "W")
        inc_e.add(vid_V)
        if vid_P in pendientes:
            inc_e.add(vid_P)
    ecs.insert(1, ec_e)
    incid.insert(1, ("energia", inc_e))
    if not ent:
        ecs.append(_ec("estado.flujo", pv, "estado", [], r"u+Pv\equiv h\ \text{(identidad aplicada al trabajo de "
                       r"flujo; se resuelve con }h\text{)}", "J/kg"))
    # cierre termodinamico
    if rig:
        inc_c = {f"{pref}.T", f"{pref}.P", f"{pref}.q"} | ({vid_V} & pendientes)
        ecs += [_ec("estado.u", pv, "estado", [E_id, m_id, f"{pref}.T", f"{pref}.P", f"{pref}.q"],
                    r"U=m\,u(T,P,q)", "J"),
                _ec("estado.v", pv, "estado", [vid_V, m_id, f"{pref}.T", f"{pref}.P", f"{pref}.q"],
                    r"V=m\,v(T,P,q)", "m3"),
                _ec("estado.reparto", pv, "estado", [f"{pref}.T", f"{pref}.P", f"{pref}.q"],
                    r"q:\ \max S\ \text{a}\ (U,V,m)\ \text{(IAPWS-95, cierre UV)}", "1")]
    else:
        inc_c = {f"{pref}.T", vid_V, f"{pref}.q"} | ({vid_P} & pendientes)
        ecs += [_ec("estado.h", pv, "estado", [E_id, m_id, f"{pref}.T", f"{pref}.P", f"{pref}.q"],
                    r"H=m\,h(T,P,q)", "J"),
                _ec("estado.v", pv, "estado", [vid_V, m_id, f"{pref}.T", f"{pref}.P", f"{pref}.q"],
                    r"V=m\,v(T,P,q)", "m3"),
                _ec("estado.reparto", pv, "estado", [f"{pref}.T", f"{pref}.P", f"{pref}.q"],
                    r"q:\ \max S\ \text{a}\ (H,P,m)\ \text{(IAPWS-95, cierre PH)}", "1"),
                _ec("estado.U", pv, "estado", [f"{pref}.U", E_id, f"{pref}.P", vid_V], r"U=H-PV", "J"),
                _ec("mecanica.trabajo", pv, "mecanica", [f"{pref}.W", f"{pref}.P", vid_V],
                    r"\frac{dW}{dt}=P\frac{dV}{dt},\ \frac{dV}{dt}=v\frac{dm}{dt}+m\Big[\Big(\frac{\partial v}"
                    r"{\partial h}\Big)_P\frac{dh}{dt}+\Big(\frac{\partial v}{\partial P}\Big)_h\frac{dP}{dt}\Big]"
                    r"\ \text{(comprobación de la forma en }U\text{)}", "W")]
    for e_id in ("estado.u", "estado.h", "estado.v", "estado.reparto"):
        if any(e["id"] == e_id for e in ecs):
            incid.append((e_id, set(inc_c)))
    if not rig:
        incid.append(("estado.U", {f"{pref}.U"}))
        incid.append(("mecanica.trabajo", {f"{pref}.W"}))
    if rig and Prestr is not None:
        ecs.append(_ec("mecanica.P_restriccion", pv, "mecanica", [f"{pref}.P", Prestr.id],
                       r"P=P_{\mathrm{dato}}\ \text{(restricción adicional al cierre UV)}", "Pa"))
        incid.append(("mecanica.P_restriccion", {f"{pref}.P"}))
    # recuento estructural: emparejamiento maximo ecuaciones <-> incognitas
    incognitas = set().union(*[s for _, s in incid])
    pareja = _emparejar(incid, pendientes)
    sin_ecuacion = sorted(incognitas - set(pareja.values()))
    sobrantes = [e for e, _ in incid if e not in pareja]
    datos_ref = [d for d in lec.referenciados.values()]
    definidos = sum(1 for d in datos_ref if d.estado == "ok")
    faltantes = sum(1 for d in datos_ref if d.estado == "pendiente")
    ini_falt = sum(1 for d in (m0, E0) if d is None or d.estado != "ok")
    if any(d.estado == "invalido" for d in datos_ref):
        estado = "no_evaluable"
    elif sobrantes:
        estado = "conflicto"
    elif sin_ecuacion or faltantes or ini_falt:
        estado = "incompleto"
    else:
        estado = "listo"
    rec = {"estado": estado, "analisis": "estructural", "variables": len(vars_),
           "ecuacionesIndependientes": len(pareja), "datosDefinidos": definidos, "datosFaltantes": faltantes,
           "inicialesFaltantes": ini_falt,
           "gradosLibertad": len(incognitas) - len(incid) if not sobrantes else None}
    motivos = []
    if sobrantes:
        motivos.append(f"Ecuaciones sin incógnita propia (sobredeterminación estructural): {', '.join(sobrantes)}.")
    if sin_ecuacion:
        motivos.append(f"Incógnitas sin ecuación: {', '.join(sin_ecuacion)}.")
    if any(d.estado == "invalido" for d in datos_ref):
        motivos.append("Hay datos inválidos: el recuento no se certifica.")
    for e_id in sobrantes:
        ec = next(e for e in ecs if e["id"] == e_id)
        datos_e = [v for v in ec["variableIds"] if v in lec.referenciados] + [
            x["datoId"] for x in vars_ if x["id"] in ec["variableIds"] and "datoId" in x]
        lec.diag("MOTOR_ENS_SOBREDETERMINADO", "conflicto",
                 f"La ecuación {e_id} no tiene incógnita propia: con los datos y relaciones activos el sistema queda "
                 "sobredeterminado. Se conserva y se diagnostica; no se descarta para resolver.",
                 "/volumen", sorted(set(datos_e + ec["variableIds"])), ec["propietarioId"])
    rec["motivo"] = (" ".join(motivos) + " " if motivos else "") + (
        "Análisis estructural: emparejamiento máximo entre ecuaciones e incógnitas (derivadas de los estados, "
        "variables algebraicas y datos pendientes). La regla de fases no se resta aparte: el reparto entre fases "
        "lo fija el cierre de equilibrio.")
    if estado == "no_evaluable":
        rec.update(gradosLibertad=None, ecuacionesIndependientes=None)
    return vars_, ecs, rec


def _ec(id_, prop, fam, vars_, latex, uni):
    return {"id": id_, "propietarioId": prop, "familia": fam, "variableIds": list(vars_), "latex": latex,
            "unidadResiduo": uni}


def _emparejar(incid, ultimas=()):
    """Emparejamiento maximo (caminos aumentantes). {ecuacion: incognita}.
    Las incognitas de `ultimas` (datos pendientes) se emparejan al final, de
    modo que, si sobran incognitas, sean ellas las que queden sin ecuacion:
    el diagnostico apunta al dato que falta y no a una variable interna."""
    pareja_inc, pareja_ec = {}, {}

    def aumentar(e, vistos):
        for x in sorted(dict(incid)[e], key=lambda v: (v in ultimas, v)):
            if x in vistos:
                continue
            vistos.add(x)
            if x not in pareja_inc or aumentar(pareja_inc[x], vistos):
                pareja_inc[x], pareja_ec[e] = e, x
                return True
        return False
    for e, _ in incid:
        aumentar(e, set())
    return pareja_ec


def _canon(d):
    if d is None:
        return None
    if d.estado != "ok":
        return ["pendiente", d.id]
    if not d.depende_t:
        return round(d.funcion(0.0), 12)
    return [ex.canonica(d.arbol), d.funcion.factor, d.funcion.desplazamiento]


def _modelo_id(cas, cierre, tipo_fr, V, P, Prestr, Qd, corrientes, m0, E0, en, bal, fe, fm):
    ident = {
        "cas": cas, "M": agua.M, "modelo": cierre.get("modelo"), "politica": cierre.get("politica"),
        "referencia": mt.REFERENCIA_AGUA["id"], "balances": bal, "formas": [fm.get("vista"), fe.get("forma")],
        "frontera": [tipo_fr, _canon(V), _canon(P), _canon(Prestr)], "Q": _canon(Qd),
        "corrientes": [[c["id"], c["signo"], _canon(c["F"]), c["base"], _canon(c["Text"]), _canon(c["Pext"]),
                        c["continuidad"], list(c["extraccion"])] for c in sorted(corrientes, key=lambda c: c["id"])],
        "inicial": [_canon(m0), en.get("tipo"), _canon(E0)],
    }
    return "ens-" + hashlib.sha256(json.dumps(ident, sort_keys=True, default=str).encode()).hexdigest()[:32]


# ----------------------------------------------------------------------
# Inicializacion y estados certificados (servicio puntual local, sin HTTP)
# ----------------------------------------------------------------------
def fraccion_vapor(ev):
    """q = fraccion masica de vapor del estado: suma de fraccionMasica de las
    fases de tipo 'vapor' presentes, dentro o fuera de la campana (vapor
    sobrecalentado: 1; liquido: 0; coexistencia: el titulo). Un fluido
    supercritico (tipo 'fluido') no es vapor: q = 0, y la serie se lee junto a
    las fases publicadas. Es la misma definicion que aplica el lector del
    frontend (lectorEnsamblajeTermodinamico.ts)."""
    return sum(f["fraccionMasica"] for f in ev["fases"] if f["tipo"] == "vapor")


def _solicitud_puntual(sid, cid, cas, especificacion, pol):
    return {"revision": 1, "solicitudId": sid, "propietarioId": "ensamblaje",
            "componentes": [{"id": cid, "nombre": "Agua", "simbolo": "A", "identidadQuimica": {"cas": cas}}],
            "declaracion": {"modelo": dict(mt.MODELO_AGUA), "especificacion": especificacion,
                            "politica": dict(pol)}}


def _cant(valor, unidad):
    return {"valor": valor, "unidad": unidad}


def evaluar_certificado(tipo, cid, cas, pol, m, E=None, V=None, P=None, T=None):
    """Respuesta del servicio puntual para el estado del volumen."""
    if tipo == "UV":
        esp = {"tipo": "UV", "U": _cant(E, "J"), "V": _cant(V, "m3"),
               "cantidades": {"base": "masica", "valores": {str(cid): _cant(m, "kg")}}}
    elif tipo == "UP":
        esp = {"tipo": "UP", "U": _cant(E, "J"), "P": _cant(P, "Pa"),
               "cantidades": {"base": "masica", "valores": {str(cid): _cant(m, "kg")}}}
    elif tipo == "PH":
        esp = {"tipo": "PH", "P": _cant(P, "Pa"), "h": _cant(E / m, "J/kg"),
               "composicion": {"base": "masica", "fracciones": {str(cid): 1}}}
    else:
        esp = {"tipo": "TP", "T": _cant(T, "K"), "P": _cant(P, "Pa"),
               "composicion": {"base": "masica", "fracciones": {str(cid): 1}}}
    return mt.evaluar(_solicitud_puntual("ensamblaje", cid, cas, esp, pol))


def _inicializar(vid, cid, tipo_fr, V, P, m0, E0, en, pol, diag, pv):
    pref = f"volumen.{vid}"
    m = m0.funcion(0.0)
    sal = {"estado": "pendiente", "variables": {}, "estadoTermodinamico": None}
    prop_e, ruta_e = E0.origen
    if not m > 0:
        diag("MOTOR_ENS_INICIAL_VACIO", "invalido",
             "Masa inicial nula: un volumen vacío no tiene estado intensivo que inicializar.", m0.origen[1],
             [m0.id], m0.origen[0])
        sal["estado"] = "incompatible"
        return sal, None
    pol_ini = {k: pol[k] for k in ("cantidad", "cambioInterno", "evaluacion", "tiposPermitidos") if k in pol}
    try:
        if tipo_fr == "rigida":
            Vv = V.funcion(0.0)
            if en["tipo"] == "U":
                r = evaluar_certificado("UV", cid, agua.CAS, pol_ini, m, E=E0.funcion(0.0), V=Vv)
            else:
                T0 = E0.funcion(0.0)
                e = agua.evaluar_TV(T0, Vv / m)          # minimo de A a (T, V, m); no publicado en la API puntual
                r = evaluar_certificado("UV", cid, agua.CAS, pol_ini, m, E=m * e.u, V=Vv)
                if r["estado"] == "evaluado" and abs(r["evaluacion"]["T"] - T0) > 1e-7 * T0:
                    diag("MOTOR_ENS_INICIAL_TV", "invalido", "La inicialización TV no se reproduce con el cierre UV.",
                         ruta_e, [E0.id], prop_e)
                    sal["estado"] = "incompatible"
                    return sal, None
        else:
            P0 = P.funcion(0.0)
            if en["tipo"] == "U":
                r = evaluar_certificado("UP", cid, agua.CAS, pol_ini, m, E=E0.funcion(0.0), P=P0)
            else:
                r = evaluar_certificado("TP", cid, agua.CAS, pol_ini, m, T=E0.funcion(0.0), P=P0)
    except agua.FueraDeAlcance as x:
        estado = "no_soportada" if x.motivo == "region_critica" else "incompatible"
        diag("MOTOR_ENS_INICIAL_" + x.motivo.upper(), "invalido" if estado == "incompatible" else "no_soportado",
             x.mensaje, ruta_e, [E0.id], prop_e)
        sal["estado"] = estado
        return sal, None
    if r["estado"] != "evaluado":
        cods = {d["codigo"] for d in r["diagnosticos"]}
        if "MOTOR_ESTADO_SATURACION_INDETERMINADA" in cods:
            estado, est_d = "pendiente", "incompleto"
        elif "MOTOR_ESTADO_REGION_CRITICA" in cods:
            estado, est_d = "no_soportada", "no_soportado"
        else:
            estado, est_d = "incompatible", "invalido"
        for d in r["diagnosticos"]:
            diag("MOTOR_ENS_INICIAL." + d["codigo"], est_d, d["mensaje"], ruta_e, [E0.id], prop_e)
        sal["estado"] = estado
        return sal, None
    ev = r["evaluacion"]
    mezcla = ev["mezcla"]
    Vv = m * mezcla["v"]
    U0 = m * mezcla["u"]
    q = fraccion_vapor(ev)
    variables = {f"{pref}.m.{cid}": m, f"{pref}.U": U0, f"{pref}.T": ev["T"], f"{pref}.P": ev["P"],
                 f"{pref}.V": Vv, f"{pref}.q": q}
    if tipo_fr != "rigida":
        variables[f"{pref}.H"] = U0 + ev["P"] * Vv
    sal = {"estado": "compatible", "variables": variables, "estadoTermodinamico": ev}
    E_estado = U0 if tipo_fr == "rigida" else U0 + ev["P"] * Vv
    return sal, {"m": m, "E": E_estado, "T": ev["T"], "U": U0, "V": Vv}


# ----------------------------------------------------------------------
# Resolucion
# ----------------------------------------------------------------------
def _recortar(ev):
    """EvaluacionEstado de una muestra sin los textos largos de motivo."""
    ev = dict(ev)
    ev["verificaciones"] = [{k: v for k, v in x.items() if k != "motivo"} for x in ev["verificaciones"]]
    return ev


def resolver(cuerpo):
    if isinstance(cuerpo, dict) and cuerpo.get("revision") == 2 and not isinstance(cuerpo.get("revision"), bool):
        from backend.motor_ensamblaje_v2 import resolver_v2
        return resolver_v2(cuerpo)
    val, ctx = validar(cuerpo)
    diags = val["diagnosticos"]

    def rechazo(estado):
        return {"validacion": val, "estado": estado, "resultados": None}
    if ctx is None or val["recuento"]["estado"] != "listo" or val["inicializacion"]["estado"] != "compatible" or any(
            d["estado"] in ("invalido", "conflicto", "incompleto", "no_soportado") for d in diags):
        return rechazo("no_soportado" if any(d["estado"] == "no_soportado" for d in diags) else "invalido")
    vid, cid, pol = ctx["vid"], ctx["cid"], ctx["pol"]
    pref = f"volumen.{vid}"
    est = ctx["est"]
    tf = ctx["lec"].tf
    rig = ctx["tipo"] == "rigida"
    cors = []
    for c in ctx["corrientes"]:
        F = c["F"].funcion
        if c["base"] == "molar":
            F = dyn.Funcion(F.f, F.df, F.factor * agua.M, 0.0, F.constante)
        cors.append(dyn.CorrienteSI(id=c["id"], signo=c["signo"], F=F,
                                    T_ext=c["Text"].funcion if c["Text"] is not None else None,
                                    P_ext=c["Pext"].funcion if c["Pext"] is not None else None,
                                    continuidad=c["continuidad"], extraccion=c["extraccion"]))
    ini = ctx["ini"]
    prob = dyn.Problema(frontera="rigida" if rig else "presion", V=ctx["V"].funcion(0.0) if rig else None,
                        P=None if rig else ctx["P"].funcion, Q=ctx["Q"].funcion if ctx["Q"] is not None else None,
                        corrientes=cors, m0=ini["m"], energia0=("E", ini["E"]), tf=tf, muestras=est["muestras"],
                        rtol=est["rtol"], atol_m=est["atol"]["masa"], atol_E=est["atol"]["energia"], politica=pol,
                        id_volumen=vid, id_componente=cid)
    try:
        tray = dyn.integrar(prob, [ini["m"], ini["E"], 0.0, 0.0], ini["T"])
    except (agua.FueraDeAlcance, dyn.Detencion) as x:
        diags.append({"codigo": "MOTOR_ENS_NO_CONVERGENTE", "estado": "invalido",
                      "mensaje": getattr(x, "mensaje", str(x)), "variableIds": [],
                      "origen": {"propietarioId": f"volumen:{vid}", "ruta": "/volumen"}})
        return rechazo("no_convergente")
    pol_m = {k: pol[k] for k in ("cantidad", "cambioInterno", "evaluacion", "tiposPermitidos") if k in pol}
    # politica de las muestras: se certifica el equilibrio; la politica ya la vigila el integrador
    pol_m = {"cantidad": "sin_restriccion", "cambioInterno": "permitido", "evaluacion": "equilibrio_estable"}
    tiempos, estados, filas, eventos_extra = [], [], [], []
    U0 = ini["U"]
    detenida = tray.detenida
    for t, y in dyn.muestras(prob, tray):
        m, E, Ein, W = y
        try:
            if rig:
                r = evaluar_certificado("UV", cid, agua.CAS, pol_m, m, E=E, V=prob.V)
            else:
                r = evaluar_certificado("PH", cid, agua.CAS, pol_m, m, E=E, P=prob.P(t))
        except agua.FueraDeAlcance as x:
            r = {"estado": "no_convergente", "diagnosticos": [{"codigo": x.motivo, "mensaje": x.mensaje}]}
        if r["estado"] != "evaluado":
            diags.append({"codigo": "MOTOR_ENS_MUESTRA_NO_CERTIFICADA", "estado": "invalido",
                          "mensaje": f"La muestra t = {t:.9g} s no se certifica: "
                                     + "; ".join(d["mensaje"] for d in r["diagnosticos"]),
                          "variableIds": [f"{pref}.U"], "origen": {"propietarioId": f"volumen:{vid}",
                                                                    "ruta": "/estudio"}})
            detenida = detenida or dyn.Detencion("muestra_no_certificada", "", t)
            eventos_extra.append(("muestra_no_certificada", t))
            break
        ev = r["evaluacion"]
        mz = ev["mezcla"]
        Vt = prob.V if rig else m * mz["v"]
        Ut = E if rig else E - ev["P"] * Vt
        q = fraccion_vapor(ev)
        ev_vol = dyn.estado_volumen(prob, t, m, E, semilla=ev["T"])
        fila = {"t": t, "m": m, "E": E, "Ein": Ein, "W": W, "U": Ut, "T": ev["T"], "P": ev["P"], "V": Vt, "q": q,
                "u_cert": mz["u"], "h_cert": mz["h"], "v_cert": mz["v"], "corr": {}}
        for c in prob.corrientes:
            tasa = c.signo * c.F(t)
            h_d, res_d = 0.0, 0.0
            if tasa > 0:
                P_d = ev["P"] if c.continuidad else c.P_ext(t)
                rd = evaluar_certificado("TP", cid, agua.CAS, pol_m, 1.0, T=c.T_ext(t), P=P_d)
                if rd["estado"] != "evaluado":
                    diags.append({"codigo": "MOTOR_ENS_DONANTE_NO_CERTIFICADO", "estado": "invalido",
                                  "mensaje": f"Donante exterior de la corriente {c.id} en t = {t:.9g} s: "
                                             + "; ".join(d["mensaje"] for d in rd["diagnosticos"]),
                                  "variableIds": [f"corriente.{c.id}.Text"],
                                  "origen": {"propietarioId": f"corriente:{c.id}", "ruta": "/corrientes"}})
                    detenida = detenida or dyn.Detencion("donante_no_certificado", "", t)
                    break
                h_d = rd["evaluacion"]["mezcla"]["h"]
                res_d = abs(h_d - dyn.h_TP(c.T_ext(t), P_d)) / (agua.R * c.T_ext(t))
            elif tasa < 0:
                try:
                    h_d = dyn.h_extraccion(c, ev_vol)
                except dyn.Detencion:
                    h_d = None          # fase de extraccion ausente: no se inventa h

            fila["corr"][c.id] = (c.F(t), h_d, res_d)
        else:
            tiempos.append(t)
            estados.append(_recortar(ev))
            filas.append(fila)
            continue
        break
    if not filas:
        return rechazo("no_convergente")
    # series
    series = []

    def serie(id_, uni, vals):
        series.append({"variableId": id_, "unidadSI": uni, "valores": [float(v) for v in vals]})
    serie(f"{pref}.m.{cid}", "kg", [f["m"] for f in filas])
    serie(f"{pref}.U", "J", [f["U"] for f in filas])
    if not rig:
        serie(f"{pref}.H", "J", [f["E"] for f in filas])
        serie(f"{pref}.W", "J", [f["W"] for f in filas])
    serie(f"{pref}.T", "K", [f["T"] for f in filas])
    serie(f"{pref}.P", "Pa", [f["P"] for f in filas])
    serie(f"{pref}.V", "m3", [f["V"] for f in filas])
    serie(f"{pref}.q", "1", [f["q"] for f in filas])
    if prob.Q is not None:
        serie(f"{pref}.Q", "W", [prob.Q(f["t"]) for f in filas])
    for c in prob.corrientes:
        serie(f"corriente.{c.id}.F", "kg/s", [f["corr"][c.id][0] for f in filas])
        hs = [f["corr"][c.id][1] for f in filas]
        if all(h is not None for h in hs):     # si alguna muestra no la define, la serie no se publica
            serie(f"corriente.{c.id}.h", "J/kg", hs)
    # residuos
    from scipy.integrate import quad
    escala_m = est["atol"]["masa"] + est["rtol"] * max(abs(f["m"]) for f in filas)
    escala_E = est["atol"]["energia"] + est["rtol"] * max(max(abs(f["U"]) for f in filas),
                                                          max(abs(f["Ein"]) for f in filas), 1.0)
    neto = lambda t: sum(c.signo * c.F(t) for c in prob.corrientes)     # noqa: E731
    res_m = 0.0
    acum, t_prev = 0.0, 0.0
    for f in filas:
        if f["t"] > t_prev:
            acum += quad(neto, t_prev, f["t"], epsabs=1e-14, epsrel=1e-12, limit=200)[0]
        t_prev = f["t"]
        res_m = max(res_m, abs(f["m"] - ini["m"] - acum))
    res_E = max(abs(f["U"] - (U0 + f["Ein"] - f["W"])) for f in filas)
    res_u = max(abs(f["m"] * (f["u_cert"] if rig else f["h_cert"]) - f["E"]) for f in filas)
    res_v = max(abs(f["m"] * f["v_cert"] - f["V"]) / f["V"] for f in filas)
    res_P = 0.0 if rig else max(abs(f["P"] - prob.P(f["t"])) / f["P"] for f in filas)
    res_d = max([f["corr"][c][2] for f in filas for c in f["corr"]] or [0.0])
    residuos = [
        {"ecuacionId": f"materia.{cid}", "maximoEscalado": res_m / escala_m, "tolerancia": 10.0},
        {"ecuacionId": "energia", "maximoEscalado": res_E / escala_E, "tolerancia": 10.0},
        {"ecuacionId": "estado.u" if rig else "estado.h", "maximoEscalado": res_u / escala_E, "tolerancia": 1.0},
        {"ecuacionId": "estado.v", "maximoEscalado": res_v / 1e-9, "tolerancia": 1.0},
    ]
    if not rig:
        residuos.append({"ecuacionId": "mecanica.P", "maximoEscalado": res_P / 1e-12, "tolerancia": 1.0})
    if prob.corrientes:
        residuos.append({"ecuacionId": "estado.donante", "maximoEscalado": res_d / 1e-9, "tolerancia": 1.0})
    eventos = [{"codigo": c, "tiempo": t, "variableIds": [f"{pref}.q", f"{pref}.T"]} for c, t, _ in tray.eventos]
    eventos += [{"codigo": c, "tiempo": t, "variableIds": [f"{pref}.U"]} for c, t in eventos_extra]
    if tray.detenida is not None:
        d = tray.detenida
        diags.append({"codigo": f"MOTOR_ENS_DETENIDO_{d.codigo.upper()}", "estado": "invalido",
                      "mensaje": f"Trayectoria detenida en t = {d.t:.9g} s: {d.mensaje}. Se publican solo las "
                                 "muestras certificadas hasta ese instante.",
                      "variableIds": [f"{pref}.q"] if "fase" in d.codigo else [f"{pref}.m.{cid}", f"{pref}.U"],
                      "origen": {"propietarioId": f"volumen:{vid}", "ruta": "/volumen/cierre/politica"
                                 if d.codigo == "cambio_fase_prohibido" else "/estudio"}})
    metodo = (f"RK45 Dormand-Prince 5(4) (scipy {scipy.__version__}), rtol {est['rtol']:g}, atol masa "
              f"{est['atol']['masa']:g} kg, atol energía {est['atol']['energia']:g} J, paso máximo = intervalo de "
              f"muestreo ({tf / max(prob.muestras - 1, 1):g} s). Estados: m y "
              f"{'U (cierre UV)' if rig else 'H = U + PV (cierre PH; U reconstruida)'}. Eventos de fase "
              "vigilados en 3 puntos interiores y el extremo de cada paso aceptado, localizados por bisección "
              f"(tolerancia 1e-9·tf) con re-integración y reinicio. {tray.pasos} pasos, "
              f"{tray.rechazos_dominio} reintentos por fallo de flash. Cada muestra certificada con el servicio "
              "puntual (barrido global y estabilidad).")
    final = "parcial" if (detenida is not None) else "resuelto"
    return {"validacion": val, "estado": final,
            "resultados": {"metodo": metodo, "tiempos": [float(t) for t in tiempos], "series": series,
                           "estadosTermodinamicos": estados, "eventos": eventos, "residuos": residuos}}
