"""
Analisis dimensional de las ecuaciones del ensamblaje.

No interpreta LaTeX: tipa EXPRESIONES del ensamblaje. Un balance se tipa
desde su lista `terminos` (cada termino es signo x coeficiente x producto de
variables, cada variable con su unidad SI del modelo) y su `acumulacion`
(d/dt de esas variables); una relacion constitutiva, desde una forma tipada
que construye el motor junto a la ecuacion (`formas_tipadas`). Las unidades
se resuelven con pint, el mismo registro que valida la tabla de unidades.

Reglas:
  - todos los terminos y el lado izquierdo tienen que tener la MISMA
    dimension y el mismo factor a SI (un W no es un kW);
  - una temperatura ABSOLUTA no puede ser factor de un producto: lo que
    multiplica a una conductancia o a una capacidad es una DIFERENCIA
    (T_1 - T_2), y un desplazamiento Celsius nunca entra como factor;
  - un cero o un termino anulado conserva la dimension del balance;
  - lo que no tiene forma tipada se declara 'no_evaluable' con su motivo.

Compatible NO demuestra conservacion ni exactitud: solo que las magnitudes
que se suman son sumables.
"""

import functools

import pint

_UREG = pint.UnitRegistry()

_ALIAS = {"m3": "m**3", "m2": "m**2", "m3/s": "m**3/s", "mol/m3": "mol/m**3",
          "adimensional": "dimensionless", "-": "dimensionless", "1/s": "1/s"}


@functools.lru_cache(maxsize=None)
def _cantidad(unidad):
    """pint Quantity de 1 unidad, o None si no se reconoce."""
    if unidad is None:
        return None
    texto = _ALIAS.get(unidad, unidad)
    try:
        return _UREG.Quantity(1.0, texto)
    except Exception:
        return None


def _latex(q):
    try:
        s = f"{q.units:~L}"
        return s if s else "1"
    except Exception:
        return None


def _clave(q):
    """(dimensionalidad, factor a SI): dos cantidades son sumables si coinciden."""
    base = q.to_base_units()
    return (str(q.dimensionality), round(float(base.magnitude), 12))


# Unidades SI coherentes en las que se PRESENTA una magnitud (pint simplifica
# mol/s x J/mol a J/s; se escribe W). Solo presentacion: la comprobacion usa
# la dimension y el factor a SI.
_PREFERIDAS = ["W", "J", "mol/s", "mol", "kg", "kg/s", "K", "Pa", "m**3", "m**2",
               "J/mol", "W/K", "J/K", "J/(mol*K)", "mol/m**3", "m**3/s", "kg/mol",
               "J/(kg*K)", "1/s", "s", "dimensionless"]


def _presentable(q):
    for u in _PREFERIDAS:
        ref = _UREG.Quantity(1.0, u)
        if ref.dimensionality == q.dimensionality:
            try:
                if abs(float(q.to(u).magnitude) - 1.0) < 1e-12:
                    return ref
            except Exception:
                pass
    return q


def _describe(q):
    if q is None:
        return {"unidad": None, "latex_unidad": None, "dimension": None}
    p = _presentable(q)
    return {"unidad": f"{p.units:~C}" if str(p.units) != "dimensionless" else "1",
            "latex_unidad": _latex(p),
            "dimension": str(q.dimensionality)}


def _factor(f, unidades, magnitudes):
    """
    (Quantity, descripcion, problema) de un factor tipado:
      {"v": id, "exp": k}         variable del modelo (exponente opcional)
      {"dif": [a, b]}             diferencia de dos temperaturas
      {"f": nombre, "unidad": u}  funcion tipada (u_i(T), T_sat(P)...)
      {"k": unidad, "nombre": n}  coeficiente con unidad
    """
    if "v" in f:
        u = unidades.get(f["v"])
        q = _cantidad(u)
        if q is None:
            return None, {"variable_id": f["v"], "unidad": u}, (
                f"la variable {f['v']!r} no tiene unidad reconocible en el modelo")
        exp = f.get("exp", 1)
        naturaleza = ("temperatura_absoluta" if magnitudes.get(f["v"]) == "T"
                      else None)
        return q ** exp, {"variable_id": f["v"], "unidad": u, "exponente": exp,
                          "naturaleza": naturaleza}, None
    if "dif" in f:
        a, b = f["dif"]
        ua, ub = unidades.get(a), unidades.get(b)
        qa, qb = _cantidad(ua), _cantidad(ub)
        if qa is None or qb is None:
            return None, {"diferencia": [a, b]}, (
                f"la diferencia {a} - {b} tiene un extremo sin unidad")
        if _clave(qa) != _clave(qb):
            return None, {"diferencia": [a, b], "unidades": [ua, ub]}, (
                f"{a} ({ua}) y {b} ({ub}) no se pueden restar")
        return qa, {"diferencia": [a, b], "unidad": ua,
                    "naturaleza": ("temperatura_diferencia"
                                   if magnitudes.get(a) == "T" else "diferencia")}, None
    if "f" in f:
        q = _cantidad(f["unidad"])
        return q, {"funcion": f["f"], "unidad": f["unidad"],
                   "naturaleza": f.get("naturaleza")}, (
            None if q is not None else f"la funcion {f['f']} no tiene unidad")
    if "k" in f:
        q = _cantidad(f["k"])
        return q, {"coeficiente": f.get("nombre"), "unidad": f["k"]}, (
            None if q is not None else f"el coeficiente {f.get('nombre')} sin unidad")
    return None, {"crudo": f}, "factor sin tipo"


def _producto(factores, unidades, magnitudes):
    """(Quantity, [descripciones], problema) de un producto de factores."""
    q, desc, problema = _UREG.Quantity(1.0, "dimensionless"), [], None
    for f in factores:
        qf, d, prob = _factor(f, unidades, magnitudes)
        desc.append(d)
        if prob and problema is None:
            problema = ("no_evaluable", prob)
            continue
        if qf is None:
            continue
        q = q * qf
    if problema is None and len(factores) > 1:
        absolutas = [d["variable_id"] for d in desc
                     if d.get("naturaleza") == "temperatura_absoluta"]
        if absolutas:
            problema = ("incompatible",
                        f"temperatura absoluta {', '.join(absolutas)} como factor de un "
                        "producto: lo que multiplica a una conductancia o a una "
                        "capacidad es una DIFERENCIA de temperaturas")
    return q, desc, problema


def analizar(lado_izquierdo, terminos, unidades, magnitudes, fuente):
    """
    lado_izquierdo: lista de factores, o {"derivada_de": [ids]} (d/dt de la
    suma de esas variables), o None (un cero: toma la dimension de los
    terminos). terminos: [{"factores": [...], "termino": dict o None}].
    """
    salida_t, claves, problemas = [], [], []
    for k, t in enumerate(terminos):
        q, desc, prob = _producto(t["factores"], unidades, magnitudes)
        orig = t.get("termino") or {}
        item = {"indice": k, "rol": orig.get("rol"), "latex": orig.get("latex"),
                "bloque_id": orig.get("bloque_id"), "conexion_id": orig.get("conexion_id"),
                "clave": orig.get("clave"), "factores": desc,
                **_describe(q if prob is None or prob[0] == "incompatible" else None)}
        if prob:
            item["estado"], item["motivo"] = prob
            problemas.append((prob[0], f"termino {k} ({orig.get('latex') or '?'}): "
                                       f"{prob[1]}", k))
        else:
            item["estado"] = "compatible"
            claves.append((k, _clave(q), q))
        salida_t.append(item)
    izq, q_izq, prob_izq = None, None, None
    if isinstance(lado_izquierdo, dict) and "derivada_de" in lado_izquierdo:
        qs = [_cantidad(unidades.get(v)) for v in lado_izquierdo["derivada_de"]]
        if any(x is None for x in qs) or not qs:
            prob_izq = ("no_evaluable", "acumulacion sin unidad")
        else:
            q_izq = qs[0] / _UREG.Quantity(1.0, "s")
            if any(_clave(x) != _clave(qs[0]) for x in qs):
                prob_izq = ("incompatible", "la acumulacion suma magnitudes distintas")
        izq = {"forma": "derivada temporal",
               "variables": list(lado_izquierdo["derivada_de"]), **_describe(q_izq)}
    elif lado_izquierdo is None:
        izq = {"forma": "cero (conserva la dimension de los terminos)"}
        if claves:
            q_izq = claves[0][2]
            izq.update(_describe(q_izq))
    else:
        q_izq, desc, prob_izq = _producto(lado_izquierdo, unidades, magnitudes)
        izq = {"forma": "expresion", "factores": desc, **_describe(q_izq)}
    if prob_izq:
        problemas.append((prob_izq[0], f"lado izquierdo: {prob_izq[1]}", None))
    if q_izq is not None and not prob_izq:
        ref = _clave(q_izq)
        for k, cl, q in claves:
            if cl != ref:
                salida_t[k]["estado"] = "incompatible"
                salida_t[k]["motivo"] = (f"{salida_t[k]['unidad']} no es "
                                         f"{_describe(q_izq)['unidad']}")
                problemas.append(("incompatible",
                                  f"termino {k} ({salida_t[k]['latex'] or '?'}): "
                                  f"{salida_t[k]['unidad']} frente a "
                                  f"{_describe(q_izq)['unidad']} del lado izquierdo", k))
    estado = ("incompatible" if any(p[0] == "incompatible" for p in problemas) else
              "no_evaluable" if problemas else "compatible")
    if estado == "compatible" and claves:
        # La unidad de presentacion: la de los terminos (W mejor que J/s); es
        # la misma magnitud, ya comprobado.
        q_izq = claves[0][2]
    return {"estado": estado,
            "motivo": "; ".join(p[1] for p in problemas) or None,
            "terminos_en_conflicto": [p[2] for p in problemas
                                      if p[0] == "incompatible" and p[2] is not None],
            "fuente": fuente, "lado_izquierdo": izq, "terminos": salida_t,
            **({"unidad_ecuacion": _describe(q_izq)["unidad"],
                "latex_unidad": _describe(q_izq)["latex_unidad"]}
               if q_izq is not None else {"unidad_ecuacion": None,
                                          "latex_unidad": None})}


def analizar_ecuacion(q, unidades, magnitudes, forma=None):
    """El analisis de una ecuacion del modelo (dict de _ec)."""
    if q.get("terminos") is not None:
        acum = q.get("acumulacion")
        izq = {"derivada_de": acum} if acum else None
        terms = []
        for t in q["terminos"]:
            factores = [{"v": v} for v in t["variables"]]
            if t.get("coeficiente") is not None:
                factores.append({"k": t.get("unidad_coeficiente") or "dimensionless",
                                 "nombre": "coeficiente"})
            terms.append({"factores": factores, "termino": t})
        return analizar(izq, terms, unidades, magnitudes,
                        "terminos tipados del ensamblaje (los mismos que se evaluan)")
    if forma is not None:
        return analizar(forma["izquierda"],
                        [{"factores": f, "termino": {"latex": None}}
                         for f in forma["terminos"]], unidades, magnitudes,
                        "forma tipada de la relacion, construida con la ecuacion")
    return {"estado": "no_evaluable", "fuente": None,
            "motivo": forma_ausente(q), "lado_izquierdo": None, "terminos": [],
            "terminos_en_conflicto": [], "unidad_ecuacion": None,
            "latex_unidad": None}


def forma_ausente(q):
    if q.get("tipo") in ("condicion",):
        return ("es una condicion (fija un valor): no suma magnitudes que comprobar")
    if q.get("tipo") == "derivada_de_restriccion":
        return "derivada de una restriccion ya analizada; no tiene forma propia"
    return "relacion sin forma tipada en esta entrega"
