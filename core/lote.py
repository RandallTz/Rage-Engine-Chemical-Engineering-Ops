"""
Lote transitorio: la misma quimica, integrada en el tiempo.

QUE CAMBIA RESPECTO AL ESTACIONARIO
-----------------------------------
En un CSTR estacionario el avance sale de igualar lo que entra con lo que
sale (ver core/cinetica.py). En un lote no entra ni sale nada: lo que hay
es una condicion inicial y una trayectoria.

    dn_i/dt = sum_r nu_ir r_r(T, x(t))        n_i(0) = n_i0

Deja de ser un sistema algebraico --implicito o no-- y pasa a ser un
sistema de ecuaciones diferenciales ordinarias. Se integra, y eso trae sus
propias preguntas: con que metodo, con que tolerancias, hasta cuando, y
que hacer cuando una especie se agota.

LAS CUATRO COSAS QUE EL CONTRATO PIDE, Y COMO SE RESUELVEN
----------------------------------------------------------
**Estado inicial compatible.** Los moles iniciales tienen que ser no
negativos y sumar algo. Una base en concentracion necesita el volumen, y
si no se da no se supone 1 m3: se diagnostica. Es la misma regla que con
las tasas volumetricas.

**Tolerancias.** `rtol` y `atol` se declaran y viajan en la respuesta. Una
trayectoria sin tolerancia declarada no se puede reproducir ni comparar.

**Agotamiento.** No se detecta mirando si algun numero salio negativo: se
detecta con un EVENTO del integrador, que localiza el instante en que la
especie llega a cero con la misma precision que la trayectoria. Un
chequeo a posteriori sobre los puntos muestreados se perderia el cruce si
cae entre dos muestras.

**No negatividad.** Una ley de accion de masas con ordenes positivos la
respeta sola --la tasa cae a cero cuando el reactivo se agota-- pero el
integrador puede pasarse por debajo en un paso. Se recorta al EVALUAR la
ley, porque UNIFAC con fracciones negativas no significa nada, y se
COMPRUEBA sobre la trayectoria devuelta. Recortar y callarse convertiria
un dato imposible en una curva plausible.

LO QUE NO HACE
--------------
Isotermo. Un lote adiabatico anade la ecuacion de la energia al sistema de
ODEs --dT/dt a partir del calor de reaccion y la capacidad calorifica de
la mezcla-- y eso es otra entrega: exige su propia verificacion, y las
soluciones analiticas con las que se comprueba esta son todas isotermas.

Zona libre de pint: SI (mol, s, K, m3).
"""

import math

import numpy as np
from scipy.integrate import solve_ivp

from core import cinetica as cin
from core import errores as codigos
from core.errores import ErrorDeDatos, ErrorFisico, ErrorNumerico

# Metodos del integrador que se admiten, con para que sirve cada uno.
#
# LSODA por omision porque cambia solo entre no rigido y rigido, y una red
# de reacciones con constantes muy distintas es rigida sin avisar. Radau y
# BDF estan para quien ya sepa que la suya lo es.
METODOS = {
    "LSODA": "Adams/BDF con deteccion automatica de rigidez. Por omision: una "
             "red con constantes muy distintas se vuelve rigida sin avisar.",
    "Radau": "Runge-Kutta implicito de orden 5. Para sistemas rigidos.",
    "BDF": "Formulas de diferenciacion hacia atras. Para sistemas rigidos.",
    "RK45": "Runge-Kutta explicito 4(5). Rapido si el sistema NO es rigido; "
            "con constantes muy distintas da pasos diminutos.",
}

RTOL_POR_OMISION = 1e-10
ATOL_RELATIVO_POR_OMISION = 1e-12

# Tope de puntos de muestreo. Una trayectoria de un millon de puntos no se
# lee: se descarga.
MAX_MUESTRAS = 2000


def _moles_iniciales(n0):
    n0 = np.asarray(n0, dtype=float)
    if not np.all(np.isfinite(n0)):
        raise ErrorDeDatos(
            f"El estado inicial tiene valores no finitos: {list(n0)}.",
            codigo=codigos.LAB_VALOR_NO_FINITO,
        )
    if np.any(n0 < 0):
        negativas = [i for i, v in enumerate(n0) if v < 0]
        raise ErrorDeDatos(
            f"El estado inicial tiene moles negativos en las posiciones "
            f"{negativas}. Un mol negativo no es una cantidad pequena: no es una "
            "cantidad.",
            codigo=codigos.LAB_VALOR_FUERA_DE_DOMINIO,
        )
    if float(np.sum(n0)) <= 0:
        raise ErrorDeDatos(
            "El estado inicial no tiene materia: todos los moles son cero.",
            codigo=codigos.CAUDAL_NO_FISICO,
        )
    return n0


def integrar(proveedor, reacciones, n0, T, t_final, n_muestras=200,
             metodo="LSODA", rtol=RTOL_POR_OMISION, atol=None,
             volumen=None, t_inicial=0.0, K_eq_de=None):
    """
    La trayectoria de un lote isotermo.

    `reacciones` son `ReaccionCinetica` de core/cinetica.py -- las mismas
    que el CSTR, con las mismas leyes. Es deliberado: la ley de velocidad
    es la misma fisica en los dos regimenes, y tener dos implementaciones
    seria tener dos fisicas que se pueden separar.

    Las constantes en base VOLUMETRICA se integran con el volumen, igual
    que en el estacionario. La unidad de k declara la base.
    """
    n0 = _moles_iniciales(n0)
    n_especies = n0.size
    total0 = float(np.sum(n0))
    t_final = float(t_final)
    t_inicial = float(t_inicial)

    if t_final <= t_inicial:
        raise ErrorDeDatos(
            f"El tiempo final ({t_final} s) no es posterior al inicial "
            f"({t_inicial} s).",
            codigo=codigos.LAB_VALOR_FUERA_DE_DOMINIO,
        )
    if metodo not in METODOS:
        raise ErrorDeDatos(
            f"Metodo de integracion no admitido: {metodo!r}. Admitidos: "
            f"{', '.join(sorted(METODOS))}.",
            codigo=codigos.LAB_METODO_NO_SOPORTADO,
        )
    n_muestras = int(n_muestras)
    if n_muestras < 2 or n_muestras > MAX_MUESTRAS:
        raise ErrorDeDatos(
            f"El numero de muestras ({n_muestras}) tiene que estar entre 2 y "
            f"{MAX_MUESTRAS}. No es un limite fisico: una trayectoria de un "
            "millon de puntos no se lee, se descarga.",
            codigo=codigos.LAB_VALOR_FUERA_DE_DOMINIO,
        )

    if atol is None:
        atol = ATOL_RELATIVO_POR_OMISION * max(total0, 1.0)
    atol = float(atol)

    NU = np.array([r.nu for r in reacciones], dtype=float)
    suelo = 0.0
    evaluaciones = {"n": 0}
    recortes = {"n": 0}

    def tasas(t, n):
        evaluaciones["n"] += 1
        n_segura = np.clip(n, 0.0, None)
        if np.any(n < -1e-12 * max(total0, 1.0)):
            recortes["n"] += 1
        total = float(np.sum(n_segura))
        if total <= 0:
            return np.zeros(len(reacciones))
        x = n_segura / total
        # Una cache por base para esta (T, x): cada ley usa la de SU base
        # (antes se calculaban con la base de la primera reaccion para todas).
        actividades = {}
        netas = np.empty(len(reacciones), dtype=float)
        for j, reaccion in enumerate(reacciones):
            # K_eq hace falta si la inversa se deriva del equilibrio. Se
            # pasa como callback porque depende de T y el lote es isotermo:
            # se evalua una vez por paso y no se cachea aqui, que es
            # trabajo del que la provee.
            K = None
            if getattr(reaccion, "inversa_desde_equilibrio", False):
                if K_eq_de is None:
                    raise ErrorDeDatos(
                        f"La reaccion {reaccion.id!r} deriva su tasa inversa del "
                        "equilibrio y no se dio como calcular K_eq(T).",
                        codigo=codigos.LAB_EQUILIBRIO_NO_UTILIZABLE,
                    )
                K = K_eq_de(reaccion.id, T)
                reaccion._K_eq = K
            directa, inversa = reaccion.tasas(proveedor, T, x, actividades, K)
            netas[j] = directa - inversa
        return netas

    def derivada(t, n):
        return NU.T @ tasas(t, n)

    # --- el agotamiento, como EVENTO
    #
    # No se detecta mirando si algun numero salio negativo en las muestras:
    # eso se perderia el cruce si cae entre dos. Un evento lo localiza con
    # la misma precision que la trayectoria.
    eventos = []
    for i in range(n_especies):
        def agotada(t, n, indice=i):
            return n[indice] - 1e-12 * max(total0, 1.0)
        agotada.terminal = False
        agotada.direction = -1.0
        eventos.append(agotada)

    solucion = solve_ivp(
        derivada, (t_inicial, t_final), n0, method=metodo,
        t_eval=np.linspace(t_inicial, t_final, n_muestras),
        rtol=rtol, atol=atol, events=eventos, dense_output=False,
    )

    if not solucion.success:
        raise ErrorNumerico(
            f"La integracion del lote fallo: {solucion.message}",
            codigo=codigos.LAB_INTEGRACION_FALLIDA,
        )

    t = np.asarray(solucion.t, dtype=float)
    n_t = np.asarray(solucion.y, dtype=float)      # (especies, tiempos)

    # La no negatividad, COMPROBADA sobre la trayectoria devuelta.
    escala = max(total0, 1.0)
    peor_negativo = float(np.min(n_t)) if n_t.size else 0.0
    violaciones = [
        {"especie": int(i), "instante": float(t[k]), "moles": float(n_t[i, k])}
        for i in range(n_especies) for k in range(t.size)
        if n_t[i, k] < -1e-9 * escala
    ]

    agotamientos = []
    for i, instantes in enumerate(solucion.t_events or []):
        for instante in np.atleast_1d(instantes):
            agotamientos.append({
                "especie": int(i),
                "instante": float(instante),
                "unidad": "s",
                "nota": "localizado por un evento del integrador, no mirando las "
                        "muestras: un cruce entre dos muestras se habria perdido",
            })

    # Conservacion elemental y de masa, medidas sobre la trayectoria. Es la
    # comprobacion independiente: si la nu esta bien y la integracion
    # tambien, los atomos que habia al principio siguen ahi al final.
    return {
        "metodo": metodo,
        "descripcion_metodo": METODOS[metodo],
        "tolerancias": {"rtol": rtol, "atol": atol,
                        "nota": "Declaradas y devueltas: una trayectoria sin "
                                "tolerancia declarada no se puede reproducir ni "
                                "comparar con otra."},
        "t": [float(v) for v in t],
        "unidad_tiempo": "s",
        "moles": [[float(v) for v in fila] for fila in n_t],
        "unidad_moles": "mol",
        "n_muestras": int(t.size),
        "volumen_m3": volumen,
        "evaluaciones_de_la_ley": evaluaciones["n"],
        "pasos_del_integrador": int(solucion.nfev),
        "agotamientos": agotamientos,
        "no_negatividad": {
            "peor_valor": peor_negativo,
            "violaciones": violaciones[:20],
            "total_violaciones": len(violaciones),
            "cumple": not violaciones,
            "evaluaciones_con_recorte": recortes["n"],
            "nota": "La ley se evalua con los moles recortados a cero --UNIFAC con "
                    "fracciones negativas no significa nada-- pero la "
                    "comprobacion se hace sobre la trayectoria DEVUELTA. Recortar "
                    "y callarse convertiria un dato imposible en una curva "
                    "plausible.",
        },
        "mensaje": str(solucion.message),
    }


def conservacion_en_la_trayectoria(n_t, A, mw):
    """
    Elementos y masa a lo largo de la trayectoria, medidos.

    `n_t` tiene forma (especies, tiempos). Devuelve el peor residuo
    relativo de cada elemento y de la masa, que es la comprobacion
    independiente de que la integracion no inventa ni pierde atomos.
    """
    n_t = np.asarray(n_t, dtype=float)
    A = np.asarray(A, dtype=float)
    mw = np.asarray(mw, dtype=float)

    elementos_t = A @ n_t                     # (elementos, tiempos)
    inicial = elementos_t[:, 0]
    escala = np.maximum(np.abs(inicial), 1e-30)
    residuo_elem = np.max(np.abs(elementos_t - inicial[:, None]) / escala[:, None],
                          axis=1)

    masa_t = mw @ n_t
    escala_masa = max(abs(float(masa_t[0])), 1e-30)
    residuo_masa = float(np.max(np.abs(masa_t - masa_t[0])) / escala_masa)

    return {
        "residuo_elemental_maximo": float(np.max(residuo_elem))
        if residuo_elem.size else 0.0,
        "por_elemento": [float(v) for v in residuo_elem],
        "masa": {
            "inicial": float(masa_t[0]),
            "final": float(masa_t[-1]),
            "residuo_relativo": residuo_masa,
            "unidad": "g",
        },
        "moles_totales": {
            "inicial": float(np.sum(n_t[:, 0])),
            "final": float(np.sum(n_t[:, -1])),
            "nota": "El total PUEDE cambiar si sum(nu) no es cero. La masa no.",
        },
        "escala": "residuos relativos al valor inicial; adimensionales",
    }
