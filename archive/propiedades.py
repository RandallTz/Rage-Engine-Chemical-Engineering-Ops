"""
Motor de propiedades: evalua las correlaciones de Yaws (Antoine, Cp, Gf,
Hvap, ...) usando los coeficientes crudos que devuelve RepositorioQuimico.

Cada magnitud se calcula UNICAMENTE cuando se solicita (evaluacion
perezosa) y se cachea por (compuesto, magnitud, T) para no repetir el
calculo en cada iteracion de una columna o un flash.

Este modulo no sabe nada de Excel/JSON/SQLite: solo consume el diccionario
que ya entrega RepositorioQuimico.obtener_propiedades_puras(). Tampoco
decide topologia de destilacion ni coeficientes de actividad -- eso sigue
viviendo en equations.py y thermodynamic_models.py; aqui solo se les
arman los numeros que necesitan.
"""

import math

R_GAS_J = 8.314462618  # J/(mol*K)
R_GAS_kJ = R_GAS_J / 1000  # kJ/(mol*K), unidades en que Yaws da Gf/Hf/Af/Uf


def _primer_registro(propiedades, *slugs_preferidos):
    """Devuelve (slug, registro) de la primera tabla disponible en el orden dado."""
    for slug in slugs_preferidos:
        registros = propiedades.get(slug)
        if registros:
            return slug, registros[0]
    return None, None


class MotorPropiedades:
    def __init__(self, repositorio):
        self._repo = repositorio
        self._cache_propiedades = {}
        self._cache_calculos = {}

    def _propiedades(self, nombre):
        if nombre not in self._cache_propiedades:
            datos = self._repo.obtener_propiedades_puras([nombre])[nombre]
            if datos is None:
                raise ValueError(
                    f"Compuesto no encontrado en la base de datos: {nombre!r}"
                )
            self._cache_propiedades[nombre] = datos["propiedades"]
        return self._cache_propiedades[nombre]

    def _con_cache(self, clave, calcular):
        if clave not in self._cache_calculos:
            self._cache_calculos[clave] = calcular()
        return self._cache_calculos[clave]

    # ------------------------------------------------------------------
    # Propiedades individuales (una funcion por tipo de correlacion)
    # ------------------------------------------------------------------

    def presion_vapor(self, nombre, T):
        """Psat(T) en mmHg, con la correlacion de Antoine disponible (K o C)."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(props, "antoine_organico_K", "antoine_inorganico_K")
            if r is not None:
                log10P = (
                    r["A"] + r["B"] / T
                    + (r.get("C") or 0) * math.log10(T)
                    + (r.get("D") or 0) * T
                    + (r.get("E") or 0) * T ** 2
                )
                return 10 ** log10P

            _, r = _primer_registro(props, "antoine_organico_C")
            if r is not None:
                T_C = T - 273.15
                log10P = r["A"] - r["B"] / (T_C + r["C"])
                return 10 ** log10P

            raise ValueError(f"Sin coeficientes de Antoine para {nombre!r}")
        return self._con_cache(("Psat", nombre, T), _calcular)

    def capacidad_calorifica_liquido(self, nombre, T):
        """Cp_liquido(T) en J/(mol*K)."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(props, "cp_liquido_organico", "cp_liquido_inorganico")
            if r is None:
                raise ValueError(f"Sin Cp liquido para {nombre!r}")
            return (
                r["A"] + r["B"] * T + (r.get("C") or 0) * T ** 2
                + (r.get("D") or 0) * T ** 3
            )
        return self._con_cache(("Cp_liq", nombre, T), _calcular)

    def capacidad_calorifica_gas(self, nombre, T):
        """Cp_gas(T) en J/(mol*K)."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(props, "cp_gas_organico", "cp_gas_inorganico")
            if r is None:
                raise ValueError(f"Sin Cp gas para {nombre!r}")
            return (
                r["A"] + r["B"] * T + (r.get("C") or 0) * T ** 2
                + (r.get("D") or 0) * T ** 3 + (r.get("E") or 0) * T ** 4
            )
        return self._con_cache(("Cp_gas", nombre, T), _calcular)

    def entalpia_formacion(self, nombre, T):
        """Hf(T) en kJ/mol (gas ideal), Hf = A + B*T + C*T^2."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(props, "calor_formacion_organico")
            if r is None:
                raise ValueError(f"Sin dato de Hf para {nombre!r}")
            return r["A"] + r["B"] * T + (r.get("C") or 0) * T ** 2
        return self._con_cache(("Hf", nombre, T), _calcular)

    def energia_gibbs_formacion(self, nombre, T):
        """Gf(T) en kJ/mol (gas ideal), Gf = A + B*T + C*T^2."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(props, "energia_gibbs_formacion_organico")
            if r is None:
                raise ValueError(f"Sin dato de Gf para {nombre!r}")
            return r["A"] + r["B"] * T + (r.get("C") or 0) * T ** 2
        return self._con_cache(("Gf", nombre, T), _calcular)

    def calor_vaporizacion(self, nombre, T):
        """Hvap(T) en kJ/mol, ecuacion de Watson: Hvap = A*(1-T/Tc)^n."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(
                props, "calor_vaporizacion_organico", "calor_vaporizacion_inorganico"
            )
            if r is None:
                raise ValueError(f"Sin dato de Hvap para {nombre!r}")
            return r["A"] * (1 - T / r["Tc"]) ** r["n"]
        return self._con_cache(("Hvap", nombre, T), _calcular)

    def densidad_liquido(self, nombre, T):
        """rho_liq(T) en g/cm3 (o g/mL), rho = A*B^-((1-T/Tc)^n)."""
        def _calcular():
            props = self._propiedades(nombre)
            _, r = _primer_registro(
                props, "densidad_liquido_organico", "densidad_liquido_inorganico"
            )
            if r is None:
                raise ValueError(f"Sin dato de densidad liquida para {nombre!r}")
            return r["A"] * r["B"] ** (-((1 - T / r["Tc"]) ** r["n"]))
        return self._con_cache(("rho_liq", nombre, T), _calcular)

    # ------------------------------------------------------------------
    # Adaptadores: arman exactamente lo que esperan los motores existentes
    # ------------------------------------------------------------------

    def calcular_alpha_relativo(self, nombres, T, referencia=None):
        """
        Vector de volatilidad relativa alpha_i = Psat_i(T) / Psat_ref(T),
        listo para pasarle a ThermodynamicEngine(alpha=...) en equations.py.
        """
        referencia = referencia or nombres[0]
        Psat_ref = self.presion_vapor(referencia, T)
        return [self.presion_vapor(n, T) / Psat_ref for n in nombres]

    def calcular_K_R(self, nombres, nu, T):
        """
        Constante de equilibrio quimico K_R(T), lista para
        ThermodynamicEngine(K_R=...) en equations.py.

        dG_rxn(T) = sum(nu_i * Gf_i(T))   (Gf de Yaws, kJ/mol)
        K_R(T)    = exp(-dG_rxn(T) / (R*T))
        """
        dG_rxn = sum(
            coef * self.energia_gibbs_formacion(nombre, T)
            for nombre, coef in zip(nombres, nu)
        )
        return math.exp(-dG_rxn / (R_GAS_kJ * T))

    def parametros_nrtl(self, nombres):
        """
        Arma (delta_g, alpha) para NRTL.calcular_gamma en
        thermodynamic_models.py, leyendo repositorio.obtener_parametros_binarios().

        IMPORTANTE: el Yaws Handbook no trae parametros de interaccion
        binaria (no se derivan de Hf/Gf/Cp de compuestos puros; son
        parametros de regresion contra datos experimentales del par, o de
        un metodo predictivo como UNIFAC). Esto FALLA explicitamente si
        'parametros_binarios' no fue poblado desde otra fuente, en vez de
        devolver ceros o None silenciosamente.
        """
        pares = self._repo.obtener_parametros_binarios(nombres)
        n = len(nombres)
        delta_g = [[0.0] * n for _ in range(n)]
        alpha = [[0.0] * n for _ in range(n)]
        faltantes = []

        for (a, b), datos in pares.items():
            if not datos:
                faltantes.append((a, b))
                continue
            i, j = nombres.index(a), nombres.index(b)
            delta_g[i][j] = datos["g_ij"]
            delta_g[j][i] = datos["g_ji"]
            alpha[i][j] = alpha[j][i] = datos["alpha_ij"]

        if faltantes:
            raise ValueError(
                "Faltan parametros NRTL (no existen en el Yaws Handbook; "
                "deben cargarse desde datos experimentales o UNIFAC) para "
                f"los pares: {faltantes}"
            )
        return delta_g, alpha
