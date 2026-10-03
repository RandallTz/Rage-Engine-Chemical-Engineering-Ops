"""
Dimensionado de equipos: de etapas teoricas a hardware.

Por que hacia falta. Hasta aqui el simulador daba etapas teoricas, cargas
termicas y volumenes de tanque. Nada de eso es un equipo:

  - "12 etapas teoricas" no es una columna. Falta el DIAMETRO, que es lo
    que decide si la columna se inunda, y es la dimension que manda en el
    coste.
  - "4.1 MW en el condensador" no es un intercambiador. Falta el AREA.

Sin esos dos numeros no se pueden comparar dos disenos, que es para lo que
sirve un simulador.

Este modulo NO contiene termodinamica: recibe densidades, tensiones
superficiales y cargas ya calculadas, y devuelve geometria. Esa separacion
es deliberada -- las correlaciones de aqui son empiricas y tienen rango de
validez, mientras que lo de thermodynamics/ es modelo; mezclarlos haria
imposible saber de donde sale la incertidumbre de un resultado.

DE DONDE SALEN LAS CORRELACIONES
--------------------------------
De Perry's Chemical Engineers' Handbook, seccion 14 (Equipment for
Distillation and Gas Absorption), con su numero de ecuacion. No son de
memoria ni derivadas aqui: son ajustes empiricos a datos de plantas, y
citarlas con su numero es lo que permite comprobar que estan bien
transcritas y saber a que rango se aplican.

Zona libre de pint: floats en SI, salvo donde la correlacion esta ajustada
en otras unidades -- y entonces se dice en el nombre del argumento.
"""

import math

import numpy as np

_TOL = 1e-12


# ---------------------------------------------------------------------
# Columnas de platos: el diametro
# ---------------------------------------------------------------------

def parametro_de_flujo(caudal_masico_liquido, caudal_masico_vapor,
                       densidad_liquido, densidad_vapor):
    """
    El parametro de flujo de Fair, Perry's Eq. (14-89):

        F_LG = (L/G) * sqrt(rho_G / rho_L)

    Representa la razon de energias cineticas de liquido y vapor. Valores
    bajos indican operacion en vacio; altos, presiones elevadas o mucha
    carga de liquido.

    OJO: L/G va en base MASICA, no molar. Es la primera forma de
    equivocarse aqui, y el error no revienta -- da un diametro plausible.
    Por eso los argumentos se llaman `caudal_masico_*` y no `L` y `G`.
    """
    L = float(caudal_masico_liquido)
    G = float(caudal_masico_vapor)
    if G <= _TOL:
        raise ValueError(
            "El parametro de flujo no esta definido sin caudal de vapor "
            f"(G = {G:.6g}). Una columna sin vapor no tiene diametro de inundacion."
        )
    if L < 0:
        raise ValueError(f"El caudal de liquido no puede ser negativo ({L:.6g}).")
    rho_L, rho_G = float(densidad_liquido), float(densidad_vapor)
    if rho_L <= 0 or rho_G <= 0:
        raise ValueError(
            f"Las densidades tienen que ser positivas (rho_L = {rho_L:.6g}, "
            f"rho_G = {rho_G:.6g} kg/m3)."
        )
    if rho_G >= rho_L:
        raise ValueError(
            f"La densidad del vapor ({rho_G:.6g}) no puede ser mayor o igual que la del "
            f"liquido ({rho_L:.6g} kg/m3). Cerca del punto critico las dos fases se "
            "parecen y estas correlaciones dejan de tener sentido."
        )
    return (L / G) * math.sqrt(rho_G / rho_L)


def capacidad_sin_corregir(parametro_flujo, espaciado_platos_mm):
    """
    El factor de capacidad de Souders-Brown C_sbf, Perry's Eq. (14-90):

        C_sbf = 0.0105 + 8.127e-4 * TS^0.755 * exp(-1.463 * F_LG^0.842)

    con TS el espaciado de platos en MILIMETROS y C_sbf en m/s.

    Es la forma algebraica de la grafica de Fair (Fig. 14-31), ajustada por
    Lygeros y Magoulas, Hydrocarbon Proc. 65(12), 43 (1986). Tener la
    ecuacion y no la grafica es lo que permite calcular sin leer puntos a
    ojo, y la suite comprueba que reproduce el valor que Perry's lee de la
    grafica en su propio ejemplo resuelto.

    El espaciado en mm, y no en metros, no es un descuido: la correlacion
    esta ajustada asi. Pasarle metros daria un numero 180 veces menor sin
    avisar de nada.
    """
    F = float(parametro_flujo)
    TS = float(espaciado_platos_mm)
    if F <= 0:
        raise ValueError(f"El parametro de flujo tiene que ser positivo (se dio {F:.6g}).")
    if not (150.0 <= TS <= 900.0):
        raise ValueError(
            f"El espaciado de platos ({TS:.6g} mm) esta fuera del rango en el que la "
            "correlacion de Fair esta ajustada (150 a 900 mm, Perry's Fig. 14-31). "
            "Si de verdad es ese, el numero que saldria no estaria respaldado por los "
            "datos del ajuste."
        )
    return 0.0105 + 8.127e-4 * (TS ** 0.755) * math.exp(-1.463 * (F ** 0.842))


def velocidad_de_inundacion(parametro_flujo, espaciado_platos_mm,
                            densidad_liquido, densidad_vapor,
                            tension_superficial_mN_m=20.0):
    """
    Velocidad del gas por el area NETA en la inundacion, Perry's Eq. (14-91):

        U_nf = C_sbf * (sigma/20)^0.2 * sqrt((rho_L - rho_G)/rho_G)

    con sigma en mN/m (equivalente a dyn/cm). El 20 es el valor de
    referencia del ajuste, no una constante fisica: de ahi que el
    exponente sea pequeno y la correccion suave.

    Devuelve m/s, referida al AREA NETA del plato -- no a la seccion total
    de la columna. Confundir las dos es la segunda forma de equivocarse
    aqui, y da una columna un 12 % mas estrecha de lo que toca.
    """
    sigma = float(tension_superficial_mN_m)
    if sigma <= 0:
        raise ValueError(f"La tension superficial tiene que ser positiva ({sigma:.6g} mN/m).")
    C_sbf = capacidad_sin_corregir(parametro_flujo, espaciado_platos_mm)
    rho_L, rho_G = float(densidad_liquido), float(densidad_vapor)
    return C_sbf * (sigma / 20.0) ** 0.2 * math.sqrt((rho_L - rho_G) / rho_G)


def diametro_columna(caudal_masico_vapor, caudal_masico_liquido,
                     densidad_vapor, densidad_liquido,
                     espaciado_platos_mm=600.0,
                     tension_superficial_mN_m=20.0,
                     fraccion_de_inundacion=0.80,
                     fraccion_bajantes=0.12):
    """
    El diametro de una columna de platos, por la correlacion de Fair.

    Caudales en kg/s, densidades en kg/m3, el resultado en metros.

    fraccion_de_inundacion -- Perry's recomienda disenar al 60-80 % de la
        velocidad de inundacion (seccion 14), y senala que las columnas
        reales suelen operar al 80-90 %. Por omision 0.80: el extremo
        superior del rango de diseno, que es lo que se usa cuando el coste
        importa. Subirlo mas no es un error de calculo, es una decision de
        riesgo, y por eso es un argumento y no una constante.

    fraccion_bajantes -- la parte de la seccion que se llevan los
        bajantes. 0.12 es lo tipico en un paso. El area NETA es la que
        queda para el vapor, y es la que la correlacion de Fair usa.

    Devuelve un diccionario con la geometria Y con los numeros
    intermedios, para que el resultado se pueda rastrear: un diametro
    suelto no se puede comprobar contra nada.
    """
    f = float(fraccion_de_inundacion)
    if not (0.0 < f <= 1.0):
        raise ValueError(
            f"La fraccion de inundacion tiene que estar en (0, 1] (se dio {f:.6g}). "
            "Por encima de 1 la columna estaria inundada por definicion."
        )
    fb = float(fraccion_bajantes)
    if not (0.0 <= fb < 1.0):
        raise ValueError(
            f"La fraccion de bajantes tiene que estar en [0, 1) (se dio {fb:.6g})."
        )
    G = float(caudal_masico_vapor)
    if G <= _TOL:
        raise ValueError(
            f"Sin caudal de vapor no hay diametro de inundacion que calcular (G = {G:.6g} kg/s)."
        )
    rho_G = float(densidad_vapor)

    F_LG = parametro_de_flujo(caudal_masico_liquido, G, densidad_liquido, rho_G)
    C_sbf = capacidad_sin_corregir(F_LG, espaciado_platos_mm)
    U_nf = velocidad_de_inundacion(F_LG, espaciado_platos_mm, densidad_liquido,
                                   rho_G, tension_superficial_mN_m)
    U_diseno = f * U_nf

    caudal_volumetrico = G / rho_G            # m3/s de vapor
    area_neta = caudal_volumetrico / U_diseno
    area_total = area_neta / (1.0 - fb)
    diametro = math.sqrt(4.0 * area_total / math.pi)

    return {
        "diametro": diametro,
        "area_total": area_total,
        "area_neta": area_neta,
        "velocidad_inundacion": U_nf,
        "velocidad_diseno": U_diseno,
        "parametro_flujo": F_LG,
        "C_sbf": C_sbf,
        "caudal_volumetrico_vapor": caudal_volumetrico,
        "fraccion_de_inundacion": f,
    }


def fraccion_de_inundacion_de(caudal_masico_vapor, caudal_masico_liquido,
                              densidad_vapor, densidad_liquido, area_neta,
                              espaciado_platos_mm=600.0,
                              tension_superficial_mN_m=20.0):
    """
    La inversa: dada una columna que YA EXISTE, a que fraccion de la
    inundacion esta operando.

    Es la pregunta que se hace de verdad en una planta -- no "que diametro
    necesito" sino "con lo que tengo, cuanto margen me queda" -- y es la
    forma del ejemplo resuelto de Perry's (Ejemplo 9, seccion 14), que es
    contra lo que la suite compara.
    """
    rho_G = float(densidad_vapor)
    A = float(area_neta)
    if A <= _TOL:
        raise ValueError(f"El area neta tiene que ser positiva ({A:.6g} m2).")
    F_LG = parametro_de_flujo(caudal_masico_liquido, caudal_masico_vapor,
                              densidad_liquido, rho_G)
    U_nf = velocidad_de_inundacion(F_LG, espaciado_platos_mm, densidad_liquido,
                                   rho_G, tension_superficial_mN_m)
    U = float(caudal_masico_vapor) / rho_G / A
    return {
        "velocidad": U,
        "velocidad_inundacion": U_nf,
        "fraccion_de_inundacion": U / U_nf,
        "parametro_flujo": F_LG,
        "C_sbf": capacidad_sin_corregir(F_LG, espaciado_platos_mm),
        # El "C-factor" con el que Perry's expresa el resultado del ejemplo:
        # la velocidad corregida por la raiz de la razon de densidades.
        "factor_C": U * math.sqrt(rho_G / (float(densidad_liquido) - rho_G)),
    }


# ---------------------------------------------------------------------
# Intercambiadores: el area
# ---------------------------------------------------------------------

def diferencia_media_logaritmica(T_caliente_entrada, T_caliente_salida,
                                 T_frio_entrada, T_frio_salida,
                                 contracorriente=True):
    """
    La diferencia media logaritmica de temperaturas.

        LMTD = (dT_1 - dT_2) / ln(dT_1 / dT_2)

    Dos cosas que la rompen y que aqui se comprueban en vez de confiarse:

      - **Un cruce de temperaturas** da un dT negativo, y el logaritmo de
        un cociente negativo no existe. Fisicamente significa que el calor
        tendria que subir solo. Se rechaza nombrando las dos temperaturas
        que se cruzan.
      - **dT_1 = dT_2** da 0/0. El limite existe y vale dT, pero
        calcularlo por la formula da NaN. Es el caso de un intercambiador
        con las dos corrientes a diferencia constante, que no es raro.
    """
    Tce, Tcs = float(T_caliente_entrada), float(T_caliente_salida)
    Tfe, Tfs = float(T_frio_entrada), float(T_frio_salida)

    if contracorriente:
        dT1, dT2 = Tce - Tfs, Tcs - Tfe
    else:
        dT1, dT2 = Tce - Tfe, Tcs - Tfs

    if dT1 <= 0 or dT2 <= 0:
        extremo = "la entrada del caliente con la salida del frio" if dT1 <= 0 else \
                  "la salida del caliente con la entrada del frio"
        raise ValueError(
            f"Las temperaturas se cruzan en {extremo}: dT_1 = {dT1:.4g} K, "
            f"dT_2 = {dT2:.4g} K. El calor no pasa de frio a caliente, asi que no hay "
            "diferencia media que calcular. Revisa si la configuracion es "
            f"{'contracorriente' if contracorriente else 'en paralelo'} o si las "
            "temperaturas de salida son compatibles con el balance."
        )
    if abs(dT1 - dT2) < 1e-9 * max(dT1, dT2):
        # El limite de la expresion cuando los dos extremos coinciden. Por
        # la formula seria 0/0.
        return 0.5 * (dT1 + dT2)
    return (dT1 - dT2) / math.log(dT1 / dT2)


def area_intercambiador(Q, coeficiente_global_U, lmtd, factor_correccion_F=1.0):
    """
        A = |Q| / (U * LMTD * F)

    Q en W, U en W/(m2 K), LMTD en K; el area sale en m2.

    Se toma el VALOR ABSOLUTO de Q a proposito: el signo dice si el equipo
    calienta o enfria, y un area no tiene signo. Sin eso, un condensador
    (Q < 0) daria un area negativa, que es el tipo de numero que se cuela
    en una hoja de calculo y no se nota.

    factor_correccion_F corrige la LMTD cuando el flujo no es
    contracorriente puro (un intercambiador de carcasa y tubos con varios
    pasos, por ejemplo). Por omision 1.0, que es contracorriente puro, y
    se exige que este en (0, 1]: un F mayor que 1 significaria que el
    equipo aprovecha mejor que la contracorriente, que es imposible.
    """
    U = float(coeficiente_global_U)
    dT = float(lmtd)
    F = float(factor_correccion_F)
    if U <= 0:
        raise ValueError(
            f"El coeficiente global tiene que ser positivo (se dio {U:.6g} W/m2K)."
        )
    if dT <= 0:
        raise ValueError(
            f"La diferencia media de temperaturas tiene que ser positiva ({dT:.6g} K)."
        )
    if not (0.0 < F <= 1.0):
        raise ValueError(
            f"El factor de correccion de la LMTD tiene que estar en (0, 1] (se dio "
            f"{F:.6g}). Por encima de 1 el equipo aprovecharia la diferencia de "
            "temperaturas mejor que la contracorriente pura, que es el limite."
        )
    return abs(float(Q)) / (U * dT * F)


# Coeficientes globales tipicos, Perry's tabla 11-3 y Seader. Son ORDENES
# DE MAGNITUD para tantear, no valores de diseno: el real depende del
# ensuciamiento, de la geometria y de la velocidad, y puede moverse un
# factor 2. Estan aqui para que quien tantee no tenga que inventarselos,
# y con el rango a la vista para que no los confunda con un dato.
COEFICIENTES_GLOBALES_TIPICOS = {
    # servicio: (U minimo, U tipico, U maximo) en W/(m2 K)
    "agua-agua": (850, 1400, 1700),
    "agua-organico_ligero": (310, 500, 850),
    "agua-organico_viscoso": (60, 150, 280),
    "vapor-agua": (1400, 2300, 4500),
    "vapor-organico_ligero": (480, 700, 1000),
    "vapor-organico_viscoso": (60, 180, 340),
    "organico-organico": (110, 250, 450),
    "condensador_organico-agua": (280, 500, 800),
    "rehervidor_vapor-organico": (480, 800, 1300),
    "gas-gas_baja_presion": (6, 25, 60),
}


def coeficiente_global_tipico(servicio):
    """
    Un U de partida para tantear, con su rango.

    Devuelve (tipico, minimo, maximo). Que devuelva los tres y no solo el
    tipico es intencionado: un area calculada con un U tabulado tiene la
    incertidumbre del U, y presentarla como un numero unico seria
    esconderla. El rango completo suele ser un factor 2 o mas.
    """
    if servicio not in COEFICIENTES_GLOBALES_TIPICOS:
        raise ValueError(
            f"No hay coeficiente tabulado para '{servicio}'. Los disponibles son: "
            + ", ".join(sorted(COEFICIENTES_GLOBALES_TIPICOS))
        )
    minimo, tipico, maximo = COEFICIENTES_GLOBALES_TIPICOS[servicio]
    return {"tipico": float(tipico), "minimo": float(minimo), "maximo": float(maximo)}
