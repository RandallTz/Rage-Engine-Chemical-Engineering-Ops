"""
Reactor continuo de tanque agitado (CSTR) en estado estacionario.

Mismo estandar que el resto del simulador: NO es un bloque "de adelante
hacia atras" solamente -- resuelve en la direccion que haga falta. Las
tres direcciones utiles estan implementadas de forma EXACTA (algebra,
sin iterar):

  adelante : conocidos el alimento y el avance xi  -> salida
  atras    : conocidas la salida y xi              -> alimento
  avance   : conocidos el alimento y UNA fraccion
             de salida                             -> xi (y con el, todo lo demas)

La tercera es la que hace util al bloque en la practica: normalmente uno
sabe lo que entra y QUE PUREZA quiere a la salida, y lo que busca es el
avance (y de ahi el volumen) que hace falta.

Balance por componente, en estado estacionario:

    F_out * x_out_i = F_in * x_in_i + sum_j nu_ji * xi_j

donde xi_j [mol/s] es el avance de la reaccion j. Sumando en i y usando
que las fracciones suman 1 sale el balance total,
F_out = F_in + sum_j nu_tot_j * xi_j, que por eso no se impone aparte
(seria redundante).

Cinetica (bloque separado, porque no siempre se quiere): en un CSTR la
composicion del tanque ES la de salida, asi que

    xi_j = V * r_j(T, x_out)

VARIAS REACCIONES A LA VEZ
--------------------------
`nu` admite un vector (una reaccion) o una matriz n_reacciones x
n_componentes. Con una sola, todo se comporta EXACTAMENTE como antes:
los avances entran y salen como escalares y los numeros validados no se
mueven. Con varias, el avance es un vector y hay tantas ecuaciones
cineticas (o de equilibrio) como reacciones.

Tres metodos NO se generalizan sin cambiar de significado, y eso se dice
en vez de disimularlo:

  - `avance_desde_fraccion`: UNA fraccion de salida determina UN avance.
    Con R reacciones hacen falta R fracciones, y el sistema pasa a ser
    lineal de RxR -> `avances_desde_fracciones`.
  - `volumen_desde_avance`: un solo volumen tiene que satisfacer las R
    ecuaciones cineticas a la vez, asi que un juego cualquiera de avances
    NO es alcanzable. Con varias reacciones se exige el indice de la
    reaccion que fija V y se COMPRUEBA que las demas cuadren.
  - `conversion`: con varias reacciones un reactivo puede consumirse en
    mas de una, asi que el consumo es la suma sobre reacciones. Eso si
    generaliza, y lo hace.

BALANCE DE ENERGIA (ver _exigir_energia y siguientes):

    F_in*h(T_in, x_in) + Q  =  F_out*h(T_out, x_out) + xi*dH_rxn(T_ref)

La sutileza esta en el ULTIMO termino, y es la razon de que este balance
no se pudiera escribir bien hasta que la entalpia se unifico. Se
desarrolla en docs/09-reactor-cstr.md; en corto:

  - h mide entalpia SENSIBLE, con referencia "componentes puros liquidos
    a T_ref con h_i = 0". No incluye entalpias de formacion.
  - Por eso el calor de reaccion hay que ponerlo a mano, y hay que
    ponerlo evaluado EXACTAMENTE en esa T_ref -- no en T_out.
  - No es una aproximacion de "dH_rxn constante con T": la dependencia
    con T del calor de reaccion ya esta contenida en el termino
    F_out*h(T_out, x_out), porque ese termino incluye sum(nu_i*h_i(T_out)).
    Usar dH_rxn(T_out) contaria esa dependencia DOS veces.

Que las dos referencias coincidan (T_ref = 298.15 K en
CalculadoraEntalpia, T_std = 298.15 K en GestorReaccion, que es donde
'thermo' da sus Hf) no es casualidad, pero tampoco se da por hecho: se
comprueba antes de cada balance.

Zona libre de pint: solo floats/np.ndarray en SI.
"""

import numpy as np
from scipy.optimize import brentq, root

_TOL_SINGULAR = 1e-12


class EvaluadorCSTR:
    def __init__(self, nu, gestor_reaccion=None, evaluador_flash=None, dH_rxn=None):
        """
        nu              : vector estequiometrico (negativo=reactivo,
                          positivo=producto), o matriz n_reacciones x
                          n_componentes para varias reacciones.
        gestor_reaccion : GestorReaccion, hace falta para el bloque
                          cinetico (xi a partir de V y T). El balance de
                          materia funciona sin el.
        evaluador_flash : EvaluadorFlash, opcional. Da dos cosas al balance
                          de energia: la calculadora de entalpia compartida
                          y el punto de burbuja, con el que se comprueba
                          que el tanque no este hirviendo (ver
                          _exigir_liquido). Sin el, no hay balance de
                          energia -- el reactor vuelve a ser isotermo con
                          T como dato, que es como estaba antes.
        dH_rxn          : [J/mol] para dar el calor de reaccion a mano
                          cuando no hay GestorReaccion (un reactor sin
                          cinetica sigue teniendo calor de reaccion). Con
                          varias reacciones, uno por reaccion.
        """
        nu = np.asarray(nu, dtype=float)
        if nu.ndim not in (1, 2):
            raise ValueError(
                f"'nu' tiene {nu.ndim} dimensiones. Se espera un vector (una reaccion) "
                "o una matriz n_reacciones x n_componentes (varias)."
            )
        self.una_sola = nu.ndim == 1
        self.nu = nu                            # la forma que dio quien llama
        self.NU = np.atleast_2d(nu)             # la forma con la que se trabaja
        self.n_reacciones = self.NU.shape[0]
        self.nu_tot_de_cada_una = self.NU.sum(axis=1)
        # Se conserva como escalar solo cuando tiene sentido que lo sea.
        self.nu_tot = (float(self.nu_tot_de_cada_una[0]) if self.una_sola
                       else self.nu_tot_de_cada_una)

        self.gestor_reaccion = gestor_reaccion
        self.evaluador_flash = evaluador_flash
        self.entalpia = evaluador_flash.entalpia if evaluador_flash is not None else None

        if dH_rxn is not None:
            dH = np.atleast_1d(np.asarray(dH_rxn, dtype=float))
            if dH.size == 1 and self.n_reacciones > 1:
                raise ValueError(
                    f"Se dio un solo dH_rxn para {self.n_reacciones} reacciones. Cada una "
                    "tiene el suyo: pon una lista, o usa un GestorReaccion que los calcule."
                )
            if dH.size != self.n_reacciones:
                raise ValueError(
                    f"'dH_rxn' trae {dH.size} valores para {self.n_reacciones} reacciones."
                )
            self.dH_rxn_de_cada_una = dH
        elif gestor_reaccion is not None:
            if gestor_reaccion.n_reacciones != self.n_reacciones:
                raise ValueError(
                    f"El reactor tiene {self.n_reacciones} reaccion(es) y el GestorReaccion "
                    f"{gestor_reaccion.n_reacciones}. Tienen que ser las mismas, en el mismo "
                    "orden: si no, la cinetica de una reaccion se aplicaria a otra."
                )
            self.dH_rxn_de_cada_una = np.asarray(
                gestor_reaccion.dH_rxn_de_cada_una, dtype=float)
        else:
            self.dH_rxn_de_cada_una = None

        filas_nulas = [j for j in range(self.n_reacciones)
                       if np.allclose(self.NU[j], 0.0)]
        if filas_nulas:
            raise ValueError(
                f"La(s) reaccion(es) {filas_nulas} tienen el vector estequiometrico todo "
                "a ceros: eso no es una reaccion."
            )

    # ------------------------------------------------------------------
    @property
    def dH_rxn(self):
        """
        El calor de reaccion, escalar, SOLO con una reaccion.

        Con varias lanza error en vez de devolver el de la primera, por la
        misma razon que en GestorReaccion: `xi*dH_rxn` es correcto con una
        reaccion y silenciosamente FALSO con tres, y seguiria corriendo.
        """
        if self.dH_rxn_de_cada_una is None:
            return None
        if not self.una_sola:
            raise ValueError(
                f"'dH_rxn' es un escalar y este reactor tiene {self.n_reacciones} "
                "reacciones. Usa 'dH_rxn_de_cada_una', o 'calor_de_reaccion(xi)', que ya "
                "suma la contribucion de todas."
            )
        return float(self.dH_rxn_de_cada_una[0])

    def _vector_xi(self, xi):
        """
        Un avance por reaccion, sea lo que sea lo que llegue.

        Acepta un escalar cuando hay una sola reaccion -- es lo que
        escribe todo el codigo que ya existia -- y exige la lista
        completa cuando hay varias. Un escalar con tres reacciones no se
        interpreta como "la primera": no hay forma de saber cual.
        """
        v = np.atleast_1d(np.asarray(xi, dtype=float))
        if v.size == self.n_reacciones:
            return v
        if v.size == 1 and self.n_reacciones > 1:
            raise ValueError(
                f"Se dio un solo avance para {self.n_reacciones} reacciones. Pon uno por "
                "reaccion, en el mismo orden que las filas de 'nu'."
            )
        raise ValueError(
            f"Se dieron {v.size} avances para {self.n_reacciones} reaccion(es)."
        )

    def _escalar_si_una(self, v):
        """Devuelve un float con una reaccion y el vector con varias."""
        return float(v[0]) if self.una_sola else np.asarray(v, dtype=float)

    # ------------------------------------------------------------------
    def salida_desde_entrada(self, F_in, x_in, xi):
        """
        Adelante: alimento + avance(s) -> salida.

        Con varias reacciones el termino `nu*xi` pasa a ser el producto
        matriz-vector `NU^T xi`, que es la unica diferencia de fondo en
        toda la estequiometria.
        """
        x_in = np.asarray(x_in, dtype=float)
        v = self._vector_xi(xi)
        F_out = F_in + float(self.nu_tot_de_cada_una @ v)
        if F_out <= _TOL_SINGULAR:
            raise ValueError(
                f"El avance xi={np.array2string(v, precision=6)} deja un caudal de salida "
                f"no positivo (F_out={F_out:.6g} mol/s). Ese avance es imposible con este "
                "alimento."
            )
        x_out = (F_in * x_in + self.NU.T @ v) / F_out
        self._exigir_simplex(x_out, "de salida", v)
        return F_out, x_out

    def entrada_desde_salida(self, F_out, x_out, xi):
        """Atras: salida + avance(s) -> alimento. Es la misma ecuacion despejada."""
        x_out = np.asarray(x_out, dtype=float)
        v = self._vector_xi(xi)
        F_in = F_out - float(self.nu_tot_de_cada_una @ v)
        if F_in <= _TOL_SINGULAR:
            raise ValueError(
                f"Con xi={np.array2string(v, precision=6)} el alimento necesario seria "
                f"F_in={F_in:.6g} mol/s, que no es fisico. Revisa el avance o la corriente "
                "de salida."
            )
        x_in = (F_out * x_out - self.NU.T @ v) / F_in
        self._exigir_simplex(x_in, "de alimentacion", v)
        return F_in, x_in

    def avance_desde_fraccion(self, F_in, x_in_j, x_out_j, j):
        """
        Avance a partir de UNA fraccion conocida de la salida. Exacto:
        sustituyendo F_out = F_in + nu_tot*xi en el balance del componente j,

            x_out_j * (F_in + nu_tot*xi) = F_in*x_in_j + nu_j*xi

        queda lineal en xi:

            xi = F_in * (x_in_j - x_out_j) / (x_out_j*nu_tot - nu_j)
        """
        if not self.una_sola:
            raise ValueError(
                f"Una sola fraccion de salida determina UN avance, y este reactor tiene "
                f"{self.n_reacciones} reacciones. Usa 'avances_desde_fracciones', que toma "
                "una fraccion por reaccion y resuelve el sistema lineal."
            )
        denominador = x_out_j * self.nu_tot - self.nu[j]
        if abs(denominador) < _TOL_SINGULAR:
            raise ValueError(
                f"La fraccion de salida del componente {j} no determina el avance "
                f"(el denominador x_out*nu_tot - nu_{j} se anula). Da la de otro componente."
            )
        return F_in * (x_in_j - x_out_j) / denominador

    def avances_desde_fracciones(self, F_in, x_in, fracciones_salida):
        """
        Los R avances a partir de R fracciones de salida conocidas.

        fracciones_salida : {indice_componente: fraccion_de_salida}

        Sigue siendo EXACTO, sin iterar, porque el balance del componente
        j es lineal en los avances tambien con varias reacciones:

            x_out_j * (F_in + sum_r nu_tot_r xi_r) = F_in x_in_j + sum_r nu_rj xi_r

        reordenando,

            sum_r (x_out_j nu_tot_r - nu_rj) xi_r = F_in (x_in_j - x_out_j)

        que es A xi = b con A de RxR. Hacen falta exactamente R fracciones:
        con menos el sistema esta abierto y con mas esta sobredeterminado,
        y en los dos casos se dice en vez de elegir por cuenta propia.
        """
        x_in = np.asarray(x_in, dtype=float)
        indices = list(fracciones_salida.keys())
        R = self.n_reacciones
        if len(indices) != R:
            raise ValueError(
                f"Se dieron {len(indices)} fraccion(es) de salida para {R} reaccion(es). "
                "Hacen falta exactamente tantas como reacciones: cada una aporta una "
                "ecuacion y cada reaccion una incognita."
            )

        A = np.empty((R, R))
        b = np.empty(R)
        for k, j in enumerate(indices):
            x_out_j = float(fracciones_salida[j])
            A[k, :] = x_out_j * self.nu_tot_de_cada_una - self.NU[:, j]
            b[k] = F_in * (x_in[j] - x_out_j)

        # Una matriz casi singular significa que esas fracciones no
        # distinguen entre las reacciones -- el caso tipico es elegir
        # componentes que participan igual en todas. Decirlo es mas util
        # que devolver un avance con ruido amplificado.
        if abs(np.linalg.det(A)) < _TOL_SINGULAR:
            raise ValueError(
                f"Las fracciones de los componentes {indices} no determinan los avances: "
                "el sistema sale singular. Elige componentes que participen de forma "
                "distinta en cada reaccion (por ejemplo, uno exclusivo de cada una)."
            )
        v = np.linalg.solve(A, b)
        return self._escalar_si_una(v)

    def avance_desde_cinetica(self, V, T, x_out):
        """
        En un CSTR el contenido del tanque esta perfectamente mezclado, o
        sea que su composicion es la de SALIDA -- por eso r se evalua en
        x_out y no en el alimento. Esa es justamente la diferencia con un
        reactor de flujo piston.
        """
        if self.gestor_reaccion is None:
            raise ValueError("Para usar la cinetica hace falta un GestorReaccion.")
        r = self.gestor_reaccion.velocidades(T, np.asarray(x_out, dtype=float))
        return self._escalar_si_una(V * r)

    def volumen_desde_avance(self, xi, T, x_out, indice=None, tolerancia=1e-6):
        """
        La inversa de la anterior: que tanque hace falta para ese avance.

        Con varias reacciones esto deja de ser una inversion y pasa a ser
        una COMPROBACION, y conviene entender por que. Un solo volumen
        tiene que cumplir xi_j = V r_j para TODAS las reacciones a la vez,
        asi que las R ecuaciones comparten una unica incognita: un juego
        cualquiera de avances simplemente no es alcanzable en un CSTR.

        Lo unico honesto es calcular V a partir de una reaccion (`indice`)
        y comprobar que las demas cuadran. Si no cuadran, se dice cuanto
        se desvian en vez de devolver un volumen que no produce esos
        avances.
        """
        if self.gestor_reaccion is None:
            raise ValueError("Para usar la cinetica hace falta un GestorReaccion.")
        v = self._vector_xi(xi)
        r = self.gestor_reaccion.velocidades(T, np.asarray(x_out, dtype=float))

        if indice is None:
            if not self.una_sola:
                raise ValueError(
                    f"Con {self.n_reacciones} reacciones hay que decir con cual se fija el "
                    "volumen ('indice'): un solo V tiene que satisfacer las "
                    f"{self.n_reacciones} ecuaciones cineticas a la vez, asi que no "
                    "cualquier juego de avances es alcanzable."
                )
            indice = 0
        indice = int(indice)

        if abs(r[indice]) < _TOL_SINGULAR:
            raise ValueError(
                f"La velocidad de la reaccion {indice} a T={T:.4g} K en la composicion de "
                "salida es practicamente cero (ahi ya esta en equilibrio quimico): "
                "ningun volumen finito da ese avance."
            )
        V = float(v[indice] / r[indice])

        if not self.una_sola:
            esperados = V * r
            escala = max(float(np.max(np.abs(v))), _TOL_SINGULAR)
            desviacion = np.abs(esperados - v) / escala
            peor = int(np.argmax(desviacion))
            if desviacion[peor] > tolerancia:
                raise ValueError(
                    f"Con V={V:.6g} m3 (fijado por la reaccion {indice}) la reaccion {peor} "
                    f"daria un avance de {esperados[peor]:.6g} mol/s y se pidio "
                    f"{v[peor]:.6g} mol/s ({100*desviacion[peor]:.2f} % de diferencia). "
                    "Ese juego de avances no es alcanzable en un solo CSTR a esa "
                    "temperatura y composicion."
                )
        return V

    # ------------------------------------------------------------------
    def avance_de_equilibrio(self, F_in, x_in, T, tolerancia=1e-12):
        """
        Avance al que la reaccion se DETIENE por equilibrio quimico, sin
        cinetica ninguna:

            prod_i a_i(x_out(xi))^nu_i  =  K_eq(T),     a_i = x_i * gamma_i

        Es el reactor "de equilibrio" clasico, y responde a una pregunta
        distinta a la del CSTR cinetico. El cinetico dice "con este tanque
        y esta velocidad, llego hasta aqui"; este dice "por mucho tanque
        que pongas, NO pasas de aqui". Son el limite practico y el limite
        termodinamico, y conviene poder ver los dos.

        Barato de anadir porque las dos piezas ya existian: K_eq(T) de
        van't Hoff en GestorReaccion y gamma de UNIFAC en el proveedor.

        BRACKET. El avance no se busca en (0, xi_max) sino entre los dos
        limites estequiometricos REALES:

          - hacia adelante, hasta que se agote un reactivo,
          - hacia atras (xi < 0), hasta que se agote un producto.

        Permitir xi negativo no es un capricho: si la alimentacion ya trae
        producto por encima del equilibrio, la reaccion corre al REVES, y
        un bracket que empiece en cero no encontraria esa raiz -- devolveria
        "no hay equilibrio" sobre un caso perfectamente normal (p.ej. un
        reciclo que devuelve producto al reactor).

        En los extremos el residuo diverge con signos opuestos (en uno se
        anula un reactivo y el productorio se va a infinito; en el otro se
        anula un producto y se va a cero), asi que la raiz esta encerrada
        por construccion.
        """
        if self.gestor_reaccion is None:
            raise ValueError(
                "El reactor de equilibrio necesita la reaccion (GestorReaccion): "
                "sin K_eq(T) no hay equilibrio que calcular."
            )
        if not self.una_sola:
            return self._equilibrio_varias(F_in, x_in, T, tolerancia)
        x_in = np.asarray(x_in, dtype=float)
        K = float(self.gestor_reaccion.K_eq(T))
        proveedor = self.gestor_reaccion.proveedor

        # Limites estequiometricos: cuanto se puede avanzar antes de
        # agotar algo, en cada sentido.
        hacia_adelante = [F_in * x_in[i] / abs(self.nu[i])
                          for i in np.where(self.nu < 0)[0]]
        hacia_atras = [F_in * x_in[i] / abs(self.nu[i])
                       for i in np.where(self.nu > 0)[0]]
        if not hacia_adelante or not hacia_atras:
            raise ValueError(
                "La reaccion necesita al menos un reactivo y un producto con "
                "coeficiente no nulo para tener equilibrio."
            )
        xi_max = min(hacia_adelante)
        xi_min = -min(hacia_atras)

        def residuo(xi):
            F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)
            gamma = proveedor.coeficientes_actividad(T, x_out)
            actividad = np.clip(x_out * gamma, 1e-300, None)
            # En logaritmos: el productorio de actividades elevadas a nu
            # recorre varios ordenes de magnitud y multiplicarlo
            # directamente pierde precision (o desborda) cerca de los
            # extremos, que es justo donde hay que evaluarlo.
            return float(np.dot(self.nu, np.log(actividad)) - np.log(K))

        # Se entra un pelin por dentro: en los extremos exactos hay una
        # fraccion molar nula y el logaritmo no esta definido.
        margen = 1e-9 * max(xi_max - xi_min, 1.0)
        a, b = xi_min + margen, xi_max - margen
        try:
            r_a, r_b = residuo(a), residuo(b)
        except Exception as e:
            raise ValueError(
                f"No se pudo evaluar el equilibrio en los extremos del avance "
                f"[{a:.6g}, {b:.6g}] mol/s: {e}"
            ) from e

        if np.sign(r_a) == np.sign(r_b):
            raise ValueError(
                f"No hay avance de equilibrio dentro del rango estequiometrico "
                f"[{xi_min:.6g}, {xi_max:.6g}] mol/s a T={T:.2f} K "
                f"(K_eq={K:.6g}). Con estos reactivos la reaccion se iria "
                "entera hacia un lado: la composicion de equilibrio cae fuera "
                "de lo que la alimentacion permite."
            )

        xi = float(brentq(residuo, a, b, xtol=tolerancia, rtol=1e-14))
        F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)
        gamma = proveedor.coeficientes_actividad(T, x_out)
        producto = float(np.prod((x_out * gamma) ** self.nu))
        return {
            "xi": xi, "F_out": float(F_out), "x_out": x_out, "T": float(T),
            "K_eq": K, "producto_actividades": producto,
            "residual": abs(producto - K) / max(K, 1e-300),
        }

    # ------------------------------------------------------------------
    def _capacidades(self, F_in, x_in):
        """
        Cuanto puede avanzar CADA reaccion por si sola antes de agotar
        alguno de sus reactivos. Es la escala natural de los avances y se
        usa tanto para los arranques del solver como para acotar.

        No es una cota conjunta: si dos reacciones comparten reactivo, la
        suma de sus capacidades individuales es inalcanzable. Lo que
        garantiza que no se cruce el limite de verdad es
        `_exigir_simplex`, que mira la composicion resultante.
        """
        x_in = np.asarray(x_in, dtype=float)
        caps = np.empty(self.n_reacciones)
        for j in range(self.n_reacciones):
            reactivos = np.where(self.NU[j] < 0)[0]
            if len(reactivos) == 0:
                caps[j] = np.inf
                continue
            caps[j] = min(F_in * x_in[i] / abs(self.NU[j, i]) for i in reactivos)
        return caps

    def _equilibrio_varias(self, F_in, x_in, T, tolerancia=1e-12):
        """
        Equilibrio quimico simultaneo de R reacciones:

            sum_i nu_ji * ln a_i(x_out(xi))  =  ln K_j(T)     para cada j

        Por que cambia el metodo y no solo la dimension. Con una reaccion
        el avance se encierra entre dos limites estequiometricos y `brentq`
        no puede escaparse. En R dimensiones **no existe el bracket**: la
        region factible es un politopo y no hay cambio de signo que
        encerrar. Asi que se resuelve con `root` y se protege de otra
        forma:

          - los residuos van en LOGARITMOS, igual que en el caso de una
            reaccion, porque las productorias de actividades recorren
            varios ordenes de magnitud;
          - un avance que saque la composicion del simplex devuelve un
            residuo grande en vez de reventar a mitad del root-finding;
          - se prueban VARIOS arranques, porque un sistema de equilibrios
            acoplados puede tener mas de una raiz matematica y solo
            algunas son fisicas;
          - y no se confia en `sol.success`: se exige que el residuo sea
            pequeno de verdad, que es el criterio del resto del proyecto.
        """
        x_in = np.asarray(x_in, dtype=float)
        proveedor = self.gestor_reaccion.proveedor
        lnK = np.log(self.gestor_reaccion.K_eq_de_cada_una(T))
        caps = self._capacidades(F_in, x_in)
        if not np.all(np.isfinite(caps)):
            raise ValueError(
                "Alguna reaccion no tiene reactivos (ningun nu negativo): su equilibrio "
                "no esta acotado y el avance se iria al infinito."
            )

        def residuos(v):
            try:
                _F_out, x_out = self.salida_desde_entrada(F_in, x_in, v)
            except ValueError:
                return np.full(self.n_reacciones, 1e6)
            try:
                gamma = proveedor.coeficientes_actividad(T, x_out)
            except Exception:
                return np.full(self.n_reacciones, 1e6)
            actividad = np.clip(x_out * gamma, 1e-300, None)
            return self.NU @ np.log(actividad) - lnK

        arranques = []
        for fraccion in (0.05, 0.25, 0.5, 0.75):
            arranques.append(fraccion * caps)
        # Y uno con avance negativo: si la alimentacion ya trae producto
        # por encima del equilibrio, alguna reaccion corre al REVES. Es el
        # caso de un reciclo que devuelve producto, y arrancar solo desde
        # avances positivos lo dejaria sin encontrar.
        arranques.append(-0.1 * caps)

        soluciones = []
        for v0 in arranques:
            try:
                sol = root(residuos, v0, method="hybr")
            except Exception:
                continue
            v = np.asarray(sol.x, dtype=float)
            try:
                res = float(np.max(np.abs(residuos(v))))
                F_out, x_out = self.salida_desde_entrada(F_in, x_in, v)
            except Exception:
                continue
            if not np.isfinite(res) or res > 1e-8:
                continue
            if any(np.allclose(v, otra[0], rtol=0, atol=1e-7) for otra in soluciones):
                continue
            soluciones.append((v, float(F_out), x_out, res))

        if not soluciones:
            raise ValueError(
                f"El equilibrio simultaneo de las {self.n_reacciones} reacciones no "
                f"convergio desde ninguno de los {len(arranques)} arranques probados a "
                f"T={T:.2f} K. Puede que la composicion de equilibrio caiga fuera de lo que "
                "la alimentacion permite (como pasa con una sola reaccion cuando se iria "
                "entera hacia un lado), o que las reacciones sean incompatibles entre si "
                "con este alimento."
            )

        # Si hay mas de una raiz fisica no se elige en silencio: se
        # devuelve la de menor avance total -- la mas cercana al alimento,
        # que es la que un arranque en frio alcanza -- y se reportan todas.
        soluciones.sort(key=lambda t: float(np.sum(np.abs(t[0]))))
        v, F_out, x_out, res = soluciones[0]

        gamma = proveedor.coeficientes_actividad(T, x_out)
        actividad = x_out * gamma
        producto = np.exp(self.NU @ np.log(np.clip(actividad, 1e-300, None)))
        K = self.gestor_reaccion.K_eq_de_cada_una(T)
        return {
            "xi": v, "F_out": float(F_out), "x_out": x_out, "T": float(T),
            "K_eq": K, "producto_actividades": producto,
            "residual": float(np.max(np.abs(producto - K) / np.maximum(K, 1e-300))),
            "soluciones": [{"xi": t[0]} for t in soluciones],
            "multiplicidad": len(soluciones) > 1,
        }

    # ------------------------------------------------------------------
    # Balance de energia
    # ------------------------------------------------------------------
    def _exigir_energia(self):
        """
        Comprueba lo que hace falta para un balance de energia, incluido
        que las DOS referencias coincidan.

        Esa ultima comprobacion es la que evita el error silencioso: si
        alguien construyera la calculadora de entalpia con otra T_ref, el
        termino xi*dH_rxn quedaria referido a una temperatura distinta de
        la del resto del balance. El resultado seguiria siendo un numero
        plausible, con el error repartido entre Q y T, y nadie lo notaria.
        """
        if self.entalpia is None:
            raise ValueError(
                "Este reactor no tiene balance de energia: se construyo sin "
                "EvaluadorFlash, asi que no hay ni entalpias ni punto de burbuja. "
                "Pasa evaluador_flash=... para activarlo."
            )
        # Se mira la version en PLURAL a proposito: la propiedad en
        # singular lanza error con varias reacciones, y aqui lo unico que
        # se quiere saber es si hay calor de reaccion o no.
        if self.dH_rxn_de_cada_una is None:
            raise ValueError(
                "No hay calor de reaccion disponible: el reactor se construyo sin "
                "GestorReaccion y sin dH_rxn explicito. Sin el, el balance de energia "
                "no puede distinguir una reaccion exotermica de una endotermica."
            )
        T_ref_reaccion = getattr(self.gestor_reaccion, "T_std", None)
        if T_ref_reaccion is not None and abs(T_ref_reaccion - self.entalpia.T_ref) > 1e-9:
            raise ValueError(
                f"Las dos referencias no coinciden: la entalpia esta referida a "
                f"{self.entalpia.T_ref} K y el calor de reaccion a {T_ref_reaccion} K. "
                "El termino xi*dH_rxn solo es exacto evaluado en la MISMA T_ref que h "
                "(ver la cabecera de este modulo)."
            )

    def _exigir_liquido(self, T, x, P, exigir_liquido):
        """
        Un CSTR de este simulador es un tanque LIQUIDO: la cinetica usa
        actividades a_i = x_i*gamma_i, que son de fase liquida, y la
        entalpia del balance es h_liquido. Si la T que sale del balance
        esta por encima del punto de burbuja a la P de operacion, el
        tanque estaria hirviendo y el modelo deja de describirlo.

        Es exactamente el patron de fallo que persigue este proyecto: un
        numero plausible sobre algo fisicamente imposible. Por eso se
        comprueba en vez de confiar.
        """
        if P is None or self.evaluador_flash is None:
            return None
        T_burbuja, _ = self.evaluador_flash.calculadora_elv.burbuja_T(P, np.asarray(x, dtype=float))
        if T <= T_burbuja:
            return T_burbuja
        mensaje = (
            f"El balance da T={T:.2f} K, por encima del punto de burbuja de la mezcla de "
            f"salida a {P:.4g} Pa (T_burbuja={T_burbuja:.2f} K): el tanque estaria "
            "hirviendo. Este CSTR se modela como monofasico liquido (la cinetica usa "
            "actividades de fase liquida), asi que ese resultado no es de fiar. Sube la "
            "presion, quita calor, o usa exigir_liquido=False si de verdad quieres el "
            "numero sabiendo lo que significa."
        )
        if exigir_liquido:
            raise ValueError(mensaje)
        return T_burbuja

    def calor_de_reaccion(self, xi):
        """
        Calor liberado/absorbido por la reaccion [W], con el signo de la
        convencion termodinamica: dH_rxn < 0 es exotermica, asi que
        xi*dH_rxn < 0 significa energia que la reaccion SUELTA al tanque.
        """
        if self.dH_rxn_de_cada_una is None:
            raise ValueError("No hay calor de reaccion disponible (ni GestorReaccion ni dH_rxn).")
        # Una SUMA con signo, no un maximo ni un promedio: una exotermica y
        # una endotermica se compensan de verdad, y ese es justo el caso
        # que un reactor con varias reacciones permite plantear.
        return float(np.dot(self._vector_xi(xi), self.dH_rxn_de_cada_una))

    def calor_necesario(self, F_in, x_in, T_in, xi, T_salida, P=None, exigir_liquido=True):
        """
        Modo ISOTERMO (o de T impuesta): se sabe a que temperatura se
        quiere operar y se calcula el calor que cuesta mantenerla.

            Q = F_out*h(T_out, x_out) + xi*dH_rxn - F_in*h(T_in, x_in)

        Q < 0 significa que hay que REFRIAR. Es el caso normal de una
        exotermica, y es un numero que antes el simulador no daba: un
        reactor isotermo sin este balance oculta cuanta refrigeracion
        hace falta, que suele ser la restriccion de diseno de verdad.
        """
        self._exigir_energia()
        x_in = np.asarray(x_in, dtype=float)
        F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)
        T_burbuja = self._exigir_liquido(T_salida, x_out, P, exigir_liquido)

        h_in = self.entalpia.h_liquido(T_in, x_in)
        h_out = self.entalpia.h_liquido(T_salida, x_out)
        Q_reaccion = self.calor_de_reaccion(xi)
        Q = F_out * h_out + Q_reaccion - F_in * h_in

        return {
            "Q": float(Q), "Q_por_mol": float(Q / F_in),
            "Q_reaccion": float(Q_reaccion),
            "T_salida": float(T_salida), "T_entrada": float(T_in),
            "F_out": float(F_out), "x_out": x_out,
            "xi": self._escalar_si_una(self._vector_xi(xi)),
            "h_in": float(h_in), "h_out": float(h_out),
            "T_burbuja_salida": T_burbuja,
        }

    def temperatura_desde_calor(self, F_in, x_in, T_in, xi, Q=0.0, P=None,
                                exigir_liquido=True):
        """
        Modo ADIABATICO (Q = 0) o de calor impuesto: se sabe cuanta
        energia entra o sale y se calcula la temperatura que resulta.

        Es la misma ecuacion despejada:

            h(T_out, x_out) = [F_in*h(T_in, x_in) + Q - xi*dH_rxn] / F_out

        y de ahi T_out por inversion exacta (h es estrictamente creciente
        en T, ver thermodynamics/entalpia.py).
        """
        self._exigir_energia()
        x_in = np.asarray(x_in, dtype=float)
        F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)

        h_in = self.entalpia.h_liquido(T_in, x_in)
        Q_reaccion = self.calor_de_reaccion(xi)
        h_out = (F_in * h_in + float(Q) - Q_reaccion) / F_out
        T_salida = self.entalpia.T_desde_h_liquido(h_out, x_out)
        T_burbuja = self._exigir_liquido(T_salida, x_out, P, exigir_liquido)

        return {
            "Q": float(Q), "Q_por_mol": float(Q) / F_in,
            "Q_reaccion": float(Q_reaccion),
            "T_salida": float(T_salida), "T_entrada": float(T_in),
            "F_out": float(F_out), "x_out": x_out,
            "xi": self._escalar_si_una(self._vector_xi(xi)),
            "h_in": float(h_in), "h_out": float(h_out),
            "T_burbuja_salida": T_burbuja,
        }

    # ------------------------------------------------------------------
    def resolver_con_cinetica(self, F_in, x_in, T_in, V, Q=0.0, P=None,
                              exigir_liquido=True, xi_inicial=None, T_inicial=None):
        """
        El caso ACOPLADO, y el unico que de verdad necesita resolverse
        como sistema: reactor adiabatico (o con calor dado) del que se
        conoce el VOLUMEN.

        Por que no lo puede hacer el motor de punto fijo del orquestador:
        la cinetica necesita T para dar xi, y el balance de energia
        necesita xi para dar T. Ninguno de los dos puede arrancar. No es
        que falten datos -- es un lazo, igual que un reciclo, y se
        resuelve igual: planteando las dos ecuaciones a la vez.

            R1(xi, T) = xi - V*r(T, x_out(xi))
            R2(xi, T) = F_in*h(T_in,x_in) + Q - F_out(xi)*h(T,x_out(xi)) - xi*dH_rxn

        Los dos residuos se ADIMENSIONALIZAN antes de entregarlos al
        solver, R1 con el caudal de entrada y R2 con F_in*|dH_rxn|. Sin
        eso quedan en unidades distintas (mol/s frente a W) y con ordenes
        de magnitud separados por ~10^6: hybr reparte su esfuerzo segun
        la norma del vector, asi que el de materia se vuelve invisible
        frente al de energia, y un criterio de parada unico no significa
        lo mismo para los dos. Con ambos adimensionales, "residuo < 1e-9"
        quiere decir lo mismo en las dos ecuaciones: error relativo.

        Aqui vive el acoplamiento que hace interesante a la destilacion
        reactiva: con una exotermica, mas avance sube T, y mas T sube la
        velocidad -- realimentacion positiva. El solver la resuelve; que
        la solucion sea ESTABLE en la planta real es otra pregunta, y
        este modelo estacionario no la responde (ver docs).
        """
        self._exigir_energia()
        if self.gestor_reaccion is None:
            raise ValueError("Para el caso acoplado hace falta la cinetica (GestorReaccion).")
        x_in = np.asarray(x_in, dtype=float)
        # Se evalua UNA vez: no depende de las incognitas, y esta dentro
        # del residuo se pagaria en cada paso del root-finding.
        h_in_fijo = self.entalpia.h_liquido(T_in, x_in)
        R = self.n_reacciones
        # La escala de energia usa el calor de reaccion MAS GRANDE en valor
        # absoluto, no el de la primera: con varias reacciones, escalar por
        # una que apenas libera calor dejaria el residuo energetico
        # artificialmente enorme.
        escala_energia = F_in * max(float(np.max(np.abs(self.dH_rxn_de_cada_una))), 1.0)
        n_grande = np.full(R + 1, 1e6)

        def residuos(v):
            xi = np.asarray(v[:R], dtype=float)
            T = float(v[R])
            try:
                F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)
            except ValueError:
                # Avance fuera del simplex: se devuelve un residuo grande
                # en vez de dejar que reviente a mitad del root-finding.
                return n_grande
            try:
                r = self.gestor_reaccion.velocidades(T, x_out)
                h_out = self.entalpia.h_liquido(T, x_out)
            except Exception:
                return n_grande
            # R ecuaciones cineticas, una por reaccion, todas con el MISMO
            # volumen -- que es lo que las acopla entre si, ademas de
            # acoplarlas con la energia.
            R_cinetica = (xi - V * r) / F_in
            R_energia = (F_in * h_in_fijo + float(Q) - F_out * h_out
                         - float(np.dot(xi, self.dH_rxn_de_cada_una))) / escala_energia
            return np.concatenate([R_cinetica, [R_energia]])

        # ARRANQUES MULTIPLES, y no por comodidad. Un arranque unico y
        # timido (1 % del limite estequiometrico, T = T_in) parece la
        # opcion prudente y resulta ser la mala: con una exotermica
        # fuerte el estacionario esta lejos, hybr no lo alcanza y el
        # metodo reportaba "no convergio" cuando SI habia solucion.
        # Medido con A=1e10 y V=2 m3: desde el arranque timido fallaba, y
        # desde 10 de 15 arranques distintos convergia siempre al mismo
        # xi=9.4699 mol/s, T=372.66 K.
        #
        # Los puntos de partida no son arbitrarios: para cada avance de
        # prueba se calcula la T que le corresponde POR BALANCE DE
        # ENERGIA, o sea que cada arranque ya satisface R2 y al solver
        # solo le queda arreglar la cinetica. Barrer el avance es barrer
        # una curva, no un plano.
        capacidades = self._capacidades(F_in, x_in)
        capacidad = float(np.min(capacidades))     # para los mensajes

        if xi_inicial is not None or T_inicial is not None:
            # Arranque impuesto: se respeta tal cual y no se barre nada,
            # que es lo que permite pedir una rama concreta a proposito.
            xi0 = (self._vector_xi(xi_inicial) if xi_inicial is not None
                   else 0.01 * capacidades)
            arranques = [(xi0, float(T_inicial if T_inicial is not None else T_in))]
        else:
            arranques = []
            for fraccion in (0.01, 0.1, 0.3, 0.6, 0.9):
                xi0 = fraccion * capacidades
                try:
                    T0 = self.temperatura_desde_calor(
                        F_in, x_in, T_in, xi0, Q=Q, P=None, exigir_liquido=False
                    )["T_salida"]
                except Exception:
                    T0 = T_in
                arranques.append((xi0, T0))

        soluciones = []
        for xi0, T0 in arranques:
            try:
                solucion = root(residuos, np.concatenate([np.atleast_1d(xi0), [T0]]),
                                method="hybr")
            except Exception:
                continue
            xi_c = np.asarray(solucion.x[:R], dtype=float)
            T_c = float(solucion.x[R])
            try:
                residual_c = float(np.max(np.abs(residuos(solucion.x))))
            except Exception:
                continue
            # No se confia en sol.success: MINPACK puede reportar exito
            # con residuo grande y fracaso con el residuo ya en cero.
            # Es el mismo criterio que el balance de materia global.
            if not np.isfinite(residual_c) or residual_c > 1e-9:
                continue
            # Rango estequiometrico, reaccion por reaccion. La cota
            # superior es la capacidad INDIVIDUAL de cada una; que la suma
            # sea alcanzable ya lo garantiza _exigir_simplex dentro de
            # salida_desde_entrada.
            if np.any(xi_c < -1e-9) or np.any(xi_c > capacidades + 1e-9):
                continue
            if not any(np.allclose(xi_c, s[0], rtol=0, atol=1e-6) and abs(T_c - s[1]) < 1e-6
                       for s in soluciones):
                soluciones.append((xi_c, T_c, residual_c))

        if not soluciones:
            raise RuntimeError(
                f"El reactor acoplado (cinetica + energia) no convergio desde ninguno de "
                f"los {len(arranques)} arranques probados (avances entre "
                f"{arranques[0][0]:.4g} y {arranques[-1][0]:.4g} mol/s). Con una exotermica "
                "fuerte el lazo T->r->xi->T puede no tener estado estacionario en el rango "
                "liquido; prueba un volumen menor, retirar calor (Q<0), o forzar un arranque "
                "concreto con xi_inicial/T_inicial."
            )

        # MULTIPLICIDAD: un CSTR exotermico puede tener mas de un estado
        # estacionario (el fenomeno clasico de ignicion/extincion). Si
        # aparece, no se elige en silencio: se devuelve el mas FRIO -- el
        # que alcanza un arranque en frio, que es lo que fisicamente pasa
        # al poner en marcha el equipo -- y se reportan todos en
        # 'soluciones' para que quien mire sepa que hay mas.
        soluciones.sort(key=lambda s: s[1])
        xi, T, residual = soluciones[0]
        xi = self._escalar_si_una(xi)

        resultado = self.temperatura_desde_calor(
            F_in, x_in, T_in, xi, Q=Q, P=P, exigir_liquido=exigir_liquido
        )
        resultado["V"] = float(V)
        resultado["residual"] = residual
        resultado["soluciones"] = [
            {"xi": self._escalar_si_una(s_[0]), "T": s_[1]} for s_ in soluciones
        ]
        resultado["multiplicidad"] = len(soluciones) > 1
        # Coherencia: la T del balance y la del sistema acoplado tienen
        # que ser la misma; si no, algo se desincronizo entre las dos vias.
        if abs(resultado["T_salida"] - T) > 1e-6:
            raise RuntimeError(
                f"Incoherencia interna: el sistema acoplado da T={T:.6f} K y el balance "
                f"de energia recalculado da {resultado['T_salida']:.6f} K."
            )
        return resultado

    # ------------------------------------------------------------------
    def conversion(self, F_in, x_in, xi, indice_limitante=None):
        """
        Conversion del reactivo limitante: cuanto de el desaparece.
        Si no se dice cual, se toma el reactivo (nu<0) que se agote antes,
        que es la definicion habitual.
        """
        x_in = np.asarray(x_in, dtype=float)
        v = self._vector_xi(xi)
        # Un reactivo es el que tiene coeficiente negativo en ALGUNA
        # reaccion. Con varias puede ser reactivo en una y producto en
        # otra; lo que decide su consumo neto es la suma.
        consumo_unitario = -self.NU.sum(axis=0)       # por unidad de avance de cada una
        reactivos = np.where(np.any(self.NU < 0, axis=0))[0]
        if len(reactivos) == 0:
            raise ValueError("No hay ningun reactivo (ningun nu negativo): la conversion no esta definida.")
        if indice_limitante is None:
            # El limitante es el de menor moles disponibles por unidad de
            # avance TOTAL sobre las reacciones que lo consumen.
            def por_unidad(i):
                consumo = -float(np.sum(np.minimum(self.NU[:, i], 0.0)))
                return F_in * x_in[i] / consumo if consumo > 0 else np.inf
            capacidad = [por_unidad(i) for i in reactivos]
            indice_limitante = int(reactivos[int(np.argmin(capacidad))])

        entrada = F_in * x_in[indice_limitante]
        if entrada <= _TOL_SINGULAR:
            raise ValueError(
                f"El componente {indice_limitante} no entra al reactor "
                "(su caudal de alimentacion es cero): su conversion no esta definida."
            )
        # Consumo NETO: sum_j (-nu_j,limitante) * xi_j. Con una reaccion es
        # exactamente |nu_i|*xi, o sea que el caso validado no se mueve.
        consumido = float(-np.dot(self.NU[:, indice_limitante], v))
        return consumido / entrada, indice_limitante

    # ------------------------------------------------------------------
    def _exigir_simplex(self, x, cual, xi, tolerancia=1e-8):
        if np.any(x < -tolerancia):
            negativos = [i for i, v in enumerate(x) if v < -tolerancia]
            avance = (f"{float(np.atleast_1d(xi)[0]):.6g}" if self.una_sola
                      else np.array2string(np.atleast_1d(xi), precision=6))
            # Con varias reacciones el aviso cambia de sentido, y conviene
            # decirlo: puede que ningun avance sea excesivo por si solo y
            # que el problema sea la SUMA, porque dos reacciones compiten
            # por el mismo reactivo.
            pista = ("" if self.una_sola else
                     " Con varias reacciones puede que ninguna se pase por si sola y que "
                     "el problema sea la suma: comprueba si compiten por ese componente.")
            raise ValueError(
                f"Con un avance xi={avance} la composicion {cual} sale negativa en "
                f"el componente {negativos[0]} (x={x[negativos[0]]:.4g}). "
                "Fisicamente no se puede consumir mas de lo que hay: baja el avance."
                + pista
            )
