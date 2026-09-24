"""
Deteccion de nodos azeotropicos (equilibrio quimico y control cinetico)
via root-finding matricial (scipy.optimize.root), reutilizando
CalculadoraELV, GestorReaccion y EspacioReactivo ya construidos.

Nota de duplicacion (deliberada, temporal): encontrar_azeotropo_equilibrio
reimplementa el mismo root-find anidado sobre x_k que
ThermodynamicEngine.generar_curva_residual_equilibrio (core/topology.py)
usa para reconstruir x real desde X. Es la misma logica fisica en dos
archivos -- candidato claro a extraerse a un helper compartido si un
tercer consumidor la vuelve a necesitar. Por ahora se deja duplicada tal
como se pidio explicitamente.

Zona libre de pint: solo floats/np.ndarray en SI.
"""

import numpy as np
import matplotlib.pyplot as plt
import ternary
from scipy.optimize import root, root_scalar

_PENALIZACION = 1e6  # residual devuelto cuando un punto de prueba es invalido
_TOLERANCIA_RESIDUAL = 1e-6  # scipy puede marcar success=True con residual no despreciable


class BuscadorAzeotropos:
    def __init__(self, calculadora_elv, gestor_reaccion, espacio_reactivo):
        """
        calculadora_elv  : CalculadoraELV (burbuja_P, burbuja_T).
        gestor_reaccion  : GestorReaccion (K_eq(T), velocidad_reaccion).
        espacio_reactivo : EspacioReactivo (transformar/inversa, nu, k, nu_tot).

        No se inyecta ProveedorTermodinamico aparte: se reutiliza el que
        ya tiene CalculadoraELV (calculadora_elv.proveedor) para pedir
        coeficientes de actividad directamente, en vez de agregar una
        cuarta dependencia al constructor.
        """
        self.calculadora_elv = calculadora_elv
        self.gestor_reaccion = gestor_reaccion
        self.espacio_reactivo = espacio_reactivo
        self.proveedor = calculadora_elv.proveedor

    # ------------------------------------------------------------------
    # 1. Azeotropo de EQUILIBRIO QUIMICO, en el espacio transformado X
    # ------------------------------------------------------------------
    def encontrar_azeotropo_equilibrio(self, X_guess, P_sistema):
        """
        Busca X* tal que R(X*) = X* - Y*(X*) = 0.

        X tiene, en realidad, n-2 grados de libertad (no n-1): ademas de
        X_k = 0 (identicamente, por construccion de EspacioReactivo), se
        cumple sum(X excluyendo k) = 1 para cualquier X que provenga de un
        x fisico real (demostrado y verificado en core/transformaciones.py).
        Un root-finder que solo elimina X_k y deja libres las otras n-1
        componentes puede vagar por X's que no respetan esa suma, y
        entonces EspacioReactivo.inversa() reconstruye un x que ni
        siquiera suma 1 -- se reprodujo exactamente ese fallo antes de
        esta correccion. Por eso aqui se elimina UNA componente adicional
        (la ultima de las libres), reconstruida como 1 - suma(las demas),
        dejando solo n-2 variables realmente independientes para el
        solver (p.ej. una sola variable escalar en un sistema ternario:
        el espacio transformado de una reaccion ternaria es una LINEA).

        Devuelve un dict con X, x (reconstruido), T y diagnostico de
        convergencia de scipy.optimize.root.
        """
        espacio = self.espacio_reactivo
        nu = espacio.nu
        k = espacio.k
        indices_libres = [i for i in range(len(nu)) if i != k]
        idx_dependiente = indices_libres[-1]
        indices_independientes = indices_libres[:-1]

        def residual_xk(x_k, X):
            x_prueba = espacio.inversa(X, x_k)
            T_prueba, _ = self.calculadora_elv.burbuja_T(P_sistema, x_prueba)
            gamma_prueba = self.proveedor.coeficientes_actividad(T_prueba, x_prueba)
            actividades = x_prueba * gamma_prueba
            K_prueba = self.gestor_reaccion.K_eq(T_prueba)
            return K_prueba - np.prod(np.power(actividades, nu))

        def bracket_valido(X, n_muestras=60):
            candidatos = np.linspace(1e-6, 1.0 - 1e-6, n_muestras)
            xk_prev, resid_prev = None, None
            for xk in candidatos:
                x_prueba = espacio.inversa(X, xk)
                if np.any(x_prueba < 0.0) or np.any(x_prueba > 1.0):
                    xk_prev, resid_prev = None, None
                    continue
                try:
                    resid = residual_xk(xk, X)
                except ValueError:
                    xk_prev, resid_prev = None, None
                    continue
                if resid_prev is not None and np.sign(resid) != np.sign(resid_prev):
                    return xk_prev, xk
                xk_prev, resid_prev = xk, resid
            raise RuntimeError(
                f"No se encontro un sub-intervalo fisico de x_k para X={X}."
            )

        def x_y_T_de(X):
            a, b = bracket_valido(X)
            sol_xk = root_scalar(residual_xk, args=(X,), bracket=[a, b], method='brentq')
            x_real = espacio.inversa(X, sol_xk.root)
            T_real, y_vapor = self.calculadora_elv.burbuja_T(P_sistema, x_real)
            return x_real, y_vapor, T_real

        def reconstruir_X(X_independiente):
            X = np.zeros(len(nu))
            X[indices_independientes] = X_independiente
            X[idx_dependiente] = 1.0 - np.sum(X_independiente)
            return X

        def residual_reducido(X_independiente):
            X = reconstruir_X(X_independiente)
            try:
                _, y_vapor, _ = x_y_T_de(X)
            except (ValueError, RuntimeError):
                return np.full(len(indices_independientes), _PENALIZACION)
            Y_estrella = espacio.transformar(y_vapor)
            return (X - Y_estrella)[indices_independientes]

        X_guess = np.asarray(X_guess, dtype=float)
        sol = root(residual_reducido, X_guess[indices_independientes], method='hybr')

        X_azeotropo = reconstruir_X(sol.x)
        try:
            x_azeotropo, _, T_azeotropo = x_y_T_de(X_azeotropo)
        except (ValueError, RuntimeError) as e:
            return {
                "X": X_azeotropo, "x": None, "T": None,
                "convergio": False, "mensaje": f"solucion final invalida: {e}",
                "residual_max": None,
            }

        residual_max = float(np.max(np.abs(sol.fun)))
        return {
            "X": X_azeotropo,
            "x": x_azeotropo,
            "T": T_azeotropo,
            # sol.success de scipy NO garantiza residual chico (puede terminar
            # por xtol con el residual todavia grande) -- se exige ademas
            # residual_max < tolerancia para reportar convergencia real.
            "convergio": bool(sol.success) and residual_max < _TOLERANCIA_RESIDUAL,
            "mensaje": sol.message,
            "residual_max": residual_max,
        }

    # ------------------------------------------------------------------
    # 2. Azeotropo bajo control CINETICO, en el espacio real x
    # ------------------------------------------------------------------
    def encontrar_azeotropo_cinetico(self, x_guess, Da, P_sistema=101325.0):
        """
        Busca x* tal que R(x*) = (x*-y*(x*)) + Da*r*(nu - nu_tot*x*) = 0,
        eliminando el ultimo componente del solver (las fracciones son
        linealmente dependientes por sum(x_i)=1) y reconstruyendolo como
        1 - sum(resto), normalizando el vector completo por si acaso.

        Nota: P_sistema no estaba en la firma pedida pero CalculadoraELV.
        burbuja_T la requiere; se agrega con un valor por defecto (1 atm)
        en vez de asumirla en silencio (mismo criterio que en
        generar_curva_residual_cinetica).

        Devuelve un dict con x, T y diagnostico de convergencia.
        """
        nu = self.espacio_reactivo.nu
        nu_tot = self.espacio_reactivo.nu_tot
        n = len(nu)

        def reconstruir_x(x_reducido):
            ultimo = 1.0 - np.sum(x_reducido)
            x = np.concatenate([x_reducido, [ultimo]])
            return x / np.sum(x)

        def residual_reducido(x_reducido):
            x = reconstruir_x(x_reducido)
            try:
                T_burbuja, y_vapor = self.calculadora_elv.burbuja_T(P_sistema, x)
            except ValueError:
                return np.full(n - 1, _PENALIZACION)
            r = self.gestor_reaccion.velocidad_reaccion(T_burbuja, x)
            R = (x - y_vapor) + Da * r * (nu - nu_tot * x)
            return R[:-1]

        x_guess = np.asarray(x_guess, dtype=float)
        sol = root(residual_reducido, x_guess[:-1], method='hybr')

        x_azeotropo = reconstruir_x(sol.x)
        try:
            T_azeotropo, _ = self.calculadora_elv.burbuja_T(P_sistema, x_azeotropo)
        except ValueError as e:
            return {
                "x": x_azeotropo, "T": None,
                "convergio": False, "mensaje": f"solucion final invalida: {e}",
                "residual_max": None,
            }

        residual_max = float(np.max(np.abs(sol.fun)))
        return {
            "x": x_azeotropo,
            "T": T_azeotropo,
            "convergio": bool(sol.success) and residual_max < _TOLERANCIA_RESIDUAL,
            "mensaje": sol.message,
            "residual_max": residual_max,
        }

    # ------------------------------------------------------------------------------
    # 3. Visualizacion: diagrama ternario con los azeotropos encontrados
    # ------------------------------------------------------------------
    def graficar_azeotropos(self, resultados, nombres_componentes, motor=None,
                             T_actual=None, n_puntos=150, max_etapas=150,
                             titulo=None):
        """
        Dibuja un diagrama ternario marcando los nodos azeotropicos
        encontrados por encontrar_azeotropo_cinetico/_equilibrio.

        resultados : un dict (o lista de dicts) como los que devuelven esos
            dos metodos -- necesitan al menos la clave 'x'; si tienen
            'T'/'convergio'/'mensaje' se usan para la leyenda y el estilo
            del marcador. Se le puede agregar la clave 'etiqueta' a cada
            dict (antes de pasarlo) para identificarlo en la leyenda, p.ej.
            resultado['etiqueta'] = 'cinetico Da=5'.
        nombres_componentes : lista de 3 nombres, para las esquinas.
        motor : instancia opcional de ThermodynamicEngine -- si se pasa
            (junto con T_actual), se dibujan de fondo trayectorias
            reactivas (draw_reactive_line) para dar contexto, igual que en
            ThermodynamicEngine.plot_ternary. Sin 'motor', el diagrama
            muestra solo los ejes y los azeotropos.

        Puntos con 'convergio' False (o sin esa clave) se marcan en gris
        con una 'x' y se etiquetan "NO convergio" -- no se descartan
        silenciosamente, para que quede visible tambien donde NO se
        encontro un azeotropo (como el caso de equilibrio quimico de este
        sistema MTBE, que es un resultado real, no un error a esconder).
        """
        if isinstance(resultados, dict):
            resultados = [resultados]

        figura, tax = ternary.figure(scale=1.0)
        figura.set_size_inches(9, 8)
        tax.boundary(linewidth=2.0)
        tax.gridlines(multiple=0.1, color="gray", linestyle="--", linewidth=0.5)

        if motor is not None:
            if T_actual is None:
                raise ValueError("Si pasas 'motor' tambien debes pasar 'T_actual'.")
            puntos_iniciales = np.random.dirichlet((1, 1, 1), size=n_puntos)
            for x_ini in puntos_iniciales:
                historial = motor.draw_reactive_line(
                    x_inicial=x_ini, T_actual=T_actual, max_etapas=max_etapas
                )
                tax.plot(historial, linewidth=1.0, color="blue", alpha=0.25, zorder=1)

        estilos = [
            dict(marker="*", color="red", s=260),
            dict(marker="X", color="black", s=160),
            dict(marker="P", color="darkorange", s=160),
            dict(marker="D", color="purple", s=140),
        ]

        for i, resultado in enumerate(resultados):
            x = resultado.get("x")
            if x is None:
                continue
            etiqueta = resultado.get("etiqueta", f"resultado {i + 1}")

            if not resultado.get("convergio", False):
                tax.scatter(
                    [x], marker="x", color="gray", s=90, zorder=4,
                    label=f"{etiqueta} (NO convergió)",
                )
                continue

            T = resultado.get("T")
            texto_T = f", T={T:.1f} K" if T is not None else ""
            estilo = estilos[i % len(estilos)]
            tax.scatter(
                [x], marker=estilo["marker"], color=estilo["color"],
                s=estilo["s"], zorder=5, label=f"{etiqueta}{texto_T}",
            )

        tax.right_corner_label(nombres_componentes[0], fontsize=12)
        tax.top_corner_label(nombres_componentes[1], fontsize=12)
        tax.left_corner_label(nombres_componentes[2], fontsize=12)
        tax.get_axes().axis("off")
        tax.clear_matplotlib_ticks()
        tax.legend()
        plt.title(titulo or "Nodos Azeotrópicos Reactivos", fontsize=14)
        plt.show()
