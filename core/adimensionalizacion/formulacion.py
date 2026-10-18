"""
Una formulacion publicada: aplica la solucion de A3 a la transformacion A2
preparada y construye ecuaciones, terminos, grupos, restricciones, pasos,
transformaciones directa/inversa y el certificado de equivalencia.
"""

import copy
from fractions import Fraction

from . import algebra as A
from .dimensional import dim_a_json, dimension_de, limpiar
from .exportar_texto import texto
from .transformacion import ALCANCE_EQUIVALENCIA, _prod, _sim, presentar_lado, reescribir


def _cociente(n, d):
    return {"tipo": "cociente", "numerador": copy.deepcopy(n), "denominador": copy.deepcopy(d)}


class _Grupos:
    def __init__(self, prep):
        self.prep = prep
        self.lista = []
        self.por_clave = {}

    def registrar(self, coef, ambito, interno=False):
        """Devuelve el id del grupo del coeficiente (sin su factor numerico), o None."""
        u = coef.monomio_unico()
        if u is not None:
            c, m = u
            if not m:
                return None
            poli = A.monomio(1, dict(m))
            clave = A.clave_monomio(m)
        else:
            poli, clave = coef, coef.clave
        if clave in self.por_clave:
            g = self.por_clave[clave]
            if ambito not in g["usos"]:
                g["usos"].append(ambito)
            g["interno"] = g["interno"] and interno
            return g["id"]
        definicion = A.ast(poli)
        dim = dimension_de(definicion, self.prep.dims_t, self.prep.funciones_dim)
        g = {"id": f"G{len(self.lista) + 1}", "definicion": definicion,
             "dimension": dim_a_json(dim) if dim is not None else None,
             "adimensional": dim is not None and not limpiar(dim),
             "contieneEscalasLibres": False, "usos": [ambito], "interno": interno, "inversoDe": None}
        if u is not None:
            inv = A.clave_monomio(tuple((a, -e) for a, e in u[1]))
            if inv in self.por_clave:
                g["inversoDe"] = self.por_clave[inv]["id"]
        self.lista.append(g)
        self.por_clave[clave] = g
        return g["id"]

    def internos(self, nucleo, ambito):
        """Coeficientes dentro de funciones, llamadas y sumas internas."""
        for a, _ in nucleo:
            for P in A._polis_internos(a):
                for n, c in A.separar_terminos(P, self.prep.ctx_t):
                    if c.constante_numerica() is None:
                        self.registrar(c, ambito, interno=True)
                    self.internos(n, ambito)


def formular(prep, objetivos, presentacion):
    estados, solucion, situacion, signos_usados, rango, filas = prep.resolver(objetivos)
    mapa_sol = {sid: A.ast(P) for sid, P in solucion.items()}
    valor = {}
    for e in prep.escalas:
        sid = e["id"]
        valor[sid] = copy.deepcopy(prep.mapa_expr.get(sid) or mapa_sol.get(sid) or _sim(sid))
    libres = sorted(sid for sid, s in situacion.items() if s == "libre")
    grupos = _Grupos(prep)

    def final(P):
        return prep._final(P, mapa_sol)

    def publicar(reg):
        terminos_pub, lados, lados_antes, lados_des = [], {}, {}, {}
        for lado, terminos in reg["lados"].items():
            items, items_antes = [], []
            for t in terminos:
                for n, c in t["partes_F"]:
                    items_antes.append((n, c))
                    for n2, c2 in A.separar_terminos(final(A.multiplicar(c, A.Poli({n: Fraction(1)}))), prep.ctx_t):
                        items.append((n2, c2))
                        gid = grupos.registrar(c2, t["id"])
                        grupos.internos(n2, t["id"])
                        nucleo_ast = A.ast_monomio(Fraction(1), n2) if n2 else {"tipo": "numero", "valor": 1}
                        dn = dimension_de(nucleo_ast, prep.dims_t, prep.funciones_dim)
                        terminos_pub.append({"id": t["id"], "lado": lado, "ruta": t["ruta"], "original": t["original"],
                                             "coeficiente": A.ast(c2), "grupoId": gid, "nucleo": nucleo_ast,
                                             "dimensionNucleo": dim_a_json(dn) if dn is not None else None,
                                             "_coef": c2})
            lados[lado] = presentar_lado(items, presentacion)
            lados_antes[lado] = presentar_lado(items_antes, "desarrollada")
            lados_des[lado] = presentar_lado(items, "desarrollada")
        F = final(reg["F_expr"])
        igualdad = {"id": reg["id"], "izquierda": lados["izquierda"], "derecha": lados["derecha"]}
        pasos = [{"ambito": reg["id"], "regla": r, "antes": a, "despues": d, "supuestos": s} for r, a, d, s in reg["pasos"]]
        if mapa_sol:
            pasos.append({"ambito": reg["id"], "regla": "sustitucion_de_escalas_determinadas", "antes": lados_antes,
                          "despues": {"izquierda": igualdad["izquierda"], "derecha": igualdad["derecha"]},
                          "supuestos": ["solucion exacta de los objetivos monomiales con escalas positivas"]})
        publicaciones.append({"reg": reg, "igualdad": igualdad, "antes": lados_antes, "desarrollada": lados_des,
                              "tipo": reg["ambito"]})
        return igualdad, terminos_pub, F, pasos

    ecuaciones, terminos, pasos, factores, publicaciones = [], [], [], {}, []
    for reg in prep.ecuaciones:
        igualdad, tp, F, ps = publicar(reg)
        ecuaciones.append({"igualdad": igualdad, "factorGlobal": A.ast(F), "terminos": tp})
        factores[reg["id"]] = F
        terminos.extend(tp)
        pasos.extend(ps)
    condiciones = []
    for reg, c in zip(prep.condiciones, prep.modelo["condiciones"]):
        igualdad, tp, F, ps = publicar(reg)
        for t in tp:
            del t["_coef"]
        igualdad["id"] = c["ecuacion"]["id"]
        condiciones.append({"id": c["id"], "tipo": c["tipo"], "dominioId": c["dominioId"], "ecuacion": igualdad,
                            "factorGlobal": A.ast(F), "terminos": tp,
                            "ubicacion": "inicio del dominio temporal" if c["tipo"] == "inicial" else "frontera del dominio (el contrato v1 no declara el extremo)"})
        factores["condicion:" + c["id"]] = F
        for p in ps:
            p["ambito"] = c["id"]
        pasos.extend(ps)
    dominios = []
    for d in prep.dominios:
        dominios.append({"id": d["original"]["id"], "variableId": d["variable"],
                         "desde": A.ast(final(d["poli"]["desde"])), "hasta": A.ast(final(d["poli"]["hasta"]))})
    # v2: ubicacion declarada -> extremo transformado del dominio.
    por_dominio = {x["id"]: x for x in dominios}
    for c, pub in zip(prep.modelo["condiciones"], condiciones):
        if "ubicacion" not in c:
            continue
        dom = por_dominio[c["dominioId"]]
        extremo = c["ubicacion"]["extremo"]
        pub["lugar"] = {"variableId": dom["variableId"], "variableOriginal": c["ubicacion"]["variableId"], "extremo": extremo,
                        "valor": copy.deepcopy(dom[extremo]),
                        "original": copy.deepcopy(next(x for x in prep.modelo["dominios"] if x["id"] == c["dominioId"])[extremo])}
        pub["ubicacion"] = f"{dom['variableId']} = {texto(dom[extremo])} (extremo '{extremo}' del dominio {c['dominioId']})"
    for g in grupos.lista:
        g["contieneEscalasLibres"] = bool(_simbolos(g["definicion"]) & set(libres))

    # Objetivos: coeficiente final comprobado.
    por_termino = {t["id"]: t for t in terminos}
    for est in estados:
        if est.get("estado") in ("satisfecho", "dependiente"):
            t = por_termino.get(est["terminoId"])
            est["coeficienteFinal"] = A.ast(t["_coef"]) if t else None
            est["comprobado"] = bool(t) and t["_coef"] == A.numero(est["valorObjetivo"])
    for t in terminos:
        del t["_coef"]

    # Restricciones tipadas.
    restricciones = copy.deepcopy(prep.restricciones)

    def restringir(tipo, expresion, motivo, **extra):
        r = {"id": f"R{len(restricciones) + 1}", "tipo": tipo, "expresion": copy.deepcopy(expresion), "motivo": motivo}
        r.update(extra)
        restricciones.append(r)
        return r["id"]

    for e in prep.escalas:
        if e["papel"] == "escala":
            restringir("positivo", _sim(e["id"]), f"escala de {e['variable']}")
        if situacion[e["id"]] in ("determinada", "relacionada", "dada_por_expresion"):
            restringir("igualdad", _sim(e["id"]), f"escala {situacion[e['id']].replace('_', ' ')}", valor=valor[e["id"]])
    simbolos_modelo = prep.simbolos_modelo
    for p in sorted(signos_usados):
        if p in simbolos_modelo:
            restringir("signo", _sim(p), "signo declarado usado al normalizar", signo=simbolos_modelo[p]["signo"])

    # Transformaciones directa e inversa.
    valores = {e["id"]: valor[e["id"]] for e in prep.escalas}
    dir_final = {m["variable"]: A.sustituir(m["directa"], valores) for m in prep.mapas}
    inv_final = {m["variable"]: A.sustituir(m["inversa"], valores) for m in prep.mapas}
    directa = [{"simboloId": m["variable"], "expresion": dir_final[m["variable"]]} for m in prep.mapas]
    inversa = [{"simboloId": m["nuevo"], "expresion": inv_final[m["variable"]]} for m in prep.mapas]
    transformaciones = [{"variableId": m["variable"], "nuevoId": m["nuevo"], "familia": m["familia"],
                         "directa": dir_final[m["variable"]], "inversa": inv_final[m["variable"]],
                         "dominio": m["dominio"], "constantes": m["constantes"]} for m in prep.mapas]

    # Normalizacion.
    motivos = []
    if prep.sin_transformar:
        motivos.append({"codigo": "variables_sin_transformar", "simbolos": prep.sin_transformar,
                        "mensaje": "variables dimensionales que se conservan: " + ", ".join(prep.sin_transformar)})
    dimensionales = sorted({t["id"] for t in terminos if t["dimensionNucleo"] != {}})
    if dimensionales:
        motivos.append({"codigo": "nucleos_dimensionales", "terminos": dimensionales,
                        "mensaje": "terminos cuyo nucleo conserva dimensiones (funciones declaradas o coeficientes variables sin escala extraida)"})
    no_adim = [g["id"] for g in grupos.lista if not g["adimensional"]]
    if no_adim:
        motivos.append({"codigo": "grupos_dimensionales", "grupos": no_adim, "mensaje": "coeficientes con dimension"})
    normalizacion = {"estado": "parcial" if motivos else "completa", "motivos": motivos}

    # Certificado de equivalencia sobre lo publicado.
    inv_A = {m["nuevo"]: inv_final[m["variable"]] for m in prep.mapas}
    inv_B = {}
    for m in prep.mapas:
        if m["rol"] in A.INDEPENDIENTES:
            dh = A.derivar_ast(inv_final[m["variable"]], m["variable"], prep.ctx_o)
            inv_B[m["nuevo"]] = (m["variable"], dh, m["variable"] not in _simbolos(dh))
    comprobaciones = []

    reconstrucciones = []

    def comprobar_igualdad(ambito, original, publicada, F):
        try:
            res_o = A.canonica({"tipo": "suma", "argumentos": [original["izquierda"], A.negar_ast(original["derecha"])]}, prep.ctx_o, "expandir")
            res_p = {"tipo": "suma", "argumentos": [publicada["izquierda"], A.negar_ast(publicada["derecha"])]}
            inv = reescribir(reescribir(prep.deshacer_llamadas(res_p, valores), inv_A, {}), {}, inv_B)
            res_r = A.canonica(_prod(A.ast(F), inv), prep.ctx_o, "expandir")
            ok = A.iguales(res_o, res_r)
            lados_inv = {lado: A.ast(A.canonica(_prod(A.ast(F), reescribir(reescribir(prep.deshacer_llamadas(publicada[lado], valores), inv_A, {}), {}, inv_B)), prep.ctx_o, "expandir"))
                         for lado in ("izquierda", "derecha")}
            reconstrucciones.append({"ambito": ambito, "publicada": publicada, "estado": "demostrada" if ok else "no_demostrada", **lados_inv})
        except (A.ErrorAlgebraico, A.NoSoportado) as ex:
            ok = False
            comprobaciones.append({"ambito": ambito, "tipo": "sustitucion_inversa", "estado": "no_demostrada", "motivo": ex.mensaje})
            return
        comprobaciones.append({"ambito": ambito, "tipo": "sustitucion_inversa", "estado": "demostrada" if ok else "no_demostrada"})

    for reg, ec in zip(prep.ecuaciones, ecuaciones):
        comprobar_igualdad(reg["id"], reg["original"], ec["igualdad"], factores[reg["id"]])
    for reg, c in zip(prep.condiciones, condiciones):
        comprobar_igualdad(c["id"], reg["original"], c["ecuacion"], factores["condicion:" + c["id"]])
    for d, pub in zip(prep.dominios, dominios):
        ok = True
        for lado in ("desde", "hasta"):
            orig = A.canonica(d["original"][lado], prep.ctx_o, "expandir")
            x = reescribir(pub[lado], inv_A, {})
            if d["mapa"]:
                x = A.sustituir(dir_final[d["mapa"]["variable"]], {d["mapa"]["nuevo"]: x})
            ok = ok and A.iguales(orig, A.canonica(x, prep.ctx_o, "expandir"))
        comprobaciones.append({"ambito": pub["id"], "tipo": "dominio", "estado": "demostrada" if ok else "no_demostrada"})
    for ec in ecuaciones + [{"igualdad": c["ecuacion"]} for c in condiciones]:
        eq = ec["igualdad"]
        di = dimension_de(eq["izquierda"], prep.dims_t, prep.funciones_dim)
        dd = dimension_de(eq["derecha"], prep.dims_t, prep.funciones_dim)
        es_cero = eq["derecha"] == {"tipo": "numero", "valor": 0} or eq["izquierda"] == {"tipo": "numero", "valor": 0}
        ok = di is not None and (es_cero or (dd is not None and limpiar(di) == limpiar(dd)))
        comprobaciones.append({"ambito": eq["id"], "tipo": "dimensiones", "estado": "demostrada" if ok else "no_demostrada",
                               "dimension": dim_a_json(di) if di is not None else None})
    for est in estados:
        if "comprobado" in est:
            comprobaciones.append({"ambito": est["id"], "tipo": "objetivo", "estado": "demostrada" if est["comprobado"] else "no_demostrada"})
    equivalencia = {"estado": "demostrada" if all(c["estado"] == "demostrada" for c in comprobaciones) else "no_demostrada",
                    "alcance": ALCANCE_EQUIVALENCIA, "restricciones": [r["id"] for r in restricciones],
                    "comprobaciones": comprobaciones}

    simbolos = []
    for e in prep.escalas:
        s = {"id": e["id"], "nombre": e["nombre"], "rol": "escala", "papel": e["papel"], "variableId": e["variable"],
             "dimension": dim_a_json(e["dimension"]), "estado": situacion[e["id"]],
             "valor": None if situacion[e["id"]] in ("libre", "dada") else valor[e["id"]]}
        if "cantidad" in e:
            s["cantidad"] = e["cantidad"]
        simbolos.append(s)
    for m in prep.mapas:
        info = prep.ctx_t.simbolos[m["nuevo"]]
        simbolos.append({"id": m["nuevo"], "nombre": m["nuevo"], "rol": "variable_adimensional", "rolOrigen": m["rol"],
                         "variableId": m["variable"], "dimension": {}, "dependeDe": sorted(info["dependeDe"]),
                         "signo": info["signo"]})

    from .desarrollo import construir
    desarrollo = construir(prep, {"estados": estados, "filas": filas, "rango": rango, "valor": valor, "libres": libres,
                                  "mapa_sol": mapa_sol, "signos_usados": signos_usados, "publicaciones": publicaciones,
                                  "dominios": dominios, "condiciones": condiciones, "grupos": grupos.lista, "restricciones": restricciones,
                                  "reconstrucciones": reconstrucciones})

    extra = {}
    usadas = [(fid, info) for fid, info in prep.funciones_escaladas.items() if any(x is not None for x in info["args"])]
    if usadas:
        # v2: fhat(w) = f(s w) / S, con las escalas ya resueltas.
        extra["funcionesAdimensionales"] = [{
            "id": info["fhat"], "nombre": info["fhat"], "funcionId": fid, "escalaId": info["escala"],
            "entradas": [dim_a_json(x) for x in prep.funciones_dim[info["fhat"]]["entradas"]], "salida": {},
            "dependeDe": sorted(prep.ctx_t.funciones[info["fhat"]]["dependeDe"]),
            "argumentos": [{"escala": prep.escala_argumento(info, i, valores), "extraida": info["args"][i] is not None and info["args"][i] != A.UNO}
                           for i in range(len(info["args"]))],
            "definicion": prep.supuestos_funciones(valores)[[f for f, _ in usadas].index(fid)],
        } for fid, info in usadas]
    return {
        **extra,
        "desarrollo": desarrollo,
        "desarrolloEstado": {"estado": "completo", "nota": "cada operacion realizada por el nucleo, en su orden; sin hipotesis fisicas"},
        "simbolos": simbolos,
        "escalas": [{"simboloId": e["variable"], "escalaId": e["id"], "papel": e["papel"], "estado": situacion[e["id"]], "valor": valor[e["id"]]} for e in prep.escalas],
        "transformaciones": transformaciones,
        "libres": libres,
        "rangoObjetivos": rango,
        "normalizacion": normalizacion,
        "ecuaciones": ecuaciones,
        "dominios": dominios,
        "condiciones": condiciones,
        "directa": directa,
        "inversa": inversa,
        "grupos": grupos.lista,
        "objetivos": estados,
        "restricciones": restricciones,
        "pasos": pasos,
        "equivalencia": equivalencia,
    }


def _simbolos(e):
    if e["tipo"] == "simbolo":
        return {e["id"]}
    r = set()
    for a in e.get("argumentos", []):
        r |= _simbolos(a)
    for k in ("numerador", "denominador", "base", "exponente", "expresion"):
        if k in e:
            r |= _simbolos(e[k])
    return r


def huella(formulacion):
    """Clave de comparacion de dos formulaciones del mismo modelo: conjunto
    de igualdades publicadas (sin depender del orden de terminos) mas
    dominios. Sirve para eliminar duplicados demostrables."""
    partes = []
    for ec in formulacion["ecuaciones"]:
        partes.append(("e", ec["igualdad"]["id"], _clave_igualdad(ec["igualdad"])))
    for c in formulacion["condiciones"]:
        partes.append(("c", c["id"], _clave_igualdad(c["ecuacion"])))
    for d in formulacion["dominios"]:
        partes.append(("d", d["id"], repr(d["desde"]) + repr(d["hasta"])))
    return tuple(sorted(partes))


def _clave_igualdad(eq):
    from .algebra import Contexto
    ctx = Contexto({}, {})
    try:
        return A.canonica({"tipo": "suma", "argumentos": [eq["izquierda"], A.negar_ast(eq["derecha"])]}, ctx).clave
    except Exception:
        return repr(eq)
