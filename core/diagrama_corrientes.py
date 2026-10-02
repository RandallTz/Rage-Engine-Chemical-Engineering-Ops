"""
DiagramaCorrientes: flowsheet donde la CORRIENTE es un elemento de
primera clase, no una flecha.

Diferencia de fondo con core/diagrama_flujo.py (al que reemplaza para
este uso): alli un puerto guardaba un objeto Corriente ENTERO como valor
atomico del pool -- o conocias la corriente completa o no conocias nada.
Eso obligaba a envolver cada operacion como un bloque NO invertible
("solo se dispara con TODAS sus entradas dadas"), y hacia imposible lo
que un simulador de verdad debe permitir: dar cualquier subconjunto de
variables, donde sea, y que el sistema resuelva en la direccion que haga
falta (hacia adelante o hacia atras).

Aqui cada corriente aporta variables ESCALARES al pool compartido:

    s1.F   flujo molar [mol/s]
    s1.T   temperatura [K]
    s1.P   presion [Pa]
    s1.x0, s1.x1, ...  fracciones molares (una por componente)

y cada operacion aporta sus ecuaciones YA EXISTENTES (balance de
materia, McCabe-Thiele, cargas termicas...) renombradas para apuntar a
las variables de las corrientes que toca (ver renombrar_bloque en
core/orquestador.py). No se reescribio ningun metodo matematico: la
invertibilidad ya estaba en los solvers (BalanceMateriaGlobal resuelve
cualquier 2 de 6; SolucionadorMcCabeThiele cualquier 1 de 5); era la
envoltura la que la desperdiciaba.

Consecuencia directa: conectar dos operaciones no necesita "cables" --
comparten la misma corriente, o sea literalmente las mismas variables.
"""

import numpy as np

from core.balance_materia import BalanceMateriaGlobal
from core.reactor_cstr import EvaluadorCSTR
from core.reactor_pfr import EvaluadorPFR
from core.absorbedor import EvaluadorAbsorbedor
from core.flash import EvaluadorFlash
from thermodynamics.elv import CalculadoraELV
from thermodynamics.entalpia import entalpia_de
from core.orquestador import (
    Orquestador,
    BloqueEcuaciones,
    renombrar_bloque,
    verificar_consistencia,
    bloque_balance_materia,
    bloque_mccabe_thiele,
    bloque_ponchon_savarit,
    bloque_cargas_termicas,
    bloque_cargas_termicas_ps,
)


def variables_de_corriente(nombre, n_componentes):
    return (
        f"{nombre}.F",
        f"{nombre}.T",
        f"{nombre}.P",
        *[f"{nombre}.x{i}" for i in range(n_componentes)],
    )


def _bloque_cierre_composicion(nombre, n_componentes):
    """
    sum(x_i) = 1 en una corriente. Es invertible: con una sola fraccion
    desconocida, la despeja. Para un binario esto es lo que hace que dar
    x0 baste (x1 sale solo), sin que el usuario tenga que escribir las
    dos.
    """
    claves = [f"{nombre}.x{i}" for i in range(n_componentes)]

    def resolver_fn(**conocidos):
        faltan = [c for c in claves if c not in conocidos]
        if len(faltan) != 1:
            return {}
        return {faltan[0]: 1.0 - sum(conocidos[c] for c in claves if c in conocidos)}

    return BloqueEcuaciones(
        nombre=f"Cierre de composicion ({nombre})",
        variables=tuple(claves),
        puede_resolver=lambda n: n == 1,
        resolver_fn=resolver_fn,
    )


def _bloque_caudal_masico(nombre, n_componentes, masas_molares, kg_por_segundo):
    """
    Restriccion "esta corriente lleva tantos kg/s":

        F * MW_mezcla(x) / 1000 = kg_por_segundo

    NO es una variable nueva: el caudal sigue siendo UNO solo (F, en
    mol/s). Dar el caudal en masa es una forma distinta de fijar esa
    misma variable, y la conversion depende de la composicion de la
    corriente (1 kg/s son 11.56 mol/s con x_benceno=0.4 pero 12.58 con
    x=0.9), asi que no puede ser una simple unidad: tiene que esperar a
    conocer la composicion. Por eso es un bloque y no un valor fijo.

    Las masas molares vienen de 'thermo' (Chemical.MW).
    """
    clave_F = f"{nombre}.F"
    claves_x = [f"{nombre}.x{i}" for i in range(n_componentes)]

    def resolver_fn(**conocidos):
        if any(c not in conocidos for c in claves_x):
            return {}  # sin composicion completa no hay MW de la mezcla
        mw_mezcla = sum(conocidos[c] * masas_molares[i] for i, c in enumerate(claves_x))
        if mw_mezcla <= 0:
            return {}
        return {clave_F: kg_por_segundo * 1000.0 / mw_mezcla}

    return BloqueEcuaciones(
        nombre=f"Caudal masico dado ({nombre})",
        variables=tuple([clave_F] + claves_x),
        variables_entrada=tuple(claves_x),
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=1,
    )


class DiagramaCorrientes:
    def __init__(self, nombres_componentes, masas_molares=None, proveedor=None):
        """
        masas_molares: [g/mol] por componente, en el mismo orden. Con
        ellas cada corriente gana un caudal MASICO como variable propia
        (ver _bloque_caudal_masico). Sin ellas, no se anade.
        proveedor: ProveedorTermodinamico, opcional. Hace falta para los
        balances de energia que no pasan por un evaluador de columna --
        hoy, la temperatura de salida de un mezclador. Sin el, el
        mezclador cae a la media ponderada por caudal, que solo es
        exacta si todos los Cp son iguales.
        """
        self.nombres_componentes = list(nombres_componentes)
        self.masas_molares = list(masas_molares) if masas_molares else None
        self._proveedor = proveedor
        self._entalpia = None
        self._flash = None
        self.n = len(self.nombres_componentes)
        self.corrientes: list[str] = []
        self._bloques: list[BloqueEcuaciones] = []
        self._operaciones: dict[str, dict] = {}
        # Corrientes a las que ya se les fijo la presion: evita que dos
        # equipos que comparten una corriente le pongan dos ecuaciones.
        self._presion_fijada: set[str] = set()
        # Lo mismo para la temperatura: una corriente que sale de un equipo
        # y entra en otro no puede recibir dos ecuaciones de T.
        self._temperatura_fijada: set[str] = set()

    # ------------------------------------------------------------------
    def agregar_corriente(self, nombre):
        if nombre in self.corrientes:
            raise ValueError(f"Ya existe una corriente llamada {nombre!r}.")
        self.corrientes.append(nombre)
        if self.n > 1:
            self._bloques.append(_bloque_cierre_composicion(nombre, self.n))
        return nombre

    def fijar_caudal_masico(self, corriente, kg_por_segundo):
        """Fija el caudal de una corriente dandolo en masa en vez de en moles."""
        self._exigir_corriente(corriente)
        if not self.masas_molares:
            raise ValueError("Para dar caudales en masa hacen falta las masas molares de los componentes.")
        self._bloques.append(
            _bloque_caudal_masico(corriente, self.n, self.masas_molares, float(kg_por_segundo))
        )

    def masas_molares_de_mezcla(self, pool):
        """
        MW [g/mol] de cada corriente cuya composicion ya se conoce. El
        cliente la necesita para MOSTRAR un caudal en masa; se calcula
        aqui, con las MW de 'thermo', en vez de que el frontend las
        tenga que llevar.
        """
        resultado = {}
        if not self.masas_molares:
            return resultado
        for corriente in self.corrientes:
            fracciones = [pool.get(f"{corriente}.x{i}") for i in range(self.n)]
            if any(x is None for x in fracciones):
                continue
            mw = sum(x * self.masas_molares[i] for i, x in enumerate(fracciones))
            if mw > 0:
                resultado[corriente] = float(mw)
        return resultado

    def entalpia(self):
        """
        LA calculadora de entalpia de este diagrama, o None si no se dio
        proveedor. Perezosa: construirla tabula Cp y DHvap sobre ~160
        temperaturas, asi que no se paga si el diagrama no tiene ningun
        balance de energia. Una sola por proveedor (entalpia_de), que es
        lo que garantiza que mezclador, flash, intercambiador y columna
        midan la energia con la misma referencia.
        """
        if self._proveedor is None:
            return None
        if self._entalpia is None:
            self._entalpia = entalpia_de(self._proveedor)
        return self._entalpia

    def flash(self):
        """
        EL evaluador de flash del diagrama, o None si no hay proveedor.

        Lo usan el flash propiamente dicho, la valvula, el intercambiador
        y -- lo que mas importa -- el MEZCLADOR, para medir la entalpia
        de cada corriente sin tener que suponer en que fase viene.
        """
        if self._proveedor is None:
            return None
        if self._flash is None:
            self._flash = EvaluadorFlash(CalculadoraELV(self._proveedor))
        return self._flash

    def _registrar_operacion(self, nombre, tipo, entradas, salidas, desde, extra=None):
        """
        Anota que corrientes CONSUME y cuales PRODUCE cada operacion, y
        que bloques creo (por indice). Las dos cosas hacen falta para los
        reciclos: el grafo entradas->salidas es donde se detectan los
        lazos, y saber que bloques pertenecen a la operacion es lo que
        permite cortar una corriente redirigiendo SOLO a quien la produce.
        """
        self._operaciones[nombre] = {
            "tipo": tipo,
            "entradas": list(entradas),
            "salidas": list(salidas),
            "bloques": list(range(desde, len(self._bloques))),
            **(extra or {}),
        }

    def _exigir_corriente(self, nombre):
        if nombre not in self.corrientes:
            raise ValueError(f"No existe la corriente {nombre!r}. Agregala con agregar_corriente().")

    # ------------------------------------------------------------------
    def agregar_columna_binaria(self, nombre, solucionador, alimentacion, destilado, fondos,
                                 metodo="mccabe_thiele", q_fijo=None, con_cargas_termicas=True):
        """
        Conecta una columna binaria a tres corrientes ya declaradas. Las
        ecuaciones de la columna se renombran para operar directamente
        sobre las variables de esas corrientes -- por eso el sistema
        puede resolver en cualquier direccion (p.ej. dados destilado y
        fondos, hallar la alimentacion).

        Convencion de composicion: x0 de cada corriente es la fraccion
        del componente 0, el "ligero" -- la misma convencion que ya usan
        EvaluadorMcCabeThiele y EvaluadorPonchonSavarit.
        """
        _ini = len(self._bloques)
        for s in (alimentacion, destilado, fondos):
            self._exigir_corriente(s)
        if self.n != 2:
            raise ValueError(
                f"{nombre}: {metodo!r} es un metodo BINARIO (se construye sobre un solo "
                f"par x-y) y esta simulacion tiene {self.n} componentes. No es una "
                "limitacion del programa sino del metodo. Para una mezcla "
                f"multicomponente usa FUG (Fenske-Underwood-Gilliland), que si maneja "
                f"{self.n} componentes: cambia el metodo de la columna en su panel."
            )

        mapa_streams = {
            "F": f"{alimentacion}.F", "z_F": f"{alimentacion}.x0",
            "D": f"{destilado}.F", "x_D": f"{destilado}.x0",
            "B": f"{fondos}.F", "x_B": f"{fondos}.x0",
        }
        mapa_op = {v: f"{nombre}.{v}" for v in ("q", "R", "N", "Qc_D", "QR_B", "Q_c", "Q_R", "R_int", "V_barra", "T_D", "T_B", "T_reflujo")}

        self._bloques.append(
            renombrar_bloque(
                bloque_balance_materia(BalanceMateriaGlobal()),
                mapa_streams,
                nombre=f"{nombre}: balance de materia",
            )
        )

        if metodo == "mccabe_thiele":
            self._bloques.append(
                renombrar_bloque(
                    bloque_mccabe_thiele(solucionador),
                    {**mapa_streams, **mapa_op},
                    nombre=f"{nombre}: McCabe-Thiele",
                )
            )
            if con_cargas_termicas:
                self._bloques.append(
                    renombrar_bloque(
                        bloque_cargas_termicas(solucionador.evaluador),
                        {**mapa_streams, **mapa_op},
                        nombre=f"{nombre}: cargas termicas",
                    )
                )
            # q_fijo se IGNORABA en esta rama. Ponchon-Savarit lo publicaba
            # en el pool y McCabe-Thiele no, asi que pasar q_fijo=1.0 a una
            # columna McCabe-Thiele no hacia absolutamente nada: q seguia
            # sin determinarse y arrastraba consigo N, Q_c, Q_R y las
            # temperaturas, con el contador de grados de libertad diciendo
            # GL=0 -- o sea, el mismo fallo silencioso que ya habia mordido
            # antes (datos "correctos", nada resuelto, ningun motivo).
            # Se encontro encadenando un flash con una columna.
            #
            # Aqui q SI es variable de pool (a diferencia de en
            # Ponchon-Savarit), asi que darla por el panel y darla como
            # dato son dos caminos al mismo sitio: si se dan los dos y no
            # coinciden, lo detecta la verificacion de consistencia.
            if q_fijo is not None:
                self._bloques.append(
                    self._bloque_valor_fijo(
                        f"{nombre}.q", q_fijo, nombre=f"q dada ({nombre})"
                    )
                )
        elif metodo == "ponchon_savarit":
            if q_fijo is None:
                raise ValueError("ponchon_savarit necesita q_fijo (no es variable de pool en ese metodo).")
            self._bloques.append(
                renombrar_bloque(
                    bloque_ponchon_savarit(solucionador, q_fijo),
                    {**mapa_streams, **mapa_op},
                    nombre=f"{nombre}: Ponchon-Savarit",
                )
            )
            # Antes el checkbox "incluir balance de energia" se dibujaba
            # para Ponchon-Savarit pero NO hacia nada: con_cargas_termicas
            # solo se consultaba en la rama de McCabe-Thiele. El bloque es
            # distinto (aqui la energia sale de Qc_D y la colinealidad de
            # los polos, no de R y CMO), por eso no se reutiliza el otro.
            if con_cargas_termicas:
                self._bloques.append(
                    renombrar_bloque(
                        bloque_cargas_termicas_ps(solucionador.evaluador, q_fijo),
                        {**mapa_streams, **mapa_op},
                        nombre=f"{nombre}: cargas termicas",
                    )
                )
            # q es un DATO en este metodo (se escribe en el panel de la
            # columna), pero antes se pasaba solo al solver y nunca
            # entraba al pool: por eso 'col1.q' y, en cascada, la T de la
            # alimentacion quedaban eternamente "sin determinar" aunque
            # el usuario si hubiera dado q. Publicarlo lo arregla y no
            # altera los grados de libertad (la variable ya estaba
            # declarada por el bloque de T de alimentacion; esto solo
            # aporta la ecuacion que le faltaba).
            self._bloques.append(
                self._bloque_valor_fijo(
                    f"{nombre}.q", q_fijo, nombre=f"q dada ({nombre})"
                )
            )
        else:
            raise ValueError(f"metodo binario desconocido: {metodo!r}")

        # T y P de los productos: salen a su punto de burbuja, a la P de
        # la columna. Es forward-only (no se invierte), asi que solo se
        # dispara cuando ya se conoce la composicion del producto.
        #
        # La guarda de _temperatura_fijada es del mismo tipo que la de
        # _presion_fijada y la que ya tenia FUG: una corriente no puede
        # recibir DOS ecuaciones de temperatura. Aqui faltaba, y el hueco
        # aparecio al encadenar un flash con una columna -- el flash ya
        # fija la T de su liquido, la columna se la volvia a fijar, y el
        # contador decia GL=-1 ("sobran datos") con el diagrama bien
        # planteado. Mismo fallo que ya se habia corregido para la
        # presion, solo que en la mitad de los sitios.
        evaluador = solucionador.evaluador
        for corriente in (destilado, fondos):
            if f"{corriente}.T" in self._temperatura_fijada:
                continue
            self._temperatura_fijada.add(f"{corriente}.T")
            self._bloques.append(self._bloque_burbuja(corriente, evaluador))

        # P de TODAS las corrientes de la columna = P de operacion (el
        # proyecto no modela caida de presion). Si el usuario da una P
        # distinta, la suya gana: el Orquestador solo rellena huecos.
        for corriente in (alimentacion, destilado, fondos):
            bloque_P = self._bloque_presion_fija(corriente, evaluador.P_sistema)
            if bloque_P is not None:
                self._bloques.append(bloque_P)

        # T de la alimentacion cuando q=1 (liquido saturado, el caso por
        # defecto): es su punto de burbuja. Para otros q la relacion
        # q -> T existe pero necesita entalpias, y aqui se deja sin
        # determinar a proposito en vez de inventar un valor.
        #
        # Si quien alimenta la columna ya le puso T (un flash, un reactor,
        # un intercambiador), esta ecuacion NO se anade. Y no se pierde
        # nada fisicamente: el liquido que sale de un flash esta en su
        # punto de burbuja, que es exactamente lo que este bloque habria
        # calculado.
        if f"{alimentacion}.T" not in self._temperatura_fijada:
            self._temperatura_fijada.add(f"{alimentacion}.T")
            self._bloques.append(
                self._bloque_T_alimentacion(alimentacion, f"{nombre}.q", evaluador)
            )

        self._registrar_operacion(
            nombre, "columna", entradas=[alimentacion], salidas=[destilado, fondos],
            desde=_ini, extra={"metodo": metodo,
                               "corrientes": {"alimentacion": alimentacion,
                                              "destilado": destilado, "fondos": fondos}},
        )
        return nombre

    def _bloque_burbuja(self, corriente, evaluador):
        clave_x0 = f"{corriente}.x0"
        clave_T = f"{corriente}.T"
        clave_P = f"{corriente}.P"

        def resolver_fn(**conocidos):
            x0 = conocidos[clave_x0]
            P = conocidos.get(clave_P, evaluador.P_sistema)
            T, _ = evaluador.calculadora_elv.burbuja_T(P, np.array([x0, 1.0 - x0]))
            return {clave_T: float(T)}

        return BloqueEcuaciones(
            nombre=f"Punto de burbuja ({corriente})",
            variables=(clave_x0, clave_P, clave_T),
            variables_entrada=(clave_x0,),
            puede_resolver=lambda n: n == 0,
            resolver_fn=resolver_fn,
            n_ecuaciones=1,  # solo determina T; la P la fija el bloque de presion
        )

    def _bloque_presion_fija(self, corriente, P_sistema):
        """
        Fija la P de una corriente a la de operacion del equipo.

        Devuelve None si esa corriente YA tiene quien le fije la presion.
        Hace falta porque una corriente puede tocar dos equipos a la vez
        (la salida de un reactor que alimenta una columna, por ejemplo) y
        entonces los dos intentaban fijarle la P: dos ecuaciones para una
        variable. El resultado era un GL negativo espureo -- el medidor
        decia que sobraban datos cuando el problema estaba bien planteado.
        """
        clave = f"{corriente}.P"
        if clave in self._presion_fijada:
            return None
        self._presion_fijada.add(clave)

        def resolver_fn(**_):
            return {clave: float(P_sistema)}

        return BloqueEcuaciones(
            nombre=f"Presion de operacion ({corriente})",
            variables=(clave,),
            variables_entrada=(),
            puede_resolver=lambda n: n == 0,
            resolver_fn=resolver_fn,
        )

    def _bloque_igualdad(self, clave_a, clave_b, nombre):
        """a = b, en las dos direcciones: sirve tanto para propagar
        hacia adelante como para deducir hacia atras."""
        def resolver_fn(**c):
            if c.get(clave_a) is None and c.get(clave_b) is not None:
                return {clave_a: float(c[clave_b])}
            if c.get(clave_b) is None and c.get(clave_a) is not None:
                return {clave_b: float(c[clave_a])}
            return {}

        return BloqueEcuaciones(
            nombre=nombre,
            variables=(clave_a, clave_b),
            puede_resolver=lambda n: n <= 1,
            resolver_fn=resolver_fn,
            n_ecuaciones=1,
        )

    def _bloque_valor_fijo(self, clave, valor, nombre):
        """Mete en el pool un parametro que el usuario ya dio en el panel
        de la operacion (no es una incognita: cuenta como una ecuacion)."""
        def resolver_fn(**_):
            return {clave: float(valor)}

        return BloqueEcuaciones(
            nombre=nombre,
            variables=(clave,),
            variables_entrada=(),
            puede_resolver=lambda n: n == 0,
            resolver_fn=resolver_fn,
        )

    def _bloque_T_alimentacion(self, corriente, clave_q, evaluador):
        clave_x0 = f"{corriente}.x0"
        clave_T = f"{corriente}.T"
        clave_P = f"{corriente}.P"

        def resolver_fn(**conocidos):
            if not np.isclose(conocidos[clave_q], 1.0):
                return {}  # solo el caso de liquido saturado
            P = conocidos.get(clave_P, evaluador.P_sistema)
            x0 = conocidos[clave_x0]
            T, _ = evaluador.calculadora_elv.burbuja_T(P, np.array([x0, 1.0 - x0]))
            return {clave_T: float(T)}

        return BloqueEcuaciones(
            nombre=f"T de alimentacion ({corriente}, si q=1)",
            variables=(clave_x0, clave_q, clave_P, clave_T),
            variables_entrada=(clave_x0, clave_q),
            puede_resolver=lambda n: n == 0,
            resolver_fn=resolver_fn,
            n_ecuaciones=1,  # solo determina T (y solo si q=1)
        )

    # ------------------------------------------------------------------
    def agregar_columna_fug(self, nombre, alimentacion, destilado, fondos,
                             calculadora_elv, proveedor, indice_LK, indice_HK,
                             q_fijo=1.0, P_sistema=101325.0, con_cargas_termicas=True):
        """
        Columna MULTICOMPONENTE por Fenske-Underwood-Gilliland.

        Es lo que faltaba para que el flowsheet no se atascara en cuanto
        la mezcla pasaba de dos componentes: McCabe-Thiele y
        Ponchon-Savarit son metodos binarios por construccion, asi que
        con 3 o mas componentes no hay nada que puedan hacer. FUG si.

        Diferencia de ingenieria con los binarios: aqui NO se especifican
        purezas (x_D, x_B) sino RECUPERACIONES de los dos componentes
        clave -- cuanto del ligero se va por el domo y cuanto del pesado
        por el fondo. Las composiciones de producto son RESULTADO del
        metodo (el reparto de los no-clave lo decide Fenske), no un dato.

        Detalle de implementacion que obliga a construir el analizador
        dentro del bloque y no aqui: AnalizadorFUG exige z_F COMPLETO en
        su constructor, pero en este modelo la composicion de la
        alimentacion vive en el pool y puede no conocerse todavia cuando
        se arma el diagrama.
        """
        _ini = len(self._bloques)
        for s in (alimentacion, destilado, fondos):
            self._exigir_corriente(s)
        if self.n < 2:
            raise ValueError(f"FUG necesita al menos 2 componentes; hay {self.n}.")
        if indice_LK == indice_HK:
            raise ValueError(
                "El clave ligero y el clave pesado deben ser componentes distintos."
            )
        for idx, papel in ((indice_LK, "ligero"), (indice_HK, "pesado")):
            if not (0 <= idx < self.n):
                raise ValueError(
                    f"El indice del clave {papel} ({idx}) esta fuera de rango "
                    f"para {self.n} componentes."
                )

        contexto = dict(
            calculadora_elv=calculadora_elv, proveedor=proveedor,
            nombres=self.nombres_componentes, q=q_fijo, P_sistema=P_sistema,
            indice_LK=indice_LK, indice_HK=indice_HK,
        )

        # Si la alimentacion viene de otro equipo que ya le fija la T
        # (la salida de un reactor, por ejemplo), FUG no debe volver a
        # ponerle una ecuacion: seria contar dos veces y el medidor de
        # grados de libertad diria que sobran datos.
        reclama_T_alimentacion = f"{alimentacion}.T" not in self._temperatura_fijada
        self._temperatura_fijada.update(
            {f"{destilado}.T", f"{fondos}.T"}
            | ({f"{alimentacion}.T"} if reclama_T_alimentacion else set())
        )
        self._bloques.append(
            _bloque_fug_corrientes(nombre, alimentacion, destilado, fondos, self.n,
                                   contexto, reclama_T_alimentacion=reclama_T_alimentacion)
        )
        if con_cargas_termicas:
            self._bloques.append(
                _bloque_cargas_fug_corrientes(nombre, alimentacion, destilado, fondos,
                                              self.n, contexto)
            )

        # q es un dato del panel, igual que en Ponchon-Savarit: se publica
        # para que quede visible y no aparezca como incognita eterna.
        self._bloques.append(
            self._bloque_valor_fijo(f"{nombre}.q", q_fijo, nombre=f"q dada ({nombre})")
        )
        for corriente in (alimentacion, destilado, fondos):
            bloque_P = self._bloque_presion_fija(corriente, P_sistema)
            if bloque_P is not None:
                self._bloques.append(bloque_P)

        self._operaciones[nombre] = {
            "tipo": "columna", "metodo": "fug",
            "corrientes": {"alimentacion": alimentacion, "destilado": destilado, "fondos": fondos},
        }
        return nombre

    # ------------------------------------------------------------------
    def agregar_reactor_cstr(self, nombre, entrada, salida, nu, gestor_reaccion=None,
                              con_cinetica=True, entradas=None,
                              modo_energia="isotermo", Q=None,
                              con_balance_energia=True,
                              modo_reaccion="cinetico"):
        """
        Reactor CSTR en estado estacionario. Igual que el resto de
        operaciones, NO es forward-only: el balance por componente se
        resuelve en cualquiera de sus tres direcciones utiles (ver
        core/reactor_cstr.py).

        modo_energia -- que se da y que se calcula en el balance de energia:

            "isotermo"   (por defecto) se da la T del tanque y se calcula
                         el calor Q que cuesta mantenerla. Es compatible
                         hacia atras: un reactor que antes solo pedia T
                         sigue funcionando igual, y ademas ahora dice
                         cuanta refrigeracion necesita.
            "adiabatico" Q = 0 y se calcula la T que resulta.
            "calor_dado" se da Q [W] y se calcula la T que resulta.

        Los dos ultimos necesitan proveedor termodinamico y calor de
        reaccion; sin ellos se rechaza en vez de fingir un balance.

        Variables propias:
            <nombre>.xi          avance de reaccion [mol/s]
            <nombre>.X           conversion del reactivo limitante
            <nombre>.V           volumen del tanque [m^3]   (solo con cinetica)
            <nombre>.T           temperatura del tanque [K]
            <nombre>.Q           calor intercambiado [W]; < 0 = hay que refrigerar
            <nombre>.Q_reaccion  calor liberado por la reaccion, xi*dH_rxn [W]
        """
        _ini = len(self._bloques)

        # VARIAS ENTRADAS: un reactor real recibe mas de una corriente
        # (alimentacion fresca + reciclo + inyeccion de reactivo). Se
        # resuelve mezclandolas dentro del propio equipo, en una corriente
        # interna, y reutilizando el mezclador que ya existe y ya esta
        # probado -- incluido su balance de energia. Asi el reactor no
        # tiene que reimplementar nada y el caso de una sola entrada sigue
        # siendo exactamente el de antes (no pierde invertibilidad).
        lista_entradas = list(entradas) if entradas else [entrada]
        lista_entradas = [e for e in lista_entradas if e]
        if not lista_entradas:
            raise ValueError(f"{nombre}: el reactor necesita al menos una corriente de entrada.")
        if len(set(lista_entradas)) != len(lista_entradas):
            raise ValueError(
                f"{nombre}: hay una corriente repetida en las entradas ({lista_entradas}). "
                "Cada entrada debe ser una corriente distinta."
            )
        for s in lista_entradas:
            self._exigir_corriente(s)
        self._exigir_corriente(salida)

        if len(lista_entradas) == 1:
            entrada = lista_entradas[0]
        else:
            entrada = f"{nombre}{self.SUFIJO_INTERNO}entrada"
            self.agregar_corriente(entrada)
            self.agregar_mezclador(f"{nombre}: mezcla de entradas",
                                   entradas=lista_entradas, salida=entrada)

        if modo_energia not in ("isotermo", "adiabatico", "calor_dado"):
            raise ValueError(
                f"{nombre}: modo_energia desconocido {modo_energia!r}. "
                "Usa 'isotermo' (das T, se calcula el calor que cuesta mantenerla), "
                "'adiabatico' (Q=0, se calcula la T que resulta) o "
                "'calor_dado' (das Q, se calcula T)."
            )
        if modo_energia == "calor_dado" and Q is None:
            raise ValueError(f"{nombre}: modo_energia='calor_dado' necesita Q (en W).")
        if modo_energia != "calor_dado" and Q is not None:
            raise ValueError(
                f"{nombre}: se dio Q con modo_energia={modo_energia!r}. En 'adiabatico' "
                "Q vale 0 por definicion, y en 'isotermo' Q es el RESULTADO, no un dato."
            )

        evaluador = EvaluadorCSTR(nu, gestor_reaccion, evaluador_flash=self.flash())
        # Sin proveedor termodinamico no hay entalpias: el reactor se
        # queda como estaba antes de esta version -- isotermo con T como
        # dato y sin decir cuanto calor cuesta. Se avisa en vez de
        # simular un balance que no se puede hacer.
        # con_balance_energia=False apaga la energia del reactor, igual que
        # en las columnas. No es un capricho: el balance NECESITA la T y la
        # P de la corriente de entrada, asi que encenderlo anade un
        # requisito de datos. Un diagrama que solo quiere balances de
        # materia no tiene por que darlos -- y sin esta escotilla, sus
        # variables Q se quedarian eternamente sin determinar y el
        # diagrama nunca saldria "completo".
        hay_energia = (
            con_balance_energia
            and evaluador.entalpia is not None
            and evaluador.dH_rxn is not None
        )
        if not hay_energia and modo_energia != "isotermo":
            raise ValueError(
                f"{nombre}: modo_energia={modo_energia!r} necesita balance de energia, y "
                "este diagrama no puede hacerlo: falta el ProveedorTermodinamico "
                "(DiagramaCorrientes(..., proveedor=...)) o el calor de reaccion "
                "(GestorReaccion). Sin eso, el unico modo posible es 'isotermo' con T dada."
            )

        self._bloques.append(
            _bloque_balance_cstr(nombre, entrada, salida, self.n, evaluador)
        )
        self._bloques.append(
            _bloque_conversion_cstr(nombre, entrada, self.n, evaluador)
        )

        # Con cinetica Y sin ser isotermo, T y xi se necesitan mutuamente:
        # un solo bloque acoplado resuelve las dos a la vez (ver
        # _bloque_reactor_acoplado). En cualquier otro caso van separados.
        if modo_reaccion not in ("cinetico", "equilibrio"):
            raise ValueError(
                f"{nombre}: modo_reaccion desconocido {modo_reaccion!r}. "
                "Usa 'cinetico' (xi = V*r, necesita Arrhenius y da el volumen) o "
                "'equilibrio' (xi del equilibrio quimico, sin volumen)."
            )

        # En equilibrio no hay cinetica que acoplar: xi sale de K_eq(T) y
        # T es un dato (o la calcula el balance de energia a partir de xi,
        # que entonces SI es un lazo -- ver abajo).
        if modo_reaccion == "equilibrio":
            if gestor_reaccion is None:
                raise ValueError(
                    f"{nombre}: el reactor de equilibrio necesita la reaccion "
                    "(para K_eq); sin ella no hay equilibrio que calcular."
                )
            if modo_energia != "isotermo":
                raise ValueError(
                    f"{nombre}: el reactor de equilibrio solo esta implementado en modo "
                    "isotermo. Adiabatico acopla K_eq(T) con el balance de energia en un "
                    "lazo que aun no se resuelve aqui; usa el modo cinetico para eso."
                )
            self._bloques.append(
                _bloque_equilibrio_cstr(nombre, entrada, self.n, evaluador)
            )

        acoplado = (modo_reaccion == "cinetico" and con_cinetica
                    and hay_energia and modo_energia != "isotermo")

        if modo_reaccion == "cinetico" and con_cinetica:
            if gestor_reaccion is None:
                raise ValueError(
                    "Para resolver el CSTR por cinetica hace falta la reaccion "
                    "(parametros de Arrhenius); sin ella, da el avance o la conversion."
                )
            if not acoplado:
                self._bloques.append(
                    _bloque_cinetica_cstr(nombre, salida, self.n, evaluador)
                )

        if hay_energia:
            if modo_energia == "adiabatico":
                self._bloques.append(
                    self._bloque_valor_fijo(f"{nombre}.Q", 0.0,
                                            nombre=f"Adiabatico, Q=0 ({nombre})")
                )
            elif modo_energia == "calor_dado":
                self._bloques.append(
                    self._bloque_valor_fijo(f"{nombre}.Q", float(Q),
                                            nombre=f"Calor dado ({nombre})")
                )
            if acoplado:
                self._bloques.append(
                    _bloque_reactor_acoplado(nombre, entrada, salida, self.n,
                                             evaluador, P_conocida_de=entrada)
                )
            else:
                self._bloques.append(
                    _bloque_energia_cstr(nombre, entrada, salida, self.n,
                                         evaluador, P_conocida_de=entrada)
                )

        # T de salida = T del tanque. En un CSTR el contenido esta
        # perfectamente mezclado, asi que lo que sale esta a la
        # temperatura del reactor -- no es una suposicion adicional, es la
        # definicion del modelo.
        #
        # Esto va FUERA del 'if con_cinetica' a proposito: un tanque tiene
        # temperatura tenga o no cinetica. Cuando estaba dentro, un
        # reactor sin cinetica no daba T a su salida y paralizaba a todo
        # el que viniera detras -- se vio armando un reciclo, donde el
        # divisor aguas abajo no podia arrancar por eso.
        if f"{salida}.T" not in self._temperatura_fijada:
            self._temperatura_fijada.add(f"{salida}.T")
            self._bloques.append(
                self._bloque_igualdad(f"{salida}.T", f"{nombre}.T",
                                      f"T de salida = T del tanque ({nombre})")
            )

        # Sin caida de presion (el proyecto no la modela en ningun equipo).
        # Se registra en _presion_fijada para que un equipo aguas abajo que
        # reciba esta corriente NO le vuelva a poner otra ecuacion de P.
        if f"{salida}.P" not in self._presion_fijada:
            self._presion_fijada.add(f"{salida}.P")
            self._bloques.append(
                self._bloque_igualdad(f"{salida}.P", f"{entrada}.P",
                                      f"Presion sin caida ({nombre})")
            )

        self._registrar_operacion(
            nombre, "reactor_cstr" if modo_reaccion == "cinetico" else "reactor_equilibrio",
            entradas=lista_entradas, salidas=[salida], desde=_ini,
            extra={"corrientes": {"entradas": lista_entradas, "entrada": entrada,
                                  "salida": salida}},
        )
        return nombre

    # ------------------------------------------------------------------
    def agregar_mezclador(self, nombre, entradas, salida):
        """
        Mezcla adiabatica: balance por componente, balance total, balance
        de ENERGIA y presion.

        La version anterior solo hacia materia, asi que la salida del
        mezclador se quedaba sin T ni P -- y eso no se notaba en un
        mezclador suelto pero paralizaba todo lo que viniera detras (se
        midio: 'mezclador -> reactor' dejaba m1.T, m1.P y hasta la P del
        producto del reactor sin determinar). Un mezclador sin T de
        salida es inservible en un flowsheet real, y ademas es justo el
        equipo por el que entra un reciclo.
        """
        _ini = len(self._bloques)
        for s in (*entradas, salida):
            self._exigir_corriente(s)

        claves_entrada = []
        for s in entradas:
            claves_entrada += [f"{s}.F", f"{s}.T", f"{s}.P",
                               *[f"{s}.x{i}" for i in range(self.n)]]
        claves_salida = [f"{salida}.F", f"{salida}.T", f"{salida}.P",
                         *[f"{salida}.x{i}" for i in range(self.n)]]
        evaluador_flash = self.flash()

        def resolver_fn(**conocidos):
            F_total = sum(conocidos[f"{s}.F"] for s in entradas)
            if F_total <= 0:
                return {}
            valores = {f"{salida}.F": F_total}
            x_salida = []
            for i in range(self.n):
                flujo_i = sum(conocidos[f"{s}.F"] * conocidos[f"{s}.x{i}"] for s in entradas)
                x_i = flujo_i / F_total
                valores[f"{salida}.x{i}"] = x_i
                x_salida.append(x_i)

            # Presion: la mezcla no puede salir a mas presion que la mas
            # baja de sus entradas (contra esa es contra la que tiene que
            # empujar). Sin bomba, esa es la que manda.
            valores[f"{salida}.P"] = min(conocidos[f"{s}.P"] for s in entradas)

            # Temperatura por BALANCE DE ENERGIA adiabatico:
            #     sum(F_in * h(T_in, P_in, x_in)) = F_out * h(T_out, P_out, x_out)
            #
            # Dos cambios respecto a la version anterior, los dos por la
            # misma razon -- este bloque es por donde entra un reciclo, y
            # un reciclo puede traer vapor:
            #
            # 1. h ya no es la forma linealizada h = Cp(T)*(T - T_ref) de
            #    cosecha propia, sino la entalpia COMPARTIDA del proyecto
            #    (integral real de Cp). No es lo mismo salvo que Cp sea
            #    constante, y no lo es.
            # 2. h ya no supone que toda corriente es liquida: se mide con
            #    entalpia_de_corriente, que DEDUCE la fase del flash en
            #    (T, P, z). Si una entrada trae vapor, su calor latente
            #    entra en el balance; antes se ignoraba en silencio, o
            #    sea que se contaba MENOS energia de la que entraba y la
            #    T de mezcla salia demasiado BAJA. Medido con 100 mol/s
            #    de liquido a 330 K y 40 mol/s de vapor sobrecalentado a
            #    378 K: faltaban 9032 J/mol (el 56 % de la entalpia de
            #    la mezcla) y la T salia 344.30 K en vez de 368.13 K --
            #    ademas de declararla liquida cuando en realidad la
            #    mezcla es bifasica (beta = 0.163).
            #
            # La salida tambien se resuelve con un flash P-H en vez de
            # invertir h_liquido: mezclar dos corrientes calientes puede
            # dar una mezcla que ya no es liquida.
            P_salida = valores[f"{salida}.P"]
            T_media = sum(conocidos[f"{s}.F"] * conocidos[f"{s}.T"] for s in entradas) / F_total
            if evaluador_flash is None:
                # Sin proveedor la unica respuesta honesta es la media
                # ponderada, que es exacta solo si todos los Cp coinciden.
                valores[f"{salida}.T"] = T_media
                return valores

            try:
                entalpia_entrante = 0.0
                for s in entradas:
                    T_s = conocidos[f"{s}.T"]
                    x_s = np.array([conocidos[f"{s}.x{i}"] for i in range(self.n)])
                    x_s = x_s / np.sum(x_s)
                    entalpia_entrante += conocidos[f"{s}.F"] * evaluador_flash.entalpia_de_corriente(
                        T_s, conocidos[f"{s}.P"], x_s
                    )

                h_out = entalpia_entrante / F_total
                resultado = evaluador_flash.a_entalpia(P_salida, np.array(x_salida), h_out)
                valores[f"{salida}.T"] = float(resultado["T"])
            except Exception:
                valores[f"{salida}.T"] = T_media
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: mezcla",
                variables=tuple(claves_entrada + claves_salida),
                variables_entrada=tuple(claves_entrada),
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        self._presion_fijada.add(f"{salida}.P")
        self._temperatura_fijada.add(f"{salida}.T")
        self._registrar_operacion(
            nombre, "mezclador", entradas=list(entradas), salidas=[salida], desde=_ini,
            extra={"corrientes": {"entradas": list(entradas), "salida": salida}},
        )
        return nombre

    def agregar_divisor(self, nombre, entrada, salidas, fracciones):
        """Reparto ideal: misma composicion/T/P, el flujo se divide."""
        _ini = len(self._bloques)
        for s in (entrada, *salidas):
            self._exigir_corriente(s)
        fracciones = [float(f) for f in fracciones]
        if not np.isclose(sum(fracciones), 1.0, atol=1e-6):
            raise ValueError(f"Las fracciones del divisor deben sumar 1.0 (suman {sum(fracciones)}).")

        claves_entrada = (f"{entrada}.F", f"{entrada}.T", f"{entrada}.P", *[f"{entrada}.x{i}" for i in range(self.n)])
        claves_salida = tuple(
            clave for s in salidas
            for clave in (f"{s}.F", f"{s}.T", f"{s}.P", *[f"{s}.x{i}" for i in range(self.n)])
        )

        def resolver_fn(**conocidos):
            resultado = {}
            for s, fraccion in zip(salidas, fracciones):
                resultado[f"{s}.F"] = conocidos[f"{entrada}.F"] * fraccion
                resultado[f"{s}.T"] = conocidos[f"{entrada}.T"]
                resultado[f"{s}.P"] = conocidos[f"{entrada}.P"]
                for i in range(self.n):
                    resultado[f"{s}.x{i}"] = conocidos[f"{entrada}.x{i}"]
            return resultado

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: division",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        self._registrar_operacion(
            nombre, "divisor", entradas=[entrada], salidas=list(salidas), desde=_ini,
            extra={"corrientes": {"entrada": entrada, "salidas": list(salidas)}},
        )
        return nombre

    # ------------------------------------------------------------------
    # Operaciones termicas. Las tres comparten una idea: la FASE de una
    # corriente no es un dato que haya que declarar, es una consecuencia
    # de (T, P, z). Por eso todas miden la entalpia de entrada con
    # EvaluadorFlash.entalpia_de_corriente en vez de suponer liquido, y
    # por eso una corriente bifasica se describe sin ambiguedad con las
    # variables que ya existen (F, T, P, x) -- no hizo falta anadir
    # ninguna variable de fase por corriente.
    #
    # Limite conocido: un equipo que SI supone una fase concreta (una
    # columna binaria espera su alimentacion segun la q que se le dio) no
    # valida que la corriente que recibe este en esa fase. Si un flash le
    # manda vapor a una columna esperando liquido, el resultado sera
    # incoherente y nadie avisara. Queda anotado en docs/12-flash.md.

    def agregar_flash(self, nombre, entrada, vapor, liquido, P_operacion,
                      T_operacion=None, Q_por_mol=None, fraccion_vapor=None):
        """
        Separador liquido-vapor en equilibrio: una etapa MESH.

        Tres especificaciones posibles, exactamente una a la vez:

            T_operacion    -> flash isotermico (se calcula el Q que cuesta)
            Q_por_mol      -> flash con calor; Q=0 es el adiabatico
            fraccion_vapor -> spec de diseno: "vaporiza el 40 %"; se calculan T y Q

        Sin ninguna de las tres se asume adiabatico (Q_por_mol = 0), que
        es el tanque de separacion tipico detras de una valvula.

        Variables propias:
            <nombre>.T           temperatura del recipiente [K]
            <nombre>.beta        fraccion vaporizada V/F
            <nombre>.Q_por_mol   calor por mol de alimentacion [J/mol]
            <nombre>.Q           calor total [W] (ya multiplicado por F)
        """
        _ini = len(self._bloques)
        for s in (entrada, vapor, liquido):
            self._exigir_corriente(s)

        dadas = [("T_operacion", T_operacion), ("Q_por_mol", Q_por_mol),
                 ("fraccion_vapor", fraccion_vapor)]
        activas = [n for n, v in dadas if v is not None]
        if len(activas) > 1:
            raise ValueError(
                f"{nombre}: el flash acepta UNA especificacion y se dieron {len(activas)} "
                f"({', '.join(activas)}). Con dos el sistema queda sobre-especificado: "
                "fijar T y beta a la vez solo es consistente por casualidad."
            )
        modo = activas[0] if activas else "Q_por_mol"
        if not activas:
            Q_por_mol = 0.0

        evaluador = self.flash()
        if evaluador is None:
            raise ValueError(
                f"{nombre}: un flash necesita el ProveedorTermodinamico del diagrama "
                "(DiagramaCorrientes(..., proveedor=...)). Sin el no hay ni equilibrio "
                "ni entalpias que resolver."
            )
        P_op = float(P_operacion)

        claves_entrada = (f"{entrada}.F", f"{entrada}.T", f"{entrada}.P",
                          *[f"{entrada}.x{i}" for i in range(self.n)])
        claves_salida = tuple(
            clave for s in (vapor, liquido)
            for clave in (f"{s}.F", f"{s}.T", f"{s}.P", *[f"{s}.x{i}" for i in range(self.n)])
        ) + (f"{nombre}.T", f"{nombre}.beta", f"{nombre}.Q_por_mol", f"{nombre}.Q")

        def resolver_fn(**conocidos):
            F = conocidos[f"{entrada}.F"]
            z = np.array([conocidos[f"{entrada}.x{i}"] for i in range(self.n)], dtype=float)
            suma = float(np.sum(z))
            if suma <= 0:
                return {}
            z = z / suma
            if F <= 0:
                T_vacio = float(T_operacion) if modo == "T_operacion" else conocidos[f"{entrada}.T"]
                valores = {
                    f"{vapor}.F": 0.0, f"{liquido}.F": 0.0,
                    f"{vapor}.T": T_vacio, f"{liquido}.T": T_vacio,
                    f"{vapor}.P": P_op, f"{liquido}.P": P_op,
                    f"{nombre}.T": T_vacio, f"{nombre}.beta": 0.0,
                    f"{nombre}.Q_por_mol": 0.0, f"{nombre}.Q": 0.0,
                }
                for i in range(self.n):
                    valores[f"{vapor}.x{i}"] = float(z[i])
                    valores[f"{liquido}.x{i}"] = float(z[i])
                return valores

            T_in = conocidos[f"{entrada}.T"]
            P_in = conocidos[f"{entrada}.P"]
            h_in = evaluador.entalpia_de_corriente(T_in, P_in, z)

            if modo == "T_operacion":
                r = evaluador.isotermico(float(T_operacion), P_op, z)
            elif modo == "fraccion_vapor":
                r = evaluador.a_fraccion(P_op, z, float(fraccion_vapor))
            else:
                r = evaluador.a_entalpia(P_op, z, h_in + float(Q_por_mol))

            V = r["beta"] * F
            q_especifico = r["h"] - h_in
            valores = {
                f"{vapor}.F": V, f"{liquido}.F": F - V,
                f"{vapor}.T": r["T"], f"{liquido}.T": r["T"],
                f"{vapor}.P": P_op, f"{liquido}.P": P_op,
                f"{nombre}.T": r["T"], f"{nombre}.beta": r["beta"],
                f"{nombre}.Q_por_mol": q_especifico, f"{nombre}.Q": q_especifico * F,
            }
            for i in range(self.n):
                valores[f"{vapor}.x{i}"] = float(r["y"][i])
                valores[f"{liquido}.x{i}"] = float(r["x"][i])
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: flash ({modo})",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        for s in (vapor, liquido):
            self._presion_fijada.add(f"{s}.P")
            self._temperatura_fijada.add(f"{s}.T")
        self._registrar_operacion(
            nombre, "flash", entradas=[entrada], salidas=[vapor, liquido], desde=_ini,
            extra={"corrientes": {"entrada": entrada, "vapor": vapor, "liquido": liquido},
                   "modo": modo, "P_operacion": P_op},
        )
        return nombre

    def agregar_intercambiador(self, nombre, entrada, salida, Q_por_mol=None, T_salida=None):
        """
        Intercambiador de calor: cambia la entalpia de la corriente sin
        tocar su caudal, su composicion ni su presion.

        Dos especificaciones, una a la vez:

            Q_por_mol dado -> se calcula la T de salida (y si vaporiza, cuanto)
            T_salida dada  -> se calcula el Q que hace falta

        El calculo de T pasa por el flash P-H, no por T_desde_h_liquido:
        calentar lo suficiente VAPORIZA, y esa es justo la situacion en
        la que un "calentador" se vuelve un vaporizador parcial. Con
        h_liquido puro el equipo devolveria una T inventada por encima
        del punto de burbuja, sin avisar de nada.

        Variables propias:
            <nombre>.Q_por_mol   [J/mol]      <nombre>.Q             [W]
            <nombre>.beta_salida fraccion vaporizada a la salida
        """
        _ini = len(self._bloques)
        for s in (entrada, salida):
            self._exigir_corriente(s)
        if (Q_por_mol is None) == (T_salida is None):
            raise ValueError(
                f"{nombre}: da exactamente UNA de Q_por_mol o T_salida. Dar las dos "
                "sobre-especifica el equipo (solo serian compatibles por casualidad) y "
                "no dar ninguna lo deja sin ecuacion de energia."
            )

        evaluador = self.flash()
        if evaluador is None:
            raise ValueError(
                f"{nombre}: un intercambiador necesita el ProveedorTermodinamico del "
                "diagrama para medir entalpias."
            )

        claves_entrada = (f"{entrada}.F", f"{entrada}.T", f"{entrada}.P",
                          *[f"{entrada}.x{i}" for i in range(self.n)])
        claves_salida = (f"{salida}.F", f"{salida}.T", f"{salida}.P",
                         *[f"{salida}.x{i}" for i in range(self.n)],
                         f"{nombre}.Q_por_mol", f"{nombre}.Q", f"{nombre}.beta_salida")

        def resolver_fn(**conocidos):
            F = conocidos[f"{entrada}.F"]
            z = np.array([conocidos[f"{entrada}.x{i}"] for i in range(self.n)], dtype=float)
            suma = float(np.sum(z))
            if suma <= 0:
                return {}
            z = z / suma
            T_in, P = conocidos[f"{entrada}.T"], conocidos[f"{entrada}.P"]
            if F <= 0:
                T_vacio = float(T_salida) if T_salida is not None else T_in
                valores = {
                    f"{salida}.F": 0.0, f"{salida}.T": T_vacio, f"{salida}.P": P,
                    f"{nombre}.Q_por_mol": 0.0, f"{nombre}.Q": 0.0,
                    f"{nombre}.beta_salida": 0.0,
                }
                for i in range(self.n):
                    valores[f"{salida}.x{i}"] = float(z[i])
                return valores
            h_in = evaluador.entalpia_de_corriente(T_in, P, z)

            if T_salida is not None:
                r = evaluador.isotermico(float(T_salida), P, z)
            else:
                r = evaluador.a_entalpia(P, z, h_in + float(Q_por_mol))

            q_especifico = r["h"] - h_in
            valores = {
                f"{salida}.F": F, f"{salida}.T": r["T"], f"{salida}.P": P,
                f"{nombre}.Q_por_mol": q_especifico, f"{nombre}.Q": q_especifico * F,
                f"{nombre}.beta_salida": r["beta"],
            }
            for i in range(self.n):
                valores[f"{salida}.x{i}"] = float(z[i])
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: intercambio de calor",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        self._presion_fijada.add(f"{salida}.P")
        self._temperatura_fijada.add(f"{salida}.T")
        self._registrar_operacion(
            nombre, "intercambiador", entradas=[entrada], salidas=[salida], desde=_ini,
            extra={"corrientes": {"entrada": entrada, "salida": salida},
                   "modo": "T_salida" if T_salida is not None else "Q_por_mol"},
        )
        return nombre

    def agregar_reactor_pfr(self, nombre, entrada, salida, nu, gestor_reaccion,
                            entradas=None):
        """
        Reactor de flujo piston. La misma estequiometria que el CSTR con
        otra relacion volumen-avance (ver core/reactor_pfr.py):

            CSTR:  xi = V * r(T, x_salida)       algebraica
            PFR:   d(xi)/dV = r(T, x(xi))        diferencial

        Invertible en las dos direcciones utiles, igual que el CSTR: dado
        V se integra el avance, y dado el avance se busca el volumen (con
        un evento terminal, una sola integracion en vez de una por
        iteracion).

        Variables propias:
            <nombre>.xi  avance [mol/s]   <nombre>.X  conversion
            <nombre>.V   volumen [m^3]    <nombre>.T  temperatura [K]
        """
        _ini = len(self._bloques)
        lista_entradas = [e for e in (list(entradas) if entradas else [entrada]) if e]
        if not lista_entradas:
            raise ValueError(f"{nombre}: el reactor necesita al menos una entrada.")
        for s in lista_entradas:
            self._exigir_corriente(s)
        self._exigir_corriente(salida)
        if gestor_reaccion is None:
            raise ValueError(
                f"{nombre}: un PFR necesita la cinetica (parametros de Arrhenius). "
                "Sin ella no hay nada que integrar a lo largo del tubo."
            )

        if len(lista_entradas) == 1:
            entrada = lista_entradas[0]
        else:
            entrada = f"{nombre}{self.SUFIJO_INTERNO}entrada"
            self.agregar_corriente(entrada)
            self.agregar_mezclador(f"{nombre}: mezcla de entradas",
                                   entradas=lista_entradas, salida=entrada)

        evaluador = EvaluadorPFR(nu, gestor_reaccion, evaluador_flash=self.flash())

        self._bloques.append(
            _bloque_balance_cstr(nombre, entrada, salida, self.n, evaluador)
        )
        self._bloques.append(
            _bloque_conversion_cstr(nombre, entrada, self.n, evaluador)
        )
        self._bloques.append(
            _bloque_cinetica_pfr(nombre, entrada, self.n, evaluador)
        )

        if f"{salida}.T" not in self._temperatura_fijada:
            self._temperatura_fijada.add(f"{salida}.T")
            self._bloques.append(
                self._bloque_igualdad(f"{salida}.T", f"{nombre}.T",
                                      f"T de salida = T del tubo ({nombre})")
            )
        if f"{salida}.P" not in self._presion_fijada:
            self._presion_fijada.add(f"{salida}.P")
            self._bloques.append(
                self._bloque_igualdad(f"{salida}.P", f"{entrada}.P",
                                      f"Presion sin caida ({nombre})")
            )

        self._registrar_operacion(
            nombre, "reactor_pfr", entradas=lista_entradas, salidas=[salida], desde=_ini,
            extra={"corrientes": {"entradas": lista_entradas, "entrada": entrada,
                                  "salida": salida}},
        )
        return nombre

    def agregar_absorbedor(self, nombre, gas_entrada, gas_salida,
                           liquido_entrada, liquido_salida,
                           N_etapas=6, P_operacion=101325.0, T_operacion=None):
        """
        Absorbedor / desorbedor por el metodo de Kremser
        (ver core/absorbedor.py).

        Cuatro puertos: el gas entra por abajo y sale por arriba, el
        liquido al reves. Como el intercambiador de dos corrientes, es un
        equipo que toma DOS entradas que pueden venir de ramas distintas
        del diagrama.

        El mismo bloque absorbe y desorbe: si el liquido entra mas cargado
        de lo que el equilibrio admite, el transferido sale negativo y el
        componente pasa del liquido al gas.

        Variables propias:
            <nombre>.N  etapas teoricas     <nombre>.T  temperatura [K]
        """
        _ini = len(self._bloques)
        for s in (gas_entrada, gas_salida, liquido_entrada, liquido_salida):
            self._exigir_corriente(s)

        evaluador_flash = self.flash()
        if evaluador_flash is None:
            raise ValueError(
                f"{nombre}: un absorbedor necesita el ProveedorTermodinamico del diagrama "
                "para las constantes de equilibrio K."
            )
        evaluador = EvaluadorAbsorbedor(evaluador_flash.calculadora_elv,
                                        P_sistema=float(P_operacion))
        N = float(N_etapas)
        P_op = float(P_operacion)

        def claves_de(s):
            return (f"{s}.F", f"{s}.T", f"{s}.P", *[f"{s}.x{i}" for i in range(self.n)])

        claves_entrada = claves_de(gas_entrada) + claves_de(liquido_entrada)
        claves_salida = (claves_de(gas_salida) + claves_de(liquido_salida)
                         + (f"{nombre}.N", f"{nombre}.T"))

        def resolver_fn(**c):
            def leer(s):
                F = c[f"{s}.F"]
                x = np.array([c[f"{s}.x{i}"] for i in range(self.n)], dtype=float)
                suma = float(np.sum(x))
                if suma <= 0:
                    return None
                return F, x / suma, c[f"{s}.T"]

            gas, liq = leer(gas_entrada), leer(liquido_entrada)
            if gas is None or liq is None:
                return {}
            V_gas, y_ent, T_gas = gas
            L_liq, x_ent, T_liq = liq

            T = float(T_operacion) if T_operacion is not None else T_liq

            # Rama seca: sin gas o sin disolvente no hay transferencia, y
            # cada corriente sale como entro.
            if V_gas <= 0 or L_liq <= 0:
                valores = {
                    f"{gas_salida}.F": max(V_gas, 0.0), f"{gas_salida}.T": T,
                    f"{gas_salida}.P": P_op,
                    f"{liquido_salida}.F": max(L_liq, 0.0), f"{liquido_salida}.T": T,
                    f"{liquido_salida}.P": P_op,
                    f"{nombre}.N": N, f"{nombre}.T": T,
                }
                for i in range(self.n):
                    valores[f"{gas_salida}.x{i}"] = float(y_ent[i])
                    valores[f"{liquido_salida}.x{i}"] = float(x_ent[i])
                return valores

            r = evaluador.resolver(
                V_gas=V_gas, y_entrada=y_ent, L_liquido=L_liq, x_entrada=x_ent,
                N_etapas=N, T_operacion=T, P=P_op,
            )
            valores = {
                f"{gas_salida}.F": r["V_salida"], f"{gas_salida}.T": T,
                f"{gas_salida}.P": P_op,
                f"{liquido_salida}.F": r["L_salida"], f"{liquido_salida}.T": T,
                f"{liquido_salida}.P": P_op,
                f"{nombre}.N": N, f"{nombre}.T": T,
            }
            for i in range(self.n):
                valores[f"{gas_salida}.x{i}"] = float(r["y_salida"][i])
                valores[f"{liquido_salida}.x{i}"] = float(r["x_salida"][i])
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: absorcion (Kremser, N={N:g})",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        for s in (gas_salida, liquido_salida):
            self._presion_fijada.add(f"{s}.P")
            self._temperatura_fijada.add(f"{s}.T")
        self._registrar_operacion(
            nombre, "absorbedor",
            entradas=[gas_entrada, liquido_entrada],
            salidas=[gas_salida, liquido_salida], desde=_ini,
            extra={"corrientes": {"gas_entrada": gas_entrada, "gas_salida": gas_salida,
                                  "liquido_entrada": liquido_entrada,
                                  "liquido_salida": liquido_salida},
                   "N_etapas": N, "P_operacion": P_op},
        )
        return nombre

    def agregar_intercambiador_doble(self, nombre, caliente_entrada, caliente_salida,
                                     frio_entrada, frio_salida,
                                     Q=None, T_salida_caliente=None, T_salida_frio=None,
                                     aproximacion_minima=5.0, contracorriente=True):
        """
        Intercambiador de DOS corrientes: lo que pierde la caliente lo gana
        la fria.

            F_cal * [h(T_cal_ent) - h(T_cal_sal)]  =  Q
                                                   =  F_frio * [h(T_frio_sal) - h(T_frio_ent)]

        Por que importa tener este y no solo el de una corriente. El
        intercambiador simple recibe un Q de la nada, como si existiera un
        servicio infinito. Este ACOPLA dos puntos del diagrama: la energia
        que sale de un sitio tiene que entrar en otro. Es lo que permite
        integracion energetica -- precalentar la alimentacion con el
        producto caliente, que es el primer ahorro que se busca en
        cualquier proceso real.

        Y para el solver es el caso interesante: es el unico equipo cuyo
        bloque necesita DOS corrientes de entrada que pueden venir de
        ramas distintas del diagrama. Si el motor de punto fijo sabe
        esperar a que las dos esten listas, sabe resolver casi cualquier
        topologia.

        Una sola especificacion de las tres (Q, T de salida caliente, T de
        salida fria). Las otras dos salen del balance.

        SEGUNDA LEY. Se comprueba que no haya cruce de temperaturas: el
        calor no pasa de lo frio a lo caliente. En contracorriente la
        condicion es que la aproximacion en los DOS extremos supere un
        minimo; en co-corriente, que la salida caliente siga por encima de
        la salida fria. Sin esta guarda el balance de energia se cumple
        tan contento con un equipo imposible de construir, que es
        exactamente el patron de fallo que este proyecto persigue: un
        numero plausible sobre algo que no existe.
        """
        _ini = len(self._bloques)
        for s in (caliente_entrada, caliente_salida, frio_entrada, frio_salida):
            self._exigir_corriente(s)

        dadas = [("Q", Q), ("T_salida_caliente", T_salida_caliente),
                 ("T_salida_frio", T_salida_frio)]
        activas = [n for n, v in dadas if v is not None]
        if len(activas) != 1:
            raise ValueError(
                f"{nombre}: da EXACTAMENTE una de Q, T_salida_caliente o T_salida_frio "
                f"(se dieron {len(activas)}: {', '.join(activas) or 'ninguna'}). Las otras "
                "dos salen del balance de energia; fijar dos seria sobre-especificar el equipo."
            )
        modo = activas[0]

        evaluador = self.flash()
        if evaluador is None:
            raise ValueError(
                f"{nombre}: un intercambiador de dos corrientes necesita el "
                "ProveedorTermodinamico del diagrama para medir entalpias."
            )
        aprox_min = float(aproximacion_minima)

        def claves_de(s):
            return (f"{s}.F", f"{s}.T", f"{s}.P", *[f"{s}.x{i}" for i in range(self.n)])

        claves_entrada = claves_de(caliente_entrada) + claves_de(frio_entrada)
        claves_salida = (claves_de(caliente_salida) + claves_de(frio_salida)
                         + (f"{nombre}.Q", f"{nombre}.aproximacion"))

        def resolver_fn(**c):
            def leer(s):
                F = c[f"{s}.F"]
                x = np.array([c[f"{s}.x{i}"] for i in range(self.n)], dtype=float)
                suma = float(np.sum(x))
                if suma <= 0:
                    return None   # sin composicion no hay entalpia que medir
                return F, x / suma, c[f"{s}.T"], c[f"{s}.P"]

            cal, fri = leer(caliente_entrada), leer(frio_entrada)
            if cal is None or fri is None:
                return {}
            F_cal, x_cal, T_cal_ent, P_cal = cal
            F_fri, x_fri, T_fri_ent, P_fri = fri

            # Un lado seco significa que no hay nada que intercambiar: Q=0
            # y cada corriente sale como entro. Importa mas aqui que en
            # ningun otro equipo, porque este cierra un lazo el solito
            # (precalentar la entrada de un reactor con su propia salida),
            # y la primera vuelta de ese lazo arranca justamente con un
            # lado a caudal cero. Sin esto, el lazo no llega a empezar.
            if F_cal <= 0 or F_fri <= 0:
                valores = {
                    f"{caliente_salida}.F": max(F_cal, 0.0),
                    f"{caliente_salida}.T": T_cal_ent, f"{caliente_salida}.P": P_cal,
                    f"{frio_salida}.F": max(F_fri, 0.0),
                    f"{frio_salida}.T": T_fri_ent, f"{frio_salida}.P": P_fri,
                    f"{nombre}.Q": 0.0,
                    f"{nombre}.aproximacion": float(T_cal_ent - T_fri_ent),
                }
                for i in range(self.n):
                    valores[f"{caliente_salida}.x{i}"] = float(x_cal[i])
                    valores[f"{frio_salida}.x{i}"] = float(x_fri[i])
                return valores

            h_cal_ent = evaluador.entalpia_de_corriente(T_cal_ent, P_cal, x_cal)
            h_fri_ent = evaluador.entalpia_de_corriente(T_fri_ent, P_fri, x_fri)

            if modo == "T_salida_caliente":
                r_cal = evaluador.isotermico(float(T_salida_caliente), P_cal, x_cal)
                calor = F_cal * (h_cal_ent - r_cal["h"])
                r_fri = evaluador.a_entalpia(P_fri, x_fri, h_fri_ent + calor / F_fri)
            elif modo == "T_salida_frio":
                r_fri = evaluador.isotermico(float(T_salida_frio), P_fri, x_fri)
                calor = F_fri * (r_fri["h"] - h_fri_ent)
                r_cal = evaluador.a_entalpia(P_cal, x_cal, h_cal_ent - calor / F_cal)
            else:
                calor = float(Q)
                r_cal = evaluador.a_entalpia(P_cal, x_cal, h_cal_ent - calor / F_cal)
                r_fri = evaluador.a_entalpia(P_fri, x_fri, h_fri_ent + calor / F_fri)

            if calor < 0:
                raise ValueError(
                    f"{nombre}: el balance da Q={calor/1000:.3f} kW, o sea calor pasando de la "
                    "corriente FRIA a la CALIENTE. Eso no ocurre solo. Revisa cuál de las dos "
                    "corrientes es la caliente, o la especificación."
                )

            T_cal_sal, T_fri_sal = r_cal["T"], r_fri["T"]
            if contracorriente:
                # En contracorriente los extremos se enfrentan cruzados:
                # la salida caliente sale junto a la entrada fria.
                aproximacion = min(T_cal_sal - T_fri_ent, T_cal_ent - T_fri_sal)
            else:
                aproximacion = T_cal_sal - T_fri_sal
            if aproximacion < aprox_min:
                raise ValueError(
                    f"{nombre}: la aproximación de temperaturas sale {aproximacion:.2f} K, por "
                    f"debajo del mínimo de {aprox_min:.2f} K"
                    + (" (cruce de temperaturas: el equipo es imposible)" if aproximacion < 0 else
                       " (haría falta un área enorme)")
                    + f". Caliente {T_cal_ent:.2f}→{T_cal_sal:.2f} K, fría "
                      f"{T_fri_ent:.2f}→{T_fri_sal:.2f} K."
                )

            valores = {
                f"{caliente_salida}.F": F_cal, f"{caliente_salida}.T": T_cal_sal,
                f"{caliente_salida}.P": P_cal,
                f"{frio_salida}.F": F_fri, f"{frio_salida}.T": T_fri_sal,
                f"{frio_salida}.P": P_fri,
                f"{nombre}.Q": float(calor), f"{nombre}.aproximacion": float(aproximacion),
            }
            for i in range(self.n):
                valores[f"{caliente_salida}.x{i}"] = float(x_cal[i])
                valores[f"{frio_salida}.x{i}"] = float(x_fri[i])
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: intercambio entre dos corrientes ({modo})",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        for s in (caliente_salida, frio_salida):
            self._presion_fijada.add(f"{s}.P")
            self._temperatura_fijada.add(f"{s}.T")
        self._registrar_operacion(
            nombre, "intercambiador_doble",
            entradas=[caliente_entrada, frio_entrada],
            salidas=[caliente_salida, frio_salida], desde=_ini,
            extra={"corrientes": {"caliente_entrada": caliente_entrada,
                                  "caliente_salida": caliente_salida,
                                  "frio_entrada": frio_entrada,
                                  "frio_salida": frio_salida},
                   "modo": modo, "aproximacion_minima": aprox_min},
        )
        return nombre

    def agregar_valvula(self, nombre, entrada, salida, P_salida):
        """
        Valvula de expansion ISENTALPICA: h_salida = h_entrada, exacto.

        No es un intercambiador con Q=0. Aqui lo que cambia es la
        PRESION, y es ese cambio el que redistribuye la MISMA entalpia
        entre calor sensible y calor latente. Un liquido que cruza una
        valvula se vaporiza en parte y, como el calor latente sale de la
        propia corriente, SE ENFRIA sin que nadie le quite energia.

        Variables propias:
            <nombre>.beta_salida fraccion vaporizada tras la expansion
            <nombre>.caida_P     [Pa]
        """
        _ini = len(self._bloques)
        for s in (entrada, salida):
            self._exigir_corriente(s)
        P_out = float(P_salida)

        evaluador = self.flash()
        if evaluador is None:
            raise ValueError(
                f"{nombre}: una valvula necesita el ProveedorTermodinamico del diagrama "
                "para saber cuanto vaporiza al expandirse."
            )

        claves_entrada = (f"{entrada}.F", f"{entrada}.T", f"{entrada}.P",
                          *[f"{entrada}.x{i}" for i in range(self.n)])
        claves_salida = (f"{salida}.F", f"{salida}.T", f"{salida}.P",
                         *[f"{salida}.x{i}" for i in range(self.n)],
                         f"{nombre}.beta_salida", f"{nombre}.caida_P")

        def resolver_fn(**conocidos):
            F = conocidos[f"{entrada}.F"]
            z = np.array([conocidos[f"{entrada}.x{i}"] for i in range(self.n)], dtype=float)
            suma = float(np.sum(z))
            if suma <= 0:
                return {}
            z = z / suma
            T_in, P_in = conocidos[f"{entrada}.T"], conocidos[f"{entrada}.P"]
            if F <= 0:
                valores = {
                    f"{salida}.F": 0.0, f"{salida}.T": T_in, f"{salida}.P": P_out,
                    f"{nombre}.beta_salida": 0.0,
                    f"{nombre}.caida_P": float(P_in - P_out),
                }
                for i in range(self.n):
                    valores[f"{salida}.x{i}"] = float(z[i])
                return valores
            if P_out > P_in:
                raise ValueError(
                    f"{nombre}: una valvula no sube la presion. Entra a {P_in:.4g} Pa y se "
                    f"pidio salida a {P_out:.4g} Pa. Para subir presion usa una bomba."
                )
            h_in = evaluador.entalpia_de_corriente(T_in, P_in, z)
            r = evaluador.a_entalpia(P_out, z, h_in)
            valores = {
                f"{salida}.F": F, f"{salida}.T": r["T"], f"{salida}.P": P_out,
                f"{nombre}.beta_salida": r["beta"], f"{nombre}.caida_P": P_in - P_out,
            }
            for i in range(self.n):
                valores[f"{salida}.x{i}"] = float(z[i])
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: expansion isentalpica",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        self._presion_fijada.add(f"{salida}.P")
        self._temperatura_fijada.add(f"{salida}.T")
        self._registrar_operacion(
            nombre, "valvula", entradas=[entrada], salidas=[salida], desde=_ini,
            extra={"corrientes": {"entrada": entrada, "salida": salida}, "P_salida": P_out},
        )
        return nombre

    def agregar_separador(self, nombre, entrada, salida_ligeros, salida_pesados,
                          recuperaciones):
        """
        Separador de componentes "de atajo": se dice QUE FRACCION de cada
        componente se va por la primera salida, y el equipo reparte.

        Para que sirve, y por que lo tiene todo simulador. Montar un
        diagrama de proceso completo obliga a separar cosas en sitios
        donde todavia no se ha decidido CON QUE equipo. Si lo unico
        disponible es una columna rigurosa, hay que elegir metodo, claves,
        reflujo y presion solo para seguir dibujando. Este bloque corta
        ese nudo: separa como se le pida, y mas adelante se sustituye por
        la columna de verdad.

        Lo que NO es: fisica. No hay equilibrio ni etapas aqui. Es una
        ESPECIFICACION de separacion, y una que puede ser imposible --
        nada impide pedir que dos componentes con el mismo punto de
        ebullicion se separen al 99.9 %. Por eso su ficha lo dice y por
        eso no sustituye a una columna cuando lo que se quiere es saber
        si la separacion se puede hacer.

        recuperaciones: una por componente, en el mismo orden. r_i es la
        fraccion del componente i que sale por 'salida_ligeros'.

            F_lig * x_lig_i = r_i * F_in * z_i
            F_pes * x_pes_i = (1 - r_i) * F_in * z_i

        T y P: las dos salidas heredan las de la entrada. Es la convencion
        habitual para un separador de atajo -- no hay un equipo real
        detras al que pedirle un balance de energia.
        """
        _ini = len(self._bloques)
        for s in (entrada, salida_ligeros, salida_pesados):
            self._exigir_corriente(s)

        recuperaciones = [float(r) for r in recuperaciones]
        if len(recuperaciones) != self.n:
            raise ValueError(
                f"{nombre}: hacen falta {self.n} recuperaciones (una por componente) "
                f"y se dieron {len(recuperaciones)}."
            )
        fuera = [i for i, r in enumerate(recuperaciones) if not (0.0 <= r <= 1.0)]
        if fuera:
            raise ValueError(
                f"{nombre}: la recuperacion del componente {fuera[0]} es "
                f"{recuperaciones[fuera[0]]}, y una recuperacion es una FRACCION: "
                "tiene que estar entre 0 y 1."
            )

        claves_entrada = (f"{entrada}.F", f"{entrada}.T", f"{entrada}.P",
                          *[f"{entrada}.x{i}" for i in range(self.n)])
        claves_salida = tuple(
            clave for s in (salida_ligeros, salida_pesados)
            for clave in (f"{s}.F", f"{s}.T", f"{s}.P", *[f"{s}.x{i}" for i in range(self.n)])
        )

        def resolver_fn(**conocidos):
            F = conocidos[f"{entrada}.F"]
            z = np.array([conocidos[f"{entrada}.x{i}"] for i in range(self.n)], dtype=float)
            suma = float(np.sum(z))
            if suma <= 0:
                return {}   # sin composicion no hay nada que repartir
            z = z / suma
            if F <= 0:
                # Rama seca: no circula materia, pero el estado se propaga
                # igual para que lo de aguas abajo pueda seguir.
                valores = {
                    f"{salida_ligeros}.F": 0.0, f"{salida_pesados}.F": 0.0,
                    f"{salida_ligeros}.T": conocidos[f"{entrada}.T"],
                    f"{salida_pesados}.T": conocidos[f"{entrada}.T"],
                    f"{salida_ligeros}.P": conocidos[f"{entrada}.P"],
                    f"{salida_pesados}.P": conocidos[f"{entrada}.P"],
                }
                for i in range(self.n):
                    valores[f"{salida_ligeros}.x{i}"] = float(z[i])
                    valores[f"{salida_pesados}.x{i}"] = float(z[i])
                return valores
            caudales = F * z
            lig = caudales * np.array(recuperaciones)
            pes = caudales - lig
            F_lig, F_pes = float(np.sum(lig)), float(np.sum(pes))

            valores = {
                f"{salida_ligeros}.F": F_lig, f"{salida_pesados}.F": F_pes,
                f"{salida_ligeros}.T": conocidos[f"{entrada}.T"],
                f"{salida_pesados}.T": conocidos[f"{entrada}.T"],
                f"{salida_ligeros}.P": conocidos[f"{entrada}.P"],
                f"{salida_pesados}.P": conocidos[f"{entrada}.P"],
            }
            # Una salida con caudal cero no tiene composicion definida. Se
            # reparte uniformemente en vez de dejar NaN: asi el diagrama
            # sigue resolviendo y el caudal nulo ya dice lo que hay que saber.
            for i in range(self.n):
                valores[f"{salida_ligeros}.x{i}"] = float(lig[i] / F_lig) if F_lig > 0 else 1.0 / self.n
                valores[f"{salida_pesados}.x{i}"] = float(pes[i] / F_pes) if F_pes > 0 else 1.0 / self.n
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: separacion por recuperaciones",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        for s in (salida_ligeros, salida_pesados):
            self._presion_fijada.add(f"{s}.P")
            self._temperatura_fijada.add(f"{s}.T")
        self._registrar_operacion(
            nombre, "separador", entradas=[entrada],
            salidas=[salida_ligeros, salida_pesados], desde=_ini,
            extra={"corrientes": {"entrada": entrada, "ligeros": salida_ligeros,
                                  "pesados": salida_pesados},
                   "recuperaciones": recuperaciones},
        )
        return nombre

    def agregar_compresor(self, nombre, entrada, salida, P_salida, eficiencia=0.75):
        """
        Compresor o turbina, segun hacia donde vaya la presion. Es el
        mismo equipo: comprimir consume trabajo y expandir lo produce.

        Relacion isentropica de gas ideal para la temperatura ideal, y
        eficiencia isentropica para la real:

            T2s = T1 * (P2/P1)^((k-1)/k)        con k = Cp/(Cp - R)
            T2  = T1 + (T2s - T1) / eta        (compresion)
            T2  = T1 + (T2s - T1) * eta        (expansion)

        Los dos casos son la MISMA idea: la ineficiencia siempre calienta
        respecto del ideal. Comprimiendo eso significa llegar mas caliente
        de lo ideal (se divide); expandiendo, enfriarse menos de lo ideal
        (se multiplica). Escribirlo con un solo signo es el error clasico
        y da turbinas que enfrian de mas.

        El trabajo sale de la entalpia ya validada del proyecto, no de una
        formula aparte:

            W = F * [h_V(T2, y) - h_V(T1, y)]

        y eso es exactamente la integral de Cp del vapor, porque
        h_V = h_L + DHvap y la derivada de esa suma es Cp_V por
        definicion. Asi el compresor mide la energia con la misma regla
        que el flash, el reactor y el mezclador.

        LIMITE, y conviene tenerlo presente: supone que lo que entra es
        GAS, y gas ideal. Comprimir un liquido con esto no tiene sentido
        (para eso esta la bomba). No se comprueba la fase de la entrada:
        es la misma frontera que ya tiene el resto del flowsheet.
        """
        _ini = len(self._bloques)
        for s in (entrada, salida):
            self._exigir_corriente(s)
        P_out = float(P_salida)
        eta = float(eficiencia)
        if not (0.0 < eta <= 1.0):
            raise ValueError(
                f"{nombre}: la eficiencia isentropica es {eta} y tiene que estar en (0, 1]. "
                "Con 1 el equipo seria reversible, que es el limite termodinamico."
            )

        evaluador = self.flash()
        if evaluador is None:
            raise ValueError(
                f"{nombre}: un compresor necesita el ProveedorTermodinamico del diagrama "
                "para el Cp del gas y las entalpias."
            )
        proveedor = self._proveedor
        entalpia = evaluador.entalpia

        claves_entrada = (f"{entrada}.F", f"{entrada}.T", f"{entrada}.P",
                          *[f"{entrada}.x{i}" for i in range(self.n)])
        claves_salida = (f"{salida}.F", f"{salida}.T", f"{salida}.P",
                         *[f"{salida}.x{i}" for i in range(self.n)],
                         f"{nombre}.W", f"{nombre}.T_ideal", f"{nombre}.razon_P")

        def resolver_fn(**conocidos):
            F = conocidos[f"{entrada}.F"]
            y = np.array([conocidos[f"{entrada}.x{i}"] for i in range(self.n)], dtype=float)
            suma = float(np.sum(y))
            if suma <= 0:
                return {}
            y = y / suma
            T1, P1 = conocidos[f"{entrada}.T"], conocidos[f"{entrada}.P"]
            if P1 <= 0:
                return {}
            if F <= 0:
                # Sin caudal no hay trabajo, pero la presion de descarga
                # sigue siendo la del equipo y la corriente conserva su
                # estado: la rama seca no bloquea el diagrama.
                valores = {
                    f"{salida}.F": 0.0, f"{salida}.T": T1, f"{salida}.P": P_out,
                    f"{nombre}.W": 0.0, f"{nombre}.T_ideal": T1,
                    f"{nombre}.razon_P": float(P_out / P1),
                }
                for i in range(self.n):
                    valores[f"{salida}.x{i}"] = float(y[i])
                return valores

            k = proveedor.exponente_isentropico(T1, y)
            razon = P_out / P1
            T2s = T1 * razon ** ((k - 1.0) / k)
            # Un solo signo para los dos casos: la ineficiencia SIEMPRE
            # deja la salida mas caliente que la ideal.
            T2 = T1 + (T2s - T1) / eta if razon >= 1.0 else T1 + (T2s - T1) * eta
            W = F * (entalpia.h_vapor(T2, y) - entalpia.h_vapor(T1, y))

            valores = {
                f"{salida}.F": F, f"{salida}.T": float(T2), f"{salida}.P": P_out,
                f"{nombre}.W": float(W), f"{nombre}.T_ideal": float(T2s),
                f"{nombre}.razon_P": float(razon),
            }
            for i in range(self.n):
                valores[f"{salida}.x{i}"] = float(y[i])
            return valores

        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: compresion isentropica",
                variables=claves_entrada + claves_salida,
                variables_entrada=claves_entrada,
                puede_resolver=lambda n: n == 0,
                resolver_fn=resolver_fn,
            )
        )
        self._presion_fijada.add(f"{salida}.P")
        self._temperatura_fijada.add(f"{salida}.T")
        self._registrar_operacion(
            nombre, "compresor", entradas=[entrada], salidas=[salida], desde=_ini,
            extra={"corrientes": {"entrada": entrada, "salida": salida},
                   "P_salida": P_out, "eficiencia": eta},
        )
        return nombre

    def agregar_bomba(self, nombre, entrada, salida):
        _ini = len(self._bloques)
        """Bomba ideal: solo cambia P. INVERTIBLE -- conocer cualquiera de los dos lados da el otro."""
        for s in (entrada, salida):
            self._exigir_corriente(s)
        campos = ("F", "T", *[f"x{i}" for i in range(self.n)])

        def resolver_fn(**conocidos):
            resultado = {}
            for campo in campos:
                if f"{entrada}.{campo}" in conocidos and f"{salida}.{campo}" not in conocidos:
                    resultado[f"{salida}.{campo}"] = conocidos[f"{entrada}.{campo}"]
                elif f"{salida}.{campo}" in conocidos and f"{entrada}.{campo}" not in conocidos:
                    resultado[f"{entrada}.{campo}"] = conocidos[f"{salida}.{campo}"]
            if f"{nombre}.factor_P" in conocidos and f"{entrada}.P" in conocidos:
                resultado[f"{salida}.P"] = conocidos[f"{entrada}.P"] * conocidos[f"{nombre}.factor_P"]
            elif f"{nombre}.factor_P" in conocidos and f"{salida}.P" in conocidos:
                resultado[f"{entrada}.P"] = conocidos[f"{salida}.P"] / conocidos[f"{nombre}.factor_P"]
            return resultado

        variables = tuple(
            [f"{entrada}.{c}" for c in campos] + [f"{salida}.{c}" for c in campos]
            + [f"{entrada}.P", f"{salida}.P", f"{nombre}.factor_P"]
        )
        self._bloques.append(
            BloqueEcuaciones(
                nombre=f"{nombre}: bombeo",
                variables=variables,
                puede_resolver=lambda n: n >= 1,
                resolver_fn=resolver_fn,
            )
        )
        self._registrar_operacion(
            nombre, "bomba", entradas=[entrada], salidas=[salida], desde=_ini,
            extra={"corrientes": {"entrada": entrada, "salida": salida}},
        )
        return nombre

    # ------------------------------------------------------------------
    def todas_las_variables(self):
        variables = set()
        for bloque in self._bloques:
            variables.update(bloque.variables)
        for corriente in self.corrientes:
            variables.update(variables_de_corriente(corriente, self.n))
        return sorted(variables)

    # ==================================================================
    # RECICLOS
    #
    # El motor de punto fijo solo RELLENA huecos, nunca reescribe. Eso lo
    # hace inmune a oscilar, pero significa que un lazo no tiene por donde
    # empezar: cada corriente del lazo espera a la anterior y ninguna
    # arranca. El sintoma era "faltan datos", indistinguible de un
    # problema mal planteado.
    #
    # La solucion estandar es CORTAR (tearing): se elige una corriente del
    # lazo, se la supone, se resuelve el diagrama entero como si fuera
    # abierto, y se compara el valor que sale por el otro extremo con el
    # supuesto. Se repite hasta que coincidan.
    #
    # Aqui el corte se hace redirigiendo las SALIDAS de quien produce la
    # corriente cortada hacia un alias interno ("s5#calc"), asi que en el
    # diagrama roto nadie escribe "s5" y su valor es el supuesto. No hay
    # que tocar ningun bloque: se reutiliza renombrar_bloque, el mismo
    # mecanismo con el que las operaciones ya apuntan a las corrientes.
    # ==================================================================

    SUFIJO_CORTE = "#calc"
    # Todo lo que lleva '#' en el nombre es maquinaria interna (el alias
    # del corte de un reciclo, la corriente que mezcla las entradas de un
    # reactor): existe en el sistema de ecuaciones pero no se le ensena al
    # usuario, que no la ha dibujado.
    SUFIJO_INTERNO = "#"

    def _grafo_operaciones(self):
        """productor[corriente] = operacion que la genera."""
        productor = {}
        for nombre, info in self._operaciones.items():
            for s in info.get("salidas", []):
                productor[s] = nombre
        return productor

    def detectar_reciclos(self):
        """
        Devuelve las corrientes que hay que cortar, una por lazo.

        Recorre el grafo operacion -> operacion (A precede a B si una
        salida de A es entrada de B) buscando ciclos. Por cada ciclo se
        corta UNA corriente; se elige la que participa en mas ciclos, que
        es la heuristica habitual para cortar lo menos posible.
        """
        productor = self._grafo_operaciones()
        sucesores = {n: set() for n in self._operaciones}
        for nombre, info in self._operaciones.items():
            for s in info.get("entradas", []):
                origen = productor.get(s)
                if origen is not None and origen != nombre:
                    sucesores[origen].add(nombre)

        ciclos = []
        camino, en_camino = [], set()
        visitados = set()

        def dfs(nodo):
            camino.append(nodo)
            en_camino.add(nodo)
            for sig in sorted(sucesores[nodo]):
                if sig in en_camino:
                    ciclos.append(camino[camino.index(sig):] + [sig])
                elif sig not in visitados:
                    dfs(sig)
            camino.pop()
            en_camino.discard(nodo)
            visitados.add(nodo)

        for nodo in sorted(self._operaciones):
            if nodo not in visitados:
                dfs(nodo)

        if not ciclos:
            return []

        # Candidatas de cada ciclo, anotando quien las consume: hace falta
        # para elegir BIEN cual cortar.
        candidatas_por_ciclo = []
        consumidor_de = {}
        equipos_del_ciclo = {}
        for ciclo in ciclos:
            candidatas = set()
            equipos = set(ciclo)
            for a, b in zip(ciclo[:-1], ciclo[1:]):
                for s in self._operaciones[b].get("entradas", []):
                    if productor.get(s) == a:
                        candidatas.add(s)
                        consumidor_de[s] = b
                        equipos_del_ciclo[s] = equipos
            if candidatas:
                candidatas_por_ciclo.append(candidatas)

        # Equipos que participan en ALGUN lazo. Es contra esto que se mide
        # si una entrada es "de fuera", y no contra el ciclo concreto que
        # se este mirando.
        #
        # El fallo que esto corrige, encontrado con una planta de 10
        # equipos y dos lazos entrelazados: 'mezcla' (la salida del
        # mezclador) parecia tener anclaje externo porque la otra entrada
        # de su consumidor venia de un equipo que no estaba en ESE ciclo
        # -- pero si estaba en otro, o sea que tampoco era una
        # alimentacion fresca. Con ese falso anclaje se elegia cortar la
        # salida del mezclador, que es justo el corte que NO funciona
        # (suponerla con F=0 deja sin caudal a todo lo que viene detras),
        # y el lazo no arrancaba: "siguen sin determinarse 11 variables".
        equipos_en_algun_ciclo = {eq for ciclo in ciclos for eq in ciclo}

        def tiene_anclaje_externo(corriente):
            """
            ¿El equipo que CONSUME esta corriente recibe ademas algo de
            fuera del lazo (una alimentacion fresca)?

            Es el criterio que decide si el corte va a funcionar
            numericamente. Matematicamente da igual que corriente del lazo
            se corte, pero en la practica NO: si se corta la salida de un
            mezclador, el supuesto tiene que incluir tambien la
            alimentacion fresca, y empezar por F=0 es absurdo (se probo:
            el reactor recibia caudal cero y el avance pedido resultaba
            imposible). Cortando en cambio la corriente que ENTRA al
            mezclador -- el reciclo propiamente dicho -- suponer F=0
            significa "arrancar la planta sin recirculacion", que es
            fisicamente lo que pasa y converge solo.
            """
            consumidor = consumidor_de.get(corriente)
            if consumidor is None:
                return False
            for entrada in self._operaciones[consumidor].get("entradas", []):
                if entrada == corriente:
                    continue
                origen = productor.get(entrada)
                if origen is None or origen not in equipos_en_algun_ciclo:
                    return True   # alimentacion fresca: ancla la solucion
            return False

        cortes = []
        anclados = {}
        pendientes = list(candidatas_por_ciclo)
        while pendientes:
            frecuencia = {}
            for cand in pendientes:
                for s in cand:
                    frecuencia[s] = frecuencia.get(s, 0) + 1
            # Orden de preferencia: primero las que tienen anclaje externo
            # (razon numerica, ver arriba); luego las que cortan mas
            # ciclos de una vez; y el nombre para que sea determinista.
            elegida = sorted(
                frecuencia.items(),
                key=lambda kv: (not tiene_anclaje_externo(kv[0]), -kv[1], kv[0]),
            )[0][0]
            cortes.append(elegida)
            anclados[elegida] = tiene_anclaje_externo(elegida)
            pendientes = [c for c in pendientes if elegida not in c]
        # Se guarda para que _estimacion_inicial sepa de que tipo de corte
        # se trata: el supuesto bueno NO es el mismo para un reciclo que
        # para una corriente interna de proceso.
        self._cortes_anclados = anclados
        return cortes

    def _bloques_cortados(self, cortes):
        """
        Copia de los bloques donde, para cada corriente cortada, quien la
        PRODUCE escribe en el alias '<corriente>#calc' en vez de en ella.
        """
        productor = self._grafo_operaciones()
        indices_a_renombrar = {}
        for corriente in cortes:
            op = productor.get(corriente)
            if op is None:
                raise ValueError(
                    f"No se puede cortar {corriente!r}: ninguna operacion la produce."
                )
            for idx in self._operaciones[op].get("bloques", []):
                indices_a_renombrar.setdefault(idx, []).append(corriente)

        bloques = []
        for idx, bloque in enumerate(self._bloques):
            cortadas = indices_a_renombrar.get(idx)
            if not cortadas:
                bloques.append(bloque)
                continue
            mapa = {}
            for corriente in cortadas:
                alias = f"{corriente}{self.SUFIJO_CORTE}"
                for v in variables_de_corriente(corriente, self.n):
                    mapa[v] = v.replace(f"{corriente}.", f"{alias}.", 1)
            bloques.append(renombrar_bloque(bloque, mapa, nombre=bloque.nombre))
        return bloques

    def _estimacion_inicial(self, corriente, valores):
        """
        Supuesto de arranque de una corriente cortada.

        Hay DOS casos, y usar el mismo supuesto para los dos no funciona.

        1. Corte ANCLADO -- un reciclo que entra a un equipo que ademas
           recibe alimentacion fresca. Aqui F = 0 es el supuesto correcto:
           equivale a "arranca la planta sin recirculacion", que es
           fisicamente lo que pasa, y la alimentacion fresca ancla la
           solucion desde la primera vuelta.

        2. Corte NO anclado -- una corriente interna de proceso, dentro de
           un lazo que no toca ninguna alimentacion fresca. El caso tipico
           es la INTEGRACION ENERGETICA: un intercambiador que precalienta
           la entrada de un reactor con la salida del mismo reactor cierra
           un lazo entre tres equipos sin una sola corriente fresca
           dentro. Ahi F = 0 no significa "arrancar sin reciclo", significa
           "no circula nada", y entonces todos los equipos del lazo se
           niegan a calcular y la primera vuelta no determina nada: el
           lazo no llega a arrancar. Se vio con una planta de 10 equipos y
           dos reciclos.

           El supuesto util es que por ahi circula aproximadamente lo que
           entra fresco a la planta. No hace falta acertar -- es un punto
           de partida, y Wegstein corrige -- pero tiene que ser distinto
           de cero.

        La presion NO puede ser 0 en ningun caso porque el mezclador toma
        el minimo de sus entradas y arruinaria el resultado; se usa la
        mayor presion conocida del diagrama.
        """
        presiones = [v for k, v in valores.items()
                     if k.endswith(".P") and isinstance(v, (int, float))]
        P = max(presiones) if presiones else 101325.0
        temperaturas = [v for k, v in valores.items()
                        if k.endswith(".T") and isinstance(v, (int, float))]
        T = max(temperaturas) if temperaturas else 298.15

        anclada = getattr(self, "_cortes_anclados", {}).get(corriente, True)
        if anclada:
            F = 0.0
            composicion = [1.0 / self.n] * self.n
        else:
            caudales = [v for k, v in valores.items()
                        if k.endswith(".F") and isinstance(v, (int, float)) and v > 0]
            F = sum(caudales) if caudales else 1.0
            # Composicion de la corriente dada mas grande, que suele ser
            # la alimentacion principal.
            composicion = [1.0 / self.n] * self.n
            mejor = None
            for nombre_c in self.corrientes:
                f = valores.get(f"{nombre_c}.F")
                xs = [valores.get(f"{nombre_c}.x{i}") for i in range(self.n)]
                dados = [x for x in xs if isinstance(x, (int, float))]
                if isinstance(f, (int, float)) and f > 0 and len(dados) >= self.n - 1:
                    if mejor is None or f > mejor:
                        mejor = f
                        falta = sum(x for x in dados)
                        composicion = [
                            x if isinstance(x, (int, float)) else max(0.0, 1.0 - falta)
                            for x in xs
                        ]
            total = sum(composicion)
            if total > 0:
                composicion = [c / total for c in composicion]

        est = {f"{corriente}.F": F, f"{corriente}.T": T, f"{corriente}.P": P}
        for i in range(self.n):
            est[f"{corriente}.x{i}"] = composicion[i]
        return est

    def resolver(self, max_iteraciones=None, tolerancia_reciclo=1e-8,
                 max_ciclos_reciclo=200, amortiguacion=0.0,
                 usar_wegstein=True, estimaciones_reciclo=None, **valores):
        cortes = self.detectar_reciclos()
        if not cortes:
            abierto = self._resolver_abierto(max_iteraciones, valores, info_reciclo=None)
            abierto.pop("pool_crudo", None)
            return abierto

        bloques = self._bloques_cortados(cortes)
        claves_por_corte = {c: list(variables_de_corriente(c, self.n)) for c in cortes}
        todas_las_claves_cortadas = {k for cl in claves_por_corte.values() for k in cl}

        supuesto = {}
        for c in cortes:
            dado = (estimaciones_reciclo or {}).get(c)
            supuesto.update(dado if dado else self._estimacion_inicial(c, valores))
        # Lo que el usuario haya fijado a mano sobre la corriente cortada manda.
        supuesto.update({k: v for k, v in valores.items()
                         if v is not None and k in todas_las_claves_cortadas})

        convergio = False
        error = None
        ciclo = 0
        anterior = {}   # k -> (x_{k-1}, g_{k-1}) para Wegstein
        for ciclo in range(1, max_ciclos_reciclo + 1):
            resultado = self._resolver_abierto(
                max_iteraciones, {**valores, **supuesto}, info_reciclo=None, bloques=bloques
            )
            pool = resultado["pool_crudo"]

            calculado, faltan = {}, []
            for c in cortes:
                for clave in claves_por_corte[c]:
                    alias = clave.replace(f"{c}.", f"{c}{self.SUFIJO_CORTE}.", 1)
                    v = pool.get(alias)
                    if v is None:
                        faltan.append(alias)
                    else:
                        calculado[clave] = float(v)
            if faltan:
                error = (
                    "El lazo no se puede cerrar: tras cortar "
                    f"{', '.join(cortes)} siguen sin determinarse {len(faltan)} "
                    f"variables del extremo calculado (p.ej. {faltan[0]}). "
                    "Suele significar que faltan datos FUERA del lazo."
                )
                break

            error = max(
                abs(calculado[k] - supuesto.get(k, 0.0)) / max(abs(calculado[k]), 1.0)
                for k in calculado
            )
            if error < tolerancia_reciclo:
                convergio = True
                break

            # Actualizacion del supuesto. La sustitucion sucesiva pura
            # (supuesto <- calculado) converge, pero despacio cuando el
            # reciclo es grande: medido, con 90 % de recirculacion tardaba
            # 154 vueltas. WEGSTEIN extrapola a partir de las dos ultimas
            # iteraciones -- es el acelerador clasico para esto y no
            # cambia la solucion, solo la velocidad con que se llega:
            #
            #     s = (g_k - g_{k-1}) / (x_k - x_{k-1})
            #     q = s / (s - 1)
            #     x_{k+1} = q*x_k + (1-q)*g_k
            #
            # q se acota porque la extrapolacion sin limites puede
            # disparar el supuesto fuera de lo fisico (caudales
            # negativos) en las primeras vueltas, cuando todavia no hay
            # una pendiente fiable.
            nuevo_supuesto = {}
            for k, g_k in calculado.items():
                x_k = supuesto.get(k, g_k)
                previo = anterior.get(k)
                if previo is None or usar_wegstein is False:
                    nuevo = g_k
                else:
                    x_ant, g_ant = previo
                    dx = x_k - x_ant
                    if abs(dx) < 1e-14:
                        nuevo = g_k
                    else:
                        pendiente = (g_k - g_ant) / dx
                        if abs(pendiente - 1.0) < 1e-12:
                            nuevo = g_k
                        else:
                            q = pendiente / (pendiente - 1.0)
                            q = min(max(q, -8.0), 0.95)   # cota de estabilidad
                            nuevo = q * x_k + (1.0 - q) * g_k
                # Amortiguacion explicita encima, si el usuario la pide.
                if amortiguacion:
                    nuevo = amortiguacion * x_k + (1.0 - amortiguacion) * nuevo
                anterior[k] = (x_k, g_k)
                nuevo_supuesto[k] = nuevo
            supuesto.update(nuevo_supuesto)

        info = {
            "cortes": cortes,
            "convergio": convergio,
            "ciclos": ciclo,
            "error": error if isinstance(error, float) else None,
            "mensaje": error if isinstance(error, str) else None,
            "tolerancia": tolerancia_reciclo,
        }
        final = self._resolver_abierto(
            max_iteraciones, {**valores, **supuesto}, info_reciclo=info, bloques=bloques
        )
        final.pop("pool_crudo", None)   # maquinaria interna del corte
        return final

    def _resolver_abierto(self, max_iteraciones, valores, info_reciclo, bloques=None):
        bloques = self._bloques if bloques is None else bloques
        variables = set(self.todas_las_variables())
        for b in bloques:
            variables.update(b.variables)
        pool_inicial = {v: None for v in variables}
        pool_inicial.update({k: v for k, v in valores.items() if v is not None})
        resultado = Orquestador(bloques).resolver(max_iteraciones=max_iteraciones, **pool_inicial)
        resultado["reciclo"] = info_reciclo
        # Las variables alias del corte son maquinaria interna: se guardan
        # aparte (pool_crudo, que usa el bucle del reciclo) y se quitan de
        # lo que se reporta, para no ensuciar la vista del usuario.
        resultado["pool_crudo"] = dict(resultado["pool"])
        if any(self.SUFIJO_INTERNO in v for v in resultado["pool"]):
            resultado["pool"] = {k: v for k, v in resultado["pool"].items()
                                 if self.SUFIJO_INTERNO not in k}
            resultado["incognitas_restantes"] = [
                v for v in resultado["incognitas_restantes"] if self.SUFIJO_INTERNO not in v
            ]
            resultado["completo"] = len(resultado["incognitas_restantes"]) == 0
        resultado["diagnostico"] = self.diagnostico(resultado["pool"])
        # Sin esto, dar TODAS las variables de una ecuacion hacia que esa
        # ecuacion nunca se evaluara y los datos incoherentes pasaran en
        # silencio (ver verificar_consistencia).
        inconsistencias = verificar_consistencia(bloques, resultado["pool"])
        # Un bloque que fallo al resolver tambien es informacion para el
        # usuario: sus datos no cumplen esa ecuacion.
        for nombre, mensaje in resultado.get("errores_bloque", {}).items():
            inconsistencias.append({"bloque": nombre, "variable": None, "dado": None,
                                     "implicado": None, "mensaje": mensaje})

        # Si la resolucion se corto por el tope de pasadas, decirlo. Sin
        # esto el sintoma era identico al de "faltan datos" -- y encima
        # el contador de grados de libertad decia GL=0 -- asi que el
        # usuario no tenia forma de saber que el limite era del solver.
        if resultado.get("agotado_el_tope"):
            inconsistencias.append({
                "bloque": "Resolucion", "variable": None, "dado": None, "implicado": None,
                "mensaje": (
                    f"La resolucion se detuvo tras {resultado['iteraciones']} pasadas "
                    "todavia avanzando: el diagrama es mas largo de lo que el tope "
                    "permite recorrer. NO es que falten datos. Si esto aparece con un "
                    "diagrama normal, es un fallo del simulador -- reportalo."
                ),
            })
        if info_reciclo is not None and not info_reciclo["convergio"]:
            detalle = info_reciclo["mensaje"] or (
                f"tras {info_reciclo['ciclos']} vueltas el error todavia es "
                f"{info_reciclo['error']:.3g} (se pide {info_reciclo['tolerancia']:.1g})"
            )
            inconsistencias.append({
                "bloque": "Reciclo", "variable": None, "dado": None, "implicado": None,
                "mensaje": (
                    f"El reciclo por {', '.join(info_reciclo['cortes'])} NO convergio: "
                    f"{detalle}. Los valores mostrados son la ultima iteracion, no una solucion."
                ),
            })
        resultado["inconsistencias"] = inconsistencias
        return resultado

    def grados_de_libertad(self, valores_dados):
        """
        Conteo en vivo: variables totales, cuantas estan dadas y cuantas
        ecuaciones aporta el diagrama.

            grados_de_libertad = incognitas - ecuaciones

        > 0  faltan datos;  = 0  exactamente especificado;
        < 0  sobran datos (hay que comprobar que sean compatibles).

        El total (variables/dadas/incognitas/ecuaciones) es un conteo
        ESTATICO sobre 'valores_dados' tal cual, sin resolver nada --
        supone que las ecuaciones son independientes entre si, y alguna
        es condicional (la T de alimentacion solo existe como ecuacion
        si q=1). 'redundancias' (ver abajo) SI resuelve una vez, porque
        sin eso no puede ver variables determinadas por un camino
        indirecto (p.ej. un caudal masico + composicion). La verdad
        definitiva sigue siendo lo que resolver() consigue determinar.
        """
        variables = self.todas_las_variables()
        dadas = [v for v in variables if valores_dados.get(v) is not None]
        n_ecuaciones = sum(b.n_ecuaciones for b in self._bloques) - self._composiciones_dependientes()
        incognitas = len(variables) - len(dadas)
        return {
            "variables": len(variables),
            "dadas": len(dadas),
            "incognitas": incognitas,
            "ecuaciones": n_ecuaciones,
            "grados_de_libertad": incognitas - n_ecuaciones,
            "redundancias": self.redundancias(valores_dados),
        }

    def _composiciones_dependientes(self):
        """
        Cuantas ecuaciones de composicion hay que DESCONTAR del conteo.

        La regla, que vale para cualquier bloque presente o futuro: si un
        bloque calcula el vector de composicion COMPLETO de una corriente
        (las n fracciones como salida), esas n escrituras no son n
        ecuaciones independientes sino n-1, porque las fracciones que
        produce ya suman 1 -- y esa ecuacion de cierre la aporta aparte el
        bloque de cierre de composicion de esa corriente. Contar las n
        seria contar dos veces.

        Antes esto se compensaba A MANO dentro de cada bloque (en FUG se
        escribio literalmente 'len(variables_salida) - 2'), y por eso solo
        estaba bien en los bloques que se habian revisado: el mezclador y
        el divisor nunca se corrigieron, y cualquier diagrama que los
        usara reportaba GL negativo aunque estuviera bien planteado (se
        midio: -2 con un divisor, -5 con seis equipos). Hacerlo aqui, de
        forma estructural, quita el problema de raiz y no hay que
        acordarse de nada al anadir bloques nuevos.
        """
        if self.n <= 1:
            return 0
        descuento = 0
        for bloque in self._bloques:
            salidas = set(bloque.variables) - set(bloque.variables_entrada)
            if not salidas:
                continue  # bloque invertible: no hay "salidas" fijas que descontar
            for corriente in self.corrientes:
                claves_x = {f"{corriente}.x{i}" for i in range(self.n)}
                if claves_x <= salidas:
                    descuento += 1
        return descuento

    def redundancias(self, valores_dados):
        """
        Donde SOBRAN datos, ecuacion por ecuacion.

        El conteo global de grados de libertad es un agregado y no ve la
        DISTRIBUCION: se puede tener GL<0 ("sobran datos") y a la vez
        variables sin determinar, porque los datos de mas estan en una
        ecuacion y los que faltan hacen falta en otra. Caso real: dar
        x0 Y x1 de una corriente binaria (el cierre solo necesita una)
        mientras faltan q y R para que McCabe-Thiele se dispare.

        Una ecuacion con n variables necesita n - n_ecuaciones datos;
        todo lo que se de por encima de eso es redundante -- no
        necesariamente erroneo, pero se comprobara por consistencia en
        vez de calcularse.

        BUG REAL encontrado y corregido: esto comparaba contra
        'valores_dados' (lo que el usuario escribio a mano), pero una
        variable puede quedar determinada por un camino INDIRECTO -- el
        caso real que lo destapo: dar un caudal en masa (kg/h) mas la
        composicion completa de esa corriente determinan F sin que
        "s1.F" aparezca nunca en valores_dados. Con la version vieja,
        el bloque de balance de materia parecia FALTO de datos (solo
        veia las 3 composiciones escritas a mano) cuando en realidad
        estaba SOBRADO por 1 (F y B ya resueltos por otro camino, mas
        x_D dado encima) -- el panel "Donde sobran datos" no senalaba
        el bloque que de verdad rompia el calculo, y solo mostraba
        redundancias inofensivas (dar x0 Y x1, dar P). Se corrige
        resolviendo una vez (el propio Orquestador tolera bloques que
        fallan, ver core/orquestador.py) y comparando contra el POOL
        resultante, no contra la entrada cruda -- asi una variable
        cuenta como "conocida" tanto si el usuario la escribio como si
        otro bloque ya la determino.
        """
        resultado = Orquestador(self._bloques).resolver(**valores_dados)
        pool = resultado["pool"]
        resueltos_por = resultado["resueltos_por"]

        informes = []
        for bloque in self._bloques:
            # OJO: la salida que el propio bloque acaba de calcular NO
            # cuenta como "dado" para EL MISMO -- si se contara, cualquier
            # bloque que terminara de resolverse aparentaria estar
            # sobre-especificado por su propio resultado (se probo: sin
            # este filtro, "McCabe-Thiele" y "Punto de burbuja" salian
            # como falsos positivos apenas se resolvian). Si otro bloque
            # ya calculo esa variable antes, si cuenta -- es informacion
            # externa a este bloque, igual que si el usuario la escribio.
            dados = [
                v for v in bloque.variables
                if pool.get(v) is not None and resueltos_por.get(v) != bloque.nombre
            ]
            necesarios = len(bloque.variables) - bloque.n_ecuaciones
            sobran = len(dados) - necesarios
            if sobran > 0:
                informes.append({
                    "bloque": bloque.nombre,
                    "sobran": sobran,
                    "dados": dados,
                    "necesarios": max(necesarios, 0),
                })
        return informes

    def diagnostico(self, pool):
        """
        Para la guia de la interfaz: por cada bloque dice cuantas
        incognitas tiene y si podria dispararse. Un bloque "bloqueado"
        (tiene incognitas pero no admite tantas) es exactamente donde el
        usuario debe dar mas datos, y 'faltantes' dice cuales sirven.
        """
        informes = []
        for bloque in self._bloques:
            incognitas = [v for v in bloque.variables if pool.get(v) is None]
            if not incognitas:
                continue
            entradas_incognitas = [v for v in bloque.variables_entrada if pool.get(v) is None]
            informes.append({
                "bloque": bloque.nombre,
                "incognitas": incognitas,
                "faltantes_para_disparar": entradas_incognitas,
                "puede_dispararse": bool(bloque.puede_resolver(len(entradas_incognitas))),
            })
        return informes


# ---------------------------------------------------------------------
# Reactor CSTR. Los tres bloques son independientes a proposito: el
# balance de materia funciona sin saber nada de cinetica (basta con dar
# el avance o una pureza de salida), y la cinetica se suma solo si se
# quiere dimensionar el tanque. Asi el reactor sirve tanto para
# "cuanto convierto con este volumen" como para "que volumen necesito
# para esta pureza", que son las dos preguntas reales.
# ---------------------------------------------------------------------

def _bloque_balance_cstr(nombre, entrada, salida, n_componentes, evaluador):
    """
    F_out*x_out_i = F_in*x_in_i + nu_i*xi, para los n componentes.

    Invertible en las tres direcciones (ver core/reactor_cstr.py): hacia
    adelante, hacia atras, y despejando el avance a partir de UNA
    fraccion de salida -- que es el caso que de verdad se usa ("entra
    esto, quiero esta pureza: cuanto tengo que hacer reaccionar").

    Aporta n ecuaciones. El balance TOTAL (F_out = F_in + nu_tot*xi) no
    se impone aparte: sale de sumar estos n usando que las fracciones de
    cada corriente suman 1, cosa que ya garantiza el bloque de cierre de
    composicion. Imponerlo seria contar una ecuacion de mas y el contador
    de grados de libertad mentiria.
    """
    clave_F_in = f"{entrada}.F"
    clave_F_out = f"{salida}.F"
    claves_x_in = [f"{entrada}.x{i}" for i in range(n_componentes)]
    claves_x_out = [f"{salida}.x{i}" for i in range(n_componentes)]
    clave_xi = f"{nombre}.xi"
    variables = (clave_F_in, clave_F_out, clave_xi, *claves_x_in, *claves_x_out)

    def resolver_fn(**c):
        tiene = lambda k: c.get(k) is not None
        x_in_completo = all(tiene(k) for k in claves_x_in)
        x_out_completo = all(tiene(k) for k in claves_x_out)
        xi = c.get(clave_xi)

        # 1. adelante: alimento completo + avance -> salida
        if xi is not None and tiene(clave_F_in) and x_in_completo:
            F_out, x_out = evaluador.salida_desde_entrada(
                c[clave_F_in], [c[k] for k in claves_x_in], xi
            )
            return {clave_F_out: float(F_out),
                    **{k: float(v) for k, v in zip(claves_x_out, x_out)}}

        # 2. atras: salida completa + avance -> alimento
        if xi is not None and tiene(clave_F_out) and x_out_completo:
            F_in, x_in = evaluador.entrada_desde_salida(
                c[clave_F_out], [c[k] for k in claves_x_out], xi
            )
            return {clave_F_in: float(F_in),
                    **{k: float(v) for k, v in zip(claves_x_in, x_in)}}

        # 3. el avance a partir de UNA fraccion de salida conocida
        if xi is None and tiene(clave_F_in) and x_in_completo:
            for j, clave in enumerate(claves_x_out):
                if not tiene(clave):
                    continue
                xi_hallado = evaluador.avance_desde_fraccion(
                    c[clave_F_in], c[claves_x_in[j]], c[clave], j
                )
                F_out, x_out = evaluador.salida_desde_entrada(
                    c[clave_F_in], [c[k] for k in claves_x_in], xi_hallado
                )
                return {clave_xi: float(xi_hallado), clave_F_out: float(F_out),
                        **{k: float(v) for k, v in zip(claves_x_out, x_out)}}
        return {}

    return BloqueEcuaciones(
        nombre=f"{nombre}: balance del reactor",
        variables=variables,
        puede_resolver=lambda n: n >= 0,  # decide por si mismo que direccion puede
        resolver_fn=resolver_fn,
        n_ecuaciones=n_componentes,
    )


def _bloque_conversion_cstr(nombre, entrada, n_componentes, evaluador):
    """
    X = (lo que se consume del reactivo limitante) / (lo que entra de el).
    Es una DEFINICION, asi que va en su propio bloque: quien no quiera
    razonar en conversion simplemente no la da ni la mira.

    Tambien invertible: dada X se obtiene el avance, que es como se suele
    plantear un problema de reactores ("quiero 85 % de conversion").
    """
    clave_F_in = f"{entrada}.F"
    claves_x_in = [f"{entrada}.x{i}" for i in range(n_componentes)]
    clave_xi = f"{nombre}.xi"
    clave_X = f"{nombre}.X"
    variables = (clave_F_in, clave_xi, clave_X, *claves_x_in)

    def resolver_fn(**c):
        tiene = lambda k: c.get(k) is not None
        if not tiene(clave_F_in) or not all(tiene(k) for k in claves_x_in):
            return {}
        F_in = c[clave_F_in]
        x_in = [c[k] for k in claves_x_in]

        if tiene(clave_xi) and not tiene(clave_X):
            X, _ = evaluador.conversion(F_in, x_in, c[clave_xi])
            return {clave_X: float(X)}

        if tiene(clave_X) and not tiene(clave_xi):
            # xi desde X: se necesita saber cual es el limitante, y eso
            # depende solo del alimento, que ya se conoce aqui.
            _, limitante = evaluador.conversion(F_in, x_in, 0.0)
            import numpy as _np
            consumo_unitario = abs(float(_np.asarray(evaluador.nu)[limitante]))
            xi = c[clave_X] * F_in * x_in[limitante] / consumo_unitario
            return {clave_xi: float(xi)}
        return {}

    return BloqueEcuaciones(
        nombre=f"{nombre}: conversion",
        variables=variables,
        puede_resolver=lambda n: n >= 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=1,
    )


def _bloque_cinetica_pfr(nombre, entrada, n_componentes, evaluador):
    """
    d(xi)/dV = r(T, x(xi)), integrado a lo largo del tubo.

    Es el gemelo de _bloque_cinetica_cstr y, como el, invertible en las
    dos direcciones: con V se integra hasta la salida; con xi se busca el
    volumen que lo produce.

    La diferencia de firma con el CSTR no es cosmetica. Alli el volumen
    sale de V = xi/r, que solo necesita la composicion de SALIDA. Aqui la
    velocidad cambia a lo largo del tubo, asi que hace falta el ALIMENTO
    para saber por donde empieza la integracion -- por eso este bloque lee
    la corriente de entrada y el del CSTR lee la de salida.
    """
    clave_F_in = f"{entrada}.F"
    claves_x_in = [f"{entrada}.x{i}" for i in range(n_componentes)]
    clave_xi, clave_V, clave_T = f"{nombre}.xi", f"{nombre}.V", f"{nombre}.T"
    variables = (clave_F_in, clave_xi, clave_V, clave_T, *claves_x_in)

    def resolver_fn(**c):
        tiene = lambda k: c.get(k) is not None
        if not tiene(clave_T) or not tiene(clave_F_in):
            return {}
        if not all(tiene(k) for k in claves_x_in):
            return {}
        F_in = c[clave_F_in]
        x_in = np.array([c[k] for k in claves_x_in], dtype=float)
        suma = float(np.sum(x_in))
        if F_in <= 0 or suma <= 0:
            return {}
        x_in = x_in / suma

        if tiene(clave_V) and not tiene(clave_xi):
            r = evaluador.avance_desde_volumen(F_in, x_in, c[clave_T], c[clave_V])
            return {clave_xi: r["xi"]}
        if tiene(clave_xi) and not tiene(clave_V):
            V = evaluador.volumen_desde_avance(
                c[clave_xi], c[clave_T], F_in=F_in, x_in=x_in
            )
            return {clave_V: float(V)}
        return {}

    return BloqueEcuaciones(
        nombre=f"{nombre}: cinetica (flujo piston)",
        variables=variables,
        puede_resolver=lambda n: n >= 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=1,
    )


def _bloque_equilibrio_cstr(nombre, entrada, n_componentes, evaluador):
    """
    xi determinado por EQUILIBRIO QUIMICO a la temperatura del tanque:

        prod_i a_i^nu_i = K_eq(T)

    Sustituye al bloque de cinetica, no se suma a el: los dos calculan el
    mismo xi por caminos distintos y tenerlos a la vez seria contar dos
    veces la misma ecuacion.

    La diferencia con la cinetica no es de precision sino de PREGUNTA. La
    cinetica dice "con este tanque llego hasta aqui"; el equilibrio dice
    "por mucho tanque que pongas, no pasas de aqui". Poder ver los dos
    sobre el mismo diagrama es justo lo que hace falta para decidir si un
    reactor merece la pena.

    No necesita volumen: el equilibrio es independiente del tamano. Por eso
    un reactor en este modo NO declara V.
    """
    clave_F_in = f"{entrada}.F"
    claves_x_in = [f"{entrada}.x{i}" for i in range(n_componentes)]
    clave_xi = f"{nombre}.xi"
    clave_T = f"{nombre}.T"
    clave_K = f"{nombre}.K_eq"
    entradas = (clave_F_in, clave_T, *claves_x_in)
    variables = entradas + (clave_xi, clave_K)

    def resolver_fn(**c):
        if any(c.get(k) is None for k in entradas):
            return {}
        F_in = c[clave_F_in]
        x_in = np.array([c[k] for k in claves_x_in], dtype=float)
        suma = float(np.sum(x_in))
        if F_in <= 0 or suma <= 0:
            return {}
        r = evaluador.avance_de_equilibrio(F_in, x_in / suma, c[clave_T])
        return {clave_xi: r["xi"], clave_K: r["K_eq"]}

    return BloqueEcuaciones(
        nombre=f"{nombre}: equilibrio quimico",
        variables=variables,
        variables_entrada=entradas,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=2,
    )


def _bloque_energia_cstr(nombre, entrada, salida, n_componentes, evaluador, P_conocida_de):
    """
    F_in*h(T_in,x_in) + Q = F_out*h(T_out,x_out) + xi*dH_rxn(T_ref).

    UNA ecuacion de energia, resuelta en las dos direcciones utiles --
    igual que el resto de bloques del proyecto, no solo hacia adelante:

      T de salida conocida  ->  se calcula Q   (reactor isotermo o de T impuesta)
      Q conocido            ->  se calcula T   (adiabatico si Q=0)

    El primer caso es el que mas cambia lo que el simulador puede decir:
    un reactor isotermo sin este balance oculta CUANTA refrigeracion hace
    falta para mantener esa temperatura, que en una exotermica suele ser
    la restriccion de diseno de verdad. Con MTBE a 12 mol/s de avance son
    702 kW que antes no aparecian por ningun lado.
    """
    clave_F_in, clave_F_out = f"{entrada}.F", f"{salida}.F"
    claves_x_in = [f"{entrada}.x{i}" for i in range(n_componentes)]
    clave_T_in, clave_T_out = f"{entrada}.T", f"{salida}.T"
    clave_P = f"{P_conocida_de}.P"
    clave_xi = f"{nombre}.xi"
    clave_Q = f"{nombre}.Q"
    clave_Q_rxn = f"{nombre}.Q_reaccion"

    entradas = (clave_F_in, clave_T_in, clave_xi, *claves_x_in)
    variables = entradas + (clave_T_out, clave_Q, clave_Q_rxn, clave_P, clave_F_out)

    def resolver_fn(**c):
        tiene = lambda k: c.get(k) is not None
        if not (tiene(clave_F_in) and tiene(clave_T_in) and tiene(clave_xi)
                and all(tiene(k) for k in claves_x_in)):
            return {}
        F_in = c[clave_F_in]
        x_in = np.array([c[k] for k in claves_x_in], dtype=float)
        suma = float(np.sum(x_in))
        if F_in <= 0 or suma <= 0:
            return {}
        x_in = x_in / suma
        T_in, xi = c[clave_T_in], c[clave_xi]
        P = c.get(clave_P)

        if tiene(clave_T_out) and not tiene(clave_Q):
            r = evaluador.calor_necesario(F_in, x_in, T_in, xi, T_salida=c[clave_T_out], P=P)
            return {clave_Q: r["Q"], clave_Q_rxn: r["Q_reaccion"]}

        if tiene(clave_Q) and not tiene(clave_T_out):
            r = evaluador.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=c[clave_Q], P=P)
            return {clave_T_out: r["T_salida"], clave_Q_rxn: r["Q_reaccion"]}

        # Las dos conocidas: no queda nada que despejar, pero el calor de
        # reaccion si se puede publicar (es una definicion, no el balance).
        if tiene(clave_T_out) and tiene(clave_Q) and not tiene(clave_Q_rxn):
            return {clave_Q_rxn: evaluador.calor_de_reaccion(xi)}
        return {}

    return BloqueEcuaciones(
        nombre=f"{nombre}: balance de energia",
        variables=variables,
        variables_entrada=entradas,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
        # Dos: el balance de energia en si, y la definicion del calor de
        # reaccion. La tercera variable de salida (T o Q, segun el modo)
        # es la que el balance despeja, no una ecuacion adicional.
        n_ecuaciones=2,
    )


def _bloque_reactor_acoplado(nombre, entrada, salida, n_componentes, evaluador, P_conocida_de):
    """
    Cinetica Y energia a la vez, para el caso en que las dos se necesitan
    mutuamente: reactor del que se conoce el VOLUMEN y que no es isotermo.

    Por que no puede hacerlo el motor de punto fijo repartido en dos
    bloques: la cinetica necesita T para dar xi, y el balance de energia
    necesita xi para dar T. Ninguno de los dos puede arrancar, y el
    sintoma seria "faltan datos" -- indistinguible de un diagrama mal
    planteado. Es el mismo caso que un reciclo, y se resuelve igual:
    planteando las dos ecuaciones a la vez (ver
    EvaluadorCSTR.resolver_con_cinetica).

    Este bloque SUSTITUYE a los de cinetica y energia por separado; no se
    suma a ellos. Aporta las mismas 3 ecuaciones que aportaban entre los
    dos (xi, T y el calor de reaccion), asi que el conteo de grados de
    libertad no cambia.
    """
    clave_F_in = f"{entrada}.F"
    claves_x_in = [f"{entrada}.x{i}" for i in range(n_componentes)]
    clave_T_in = f"{entrada}.T"
    clave_P = f"{P_conocida_de}.P"
    clave_V, clave_Q = f"{nombre}.V", f"{nombre}.Q"
    clave_xi, clave_T = f"{nombre}.xi", f"{nombre}.T"
    clave_Q_rxn = f"{nombre}.Q_reaccion"

    entradas = (clave_F_in, clave_T_in, clave_V, clave_Q, *claves_x_in)
    variables = entradas + (clave_xi, clave_T, clave_Q_rxn, clave_P)

    def resolver_fn(**c):
        tiene = lambda k: c.get(k) is not None
        if not all(tiene(k) for k in (clave_F_in, clave_T_in, clave_V, clave_Q)):
            return {}
        if not all(tiene(k) for k in claves_x_in):
            return {}
        if tiene(clave_xi) and tiene(clave_T):
            return {}
        F_in = c[clave_F_in]
        x_in = np.array([c[k] for k in claves_x_in], dtype=float)
        suma = float(np.sum(x_in))
        if F_in <= 0 or suma <= 0:
            return {}
        r = evaluador.resolver_con_cinetica(
            F_in, x_in / suma, c[clave_T_in], c[clave_V],
            Q=c[clave_Q], P=c.get(clave_P),
        )
        return {clave_xi: r["xi"], clave_T: r["T_salida"], clave_Q_rxn: r["Q_reaccion"]}

    return BloqueEcuaciones(
        nombre=f"{nombre}: cinetica + energia acopladas",
        variables=variables,
        variables_entrada=entradas,
        puede_resolver=lambda n: n == 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=3,
    )


def _bloque_cinetica_cstr(nombre, salida, n_componentes, evaluador):
    """
    xi = V * r(T, x_out).

    OJO a la composicion en la que se evalua r: en un CSTR el tanque esta
    perfectamente mezclado, asi que su contenido es la corriente de
    SALIDA. Evaluar la velocidad en el alimento seria el error clasico
    (y daria un reactor mucho mas chico de lo real, porque la velocidad
    en el alimento es la mas alta de todo el reactor).

    Invertible en las dos direcciones que importan: V dado xi (dimensionar)
    y xi dado V (simular un tanque que ya existe).
    """
    claves_x_out = [f"{salida}.x{i}" for i in range(n_componentes)]
    clave_xi = f"{nombre}.xi"
    clave_V = f"{nombre}.V"
    clave_T = f"{nombre}.T"
    variables = (clave_xi, clave_V, clave_T, *claves_x_out)

    def resolver_fn(**c):
        tiene = lambda k: c.get(k) is not None
        if not tiene(clave_T) or not all(tiene(k) for k in claves_x_out):
            return {}
        x_out = [c[k] for k in claves_x_out]

        if tiene(clave_V) and not tiene(clave_xi):
            return {clave_xi: float(evaluador.avance_desde_cinetica(c[clave_V], c[clave_T], x_out))}
        if tiene(clave_xi) and not tiene(clave_V):
            return {clave_V: float(evaluador.volumen_desde_avance(c[clave_xi], c[clave_T], x_out))}
        return {}

    return BloqueEcuaciones(
        nombre=f"{nombre}: cinetica",
        variables=variables,
        puede_resolver=lambda n: n >= 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=1,
    )


# ---------------------------------------------------------------------
# Columna multicomponente FUG sobre variables de corriente.
#
# El nucleo (core/fug.py + bloque_fug en orquestador.py) ya resolvia FUG,
# pero con variables de pool VECTORIALES (x_D, x_B eran arrays enteros).
# Aqui el pool es escalar por corriente (s2.x0, s2.x1, ...), asi que
# estos dos bloques hacen de traductores: leen las fracciones sueltas,
# arman los vectores, llaman a AnalizadorFUG y vuelven a repartir el
# resultado en fracciones sueltas.
# ---------------------------------------------------------------------

def _analizador_fug(contexto, z_F):
    from core.fug import AnalizadorFUG
    return AnalizadorFUG(
        calculadora_elv=contexto["calculadora_elv"],
        proveedor=contexto["proveedor"],
        nombres=contexto["nombres"],
        z_F=np.asarray(z_F, dtype=float),
        q=contexto["q"],
        P_sistema=contexto["P_sistema"],
        indice_LK=contexto["indice_LK"],
        indice_HK=contexto["indice_HK"],
    )


def _bloque_fug_corrientes(nombre, alimentacion, destilado, fondos, n, contexto,
                            reclama_T_alimentacion=True):
    """
    Fenske-Underwood-Gilliland. Forward-only por naturaleza: dadas la
    alimentacion, el reflujo y las dos recuperaciones clave, calcula TODO
    el reparto de una pasada. No es invertible (no hay forma de pedirle
    "que alimentacion da este destilado"), igual que bloque_fug original.

    Conteo de ecuaciones: el bloque declara TODAS sus salidas. El
    descuento por escribir vectores de composicion completos (n
    escrituras que son n-1 ecuaciones, porque el cierre aporta la otra)
    lo hace el diagrama de forma estructural en
    _composiciones_dependientes -- antes estaba puesto a mano aqui y por
    eso solo estaba bien en este bloque y no en el mezclador ni el divisor.
    """
    clave_F = f"{alimentacion}.F"
    claves_z = [f"{alimentacion}.x{i}" for i in range(n)]
    clave_T_F = f"{alimentacion}.T"
    clave_D = f"{destilado}.F"
    claves_xD = [f"{destilado}.x{i}" for i in range(n)]
    clave_T_D = f"{destilado}.T"
    clave_B = f"{fondos}.F"
    claves_xB = [f"{fondos}.x{i}" for i in range(n)]
    clave_T_B = f"{fondos}.T"
    clave_R = f"{nombre}.R"
    clave_rLK = f"{nombre}.recuperacion_LK_D"
    clave_rHK = f"{nombre}.recuperacion_HK_B"
    claves_op = [f"{nombre}.{v}" for v in ("N", "N_min", "R_min", "theta")]

    variables_entrada = (clave_F, *claves_z, clave_R, clave_rLK, clave_rHK)
    variables_salida = (clave_D, *claves_xD, clave_B, *claves_xB,
                        *claves_op, clave_T_D, clave_T_B)
    if reclama_T_alimentacion:
        variables_salida = variables_salida + (clave_T_F,)

    def resolver_fn(**c):
        z_F = np.array([c[k] for k in claves_z], dtype=float)
        suma = z_F.sum()
        if not np.isclose(suma, 1.0, atol=1e-6):
            raise ValueError(
                f"{nombre}: la composicion de la alimentacion suma {suma:.6g}, no 1. "
                "FUG necesita la alimentacion COMPLETA (todas las fracciones)."
            )
        analizador = _analizador_fug(contexto, z_F / suma)
        rep = analizador.reporte_completo(
            recuperacion_LK_D=c[clave_rLK],
            recuperacion_HK_B=c[clave_rHK],
            R=c[clave_R],
        )
        F = c[clave_F]
        # theta (raiz de Underwood) viene como LISTA: puede haber mas de
        # una cuando se distribuyen varios componentes no clave. El pool
        # guarda escalares, asi que se publica la primera -- que es la que
        # usa el propio metodo para R_min -- en vez de reventar al
        # convertir una lista a float, que es lo que pasaba.
        thetas = rep["theta"]
        theta_principal = float(thetas[0] if isinstance(thetas, (list, tuple, np.ndarray)) else thetas)

        salida = {
            clave_D: float(rep["D"]) * F,
            clave_B: float(rep["B"]) * F,
            f"{nombre}.N": float(rep["N"]),
            f"{nombre}.N_min": float(rep["N_min"]),
            f"{nombre}.R_min": float(rep["R_min"]),
            f"{nombre}.theta": theta_principal,
            clave_T_D: float(rep["T_D"]),
            clave_T_B: float(rep["T_B"]),
        }
        if reclama_T_alimentacion:
            salida[clave_T_F] = float(rep["T_F"])
        for i in range(n):
            salida[claves_xD[i]] = float(rep["x_D"][i])
            salida[claves_xB[i]] = float(rep["x_B"][i])
        return salida

    return BloqueEcuaciones(
        nombre=f"{nombre}: FUG",
        variables=variables_entrada + variables_salida,
        variables_entrada=variables_entrada,
        puede_resolver=lambda n_inc: n_inc == 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=len(variables_salida),
    )


def _bloque_cargas_fug_corrientes(nombre, alimentacion, destilado, fondos, n, contexto):
    """
    Balance de energia de la columna FUG. Va aparte del bloque de FUG
    (igual que en McCabe-Thiele y Ponchon-Savarit) para poder resolver
    primero la materia y acoplar la energia solo cuando haga falta.
    """
    clave_F = f"{alimentacion}.F"
    claves_z = [f"{alimentacion}.x{i}" for i in range(n)]
    clave_D = f"{destilado}.F"
    claves_xD = [f"{destilado}.x{i}" for i in range(n)]
    clave_T_D = f"{destilado}.T"
    clave_B = f"{fondos}.F"
    claves_xB = [f"{fondos}.x{i}" for i in range(n)]
    clave_T_B = f"{fondos}.T"
    clave_R = f"{nombre}.R"
    claves_salida = [f"{nombre}.{v}" for v in
                     ("Q_c", "Q_R", "R_int", "V_barra", "T_reflujo")]

    variables_entrada = (clave_F, *claves_z, clave_D, *claves_xD, clave_T_D,
                         clave_B, *claves_xB, clave_T_B, clave_R)

    def resolver_fn(**c):
        z_F = np.array([c[k] for k in claves_z], dtype=float)
        analizador = _analizador_fug(contexto, z_F / z_F.sum())
        cargas = analizador.calcular_cargas_termicas(
            D=c[clave_D], B=c[clave_B], F=c[clave_F],
            x_D=np.array([c[k] for k in claves_xD], dtype=float),
            x_B=np.array([c[k] for k in claves_xB], dtype=float),
            T_D=c[clave_T_D], T_B=c[clave_T_B], R_ext=c[clave_R],
        )
        return {f"{nombre}.{k}": float(v) for k, v in cargas.items()
                if f"{nombre}.{k}" in claves_salida}

    return BloqueEcuaciones(
        nombre=f"{nombre}: cargas termicas",
        variables=variables_entrada + tuple(claves_salida),
        variables_entrada=variables_entrada,
        puede_resolver=lambda n_inc: n_inc == 0,
        resolver_fn=resolver_fn,
        n_ecuaciones=len(claves_salida),
    )
