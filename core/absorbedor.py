"""
Absorbedor / desorbedor por el metodo de Kremser.

Que resuelve: una columna donde un gas sube y un liquido (el disolvente)
baja en contracorriente, y los componentes se reparten entre las dos
fases. Es la familia de equipos del lavado de gases -- absorcion,
desorcion, stripping -- que el simulador no tenia en absoluto.

Kremser es un metodo de ATAJO, igual que FUG lo es para destilacion: da
el reparto con N etapas sin resolver etapa por etapa. Para cada
componente, con el factor de absorcion A = L/(K*V):

    fraccion recuperada  phi = (A^(N+1) - A) / (A^(N+1) - 1)

y lo transferido del gas al liquido es

    transferido_i = V * (y_ent,i - K_i * x_ent,i) * phi_i

La forma con el termino K*x_ent, y no solo con y_ent, importa: hace que
el mismo bloque sirva para DESORBER sin escribir nada aparte. Si el
liquido entra mas cargado de lo que el equilibrio admite
(K*x_ent > y_ent), el transferido sale NEGATIVO y el componente pasa del
liquido al gas, que es exactamente lo que hace un stripper. Un absorbedor
y un desorbedor son el mismo equipo con el gradiente al reves.

SUPOSICIONES, y son fuertes:

  - Isotermo. La absorcion libera calor y en una columna real la
    temperatura sube; aqui se opera a una T dada (por defecto la del
    liquido que entra, que suele ser el sumidero termico dominante).
  - Caudales de gas y liquido CONSTANTES a lo largo de la columna. Es la
    hipotesis de sistema diluido sobre la que se deduce Kremser. Si se
    absorbe una fraccion grande del gas, deja de valer.
  - K_i evaluada en las condiciones de entrada del liquido. Para un
    disolvente casi puro eso es practicamente la dilucion infinita, que
    es la condicion correcta para absorcion.

Zona libre de pint: floats/np.ndarray en SI.
"""

import numpy as np

_TOL = 1e-12


class EvaluadorAbsorbedor:
    def __init__(self, calculadora_elv, P_sistema=101325.0):
        self.calculadora_elv = calculadora_elv
        self.proveedor = calculadora_elv.proveedor
        self.P_sistema = float(P_sistema)
        self.n = len(self.proveedor.componentes)

    def factores_absorcion(self, T, P, L, V, x_liquido):
        """
        A_i = L / (K_i * V), con K_i = gamma_i(T,x) * Psat_i(T) / P.

        A > 1 significa que el disolvente tiene capacidad de sobra para
        ese componente y se absorbe bien; A < 1, que el gas se lo lleva.
        Es el numero que gobierna todo el metodo.
        """
        x = np.asarray(x_liquido, dtype=float)
        gamma = self.proveedor.coeficientes_actividad(T, x)
        p_sat = self.proveedor.presiones_saturacion(T)
        K = gamma * p_sat / P
        if V <= _TOL:
            raise ValueError("Sin caudal de gas no hay absorcion que calcular.")
        return L / np.clip(K, 1e-300, None) / V, K

    @staticmethod
    def _recuperacion(A, N):
        """
        phi = (A^(N+1) - A) / (A^(N+1) - 1), con el limite A -> 1.

        En A = 1 la expresion es 0/0; el limite vale N/(N+1). Se trata
        aparte porque A = 1 no es un caso raro de laboratorio: es
        exactamente donde se disena muchas columnas (L/V ajustado a K), y
        dejar que el flotante se acerque a 0/0 ahi da ruido en vez de un
        numero.
        """
        A = np.asarray(A, dtype=float)
        phi = np.empty_like(A)

        cerca_de_uno = np.abs(A - 1.0) < 1e-6
        phi[cerca_de_uno] = N / (N + 1.0)

        # A > 1 con N grande DESBORDA: A^(N+1) se va al infinito y la
        # expresion da inf/inf = NaN. Medido: con A=2.8 revienta hacia
        # N~1000, y un absorbedor con muchas etapas no es raro.
        #
        # Se arregla dividiendo arriba y abajo por A^(N+1), que es
        # algebraicamente lo mismo pero numericamente al reves: ahora lo
        # que aparece es A^(-N), que tiende a CERO en vez de a infinito.
        #
        #     phi = (1 - A^(-N)) / (1 - A^(-(N+1)))
        #
        # Para A < 1 la forma original ya es estable (A^(N+1) -> 0), asi
        # que cada rama usa la escritura que no se rompe.
        alto = (~cerca_de_uno) & (A > 1.0)
        if np.any(alto):
            a = A[alto]
            phi[alto] = (1.0 - a ** (-N)) / (1.0 - a ** (-(N + 1.0)))

        bajo = (~cerca_de_uno) & (A <= 1.0)
        if np.any(bajo):
            a = A[bajo]
            potencia = a ** (N + 1.0)
            phi[bajo] = (potencia - a) / (potencia - 1.0)

        return np.clip(phi, 0.0, 1.0)

    def resolver(self, V_gas, y_entrada, L_liquido, x_entrada, N_etapas,
                 T_operacion=None, P=None, T_gas=None, T_liquido=None):
        """
        Devuelve los caudales y composiciones de las dos salidas.

        V_gas, L_liquido : caudales molares de gas y liquido [mol/s]
        y_entrada        : composicion del gas que entra (por abajo)
        x_entrada        : composicion del liquido que entra (por arriba)
        N_etapas         : etapas teoricas
        T_operacion      : si no se da, la del liquido que entra
        """
        P = self.P_sistema if P is None else float(P)
        N = float(N_etapas)
        if N <= 0:
            raise ValueError(f"Un absorbedor necesita al menos una etapa (se dio N={N_etapas}).")
        y_ent = np.asarray(y_entrada, dtype=float)
        x_ent = np.asarray(x_entrada, dtype=float)
        V, L = float(V_gas), float(L_liquido)

        if T_operacion is None:
            T_operacion = T_liquido if T_liquido is not None else T_gas
        if T_operacion is None:
            raise ValueError("Hace falta una temperatura de operacion para evaluar K.")
        T = float(T_operacion)

        A, K = self.factores_absorcion(T, P, L, V, x_ent)
        phi = self._recuperacion(A, N)

        # Fuerza impulsora: lo que el gas trae de mas (o de menos) frente
        # a lo que estaria en equilibrio con el liquido que entra.
        transferido = V * (y_ent - K * x_ent) * phi

        # Cotas fisicas: no se puede quitar del gas mas de lo que trae, ni
        # del liquido mas de lo que lleva. Que una cota APRIETE significa
        # que Kremser se esta usando fuera de su rango (sistema no
        # diluido), asi que se avisa en vez de recortar en silencio.
        tope_gas = V * y_ent
        tope_liquido = L * x_ent
        excedido = (transferido > tope_gas + 1e-9) | (transferido < -tope_liquido - 1e-9)
        if np.any(excedido):
            i = int(np.argmax(excedido))
            raise ValueError(
                f"Kremser predice transferir {transferido[i]:.6g} mol/s del componente {i}, "
                f"mas de lo que hay disponible ({tope_gas[i]:.6g} mol/s en el gas, "
                f"{tope_liquido[i]:.6g} mol/s en el liquido). El metodo supone sistema "
                "DILUIDO y caudales constantes; con una absorcion tan fuerte deja de valer. "
                "Baja el numero de etapas, el caudal de disolvente, o usa una columna rigurosa."
            )

        gas_salida = V * y_ent - transferido
        liq_salida = L * x_ent + transferido
        V_out, L_out = float(np.sum(gas_salida)), float(np.sum(liq_salida))

        y_out = gas_salida / V_out if V_out > _TOL else np.full(self.n, 1.0 / self.n)
        x_out = liq_salida / L_out if L_out > _TOL else np.full(self.n, 1.0 / self.n)

        # Recuperacion REAL por componente: que fraccion de lo que entraba
        # en el gas acaba en el liquido. No es phi -- phi es la fraccion
        # de la fuerza impulsora aprovechada, no de la materia.
        recuperacion = np.where(tope_gas > _TOL, transferido / np.clip(tope_gas, _TOL, None), 0.0)

        return {
            "V_salida": V_out, "y_salida": y_out,
            "L_salida": L_out, "x_salida": x_out,
            "T": T, "P": P, "N_etapas": N,
            "A": A, "K": K, "phi": phi,
            "transferido": transferido, "recuperacion": recuperacion,
        }
