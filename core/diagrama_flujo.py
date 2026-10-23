"""
DiagramaFlujo: conecta operaciones unitarias autocontenidas (columnas,
reactores, bombas, mezcladores...) mediante Corrientes -- las "flechas"
pedidas. NO reinventa un motor de resolucion nuevo: cada operacion se
envuelve como un OperacionUnitaria (mismo patron que BloqueEcuaciones de
Orquestador, ver core/orquestador.py) y cada CONEXION se traduce a un
bloque "cable" -- una operacion no invertible trivial que solo copia el
valor de la clave de salida del origen a la clave de entrada del
destino. El grafo completo (operaciones + cables) se resuelve con un
Orquestador normal, sin cambiar nada de su motor de iteracion de punto
fijo (ya verificado con vectores/Corrientes -- solo compara 'is None').

Nombres de puerto GLOBALES: cada operacion tiene un nombre unico
("columna1", "mezclador1"...) y cada puerto suyo vive en el pool
compartido como "nombre_operacion.puerto" (p.ej. "columna1.D"). Esto
evita el choque de nombres que tendrian dos columnas del mismo metodo si
compartieran claves como "D" directamente -- cada operacion vive en su
propio espacio de nombres, y conectar dos operaciones es agregar un
cable entre sus claves calificadas, no fusionar sus pools.

Reciclos: sin ayuda, un ciclo real (A necesita la salida de B, B
necesita la salida de A, directa o transitivamente) nunca converge con
una sola pasada de punto fijo -- ninguno de los dos puede dispararse
primero, y Orquestador.resolver() lo reporta correctamente como
incognitas restantes (no intenta adivinar nada, que es el
comportamiento correcto sin mas informacion).

resolver_con_reciclo() rompe el ciclo con SUSTITUCION SUCESIVA, el
metodo mas simple y estandar en simulacion de procesos (no Wegstein ni
aceleracion todavia -- se puede agregar despues sin cambiar la interfaz,
ver nota abajo): se elige una conexion del ciclo como "corriente de
ruptura", se EXCLUYE su cable del grafo, se alimenta un valor supuesto
directamente en la clave de ENTRADA que ese cable habria llenado, se
resuelve el resto del diagrama, y se lee el valor que de verdad se
calculo en la clave de SALIDA del origen (que al no estar cableada a su
destino en este armado, el Orquestador sí la calcula libremente). Si el
supuesto y el recalculado coinciden dentro de tolerancia, convergio; si
no, el recalculado pasa a ser el nuevo supuesto, y se repite.
"""

import numpy as np

from core.orquestador import Orquestador, BloqueEcuaciones


class OperacionUnitaria:
    """
    Envoltura de una operacion (columna, mezclador, bomba, lo que sea)
    como bloque de Orquestador. TODAS sus variables -- sean Corrientes
    en un puerto o parametros escalares (R, recuperaciones, N...) -- se
    califican con el nombre de la operacion en el pool compartido,
    uniformemente. No se distingue "puerto" de "parametro" a proposito:
    a Orquestador ya le da igual el tipo del valor, y calificar TODO
    (no solo las corrientes) evita que dos instancias de la misma
    operacion choquen tambien en un parametro compartido como "R".

    variables_entrada/variables_salida : nombres LOCALES (p.ej. "F",
        "D", "R"); DiagramaFlujo los califica como "nombre_operacion.variable".
    resolver_fn(**entradas_locales) -> dict con las variables de SALIDA
        (nombres locales, sin calificar).
    """
    def __init__(self, nombre, variables_entrada, variables_salida, resolver_fn):
        self.nombre = nombre
        self.variables_entrada = tuple(variables_entrada)
        self.variables_salida = tuple(variables_salida)
        self.resolver_fn = resolver_fn

    def _clave(self, variable):
        return f"{self.nombre}.{variable}"

    def a_bloque(self):
        claves_entrada = tuple(self._clave(v) for v in self.variables_entrada)
        claves_salida = tuple(self._clave(v) for v in self.variables_salida)
        variables = claves_entrada + claves_salida

        def resolver_fn_calificado(**conocidos):
            entradas_locales = {
                v: conocidos[self._clave(v)] for v in self.variables_entrada
                if self._clave(v) in conocidos
            }
            resultado = self.resolver_fn(**entradas_locales)
            return {
                self._clave(v): resultado[v] for v in self.variables_salida
                if v in resultado
            }

        return BloqueEcuaciones(
            nombre=self.nombre,
            variables=variables,
            variables_entrada=claves_entrada,
            puede_resolver=lambda n: n == 0,
            resolver_fn=resolver_fn_calificado,
        )


def _bloque_cable(op_origen, puerto_salida, op_destino, puerto_entrada):
    clave_origen = f"{op_origen}.{puerto_salida}"
    clave_destino = f"{op_destino}.{puerto_entrada}"

    def resolver_fn(**conocidos):
        return {clave_destino: conocidos[clave_origen]}

    return BloqueEcuaciones(
        nombre=f"Cable {clave_origen} -> {clave_destino}",
        variables=(clave_origen, clave_destino),
        variables_entrada=(clave_origen,),
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
    )


def _corrientes_cercanas(a, b, tolerancia):
    flujo_ok = abs(a.flujo_molar - b.flujo_molar) <= tolerancia * max(a.flujo_molar, b.flujo_molar, 1.0)
    T_ok = abs(a.T - b.T) <= tolerancia * max(a.T, b.T, 1.0)
    comp_ok = np.max(np.abs(a.composicion - b.composicion)) <= tolerancia
    return bool(flujo_ok and T_ok and comp_ok)


class DiagramaFlujo:
    def __init__(self):
        self.operaciones = {}
        self.conexiones = []  # lista de tuplas (op_origen, puerto_salida, op_destino, puerto_entrada)

    def agregar_operacion(self, operacion):
        if operacion.nombre in self.operaciones:
            raise ValueError(f"Ya existe una operacion llamada {operacion.nombre!r}.")
        self.operaciones[operacion.nombre] = operacion

    def conectar(self, op_origen, puerto_salida, op_destino, puerto_entrada):
        if op_origen not in self.operaciones:
            raise ValueError(f"Operacion de origen desconocida: {op_origen!r}.")
        if op_destino not in self.operaciones:
            raise ValueError(f"Operacion de destino desconocida: {op_destino!r}.")
        self.conexiones.append((op_origen, puerto_salida, op_destino, puerto_entrada))

    def _construir_orquestador(self, excluir_conexion=None):
        bloques = [op.a_bloque() for op in self.operaciones.values()]
        for conexion in self.conexiones:
            if conexion == excluir_conexion:
                continue
            bloques.append(_bloque_cable(*conexion))
        return Orquestador(bloques)

    def resolver(self, max_iteraciones=None, **valores_conocidos):
        """
        valores_conocidos: claves calificadas ('operacion.puerto' o parametro sin calificar).

        max_iteraciones=None (por omision) deja que el Orquestador calcule su
        tope con el numero de bloques (len + 2); un numero fijo (antes 20)
        cortaba las cadenas largas. Un tope pedido explicitamente se respeta.
        """
        return self._construir_orquestador().resolver(max_iteraciones=max_iteraciones, **valores_conocidos)

    def resolver_con_reciclo(self, conexion_ruptura, valor_inicial, tolerancia=1e-4,
                              max_iteraciones_reciclo=50, max_iteraciones_internas=None,
                              **valores_conocidos):
        """
        conexion_ruptura: tupla (op_origen, puerto_salida, op_destino,
            puerto_entrada) -- debe ser una de las conexiones agregadas
            con .conectar(), y debe estar dentro del ciclo real.
        valor_inicial: Corriente supuesta para arrancar la sustitucion
            sucesiva en la clave de entrada del destino.
        """
        if conexion_ruptura not in self.conexiones:
            raise ValueError(f"{conexion_ruptura!r} no es una conexion de este diagrama.")

        op_origen, puerto_salida, op_destino, puerto_entrada = conexion_ruptura
        clave_origen = f"{op_origen}.{puerto_salida}"
        clave_destino = f"{op_destino}.{puerto_entrada}"

        orquestador = self._construir_orquestador(excluir_conexion=conexion_ruptura)

        supuesto = valor_inicial
        historial = []
        resultado = None
        for iteracion in range(1, max_iteraciones_reciclo + 1):
            valores = dict(valores_conocidos)
            valores[clave_destino] = supuesto
            resultado = orquestador.resolver(max_iteraciones=max_iteraciones_internas, **valores)

            recalculado = resultado["pool"].get(clave_origen)
            if recalculado is None:
                raise RuntimeError(
                    f"'{clave_origen}' no se pudo calcular sin la conexion de ruptura -- "
                    "revisa que el resto del diagrama tenga toda la informacion que le falta."
                )

            convergio = _corrientes_cercanas(supuesto, recalculado, tolerancia)
            historial.append({"iteracion": iteracion, "supuesto": supuesto, "recalculado": recalculado})
            if convergio:
                resultado["convergencia_reciclo"] = True
                resultado["iteraciones_reciclo"] = iteracion
                resultado["historial_reciclo"] = historial
                return resultado
            supuesto = recalculado

        resultado["convergencia_reciclo"] = False
        resultado["iteraciones_reciclo"] = max_iteraciones_reciclo
        resultado["historial_reciclo"] = historial
        return resultado
