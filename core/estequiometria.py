"""
Estequiometria de un volumen reactivo: avances, fuentes y conservacion.

Este modulo contesta una pregunta que parece trivial y no lo es: **cuanto
de cada especie se produce y cuanto se consume**. La respuesta ingenua
--mirar el signo de la fuente neta-- es incorrecta, y el contrato del
laboratorio lo subraya con un ejemplo que no admite discusion.

LA DISTINCION QUE DA SENTIDO AL MODULO: BRUTO NO ES NETO
--------------------------------------------------------
Una reaccion reversible en equilibrio tiene r+ = r- > 0. La fuente neta de
cada especie es CERO, y sin embargo cada especie se esta produciendo y
consumiendo a un ritmo positivo. Las moleculas no estan quietas: estan
yendo y viniendo a la misma velocidad.

De ahi se siguen tres reglas, y las tres estan implementadas:

  1. **Si se conocen r+ y r- por separado**, la generacion y el consumo
     brutos se calculan y se marcan como BRUTOS.

  2. **Si solo se conoce la tasa neta**, la generacion y el consumo brutos
     NO SE PUEDEN SABER, y se devuelven como None con el motivo. Jamas se
     rellenan con max(neto, 0): eso daria cero generacion en el equilibrio
     de una reaccion que esta funcionando a toda velocidad, que es
     exactamente la conclusion falsa que hay que evitar.

  3. La descomposicion max(neto,0) / max(-neto,0) SI se ofrece, pero en un
     campo aparte y etiquetada como **descomposicion del neto**. Es una
     cantidad util --dice en que direccion va la especie-- y no es el
     intercambio bruto. Mezclarlas es el error que este modulo existe para
     no cometer.

LA OTRA REGLA: NO HAY INCOGNITAS LIBRES POR ESPECIE
---------------------------------------------------
G_i y C_i se DERIVAN de la estequiometria y de las tasas. No son dos
variables mas que el sistema tenga que determinar: con n especies serian
2n incognitas nuevas y el problema quedaria irremediablemente
indeterminado. Se calculan, se reportan, y no entran en el recuento.

CONSERVACION
------------
Una estequiometria que no conserva los elementos no es una reaccion: es un
dato mal puesto. Se comprueba con la matriz elemental A (filas =
elementos, columnas = componentes), que sale de los atomos que 'thermo' da
para cada especie:

    A @ nu = 0   para cada reaccion

y de ahi se sigue la conservacion de masa (MW @ nu = 0), que se comprueba
aparte porque es la que el usuario reconoce. El caudal molar TOTAL si
puede cambiar: Sum(nu) no tiene por que ser cero.

CONVENCION DE SIGNO
-------------------
nu > 0 producto, nu < 0 reactivo. Un mismo evento produce unos componentes
y consume otros, y por eso el signo va en el coeficiente y no en la tasa:
las tasas brutas son siempre >= 0.

Zona libre de pint: todo en SI (mol/s, mol/(m3 s), J/mol).
"""

import math

import numpy as np

from core import errores as codigos
from core.errores import ErrorDeDatos, ErrorFisico

# Tolerancia del balance elemental de una estequiometria.
#
# Los atomos son enteros y los coeficientes suelen serlo, asi que el
# residuo exacto es 0. Se deja holgura para coeficientes fraccionarios
# legitimos (media molecula de O2 en una combustion), donde el redondeo
# de un float puede dejar un 1e-16.
TOLERANCIA_ELEMENTOS = 1e-9

# Tolerancia de la conservacion de masa, relativa a la masa movida.
TOLERANCIA_MASA = 1e-9


def _f(valor):
    """
    Un float limpio para la respuesta, sin cero negativo.

    `max(-0.0, 0.0)` devuelve -0.0 en Python, y un -0.0 en el JSON es
    valido pero desconcierta a quien compare con 0 o lo imprima: una
    generacion de "-0" parece un error de signo donde solo hay un cero.
    Sumar 0.0 lo normaliza sin tocar ningun otro valor.
    """
    return float(valor) + 0.0


# =====================================================================
# Matriz elemental
# =====================================================================

def matriz_elemental(proveedor):
    """
    (elementos, A) con A[k][i] = atomos del elemento k en el componente i.

    Sale de `Chemical.atoms` de 'thermo', que es un diccionario por
    especie. Los elementos se ordenan alfabeticamente para que la matriz
    sea reproducible: el orden de un diccionario no es parte de la quimica
    y sin ordenar la comprobacion dependeria de como 'thermo' lo
    construyo.
    """
    componentes = list(getattr(proveedor, "componentes", None) or [])
    if not componentes:
        raise ErrorDeDatos(
            "No hay componentes de los que sacar la composicion elemental.",
            codigo=codigos.LAB_COMPONENTE_NO_DISPONIBLE,
        )

    atomos = []
    sin_atomos = []
    for c in componentes:
        a = getattr(c, "atoms", None)
        if not a:
            sin_atomos.append(getattr(c, "name", None) or str(c))
            atomos.append({})
        else:
            atomos.append(dict(a))
    if sin_atomos:
        raise ErrorDeDatos(
            f"'thermo' no da la composicion elemental de: {', '.join(sin_atomos)}. "
            "Sin ella no se puede comprobar que la estequiometria conserve los "
            "elementos, y una estequiometria sin comprobar es un dato en el que no "
            "se puede confiar.",
            codigo=codigos.LAB_COMPONENTE_NO_DISPONIBLE,
        )

    elementos = sorted({e for a in atomos for e in a})
    A = np.array([[float(a.get(e, 0)) for a in atomos] for e in elementos],
                 dtype=float)
    return elementos, A


def masas_molares(proveedor):
    """MW de cada componente [kg/kmol = g/mol], en orden."""
    mw = np.array([float(c.MW) for c in proveedor.componentes], dtype=float)
    if not np.all(np.isfinite(mw)) or np.any(mw <= 0):
        raise ErrorDeDatos(
            f"Masas molares no utilizables: {mw}.",
            codigo=codigos.LAB_COMPONENTE_NO_DISPONIBLE,
        )
    return mw


# =====================================================================
# Una reaccion
# =====================================================================

class Reaccion:
    """
    Una reaccion de tasa especificada, con su avance y sus fuentes.

    `brutas_disponibles` es el campo que hay que mirar antes que ninguno:
    dice si esta reaccion sabe cuanto produce y cuanto consume, o solo el
    balance entre las dos cosas.
    """

    def __init__(self, id, bloque_id, nu, modo, r_directa=None, r_inversa=None,
                 r_neta=None, base="integrada", unidad=None, volumen=None):
        self.id = id
        self.bloque_id = bloque_id
        self.nu = np.asarray(nu, dtype=float)
        self.modo = modo                  # irreversible | reversible_bruta | neta
        self.r_directa = r_directa        # mol/s, >= 0
        self.r_inversa = r_inversa        # mol/s, >= 0
        self.r_neta = r_neta              # mol/s, cualquier signo
        self.base = base                  # integrada | volumetrica
        self.unidad = unidad
        self.volumen = volumen            # m3, solo si la base es volumetrica
        # Diagnosticos propios de la reaccion, para no perderlos.
        self.balance_elemental = None
        self.balance_masa = None

    # -- avance -----------------------------------------------------
    @property
    def xi(self):
        """
        El avance NETO de la reaccion [mol/s].

        Es lo unico que el balance de materia necesita: la composicion de
        salida depende del neto y no de las brutas. Las brutas hacen falta
        para reportar G y C, no para resolver.
        """
        if self.modo == "irreversible":
            return self.r_directa
        if self.modo == "reversible_bruta":
            return self.r_directa - self.r_inversa
        return self.r_neta

    @property
    def brutas_disponibles(self):
        """
        Si esta reaccion sabe cuanto produce y cuanto consume.

        False cuando solo se dio la tasa neta. No es un defecto del modulo:
        es que el dato no esta. Un neto de cero es compatible con r+=r-=0
        (reaccion parada) y con r+=r-=1000 (equilibrio dinamico), y nada
        en la tasa neta distingue los dos casos.
        """
        return self.modo in ("irreversible", "reversible_bruta")

    # -- fuentes por especie ----------------------------------------
    def fuente_neta(self):
        """nu_i * xi [mol/s] por especie. Siempre disponible."""
        return self.nu * self.xi

    def generacion_bruta(self):
        """
        G_i [mol/s] >= 0, o None si no se puede saber.

        El evento DIRECTO produce las especies con nu > 0 a ritmo nu_i r+.
        El evento INVERSO produce las que tienen nu < 0, a ritmo |nu_i| r-.
        Las dos cosas generan, y por eso se suman.
        """
        if not self.brutas_disponibles:
            return None
        directa = np.maximum(self.nu, 0.0) * self.r_directa
        inversa = (np.maximum(-self.nu, 0.0) * self.r_inversa
                   if self.r_inversa else np.zeros_like(self.nu))
        return directa + inversa

    def consumo_bruto(self):
        """
        C_i [mol/s] >= 0, o None si no se puede saber.

        Simetrico de la generacion: el evento directo consume lo que tiene
        nu < 0 y el inverso consume lo que tiene nu > 0.
        """
        if not self.brutas_disponibles:
            return None
        directa = np.maximum(-self.nu, 0.0) * self.r_directa
        inversa = (np.maximum(self.nu, 0.0) * self.r_inversa
                   if self.r_inversa else np.zeros_like(self.nu))
        return directa + inversa

    def como_diccionario(self, componentes):
        g = self.generacion_bruta()
        c = self.consumo_bruto()
        neta = self.fuente_neta()
        return {
            "id": self.id,
            "bloque_id": self.bloque_id,
            "nu": [_f(v) for v in self.nu],
            "convencion_nu": "positivo producto, negativo reactivo",
            "modo_tasa": self.modo,
            "base_tasa": self.base,
            "unidad_declarada": self.unidad,
            "volumen_m3": self.volumen,
            "tasa_directa": self.r_directa,
            "tasa_inversa": self.r_inversa,
            "tasa_neta_declarada": self.r_neta,
            "avance_neto": _f(self.xi),
            "unidad_avance": "mol/s",
            "brutas_disponibles": self.brutas_disponibles,
            "motivo_brutas_no_disponibles": (
                None if self.brutas_disponibles else
                "Solo se dio la tasa neta. Un neto de cero es compatible con una "
                "reaccion parada (r+=r-=0) y con un equilibrio dinamico "
                "(r+=r->0), y la tasa neta no distingue los dos casos. "
                "Declara tasa_directa y tasa_inversa para obtener las brutas."
            ),
            "por_especie": [
                {
                    "componente": componentes[i],
                    "nu": _f(self.nu[i]),
                    "generacion_bruta": None if g is None else _f(g[i]),
                    "consumo_bruto": None if c is None else _f(c[i]),
                    "fuente_neta": _f(neta[i]),
                }
                for i in range(len(self.nu))
            ],
            "balance_elemental": self.balance_elemental,
            "balance_masa": self.balance_masa,
        }


# =====================================================================
# Validacion de la estequiometria
# =====================================================================

def validar_estequiometria(reaccion, elementos, A, mw, nombres):
    """
    Comprueba que una estequiometria sea una reaccion y no un dato suelto.

    Lanza ErrorDeDatos con el codigo preciso, y en el camino deja medidos
    los residuos elemental y de masa en la propia reaccion -- medirlos y
    no guardarlos obligaria a recalcularlos para el informe.
    """
    nu = reaccion.nu
    n = A.shape[1]

    if nu.ndim != 1 or nu.shape[0] != n:
        raise ErrorDeDatos(
            f"La reaccion {reaccion.id!r} tiene {nu.shape} coeficientes y hay {n} "
            "componentes. Hace falta uno por componente, EN EL MISMO ORDEN: el "
            "coeficiente i es el del componente i.",
            codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
        )
    if not np.all(np.isfinite(nu)):
        raise ErrorDeDatos(
            f"La reaccion {reaccion.id!r} tiene coeficientes no finitos: {list(nu)}.",
            codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
        )
    if np.allclose(nu, 0.0):
        raise ErrorDeDatos(
            f"La reaccion {reaccion.id!r} tiene todos los coeficientes a cero. Una "
            "reaccion sin reactivos ni productos no es una reaccion.",
            codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
        )
    if not np.any(nu < 0) or not np.any(nu > 0):
        raise ErrorDeDatos(
            f"La reaccion {reaccion.id!r} no tiene reactivos y productos a la vez "
            f"(nu = {list(nu)}). Con la convencion de este motor --negativo "
            "reactivo, positivo producto-- un evento tiene que consumir algo y "
            "producir algo.",
            codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
        )

    # --- los elementos
    residuo = A @ nu
    escala = float(np.max(np.abs(A) @ np.abs(nu))) or 1.0
    por_elemento = {e: float(residuo[k]) for k, e in enumerate(elementos)}
    reaccion.balance_elemental = {
        "elementos": list(elementos),
        "residuo_por_elemento": por_elemento,
        "residuo_maximo": float(np.max(np.abs(residuo))) if residuo.size else 0.0,
        "escala": escala,
        "conserva": bool(np.max(np.abs(residuo)) <= TOLERANCIA_ELEMENTOS * escala)
        if residuo.size else True,
    }
    if not reaccion.balance_elemental["conserva"]:
        descuadre = {e: v for e, v in por_elemento.items()
                     if abs(v) > TOLERANCIA_ELEMENTOS * escala}
        detalle = ", ".join(f"{e}: {v:+.6g}" for e, v in sorted(descuadre.items()))
        raise ErrorDeDatos(
            f"La reaccion {reaccion.id!r} no conserva los elementos ({detalle}). "
            f"Con nu = {list(nu)} y los componentes "
            f"{', '.join(nombres)}, los atomos no cuadran: eso no es una reaccion "
            "quimica, es un dato mal puesto.",
            codigo=codigos.LAB_ELEMENTOS_NO_CONSERVADOS,
        )

    # --- la masa, que se sigue de los elementos pero es la que se
    #     reconoce a simple vista
    residuo_masa = float(mw @ nu)
    escala_masa = float(np.abs(mw) @ np.abs(nu)) or 1.0
    reaccion.balance_masa = {
        "residuo": residuo_masa,
        "escala": escala_masa,
        "unidad": "g/mol por unidad de avance",
        "conserva": abs(residuo_masa) <= TOLERANCIA_MASA * escala_masa,
        "nota": "Se sigue del balance elemental; se mide aparte porque es la "
                "conservacion que se reconoce a simple vista. El caudal molar "
                "TOTAL si puede cambiar: sum(nu) no tiene por que ser cero.",
    }
    if not reaccion.balance_masa["conserva"]:
        raise ErrorDeDatos(
            f"La reaccion {reaccion.id!r} no conserva la masa: sobran o faltan "
            f"{residuo_masa:+.6g} g por mol de avance.",
            codigo=codigos.LAB_MASA_NO_CONSERVADA,
        )


# =====================================================================
# Fuentes agregadas de un volumen
# =====================================================================

def fuentes_del_volumen(reacciones, n, componentes):
    """
    G_i, C_i y la fuente neta de un volumen con varias reacciones.

    La regla que importa: si **alguna** reaccion del volumen solo trae su
    tasa neta, las brutas del VOLUMEN no estan disponibles. No es
    pesimismo: G_i es una suma y uno de sus terminos es desconocido, asi
    que la suma lo es. Reportar la suma de los terminos conocidos seria
    dar un numero menor que el verdadero presentandolo como el verdadero.
    """
    neta = np.zeros(n, dtype=float)
    for r in reacciones:
        neta = neta + r.fuente_neta()

    sin_brutas = [r.id for r in reacciones if not r.brutas_disponibles]
    if sin_brutas:
        g = c = None
    else:
        g = np.zeros(n, dtype=float)
        c = np.zeros(n, dtype=float)
        for r in reacciones:
            g = g + r.generacion_bruta()
            c = c + r.consumo_bruto()

    return {
        "componentes": list(componentes),
        "unidad": "mol/s",
        "brutas_disponibles": not sin_brutas,
        "motivo_brutas_no_disponibles": (
            None if not sin_brutas else
            "La generacion y el consumo brutos del volumen son una SUMA sobre sus "
            f"reacciones, y {', '.join(sin_brutas)} solo trae(n) la tasa neta. Un "
            "termino desconocido hace desconocida la suma; devolver la suma de los "
            "terminos conocidos seria dar un numero menor que el verdadero "
            "presentandolo como el verdadero."
        ),
        "por_especie": [
            {
                "componente": componentes[i],
                "generacion_bruta": None if g is None else _f(g[i]),
                "consumo_bruto": None if c is None else _f(c[i]),
                "fuente_neta": _f(neta[i]),
                # La descomposicion del NETO. Se ofrece siempre porque dice
                # en que direccion va la especie, y se etiqueta aparte
                # porque NO es el intercambio bruto.
                "descomposicion_neta": {
                    "aparente_generacion": _f(max(neta[i], 0.0)),
                    "aparente_consumo": _f(max(-neta[i], 0.0)),
                },
            }
            for i in range(n)
        ],
        "advertencia_descomposicion_neta": (
            "'descomposicion_neta' NO es el intercambio bruto: es el signo del "
            "neto repartido en dos casillas no negativas. En el equilibrio de una "
            "reaccion reversible el neto es cero y la descomposicion da cero en "
            "las dos, mientras la generacion y el consumo brutos son POSITIVOS. "
            "Usa 'generacion_bruta' y 'consumo_bruto' cuando esten disponibles, y "
            "cuando no, di que no lo estan."
        ),
        "suma_nu": None,
    }


# =====================================================================
# Conservacion medida sobre el resultado
# =====================================================================

def conservacion_medida(F_in, F_out, elementos, A, mw):
    """
    Los elementos y la masa, comprobados sobre los caudales RESUELTOS.

    No es lo mismo que validar la estequiometria. Aquello comprueba que la
    reaccion tenga sentido; esto comprueba que el balance se haya aplicado
    bien, y es una comprobacion independiente: si el balance por especie se
    resolvio correctamente, los atomos que entran tienen que salir.

    Una reaccion bien balanceada con un balance mal aplicado pasaria la
    primera comprobacion y fallaria esta.
    """
    F_in = np.asarray(F_in, dtype=float)
    F_out = np.asarray(F_out, dtype=float)

    elem_in = A @ F_in
    elem_out = A @ F_out
    escala_elem = np.maximum(np.abs(elem_in), 1e-30)
    residuos = np.abs(elem_out - elem_in) / escala_elem

    masa_in = float(mw @ F_in)
    masa_out = float(mw @ F_out)
    escala_masa = max(abs(masa_in), abs(masa_out), 1e-30)

    return {
        "elementos": {
            e: {
                "entra": float(elem_in[k]),
                "sale": float(elem_out[k]),
                "residuo_relativo": float(residuos[k]),
            }
            for k, e in enumerate(elementos)
        },
        "residuo_elemental_maximo": float(np.max(residuos)) if residuos.size else 0.0,
        "masa": {
            "entra_g_s": masa_in,
            "sale_g_s": masa_out,
            "residuo_relativo": abs(masa_out - masa_in) / escala_masa,
        },
        "caudal_molar": {
            "entra_mol_s": float(np.sum(F_in)),
            "sale_mol_s": float(np.sum(F_out)),
            "cambia": not math.isclose(float(np.sum(F_in)), float(np.sum(F_out)),
                                       rel_tol=1e-12, abs_tol=0.0),
            "nota": "El caudal molar total PUEDE cambiar: sum(nu) no tiene por que "
                    "ser cero. La masa no cambia nunca.",
        },
        "escala": "residuos relativos a lo que entra; adimensionales",
    }


# =====================================================================
# Calor de reaccion
# =====================================================================

def entalpias_de_reaccion(proveedor, reacciones):
    """
    dH_rxn de cada reaccion [J/mol de avance], a la T de referencia.

    POR QUE A LA T DE REFERENCIA Y NO A LA DEL VOLUMEN
    --------------------------------------------------
    Porque las entalpias sensibles ya se encargan de la temperatura. La
    entalpia absoluta de una corriente es

        H = sum_i F_i ( h_f,i(T_ref) + h_sens,i(T) )

    y al restar entrada de salida, los h_f salen multiplicados por
    (F_i,sal - F_i,ent) = sum_r nu_ir xi_r, lo que da exactamente
    sum_r xi_r dH_rxn,r(T_ref). El resto --toda la dependencia con T-- ya
    esta en los terminos sensibles.

    Corregir aqui dH_rxn a la temperatura del volumen con Kirchhoff
    SERIA CONTARLO DOS VECES. Es el error que el contrato pide evitar,
    visto desde el otro lado.
    """
    Hf = np.asarray(proveedor.entalpias_formacion_liquido(), dtype=float)
    if not np.all(np.isfinite(Hf)):
        faltan = [getattr(c, "name", str(c)) for c, h in
                  zip(proveedor.componentes, Hf) if not math.isfinite(float(h))]
        raise ErrorDeDatos(
            f"No hay entalpia de formacion liquida para: {', '.join(faltan)}. Sin "
            "ella no se puede calcular el calor de reaccion, y suponerlo cero "
            "convertiria una reaccion exotermica en un calentador neutro.",
            codigo=codigos.LAB_ENTALPIA_FORMACION_NO_DISPONIBLE,
        )
    return {r.id: float(r.nu @ Hf) for r in reacciones}


def calor_de_reaccion(reacciones, dH_por_reaccion):
    """
    sum_r xi_r dH_rxn,r [W]: lo que la quimica le quita al balance.

    Signo: con dH < 0 (exotermica) y xi > 0, el termino es negativo, asi
    que el balance

        Q + F_ent h_ent - F_sal h_sal - sum_r xi_r dH_rxn,r = 0

    pide un Q mas negativo para mantener la temperatura. O sea: hay que
    RETIRAR calor de una exotermica, que es lo correcto.
    """
    return float(sum(r.xi * dH_por_reaccion[r.id] for r in reacciones))
