"""
Equilibrio quimico calculado: K(T), potenciales quimicos y la composicion.

LA ADVERTENCIA QUE DA SENTIDO AL MODULO
---------------------------------------
**Imponer r+ = r- NO demuestra equilibrio termodinamico.** Describe un
estado estacionario con esas dos tasas, nada mas. Dos velocidades iguales
pueden venir de dos constantes cineticas cualesquiera, y el equilibrio
termodinamico exige una cosa distinta y mas fuerte:

    Q_r = K_r(T)      equivalentemente    dG_rxn = 0

donde K sale de dG DE FORMACION, no de ninguna cinetica. Este modulo
calcula eso, y ofrece de paso la comprobacion: dado un estado --venga de
donde venga-- decir si esta en equilibrio y a que distancia.

K(T): DOS CAMINOS Y LA DIFERENCIA ENTRE ELLOS
---------------------------------------------
**van't Hoff** supone dH_rxn CONSTANTE con la temperatura:

    K(T) = K(T_ref) exp[ -dH(T_ref)/R (1/T - 1/T_ref) ]

Es lo que el motor usaba hasta ahora, y se declaraba como aproximacion.

**Riguroso**, con Kirchhoff y la integral de entropia:

    dH(T) = dH(T_ref) + integral de dCp dT
    dS(T) = dS(T_ref) + integral de dCp/T dT
    dG(T) = dH(T) - T dS(T)          K = exp(-dG(T)/RT)

Los dos se calculan y se devuelven los dos, para que la diferencia se vea
en vez de suponerse pequena. Con los butanos, Cp pasa de 142 a 211
J/(mol K) entre 300 y 400 K: la aproximacion no es inocua.

Y UN DETALLE QUE AHORRA UNA INTEGRAL
------------------------------------
dH(T) no hace falta integrarla: las entalpias SENSIBLES del motor ya la
llevan dentro.

    dH_rxn(T) = nu . (Hf + h_sens(T))

Es la misma identidad que explica por que el balance de energia no debe
corregir dH con Kirchhoff (ver docs/15 §15.9bis): ahi lo contaria dos
veces, y aqui lo da gratis. La integral que si hace falta es la de la
ENTROPIA, dCp/T, que no esta tabulada.

EL CRITERIO DE ESTABILIDAD
--------------------------
dG = 0 dice que es un punto estacionario de la energia de Gibbs, no que
sea un MINIMO. Lo que lo decide es la segunda derivada: el hessiano de G
respecto de los avances tiene que ser definido positivo. Se calcula
numericamente y se devuelven sus autovalores, que es el criterio y no una
etiqueta.

Zona libre de pint: SI (J/mol, K, mol/s o mol).
"""

import math

import numpy as np
from scipy.integrate import quad
from scipy.optimize import least_squares

from core import errores as codigos
from core.errores import ErrorDeDatos, ErrorFisico, ErrorNumerico

R_UNIVERSAL = 8.31446261815324
T_ESTANDAR = 298.15

# Suelo de los moles al evaluar actividades. No es un recorte cosmetico:
# ln(0) es -infinito y una especie ausente con nu != 0 reventaria la
# ecuacion. Se usa un suelo RELATIVO y se reporta si se toco, porque
# tocarlo significa que el equilibrio empuja a agotar una especie.
SUELO_RELATIVO = 1e-14

TOLERANCIA_EQUILIBRIO = 1e-10


def _h_puros(calculadora, T, n):
    """
    h_sens de cada componente puro a T [J/mol].

    Se piden con vectores unitarios sobre la API publica `h_liquido` en
    vez de tocar la tabla por dentro. Son n llamadas a una interpolacion,
    que no cuesta nada, y no ata este modulo a un detalle privado.
    """
    puros = np.empty(n, dtype=float)
    for i in range(n):
        x = np.zeros(n)
        x[i] = 1.0
        puros[i] = calculadora.h_liquido(float(T), x)
    return puros


def propiedades_de_reaccion(proveedor, calculadora, nu, T, T_ref=T_ESTANDAR):
    """
    dH, dS, dG y K de una reaccion a T, por los dos caminos.

    Devuelve tambien las magnitudes en T_ref, que son las que salen
    directamente de las propiedades de formacion y no dependen de ningun
    modelo de Cp.
    """
    nu = np.asarray(nu, dtype=float)
    n = nu.size

    Hf = np.asarray(proveedor.entalpias_formacion_liquido(), dtype=float)
    Gf = np.asarray(proveedor.energias_gibbs_formacion_liquido(), dtype=float)
    if not np.all(np.isfinite(Hf)) or not np.all(np.isfinite(Gf)):
        faltan = [getattr(c, "name", str(c)) for c, h, g in
                  zip(proveedor.componentes, Hf, Gf)
                  if not (math.isfinite(float(h)) and math.isfinite(float(g)))]
        raise ErrorDeDatos(
            f"Faltan propiedades de formacion de: {', '.join(faltan)}. Sin "
            "entalpia Y energia de Gibbs de formacion no hay K ni dG de "
            "reaccion; suponerlas cero daria un equilibrio inventado.",
            codigo=codigos.LAB_ENTALPIA_FORMACION_NO_DISPONIBLE,
        )

    dH_ref = float(nu @ Hf)
    dG_ref = float(nu @ Gf)
    dS_ref = (dH_ref - dG_ref) / T_ref
    K_ref = math.exp(-dG_ref / (R_UNIVERSAL * T_ref))

    T = float(T)

    # --- camino riguroso
    #
    # dH(T) sale GRATIS de las entalpias sensibles: nu . h_sens(T) es
    # exactamente la integral de dCp que Kirchhoff pide. La que si hay que
    # integrar es la de entropia, dCp/T, que no esta tabulada.
    h_sens = _h_puros(calculadora, T, n)
    dH_T = dH_ref + float(nu @ h_sens)

    def dCp_sobre_T(temperatura):
        Cp = np.asarray(
            proveedor.capacidades_calorificas_liquido(float(temperatura)),
            dtype=float)
        return float(nu @ Cp) / float(temperatura)

    if abs(T - T_ref) < 1e-12:
        integral_S, error_S = 0.0, 0.0
    else:
        integral_S, error_S = quad(dCp_sobre_T, T_ref, T, limit=100)
    dS_T = dS_ref + float(integral_S)
    dG_T = dH_T - T * dS_T
    K_riguroso = math.exp(-dG_T / (R_UNIVERSAL * T))

    # --- van't Hoff, la aproximacion
    K_vant_hoff = K_ref * math.exp(
        -(dH_ref / R_UNIVERSAL) * (1.0 / T - 1.0 / T_ref))

    dCp_T = float(nu @ np.asarray(
        proveedor.capacidades_calorificas_liquido(T), dtype=float))
    dCp_ref = float(nu @ np.asarray(
        proveedor.capacidades_calorificas_liquido(T_ref), dtype=float))

    return {
        "T": T,
        "T_ref": T_ref,
        "en_referencia": {
            "dH": dH_ref, "dS": dS_ref, "dG": dG_ref, "K": K_ref,
            "unidades": {"dH": "J/mol", "dS": "J/(mol K)", "dG": "J/mol",
                         "K": "adimensional"},
            "origen": "propiedades de formacion de 'thermo' (Hfm y Gfm) a "
                      "298.15 K. No dependen de ningun modelo de Cp.",
        },
        "riguroso": {
            "dH": dH_T, "dS": dS_T, "dG": dG_T, "K": K_riguroso,
            "metodo": "Kirchhoff para dH --que sale de las entalpias sensibles "
                      "sin integrar nada-- e integracion numerica de dCp/T para "
                      "dS (scipy.integrate.quad)",
            "error_estimado_integral_S": float(error_S),
        },
        "vant_hoff": {
            "K": K_vant_hoff,
            "aproximacion": "supone dH_rxn CONSTANTE con la temperatura",
            "diferencia_relativa_con_riguroso": (
                abs(K_vant_hoff - K_riguroso) / abs(K_riguroso)
                if K_riguroso != 0 else None),
        },
        "dCp": {
            "en_T": dCp_T, "en_T_ref": dCp_ref, "unidad": "J/(mol K)",
            "nota": "Si dCp no es despreciable, van't Hoff y el camino riguroso "
                    "se separan al alejarse de T_ref. Se dan los dos para que la "
                    "diferencia se vea en vez de suponerse pequena.",
        },
        "nu": [float(v) + 0.0 for v in nu],
        "convencion": "K = exp(-dG/RT) con dG = suma de nu_i mu_i^0. Actividades "
                      "adimensionales referidas al liquido puro.",
    }


def actividades(proveedor, T, x, base="actividad"):
    """a_i = x_i gamma_i, o x_i en la base ideal."""
    x = np.asarray(x, dtype=float)
    if base == "fraccion_molar":
        return x
    gamma = np.asarray(proveedor.coeficientes_actividad(float(T), x),
                       dtype=float)
    return x * gamma


def potenciales_quimicos(proveedor, calculadora, T, x, base="actividad",
                         T_ref=T_ESTANDAR):
    """
    mu_i = mu_i^0(T) + R T ln a_i [J/mol], con el estado estandar declarado.

    El estado estandar de este motor es el LIQUIDO PURO a la temperatura
    de la mezcla y la presion del sistema. Es el convenio que corresponde a
    unas actividades a_i = x_i gamma_i con gamma -> 1 cuando x -> 1, que es
    lo que UNIFAC da. Decirlo importa: un mu sin estado estandar declarado
    no se puede comparar con otro.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    a = actividades(proveedor, T, x, base)
    a_segura = np.maximum(a, SUELO_RELATIVO)

    Gf = np.asarray(proveedor.energias_gibbs_formacion_liquido(), dtype=float)
    Hf = np.asarray(proveedor.entalpias_formacion_liquido(), dtype=float)
    # mu^0(T) del puro, llevado de T_ref a T con la misma identidad que
    # arriba: la parte sensible ya esta en las entalpias, y la entropica se
    # integra. Para el potencial de cada especie se usa la aproximacion de
    # Gibbs-Helmholtz con su propia Cp.
    h_sens = _h_puros(calculadora, T, n)
    S_ref = (Hf - Gf) / T_ref

    def integral_S_de(i):
        if abs(T - T_ref) < 1e-12:
            return 0.0
        def integrando(temperatura):
            Cp = np.asarray(
                proveedor.capacidades_calorificas_liquido(float(temperatura)),
                dtype=float)
            return float(Cp[i]) / float(temperatura)
        valor, _ = quad(integrando, T_ref, T, limit=100)
        return float(valor)

    S_T = np.array([S_ref[i] + integral_S_de(i) for i in range(n)])
    H_T = Hf + h_sens
    mu_0 = H_T - T * S_T
    mu = mu_0 + R_UNIVERSAL * T * np.log(a_segura)

    return {
        "T": float(T),
        "estado_estandar": "liquido puro a la T de la mezcla y la p del sistema",
        "base_actividad": base,
        "por_especie": [
            {
                "indice": i,
                "x": float(x[i]),
                "actividad": float(a[i]),
                "gamma": (float(a[i] / x[i]) if x[i] > 0 else None),
                "mu_estandar": float(mu_0[i]),
                "mu": float(mu[i]),
                "unidad": "J/mol",
                "actividad_recortada": bool(a[i] < SUELO_RELATIVO),
            }
            for i in range(n)
        ],
        "nota_recorte": (
            f"Una actividad por debajo de {SUELO_RELATIVO:g} se recorta a ese "
            "suelo para evaluar el logaritmo. ln(0) es menos infinito, y una "
            "especie ausente con nu distinto de cero reventaria la ecuacion. "
            "Cuando se recorta se dice, porque significa que el equilibrio "
            "empuja a agotar esa especie."
        ),
    }


def cociente_de_reaccion(proveedor, T, x, nu, base="actividad"):
    """
    Q = prod a_i^nu_i, y su logaritmo, que es el que se usa.

    Se trabaja con ln Q y no con Q porque Q recorre ordenes de magnitud:
    con dG de -60 kJ/mol, K vale 1e10. Un residuo Q - K no se puede
    escalar de forma util; ln Q - ln K si.
    """
    nu = np.asarray(nu, dtype=float)
    a = np.maximum(actividades(proveedor, T, x, base), SUELO_RELATIVO)
    ln_Q = float(nu @ np.log(a))
    return ln_Q, math.exp(ln_Q) if -700 < ln_Q < 700 else math.inf


def distancia_al_equilibrio(proveedor, calculadora, NU, T, x,
                            base="actividad", T_ref=T_ESTANDAR):
    """
    Si un estado esta en equilibrio, y a que distancia.

    ES LA COMPROBACION QUE EL CONTRATO PIDE. Un estado estacionario con
    r+ = r- impuestas no esta necesariamente en equilibrio termodinamico, y
    esto lo dice con un numero: dG_rxn de cada reaccion. Cero es
    equilibrio; distinto de cero dice en que direccion se movera.
    """
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    x = np.asarray(x, dtype=float)
    salida = []
    for j, nu in enumerate(NU):
        propiedades = propiedades_de_reaccion(proveedor, calculadora, nu, T,
                                              T_ref)
        K = propiedades["riguroso"]["K"]
        ln_Q, Q = cociente_de_reaccion(proveedor, T, x, nu, base)
        dG_rxn = R_UNIVERSAL * T * (ln_Q - math.log(K))
        salida.append({
            "reaccion": j,
            "nu": [float(v) + 0.0 for v in nu],
            "K": K,
            "Q": Q,
            "ln_Q_menos_ln_K": ln_Q - math.log(K),
            "dG_rxn": dG_rxn,
            "unidad_dG": "J/mol",
            "en_equilibrio": abs(dG_rxn) < 1.0,
            "direccion": (
                "en equilibrio" if abs(dG_rxn) < 1.0 else
                ("avanza hacia los productos" if dG_rxn < 0 else
                 "retrocede hacia los reactivos")
            ),
            "criterio": "dG_rxn = R T ln(Q/K). Cero es equilibrio; el signo dice "
                        "hacia donde se mueve. El umbral de 1 J/mol es una "
                        "tolerancia practica, no una ley.",
        })
    return salida


def _moles_de(n0, NU, xi, suelo):
    """Los moles tras los avances, con suelo para poder tomar logaritmos."""
    n = np.asarray(n0, dtype=float) + NU.T @ np.atleast_1d(xi)
    return np.maximum(n, suelo)


def composicion_de_equilibrio(proveedor, calculadora, NU, n0, T,
                              base="actividad", T_ref=T_ESTANDAR):
    """
    La composicion de equilibrio de una alimentacion dada.

    Incognitas: los avances. Ecuaciones: ln Q_r = ln K_r, una por
    reaccion. **Las restricciones elementales se cumplen por
    construccion**: un avance sobre una nu validada conserva los elementos,
    asi que no hacen falta como ecuaciones aparte -- y anadirlas habria
    sido contar dos veces lo mismo.

    La no negatividad SI hace falta imponerla, y es la parte delicada: una
    especie en cero tiene actividad cero y ln(0) es menos infinito. Se
    acota el avance al interior del simplex estequiometrico y se recorta
    con un suelo relativo al evaluar, diciendo cuando se recorta.
    """
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    n0 = np.asarray(n0, dtype=float)
    n_reacciones, n_especies = NU.shape
    total0 = float(np.sum(n0))
    if total0 <= 0:
        raise ErrorDeDatos(
            "La alimentacion no tiene moles: no hay nada que equilibrar.",
            codigo=codigos.CAUDAL_NO_FISICO,
        )
    suelo = SUELO_RELATIVO * total0

    propiedades = [propiedades_de_reaccion(proveedor, calculadora, nu, T, T_ref)
                   for nu in NU]
    ln_K = np.array([math.log(p["riguroso"]["K"]) for p in propiedades])

    evaluaciones = {"n": 0}
    recortes = {"n": 0}

    def residuo(xi):
        evaluaciones["n"] += 1
        n = np.asarray(n0, dtype=float) + NU.T @ np.atleast_1d(xi)
        if np.any(n < suelo):
            recortes["n"] += 1
        n = np.maximum(n, suelo)
        x = n / float(np.sum(n))
        a = np.maximum(actividades(proveedor, T, x, base), SUELO_RELATIVO)
        ln_a = np.log(a)
        # ln Q - ln K, escalado por ln K cuando es grande: con K de 1e10
        # el residuo bruto vale 23 y no se puede comparar con una
        # tolerancia absoluta.
        escala = np.maximum(np.abs(ln_K), 1.0)
        return (NU @ ln_a - ln_K) / escala

    # Los limites: el interior del simplex. Con una reaccion son exactos;
    # con varias, una caja floja (ver core/cinetica.caja_de_avances) y la
    # factibilidad se comprueba despues.
    inferior = np.full(n_reacciones, -np.inf)
    superior = np.full(n_reacciones, np.inf)
    if n_reacciones == 1:
        nu = NU[0]
        lo, hi = -np.inf, np.inf
        for i, coef in enumerate(nu):
            if abs(coef) < 1e-15:
                continue
            limite = -n0[i] / coef
            if coef > 0:
                lo = max(lo, limite)
            else:
                hi = min(hi, limite)
        margen = 1e-9 * max(total0, 1.0)
        inferior[0] = lo + margen if np.isfinite(lo) else -total0
        superior[0] = hi - margen if np.isfinite(hi) else total0
        if inferior[0] >= superior[0]:
            raise ErrorFisico(
                "La alimentacion no deja sitio para ningun avance: el intervalo "
                f"estequiometrico es vacio ([{lo:.6g}, {hi:.6g}] mol).",
                codigo=codigos.LAB_CAUDAL_ESPECIE_NEGATIVO,
            )
    else:
        holgura = 4.0 * total0
        for j, nu in enumerate(NU):
            activos = np.abs(nu[np.abs(nu) > 1e-15])
            minimo = float(np.min(activos)) if activos.size else 1.0
            inferior[j], superior[j] = -holgura / minimo, holgura / minimo

    # El arranque en cero cae JUSTO en el limite cuando la alimentacion no
    # trae alguno de los productos: con n_B = 0, el avance tiene que ser
    # estrictamente positivo para que n_B siga siendo no negativo. Se mete
    # el punto de partida dentro de la caja en vez de dejar que el solver
    # lo rechace.
    inicial = np.clip(np.zeros(n_reacciones),
                      inferior + 1e-12 * max(total0, 1.0),
                      superior - 1e-12 * max(total0, 1.0))
    solucion = least_squares(residuo, inicial, bounds=(inferior, superior),
                             method="trf", xtol=1e-15, ftol=1e-15, gtol=1e-15,
                             max_nfev=4000)
    xi = np.atleast_1d(np.asarray(solucion.x, dtype=float))
    res = float(np.max(np.abs(residuo(xi))))

    n_eq_crudo = n0 + NU.T @ xi
    negativas = [i for i in range(n_especies)
                 if n_eq_crudo[i] < -1e-9 * total0]
    n_eq = np.maximum(n_eq_crudo, 0.0)
    x_eq = n_eq / float(np.sum(n_eq))

    # El hessiano de G respecto de los avances: el criterio de estabilidad.
    hessiano, autovalores, definido_positivo = _hessiano_de_gibbs(
        proveedor, NU, n0, xi, T, base, suelo)

    distancias = distancia_al_equilibrio(proveedor, calculadora, NU, T, x_eq,
                                         base, T_ref)

    return {
        "T": float(T),
        "avances": [float(v) + 0.0 for v in xi],
        "unidad_avance": "las mismas que n0 (mol o mol/s)",
        "moles_equilibrio": [float(v) + 0.0 for v in n_eq],
        "composicion_equilibrio": [float(v) + 0.0 for v in x_eq],
        "propiedades_por_reaccion": propiedades,
        "comprobacion": distancias,
        "convergencia": {
            "metodo": "scipy.optimize.least_squares con trf y limites, sobre los "
                      "avances; residuo ln Q - ln K escalado",
            "residuo_escalado": res,
            "tolerancia": TOLERANCIA_EQUILIBRIO,
            "convergio": res < TOLERANCIA_EQUILIBRIO and not negativas,
            "evaluaciones_de_funcion": evaluaciones["n"],
            "evaluaciones_con_recorte": recortes["n"],
            "escala_residuo": "ln Q - ln K dividido por max(|ln K|, 1). Se usa el "
                              "logaritmo porque Q recorre ordenes de magnitud: con "
                              "dG de -60 kJ/mol, K vale 1e10 y un residuo Q - K no "
                              "se puede escalar de forma util",
            "restricciones": [
                "restricciones elementales: se cumplen POR CONSTRUCCION, porque un "
                "avance sobre una nu validada conserva los elementos. Anadirlas "
                "como ecuaciones habria contado dos veces lo mismo",
                "no negatividad: el avance se acota al interior del simplex "
                "estequiometrico, y las actividades se recortan a un suelo "
                f"relativo de {SUELO_RELATIVO:g} para poder tomar logaritmos",
            ],
            "mensaje": str(solucion.message),
        },
        "estabilidad": {
            "hessiano_de_gibbs": [[float(v) for v in fila] for fila in hessiano],
            "autovalores": [float(v) for v in autovalores],
            "definido_positivo": bool(definido_positivo),
            "es_minimo": bool(definido_positivo),
            "criterio": (
                "dG = 0 dice que es un punto ESTACIONARIO de la energia de Gibbs, "
                "no que sea un minimo. Lo decide la segunda derivada: el hessiano "
                "de G respecto de los avances tiene que ser definido positivo. Se "
                "calcula por diferencias finitas y se dan los autovalores, que son "
                "el criterio -- no una etiqueta."
            ),
            "unidad": "J/mol por unidad de avance al cuadrado",
        },
        "especies_agotadas": [
            {"indice": i, "moles": float(n_eq[i])}
            for i in range(n_especies) if n_eq[i] <= suelo * 10
        ],
        "aviso_negativas": (
            None if not negativas else
            f"El avance deja moles negativos en {negativas}: la solucion no es "
            "fisica y el resultado no se debe usar."
        ),
    }


def _hessiano_de_gibbs(proveedor, NU, n0, xi, T, base, suelo):
    """
    La segunda derivada de G respecto de los avances, por diferencias.

    G(xi) = suma_i n_i mu_i, y solo importa su parte que depende de xi: la
    de mezcla, R T suma n_i ln a_i, mas la estandar, que es lineal en xi y
    por tanto no aporta al hessiano. Asi que basta derivar dos veces la
    parte de mezcla.
    """
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    n_reacciones = NU.shape[0]
    escala = max(float(np.sum(n0)), 1.0)
    paso = 1e-5 * escala

    def G_mezcla(avances):
        n = np.maximum(np.asarray(n0, dtype=float) + NU.T @ avances, suelo)
        x = n / float(np.sum(n))
        a = np.maximum(actividades(proveedor, T, x, base), suelo)
        return R_UNIVERSAL * float(T) * float(np.sum(n * np.log(a)))

    H = np.zeros((n_reacciones, n_reacciones))
    xi = np.atleast_1d(np.asarray(xi, dtype=float))
    for i in range(n_reacciones):
        for j in range(i, n_reacciones):
            ei = np.zeros(n_reacciones); ei[i] = paso
            ej = np.zeros(n_reacciones); ej[j] = paso
            valor = (G_mezcla(xi + ei + ej) - G_mezcla(xi + ei - ej)
                     - G_mezcla(xi - ei + ej) + G_mezcla(xi - ei - ej))
            H[i, j] = H[j, i] = valor / (4.0 * paso * paso)
    autovalores = np.linalg.eigvalsh(H)
    return H, autovalores, bool(np.all(autovalores > 0))
