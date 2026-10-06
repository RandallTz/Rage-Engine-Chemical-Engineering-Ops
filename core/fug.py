"""
Fenske-Underwood-Gilliland: metodo shortcut para destilacion
multicomponente. Reutiliza CalculadoraELV/ProveedorTermodinamico tal
cual estan -- ya son multicomponente-generales (coeficientes_actividad
via UNIFAC y presiones_saturacion no tienen ningun supuesto binario
hardcodeado), asi que no hizo falta tocarlos.

Hueco real en la directiva, resuelto con criterio de ingenieria
estandar (documentado, no oculto): para el alfa promedio de 3 puntos de
Fenske hace falta T_D/T_B, que a su vez necesitan una composicion de
producto -- pero esa composicion es justo lo que el metodo esta
calculando. Se resuelve con el bootstrap clasico de libro de texto:
  1. Clasificar componentes como mas ligeros que LK / mas pesados que
     HK / intermedios, usando el punto de ebullicion normal (Tb) --
     aproximacion estandar, ya que el orden de volatilidad no suele
     invertirse en el rango de T de una columna.
  2. Distribucion inicial: no-clave se va 100% a un producto;
     claves, segun las recuperaciones especificadas; intermedios,
     50/50 como arranque (se refinan en el paso 4).
  3. T_D/T_B = punto de burbuja de esa distribucion inicial.
  4. Con N_min ya calculado, se refina la distribucion COMPLETA
     (incluyendo intermedios) con la propia razon de Fenske
     (d_i/b_i) = (d_LK/b_LK)*(alpha_i/alpha_LK)^N_min.

Underwood con multiples raices (mas de un componente realmente
distribuido entre LK y HK en volatilidad) es una extension avanzada,
menos estandar que el caso de una sola raiz -- se implemento la
estructura que pide la directiva (un theta por cada intervalo entre
volatilidades adyacentes de componentes distribuidos, sistema lineal
para R_min + los d_i intermedios desconocidos) y se verifico con un
caso sintetico de 2 raices antes de confiar en ella (ver roadmap.md).
"""

import numpy as np
from scipy.optimize import brentq
from core.errores import ErrorFisico
from core import errores


class AnalizadorFUG:
    def __init__(self, calculadora_elv, proveedor, nombres, z_F, q, P_sistema,
                 indice_LK, indice_HK):
        """
        z_F        : vector de composicion de la alimentacion (n componentes).
        indice_LK, indice_HK: indices (0-based) del clave ligero y pesado
                     dentro de 'nombres'/'z_F'. Deben ser distintos.
        """
        self.calculadora_elv = calculadora_elv
        self.proveedor = proveedor
        self.nombres = list(nombres)
        self.z_F = np.asarray(z_F, dtype=float)
        self.q = float(q)
        self.P_sistema = float(P_sistema)
        self.idx_LK = indice_LK
        self.idx_HK = indice_HK
        self.n = len(self.nombres)

        if not np.isclose(self.z_F.sum(), 1.0):
            raise ValueError(f"z_F debe sumar 1.0 (suma actual: {self.z_F.sum()}).")
        if indice_LK == indice_HK:
            raise ValueError("indice_LK e indice_HK deben ser distintos.")

    # ------------------------------------------------------------------
    # Bootstrap de distribucion inicial (ver nota del modulo)
    # ------------------------------------------------------------------
    def _clasificar_por_ebullicion(self):
        Tb = np.array([c.Tb for c in self.proveedor.componentes])
        Tb_LK, Tb_HK = Tb[self.idx_LK], Tb[self.idx_HK]
        ligeros, pesados, intermedios = [], [], []
        for i in range(self.n):
            if i in (self.idx_LK, self.idx_HK):
                continue
            if Tb[i] < Tb_LK:
                ligeros.append(i)
            elif Tb[i] > Tb_HK:
                pesados.append(i)
            else:
                intermedios.append(i)
        return ligeros, pesados, intermedios

    def _distribucion_inicial(self, recuperacion_LK_D, recuperacion_HK_B):
        ligeros, pesados, intermedios = self._clasificar_por_ebullicion()
        d = np.zeros(self.n)
        b = np.zeros(self.n)
        for i in ligeros:
            d[i] = self.z_F[i]
        for i in pesados:
            b[i] = self.z_F[i]
        for i in intermedios:
            d[i] = 0.5 * self.z_F[i]
            b[i] = 0.5 * self.z_F[i]
        d[self.idx_LK] = self.z_F[self.idx_LK] * recuperacion_LK_D
        b[self.idx_LK] = self.z_F[self.idx_LK] * (1.0 - recuperacion_LK_D)
        b[self.idx_HK] = self.z_F[self.idx_HK] * recuperacion_HK_B
        d[self.idx_HK] = self.z_F[self.idx_HK] * (1.0 - recuperacion_HK_B)
        return d, b

    @staticmethod
    def _xD_xB_D_B(d, b):
        D, B = float(d.sum()), float(b.sum())
        return d / D, b / B, D, B

    def _alpha_relativo(self, T, x):
        gamma = self.proveedor.coeficientes_actividad(T, x)
        Psat = self.proveedor.presiones_saturacion(T)
        K = gamma * Psat  # falta dividir entre P_sistema, pero se cancela en el cociente
        return K / K[self.idx_HK]

    # ------------------------------------------------------------------
    # 1. Fenske
    # ------------------------------------------------------------------
    def preparar_fenske(self, recuperacion_LK_D, recuperacion_HK_B):
        d0, b0 = self._distribucion_inicial(recuperacion_LK_D, recuperacion_HK_B)
        x_D0, x_B0, _, _ = self._xD_xB_D_B(d0, b0)

        T_F, _ = self.calculadora_elv.burbuja_T(self.P_sistema, self.z_F)
        T_D, _ = self.calculadora_elv.burbuja_T(self.P_sistema, x_D0)
        T_B, _ = self.calculadora_elv.burbuja_T(self.P_sistema, x_B0)

        alpha_D = self._alpha_relativo(T_D, x_D0)
        alpha_F = self._alpha_relativo(T_F, self.z_F)
        alpha_B = self._alpha_relativo(T_B, x_B0)
        alpha_avg = (alpha_D * alpha_F * alpha_B) ** (1.0 / 3.0)

        # alpha_avg esta referido al clave PESADO (ver _alpha_relativo), asi
        # que alpha_avg[idx_LK] es la volatilidad del ligero respecto del
        # pesado y DEBE ser > 1. Si no lo es, los claves estan invertidos:
        # el que se llamo "ligero" es en realidad el menos volatil.
        #
        # Sin esta guarda el fallo era silencioso y grave: log(alpha<1) es
        # negativo, asi que N_min salia NEGATIVO y se arrastraba hasta un
        # numero de etapas negativo (-21.4 en el caso que lo destapo:
        # isobuteno/metanol/MTBE con LK=metanol y HK=MTBE, cuando el MTBE
        # hierve a 328 K y el metanol a 338 K -- o sea el MTBE es el
        # ligero). Una columna con -21 etapas no es un aviso: es basura
        # presentada como resultado.
        alpha_LK = float(alpha_avg[self.idx_LK])
        if alpha_LK <= 1.0:
            Tb = [getattr(c, "Tb", None) for c in self.proveedor.componentes]
            nom_LK, nom_HK = self.nombres[self.idx_LK], self.nombres[self.idx_HK]
            detalle_Tb = ""
            if Tb[self.idx_LK] and Tb[self.idx_HK]:
                detalle_Tb = (
                    f" Puntos de ebullicion: {nom_LK} hierve a {Tb[self.idx_LK]:.1f} K y "
                    f"{nom_HK} a {Tb[self.idx_HK]:.1f} K."
                )
            raise ValueError(
                f"Los componentes clave estan invertidos: se declaro a {nom_LK!r} como "
                f"clave LIGERO y a {nom_HK!r} como PESADO, pero su volatilidad relativa "
                f"es alpha = {alpha_LK:.4g} <= 1, o sea que {nom_LK!r} es el MENOS "
                f"volatil de los dos.{detalle_Tb} Intercambialos: el clave ligero es el "
                "que se va por el domo."
            )

        N_min = np.log(
            (d0[self.idx_LK] / b0[self.idx_LK]) * (b0[self.idx_HK] / d0[self.idx_HK])
        ) / np.log(alpha_LK)

        # Refinamiento de Fenske para TODOS los componentes dado N_min.
        razon_LK = d0[self.idx_LK] / b0[self.idx_LK]
        razon_i = razon_LK * (alpha_avg / alpha_avg[self.idx_LK]) ** N_min
        d = self.z_F * razon_i / (1.0 + razon_i)
        b = self.z_F - d
        # Las claves conservan su recuperacion EXACTA (la formula de
        # arriba deberia reproducirlas casi exacto; se fuerza para no
        # arrastrar el pequeno error numerico del log/potencia).
        d[self.idx_LK], b[self.idx_LK] = d0[self.idx_LK], b0[self.idx_LK]
        d[self.idx_HK], b[self.idx_HK] = d0[self.idx_HK], b0[self.idx_HK]

        x_D, x_B, D, B = self._xD_xB_D_B(d, b)

        self.alpha_avg = alpha_avg
        self.N_min = float(N_min)
        self.d, self.b, self.x_D, self.x_B, self.D, self.B = d, b, x_D, x_B, D, B
        self.T_D, self.T_F, self.T_B = T_D, T_F, T_B

        return {
            "N_min": self.N_min, "alpha_avg": alpha_avg,
            "T_D": T_D, "T_F": T_F, "T_B": T_B,
            "d": d, "b": b, "x_D": x_D, "x_B": x_B, "D": D, "B": B,
        }

    # ------------------------------------------------------------------
    # 2. Underwood
    # ------------------------------------------------------------------
    def _componentes_distribuidos_para_underwood(self):
        alpha_HK, alpha_LK = self.alpha_avg[self.idx_HK], self.alpha_avg[self.idx_LK]
        indices = [self.idx_HK, self.idx_LK]
        for i in range(self.n):
            if i in (self.idx_LK, self.idx_HK):
                continue
            if alpha_HK < self.alpha_avg[i] < alpha_LK:
                indices.append(i)
        return sorted(indices, key=lambda i: self.alpha_avg[i])

    def resolver_underwood(self):
        if not hasattr(self, "alpha_avg"):
            raise RuntimeError("Llama primero a preparar_fenske().")

        distribuidos = self._componentes_distribuidos_para_underwood()
        alphas_distribuidos = [self.alpha_avg[i] for i in distribuidos]

        def residuo_ecuacion1(theta):
            return np.sum(self.alpha_avg * self.z_F / (self.alpha_avg - theta)) - (1.0 - self.q)

        raices = []
        eps = 1e-9
        for a_inf, a_sup in zip(alphas_distribuidos[:-1], alphas_distribuidos[1:]):
            lo, hi = a_inf * (1 + eps), a_sup * (1 - eps)
            raices.append(brentq(residuo_ecuacion1, lo, hi))

        if len(raices) == 0:
            raise RuntimeError(
                "Underwood: no hay componentes distribuidos entre alpha_HK y "
                "alpha_LK -- revisa la seleccion de LK/HK."
            )

        if len(raices) == 1:
            theta = raices[0]
            R_min = float(np.sum(self.alpha_avg * self.x_D / (self.alpha_avg - theta)) - 1.0)
            return {"theta": raices, "R_min": R_min, "d_ajustado": self.d.copy()}

        # Multiples raices: sistema lineal simultaneo para R_min y los
        # d_i de los componentes intermedios (no clave) distribuidos.
        intermedios = [i for i in distribuidos if i not in (self.idx_LK, self.idx_HK)]
        d_conocido = self.d.copy()
        for i in intermedios:
            d_conocido[i] = 0.0  # estos se resuelven, no se asumen del bootstrap

        n_inc = 1 + len(intermedios)
        A = np.zeros((n_inc, n_inc))
        rhs = np.zeros(n_inc)
        for fila, theta in enumerate(raices):
            suma_conocida = np.sum(self.alpha_avg * d_conocido / (self.alpha_avg - theta))
            rhs[fila] = 1.0 - suma_conocida
            A[fila, 0] = -1.0  # coeficiente de R_min
            for col, i in enumerate(intermedios, start=1):
                A[fila, col] = self.alpha_avg[i] / (self.alpha_avg[i] - theta)

        solucion = np.linalg.solve(A, rhs)
        R_min = float(solucion[0])
        d_ajustado = d_conocido.copy()
        for col, i in enumerate(intermedios, start=1):
            d_ajustado[i] = solucion[col]

        return {"theta": raices, "R_min": R_min, "d_ajustado": d_ajustado}

    # ------------------------------------------------------------------
    # 3. Gilliland (Eduljee, 1975)
    # ------------------------------------------------------------------
    def calcular_etapas_reales(self, R, R_min):
        # Un R_min NEGATIVO no es fisico: el reflujo minimo es, como poco,
        # cero. Underwood lo puede devolver cuando el corte pedido es tan
        # suave que la alimentacion ya esta practicamente separada -- ahi
        # la columna no necesita seccion de rectificacion y el metodo se
        # sale de su rango de validez.
        #
        # Importa avisarlo porque el resultado NO parecia roto: con
        # R_min = -0.068 la comprobacion "R <= R_min" pasaba tan ricamente
        # y Gilliland devolvia un numero de etapas de aspecto razonable
        # (3.95) construido sobre un minimo imposible. Se detecto armando
        # un caso columna+reactor con recuperaciones del 70 %.
        if R_min < 0.0:
            raise ValueError(
                f"Underwood da un reflujo minimo negativo (R_min = {R_min:.4g}), que no "
                "es fisico. Suele significar que el corte pedido es demasiado suave "
                "para estos componentes clave: la alimentacion ya esta casi separada "
                "respecto de ese par y la columna casi no hace falta. Sube las "
                "recuperaciones o elige un par de claves mas dificil de separar."
            )
        if R <= R_min:
            raise ErrorFisico(
                f"R={R} <= R_min={R_min}: requeriria etapas infinitas.",
                codigo=errores.REFLUJO_BAJO_MINIMO,
            )
        X = (R - R_min) / (R + 1.0)
        Y = 0.75 - 0.75 * X ** 0.5668
        return (self.N_min + Y) / (1.0 - Y)

    # ------------------------------------------------------------------
    # 4. Cargas termicas (CMO) -- mismo patron y formulas que
    # EvaluadorMcCabeThiele.calcular_cargas_termicas (core/mccabe_thiele.py),
    # generalizadas a n componentes: ahi Hvap/Cp "de mezcla" se calculan
    # con un vector [x, 1-x] hardcodeado a 2 componentes; aqui es el
    # mismo producto punto pero con x_D/x_B de n componentes.
    # ProveedorTermodinamico.entalpias_vaporizacion/
    # capacidades_calorificas_liquido ya devuelven vectores de n
    # componentes sin cambios (confirmado leyendo su codigo) -- no hizo
    # falta tocarlas.
    # ------------------------------------------------------------------
    def calcular_cargas_termicas(self, D, B, F, x_D, x_B, T_D, T_B, R_ext, T_reflujo=None):
        """
        D, B, F  : flujos molares REALES [mol/tiempo] -- reporte_completo
                   trabaja normalizado a F=1 (z_F suma 1), asi que sus
                   'D'/'B' son FRACCIONES; hay que escalarlas por el
                   flujo real de alimentacion antes de llamar a esto
                   (ver bloque_fug en core/orquestador.py).
        x_D, x_B : composiciones de producto (vectores de n componentes).
        T_D, T_B : temperaturas de burbuja de domo/fondo.
        """
        if T_reflujo is None:
            T_reflujo = T_D

        Hvap_D = float(np.dot(x_D, self.proveedor.entalpias_vaporizacion(T_D)))
        Cp_D = float(np.dot(x_D, self.proveedor.capacidades_calorificas_liquido(T_D)))
        Hvap_B = float(np.dot(x_B, self.proveedor.entalpias_vaporizacion(T_B)))

        Q_c = D * (R_ext + 1.0) * (Hvap_D + Cp_D * (T_D - T_reflujo))
        R_int = R_ext * (1.0 + Cp_D * (T_D - T_reflujo) / Hvap_D)
        V_barra = D * (R_int + 1.0) - F * (1.0 - self.q)
        Q_R = V_barra * Hvap_B

        return {
            "Q_c": Q_c, "Q_R": Q_R, "R_int": R_int, "V_barra": V_barra,
            "T_reflujo": T_reflujo, "Hvap_D": Hvap_D, "Hvap_B": Hvap_B, "Cp_D": Cp_D,
        }

    # ------------------------------------------------------------------
    def reporte_completo(self, recuperacion_LK_D, recuperacion_HK_B, R):
        fenske = self.preparar_fenske(recuperacion_LK_D, recuperacion_HK_B)
        underwood = self.resolver_underwood()
        N = self.calcular_etapas_reales(R, underwood["R_min"])

        d_final = underwood["d_ajustado"]
        b_final = self.z_F - d_final
        x_D_final, x_B_final, D_final, B_final = self._xD_xB_D_B(d_final, b_final)

        return {
            "N_min": fenske["N_min"], "R_min": underwood["R_min"], "N": N, "R": R,
            "theta": underwood["theta"], "alpha_avg": fenske["alpha_avg"],
            "T_D": fenske["T_D"], "T_F": fenske["T_F"], "T_B": fenske["T_B"],
            "nombres": self.nombres, "d": d_final, "b": b_final,
            "x_D": x_D_final, "x_B": x_B_final, "D": D_final, "B": B_final,
        }
