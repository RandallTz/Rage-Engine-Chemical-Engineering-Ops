"""
Ponchon-Savarit: metodo riguroso de entalpia-composicion, sin la
simplificacion de Reflujo Molar Constante (CMO) que usa McCabe-Thiele.
Reutiliza CalculadoraELV (para T de burbuja y la curva de equilibrio) y
ProveedorTermodinamico (Cp_liquido, Hvap) -- no depende de
EvaluadorMcCabeThiele: construye su propia curva y(x) internamente, del
mismo barrido de burbuja_T que ya necesita para H_L/H_V (evitar una
dependencia cruzada innecesaria entre dos "metodos academicos").

Diferencia de interfaz respecto a la directiva (deliberada): en vez de
pedir D, B, Q_c, Q_R por separado, el escalonamiento solo necesita los
COCIENTES Qc/D y QR/B (asi aparecen en H_delta_D = H_L(x_D) + Qc/D y
H_delta_B = H_L(x_B) - QR/B) -- se acepta directamente 'Qc_D' y 'QR_B'
como las cargas termicas ESPECIFICAS (por mol de D o de B), analogas al
reflujo R de McCabe-Thiele (que tampoco necesitaba D absoluto). Los
flujos absolutos D/B/Qc/QR solo hacen falta para calcular esos cocientes
o para reportar cargas termicas totales, no para la geometria del
escalonamiento en si.

Zona con numpy/scipy; el escalonamiento es iterativo (una etapa depende
de la anterior), igual que en core/mccabe_thiele.py.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.optimize import brentq, root_scalar

from thermodynamics.entalpia import entalpia_de

_MAX_ETAPAS = 200


class EvaluadorPonchonSavarit:
    def __init__(self, calculadora_elv, nombres, P_sistema=101325.0, T_ref=298.15,
                 n_puntos_curva=80):
        """
        Construye H_L(x), H_V(y) y la curva de equilibrio y(x), todas del
        MISMO barrido de composicion (para que H_L(x) y H_V(y_eq(x)) esten
        evaluadas a la misma T de burbuja -- son una linea de reparto real,
        no dos curvas independientes).

        H_L,puro(T_ref) = 0 (referencia). H_L(x,T) = suma ponderada por x
        de integral(Cp_L,i, T_ref, T). H_V(y,T) = H_L(y,T) [mismo camino:
        calentar liquido de T_ref a T] + suma ponderada por y de
        DHvap_i(T). Es la aproximacion ideal (sin entalpia de exceso),
        consistente con el resto del proyecto.
        """
        # Mismo motivo que en EvaluadorMcCabeThiele: el diagrama H-x-y es
        # binario por construccion. Se rechaza aqui, con el nombre del
        # metodo alternativo, en vez de dejar que reviente mas abajo con
        # un error de punto de burbuja que no explica nada.
        if len(nombres) != 2:
            raise ValueError(
                f"Ponchon-Savarit es un metodo BINARIO y recibio {len(nombres)} "
                f"componentes ({', '.join(nombres)}). Para una mezcla "
                "multicomponente usa FUG (Fenske-Underwood-Gilliland), que "
                "trabaja con cualquier numero de componentes especificando "
                "las recuperaciones de los dos claves."
            )

        self.calculadora_elv = calculadora_elv
        self.proveedor = calculadora_elv.proveedor
        self.nombres = nombres
        self.P_sistema = float(P_sistema)
        self.T_ref = float(T_ref)
        # La MISMA entalpia que usan el mezclador, el flash y el
        # intercambiador del flowsheet: una sola tabla por proveedor.
        self.entalpia = entalpia_de(self.proveedor, T_ref=self.T_ref)

        x1 = np.linspace(1e-4, 1.0 - 1e-4, n_puntos_curva)
        HL = np.empty(n_puntos_curva)
        HV = np.empty(n_puntos_curva)
        y1 = np.empty(n_puntos_curva)
        for i, x in enumerate(x1):  # bucle permitido: burbuja_T es una composicion a la vez
            T, y_vapor = calculadora_elv.burbuja_T(P_sistema, np.array([x, 1.0 - x]))
            HL[i] = self._entalpia_liquido(np.array([x, 1.0 - x]), T)
            y1[i] = y_vapor[0]
            HV[i] = self._entalpia_vapor(y_vapor, T)

        # extremos exactos en los componentes puros, en su propio punto de
        # ebullicion (Tb) -- sin pasar por UNIFAC/burbuja_T, que se porta
        # mal justo en x=0 o x=1 (fraccion molar cero de un componente).
        Tb0 = self.proveedor.componentes[0].Tb
        Tb1 = self.proveedor.componentes[1].Tb
        HL0 = self._entalpia_liquido(np.array([0.0, 1.0]), Tb1)
        HV0 = self._entalpia_vapor(np.array([0.0, 1.0]), Tb1)
        HL1 = self._entalpia_liquido(np.array([1.0, 0.0]), Tb0)
        HV1 = self._entalpia_vapor(np.array([1.0, 0.0]), Tb0)

        x_ext = np.concatenate([[0.0], x1, [1.0]])
        HL_ext = np.concatenate([[HL0], HL, [HL1]])
        y_ext = np.concatenate([[0.0], y1, [1.0]])
        HV_ext = np.concatenate([[HV0], HV, [HV1]])

        self._spline_HL = CubicSpline(x_ext, HL_ext)
        orden = np.argsort(y_ext)
        self._spline_HV = CubicSpline(y_ext[orden], HV_ext[orden])
        self._spline_y_eq = PchipInterpolator(x_ext, y_ext)

    def _entalpia_liquido(self, x_vec, T):
        """
        Delegado a CalculadoraEntalpia (camino y referencia identicos a
        los que tenia aqui). Antes se integraba con quad sobre el Cp de
        la MEZCLA, una cuadratura por cada punto del barrido; ahora la
        integral esta tabulada por componente puro y esto es un producto
        punto. Verificado que coincide con la quad anterior a 1e-10
        relativo (tests/validar_entalpia.py, comprobacion 3).
        """
        return self.entalpia.h_liquido(T, x_vec)

    def _entalpia_vapor(self, y_vec, T):
        return self.entalpia.h_vapor(T, y_vec)

    def H_L(self, x):
        return float(self._spline_HL(x))

    def H_V(self, y):
        return float(self._spline_HV(y))

    def y_equilibrio(self, x):
        return float(self._spline_y_eq(x))

    def H_F_desde_q(self, z_F, q):
        """
        Conversion de conveniencia q -> H_F. Aproximacion: usa H_L(z_F) y
        H_V(z_F) (las mismas splines de la curva de equilibrio) como
        "z_F liquido saturado"/"z_F vapor saturado". Rigurosamente
        H_V(z_F) deberia evaluarse en el punto de ROCIO de z_F (T distinta
        a la de burbuja, salvo azeotropo), y no se implemento aqui un
        solver de rocio aparte -- si se necesita H_F riguroso, se pasa
        directo en vez de derivarlo de q.
        """
        HL_zF, HV_zF = self.H_L(z_F), self.H_V(z_F)
        return HL_zF + (1.0 - q) * (HV_zF - HL_zF)

    def calcular_polos(self, z_F, x_D, x_B, Qc_D, QR_B, H_F=None, q=None,
                        tolerancia_colinealidad=1e-3):
        """
        H_delta_D = H_L(x_D) + Qc_D ; H_delta_B = H_L(x_B) - QR_B.

        Verifica que (x_D,H_delta_D), (z_F,H_F) y (x_B,H_delta_B) sean
        colineales -- consecuencia del balance de energia GLOBAL de la
        columna (F*H_F + Q_R = D*H_D + B*H_B + Q_c). Si Qc_D/QR_B/H_F no
        son mutuamente consistentes con ese balance, esto falla, que es
        la senal correcta (mejor que dibujar un diagrama incorrecto).

        Nota sobre la tolerancia: la directiva pedia 1e-6 ABSOLUTO sobre
        la diferencia de pendientes, pero las entalpias aqui son de orden
        10^4-10^5 J/mol, asi que las pendientes tambien lo son -- 1e-6
        absoluto es, en la practica, exigir igualdad casi exacta en doble
        precision (ni el redondeo de un spline lo cumple). Se uso una
        tolerancia RELATIVA (rtol) en su lugar, con 1e-3 como default.
        """
        if H_F is None:
            if q is None:
                raise ValueError("Debes dar H_F o q (para derivar H_F via H_F_desde_q).")
            H_F = self.H_F_desde_q(z_F, q)

        H_delta_D = self.H_L(x_D) + Qc_D
        H_delta_B = self.H_L(x_B) - QR_B

        m1 = (H_F - H_delta_D) / (z_F - x_D)
        m2 = (H_delta_B - H_F) / (x_B - z_F)
        if not np.isclose(m1, m2, rtol=tolerancia_colinealidad):
            raise ValueError(
                "Delta_D, (z_F,H_F) y Delta_B no son colineales dentro de "
                f"rtol={tolerancia_colinealidad}: pendiente Delta_D->F={m1:.2f}, "
                f"pendiente F->Delta_B={m2:.2f}. Qc_D, QR_B y H_F deben ser "
                "mutuamente consistentes con el balance de energia global "
                "de la columna (F*H_F + Q_R = D*H_D + B*H_B + Q_c)."
            )
        return {
            "x_delta_D": x_D, "H_delta_D": H_delta_D,
            "x_delta_B": x_B, "H_delta_B": H_delta_B,
            "z_F": z_F, "H_F": H_F,
        }

    def derivar_QR_B(self, z_F, x_D, x_B, Qc_D, H_F):
        """
        Dado Qc_D (la unica incognita 'libre', analoga a R en McCabe-
        Thiele), deriva el QR_B que hace a Delta_D, (z_F,H_F) y Delta_B
        EXACTAMENTE colineales -- QR_B no es una segunda incognita
        independiente, esta atado a Qc_D por el balance de energia global.
        """
        H_delta_D = self.H_L(x_D) + Qc_D
        pendiente = (H_F - H_delta_D) / (z_F - x_D)
        H_delta_B = H_delta_D + pendiente * (x_B - x_D)
        return self.H_L(x_B) - H_delta_B

    def calcular_Qc_D_min(self, z_F, x_D, x_B, H_F, tolerancia=1e-3, max_iter=60):
        """
        Busqueda NUMERICA (biseccion) del Qc_D minimo por debajo del cual
        calcular_escalones hace pinch -- el equivalente de R_min en
        McCabe-Thiele. A diferencia de R_min (formula cerrada, interseccion
        de la linea q con la curva de equilibrio), en Ponchon-Savarit el
        punto de pinch no tiene una formula algebraica simple en general
        (no necesariamente coincide con z_F), asi que se ubica probando
        exito/fracaso de calcular_escalones directamente.

        Asume (verificado en las pruebas) que la factibilidad es monotona:
        si un Qc_D funciona, cualquier Qc_D mayor tambien funciona.
        """
        def factible(Qc_D):
            QR_B = self.derivar_QR_B(z_F, x_D, x_B, Qc_D, H_F)
            try:
                # _diagnosticar=False: sin esto, cada intento fallido de la
                # biseccion (hasta ~60) dispararia SU PROPIA busqueda de
                # Qc_D_min para armar un mensaje de error -- que a su vez
                # hace hasta 60 intentos mas. Aqui solo interesa el
                # booleano exito/fracaso, no un mensaje.
                self.calcular_escalones(z_F, x_D, x_B, Qc_D, QR_B, H_F=H_F, _diagnosticar=False)
                return True
            except (RuntimeError, ValueError):
                return False

        Hvap_D_aprox = self.H_V(x_D) - self.H_L(x_D)
        alto = max(Hvap_D_aprox, 1.0)
        intentos_expansion = 0
        while not factible(alto) and intentos_expansion < 25:
            alto *= 2.0
            intentos_expansion += 1
        if not factible(alto):
            raise RuntimeError(
                "No se encontro ningun Qc_D factible ni ampliando la busqueda "
                "25 veces -- revisa z_F/x_D/x_B/H_F."
            )

        bajo = 1e-6
        if factible(bajo):
            return bajo  # caso raro: casi cualquier Qc_D alcanza

        for _ in range(max_iter):
            medio = 0.5 * (bajo + alto)
            if factible(medio):
                alto = medio
            else:
                bajo = medio
            if (alto - bajo) < tolerancia * alto:
                break
        return alto

    def calcular_escalones(self, z_F, x_D, x_B, Qc_D, QR_B, H_F=None, q=None,
                            tolerancia_colinealidad=1e-3, _diagnosticar=True):
        """
        Escalona desde (x_D, H_L(x_D)) hasta cruzar x_B, alternando el
        paso de equilibrio (tie-line: y_actual -> x_actual via la curva
        y(x)) con el paso operativo (recta desde el polo activo -- Delta_D
        o Delta_B -- a traves del punto recien hallado, hasta cortar la
        OTRA curva de saturacion). El polo activo cambia de Delta_D a
        Delta_B cuando la pendiente operativa local supera la pendiente
        global Delta_D-Delta_B (verificado numericamente el sentido de
        esta comparacion antes de darla por buena).

        _diagnosticar: si el escalonamiento falla (pinch -- Qc_D por
        debajo del minimo), busca Qc_D_min numericamente para dar un
        mensaje claro, igual que "R<=R_min" en McCabe-Thiele -- pero aqui
        Qc_D_min no tiene formula cerrada (ver calcular_Qc_D_min), asi
        que se ubica SOLO cuando de verdad hace falta (en el camino de
        error), no en cada llamada. calcular_Qc_D_min pasa
        _diagnosticar=False en sus propias llamadas internas para no
        disparar una busqueda anidada por cada intento de su biseccion.
        """
        if not (0.0 < x_B < z_F < x_D < 1.0):
            raise ValueError(
                f"Se requiere 0 < x_B < z_F < x_D < 1 (recibido x_B={x_B}, "
                f"z_F={z_F}, x_D={x_D})."
            )

        polos = self.calcular_polos(
            z_F, x_D, x_B, Qc_D, QR_B, H_F=H_F, q=q,
            tolerancia_colinealidad=tolerancia_colinealidad,
        )
        H_delta_D, H_delta_B = polos["H_delta_D"], polos["H_delta_B"]
        H_F_resuelto = polos["H_F"]
        m_global = (H_delta_D - H_delta_B) / (x_D - x_B)

        def paso_operativo(x_actual, H_actual, x_piv, H_piv):
            m = (H_piv - H_actual) / (x_piv - x_actual)
            residuo = lambda y: self.H_V(y) - (H_actual + m * (y - x_actual))
            y_nuevo = brentq(residuo, 1e-9, 1.0 - 1e-9)
            return y_nuevo, m

        # Punto de partida: y_actual=x_D representa el VAPOR que sale del
        # primer plato (condensador total: y_1 = x_D). Va en la curva de
        # VAPOR (H_V(x_D)), no en la liquida -- ese fue justamente el bug
        # de graficacion que se corrigio aqui (antes se ploteaba
        # (x_D, H_L(x_D)), el reflujo/destilado liquido, como si fuera el
        # arranque de la cascada de equilibrio, que en realidad empieza
        # del lado del vapor).
        puntos = [(x_D, self.H_V(x_D))]
        tie_lines = []       # cada una: (x, H_L(x), y, H_V(y)) -- reparto/equilibrio
        lineas_operativas = []  # cada una: (x_polo, H_polo, x, H_L(x), y, H_V(y))
        y_actual = x_D
        x_prev = x_D
        pivote_es_D = True
        N_enteras = 0

        try:
            for _ in range(_MAX_ETAPAS):
                x_actual = brentq(lambda x: self.y_equilibrio(x) - y_actual, 1e-9, 1.0 - 1e-9)
                H_actual = self.H_L(x_actual)

                if x_actual <= x_B:
                    # Este ultimo paso de equilibrio se "pasa" de x_B (liquido
                    # mas puro de lo necesario) -- NO se agrega el punto de
                    # sobrepaso x_actual; se trunca directo en x_B, tanto en
                    # la escalera como en la linea de reparto de esta etapa
                    # (antes se agregaban AMBOS puntos, x_actual y x_B, y la
                    # escalera hacia un zigzag raro yendo mas alla y luego
                    # "regresando").
                    if np.isclose(x_prev, x_actual):
                        fraccion = 1.0
                    else:
                        fraccion = (x_prev - x_B) / (x_prev - x_actual)
                        fraccion = float(np.clip(fraccion, 0.0, 1.0))
                    N_total = N_enteras + fraccion
                    H_L_xB = self.H_L(x_B)
                    puntos.append((x_B, H_L_xB))
                    tie_lines.append((x_B, H_L_xB, y_actual, self.H_V(y_actual)))
                    return {
                        "N": N_total,
                        "puntos": np.array(puntos),
                        "tie_lines": tie_lines,
                        "lineas_operativas": lineas_operativas,
                        "polos": polos,
                        "z_F": z_F, "x_D": x_D, "x_B": x_B,
                        "Qc_D": Qc_D, "QR_B": QR_B,
                    }

                puntos.append((x_actual, H_actual))
                tie_lines.append((x_actual, H_actual, y_actual, self.H_V(y_actual)))

                N_enteras += 1
                x_piv, H_piv = (x_D, H_delta_D) if pivote_es_D else (x_B, H_delta_B)
                y_nuevo, m = paso_operativo(x_actual, H_actual, x_piv, H_piv)

                # Nota: la pendiente m parte muy por ENCIMA de m_global (pivote D,
                # cerca de x_D) y decrece monotonamente etapa a etapa -- el
                # cambio de seccion ocurre cuando m CAE por debajo de m_global,
                # no cuando lo supera (lo opuesto de lo que decia la directiva
                # literalmente; verificado numericamente: con el sentido ">"
                # el cambio se disparaba en la primerisima etapa, todavia
                # pegado a x_D, lo cual es fisicamente incorrecto).
                if pivote_es_D and m < m_global:
                    pivote_es_D = False
                    x_piv, H_piv = x_B, H_delta_B
                    y_nuevo, m = paso_operativo(x_actual, H_actual, x_B, H_delta_B)

                lineas_operativas.append((x_piv, H_piv, x_actual, H_actual, y_nuevo, self.H_V(y_nuevo)))
                puntos.append((y_nuevo, self.H_V(y_nuevo)))
                x_prev = x_actual
                y_actual = y_nuevo

            raise RuntimeError(
                f"No se alcanzo x_B tras {_MAX_ETAPAS} etapas -- revisa Qc_D/QR_B/x_B/x_D."
            )
        except (ValueError, RuntimeError) as e:
            # Antes esto dejaba escapar el "f(a) and f(b) must have
            # different signs" crudo de scipy (o el RuntimeError generico
            # de arriba) sin decir POR QUE -- el mismo tipo de fallo que ya
            # se habia resuelto para McCabe-Thiele (R<=R_min). Aqui no hay
            # formula cerrada para el minimo, asi que se ubica numericamente
            # (calcular_Qc_D_min) SOLO en este camino de error, no en cada
            # llamada normal -- por eso _diagnosticar existe y por eso
            # calcular_Qc_D_min llama a calcular_escalones con
            # _diagnosticar=False (si no, cada uno de sus ~60 intentos de
            # biseccion dispararia otra busqueda anidada de Qc_D_min).
            if not _diagnosticar:
                raise
            try:
                Qc_D_min = self.calcular_Qc_D_min(z_F, x_D, x_B, H_F_resuelto)
            except RuntimeError:
                raise ValueError(
                    f"El escalonamiento no converge con Qc_D={Qc_D:.6g} ({e}). "
                    "Revisa z_F/x_D/x_B/Qc_D."
                ) from e
            if Qc_D < Qc_D_min * (1 - 1e-6):
                raise ValueError(
                    f"Qc_D={Qc_D:.6g} esta por debajo del minimo requerido "
                    f"(Qc_D_min≈{Qc_D_min:.6g}): produce un pinch, necesitaria "
                    "etapas infinitas. Sube Qc_D."
                ) from e
            raise ValueError(
                f"El escalonamiento no converge con Qc_D={Qc_D:.6g}, aunque esta por "
                f"encima del minimo estimado (Qc_D_min≈{Qc_D_min:.6g}): {e}"
            ) from e

    def graficar_diagrama(self, resultado, titulo=None):
        """
        Diagrama H-x-y completo: curvas de saturacion, polos, la linea
        global Delta_D-Delta_B, Y ADEMAS -- por cada etapa -- su recta
        operativa COMPLETA (desde el polo activo hasta la curva de vapor,
        pasando por el punto liquido) y su linea de reparto/equilibrio
        (conectando el liquido x_n con su vapor conjugado y_n a la misma
        T). Antes solo se dibujaba el zigzag entre puntos consecutivos
        (geometricamente las mismas rectas, pero truncadas: no llegaban
        hasta el polo ni distinguian equilibrio de operativa).
        """
        polos = resultado["polos"]
        x_D, x_B, z_F = resultado["x_D"], resultado["x_B"], resultado["z_F"]
        puntos = resultado["puntos"]

        malla_x = np.linspace(0.0, 1.0, 250)
        malla_HL = np.array([self.H_L(x) for x in malla_x])
        malla_HV = np.array([self.H_V(x) for x in malla_x])

        fig, ax = plt.subplots(figsize=(9, 8))
        ax.plot(malla_x, malla_HL, color="tab:blue", linewidth=2, label="$H_L(x)$ líquido saturado", zorder=3)
        ax.plot(malla_x, malla_HV, color="tab:red", linewidth=2, label="$H_V(y)$ vapor saturado", zorder=3)

        # Lineas operativas completas: polo -> punto liquido -> vapor nuevo
        # (los tres son colineales por construccion; se dibuja la recta
        # entera para que se vea el abanico converger en el polo, como en
        # el diagrama de referencia).
        for i, (x_piv, H_piv, x_act, H_act, y_nue, H_vnue) in enumerate(resultado["lineas_operativas"]):
            etiqueta = "Línea operativa" if i == 0 else None
            ax.plot([x_piv, y_nue], [H_piv, H_vnue], color="black", linewidth=0.7,
                    alpha=0.8, zorder=2, label=etiqueta)

        # Lineas de reparto (equilibrio): liquido x_n <-> su vapor conjugado y_n
        for i, (x_eq, H_eq, y_eq, H_yeq) in enumerate(resultado["tie_lines"]):
            etiqueta = "Línea de reparto (equilibrio)" if i == 0 else None
            ax.plot([x_eq, y_eq], [H_eq, H_yeq], color="tab:orange", linewidth=1.0,
                    linestyle="-", alpha=0.9, zorder=4, label=etiqueta)

        ax.scatter([polos["x_delta_D"]], [polos["H_delta_D"]], color="tab:green", marker="^",
                   s=150, zorder=6, label=r"$\Delta_D$")
        ax.scatter([polos["x_delta_B"]], [polos["H_delta_B"]], color="tab:purple", marker="v",
                   s=150, zorder=6, label=r"$\Delta_B$")
        ax.plot([polos["x_delta_D"], polos["x_delta_B"]],
                [polos["H_delta_D"], polos["H_delta_B"]],
                color="gray", linestyle="--", linewidth=1, label=r"Línea global $\Delta_D$-$\Delta_B$", zorder=2)
        ax.scatter([z_F], [polos["H_F"]], color="darkmagenta", marker="s", s=80, zorder=6,
                   label="Alimentación (z_F,H_F)")

        # Escalera: la misma trayectoria de siempre conectando los vertices
        # en secuencia (x_D -> x1 -> y1 -> x2 -> ...) -- se habia quitado
        # al agregar el abanico/reparto y se repone, ahora en un estilo
        # distinto para no confundirla con las lineas operativas.
        ax.plot(puntos[:, 0], puntos[:, 1], color="black", linewidth=1.3,
                linestyle="-", zorder=5)
        ax.scatter(puntos[:, 0], puntos[:, 1], color="black", s=20, zorder=6,
                   label=f"Escalera (N={resultado['N']:.2f})")

        for x_ref, etiqueta in [(x_D, "x_D"), (x_B, "x_B"), (z_F, "z_F")]:
            ax.axvline(x_ref, color="gray", linestyle=":", linewidth=0.6)
            ax.annotate(etiqueta, (x_ref, 1.0), xycoords=("data", "axes fraction"),
                        fontsize=9, ha="center", va="bottom", color="gray")

        y_min = min(polos["H_delta_B"], malla_HL.min())
        y_max = max(polos["H_delta_D"], malla_HV.max())
        margen = 0.05 * (y_max - y_min)
        ax.set_xlim(0, 1)
        ax.set_ylim(y_min - margen, y_max + margen)
        ax.set_xlabel(f"x, y ({self.nombres[0]})")
        ax.set_ylabel("H [J/mol]")
        ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5))
        ax.grid(alpha=0.3)
        ax.set_title(titulo or f"Ponchon-Savarit — N={resultado['N']:.2f}", fontsize=12)
        plt.tight_layout()
        plt.show()


class SolucionadorPonchonSavarit:
    """
    Igual patron EO de grados de libertad que SolucionadorMcCabeThiele.
    calcular_escalones(z_F,x_D,x_B,Qc_D,QR_B) -> N sigue siendo UNA sola
    ecuacion -- pero aqui QR_B NO es una incognita independiente: esta
    atado a Qc_D por la colinealidad de los polos (ver derivar_QR_B), asi
    que las variables 'libres' del evaluador son (z_F, x_D, x_B, Qc_D),
    exactamente 4, igual que las 5 de McCabe-Thiele menos R que aqui es
    Qc_D. Solo se puede resolver UNA incognita entre esas 4 a la vez,
    dado N.
    """
    _VARIABLES_EVALUADOR = ("z_F", "x_D", "x_B", "Qc_D")

    def __init__(self, evaluador):
        self.evaluador = evaluador

    def _evaluar(self, z_F, x_D, x_B, Qc_D, H_F):
        QR_B = self.evaluador.derivar_QR_B(z_F, x_D, x_B, Qc_D, H_F)
        return self.evaluador.calcular_escalones(z_F, x_D, x_B, Qc_D, QR_B, H_F=H_F)

    def resolver(self, z_F=None, x_D=None, x_B=None, Qc_D=None, H_F=None, q=None, N=None):
        if H_F is None:
            if q is None:
                raise ValueError("Debes dar H_F o q (para derivar H_F via H_F_desde_q).")
            # H_F depende de z_F: si z_F es la incognita, se recalcula mas
            # abajo en cada intento del solver; si no, se fija una vez aqui.
            H_F_fijo = None if z_F is None else self.evaluador.H_F_desde_q(z_F, q)
        else:
            H_F_fijo = H_F

        valores = {"z_F": z_F, "x_D": x_D, "x_B": x_B, "Qc_D": Qc_D}
        incognitas = [nombre for nombre, v in valores.items() if v is None]

        if len(incognitas) == 0:
            H_F_local = H_F_fijo if H_F_fijo is not None else self.evaluador.H_F_desde_q(z_F, q)
            resultado = self._evaluar(z_F, x_D, x_B, Qc_D, H_F_local)
            if N is not None and not np.isclose(resultado["N"], N, atol=1e-3):
                raise ValueError(
                    "Sistema sobre-especificado e inconsistente: con estos "
                    f"z_F/x_D/x_B/Qc_D se obtienen N={resultado['N']:.3f} "
                    f"etapas, no el N={N} dado."
                )
            resultado["modo"] = "evaluacion_directa"
            return resultado

        if len(incognitas) > 1:
            raise ValueError(
                "Subdeterminado: calcular_escalones es UNA sola ecuacion "
                f"(N = f(z_F,x_D,x_B,Qc_D), con QR_B derivado por colinealidad, "
                f"no libre); no puede resolver {len(incognitas)} incognitas "
                f"simultaneas ({incognitas})."
            )

        if N is None:
            raise ValueError(
                f"Falta '{incognitas[0]}' pero no se dio N como objetivo -- "
                "no hay nada que resolver (0 ecuaciones, 1 incognita)."
            )

        incognita = incognitas[0]
        a, b = self._bracket_para(incognita, valores, H_F_fijo, q)

        def residuo(valor_prueba):
            candidatos = dict(valores)
            candidatos[incognita] = valor_prueba
            H_F_local = (
                H_F_fijo if H_F_fijo is not None
                else self.evaluador.H_F_desde_q(candidatos["z_F"], q)
            )
            try:
                return self._evaluar(
                    candidatos["z_F"], candidatos["x_D"], candidatos["x_B"],
                    candidatos["Qc_D"], H_F_local,
                )["N"] - N
            except (ValueError, RuntimeError):
                # reutiliza el bracket [a,b] ya calculado -- NO lo vuelve a
                # calcular (evitaria recorrer la biseccion de Qc_D_min en
                # cada evaluacion fallida de brentq, muy costoso).
                return _PENALIZACION_SIGNO(valor_prueba, a, b)

        sol = root_scalar(residuo, bracket=[a, b], method="brentq")

        valores[incognita] = sol.root
        H_F_local = H_F_fijo if H_F_fijo is not None else self.evaluador.H_F_desde_q(valores["z_F"], q)
        resultado = self._evaluar(valores["z_F"], valores["x_D"], valores["x_B"], valores["Qc_D"], H_F_local)
        resultado["modo"] = f"resuelto:{incognita}"
        resultado["valor_resuelto"] = sol.root
        resultado["convergio"] = bool(sol.converged)
        return resultado

    def _bracket_para(self, incognita, valores, H_F_fijo, q):
        eps = 1e-4
        if incognita == "Qc_D":
            H_F_local = H_F_fijo if H_F_fijo is not None else self.evaluador.H_F_desde_q(valores["z_F"], q)
            Qc_D_min = self.evaluador.calcular_Qc_D_min(
                valores["z_F"], valores["x_D"], valores["x_B"], H_F_local
            )
            return Qc_D_min * 1.01, max(Qc_D_min * 30.0, Qc_D_min + 30.0)
        if incognita == "x_D":
            return max(valores["x_B"], valores["z_F"]) + eps, 1.0 - eps
        if incognita == "x_B":
            return eps, min(valores["x_D"], valores["z_F"]) - eps
        if incognita == "z_F":
            return valores["x_B"] + eps, valores["x_D"] - eps
        raise ValueError(f"Variable desconocida: {incognita}")


def _PENALIZACION_SIGNO(valor_prueba, a, b):
    punto_medio = 0.5 * (a + b)
    return 1e6 if valor_prueba < punto_medio else -1e6
