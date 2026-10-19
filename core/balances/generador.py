"""
Motor de balances: de las ecuaciones fundamentales y los supuestos de cada
volumen a las ecuaciones explícitas del modelo común (ARQUITECTURA_MOTOR.md §5,
paso 5.5 adelantado por §9.1).

Entrada: un modelo común cuyos volúmenes declaran su estado como supuesto
(`fase_no_evaluada` o `u_lineal`), sus supuestos de reducción (los indicadores
de la hoja: `supuestos.materia`, `supuestos.energia`), la topología (corrientes
entre volúmenes o con el exterior) y los datos. Salida: el mismo modelo con
`matematico` (el árbol del documento v2) y `restricciones`; lo resuelve la
entrada de ecuaciones escritas del compilador (core/compilador/explicito.py).

Leyes generales, sin ramas por equipo, operación ni sustancia:

  materia, por volumen v y componente i (forma total, masa como estado):
      dm_iv/dt = sum_s B_vs mdot_is  - Phi_iv,resto  + G_iv - C_iv
    - los términos de frontera desaparecen si el volumen elimina el transporte
      (frontera fija, sin convección ni difusión);
    - Phi_resto, si la frontera restante no es impermeable;
    - G y C, si las fuentes no se han eliminado; por volumen (tasa · V) si se
      declararon uniformes, integradas si no;
    - mdot_is: dato por componente (base másica o molar · M_i) o caudal total
      por fracciones.

  energía, por volumen v con u(T) declarada como supuesto (u_lineal):
      U_v = m_v u(T_v),  u(T) = u_ref + c (T - T_ref)
      dU_v/dt = sum_s B_vs [max(q,0) h(donante aguas arriba) + min(q,0) h(v)]
                + Qdot + Wtau + Wb + R  - p dV_v/dt (frontera móvil)
    - h = u(T) + p/rho si la entalpía transporta la energía de flujo, u(T) si
      no (y entonces el trabajo de flujo p/rho va aparte);
    - el donante de cada corriente se elige por el signo del caudal, con
      max/min: ninguna dirección se supone;
    - el dominio de validez del supuesto, T_min <= T <= T_max, se vigila:
      el cálculo se detiene al salir de él.

Las expresiones de los datos usan las variables del Engine: por volumen v y
componente de símbolo S, m_S_v, m_total_v, V_v, rho_S_v, rho_total_v; en los
datos propios de un volumen, también m, m_total, V, rho, rho_total, m_S, rho_S,
T y U; y t. Cada una se define una sola vez como expresión de los estados.
"""

import math
from fractions import Fraction

from core import expresiones_motor as ex
from core import unidades as un
from core.modelo import leer_modelo_comun


class NoGenerable(Exception):
    """El modelo no se puede llevar a ecuaciones explícitas: el motivo, con su ruta."""


# --- árbol común ---------------------------------------------------------------------------
def num(v):
    return {"tipo": "numero", "valor": float(v)}


def sim(i):
    return {"tipo": "simbolo", "id": i}


def suma(*a):
    a = [x for x in a if not (x["tipo"] == "numero" and x["valor"] == 0)]
    return num(0) if not a else a[0] if len(a) == 1 else {"tipo": "suma", "argumentos": list(a)}


def prod(*a):
    if any(x["tipo"] == "numero" and x["valor"] == 0 for x in a):
        return num(0)
    a = [x for x in a if not (x["tipo"] == "numero" and x["valor"] == 1)]
    return num(1) if not a else a[0] if len(a) == 1 else {"tipo": "producto", "argumentos": list(a)}


def neg(a):
    return prod(num(-1), a)


def div(a, b):
    return {"tipo": "cociente", "numerador": a, "denominador": b}


def fun(nombre, *a):
    return {"tipo": "funcion", "nombre": nombre, "argumentos": list(a)}


def es_cero(e):
    return e["tipo"] == "numero" and e["valor"] == 0


DIM = {
    "masa": {"M": 1}, "caudal_masico": {"M": 1, "T": -1}, "caudal_molar": {"N": 1, "T": -1},
    "tasa_volumetrica_masica": {"M": 1, "L": -3, "T": -1}, "volumen": {"L": 3}, "temperatura": {"Theta": 1},
    "energia": {"M": 1, "L": 2, "T": -2}, "potencia": {"M": 1, "L": 2, "T": -3},
    "capacidad_calorifica_especifica": {"L": 2, "T": -2, "Theta": -1}, "energia_especifica": {"L": 2, "T": -2},
    "densidad": {"M": 1, "L": -3}, "presion": {"M": 1, "L": -1, "T": -2}, "cantidad": {"N": 1}, "adimensional": {},
}


class _Generador:
    def __init__(self, modelo):
        self.m = leer_modelo_comun(modelo)
        m = self.m
        if m["matematico"] is not None:
            raise NoGenerable("el modelo ya trae sus ecuaciones escritas")
        if not m["volumenes"]:
            raise NoGenerable("el modelo no tiene volúmenes")
        for v in m["volumenes"]:
            if v["termodinamica"]["tipo"] != "supuesto":
                raise NoGenerable(f"volumen {v['id']}: su estado sale del equilibrio; lo ejecuta la entrada estructural del compilador")
        self.comp = {c["id"]: c for c in m["componentes"]}
        self.vol = {v["id"]: v for v in m["volumenes"]}
        self.simbolos = [{"id": "t", "nombre": "t", "rol": "tiempo", "dimension": {"T": {"n": 1, "d": 1}}, "unidad": None,
                          "constante": False, "dependeDe": [], "signo": "desconocido"}]
        self.ecuaciones, self.condiciones, self.restricciones = [], [], []
        self.observables, self.verificaciones = [], []
        self.exterior_m = {}      # componente -> términos que cruzan la frontera del sistema (corrientes exteriores, fuentes)
        self.exterior_E = []      # ídem para la energía (corrientes exteriores, calor, trabajos, fuentes)
        self.alias_global = {"t": sim("t")}
        self._cache = {}

    # --- datos ---------------------------------------------------------------------------
    def dato(self, did, magnitud, local=None, ruta=None):
        """Dato -> árbol en SI, con las variables del Engine sustituidas."""
        ruta = ruta or f"datos.{did}"
        if did not in self.m["datos"]:
            raise NoGenerable(f"{ruta}: dato inexistente")
        d = self.m["datos"][did]["declaracion"]
        if not d["texto"].strip():
            raise NoGenerable(f"{ruta}: dato pendiente")
        try:
            u = un.interpretar(d["unidad"])
        except un.ErrorUnidad as e:
            raise NoGenerable(f"{ruta}: {e}") from e
        esperada = {k: Fraction(v) for k, v in DIM[magnitud].items()}
        if u["dimension"] != esperada:
            raise NoGenerable(f"{ruta}: la unidad {d['unidad']!r} ({un.dimension_texto(u['dimension'])}) no es de {magnitud} ({un.dimension_texto(esperada)})")
        alias = {**self.alias_global, **(local or {})}
        try:
            arbol = ex.analizar(d["texto"], sorted(alias))
        except ex.ErrorExpresion as e:
            raise NoGenerable(f"{ruta}: {e}") from e
        e = self._traducir(arbol, alias, ruta)
        e = prod(num(u["factor"]), e) if u["factor"] != 1 else e
        return suma(e, num(u["desplazamiento"])) if u["desplazamiento"] else e

    def constante(self, did, magnitud):
        """Valor numérico de un dato que no depende de nada (o None si depende)."""
        e = self.dato(did, magnitud, {})
        return e["valor"] if e["tipo"] == "numero" else None

    def _traducir(self, a, alias, ruta):
        if a[0] == "num":
            return num(a[1])
        if a[0] == "var":
            return alias[a[1]]
        op, args = a[1], [self._traducir(x, alias, ruta) for x in a[2]]
        if op == "+":
            return suma(*args)
        if op == "-":
            return suma(args[0], neg(args[1]))
        if op == "*":
            return prod(*args)
        if op == "/":
            return div(*args)
        if op == "^":
            return {"tipo": "potencia", "base": args[0], "exponente": args[1]}
        if op == "neg":
            return neg(args[0])
        if op == "sqrt":
            return {"tipo": "potencia", "base": args[0], "exponente": num(0.5)}
        if op in ("sin", "cos", "exp", "log", "abs", "min", "max"):
            return fun(op, *args)
        raise NoGenerable(f"{ruta}: la función {op} no tiene traducción al árbol común (su derivada no existe en el cero)")

    # --- símbolos ----------------------------------------------------------------------------
    def campo(self, sid, dim, unidad):
        self.simbolos.append({"id": sid, "nombre": sid, "rol": "campo", "dimension": {k: {"n": v, "d": 1} for k, v in dim.items()},
                              "unidad": unidad, "constante": False, "dependeDe": ["t"], "signo": "desconocido"})
        return sim(sid)

    # --- generación --------------------------------------------------------------------------
    def generar(self):
        m = self.m
        # 1. Estados de materia (masa por componente) y variables del Engine por volumen.
        self.masa, self.V, self.fm = {}, {}, {}
        for v in m["volumenes"]:
            vid, fm = v["id"], v["supuestos"]["materia"]
            self.fm[vid] = fm
            if fm.get("vista") != "cantidad" or fm.get("cantidadVolumen"):
                raise NoGenerable(f"volumen {vid}: el motor de balances genera la forma total con la masa de cada componente como estado; "
                                  "la sustitución por volumen o un campo espacial siguen por su camino (adaptador y motor de discretización)")
            if fm.get("reglasEstado"):
                raise NoGenerable(f"volumen {vid}: reglas de estado: pendientes del motor de balances")
            for c in v["componenteIds"]:
                s = self.comp[c]["simbolo"]
                self.masa[(vid, c)] = self.campo(f"m_{s}_{vid}", {"M": 1}, "kg")
                self.alias_global[f"m_{s}_{vid}"] = self.masa[(vid, c)]
            self.alias_global[f"m_total_{vid}"] = suma(*[self.masa[(vid, c)] for c in v["componenteIds"]])
        for v in m["volumenes"]:
            vid = v["id"]
            if v.get("volumenDatoId"):
                self.V[vid] = self.dato(v["volumenDatoId"], "volumen", {})
                self.alias_global[f"V_{vid}"] = self.V[vid]
                for c in v["componenteIds"]:
                    s = self.comp[c]["simbolo"]
                    self.alias_global[f"rho_{s}_{vid}"] = div(self.masa[(vid, c)], self.V[vid])
                self.alias_global[f"rho_total_{vid}"] = div(self.alias_global[f"m_total_{vid}"], self.V[vid])
        # 2. Energía: estado U y temperatura por volumen con u(T) supuesta.
        self.energia = {}
        for v in m["volumenes"]:
            if v["balances"]["energia"]:
                self._preparar_energia(v)
        # 3. Caudales másicos por corriente y componente (una sola vez cada uno).
        self.caudal = {}
        for s in m["corrientes"]:
            self._caudales(s)
        # 4. Ecuaciones.
        for v in m["volumenes"]:
            self._materia(v)
            if v["balances"]["energia"]:
                self._energia(v)
            elif v["termodinamica"]["supuesto"] == "u_lineal":
                raise NoGenerable(f"volumen {v['id']}: declara u(T) sin balance de energía activo")
            if v["balances"]["momento"]:
                raise NoGenerable(f"volumen {v['id']}: el balance de momento todavía no se genera")
        for s in m["corrientes"]:
            if s["mecanismo"] == "convectivo":
                q = [self.caudal[(s["id"], c)] for c in s["componenteIds"]]
                for i in range(len(q)):
                    for j in range(i + 1, len(q)):
                        self.restricciones.append({"expresion": prod(q[i], q[j]), "tipo": "no_negativo",
                                                   "descripcion": f"corriente {s['id']}: una corriente convectiva lleva todos sus componentes en el mismo sentido"})
        return self._modelo()

    def _local(self, v, c=None):
        """Variables propias de los datos de un volumen (y de un componente)."""
        vid = v["id"]
        loc = {"m_total": self.alias_global[f"m_total_{vid}"]}
        for k in v["componenteIds"]:
            loc[f"m_{self.comp[k]['simbolo']}"] = self.masa[(vid, k)]
        if c is not None:
            loc["m"] = self.masa[(vid, c)]
        elif len(v["componenteIds"]) == 1:
            loc["m"] = loc["m_total"]
        if vid in self.V:
            loc["V"] = self.V[vid]
            loc["rho_total"] = div(loc["m_total"], self.V[vid])
            for k in v["componenteIds"]:
                loc[f"rho_{self.comp[k]['simbolo']}"] = div(self.masa[(vid, k)], self.V[vid])
            if c is not None:
                loc["rho"] = div(self.masa[(vid, c)], self.V[vid])
        if vid in self.energia:
            e = self.energia[vid]
            loc.update({"T": e["T"], "U": e["U"]})
            if e["rho"] is not None:
                loc["rho"] = e["rho"]
                loc["V"] = div(loc["m_total"], e["rho"])
        return loc

    def _caudales(self, s):
        mat, sid = s["materia"], s["id"]
        extremos = [x for x in (s["desde"], s["hasta"]) if x is not None]
        for c in s["componenteIds"]:
            # Una corriente con un solo volumen en un extremo admite también sus variables propias.
            local = {**self.alias_global, **self._local(self.vol[extremos[0]], c)} if len(extremos) == 1 else self.alias_global
            ruta = f"corrientes.{sid}.materia"
            if mat["modo"] == "por_componente":
                did = mat["caudalIds"].get(str(c))
                if did is None:
                    q = num(0)
                elif mat["base"] == "masica":
                    q = self.dato(did, "caudal_masico", local, f"{ruta}.caudalIds.{c}")
                elif mat["base"] == "molar":
                    q = prod(num(self._M(c, sid)), self.dato(did, "caudal_molar", local, f"{ruta}.caudalIds.{c}"))
                else:
                    raise NoGenerable(f"corriente {sid}: caudal volumétrico: pendiente del motor de balances")
            elif mat["modo"] == "total_y_composicion":
                x = float(mat["fracciones"][str(c)])
                tot = self.dato(mat["caudalId"], "caudal_masico" if mat["base"] == "masica" else "caudal_molar", local, f"{ruta}.caudalId")
                q = prod(num(x * (1.0 if mat["base"] == "masica" else self._M(c, sid))), tot)
            else:
                raise NoGenerable(f"corriente {sid}: el modo {mat['modo']} necesita el estado del donante (camino estructural)")
            self.caudal[(sid, c)] = q

    def _M(self, c, sid):
        M = self.comp[c].get("masaMolar")
        if not M:
            raise NoGenerable(f"corriente {sid}: caudal molar del componente {c} sin masa molar declarada")
        q = M.get("cantidad", M) if isinstance(M, dict) else {"valor": M, "unidad": "kg/mol"}
        return un.a_SI(float(q["valor"]), q["unidad"])

    def _materia(self, v):
        vid, fm = v["id"], self.fm[v["id"]]
        campo = fm.get("campo", {})
        sin_difusion = campo.get("sinDifusion") or len(v["componenteIds"]) == 1
        sin_transporte = fm.get("fija") and campo.get("sinConveccion") and sin_difusion
        fuentes = {"generacion": not (campo.get("sinReaccion") or campo.get("sinGeneracion")),
                   "consumo": not (campo.get("sinReaccion") or campo.get("sinConsumo"))}
        uniforme = {"generacion": fm.get("generacionUniforme"), "consumo": fm.get("consumoUniforme")}
        terminos = v.get("terminos", {})
        acumula = not (fm.get("sinAcumulacion"))
        materia = v["balances"]["materia"]
        for c in v["componenteIds"]:
            der = []
            for s in self.m["corrientes"]:
                B = (1 if s["hasta"] == vid else 0) - (1 if s["desde"] == vid else 0)
                if B == 0 or c not in s["componenteIds"]:
                    continue
                q = self.caudal[(s["id"], c)]
                if not materia and not es_cero(q):
                    raise NoGenerable(f"volumen {vid}: sin balance de materia la cantidad es constante, y la corriente {s['id']} la cambia; activa materia")
                if sin_transporte:
                    if not es_cero(q):
                        raise NoGenerable(f"volumen {vid}: sus supuestos eliminan el transporte por la frontera y la corriente {s['id']} la atraviesa")
                    continue
                der.append(q if B > 0 else neg(q))
                if s["desde"] is None or s["hasta"] is None:
                    self.exterior_m.setdefault(c, []).append(der[-1])
            if not sin_transporte and not fm.get("restoImpermeable"):
                der.append(neg(self._termino(v, f"resto.{c}", "caudal_masico", c)))
                self.exterior_m.setdefault(c, []).append(der[-1])
            for rol, signo in (("generacion", 1), ("consumo", -1)):
                if not fuentes[rol]:
                    continue
                if uniforme[rol]:
                    if vid not in self.V:
                        raise NoGenerable(f"volumen {vid}: una fuente uniforme por volumen necesita el volumen del dominio como dato")
                    g = prod(self._termino(v, f"{rol}.{c}", "tasa_volumetrica_masica", c), self.V[vid])
                else:
                    g = self._termino(v, f"{rol}.{c}", "caudal_masico", c)
                der.append(g if signo > 0 else neg(g))
                self.exterior_m.setdefault(c, []).append(der[-1])
                self.restricciones.append({"expresion": self._termino(v, f"{rol}.{c}", "tasa_volumetrica_masica" if uniforme[rol] else "caudal_masico", c),
                                           "tipo": "no_negativo", "descripcion": f"volumen {vid}: {rol} es una tasa bruta no negativa"})
            if not materia:
                der = []                       # sin balance de materia: la cantidad declarada es constante
                self.exterior_m.pop(c, None)
            if not acumula:
                raise NoGenerable(f"volumen {vid}: sin acumulación el balance es algebraico (estacionario): pendiente de los solvers")
            u = self.masa[(vid, c)]["id"]
            self.ecuaciones.append({"id": f"materia.{vid}.{c}", "izquierda": {"tipo": "derivada", "expresion": sim(u), "respecto": "t", "orden": 1},
                                    "derecha": suma(*der)})
            ini = v["inicial"]
            if ini.get("tipo") == "por_datos" or "cantidades" not in ini:
                raise NoGenerable(f"volumen {vid}: faltan las cantidades iniciales")
            cant = ini["cantidades"]
            did = cant["datoIds"].get(str(c))
            if did is None:
                raise NoGenerable(f"volumen {vid}: falta la cantidad inicial del componente {c}")
            m0 = self.dato(did, "masa", {}) if cant["base"] == "masica" else prod(num(self._M(c, vid)), self.dato(did, "cantidad", {}))
            self.condiciones.append({"id": f"inicial.{u}", "tipo": "inicial", "dominioId": "it",
                                     "ecuacion": {"id": f"inicial.{u}.eq", "izquierda": sim(u), "derecha": m0}})
            self.restricciones.append({"simboloId": u, "tipo": "no_negativo"})

    def _termino(self, v, clave, magnitud, c=None):
        did = v.get("terminos", {}).get(clave)
        if did is None:
            raise NoGenerable(f"volumen {v['id']}: sus supuestos conservan el término {clave} y no tiene dato")
        k = (v["id"], clave)
        if k not in self._cache:
            self._cache[k] = self.dato(did, magnitud, {**self.alias_global, **self._local(v, c)}, f"volumenes.{v['id']}.terminos.{clave}")
        return self._cache[k]

    # --- energía -------------------------------------------------------------------------------
    def _preparar_energia(self, v):
        vid, fe, t = v["id"], v["supuestos"]["energia"], v["termodinamica"]
        if fe is None:
            raise NoGenerable(f"volumen {vid}: balance de energía activo sin su formulación")
        if t["supuesto"] != "u_lineal":
            raise NoGenerable(f"volumen {vid}: el estado no se evalúa; declara u(T) (u_lineal) o un paquete termodinámico")
        motivos = []
        if fe.get("forma") != "total":
            motivos.append("la energía debe estar en forma total (Gauss, Reynolds y puertos)")
        if fe.get("estacionario") or fe.get("sinAcumulacionTotal"):
            motivos.append("sin acumulación el balance es algebraico (estacionario)")
        if not fe.get("sinCinetica"):
            motivos.append("la energía cinética no se ha declarado despreciable y u(T) no la contiene")
        if not fe.get("uniforme"):
            motivos.append("U = m u(T) exige estado térmico uniforme")
        if not (fe.get("monofasico") and fe.get("sinCambioFase")):
            motivos.append("u(T) lineal exige régimen monofásico sin cambio de fase")
        if not fe.get("separarPresion"):
            motivos.append("los esfuerzos deben separarse en presión y esfuerzo viscoso")
        if motivos:
            raise NoGenerable(f"volumen {vid}: " + "; ".join(motivos))
        p = t.get("parametros")
        if not p:
            raise NoGenerable(f"volumen {vid}: u(T) sin sus parámetros (c, u_ref, T_ref, T_min, T_max)")
        c = self.constante(p["cId"], "capacidad_calorifica_especifica")
        uref = self.constante(p["uRefId"], "energia_especifica")
        Tref = self.constante(p["TRefId"], "temperatura")
        Tmin = self.constante(p["TMinId"], "temperatura")
        Tmax = self.constante(p["TMaxId"], "temperatura")
        if None in (c, uref, Tref, Tmin, Tmax):
            raise NoGenerable(f"volumen {vid}: los parámetros de u(T) deben ser constantes")
        if not c > 0 or not Tmax > Tmin:
            raise NoGenerable(f"volumen {vid}: u(T) necesita c > 0 y T_max > T_min")
        rho = self.dato(p["rhoId"], "densidad", {}) if p.get("rhoId") else None
        U = self.campo(f"U_{vid}", {"M": 1, "L": 2, "T": -2}, "J")
        mt = self.alias_global[f"m_total_{vid}"]
        T = suma(num(Tref), div(suma(div(U, mt), num(-uref)), num(c)))
        self.energia[vid] = {"U": U, "T": T, "c": c, "uref": uref, "Tref": Tref, "Tmin": Tmin, "Tmax": Tmax, "rho": rho}
        self.alias_global[f"T_{vid}"] = T
        self.alias_global[f"U_{vid}"] = U

    def _u(self, vid, T):
        e = self.energia[vid]
        return suma(num(e["uref"]), prod(num(e["c"]), suma(T, num(-e["Tref"]))))

    def _energia(self, v):
        vid, fe, fm = v["id"], v["supuestos"]["energia"], self.fm[v["id"]]
        e = self.energia[vid]
        fija = fm.get("fija")
        P = None
        if v["frontera"]["tipo"] == "presion_prescrita":
            P = self.dato(v["frontera"]["presionId"], "presion", {"t": sim("t")})
        entalpia = fe.get("entalpia")
        loc = self._local(v)
        der = []
        for s in self.m["corrientes"]:
            B = (1 if s["hasta"] == vid else 0) - (1 if s["desde"] == vid else 0)
            if B == 0:
                continue
            q = suma(*[self.caudal[(s["id"], c)] for c in s["componenteIds"]])   # másico, sentido desde -> hasta
            if es_cero(q):
                continue
            hacia = q if B > 0 else neg(q)                                         # positivo si entra a v
            otro = s["desde"] if B > 0 else s["hasta"]
            if P is None or e["rho"] is None:
                raise NoGenerable(f"volumen {vid}: con corrientes, la energía de flujo necesita presión impuesta y densidad (p/rho)")
            pv = div(P, e["rho"])
            h = lambda u_: suma(u_, pv) if entalpia else u_                       # noqa: E731
            h_v = h(self._u(vid, e["T"]))
            if otro is None:
                Te = (s.get("estadoExterior") or {}).get("temperaturaId")
                h_e = h(self._u(vid, self.dato(Te, "temperatura", {"t": sim("t")}))) if Te else None
            else:
                if otro not in self.energia:
                    raise NoGenerable(f"corriente {s['id']}: su otro extremo ({otro}) no tiene balance de energía")
                ot = self.energia[otro]
                h_e = h(self._u(otro, ot["T"]))
            entra, sale = fun("max", hacia, num(0)), fun("min", hacia, num(0))
            if h_e is None:
                # Sin estado exterior declarado: la corriente solo puede sacar; si se invierte, el cálculo se detiene.
                self.restricciones.append({"expresion": neg(hacia), "tipo": "no_negativo",
                                           "descripcion": f"corriente {s['id']}: entra a {vid} y no tiene estado exterior declarado"})
                E_s = prod(hacia, h_v)
                h_don = h_v
            else:
                E_s = suma(prod(entra, h_e), prod(sale, h_v))
                h_don = suma(prod(fun("max", fun("min", prod(hacia, num(1e300)), num(1)), num(0)), h_e),
                             prod(fun("max", fun("min", prod(neg(hacia), num(1e300)), num(1)), num(0)), h_v))
            if not entalpia:
                E_s = suma(E_s, prod(hacia, pv))
            der.append(E_s)
            if otro is None:
                self.exterior_E.append(E_s)
            self.observables += [{"id": f"corriente.{s['id']}.mdot", "nombre": f"Caudal · corriente {s['id']}", "unidadSI": "kg/s", "expresion": q},
                                 {"id": f"corriente.{s['id']}.h", "nombre": f"Entalpía del donante · corriente {s['id']}", "unidadSI": "J/kg", "expresion": h_don},
                                 {"id": f"corriente.{s['id']}.E", "nombre": f"Energía hacia {vid} · corriente {s['id']}", "unidadSI": "W", "expresion": E_s}]
        for clave, activo, nombre in (("calor", not (fe.get("adiabatico") or fe.get("sinConduccionLocal")), "Calor hacia el volumen"),
                                      ("trabajo_viscoso", not fe.get("sinTrabajoViscoso"), "Trabajo viscoso hacia el volumen"),
                                      ("fuerzas", not fe.get("sinFuerzasVolumen"), "Trabajo de fuerzas de volumen"),
                                      ("fuente", not fe.get("sinFuenteVolumetrica"), "Aporte volumétrico integrado")):
            if activo:
                x = self._termino_e(v, clave, loc)
                der.append(x)
                self.exterior_E.append(x)
                self.observables.append({"id": f"volumen.{vid}.{clave}", "nombre": nombre, "unidadSI": "W", "expresion": x})
        if not fija:
            if P is None or e["rho"] is None:
                raise NoGenerable(f"volumen {vid}: la frontera móvil necesita presión impuesta y densidad para su trabajo p dV/dt")
            dm = suma(*[self._dmdt(v, c) for c in v["componenteIds"]])
            Wb = prod(P, div(dm, e["rho"]))
            der.append(neg(Wb))
            self.exterior_E.append(neg(Wb))
            self.observables.append({"id": f"volumen.{vid}.trabajo_frontera", "nombre": "Trabajo de presión de la frontera", "unidadSI": "W", "expresion": Wb})
        self.observables.append({"id": f"volumen.{vid}.T", "nombre": "Temperatura", "unidadSI": "K", "expresion": e["T"]})
        self.observables.append({"id": f"volumen.{vid}.dUdt", "nombre": "Acumulación energética", "unidadSI": "W", "expresion": suma(*der)})
        if e["rho"] is not None:
            self.observables.append({"id": f"volumen.{vid}.V", "nombre": "Volumen ocupado", "unidadSI": "m^3", "expresion": div(self.alias_global[f"m_total_{vid}"], e["rho"])})
        elif vid in self.V:
            self.observables.append({"id": f"volumen.{vid}.V", "nombre": "Volumen geométrico", "unidadSI": "m^3", "expresion": self.V[vid]})
        Uid = e["U"]["id"]
        self.ecuaciones.append({"id": f"energia.{vid}", "izquierda": {"tipo": "derivada", "expresion": sim(Uid), "respecto": "t", "orden": 1},
                                "derecha": suma(*der)})
        ini = v["inicial"].get("energia")
        if ini is None:
            raise NoGenerable(f"volumen {vid}: falta la energía o la temperatura inicial")
        m0 = suma(*[self._inicial_masa(v, c) for c in v["componenteIds"]])
        U0 = self.dato(ini["datoId"], "energia", {}) if ini["tipo"] == "U" else prod(m0, self._u(vid, self.dato(ini["datoId"], "temperatura", {})))
        self.condiciones.append({"id": f"inicial.{Uid}", "tipo": "inicial", "dominioId": "it",
                                 "ecuacion": {"id": f"inicial.{Uid}.eq", "izquierda": sim(Uid), "derecha": U0}})
        self.restricciones.append({"expresion": suma(e["T"], num(-e["Tmin"])), "tipo": "no_negativo",
                                   "descripcion": f"volumen {vid}: T >= T_min, dominio del supuesto u(T)"})
        self.restricciones.append({"expresion": suma(num(e["Tmax"]), neg(e["T"])), "tipo": "no_negativo",
                                   "descripcion": f"volumen {vid}: T <= T_max, dominio del supuesto u(T)"})

    def _termino_e(self, v, clave, loc):
        did = v.get("terminos", {}).get(clave)
        if did is None:
            raise NoGenerable(f"volumen {v['id']}: sus supuestos conservan el término de energía {clave} y no tiene dato")
        return self.dato(did, "potencia", {**self.alias_global, **loc}, f"volumenes.{v['id']}.terminos.{clave}")

    def _dmdt(self, v, c):
        u = self.masa[(v["id"], c)]["id"]
        return next(e["derecha"] for e in self.ecuaciones if e["izquierda"]["expresion"]["id"] == u)

    def _inicial_masa(self, v, c):
        u = self.masa[(v["id"], c)]["id"]
        return next(x["ecuacion"]["derecha"] for x in self.condiciones if x["ecuacion"]["izquierda"]["id"] == u)

    def _auxiliares(self):
        """Cierres de presupuesto: cada estado frente a la integral de su propio balance, y el sistema
        completo frente a lo que cruza su frontera (las transferencias internas deben anularse)."""
        estados = [(e["izquierda"]["expresion"]["id"], e["derecha"]) for e in self.ecuaciones]
        ini = {x["ecuacion"]["izquierda"]["id"]: x["ecuacion"]["derecha"] for x in self.condiciones}
        es_E = lambda u: u.startswith("U_")                                   # noqa: E731
        for u, f in estados:
            a = self.campo(f"aux_{u}", {"M": 1, "L": 2, "T": -2} if es_E(u) else {"M": 1}, "J" if es_E(u) else "kg")
            self._ec(a["id"], f, num(0))
            self.verificaciones.append({"id": f"estado.{u}", "descripcion": f"{u}(t) - {u}(0) - integral de su balance",
                                        "expresion": suma(sim(u), neg(ini[u]), neg(a)), "escala": suma(fun("abs", sim(u)), fun("abs", a)), "tolerancia": 1e-7})
        for c in sorted({c for (_, c) in self.masa}):
            ms = [self.masa[(v["id"], c)] for v in self.m["volumenes"] if (v["id"], c) in self.masa]
            a = self.campo(f"aux_global_{self.comp[c]['simbolo']}", {"M": 1}, "kg")
            self._ec(a["id"], suma(*self.exterior_m.get(c, [])), num(0))
            self.verificaciones.append({"id": f"global.materia.{c}", "descripcion": f"sum_v m_{c} - sum_v m_{c}(0) - integral de lo que cruza la frontera del sistema",
                                        "expresion": suma(*ms, *[neg(ini[x["id"]]) for x in ms], neg(a)),
                                        "escala": suma(*[fun("abs", x) for x in ms], fun("abs", a)), "tolerancia": 1e-7})
        if self.energia:
            Us = [e["U"] for e in self.energia.values()]
            a = self.campo("aux_global_E", {"M": 1, "L": 2, "T": -2}, "J")
            self._ec(a["id"], suma(*self.exterior_E), num(0))
            self.verificaciones.append({"id": "global.energia", "descripcion": "sum_v U - sum_v U(0) - integral de lo que cruza la frontera del sistema",
                                        "expresion": suma(*Us, *[neg(ini[x["id"]]) for x in Us], neg(a)),
                                        "escala": suma(*[fun("abs", x) for x in Us], fun("abs", a)), "tolerancia": 1e-7})

    def _ec(self, u, f, x0):
        self.ecuaciones.append({"id": f"auxiliar.{u}", "izquierda": {"tipo": "derivada", "expresion": sim(u), "respecto": "t", "orden": 1}, "derecha": f})
        self.condiciones.append({"id": f"inicial.{u}", "tipo": "inicial", "dominioId": "it", "ecuacion": {"id": f"inicial.{u}.eq", "izquierda": sim(u), "derecha": x0}})

    def _modelo(self):
        self._auxiliares()
        m = dict(self.m)
        m["matematico"] = {"id": f"{m['id']}.balances", "revision": 1, "simbolos": self.simbolos, "funciones": [],
                           "ecuaciones": self.ecuaciones,
                           "dominios": [{"id": "it", "variableId": "t", "desde": num(0), "hasta": num(1)}],
                           "condiciones": self.condiciones}
        m["restricciones"] = self.restricciones
        m["observables"] = self.observables
        m["verificaciones"] = self.verificaciones
        return m


def generar(modelo):
    """Modelo común con volúmenes de estado supuesto -> el mismo modelo con sus ecuaciones explícitas."""
    return _Generador(modelo).generar()
