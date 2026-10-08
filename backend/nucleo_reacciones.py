"""
Frontera de /laboratorio/{balancear,equilibrio,lote}.

Los tres servicios comparten el mismo patron que el resto del laboratorio:
aqui no hay fisica, solo el paso de la peticion a los modulos del nucleo y
la vuelta, con la trazabilidad y los diagnosticos envueltos.

POR QUE SON TRES ENDPOINTS Y NO UNO
-----------------------------------
Porque contestan tres preguntas distintas y con requisitos distintos:

  balancear    que reaccion conserva los elementos entre estas especies.
               Solo necesita la composicion elemental; ni propiedades
               termodinamicas ni tasas.
  equilibrio   donde para la reaccion si se la deja. Necesita dG de
               formacion, y no necesita ninguna cinetica.
  lote         que camino recorre en el tiempo. Necesita leyes de
               velocidad, y no necesita dG.

Meterlas en un endpoint con una bandera obligaria a declarar datos que no
hacen falta y a devolver campos vacios.

LA RELACION ENTRE LOS DOS ULTIMOS, QUE ES LA COMPROBACION
---------------------------------------------------------
Un lote con una cinetica termodinamicamente consistente
(`desde_equilibrio`) tiene que converger, cuando t tiende a infinito, a la
MISMA composicion que calcula /equilibrio. Son dos caminos
independientes: uno integra una ODE y el otro resuelve ln Q = ln K.
Coinciden a 1e-17 con los xilenos, y esa coincidencia es la validacion
cruzada de los dos servicios.
"""

import math

import numpy as np

from core import balanceo as bal
from core import cinetica as cin
from core import equilibrio as eqm
from core import errores as codigos
from core import estequiometria as est
from core import laboratorio as lab
from core import lote as lot
from core.errores import ErrorDeDatos, ErrorFisico, ErrorNumerico
from core.flash import EvaluadorFlash
from thermodynamics.elv import CalculadoraELV
from thermodynamics.entalpia import entalpia_de
from chemicals.identifiers import search_chemical
from thermo.chemical import Chemical
from thermodynamics.proveedor import ProveedorTermodinamico

from backend import trazabilidad


def _diagnostico(codigo, severidad, mensaje, accion=None, categoria="datos"):
    return {
        "codigo": codigo, "severidad": severidad, "categoria": categoria,
        "mensaje": mensaje, "accion_sugerida": accion,
        "bloque_ids": [], "conexion_ids": [], "variable_ids": [],
    }


def _resumen(diagnosticos):
    por_severidad, por_categoria = {}, {}
    for d in diagnosticos:
        por_severidad[d["severidad"]] = por_severidad.get(d["severidad"], 0) + 1
        por_categoria[d["categoria"]] = por_categoria.get(d["categoria"], 0) + 1
    return {
        "total": len(diagnosticos),
        "por_severidad": por_severidad,
        "por_categoria": por_categoria,
        "hay_errores": any(d["severidad"] == "error" for d in diagnosticos),
    }


def _envolver(resultado, entradas, estado, diagnosticos, modelo=None):
    resultado = dict(resultado)
    resultado["schema_version"] = lab.SCHEMA_VERSION
    resultado["estado"] = estado
    resultado["modelo_id"] = trazabilidad.huella(entradas)
    resultado["calculo"] = trazabilidad.construir_calculo_desde(
        entradas, modelo_termodinamico=modelo or lab.MODELO_POR_OMISION)
    resultado["diagnosticos"] = diagnosticos
    resultado["resumen_diagnosticos"] = _resumen(diagnosticos)
    return resultado


def _proveedor_de(componentes):
    """El proveedor, o un ErrorDeDatos con el motivo."""
    try:
        return ProveedorTermodinamico(list(componentes))
    except Exception as e:
        raise ErrorDeDatos(
            f"El modelo no admite estos componentes: {e}. Consulta cada uno en "
            "/laboratorio/sustancias/buscar, que dice ademas si sirve para "
            "reaccion.",
            codigo=codigos.LAB_COMPONENTE_NO_DISPONIBLE,
        ) from e


def _atomos_sin_proveedor(componentes):
    """
    La composicion elemental, SIN exigir grupos UNIFAC.

    Balancear es la conservacion de los atomos, y para eso no hace falta
    ningun modelo de actividad: hace falta saber de que esta hecha cada
    especie. Construir el proveedor completo aqui excluia el ejemplo
    canonico --la combustion del metano-- porque el metano no tiene grupos
    UNIFAC, y eso no tiene nada que ver con balancear.

    Devuelve (atomos, apto_para_termodinamica), para que la respuesta pueda
    decir que la reaccion esta balanceada Y que no se le puede calcular el
    calor.
    """
    atomos, sin_atomos, sin_unifac = [], [], []
    for nombre in componentes:
        try:
            metadata = search_chemical(nombre)
        except Exception:
            sin_atomos.append(nombre)
            atomos.append({})
            continue
        try:
            quimico = Chemical(metadata.common_name)
            a = dict(getattr(quimico, "atoms", None) or {})
            if not (getattr(quimico, "UNIFAC_groups", None) or {}):
                sin_unifac.append(nombre)
        except Exception:
            a = {}
        if not a:
            sin_atomos.append(nombre)
        atomos.append(a)

    if sin_atomos:
        raise ErrorDeDatos(
            f"No se pudo obtener la composicion elemental de: "
            f"{', '.join(sin_atomos)}. El balanceo ES la conservacion de los "
            "atomos, asi que sin ella no hay nada que hacer. Comprueba el nombre "
            "en /laboratorio/sustancias/buscar.",
            codigo=codigos.LAB_COMPONENTE_NO_DISPONIBLE,
        )
    return atomos, sin_unifac


def _validar_componentes(componentes):
    if len(componentes) < 2:
        raise ErrorDeDatos(
            f"Hacen falta al menos dos componentes y se dieron {len(componentes)}.",
            codigo=codigos.LAB_NUMERO_DE_COMPONENTES,
        )
    if len(componentes) > lab.MAX_COMPONENTES:
        raise ErrorDeDatos(
            f"Esta entrega admite hasta {lab.MAX_COMPONENTES} componentes y se "
            f"dieron {len(componentes)}.",
            codigo=codigos.LAB_NUMERO_DE_COMPONENTES,
        )
    if len(componentes) != len(set(componentes)):
        repetidos = sorted({c for c in componentes if componentes.count(c) > 1})
        raise ErrorDeDatos(
            f"Hay componentes repetidos: {', '.join(repetidos)}.",
            codigo=codigos.LAB_NUMERO_DE_COMPONENTES,
        )


# =====================================================================
# Balanceo
# =====================================================================

def balancear(request):
    """
    Las reacciones que conservan los elementos entre unas especies.

    Es el unico de los tres que NO necesita propiedades termodinamicas:
    solo la composicion elemental. Por eso admite especies que no sirven
    para reaccionar --sin entalpia de formacion-- y lo dice en vez de
    rechazarlas: balancear una reaccion es util aunque luego no se pueda
    calcular su calor.
    """
    componentes = list(request.componentes)
    entradas = {
        "servicio": "balancear",
        "componentes": componentes,
        "reactivos": list(request.reactivos or []),
    }
    diagnosticos = []
    try:
        _validar_componentes(componentes)
        # SIN proveedor: balancear no necesita UNIFAC. Ver
        # _atomos_sin_proveedor.
        atomos, sin_unifac = _atomos_sin_proveedor(componentes)
        resultado = bal.balancear(componentes, atomos,
                                  reactivos=list(request.reactivos or []))
    except (ErrorDeDatos, ErrorFisico) as e:
        datos = e.como_diccionario()
        return _envolver(
            {"especies": componentes, "reacciones": [], "elementos": [],
             "matriz_elemental": [], "dimension_del_espacio": 0,
             "diagnostico": {"caso": "error", "mensaje": str(e)}},
            entradas, "invalido",
            [_diagnostico(datos.get("codigo", codigos.SIN_CLASIFICAR), "error",
                          str(e), categoria=datos.get("categoria", "datos"))],
        )

    # Una especie puede servir para balancear y no para calcular su calor
    # de reaccion. Se dice, porque el usuario que balancea suele querer
    # calcular despues.
    resultado["aptas_para_termodinamica"] = not sin_unifac
    resultado["sin_grupos_unifac"] = list(sin_unifac)
    # Solo si de verdad salio una reaccion: decir "balanceado, pero..."
    # cuando no hubo balance es decir dos cosas y una es falsa.
    if sin_unifac and resultado["dimension_del_espacio"] > 0:
        diagnosticos.append(_diagnostico(
            codigos.LAB_INFO_FASE, "informacion",
            f"Balanceado, pero {', '.join(sin_unifac)} no tiene(n) grupos UNIFAC: "
            "esta reaccion NO se puede usar en /laboratorio/equilibrio ni en "
            "/laboratorio/lote con este modelo. Balancear solo necesita los "
            "atomos; calcular necesita ademas la termodinamica.",
            "Consulta las capacidades de cada especie en "
            "/laboratorio/sustancias/buscar.",
            categoria="informacion"))

    caso = resultado["diagnostico"]["caso"]
    if caso == "sin_reaccion":
        diagnosticos.append(_diagnostico(
            codigos.LAB_SIN_BALANCE_POSIBLE, "error",
            resultado["diagnostico"]["mensaje"],
            "Revisa si falta alguna especie: una reaccion incompleta no cuadra.",
            categoria="modelo"))
        estado = "invalido"
    elif caso == "subespacio":
        diagnosticos.append(_diagnostico(
            codigos.LAB_BALANCEO_NO_UNICO, "advertencia",
            resultado["diagnostico"]["mensaje"],
            "Elige cual de las reacciones de la base describe tu quimica, o "
            "trabaja con todas: cualquier combinacion lineal tambien conserva "
            "los elementos.",
            categoria="modelo"))
        estado = "resuelto"
    else:
        estado = "resuelto"

    return _envolver(resultado, entradas, estado, diagnosticos)


def comprobar_estequiometria(request):
    """Juzga una nu dada en vez de buscarla."""
    componentes = list(request.componentes)
    entradas = {"servicio": "comprobar_nu", "componentes": componentes,
                "nu": trazabilidad.canonico(list(request.nu))}
    try:
        _validar_componentes(componentes)
        proveedor = _proveedor_de(componentes)
        atomos = [dict(getattr(c, "atoms", None) or {})
                  for c in proveedor.componentes]
        if len(request.nu) != len(componentes):
            raise ErrorDeDatos(
                f"Hay {len(request.nu)} coeficientes y {len(componentes)} "
                "componentes. Hace falta uno por componente, en el mismo orden.",
                codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
            )
        resultado = bal.comprobar_nu(list(request.nu), atomos, componentes)
    except (ErrorDeDatos, ErrorFisico) as e:
        datos = e.como_diccionario()
        return _envolver(
            {"especies": componentes, "nu": list(request.nu), "conserva": False,
             "elementos": [], "residuo_elemental": {}, "descuadre": {},
             "mensaje": str(e)},
            entradas, "invalido",
            [_diagnostico(datos.get("codigo", codigos.SIN_CLASIFICAR), "error",
                          str(e), categoria=datos.get("categoria", "datos"))])

    diagnosticos = []
    if not resultado["conserva"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_ELEMENTOS_NO_CONSERVADOS, "error", resultado["mensaje"],
            "Usa /laboratorio/balancear para obtener los coeficientes que si "
            "cuadran."))
    return _envolver(resultado, entradas,
                     "resuelto" if resultado["conserva"] else "invalido",
                     diagnosticos)


# =====================================================================
# Lo comun a equilibrio y lote
# =====================================================================

def _montar(request, servicio):
    """Proveedor, calculadora, nu validadas y estado inicial."""
    componentes = list(request.componentes)
    _validar_componentes(componentes)
    proveedor = _proveedor_de(componentes)
    calculadora = entalpia_de(proveedor)
    n = len(componentes)

    elementos, A = est.matriz_elemental(proveedor)
    mw = est.masas_molares(proveedor)

    T = lab.convertir("T", request.T.valor, request.T.unidad)
    if T <= 0:
        raise ErrorDeDatos(f"Temperatura no fisica: {T} K.",
                           codigo=codigos.LAB_VALOR_FUERA_DE_DOMINIO)

    n0 = np.zeros(n, dtype=float)
    vistos = set()
    for entrada in request.estado_inicial:
        if entrada.componente not in componentes:
            raise ErrorDeDatos(
                f"El estado inicial menciona {entrada.componente!r}, que no esta "
                f"entre los componentes ({', '.join(componentes)}).",
                codigo=codigos.LAB_VARIABLE_DESCONOCIDA)
        if entrada.componente in vistos:
            raise ErrorDeDatos(
                f"El estado inicial da {entrada.componente!r} dos veces.",
                codigo=codigos.LAB_ESPECIFICACION_DUPLICADA)
        vistos.add(entrada.componente)
        valor = lab.convertir("F", entrada.valor, entrada.unidad) \
            if entrada.unidad in lab.UNIDADES["F"] else None
        if valor is None:
            # Moles, no caudal: la unidad es 'mol' o 'kmol'.
            factores = {"mol": 1.0, "kmol": 1000.0, "mmol": 1e-3}
            if entrada.unidad not in factores:
                raise ErrorDeDatos(
                    f"Unidad no admitida para el estado inicial: "
                    f"{entrada.unidad!r}. Admitidas: "
                    f"{', '.join(sorted(factores))} (cantidad) o "
                    f"{', '.join(sorted(lab.UNIDADES['F']))} (caudal).",
                    codigo=codigos.LAB_UNIDAD_INCOMPATIBLE)
            valor = float(entrada.valor) * factores[entrada.unidad]
        n0[componentes.index(entrada.componente)] = valor

    reacciones = []
    for i, d in enumerate(request.reacciones):
        etiqueta = f"reacciones[{i}] ({d.id})"
        nu = np.asarray(d.nu, dtype=float)
        if nu.size != n:
            raise ErrorDeDatos(
                f"{etiqueta}: hay {nu.size} coeficientes y {n} componentes.",
                codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA)
        provisional = est.Reaccion(d.id, servicio, nu, "irreversible",
                                   r_directa=0.0)
        est.validar_estequiometria(provisional, elementos, A, mw, componentes)
        reacciones.append((d, nu))

    return {
        "componentes": componentes, "proveedor": proveedor,
        "calculadora": calculadora, "elementos": elementos, "A": A, "mw": mw,
        "T": T, "n0": n0, "reacciones": reacciones, "n": n,
    }


def _entradas_de(request, servicio):
    """La huella: lo que define el calculo, normalizado."""
    canonico = trazabilidad.canonico
    return {
        "servicio": servicio,
        "componentes": list(request.componentes),
        "modelo": lab.MODELO_POR_OMISION,
        "T": canonico({"valor": request.T.valor, "unidad": request.T.unidad}),
        "estado_inicial": sorted(
            ({"componente": e.componente, "valor": canonico(e.valor),
              "unidad": e.unidad} for e in request.estado_inicial),
            key=lambda e: e["componente"]),
        "reacciones": sorted(
            (canonico(r.model_dump(exclude_none=True))
             for r in request.reacciones),
            key=lambda r: str(r.get("id"))),
        "base_actividad": request.base_actividad or "actividad",
    }


# =====================================================================
# Equilibrio
# =====================================================================

def resolver_equilibrio(request):
    """
    La composicion de equilibrio, con K(T), potenciales y estabilidad.

    **Imponer r+ = r- no demuestra equilibrio termodinamico**, y este
    servicio existe para calcular el de verdad: K sale de dG de FORMACION,
    no de ninguna cinetica.
    """
    entradas = _entradas_de(request, "equilibrio")
    try:
        m = _montar(request, "equilibrio")
    except (ErrorDeDatos, ErrorFisico) as e:
        datos = e.como_diccionario()
        return _envolver(
            {"T": None, "avances": [], "moles_equilibrio": [],
             "composicion_equilibrio": [], "propiedades_por_reaccion": [],
             "comprobacion": [], "convergencia": None, "estabilidad": None,
             "potenciales_quimicos": None, "componentes": list(request.componentes),
             "especies_agotadas": [], "aviso_negativas": None},
            entradas, "invalido",
            [_diagnostico(datos.get("codigo", codigos.SIN_CLASIFICAR), "error",
                          str(e), categoria=datos.get("categoria", "datos"))])

    base = request.base_actividad or "actividad"
    if base not in cin.BASES_ACTIVIDAD:
        return _envolver(
            {"componentes": m["componentes"], "T": m["T"], "avances": [],
             "moles_equilibrio": [], "composicion_equilibrio": [],
             "propiedades_por_reaccion": [], "comprobacion": [],
             "convergencia": None, "estabilidad": None,
             "potenciales_quimicos": None, "especies_agotadas": [],
             "aviso_negativas": None},
            entradas, "invalido",
            [_diagnostico(
                codigos.LAB_BASE_ACTIVIDAD_NO_SOPORTADA, "error",
                f"Base de actividad no admitida: {base!r}. Admitidas: "
                f"{', '.join(sorted(cin.BASES_ACTIVIDAD))}.")])

    NU = np.array([nu for _, nu in m["reacciones"]], dtype=float)
    diagnosticos = []
    try:
        resultado = eqm.composicion_de_equilibrio(
            m["proveedor"], m["calculadora"], NU, m["n0"], m["T"], base)
        potenciales = eqm.potenciales_quimicos(
            m["proveedor"], m["calculadora"], m["T"],
            np.array(resultado["composicion_equilibrio"]), base)
    except (ErrorDeDatos, ErrorFisico, ErrorNumerico) as e:
        datos = e.como_diccionario()
        return _envolver(
            {"componentes": m["componentes"], "T": m["T"], "avances": [],
             "moles_equilibrio": [], "composicion_equilibrio": [],
             "propiedades_por_reaccion": [], "comprobacion": [],
             "convergencia": None, "estabilidad": None,
             "potenciales_quimicos": None, "especies_agotadas": [],
             "aviso_negativas": None},
            entradas, "invalido",
            [_diagnostico(datos.get("codigo", codigos.SIN_CLASIFICAR), "error",
                          str(e), categoria=datos.get("categoria", "fisica"))])

    resultado["componentes"] = m["componentes"]
    resultado["potenciales_quimicos"] = potenciales
    resultado["conservacion"] = est.conservacion_medida(
        m["n0"], np.array(resultado["moles_equilibrio"]), m["elementos"],
        m["A"], m["mw"])
    resultado["base_actividad"] = base
    resultado["aviso_tasas"] = (
        "Imponer r+ = r- NO demuestra equilibrio termodinamico: describe un "
        "estado estacionario con esas dos tasas. El equilibrio es Q = K, y K "
        "sale de dG de FORMACION, no de ninguna cinetica. Este servicio calcula "
        "eso; usa 'comprobacion' para saber si un estado cualquiera lo cumple."
    )

    if not resultado["convergencia"]["convergio"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_EQUILIBRIO_SIN_CONVERGENCIA, "error",
            f"El equilibrio no convergio: residuo escalado "
            f"{resultado['convergencia']['residuo_escalado']:.3e} frente a una "
            f"tolerancia de {eqm.TOLERANCIA_EQUILIBRIO:.0e}.",
            "Revisa la estequiometria y la alimentacion.", categoria="numerica"))
    if resultado["aviso_negativas"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_CAUDAL_ESPECIE_NEGATIVO, "error",
            resultado["aviso_negativas"], categoria="fisica"))
    if not resultado["estabilidad"]["definido_positivo"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_EQUILIBRIO_NO_UTILIZABLE, "advertencia",
            "El hessiano de Gibbs NO es definido positivo en la solucion: el "
            f"punto es estacionario pero no un minimo (autovalores: "
            f"{resultado['estabilidad']['autovalores']}). Puede ser un punto de "
            "silla o el borde del dominio.",
            "dG = 0 no basta para que sea equilibrio estable; el criterio es la "
            "segunda derivada.", categoria="fisica"))
    if resultado["especies_agotadas"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_INFO_FASE, "informacion",
            "El equilibrio agota: "
            + ", ".join(m["componentes"][e["indice"]]
                        for e in resultado["especies_agotadas"])
            + ". Su actividad se recorto a un suelo para poder tomar logaritmos.",
            categoria="informacion"))

    estado = "resuelto" if not any(d["severidad"] == "error"
                                   for d in diagnosticos) else "no_convergente"
    return _envolver(resultado, entradas, estado, diagnosticos)


# =====================================================================
# Lote
# =====================================================================

def resolver_lote(request):
    """
    La trayectoria de un lote isotermo.

    Usa las MISMAS leyes de velocidad que el CSTR (core/cinetica.py): la
    ley es la misma fisica en los dos regimenes, y tener dos
    implementaciones seria tener dos fisicas que se pueden separar.
    """
    entradas = _entradas_de(request, "lote")
    entradas["tiempo"] = trazabilidad.canonico({
        "final": request.tiempo.final, "unidad": request.tiempo.unidad,
        "muestras": request.tiempo.muestras})
    entradas["integrador"] = trazabilidad.canonico({
        "metodo": request.integrador.metodo if request.integrador else None,
        "rtol": request.integrador.rtol if request.integrador else None,
        "atol": request.integrador.atol if request.integrador else None})

    vacio = {
        "componentes": list(request.componentes), "T": None, "t": [],
        "moles": [], "trayectoria_por_especie": [], "metodo": None,
        "tolerancias": None, "agotamientos": [], "no_negatividad": None,
        "conservacion": None, "equilibrio_alcanzado": None,
    }
    try:
        m = _montar(request, "lote")
    except (ErrorDeDatos, ErrorFisico) as e:
        datos = e.como_diccionario()
        return _envolver(vacio, entradas, "invalido",
                         [_diagnostico(datos.get("codigo", codigos.SIN_CLASIFICAR),
                                       "error", str(e),
                                       categoria=datos.get("categoria", "datos"))])

    # Las leyes, con el mismo lector que el CSTR para no duplicar fisica.
    montaje_falso = lab.Montaje({})
    montaje_falso.n = m["n"]
    montaje_falso.componentes = m["componentes"]
    montaje_falso.proveedor = m["proveedor"]

    reacciones, diagnosticos = [], []
    volumen = None
    if request.volumen is not None:
        volumen = lab.convertir("V", request.volumen.valor,
                                request.volumen.unidad)
    try:
        for i, (d, nu) in enumerate(m["reacciones"]):
            etiqueta = f"reacciones[{i}] ({d.id})"
            if d.ley_directa is None:
                raise ErrorDeDatos(
                    f"{etiqueta}: un lote necesita una ley de velocidad. Una tasa "
                    "constante en el tiempo no describe un lote: la composicion "
                    "cambia y la tasa con ella.",
                    codigo=codigos.LAB_LEY_INVALIDA)
            directa, base_tasa = lab._leer_ley(
                montaje_falso, f"{etiqueta}.ley_directa",
                d.ley_directa.model_dump(exclude_none=True), nu, m["n"],
                m["componentes"])
            inversa, desde_equilibrio = None, False
            if d.ley_inversa is not None:
                declarada = d.ley_inversa.model_dump(exclude_none=True)
                if declarada.get("desde_equilibrio"):
                    desde_equilibrio = True
                else:
                    inversa, _ = lab._leer_ley(
                        montaje_falso, f"{etiqueta}.ley_inversa", declarada, nu,
                        m["n"], m["componentes"], base_tasa_esperada=base_tasa)
            if base_tasa == "volumetrica":
                if volumen is None:
                    raise ErrorDeDatos(
                        f"{etiqueta}: la constante esta en base volumetrica y no "
                        "se dio el volumen del lote. No se supone 1 m3.",
                        codigo=codigos.LAB_FALTA_VOLUMEN_REACTOR)
                directa.k_ref *= volumen
                if inversa is not None:
                    inversa.k_ref *= volumen
            reacciones.append(cin.ReaccionCinetica(
                d.id, "lote", nu, directa, ley_inversa=inversa,
                inversa_desde_equilibrio=desde_equilibrio, volumen=volumen))
    except ErrorDeDatos as e:
        datos = e.como_diccionario()
        return _envolver(vacio, entradas, "invalido",
                         [_diagnostico(datos.get("codigo", codigos.LAB_LEY_INVALIDA),
                                       "error", str(e),
                                       categoria=datos.get("categoria", "datos"))])

    # K_eq para las inversas del equilibrio, por la ruta RIGUROSA.
    cache = {}

    def K_de(reaccion_id, T):
        clave = (reaccion_id, round(float(T), 9))
        if clave not in cache:
            nu = next(r.nu for r in reacciones if r.id == reaccion_id)
            cache[clave] = float(eqm.propiedades_de_reaccion(
                m["proveedor"], m["calculadora"], nu, float(T))["riguroso"]["K"])
        return cache[clave]

    factores_tiempo = {"s": 1.0, "min": 60.0, "h": 3600.0, "ms": 1e-3}
    if request.tiempo.unidad not in factores_tiempo:
        return _envolver(vacio, entradas, "invalido", [_diagnostico(
            codigos.LAB_UNIDAD_INCOMPATIBLE, "error",
            f"Unidad de tiempo no admitida: {request.tiempo.unidad!r}. "
            f"Admitidas: {', '.join(sorted(factores_tiempo))}.")])
    t_final = float(request.tiempo.final) * factores_tiempo[request.tiempo.unidad]

    integrador = request.integrador
    try:
        resultado = lot.integrar(
            m["proveedor"], reacciones, m["n0"], m["T"], t_final,
            n_muestras=request.tiempo.muestras,
            metodo=(integrador.metodo if integrador and integrador.metodo
                    else "LSODA"),
            rtol=(integrador.rtol if integrador and integrador.rtol
                  else lot.RTOL_POR_OMISION),
            atol=(integrador.atol if integrador else None),
            volumen=volumen, K_eq_de=K_de,
        )
    except (ErrorDeDatos, ErrorFisico, ErrorNumerico) as e:
        datos = e.como_diccionario()
        return _envolver(vacio, entradas,
                         "no_convergente" if datos.get("categoria") == "numerica"
                         else "invalido",
                         [_diagnostico(datos.get("codigo", codigos.SIN_CLASIFICAR),
                                       "error", str(e),
                                       categoria=datos.get("categoria", "datos"))])

    n_t = np.array(resultado["moles"], dtype=float)
    resultado["componentes"] = m["componentes"]
    resultado["T"] = m["T"]
    resultado["conservacion"] = lot.conservacion_en_la_trayectoria(
        n_t, m["A"], m["mw"])
    resultado["trayectoria_por_especie"] = [
        {"componente": m["componentes"][i],
         "moles": [float(v) for v in n_t[i]],
         "fraccion_molar": [float(n_t[i, k] / max(float(np.sum(n_t[:, k])), 1e-30))
                            for k in range(n_t.shape[1])],
         "inicial": float(n_t[i, 0]), "final": float(n_t[i, -1])}
        for i in range(m["n"])
    ]
    for a in resultado["agotamientos"]:
        a["componente"] = m["componentes"][a["especie"]]

    # La comprobacion que cruza los dos servicios: si la cinetica es
    # termodinamicamente consistente, el final del lote tiene que ser el
    # equilibrio. Se mide la distancia en vez de afirmarla.
    x_final = n_t[:, -1] / max(float(np.sum(n_t[:, -1])), 1e-30)
    NU = np.array([r.nu for r in reacciones], dtype=float)
    try:
        resultado["equilibrio_alcanzado"] = {
            "composicion_final": [float(v) for v in x_final],
            "distancia": eqm.distancia_al_equilibrio(
                m["proveedor"], m["calculadora"], NU, m["T"], x_final,
                request.base_actividad or "actividad"),
            "nota": "dG_rxn en el ultimo punto de la trayectoria. Si la cinetica "
                    "es termodinamicamente consistente (ley_inversa con "
                    "desde_equilibrio) y el tiempo basta, tiende a cero y la "
                    "composicion final coincide con /laboratorio/equilibrio. Si "
                    "la cinetica NO lo es, no tiene por que: dos constantes "
                    "cualesquiera dan un estado estacionario que no es el "
                    "equilibrio termodinamico.",
        }
    except (ErrorDeDatos, ErrorFisico):
        resultado["equilibrio_alcanzado"] = {
            "composicion_final": [float(v) for v in x_final],
            "distancia": None,
            "nota": "No se pudo comparar con el equilibrio: faltan propiedades de "
                    "formacion de alguna especie.",
        }

    if not resultado["no_negatividad"]["cumple"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_TRAYECTORIA_NEGATIVA, "error",
            f"La trayectoria tiene moles negativos (peor valor "
            f"{resultado['no_negatividad']['peor_valor']:.3e}, "
            f"{resultado['no_negatividad']['total_violaciones']} puntos).",
            "Baja la tolerancia del integrador o revisa los ordenes: un orden "
            "cero sobre un reactivo hace que su tasa no caiga al agotarse.",
            categoria="numerica"))
    peor = max(resultado["conservacion"]["residuo_elemental_maximo"],
               resultado["conservacion"]["masa"]["residuo_relativo"])
    if peor > 1e-8:
        diagnosticos.append(_diagnostico(
            codigos.LAB_CONSERVACION_NO_MEDIDA, "error",
            f"La trayectoria no conserva elementos o masa (residuo relativo "
            f"{peor:.3e}).",
            "Es un fallo del motor o una tolerancia demasiado floja.",
            categoria="numerica"))
    for a in resultado["agotamientos"]:
        diagnosticos.append(_diagnostico(
            codigos.LAB_INFO_FASE, "informacion",
            f"{a['componente']} se agota en t = {a['instante']:.6g} s.",
            categoria="informacion"))

    estado = "resuelto" if not any(d["severidad"] == "error"
                                   for d in diagnosticos) else "no_convergente"
    return _envolver(resultado, entradas, estado, diagnosticos)


def capacidades_reacciones():
    """Lo que estos tres servicios admiten, y lo que no."""
    return {
        "schema_version": lab.SCHEMA_VERSION,
        "servicios": {
            "balancear": {
                "que_hace": "Encuentra las nu que conservan los elementos entre "
                            "unas especies, con aritmetica EXACTA.",
                "necesita": ["composicion elemental"],
                "no_necesita": ["propiedades termodinamicas", "tasas"],
                "respuestas": {
                    "dimension 0": "no hay reaccion posible entre esas especies",
                    "dimension 1": "una reaccion, unica salvo escala y signo",
                    "dimension > 1": "un SUBESPACIO de reacciones: se devuelve la "
                                     "base y no se elige una",
                },
                "signo": "La conservacion de elementos no distingue reactivo de "
                         "producto: A@nu = 0 se cumple con nu y con -nu. Da "
                         "'reactivos' para orientarla, o se orienta por convencion "
                         "y se dice.",
            },
            "equilibrio": {
                "que_hace": "La composicion de equilibrio, K(T), los potenciales "
                            "quimicos y el criterio de estabilidad.",
                "necesita": ["entalpia y energia de Gibbs de formacion"],
                "no_necesita": ["cinetica"],
                "K": {
                    "riguroso": "Kirchhoff para dH e integral de dCp/T para dS",
                    "vant_hoff": "se devuelve tambien, para que la diferencia se "
                                 "vea en vez de suponerse pequena",
                },
                "estabilidad": "dG = 0 dice que es un punto estacionario, no que "
                               "sea un minimo. Se calcula el hessiano de Gibbs y "
                               "se dan sus autovalores.",
                "aviso": "Imponer r+ = r- NO demuestra equilibrio termodinamico.",
            },
            "lote": {
                "que_hace": "La trayectoria de un lote isotermo integrando el "
                            "sistema de ODEs.",
                "necesita": ["leyes de velocidad"],
                "metodos": dict(lot.METODOS),
                "tolerancias_por_omision": {"rtol": lot.RTOL_POR_OMISION,
                                            "atol": "1e-12 por mol total"},
                "agotamiento": "se detecta con un EVENTO del integrador, no "
                               "mirando las muestras: un cruce entre dos muestras "
                               "se habria perdido",
                "no_soportado": ["lote adiabatico o no isotermo",
                                 "volumen variable"],
            },
        },
        "unidades": {
            "cantidad": ["mol", "kmol", "mmol"],
            "caudal": sorted(lab.UNIDADES["F"]),
            "tiempo": ["s", "min", "h", "ms"],
            "temperatura": sorted(lab.UNIDADES_TEMPERATURA),
            "volumen": sorted(lab.UNIDADES["V"]),
        },
        "comprobacion_cruzada": (
            "Un lote con cinetica termodinamicamente consistente "
            "(ley_inversa con desde_equilibrio) converge, cuando t tiende a "
            "infinito, a la MISMA composicion que /laboratorio/equilibrio. Son dos "
            "caminos independientes --uno integra una ODE, el otro resuelve "
            "ln Q = ln K-- y coinciden a 1e-17 con los xilenos."
        ),
    }
