"""
Termodinamica y cinetica de la reaccion, vectorizada con numpy.

GestorReaccion encapsula: (A) las propiedades estandar de reaccion
(precalculadas una vez, producto punto nu*Hf y nu*Gf), (B) la constante
de equilibrio K_eq(T) via van't Hoff, y (C) la velocidad neta de
reaccion r(T, x) via Arrhenius + actividades (x*gamma). No usa bucles
for para la matematica: las productorias estequiometricas se resuelven
con mascaras booleanas sobre nu y np.prod/np.power.

VARIAS REACCIONES A LA VEZ
--------------------------
`nu` admite dos formas, y la diferencia no es cosmetica:

  - **vector** de longitud n_componentes: UNA reaccion. Es el caso con el
    que estan tomados todos los numeros validados del proyecto, y se
    comporta exactamente igual que antes.
  - **matriz** (n_reacciones x n_componentes): VARIAS. Cada fila es una
    reaccion con su propio nu, su A y su Ea.

Internamente siempre se trabaja con la matriz (`self.NU`), asi que no hay
dos caminos de codigo que puedan divergir. Lo que cambia es la FORMA de
lo que se devuelve.

Y aqui esta la decision de diseno que importa. Los nombres en singular
--`dH_rxn`, `K_eq()`, `velocidad_reaccion()`-- devuelven un escalar
cuando hay una sola reaccion y **LANZAN UN ERROR** cuando hay varias, en
vez de devolver la primera o la suma. El motivo: un balance de energia
escrito como `xi * dH_rxn` es correcto con una reaccion y silenciosamente
FALSO con tres. Si `dH_rxn` devolviera el de la primera reaccion, ese
balance seguiria corriendo y dando un numero plausible construido sobre
algo imposible, que es el fallo mas caro de este proyecto. Que reviente
obliga a usar las versiones en plural, que son las correctas:

    dH_rxn_de_cada_una    [J/mol] por reaccion
    K_eq_de_cada_una(T)   adimensional, por reaccion
    velocidades(T, x)     por reaccion

Lo que NO se generaliza, a proposito: la transformacion de
Barbosa-Doherty (`core/transformaciones.py`) y las curvas residuales
reactivas siguen siendo de una sola reaccion. Su extension a varias no es
"el mismo codigo con un indice mas": es otra construccion, con un
conjunto de componentes de referencia en vez de uno. Se avisa con un
error claro en vez de dejar que se use fuera de su rango.
"""

import numpy as np

R_UNIVERSAL = 8.31446   # J/(mol*K)
T_STD = 298.15          # K


class GestorReaccion:
    def __init__(self, proveedor, nu, A, Ea, T_std=T_STD, R=R_UNIVERSAL):
        """
        proveedor : ProveedorTermodinamico ya construido con los mismos
                    componentes (mismo orden) que 'nu'.
        nu        : vector estequiometrico (negativo=reactivo,
                    positivo=producto), o matriz (n_reacciones x
                    n_componentes) para varias reacciones a la vez.
        A, Ea     : parametros de Arrhenius (A en las mismas unidades que
                    r; Ea en J/mol). Escalares con una reaccion; con
                    varias, uno por reaccion -- o un escalar, que se
                    entiende como "el mismo para todas".
        """
        self.proveedor = proveedor
        nu = np.asarray(nu, dtype=float)

        if nu.ndim not in (1, 2):
            raise ValueError(
                f"'nu' tiene {nu.ndim} dimensiones. Se espera un vector (una reaccion) "
                "o una matriz n_reacciones x n_componentes (varias)."
            )
        self.una_sola = nu.ndim == 1
        self.nu = nu                              # la forma que dio quien llama
        self.NU = np.atleast_2d(nu)               # la forma con la que se trabaja
        self.n_reacciones, n_comp = self.NU.shape

        n_esperado = len(getattr(proveedor, "componentes", []) or [])
        if n_esperado and n_comp != n_esperado:
            raise ValueError(
                f"'nu' tiene {n_comp} coeficientes por reaccion pero el proveedor se "
                f"construyo con {n_esperado} componentes. Tienen que coincidir en numero "
                "Y en orden: el coeficiente i es el del componente i."
            )

        # Una fila entera a cero no es "una reaccion que no avanza", es un
        # dato mal puesto: no hay nada que reaccione y la velocidad saldria
        # 0/0 en cuanto se normalizara por el componente de referencia.
        filas_nulas = [j for j in range(self.n_reacciones)
                       if np.allclose(self.NU[j], 0.0)]
        if filas_nulas:
            raise ValueError(
                f"La(s) reaccion(es) {filas_nulas} tienen todos los coeficientes a cero. "
                "Una reaccion sin reactivos ni productos no es una reaccion: quitala."
            )

        self.A = self._por_reaccion(A, "A")
        self.Ea = self._por_reaccion(Ea, "Ea")
        self.T_std = float(T_std)
        self.R = float(R)

        # Mascaras: evitan cualquier bucle for en las productorias. Con
        # varias reacciones son matrices y la productoria va por filas.
        self._exp_reactivos = np.where(self.NU < 0, -self.NU, 0.0)
        self._exp_productos = np.where(self.NU > 0, self.NU, 0.0)

        # A. Propiedades estandar de reaccion (precalculo, producto punto)
        Hf = self.proveedor.entalpias_formacion_liquido()
        Gf = self.proveedor.energias_gibbs_formacion_liquido()

        self.dH_rxn_de_cada_una = self.NU @ np.asarray(Hf, dtype=float)   # J/mol
        self.dG_rxn_de_cada_una = self.NU @ np.asarray(Gf, dtype=float)   # J/mol

        self.K_eq_std_de_cada_una = np.exp(
            -self.dG_rxn_de_cada_una / (self.R * self.T_std)
        )

        self.nu_tot_de_cada_una = self.NU.sum(axis=1)

    # ------------------------------------------------------------------
    def _por_reaccion(self, valor, nombre):
        """
        Un parametro de Arrhenius por reaccion.

        Un escalar se entiende como "el mismo para todas", que es lo
        razonable al tantear; una lista de otro largo es un error de
        datos y se dice, porque emparejar mal A y nu daria una cinetica
        que corre y miente.
        """
        v = np.atleast_1d(np.asarray(valor, dtype=float))
        if v.size == 1:
            return np.full(self.n_reacciones, float(v[0]))
        if v.size != self.n_reacciones:
            raise ValueError(
                f"'{nombre}' trae {v.size} valores para {self.n_reacciones} reacciones. "
                "Pon uno por reaccion, en el mismo orden que las filas de 'nu', o uno solo "
                "para usar el mismo en todas."
            )
        return v.astype(float)

    def _exigir_una_sola(self, nombre, plural):
        if not self.una_sola:
            raise ValueError(
                f"'{nombre}' solo tiene sentido con UNA reaccion, y este gestor tiene "
                f"{self.n_reacciones}. Usa '{plural}', que devuelve un valor por reaccion. "
                "No se devuelve el de la primera a proposito: un balance escrito para una "
                "reaccion da un numero plausible y FALSO cuando hay varias."
            )

    # ------------------------------------------------------------------
    # Nombres en singular: compatibles con una reaccion, y un error claro
    # con varias. Ver la nota de cabecera.
    # ------------------------------------------------------------------
    @property
    def dH_rxn(self):
        self._exigir_una_sola("dH_rxn", "dH_rxn_de_cada_una")
        return float(self.dH_rxn_de_cada_una[0])

    @property
    def dG_rxn(self):
        self._exigir_una_sola("dG_rxn", "dG_rxn_de_cada_una")
        return float(self.dG_rxn_de_cada_una[0])

    @property
    def K_eq_std(self):
        self._exigir_una_sola("K_eq_std", "K_eq_std_de_cada_una")
        return float(self.K_eq_std_de_cada_una[0])

    def K_eq(self, T_kelvin):
        """
        B. Constante de equilibrio K_eq(T) via van't Hoff, asumiendo
        DeltaH_rxn° constante entre T_std y T.
        """
        self._exigir_una_sola("K_eq()", "K_eq_de_cada_una()")
        return float(self.K_eq_de_cada_una(T_kelvin)[0])

    def velocidad_reaccion(self, T_kelvin, x_mezcla):
        """
        C. Velocidad neta de reaccion r(T, x):
            k(T) = A * exp(-Ea / (R*T))
            a    = x * gamma(T, x)
            r    = k(T) * ( prod_reactivos a_i^|nu_i| - (1/K_eq(T)) * prod_productos a_j^nu_j )
        """
        self._exigir_una_sola("velocidad_reaccion()", "velocidades()")
        return float(self.velocidades(T_kelvin, x_mezcla)[0])

    # ------------------------------------------------------------------
    # Nombres en plural: siempre un valor por reaccion.
    # ------------------------------------------------------------------
    def K_eq_de_cada_una(self, T_kelvin):
        """van't Hoff para cada reaccion. Devuelve un vector (n_reacciones,)."""
        return self.K_eq_std_de_cada_una * np.exp(
            (self.dH_rxn_de_cada_una / self.R) * (1.0 / self.T_std - 1.0 / T_kelvin)
        )

    def constantes_cineticas(self, T_kelvin):
        """Arrhenius para cada reaccion: k_j(T) = A_j exp(-Ea_j/(R T))."""
        return self.A * np.exp(-self.Ea / (self.R * T_kelvin))

    def velocidades(self, T_kelvin, x_mezcla):
        """
        Velocidad neta de CADA reaccion, vector (n_reacciones,).

        gamma se pide UNA sola vez y se reparte entre todas las
        reacciones. No es un ahorro menor: UNIFAC es lo mas caro de todo
        el calculo, y pedirlo por reaccion multiplicaria por
        n_reacciones el coste de cada evaluacion del reactor -- y cada
        evaluacion ocurre dentro de un lazo de Newton, que ocurre dentro
        del lazo de reciclos.
        """
        x_mezcla = np.asarray(x_mezcla, dtype=float)
        gamma = self.proveedor.coeficientes_actividad(T_kelvin, x_mezcla)
        actividades = x_mezcla * gamma

        k = self.constantes_cineticas(T_kelvin)
        K = self.K_eq_de_cada_una(T_kelvin)

        directo = np.prod(np.power(actividades, self._exp_reactivos), axis=1)
        inverso = np.prod(np.power(actividades, self._exp_productos), axis=1)

        return k * (directo - inverso / K)

    # ------------------------------------------------------------------
    def desplazamiento_composicion(self, n_entrada, xi):
        """
        Moles de salida dados los de entrada y el avance de cada reaccion:

            n_i,salida = n_i,entrada + sum_j nu_ji * xi_j

        Existe aqui, y no repetida en cada reactor, porque es la unica
        pieza de estequiometria que cambia de forma al pasar de una
        reaccion a varias: el producto `nu * xi` se convierte en el
        producto matriz-vector `NU^T xi`. Tenerla en un solo sitio es lo
        que evita que un reactor se quede con la version escalar.
        """
        xi = np.atleast_1d(np.asarray(xi, dtype=float))
        if xi.size != self.n_reacciones:
            raise ValueError(
                f"Se dieron {xi.size} avances para {self.n_reacciones} reacciones."
            )
        return np.asarray(n_entrada, dtype=float) + self.NU.T @ xi

    def calor_liberado(self, xi):
        """
        Calor de reaccion total, sum_j xi_j * dH_rxn_j [W si xi va en mol/s].

        Es una suma, no un maximo ni un promedio: cada reaccion aporta su
        propio calor y las exotermicas y endotermicas se compensan de
        verdad.
        """
        xi = np.atleast_1d(np.asarray(xi, dtype=float))
        if xi.size != self.n_reacciones:
            raise ValueError(
                f"Se dieron {xi.size} avances para {self.n_reacciones} reacciones."
            )
        return float(np.dot(xi, self.dH_rxn_de_cada_una))
