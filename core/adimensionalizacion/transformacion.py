"""
A2 + A3: transformacion por escalas multiplicativas constantes y
resolucion de escalas libres mediante objetivos monomiales.

Flujo (el mismo para cualquier modelo; no hay ramas por simbolos, especies
ni numero de campos):

 1. Sustitucion v = S_v * v' de cada variable transformada (campos, tiempo,
    coordenadas). Las variables no transformadas se conservan.
 2. Regla de la cadena: d^n/dv^n = S_v^-n d^n/dv'^n; los operadores de una
    coordenada se escalan; los de varias coordenadas se desarrollan en
    componentes cartesianas (cada coordenada puede tener su escala).
 3. Linealidad: se extraen los factores constantes y se separa cada termino
    en coeficiente (parametros y escalas) y nucleo (lo que depende de las
    variables). Funciones declaradas y coeficientes variables quedan en el
    nucleo, sin desarrollar.
 4. Factor global: cada igualdad se divide por la magnitud del coeficiente
    de su lado izquierdo cuando este es un unico termino monomial. Esa
    division es una operacion distinta de elegir escalas y se registra
    aparte.
 5. Escalas dadas por expresion: se sustituyen.
 6. Objetivos: |coeficiente efectivo| = 1 (con signo exigido o conservado)
    es una ecuacion lineal en log(escalas); se resuelve de forma exacta con
    rango y dependencia. Resultado: escalas determinadas, relacionadas o
    libres (familia), objetivos satisfechos, dependientes, incompatibles o
    pendientes, con las elecciones responsables.
 7. Certificado: sustitucion inversa sobre lo PUBLICADO y comparacion de
    formas canonicas cartesianas con el original.
"""

import copy
from fractions import Fraction

from . import algebra as A
from .dimensional import cantidad_SI, dim_desde_json, dimension_de, interpretar_unidad, limpiar
from .racional import SistemaRacional, factorizar

ALCANCE_EQUIVALENCIA = (
    "Igualdad de formas canonicas tras la sustitucion inversa de lo publicado: "
    "suma y producto conmutativos y distributivos, a^p a^q = a^(p+q), "
    "(ab)^q = a^q b^q solo con q entero o factores positivos, derivadas "
    "cartesianas desarrolladas con las reglas del producto, de la potencia y de "
    "la cadena (exp, log, sin, cos, tan, sinh, cosh, tanh, atan, potencias), "
    "d^m(d^n f) = d^(m+n) f, log(exp y) = y y exp(log y) = y solo con y > 0 por "
    "los signos y dominios declarados. Las derivadas de funciones declaradas, "
    "erf, abs, min y max no se desarrollan; no se usan otras identidades de "
    "exp/log/trig/hiperbolicas ni el intercambio "
    "de derivadas mixtas. La nulidad de la diferencia se decide multiplicando por "
    "las sumas que aparecen como denominador (no nulas porque el original divide "
    "por ellas). Coordenadas cartesianas. Si las formas no coinciden el estado es "
    "'no_demostrada'; no se muestrean numeros.")


class Rechazo(Exception):
    def __init__(self, estado, diagnosticos):
        super().__init__(estado)
        self.estado = estado
        self.diagnosticos = diagnosticos


def _diag(ruta, codigo, mensaje, severidad="error", **extra):
    d = {"ruta": ruta, "codigo": codigo, "severidad": severidad, "mensaje": mensaje}
    d.update(extra)
    return d


def _sim(i):
    return {"tipo": "simbolo", "id": i}


def _pot(base, n):
    n = Fraction(n)
    if n == 1:
        return copy.deepcopy(base)
    return {"tipo": "potencia", "base": copy.deepcopy(base), "exponente": A.ast_numero(n)}


def _prod(*fs):
    return A._producto([copy.deepcopy(f) for f in fs])


def reescribir(e, simbolos, variables):
    """Sustitucion estructural de simbolos y regla de la cadena.

    simbolos: id -> AST que lo reemplaza.
    variables: id -> (nuevo_id, dphi_ast, lineal) para el cambio de una
    variable independiente v = phi(nuevo): d/dv = (1/phi'(nuevo)) d/dnuevo.
    Si phi' es constante (lineal) se usa la forma cerrada phi'^-n; si no, se
    anida el operador n veces y el desarrollo de la cadena lo hace el algebra.
    """
    t = e["tipo"]
    if t == "simbolo":
        return copy.deepcopy(simbolos.get(e["id"], e))
    if t == "derivada":
        interior = reescribir(e["expresion"], simbolos, variables)
        v, n = e["respecto"], e["orden"]
        if v in variables:
            nv, dphi, lineal = variables[v]
            if lineal:
                return _prod(_pot(dphi, -n), {"tipo": "derivada", "expresion": interior, "respecto": nv, "orden": n})
            x = interior
            for _ in range(n):
                x = {"tipo": "cociente", "numerador": {"tipo": "derivada", "expresion": x, "respecto": nv, "orden": 1},
                     "denominador": copy.deepcopy(dphi)}
            return x
        return {"tipo": "derivada", "expresion": interior, "respecto": v, "orden": n}
    if t in ("gradiente", "divergencia", "laplaciano"):
        coords = e["coordenadas"]
        if not any(x in variables for x in coords):
            return {"tipo": t, "expresion": reescribir(e["expresion"], simbolos, variables), "coordenadas": list(coords)}
        if len(coords) == 1 and variables[coords[0]][2]:
            nv, dphi, _ = variables[coords[0]]
            orden = 2 if t == "laplaciano" else 1
            return _prod(_pot(dphi, -orden), {"tipo": t, "expresion": reescribir(e["expresion"], simbolos, variables), "coordenadas": [nv]})
        return reescribir(A.cartesiano(e), simbolos, variables)
    return A.mapear_hijos(e, lambda h: reescribir(h, simbolos, variables))


def sumandos(e, ruta):
    """Sumandos aditivos explicitos con su ruta (mismo recorrido que el
    inventario del cliente: las sumas anidadas se aplanan)."""
    if e["tipo"] == "suma":
        r = []
        for j, a in enumerate(e["argumentos"]):
            r.extend(sumandos(a, f"{ruta}.argumentos[{j}]"))
        return r
    return [(e, ruta)]


class Preparado:
    """Transformacion A2 de un modelo con una eleccion de mapas v = g(v').

    Las escalas de la forma son el caso multiplicativo v = v_ref v'. Las
    transformaciones declaradas en la solicitud admiten mapas afines y no
    lineales; su inversa se DEMUESTRA componiendo g y h en forma canonica.
    Se calcula una vez y se reutiliza para cada conjunto de objetivos (A3)."""

    def __init__(self, modelo, forma, analisis, transformaciones=None):
        self.modelo = modelo
        self.forma = forma
        self.analisis = analisis
        self.transformaciones = transformaciones or []
        self.diagnosticos = []
        self.restricciones = []
        self.pasos = []
        # v2: f(z) = S fhat(z/s) declarada en funciones[].escala.
        self.funciones_escaladas = {}
        for i, f in enumerate(modelo["funciones"]):
            if "escala" in f:
                self.funciones_escaladas[f["id"]] = {"funcion": f, "ruta": f"funciones[{i}].escala", "escala": f["escala"]["simboloId"],
                                                     "fhat": f["escala"]["funcionAdimensional"], "args": [None] * len(f["entradas"])}
        self._preparar_mapas()
        self._preparar_prioridad()
        self._contextos()
        self._comprobar_mapas()
        self.referencias = {x["ecuacionId"]: x["terminoId"] for x in forma.get("referencias", [])}
        self._transformar()

    # --- mapas y constantes -------------------------------------------------
    def _preparar_mapas(self):
        modelo, forma, an = self.modelo, self.forma, self.analisis
        dims = an["dimensiones"]
        simbolos = {s["id"]: s for s in modelo["simbolos"]}
        self.simbolos_modelo = simbolos
        ocupados = set(simbolos) | {f["id"] for f in modelo["funciones"]} | {x["fhat"] for x in self.funciones_escaladas.values()}
        errores = []
        self.escalas = []  # constantes introducidas por los mapas (escalas y referencias)
        self.mapas = []
        declaradas = {t["variableId"] for t in self.transformaciones}

        def ocupar(nombre, cual, ruta):
            if nombre in ocupados:
                errores.append(_diag(ruta, "identidad_ocupada", f"la identidad '{nombre}' de la {cual} ya existe en el modelo o en otra transformacion"))
            ocupados.add(nombre)

        for j, e in enumerate(forma["escalas"]):
            ruta = f"forma.escalas[{j}]"
            if not e["transformar"]:
                continue
            v = e["simboloId"]
            if v in declaradas:
                self.diagnosticos.append(_diag(ruta, "escala_sustituida", f"la transformacion declarada de {v} sustituye a su escala de la forma", "aviso"))
                continue
            dim_v = dims.get(v)
            if dim_v is None:
                errores.append(_diag(ruta, "dimension_pendiente", f"la dimension de {v} no esta determinada; no se puede escalar"))
                continue
            if e["dimension"] is not None and dim_desde_json(e["dimension"]) != limpiar(dim_v):
                errores.append(_diag(ruta + ".dimension", "dimension_incompatible", f"la escala de {v} debe tener la dimension de {v}"))
                continue
            u = an["unidades"].get(v)
            if u and u["afin"]:
                errores.append(_diag(ruta, "temperatura_afin", f"{v} es una temperatura absoluta con desplazamiento; requiere una transformacion afin v = v_ref + dv v', no una escala multiplicativa"))
                continue
            sid, nuevo = f"{v}_ref", e["nuevoNombre"]
            ocupar(sid, "escala", ruta)
            ocupar(nuevo, "variable adimensional", ruta)
            info = {"variable": v, "id": sid, "nombre": f"{simbolos[v]['nombre']}_ref", "dimension": dim_v, "papel": "escala",
                    "rol": simbolos[v]["rol"], "ruta": ruta, "orden": (len(self.mapas), 0), "valor_decl": e["valor"]}
            self.escalas.append(info)
            self.mapas.append({"variable": v, "nuevo": nuevo, "rol": simbolos[v]["rol"], "ruta": ruta, "declarada": False,
                               "directa": _prod(_sim(sid), _sim(nuevo)),
                               "inversa": {"tipo": "cociente", "numerador": _sim(v), "denominador": _sim(sid)},
                               "dominio": {"original": None, "nuevo": None}, "constantes": [sid]})
        for i, t in enumerate(self.transformaciones):
            ruta = f"transformaciones[{i}]"
            v, nuevo = t["variableId"], t["nuevoId"]
            dim_v = dims.get(v)
            if dim_v is None:
                errores.append(_diag(ruta, "dimension_pendiente", f"la dimension de {v} no esta determinada"))
                continue
            ocupar(nuevo, "variable nueva", ruta)
            ids = []
            for k, c in enumerate(t["constantes"]):
                ocupar(c["id"], "constante", f"{ruta}.constantes[{k}]")
                ids.append(c["id"])
                self.escalas.append({"variable": v, "id": c["id"], "nombre": c["nombre"], "dimension": dim_desde_json(c["dimension"]),
                                     "papel": c["papel"], "rol": simbolos[v]["rol"], "ruta": f"{ruta}.constantes[{k}]",
                                     "orden": (len(self.mapas), k), "valor_decl": c["valor"]})
            self.mapas.append({"variable": v, "nuevo": nuevo, "rol": simbolos[v]["rol"], "ruta": ruta, "declarada": True,
                               "directa": t["directa"], "inversa": t["inversa"], "dominio": dict(t["dominio"]), "constantes": ids})
        if errores:
            raise Rechazo("rechazado", errores)
        self._dimensiones_de_constantes()
        for info in self.escalas:
            self._valor_constante(info, errores)
        if errores:
            raise Rechazo("rechazado", errores)
        self.por_variable = {m["variable"]: m for m in self.mapas}
        self.por_id = {e["id"]: e for e in self.escalas}

    def _preparar_prioridad(self):
        """v2: `prioridadEscalas` lista variables (sus escalas) o constantes de
        mapas; las listadas se despejan primero, en ese orden, y las demas
        siguen el orden publicado por defecto (tiempo, campos, coordenadas)."""
        self.rango_prioridad = {}
        errores = []
        for j, x in enumerate(self.forma.get("prioridadEscalas", [])):
            if x in self.por_id:
                ids = [x]
            elif x in self.por_variable:
                ids = [c for c in self.por_variable[x]["constantes"] if self.por_id[c]["papel"] == "escala"]
            else:
                errores.append(_diag(f"forma.prioridadEscalas[{j}]", "prioridad_desconocida",
                                     f"'{x}' no es una variable transformada ni una constante de un mapa"))
                continue
            for sid in ids:
                self.rango_prioridad.setdefault(sid, len(self.rango_prioridad))
        if errores:
            raise Rechazo("rechazado", errores)

    def _dimensiones_de_constantes(self):
        """Infiere las dimensiones de las constantes de cada mapa declarado:
        g(v') tiene la dimension de v y h(v) es adimensional."""
        from .dimensional import Analizador
        errores = []
        base = dict(self.analisis["dimensiones"])
        fdim = self.analisis["funciones_dim"]
        funciones = {fid: {"entradas": v["entradas_finales"], "salida": v["salida_final"]} for fid, v in fdim.items()}
        for m in self.mapas:
            if not m["declarada"]:
                continue
            simbolos = {k: {"dimension": d, "rol": None} for k, d in base.items()}
            simbolos[m["nuevo"]] = {"dimension": {}, "rol": None}
            propias = [e for e in self.escalas if e["id"] in m["constantes"]]
            for e in propias:
                simbolos[e["id"]] = {"dimension": e["dimension"], "rol": "parametro"}
            an = Analizador(simbolos, funciones)
            dg, _ = an.expresion(m["directa"], m["ruta"] + ".directa")
            an.igual(dg, an._simbolo(m["variable"]), m["ruta"] + ".directa", f"g({m['nuevo']}) debe tener la dimension de {m['variable']}")
            dh, _ = an.expresion(m["inversa"], m["ruta"] + ".inversa")
            an.adimensional(dh, m["ruta"] + ".inversa", f"la inversa debe dar {m['nuevo']} adimensional")
            for d in an.diagnosticos:
                if d["severidad"] == "error":
                    errores.append(d)
            for e in propias:
                if e["dimension"] is None:
                    v = an.valor("s:" + e["id"])
                    if v is None:
                        errores.append(_diag(e["ruta"], "dimension_indeterminada", f"el mapa no determina la dimension de {e['id']}; declarela"))
                    e["dimension"] = v
        if errores:
            raise Rechazo("rechazado", errores)

    def _valor_constante(self, info, errores):
        valor = info["valor_decl"]
        info["tipo"] = valor["tipo"]
        ruta = info["ruta"] + ".valor"
        if valor["tipo"] == "cantidad":
            uv = interpretar_unidad(valor["unidad"])
            if uv is None:
                errores.append(_diag(ruta + ".unidad", "unidad_no_reconocida", f"unidad '{valor['unidad']}' no reconocida"))
                return
            if uv["afin"] and info["papel"] != "referencia":
                errores.append(_diag(ruta + ".unidad", "temperatura_afin", "una temperatura con desplazamiento solo puede ser una referencia, no una escala multiplicativa"))
                return
            if not set(info["dimension"]) <= {"L", "M", "T", "I", "Theta", "N", "J"}:
                errores.append(_diag(ruta + ".unidad", "unidad_no_comparable", "una constante con unidad requiere bases L, M, T, I, Theta, N, J"))
                return
            if uv["dimension"] != limpiar(info["dimension"]):
                errores.append(_diag(ruta + ".unidad", "dimension_incompatible", f"la unidad '{valor['unidad']}' no tiene la dimension de {info['id']}"))
                return
            mag, uni = cantidad_SI(valor["valor"], valor["unidad"])
            info["cantidad"] = {"valor": valor["valor"], "unidad": valor["unidad"], "valorSI": mag, "unidadSI": uni}
        elif valor["tipo"] == "expresion":
            info["expresion"] = valor["expresion"]

    def _contextos(self):
        modelo = self.modelo
        mapa_var = {m["variable"]: m["nuevo"] for m in self.mapas if m["rol"] in A.INDEPENDIENTES}
        orig, trans = {}, {}
        dominio_original = {m["variable"]: m["dominio"]["original"] for m in self.mapas if m["dominio"]["original"]}
        for s in modelo["simbolos"]:
            signo = dominio_original.get(s["id"], s["signo"])
            orig[s["id"]] = {"rol": s["rol"], "constante": s["constante"], "dependeDe": set(s["dependeDe"]), "signo": signo}
            trans[s["id"]] = {"rol": s["rol"], "constante": s["constante"], "dependeDe": {mapa_var.get(d, d) for d in s["dependeDe"]}, "signo": signo}
        for esc in self.escalas:
            info = {"rol": "escala", "constante": True, "dependeDe": set(),
                    "signo": "positivo" if esc["papel"] == "escala" else "desconocido"}
            orig[esc["id"]] = info
            trans[esc["id"]] = info
        for m in self.mapas:
            s = self.simbolos_modelo[m["variable"]]
            signo = m["dominio"]["nuevo"] or (orig[m["variable"]]["signo"] if not m["declarada"] else "desconocido")
            trans[m["nuevo"]] = {"rol": s["rol"], "constante": False,
                                 "dependeDe": {mapa_var.get(d, d) for d in s["dependeDe"]}, "signo": signo}
        fo = {f["id"]: {"dependeDe": set(f["dependeDe"])} for f in modelo["funciones"]}
        ft = {f["id"]: {"dependeDe": {mapa_var.get(d, d) for d in f["dependeDe"]}} for f in modelo["funciones"]}
        self.ctx_o = A.Contexto(orig, fo)
        self.ctx_t = A.Contexto(trans, ft)
        self.mapa_var = mapa_var
        self.directa_A = {m["variable"]: m["directa"] for m in self.mapas}
        dims = dict(self.analisis["dimensiones"])
        for e in self.escalas:
            dims[e["id"]] = e["dimension"]
        for m in self.mapas:
            dims[m["nuevo"]] = {}
        self.dims_t = dims
        fdim = self.analisis["funciones_dim"]
        self.funciones_dim = {fid: {"entradas": v["entradas_finales"], "salida": v["salida_final"]} for fid, v in fdim.items()}
        for ctx in (self.ctx_o, self.ctx_t):
            ctx.dimensiones = dims
            ctx.funciones_dim = self.funciones_dim
        for fid, info in self.funciones_escaladas.items():
            # fhat es adimensional; sus entradas pasan a {} donde se extrae la escala.
            ft[info["fhat"]] = {"dependeDe": set(ft[fid]["dependeDe"])}
            self.funciones_dim[info["fhat"]] = {"entradas": list(self.funciones_dim[fid]["entradas"]), "salida": {}}
            if self.analisis["dimensiones"].get(info["escala"]) is None or self.funciones_dim[fid]["salida"] is None:
                raise Rechazo("rechazado", [_diag(info["ruta"], "dimension_pendiente", f"no se determina la dimension de {info['escala']}, escala de {fid}")])
            if self.ctx_o.signo(info["escala"]) == "desconocido":
                self._restriccion("no_nulo", _sim(info["escala"]), f"escala declarada de la funcion {fid}: {fid} = {info['escala']} {info['fhat']}")
        # Constantes dadas por expresion: constantes, con su dimension y, si
        # son escalas, positivas (o un supuesto publicado).
        errores = []
        self.mapa_expr = {}
        for e in self.escalas:
            if e["tipo"] != "expresion":
                continue
            x = e["expresion"]
            P = A.canonica(x, self.ctx_o)
            if not A.poli_constante_total(P, self.ctx_o):
                errores.append(_diag(e["ruta"] + ".valor.expresion", "escala_no_constante", "una escala o referencia debe ser constante (sin variables ni coeficientes variables)"))
                continue
            if P.es_cero and e["papel"] == "escala":
                errores.append(_diag(e["ruta"] + ".valor.expresion", "escala_singular", "la escala es nula: la transformacion no es invertible"))
                continue
            d = dimension_de(x, self.analisis["dimensiones"], self.funciones_dim)
            if not P.es_cero and (d is None or limpiar(d) != limpiar(e["dimension"])):
                errores.append(_diag(e["ruta"] + ".valor.expresion", "dimension_incompatible", f"la expresion no tiene la dimension de {e['id']}"))
                continue
            if e["papel"] == "escala":
                signo = _signo_poli(P, self.ctx_o)
                if signo == -1:
                    errores.append(_diag(e["ruta"] + ".valor.expresion", "escala_negativa", "la escala es negativa con los signos declarados; use |.| o cambie el signo"))
                    continue
                if signo is None:
                    self._restriccion("positivo", x, f"escala de {e['variable']} dada por expresion de signo no determinado: se supone positiva")
            self.mapa_expr[e["id"]] = x
        if errores:
            raise Rechazo("rechazado", errores)

    def _comprobar_mapas(self):
        """Familia, invertibilidad demostrada y regla de la cadena de cada mapa."""
        errores = []
        constantes_modelo = {s["id"] for s in self.modelo["simbolos"] if self.ctx_o.constante_total(s["id"])}
        for m in self.mapas:
            v, w, ruta = m["variable"], m["nuevo"], m["ruta"]
            propias = set(m["constantes"])
            sd, si = _simbolos_en(m["directa"]), _simbolos_en(m["inversa"])
            if w not in sd or not sd <= {w} | propias | constantes_modelo:
                errores.append(_diag(ruta + ".directa", "mapa_mal_formado", f"g debe depender de {w} y solo de constantes"))
                continue
            if v not in si or not si <= {v} | propias | constantes_modelo:
                errores.append(_diag(ruta + ".inversa", "mapa_mal_formado", f"h debe depender de {v} y solo de constantes"))
                continue
            try:
                ida = A.canonica(A.sustituir(m["inversa"], {v: m["directa"]}), self.ctx_t, "expandir")
                vuelta = A.canonica(A.sustituir(m["directa"], {w: m["inversa"]}), self.ctx_o, "expandir")
                ok = A.iguales(ida, A.canonica(_sim(w), self.ctx_t)) and A.iguales(vuelta, A.canonica(_sim(v), self.ctx_o))
                dphi = A.derivar_ast(m["directa"], w, self.ctx_t)
            except (A.ErrorAlgebraico, A.NoSoportado) as ex:
                errores.append(_diag(ruta, "inversa_no_demostrada", f"no se pudo componer el mapa: {ex.mensaje}"))
                continue
            if not ok:
                errores.append(_diag(ruta, "inversa_no_demostrada",
                                     f"h(g({w})) = {w} y g(h({v})) = {v} no se demuestran con los dominios declarados; el cambio no se acepta como invertible"))
                continue
            lineal = w not in _simbolos_en(dphi)
            if lineal:
                cero = A.canonica(A.sustituir(m["directa"], {w: {"tipo": "numero", "valor": 0}}), self.ctx_t)
                m["familia"] = "multiplicativa" if cero.es_cero else "afin"
            else:
                m["familia"] = "no_lineal"
            u = self.analisis["unidades"].get(v)
            if u and u["afin"] and m["familia"] == "multiplicativa":
                errores.append(_diag(ruta, "temperatura_afin", f"{v} tiene una unidad con desplazamiento; requiere un mapa afin con referencia"))
                continue
            m["dphi"], m["lineal"] = dphi, lineal
            for lado, x in (("original", v), ("nuevo", w)):
                signo = m["dominio"][lado]
                if signo:
                    self._restriccion("positivo" if signo == "positivo" else "negativo", _sim(x), f"dominio del cambio de variable de {v}")
            if m["rol"] in A.INDEPENDIENTES and not lineal:
                self._restriccion("no_nulo", dphi, f"jacobiano del cambio de {v}: el mapa debe ser monotono en el dominio")
        if errores:
            raise Rechazo("rechazado", errores)
        self.directa_B = {m["variable"]: (m["nuevo"], m["dphi"], m["lineal"]) for m in self.mapas if m["rol"] in A.INDEPENDIENTES}
        self.modo_t = "expandir" if any(m["familia"] == "no_lineal" for m in self.mapas) else "conservar"

    def _restriccion(self, tipo, expresion, motivo, **extra):
        for r in self.restricciones:
            if r["tipo"] == tipo and r["expresion"] == expresion and r.get("signo") == extra.get("signo"):
                return r["id"]
        rid = f"R{len(self.restricciones) + 1}"
        r = {"id": rid, "tipo": tipo, "expresion": copy.deepcopy(expresion), "motivo": motivo}
        r.update(extra)
        self.restricciones.append(r)
        return rid

    # --- transformacion ------------------------------------------------------
    def _transformar_igualdad(self, eq, ruta, prefijo, ambito):
        """Transforma una igualdad termino a termino; devuelve su registro."""
        registro = {"ambito": ambito, "id": eq["id"], "original": eq, "lados": {}}
        for lado in ("izquierda", "derecha"):
            terminos = []
            for s, r in sumandos(eq[lado], f"{ruta}.{lado}"):
                P = A.canonica(s, self.ctx_o)
                partes = A.separar_terminos(P, self.ctx_o)
                for k, (nucleo, coef) in enumerate(partes):
                    tid = f"{prefijo}:{r}" if len(partes) == 1 else f"{prefijo}:{r}#{k + 1}"
                    original = A.multiplicar(coef, A.Poli({nucleo: Fraction(1)}))
                    ast_o = A.ast(original)
                    T = self.escalar_llamadas(reescribir(reescribir(ast_o, self.directa_A, {}), {}, self.directa_B), tid)
                    Pt = A.canonica(T, self.ctx_t, self.modo_t)
                    trans = A.separar_terminos(Pt, self.ctx_t)
                    terminos.append({"id": tid, "ruta": r, "lado": lado, "original": ast_o, "poli_original": original,
                                     "nucleo_original": nucleo, "partes": trans, "dividido_en": len(partes)})
            registro["lados"][lado] = terminos
        # Factor global: magnitud del coeficiente del unico termino izquierdo,
        # o (v2) del termino de referencia declarado en la forma.
        izq = registro["lados"]["izquierda"]
        F, motivo_F = A.UNO, None
        ref = self.referencias.get(prefijo)
        registro["referencia"] = ref
        if ref is not None:
            todos = {t["id"]: t for ts in registro["lados"].values() for t in ts}
            if ref not in todos:
                partes = [x for x in todos if x.startswith(ref + "#")]
                raise Rechazo("rechazado", [_diag("forma.referencias", "referencia_no_encontrada",
                                                  f"el termino '{ref}' no existe en {ambito} '{eq['id']}'"
                                                  + (f"; se desarrolla en {', '.join(partes)}" if partes else ""))])
            if len(todos[ref]["partes"]) != 1 or todos[ref]["partes"][0][1].monomio_unico() is None:
                raise Rechazo("rechazado", [_diag("forma.referencias", "referencia_no_monomial",
                                                  f"el coeficiente de '{ref}' tras transformar no es un unico monomio; no sirve como factor global")])
            izq = [todos[ref]]
        if len(izq) == 1 and len(izq[0]["partes"]) == 1:
            u = izq[0]["partes"][0][1].monomio_unico()
            if u is None:
                motivo_F = "el coeficiente del lado izquierdo no es monomial"
            else:
                c, m = u
                nulos = [a[1] for a, _ in m if a[0] == "s" and self.ctx_t.signo(a[1]) == "cero"]
                if nulos:
                    motivo_F = f"el factor del lado izquierdo contiene {', '.join(nulos)} declarado nulo"
                else:
                    F = A.monomio(abs(c), dict(m))
                    for a, _ in m:
                        if a[0] == "s" and self.ctx_t.signo(a[1]) == "desconocido":
                            self._restriccion("no_nulo", _sim(a[1]), f"se divide {ambito} '{eq['id']}' por su factor global")
        else:
            motivo_F = "el lado izquierdo no es un unico termino"
        if motivo_F and ref is not None:
            # Una referencia pedida que no se puede usar no se relaja en silencio.
            raise Rechazo("rechazado", [_diag("forma.referencias", "referencia_nula",
                                              f"no se puede dividir {ambito} '{eq['id']}' por el coeficiente de '{ref}': {motivo_F.replace('del lado izquierdo', 'de la referencia')}")])
        if motivo_F:
            self.diagnosticos.append(_diag(ruta, "sin_factor_global", f"{ambito} '{eq['id']}' no se divide por un factor global: {motivo_F}", "aviso"))
        registro["F"] = F
        Finv = A.potencia(F, -1, self.ctx_t)
        for terminos in registro["lados"].values():
            for t in terminos:
                t["partes_F"] = []
                for n, c in t["partes"]:
                    P = self._final(A.multiplicar(c, Finv, A.Poli({n: Fraction(1)})), self.mapa_expr)
                    t["partes_F"].extend(A.separar_terminos(P, self.ctx_t))
        registro["F_expr"] = self._final(F, self.mapa_expr)
        # Pasos a nivel de la igualdad completa (presentacion).
        pA = {lado: reescribir(eq[lado], self.directa_A, {}) for lado in ("izquierda", "derecha")}
        pB = {lado: reescribir(pA[lado], {}, self.directa_B) for lado in ("izquierda", "derecha")}
        pC = {lado: self.escalar_llamadas(pB[lado], eq["id"]) for lado in ("izquierda", "derecha")}
        registro["pasos"] = [
            ("sustitucion_de_variables", _igualdad(eq), _igualdad_de(pA), self._supuestos_sustitucion()),
            ("regla_de_la_cadena", _igualdad_de(pA), _igualdad_de(pB), ["escalas constantes", "coordenadas cartesianas"]),
        ]
        if pC != pB:
            registro["pasos"].append(("escala_declarada_de_funciones", _igualdad_de(pB), _igualdad_de(pC), self.supuestos_funciones()))
        registro["pasos"].append(("linealidad_y_agrupacion", _igualdad_de(pC), self._igualdad_partes(registro, "partes"),
                                  ["linealidad de derivadas y operadores", "funciones declaradas sin desarrollar"]))
        if not motivo_F:
            origen_F = f" (coeficiente del termino de referencia {ref})" if ref else ""
            registro["pasos"].append(("division_por_factor_global", self._igualdad_partes(registro, "partes"),
                                      self._igualdad_partes(registro, "partes_F_sin_expr", Finv=Finv),
                                      [f"factor global {_texto_poli(F)} distinto de cero{origen_F}"]))
        if self.mapa_expr:
            registro["pasos"].append(("sustitucion_de_escalas_dadas", self._igualdad_partes(registro, "partes_F_sin_expr", Finv=Finv),
                                      self._igualdad_partes(registro, "partes_F"), ["escalas dadas por expresion"]))
        return registro

    def _supuestos_sustitucion(self):
        from .exportar_texto import texto
        return [f"{m['variable']} = {texto(m['directa'])}" for m in self.mapas] + [
            f"{e['id']} > 0" for e in self.escalas if e["papel"] == "escala"]

    def _final(self, P, mapa):
        if not mapa:
            return P
        return A.canonica(A.sustituir(A.ast(P), mapa), self.ctx_t, self.modo_t)

    # --- escala declarada de funciones (v2) ---------------------------------
    def _separar_escala(self, P):
        """Argumento transformado P = s w, con s el producto de las escalas de
        los mapas y w adimensional. Si no es un unico monomio o w conserva
        dimension, la escala no se extrae (s = 1, w = P)."""
        u = P.monomio_unico()
        if u is None:
            return A.UNO, P
        c, m = u
        escalas = {a: e for a, e in m if a[0] == "s" and a[1] in self.por_id and self.por_id[a[1]]["papel"] == "escala"}
        resto = {a: e for a, e in m if a not in escalas}
        w = A.monomio(c, resto)
        d = dimension_de(A.ast(w), self.dims_t, self.funciones_dim)
        if not escalas or d is None or limpiar(d):
            return A.UNO, P
        return A.monomio(1, escalas), w

    def escalar_llamadas(self, e, ambito):
        """f(z) -> S fhat(w) con z = s w (definicion: fhat(w) = f(s w) / S).
        Cada entrada de f debe recibir la misma escala s en todas sus llamadas;
        si no, fhat no estaria bien definida y se rechaza."""
        if not self.funciones_escaladas:
            return e
        e = A.mapear_hijos(e, lambda h: self.escalar_llamadas(h, ambito))
        if e["tipo"] != "llamada" or e["funcionId"] not in self.funciones_escaladas:
            return e
        info = self.funciones_escaladas[e["funcionId"]]
        args = []
        for i, a in enumerate(e["argumentos"]):
            s, w = self._separar_escala(A.canonica(a, self.ctx_t, self.modo_t))
            previo = info["args"][i]
            if previo is None:
                info["args"][i] = s
                if not s.es_cero and s != A.UNO:
                    self.funciones_dim[info["fhat"]]["entradas"][i] = {}
            elif previo != s:
                raise Rechazo("rechazado", [_diag(info["ruta"], "escala_funcion_inconsistente",
                                                  f"la entrada {i + 1} de {e['funcionId']} recibe escalas distintas en '{ambito}' ({_texto_poli(previo)} y {_texto_poli(s)}); {info['fhat']} no quedaria bien definida")])
            args.append(A.ast(w))
        return _prod(_sim(info["escala"]), {"tipo": "llamada", "funcionId": info["fhat"], "argumentos": args})

    def supuestos_funciones(self, valores=None):
        from .exportar_texto import texto
        r = []
        for fid, info in self.funciones_escaladas.items():
            if any(x is not None for x in info["args"]):
                n = len(info["args"])
                ws = ", ".join(f"w{i + 1}" for i in range(n))
                zs = ", ".join(f"{texto(self.escala_argumento(info, i, valores))} w{i + 1}" for i in range(n))
                r.append(f"{info['fhat']}({ws}) = {fid}({zs}) / {info['escala']}")
        return r

    def escala_argumento(self, info, i, valores=None):
        s = info["args"][i] if info["args"][i] is not None else A.UNO
        x = A.ast(s)
        return A.ast(A.canonica(A.sustituir(x, valores), self.ctx_t)) if valores else x

    def deshacer_llamadas(self, e, valores):
        """Inversa de escalar_llamadas para el certificado: fhat(w) -> f(s w)/S,
        con las escalas ya resueltas (`valores`)."""
        if not self.funciones_escaladas:
            return e
        e = A.mapear_hijos(e, lambda h: self.deshacer_llamadas(h, valores))
        if e["tipo"] != "llamada":
            return e
        info = next((x for x in self.funciones_escaladas.values() if x["fhat"] == e["funcionId"]), None)
        if info is None:
            return e
        args = [_prod(self.escala_argumento(info, i, valores), w) for i, w in enumerate(e["argumentos"])]
        return {"tipo": "cociente", "numerador": {"tipo": "llamada", "funcionId": info["funcion"]["id"], "argumentos": args},
                "denominador": _sim(info["escala"])}

    def _igualdad_partes(self, registro, clave, Finv=None, presentacion="desarrollada"):
        lados = {}
        for lado, terminos in registro["lados"].items():
            items = []
            for t in terminos:
                if clave == "partes_F_sin_expr":
                    partes = [(n, A.multiplicar(c, Finv)) for n, c in t["partes"]]
                else:
                    partes = t[clave]
                items.extend(partes)
            lados[lado] = presentar_lado(items, presentacion)
        return {"izquierda": lados["izquierda"], "derecha": lados["derecha"]}

    def _transformar(self):
        m = self.modelo
        self.ecuaciones = [self._transformar_igualdad(eq, f"ecuaciones[{i}]", eq["id"], "ecuacion") for i, eq in enumerate(m["ecuaciones"])]
        self.condiciones = [self._transformar_igualdad(c["ecuacion"], f"condiciones[{i}].ecuacion", c["id"], "condicion") for i, c in enumerate(m["condiciones"])]
        self.terminos = {}
        for reg in self.ecuaciones:
            for terminos in reg["lados"].values():
                for t in terminos:
                    t["ecuacionId"] = reg["id"]
                    self.terminos[t["id"]] = t
        self.dominios = []
        for d in m["dominios"]:
            v = d["variableId"]
            mapa = self.por_variable.get(v)
            nuevo = {}
            for lado in ("desde", "hasta"):
                x = reescribir(d[lado], self.directa_A, {})
                if mapa:
                    x = A.sustituir(mapa["inversa"], {v: x})
                nuevo[lado] = self._final(A.canonica(x, self.ctx_t, self.modo_t), self.mapa_expr)
            self.dominios.append({"original": d, "variable": mapa["nuevo"] if mapa else v, "mapa": mapa, "poli": nuevo})
        # Variables presentes que no se transforman (normalizacion parcial).
        presentes = set()
        for eq in m["ecuaciones"]:
            presentes |= _simbolos_en(eq["izquierda"]) | _simbolos_en(eq["derecha"])
        for c in m["condiciones"]:
            presentes |= _simbolos_en(c["ecuacion"]["izquierda"]) | _simbolos_en(c["ecuacion"]["derecha"])
        for eq in m["ecuaciones"]:
            presentes |= _variables_derivadas(eq["izquierda"]) | _variables_derivadas(eq["derecha"])
        self.sin_transformar = sorted(v for v in presentes if self.simbolos_modelo[v]["rol"] in ("campo", "tiempo", "coordenada") and v not in self.por_variable)

    # --- objetivos (A3) ------------------------------------------------------
    def buscar_termino(self, ecuacion_id, termino_ast):
        """Termino del contrato v1 (expresion) -> id; ignora el factor numerico."""
        P = A.canonica(termino_ast, self.ctx_o)
        u = P.monomio_unico()
        if u is None:
            return None, "la expresion del objetivo no es un unico termino monomial"
        candidatos = []
        for t in self.terminos.values():
            if t["ecuacionId"] != ecuacion_id:
                continue
            ut = t["poli_original"].monomio_unico()
            if ut and ut[1] == u[1]:
                candidatos.append(t["id"])
        if not candidatos:
            return None, "el termino no aparece en la ecuacion"
        if len(candidatos) > 1:
            return None, f"el termino es ambiguo: coincide con {', '.join(candidatos)}"
        return candidatos[0], None

    def prioridad(self, sid):
        if sid in self.rango_prioridad:
            return (0, self.rango_prioridad[sid], (0, 0))
        e = self.por_id[sid]
        return (1, {"tiempo": 0, "campo": 1, "coordenada": 2}[e["rol"]], e["orden"])

    def resolver(self, objetivos):
        """objetivos: [{id, terminoId|None, motivo_no_encontrado, modo: 'valor'|'magnitud'|'conservar', valor}]"""
        libres = {e["id"] for e in self.escalas if e["tipo"] == "libre"}
        sistema = SistemaRacional(prioridad=self.prioridad)
        estados = []
        signos_usados = set()
        for o in objetivos:
            est = {"id": o["id"], "terminoId": o.get("terminoId")}
            estados.append(est)
            if o["modo"] == "conservar":
                est.update(estado="conservado", motivo="se conserva como grupo; no impone restriccion")
                continue
            t = self.terminos.get(o.get("terminoId"))
            if t is None:
                est.update(estado="pendiente", codigo=o.get("codigo") or "termino_no_encontrado", motivo=o.get("motivo") or "termino no encontrado")
                continue
            if len(t["partes_F"]) != 1:
                est.update(estado="pendiente", codigo="no_monomial", motivo="el termino se desarrolla en varios terminos; el coeficiente efectivo no es unico")
                continue
            nucleo, coef = t["partes_F"][0]
            u = coef.monomio_unico()
            if u is None:
                est.update(estado="pendiente", codigo="no_monomial", motivo="coeficiente efectivo no monomial: fuera del alcance de A3")
                continue
            c, m = u
            fila, rhs, problema = {}, {}, None
            usados = set()
            dc = dimension_de(A.ast(coef), self.dims_t, self.funciones_dim)
            if dc is None or limpiar(dc):
                est.update(estado="pendiente", codigo="coeficiente_dimensional",
                           motivo="el coeficiente efectivo conserva dimensiones (su nucleo es dimensional): igualarlo a 1 no es una normalizacion valida")
                continue
            for a, e in m:
                if a[0] == "s" and a[1] in libres:
                    fila[a[1]] = e
                    continue
                if a[0] == "s" and self.ctx_t.signo(a[1]) == "cero":
                    problema = ("incompatible", "parametro_nulo", f"{a[1]} esta declarado nulo: el termino se anula y su coeficiente no puede normalizarse")
                    break
                if not (A.atomo_positivo(a, self.ctx_t) and A.atomo_constante_total(a, self.ctx_t)):
                    nombre = a[1] if a[0] == "s" else A.clave_atomo(a)
                    problema = ("pendiente", "signo_desconocido", f"signo de {nombre} no declarado: la normalizacion exige conocerlo (declare el signo o mantenga el objetivo pendiente)")
                    break
                rhs[a] = rhs.get(a, 0) - e
                if a[0] == "f" and a[1] == "abs":
                    usados.add(_texto_poli(a[2][0]))
                elif a[0] == "s" and self.ctx_t.signo(a[1]) == "positivo" and a[1] not in self.por_id:
                    usados.add(a[1])
            if problema is None:
                if o["modo"] == "valor" and (1 if c > 0 else -1) != o["valor"]:
                    problema = ("incompatible", "signo", f"el coeficiente efectivo tiene signo {'+' if c > 0 else '-'} con escalas positivas; no puede valer {o['valor']:+d} (pida {'+1' if c > 0 else '-1'} o conserve el signo)")
            if problema is None:
                f = factorizar(abs(c).numerator)
                g = factorizar(abs(c).denominator)
                if f is None or g is None:
                    problema = ("pendiente", "numero_grande", "coeficiente numerico con factores primos grandes")
                else:
                    for p, k in f.items():
                        rhs[("n", p)] = rhs.get(("n", p), 0) - k
                    for p, k in g.items():
                        rhs[("n", p)] = rhs.get(("n", p), 0) + k
            if problema:
                est.update(estado=problema[0], codigo=problema[1], motivo=problema[2])
                continue
            signos_usados |= usados
            estado, origen, residuo = sistema.agregar(fila, rhs, o["id"])
            objetivo_signo = 1 if c > 0 else -1
            est["valorObjetivo"] = objetivo_signo if o["modo"] == "magnitud" else o["valor"]
            if estado == "independiente":
                est.update(estado="satisfecho", motivo="determina o relaciona escalas")
            elif estado == "dependiente":
                est.update(estado="dependiente", motivo="consecuencia de otros objetivos o del factor global", responsables=sorted(k for k in origen if k != o["id"]))
            else:
                rel = A.monomio(1, {a: -e for a, e in residuo.items()})
                est.update(estado="incompatible", codigo="sobredeterminado",
                           motivo="exigiria una relacion entre datos que no impone el modelo" if residuo else "incompatible",
                           responsables=sorted(origen), relacion={"izquierda": A.ast(rel), "derecha": {"tipo": "numero", "valor": 1}})
        # Solucion: pivotes en funcion de datos y escalas libres restantes.
        piv = sistema.pivotes()
        solucion, situacion = {}, {}
        for e in self.escalas:
            sid = e["id"]
            if e["tipo"] == "cantidad":
                situacion[sid] = "dada"
            elif e["tipo"] == "expresion":
                situacion[sid] = "dada_por_expresion"
            elif sid in piv:
                fila = piv[sid]
                exps = {a: x for a, x in fila["rhs"].items()}
                for col, x in fila["coef"].items():
                    if col != sid:
                        exps[("s", col)] = exps.get(("s", col), 0) - x
                solucion[sid] = A.monomio(1, exps)
                situacion[sid] = "relacionada" if len(fila["coef"]) > 1 else "determinada"
            else:
                situacion[sid] = "libre"
        filas = [{"piv": f["piv"], "coef": dict(f["coef"]), "rhs": dict(f["rhs"])} for f in sistema.filas]
        return estados, solucion, situacion, signos_usados, sistema.rango, filas


def _signo_poli(P, ctx):
    if P.es_cero:
        return 0
    signos = {A.signo_monomio(c, m, ctx) for m, c in P.t.items()}
    if signos == {1}:
        return 1
    if signos == {-1}:
        return -1
    return None


def _texto_poli(P):
    from .exportar_texto import texto
    return texto(A.ast(P))


def _igualdad(eq):
    return {"izquierda": eq["izquierda"], "derecha": eq["derecha"]}


def _igualdad_de(lados):
    return {"izquierda": lados["izquierda"], "derecha": lados["derecha"]}


def _simbolos_en(e):
    if e["tipo"] == "simbolo":
        return {e["id"]}
    r = set()
    for k in ("argumentos",):
        for a in e.get(k, []):
            r |= _simbolos_en(a)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            r |= _simbolos_en(e[k])
    return r


def _variables_derivadas(e):
    r = set()
    if e["tipo"] == "derivada":
        r.add(e["respecto"])
    if e["tipo"] in ("gradiente", "divergencia", "laplaciano"):
        r |= set(e["coordenadas"])
    for a in e.get("argumentos", []):
        r |= _variables_derivadas(a)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            r |= _variables_derivadas(e[k])
    return r


def termino_ast(coef, nucleo):
    """coef (Poli) por nucleo (monomio) como AST: (coeficiente) (nucleo)."""
    nucleo_ast = A.ast_monomio(Fraction(1), nucleo) if nucleo else None
    u = coef.monomio_unico()
    if u is None:
        c_ast = A.ast(coef)
        return c_ast if nucleo_ast is None else A._producto([c_ast, nucleo_ast])
    c, m = u
    if nucleo_ast is None:
        return A.ast_monomio(c, m)
    if not m:
        return A.ast_monomio(c, nucleo)
    r = A._producto([A.ast_monomio(abs(c), m), nucleo_ast])
    return A.negar_ast(r) if c < 0 else r


def presentar_lado(items, presentacion):
    """items: [(nucleo, coef)] en orden. 'factorizada' agrupa los terminos
    que comparten el mismo coeficiente no numerico."""
    if presentacion == "factorizada":
        grupos, orden = {}, []
        for nucleo, coef in items:
            u = coef.monomio_unico()
            clave = A.clave_monomio(u[1]) if u and u[1] else None
            if clave is None:
                orden.append(("solo", nucleo, coef))
                continue
            if clave not in grupos:
                grupos[clave] = (u[1], [])
                orden.append(("grupo", clave, None))
            grupos[clave][1].append((nucleo, u[0]))
        terminos = []
        for tipo, a, b in orden:
            if tipo == "solo":
                terminos.append(termino_ast(b, a))
                continue
            m, miembros = grupos[a]
            if len(miembros) == 1:
                nucleo, c = miembros[0]
                terminos.append(termino_ast(A.monomio(c, dict(m)), nucleo))
                continue
            interior = A.ast_suma([termino_ast(A.numero(c), n) for n, c in miembros])
            terminos.append(A._producto([A.ast_monomio(Fraction(1), m), interior]))
        return A.ast_suma(terminos)
    return A.ast_suma([termino_ast(c, n) for n, c in items])
