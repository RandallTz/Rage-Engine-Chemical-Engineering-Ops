"""
Orquestador: une varios bloques de ecuaciones (cada uno ya resuelto de
forma robusta por separado -- BalanceMateriaGlobal, SolucionadorMcCabeThiele,
SolucionadorPonchonSavarit, calcular_cargas_termicas...) en un solo
"pool" de variables compartidas, para poder introducir cualquier
combinacion de datos conocidos y que el sistema calcule el resto,
respetando grados de libertad, SIN tener que llamar a cada solver a mano
en el orden correcto.

Por que esto es un modulo aparte y no una fusion de los solvers: cada
bloque ya resuelve su propia ecuacion (o sistema) de la forma mas robusta
posible (root_scalar con bracket para McCabe-Thiele, root generico para
el balance lineal). Fusionarlos en un solo sistema simultaneo perderia
esa robustez (ver la discusion previa sobre EO puro vs. secuencial-
modular). En su lugar, el orquestador hace lo que un ingeniero haria a
mano: mira que bloque ya tiene suficiente informacion, lo resuelve con
SU propio metodo, actualiza el pool compartido, y repite hasta que no
hay mas progreso -- "secuencial-modular de bloques EO".

Limitacion real (no oculta): esto resuelve la union de sistemas
LOCALMENTE resolubles bloque por bloque. Si dos bloques quedan acoplados
de forma que NINGUNO es resoluble por si solo con lo que se sabe (un
verdadero sistema simultaneo entre bloques), esto lo reporta como
incognitas restantes en vez de intentar una resolucion simultanea global
-- exactamente la frontera que se discutio antes de construirlo.

Variables vectoriales en el pool (ver bloque_fug): el pool y el bucle de
resolucion tratan cada valor como opaco -- solo comparan 'pool[v] is
None' (identidad), nunca hacen aritmetica ni evaluan verdad-o-falso
sobre el valor. Por eso una variable puede ser un float (McCabe-Thiele,
Ponchon-Savarit) o un numpy.ndarray de n componentes (FUG) sin que
Orquestador/BloqueEcuaciones necesiten saberlo.
"""


class BloqueEcuaciones:
    def __init__(self, nombre, variables, puede_resolver, resolver_fn, variables_entrada=None,
                 n_ecuaciones=None):
        """
        nombre        : para reportes/depuracion.
        variables     : tupla de TODAS las variables de este bloque
                        (entrada + salida) -- se usan para actualizar el
                        pool compartido una vez resuelto.
        variables_entrada: subconjunto de 'variables' que se cuenta para
                        decidir SI este bloque ya se puede intentar
                        (puede_resolver se evalua sobre cuantas de ESTAS
                        faltan, no sobre todas). Por defecto, igual a
                        'variables' (los bloques invertibles como
                        BalanceMateriaGlobal o McCabe-Thiele no
                        distinguen entrada/salida: cualquiera de sus
                        variables puede ser la incognita). Los bloques NO
                        invertibles (p.ej. calcular_cargas_termicas, que
                        solo calcula hacia adelante) sí necesitan esta
                        distincion: sus salidas nunca cuentan como
                        "incognitas que bloquean" el disparo del bloque.
        puede_resolver: callable(n_incognitas_de_entrada) -> bool.
        resolver_fn   : callable(**conocidos) -> dict con TODAS las
                        variables de este bloque (entrada + salida).
        n_ecuaciones  : cuantas ecuaciones INDEPENDIENTES aporta este
                        bloque. Solo se usa para contar grados de
                        libertad (variables - ecuaciones) y avisar en
                        tiempo real de si faltan o sobran datos; no
                        interviene en la resolucion. Por defecto se
                        deduce: un bloque no invertible aporta tantas
                        ecuaciones como variables de salida tenga, y uno
                        invertible aporta 1 salvo que se diga otra cosa
                        (el balance de materia, p.ej., aporta 2).
        """
        self.nombre = nombre
        self.variables = tuple(variables)
        self.variables_entrada = tuple(variables_entrada) if variables_entrada is not None else self.variables
        if n_ecuaciones is None:
            salidas = len(self.variables) - len(self.variables_entrada)
            n_ecuaciones = salidas if salidas > 0 else 1
        self.n_ecuaciones = int(n_ecuaciones)
        self.puede_resolver = puede_resolver
        self.resolver_fn = resolver_fn


class Orquestador:
    def __init__(self, bloques):
        self.bloques = list(bloques)

    def resolver(self, max_iteraciones=None, **valores_iniciales):
        """
        Punto fijo: se recorren los bloques una y otra vez, cada uno
        rellenando lo que pueda, hasta que una pasada entera no cambie
        nada.

        Sobre max_iteraciones=None (el default): el tope se calcula a
        partir del numero de bloques en vez de ser una constante. El
        motivo esta medido, no supuesto -- en el peor orden posible
        (bloques de aguas abajo primero) cada pasada propaga UN bloque,
        asi que una cadena de N operaciones necesita ~N+2 pasadas. Con
        el tope fijo de antes (20, y 30 desde DiagramaCorrientes) un
        diagrama de ~29 equipos se quedaba a medias y el fallo era
        indistinguible de "faltan datos": completo=False, cero
        inconsistencias, cero errores, y el contador de grados de
        libertad diciendo GL=0 ("exactamente especificado"). O sea, se
        le decia al usuario que sus datos estaban bien, no se resolvia,
        y no se daba ningun motivo.

        len(bloques)+2 es cota superior segura para un diagrama sin
        lazos: en el peor caso cada pasada resuelve al menos un bloque.
        """
        if max_iteraciones is None:
            max_iteraciones = len(self.bloques) + 2
        pool = dict(valores_iniciales)
        for bloque in self.bloques:
            for v in bloque.variables:
                pool.setdefault(v, None)

        todas_variables = set(pool.keys())
        resueltos_por = {}
        resultados_bloques = {}
        errores_bloque = {}

        cambio = True
        iteraciones = 0
        while cambio and iteraciones < max_iteraciones:
            cambio = False
            iteraciones += 1
            for bloque in self.bloques:
                incognitas = [v for v in bloque.variables if pool[v] is None]
                if len(incognitas) == 0:
                    continue  # este bloque ya esta completo, nada que resolver
                incognitas_entrada = [v for v in bloque.variables_entrada if pool[v] is None]
                if not bloque.puede_resolver(len(incognitas_entrada)):
                    continue  # todavia no hay suficiente info para este bloque

                conocidos = {v: pool[v] for v in bloque.variables if pool[v] is not None}
                try:
                    resultado = bloque.resolver_fn(**conocidos)
                except Exception as e:
                    # Un bloque que no puede resolverse con los datos dados
                    # no debe tumbar todo el diagrama: se anota y se sigue
                    # con los demas. Antes, cualquier excepcion aqui
                    # abortaba la resolucion entera.
                    errores_bloque[bloque.nombre] = str(e)
                    continue
                resultados_bloques[bloque.nombre] = resultado

                # OJO: 'cambio' solo si de verdad se escribio algo. Antes
                # se ponia a True por el mero hecho de que el bloque
                # corriera, y muchisimos bloques devuelven {} cuando aun
                # no pueden decidir una direccion (el balance del CSTR, el
                # cierre de composicion con 2 huecos, la cinetica sin T...).
                # Con eso el bucle NUNCA terminaba antes de tiempo: agotaba
                # siempre el tope de pasadas aunque llevara rato sin
                # avanzar. Dos consecuencias medidas: trabajo inutil en
                # cada resolucion, y la bandera 'agotado_el_tope' daba
                # falsos positivos (marcaba como truncado un diagrama que
                # simplemente estaba incompleto por falta de datos).
                escribio = False
                for v in bloque.variables:
                    if pool[v] is None and resultado.get(v) is not None:
                        pool[v] = resultado[v]
                        resueltos_por[v] = bloque.nombre
                        escribio = True
                if escribio:
                    cambio = True

        incognitas_restantes = [v for v in todas_variables if pool[v] is None]
        # 'cambio' sigue en True solo si la ultima pasada aun estaba
        # avanzando: entonces el corte lo puso el tope, no el agotamiento
        # de informacion. Distinguir los dos casos es lo que evita
        # presentar un limite del solver como si fueran datos faltantes.
        agotado_el_tope = cambio and iteraciones >= max_iteraciones

        # Errores RANCIOS: un bloque puede fallar en una pasada temprana
        # (todavia sin datos) y acertar en una posterior. Su mensaje viejo
        # se reportaba igual como si fuera una ecuacion violada. Si el
        # bloque acabo resolviendo algo, su error ya no describe el
        # estado final y se descarta.
        bloques_que_resolvieron = set(resueltos_por.values())
        errores_bloque = {
            nombre: mensaje for nombre, mensaje in errores_bloque.items()
            if nombre not in bloques_que_resolvieron
        }

        return {
            "pool": pool,
            "resueltos_por": resueltos_por,
            "incognitas_restantes": incognitas_restantes,
            "resultados_bloques": resultados_bloques,
            "errores_bloque": errores_bloque,
            "completo": len(incognitas_restantes) == 0,
            "iteraciones": iteraciones,
            "agotado_el_tope": agotado_el_tope,
        }


import numpy as np


def verificar_consistencia(bloques, pool, tolerancia=1e-6):
    """
    Comprueba los bloques que quedaron COMPLETAMENTE determinados.

    Por que hace falta: el bucle de resolucion salta los bloques sin
    incognitas ("no hay nada que resolver"), asi que si el usuario da
    TODAS las variables de una ecuacion, esa ecuacion nunca se evalua y
    nadie se entera de que los datos no la cumplen. Se verifico con un
    caso real: F=100, z_F=0.5, D=20, x_D=0.8, B=80, x_B=0.1 cierra el
    balance total (100=20+80) pero viola el de componente por 26 mol/s,
    y el simulador reportaba "resuelto por completo".

    Metodo: por cada bloque completo se "olvida" una variable, se vuelve
    a calcular con las demas y se compara con el valor dado. Es generico
    -- funciona con cualquier bloque, invertible o no -- porque reutiliza
    el propio resolver del bloque. Se prefiere olvidar una variable de
    SALIDA, para que los bloques no invertibles (que exigen todas sus
    entradas) tambien se puedan comprobar.

    UN BLOQUE NO ES UNA ECUACION, y de ahi venia un agujero real
    ------------------------------------------------------------
    La primera version comparaba SOLO la variable olvidada y hacia `break`
    en cuanto una comprobacion salia bien, con el razonamiento de que "una
    comprobacion por bloque es suficiente". Eso vale si cada bloque es una
    ecuacion, y varios no lo son: el de la bomba empaqueta n+2 ecuaciones
    independientes (F, T, P y las composiciones), el mezclador 5, el
    divisor 10.

    Consecuencia medida: con una bomba a la que se le daban `s1.P`,
    `factor_P` Y `s2.P` a la vez -- tres condiciones incompatibles, porque
    3 x 101325 no es 100000 -- la primera comprobacion recaia sobre la
    igualdad de caudales, salia bien, y el `break` dejaba la ecuacion de
    presion sin evaluar NUNCA. El simulador respondia "resuelto por
    completo", sin incidencias, conservando la presion de salida dada.

    Dos cambios, y el primero no cuesta nada:

      1. **Se compara TODO lo que el bloque devuelve**, no solo la
         variable olvidada. Un `resolver_fn` devuelve un diccionario con
         las variables que ha podido calcular, y a menudo son varias: al
         omitir `s1.F` de la bomba, su resolver devuelve `s1.F` *y*
         `s2.P`, porque la rama de presion dispara con `factor_P` y
         `s1.P` presentes. Comparar las dos caza la incompatibilidad en
         la PRIMERA llamada, sin una sola evaluacion extra.
      2. Se sigue probando variables hasta haber ejercitado tantas
         ecuaciones como el bloque declara (`n_ecuaciones`), en vez de
         parar en la primera. El coste esta acotado por ese numero, y en
         los bloques no invertibles -- que devuelven todas sus salidas de
         una vez -- se cubre todo en una sola llamada igual que antes.

    Se para en cuanto aparece UNA incompatibilidad: para decirle a quien
    mira que sus datos no cuadran, la primera ya sirve, y seguir solo
    produciria mensajes repetidos sobre la misma causa.
    """
    inconsistencias = []
    for bloque in bloques:
        if any(pool.get(v) is None for v in bloque.variables):
            continue

        candidatas = [v for v in bloque.variables if v not in bloque.variables_entrada]
        candidatas += [v for v in bloque.variables if v in bloque.variables_entrada]

        # Cuantas ecuaciones distintas se han llegado a evaluar. Se mide
        # por variables recalculadas y comparadas: cada una ejercita al
        # menos una ecuacion del bloque.
        comprobadas = set()
        incompatible = None

        for objetivo in candidatas:
            if len(comprobadas) >= bloque.n_ecuaciones:
                break
            incognitas_entrada = 1 if objetivo in bloque.variables_entrada else 0
            if not bloque.puede_resolver(incognitas_entrada):
                continue
            conocidos = {v: pool[v] for v in bloque.variables if v != objetivo}
            try:
                resultado = bloque.resolver_fn(**conocidos)
            except Exception:
                continue  # este bloque no se deja invertir por aqui; se prueba otra variable
            if not isinstance(resultado, dict):
                continue

            # TODO lo devuelto, no solo `objetivo`. Lo que el bloque
            # recalcula sobre una variable que ya estaba en el pool es
            # precisamente una ecuacion que nadie habia evaluado.
            for variable, recalculado in resultado.items():
                if not isinstance(recalculado, (int, float, np.floating, np.integer)):
                    continue
                if pool.get(variable) is None:
                    continue
                dado = float(pool[variable])
                recalculado = float(recalculado)
                comprobadas.add(variable)
                escala = max(abs(dado), abs(recalculado), 1.0)
                if abs(dado - recalculado) / escala > tolerancia:
                    incompatible = (variable, dado, recalculado)
                    break
            if incompatible is not None:
                break

        if incompatible is not None:
            variable, dado, recalculado = incompatible
            inconsistencias.append({
                "bloque": bloque.nombre,
                "variable": variable,
                "dado": dado,
                "implicado": recalculado,
                "mensaje": (
                    f"{bloque.nombre}: diste {variable}={dado:.6g}, pero el resto de los datos "
                    f"implica {variable}={recalculado:.6g}. Los datos no son compatibles entre si."
                ),
            })
    return inconsistencias


def renombrar_bloque(bloque, mapa, nombre=None):
    """
    Devuelve el MISMO bloque con sus variables renombradas segun 'mapa'
    ({nombre_interno: nombre_global}); las que no aparezcan se quedan
    igual.

    Para que sirve: permite que las variables internas de una operacion
    (F, z_F, x_D, D...) apunten a las variables de las CORRIENTES a las
    que esta conectada en un diagrama ("s1.F", "s1.x0", "s2.x0"...), sin
    tocar el solver de la operacion. Asi varias operaciones que comparten
    una corriente comparten literalmente las mismas variables del pool, y
    la informacion fluye en CUALQUIER direccion (aguas abajo o aguas
    arriba) con el mismo bucle de punto fijo de siempre -- que es lo que
    un envoltorio no invertible por puertos no permitia.

    El renombrado es una biyeccion, asi que 'puede_resolver' (que cuenta
    incognitas) sigue significando exactamente lo mismo.
    """
    def traducir(v):
        return mapa.get(v, v)

    inverso = {}
    for v in bloque.variables:
        global_ = traducir(v)
        if global_ in inverso:
            raise ValueError(
                f"Mapa de renombrado invalido para el bloque {bloque.nombre!r}: "
                f"'{inverso[global_]}' y '{v}' apuntan ambos a '{global_}'."
            )
        inverso[global_] = v

    def resolver_fn(**conocidos):
        internos = {inverso[k]: v for k, v in conocidos.items() if k in inverso}
        resultado = bloque.resolver_fn(**internos)
        return {traducir(k): v for k, v in resultado.items()}

    return BloqueEcuaciones(
        nombre=nombre or bloque.nombre,
        variables=tuple(traducir(v) for v in bloque.variables),
        variables_entrada=tuple(traducir(v) for v in bloque.variables_entrada),
        puede_resolver=bloque.puede_resolver,
        resolver_fn=resolver_fn,
        n_ecuaciones=bloque.n_ecuaciones,
    )


# ---------------------------------------------------------------------
# Fabricas: envuelven los solvers ya existentes como BloqueEcuaciones.
# No se modifico BalanceMateriaGlobal ni SolucionadorMcCabeThiele para
# esto -- ambos ya devuelven, en su dict de resultado, todas las
# variables de su propio dominio (confirmado leyendo su codigo), asi que
# el adaptador solo necesita filtrar esas claves.
# ---------------------------------------------------------------------

def bloque_balance_materia(balance):
    """
    balance: instancia de BalanceMateriaGlobal (core/balance_materia.py).
    Aporta 2 ecuaciones (F=D+B; F*z_F=D*x_D+B*x_B) sobre 6 variables.
    BalanceMateriaGlobal.resolver admite hasta 2 incognitas (con 1 el
    sistema queda sobre-determinado y se resuelve por minimos cuadrados
    exigiendo residuo cero), asi que aqui puede_resolver acepta 1 o 2.
    Con 0 no hay nada que resolver, y el Orquestador ni siquiera llama a
    un bloque sin incognitas.
    """
    variables = ("F", "D", "B", "z_F", "x_D", "x_B")

    def resolver_fn(**conocidos):
        resultado = balance.resolver(**conocidos)
        return {v: resultado[v] for v in variables}

    return BloqueEcuaciones(
        nombre="Balance de Materia Global",
        variables=variables,
        n_ecuaciones=2,  # F=D+B  y  F*z_F=D*x_D+B*x_B
        puede_resolver=lambda n: 1 <= n <= 2,
        resolver_fn=resolver_fn,
    )


def bloque_mccabe_thiele(solucionador_mt):
    """
    solucionador_mt: instancia de SolucionadorMcCabeThiele
    (core/mccabe_thiele.py). Aporta 1 ecuacion (N=f(z_F,q,x_D,x_B,R))
    sobre 6 variables (incluyendo N, que en el propio resolver() se trata
    como el 'objetivo' pero que aqui, para el pool, es una variable mas:
    con las otras 5 conocidas, N sale por evaluacion directa; con N y 4 de
    las otras 5 conocidas, sale la 5a por diseño inverso).
    """
    variables = ("z_F", "q", "x_D", "x_B", "R", "N")

    def resolver_fn(**conocidos):
        resultado = solucionador_mt.resolver(**conocidos)
        return {v: resultado[v] for v in variables}

    return BloqueEcuaciones(
        nombre="McCabe-Thiele",
        variables=variables,
        puede_resolver=lambda n: n <= 1,
        resolver_fn=resolver_fn,
    )


def bloque_ponchon_savarit(solucionador_ps, q):
    """
    solucionador_ps: instancia de SolucionadorPonchonSavarit.
    q: condicion termica de la alimentacion. A diferencia de McCabe-
    Thiele, SolucionadorPonchonSavarit.resolver() NO trata a 'q' como una
    incognita resoluble (solo lo usa para derivar H_F internamente) --
    por eso aqui se pasa FIJO, no es una variable del pool.

    Aporta 1 ecuacion (N=f(z_F,x_D,x_B,Qc_D)) sobre 5 variables. QR_B no
    es una variable libre (queda derivada de Qc_D por colinealidad,
    dentro del propio EvaluadorPonchonSavarit) asi que tampoco esta en
    el pool.
    """
    variables = ("z_F", "x_D", "x_B", "Qc_D", "N")

    def resolver_fn(**conocidos):
        resultado = solucionador_ps.resolver(q=q, **conocidos)
        return {v: resultado[v] for v in variables}

    return BloqueEcuaciones(
        nombre="Ponchon-Savarit",
        variables=variables,
        puede_resolver=lambda n: n <= 1,
        resolver_fn=resolver_fn,
    )


def bloque_cargas_termicas(evaluador_mt):
    """
    evaluador_mt: instancia de EvaluadorMcCabeThiele (su metodo
    calcular_cargas_termicas). Especifico de McCabe-Thiele/CMO -- usa R,
    no Qc_D -- por eso NO se combina con el bloque de Ponchon-Savarit en
    el mismo orquestador (Ponchon-Savarit ya trae su propia contabilidad
    de energia via Qc_D/QR_B; conectar los dos contaria la energia dos
    veces con dos metodos distintos).

    A diferencia de los otros bloques, este NO es invertible: dadas sus
    8 entradas, calcula sus 6 salidas de una sola vez (no hay forma de
    pedirle, p.ej., D dado Q_c). Por eso usa 'variables_entrada' -- las
    salidas nunca cuentan como incognitas que bloqueen el disparo, y el
    bloque solo se activa cuando las 8 ENTRADAS estan completas
    (puede_resolver exige n==0 entre ellas, no "hasta cierto numero").

    Nota: no se conecta T_reflujo (subenfriamiento) para no complicar el
    bloque -- siempre asume reflujo saturado (T_reflujo=None dentro de
    calcular_cargas_termicas). Si se necesita, se puede agregar despues.
    """
    variables_entrada = ("D", "B", "F", "z_F", "x_D", "x_B", "R", "q")
    variables_salida = ("Q_c", "Q_R", "R_int", "V_barra", "T_D", "T_B")
    variables = variables_entrada + variables_salida

    def resolver_fn(**conocidos):
        resultado = evaluador_mt.calcular_cargas_termicas(
            D=conocidos["D"], B=conocidos["B"], F=conocidos["F"],
            z_F=conocidos["z_F"], x_D=conocidos["x_D"], x_B=conocidos["x_B"],
            R_ext=conocidos["R"], q=conocidos["q"],
        )
        return {
            "Q_c": resultado["Q_c"], "Q_R": resultado["Q_R"],
            "R_int": resultado["R_int"], "V_barra": resultado["V_barra"],
            "T_D": resultado["T_D"], "T_B": resultado["T_B"],
        }

    return BloqueEcuaciones(
        nombre="Cargas Termicas",
        variables=variables,
        variables_entrada=variables_entrada,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
    )


def bloque_cargas_termicas_ps(evaluador_ps, q):
    """
    Cargas termicas para Ponchon-Savarit. NO es el mismo bloque que
    bloque_cargas_termicas (ese usa R y CMO); aqui la energia sale de la
    propia construccion entalpica, que es justamente la ventaja del
    metodo: no supone flujo molar constante.

    Relaciones (todas consecuencia de las definiciones de los polos, no
    correlaciones nuevas):

        Q_c  = Qc_D * D                    [W]   (Qc_D en J/mol de destilado)
        QR_B = derivar_QR_B(...)           [J/mol de fondos] -- atado a Qc_D
               por la colinealidad Delta_D -- (z_F,H_F) -- Delta_B, o sea
               por el balance de energia GLOBAL; no es libre.
        Q_R  = QR_B * B                    [W]
        R    = Qc_D / (H_V(x_D) - H_L(x_D)) - 1

    La ultima merece justificacion porque conecta este metodo con el
    reflujo de toda la vida: con condensador total, el vapor que llega
    es V_1 = D*(R+1) y se condensa de H_V(x_D) a H_L(x_D), asi que
    Q_c = D*(R+1)*(H_V(x_D) - H_L(x_D)); dividiendo por D queda
    Qc_D = (R+1)*(H_V - H_L). Se despeja R de ahi. Verificado
    numericamente contra el balance global F*H_F + Q_R = D*H_D + B*H_B + Q_c.

    No invertible, igual que bloque_cargas_termicas: dadas las entradas
    calcula todas las salidas de una pasada.
    """
    variables_entrada = ("D", "B", "z_F", "x_D", "x_B", "Qc_D")
    variables_salida = ("Q_c", "Q_R", "QR_B", "R", "T_D", "T_B")
    variables = variables_entrada + variables_salida

    def resolver_fn(**conocidos):
        z_F, x_D, x_B = conocidos["z_F"], conocidos["x_D"], conocidos["x_B"]
        D, B, Qc_D = conocidos["D"], conocidos["B"], conocidos["Qc_D"]

        H_F = evaluador_ps.H_F_desde_q(z_F, q)
        QR_B = evaluador_ps.derivar_QR_B(z_F, x_D, x_B, Qc_D, H_F)

        salto_condensador = evaluador_ps.H_V(x_D) - evaluador_ps.H_L(x_D)
        R = Qc_D / salto_condensador - 1.0

        elv = evaluador_ps.calculadora_elv
        P = evaluador_ps.P_sistema
        T_D, _ = elv.burbuja_T(P, np.array([x_D, 1.0 - x_D]))
        T_B, _ = elv.burbuja_T(P, np.array([x_B, 1.0 - x_B]))

        return {
            "Q_c": float(Qc_D * D), "Q_R": float(QR_B * B),
            "QR_B": float(QR_B), "R": float(R),
            "T_D": float(T_D), "T_B": float(T_B),
        }

    return BloqueEcuaciones(
        nombre="Cargas Termicas (Ponchon-Savarit)",
        variables=variables,
        variables_entrada=variables_entrada,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
    )


def bloque_fug(analizador_fug):
    """
    analizador_fug: instancia de AnalizadorFUG (core/fug.py), ya
    construida con z_F, q, P_sistema, idx_LK, idx_HK fijos -- son datos
    del problema, no incognitas del orquestador (mismo tratamiento que
    'q' en bloque_ponchon_savarit).

    NO invertible (mismo patron que bloque_cargas_termicas): dadas sus 4
    entradas, reporte_completo calcula todo lo demas de una sola pasada;
    no hay forma de, p.ej., pedirle R dado N.

    Primer bloque cuyas variables de pool son VECTORES (x_D, x_B, d, b
    son arrays de n componentes, no floats): no hizo falta cambiar
    Orquestador/BloqueEcuaciones para esto -- el bucle de resolucion
    solo hace 'pool[v] is None' (identidad) y nunca aritmetica ni
    verdad-o-falso sobre el valor en si, asi que ya era agnostico al
    tipo. Se verifico corriendolo (ver ejemplo_orquestador.py) antes de
    confiar en esta afirmacion.

    F entra como variable_entrada porque AnalizadorFUG trabaja
    normalizado a F=1 (z_F suma 1) -- 'D'/'B'/'d'/'b' que devuelve
    reporte_completo son FRACCIONES de esa alimentacion normalizada. Se
    escalan aqui por F antes de escribirlas al pool, para que "D"/"B"
    signifiquen lo mismo (flujo molar real) que en bloque_balance_materia
    y bloque_cargas_termicas.

    Este bloque (y bloque_cargas_termicas_fug) son para un Orquestador
    dedicado a FUG -- no se combinan con los bloques binarios
    (bloque_balance_materia/bloque_mccabe_thiele/bloque_ponchon_savarit)
    porque 'z_F'/'x_D'/'x_B' ahi son floats (fraccion molar de UN
    componente), no arrays.
    """
    variables_entrada = ("recuperacion_LK_D", "recuperacion_HK_B", "R", "F")
    variables_salida = ("N_min", "R_min", "N", "theta", "T_D", "T_F", "T_B",
                         "x_D", "x_B", "d", "b", "D", "B")
    variables = variables_entrada + variables_salida

    def resolver_fn(**conocidos):
        reporte = analizador_fug.reporte_completo(
            recuperacion_LK_D=conocidos["recuperacion_LK_D"],
            recuperacion_HK_B=conocidos["recuperacion_HK_B"],
            R=conocidos["R"],
        )
        F = conocidos["F"]
        return {
            "N_min": reporte["N_min"], "R_min": reporte["R_min"], "N": reporte["N"],
            "theta": reporte["theta"], "T_D": reporte["T_D"], "T_F": reporte["T_F"],
            "T_B": reporte["T_B"], "x_D": reporte["x_D"], "x_B": reporte["x_B"],
            "d": reporte["d"] * F, "b": reporte["b"] * F,
            "D": reporte["D"] * F, "B": reporte["B"] * F,
        }

    return BloqueEcuaciones(
        nombre="FUG",
        variables=variables,
        variables_entrada=variables_entrada,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
    )


def bloque_cargas_termicas_fug(analizador_fug):
    """
    Cargas termicas para el bloque FUG -- mismo patron no invertible que
    bloque_cargas_termicas, pero via AnalizadorFUG.calcular_cargas_termicas
    (n componentes) en vez de la version binaria de EvaluadorMcCabeThiele.
    Depende de que 'FUG' ya haya corrido en el mismo orquestador: D, B,
    x_D, x_B, T_D, T_B, R son salida de bloque_fug; F es la misma entrada
    que ya uso bloque_fug para escalar fracciones a flujos.
    """
    variables_entrada = ("D", "B", "F", "x_D", "x_B", "T_D", "T_B", "R")
    variables_salida = ("Q_c", "Q_R", "R_int", "V_barra", "T_reflujo",
                         "Hvap_D", "Hvap_B", "Cp_D")
    variables = variables_entrada + variables_salida

    def resolver_fn(**conocidos):
        return analizador_fug.calcular_cargas_termicas(
            D=conocidos["D"], B=conocidos["B"], F=conocidos["F"],
            x_D=conocidos["x_D"], x_B=conocidos["x_B"],
            T_D=conocidos["T_D"], T_B=conocidos["T_B"], R_ext=conocidos["R"],
        )

    return BloqueEcuaciones(
        nombre="Cargas Termicas FUG",
        variables=variables,
        variables_entrada=variables_entrada,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
    )
