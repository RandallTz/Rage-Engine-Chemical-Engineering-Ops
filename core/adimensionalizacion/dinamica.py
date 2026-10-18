"""
Escalas, estabilidad lineal y continuacion de una formulacion en forma de
evolucion  du_i/dtau = F_i(u, du/dxi, d2u/dxi2, ...), con valores numericos.

Linealizacion. En un estado homogeneo u*, cada derivada espacial de orden n
de cada campo se trata como una variable independiente w_{j,n} (vale 0 en
u*). Las derivadas parciales de F respecto de u_j y de w_{j,n} se obtienen
por paso complejo (exactas a precision de maquina para funciones
analiticas):

    J = dF/du,    C_n = dF/dw_n   (matrices campo x campo).

Para una perturbacion exp(i k xi + sigma tau), d^n/dxi^n -> (i k)^n, asi que
sigma(k) son los autovalores de  M(k) = J + sum_n (i k)^n C_n.  Es exacto
para el problema linealizado en un dominio infinito; en un dominio finito con
flujo nulo los modos admisibles son k = n pi / L.

Estados homogeneos: F(u) = 0 con derivadas nulas. Busqueda finita en una
caja (barrido con cambio de signo y Brent para un campo; arranques en malla
con Newton-Powell para varios). Se publica la caja: puede haber estados fuera.
"""

import math

import numpy as np
from scipy import optimize

from .estudio import clave_derivada, estado, requiere
from .numerico import NoEvaluable

H_COMPLEJO = 1e-30
MAX_ESTADOS = 20


def _evolucion_o_motivo(sistema):
    if sistema.evolucion is None:
        return estado("no_soportado", "la formulacion no esta en forma de evolucion: " + "; ".join(sistema.problemas[:3]))
    return None


def _caja(cx, sistema, B):
    caja = []
    for item in sistema.evolucion:
        s = cx.ctx.signo(item["campo"])
        caja.append((0.0, B) if s == "positivo" else (-B, 0.0) if s == "negativo" else (-B, B))
    return caja


def _F(sistema, valores=None):
    def f(u):
        return sistema.rhs_homogeneo(u, valores)
    return f


def jacobiano(sistema, u, valores=None):
    n = len(u)
    J = np.zeros((n, n))
    for j in range(n):
        x = np.array(u, dtype=complex)
        x[j] += 1j * H_COMPLEJO
        J[:, j] = np.imag(sistema.rhs_homogeneo(x, valores)) / H_COMPLEJO
    return J


def coeficientes_derivada(sistema, u, coordenada, orden, valores=None):
    """C_orden = dF/dw_{j,orden} en el estado homogeneo u."""
    campos = [item["campo"] for item in sistema.evolucion]
    n = len(campos)
    C = np.zeros((n, n))
    coords = set(sistema.cx.coordenadas)
    for j, cj in enumerate(campos):
        def derivadas(a, cj=cj):
            if a[0] == "o":
                raise NoEvaluable("operador", "operador sin desarrollar")
            clave = clave_derivada(a, set(campos))
            if clave is None:
                if a[2] in coords:
                    raise NoEvaluable("derivada_no_lineal", "derivada de una funcion declarada o derivada mixta: no se linealiza")
                raise NoEvaluable("derivada", "derivada temporal en el miembro derecho")
            if clave == (cj, coordenada, orden):
                return 1j * H_COMPLEJO
            return 0.0
        valores_campos = {c: complex(u[i]) for i, c in enumerate(campos)}
        r = sistema.rhs(valores_campos, derivadas, valores)
        C[:, j] = np.imag(np.array(r, dtype=complex)) / H_COMPLEJO
    return C


def _ordenes(sistema):
    return sorted({t.clase["ordenEspacial"] for item in sistema.evolucion for t in item["resto"] if t.clase["ordenEspacial"]})


def estados_homogeneos(cx, sistema, valores=None, B=None):
    B = B or cx.opciones.get("cajaEstados", 10.0)
    caja = _caja(cx, sistema, B)
    f = _F(sistema, valores)
    n = len(caja)
    encontrados = []

    def agregar(x):
        x = np.asarray(x, dtype=float)
        if not np.all(np.isfinite(x)):
            return
        r = f(x)
        if not np.all(np.isfinite(r)) or np.max(np.abs(r)) > 1e-9 * max(1.0, np.max(np.abs(x))):
            return
        for y in encontrados:
            if np.max(np.abs(y - x)) <= 1e-7 * max(1.0, np.max(np.abs(x))):
                return
        encontrados.append(x)

    if n == 1:
        a, b = caja[0]
        xs = np.linspace(a, b, 4001)
        with np.errstate(all="ignore"):
            try:
                ys = np.real(np.asarray(f([xs])[0], dtype=complex)) * np.ones_like(xs)
            except NoEvaluable:
                ys = np.array([_seguro(f, np.array([x]))[0] for x in xs])
        finitos = np.isfinite(ys)
        if finitos.any() and np.all(ys[finitos] == 0):
            # F = 0 para todo valor constante: continuo de estados homogeneos.
            centro = 0.0 if a <= 0.0 <= b else 0.5 * (a + b)
            return [np.array([centro])], caja, True
        for i in range(len(xs)):
            if ys[i] == 0:
                agregar([xs[i]])
            if i and np.isfinite(ys[i - 1]) and np.isfinite(ys[i]) and ys[i - 1] * ys[i] < 0:
                try:
                    raiz = optimize.brentq(lambda x: float(np.real(f(np.array([x]))[0])), xs[i - 1], xs[i], xtol=1e-14, rtol=1e-13)
                    agregar([raiz])
                except (ValueError, NoEvaluable):
                    pass
    else:
        m = max(2, int(round(300 ** (1.0 / n))))
        rejillas = [np.linspace(lo, hi, m) for lo, hi in caja]
        arranques = np.array(np.meshgrid(*rejillas)).reshape(n, -1).T
        rng = np.random.default_rng(0)
        aleatorios = np.array([[rng.uniform(lo, hi) for lo, hi in caja] for _ in range(100)])
        for x0 in np.vstack([arranques, aleatorios]):
            try:
                sol = optimize.root(lambda x: f(x), x0, jac=lambda x: jacobiano(sistema, x, valores), method="hybr", options={"xtol": 1e-13})
            except (NoEvaluable, ValueError, FloatingPointError, OverflowError, ZeroDivisionError):
                continue
            if sol.success:
                agregar(sol.x)
    margen = [(lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo)) for lo, hi in caja]
    encontrados = [x for x in encontrados if all(lo <= xi <= hi for xi, (lo, hi) in zip(x, margen))]
    encontrados.sort(key=lambda x: tuple(x))
    # Muchos estados distintos indican una variedad continua de equilibrios.
    return encontrados[:MAX_ESTADOS], caja, len(encontrados) > MAX_ESTADOS


def _seguro(f, x):
    try:
        return np.real(np.asarray(f(x), dtype=complex))
    except (NoEvaluable, ValueError, FloatingPointError, ZeroDivisionError, OverflowError):
        return np.array([np.nan])


def _dispersion(J, Cs, ks):
    reales, imags = [], []
    for k in ks:
        M = J.astype(complex)
        for orden, C in Cs.items():
            M = M + (1j * k) ** orden * C
        ev = np.linalg.eigvals(M)
        i = int(np.argmax(ev.real))
        reales.append(float(ev.real[i]))
        imags.append(float(ev.imag[i]))
    return np.array(reales), np.array(imags)


def _escala_tol(J, Cs):
    escala = max([np.max(np.abs(J))] + [np.max(np.abs(C)) for C in Cs.values()] + [1e-300])
    return 1e-9 * escala


def estabilidad(cx, sistema):
    motivo = _evolucion_o_motivo(sistema) or requiere(sistema)
    if motivo:
        return motivo
    explicitos = sistema.explicitas()
    if explicitos:
        return estado("no_soportado", "el miembro derecho depende explicitamente de " + ", ".join(explicitos) + ": no hay estados homogeneos constantes")
    estados, caja, continuo = estados_homogeneos(cx, sistema)
    campos = [item["campo"] for item in sistema.evolucion]
    if not estados:
        return estado("calculado", "no se encontraron estados homogeneos en la caja de busqueda", caja=caja, estados=[], campos=campos)
    ordenes = _ordenes(sistema)
    resultados = []
    for u in estados:
        J = jacobiano(sistema, u)
        ev = np.linalg.eigvals(J)
        item = {"u": {c: float(u[i]) for i, c in enumerate(campos)}, "jacobiano": J.tolist(),
                "autovalores": [{"re": float(x.real), "im": float(x.imag)} for x in ev]}
        tol = _escala_tol(J, {})
        homogeneo = "estable" if np.max(ev.real) < -tol else ("marginal" if np.max(ev.real) <= tol else "inestable")
        item["homogeneo"] = homogeneo
        por_coord = []
        for coord in cx.coordenadas:
            try:
                Cs = {o: coeficientes_derivada(sistema, u, coord, o) for o in ordenes}
            except NoEvaluable as e:
                por_coord.append({"coordenada": coord, "estado": "no_soportado", "motivo": e.mensaje})
                continue
            Cs = {o: C for o, C in Cs.items() if np.any(C)}
            if not Cs:
                continue
            tol = _escala_tol(J, Cs)
            C2 = Cs.get(2)
            rJ = max(np.max(np.abs(ev)), 1e-12)
            rD = max(np.max(np.abs(np.linalg.eigvals(C2))) if C2 is not None else 0.0, 1e-300)
            dom = sistema.dominios.get(coord)
            L = (dom["hasta"] - dom["desde"]) if dom and dom["desde"] is not None and dom["hasta"] is not None else None
            kmax = cx.opciones.get("estabilidad", {}).get("kMax") or max(10.0, 6.0 * math.sqrt(rJ / rD) if C2 is not None else 10.0,
                                                                         (40 * math.pi / L) if L else 0.0)
            ks = np.linspace(0.0, kmax, 801)
            re, im = _dispersion(J, Cs, ks)
            imax = int(np.argmax(re))
            clase = "estable"
            if re[0] > tol:
                clase = "oscilatoria_homogenea" if abs(im[0]) > tol else "inestable_homogenea"
            elif np.any(re[1:] > tol):
                clase = "turing" if abs(im[imax]) <= 1e-7 * max(1.0, abs(re[imax])) else "onda"
            banda = None
            if clase in ("turing", "onda"):
                inest = ks[re > tol]
                banda = {"desde": float(inest.min()), "hasta": float(inest.max())}
            r = {"coordenada": coord, "estado": "calculado", "clase": clase,
                 "coeficientes": {str(o): C.tolist() for o, C in Cs.items()},
                 "k": ks[::8].tolist(), "reSigma": re[::8].tolist(), "imSigma": im[::8].tolist(),
                 "kCritico": float(ks[imax]) if clase in ("turing", "onda") else None,
                 "sigmaMaximo": float(re[imax]), "banda": banda}
            if L and L > 0:
                modos = []
                for nmodo in range(1, 401):
                    kn = nmodo * math.pi / L
                    rn, inn = _dispersion(J, Cs, [kn])
                    if rn[0] > tol:
                        modos.append({"n": nmodo, "k": kn, "re": float(rn[0]), "im": float(inn[0])})
                r["dominio"] = {"longitud": L, "modosInestablesNeumann": modos[:50], "nota": "modos cos(n pi xi / L) de un dominio con flujo nulo en ambos extremos"}
            por_coord.append(r)
        item["espacial"] = por_coord
        resultados.append(item)
    r = {"estado": "calculado",
         "motivo": "estados homogeneos por busqueda finita en la caja; jacobiano y coeficientes de derivada por paso complejo; sigma(k) = autovalores de J + sum (i k)^n C_n",
         "campos": campos, "caja": [list(c) for c in caja], "estados": resultados}
    if continuo:
        r["continuo"] = True
        r["notaContinuo"] = ("todo valor constante es un estado homogeneo (la reaccion se anula identicamente): se analiza un representante"
                             if len(campos) == 1 else f"hay mas de {MAX_ESTADOS} estados distintos (posible variedad continua de equilibrios): se publican los primeros {MAX_ESTADOS}")
    return r


# --- Escalas, malla y rigidez -------------------------------------------------------

def _estado_referencia(cx, sistema):
    try:
        estados, _, _ = estados_homogeneos(cx, sistema)
    except NoEvaluable:
        estados = []
    for u in estados:
        ev = np.linalg.eigvals(jacobiano(sistema, u))
        if np.max(ev.real) < 0:
            return u, "estado homogéneo estable"
    if estados:
        return estados[0], "estado homogéneo (no estable)"
    return np.ones(len(sistema.evolucion)), "u = 1 en cada campo (no se encontró estado homogéneo)"


def _operador_discreto(J, Cs, N, L):
    """Jacobiano semidiscreto con diferencias centradas en N nodos interiores
    (extremos de Dirichlet homogeneo)."""
    n = J.shape[0]
    h = L / (N + 1)
    M = np.zeros((n * N, n * N))
    C1, C2 = Cs.get(1, np.zeros((n, n))), Cs.get(2, np.zeros((n, n)))
    for i in range(N):
        M[i * n:(i + 1) * n, i * n:(i + 1) * n] = J - 2 * C2 / h ** 2
        if i > 0:
            M[i * n:(i + 1) * n, (i - 1) * n:i * n] = C2 / h ** 2 - C1 / (2 * h)
        if i < N - 1:
            M[i * n:(i + 1) * n, (i + 1) * n:(i + 2) * n] = C2 / h ** 2 + C1 / (2 * h)
    return M


def escalas(cx, sistema):
    motivo = _evolucion_o_motivo(sistema) or requiere(sistema)
    if motivo:
        return motivo
    u, origen = _estado_referencia(cx, sistema)
    campos = [item["campo"] for item in sistema.evolucion]
    J = jacobiano(sistema, u)
    rJ = float(np.max(np.abs(np.linalg.eigvals(J)))) if J.size else 0.0
    tiempos = {"reaccion": (1.0 / rJ) if rJ > 0 else None}
    ordenes = _ordenes(sistema)
    por_coord = []
    for coord in cx.coordenadas:
        dom = sistema.dominios.get(coord)
        L = (dom["hasta"] - dom["desde"]) if dom and dom["desde"] is not None and dom["hasta"] is not None else None
        try:
            Cs = {o: coeficientes_derivada(sistema, u, coord, o) for o in ordenes}
        except NoEvaluable as e:
            por_coord.append({"coordenada": coord, "estado": "no_soportado", "motivo": e.mensaje})
            continue
        Cs = {o: C for o, C in Cs.items() if np.any(C)}
        if not Cs:
            continue
        D = float(np.max(np.abs(np.linalg.eigvals(Cs[2])))) if 2 in Cs else 0.0
        V = float(np.max(np.abs(np.linalg.eigvals(Cs[1])))) if 1 in Cs else 0.0
        r = {"coordenada": coord, "estado": "calculado", "difusividad": D, "velocidad": V, "longitud": L}
        if L:
            r["tiempoDifusion"] = L ** 2 / D if D else None
            r["tiempoConveccion"] = L / V if V else None
        longitudes = []
        if D and V:
            longitudes.append(("difusión/convección", D / V))
        if D and rJ:
            longitudes.append(("difusión/reacción", math.sqrt(D / rJ)))
        r["longitudesInternas"] = [{"balance": b, "longitud": x} for b, x in longitudes]
        if L and D:
            n_pe = math.ceil(L * V / (2 * D)) + 1 if V else 2
            n_capa = max((math.ceil(10 * L / x) + 1 for _, x in longitudes), default=2)
            N = min(max(41, n_pe, n_capa), 2001)
            h = L / (N - 1)
            r["malla"] = {"nodosPeclet": n_pe, "nodosCapas": n_capa, "nodosRecomendados": N,
                          "pecletCelda": V * h / D if V else 0.0,
                          "criterio": "Péclet de celda ≤ 2 y al menos 10 nodos por cada longitud interna"}
            limites = {"difusion": h ** 2 / (2 * D)}
            if V:
                limites["conveccion"] = h / V
            if rJ:
                limites["reaccion"] = 2.0 / rJ
            r["pasoExplicitoMaximo"] = {"eulerExplicito": min(limites.values()), "porMecanismo": limites}
            Nm = min(N - 2, max(10, 400 // max(1, len(campos))))
            M = _operador_discreto(J, Cs, Nm, L)
            ev = np.linalg.eigvals(M)
            neg = np.abs(ev.real[ev.real < -1e-14])
            if len(neg):
                r["rigidez"] = {"nodos": Nm + 2, "radioEspectral": float(np.max(np.abs(ev))), "lentoMasRapido": float(np.min(neg)),
                                "cociente": float(np.max(np.abs(ev)) / np.min(neg)),
                                "recomendacion": "implícito (BDF, Radau)" if np.max(np.abs(ev)) / np.min(neg) > 1e3 else "explícito adaptativo (RK45)",
                                "nota": "autovalores del jacobiano semidiscreto con diferencias centradas y extremos de Dirichlet homogéneo"}
        por_coord.append(r)
    return {"estado": "calculado",
            "motivo": "coeficientes efectivos de la linealizacion en el estado de referencia; tiempos, longitudes internas, malla y rigidez del operador discreto",
            "referencia": {"u": {c: float(u[i]) for i, c in enumerate(campos)}, "origen": origen},
            "tiempos": tiempos, "radioJacobiano": rJ, "coordenadas": por_coord}


# --- Continuacion -----------------------------------------------------------------

def continuacion(cx, sistema):
    motivo = _evolucion_o_motivo(sistema) or requiere(sistema)
    if motivo:
        return motivo
    op = cx.opciones.get("continuacion")
    if not op:
        return estado("requiere_datos", "indique el parametro y el intervalo (estudio.continuacion)")
    pid = op["parametroId"]
    if pid not in cx.valores:
        return estado("requiere_datos", f"falta el valor de {pid}", faltan=[pid])
    if sistema.explicitas():
        return estado("no_soportado", "el miembro derecho depende explicitamente de las variables independientes")
    from .dimensional import cantidad_SI
    unidad = op.get("unidad") or (cx.simbolos_modelo[pid]["unidad"] if pid in cx.simbolos_modelo else None)
    a, b = op["desde"], op["hasta"]
    if unidad:
        a, _ = cantidad_SI(a, unidad)
        b, _ = cantidad_SI(b, unidad)
    if not a < b:
        return estado("rechazado", "el intervalo de continuacion debe ser creciente")
    if not any(pid in {x[1] for m in t.C.t for x, _ in m if x[0] == "s"} | _simbolos_abs(t.C)
               for item in sistema.evolucion for t in item["resto"] + [item["temporal"]]):
        return estado("no_aplicable", f"{pid} no aparece en los coeficientes de la formulacion: no cambia sus estados")
    R = b - a
    p0 = min(max(cx.valores[pid], a), b)

    def vals(p):
        v = dict(cx.valores)
        v[pid] = p
        return v

    def G(x):
        return sistema.rhs_homogeneo(x[:-1], vals(a + R * x[-1]))

    def jac(x):
        n = len(x) - 1
        Ju = jacobiano(sistema, x[:-1], vals(a + R * x[-1]))
        y = sistema.rhs_homogeneo(x[:-1].astype(complex), vals(a + R * (x[-1] + 1j * H_COMPLEJO)))
        Jl = np.imag(y) / H_COMPLEJO
        return np.hstack([Ju, Jl.reshape(n, 1)])

    inicios, _, _ = estados_homogeneos(cx, sistema, vals(p0))
    campos = [item["campo"] for item in sistema.evolucion]
    pasos_max = op.get("pasosMax", 600)
    B = cx.opciones.get("cajaEstados", 10.0) * 10
    ramas, especiales, visitados = [], [], []

    def tangente(x, previa=None):
        Jx = jac(x)
        _, _, vh = np.linalg.svd(Jx)
        t = vh[-1]
        if previa is not None and np.dot(t, previa) < 0:
            t = -t
        return t / np.linalg.norm(t)

    def estable(x):
        ev = np.linalg.eigvals(jacobiano(sistema, x[:-1], vals(a + R * x[-1])))
        return ev

    def refinar_pliegue(z, t):
        """Punto limite exacto: F = 0, F_u v = 0, |v| = 1 (Newton)."""
        n = len(z) - 1
        Ju = jacobiano(sistema, z[:-1], vals(a + R * z[-1]))
        _, _, vh = np.linalg.svd(Ju)
        v0 = vh[-1]

        def fun(w):
            u, lam, v = w[:n], w[n], w[n + 1:]
            Jw = jacobiano(sistema, u, vals(a + R * lam))
            return np.concatenate([sistema.rhs_homogeneo(u, vals(a + R * lam)), Jw @ v, [np.dot(v, v0) - 1.0]])
        sol = optimize.root(fun, np.concatenate([z, v0]), method="hybr", options={"xtol": 1e-13})
        if sol.success and np.max(np.abs(sol.fun)) < 1e-9:
            return sol.x[:n + 1]
        return z

    for u0 in inicios:
        x0 = np.concatenate([u0, [(p0 - a) / R]])
        if any(np.max(np.abs(v - x0)) < 0.06 for v in visitados):
            continue
        puntos_rama = []
        for sentido in (1, -1):
            x = x0.copy()
            t = tangente(x)
            t = t * sentido * (1 if t[-1] >= 0 else -1) if abs(t[-1]) > 1e-12 else t * sentido
            ds = 0.01
            serie = []
            for _ in range(pasos_max):
                ok = False
                while ds > 1e-8:
                    xp = x + ds * t
                    y = xp.copy()
                    for _ in range(20):
                        F = np.concatenate([G(y), [np.dot(t, y - xp)]])
                        Jx = np.vstack([jac(y), t])
                        try:
                            dy = np.linalg.solve(Jx, -F)
                        except np.linalg.LinAlgError:
                            break
                        y = y + dy
                        if np.max(np.abs(dy)) < 1e-12 * max(1.0, np.max(np.abs(y))):
                            ok = True
                            break
                    if ok and np.max(np.abs(G(y))) < 1e-9 * max(1.0, np.max(np.abs(y))):
                        break
                    ok = False
                    ds /= 2
                if not ok:
                    break
                t_nueva = tangente(y, t)
                serie.append((y.copy(), t_nueva.copy()))
                visitados.append(y.copy())
                x, t = y, t_nueva
                ds = min(ds * 1.5, 0.05)
                if not (-1e-3 <= x[-1] <= 1 + 1e-3) or np.max(np.abs(x[:-1])) > B:
                    break
            if sentido == 1:
                puntos_rama = list(reversed(serie)) + [(x0, tangente(x0))]
            else:
                puntos_rama = puntos_rama + serie
        # Orientacion coherente de las tangentes a lo largo de la rama (la
        # mitad recorrida hacia atras llega con el sentido opuesto).
        orientadas = []
        for y, t in puntos_rama:
            if orientadas and np.dot(orientadas[-1][1], t) < 0:
                t = -t
            orientadas.append((y, t))
        puntos_rama = orientadas
        puntos = []
        previo = None
        for y, t in puntos_rama:
            ev = estable(y)
            p = a + R * y[-1]
            pt = {"p": float(p), "u": {c: float(y[i]) for i, c in enumerate(campos)}, "estable": bool(np.max(ev.real) < 0),
                  "maxRe": float(np.max(ev.real))}
            if previo is not None:
                yp, tp, evp = previo
                if tp[-1] * t[-1] < 0 and abs(tp[-1]) + abs(t[-1]) > 0:
                    w = abs(tp[-1]) / (abs(tp[-1]) + abs(t[-1]))
                    z = refinar_pliegue(yp + w * (y - yp), t)
                    especiales.append({"tipo": "pliegue", "p": float(a + R * z[-1]), "u": {c: float(z[i]) for i, c in enumerate(campos)}})
                cp = [e.real for e in evp if abs(e.imag) > 1e-8]
                cn = [e.real for e in ev if abs(e.imag) > 1e-8]
                if cp and cn and max(cp) * max(cn) < 0:
                    w = abs(max(cp)) / (abs(max(cp)) + abs(max(cn)))
                    z = yp + w * (y - yp)
                    especiales.append({"tipo": "hopf", "p": float(a + R * z[-1]), "u": {c: float(z[i]) for i, c in enumerate(campos)},
                                       "frecuencia": float(abs([e for e in ev if abs(e.imag) > 1e-8][0].imag))})
            puntos.append(pt)
            previo = (y, t, ev)
        puntos = [x for x in puntos if a - 1e-9 * R <= x["p"] <= b + 1e-9 * R]
        if len(puntos) > 400:
            paso = math.ceil(len(puntos) / 400)
            puntos = puntos[::paso] + [puntos[-1]]
        ramas.append({"inicio": {c: float(u0[i]) for i, c in enumerate(campos)}, "puntos": puntos})
    especiales = [e for e in especiales if a <= e["p"] <= b]
    unicos = []
    for e in especiales:
        if not any(x["tipo"] == e["tipo"] and abs(x["p"] - e["p"]) <= 1e-4 * R and all(abs(x["u"][c] - e["u"][c]) < 1e-3 * max(1.0, abs(e["u"][c])) for c in campos) for x in unicos):
            unicos.append(e)
    return {"estado": "calculado",
            "motivo": "continuacion por longitud de arco de F(u; p) = 0 desde los estados homogeneos en el valor dado; pliegues por cambio de signo de dp/ds; Hopf por cruce de un par complejo",
            "parametroId": pid, "intervaloSI": [a, b], "campos": campos, "ramas": ramas, "especiales": unicos}


def _simbolos_abs(P):
    r = set()
    for m in P.t:
        for a, _ in m:
            if a[0] == "f" and a[1] == "abs":
                for q in a[2]:
                    r |= {x[1] for mm in q.t for x, _ in mm if x[0] == "s"}
    return r
