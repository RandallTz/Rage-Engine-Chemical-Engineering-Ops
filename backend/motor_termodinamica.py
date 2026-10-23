"""
Contrato de evaluacion termodinamica del motor independiente (/motor),
revision 1. Referencia de nombres y tipos:
frontend/app/motor/contratoTermodinamica.ts.

    GET  /motor/termodinamica/capacidades
    POST /motor/termodinamica/evaluar

La evaluacion no tiene efectos: no cambia cantidades, flujos, topologia
ni integradores. Recibe el JSON tal cual (no un modelo Pydantic) porque
el contrato exige que TODO rechazo conocido salga como respuesta del
contrato con diagnosticos, no como un 422 generico: un campo de mas, una
unidad desconocida o un `valor: null` tienen cada uno su codigo y su
ruta.

Estados de rechazo, por prioridad cuando hay varios problemas:
    invalido       datos mal formados, contradictorios o incompatibles
    no_soportado   modelo, sustancia, especificacion o region no admitidos
    incompleto     faltan datos (valor null, componente sin declarar) o el
                   estado no queda determinado (T/P en saturacion)
    no_convergente el calculo o su certificacion fallaron
Un rechazo siempre lleva evaluacion = null.

Decisiones fisicas y definiciones de residuos:
docs/engine/thermodynamics-h0-h1.md.
"""

import math
import re
from functools import lru_cache

from core import agua_iapws95 as agua

REVISION = 1
MODELO_AGUA = {"id": "agua-iapws95", "version": "1"}
REFERENCIA_AGUA = {
    "id": "iapws95-u0-s0-liquido-saturado-punto-triple",
    "descripcion": "IAPWS-95: u = 0 y s = 0 del líquido saturado en el punto triple "
                   "(273.16 K, 611.655 Pa). Propiedades específicas por kg.",
}
FUENTE_MASA_MOLAR = "IAPWS-95 (R6-95(2018)): M = 18.015268 g/mol"
TOL_MASA_MOLAR = 1e-7       # la misma que aplica el cliente
TOL_COMPOSICION = 1e-10     # suma de fracciones, la misma que el cliente
ALCANCE_ESTABILIDAD = ["liquido", "vapor", "fluido"]
FASES = ("liquido", "vapor", "solido", "fluido")

UNIDADES = {
    "T": {"K": (1.0, 0.0), "degC": (1.0, 273.15), "degF": (5.0 / 9.0, 273.15 - 32.0 * 5.0 / 9.0)},
    "P": {"Pa": (1.0, 0.0), "kPa": (1e3, 0.0), "bar": (1e5, 0.0)},
    "h": {"J/kg": (1.0, 0.0), "kJ/kg": (1e3, 0.0)},
    "U": {"J": (1.0, 0.0), "kJ": (1e3, 0.0)},
    "V": {"m3": (1.0, 0.0), "L": (1e-3, 0.0)},
    "m": {"kg": (1.0, 0.0), "g": (1e-3, 0.0)},
    "n": {"mol": (1.0, 0.0), "kmol": (1e3, 0.0)},
}
POSITIVAS = {"T", "P", "V"}
CAMPOS_ESPECIFICACION = {
    "TP": ("T", "P", "composicion"),
    "PH": ("P", "h", "composicion"),
    "UV": ("U", "V", "cantidades"),
    "UP": ("U", "P", "cantidades"),
}
_PRIORIDAD = ("invalido", "no_soportado", "incompleto", "no_convergente")
# Solo especificaciones con pruebas propias (tests/validar_motor_termodinamica_h3.py).
ESPECIFICACIONES_PUBLICADAS = ("TP", "PH", "UP", "UV")
ALTERNATIVAS_SATURACION = [["P", "h", "composicion"], ["U", "P", "cantidades"], ["U", "V", "cantidades"]]


@lru_cache(maxsize=1)
def _verificacion_modelo():
    """(publicable, motivo). Se publica el modelo solo si la libreria es la
    version auditada y reproduce los valores publicados de IAPWS-95."""
    if not agua.version_auditada():
        return False, (f"chemicals {agua.chemicals.__version__} no es la versión auditada "
                       f"{agua.VERSION_CHEMICALS_AUDITADA}")
    peor = max(agua.verificar(), key=lambda fila: fila[3])
    if peor[3] > 1e-8:
        return False, f"{peor[0]}: error relativo {peor[3]:.3g} frente al valor publicado"
    return True, ""


def capacidad_agua():
    return {
        "id": MODELO_AGUA["id"],
        "version": MODELO_AGUA["version"],
        "nombre": "Agua pura, IAPWS-95 (estado de equilibrio puntual)",
        "componentesCAS": [agua.CAS],
        "especificaciones": list(ESPECIFICACIONES_PUBLICADAS),
        "fases": list(ALCANCE_ESTABILIDAD),
        "dominio": {"T": [agua.T_MIN, agua.T_MAX], "P": [agua.P_MIN, agua.P_MAX]},
        "referencia": dict(REFERENCIA_AGUA),
        "propiedades": ["u", "h", "v", "s", "cp", "cv"],
        "dinamica": False,
    }


def capacidades():
    publicable, _ = _verificacion_modelo()
    from backend.motor_mezclas import capacidades_mezcla
    from backend import motor_hielo
    hielo = [motor_hielo.capacidad()] if motor_hielo.verificacion()[0] else []
    return {"revision": REVISION,
            "modelos": ([capacidad_agua()] + capacidades_mezcla() + hielo) if publicable else []}


# ----------------------------------------------------------------------
# Lectura de la solicitud
# ----------------------------------------------------------------------
class _Lector:
    def __init__(self, propietario):
        self.propietario = propietario
        self.diagnosticos = []
        self.estados = set()

    def diag(self, estado, codigo, ruta, mensaje, componentes=(), alternativas=None):
        d = {"codigo": codigo, "mensaje": mensaje, "ruta": ruta,
             "componenteIds": list(componentes), "propietarioId": self.propietario}
        if alternativas:
            d["alternativas"] = alternativas
        self.diagnosticos.append(d)
        self.estados.add(estado)

    def objeto(self, valor, ruta, requeridos, opcionales=()):
        """dict con exactamente esas claves; None si no lo es."""
        if not isinstance(valor, dict):
            self.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", ruta, "Se esperaba un objeto.")
            return None
        for k in valor:
            if k not in requeridos and k not in opcionales:
                self.diag("invalido", "MOTOR_ESTADO_CAMPO_NO_ADMITIDO", _ruta(ruta, k),
                          f"Campo «{k}» no admitido aquí; no se ignoran datos adicionales.")
        for k in requeridos:
            if k not in valor:
                self.diag("incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", _ruta(ruta, k),
                          f"Falta «{k}».")
        return valor

    def texto(self, valor, ruta, nombre):
        if not isinstance(valor, str) or not valor.strip():
            self.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", ruta, f"{nombre} debe ser un texto no vacío.")
            return None
        return valor

    def cantidad(self, valor, ruta, magnitud, componentes=()):
        """Valor en SI, o None si falta o es invalido (ya diagnosticado)."""
        q = self.objeto(valor, ruta, ("valor", "unidad"))
        if q is None or "valor" not in q or "unidad" not in q:
            return None
        v, u = q["valor"], q["unidad"]
        if v is None:
            self.diag("incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", ruta,
                      "Dato sin declarar (valor null no significa cero).", componentes)
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            self.diag("invalido", "MOTOR_ESTADO_DATO_INVALIDO", ruta, "El valor debe ser un número finito.",
                      componentes)
            return None
        tabla = UNIDADES[magnitud]
        if not isinstance(u, str) or u not in tabla:
            self.diag("invalido", "MOTOR_ESTADO_UNIDAD_INCOMPATIBLE", ruta,
                      f"Unidad {u!r} no admitida; usa una de: {', '.join(tabla)}.", componentes)
            return None
        factor, desplazamiento = tabla[u]
        x = float(v) * factor + desplazamiento
        if magnitud in POSITIVAS and not x > 0 or magnitud in ("m", "n") and x < 0:
            self.diag("invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", ruta,
                      "Valor fuera del dominio de la magnitud "
                      + ("(T, P y V deben ser positivas; T absoluta)." if magnitud in POSITIVAS
                         else "(cantidad negativa)."), componentes)
            return None
        return x


def _ruta(base, clave):
    return f"{base}.{clave}" if base else str(clave)


_CAS = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")


def _cas_valido(cas):
    m = _CAS.match(cas)
    if not m:
        return False
    digitos = (m.group(1) + m.group(2))[::-1]
    return sum((i + 1) * int(c) for i, c in enumerate(digitos)) % 10 == int(m.group(3))


def _leer_componentes(lector, valor):
    """[(id, cas)] de los componentes bien formados."""
    if not isinstance(valor, list) or not valor:
        lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", "componentes",
                    "Declara una lista no vacía de componentes.")
        return []
    salida, vistos = [], set()
    for i, c in enumerate(valor):
        ruta = f"componentes.{i}"
        c = lector.objeto(c, ruta, ("id", "nombre", "simbolo"), ("identidadQuimica", "masaMolar"))
        if c is None:
            continue
        cid = c.get("id")
        if isinstance(cid, bool) or not isinstance(cid, int) or cid < 1:
            lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", f"{ruta}.id",
                        "El ID de componente debe ser un entero positivo.")
            continue
        ruta = f"componentes.{cid}"
        if cid in vistos:
            lector.diag("invalido", "MOTOR_ESTADO_ID_DUPLICADO", ruta, f"ID {cid} repetido.", [cid])
            continue
        vistos.add(cid)
        for campo in ("nombre", "simbolo"):
            if campo in c and not isinstance(c[campo], str):
                lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", f"{ruta}.{campo}",
                            f"«{campo}» debe ser texto.", [cid])
        cas = None
        ident = c.get("identidadQuimica")
        ruta_id = f"{ruta}.identidadQuimica"
        if ident is None:
            lector.diag("incompleto", "MOTOR_ESTADO_IDENTIDAD_SIN_DECLARAR", ruta_id,
                        "Identidad química sin declarar; el nombre y el símbolo son presentación y no "
                        "identifican un modelo físico. Declara el CAS.", [cid])
        elif lector.objeto(ident, ruta_id, (), ("cas", "proveedorId")) is not None:
            if "cas" not in ident and "proveedorId" not in ident:
                lector.diag("incompleto", "MOTOR_ESTADO_IDENTIDAD_SIN_DECLARAR", ruta_id,
                            "Identidad química vacía. Declara el CAS.", [cid])
            if "cas" in ident:
                if not isinstance(ident["cas"], str) or not _cas_valido(ident["cas"]):
                    lector.diag("invalido", "MOTOR_ESTADO_CAS_INVALIDO", f"{ruta_id}.cas",
                                f"{ident['cas']!r} no es un número CAS válido (formato o dígito de control).",
                                [cid])
                else:
                    cas = ident["cas"]
            if "proveedorId" in ident:
                lector.diag("no_soportado", "MOTOR_ESTADO_IDENTIDAD_NO_VERIFICABLE", f"{ruta_id}.proveedorId",
                            "Este modelo identifica sustancias solo por CAS; no puede verificar "
                            f"el proveedorId {ident['proveedorId']!r}. Retíralo y declara el CAS.", [cid])
        if "masaMolar" in c:
            _leer_masa_molar(lector, c["masaMolar"], f"{ruta}.masaMolar", cid, cas)
        salida.append((cid, cas))
    return salida


def _leer_masa_molar(lector, valor, ruta, cid, cas):
    mm = lector.objeto(valor, ruta, ("cantidad", "fuente"))
    if mm is None or "cantidad" not in mm:
        return
    if "fuente" in mm and (not isinstance(mm["fuente"], str) or not mm["fuente"].strip()):
        lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", f"{ruta}.fuente",
                    "La masa molar declarada necesita una fuente.", [cid])
    q = lector.objeto(mm["cantidad"], f"{ruta}.cantidad", ("valor", "unidad"))
    if q is None or q.get("valor") is None:
        return      # sin declarar: el modelo aporta la suya
    v, u = q["valor"], q.get("unidad")
    factor = {"kg/mol": 1.0, "g/mol": 1e-3}.get(u)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 or factor is None:
        lector.diag("invalido", "MOTOR_ESTADO_DATO_INVALIDO", f"{ruta}.cantidad",
                    "Masa molar: número positivo en kg/mol o g/mol.", [cid])
        return
    if cas == agua.CAS and abs(v * factor - agua.M) > TOL_MASA_MOLAR * agua.M:
        lector.diag("invalido", "MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA", f"{ruta}.cantidad",
                    f"La masa molar declarada ({v} {u}) contradice la del modelo "
                    f"(18.015268 g/mol, {FUENTE_MASA_MOLAR}; tolerancia relativa {TOL_MASA_MOLAR:g}). "
                    "No se usa un valor contradictorio para convertir bases.", [cid])


def _leer_politica(lector, valor):
    ruta = "declaracion.politica"
    p = lector.objeto(valor, ruta, ("cantidad", "cambioInterno", "evaluacion"), ("tiposPermitidos",))
    if p is None:
        return None
    ok = True
    for campo, admitidos in (("cantidad", ("sin_restriccion", "monofasico")),
                             ("cambioInterno", ("permitido", "prohibido")),
                             ("evaluacion", ("equilibrio_estable",))):
        if campo in p and p[campo] not in admitidos:
            lector.diag("invalido", "MOTOR_ESTADO_POLITICA_INVALIDA", f"{ruta}.{campo}",
                        f"Valor {p[campo]!r} no admitido; usa {' | '.join(admitidos)}.")
            ok = False
    if "tiposPermitidos" in p:
        t = p["tiposPermitidos"]
        if (not isinstance(t, list) or not t or len(set(map(str, t))) != len(t)
                or any(x not in FASES for x in t)):
            lector.diag("invalido", "MOTOR_ESTADO_POLITICA_INVALIDA", f"{ruta}.tiposPermitidos",
                        "Lista no vacía y sin repetir de: liquido, vapor, solido, fluido.")
            ok = False
    return p if ok and all(k in p for k in ("cantidad", "cambioInterno", "evaluacion")) else None


def _leer_especificacion(lector, valor, comps):
    """(tipo, {magnitud: SI}, composicion (base, {id: x}), cantidades (base, {id: SI})) o None."""
    ruta = "declaracion.especificacion"
    if not isinstance(valor, dict):
        lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", ruta, "Se esperaba un objeto.")
        return None
    tipo = valor.get("tipo")
    if tipo not in CAMPOS_ESPECIFICACION:
        lector.diag("invalido", "MOTOR_ESTADO_ESPECIFICACION_DESCONOCIDA", f"{ruta}.tipo",
                    f"Especificación {tipo!r} desconocida; usa TP, PH, UV o UP.")
        return None
    campos = CAMPOS_ESPECIFICACION[tipo]
    extra = [k for k in valor if k != "tipo" and k not in campos]
    for k in extra:
        lector.diag("invalido", "MOTOR_ESTADO_SOBREESPECIFICADO", f"{ruta}.{k}",
                    f"«{k}» sobra en una especificación {tipo} ({', '.join(campos)}): un dato adicional "
                    "sobreespecifica el estado y no se ignora.")
    for k in campos:
        if k not in valor:
            lector.diag("incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", f"{ruta}.{k}", f"Falta «{k}».")
    valores = {}
    for k in campos:
        if k in valor and k in UNIDADES:
            valores[k] = lector.cantidad(valor[k], f"{ruta}.{k}", k)
    ids = [cid for cid, _ in comps]
    z = None
    if "composicion" in campos and "composicion" in valor:
        z = _leer_composicion(lector, valor["composicion"], f"{ruta}.composicion", ids)
    n = None
    if "cantidades" in campos and "cantidades" in valor:
        n = _leer_cantidades(lector, valor["cantidades"], f"{ruta}.cantidades", ids)
    return tipo, valores, z, n


def _leer_composicion(lector, valor, ruta, ids):
    """Fracciones por ID (base declarada) o None."""
    c = lector.objeto(valor, ruta, ("base", "fracciones"))
    if c is None or "base" not in c or "fracciones" not in c:
        return None
    if c["base"] not in ("molar", "masica"):
        lector.diag("invalido", "MOTOR_ESTADO_BASE_INVALIDA", f"{ruta}.base", "Base molar o masica.")
        return None
    f = c["fracciones"]
    if not isinstance(f, dict):
        lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", f"{ruta}.fracciones", "Se esperaba un objeto por ID.")
        return None
    claves = {str(i) for i in ids}
    ok = True
    for k in f:
        if k not in claves:
            lector.diag("invalido", "MOTOR_ESTADO_COMPONENTE_DESCONOCIDO", f"{ruta}.fracciones.{k}",
                        f"No hay componente con ID {k}.")
            ok = False
    salida = {}
    for i in ids:
        k = str(i)
        if k not in f or f[k] is None:
            lector.diag("incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", f"{ruta}.fracciones.{k}",
                        "Fracción sin declarar; una especie ausente se declara con cero explícito.", [i])
            ok = False
            continue
        v = f[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            lector.diag("invalido", "MOTOR_ESTADO_DATO_INVALIDO", f"{ruta}.fracciones.{k}",
                        "Fracción finita y no negativa.", [i])
            ok = False
            continue
        salida[i] = float(v)
    if ok and abs(sum(salida.values()) - 1.0) > TOL_COMPOSICION:
        lector.diag("invalido", "MOTOR_ESTADO_COMPOSICION_NO_NORMALIZADA", f"{ruta}.fracciones",
                    f"Las fracciones suman {sum(salida.values())!r}, no 1 (tolerancia {TOL_COMPOSICION:g}). "
                    "No se renormalizan.")
        ok = False
    return (c["base"], salida) if ok else None


def _leer_cantidades(lector, valor, ruta, ids):
    """(base, {id: kg o mol}) o None."""
    c = lector.objeto(valor, ruta, ("base", "valores"))
    if c is None or "base" not in c or "valores" not in c:
        return None
    if c["base"] not in ("molar", "masica"):
        lector.diag("invalido", "MOTOR_ESTADO_BASE_INVALIDA", f"{ruta}.base", "Base molar o masica.")
        return None
    vals = c["valores"]
    if not isinstance(vals, dict):
        lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", f"{ruta}.valores", "Se esperaba un objeto por ID.")
        return None
    claves = {str(i) for i in ids}
    for k in vals:
        if k not in claves:
            lector.diag("invalido", "MOTOR_ESTADO_COMPONENTE_DESCONOCIDO", f"{ruta}.valores.{k}",
                        f"No hay componente con ID {k}.")
    total, completo, salida = 0.0, True, {}
    for i in ids:
        k = str(i)
        if k not in vals:
            lector.diag("incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", f"{ruta}.valores.{k}",
                        "Cantidad sin declarar; una especie ausente se declara con cero explícito.", [i])
            completo = False
            continue
        x = lector.cantidad(vals[k], f"{ruta}.valores.{k}", "n" if c["base"] == "molar" else "m", [i])
        if x is None:
            completo = False
        else:
            total += x
            salida[i] = x
    if completo and not total > 0:
        lector.diag("invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", f"{ruta}.valores",
                    "El estado necesita una cantidad total positiva.")
        completo = False
    return (c["base"], salida) if completo else None


# ----------------------------------------------------------------------
# Evaluacion
# ----------------------------------------------------------------------
def _respuesta(solicitud_id, modelo, estado, evaluacion, diagnosticos):
    return {"revision": REVISION, "solicitudId": solicitud_id, "modelo": modelo,
            "estado": estado, "evaluacion": evaluacion, "diagnosticos": diagnosticos}


def evaluar(cuerpo):
    """Respuesta del contrato (dict) para el cuerpo JSON recibido."""
    sid = cuerpo.get("solicitudId") if isinstance(cuerpo, dict) else None
    sid = sid if isinstance(sid, str) else ""
    prop = cuerpo.get("propietarioId") if isinstance(cuerpo, dict) else None
    lector = _Lector(prop if isinstance(prop, str) else "")
    decl = cuerpo.get("declaracion") if isinstance(cuerpo, dict) else None
    mod = decl.get("modelo") if isinstance(decl, dict) else None
    modelo_eco = {"id": mod.get("id") if isinstance(mod, dict) and isinstance(mod.get("id"), str) else "",
                  "version": mod.get("version") if isinstance(mod, dict) and isinstance(mod.get("version"), str) else ""}

    def rechazo():
        estado = next(e for e in _PRIORIDAD if e in lector.estados)
        return _respuesta(sid, modelo_eco, estado, None, lector.diagnosticos)

    raiz = lector.objeto(cuerpo, "", ("revision", "solicitudId", "propietarioId", "componentes", "declaracion"))
    if raiz is None:
        return rechazo()
    if "revision" in raiz and (isinstance(raiz["revision"], bool) or raiz["revision"] != REVISION):
        lector.diag("invalido", "MOTOR_ESTADO_REVISION", "revision",
                    f"Revisión {raiz['revision']!r} no admitida; este servicio implementa la revisión {REVISION}.")
    if "solicitudId" in raiz:
        lector.texto(raiz["solicitudId"], "solicitudId", "solicitudId")
    if "propietarioId" in raiz:
        lector.texto(raiz["propietarioId"], "propietarioId", "propietarioId")
    comps = _leer_componentes(lector, raiz["componentes"]) if "componentes" in raiz else []

    espec = politica = None
    d = lector.objeto(decl, "declaracion", ("modelo", "especificacion", "politica"),
                      ("datosPuros",)) if "declaracion" in raiz else None
    if d is not None:
        if "modelo" in d and lector.objeto(d["modelo"], "declaracion.modelo", ("id", "version")) is not None:
            for k in ("id", "version"):
                if k in d["modelo"]:
                    lector.texto(d["modelo"][k], f"declaracion.modelo.{k}", k)
        if "politica" in d:
            politica = _leer_politica(lector, d["politica"])
        if "especificacion" in d:
            espec = _leer_especificacion(lector, d["especificacion"], comps)

    # Paquetes de mezcla (ampliacion aditiva de la revision 1): backend/motor_mezclas.py
    from backend import motor_mezclas
    if motor_mezclas.es_modelo_mezcla(modelo_eco) and _verificacion_modelo()[0]:
        if espec is not None and espec[0] not in ESPECIFICACIONES_PUBLICADAS:
            lector.diag("no_soportado", "MOTOR_ESTADO_ESPECIFICACION_NO_SOPORTADA", "declaracion.especificacion.tipo",
                        f"La especificación {espec[0]} no está publicada en este modelo.")
        vistos_m = {}
        for cid, cas in comps:
            if cas is not None and cas in vistos_m:
                lector.diag("invalido", "MOTOR_ESTADO_IDENTIDAD_DUPLICADA", f"componentes.{cid}.identidadQuimica.cas",
                            f"Los componentes {vistos_m[cas]} y {cid} declaran la misma sustancia ({cas}).",
                            [vistos_m[cas], cid])
            elif cas is not None and cas not in motor_mezclas.md.especies_disponibles():
                lector.diag("no_soportado", "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO",
                            f"componentes.{cid}.identidadQuimica.cas",
                            f"El paquete {modelo_eco['id']} no tiene datos de componente puro para {cas}.", [cid])
            vistos_m.setdefault(cas, cid)
        if lector.estados or espec is None or politica is None or not comps:
            if not lector.estados:
                lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", "", "Solicitud incompleta.")
            return rechazo()
        return motor_mezclas.evaluar_mezcla(
            lector, sid, modelo_eco, comps, raiz["componentes"], espec, politica, rechazo,
            lambda ev: _respuesta(sid, dict(modelo_eco), "evaluado", ev, lector.diagnosticos),
            sustituciones=(d or {}).get("datosPuros"))
    if d is not None and "datosPuros" in d:
        # F2.4: solo los paquetes de mezcla tienen datos de entrada sustituibles (IAPWS-95 es una formulacion completa)
        lector.diag("no_soportado", "MOTOR_ESTADO_SUSTITUCION_NO_ADMITIDA", "declaracion.datosPuros",
                    f"El modelo {modelo_eco.get('id') if isinstance(modelo_eco, dict) else modelo_eco} no admite "
                    "sustituir datos puros: es una formulacion completa sin entradas sustituibles.")
        return rechazo()

    # Agua con hielo Ih (M5, ampliacion aditiva): backend/motor_hielo.py
    from backend import motor_hielo
    if motor_hielo.es_modelo(modelo_eco) and _verificacion_modelo()[0] and motor_hielo.verificacion()[0]:
        vistos_h = {}
        for cid, cas in comps:
            if cas is not None and cas in vistos_h:
                lector.diag("invalido", "MOTOR_ESTADO_IDENTIDAD_DUPLICADA", f"componentes.{cid}.identidadQuimica.cas",
                            f"Los componentes {vistos_h[cas]} y {cid} declaran la misma sustancia ({cas}).",
                            [vistos_h[cas], cid])
            elif cas is not None and cas != agua.CAS:
                lector.diag("no_soportado", "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO",
                            f"componentes.{cid}.identidadQuimica.cas",
                            f"El modelo {motor_hielo.MODELO['id']} solo describe agua pura (CAS {agua.CAS}). Los "
                            "sólidos en mezclas (solubilidad, SLE, eutécticos) necesitan paquetes y datos propios.",
                            [cid])
            vistos_h.setdefault(cas, cid)
        if espec is not None and espec[0] not in ESPECIFICACIONES_PUBLICADAS:
            lector.diag("no_soportado", "MOTOR_ESTADO_ESPECIFICACION_NO_SOPORTADA", "declaracion.especificacion.tipo",
                        f"La especificación {espec[0]} no está publicada en este modelo.")
        if lector.estados or espec is None or politica is None or len(comps) != 1:
            if not lector.estados:
                lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", "", "Solicitud incompleta.")
            return rechazo()
        return motor_hielo.evaluar(lector, sid, comps, raiz["componentes"], espec, politica, rechazo,
                                   lambda ev: _respuesta(sid, dict(motor_hielo.MODELO), "evaluado", ev,
                                                         lector.diagnosticos))

    # Soporte del modelo: se diagnostica aunque falten datos, para que el
    # usuario vea de una vez todo lo que le impide evaluar.
    publicable, motivo = _verificacion_modelo()
    if modelo_eco != MODELO_AGUA or not publicable:
        lector.diag("no_soportado", "MOTOR_ESTADO_MODELO_NO_PUBLICADO", "declaracion.modelo",
                    f"El modelo {modelo_eco['id']!r} versión {modelo_eco['version']!r} no está publicado"
                    + (f" ({motivo})." if not publicable else
                       f"; consulta /motor/termodinamica/capacidades (disponible: {MODELO_AGUA['id']} "
                       f"versión {MODELO_AGUA['version']})."))
    vistos_cas = {}
    for cid, cas in comps:
        if cas is None:
            continue
        if cas in vistos_cas:
            lector.diag("invalido", "MOTOR_ESTADO_IDENTIDAD_DUPLICADA", f"componentes.{cid}.identidadQuimica.cas",
                        f"Los componentes {vistos_cas[cas]} y {cid} declaran la misma sustancia ({cas}).",
                        [vistos_cas[cas], cid])
        vistos_cas.setdefault(cas, cid)
        if cas != agua.CAS:
            lector.diag("no_soportado", "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO",
                        f"componentes.{cid}.identidadQuimica.cas",
                        f"El modelo {MODELO_AGUA['id']} solo describe agua pura (CAS {agua.CAS}); "
                        f"no tiene parámetros para {cas}. Las mezclas llegarán con modelos propios.", [cid])
    if espec is not None and espec[0] not in ESPECIFICACIONES_PUBLICADAS:
        lector.diag("no_soportado", "MOTOR_ESTADO_ESPECIFICACION_NO_SOPORTADA", "declaracion.especificacion.tipo",
                    f"La especificación {espec[0]} no está publicada en este modelo.",
                    alternativas=[list(CAMPOS_ESPECIFICACION[t]) for t in ESPECIFICACIONES_PUBLICADAS])

    if lector.estados or espec is None or politica is None or len(comps) != 1:
        if not lector.estados:
            lector.diag("invalido", "MOTOR_ESTADO_FORMA_INVALIDA", "", "Solicitud incompleta.")
        return rechazo()

    tipo, valores, z, n = espec
    cid = comps[0][0]
    if tipo == "TP":
        T, P = valores["T"], valores["P"]
        try:
            e = agua.evaluar_TP(T, P)
        except agua.FueraDeAlcance as x:
            return _rechazo_fisico(lector, x, cid, rechazo, tipo)
        return _evaluada(lector, sid, e, T, P, cid, politica, comps, raiz["componentes"], rechazo)
    try:
        if tipo == "PH":
            e = agua.evaluar_PH(valores["P"], valores["h"])
        else:
            # masa total con la masa molar del modelo; nunca una conversion universal
            base, cantidades = n
            m = sum(cantidades.values()) * (agua.M if base == "molar" else 1.0)
            if tipo == "UP":
                e = agua.evaluar_UP(valores["P"], valores["U"] / m)
            else:
                e = agua.evaluar_UV(valores["U"] / m, valores["V"] / m)
    except agua.FueraDeAlcance as x:
        return _rechazo_fisico(lector, x, cid, rechazo, tipo)
    return _evaluada_inversa(lector, sid, e, cid, politica, comps, raiz["componentes"], rechazo)


# Que dato de cada especificacion responde de una T o una P fuera de dominio.
_RUTA_FUERA = {"TP": {"T": "T", "P": "P"}, "PH": {"T": "h", "P": "P"},
               "UP": {"T": "U", "P": "P"}, "UV": {"T": "U", "P": "V"}}


def _rechazo_fisico(lector, x, cid, rechazo, tipo="TP"):
    ruta = "declaracion.especificacion"
    if x.motivo == "fuera_de_dominio":
        marcadas = [k for k in ("T", "P") if x.datos.get(f"{k}_fuera")]
        for k in marcadas:
            lector.diag("no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", f"{ruta}.{_RUTA_FUERA[tipo][k]}",
                        x.mensaje, [cid])
        if not marcadas:
            lector.diag("no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", ruta, x.mensaje, [cid])
    elif x.motivo == "region_critica":
        lector.diag("no_soportado", "MOTOR_ESTADO_REGION_CRITICA", ruta,
                    x.mensaje + " La región crítica queda fuera del alcance de esta versión.", [cid])
    elif x.motivo == "saturacion":
        lector.diag("incompleto", "MOTOR_ESTADO_SATURACION_INDETERMINADA", ruta,
                    x.mensaje + " Hace falta una especificación de energía o volumen (PH, UP o UV); "
                    "no se elige una fracción de vapor por omisión.", [cid],
                    alternativas=[a for a, t in zip(ALTERNATIVAS_SATURACION, ("PH", "UP", "UV"))
                                  if t in ESPECIFICACIONES_PUBLICADAS])
    elif x.motivo == "ambiguo":
        lector.diag("no_convergente", "MOTOR_ESTADO_AMBIGUO", ruta,
                    x.mensaje + " No se elige una raíz arbitraria.", [cid])
    else:
        lector.diag("no_convergente", "MOTOR_ESTADO_NO_CONVERGENTE", ruta, x.mensaje, [cid])
    return rechazo()


def _verif(id_, estado, residuo, tolerancia, motivo=None):
    v = {"id": id_, "estado": estado, "residuo": residuo, "tolerancia": tolerancia}
    if motivo:
        v["motivo"] = motivo
    return v


def _evaluada(lector, sid, e, T, P, cid, politica, comps, componentes_crudos, rechazo):
    permitidos = politica.get("tiposPermitidos")
    if permitidos is not None and e.tipo not in permitidos:
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.tiposPermitidos",
                    f"El estado estable calculado es {e.tipo} ({e.regimen}), que no está entre los tipos "
                    f"permitidos ({', '.join(permitidos)}). No se busca solo la rama permitida para "
                    "llamarla estable.", [cid])
        return rechazo()

    p = e.propiedades
    props = {"u": p.u, "h": p.h, "v": p.v, "s": p.s, "cp": p.cp, "cv": p.cv}
    est = e.estabilidad
    ramas = "; ".join(f"{n} [{lo:.4g}, {hi:.4g}] kg/m3" for n, lo, hi in est.ramas)
    margen = (f"menor TPD/P en otro mínimo local: {est.margen:.3g} (a {est.rho_margen:.6g} kg/m3)"
              if est.margen is not None else "sin otro mínimo local en las ramas")
    verificaciones = [
        _verif("estabilidad", "cumple", est.residuo, agua.TOL_ESTABILIDAD,
               "Residuo = max(0, -min TPD)/P, con TPD(ρ) = ρ[f(T,ρ) - g*] + P* (distancia al plano tangente "
               f"de sustancia pura a T fija). Búsqueda: {est.evaluaciones} evaluaciones en {ramas}; {margen}. "
               f"(∂P/∂ρ)_T = {p.dP_drho_T:.6g} Pa·m3/kg > 0. Alcance: fases fluidas de IAPWS-95; el sólido "
               "lo excluye el dominio, no esta búsqueda."),
        _verif("dominio", "cumple", None, None,
               f"T en [{agua.T_MIN}, {agua.T_MAX}] K, P en [{agua.P_MIN:g}, {agua.P_MAX:g}] Pa, fuera de la "
               f"banda crítica T en [{agua.T_CRITICA[0]:.6g}, {agua.T_CRITICA[1]:.6g}] K × P en "
               f"[{agua.P_CRITICA[0]:.6g}, {agua.P_CRITICA[1]:.6g}] Pa. Sin hielo estable: T ≥ 273.16 K y "
               "P ≤ 100 MPa (curvas de fusión IAPWS R14-08). Comprobación de pertenencia, sin residuo."),
        _verif("ecuacion_estado", "cumple", e.residuo_eos, agua.TOL_EOS,
               "Residuo = |P(T,ρ) - P| / max(P, ρ(∂P/∂ρ)_T): error de presión relativo a la presión o al "
               "módulo de compresibilidad isoterma, el mayor."),
        _verif("identidad_h_u_Pv", "cumple", abs(p.h - p.u - P * p.v) / (agua.R * T), 1e-9,
               "Residuo = |h - u - P v|/(R T) con la P especificada; incluye el error de resolver ρ."),
    ]
    if math.isfinite(e.residuo_derivadas):
        verificaciones.append(_verif(
            "derivadas", "cumple" if e.residuo_derivadas <= agua.TOL_DERIVADAS else "no_cumple",
            e.residuo_derivadas, agua.TOL_DERIVADAS,
            "Residuo = max(|cp - (∂h/∂T)_P|/cp, |cv - (∂u/∂T)_ρ|/cv), derivadas analíticas de la EOS frente a "
            "diferencias centradas de paso 1e-5·T re-resolviendo ρ en la misma rama."))
    else:
        verificaciones.append(_verif(
            "derivadas", "no_evaluable", None, None,
            "A T ± 1e-5·T la presión pedida cae fuera de la misma rama monofásica; cp y cv se publican "
            "desde la EOS sin contraste numérico."))
    if any(v["estado"] == "no_cumple" for v in verificaciones):
        lector.diag("no_convergente", "MOTOR_ESTADO_VERIFICACION_FALLIDA", "declaracion.especificacion",
                    "Una verificación del estado no se cumple; no se publica.", [cid])
        return rechazo()
    if e.saturacion is not None:
        s = e.saturacion
        verificaciones.append(_verif(
            "saturacion", "cumple", s.residuo, agua.TOL_SATURACION_MAXWELL,
            f"Curva que separa las ramas: Psat = {s.Psat:.9g} Pa, ρ' = {s.rho_l:.9g}, ρ'' = {s.rho_v:.9g} kg/m3. "
            "Residuo de Maxwell = max(|g'-g''|/(R T), |P(ρ'')-Psat|/Psat, |P(ρ')-Psat|/(ρ'(∂P/∂ρ)_T')). "
            f"|P/Psat - 1| = {abs(P / s.Psat - 1):.3g} (banda de indeterminación {agua.TOL_SATURACION:g})."))
    verificaciones.append(_verif(
        "reconstruccion_material", "cumple", 0.0, 1e-12,
        "Una fase con la composición global: Σβ = 1 y z = x exactamente."))
    for c in componentes_crudos:
        if isinstance(c, dict) and c.get("id") == cid and isinstance(c.get("masaMolar"), dict):
            q = c["masaMolar"].get("cantidad") or {}
            if q.get("valor") is not None:
                factor = {"kg/mol": 1.0, "g/mol": 1e-3}[q["unidad"]]
                verificaciones.append(_verif(
                    "masa_molar", "cumple", abs(q["valor"] * factor - agua.M) / agua.M, TOL_MASA_MOLAR,
                    "Masa molar declarada frente a la del modelo."))
    if permitidos is not None or politica["cantidad"] == "monofasico":
        verificaciones.append(_verif(
            "politica_fases", "cumple", None, None,
            f"El estado estable tiene una fase ({e.tipo}), compatible con la política declarada."))
    if politica["cambioInterno"] == "prohibido":
        verificaciones.append(_verif(
            "cambio_interno", "no_evaluable", None, None,
            "Consulta puntual sin trayectoria: no hay cambio interno que comparar. No implica monofásico "
            "ni prueba ausencia de transición futura."))

    cas = comps[0][1]
    fase = {
        "id": f"{e.tipo}-1", "tipo": e.tipo, "regimen": e.regimen,
        "fraccionMolar": 1.0, "fraccionMasica": 1.0, "fraccionVolumen": 1.0,
        "composicionMolar": {str(cid): 1.0}, "propiedades": dict(props),
    }
    evaluacion = {
        "T": T, "P": P,
        "composicionMolar": {str(cid): 1.0},
        "componentes": [{"id": cid, "cas": cas, "masaMolarKgMol": agua.M, "fuente": FUENTE_MASA_MOLAR}],
        "fases": [fase],
        "mezcla": dict(props),
        "referencia": dict(REFERENCIA_AGUA),
        "estabilidad": {
            "estado": "estable", "alcance": list(ALCANCE_ESTABILIDAD),
            "metodo": "Distancia al plano tangente de sustancia pura a T fija sobre las ramas monofásicas "
                      "de IAPWS-95 (vapor y líquido separados por la curva de saturación por debajo de T_c; "
                      "una rama por encima), malla de 400 puntos por rama hasta ρ(1 GPa) y refinamiento "
                      "acotado de cada mínimo local. Tolerancia -min TPD/P ≤ 1e-9.",
        },
        "verificaciones": verificaciones,
    }
    return _respuesta(sid, dict(MODELO_AGUA), "evaluado", evaluacion, lector.diagnosticos)


# ----------------------------------------------------------------------
# H3: respuestas de PH, UP y UV (una o dos fases)
# ----------------------------------------------------------------------
_TEXTO_DOMINIO = (
    f"T en [{agua.T_MIN}, {agua.T_MAX}] K, P en [{agua.P_MIN:g}, {agua.P_MAX:g}] Pa, fuera de la banda crítica "
    f"T en [{agua.T_CRITICA[0]:.6g}, {agua.T_CRITICA[1]:.6g}] K × P en [{agua.P_CRITICA[0]:.6g}, "
    f"{agua.P_CRITICA[1]:.6g}] Pa; coexistencia solo con Tsat ≤ {agua.T_COEX_MAX:.6g} K. Sin hielo estable: "
    "T ≥ 273.16 K y P ≤ 100 MPa (curvas de fusión IAPWS R14-08). Comprobación de pertenencia, sin residuo.")


def _verificaciones_comunes(e, cid, politica, componentes_crudos):
    """masa_molar, politica_fases y cambio_interno, iguales que en TP."""
    vs = []
    for c in componentes_crudos:
        if isinstance(c, dict) and c.get("id") == cid and isinstance(c.get("masaMolar"), dict):
            q = c["masaMolar"].get("cantidad") or {}
            if q.get("valor") is not None:
                factor = {"kg/mol": 1.0, "g/mol": 1e-3}[q["unidad"]]
                vs.append(_verif("masa_molar", "cumple", abs(q["valor"] * factor - agua.M) / agua.M,
                                 TOL_MASA_MOLAR, "Masa molar declarada frente a la del modelo."))
    if politica.get("tiposPermitidos") is not None or politica["cantidad"] == "monofasico":
        vs.append(_verif("politica_fases", "cumple", None, None,
                         f"Fases del estado estable ({', '.join(f.tipo for f in e.fases)}) compatibles con la "
                         "política declarada; se comprueba después de calcular el equilibrio."))
    if politica["cambioInterno"] == "prohibido":
        vs.append(_verif("cambio_interno", "no_evaluable", None, None,
                         "Consulta puntual sin trayectoria: no hay cambio interno que comparar. No implica "
                         "monofásico ni prueba ausencia de transición futura."))
    return vs


def _evaluada_inversa(lector, sid, e, cid, politica, comps, componentes_crudos, rechazo):
    tipos = [f.tipo for f in e.fases]
    permitidos = politica.get("tiposPermitidos")
    if permitidos is not None and any(t not in permitidos for t in tipos):
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.tiposPermitidos",
                    f"El estado estable calculado tiene {' y '.join(tipos)}; no todas están entre los tipos "
                    f"permitidos ({', '.join(permitidos)}). No se fuerza una rama metastable para cumplirlo.",
                    [cid])
        return rechazo()
    if politica["cantidad"] == "monofasico" and len(e.fases) > 1:
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.cantidad",
                    f"La política es monofásica, pero el estado estable que cumple la especificación tiene "
                    f"dos fases (vapor q = {e.fases[1].fraccion:.6g}).", [cid])
        return rechazo()

    T, P, RT = e.T, e.P, agua.R * e.T
    vs = []
    if e.coexistencia is None:
        est = e.estabilidad[0]
        ramas = "; ".join(f"{n} [{lo:.4g}, {hi:.4g}] kg/m3" for n, lo, hi in est.ramas)
        vs.append(_verif(
            "estabilidad", "cumple", est.residuo, agua.TOL_ESTABILIDAD,
            "Una fase: residuo = max(0, -min TPD)/P a la T y P resultantes, como en TP. Búsqueda: "
            f"{est.evaluaciones} evaluaciones en {ramas}. (∂P/∂ρ)_T = {e.fases[0].propiedades.dP_drho_T:.6g} "
            "Pa·m3/kg > 0."))
    else:
        est = e.estabilidad[0]
        vs.append(_verif(
            "estabilidad", "cumple", est.residuo, agua.TOL_TM,
            "Coexistencia: residuo = max(0, -min tm), tm(ρ) = [ρ(f(T,ρ) - g*) + P*]/(ρ R T) con la tangente "
            "común g* = g'', P* = P'' (Δg/RT por masa de fase de prueba). Se anula en ρ' y ρ''. Búsqueda: "
            f"{est.evaluaciones} evaluaciones en las ramas monofásicas a T."))
    vs.append(_verif("dominio", "cumple", None, None, _TEXTO_DOMINIO))
    if e.coexistencia is not None:
        c = e.coexistencia
        vs.append(_verif(
            "equilibrio", "cumple", c.residuo, agua.TOL_SATURACION_MAXWELL,
            f"T' = T'' = {c.T:.9g} K por construcción. Residuo = max(|g'-g''|/(R T), |P'-P''|/max(P'', "
            f"ρ'(∂P/∂ρ)_T')); Newton en (ρ', ρ'') desde los ajustes, {c.iteraciones} iteraciones, hasta "
            f"que el residuo deja de bajar. Psat = P'' = {c.P:.9g} Pa."))
        if "presion_saturacion" in e.residuos:
            vs.append(_verif(
                "presion_saturacion", "cumple", e.residuos["presion_saturacion"], agua.TOL_INVERSION,
                "Residuo = |Psat(Tsat) - P|/P: Tsat(P) por Brent sobre el ajuste de Psat y Newton con la "
                "pendiente de Clapeyron (s''-s')/(v''-v')."))
    if "ecuacion_estado" in e.residuos:
        vs.append(_verif("ecuacion_estado", "cumple", e.residuos["ecuacion_estado"], agua.TOL_EOS,
                         "Residuo = |P(T,ρ) - P| / max(P, ρ(∂P/∂ρ)_T)."))
    escalas = {"PH": "h", "UP": "u = U/m", "UV": "u = U/m"}
    vs.append(_verif(
        "energia", "cumple" if e.residuos["energia"] <= agua.TOL_INVERSION else "no_cumple",
        e.residuos["energia"], agua.TOL_INVERSION,
        f"Residuo = |{escalas[e.especificacion].split(' ')[0]} reconstruida - especificada|/(R T), con la "
        f"especificada {escalas[e.especificacion]} y la reconstruida como Σ w_α (propiedad de fase)."))
    if "volumen" in e.residuos:
        vs.append(_verif(
            "volumen", "cumple" if e.residuos["volumen"] <= agua.TOL_INVERSION else "no_cumple",
            e.residuos["volumen"], agua.TOL_INVERSION,
            "Residuo = |v reconstruido - V/m| / (V/m); u y v se cumplen con la misma fracción de fase."))
    ident = max(abs(f.propiedades.h - f.propiedades.u - P * f.propiedades.v) / RT for f in e.fases)
    vs.append(_verif("identidad_h_u_Pv", "cumple" if ident <= 1e-9 else "no_cumple", ident, 1e-9,
                     "Residuo = max por fase de |h - u - P v|/(R T) con la P publicada."))
    ident_g = max(abs(f.propiedades.g - (f.propiedades.h - T * f.propiedades.s)) / RT for f in e.fases)
    vs.append(_verif("identidad_g_h_Ts", "cumple" if ident_g <= 1e-12 else "no_cumple", ident_g, 1e-12,
                     "Residuo = max por fase de |g - (h - T s)|/(R T), g desde φ: misma referencia en todas las fases."))
    if e.coexistencia is None:
        if math.isfinite(e.residuo_derivadas):
            vs.append(_verif(
                "derivadas", "cumple" if e.residuo_derivadas <= agua.TOL_DERIVADAS else "no_cumple",
                e.residuo_derivadas, agua.TOL_DERIVADAS,
                "Residuo = max(|cp - (∂h/∂T)_P|/cp, |cv - (∂u/∂T)_ρ|/cv) frente a diferencias centradas."))
        else:
            vs.append(_verif("derivadas", "no_evaluable", None, None,
                             "A T ± 1e-5·T la presión cae fuera de la misma rama; cp y cv sin contraste numérico."))
        if e.saturacion_rama is not None:
            s_ = e.saturacion_rama
            vs.append(_verif(
                "saturacion", "cumple", s_.residuo, agua.TOL_SATURACION_MAXWELL,
                f"Curva que separa las ramas a T: Psat = {s_.Psat:.9g} Pa; residuo de Maxwell de los ajustes."))
    w = [f.fraccion for f in e.fases]
    eps = [f.fraccion * f.propiedades.v / e.v for f in e.fases]
    vs.append(_verif("reconstruccion_material", "cumple", abs(sum(w) - 1.0), 1e-12,
                     "Residuo = |Σ β_α x_α - z| = |Σ β_α - 1| (un componente, x_α = z = 1)."))
    res_bases = max(abs(sum(w) - 1.0), abs(sum(eps) - 1.0))
    vs.append(_verif(
        "bases_fase", "cumple" if res_bases <= 1e-12 else "no_cumple", res_bases, 1e-12,
        "Residuo = max(|Σ w_α - 1|, |Σ ε_α - 1|), ε_α = w_α v_α / v. Fracción molar = másica (un "
        "componente); la volumétrica difiere." + (f" Fracción de vapor q = {w[-1]:.9g}." if len(w) > 1 else "")
        + (f" Fases con fracción < {agua.Q_MIN:g} se tratan como ausentes (conjunto activo)."
           if e.coexistencia is not None else "")))
    vs.append(_verif("unicidad", "cumple", None, None, e.unicidad))
    vs.extend(_verificaciones_comunes(e, cid, politica, componentes_crudos))
    if any(v["estado"] == "no_cumple" for v in vs):
        lector.diag("no_convergente", "MOTOR_ESTADO_VERIFICACION_FALLIDA", "declaracion.especificacion",
                    "Una verificación del estado no se cumple; no se publica.", [cid])
        return rechazo()

    fases = []
    for f, ep in zip(e.fases, eps):
        p = f.propiedades
        fases.append({
            "id": f"{f.tipo}-1", "tipo": f.tipo, "regimen": f.regimen,
            "fraccionMolar": f.fraccion, "fraccionMasica": f.fraccion, "fraccionVolumen": ep,
            "composicionMolar": {str(cid): 1.0},
            "propiedades": {"u": p.u, "h": p.h, "v": p.v, "s": p.s, "cp": p.cp, "cv": p.cv},
        })
    mezcla = {"u": e.u, "h": e.h, "v": e.v, "s": e.s}
    if e.cp is not None and len(e.fases) == 1 and not e.frontera:
        mezcla.update(cp=e.cp, cv=e.cv)
    metodo = ("Estado de una fase: distancia al plano tangente a la T y P resultantes sobre las ramas monofásicas "
              "de IAPWS-95, como en TP." if e.coexistencia is None else
              "Coexistencia: tangente común (g'', P'') sobre las ramas monofásicas a Tsat; tm ≥ -1e-9 en 400 "
              "puntos por rama con refinamiento de cada mínimo local.")
    criterio = {"PH": "Criterio PH: máximo de S a (H, P, n), equivalente al estado estable en G a su (T, P) con h dada.",
                "UP": "Criterio UP: estado estable en G a su propia (T, P) cuya u = U/m coincide; único porque u "
                      "crece a lo largo de la isobara de equilibrio (no se invoca un extremo de S a U, P).",
                "UV": "Criterio UV: máximo de S a (U, V, n); un estado homogéneo lo cumple si y solo si es estable "
                      "en G a su propia (T, P), y la coexistencia es la envolvente dentro de la campana."}
    evaluacion = {
        "T": T, "P": P,
        "composicionMolar": {str(cid): 1.0},
        "componentes": [{"id": cid, "cas": comps[0][1], "masaMolarKgMol": agua.M, "fuente": FUENTE_MASA_MOLAR}],
        "fases": fases,
        "mezcla": mezcla,
        "referencia": dict(REFERENCIA_AGUA),
        "estabilidad": {"estado": "estable", "alcance": list(ALCANCE_ESTABILIDAD),
                        "metodo": f"{criterio[e.especificacion]} {metodo}"},
        "verificaciones": vs,
    }
    return _respuesta(sid, dict(MODELO_AGUA), "evaluado", evaluacion, lector.diagnosticos)
