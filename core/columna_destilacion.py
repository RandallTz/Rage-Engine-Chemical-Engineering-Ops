"""
ColumnaDestilacion: selector de metodo para una columna de destilacion.
Encapsula la construccion del Orquestador correcto (McCabe-Thiele,
Ponchon-Savarit o FUG) segun el metodo elegido -- el llamador ya no
arma la lista de bloques a mano, solo dice que metodo quiere y le pasa
los solvers de ese metodo.

Por que esto y no un Orquestador unico compartido entre metodos: no es
solo que los bloques binarios (z_F/x_D/x_B como floats) choquen de
nombre con los de FUG (mismos nombres como arrays de n componentes) --
el problema es mas general. DOS columnas del MISMO metodo en un futuro
flowsheet tambien chocarian en nombres como "D"/"R"/"x_D" si compartieran
un solo pool. La solucion que sí escala a un flowsheet con operaciones
conectadas por flechas (pendiente, ver roadmap.md) es que cada operacion
unitaria sea AUTOCONTENIDA: su Orquestador interno es un detalle de
implementacion privado de esta clase, no algo que se comparte por
nombre con otras columnas. Cuando se construya la abstraccion de
Corriente (Stream), las conexiones entre columnas se haran pasando esas
corrientes explicitas entre instancias de ColumnaDestilacion, no
fusionando sus pools.

Los bloques de Cargas Termicas (binario o FUG) se agregan siempre --
son bloques NO invertibles que solo se disparan cuando TODAS sus
entradas estan completas (ver bloque_cargas_termicas en
core/orquestador.py); si el llamador no da suficiente informacion para
dispararlos, simplemente no corren -- agregarlos siempre no fuerza
nuevas entradas obligatorias.
"""

import numpy as np

from core.balance_materia import BalanceMateriaGlobal
from core.orquestador import (
    Orquestador,
    bloque_balance_materia,
    bloque_mccabe_thiele,
    bloque_ponchon_savarit,
    bloque_cargas_termicas,
    bloque_fug,
    bloque_cargas_termicas_fug,
)
from core.corriente import Corriente
from core.diagrama_flujo import OperacionUnitaria

METODOS_VALIDOS = ("mccabe_thiele", "ponchon_savarit", "fug")


class ColumnaDestilacion:
    def __init__(self, metodo, **solvers):
        """
        metodo : uno de METODOS_VALIDOS.
        solvers: los objetos ya construidos que necesita ESE metodo:
            - "mccabe_thiele" : solucionador_mt (SolucionadorMcCabeThiele).
            - "ponchon_savarit": solucionador_ps (SolucionadorPonchonSavarit), q.
            - "fug"           : analizador_fug (AnalizadorFUG).
        """
        if metodo not in METODOS_VALIDOS:
            raise ValueError(f"metodo debe ser uno de {METODOS_VALIDOS}, se recibio {metodo!r}.")
        self.metodo = metodo
        self._solvers = solvers
        self._orquestador = self._construir_orquestador(metodo, solvers)

    @staticmethod
    def _construir_orquestador(metodo, solvers):
        if metodo == "mccabe_thiele":
            solucionador_mt = solvers["solucionador_mt"]
            bloques = [
                bloque_balance_materia(BalanceMateriaGlobal()),
                bloque_mccabe_thiele(solucionador_mt),
                bloque_cargas_termicas(solucionador_mt.evaluador),
            ]
            return Orquestador(bloques)

        if metodo == "ponchon_savarit":
            solucionador_ps = solvers["solucionador_ps"]
            q = solvers["q"]
            bloques = [
                bloque_balance_materia(BalanceMateriaGlobal()),
                bloque_ponchon_savarit(solucionador_ps, q),
            ]
            return Orquestador(bloques)

        if metodo == "fug":
            analizador_fug = solvers["analizador_fug"]
            bloques = [
                bloque_fug(analizador_fug),
                bloque_cargas_termicas_fug(analizador_fug),
            ]
            return Orquestador(bloques)

        raise AssertionError("metodo ya validado en __init__, no deberia llegar aqui.")

    def resolver(self, **valores):
        """Mismos nombres de variable que el Orquestador interno de este metodo."""
        return self._orquestador.resolver(**valores)

    def _nombres(self):
        if self.metodo == "fug":
            return self._solvers["analizador_fug"].nombres
        return self._evaluador().nombres

    def _evaluador(self):
        if self.metodo == "mccabe_thiele":
            return self._solvers["solucionador_mt"].evaluador
        if self.metodo == "ponchon_savarit":
            return self._solvers["solucionador_ps"].evaluador
        raise AssertionError("solo binarios tienen 'evaluador' -- fug no llega aqui.")

    def resolver_desde_feed(self, F, **valores_extra):
        """
        Resuelve dado un Corriente de alimentacion F -- traduce F a
        flujo_molar/z_F segun el metodo (vector completo para 'fug',
        fraccion de nombres[0] -- el 'ligero', convencion ya establecida
        en EvaluadorMcCabeThiele/EvaluadorPonchonSavarit -- para los
        binarios), llama a self.resolver(...), y adjunta
        'corriente_D'/'corriente_B' (objetos Corriente, o None si el
        metodo no logro resolverlas) al resultado -- sin quitar nada de
        lo que self.resolver() ya trae (pool, completo,
        incognitas_restantes...). La P de D/B se toma de la P de F -- el
        proyecto no modela caida de presion en la columna.

        Reutilizado por a_operacion_unitaria (DiagramaFlujo) y por la
        API web (backend/nucleo.py) -- ambos necesitan la misma
        traduccion Corriente<->pool, pero uno descarta casi todo el
        resultado (solo le importan D/B/variables_salida_extra) y el
        otro necesita el diagnostico completo (completo,
        incognitas_restantes) para reportarlo al usuario.

        BUG REAL encontrado y corregido al probar la primera version de
        este metodo: para 'fug', z_F NO es una variable de pool de
        bloque_fug -- AnalizadorFUG.reporte_completo siempre usa
        self.z_F, fijado en el CONSTRUCTOR del analizador (ver
        core/fug.py). La primera version de este metodo escribia
        F.composicion en valores["z_F"] como si fuera a usarse, pero
        Orquestador simplemente la ignora (nadie la lee) -- si F traia
        una composicion DISTINTA a la de construccion, el resultado
        usaba silenciosamente la de construccion, sin avisar. Se
        verifico pasando una composicion deliberadamente distinta y
        confirmando que el resultado no cambiaba. Como generalizar
        AnalizadorFUG para aceptar z_F dinamico tocaria codigo ya
        verificado a fondo (bootstrap, N_min, Underwood -- todos
        derivados de self.z_F), se opto por lo mas seguro: validar y
        fallar alto en vez de fallar en silencio. Un feed FUG con
        composicion distinta necesita su propia instancia de
        AnalizadorFUG.
        """
        nombres = self._nombres()
        es_fug = self.metodo == "fug"

        # Los componentes de la corriente y los de la columna tienen que
        # ser LOS MISMOS y en el MISMO orden: mas abajo se indexa la
        # composicion por posicion (z_F vectorial en fug) o se busca
        # nombres[0] dentro de la corriente (binarios). Sin este chequeo,
        # una corriente con otra lista de componentes fallaba con un
        # "'<componente>' is not in list" de .index(), que no dice nada
        # sobre la causa real.
        if list(F.nombres) != list(nombres):
            raise ValueError(
                f"Los componentes de la corriente de alimentacion {list(F.nombres)} no coinciden "
                f"con los de la columna {list(nombres)}. Deben ser los mismos y en el mismo orden "
                "-- definelos una sola vez para toda la simulacion."
            )

        if es_fug:
            z_F_construccion = self._solvers["analizador_fug"].z_F
            if not np.allclose(F.composicion, z_F_construccion, atol=1e-6):
                raise ValueError(
                    "La composicion de la Corriente de alimentacion "
                    f"({F.composicion}) no coincide con la z_F con la que "
                    f"se construyo AnalizadorFUG ({z_F_construccion}). FUG "
                    "no admite cambiar la composicion de alimentacion "
                    "despues de construido -- crea una nueva instancia de "
                    "AnalizadorFUG (y de ColumnaDestilacion) con la "
                    "composicion correcta."
                )

        valores = dict(valores_extra)
        valores["F"] = F.flujo_molar
        valores["z_F"] = F.composicion if es_fug else F.fraccion(nombres[0])

        resultado = self.resolver(**valores)
        pool = resultado["pool"]

        corriente_D = corriente_B = None
        if es_fug:
            if pool.get("D") is not None and pool.get("x_D") is not None:
                corriente_D = Corriente(nombres, pool["x_D"], pool["D"], pool["T_D"], F.P)
            if pool.get("B") is not None and pool.get("x_B") is not None:
                corriente_B = Corriente(nombres, pool["x_B"], pool["B"], pool["T_B"], F.P)
        else:
            evaluador = self._evaluador()
            if pool.get("D") is not None and pool.get("x_D") is not None:
                x_D_vec = np.array([pool["x_D"], 1.0 - pool["x_D"]])
                T_D, _ = evaluador.calculadora_elv.burbuja_T(evaluador.P_sistema, x_D_vec)
                corriente_D = Corriente(nombres, x_D_vec, pool["D"], T_D, F.P)
            if pool.get("B") is not None and pool.get("x_B") is not None:
                x_B_vec = np.array([pool["x_B"], 1.0 - pool["x_B"]])
                T_B, _ = evaluador.calculadora_elv.burbuja_T(evaluador.P_sistema, x_B_vec)
                corriente_B = Corriente(nombres, x_B_vec, pool["B"], T_B, F.P)

        resultado["corriente_D"] = corriente_D
        resultado["corriente_B"] = corriente_B
        return resultado

    def a_operacion_unitaria(self, nombre, variables_entrada_extra=(), variables_salida_extra=()):
        """
        Expone esta columna como OperacionUnitaria para conectarla en un
        DiagramaFlujo (core/diagrama_flujo.py). "F" es SIEMPRE una
        Corriente de entrada (el feed viene de una conexion o se da
        directo); "D"/"B" son Corrientes de salida cuando el metodo
        logra resolverlas.

        Simplificacion deliberada frente a self.resolver(): ColumnaDestilacion
        es flexible en grados de libertad (cualquier variable puede ser
        la incognita); una OperacionUnitaria de DiagramaFlujo, en
        cambio, es un bloque NO invertible (solo se dispara cuando TODAS
        sus entradas estan dadas, igual que bloque_cargas_termicas) --
        por eso aqui el llamador debe decir explicitamente, para ESTE
        diagrama, cuales de las variables del metodo entran conocidas
        (variables_entrada_extra) y cuales espera que salgan resueltas
        (variables_salida_extra). Es la misma eleccion de grados de
        libertad que ya se hace al llamar a resolver() directamente,
        solo que fijada de antemano para que el nodo sepa cuando puede
        dispararse dentro del grafo.
        """
        variables_entrada = ("F",) + tuple(variables_entrada_extra)
        variables_salida = ("D", "B") + tuple(variables_salida_extra)

        def resolver_fn(**entradas_locales):
            F_corriente = entradas_locales["F"]
            valores_extra = {v: entradas_locales[v] for v in variables_entrada_extra if v in entradas_locales}
            resultado = self.resolver_desde_feed(F_corriente, **valores_extra)

            salida = {}
            if resultado["corriente_D"] is not None:
                salida["D"] = resultado["corriente_D"]
            if resultado["corriente_B"] is not None:
                salida["B"] = resultado["corriente_B"]
            for v in variables_salida_extra:
                if resultado["pool"].get(v) is not None:
                    salida[v] = resultado["pool"][v]
            return salida

        return OperacionUnitaria(nombre, variables_entrada, variables_salida, resolver_fn)
