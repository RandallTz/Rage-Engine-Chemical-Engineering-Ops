"""
Compilador del modelo común: ecuaciones explícitas.

Segunda entrada del compilador, junto a la estructural (compilador.py). Ejecuta
las ecuaciones de `modelo.matematico` (el árbol tipado del documento v2) tal
como están escritas, sin saber qué equipo, operación o sustancia describen:

    d u_k / dt = f_k(t, u, parámetros)      una ecuación por variable de campo
    u_k(0)     = g_k(parámetros)            una condición inicial por variable

Valores: cada parámetro o constante del árbol toma su valor de
`datos["matematico.<id>"]`, en cualquier unidad compatible con la dimensión
del símbolo; el servicio único de unidades lo pasa a SI y comprueba esa
compatibilidad. El tiempo final es el dato `estudio.tiempoId`.

Dominio: `modelo.restricciones` (no_negativo) detiene la trayectoria en el
instante en que una variable lo abandonaría, localizado por bisección; nunca
se recorta ni se continúa con valores fuera de dominio.

Fuera de esta versión (NoSoportado con motivo): derivadas espaciales y
operadores diferenciales (corresponden al motor de discretización),
ecuaciones algebraicas (DAE), derivadas de orden mayor que uno y funciones
declaradas sin definición.
"""

import math

import numpy as np

from core import expresiones_motor as ex
from core import unidades as un
from core.modelo import leer_modelo_comun
from core.resultados import conjunto, eje, evento, serie
from core.solvers import integrar

from .compilador import NoSoportado

PREFIJO = "matematico."
_FUNCIONES = {"exp": math.exp, "log": math.log, "sin": math.sin, "cos": math.cos, "tan": math.tan, "tanh": math.tanh,
              "sinh": math.sinh, "cosh": math.cosh, "atan": math.atan, "erf": math.erf, "abs": abs}
_METODOS = {None: "RK45", "rk45": "RK45", "euler_implicito": "BDF", "bdf": "BDF"}
_NOMBRE_METODO = {"RK45": "RK45 adaptativo (Dormand-Prince 5/4, core/solvers)",
                  "BDF": "BDF implícito de orden variable (core/solvers)"}


def es_explicito(modelo):
    """Un modelo sin volúmenes con cierre de equilibrio y con ecuaciones escritas."""
    return modelo.get("matematico") is not None and all(v["termodinamica"]["tipo"] == "supuesto" for v in modelo["volumenes"])


def _dim_de_simbolo(s):
    d = s["dimension"]
    if d is None:
        raise NoSoportado(f"matematico: el símbolo {s['id']} no declara su dimensión")
    fuera = sorted(set(d) - set(un.BASES.values()))
    if fuera:
        raise NoSoportado(f"matematico: el símbolo {s['id']} usa dimensiones fuera de las bases SI ({', '.join(fuera)})")
    from fractions import Fraction
    return {k: Fraction(v["n"], v["d"]) for k, v in d.items() if v["n"]}


def _valor_SI(dato, ruta, dim):
    texto, unidad = dato["declaracion"]["texto"], dato["declaracion"]["unidad"]
    if not texto.strip():
        raise NoSoportado(f"{ruta}: dato pendiente")
    try:
        i = un.interpretar(unidad)
    except un.ErrorUnidad as e:
        raise NoSoportado(f"{ruta}: {e}") from e
    if i["dimension"] != dim:
        raise NoSoportado(f"{ruta}: la unidad {unidad!r} ({un.dimension_texto(i['dimension'])}) no corresponde a la dimensión del símbolo ({un.dimension_texto(dim)})")
    arbol = ex.analizar(texto, [])
    return i["factor"] * ex.evaluar(arbol, {}) + i["desplazamiento"]


class SistemaExplicito:
    def __init__(self, modelo):
        self.modelo = leer_modelo_comun(modelo)
        mat = self.modelo["matematico"]
        if mat is None:
            raise NoSoportado("el modelo no tiene ecuaciones explícitas (matematico)")
        if mat["funciones"]:
            raise NoSoportado("funciones declaradas sin definición: " + ", ".join(f["id"] for f in mat["funciones"]))
        sim = {s["id"]: s for s in mat["simbolos"]}
        tiempos = [s["id"] for s in mat["simbolos"] if s["rol"] == "tiempo"]
        if len(tiempos) != 1:
            raise NoSoportado("matematico: se necesita exactamente una variable de tiempo")
        self.tiempo = tiempos[0]
        if any(s["rol"] == "coordenada" for s in mat["simbolos"]):
            raise NoSoportado("campos con coordenadas espaciales: corresponden al motor de discretización (paso 5.2)")
        self.campos = [s["id"] for s in mat["simbolos"] if s["rol"] == "campo"]
        if not self.campos:
            raise NoSoportado("matematico: no hay variables de campo que integrar")
        self.indice = {c: k for k, c in enumerate(self.campos)}
        self.dims = {c: _dim_de_simbolo(sim[c]) for c in self.campos}
        dim_t = _dim_de_simbolo(sim[self.tiempo])
        # Parámetros y constantes, en SI, solo los que el árbol usa.
        usados = set()
        for e in mat["ecuaciones"]:
            _simbolos(e["izquierda"], usados)
            _simbolos(e["derecha"], usados)
        for c in mat["condiciones"]:
            _simbolos(c["ecuacion"]["izquierda"], usados)
            _simbolos(c["ecuacion"]["derecha"], usados)
        self.valores = {}
        for sid in sorted(usados):
            s = sim.get(sid)
            if s is None:
                raise NoSoportado(f"matematico: símbolo inexistente {sid!r}")
            if s["rol"] in ("parametro", "constante"):
                clave = PREFIJO + sid
                if clave not in self.modelo["datos"]:
                    raise NoSoportado(f"datos.{clave}: falta el valor del {s['rol']} {sid}")
                self.valores[sid] = _valor_SI(self.modelo["datos"][clave], f"datos.{clave}", _dim_de_simbolo(s))
        # Una ecuación diferencial de primer orden por variable de campo.
        self.f = [None] * len(self.campos)
        for e in mat["ecuaciones"]:
            lado, otro = (e["izquierda"], e["derecha"]) if e["izquierda"]["tipo"] == "derivada" else (e["derecha"], e["izquierda"])
            if lado["tipo"] != "derivada" or lado["expresion"]["tipo"] != "simbolo" or lado["respecto"] != self.tiempo:
                raise NoSoportado(f"ecuación {e['id']}: solo se ejecutan ecuaciones d(variable)/d{self.tiempo} = expresión (las algebraicas, DAE, quedan pendientes)")
            if lado["orden"] != 1:
                raise NoSoportado(f"ecuación {e['id']}: derivada de orden {lado['orden']}: escríbela como sistema de primer orden")
            u = lado["expresion"]["id"]
            if u not in self.indice:
                raise NoSoportado(f"ecuación {e['id']}: {u} no es una variable de campo")
            if self.f[self.indice[u]] is not None:
                raise NoSoportado(f"ecuación {e['id']}: {u} ya tiene su ecuación")
            self.f[self.indice[u]] = self._compilar(otro, f"ecuación {e['id']}")
        faltan = [c for c, f in zip(self.campos, self.f) if f is None]
        if faltan:
            raise NoSoportado("sin ecuación diferencial para: " + ", ".join(faltan))
        self.g = [None] * len(self.campos)
        for c in mat["condiciones"]:
            if c["tipo"] != "inicial":
                raise NoSoportado(f"condición {c['id']}: {c['tipo']} solo tiene sentido con coordenadas espaciales")
            iz, de = c["ecuacion"]["izquierda"], c["ecuacion"]["derecha"]
            if iz["tipo"] != "simbolo" or iz["id"] not in self.indice:
                raise NoSoportado(f"condición {c['id']}: se espera variable = expresión")
            if _usa_campos(de, self.indice) or _usa(de, self.tiempo):
                raise NoSoportado(f"condición {c['id']}: el valor inicial no puede depender de variables")
            self.g[self.indice[iz["id"]]] = self._compilar(de, f"condición {c['id']}")
        faltan = [c for c, g in zip(self.campos, self.g) if g is None]
        if faltan:
            raise NoSoportado("falta la condición inicial de " + ", ".join(faltan))
        self.restringidas = [self.indice[r["simboloId"]] for r in self.modelo.get("restricciones", [])]
        est = self.modelo["estudio"]
        if est is None or est["tipo"] != "temporal":
            raise NoSoportado("el modelo no pide un estudio temporal")
        if est.get("espacial") and any(self.modelo["volumenes"][k]["frontera"]["tipo"] == "malla_1d" for k in range(len(self.modelo["volumenes"]))):
            raise NoSoportado("volumen con malla 1D: corresponde al motor de discretización (paso 5.2)")
        dt = self.modelo["datos"][est["tiempoId"]]
        self.tf = _valor_SI(dt, f"datos.{est['tiempoId']}", dim_t)
        if not (self.tf > 0 and math.isfinite(self.tf)):
            raise NoSoportado(f"datos.{est['tiempoId']}: el tiempo final debe ser positivo y finito")
        if est["metodoSolicitado"] not in _METODOS:
            raise NoSoportado(f"estudio.metodoSolicitado: método no admitido ({est['metodoSolicitado']})")
        self.metodo = _METODOS[est["metodoSolicitado"]]
        self.unidades = {c: un.unidad_SI(self.dims[c]) for c in self.campos}
        self.unidad_t = un.unidad_SI(dim_t)

    # --- árbol -> función ---------------------------------------------------------------
    def _compilar(self, e, donde):
        t = e["tipo"]
        if t == "numero":
            v = float(e["valor"])
            return lambda tt, y: v
        if t == "simbolo":
            sid = e["id"]
            if sid == self.tiempo:
                return lambda tt, y: tt
            if sid in self.indice:
                k = self.indice[sid]
                return lambda tt, y: y[k]
            v = self.valores[sid]
            return lambda tt, y: v
        if t in ("suma", "producto"):
            fs = [self._compilar(a, donde) for a in e["argumentos"]]
            if t == "suma":
                return lambda tt, y: math.fsum(f(tt, y) for f in fs)
            def prod(tt, y):
                p = 1.0
                for f in fs:
                    p *= f(tt, y)
                return p
            return prod
        if t == "cociente":
            a, b = self._compilar(e["numerador"], donde), self._compilar(e["denominador"], donde)
            return lambda tt, y: a(tt, y) / b(tt, y)
        if t == "potencia":
            a, b = self._compilar(e["base"], donde), self._compilar(e["exponente"], donde)
            def pot(tt, y):
                r = a(tt, y) ** b(tt, y)
                if isinstance(r, complex):
                    raise ValueError("potencia fuera de dominio (base negativa con exponente no entero)")
                return r
            return pot
        if t == "funcion":
            fs = [self._compilar(a, donde) for a in e["argumentos"]]
            n = e["nombre"]
            if n in ("min", "max"):
                g = min if n == "min" else max
                return lambda tt, y: g(f(tt, y) for f in fs)
            h = _FUNCIONES[n]
            return lambda tt, y: h(fs[0](tt, y))
        if t == "llamada":
            raise NoSoportado(f"{donde}: función declarada {e['funcionId']} sin definición")
        if t == "derivada":
            raise NoSoportado(f"{donde}: derivada dentro del lado derecho (respecto de {e['respecto']}): pendiente del motor de discretización")
        raise NoSoportado(f"{donde}: operador {t}: corresponde al motor de discretización (paso 5.2)")

    # --- interfaz del integrador -----------------------------------------------------------
    def inicial(self):
        return np.array([g(0.0, None) for g in self.g], dtype=float)

    def rhs(self, t, y):
        return np.array([f(t, y) for f in self.f], dtype=float)

    def firma(self, t, y):
        return None

    def dominio(self, t, y):
        return np.array([y[k] for k in self.restringidas], dtype=float)

    def describir_dominio(self, k):
        return self.campos[self.restringidas[k]]


def resolver_explicito(modelo):
    sis = SistemaExplicito(modelo)
    m, est = sis.modelo, sis.modelo["estudio"]
    muestras = int(est["muestras"])
    y0 = sis.inicial()
    for k in sis.restringidas:
        if y0[k] < 0:
            raise NoSoportado(f"condición inicial de {sis.campos[k]}: fuera de su dominio (no negativo)")
    tray = integrar(sis, y0, sis.tf, rtol=est["rtol"], atol=est["atol"]["cantidad"], max_step=sis.tf / (muestras - 1), metodo=sis.metodo)
    t_fin = tray.t_fin
    ts = [x for x in np.linspace(0.0, sis.tf, muestras) if x <= t_fin * (1 + 1e-12)]
    ts = sorted(set(ts) | {t_fin})
    filas = [tray.y(t) for t in ts]
    series = [serie(f"campo.{c}", c, sis.unidades[c], ["t"], [float(y[k]) for y in filas], propietarioId=f"campo:{c}")
              for k, c in enumerate(sis.campos)]
    eventos = []
    for codigo, t, _a, _d, msg in tray.eventos:
        eventos.append(evento(codigo, "t", t, msg))
    return conjunto(m["id"], m["nombre"], "parcial" if tray.detenida else "resuelto",
                    {"motor": "rage.compilador.explicito", "metodo": _NOMBRE_METODO[sis.metodo], "firma": None,
                     "pasos": tray.pasos, "rechazos": tray.rechazos,
                     **({"mensaje": tray.detenida.mensaje} if tray.detenida else {})},
                    [eje("t", "tiempo", "tiempo", sis.unidad_t, ts)], series, eventos, [], modeloId=m["id"])


def _simbolos(e, acc):
    t = e["tipo"]
    if t == "simbolo":
        acc.add(e["id"])
    for k in ("argumentos",):
        for a in e.get(k, []):
            _simbolos(a, acc)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            _simbolos(e[k], acc)


def _usa(e, sid):
    acc = set()
    _simbolos(e, acc)
    return sid in acc


def _usa_campos(e, indice):
    acc = set()
    _simbolos(e, acc)
    return bool(acc & set(indice))
