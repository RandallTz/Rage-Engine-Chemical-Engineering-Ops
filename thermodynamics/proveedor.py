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
