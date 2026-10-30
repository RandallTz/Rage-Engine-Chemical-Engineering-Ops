"""
Cinetica de accion de masas y el solver implicito que trae consigo.

QUE CAMBIA RESPECTO A UNA TASA ESPECIFICADA
-------------------------------------------
Con la tasa dada, el avance es un DATO: el balance por especie se resuelve
hacia delante y el sistema del laboratorio es triangular (ver
docs/15-laboratorio.md §15.3). Con una ley de velocidad deja de serlo,
porque la tasa depende de la composicion de SALIDA, que es justo lo que el
balance calcula:

    xi_r = r_r(T, x_salida)      y      x_salida = x_salida(xi)

Eso es un sistema implicito y hay que resolverlo como tal. Es el motivo de
que la entrega anterior rechazara la cinetica con un diagnostico en vez de
aproximarla: resolver un sistema implicito con una marcha aguas abajo
habria dado numeros, y numeros de otro problema.

LAS TRES COSAS QUE SE DECLARAN EN VEZ DE SUPONERSE
--------------------------------------------------
**1. Los ORDENES son explicitos.** Un orden no es el coeficiente
estequiometrico. La ley de velocidad sale de un mecanismo y la
estequiometria de un balance, y coinciden solo en una reaccion elemental.
Si no se declaran, se usa |nu| de los reactivos --accion de masas
consistente con la estequiometria-- y se dice que ese fue el defecto, para
que nadie crea que lo eligio.

**2. Las tasas DIRECTA e INVERSA son dos leyes.** Cada una con su
constante, su energia de activacion y sus ordenes. Asi las brutas se
conocen por construccion, que es lo que el contrato exige. Una ley neta
escrita como una sola expresion NO da las brutas, y entonces se dicen
desconocidas.

Hay un tercer camino: derivar la inversa del equilibrio,
k_inv = k_dir / K_eq(T). Eso SI es termodinamicamente consistente --la
razon de las constantes es la constante de equilibrio, y esa es la
restriccion que impone la termodinamica-- y se ofrece como modo explicito.
Lo que no se hace es suponerlo.

**3. ARRHENIUS REFERENCIADO.** La forma

    k(T) = k_ref * exp( -Ea/R * (1/T - 1/T_ref) )

en vez de A exp(-Ea/RT). No es estetica: A tiene magnitudes absurdas
(1e13 y mas) y el exponente -Ea/RT vale -20 o -40, asi que la expresion
resta numeros enormes para dar uno pequeno. En la forma referenciada k_ref
esta a escala humana y el exponente ronda cero cerca de T_ref. Se admiten
las dos y se declara cual se uso.

LA BASE DE LA ACTIVIDAD
-----------------------
    actividad       a_i = x_i * gamma_i(T, x)   (la correcta en liquido)
    fraccion_molar  a_i = x_i                   (ideal, mas barata)

Las dos son ADIMENSIONALES, y eso quita de encima el problema de que las
unidades de k dependan del orden global: k lleva las unidades de la tasa y
punto. La base en concentracion NO se admite -- necesitaria el volumen
molar de la mezcla, que es otra decision de modelo -- y se diagnostica.

Zona libre de pint: SI en todo (mol/s, mol/(m3 s), J/mol, K).
"""

import math

import numpy as np
from scipy.optimize import brentq, least_squares, root

from core import errores as codigos
from core.errores import ErrorDeDatos, ErrorFisico, ErrorNumerico

R_UNIVERSAL = 8.31446261815324
T_REFERENCIA_POR_OMISION = 298.15

BASES_ACTIVIDAD = {
    "actividad": "a_i = x_i gamma_i(T, x), con UNIFAC. Es la base correcta en "
                 "fase liquida no ideal.",
    "fraccion_molar": "a_i = x_i. Ignora la no idealidad; mas barata y menos "
                      "correcta.",
}

# Tolerancia del sistema implicito, sobre el residuo ESCALADO.
TOLERANCIA_IMPLICITA = 1e-10

# Tope de evaluaciones. Generoso: cada una cuesta un UNIFAC, pero agotarlo
# significa que algo va mal y es mejor decirlo que seguir.
MAX_EVALUACIONES = 2000


# =====================================================================
# Una ley de velocidad
# =====================================================================

class LeyDeVelocidad:
    """
    Accion de masas con ordenes explicitos y Arrhenius referenciado.

        r(T, x) = k(T) * prod_i a_i ^ orden_i

    `ordenes` es un vector de n componentes. Un orden cero deja la especie
    fuera de la ley, que es lo normal para los productos en una ley
    directa.
    """

    def __init__(self, k_ref, Ea, ordenes, T_ref=T_REFERENCIA_POR_OMISION,
                 base="actividad", forma="referenciada", unidad_k=None,
                 base_tasa="integrada"):
        self.k_ref = float(k_ref)
        self.Ea = float(Ea)
        self.ordenes = np.asarray(ordenes, dtype=float)
        self.T_ref = float(T_ref)
        self.base = base
        self.forma = forma            # referenciada | arrhenius_clasico
        self.unidad_k = unidad_k
        self.base_tasa = base_tasa    # integrada | volumetrica

    def k(self, T):
        """
        La constante a T.

        En la forma referenciada el exponente es -Ea/R (1/T - 1/T_ref), que
        ronda cero cerca de T_ref. En la clasica es -Ea/(R T), que vale
        -20 o -40 y obliga a que A sea enorme; se admite porque los datos
        de la literatura vienen asi, pero la referenciada esta mejor
        condicionada.
        """
        T = float(T)
        if self.forma == "arrhenius_clasico":
            return self.k_ref * math.exp(-self.Ea / (R_UNIVERSAL * T))
        return self.k_ref * math.exp(
            -(self.Ea / R_UNIVERSAL) * (1.0 / T - 1.0 / self.T_ref))

    def actividades(self, proveedor, T, x):
        """a_i segun la base declarada."""
        x = np.asarray(x, dtype=float)
        if self.base == "fraccion_molar":
            return x
        gamma = proveedor.coeficientes_actividad(float(T), x)
        return x * np.asarray(gamma, dtype=float)

    def evaluar(self, proveedor, T, x, actividades=None):
        """
        r(T, x), siempre >= 0.

        Una tasa bruta es una velocidad: no puede ser negativa. El signo
        lo lleva el coeficiente estequiometrico.

        Las actividades se pueden pasar ya calculadas porque UNIFAC es lo
        mas caro de todo esto y en un volumen con varias leyes son las
        MISMAS para todas. Pedirlas por ley multiplicaria el coste de cada
        evaluacion, y cada evaluacion ocurre dentro del lazo del solver.
        """
        if actividades is None:
            actividades = self.actividades(proveedor, T, x)
        a = np.clip(np.asarray(actividades, dtype=float), 0.0, None)
        # 0^0 es 1 y numpy lo hace bien; un orden cero deja la especie
        # fuera sin que haya que filtrarla.
        producto = float(np.prod(np.power(a, self.ordenes)))
        return self.k(T) * producto

    def como_diccionario(self, componentes):
        return {
            "forma": self.forma,
            "k_ref": self.k_ref,
            "unidad_k": self.unidad_k,
            "T_ref": self.T_ref if self.forma == "referenciada" else None,
            "Ea": self.Ea,
            "unidad_Ea": "J/mol",
            "base_actividad": self.base,
            "descripcion_base": BASES_ACTIVIDAD[self.base],
            "base_tasa": self.base_tasa,
            "ordenes": {componentes[i]: float(self.ordenes[i])
                        for i in range(len(self.ordenes))},
            "latex": (r"r = k(T)\prod_i a_i^{n_i}",),
            "nota_unidades": (
                "Las actividades son adimensionales en las dos bases, asi que k "
                "lleva las unidades de la tasa y no dependen del orden global."
            ),
        }


# =====================================================================
# Una reaccion cinetica
# =====================================================================

class ReaccionCinetica:
    """
    Una reaccion cuya tasa SE CALCULA, con su ley directa y su inversa.

    `brutas_disponibles` es True siempre que haya ley directa: una ley de
    accion de masas da la velocidad bruta de ese sentido por definicion.
    Lo que no da las brutas es una ley NETA escrita como una sola
    expresion, y para eso esta el modo 'neta'.
    """

    def __init__(self, id, bloque_id, nu, ley_directa, ley_inversa=None,
                 inversa_desde_equilibrio=False, volumen=None, modo="cinetica"):
        self.id = id
        self.bloque_id = bloque_id
        self.nu = np.asarray(nu, dtype=float)
        self.ley_directa = ley_directa
        self.ley_inversa = ley_inversa
        self.inversa_desde_equilibrio = inversa_desde_equilibrio
        self.volumen = volumen
        self.modo = modo
        self.base = "cinetica"
        self.unidad = ley_directa.unidad_k
        # Rellenados al resolver, para poder reportar lo que de verdad paso.
        self.r_directa = None
        self.r_inversa = None
        self.r_neta = None
        self.balance_elemental = None
        self.balance_masa = None
        self._K_eq = None

    # -- lo que el solver necesita ----------------------------------
    def tasas(self, proveedor, T, x, actividades=None, K_eq=None):
        """
        (r+, r-) en las unidades de k, las dos >= 0.

        La inversa tiene tres origenes posibles y los tres se distinguen:
        una ley propia, derivarla del equilibrio, o no existir.
        """
        # Cada ley con SU base. `actividades` es una cache {base: a_i} de la
        # misma (T, x), que comparten las leyes de un volumen; un array suelto
        # (forma antigua) son las de la base de la directa, y nunca se dan a
        # una inversa que declaro otra.
        if isinstance(actividades, dict):
            cache = actividades
        else:
            cache = {}
            if actividades is not None:
                cache[self.ley_directa.base] = actividades

        def de(ley):
            if ley.base not in cache:
                cache[ley.base] = ley.actividades(proveedor, T, x)
            return cache[ley.base]

        actividades = de(self.ley_directa)
        directa = self.ley_directa.evaluar(proveedor, T, x, actividades)

        if self.ley_inversa is not None:
            inversa = self.ley_inversa.evaluar(proveedor, T, x, de(self.ley_inversa))
        elif self.inversa_desde_equilibrio:
            if K_eq is None or not math.isfinite(K_eq) or K_eq <= 0:
                raise ErrorFisico(
                    f"La reaccion {self.id!r} pide derivar su tasa inversa del "
                    f"equilibrio y K_eq(T) sale {K_eq!r}.",
                    codigo=codigos.LAB_EQUILIBRIO_NO_UTILIZABLE,
                )
            # k_inv = k_dir / K_eq es la restriccion que impone la
            # termodinamica: en el equilibrio r+ = r- obliga a que la
            # razon de las constantes sea K_eq.
            a = np.clip(np.asarray(actividades, dtype=float), 0.0, None)
            exponentes_producto = np.where(self.nu > 0, self.nu, 0.0)
            exponentes_reactivo = np.where(self.nu < 0, -self.nu, 0.0)
            prod_productos = float(np.prod(np.power(a, exponentes_producto)))
            prod_reactivos = float(np.prod(np.power(a, exponentes_reactivo)))
            # r- = (k_dir/K_eq) * prod(productos^nu). La ley directa puede
            # tener ordenes propios, asi que se reconstruye con la misma
            # constante y los exponentes de la estequiometria, que es lo
            # que la consistencia termodinamica exige.
            k_dir = self.ley_directa.k(T)
            inversa = (k_dir / K_eq) * prod_productos
            # Y se deja la directa en su forma de accion de masas
            # estequiometrica, porque mezclar ordenes libres con una
            # inversa derivada del equilibrio NO es consistente: la
            # razon r+/r- dejaria de ser K_eq.
            directa = k_dir * prod_reactivos
        else:
            inversa = 0.0
        return max(directa, 0.0), max(inversa, 0.0)

    @property
    def brutas_disponibles(self):
        return self.modo != "neta"

    @property
    def xi(self):
        return self.r_neta

    def fuente_neta(self):
        return self.nu * self.r_neta

    def generacion_bruta(self):
        if not self.brutas_disponibles or self.r_directa is None:
            return None
        return (np.maximum(self.nu, 0.0) * self.r_directa
                + np.maximum(-self.nu, 0.0) * (self.r_inversa or 0.0))

    def consumo_bruto(self):
        if not self.brutas_disponibles or self.r_directa is None:
            return None
        return (np.maximum(-self.nu, 0.0) * self.r_directa
                + np.maximum(self.nu, 0.0) * (self.r_inversa or 0.0))

    def como_diccionario(self, componentes):
        g = self.generacion_bruta()
        c = self.consumo_bruto()
        neta = self.fuente_neta() if self.r_neta is not None else None
        return {
            "id": self.id,
            "bloque_id": self.bloque_id,
            "nu": [float(v) + 0.0 for v in self.nu],
            "convencion_nu": "positivo producto, negativo reactivo",
            "modo_tasa": "cinetica",
            "base_tasa": self.ley_directa.base_tasa,
            "unidad_declarada": self.unidad,
            "volumen_m3": self.volumen,
            "ley_directa": self.ley_directa.como_diccionario(componentes),
            "ley_inversa": (
                self.ley_inversa.como_diccionario(componentes)
                if self.ley_inversa is not None else
                ({"origen": "derivada del equilibrio",
                  "expresion": "k_inv = k_dir / K_eq(T)",
                  "K_eq_usada": self._K_eq,
                  "ruta_de_K": "rigurosa: Kirchhoff para dH --que sale de las "
                               "entalpias sensibles sin integrar nada-- e "
                               "integracion numerica de dCp/T para dS. NO van't "
                               "Hoff: la diferencia llega al medio por ciento en "
                               "la composicion de equilibrio a 100 K de la "
                               "referencia, y dos partes del motor contestando "
                               "cosas distintas a la misma pregunta es peor que "
                               "una aproximacion declarada.",
                  "nota": "Es la restriccion que impone la termodinamica: en el "
                          "equilibrio r+ = r- obliga a que la razon de las "
                          "constantes sea K_eq. Con este modo la ley directa usa "
                          "los exponentes de la estequiometria, porque mezclar "
                          "ordenes libres con una inversa derivada del equilibrio "
                          "romperia esa consistencia."}
                 if self.inversa_desde_equilibrio else None)
            ),
            "tasa_directa": self.r_directa,
            "tasa_inversa": self.r_inversa,
            "tasa_neta_declarada": None,
            "avance_neto": None if self.r_neta is None else float(self.r_neta) + 0.0,
            "unidad_avance": "mol/s",
            "brutas_disponibles": self.brutas_disponibles,
            "motivo_brutas_no_disponibles": None,
            "por_especie": [
                {
                    "componente": componentes[i],
                    "nu": float(self.nu[i]) + 0.0,
                    "generacion_bruta": None if g is None else float(g[i]) + 0.0,
                    "consumo_bruto": None if c is None else float(c[i]) + 0.0,
                    "fuente_neta": None if neta is None else float(neta[i]) + 0.0,
                }
                for i in range(len(self.nu))
            ],
            "balance_elemental": self.balance_elemental,
            "balance_masa": self.balance_masa,
        }


# =====================================================================
# El solver implicito
# =====================================================================

class ResultadoImplicito:
    """Lo que el solver consiguio, y con que algoritmo de verdad."""

    def __init__(self, xi, T, metodo, alcance, residuo, escala, evaluaciones,
                 convergio, nota=None, restricciones=None, motivo=None):
        self.xi = np.asarray(xi, dtype=float)
        self.T = T
        self.metodo = metodo
        self.alcance = alcance
        self.residuo = residuo
        self.escala = escala
        self.evaluaciones = evaluaciones
        self.convergio = convergio
        self.nota = nota
        self.restricciones = restricciones or []
        self.motivo = motivo

    def como_diccionario(self):
        return {
            "metodo": self.metodo,
            "alcance": self.alcance,
            "itera": True,
            "residuo_escalado": self.residuo,
            "escala_residuo": self.escala,
            "tolerancia": TOLERANCIA_IMPLICITA,
            "evaluaciones_de_funcion": self.evaluaciones,
            "convergio": self.convergio,
            "restricciones": list(self.restricciones),
            "nota": self.nota,
            "motivo_sin_convergencia": self.motivo,
        }


def limites_de_avance(F_i_in, NU):
    """
    El intervalo donde los caudales de salida se quedan en cero o mas.

    Con UNA reaccion es un intervalo exacto: el avance no puede agotar mas
    de lo que entra, ni hacia delante ni hacia atras. Con varias, los
    limites de cada una suponiendo las otras a cero NO son conservadores
    --dos reacciones pueden consumir el mismo reactivo-- y por eso con
    varias el solver no usa limites sino que comprueba la factibilidad al
    final. Decirlo es mejor que usar un limite que no limita.
    """
    F_i_in = np.asarray(F_i_in, dtype=float)
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    if NU.shape[0] != 1:
        return None, None
    nu = NU[0]
    minimo, maximo = -np.inf, np.inf
    for i, coef in enumerate(nu):
        if abs(coef) < 1e-15:
            continue
        # F_i_in + coef * xi >= 0
        limite = -F_i_in[i] / coef
        if coef > 0:
            minimo = max(minimo, limite)
        else:
            maximo = min(maximo, limite)
    return minimo, maximo


def resolver_cinetica_isoterma(proveedor, reacciones, F_i_in, T, n,
                               K_eq_de=None):
    """
    Los avances de un volumen isotermo con leyes de velocidad.

    Residuo: g_r(xi) = xi_r - r_r(T, x_salida(xi)). Escalado por el caudal
    de entrada, que es la escala natural del problema: un residuo de
    1e-3 mol/s no significa lo mismo con 1 mol/s de alimentacion que con
    10 000.

    DOS ALGORITMOS, cada uno declarado como lo que es:

      una reaccion    brentq sobre un intervalo ACOTADO por la
                      estequiometria. El cambio de signo esta garantizado:
                      en xi = 0 el residuo es -r (negativo si la reaccion
                      avanza) y en el limite el reactivo se agota, la tasa
                      cae a cero y el residuo vale xi > 0.

      varias          root/hybr sobre el vector de avances. No hay
                      intervalo que acote un sistema, asi que la
                      factibilidad se COMPRUEBA al final en vez de
                      imponerse.

    Declarar "Newton" para los dos seria falso en los dos casos.
    """
    F_i_in = np.asarray(F_i_in, dtype=float)
    F_total_in = float(np.sum(F_i_in))
    escala = max(F_total_in, 1.0)
    NU = np.array([r.nu for r in reacciones], dtype=float)
    evaluaciones = {"n": 0}

    def composicion(xi):
        F_i = F_i_in + NU.T @ np.atleast_1d(xi)
        # Para EVALUAR la ley hace falta una composicion en el simplex:
        # UNIFAC con fracciones negativas no significa nada. Se recorta
        # solo para evaluar, y la factibilidad se comprueba aparte sobre
        # el xi de verdad -- recortar y callarse convertiria un dato
        # imposible en un resultado plausible.
        F_i = np.clip(F_i, 0.0, None)
        total = float(np.sum(F_i))
        if total <= 0:
            return np.full(n, 1.0 / n)
        return F_i / total

    def tasas_en(xi, T_actual):
        evaluaciones["n"] += 1
        x = composicion(xi)
        # Una cache por base para esta (T, x): cada ley usa la suya.
        actividades = {}
        netas = np.empty(len(reacciones), dtype=float)
        for j, reaccion in enumerate(reacciones):
            K = None
            if reaccion.inversa_desde_equilibrio and K_eq_de is not None:
                K = K_eq_de(reaccion.id, T_actual)
                reaccion._K_eq = K
            directa, inversa = reaccion.tasas(
                proveedor, T_actual, x, actividades, K)
            reaccion.r_directa, reaccion.r_inversa = directa, inversa
            netas[j] = directa - inversa
        return netas

    def residuo(xi):
        xi = np.atleast_1d(np.asarray(xi, dtype=float))
        return (xi - tasas_en(xi, T)) / escala

    # ---------------------------------------------------- una reaccion
    if len(reacciones) == 1:
        minimo, maximo = limites_de_avance(F_i_in, NU)
        # Un margen hacia dentro: en el limite exacto una fraccion vale
        # cero y una potencia de orden fraccionario puede dar infinito en
        # la derivada. Se entra un epsilon.
        margen = 1e-12 * escala
        a = minimo + margen if math.isfinite(minimo) else -escala * 1e6
        b = maximo - margen if math.isfinite(maximo) else escala * 1e6
        if a >= b:
            raise ErrorFisico(
                "La alimentacion no deja sitio para ningun avance: el intervalo "
                f"estequiometrico es vacio ([{minimo:.6g}, {maximo:.6g}] mol/s).",
                codigo=codigos.LAB_CAUDAL_ESPECIE_NEGATIVO,
            )
        ga, gb = float(residuo(a)[0]), float(residuo(b)[0])
        if ga * gb > 0:
            # Sin cambio de signo no hay raiz en el intervalo FISICO. No
            # es un fallo del solver: es que la ley y la alimentacion no
            # se encuentran, y hay que decirlo con los dos extremos.
            raise ErrorNumerico(
                "El residuo no cambia de signo en el intervalo estequiometrico "
                f"[{a:.6g}, {b:.6g}] mol/s: vale {ga:.6g} en un extremo y "
                f"{gb:.6g} en el otro. No hay avance fisico que satisfaga la ley "
                "de velocidad; revisa la constante, los ordenes y la "
                "alimentacion.",
                codigo=codigos.LAB_SIN_CAMBIO_DE_SIGNO,
            )
        xi_raiz = brentq(lambda v: float(residuo(v)[0]), a, b,
                         xtol=1e-14, rtol=8.9e-16, maxiter=200)
        xi = np.array([xi_raiz], dtype=float)
        tasas_en(xi, T)
        for reaccion in reacciones:
            reaccion.r_neta = reaccion.r_directa - reaccion.r_inversa
        res = abs(float(residuo(xi)[0]))
        return ResultadoImplicito(
            xi, T,
            metodo="brentq sobre el avance, acotado por la estequiometria",
            alcance="raiz_escalar_acotada",
            residuo=res, escala="relativo al caudal molar de entrada",
            evaluaciones=evaluaciones["n"],
            convergio=res < TOLERANCIA_IMPLICITA,
            nota=f"intervalo fisico [{minimo:.6g}, {maximo:.6g}] mol/s",
            restricciones=[
                f"avance en [{minimo:.6g}, {maximo:.6g}] mol/s por la "
                "estequiometria y la alimentacion",
            ],
        )

    # ------------------------------------------------- varias reacciones
    solucion = root(residuo, np.zeros(len(reacciones)), method="hybr",
                    tol=TOLERANCIA_IMPLICITA,
                    options={"maxfev": MAX_EVALUACIONES})
    xi = np.atleast_1d(np.asarray(solucion.x, dtype=float))
    tasas_en(xi, T)
    for reaccion in reacciones:
        reaccion.r_neta = reaccion.r_directa - reaccion.r_inversa
    res = float(np.max(np.abs(residuo(xi))))
    return ResultadoImplicito(
        xi, T,
        metodo="scipy.optimize.root con hybr (Powell hibrido) sobre el vector "
               "de avances",
        alcance="sistema_acoplado",
        residuo=res, escala="maximo del residuo relativo al caudal molar de "
                            "entrada",
        evaluaciones=evaluaciones["n"],
        convergio=bool(solucion.success) and res < TOLERANCIA_IMPLICITA,
        nota=solucion.message,
        restricciones=[
            "la factibilidad (caudales de salida no negativos) se COMPRUEBA "
            "despues, no se impone: con varias reacciones los limites de cada "
            "una suponiendo las otras a cero no son conservadores, porque dos "
            "reacciones pueden consumir el mismo reactivo",
        ],
        motivo=None if solucion.success else
        f"hybr no convergio: {solucion.message}",
    )


def caja_de_avances(F_i_in, NU, holgura=4.0):
    """
    Una caja generosa para los avances, que no excluya ninguna solucion.

    Con una reaccion los limites exactos los da `limites_de_avance`. Con
    varias no hay caja exacta --dos reacciones pueden consumir el mismo
    reactivo, asi que el limite de una depende de la otra-- y una caja
    ajustada a ojo podria dejar fuera la solucion de verdad. Asi que se
    acota flojo: ningun avance fisico puede mover mas moles de los que hay,
    y se multiplica por una holgura para que el limite nunca sea el que
    decide.

    Lo que esta caja hace es impedir que el solver se vaya a 1e30, no
    garantizar factibilidad. Eso se comprueba despues.
    """
    F_i_in = np.asarray(F_i_in, dtype=float)
    total = max(float(np.sum(F_i_in)), 1.0)
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    limites = []
    for fila in NU:
        activos = np.abs(fila[np.abs(fila) > 1e-15])
        minimo_coef = float(np.min(activos)) if activos.size else 1.0
        limites.append(holgura * total / minimo_coef)
    limites = np.array(limites, dtype=float)
    return -limites, limites


# Vueltas del arranque por sustituciones sucesivas. Pocas a proposito: no
# es un solver, es una forma de llegar cerca. Si no converge en estas, el
# acoplamiento es fuerte y la pule el solver acotado.
VUELTAS_ARRANQUE = 12


def _arranque_por_sustitucion(proveedor, reacciones, F_i_in, T_in, h_in, n,
                              entalpia_de, dH_de, Q, K_eq_de, T_min, T_max):
    """
    Un punto de partida alternando los dos problemas escalares robustos.

    Devuelve (xi, T, vueltas, convergio_el_arranque). No pretende ser la
    respuesta: pretende estar cerca, porque desde (xi=0, T=T_ent) la
    direccion de descenso del cuadrado apunta al lado contrario en una
    reaccion exotermica.
    """
    F_i_in = np.asarray(F_i_in, dtype=float)
    F_total_in = float(np.sum(F_i_in))
    NU = np.array([r.nu for r in reacciones], dtype=float)
    T = min(max(float(T_in), T_min + 1e-6), T_max - 1e-6)
    xi = np.zeros(len(reacciones), dtype=float)
    vueltas = 0
    convergio = False

    for vueltas in range(1, VUELTAS_ARRANQUE + 1):
        # 1. el avance con T fija, por el camino robusto de siempre
        try:
            paso = resolver_cinetica_isoterma(
                proveedor, reacciones, F_i_in, T, n, K_eq_de=K_eq_de)
            xi_nuevo = paso.xi
        except (ErrorFisico, ErrorNumerico, ValueError):
            # Si a esta T no hay avance fisico, el arranque se queda con
            # lo que tenia: no es un fallo del calculo, es que esta vuelta
            # no sirve.
            break

        # 2. la T con el avance fijo, invirtiendo el balance de energia
        F_i = np.clip(F_i_in + NU.T @ xi_nuevo, 0.0, None)
        total = float(np.sum(F_i))
        x = np.full(n, 1.0 / n) if total <= 0 else F_i / total
        calor_rxn = sum(float(xi_nuevo[j]) * dH_de(reacciones[j].id)
                        for j in range(len(reacciones)))
        h_objetivo = (Q + F_total_in * h_in - calor_rxn) / max(total, 1e-30)

        def desajuste(T_prueba):
            return entalpia_de(T_prueba, x) - h_objetivo

        try:
            a, b = T_min + 1e-6, T_max - 1e-6
            fa, fb = desajuste(a), desajuste(b)
            if fa * fb > 0:
                # La entalpia objetivo cae fuera del rango de la tabla. No
                # se fuerza: se deja el extremo mas cercano como punto de
                # partida y que el solver acotado diga lo que haya.
                T_nuevo = a if abs(fa) < abs(fb) else b
            else:
                T_nuevo = float(brentq(desajuste, a, b, xtol=1e-10))
        except (ValueError, ArithmeticError):
            break

        cambio = max(
            float(np.max(np.abs(xi_nuevo - xi))) / max(F_total_in, 1.0),
            abs(T_nuevo - T) / max(abs(T), 1.0),
        )
        xi, T = xi_nuevo, T_nuevo
        if cambio < 1e-12:
            convergio = True
            break

    return xi, T, vueltas, convergio


def resolver_cinetica_con_energia(proveedor, reacciones, F_i_in, T_in, h_in,
                                  n, entalpia_de, dH_de, Q=None,
                                  K_eq_de=None, T_inicial=None,
                                  T_limites=None):
    """
    Los avances Y la temperatura, cerrados a la vez.

    Con cinetica la temperatura y las tasas estan acopladas en los dos
    sentidos: k(T) decide el avance y el avance decide el calor que libera,
    que decide T. Resolver uno y luego el otro da la respuesta de otro
    problema, asi que se resuelven juntos.

    Incognitas: los avances mas T. Ecuaciones: una por ley mas el balance
    de energia

        Q + F_ent h_ent - F_sal h_sal - sum_r xi_r dH_rxn,r = 0

    Con Q = 0 es el caso adiabatico, que es el que de verdad interesa:
    ahi la temperatura es una consecuencia de la quimica y no un dato.

    El algoritmo es root/hybr sobre el vector completo, SIEMPRE -- tambien
    con una sola reaccion, porque el acoplamiento con T ya hace que sea un
    sistema. Y se declara asi.
    """
    F_i_in = np.asarray(F_i_in, dtype=float)
    F_total_in = float(np.sum(F_i_in))
    escala_materia = max(F_total_in, 1.0)
    NU = np.array([r.nu for r in reacciones], dtype=float)
    Q = 0.0 if Q is None else float(Q)
    # La escala de la energia. NO |F h_ent| a secas: h es SENSIBLE y vale
    # cero a 298.15 K, asi que con una alimentacion cerca de la referencia
    # esa escala se desploma y el residuo escalado se dispara sin que
    # ocurra nada fisico. Se toma el mayor de lo que de verdad mide el
    # balance, y F R T como suelo porque es la escala natural de una
    # energia molar.
    escala_energia = max(
        abs(F_total_in * h_in),
        abs(Q),
        F_total_in * R_UNIVERSAL * max(float(T_in), 1.0),
        1.0,
    )
    evaluaciones = {"n": 0}

    def descomponer(v):
        return np.atleast_1d(np.asarray(v[:-1], dtype=float)), float(v[-1])

    def residuo(v):
        xi, T = descomponer(v)
        evaluaciones["n"] += 1
        F_i = np.clip(F_i_in + NU.T @ xi, 0.0, None)
        total = float(np.sum(F_i))
        x = np.full(n, 1.0 / n) if total <= 0 else F_i / total

        # Una cache por base para esta (T, x): cada ley usa la suya.
        actividades = {}
        netas = np.empty(len(reacciones), dtype=float)
        for j, reaccion in enumerate(reacciones):
            K = None
            if reaccion.inversa_desde_equilibrio and K_eq_de is not None:
                K = K_eq_de(reaccion.id, T)
                reaccion._K_eq = K
            directa, inversa = reaccion.tasas(proveedor, T, x, actividades, K)
            reaccion.r_directa, reaccion.r_inversa = directa, inversa
            netas[j] = directa - inversa

        # El balance de energia, con el calor de reaccion explicito porque
        # la referencia de entalpia es sensible (ver docs/15 §15.9bis).
        h_out = entalpia_de(T, x)
        calor_rxn = sum(float(xi[j]) * dH_de(reacciones[j].id)
                        for j in range(len(reacciones)))
        energia = (Q + F_total_in * h_in - total * h_out - calor_rxn)

        return np.concatenate([(xi - netas) / escala_materia,
                               [energia / escala_energia]])

    # --- los limites
    #
    # La temperatura, al dominio de la tabla de entalpia. Es un limite
    # RIGUROSO: fuera de ahi el modelo no esta definido, y dejar que el
    # solver mire ahi es lo que hacia que no convergiera -- con la tasa
    # creciendo como exp(-Ea/RT), el primer paso se iba a temperaturas sin
    # sentido y no volvia.
    T_min, T_max = (T_limites if T_limites is not None
                    else (max(float(T_in) - 500.0, 1.0), float(T_in) + 500.0))
    xi_min, xi_max = caja_de_avances(F_i_in, NU)
    inferior = np.concatenate([xi_min, [T_min]])
    superior = np.concatenate([xi_max, [T_max]])

    # El arranque. Sin esto, least_squares se para en un minimo local del
    # cuadrado que no es raiz: desde (xi=0, T=T_ent) la direccion de
    # descenso apunta a T menor, al lado contrario de donde esta la
    # solucion de una exotermica.
    xi0, T0, vueltas, arranque_convergio = _arranque_por_sustitucion(
        proveedor, reacciones, F_i_in, T_in, h_in, n, entalpia_de, dH_de, Q,
        K_eq_de, T_min, T_max)
    T0 = min(max(float(T0), T_min + 1e-9), T_max - 1e-9)
    xi0 = np.clip(xi0, xi_min, xi_max)
    inicial = np.concatenate([xi0, [T0]])

    solucion = least_squares(
        residuo, inicial, bounds=(inferior, superior), method="trf",
        xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=MAX_EVALUACIONES,
    )
    xi, T = descomponer(solucion.x)
    residuos = residuo(solucion.x)
    for reaccion in reacciones:
        reaccion.r_neta = reaccion.r_directa - reaccion.r_inversa
    res = float(np.max(np.abs(residuos)))
    # Un limite ACTIVO no es una solucion: significa que el solver se
    # quedo en la pared, y el residuo de ahi no describe un estado
    # estacionario. Se detecta y se dice.
    en_el_limite = [
        nombre for nombre, valor, lim_inf, lim_sup in zip(
            [f"avance de {r.id}" for r in reacciones] + ["temperatura"],
            solucion.x, inferior, superior)
        if abs(valor - lim_inf) < 1e-8 * max(abs(lim_inf), 1.0)
        or abs(valor - lim_sup) < 1e-8 * max(abs(lim_sup), 1.0)
    ]
    return ResultadoImplicito(
        xi, T,
        metodo=(
            "arranque por sustituciones sucesivas (avance con T fija por brentq, "
            "y T con el avance fijo invirtiendo el balance de energia, tambien "
            f"por brentq; {vueltas} vuelta(s)"
            + (", convergido" if arranque_convergio else ", sin converger")
            + "), y despues scipy.optimize.least_squares con trf (region de "
              "confianza reflectiva) sobre los avances Y la temperatura a la vez, "
              "con limites"
        ),
        alcance="sistema_acoplado",
        residuo=res,
        escala="maximo de: residuos de avance relativos al caudal molar de "
               "entrada, y residuo de energia relativo al mayor de |F h|, |Q| y "
               "F R T",
        evaluaciones=int(solucion.nfev),
        convergio=res < TOLERANCIA_IMPLICITA and not en_el_limite,
        nota=(str(solucion.message)
              + " | Se resuelve como sistema tambien con una sola reaccion: el "
                "acoplamiento con T ya lo hace un sistema. Se usa un solver CON "
                "LIMITES porque la temperatura los tiene: la tabla de entalpia "
                f"cubre [{T_min:.1f}, {T_max:.1f}] K y fuera de ahi el modelo no "
                "esta definido."),
        restricciones=[
            f"temperatura en [{T_min:.1f}, {T_max:.1f}] K, el dominio de la tabla "
            "de entalpia. Es un limite riguroso: fuera el modelo no existe",
            "el arranque alterna dos problemas escalares acotados, cada uno con "
            "cambio de signo garantizado; hace falta porque least_squares minimiza "
            "el cuadrado del residuo y puede pararse en un minimo local que no es "
            "raiz",
            "avances en una caja generosa derivada de los moles disponibles. No es "
            "ajustada --con varias reacciones no puede serlo-- y solo sirve para "
            "que el solver no se vaya lejos",
            "la factibilidad (caudales de salida no negativos) se comprueba "
            "despues de converger",
        ],
        motivo=(
            None if res < TOLERANCIA_IMPLICITA and not en_el_limite else
            (f"la solucion se quedo en el limite de {', '.join(en_el_limite)}, asi "
             "que no es un estado estacionario: el sistema pide salirse del "
             "dominio del modelo."
             if en_el_limite else
             f"el residuo escalado quedo en {res:.3e}, por encima de la "
             f"tolerancia de {TOLERANCIA_IMPLICITA:.0e}. {solucion.message}")
        ),
    )
