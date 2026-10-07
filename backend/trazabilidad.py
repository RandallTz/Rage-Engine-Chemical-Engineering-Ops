"""
Trazabilidad de un calculo: con que se calculo y sobre que entradas.

Para que sirve. Un numero sin procedencia no se puede reproducir ni
auditar, y en este proyecto eso importa mas de lo normal porque las
validaciones comparan contra valores EXACTOS ("benceno/tolueno 50/50 =
365.515693 K, identico bit a bit"). Un informe que diga "365.52 K" sin
decir con que version del motor y con que version de 'thermo' se obtuvo
no es un resultado reproducible: es una captura de pantalla.

Tres cosas se certifican aqui:

  1. **El motor**: version del proyecto y commit de git. El commit es lo
     unico que identifica el codigo sin ambiguedad; la version sola no
     distingue dos estados del arbol de trabajo.
  2. **El proveedor termodinamico**: su identificador (que modelo) y su
     version REAL, que son las versiones de 'thermo', 'chemicals' y
     'fluids'. Esto no es un detalle administrativo -- es la razon de que
     requirements.txt tenga las versiones fijas. Una correlacion que
     cambie rio arriba cambia los numeros de este simulador sin que nadie
     toque una linea, y ya paso una vez (los atributos Hfl/Gfl de
     'thermo', registrado en roadmap.md).
  3. **Las entradas**: una huella determinista de las entradas FISICAS
     normalizadas. Dos peticiones con la misma huella tienen que dar el
     mismo resultado; si dan otro, el cambio esta en el motor o en las
     dependencias, y eso es exactamente lo que la huella permite
     distinguir.

QUE ENTRA Y QUE NO EN LA HUELLA
-------------------------------
Entra lo que cambia el resultado fisico:
  - los componentes, EN ORDEN (el orden define que es x0)
  - el modelo termodinamico
  - cada operacion: tipo, nombre, corrientes conectadas y parametros
  - los valores dados, en SI, con un formato de float canonico
  - los caudales masicos, que viajan aparte
  - las especificaciones de diseno

No entra lo que no lo cambia:
  - las coordenadas de los nodos en el lienzo
  - las unidades preferidas para MOSTRAR (el valor ya viaja en SI)
  - el nombre de la simulacion

El formato canonico de los floats no es cosmetico: `repr(0.1 + 0.2)` y
`repr(0.3)` difieren, y sin normalizar, dos peticiones identicas para
cualquier proposito practico darian huellas distintas. Se usan 15 cifras
significativas, que es lo que un float64 distingue de verdad, y los
enteros se escriben como enteros para que 1 y 1.0 no sean dos entradas
distintas.

Zona libre de pint: todo llega ya en SI desde la frontera.
"""

import hashlib
import json
import math
import os
import subprocess
from datetime import datetime, timezone

# Version del motor de calculo. Se sube A MANO cuando cambia algo que
# puede mover un numero, y el commit de git desambigua el resto.
VERSION_MOTOR = "0.15.0"

# Identificador del unico modelo termodinamico implementado. Es una
# cadena estable: si algun dia hay otro, este no cambia.
MODELO_TERMODINAMICO = "unifac_raoult"

_CIFRAS = 15


def _commit_git():
    """
    El commit del arbol de trabajo, o None si no se puede saber.

    None es una respuesta legitima y hay que poder darla: un despliegue
    desde un tarball no tiene .git, y en Render el contenedor puede no
    traer el ejecutable de git. Inventarse un identificador seria peor que
    admitir que no se sabe, porque un identificador falso se propaga a los
    informes y nadie lo cuestiona.

    Se anade el sufijo '-sucio' cuando hay cambios sin commitear: un
    commit a secas afirmaria que el codigo es exactamente el de ese
    commit, y con el arbol modificado eso es falso.
    """
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True,
            text=True, timeout=5, check=True,
        ).stdout.strip()
        if not commit:
            return None
        sucio = subprocess.run(
            ["git", "status", "--porcelain"], cwd=raiz, capture_output=True,
            text=True, timeout=5, check=True,
        ).stdout.strip()
        return f"{commit}-sucio" if sucio else commit
    except Exception:
        return None


def _versiones_dependencias():
    """
    Las versiones de las librerias que DECIDEN los numeros.

    No es la lista de dependencias del proyecto: son las tres que entran
    en cada propiedad termodinamica. Si una cambia, los resultados pueden
    cambiar, y esa es la informacion que hace falta para reproducir.
    """
    versiones = {}
    for paquete in ("thermo", "chemicals", "fluids", "numpy", "scipy"):
        try:
            modulo = __import__(paquete)
            versiones[paquete] = getattr(modulo, "__version__", None)
        except Exception:
            versiones[paquete] = None
    return versiones


def _canonico(valor):
    """
    Un valor en forma canonica, para que la huella sea estable.

    Los floats se escriben con 15 cifras significativas porque es lo que
    un float64 distingue; mas cifras introducirian ruido de redondeo en la
    huella. Un float que vale un entero se escribe como entero, para que
    1 y 1.0 no den huellas distintas.

    NaN e infinito se escriben con nombre propio en vez de dejar que
    `json.dumps` produzca `NaN`, que no es JSON valido -- aqui no se
    serializa a JSON para enviarlo, pero la huella se calcula sobre texto
    y conviene que ese texto sea legible si alguna vez hay que depurarla.
    """
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if math.isnan(valor):
            return "NaN"
        if math.isinf(valor):
            return "Infinito" if valor > 0 else "-Infinito"
        if valor == int(valor) and abs(valor) < 2 ** 53:
            return int(valor)
        return float(f"{valor:.{_CIFRAS}g}")
    if isinstance(valor, dict):
        # Ordenado por clave: el orden de un diccionario no es parte de
        # la fisica, y sin ordenar la huella dependeria de como el cliente
        # haya construido el JSON.
        return {str(k): _canonico(valor[k]) for k in sorted(valor, key=str)}
    if isinstance(valor, (list, tuple)):
        # Las listas SI conservan su orden: el de los componentes define
        # cual es x0, y el de los coeficientes estequiometricos va con el.
        return [_canonico(v) for v in valor]
    if valor is None:
        return None
    return str(valor)


def entradas_normalizadas(request):
    """
    Las entradas fisicas de una peticion, normalizadas y en orden.

    Se construye a mano, campo por campo, y no con un volcado automatico
    del request. Es mas trabajo y es lo correcto: un volcado automatico
    metería en la huella cualquier campo nuevo que alguien anada a los
    esquemas, incluido uno que no afecte al resultado, y entonces la
    huella cambiaria sin que la fisica cambie -- que es justo lo que una
    huella no debe hacer.
    """
    operaciones = []
    for op in getattr(request, "operaciones", None) or []:
        entrada = {
            "nombre": op.nombre,
            "tipo": op.tipo,
            "corrientes": _canonico(op.corrientes),
        }
        # Solo los parametros que de verdad entran en el calculo, con el
        # nombre que tienen en el esquema.
        for campo in (
            "metodo", "P_sistema", "q", "indice_LK", "indice_HK", "fracciones",
            "con_balance_energia", "con_cinetica", "modo_energia", "Q",
            "T_operacion", "fraccion_vapor", "Q_por_mol", "T_salida", "P_salida",
            "recuperaciones", "eficiencia", "T_salida_caliente", "T_salida_frio",
            "aproximacion_minima", "N_etapas", "contracorriente",
            "caida_P", "caida_P_caliente", "caida_P_frio", "caida_P_gas",
            "con_dimensionado", "espaciado_platos_mm", "fraccion_de_inundacion",
            "coeficiente_global_U", "factor_correccion_F",
        ):
            valor = getattr(op, campo, None)
            if valor is not None:
                entrada[campo] = _canonico(valor)

        # Las reacciones, en orden, con su estequiometria y su cinetica.
        reacciones = []
        for r in (getattr(op, "reacciones", None) or
                  ([op.reaccion] if getattr(op, "reaccion", None) else [])):
            reacciones.append({
                "nu": _canonico(list(r.nu)),
                "A": _canonico(r.A),
                "Ea": _canonico(r.Ea),
                "componente_referencia": r.componente_referencia,
            })
        if reacciones:
            entrada["reacciones"] = reacciones
        operaciones.append(entrada)

    # Las operaciones se ordenan por nombre: el orden en que el cliente
    # las mande no cambia el diagrama -- el solver es de punto fijo y los
    # recorre hasta que nada cambie -- asi que tampoco debe cambiar la
    # huella.
    operaciones.sort(key=lambda e: e["nombre"])

    especificaciones = [
        {
            "objetivo": e.objetivo, "valor": _canonico(e.valor),
            "manipulada": e.manipulada,
            "minimo": _canonico(e.minimo), "maximo": _canonico(e.maximo),
        }
        for e in (getattr(request, "especificaciones", None) or [])
    ]
    especificaciones.sort(key=lambda e: (e["objetivo"], e["manipulada"]))

    return {
        # El orden de los componentes SI importa: define que es x0.
        "componentes": list(getattr(request, "componentes", None) or []),
        "modelo": MODELO_TERMODINAMICO,
        "corrientes": sorted(getattr(request, "corrientes", None) or []),
        "operaciones": operaciones,
        "valores_si": _canonico(dict(getattr(request, "valores", None) or {})),
        "caudales_masicos_si": _canonico(
            dict(getattr(request, "caudales_masicos", None) or {})),
        "especificaciones": especificaciones,
    }


def huella(entradas):
    """
    SHA-256 de las entradas normalizadas, en hexadecimal.

    Se usa `json.dumps` con `sort_keys` y separadores sin espacios para
    que el texto sea unico para unas entradas dadas. El digest completo se
    devuelve entero: truncarlo a 12 caracteres queda mas bonito en un
    informe y multiplica por mucho la probabilidad de colision, y el
    cliente siempre puede acortarlo para MOSTRARLO.
    """
    texto = json.dumps(entradas, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def identificador_calculo(huella_entradas, instante):
    """
    Identificador de ESTA ejecucion.

    Mezcla la huella de las entradas con el instante, asi que dos
    ejecuciones de la misma peticion tienen identificadores distintos y la
    misma huella. Esa separacion es la util: la huella dice "mismas
    entradas" y el identificador dice "esta ejecucion concreta".
    """
    semilla = f"{huella_entradas}|{instante}"
    return hashlib.sha256(semilla.encode("utf-8")).hexdigest()[:32]


def construir_calculo(request):
    """
    El bloque `calculo` completo para la respuesta.

    Se calcula ANTES de resolver, a proposito: la fecha es la del inicio
    del calculo, y asi la huella de las entradas queda tomada sobre lo que
    de verdad se va a resolver y no sobre nada que el solver haya podido
    tocar por el camino.
    """
    entradas = entradas_normalizadas(request)
    huella_entradas = huella(entradas)
    instante = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return {
        "identificador": identificador_calculo(huella_entradas, instante),
        "instante_utc": instante,
        "motor": {
            "version": VERSION_MOTOR,
            "commit": _commit_git(),
        },
        "proveedor_termodinamico": {
            "identificador": MODELO_TERMODINAMICO,
            # La version del proveedor ES la de las librerias que calculan
            # las propiedades. Decir "v1" seria inventar un numero que no
            # cambia cuando los resultados si.
            "versiones": _versiones_dependencias(),
        },
        "huella_entradas": huella_entradas,
        "algoritmo_huella": "sha256",
    }


def canonico(valor):
    """
    El formato canonico, publico para quien tenga que normalizar sus
    propias entradas antes de pedir una huella.

    Lo usa el laboratorio, cuyas entradas son un grafo de piezas y no una
    peticion de diagrama: la normalizacion tiene que ser la MISMA en los
    dos sitios o las huellas no serian comparables entre servicios.
    """
    return _canonico(valor)


def construir_calculo_desde(entradas, modelo_termodinamico=None):
    """
    El bloque `calculo` para un servicio cuyas entradas ya vienen
    normalizadas por quien las conoce.

    `construir_calculo(request)` sabe normalizar una peticion de diagrama
    y no tiene por que saber de otras. Esta variante recibe el
    diccionario ya normalizado y aporta lo que es comun a todo el motor:
    la version, el commit, las versiones del proveedor y la huella.
    """
    huella_entradas = huella(entradas)
    instante = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return {
        "identificador": identificador_calculo(huella_entradas, instante),
        "instante_utc": instante,
        "motor": {
            "version": VERSION_MOTOR,
            "commit": _commit_git(),
        },
        "proveedor_termodinamico": {
            "identificador": modelo_termodinamico or MODELO_TERMODINAMICO,
            "versiones": _versiones_dependencias(),
        },
        "huella_entradas": huella_entradas,
        "algoritmo_huella": "sha256",
    }
