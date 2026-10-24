"""
Shared helpers of the dynamic assembly protocol, and its dispatcher.

    GET  /motor/ensamblajes/capacidades?revision=2
    POST /motor/ensamblajes/validar     revision 2: backend/motor_ensamblaje_v2.py
    POST /motor/ensamblajes/resolver    revision 2: backend/motor_ensamblaje_v2.py

Revision 1 (one water volume, solved by core/ensamblaje_dinamico.py) was retired by the user decision
dec-r5-legacy-v1 (23 October 2026): that solver could miss a short phase window between samples, and every
revision-1 case is expressible in revision 2 and solved by the common compiler with parity
(tests/test_retired_v1_assembly.py, tests/v1_assembly_cases.py). A revision-1 request now receives a structured
MOTOR_ENS_REVISION_RETIRADA diagnostic with status no_soportado. Its frozen requests and responses stay in
docs/ejemplos/motor-ensamblaje-* as references. This module keeps the units, data reader and certification
helpers that revision 2 shares.

The body is read as free JSON: every known problem is a diagnostic with its origin (owner and path), never a 422.
Nothing is filled in by default: a blank datum is pending, an explicit zero is a datum.
"""


from backend import motor_termodinamica as mt
from core.dynamic_common import Funcion
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
        self.funcion = None         # Funcion
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
        d.funcion = Funcion((lambda a: (lambda t: ex.evaluar(a, {"t": t})))(arbol), df, factor, desp,
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


RETIRADA = ("La revision 1 del ensamblaje (un volumen de agua resuelto por core/ensamblaje_dinamico.py) se retiro "
            "por la decision dec-r5-legacy-v1 (23 de octubre de 2026). Envia la misma solicitud como revision 2 "
            "(paquetes, volumenes, corrientes, intercambiosTermicos); tests/v1_assembly_cases.py muestra la "
            "traduccion campo por campo.")


def capacidades():
    """Revision 1 is retired: a structured notice. Revision 2 publishes its capabilities (?revision=2)."""
    return {"revision": 1, "disponible": False, "estado": "retirada", "motivo": RETIRADA,
            "sustituta": {"revision": 2, "ruta": "/motor/ensamblajes/capacidades?revision=2"}}


def _retirada(cuerpo):
    diag = _Diag()
    sid = cuerpo.get("solicitudId") if isinstance(cuerpo, dict) and isinstance(cuerpo.get("solicitudId"), str) else ""
    diag("MOTOR_ENS_REVISION_RETIRADA", "no_soportado", RETIRADA, "/revision")
    return {"revision": 1, "solicitudId": sid, "modeloId": None,
            "recuento": {"estado": "no_evaluable", "analisis": "no_evaluable", "variables": None,
                         "ecuacionesIndependientes": None, "datosDefinidos": None, "datosFaltantes": None,
                         "inicialesFaltantes": None, "gradosLibertad": None, "motivo": "Revision retirada."},
            "variables": [], "ecuaciones": [], "diagnosticos": diag.lista,
            "inicializacion": {"estado": "pendiente", "variables": {}, "estadoTermodinamico": None}}


def _es_revision_2(cuerpo):
    return isinstance(cuerpo, dict) and cuerpo.get("revision") == 2 and not isinstance(cuerpo.get("revision"), bool)


def validar(cuerpo):
    """(validation response, internal context or None). Revision 2 is dispatched; any other revision is retired."""
    if _es_revision_2(cuerpo):
        from backend.motor_ensamblaje_v2 import validar_v2
        return validar_v2(cuerpo)
    return _retirada(cuerpo), None


def resolver(cuerpo):
    if _es_revision_2(cuerpo):
        from backend.motor_ensamblaje_v2 import resolver_v2
        return resolver_v2(cuerpo)
    return {"validacion": _retirada(cuerpo), "estado": "no_soportado", "resultados": None}
