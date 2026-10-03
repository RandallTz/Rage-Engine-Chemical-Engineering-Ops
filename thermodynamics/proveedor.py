"""
Adapter sobre la libreria 'thermo': unico punto de contacto entre el
simulador y los datos/modelos termodinamicos predictivos (Chemical,
UNIFAC). No conoce pint -- todo lo que recibe y devuelve son floats o
arrays de numpy en el Sistema Internacional.
"""

import numpy as np
from thermo.chemical import Chemical
from thermo.unifac import UNIFAC

#: Constante de los gases [J/(mol K)]. El mismo valor que usa
#: thermodynamics/reaccion.py, para que k = Cp/(Cp-R) y van't Hoff no
#: arrastren constantes distintas.
R_GAS = 8.31446


class ProveedorTermodinamico:
    def __init__(self, nombres_componentes):
        self.componentes = [Chemical(nombre) for nombre in nombres_componentes]
        self.grupos_unifac = [comp.UNIFAC_groups for comp in self.componentes]

        # UNIFAC es por contribucion de grupos: si 'thermo' no sabe
        # descomponer una molecula, no hay gamma que calcular. Tipico en
        # gases permanentes (metano, nitrogeno, hidrogeno), que no tienen
        # grupos definidos.
        #
        # Sin esta comprobacion el fallo aparecia mucho mas abajo y
        # disfrazado: UNIFAC.from_subgroups recibia un None y lanzaba
        # "'NoneType' object has no attribute 'items'", que no menciona ni
        # el componente culpable ni la causa.
        sin_grupos = [n for n, g in zip(nombres_componentes, self.grupos_unifac) if not g]
        if sin_grupos:
            raise ValueError(
                f"'thermo' no tiene grupos UNIFAC para: {', '.join(sin_grupos)}. "
                "El modelo de este simulador es UNIFAC predictivo, que descompone cada "
                "molecula en grupos funcionales, y sin ellos no puede calcular coeficientes "
                "de actividad. Suele pasar con gases permanentes (metano, nitrogeno, "
                "hidrogeno, aire). Usa componentes condensables, o un portador como un "
                "hidrocarburo ligero que si tenga grupos."
            )

    def actualizar_estado(self, T_kelvin, P_pascal=101325.0):
        """
        Obliga a los objetos Chemical a recalcular sus propiedades dependientes de T y P.
        """
        for comp in self.componentes:
            comp.calculate(T_kelvin, P_pascal)

    def presiones_saturacion(self, T_kelvin):
        self.actualizar_estado(T_kelvin)
        # Psat devuelve Pascales nativamente en thermo
        return np.array([comp.Psat for comp in self.componentes], dtype=float)

    def entalpias_vaporizacion(self, T_kelvin):
        self.actualizar_estado(T_kelvin)
        # Hvapm devuelve J/mol nativamente en thermo
        return np.array([comp.Hvapm for comp in self.componentes], dtype=float)

    def capacidades_calorificas_liquido(self, T_kelvin):
        self.actualizar_estado(T_kelvin)
        # Cplm devuelve J/(mol*K) nativamente en thermo
        return np.array([comp.Cplm for comp in self.componentes], dtype=float)

    def capacidades_calorificas_gas(self, T_kelvin):
        """
        Cp del GAS ideal [J/(mol K)] (Cpgm de 'thermo').

        Hasta ahora el proyecto solo necesitaba el Cp del liquido: las
        entalpias de vapor se construyen como h_L + DHvap, y la variacion
        de esa suma con T ya ES el Cp del vapor, asi que no hacia falta
        pedirlo aparte.

        Lo necesita la COMPRESION: la relacion isentropica del gas ideal
        pide k = Cp/Cv = Cp/(Cp - R), y eso no se puede sacar de las
        entalpias de liquido.
        """
        self.actualizar_estado(T_kelvin)
        return np.array([comp.Cpgm for comp in self.componentes], dtype=float)

    def exponente_isentropico(self, T_kelvin, y_mezcla):
        """
        k = Cp/Cv del gas ideal para la mezcla, ponderando Cp por
        composicion: k = Cp_mezcla / (Cp_mezcla - R).

        Es la aproximacion de GAS IDEAL. Coherente con el resto del
        proyecto, que ya supone fase vapor ideal en el equilibrio, y por
        tanto hereda el mismo limite: a presiones altas o cerca de la
        critica deja de valer.
        """
        y = np.asarray(y_mezcla, dtype=float)
        cp = float(np.dot(y, self.capacidades_calorificas_gas(T_kelvin)))
        if cp <= R_GAS:
            raise ValueError(
                f"El Cp de gas de esta mezcla a {T_kelvin:.2f} K sale {cp:.4g} J/(mol K), "
                f"que no supera a R={R_GAS}. Sin Cp > R no hay un k = Cp/(Cp-R) fisico."
            )
        return cp / (cp - R_GAS)

    def propiedades_caloricas(self, T_kelvin):
        """
        (Cp_liquido, DHvap) en una sola pasada [J/(mol K)], [J/mol].

        Pedirlas por separado obliga a 'thermo' a recalcular el estado de
        cada Chemical dos veces a la misma T. CalculadoraEntalpia tabula
        las dos sobre la misma malla, asi que aqui se ahorra la mitad de
        las llamadas a calculate().
        """
        self.actualizar_estado(T_kelvin)
        Cp = np.array([comp.Cplm for comp in self.componentes], dtype=float)
        Hvap = np.array([comp.Hvapm for comp in self.componentes], dtype=float)
        return Cp, Hvap

    # ------------------------------------------------------------------
    # Propiedades que hacen falta para DIMENSIONAR, no para equilibrar.
    #
    # Van aqui y no en core/dimensionado.py a proposito: ese modulo son
    # correlaciones empiricas de geometria y no debe saber nada de
    # 'thermo'. Separarlos es lo que permite decir de donde viene la
    # incertidumbre de un resultado -- del modelo o del ajuste.
    # ------------------------------------------------------------------
    def densidades_liquido(self, T_kelvin):
        """Densidad del liquido puro de cada componente [kg/m3]."""
        self.actualizar_estado(T_kelvin)
        valores = []
        for comp in self.componentes:
            rho = getattr(comp, "rhol", None)
            if rho is None or not np.isfinite(rho) or rho <= 0:
                raise ValueError(
                    f"'thermo' no da densidad de liquido para {comp.name} a "
                    f"{T_kelvin:.2f} K. Puede que esa temperatura este por encima de su "
                    "punto critico, donde no hay liquido que medir."
                )
            valores.append(float(rho))
        return np.array(valores, dtype=float)

    def tensiones_superficiales(self, T_kelvin):
        """Tension superficial del liquido puro de cada componente [N/m]."""
        self.actualizar_estado(T_kelvin)
        valores = []
        for comp in self.componentes:
            sigma = getattr(comp, "sigma", None)
            if sigma is None or not np.isfinite(sigma) or sigma <= 0:
                raise ValueError(
                    f"'thermo' no da tension superficial para {comp.name} a "
                    f"{T_kelvin:.2f} K. Sin ella no se puede corregir la correlacion de "
                    "inundacion, que depende de sigma^0.2."
                )
            valores.append(float(sigma))
        return np.array(valores, dtype=float)

    def densidad_liquido_mezcla(self, T_kelvin, x_mezcla):
        """
        Densidad de la mezcla liquida [kg/m3], por volumenes aditivos:

            1/rho = sum_i (w_i / rho_i)        con w_i la fraccion MASICA

        Es la regla de Amagat, que para liquidos organicos parecidos
        acierta dentro de un pequeno porcentaje. No es exacta: el exceso
        de volumen de mezcla existe y puede llegar al 2-3 % en mezclas
        polares. Se elige asi, y se dice, porque la alternativa -- un
        modelo de volumen de exceso -- aportaria una precision que la
        correlacion de inundacion que consume este numero no puede
        aprovechar: esa correlacion tiene un +-10 % de su propio ajuste.
        """
        x = np.asarray(x_mezcla, dtype=float)
        x = x / float(np.sum(x))
        rho_i = self.densidades_liquido(T_kelvin)
        MW = np.array([float(c.MW) for c in self.componentes], dtype=float)
        masa = x * MW
        w = masa / float(np.sum(masa))
        return float(1.0 / np.sum(w / rho_i))

    def tension_superficial_mezcla(self, T_kelvin, x_mezcla):
        """
        Tension superficial de la mezcla [N/m], media molar.

        Una media molar simple es grosera -- la tension superficial de una
        mezcla la domina el componente que se acumula en la superficie, y
        en mezclas con agua eso hace que caiga mucho mas rapido de lo que
        la media sugiere. Se usa igual por la misma razon que arriba: la
        correlacion que la consume la eleva a 0.2, asi que un error del
        20 % en sigma se convierte en un 4 % en la velocidad de
        inundacion, por debajo de la incertidumbre del propio ajuste.
        """
        x = np.asarray(x_mezcla, dtype=float)
        x = x / float(np.sum(x))
        return float(np.dot(x, self.tensiones_superficiales(T_kelvin)))

    def densidad_vapor_ideal(self, T_kelvin, P_pascal, y_mezcla):
        """
        Densidad del vapor [kg/m3] suponiendo GAS IDEAL:

            rho = P * MW_mezcla / (R T)

        Es coherente con el resto del simulador, que supone fase vapor
        ideal en todas partes (ver docs/03-termodinamica.md). A presion
        atmosferica el error es de decimas de porcentaje; a 10 atm puede
        ser del 5-10 %, y como el diametro va con 1/sqrt(rho_V), eso es un
        2-5 % en el diametro. Esta documentado como limite en vez de
        corregido a medias.
        """
        y = np.asarray(y_mezcla, dtype=float)
        y = y / float(np.sum(y))
        MW = np.array([float(c.MW) for c in self.componentes], dtype=float)
        MW_mezcla = float(np.dot(y, MW)) / 1000.0        # kg/mol
        return float(P_pascal) * MW_mezcla / (R_GAS * float(T_kelvin))

    def coeficientes_actividad(self, T_kelvin, x_mezcla):
        """
        Coeficientes de actividad gamma_i(T, x) via UNIFAC predictivo puro.
        No depende de P (UNIFAC clasico es solo funcion de T y composicion).
        """
        # thermo requiere que xs sea una lista estandar de Python, no un ndarray
        x_lista = np.asarray(x_mezcla, dtype=float).tolist()
        modelo = UNIFAC.from_subgroups(
            T=T_kelvin, xs=x_lista, chemgroups=self.grupos_unifac
        )
        return np.array(modelo.gammas(), dtype=float)

    def entalpias_formacion_liquido(self):
        """
        Entalpia estandar de formacion en fase liquida, DeltaHf° [J/mol],
        a Tstd = 298.15 K. Es una propiedad de referencia fija de 'thermo'
        (Hfm): no depende del T,P actual de los objetos Chemical, por eso
        no llama a actualizar_estado.
        """
        return np.array([comp.Hfm for comp in self.componentes], dtype=float)

    def energias_gibbs_formacion_liquido(self):
        """
        Energia de Gibbs estandar de formacion en fase liquida,
        DeltaGf° [J/mol], a Tstd = 298.15 K (Gfm de 'thermo', misma
        naturaleza fija que entalpias_formacion_liquido).
        """
        return np.array([comp.Gfm for comp in self.componentes], dtype=float)

    def volatilidades_relativas(self, T_kelvin, x_mezcla, indice_referencia=0):
        """
        Calcula el vector de volatilidades relativas (alfa dinamico) usando
        la Ley de Raoult Modificada (alfa_i = gamma_i * P_sat_i / P_ref_total).
        """
        gamma = self.coeficientes_actividad(T_kelvin, x_mezcla)
        p_sat = self.presiones_saturacion(T_kelvin)

        volatilidades = (gamma * p_sat) / (gamma[indice_referencia] * p_sat[indice_referencia])
        return volatilidades
