"""
Especificaciones de diseño: "ajusta X hasta que Y valga T".

Qué cambia esto. Hasta ahora el simulador contestaba *"con estos datos,
¿cuánto da?"*. Una especificación de diseño contesta la pregunta inversa,
que es la que se hace de verdad al diseñar: *"quiero que el destilado
salga al 99 %; ¿qué reflujo hace falta?"*.

Dentro de UN bloque eso ya funcionaba — `SolucionadorMcCabeThiele` da el
R que produce N etapas — porque esos bloques son invertibles. Lo que no
había era la versión a nivel de DIAGRAMA, donde la variable que se mueve
y el objetivo que se persigue están en equipos distintos y con un reciclo
en medio.

Por qué encaja sin forzar nada:

  - El pool es plano y las variables tienen nombre global (`s1.F`,
    `col1.R`), así que una especificación es literalmente un par de
    nombres. No hace falta tubería para cruzar el diagrama.
  - El conteo de grados de libertad ya existe y es estructural: una
    especificación añade UNA ecuación y nada más (la variable manipulada
    YA era incógnita, justo porque no se da como dato), así que
    `grados_de_libertad` confirma solo que el problema queda cerrado en
    vez de haberlo de razonar a mano. Ver
    `grados_de_libertad_con_especificaciones` más abajo: esta cuenta es
    fácil de equivocar.
  - El lazo exterior de los reciclos tiene exactamente esta forma
    (suponer, resolver, mirar el error, corregir), así que esto es
    orquestación de maquinaria ya validada, no maquinaria nueva.

Zona libre de pint: floats en SI.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.optimize import brentq, root


@dataclass
class Especificacion:
    """
    Una ecuación más: objetivo == valor, moviendo 'manipulada'.

    objetivo   : variable del pool que se quiere fijar ("dest.x0")
    valor      : el valor que debe tomar
    manipulada : variable del pool que se mueve para conseguirlo ("col1.R")
    minimo/maximo: rango en el que buscar. No es un detalle de
                 implementación: casi todas las variables de proceso
                 tienen un rango físico (un reflujo no es negativo, una
                 fracción no pasa de 1), y acotar la búsqueda es lo que
                 evita que el solver se vaya a un sitio donde el diagrama
                 ni siquiera se puede resolver.
    """
    objetivo: str
    valor: float
    manipulada: str
    minimo: float
    maximo: float
    tolerancia: float = 1e-7

    def __post_init__(self):
        if self.minimo >= self.maximo:
            raise ValueError(
                f"El rango de búsqueda de '{self.manipulada}' está al revés o vacío "
                f"({self.minimo} .. {self.maximo})."
            )
        if self.objetivo == self.manipulada:
            raise ValueError(
                f"'{self.objetivo}' no puede ser a la vez el objetivo y la variable que se "
                "mueve: eso no es una especificación, es darle un valor."
            )


class ResolutorEspecificaciones:
    """
    Lazo exterior sobre `resolver()`. Cada evaluación es una resolución
    COMPLETA del diagrama, reciclos incluidos; por eso conviene que las
    especificaciones sean pocas y con rangos ajustados.
    """

    def __init__(self, diagrama, especificaciones, valores, **opciones_resolver):
        self.diagrama = diagrama
        self.specs = list(especificaciones)
        self.valores = dict(valores)
        self.opciones = opciones_resolver
        self.evaluaciones = 0
        self.historial = []

        for s in self.specs:
            if self.valores.get(s.manipulada) is not None:
                raise ValueError(
                    f"'{s.manipulada}' se da como dato Y como variable manipulada. Una "
                    "especificación la convierte en incógnita: quítala de los datos, o "
                    "quita la especificación."
                )

    # ------------------------------------------------------------------
    def _resolver_con(self, candidatos):
        """Resuelve el diagrama fijando las variables manipuladas a 'candidatos'."""
        datos = dict(self.valores)
        for s, x in zip(self.specs, candidatos):
            datos[s.manipulada] = float(x)
        self.evaluaciones += 1
        return self.diagrama.resolver(**datos, **self.opciones)

    def _residuos(self, candidatos):
        resultado = self._resolver_con(candidatos)
        pool = resultado["pool"]
        residuos = []
        for s in self.specs:
            obtenido = pool.get(s.objetivo)
            if obtenido is None:
                # El objetivo no se pudo calcular con ese valor. No se
                # inventa un residuo: se dice qué pasó, porque un NaN
                # silencioso aquí haría que el solver vagara sin sentido.
                #
                # Y se señala la causa MAS probable, que no es la que uno
                # supondría: casi siempre el diagrama está bien planteado
                # y lo que pasa es que ESE valor concreto de la variable
                # manipulada no es físicamente viable. El caso típico es
                # un reflujo por debajo del mínimo, donde harían falta
                # infinitas etapas. Antes el mensaje mandaba a buscar
                # datos que faltaran, que es justo donde no estaba.
                x = candidatos[self.specs.index(s)]
                motivos = [m for n, m in (self.diagrama.resolver(
                    **{**self.valores, s.manipulada: float(x)}
                ).get("errores_bloque") or {}).items()]
                pista = f" El diagrama informa: {motivos[0][:160]}" if motivos else ""
                raise ValueError(
                    f"Con {s.manipulada}={x:.6g}, el diagrama no llega a determinar "
                    f"'{s.objetivo}', así que no hay residuo que medir. Lo más probable es "
                    f"que ese valor de '{s.manipulada}' no sea viable (un reflujo por debajo "
                    f"del mínimo, por ejemplo): prueba un rango de búsqueda más estrecho."
                    + pista
                )
            residuos.append(float(obtenido) - s.valor)
        self.historial.append((list(map(float, candidatos)), list(residuos)))
        return residuos

    # ------------------------------------------------------------------
    def resolver(self):
        if not self.specs:
            return self.diagrama.resolver(**self.valores, **self.opciones)
        if len(self.specs) == 1:
            return self._una()
        return self._varias()

    def _una(self):
        """
        Una sola especificación: brentq sobre la variable manipulada.

        Se prefiere a un método de Newton porque NO necesita derivadas
        (que aquí costarían una resolución completa del diagrama cada una)
        y porque, teniendo el cambio de signo, no se puede escapar del
        rango físico.
        """
        s = self.specs[0]

        def f(x):
            return self._residuos([x])[0]

        try:
            r_min, r_max = f(s.minimo), f(s.maximo)
        except Exception as e:
            raise ValueError(
                f"No se pudo evaluar la especificación en los extremos del rango "
                f"[{s.minimo:.6g}, {s.maximo:.6g}] de '{s.manipulada}': {e}"
            ) from e

        if np.sign(r_min) == np.sign(r_max):
            alcanzado = sorted([s.valor + r_min, s.valor + r_max])
            raise ValueError(
                f"'{s.objetivo}' no alcanza {s.valor:.6g} con '{s.manipulada}' entre "
                f"{s.minimo:.6g} y {s.maximo:.6g}: en ese rango solo recorre "
                f"[{alcanzado[0]:.6g}, {alcanzado[1]:.6g}]. Amplía el rango, o el objetivo "
                "no es alcanzable con esa variable en este diagrama."
            )

        x = brentq(f, s.minimo, s.maximo, xtol=s.tolerancia, rtol=1e-12)
        resultado = self._resolver_con([x])
        return self._informar(resultado, [x])

    def _varias(self):
        """
        Varias a la vez: sistema no lineal con `root`.

        Los residuos se ESCALAN por el valor objetivo. Sin escalar, una
        especificación sobre una fracción molar (orden 1) y otra sobre un
        calor (orden 10^6) no pesan lo mismo, y el solver sacrifica la
        primera para afinar la segunda -- el mismo problema que ya apareció
        en el reactor acoplado.
        """
        escala = np.array([max(abs(s.valor), 1e-9) for s in self.specs])
        centro = np.array([0.5 * (s.minimo + s.maximo) for s in self.specs])

        def f(v):
            v_acotado = np.array([
                min(max(x, s.minimo), s.maximo) for x, s in zip(v, self.specs)
            ])
            return np.array(self._residuos(v_acotado)) / escala

        solucion = root(f, centro, method="hybr")
        x = np.array([min(max(v, s.minimo), s.maximo)
                      for v, s in zip(solucion.x, self.specs)])
        residual = float(np.max(np.abs(f(x))))
        # Mismo criterio que en el resto del proyecto: no se confía en
        # sol.success, se exige que el residuo sea pequeño de verdad.
        if not np.isfinite(residual) or residual > 1e-6:
            detalle = ", ".join(
                f"{s.objetivo}→{s.valor:.6g} con {s.manipulada}={xi:.6g}"
                for s, xi in zip(self.specs, x)
            )
            raise ValueError(
                f"Las {len(self.specs)} especificaciones no se pudieron cumplir a la vez "
                f"(residuo relativo {residual:.3e}). Último intento: {detalle}. "
                "Puede que se contradigan entre sí, o que una de las variables manipuladas "
                "no influya de verdad sobre su objetivo."
            )
        resultado = self._resolver_con(x)
        return self._informar(resultado, x)

    def _informar(self, resultado, valores_finales):
        pool = resultado["pool"]
        resultado["especificaciones"] = {
            "cumplidas": [
                {
                    "objetivo": s.objetivo, "pedido": s.valor,
                    "obtenido": pool.get(s.objetivo),
                    "error": (pool.get(s.objetivo) - s.valor)
                             if pool.get(s.objetivo) is not None else None,
                    "manipulada": s.manipulada, "valor": float(x),
                }
                for s, x in zip(self.specs, valores_finales)
            ],
            "evaluaciones": self.evaluaciones,
        }
        return resultado


def grados_de_libertad_con_especificaciones(diagrama, valores, especificaciones):
    """
    El conteo teniendo en cuenta las especificaciones.

    Cada una suma UNA ECUACION (objetivo = valor) y nada mas.

    Cuidado con la tentación de sumar también una incógnita "porque se
    libera la variable manipulada": esa variable YA estaba contada como
    incógnita, precisamente porque no se da como dato. Sumarla otra vez
    la cuenta dos veces y el contador dice que falta un dato cuando el
    problema está perfectamente planteado.

    Dicho de otro modo: una especificación de diseño no reformula el
    problema, lo CIERRA. Sin ella faltaría un dato (GL = 1); con ella,
    GL = 0.
    """
    base = dict(diagrama.grados_de_libertad(valores))
    n = len(especificaciones)
    base["ecuaciones"] += n
    base["grados_de_libertad"] = base["incognitas"] - base["ecuaciones"]
    base["especificaciones"] = n
    return base
