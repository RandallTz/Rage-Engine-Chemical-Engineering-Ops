"""
Motor topologico (mapas residuales, saltos fisico/quimico).

Migrado desde equations.py y extendido con GestorReaccion, CalculadoraELV
y EspacioReactivo para tres formas de trazar la topologia reactiva:

  - draw_reactive_line       : mapeo discreto etapa-a-etapa (preexistente).
      calculate_physical_jump usa volatilidad dinamica (UNIFAC + Psat).
      calculate_chemical_jump ahora es un salto CINETICO de Euler con
      Damkohler fijo (self.Da), no un salto de equilibrio instantaneo.
  - generar_curva_residual_cinetica  : mapeo continuo (control cinetico),
      integra dx/dxi en el espacio real x via solve_ivp.
  - generar_curva_residual_equilibrio: mapeo continuo (equilibrio quimico),
      integra dX/dxi' en el espacio transformado de Barbosa-Doherty.

Zona libre de pint: solo floats/np.ndarray en SI.
"""

import numpy as np
from scipy.optimize import fsolve, root_scalar
from scipy.integrate import solve_ivp
# Backend sin ventana por defecto (ver config/graficos.py): los
# graficar_* de aqui terminan en plt.show(), y eso bloqueaba el
# proceso con una ventana cada vez que se importaba el modulo.
import config.graficos  # noqa: F401  -- debe ir ANTES que pyplot
import matplotlib.pyplot as plt
import ternary
import plotly.graph_objects as go


class ThermodynamicEngine:
    def __init__(self, nu, proveedor, K_R, gestor_reaccion, calculadora_elv,
                 espacio_reactivo, Da):
        """
        nu               : vector estequiometrico.
        proveedor        : ProveedorTermodinamico (Psat, gamma via UNIFAC).
        K_R              : constante de equilibrio ESTATICA, usada solo por
                            la curva de equilibrio quimico de referencia
                            dibujada en plot_ternary (no participa en los
                            saltos/ODEs nuevos, que usan K_eq(T) dinamica
                            de gestor_reaccion).
        gestor_reaccion  : GestorReaccion (K_eq(T) dinamica, velocidad r(T,x)).
        calculadora_elv  : CalculadoraELV (burbuja_P, burbuja_T).
        espacio_reactivo : EspacioReactivo (transformacion de Barbosa-Doherty).
        Da               : numero de Damkohler para el salto discreto
                            (calculate_chemical_jump). Los mapeos continuos
                            reciben su propio Da como argumento de llamada.
        """
        self.nu = np.asarray(nu, dtype=float)
        self.proveedor = proveedor
        self.K_R = float(K_R)
        self.gestor_reaccion = gestor_reaccion
        self.calculadora_elv = calculadora_elv
        self.espacio_reactivo = espacio_reactivo
        self.Da = float(Da)

        self.nu_tot = np.sum(self.nu)

        if np.isclose(self.nu_tot, 0.0):
            self.is_equimolar = True
            self.x_pi = np.full_like(self.nu, np.inf)
        else:
            self.is_equimolar = False
            self.x_pi = self.nu / self.nu_tot

    def print_topology(self):
        print(f"Stequiometric Vector (nu): {self.nu}")
        print(f"Moles Totales (nu_tot): {self.nu_tot}")
        print(f"Polo Geometrico (x_pi): {self.x_pi}")
        print(f"Volatilidad: dinamica (via ProveedorTermodinamico)")
        print(f"¿Es Equimolar?: {self.is_equimolar}\n")

    def calculate_physical_jump(self, x_liquido, T_actual):
        x_liquido = np.asarray(x_liquido, dtype=float)

        # Pedimos la deformacion real del espacio termodinamico
        alpha_dinamico = self.proveedor.volatilidades_relativas(T_actual, x_liquido)

        # Hadamard normalizado
        numerador = alpha_dinamico * x_liquido
        denominador = np.sum(numerador)
        x_condensado = numerador / denominador
        return x_condensado

    def residual_quimico(self, z, x_condensado):
        x_futuro = (x_condensado + z * self.nu) / (1 + z * self.nu_tot)
        x_seguro = np.abs(x_futuro)

        potencias_reactivos = np.where(self.nu < 0, np.abs(self.nu), 0)
        potencias_productos = np.where(self.nu > 0, self.nu, 0)

        reactivos = np.prod(np.power(x_seguro, potencias_reactivos))
        productos = np.prod(np.power(x_seguro, potencias_productos))

        return productos - self.K_R * reactivos

    def calculate_chemical_jump(self, x_condensado, T_actual):
        """
        Salto quimico CINETICO (Euler explicito, Damkohler fijo self.Da):

            x_siguiente = x_condensado + Da * nu * r(x_condensado, T)

        normalizado para que sume 1. Reemplaza el salto de equilibrio
        instantaneo (root-find sobre residual_quimico/K_R) por uno que usa
        la velocidad de reaccion real de GestorReaccion; Da->0 recupera el
        limite no reactivo, Da grande se aproxima al equilibrio instantaneo.
        """
        r = self.gestor_reaccion.velocidad_reaccion(T_actual, x_condensado)
        x_siguiente = x_condensado + self.Da * self.nu * r
        return x_siguiente / np.sum(x_siguiente)

    def draw_reactive_line(self, x_inicial, T_actual, max_etapas=50, tolerancia=1e-6,
                            limite_simplex=1e-5):
        """
        Mismo mapeo discreto de siempre, con una guarda de frontera: si el
        salto quimico cinetico produce un x_siguiente con algun componente
        por debajo de 'limite_simplex', NO se usa para un nuevo salto
        fisico (eso es lo que rompia volatilidades_relativas/UNIFAC con
        composicion invalida) -- se registra ese punto como ultimo de la
        trayectoria y se detiene, igual en espiritu al evento terminal de
        generar_curva_residual_cinetica.
        """
        k_componentes = len(x_inicial)
        trayectoria = np.zeros((max_etapas, k_componentes))
        x_actual = np.asarray(x_inicial, dtype=float)

        for etapa in range(max_etapas):
            trayectoria[etapa] = x_actual

            x_condensado = self.calculate_physical_jump(x_actual, T_actual)
            x_siguiente = self.calculate_chemical_jump(x_condensado, T_actual)

            if np.min(x_siguiente) < limite_simplex:
                print(
                    "draw_reactive_line: limite del simplex alcanzado en la "
                    f"etapa {etapa+1} (min(x_siguiente)={np.min(x_siguiente):.3e}); "
                    "se detiene sin intentar otro salto fisico desde ahi."
                )
                if etapa + 1 < max_etapas:
                    trayectoria[etapa+1] = x_siguiente
                    return trayectoria[:etapa+2]
                return trayectoria[:etapa+1]

            distancia = np.linalg.norm(x_siguiente - x_actual)
            if distancia < tolerancia:
                return trayectoria[:etapa+1]

            x_actual = x_siguiente

        print("Advertencia: Se alcanzó el máximo de etapas sin converger.")
        return trayectoria

    def generar_curva_residual_cinetica(self, x_inicial, T_inicial, Da, t_span,
                                         P_sistema=101325.0, n_eval=200):
        """
        Mapeo continuo bajo control CINETICO: integra, en el espacio real
        de fracciones molares x,

            dx/dxi = (x - y*(x,T)) + Da*(nu - nu_tot*x)*r(x,T)

        T se recalcula en cada paso como T de burbuja (CalculadoraELV) a
        P_sistema fija; r se evalua con GestorReaccion. T_inicial no
        participa en el calculo (burbuja_T resuelve por biseccion en
        [273.15, 600] K, sin necesitar una semilla): se conserva en la
        firma para dejar explicito el estado inicial de la corrida.

        Nota: P_sistema no estaba en la firma pedida pero es indispensable
        para burbuja_T; se agrega con un valor por defecto (1 atm) en vez
        de asumirlo en silencio.

        Devuelve (xi, trayectoria): xi es sol.t (necesario para graficar
        bien el eje cuando el evento termina antes de t_span[1] -- usar un
        linspace(t_span) fijo del lado de quien llama daria un eje erroneo).

        Evento terminal: detiene la integracion apenas la fraccion molar
        mas chica cae a 1e-5 (limite del simplex).

        El evento SOLO no alcanza (verificado): RK45 evalua la derivada en
        puntos de prueba internos de cada paso adaptativo antes de aceptar
        el paso, y el evento se revisa recien despues de aceptarlo. Con un
        t_span largo, alguna evaluacion de prueba cae en composicion
        negativa y burbuja_T pierde su bracket ahi, antes de que el evento
        tenga chance de frenar nada -- lo reproduje y confirme exactamente
        eso. Por eso 'derivada' usa un piso numerico (x_seguro) SOLO para
        las llamadas termodinamicas (burbuja_T, velocidad_reaccion), no
        para el resto del ODE: eso mantiene la funcion evaluable en los
        pasos de prueba sin alterar la dinamica real, y el evento sigue
        revisando el estado x verdadero (no el recortado) para decidir
        cuando parar.
        """
        # Caso NO reactivo. El docstring siempre dijo que "Da->0 recupera
        # el limite no reactivo", pero eso no era ejecutable: la derivada
        # llamaba a gestor_reaccion sin comprobar que existiera, asi que
        # un motor sin reaccion (gestor=None) reventaba con AttributeError
        # en cada curva. Con Da=0 el termino quimico vale cero de todos
        # modos, asi que ademas de arreglar el fallo se ahorra evaluar la
        # cinetica -- que es lo caro -- en cada paso del integrador.
        sin_reaccion = Da == 0.0 or self.gestor_reaccion is None

        def derivada(xi, x):
            x_seguro = np.clip(x, 1e-10, None)
            T_actual, y_estrella = self.calculadora_elv.burbuja_T(P_sistema, x_seguro)
            if sin_reaccion:
                return x - y_estrella
            r = self.gestor_reaccion.velocidad_reaccion(T_actual, x_seguro)
            return (x - y_estrella) + Da * (self.nu - self.nu_tot * x) * r

        def limite_simplex(xi, x):
            return np.min(x) - 1e-5

        limite_simplex.terminal = True
        limite_simplex.direction = -1  # solo dispara bajando hacia 0, no subiendo desde abajo

        # Una curva residual TERMINA cuando deja de moverse: ha llegado a
        # su nodo. Sin este evento la integracion seguia hasta el t_span
        # pedido y ahi pasaba algo que arruinaba el mapa (medido, no
        # supuesto): al llegar al punto estacionario la derivada es ~0,
        # RK45 agranda el paso sin limite y la solucion se desintegra --
        # en el sistema acetaldehido/etanol/acetal la curva llegaba a su
        # nodo en xi~2.5 y para xi=38 sum(x) habia caido de 1.0 a 0.148,
        # o sea puntos FUERA del simplex dibujados como si fueran fisicos.
        def estacionaria(xi, x):
            return float(np.linalg.norm(derivada(xi, x))) - 1e-7

        estacionaria.terminal = True
        estacionaria.direction = -1

        # Red de seguridad: la ODE conserva sum(x)=1 analiticamente (se
        # verifico: la suma de la derivada da 2e-16), asi que cualquier
        # desviacion apreciable es basura numerica, no fisica. Mejor
        # cortar la curva ahi que dibujar composiciones imposibles.
        def deriva_masa(xi, x):
            return 1e-4 - abs(float(np.sum(x)) - 1.0)

        deriva_masa.terminal = True
        deriva_masa.direction = -1

        # El muestreo se hace sobre el tramo REALMENTE integrado, no sobre
        # el t_span pedido. Con t_eval fijo sobre todo t_span pasaba algo
        # que hacia el mapa inservible: como el evento de frontera corta la
        # integracion enseguida (xi~1-3 tipicamente), de los n_eval puntos
        # solo sobrevivian los poquisimos anteriores al corte -- con
        # t_span=(0,40) y n_eval=80 el espaciado es 0.5, asi que una curva
        # que termina en xi=1.5 se quedaba con TRES puntos y se dibujaba
        # como un segmento recto. Y subir t_span lo empeoraba. Con
        # dense_output se integra igual (no cambia la fisica ni el evento)
        # y luego se reparten los n_eval puntos sobre [t0, t_final real].
        sol = solve_ivp(
            derivada, t_span, np.asarray(x_inicial, dtype=float),
            dense_output=True, events=[limite_simplex, estacionaria, deriva_masa],
        )
        if sol.status == 1:
            cual = next(
                (n for n, ev in zip(
                    ("frontera del simplex (una fraccion molar llego a ~1e-5)",
                     "punto estacionario: la curva llego a su nodo",
                     "deriva de masa: sum(x) se alejo de 1, la integracion degenero"),
                    sol.t_events) if len(ev)),
                "desconocido",
            )
            print(f"generar_curva_residual_cinetica: detenida por {cual}.")
        elif not sol.success:
            print(f"Advertencia: solve_ivp no convergio ({sol.message}).")

        t_final = float(sol.t[-1])
        if t_final <= t_span[0] or sol.sol is None:
            return sol.t, sol.y.T
        malla = np.linspace(t_span[0], t_final, n_eval)
        return malla, sol.sol(malla).T

    def generar_curva_residual_equilibrio(self, X_inicial, P_sistema, t_span,
                                           n_eval=200):
        """
        Mapeo continuo bajo EQUILIBRIO QUIMICO: integra, en el espacio
        transformado de Barbosa-Doherty (EspacioReactivo),

            dX/dxi' = X - Y*

        Devuelve (xi, trayectoria) igual que generar_curva_residual_cinetica,
        por la misma razon (el evento puede terminar antes de t_span[1]).

        En cada evaluacion de la derivada se resuelve (anidado, con
        scipy.optimize.root_scalar) la fraccion real x_k del componente de
        referencia que satisface el equilibrio quimico completo:

            K_eq(T) - prod_i(a_i^nu_i) = 0

        donde T es, a su vez, la T de burbuja (CalculadoraELV) del x real
        reconstruido para ese x_k. Una vez hallado x_k se reconstruye x,
        se calcula su vapor y* y se transforma a Y* para el integrador.

        Advertencia de robustez (verificada, no solo teorica): probe esto
        con el sistema MTBE real y el bracket ingenuo x_k en (0,1) falla
        en la PRIMERA evaluacion -- la mayor parte de ese rango reconstruye
        composiciones fuera del simplex (componentes negativos) o hace que
        el burbuja_T interno pierda su propio bracket. La raiz real existe,
        pero en una ventana angosta. Por eso se agrega bracket_valido(): un
        escaneo previo (tecnica numerica estandar, no una decision de
        fisica nueva) que descarta x_k fuera del simplex o donde burbuja_T
        falla, y solo llama a brentq sobre el sub-intervalo donde de verdad
        detecta un cambio de signo. Aun asi, esto es una raiz anidada
        dentro de otra raiz dentro de cada paso del integrador -- es
        costoso y puede no encontrar bracket para todo X/sistema.

        Evento terminal: cuando la trayectoria se acerca lo suficiente a un
        vertice, bracket_valido() deja de encontrar cambio de signo y antes
        esto tumbaba toda la integracion con un RuntimeError sin control
        (verificado). Ahora, igual que en generar_curva_residual_cinetica,
        se aplica el mismo patron en dos partes: 'derivada' atrapa ese
        RuntimeError y devuelve una derivada nula en vez de propagar la
        excepcion (para no romper las evaluaciones de prueba internas del
        integrador), y un evento independiente ('limite_equilibrio')
        vuelve a intentar bracket_valido sobre el X ya aceptado y detiene
        la integracion en cuanto deja de existir una raiz valida.
        """
        def residual_xk(x_k, X):
            x_prueba = self.espacio_reactivo.inversa(X, x_k)
            T_prueba, _ = self.calculadora_elv.burbuja_T(P_sistema, x_prueba)
            gamma_prueba = self.proveedor.coeficientes_actividad(T_prueba, x_prueba)
            actividades = x_prueba * gamma_prueba
            K_prueba = self.gestor_reaccion.K_eq(T_prueba)
            return K_prueba - np.prod(np.power(actividades, self.nu))

        def bracket_valido(X, n_muestras=60):
            candidatos = np.linspace(1e-6, 1.0 - 1e-6, n_muestras)
            xk_prev, resid_prev = None, None
            for xk in candidatos:
                x_prueba = self.espacio_reactivo.inversa(X, xk)
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
                "No se encontro un sub-intervalo fisico de x_k con cambio "
                f"de signo para resolver el equilibrio quimico en X={X}."
            )

        def y_equilibrio_de(X):
            a, b = bracket_valido(X)
            sol_xk = root_scalar(residual_xk, args=(X,), bracket=[a, b], method='brentq')
            x_eq = self.espacio_reactivo.inversa(X, sol_xk.root)
            _, y_vapor = self.calculadora_elv.burbuja_T(P_sistema, x_eq)
            return y_vapor

        def derivada(xi, X):
            try:
                Y_estrella = self.espacio_reactivo.transformar(y_equilibrio_de(X))
            except RuntimeError:
                return np.zeros_like(X)
            return X - Y_estrella

        def limite_equilibrio(xi, X):
            try:
                bracket_valido(X)
                return 1.0
            except RuntimeError:
                return -1.0

        limite_equilibrio.terminal = True
        limite_equilibrio.direction = -1

        sol = solve_ivp(
            derivada, t_span, np.asarray(X_inicial, dtype=float),
            t_eval=np.linspace(t_span[0], t_span[1], n_eval),
            events=limite_equilibrio,
        )
        if sol.status == 1:
            print(
                "generar_curva_residual_equilibrio: integracion detenida por "
                f"el evento de equilibrio no resoluble en xi={sol.t_events[0][0]:.6g} "
                "(bracket_valido dejo de encontrar raiz cerca de un vertice)."
            )
        elif not sol.success:
            print(f"Advertencia: solve_ivp no convergio ({sol.message}).")
        return sol.t, sol.y.T

    # ------------------------------------------------------------------
    # Los tres elementos que acompañan a las trayectorias en el mapa
    # topológico del método original (archive/equations.py). Estaban
    # escritos DENTRO de plot_ternary, enredados con matplotlib, así que
    # solo existían si se abría una ventana de escritorio -- por eso no
    # llegaron a la web. Aquí se extraen TAL CUAL (misma matemática, mismo
    # muestreo) a métodos que devuelven datos, y plot_ternary pasa a
    # llamarlos: una sola implementación, no dos que se desincronicen.
    # ------------------------------------------------------------------

    def curva_equilibrio_quimico(self, T_actual, n_puntos=150):
        """
        Lugar geométrico donde se cumple el equilibrio químico:
            prod(productos) - K_eq(T) * prod(reactivos) = 0
        Se barre la fracción del componente A y se resuelve la de B.

        Usa K_eq(T_actual) real de GestorReaccion (Gibbs de formación vía
        thermo), no el K_R estático -- consistente con las trayectorias,
        que ya usan la reacción real vía calculate_chemical_jump.
        """
        if self.gestor_reaccion is None:
            return []
        K_eq_actual = self.gestor_reaccion.K_eq(T_actual)
        curva_equilibrio = []
        fracciones_A = np.linspace(0.001, 0.999, n_puntos)

        for fa in fracciones_A:
            def buscar_equilibrio(fb_array):
                fb = fb_array[0]
                fc = 1.0 - fa - fb
                x_prueba = np.array([fa, fb, fc])
                x_seguro = np.abs(x_prueba)
                potencias_reactivos = np.where(self.nu < 0, np.abs(self.nu), 0)
                potencias_productos = np.where(self.nu > 0, self.nu, 0)
                reactivos = np.prod(np.power(x_seguro, potencias_reactivos))
                productos = np.prod(np.power(x_seguro, potencias_productos))
                return productos - K_eq_actual * reactivos

            try:
                fb_solucion = fsolve(buscar_equilibrio, 0.5)[0]
                fc_solucion = 1.0 - fa - fb_solucion
                if (0.0 <= fb_solucion <= 1.0) and (0.0 <= fc_solucion <= 1.0):
                    curva_equilibrio.append([fa, fb_solucion, fc_solucion])
            except Exception:
                pass
        return curva_equilibrio

    def lineas_estequiometricas(self, n_lineas=12, n_z=200):
        """
        Rectas de reacción: desde una base sobre la arista A-C se avanza
        el grado de avance z en la dirección de nu,

            x(z) = (x_base + z*nu) / (1 + z*nu_tot)

        conservando solo los tramos que caen dentro del símplex. Son las
        trayectorias que seguiría la composición por reacción PURA, sin
        separación -- por eso enmarcan el mapa.
        """
        lineas = []
        fracciones_base_A = np.linspace(0.05, 0.95, n_lineas)
        for fa in fracciones_base_A:
            x_base = np.array([fa, 0.0, 1.0 - fa])
            z_valores = np.linspace(-0.5, 0.5, n_z)
            linea_punteada = []
            for z in z_valores:
                x_z = (x_base + z * self.nu) / (1 + z * self.nu_tot)
                if np.all(x_z >= -1e-6) and np.all(x_z <= 1 + 1e-6):
                    linea_punteada.append([float(v) for v in x_z])
            if len(linea_punteada) > 1:
                lineas.append(linea_punteada)
        return lineas

    def polo_geometrico(self):
        """
        Polo pi = nu / nu_tot. Todas las rectas estequiométricas pasan por
        él: reaccionar mueve la composición a lo largo de la recta que une
        el punto con el polo. Si la reacción es equimolar (nu_tot = 0) el
        polo se va al infinito y esas rectas salen PARALELAS, que es un
        caso topológicamente distinto -- por eso se informa aparte en vez
        de devolver un punto inventado.
        """
        if self.is_equimolar:
            return {"equimolar": True, "x_pi": None, "direccion": [float(v) for v in self.nu]}
        return {"equimolar": False, "x_pi": [float(v) for v in self.x_pi], "direccion": None}

    def trayectorias_reactivas(self, puntos_iniciales, T_actual, max_etapas=100):
        """
        El mapeo DISCRETO etapa a etapa del método original (salto físico
        de equilibrio + salto químico), que es lo que dibuja el libro --
        distinto de las curvas residuales continuas, que integran una ODE.
        """
        trayectorias = []
        for x_ini in puntos_iniciales:
            try:
                traj = self.draw_reactive_line(
                    x_inicial=np.asarray(x_ini, dtype=float),
                    T_actual=T_actual, max_etapas=max_etapas,
                )
            except Exception:
                continue
            if len(traj) >= 2:
                trayectorias.append([[float(v) for v in fila] for fila in traj])
        return trayectorias

    def plot_ternary(self, T_actual, n_puntos=100, max_etapas=100):
        """Genera y renderiza el mapa topológico en 2D para 3 componentes."""
        if len(self.nu) != 3:
            raise ValueError("plot_ternary solo es válido para sistemas de 3 componentes.")

        puntos_iniciales = np.random.dirichlet((1, 1, 1), size=n_puntos)

        figura, tax = ternary.figure(scale=1.0)
        figura.set_size_inches(10, 8)
        tax.boundary(linewidth=2.0)
        tax.gridlines(multiple=0.1, color="gray", linestyle="--", linewidth=0.5)

        # 1. Trayectorias Reactivas (Líneas Azules)
        for x_ini in puntos_iniciales:
            matriz_historial = self.draw_reactive_line(
                x_inicial=x_ini, T_actual=T_actual, max_etapas=max_etapas
            )
            tax.plot(matriz_historial, linewidth=1.5, color="blue", alpha=0.5)
            tax.scatter([matriz_historial[0]], marker='s', color='green', s=30, zorder=3)
            tax.scatter([matriz_historial[-1]], marker='*', color='red', s=80, zorder=3)

        # 2. Curva de Equilibrio Químico (Línea Negra)
        K_eq_actual = self.gestor_reaccion.K_eq(T_actual)
        curva_equilibrio = self.curva_equilibrio_quimico(T_actual)
        if curva_equilibrio:
            tax.plot(curva_equilibrio, color="black", linewidth=2.5, label="Equilibrio Químico", zorder=4)

        # 3. Líneas Estequiométricas (Punteadas Rojas)
        for linea_punteada in self.lineas_estequiometricas():
            tax.plot(linea_punteada, color="red", linestyle=":", linewidth=2, alpha=0.6)

        tax.right_corner_label("Comp. A (Volátil)", fontsize=12)
        tax.top_corner_label("Comp. B", fontsize=12)
        tax.left_corner_label("Comp. C (Pesado)", fontsize=12)
        tax.get_axes().axis('off')
        tax.clear_matplotlib_ticks()
        plt.title(
            f"Topología de Destilación Reactiva ({n_puntos} Líneas) — "
            f"K_eq({T_actual:.0f} K) = {K_eq_actual:.3g}",
            fontsize=13,
        )
        plt.show()

    def plot_quaternary(self, T_actual, n_puntos=150, max_etapas=150):
        """Genera y renderiza el gemelo digital en 3D para 4 componentes usando GPU/Plotly."""
        if len(self.nu) != 4:
            raise ValueError("plot_quaternary solo es válido para sistemas de 4 componentes.")

        # Geometría y Proyección Interna
        V_a = np.array([0.0, 0.0, 0.0])
        V_b = np.array([1.0, 0.0, 0.0])
        V_c = np.array([0.5, np.sqrt(3)/2, 0.0])
        V_d = np.array([0.5, np.sqrt(3)/6, np.sqrt(6)/3])
        matriz_vertices = np.vstack((V_a, V_b, V_c, V_d))

        def proyectar_a_3D(matriz_fracciones):
            return np.dot(matriz_fracciones, matriz_vertices)

        figura_3d = go.Figure()

        # 1. Aristas y Etiquetas
        aristas = [(V_a, V_b), (V_b, V_c), (V_c, V_a), (V_a, V_d), (V_b, V_d), (V_c, V_d)]
        for p1, p2 in aristas:
            figura_3d.add_trace(go.Scatter3d(
                x=[p1[0], p2[0]], y=[p1[1], p2[1]], z=[p1[2], p2[2]],
                mode='lines', line=dict(color='black', width=4),
                showlegend=False, hoverinfo='skip'
            ))

        etiquetas_vertices = ["Comp. A", "Comp. B", "Comp. C", "Comp. D"]
        coords_vertices = [V_a, V_b, V_c, V_d]
        for coord, texto in zip(coords_vertices, etiquetas_vertices):
            figura_3d.add_trace(go.Scatter3d(
                x=[coord[0]], y=[coord[1]], z=[coord[2]],
                mode='text', text=[texto], textposition="top center",
                showlegend=False
            ))

        # 2. Trayectorias Reactivas (Líneas Azules)
        puntos_iniciales = np.random.dirichlet((1, 1, 1, 1), size=n_puntos)

        for x_ini in puntos_iniciales:
            historial_4D = self.draw_reactive_line(
                x_inicial=x_ini, T_actual=T_actual, max_etapas=max_etapas
            )
            historial_3D = proyectar_a_3D(historial_4D)
            X, Y, Z = historial_3D[:, 0], historial_3D[:, 1], historial_3D[:, 2]

            figura_3d.add_trace(go.Scatter3d(
                x=X, y=Y, z=Z, mode='lines',
                line=dict(color='blue', width=2), opacity=0.6, showlegend=False
            ))
            figura_3d.add_trace(go.Scatter3d(
                x=[X[0], X[-1]], y=[Y[0], Y[-1]], z=[Z[0], Z[-1]],
                mode='markers',
                marker=dict(color=['green', 'red'], size=[3, 6], symbol=['square', 'diamond']),
                showlegend=False
            ))

        # 3. Líneas Estequiométricas y Polo (Equimolar vs No Equimolar)
        if not self.is_equimolar:
            polo_4D = np.array([self.x_pi])
            polo_3D = proyectar_a_3D(polo_4D)[0]

            figura_3d.add_trace(go.Scatter3d(
                x=[polo_3D[0]], y=[polo_3D[1]], z=[polo_3D[2]],
                mode='markers+text',
                marker=dict(color='black', size=6, symbol='circle-open'),
                text=['π (Polo Geométrico)'], textposition="top right", showlegend=False
            ))

            for x_ini in puntos_iniciales:
                punto_ini_3D = proyectar_a_3D(np.array([x_ini]))[0]
                figura_3d.add_trace(go.Scatter3d(
                    x=[punto_ini_3D[0], polo_3D[0]],
                    y=[punto_ini_3D[1], polo_3D[1]],
                    z=[punto_ini_3D[2], polo_3D[2]],
                    mode='lines', line=dict(color='gray', width=1.5, dash='dot'),
                    opacity=0.4, showlegend=False
                ))
        else:
            for x_ini in puntos_iniciales:
                # Cálculo de límites universales para sistemas equimolares
                z_max = min([x_ini[i]/abs(self.nu[i]) if self.nu[i] < 0 else np.inf for i in range(4)])
                z_min = max([-x_ini[i]/self.nu[i] if self.nu[i] > 0 else -np.inf for i in range(4)])

                ext_1 = x_ini + z_min * self.nu
                ext_2 = x_ini + z_max * self.nu
                segmento_3D = proyectar_a_3D(np.array([ext_1, ext_2]))

                figura_3d.add_trace(go.Scatter3d(
                    x=segmento_3D[:, 0], y=segmento_3D[:, 1], z=segmento_3D[:, 2],
                    mode='lines', line=dict(color='red', width=2, dash='dot'),
                    opacity=0.4, showlegend=False
                ))

        figura_3d.update_layout(
            scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
            margin=dict(l=0, r=0, b=0, t=30),
            title="Gemelo Digital 3D de Destilación Reactiva"
        )
        figura_3d.show()
