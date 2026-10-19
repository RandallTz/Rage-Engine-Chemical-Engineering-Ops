"""
Lector estricto del modelo común v0. Devuelve el mismo dict si es válido; si
no, ErrorModelo con la ruta del primer problema. No convierte unidades ni
completa valores: un dato que falta es un error, nunca un valor por omisión.

La parte matemática se valida con el lector del documento v2 de la
adimensionalización (misma representación), y la configuración de ese motor
con su lector de documentos: no se duplica ninguna regla.
"""

import json

from core.adimensionalizacion import lector as adim

VERSION = 0
LIMITE_BYTES = 8_000_000
CLAVES = ["formato", "version", "id", "nombre", "componentes", "termodinamica", "volumenes", "corrientes",
          "intercambios", "datos", "matematico", "estudio", "motores", "procedencia"]
FUNCIONES_DATO = ["inicial", "frontera", "geometria", "estudio", "parametro"]
FRONTERAS = ["rigida", "presion_prescrita", "sin_relacion", "malla_1d"]
SUPUESTOS_CIERRE = ["fase_no_evaluada", "u_lineal"]
PROCEDENCIAS = ["documento_adimensional", "ensamblaje_v2", "hoja_motor_materia", "nuevo"]
MOTORES = ["adimensionalizacion"]


class ErrorModelo(Exception):
    def __init__(self, ruta, mensaje):
        super().__init__(f"{ruta}: {mensaje}")
        self.ruta = ruta
        self.mensaje = mensaje


def _fallo(ruta, motivo):
    raise ErrorModelo(ruta, motivo)


def _obj(v, ruta):
    if not isinstance(v, dict):
        _fallo(ruta, "se esperaba un objeto")
    return v


def _claves(v, ruta, obligatorias, opcionales=()):
    o = _obj(v, ruta)
    faltan = [k for k in obligatorias if k not in o]
    if faltan:
        _fallo(ruta, "faltan " + ", ".join(faltan))
    sobran = [k for k in o if k not in obligatorias and k not in opcionales]
    if sobran:
        _fallo(ruta, "campos desconocidos: " + ", ".join(sobran))
    return o


def _texto(v, ruta):
    if not isinstance(v, str) or not v.strip():
        _fallo(ruta, "texto requerido")


def _lista(v, ruta):
    if not isinstance(v, list):
        _fallo(ruta, "se esperaba una lista")
    return v


def _bool(v, ruta):
    if not isinstance(v, bool):
        _fallo(ruta, "se esperaba verdadero o falso")


def _opcion(v, ruta, opciones):
    if v not in opciones:
        _fallo(ruta, f"valor no admitido ({v!r}); admitidos: {', '.join(map(str, opciones))}")


def _numero(v, ruta):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
        _fallo(ruta, "número finito requerido")


def _unicos(items, ruta, clave="id"):
    vistos = set()
    for i, x in enumerate(items):
        k = _obj(x, f"{ruta}[{i}]").get(clave)
        if k is None:
            _fallo(f"{ruta}[{i}].{clave}", "requerido")
        if k in vistos:
            _fallo(f"{ruta}[{i}].{clave}", f"identidad repetida: {k!r}")
        vistos.add(k)
    return vistos


def _ref(v, conjunto, ruta, que):
    if v not in conjunto:
        _fallo(ruta, f"referencia inexistente ({que} {v!r})")


class _Lectura:
    def __init__(self, m):
        self.m = m
        self.datos = set(m["datos"])

    def dato(self, v, ruta):
        _ref(v, self.datos, ruta, "dato")


def leer_modelo_comun(dato):
    if len(json.dumps(dato, ensure_ascii=False).encode("utf-8")) > LIMITE_BYTES:
        _fallo("modelo", "el modelo supera 8 MB")
    m = _claves(dato, "modelo", CLAVES, ["restricciones", "observables", "verificaciones"])
    _opcion(m["formato"], "formato", ["rage.modelo"])
    _opcion(m["version"], "version", [VERSION])
    _texto(m["id"], "id")
    _texto(m["nombre"], "nombre")
    datos = _obj(m["datos"], "datos")
    for k, d in datos.items():
        r = f"datos.{k}"
        o = _claves(d, r, ["magnitud", "funcion", "declaracion", "origen"])
        _texto(o["magnitud"], r + ".magnitud")
        _opcion(o["funcion"], r + ".funcion", FUNCIONES_DATO)
        dec = _claves(o["declaracion"], r + ".declaracion", ["texto", "unidad"])
        if not isinstance(dec["texto"], str):
            _fallo(r + ".declaracion.texto", "texto requerido (vacío = dato pendiente)")
        if not isinstance(dec["unidad"], str):
            _fallo(r + ".declaracion.unidad", "texto requerido (vacío si la magnitud no tiene unidad)")
        org = _claves(o["origen"], r + ".origen", ["propietarioId", "ruta"])
        _texto(org["propietarioId"], r + ".origen.propietarioId")
        _texto(org["ruta"], r + ".origen.ruta")
    lec = _Lectura(m)

    comps = _lista(m["componentes"], "componentes")
    ids_comp = _unicos(comps, "componentes")
    for i, c in enumerate(comps):
        r = f"componentes[{i}]"
        o = _claves(c, r, ["id", "nombre", "simbolo"], ["identidadQuimica", "masaMolar"])
        if isinstance(o["id"], bool) or not isinstance(o["id"], int):
            _fallo(r + ".id", "entero requerido")
        _texto(o["nombre"], r + ".nombre")
        _texto(o["simbolo"], r + ".simbolo")
        if "identidadQuimica" in o:
            _claves(o["identidadQuimica"], r + ".identidadQuimica", [], ["cas", "proveedorId"])

    td = _claves(m["termodinamica"], "termodinamica", ["paquetes"])
    paquetes = _lista(td["paquetes"], "termodinamica.paquetes")
    ids_paq = _unicos(paquetes, "termodinamica.paquetes")
    for i, p in enumerate(paquetes):
        r = f"termodinamica.paquetes[{i}]"
        o = _claves(p, r, ["id", "modelo"], ["datosPuros"])
        mod = _claves(o["modelo"], r + ".modelo", ["id", "version"])
        _texto(mod["id"], r + ".modelo.id")
        _texto(mod["version"], r + ".modelo.version")
        if "datosPuros" in o:
            _obj(o["datosPuros"], r + ".datosPuros")

    vols = _lista(m["volumenes"], "volumenes")
    ids_vol = _unicos(vols, "volumenes")
    for i, v in enumerate(vols):
        _leer_volumen(v, f"volumenes[{i}]", ids_comp, ids_paq, lec)

    cors = _lista(m["corrientes"], "corrientes")
    _unicos(cors, "corrientes")
    for i, c in enumerate(cors):
        _leer_corriente(c, f"corrientes[{i}]", ids_comp, ids_vol, lec)

    ints = _lista(m["intercambios"], "intercambios")
    _unicos(ints, "intercambios")
    for i, q in enumerate(ints):
        _leer_intercambio(q, f"intercambios[{i}]", ids_vol, lec)

    if m["matematico"] is not None:
        try:
            adim.leer_modelo(m["matematico"], "matematico", version=2)
        except adim.ErrorContrato as e:
            _fallo(e.ruta, e.mensaje)

    if m["estudio"] is not None:
        _leer_estudio(m["estudio"], lec)

    if "restricciones" in m:
        _leer_restricciones(m)
    for clave, campos in (("observables", ["id", "nombre", "unidadSI", "expresion"]), ("verificaciones", ["id", "descripcion", "expresion", "escala"])):
        if clave in m:
            if m["matematico"] is None:
                _fallo(clave, "se declaran sobre variables del modelo matemático")
            xs = _lista(m[clave], clave)
            _unicos(xs, clave)
            for i, x in enumerate(xs):
                o = _claves(x, f"{clave}[{i}]", campos, ["tolerancia"])
                _obj(o["expresion"], f"{clave}[{i}].expresion")

    motores = _obj(m["motores"], "motores")
    for nombre, cfg in motores.items():
        _opcion(nombre, f"motores.{nombre}", MOTORES)
    if "adimensionalizacion" in motores:
        _leer_adim(motores["adimensionalizacion"], m)

    proc = _obj(m["procedencia"], "procedencia")
    _opcion(proc.get("tipo"), "procedencia.tipo", PROCEDENCIAS)
    return m


def _leer_volumen(v, r, ids_comp, ids_paq, lec):
    o = _claves(v, r, ["id", "componenteIds", "balances", "supuestos", "frontera", "inicial", "termodinamica"],
                ["terminos", "volumenDatoId"])
    # Datos de los términos que conservan los supuestos (motor de balances): "<rol>.<componenteId>" o un término de energía.
    for k, d in _obj(o.get("terminos", {}), r + ".terminos").items():
        rol = k.split(".")[0]
        _opcion(rol, f"{r}.terminos.{k}", ["generacion", "consumo", "resto", "calor", "trabajo_viscoso", "fuerzas", "fuente"])
        lec.dato(d, f"{r}.terminos.{k}")
    if "volumenDatoId" in o:
        lec.dato(o["volumenDatoId"], r + ".volumenDatoId")
    _texto(o["id"], r + ".id")
    for j, c in enumerate(_lista(o["componenteIds"], r + ".componenteIds")):
        _ref(c, ids_comp, f"{r}.componenteIds[{j}]", "componente")
    b = _claves(o["balances"], r + ".balances", ["materia", "energia", "momento"])
    for k in ("materia", "energia", "momento"):
        _bool(b[k], f"{r}.balances.{k}")
    s = _claves(o["supuestos"], r + ".supuestos", ["materia", "energia"])
    _obj(s["materia"], r + ".supuestos.materia")
    if s["energia"] is not None:
        _obj(s["energia"], r + ".supuestos.energia")
    f = _obj(o["frontera"], r + ".frontera")
    _opcion(f.get("tipo"), r + ".frontera.tipo", FRONTERAS)
    if f["tipo"] == "rigida":
        _claves(f, r + ".frontera", ["tipo", "datoId"], ["presionRestriccionId"])
        lec.dato(f["datoId"], r + ".frontera.datoId")
    elif f["tipo"] == "presion_prescrita":
        _claves(f, r + ".frontera", ["tipo", "presionId"])
        lec.dato(f["presionId"], r + ".frontera.presionId")
    else:
        _claves(f, r + ".frontera", ["tipo"])
    ini = _obj(o["inicial"], r + ".inicial")
    if ini.get("tipo") == "por_datos":
        _claves(ini, r + ".inicial", ["tipo"])
    else:
        _claves(ini, r + ".inicial", ["cantidades"], ["energia"])
        cant = _claves(ini["cantidades"], r + ".inicial.cantidades", ["base", "datoIds"])
        _opcion(cant["base"], r + ".inicial.cantidades.base", ["masica", "molar"])
        for k, d in _obj(cant["datoIds"], r + ".inicial.cantidades.datoIds").items():
            lec.dato(d, f"{r}.inicial.cantidades.datoIds.{k}")
        if "energia" in ini:
            en = _claves(ini["energia"], r + ".inicial.energia", ["tipo", "datoId"])
            _opcion(en["tipo"], r + ".inicial.energia.tipo", ["U", "T"])
            lec.dato(en["datoId"], r + ".inicial.energia.datoId")
        elif t_tipo(o) == "equilibrio":
            _fallo(r + ".inicial", "faltan energia")
    # La termodinámica siempre presente: ningún volumen sin cierre declarado.
    t = o["termodinamica"]
    if not isinstance(t, dict) or "tipo" not in t:
        _fallo(r + ".termodinamica", "todo volumen declara su cierre termodinámico (equilibrio con un paquete, "
                                     "o un supuesto explícito con su motivo)")
    _opcion(t["tipo"], r + ".termodinamica.tipo", ["equilibrio", "supuesto"])
    if t["tipo"] == "equilibrio":
        _claves(t, r + ".termodinamica", ["tipo", "paqueteId", "politica"])
        _ref(t["paqueteId"], ids_paq, r + ".termodinamica.paqueteId", "paquete")
        pol = _claves(t["politica"], r + ".termodinamica.politica", ["cantidad", "cambioInterno", "evaluacion"],
                      ["tiposPermitidos"])
        _opcion(pol["cantidad"], r + ".termodinamica.politica.cantidad", ["sin_restriccion", "monofasico"])
        _opcion(pol["cambioInterno"], r + ".termodinamica.politica.cambioInterno", ["permitido", "prohibido"])
        _opcion(pol["evaluacion"], r + ".termodinamica.politica.evaluacion", ["equilibrio_estable"])
        if f["tipo"] not in ("rigida", "presion_prescrita"):
            _fallo(r + ".frontera", "un cierre de equilibrio necesita frontera rígida (UV) o presión prescrita (PH)")
    else:
        _claves(t, r + ".termodinamica", ["tipo", "supuesto", "motivo"], ["parametros"])
        _opcion(t["supuesto"], r + ".termodinamica.supuesto", SUPUESTOS_CIERRE)
        _texto(t["motivo"], r + ".termodinamica.motivo")
        if "parametros" in t:
            if t["supuesto"] != "u_lineal":
                _fallo(r + ".termodinamica.parametros", "solo u_lineal declara parámetros")
            par = _claves(t["parametros"], r + ".termodinamica.parametros", ["cId", "uRefId", "TRefId", "TMinId", "TMaxId"], ["rhoId"])
            for k, d in par.items():
                lec.dato(d, f"{r}.termodinamica.parametros.{k}")


def t_tipo(o):
    t = o.get("termodinamica")
    return t.get("tipo") if isinstance(t, dict) else None


def _extremo(v, ids_vol, ruta):
    if v is not None:
        _ref(v, ids_vol, ruta, "volumen")


def _leer_corriente(c, r, ids_comp, ids_vol, lec):
    o = _claves(c, r, ["id", "desde", "hasta", "componenteIds", "mecanismo", "materia"],
                ["estadoExterior", "extraccion", "constante"])
    _extremo(o["desde"], ids_vol, r + ".desde")
    _extremo(o["hasta"], ids_vol, r + ".hasta")
    if o["desde"] is None and o["hasta"] is None:
        _fallo(r, "una corriente necesita al menos un extremo en un volumen")
    for j, k in enumerate(_lista(o["componenteIds"], r + ".componenteIds")):
        _ref(k, ids_comp, f"{r}.componenteIds[{j}]", "componente")
    _opcion(o["mecanismo"], r + ".mecanismo", ["convectivo", "selectivo", None])
    mat = _obj(o["materia"], r + ".materia")
    _opcion(mat.get("modo"), r + ".materia.modo", ["por_componente", "total_desde_donante", "total_y_composicion"])
    if mat["modo"] == "total_y_composicion":
        _claves(mat, r + ".materia", ["modo", "base", "caudalId", "fracciones"])
        lec.dato(mat["caudalId"], r + ".materia.caudalId")
        fr = _obj(mat["fracciones"], r + ".materia.fracciones")
        for k, x in fr.items():
            _ref(int(k) if str(k).lstrip("-").isdigit() else k, ids_comp, f"{r}.materia.fracciones.{k}", "componente")
            _numero(x, f"{r}.materia.fracciones.{k}")
        if abs(sum(fr.values()) - 1) > 1e-12 or any(x < 0 for x in fr.values()):
            _fallo(r + ".materia.fracciones", "fracciones no negativas que suman uno")
    elif mat["modo"] == "por_componente":
        _claves(mat, r + ".materia", ["modo", "base", "caudalIds"])
        for k, d in _obj(mat["caudalIds"], r + ".materia.caudalIds").items():
            _ref(int(k) if str(k).lstrip("-").isdigit() else k, ids_comp, f"{r}.materia.caudalIds.{k}", "componente")
            lec.dato(d, f"{r}.materia.caudalIds.{k}")
    else:
        _claves(mat, r + ".materia", ["modo", "base", "caudalId"])
        lec.dato(mat["caudalId"], r + ".materia.caudalId")
    _opcion(mat["base"], r + ".materia.base", ["masica", "molar", "volumetrica"])
    if "constante" in o:
        _bool(o["constante"], r + ".constante")
    if "extraccion" in o:
        for k in _obj(o["extraccion"], r + ".extraccion"):
            _ref(k, ids_vol, f"{r}.extraccion.{k}", "volumen")
    if "estadoExterior" in o:
        ee = _obj(o["estadoExterior"], r + ".estadoExterior")
        lec.dato(ee.get("temperaturaId"), r + ".estadoExterior.temperaturaId")


def _leer_intercambio(q, r, ids_vol, lec):
    o = _claves(q, r, ["id", "desde", "hasta", "ley"], ["temperaturaFronteraId"])
    _extremo(o["desde"], ids_vol, r + ".desde")
    _extremo(o["hasta"], ids_vol, r + ".hasta")
    ley = _obj(o["ley"], r + ".ley")
    _opcion(ley.get("tipo"), r + ".ley.tipo", ["impuesto", "conductancia"])
    if ley["tipo"] == "impuesto":
        _claves(ley, r + ".ley", ["tipo", "potenciaId"])
        lec.dato(ley["potenciaId"], r + ".ley.potenciaId")
    else:
        _claves(ley, r + ".ley", ["tipo", "conductanciaId"], ["temperaturaExteriorId"])
        lec.dato(ley["conductanciaId"], r + ".ley.conductanciaId")
        if "temperaturaExteriorId" in ley:
            lec.dato(ley["temperaturaExteriorId"], r + ".ley.temperaturaExteriorId")
    if "temperaturaFronteraId" in o:
        lec.dato(o["temperaturaFronteraId"], r + ".temperaturaFronteraId")


def _leer_estudio(e, lec):
    o = _claves(e, "estudio", ["tipo", "tiempoId", "metodoSolicitado", "muestras", "rtol", "atol"],
                ["espacial", "cierreMasico"])
    _opcion(o["tipo"], "estudio.tipo", ["temporal"])
    lec.dato(o["tiempoId"], "estudio.tiempoId")
    if o["metodoSolicitado"] is not None:
        _texto(o["metodoSolicitado"], "estudio.metodoSolicitado")
    if isinstance(o["muestras"], bool) or not isinstance(o["muestras"], int) or o["muestras"] < 2:
        _fallo("estudio.muestras", "entero mayor o igual que 2")
    _numero(o["rtol"], "estudio.rtol")
    at = _claves(o["atol"], "estudio.atol", ["cantidad"], ["energia"])
    for k, x in at.items():
        _numero(x, f"estudio.atol.{k}")
    if "espacial" in o:
        esp = _claves(o["espacial"], "estudio.espacial", ["celdas", "frontera"])
        if isinstance(esp["celdas"], bool) or not isinstance(esp["celdas"], int):
            _fallo("estudio.espacial.celdas", "entero requerido")
        _opcion(esp["frontera"], "estudio.espacial.frontera", ["periodica", "valores", "sin_flujo", ""])
    if "cierreMasico" in o:
        _opcion(o["cierreMasico"], "estudio.cierreMasico", ["densidad", "volumen", ""])


def _leer_restricciones(m):
    """Dominio de las variables del modelo matemático: el cálculo se detiene
    en el instante en que una variable lo abandonaría (agotamiento)."""
    if m["matematico"] is None:
        _fallo("restricciones", "las restricciones se declaran sobre variables del modelo matemático")
    campos = {s["id"] for s in m["matematico"]["simbolos"] if s["rol"] == "campo"}
    rs = _lista(m["restricciones"], "restricciones")
    vistos = set()
    for i, x in enumerate(rs):
        r = f"restricciones[{i}]"
        if "simboloId" in _obj(x, r):
            o = _claves(x, r, ["simboloId", "tipo"])
            _ref(o["simboloId"], campos, r + ".simboloId", "variable del modelo matemático")
            if o["simboloId"] in vistos:
                _fallo(r + ".simboloId", f"identidad repetida: {o['simboloId']!r}")
            vistos.add(o["simboloId"])
        else:
            # Una expresión de las variables que debe mantenerse >= 0 (dominio de validez de un supuesto).
            o = _claves(x, r, ["expresion", "tipo", "descripcion"])
            _obj(o["expresion"], r + ".expresion")
            _texto(o["descripcion"], r + ".descripcion")
        _opcion(o["tipo"], r + ".tipo", ["no_negativo"])


def _leer_adim(cfg, m):
    o = _claves(cfg, "motores.adimensionalizacion", ["version", "formas", "activaId"], ["exploracion"])
    if m["matematico"] is None:
        _fallo("motores.adimensionalizacion", "la configuración de adimensionalización necesita el modelo matemático")
    doc = {"formato": "adimensionalizacion", "version": o["version"], "id": m["id"], "nombre": m["nombre"],
           "modelo": m["matematico"], "formas": o["formas"], "activaId": o["activaId"],
           **({"exploracion": o["exploracion"]} if "exploracion" in o else {})}
    try:
        adim.leer_documento(doc)
    except adim.ErrorContrato as e:
        _fallo("motores.adimensionalizacion." + e.ruta, e.mensaje)
