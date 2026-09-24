"""
McCabe-Thiele Orientado a Ecuaciones (EO): en vez de un script rigido que
siempre calcula N a partir de (z_F, q, x_D, x_B, R), se trata el problema
como UN residuo (el conteo de etapas) sobre un vector de variables
v = [z_F, q, x_D, x_B, R, N]. Segun cual de esas variables falte, se
evalua directo (modo "rating") o se resuelve por root-finding (modo
"design spec", p.ej. fijar N y encontrar el R que lo produce).

Nota de alcance (importante, verificada antes de programar): con un solo
evaluador N=f(z_F,q,x_D,x_B,R) hay UNA sola ecuacion. Eso significa que
el solver aqui resuelve, con cero grados de libertad, el caso de
EXACTAMENTE una incognita entre {z_F,q,x_D,x_B,R} dado N (o N dado el
resto). Pedir dos incognitas a la vez (p.ej. R y x_B fijando solo N) es
subdeterminado con esta unica ecuacion -- necesitaria una ecuacion
adicional (balance de masa global F*z_F = D*x_D + B*x_B) que todavia no
esta implementada. Se deja como extension futura explicita, no como un
caso silenciosamente mal resuelto.

Zona con numpy/scipy; no es parte de core/ en el sentido estricto de
"nucleo vectorizado sin bucles" -- el escalonamiento de McCabe-Thiele es
inherentemente iterativo (una etapa depende de la anterior), asi que aqui
si hay un bucle for legitimo por etapa.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq, root_scalar

from thermodynamics.entalpia import entalpia_de

_MAX_ETAPAS = 200


class EvaluadorMcCabeThiele:
    def __init__(self, calculadora_elv, nombres, P_sistema=101325.0, n_puntos_curva=100):
        """
        calculadora_elv : CalculadoraELV (burbuja_T) para el par binario.
        nombres         : lista de 2 nombres reconocidos por 'thermo'; el
                          primero es el "ligero" -- x_D, x_B, z_F se
                          refieren a su fraccion molar.
        P_sistema       : presion de operacion de la columna [Pa].

        La curva de equilibrio y(x) se precalcula UNA vez (barriendo x1 y
        resolviendo burbuja_T -- caro, UNIFAC + root-finding anidado) y se
        interpola con un spline monotono (PCHIP) para el resto de la
        vida del objeto: el escalonamiento y el solver de grados de
        libertad evaluan y(x) muchisimas veces, y no se puede pagar un
        burbuja_T completo en cada una.
        """
        # McCabe-Thiele se construye sobre UN solo par x-y, asi que no
        # tiene sentido para mas de dos componentes. Sin esta guarda el
        # fallo llegaba mucho mas abajo y disfrazado: el bucle de abajo
        # arma composiciones de 2 elementos contra un proveedor de n, y
        # lo que veia el usuario era un error de punto de burbuja que no
        # mencionaba el verdadero problema.
        if len(nombres) != 2:
            raise ValueError(
                f"McCabe-Thiele es un metodo BINARIO y recibio {len(nombres)} "
                f"componentes ({', '.join(nombres)}). Para una mezcla "
                "multicomponente usa FUG (Fenske-Underwood-Gilliland), que "
                "trabaja con cualquier numero de componentes especificando "
                "las recuperaciones de los dos claves."
            )

        self.calculadora_elv = calculadora_elv
        self.nombres = nombres
        self.P_sistema = float(P_sistema)
        # Perezosa: solo calcular_cargas_termicas necesita entalpias, y
        # la mayoria de los usos de McCabe-Thiele (escalonamiento,
        # grados de libertad) no las tocan.
        self._entalpia = None

        x1 = np.linspace(1e-4, 1 - 1e-4, n_puntos_curva)
        y1 = np.empty(n_puntos_curva)
        for i, x in enumerate(x1):  # bucle permitido: burbuja_T es una composicion a la vez
            _, y_vapor = calculadora_elv.burbuja_T(P_sistema, np.array([x, 1.0 - x]))
            y1[i] = y_vapor[0]

        # extremos fisicos exactos (x=0->y=0, x=1->y=1) para que la spline
        # no extrapole mal cerca de los componentes puros
        x1_ext = np.concatenate([[0.0], x1, [1.0]])
        y1_ext = np.concatenate([[0.0], y1, [1.0]])
        self._curva_equilibrio = PchipInterpolator(x1_ext, y1_ext)

    @property
    def entalpia(self):
        if self._entalpia is None:
            self._entalpia = entalpia_de(self.calculadora_elv.proveedor)
        return self._entalpia

    def y_equilibrio(self, x):
        return float(self._curva_equilibrio(x))

    def azeotropo_entre(self, x_inf, x_sup, n_muestras=200):
        """
        Busca un azeotropo (cruce de y(x) con la diagonal) dentro de un
        intervalo. Es un DIAGNOSTICO, no parte del metodo: sirve para
        explicar por que un escalonamiento se atasca. Un azeotropo entre
        x_B y x_D hace la separacion imposible por destilacion simple --
        sin esto, el fallo aparece como un "f(a) and f(b) must have
        different signs" de brentq, que no dice nada.

        Devuelve la fraccion molar del azeotropo, o None si no hay.
        """
        xs = np.linspace(max(x_inf, 1e-6), min(x_sup, 1 - 1e-6), n_muestras)
        diferencia = np.array([self.y_equilibrio(float(x)) - float(x) for x in xs])
        cambios = np.where(np.diff(np.sign(diferencia)) != 0)[0]
        if len(cambios) == 0:
            return None
        i = cambios[0]
        d0, d1 = diferencia[i], diferencia[i + 1]
        fraccion = 0.0 if d1 == d0 else d0 / (d0 - d1)
        return float(xs[i] + fraccion * (xs[i + 1] - xs[i]))

    @staticmethod
    def _linea_q(x, z_F, q):
        if np.isclose(q, 1.0):
            return None  # vertical; se maneja aparte
        return (q / (q - 1.0)) * x - z_F / (q - 1.0)

    def _interseccion_q_equilibrio(self, z_F, q):
        """Interseccion de la linea q con la curva de equilibrio -> punto usado para R_min."""
        if np.isclose(q, 1.0):
            x_pinch = z_F
        else:
            residuo = lambda x: self.y_equilibrio(x) - self._linea_q(x, z_F, q)
            x_pinch = brentq(residuo, 1e-6, 1 - 1e-6)
        y_pinch = self.y_equilibrio(x_pinch)
        return x_pinch, y_pinch

    @staticmethod
    def _interseccion_rol_q(x_D, R, z_F, q):
        """Interseccion (analitica) entre la ROL y la linea q."""
        if np.isclose(q, 1.0):
            x_int = z_F
            y_int = (R / (R + 1.0)) * x_int + x_D / (R + 1.0)
            return x_int, y_int
        m_q, b_q = q / (q - 1.0), -z_F / (q - 1.0)
        m_rol, b_rol = R / (R + 1.0), x_D / (R + 1.0)
        x_int = (b_rol - b_q) / (m_q - m_rol)
        y_int = m_rol * x_int + b_rol
        return x_int, y_int

    def calcular_R_min(self, z_F, q, x_D):
        x_pinch, y_pinch = self._interseccion_q_equilibrio(z_F, q)
        if np.isclose(y_pinch, x_pinch):
            raise ValueError(
                f"Pinch degenerado (x={x_pinch:.4f} sobre la diagonal): "
                "R_min no esta definido para esta z_F/q."
            )
        return (x_D - y_pinch) / (y_pinch - x_pinch)

    def calcular_escalones(self, z_F, q, x_D, x_B, R, condensador_parcial=False, E_MV=1.0):
        """
        condensador_parcial: si True, x_D se interpreta como la
        composicion del producto de tope en fase VAPOR (y_D), no liquida.

        La geometria (R_min, ROL, SOL, escalonamiento) es identica al caso
        de condensador total: la ROL siempre cruza la diagonal y=x en el
        valor de su termino independiente, sea ese valor liquido o vapor,
        asi que no hace falta tocar esa matematica. Lo unico que cambia
        fisicamente es que el condensador PARCIAL es el mismo una etapa
        de equilibrio (el condensador total no aporta ninguna), asi que
        se suma 1 a N -- la simplificacion estandar de libro de texto.

        Nota de honestidad: la ubicacion grafica exacta del punto
        (x_0, y_D) dentro del escalonamiento tiene variantes segun el
        texto (que corriente de vapor se asume igual a cual). Se eligio
        la forma "+1 etapa" por ser la menos propensa a un error de
        indice/conteo al modificar el bucle; si se necesita el detalle
        grafico fino, conviene confirmarlo con una fuente antes.

        E_MV: eficiencia de Murphree de vapor (1.0 = etapa ideal). Afecta
        SOLO el escalonamiento (etapas reales); R_min y el pinch siguen
        usando la curva de equilibrio real -- la eficiencia de plato no
        cambia el limite termodinamico de reflujo minimo.
        """
        resultado = self._calcular_escalones_base(z_F, q, x_D, x_B, R, E_MV=E_MV)
        if condensador_parcial:
            resultado["N"] += 1.0
        resultado["condensador_parcial"] = bool(condensador_parcial)
        resultado["E_MV"] = E_MV
        return resultado

    def _calcular_escalones_base(self, z_F, q, x_D, x_B, R, E_MV=1.0):
        """
        Escalona desde (x_D, x_D) hasta cruzar x_B, cambiando de la ROL a
        la SOL en la interseccion con la linea q. Devuelve N continuo
        (con fraccion, interpolando el ultimo escalon) y las coordenadas
        de los escalones para graficar.

        Con E_MV < 1, el paso "fisico" de cada escalon ya no busca la
        curva de equilibrio real sino la de pseudo-equilibrio
        y_pseudo(x) = y_op(x) + E_MV*(y_eq(x) - y_op(x)); con E_MV=1.0
        esto se reduce identicamente al caso ideal (y_pseudo == y_eq).
        """
        if not (0.0 < x_B < z_F < x_D < 1.0):
            raise ValueError(
                f"Se requiere 0 < x_B < z_F < x_D < 1 (recibido x_B={x_B}, "
                f"z_F={z_F}, x_D={x_D})."
            )
        if not (0.0 < E_MV <= 1.0):
            raise ValueError(f"E_MV debe estar en (0, 1] (recibido {E_MV}).")

        R_min = self.calcular_R_min(z_F, q, x_D)
        if R <= R_min:
            raise ValueError(f"R={R:.4f} <= R_min={R_min:.4f}: requeriria etapas infinitas.")

        x_int, y_int = self._interseccion_rol_q(x_D, R, z_F, q)
        if not (x_B < x_int < x_D):
            raise ValueError(
                f"Interseccion ROL/q en x={x_int:.4f} fuera de (x_B, x_D) "
                "-- combinacion R/z_F/q no fisica para este x_B/x_D."
            )
        m_sol = (y_int - x_B) / (x_int - x_B)
        b_sol = x_B - m_sol * x_B  # y = m_sol*(x-x_B) + x_B = m_sol*x + b_sol

        def y_operativa(x):
            return (R / (R + 1.0)) * x + x_D / (R + 1.0) if x >= x_int else m_sol * x + b_sol

        def y_pseudo(x):
            y_op = y_operativa(x)
            return y_op + E_MV * (self.y_equilibrio(x) - y_op)

        escalones = [(x_D, x_D)]
        x_actual = x_D
        y_actual = x_D  # arranca sobre la diagonal (condensador total): x_D == y_D
        N_enteras = 0

        for _ in range(_MAX_ETAPAS):
            try:
                x_nuevo = brentq(lambda x: y_pseudo(x) - y_actual, 1e-9, x_actual)
            except ValueError as e:
                # brentq dice "f(a) and f(b) must have different signs",
                # que no explica nada. La causa habitual es un azeotropo
                # entre x_B y x_D: ahi la separacion pedida es imposible
                # por destilacion simple, por mucho reflujo que se use.
                azeotropo = self.azeotropo_entre(x_B, x_D)
                if azeotropo is not None:
                    raise ValueError(
                        f"Separacion imposible por destilacion simple: hay un azeotropo en "
                        f"x={azeotropo:.4f}, entre x_B={x_B} y x_D={x_D}. Ninguna cantidad de "
                        f"etapas ni de reflujo cruza un azeotropo -- hay que quedarse de un solo "
                        f"lado de el, o cambiar de tecnica (destilacion extractiva, azeotropica, "
                        f"cambio de presion)."
                    ) from e
                raise ValueError(
                    f"El escalonamiento se atasco en x={x_actual:.4f} (y={y_actual:.4f}): no hay "
                    f"composicion de liquido en equilibrio con ese vapor dentro de (0, {x_actual:.4f}). "
                    f"Revisa que x_B={x_B}, z_F={z_F}, x_D={x_D}, R={R} sean coherentes para este sistema."
                ) from e
            escalones.append((x_nuevo, y_actual))

            if x_nuevo <= x_B:
                # fraccion de este ultimo escalon horizontal que realmente
                # hacia falta para llegar exactamente a x_B (interpolacion
                # lineal sobre el tramo [x_nuevo, x_actual])
                if np.isclose(x_actual, x_nuevo):
                    fraccion = 1.0
                else:
                    fraccion = (x_actual - x_B) / (x_actual - x_nuevo)
                    fraccion = float(np.clip(fraccion, 0.0, 1.0))
                N_total = N_enteras + fraccion
                escalones.append((x_B, y_operativa(x_B)))
                return {
                    "N": N_total,
                    "escalones": np.array(escalones),
                    "R_min": R_min,
                    "interseccion_rol_q": (x_int, y_int),
                    # se guardan los parametros de entrada usados -- asi
                    # graficar_diagrama() no necesita que se los repitan
                    "z_F": z_F, "q": q, "x_D": x_D, "x_B": x_B, "R": R,
                }

            N_enteras += 1
            y_siguiente = y_operativa(x_nuevo)
            escalones.append((x_nuevo, y_siguiente))
            x_actual = x_nuevo
            y_actual = y_siguiente

        raise RuntimeError(
            f"No se alcanzo x_B tras {_MAX_ETAPAS} etapas -- revisa R/x_B/x_D."
        )

    def curva_N_vs_R(self, z_F, q, x_D, x_B, factores_sobre_Rmin=None):
        """
        Barrido de N(R) a R/R_min creciente -- la curva clasica de diseño
        (N cae rapido cerca de R_min y se aplana acercandose al reflujo
        total). Util para visualizar donde cae el R que resuelve
        SolucionadorMcCabeThiele frente al resto del espacio de diseño.
        """
        R_min = self.calcular_R_min(z_F, q, x_D)
        if factores_sobre_Rmin is None:
            factores_sobre_Rmin = np.concatenate([
                np.linspace(1.02, 1.5, 15), np.linspace(1.5, 6.0, 15)[1:],
            ])
        Rs, Ns = [], []
        for factor in factores_sobre_Rmin:
            R = R_min * factor
            try:
                Ns.append(self.calcular_escalones(z_F, q, x_D, x_B, R)["N"])
                Rs.append(R)
            except (ValueError, RuntimeError):
                continue
        return np.array(Rs), np.array(Ns), R_min

    def graficar_diagrama(self, resultado, titulo=None):
        """
        Dibuja el diagrama clasico de McCabe-Thiele: curva de equilibrio,
        diagonal y=x, ROL, SOL, linea q y el escalonamiento -- a partir
        del dict que devuelve calcular_escalones (o SolucionadorMcCabeThiele
        .resolver, que tiene exactamente las mismas claves).
        """
        z_F, q = resultado["z_F"], resultado["q"]
        x_D, x_B, R = resultado["x_D"], resultado["x_B"], resultado["R"]
        x_int, y_int = resultado["interseccion_rol_q"]
        escalones = resultado["escalones"]

        malla_x = np.linspace(0.0, 1.0, 300)
        malla_y = np.array([self.y_equilibrio(x) for x in malla_x])

        fig, ax = plt.subplots(figsize=(7, 7))
        ax.plot(malla_x, malla_y, color="tab:blue", linewidth=2, label="Equilibrio y(x)")
        ax.plot([0, 1], [0, 1], color="black", linewidth=1, label="y = x")

        ax.plot([x_D, x_int], [x_D, y_int], color="tab:green", linewidth=1.5, label="ROL")
        ax.plot([x_B, x_int], [x_B, y_int], color="tab:orange", linewidth=1.5, label="SOL")
        ax.plot([z_F, x_int], [z_F, y_int], color="tab:purple", linestyle="--",
                linewidth=1.5, label=f"Línea q (q={q:.2f})")

        E_MV = resultado.get("E_MV", 1.0)
        if E_MV < 1.0:
            m_sol = (y_int - x_B) / (x_int - x_B)
            b_sol = x_B - m_sol * x_B

            def y_operativa(x):
                return (R / (R + 1.0)) * x + x_D / (R + 1.0) if x >= x_int else m_sol * x + b_sol

            malla_y_op = np.array([y_operativa(x) for x in malla_x])
            malla_y_pseudo = malla_y_op + E_MV * (malla_y - malla_y_op)
            ax.plot(malla_x, malla_y_pseudo, color="tab:blue", linewidth=1.5,
                    linestyle="--", alpha=0.7, label=f"Pseudo-equilibrio (E_MV={E_MV:.2f})")

        ax.plot(escalones[:, 0], escalones[:, 1], color="red", linewidth=1.2,
                marker="o", markersize=2, label=f"Escalones (N={resultado['N']:.2f})")

        for x_ref, etiqueta in [(x_D, "x_D"), (x_B, "x_B"), (z_F, "z_F")]:
            ax.plot([x_ref, x_ref], [0, x_ref], color="gray", linestyle=":", linewidth=0.8)
            ax.annotate(etiqueta, (x_ref, 0.02), fontsize=9, ha="center", color="gray")

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel(f"x ({self.nombres[0]})")
        ax.set_ylabel(f"y ({self.nombres[0]})")
        ax.set_aspect("equal")
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(alpha=0.3)
        ax.set_title(
            titulo or
            f"McCabe-Thiele — R={R:.3f} (R_min={resultado['R_min']:.3f}), N={resultado['N']:.2f}",
            fontsize=12,
        )
        plt.tight_layout()
        plt.show()

    def graficar_N_vs_R(self, z_F, q, x_D, x_B, R_resuelto=None, N_objetivo=None, titulo=None):
        """Grafica la curva N(R) de diseño; marca opcionalmente el punto resuelto por el solver."""
        Rs, Ns, R_min = self.curva_N_vs_R(z_F, q, x_D, x_B)

        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(Rs, Ns, color="tab:blue", linewidth=2, label="N(R)")
        ax.axvline(R_min, color="gray", linestyle="--", linewidth=1, label=f"R_min={R_min:.3f}")
        if R_resuelto is not None:
            ax.scatter([R_resuelto], [N_objetivo], color="red", zorder=5, s=80,
                       label=f"Resuelto: R={R_resuelto:.3f}, N={N_objetivo:.2f}")
        ax.set_xlabel("Reflujo R")
        ax.set_ylabel("Etapas teóricas N")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
        ax.set_title(titulo or "Sensibilidad N vs. R", fontsize=12)
        plt.tight_layout()
        plt.show()

    def calcular_cargas_termicas(self, D, B, F, z_F, x_D, x_B, R_ext, q, T_reflujo=None):
        """
        Cargas termicas de condensador (total) y rehervidor (parcial),
        bajo Reflujo Molar Constante (CMO) -- consistente con las
        suposiciones del propio McCabe-Thiele; el tratamiento riguroso de
        entalpia (H-x-y) se deja para Ponchon-Savarit.

        D, B, F   : flujos molares [mol/tiempo] (mismas unidades que Q).
        R_ext     : reflujo externo (el R de siempre, L0/D).
        T_reflujo : temperatura del reflujo que vuelve a la columna; si es
                    None se asume saturado (T_reflujo = T_D, sin subenfriar).

        DHvap/Cp "de mezcla" = promedio ponderado por composicion de las
        propiedades PURAS (no hay modelo de entalpia de exceso
        disponible; es la aproximacion estandar consistente con CMO --
        sin calor de mezcla). Se toman de CalculadoraEntalpia, la misma
        que usan Ponchon-Savarit y los equipos del flowsheet.

        Cambio respecto a la version anterior: el termino de
        subenfriamiento era Cp(T_D)*(T_D - T_reflujo), o sea Cp
        congelado en T_D. Ahora es la diferencia REAL de entalpia
        h_L(T_D) - h_L(T_reflujo), que es la integral de Cp entre las dos
        temperaturas. Coinciden cuando el subenfriamiento es pequeno y se
        separan cuando es grande, que es justo cuando el termino importa.

        Devuelve Q en [J/tiempo], con 'tiempo' definido por las unidades
        en que se hayan dado D/B/F (p.ej. mol/s -> Q en W).

        Nota: 'B' y 'z_F' quedan en la firma (como se pidio) pero las
        formulas de Q_c/R_int/Q_R dadas no los usan -- solo F y q entran
        via V_barra. Se mantienen por si se agregan correcciones futuras
        (p.ej. entalpia del fondo referida a z_F).
        """
        entalpia = self.entalpia

        T_D, _ = self.calculadora_elv.burbuja_T(self.P_sistema, np.array([x_D, 1.0 - x_D]))
        T_B, _ = self.calculadora_elv.burbuja_T(self.P_sistema, np.array([x_B, 1.0 - x_B]))
        if T_reflujo is None:
            T_reflujo = T_D

        x_D_vec = np.array([x_D, 1.0 - x_D])
        x_B_vec = np.array([x_B, 1.0 - x_B])

        Hvap_D = entalpia.h_vapor(T_D, x_D_vec) - entalpia.h_liquido(T_D, x_D_vec)
        Hvap_B = entalpia.h_vapor(T_B, x_B_vec) - entalpia.h_liquido(T_B, x_B_vec)
        Cp_D = float(np.dot(x_D_vec, entalpia.capacidades_calorificas_liquido(T_D)))

        # Calor que hay que quitar de mas por devolver el reflujo frio:
        # la entalpia que le falta al liquido para estar en su burbuja.
        subenfriamiento = entalpia.h_liquido(T_D, x_D_vec) - entalpia.h_liquido(T_reflujo, x_D_vec)

        Q_c = D * (R_ext + 1.0) * (Hvap_D + subenfriamiento)
        R_int = R_ext * (1.0 + subenfriamiento / Hvap_D)
        V_barra = D * (R_int + 1.0) - F * (1.0 - q)
        Q_R = V_barra * Hvap_B

        return {
            "Q_c": Q_c, "Q_R": Q_R, "R_int": R_int, "V_barra": V_barra,
            "T_D": T_D, "T_B": T_B, "T_reflujo": T_reflujo,
            "Hvap_D": Hvap_D, "Hvap_B": Hvap_B, "Cp_D": Cp_D,
            "subenfriamiento": subenfriamiento,
        }


class SolucionadorMcCabeThiele:
    _VARIABLES_EVALUADOR = ("z_F", "q", "x_D", "x_B", "R")

    def __init__(self, evaluador):
        self.evaluador = evaluador

    def resolver(self, z_F=None, q=None, x_D=None, x_B=None, R=None, N=None,
                 condensador_parcial=False, E_MV=1.0):
        valores = {"z_F": z_F, "q": q, "x_D": x_D, "x_B": x_B, "R": R}
        incognitas = [nombre for nombre, v in valores.items() if v is None]

        if len(incognitas) == 0:
            resultado = self.evaluador.calcular_escalones(
                condensador_parcial=condensador_parcial, E_MV=E_MV, **valores
            )
            if N is not None and not np.isclose(resultado["N"], N, atol=1e-3):
                raise ValueError(
                    f"Sistema sobre-especificado e inconsistente: con estos "
                    f"z_F/q/x_D/x_B/R se obtienen N={resultado['N']:.3f} "
                    f"etapas, no el N={N} dado."
                )
            resultado["modo"] = "evaluacion_directa"
            return resultado

        if len(incognitas) > 1:
            raise ValueError(
                "Subdeterminado: calcular_escalones es UNA sola ecuacion "
                f"(N = f(z_F,q,x_D,x_B,R)); no puede resolver {len(incognitas)} "
                f"incognitas simultaneas ({incognitas}) con esta unica "
                "ecuacion. El balance de materia global (BalanceMateriaGlobal, "
                "en core/balance_materia.py) es un sistema APARTE (2 "
                "ecuaciones sobre F/D/B/z_F/x_D/x_B) -- no se combina "
                "automaticamente con este solver. Para 'que pasa si varío "
                "dos variables', usa un barrido manual."
            )

        if N is None:
            raise ValueError(
                f"Falta '{incognitas[0]}' pero no se dio N como objetivo -- "
                "no hay nada que resolver (0 ecuaciones, 1 incognita)."
            )

        incognita = incognitas[0]
        a, b = self._bracket_para(incognita, valores)

        def residuo(valor_prueba):
            candidatos = dict(valores)
            candidatos[incognita] = valor_prueba
            try:
                return self.evaluador.calcular_escalones(
                    condensador_parcial=condensador_parcial, E_MV=E_MV, **candidatos
                )["N"] - N
            except ValueError:
                return _PENALIZACION_SIGNO(valor_prueba, a, b)

        sol = root_scalar(residuo, bracket=[a, b], method="brentq")
        valores[incognita] = sol.root
        resultado = self.evaluador.calcular_escalones(
            condensador_parcial=condensador_parcial, E_MV=E_MV, **valores
        )
        resultado["modo"] = f"resuelto:{incognita}"
        resultado["valor_resuelto"] = sol.root
        resultado["convergio"] = bool(sol.converged)
        return resultado

    def _bracket_para(self, incognita, valores):
        """
        Brackets heuristicos por variable -- no hay una cota 'universal'
        para cada una (a diferencia de R, que tiene R_min como cota
        inferior natural); estas son razonables pero pueden necesitar
        ajuste segun el sistema.
        """
        eps = 1e-4
        if incognita == "R":
            R_min = self.evaluador.calcular_R_min(valores["z_F"], valores["q"], valores["x_D"])
            return R_min + eps, max(R_min * 20.0, R_min + 20.0)
        if incognita == "x_D":
            return max(valores["x_B"], valores["z_F"]) + eps, 1.0 - eps
        if incognita == "x_B":
            return eps, min(valores["x_D"], valores["z_F"]) - eps
        if incognita == "z_F":
            return valores["x_B"] + eps, valores["x_D"] - eps
        if incognita == "q":
            return -5.0, 5.0
        raise ValueError(f"Variable desconocida: {incognita}")


def _PENALIZACION_SIGNO(valor_prueba, a, b):
    """
    Si calcular_escalones falla (p.ej. R invalido a mitad de la busqueda
    de brentq), se devuelve un residuo grande con el signo que empuja a
    brentq de vuelta hacia el interior del bracket, en vez de propagar la
    excepcion y tumbar la busqueda de raiz.
    """
    punto_medio = 0.5 * (a + b)
    return 1e6 if valor_prueba < punto_medio else -1e6
