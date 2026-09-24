"""
Reactor continuo de tanque agitado (CSTR) en estado estacionario.

Mismo estandar que el resto del simulador: NO es un bloque "de adelante
hacia atras" solamente -- resuelve en la direccion que haga falta. Las
tres direcciones utiles estan implementadas de forma EXACTA (algebra,
sin iterar):

  adelante : conocidos el alimento y el avance xi  -> salida
  atras    : conocidas la salida y xi              -> alimento
  avance   : conocidos el alimento y UNA fraccion
             de salida                             -> xi (y con el, todo lo demas)

La tercera es la que hace util al bloque en la practica: normalmente uno
sabe lo que entra y QUE PUREZA quiere a la salida, y lo que busca es el
avance (y de ahi el volumen) que hace falta.

Balance por componente, en estado estacionario:

    F_out * x_out_i = F_in * x_in_i + nu_i * xi

donde xi [mol/s] es el avance de reaccion. Sumando en i y usando que las
fracciones suman 1 sale el balance total, F_out = F_in + nu_tot * xi, que
por eso no se impone aparte (seria redundante).

Cinetica (bloque separado, porque no siempre se quiere): en un CSTR la
composicion del tanque ES la de salida, asi que

    xi = V * r(T, x_out)

BALANCE DE ENERGIA (ver _exigir_energia y siguientes):

    F_in*h(T_in, x_in) + Q  =  F_out*h(T_out, x_out) + xi*dH_rxn(T_ref)

La sutileza esta en el ULTIMO termino, y es la razon de que este balance
no se pudiera escribir bien hasta que la entalpia se unifico. Se
desarrolla en docs/09-reactor-cstr.md; en corto:

  - h mide entalpia SENSIBLE, con referencia "componentes puros liquidos
    a T_ref con h_i = 0". No incluye entalpias de formacion.
  - Por eso el calor de reaccion hay que ponerlo a mano, y hay que
    ponerlo evaluado EXACTAMENTE en esa T_ref -- no en T_out.
  - No es una aproximacion de "dH_rxn constante con T": la dependencia
    con T del calor de reaccion ya esta contenida en el termino
    F_out*h(T_out, x_out), porque ese termino incluye sum(nu_i*h_i(T_out)).
    Usar dH_rxn(T_out) contaria esa dependencia DOS veces.

Que las dos referencias coincidan (T_ref = 298.15 K en
CalculadoraEntalpia, T_std = 298.15 K en GestorReaccion, que es donde
'thermo' da sus Hf) no es casualidad, pero tampoco se da por hecho: se
comprueba antes de cada balance.

Zona libre de pint: solo floats/np.ndarray en SI.
"""

import numpy as np
from scipy.optimize import root

_TOL_SINGULAR = 1e-12


class EvaluadorCSTR:
    def __init__(self, nu, gestor_reaccion=None, evaluador_flash=None, dH_rxn=None):
        """
        nu              : vector estequiometrico (negativo=reactivo, positivo=producto).
        gestor_reaccion : GestorReaccion, hace falta para el bloque
                          cinetico (xi a partir de V y T). El balance de
                          materia funciona sin el.
        evaluador_flash : EvaluadorFlash, opcional. Da dos cosas al balance
                          de energia: la calculadora de entalpia compartida
                          y el punto de burbuja, con el que se comprueba
                          que el tanque no este hirviendo (ver
                          _exigir_liquido). Sin el, no hay balance de
                          energia -- el reactor vuelve a ser isotermo con
                          T como dato, que es como estaba antes.
        dH_rxn          : [J/mol] para dar el calor de reaccion a mano
                          cuando no hay GestorReaccion (un reactor sin
                          cinetica sigue teniendo calor de reaccion).
        """
        self.nu = np.asarray(nu, dtype=float)
        self.nu_tot = float(np.sum(self.nu))
        self.gestor_reaccion = gestor_reaccion
        self.evaluador_flash = evaluador_flash
        self.entalpia = evaluador_flash.entalpia if evaluador_flash is not None else None

        if dH_rxn is not None:
            self.dH_rxn = float(dH_rxn)
        elif gestor_reaccion is not None:
            self.dH_rxn = float(gestor_reaccion.dH_rxn)
        else:
            self.dH_rxn = None

        if np.allclose(self.nu, 0.0):
            raise ValueError("El vector estequiometrico es todo ceros: eso no es una reaccion.")

    # ------------------------------------------------------------------
    def salida_desde_entrada(self, F_in, x_in, xi):
        """Adelante: alimento + avance -> salida."""
        x_in = np.asarray(x_in, dtype=float)
        F_out = F_in + self.nu_tot * xi
        if F_out <= _TOL_SINGULAR:
            raise ValueError(
                f"El avance xi={xi:.6g} deja un caudal de salida no positivo "
                f"(F_out={F_out:.6g} mol/s). Ese avance es imposible con este alimento."
            )
        x_out = (F_in * x_in + self.nu * xi) / F_out
        self._exigir_simplex(x_out, "de salida", xi)
        return F_out, x_out

    def entrada_desde_salida(self, F_out, x_out, xi):
        """Atras: salida + avance -> alimento. Es la misma ecuacion despejada."""
        x_out = np.asarray(x_out, dtype=float)
        F_in = F_out - self.nu_tot * xi
        if F_in <= _TOL_SINGULAR:
            raise ValueError(
                f"Con xi={xi:.6g} el alimento necesario seria F_in={F_in:.6g} mol/s, "
                "que no es fisico. Revisa el avance o la corriente de salida."
            )
        x_in = (F_out * x_out - self.nu * xi) / F_in
        self._exigir_simplex(x_in, "de alimentacion", xi)
        return F_in, x_in

    def avance_desde_fraccion(self, F_in, x_in_j, x_out_j, j):
        """
        Avance a partir de UNA fraccion conocida de la salida. Exacto:
        sustituyendo F_out = F_in + nu_tot*xi en el balance del componente j,

            x_out_j * (F_in + nu_tot*xi) = F_in*x_in_j + nu_j*xi

        queda lineal en xi:

            xi = F_in * (x_in_j - x_out_j) / (x_out_j*nu_tot - nu_j)
        """
        denominador = x_out_j * self.nu_tot - self.nu[j]
        if abs(denominador) < _TOL_SINGULAR:
            raise ValueError(
                f"La fraccion de salida del componente {j} no determina el avance "
                f"(el denominador x_out*nu_tot - nu_{j} se anula). Da la de otro componente."
            )
        return F_in * (x_in_j - x_out_j) / denominador

    def avance_desde_cinetica(self, V, T, x_out):
        """
        En un CSTR el contenido del tanque esta perfectamente mezclado, o
        sea que su composicion es la de SALIDA -- por eso r se evalua en
        x_out y no en el alimento. Esa es justamente la diferencia con un
        reactor de flujo piston.
        """
        if self.gestor_reaccion is None:
            raise ValueError("Para usar la cinetica hace falta un GestorReaccion.")
        r = float(self.gestor_reaccion.velocidad_reaccion(T, np.asarray(x_out, dtype=float)))
        return V * r

    def volumen_desde_avance(self, xi, T, x_out):
        """La inversa de la anterior: que tanque hace falta para ese avance."""
        if self.gestor_reaccion is None:
            raise ValueError("Para usar la cinetica hace falta un GestorReaccion.")
        r = float(self.gestor_reaccion.velocidad_reaccion(T, np.asarray(x_out, dtype=float)))
        if abs(r) < _TOL_SINGULAR:
            raise ValueError(
                f"La velocidad de reaccion a T={T:.4g} K en la composicion de salida es "
                "practicamente cero (el sistema ya esta en equilibrio quimico ahi): "
                "ningun volumen finito da ese avance."
            )
        return xi / r

    # ------------------------------------------------------------------
    # Balance de energia
    # ------------------------------------------------------------------
    def _exigir_energia(self):
        """
        Comprueba lo que hace falta para un balance de energia, incluido
        que las DOS referencias coincidan.

        Esa ultima comprobacion es la que evita el error silencioso: si
        alguien construyera la calculadora de entalpia con otra T_ref, el
        termino xi*dH_rxn quedaria referido a una temperatura distinta de
        la del resto del balance. El resultado seguiria siendo un numero
        plausible, con el error repartido entre Q y T, y nadie lo notaria.
        """
        if self.entalpia is None:
            raise ValueError(
                "Este reactor no tiene balance de energia: se construyo sin "
                "EvaluadorFlash, asi que no hay ni entalpias ni punto de burbuja. "
                "Pasa evaluador_flash=... para activarlo."
            )
        if self.dH_rxn is None:
            raise ValueError(
                "No hay calor de reaccion disponible: el reactor se construyo sin "
                "GestorReaccion y sin dH_rxn explicito. Sin el, el balance de energia "
                "no puede distinguir una reaccion exotermica de una endotermica."
            )
        T_ref_reaccion = getattr(self.gestor_reaccion, "T_std", None)
        if T_ref_reaccion is not None and abs(T_ref_reaccion - self.entalpia.T_ref) > 1e-9:
            raise ValueError(
                f"Las dos referencias no coinciden: la entalpia esta referida a "
                f"{self.entalpia.T_ref} K y el calor de reaccion a {T_ref_reaccion} K. "
                "El termino xi*dH_rxn solo es exacto evaluado en la MISMA T_ref que h "
                "(ver la cabecera de este modulo)."
            )

    def _exigir_liquido(self, T, x, P, exigir_liquido):
        """
        Un CSTR de este simulador es un tanque LIQUIDO: la cinetica usa
        actividades a_i = x_i*gamma_i, que son de fase liquida, y la
        entalpia del balance es h_liquido. Si la T que sale del balance
        esta por encima del punto de burbuja a la P de operacion, el
        tanque estaria hirviendo y el modelo deja de describirlo.

        Es exactamente el patron de fallo que persigue este proyecto: un
        numero plausible sobre algo fisicamente imposible. Por eso se
        comprueba en vez de confiar.
        """
        if P is None or self.evaluador_flash is None:
            return None
        T_burbuja, _ = self.evaluador_flash.calculadora_elv.burbuja_T(P, np.asarray(x, dtype=float))
        if T <= T_burbuja:
            return T_burbuja
        mensaje = (
            f"El balance da T={T:.2f} K, por encima del punto de burbuja de la mezcla de "
            f"salida a {P:.4g} Pa (T_burbuja={T_burbuja:.2f} K): el tanque estaria "
            "hirviendo. Este CSTR se modela como monofasico liquido (la cinetica usa "
            "actividades de fase liquida), asi que ese resultado no es de fiar. Sube la "
            "presion, quita calor, o usa exigir_liquido=False si de verdad quieres el "
            "numero sabiendo lo que significa."
        )
        if exigir_liquido:
            raise ValueError(mensaje)
        return T_burbuja

    def calor_de_reaccion(self, xi):
        """
        Calor liberado/absorbido por la reaccion [W], con el signo de la
        convencion termodinamica: dH_rxn < 0 es exotermica, asi que
        xi*dH_rxn < 0 significa energia que la reaccion SUELTA al tanque.
        """
        if self.dH_rxn is None:
            raise ValueError("No hay calor de reaccion disponible (ni GestorReaccion ni dH_rxn).")
        return float(xi) * self.dH_rxn

    def calor_necesario(self, F_in, x_in, T_in, xi, T_salida, P=None, exigir_liquido=True):
        """
        Modo ISOTERMO (o de T impuesta): se sabe a que temperatura se
        quiere operar y se calcula el calor que cuesta mantenerla.

            Q = F_out*h(T_out, x_out) + xi*dH_rxn - F_in*h(T_in, x_in)

        Q < 0 significa que hay que REFRIAR. Es el caso normal de una
        exotermica, y es un numero que antes el simulador no daba: un
        reactor isotermo sin este balance oculta cuanta refrigeracion
        hace falta, que suele ser la restriccion de diseno de verdad.
        """
        self._exigir_energia()
        x_in = np.asarray(x_in, dtype=float)
        F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)
        T_burbuja = self._exigir_liquido(T_salida, x_out, P, exigir_liquido)

        h_in = self.entalpia.h_liquido(T_in, x_in)
        h_out = self.entalpia.h_liquido(T_salida, x_out)
        Q_reaccion = self.calor_de_reaccion(xi)
        Q = F_out * h_out + Q_reaccion - F_in * h_in

        return {
            "Q": float(Q), "Q_por_mol": float(Q / F_in),
            "Q_reaccion": float(Q_reaccion),
            "T_salida": float(T_salida), "T_entrada": float(T_in),
            "F_out": float(F_out), "x_out": x_out, "xi": float(xi),
            "h_in": float(h_in), "h_out": float(h_out),
            "T_burbuja_salida": T_burbuja,
        }

    def temperatura_desde_calor(self, F_in, x_in, T_in, xi, Q=0.0, P=None,
                                exigir_liquido=True):
        """
        Modo ADIABATICO (Q = 0) o de calor impuesto: se sabe cuanta
        energia entra o sale y se calcula la temperatura que resulta.

        Es la misma ecuacion despejada:

            h(T_out, x_out) = [F_in*h(T_in, x_in) + Q - xi*dH_rxn] / F_out

        y de ahi T_out por inversion exacta (h es estrictamente creciente
        en T, ver thermodynamics/entalpia.py).
        """
        self._exigir_energia()
        x_in = np.asarray(x_in, dtype=float)
        F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)

        h_in = self.entalpia.h_liquido(T_in, x_in)
        Q_reaccion = self.calor_de_reaccion(xi)
        h_out = (F_in * h_in + float(Q) - Q_reaccion) / F_out
        T_salida = self.entalpia.T_desde_h_liquido(h_out, x_out)
        T_burbuja = self._exigir_liquido(T_salida, x_out, P, exigir_liquido)

        return {
            "Q": float(Q), "Q_por_mol": float(Q) / F_in,
            "Q_reaccion": float(Q_reaccion),
            "T_salida": float(T_salida), "T_entrada": float(T_in),
            "F_out": float(F_out), "x_out": x_out, "xi": float(xi),
            "h_in": float(h_in), "h_out": float(h_out),
            "T_burbuja_salida": T_burbuja,
        }

    # ------------------------------------------------------------------
    def resolver_con_cinetica(self, F_in, x_in, T_in, V, Q=0.0, P=None,
                              exigir_liquido=True, xi_inicial=None, T_inicial=None):
        """
        El caso ACOPLADO, y el unico que de verdad necesita resolverse
        como sistema: reactor adiabatico (o con calor dado) del que se
        conoce el VOLUMEN.

        Por que no lo puede hacer el motor de punto fijo del orquestador:
        la cinetica necesita T para dar xi, y el balance de energia
        necesita xi para dar T. Ninguno de los dos puede arrancar. No es
        que falten datos -- es un lazo, igual que un reciclo, y se
        resuelve igual: planteando las dos ecuaciones a la vez.

            R1(xi, T) = xi - V*r(T, x_out(xi))
            R2(xi, T) = F_in*h(T_in,x_in) + Q - F_out(xi)*h(T,x_out(xi)) - xi*dH_rxn

        Los dos residuos se ADIMENSIONALIZAN antes de entregarlos al
        solver, R1 con el caudal de entrada y R2 con F_in*|dH_rxn|. Sin
        eso quedan en unidades distintas (mol/s frente a W) y con ordenes
        de magnitud separados por ~10^6: hybr reparte su esfuerzo segun
        la norma del vector, asi que el de materia se vuelve invisible
        frente al de energia, y un criterio de parada unico no significa
        lo mismo para los dos. Con ambos adimensionales, "residuo < 1e-9"
        quiere decir lo mismo en las dos ecuaciones: error relativo.

        Aqui vive el acoplamiento que hace interesante a la destilacion
        reactiva: con una exotermica, mas avance sube T, y mas T sube la
        velocidad -- realimentacion positiva. El solver la resuelve; que
        la solucion sea ESTABLE en la planta real es otra pregunta, y
        este modelo estacionario no la responde (ver docs).
        """
        self._exigir_energia()
        if self.gestor_reaccion is None:
            raise ValueError("Para el caso acoplado hace falta la cinetica (GestorReaccion).")
        x_in = np.asarray(x_in, dtype=float)
        # Se evalua UNA vez: no depende de las incognitas, y esta dentro
        # del residuo se pagaria en cada paso del root-finding.
        h_in_fijo = self.entalpia.h_liquido(T_in, x_in)
        escala_energia = F_in * max(abs(self.dH_rxn), 1.0)

        def residuos(v):
            xi, T = float(v[0]), float(v[1])
            try:
                F_out, x_out = self.salida_desde_entrada(F_in, x_in, xi)
            except ValueError:
                # Avance fuera del simplex: se devuelve un residuo grande
                # en vez de dejar que reviente a mitad del root-finding.
                return [1e6, 1e6]
            try:
                r = float(self.gestor_reaccion.velocidad_reaccion(T, x_out))
                h_out = self.entalpia.h_liquido(T, x_out)
            except Exception:
                return [1e6, 1e6]
            R1 = (xi - V * r) / F_in
            R2 = (F_in * h_in_fijo + float(Q)
                  - F_out * h_out - xi * self.dH_rxn) / escala_energia
            return [R1, R2]

        # ARRANQUES MULTIPLES, y no por comodidad. Un arranque unico y
        # timido (1 % del limite estequiometrico, T = T_in) parece la
        # opcion prudente y resulta ser la mala: con una exotermica
        # fuerte el estacionario esta lejos, hybr no lo alcanza y el
        # metodo reportaba "no convergio" cuando SI habia solucion.
        # Medido con A=1e10 y V=2 m3: desde el arranque timido fallaba, y
        # desde 10 de 15 arranques distintos convergia siempre al mismo
        # xi=9.4699 mol/s, T=372.66 K.
        #
        # Los puntos de partida no son arbitrarios: para cada avance de
        # prueba se calcula la T que le corresponde POR BALANCE DE
        # ENERGIA, o sea que cada arranque ya satisface R2 y al solver
        # solo le queda arreglar la cinetica. Barrer el avance es barrer
        # una curva, no un plano.
        reactivos = np.where(self.nu < 0)[0]
        capacidad = min(F_in * x_in[i] / abs(self.nu[i]) for i in reactivos)

        if xi_inicial is not None or T_inicial is not None:
            # Arranque impuesto: se respeta tal cual y no se barre nada,
            # que es lo que permite pedir una rama concreta a proposito.
            arranques = [(float(xi_inicial if xi_inicial is not None else 0.01 * capacidad),
                          float(T_inicial if T_inicial is not None else T_in))]
        else:
            arranques = []
            for fraccion in (0.01, 0.1, 0.3, 0.6, 0.9):
                xi0 = fraccion * capacidad
                try:
                    T0 = self.temperatura_desde_calor(
                        F_in, x_in, T_in, xi0, Q=Q, P=None, exigir_liquido=False
                    )["T_salida"]
                except Exception:
                    T0 = T_in
                arranques.append((xi0, T0))

        soluciones = []
        for xi0, T0 in arranques:
            try:
                solucion = root(residuos, [xi0, T0], method="hybr")
            except Exception:
                continue
            xi_c, T_c = float(solucion.x[0]), float(solucion.x[1])
            try:
                residual_c = float(np.max(np.abs(residuos(solucion.x))))
            except Exception:
                continue
            # No se confia en sol.success: MINPACK puede reportar exito
            # con residuo grande y fracaso con el residuo ya en cero.
            # Es el mismo criterio que el balance de materia global.
            if not np.isfinite(residual_c) or residual_c > 1e-9:
                continue
            if xi_c < -1e-9 or xi_c > capacidad + 1e-9:
                continue  # fuera del rango estequiometrico posible
            if not any(abs(xi_c - s[0]) < 1e-6 and abs(T_c - s[1]) < 1e-6 for s in soluciones):
                soluciones.append((xi_c, T_c, residual_c))

        if not soluciones:
            raise RuntimeError(
                f"El reactor acoplado (cinetica + energia) no convergio desde ninguno de "
                f"los {len(arranques)} arranques probados (avances entre "
                f"{arranques[0][0]:.4g} y {arranques[-1][0]:.4g} mol/s). Con una exotermica "
                "fuerte el lazo T->r->xi->T puede no tener estado estacionario en el rango "
                "liquido; prueba un volumen menor, retirar calor (Q<0), o forzar un arranque "
                "concreto con xi_inicial/T_inicial."
            )

        # MULTIPLICIDAD: un CSTR exotermico puede tener mas de un estado
        # estacionario (el fenomeno clasico de ignicion/extincion). Si
        # aparece, no se elige en silencio: se devuelve el mas FRIO -- el
        # que alcanza un arranque en frio, que es lo que fisicamente pasa
        # al poner en marcha el equipo -- y se reportan todos en
        # 'soluciones' para que quien mire sepa que hay mas.
        soluciones.sort(key=lambda s: s[1])
        xi, T, residual = soluciones[0]

        resultado = self.temperatura_desde_calor(
            F_in, x_in, T_in, xi, Q=Q, P=P, exigir_liquido=exigir_liquido
        )
        resultado["V"] = float(V)
        resultado["residual"] = residual
        resultado["soluciones"] = [{"xi": s_[0], "T": s_[1]} for s_ in soluciones]
        resultado["multiplicidad"] = len(soluciones) > 1
        # Coherencia: la T del balance y la del sistema acoplado tienen
        # que ser la misma; si no, algo se desincronizo entre las dos vias.
        if abs(resultado["T_salida"] - T) > 1e-6:
            raise RuntimeError(
                f"Incoherencia interna: el sistema acoplado da T={T:.6f} K y el balance "
                f"de energia recalculado da {resultado['T_salida']:.6f} K."
            )
        return resultado

    # ------------------------------------------------------------------
    def conversion(self, F_in, x_in, xi, indice_limitante=None):
        """
        Conversion del reactivo limitante: cuanto de el desaparece.
        Si no se dice cual, se toma el reactivo (nu<0) que se agote antes,
        que es la definicion habitual.
        """
        x_in = np.asarray(x_in, dtype=float)
        reactivos = np.where(self.nu < 0)[0]
        if len(reactivos) == 0:
            raise ValueError("No hay ningun reactivo (ningun nu negativo): la conversion no esta definida.")
        if indice_limitante is None:
            # El limitante es el de menor moles disponibles por unidad de avance.
            capacidad = [F_in * x_in[i] / abs(self.nu[i]) for i in reactivos]
            indice_limitante = int(reactivos[int(np.argmin(capacidad))])

        entrada = F_in * x_in[indice_limitante]
        if entrada <= _TOL_SINGULAR:
            raise ValueError(
                f"El componente {indice_limitante} no entra al reactor "
                "(su caudal de alimentacion es cero): su conversion no esta definida."
            )
        consumido = abs(self.nu[indice_limitante]) * xi
        return consumido / entrada, indice_limitante

    # ------------------------------------------------------------------
    def _exigir_simplex(self, x, cual, xi, tolerancia=1e-8):
        if np.any(x < -tolerancia):
            negativos = [i for i, v in enumerate(x) if v < -tolerancia]
            raise ValueError(
                f"Con un avance xi={xi:.6g} la composicion {cual} sale negativa en "
                f"el componente {negativos[0]} (x={x[negativos[0]]:.4g}). "
                "Fisicamente no se puede consumir mas de lo que hay: baja el avance."
            )
