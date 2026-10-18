"""
Paquetes de mezcla del motor independiente: equilibrio multifasico (V, L,
LL, LV, LLV) por minimizacion de la energia de Gibbs, certificado con la
distancia al plano tangente, y operaciones TP, PH, UP, UV y TV.

Modelo fundamental (por fase; especies de core/mezclas_datos.py):

    vapor:   mu_i = g_ig_i(T, P0) + R T ln(y_i P / P0)             (gas ideal)
    liquido: mu_i = g_L_i(T, P) + R T ln(x_i gamma_i(T, x))         (actividad)
             g^E/RT del modelo de liquido; gamma_i = exp(d(n g^E/RT)/dn_i)
             h^E = g^E - T dg^E/dT,  s^E = -dg^E/dT,  v^E = 0 (g^E no depende de P)

con la referencia comun a todos los paquetes de mezcla: gas ideal puro a
298.15 K y 1e5 Pa con h = s = 0 por especie. Cada fase tiene u, h, s, v y g
molares coherentes con esas mu (g = sum x_i mu_i).

Modelos de liquido:
    'ideal' : g^E = 0 (solucion ideal; con vapor ideal, ley de Raoult con
              correccion de Poynting por v_L)
    'nrtl'  : NRTL multicomponente, tau_ij = b_ij / T, G_ij = exp(-alpha_ij tau_ij),
              parametros de la base ChemSep incluida en thermo (IPDB 'ChemSep NRTL').
              Un par sin parametros no se completa con cero: el sistema no se publica.

Equilibrio a (T, P, n): se parte de la fase unica de menor G; se busca la
fase de prueba de menor tm (vapor: minimo analitico; liquido: malla en el
simplex y refinamiento local, hasta 3 componentes); si tm < -TOL_TM se anade
esa fase y se minimiza G sobre el reparto (SLSQP) y se pule la igualdad de
potenciales con Newton; se repite hasta 3 fases. El resultado se certifica
con la prueba de estabilidad completa sobre la mu comun. Las especies
ausentes (n_i = 0) no entran: no se evalua log(0).
"""

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq, minimize

from core import mezclas_datos as datos

R = datos.R
P0 = datos.P0
TOL_TM = 1e-9           # -min tm (adimensional, por mol de fase de prueba): tolerancia de CERTIFICACION
# Se intenta separar una fase en cuanto tm < -TM_INTENTO, y una fase cuenta como ausente por debajo de
# N_AUSENTE * n. Si se intentara solo con tm < -TOL_TM habria una banda de histeresis: estados con una
# traza de vapor de equilibrio declarados monofasicos, y H_eq(T) daria saltos de ~0.1 J en el punto de
# burbuja (confundidos con una meseta por la busqueda PH).
TM_INTENTO = 1e-14
N_AUSENTE = 1e-12
TOL_MU = 1e-10          # |mu_i^a - mu_i^b| / (R T)
P_MAX = 5e5             # vapor ideal: alcance declarado
P_MIN = 100.0
MAX_FASES = 3


class FueraDeAlcance(Exception):
    def __init__(self, motivo, mensaje, **datos_):
        super().__init__(mensaje)
        self.motivo, self.mensaje, self.datos = motivo, mensaje, datos_


# ----------------------------------------------------------------------
# Modelos de liquido (energia de Gibbs de exceso)
# ----------------------------------------------------------------------
class LiquidoIdeal:
    nombre = "solución ideal (g^E = 0)"

    def __init__(self, n):
        self.n = n

    def gE_RT(self, T, x):
        return 0.0 * T

    def lngamma(self, T, x):
        return np.zeros(len(x))

    def lngamma_lote(self, T, X):
        return np.zeros_like(X, dtype=float)


class LiquidoNRTL:
    nombre = "NRTL (tau_ij = a_ij + b_ij/T)"

    def __init__(self, b, alpha, a=None):
        self.b = np.array(b, dtype=float)
        self.alpha = np.array(alpha, dtype=float)
        self.a = np.zeros_like(self.b) if a is None else np.array(a, dtype=float)

    def _tauG(self, T):
        tau = self.a + self.b / T
        return tau, np.exp(-self.alpha * tau)

    def gE_RT(self, T, x):
        """g^E/RT; admite T complejo (derivada por paso complejo)."""
        tau, G = self._tauG(T)
        x = np.asarray(x)
        num = (tau * G).T @ x            # sum_j tau_ji G_ji x_j  (indice i)
        den = G.T @ x                    # sum_k G_ki x_k
        return np.sum(x * num / den)

    def lngamma(self, T, x):
        return self.lngamma_lote(T, np.asarray(x, dtype=float)[None, :])[0]

    def lngamma_lote(self, T, X):
        """ln gamma para un lote de composiciones X (K x n)."""
        tau, G = self._tauG(T)
        den = X @ G                      # den[k, i] = sum_m x_m G_mi
        num = X @ (tau * G)              # num[k, i] = sum_j x_j tau_ji G_ji
        termino = num / den
        # sum_j x_j G_ij/den_j (tau_ij - termino_j)
        A = X / den                      # A[k, j] = x_j / den_j
        corr = (A @ (G * tau).T) - (A * termino) @ G.T
        return termino + corr


def dgE_dT(modelo, T, x):
    """d(g^E)/dT [J/(mol K)] por paso complejo (exacto a precision de maquina)."""
    h = 1e-20 * T
    gE_RT = modelo.gE_RT(T + 1j * h, x)
    return R * (gE_RT.imag / h * T + gE_RT.real) if np.iscomplexobj(gE_RT) else R * float(gE_RT)


# ----------------------------------------------------------------------
# Paquetes
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class DescripcionPaquete:
    id: str
    version: str
    nombre: str
    liquido: str            # 'ideal' | 'nrtl'


PAQUETES = {
    "mezcla-ideal": DescripcionPaquete("mezcla-ideal", "1", "Vapor ideal + solución líquida ideal (Raoult con Poynting)",
                                       "ideal"),
    "nrtl-chemsep": DescripcionPaquete("nrtl-chemsep", "1",
                                       "Vapor ideal + líquido NRTL con parámetros binarios ChemSep", "nrtl"),
    "nrtl-lle-agua-butanol": DescripcionPaquete(
        "nrtl-lle-agua-butanol", "1",
        "Vapor ideal + líquido NRTL ajustado a la solubilidad mutua agua/1-butanol (IUPAC SDS-15)", "nrtl_lle"),
    "unifac-original-public": DescripcionPaquete(
        "unifac-original-public", "1",
        "Vapor ideal + líquido UNIFAC original (parámetros DDBST publicados, asignaciones DDBST)", "unifac_original"),
    "unifac-dortmund-public": DescripcionPaquete(
        "unifac-dortmund-public", "1",
        "Vapor ideal + líquido UNIFAC modificado (Dortmund; parámetros DDBST publicados 2016, asignaciones DDBST)",
        "unifac_dortmund"),
    "unifac-original-lle-public": DescripcionPaquete(
        "unifac-original-lle-public", "1",
        "Vapor ideal + líquido UNIFAC con la tabla dedicada a ELL (Magnussen et al. 1981; 10-40 °C)", "unifac_lle"),
}

# Parametros NRTL de LLE agua (1) / 1-butanol (2): tau_ij = a_ij + b_ij/T, alpha comun. Ajuste de las
# composiciones predichas a los valores recomendados (R) de IUPAC-NIST Solubility Data Series vol. 15
# (Hefter, evaluador; 1984), 293, 313, 333, 353 y 373 K (max 0.60 g/100 g); validados en 298, 323, 343 y
# 363 K (max 0.49 g/100 g)
# (tests/ajuste_nrtl_lle_agua_butanol.py). Solo para T en [293, 373] K: fuera, no hay datos.
NRTL_LLE_AGUA_BUTANOL = {"cas": ("7732-18-5", "71-36-3"),
                         "a12": 3.8570349104336255, "b12": -88.43625001079681,
                         "a21": -5.846789240856945, "b21": 2245.810529274629,
                         "alpha": 0.4447718379999113, "T": (293.0, 373.0),
                         "procedencia": "ajuste propio a IUPAC-NIST SDS vol. 15 (Hefter 1984), valores (R) de "
                                        "solubilidad mutua 293-373 K; tests/ajuste_nrtl_lle_agua_butanol.py"}
REFERENCIA = {"id": "gas-ideal-298.15K-1bar-h0-s0",
              "descripcion": "Por especie: gas ideal puro a 298.15 K y 1e5 Pa con h = 0 y s = 0. Compartida por "
                             "todos los paquetes de mezcla; distinta de la referencia IAPWS-95 del agua."}


class FaltaParametro(Exception):
    """Falta un dato del paquete. `codigo` es el sufijo del diagnostico publicado (PARAMETRO_AUSENTE para pares
    NRTL; UNIFAC_ASIGNACION_AUSENTE, UNIFAC_GRUPO_DESCONOCIDO o UNIFAC_INTERACCION_AUSENTE para UNIFAC) y
    `detalle` identifica especie, grupo o par."""

    def __init__(self, mensaje, par, codigo="PARAMETRO_AUSENTE", detalle=None):
        super().__init__(mensaje)
        self.mensaje, self.par, self.codigo, self.detalle = mensaje, par, codigo, detalle or {}


def parametros_nrtl(cas):
    """(b, alpha, procedencia) para el orden dado; FaltaParametro si un par no esta."""
    with datos.CARGA_DATOS:
        return _parametros_nrtl(cas)


def _parametros_nrtl(cas):
    from thermo.interaction_parameters import IPDB
    n = len(cas)
    b, a = np.zeros((n, n)), np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            par = [cas[i], cas[j]]
            if not IPDB.has_ip_specific("ChemSep NRTL", par, "bij"):
                raise FaltaParametro(f"No hay parámetros NRTL ChemSep para el par {cas[i]} / {cas[j]}; no se "
                                     "completan con cero.", (cas[i], cas[j]))
            m = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", par, "bij")
            al = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", par, "alphaij")
            b[i, j], b[j, i] = m[0][1], m[1][0]
            a[i, j] = a[j, i] = al[0][1]
    return b, a, "ChemSep (thermo.interaction_parameters.IPDB, tabla 'ChemSep NRTL')"


# ----------------------------------------------------------------------
# Estado
# ----------------------------------------------------------------------
@dataclass
class FaseMezcla:
    id: str
    tipo: str               # 'liquido' | 'vapor'
    n: float                # mol
    x: np.ndarray           # fracciones molares (orden del sistema)
    h: float                # J/mol
    s: float                # J/(mol K)
    v: float                # m3/mol
    g: float                # J/mol
    mu: np.ndarray          # J/mol (nan en especies ausentes de la fase/sistema)
    M: float                # kg/mol

    @property
    def u(self):
        return self.h - self._P * self.v


@dataclass
class EstadoMezcla:
    especificacion: str
    T: float
    P: float
    especies: tuple
    n: np.ndarray
    fases: list
    verificaciones: dict = field(default_factory=dict)    # id -> (residuo, tolerancia, motivo)
    estabilidad: dict = field(default_factory=dict)

    def total(self, k):
        return sum(f.n * getattr(f, k) for f in self.fases)

    @property
    def H(self):
        return self.total("h")

    @property
    def V(self):
        return self.total("v")

    @property
    def U(self):
        return self.H - self.P * self.V

    @property
    def S(self):
        return self.total("s")

    @property
    def G(self):
        return self.total("g")

    @property
    def masa(self):
        return sum(f.n * f.M for f in self.fases)


class Sistema:
    """Un paquete aplicado a un conjunto ordenado de especies."""

    def __init__(self, paquete_id, cas, sustituciones=None):
        """sustituciones: {cas: {propiedad: dato}} ya validado por core/catalogo.leer_sustituciones (F2.4)."""
        if paquete_id not in PAQUETES:
            raise KeyError(paquete_id)
        self.paquete = PAQUETES[paquete_id]
        self.cas = tuple(cas)
        faltan = [c for c in cas if c not in datos.especies_disponibles()]
        if faltan:
            raise FaltaParametro(f"Sin datos de componente puro para {', '.join(faltan)}.", tuple(faltan),
                                 codigo="COMPONENTE_NO_SOPORTADO",
                                 detalle={"tipo": "registro", "especies": list(faltan)})
        # Regla UNICA de admision por especie (core/catalogo.py): la misma para el limite puro y para las mezclas
        # (F9-R3). Los requisitos por par o grupo se comprueban despues, al construir el modelo de liquido.
        from core import catalogo
        for c in cas:
            f = catalogo.faltantes(self.paquete.liquido, c, self.paquete.id)
            if f:
                raise FaltaParametro(f[0]["mensaje"], (c,), codigo=f[0]["codigo"],
                                     detalle={"tipo": f[0]["dato"], "cas": c, "faltantes": f})
        self.esp = [datos.especie(c) for c in cas]
        # F2.4: entradas sustituidas del potencial de cada especie (v_L, cp del gas ideal, Psat); h, s y mu se
        # derivan de ellas. Solo las de especies presentes; entran en la huella (sin sustitucion, la huella no cambia).
        self.sustituciones = {c: dict(v) for c, v in sorted((sustituciones or {}).items()) if c in cas}
        if self.sustituciones:
            from core import catalogo as _cat
            self.esp = [_cat.aplicar_sustituciones(e, self.sustituciones[c]) if c in self.sustituciones else e
                        for c, e in zip(cas, self.esp)]
        self.M = np.array([e.M for e in self.esp])
        self.vL = np.array([e.vL for e in self.esp])
        if self.paquete.liquido == "nrtl_lle":
            d = NRTL_LLE_AGUA_BUTANOL
            if not set(cas) <= set(d["cas"]):
                raise FaltaParametro("El paquete nrtl-lle-agua-butanol solo tiene parámetros para agua y 1-butanol.",
                                     tuple(c for c in cas if c not in d["cas"]))
            pos = {c: k for k, c in enumerate(d["cas"])}
            A, B = np.zeros((2, 2)), np.zeros((2, 2))
            A[0, 1], B[0, 1], A[1, 0], B[1, 0] = d["a12"], d["b12"], d["a21"], d["b21"]
            orden = [pos[c] for c in cas]
            self.liq = LiquidoNRTL(B[np.ix_(orden, orden)], np.full((len(cas), len(cas)), d["alpha"]),
                                   A[np.ix_(orden, orden)])
            self.procedencia = d["procedencia"]
        elif self.paquete.liquido == "nrtl" and len(cas) > 1:
            b, a, self.procedencia = parametros_nrtl(list(cas))
            self.liq = LiquidoNRTL(b, a)
        elif self.paquete.liquido.startswith("unifac_") and len(cas) > 1:
            from core import unifac
            variante = self.paquete.liquido.split("_", 1)[1]
            try:
                self.liq = unifac.LiquidoUNIFAC(list(cas), variante)
            except unifac.FaltaDatoUNIFAC as x:
                codigo = {"asignacion_ausente": "UNIFAC_ASIGNACION_AUSENTE", "grupo_desconocido":
                          "UNIFAC_GRUPO_DESCONOCIDO", "interaccion_ausente": "UNIFAC_INTERACCION_AUSENTE"}[x.detalle["tipo"]]
                raise FaltaParametro(x.mensaje, tuple(x.detalle.get("especies") or [x.detalle.get("cas")]),
                                     codigo=codigo, detalle=x.detalle)
            self.procedencia = (f"UNIFAC {variante}: {unifac.tablas(variante)['ident']['fuente_interacciones']}; "
                                f"{unifac.tablas(variante)['ident']['fuente_asignaciones']}")
        else:
            self.liq = LiquidoIdeal(len(cas))
            self.procedencia = "sin parámetros binarios (g^E = 0)" if self.paquete.liquido == "ideal" else \
                "un componente: g^E = 0"
        self.T_rango = (max(e.T_rango[0] for e in self.esp), min(e.T_rango[1] for e in self.esp))
        if self.paquete.liquido == "nrtl_lle":
            self.T_rango = (max(self.T_rango[0], NRTL_LLE_AGUA_BUTANOL["T"][0]),
                            min(self.T_rango[1], NRTL_LLE_AGUA_BUTANOL["T"][1]))
        if self.paquete.liquido.startswith("unifac_"):
            from core import unifac
            rango = unifac.RANGO_T.get(self.paquete.liquido.split("_", 1)[1])
            if rango is not None:           # tabla acotada por sus datos de ajuste (tambien para una especie)
                self.T_rango = (max(self.T_rango[0], rango[0]), min(self.T_rango[1], rango[1]))

    # --- dominio -------------------------------------------------------------
    def dominio(self, T, P):
        if not self.T_rango[0] <= T <= self.T_rango[1]:
            raise FueraDeAlcance("fuera_de_dominio", f"T = {T:.6g} K fuera del dominio del sistema "
                                 f"[{self.T_rango[0]:.6g}, {self.T_rango[1]:.6g}] K (rangos de Psat y cp, "
                                 "T < 0.9 Tc).", T_fuera=True)
        if not P_MIN <= P <= P_MAX:
            raise FueraDeAlcance("fuera_de_dominio", f"P = {P:.6g} Pa fuera del dominio [{P_MIN:g}, {P_MAX:g}] Pa "
                                 "(vapor ideal).", P_fuera=True)

    # --- potenciales y propiedades por fase (sobre las especies del indice idx) ----
    def _g_puros(self, T, P):
        """(g_ig0, g_L) de todas las especies a (T, P), cacheados (funciones puras)."""
        cache = self.__dict__.setdefault("_gpuros", {})
        clave = (T, P)
        if clave not in cache:
            if len(cache) > 20000:
                cache.clear()
            cache[clave] = (np.array([e.g_ig0(T) for e in self.esp]), np.array([e.g_L(T, P) for e in self.esp]))
        return cache[clave]

    def mu(self, tipo, T, P, x, idx):
        x = np.asarray(x, dtype=float)
        gig, gL = self._g_puros(T, P)
        with np.errstate(divide="raise"):
            if tipo == "vapor":
                return gig[idx] + R * T * np.log(x * P / P0)
            lg = self._lngamma(T, x, idx)
            return gL[idx] + R * T * (np.log(x) + lg)

    def _lngamma(self, T, x, idx):
        return self._modelo_sub(idx).lngamma(T, x)

    def _modelo_sub(self, idx):
        clave = tuple(idx)
        cache = self.__dict__.setdefault("_subs", {})
        if clave not in cache:
            if isinstance(self.liq, LiquidoIdeal) or len(idx) == 1:
                cache[clave] = LiquidoIdeal(len(idx))
            elif hasattr(self.liq, "subconjunto"):
                cache[clave] = self.liq.subconjunto(idx)          # UNIFAC: mismas tablas y asignaciones
            else:
                cache[clave] = LiquidoNRTL(self.liq.b[np.ix_(idx, idx)], self.liq.alpha[np.ix_(idx, idx)],
                                           self.liq.a[np.ix_(idx, idx)])
        return cache[clave]

    def _tm_liquido_lote(self, T, P, W, mu_ref, idx):
        """tm para un lote de composiciones de prueba liquidas W (K x n)."""
        RT = R * T
        gL = self._g_puros(T, P)[1][idx]
        lg = self._modelo_sub(idx).lngamma_lote(T, W)
        return np.sum(W * ((gL - mu_ref) / RT + np.log(W) + lg), axis=1)

    def fase(self, fid, tipo, T, P, nfase, idx):
        """FaseMezcla con x sobre todas las especies del sistema (0 en las ausentes)."""
        nfase = np.asarray(nfase, dtype=float)
        ntot = nfase.sum()
        xs = nfase / ntot
        mu = self.mu(tipo, T, P, xs, idx)
        x_full = np.zeros(len(self.cas))
        x_full[idx] = xs
        mu_full = np.full(len(self.cas), np.nan)
        mu_full[idx] = mu
        if tipo == "vapor":
            h = sum(xs[k] * self.esp[i].h_ig(T) for k, i in enumerate(idx))
            s = sum(xs[k] * (self.esp[i].s_ig0(T) - R * math.log(xs[k] * P / P0)) for k, i in enumerate(idx))
            v = R * T / P
        else:
            m = self._modelo_sub(idx)
            gE = R * T * float(np.real(m.gE_RT(T, xs)))
            dgE = dgE_dT(m, T, xs)
            h = sum(xs[k] * self.esp[i].h_L(T, P) for k, i in enumerate(idx)) + gE - T * dgE
            s = sum(xs[k] * (self.esp[i].s_L(T, P) - R * math.log(xs[k])) for k, i in enumerate(idx)) - dgE
            v = float(sum(xs[k] * self.vL[i] for k, i in enumerate(idx)))
        g = float(np.sum(xs * mu))
        f = FaseMezcla(id=fid, tipo=tipo, n=float(ntot), x=x_full, h=float(h), s=float(s), v=float(v), g=g,
                       mu=mu_full, M=float(np.sum(x_full * self.M)))
        f._P = P
        return f

    # --- estabilidad -----------------------------------------------------------
    def _tm_liquido(self, T, P, w, mu_ref, idx):
        w = np.asarray(w, dtype=float)
        return float(np.sum(w * (self.mu("liquido", T, P, w, idx) - mu_ref)) / (R * T))

    def prueba_estabilidad(self, T, P, mu_ref, idx, incluir_vapor=True):
        """[(tipo, w, tm)] minimos locales de la distancia al plano tangente."""
        RT = R * T
        sal = []
        if incluir_vapor:
            c = (np.array([self.esp[i].g_ig0(T) for i in idx]) + RT * math.log(P / P0) - mu_ref) / RT
            e = np.exp(-(c - c.min()))
            w = e / e.sum()
            sal.append(("vapor", w, float(-(np.log(e.sum()) - c.min()))))
        n = len(idx)
        if n == 1:
            sal.append(("liquido", np.array([1.0]), self._tm_liquido(T, P, [1.0], mu_ref, idx)))
            return sal
        if n == 2:
            # malla en logit de w1 y refinamiento acotado de cada minimo local
            u = np.linspace(-34, 34, 1361)
            w1 = 1 / (1 + np.exp(-u))
            tm = self._tm_liquido_lote(T, P, np.column_stack([w1, 1 - w1]), mu_ref, idx)
            kmin = int(np.argmin(tm))
            for k in range(1, len(u) - 1):
                # Un minimo local de la malla (paso 0.05 en logit) con tm > 1e-4 no baja de -TOL_TM
                # dentro de su celda para estas funciones suaves; se refinan los cercanos a 0 y el global.
                if tm[k] <= tm[k - 1] and tm[k] <= tm[k + 1] and (tm[k] < 1e-4 or k == kmin):
                    from scipy.optimize import minimize_scalar
                    f = lambda uu: self._tm_liquido(T, P, [1 / (1 + math.exp(-uu)), 1 - 1 / (1 + math.exp(-uu))],
                                                    mu_ref, idx)
                    r = minimize_scalar(f, bounds=(u[k - 1], u[k + 1]), method="bounded",
                                        options={"xatol": 1e-12})
                    a = 1 / (1 + math.exp(-r.x))
                    sal.append(("liquido", np.array([a, 1 - a]), float(min(r.fun, tm[k]))))
            return sal
        if n == 3:
            N = 60
            puntos = []
            for i in range(N + 1):
                for j in range(N + 1 - i):
                    k = N - i - j
                    w = np.array([i, j, k], dtype=float) + 1e-6
                    puntos.append(w / w.sum())
            W = np.array(puntos)
            tml = self._tm_liquido_lote(T, P, W, mu_ref, idx)
            tms = sorted(zip(tml.tolist(), puntos), key=lambda z: z[0])
            semillas = [w for _, w in tms[:12]]
            for w0 in semillas:
                z0 = np.log(w0[:2] / w0[2])
                f = lambda zz: self._tm_liquido(T, P, _softmax3(zz), mu_ref, idx)
                r = minimize(f, z0, method="Nelder-Mead", options={"xatol": 1e-11, "fatol": 1e-15, "maxiter": 4000})
                sal.append(("liquido", _softmax3(r.x), float(r.fun)))
            return sal
        return sal + self._estabilidad_general(T, P, mu_ref, idx)

    # --- equilibrio TP -----------------------------------------------------------
    def equilibrio_TP(self, T, P, n, especificacion="TP"):
        n = np.asarray(n, dtype=float)
        self.dominio(T, P)
        if np.any(n < 0) or not n.sum() > 0:
            raise FueraDeAlcance("invalido", "Cantidades negativas o total nulo.")
        idx = [i for i in range(len(n)) if n[i] > 0]
        nz = n[idx]
        z = nz / nz.sum()
        RT = R * T
        if len(idx) == 1:
            return self._puro_TP(T, P, n, idx, especificacion)
        # fase unica de menor G
        cand = []
        for tipo in ("liquido", "vapor"):
            cand.append((float(np.sum(z * self.mu(tipo, T, P, z, idx))), tipo))
        cand.sort()

        def secuencia(fases):
            exploradas = []
            for _ in range(MAX_FASES):
                mu_ref = self._mu_comun(T, P, fases, idx)
                tipos_presentes = {t for t, _ in fases}
                pruebas = self.prueba_estabilidad(T, P, mu_ref, idx, incluir_vapor="vapor" not in tipos_presentes)
                exploradas.extend(pruebas)
                nuevas_pr = _candidatas_nuevas(pruebas, [(t, nf / nf.sum()) for t, nf in fases])
                peor = min(nuevas_pr, key=lambda p: p[2]) if nuevas_pr else (None, None, 0.0)
                if peor[2] >= -TM_INTENTO or len(fases) >= MAX_FASES:
                    break
                nuevas = self._minimizar_G(T, P, fases, (peor[0], peor[1]), nz, idx)
                if nuevas is None:
                    break
                fases = nuevas
            # certificacion final
            mu_ref = self._mu_comun(T, P, fases, idx)
            cert = self.prueba_estabilidad(T, P, mu_ref, idx, incluir_vapor=True)
            tm_min = min(p[2] for p in cert)
            estado = self._empaquetar(especificacion, T, P, n, idx, fases)
            return fases, exploradas, cert, tm_min, estado, self._residuo_mu(estado, idx)

        fases, exploradas, cert, tm_min, estado, res_mu = secuencia([(cand[0][1], nz.copy())])
        if max(0.0, -tm_min) > TOL_TM or res_mu > TOL_MU:
            # Junto a un punto invariante (p. ej. a 1e-6 K de un heteroazeotropo) la fase de prueba competidora tiene
            # tm del orden de 1e-8 y la adicion desde la fase unica de menor G puede quedarse en el conjunto vecino.
            # Se repite la secuencia desde las demas fases unicas; se acepta solo un estado certificado. El camino
            # normal (certificado al primer intento) no cambia.
            for _, tipo in cand[1:]:
                alt = secuencia([(tipo, nz.copy())])
                if max(0.0, -alt[3]) <= TOL_TM and alt[5] <= TOL_MU:
                    fases, exploradas, cert, tm_min, estado, res_mu = alt
                    break
        estado.verificaciones["equilibrio"] = (res_mu, TOL_MU,
                                               "max |mu_i^a - mu_i^b|/(R T) entre fases presentes")
        estado.verificaciones["estabilidad"] = (max(0.0, -tm_min), TOL_TM,
                                                "-min tm sobre fases de prueba vapor (minimo analitico) y liquido "
                                                "(malla en el simplex y refinamiento local)")
        estado.estabilidad = {"tm_min": tm_min, "pruebas": len(cert) + len(exploradas),
                              "candidatas": sorted({p[0] for p in cert})}
        if max(0.0, -tm_min) > TOL_TM and len(fases) >= MAX_FASES and res_mu <= TOL_MU:
            competidora = min(cert, key=lambda q: q[2])
            raise FueraDeAlcance("no_soportado",
                                 f"A T = {T:.6g} K, P = {P:.6g} Pa el estado con {len(fases)} fases (tope MAX_FASES = "
                                 f"{MAX_FASES}) no es estable: una fase de prueba {competidora[0]} baja el plano tangente "
                                 f"(tm = {competidora[2]:.3g}). Haría falta otra fase; no se publica como estable.",
                                 tope_fases=True)
        if max(0.0, -tm_min) > TOL_TM or res_mu > TOL_MU:
            raise FueraDeAlcance("no_convergente",
                                 f"El equilibrio a T = {T:.6g} K, P = {P:.6g} Pa no se certifica (tm {tm_min:.3g}, "
                                 f"mu {res_mu:.3g}).")
        return estado

    def _mu_comun(self, T, P, fases, idx):
        tipo, nf = fases[0]
        return self.mu(tipo, T, P, nf / nf.sum(), idx)

    def _minimizar_G(self, T, P, fases, nueva, nz, idx):
        """Minimiza G sobre el reparto entre las fases actuales mas la nueva."""
        RT = R * T
        tipos = [t for t, _ in fases] + [nueva[0]]
        k = len(tipos)
        m = len(idx)
        # semilla: la nueva fase con 10 % de cada especie segun su composicion de prueba
        w = nueva[1]
        add0 = np.minimum(0.1 * nz * w / np.maximum(w, 1e-300) * w / np.max(w), 0.5 * fases[0][1])
        add0 = np.maximum(add0, 1e-9 * nz)

        def separar(vec):
            partes = [vec[a * m:(a + 1) * m] for a in range(k - 1)]
            ultima = nz - np.sum(partes, axis=0)
            return partes + [ultima]

        def G(vec):
            ps = separar(vec)
            tot = 0.0
            for t, nf in zip(tipos, ps):
                nf = np.maximum(nf, 1e-300)
                tot += float(np.sum(nf * self.mu(t, T, P, nf / nf.sum(), idx)))
            return tot / (RT * nz.sum())

        def grad(vec):
            ps = separar(vec)
            mus = [self.mu(t, T, P, np.maximum(nf, 1e-300) / np.maximum(nf, 1e-300).sum(), idx)
                   for t, nf in zip(tipos, ps)]
            return np.concatenate([(mus[a] - mus[-1]) / (RT * nz.sum()) for a in range(k - 1)])
        lo = 1e-14 * np.tile(nz, k - 1)
        cons = [{"type": "ineq", "fun": lambda v: separar(v)[-1] - 1e-14 * nz}]

        def intento(add):
            sem = [nf.copy() for _, nf in fases]
            sem[0] = sem[0] - add
            sem.append(add)
            x0 = np.concatenate(sem[:-1])
            try:
                r = minimize(G, x0, jac=grad, method="SLSQP", bounds=list(zip(lo, np.tile(nz, k - 1))),
                             constraints=cons, options={"ftol": 1e-15, "maxiter": 1000})
            except (FloatingPointError, ValueError):
                return []
            partes = separar(r.x)
            # Las fases que la minimizacion agota se retiran ANTES de pulir: el Newton en ln n no puede
            # tratar una fase de cantidad nula, y el conjunto correcto es el de las fases que quedan.
            quedan = []
            for t, nf in zip(tipos, partes):
                if nf.sum() <= 1e-9 * nz.sum():
                    continue
                # Una fase que la minimizacion lleva a la composicion de otra del mismo tipo es la MISMA fase
                # (solucion trivial: la minimizacion la vacia por ese camino); se funden y el conjunto sigue.
                for k2, (t2, nf2) in enumerate(quedan):
                    if t == t2 and np.max(np.abs(nf / nf.sum() - nf2 / nf2.sum())) < 1e-3:
                        quedan[k2] = (t2, nf2 + nf)
                        break
                else:
                    quedan.append((t, nf))
            return quedan
        quedan = intento(add0)
        if len(quedan) < 2:
            # La semilla pequena puede caer en la cuenca de la solucion trivial (la fase nueva se funde con la
            # existente) aunque la prueba de estabilidad haya encontrado tm < 0: p. ej. 6 especies con una fase
            # de prueba casi pura y diluida, donde la fase nueva en equilibrio es ~0.1 % del inventario y la
            # semilla del 10 % la sobredimensiona. Se reintenta con la fase nueva ya formada (fraccion beta del
            # inventario con la composicion de prueba, sin superar el 90 % de la fase donante). El camino
            # normal (separa al primer intento) no cambia.
            for beta in (1e-3, 1e-4, 0.05, 0.2, 0.5):
                add = np.maximum(np.minimum(beta * nz.sum() * w, 0.9 * fases[0][1]), 1e-9 * nz)
                quedan = intento(add)
                if len(quedan) >= 2:
                    break
        if len(quedan) < 2:
            return None
        tipos_q = [t for t, _ in quedan]
        partes = self._pulir(T, P, tipos_q, [nf for _, nf in quedan], nz, idx)
        if (partes is None or self._res_partes(T, P, tipos_q, partes, idx) > TOL_MU) and len(quedan) > 2:
            # Sin solucion con todas las fases (p. ej. tres fases de un binario fuera de su T invariante:
            # la minimizacion deja una fase diminuta que el Newton no puede igualar). Se prueba cada
            # subconjunto sin una de ellas y se queda el de menor G que converge.
            mejor = None
            for quitar in range(len(quedan)):
                sub = [q for k2, q in enumerate(quedan) if k2 != quitar]
                tipos_s = [t for t, _ in sub]
                ps = self._pulir(T, P, tipos_s, [nf for _, nf in sub], nz, idx)
                if ps is None or self._res_partes(T, P, tipos_s, ps, idx) > TOL_MU:
                    continue
                g = sum(float(np.sum(nf * self.mu(t, T, P, nf / nf.sum(), idx))) for t, nf in zip(tipos_s, ps))
                if mejor is None or g < mejor[0]:
                    mejor = (g, tipos_s, ps)
            if mejor is not None:
                _, tipos_q, partes = mejor
        if partes is None or self._res_partes(T, P, tipos_q, partes, idx) > TOL_MU:
            # El reparto no converge: tipicamente la fase nueva quiere anularse (a ~1e-12 K de una
            # frontera, cantidad ~1e-9 mol y ln n -> -inf). Se descarta y el conjunto previo se certifica
            # por la prueba de plano tangente (tm >= -TOL_TM), sin publicar un reparto no convergido.
            return None
        # descartar fases agotadas o duplicadas (solucion trivial)
        sal = []
        for t, nf in zip(tipos_q, partes):
            if nf.sum() <= 1e-12 * nz.sum():
                continue
            x = nf / nf.sum()
            if any(t == t2 and np.max(np.abs(x - nf2 / nf2.sum())) < 1e-6 for t2, nf2 in sal):
                return None
            sal.append((t, nf))
        if len(sal) < 2:
            return None
        return sal

    def _pulir(self, T, P, tipos, partes, nz, idx):
        """Newton sobre mu_i^a = mu_i^resto (en ln n para mantener positividad). La fase que se obtiene
        por diferencia (n - sum de las demas) es la MAS abundante: si fuera una fase diminuta, restar
        cantidades grandes destruiria su precision (fracciones de fase de 1e-7 junto a una frontera)."""
        orden = sorted(range(len(tipos)), key=lambda a: float(np.sum(partes[a])))
        if orden != list(range(len(tipos))):
            res = self._pulir(T, P, [tipos[a] for a in orden], [partes[a] for a in orden], nz, idx)
            if res is None:
                return None
            sal = [None] * len(tipos)
            for pos, a in enumerate(orden):
                sal[a] = res[pos]
            return sal
        RT = R * T
        k, m = len(tipos), len(idx)
        if any(p.min() <= 0 for p in partes):
            partes = [np.maximum(p, 1e-14 * nz) for p in partes[:-1]] + [None]
            partes[-1] = nz - np.sum(partes[:-1], axis=0)
            if partes[-1].min() <= 0:
                return None
        z = np.log(np.concatenate(partes[:-1]))

        def F(zv):
            ps = [np.exp(zv[a * m:(a + 1) * m]) for a in range(k - 1)]
            ult = nz - np.sum(ps, axis=0)
            if ult.min() <= 0 or any(p.min() <= 0 for p in ps):      # (exp que se anula por debajo)
                return None
            mus = [self.mu(t, T, P, p / p.sum(), idx) for t, p in zip(tipos, ps + [ult])]
            return np.concatenate([(mus[a] - mus[-1]) / RT for a in range(k - 1)])
        f = F(z)
        if f is None:
            return None
        for _ in range(60):
            if np.max(np.abs(f)) < 1e-14:
                break
            J = self._jacobiano_reparto(T, P, tipos, z, nz, idx, m, k)
            if J is None:
                return None
            try:
                paso = np.linalg.solve(J, -f)
            except np.linalg.LinAlgError:
                break
            a = 1.0
            mejorado = False
            for _ in range(30):
                zn = z + a * paso
                fn = F(zn)
                if fn is not None and np.max(np.abs(fn)) < np.max(np.abs(f)):
                    z, f, mejorado = zn, fn, True
                    break
                a *= 0.5
            if not mejorado:
                break
        ps = [np.exp(z[a * m:(a + 1) * m]) for a in range(k - 1)]
        return ps + [nz - np.sum(ps, axis=0)]

    def _res_partes(self, T, P, tipos, partes, idx):
        """max |mu_i^a - mu_i^b|/(R T) entre las fases dadas como cantidades (inf si alguna no es positiva)."""
        if any(p.min() <= 0 for p in partes):
            return math.inf
        mus = [self.mu(t, T, P, p / p.sum(), idx) for t, p in zip(tipos, partes)]
        return float(max(np.max(np.abs(m - mus[0])) for m in mus[1:]) / (R * T))

    def _residuo_mu(self, estado, idx):
        if len(estado.fases) < 2:
            return 0.0
        RT = R * estado.T
        ref = estado.fases[0].mu[idx]
        return float(max(np.max(np.abs(f.mu[idx] - ref)) for f in estado.fases[1:]) / RT)

    def _empaquetar(self, espec, T, P, n, idx, fases):
        objs = []
        nliq = sum(1 for t, _ in fases if t == "liquido")
        orden = sorted(fases, key=lambda tf: (tf[0] != "vapor", 0))
        # IDs: vapor-1; liquidos por densidad masica decreciente: liquido-1 el mas denso (convencion estatica)
        liqs = [nf for t, nf in fases if t == "liquido"]
        dens = []
        for nf in liqs:
            x = nf / nf.sum()
            dens.append(float(np.sum(x * self.M[idx]) / np.sum(x * self.vL[idx])))
        orden_l = sorted(range(len(liqs)), key=lambda k: -dens[k])
        for t, nf in fases:
            if t == "vapor":
                objs.append(self.fase("vapor-1", "vapor", T, P, nf, idx))
        for pos, k in enumerate(orden_l):
            objs.append(self.fase(f"liquido-{pos + 1}", "liquido", T, P, liqs[k], idx))
        e = EstadoMezcla(especificacion=espec, T=T, P=P, especies=self.cas, n=np.asarray(n, dtype=float),
                         fases=objs)
        res = float(np.max(np.abs(sum(f.n * f.x for f in objs) - n)) / n.sum())
        e.verificaciones["reconstruccion_material"] = (res, 1e-12, "max |sum_a n^a x_i^a - n_i| / n")
        return e

    # --- componente puro -----------------------------------------------------------
    def P_saturacion(self, T, i):
        """P de coexistencia del componente puro i a T en este modelo (con Poynting)."""
        e = self.esp[i]
        f = lambda P: e.g_L(T, P) - (e.g_ig0(T) + R * T * math.log(P / P0))
        Ps = e.Psat(T)
        return brentq(f, Ps * 0.5, Ps * 2.0, xtol=1e-300, rtol=1e-15)

    def _puro_TP(self, T, P, n, idx, espec, lado=None):
        """lado: fase ya conocida por quien llama (busqueda isobara a un lado de Tsat(P)). Sin el, dentro de la
        banda |P/Pe - 1| <= 1e-6 el TP es ambiguo y se rechaza; con el, se evalua esa fase (bien definida)."""
        i = idx[0]
        Pe = self.P_saturacion(T, i)
        if lado is None and abs(P / Pe - 1.0) <= 1e-6:
            raise FueraDeAlcance("saturacion", f"Componente puro en saturación a {T:.6g} K (Psat = {Pe:.9g} Pa): T y "
                                 "P no determinan el reparto.")
        tipo = lado or ("liquido" if P > Pe else "vapor")
        e = self._empaquetar(espec, T, P, n, idx, [(tipo, n[idx])])
        RT = R * T
        g_otra = (self.mu("vapor" if tipo == "liquido" else "liquido", T, P, [1.0], idx)[0] - e.fases[0].mu[i]) / RT
        e.verificaciones["equilibrio"] = (0.0, TOL_MU, "una fase")
        e.verificaciones["estabilidad"] = (max(0.0, -g_otra), TOL_TM, "g de la otra fase pura frente a la presente")
        e.estabilidad = {"tm_min": g_otra, "pruebas": 1, "candidatas": ["liquido", "vapor"]}
        return e

    # --- operaciones energeticas -------------------------------------------------------
    def _mesetas(self, T, P, n, y_nombre, objetivo):
        """Estado en una meseta (componente puro o azeotropo exacto): las fases
        coexistentes tienen la composicion global y la fraccion sale de la palanca."""
        idx = [i for i in range(len(n)) if n[i] > 0]
        nz = n[idx]
        fL = self.fase("liquido-1", "liquido", T, P, nz, idx)
        fV = self.fase("vapor-1", "vapor", T, P, nz, idx)
        yL = fL.h if y_nombre == "h" else fL.h - P * fL.v
        yV = fV.h if y_nombre == "h" else fV.h - P * fV.v
        N = nz.sum()
        beta = (objetivo / N - yL) / (yV - yL)
        if not -1e-12 <= beta <= 1 + 1e-12:
            return None
        beta = min(max(beta, 0.0), 1.0)
        fases = [t for t in (("liquido", (1 - beta) * nz), ("vapor", beta * nz)) if t[1].sum() > 0]
        e = self._empaquetar("meseta", T, P, n, idx, fases)
        # certificacion: igualdad de mu entre liquido y vapor de la misma composicion y prueba de plano
        # tangente con esa mu comun (como cualquier otro estado)
        RT = R * T
        res_mu = float(np.max(np.abs(fL.mu[idx] - fV.mu[idx])) / RT)
        pr = self.prueba_estabilidad(T, P, fL.mu[idx], idx, incluir_vapor=True)
        tm_min = min(q[2] for q in pr)
        e.verificaciones["equilibrio"] = (res_mu, max(TOL_MU, 1e-9),
                                          "meseta: max |mu_i^L - mu_i^V|/(R T) con la composicion global en ambas fases")
        e.verificaciones["estabilidad"] = (max(0.0, -tm_min), TOL_TM,
                                           "-min tm sobre fases de prueba vapor y liquido con la mu de la meseta")
        e.estabilidad = {"tm_min": tm_min, "pruebas": len(pr), "candidatas": ["liquido", "vapor"]}
        if res_mu > 1e-7 or tm_min < -TOL_TM:
            return None          # no es una meseta (componente puro o azeotropo exacto)
        return e

    def equilibrio_isobaro(self, P, n, y_nombre, objetivo, espec, semilla=None):
        """PH (y = H total, J) o UP (y = U total, J) a P dada. Con `semilla` (estado cercano, p. ej. el de la
        etapa anterior del integrador) la busqueda en T empieza en un intervalo alrededor de su T que se
        ensancha hasta encerrar la raiz, y cada TP de la busqueda parte de la evaluacion previa (flash con
        semilla y prueba de estabilidad, con caida al TP completo). La raiz, la certificacion y las mesetas
        son las mismas que sin semilla; solo cambia el coste."""
        n = np.asarray(n, dtype=float)
        T_lo, T_hi = self.T_rango
        self.dominio(T_lo, P)
        idx = [i for i in range(len(n)) if n[i] > 0]
        Ts_puro = [None]
        if len(idx) == 1:
            # Componente puro: meseta explicita en Tsat(P) (palanca); fuera de ella, una fase
            # con T a un lado u otro de Tsat (TP alli esta bien determinado).
            Ts = self.T_saturacion(P, idx[0])
            Ts_puro[0] = Ts
            if Ts is not None:
                e = self._mesetas(Ts, P, n, y_nombre, objetivo)
                if e is not None:
                    return self._recalificar(e, espec)
                f = self.fase("x", "liquido", Ts, P, n[idx], idx)
                yL = f.n * (f.h if y_nombre == "h" else f.h - P * f.v)
                if objetivo < yL:
                    T_hi = Ts * (1 - 1e-9)
                else:
                    T_lo = Ts * (1 + 1e-9)

        ult = {}
        previa = [semilla if semilla is not None and len(idx) > 1 else None]

        def Y(T):
            if len(idx) == 1 and Ts_puro[0] is not None and T != Ts_puro[0]:
                # componente puro a un lado conocido de Tsat(P): la banda de saturacion del TP (|P/Pe-1| <= 1e-6,
                # ~1e-7 relativo en T) contiene el extremo Ts(1 -+ 1e-9) del intervalo; aqui el lado no es ambiguo
                e = self._puro_TP(T, P, n, idx, "TP", lado="liquido" if T < Ts_puro[0] else "vapor")
                ult[T] = e
                return (e.H if y_nombre == "h" else e.U) - objetivo
            if previa[0] is not None:
                try:
                    e = self.flash_rapido("TP", T, P, n, previa[0])
                except FueraDeAlcance as x:
                    if x.motivo != "saturacion":
                        raise
                    e = self._TP_seguro(T, P, n)
                previa[0] = e
            else:
                e = self._TP_seguro(T, P, n)
            ult[T] = e
            return (e.H if y_nombre == "h" else e.U) - objetivo
        if previa[0] is not None and T_lo < semilla.T < T_hi:
            # intervalo local alrededor de la semilla, ensanchado x4 hasta encerrar la raiz o tocar el dominio
            d = 0.25
            while True:
                a_, b_ = max(T_lo, semilla.T - d), min(T_hi, semilla.T + d)
                previa[0] = semilla
                fa = Y(a_)
                previa[0] = semilla
                fb = Y(b_)
                if (fa <= 0 <= fb) or (a_ == T_lo and b_ == T_hi):
                    break
                d *= 4
            T_lo, T_hi, f_lo, f_hi = a_, b_, fa, fb
        else:
            f_lo, f_hi = Y(T_lo), Y(T_hi)
        if f_lo > 0 or f_hi < 0:
            raise FueraDeAlcance("fuera_de_dominio", f"Ningún estado con {y_nombre.upper()} = {objetivo:.9g} J a "
                                 f"P = {P:.6g} Pa tiene T en el dominio [{T_lo:.6g}, {T_hi:.6g}] K.", T_fuera=True)
        if f_lo == 0:
            return self._recalificar(ult[T_lo], espec)
        if f_hi == 0:
            return self._recalificar(ult[T_hi], espec)
        # Brent: la propiedad de equilibrio es creciente y continua en T salvo en una meseta (componente
        # puro o azeotropo exacto), donde salta; ahi Brent converge al salto y se aplica la palanca.
        T = brentq(Y, T_lo, T_hi, xtol=1e-300, rtol=4.5e-16 * 4, maxiter=500)
        e = ult.get(T) or self._TP_seguro(T, P, n)
        if abs((e.H if y_nombre == "h" else e.U) - objetivo) <= 1e-10 * max(abs(objetivo), R * T * n.sum()):
            return self._recalificar(e, espec)
        e = self._mesetas(T, P, n, "h" if y_nombre == "h" else "u", objetivo)
        if e is None:
            e = self._meseta_general(T, P, n, "T", y_nombre, objetivo)
        if e is None:
            raise FueraDeAlcance("no_convergente", f"{espec}: la búsqueda en T no converge ni es una meseta.")
        return self._recalificar(e, espec)

    def _recalificar(self, e, espec):
        e.especificacion = espec
        return e

    def _TP_seguro(self, T, P, n):
        try:
            return self.equilibrio_TP(T, P, n)
        except FueraDeAlcance as x:
            if x.motivo == "saturacion":     # T exactamente en la meseta: cualquier lado sirve para buscar
                return self.equilibrio_TP(T * (1 + 1e-12), P, n)
            raise

    def equilibrio_PH(self, P, H, n, semilla=None):
        return self.equilibrio_isobaro(P, n, "h", H, "PH", semilla=semilla)

    def equilibrio_UP(self, P, U, n, semilla=None):
        return self.equilibrio_isobaro(P, n, "u", U, "UP", semilla=semilla)

    def equilibrio_TV(self, T, V, n, semilla=None, rtol=1e-15):
        """P con V(T, P) = V. V es decreciente en P (vapor ideal, liquido
        incompresible). Si el liquido ocupa todo V a cualquier P, la presion
        queda indeterminada en este modelo: no se inventa."""
        n = np.asarray(n, dtype=float)
        idx = [i for i in range(len(n)) if n[i] > 0]
        VL = float(np.sum(n[idx] * self.vL[idx]))
        if V <= VL * (1 + 1e-12):
            raise FueraDeAlcance("no_soportado", f"El líquido incompresible ocupa todo el volumen ({VL:.6g} m3 >= V "
                                 f"{V:.6g} m3): la presión no está determinada en este paquete.")
        sem = [semilla]

        def tp(P):
            # TP con semilla de la evaluacion anterior: Newton sobre el conjunto de fases previo y prueba
            # de estabilidad completa del resultado (flash_rapido); cae al TP completo si cambia el conjunto.
            try:
                e = self.flash_rapido("TP", T, P, n, sem[0]) if sem[0] is not None else self._TP_seguro(T, P, n)
            except FueraDeAlcance as x:
                if x.motivo != "saturacion":
                    raise
                e = self._TP_seguro(T, P, n)
            sem[0] = e
            return e
        f = lambda P: tp(P).V - V
        P_lo, P_hi = P_MIN, P_MAX
        if f(P_lo) < 0:
            raise FueraDeAlcance("fuera_de_dominio", "La presión del estado queda bajo el dominio.", P_fuera=True)
        if f(P_hi) > 0:
            raise FueraDeAlcance("fuera_de_dominio", "La presión del estado queda sobre el dominio (5e5 Pa).",
                                 P_fuera=True)
        lnP = brentq(lambda q: f(math.exp(q)), math.log(P_lo), math.log(P_hi), xtol=rtol, rtol=max(rtol, 1e-15),
                     maxiter=300)
        e = tp(math.exp(lnP))
        if abs(e.V - V) > max(1e-9, 100 * rtol) * V:
            # salto en P: coexistencia invariante a esta T (p. ej. LLV de un binario o la curva de un puro)
            # los lados del salto deben abarcar la tolerancia de la busqueda (holgada en la semilla de UV)
            e2 = self._meseta_general(T, e.P, n, "P", "v", V, delta=max(1e-9, 4 * rtol * (1 + abs(lnP))))
            if e2 is None:
                raise FueraDeAlcance("no_convergente", "TV: la búsqueda en P no converge ni es una coexistencia "
                                     "invariante.")
            e = e2
        e.especificacion = "TV"
        return e

    def equilibrio_UV(self, U, V, n):
        n = np.asarray(n, dtype=float)
        T_lo, T_hi = self.T_rango

        ult = [None]

        def F(T):
            e = self.equilibrio_TV(T, V, n, semilla=ult[0], rtol=1e-7)     # busqueda holgada: solo semilla
            ult[0] = e
            return e.U - U
        try:
            f_lo = F(T_lo)
        except FueraDeAlcance:
            f_lo = None
        try:
            f_hi = F(T_hi)
        except FueraDeAlcance as x_hi:
            if x_hi.motivo != "fuera_de_dominio":
                raise
            # El extremo caliente no es evaluable (a V fijo la presion supera el dominio): se busca la T mas alta
            # evaluable. Si alli U todavia es menor que la pedida, el estado esta fuera del dominio.
            f_hi = None
            for Tm in np.linspace(T_hi, T_lo, 60)[1:]:
                try:
                    f_hi = F(Tm)
                    T_hi = Tm
                    break
                except FueraDeAlcance as x_m:
                    if x_m.motivo != "fuera_de_dominio":
                        raise
                    continue
            if f_hi is None:
                raise FueraDeAlcance("fuera_de_dominio", "Sin estado evaluable en el dominio con ese V.", T_fuera=True)
            if f_hi < 0:
                raise FueraDeAlcance("fuera_de_dominio", f"U = {U:.9g} J con V = {V:.6g} m3 exige una presion por "
                                     f"encima del dominio ({P_MAX:g} Pa).", P_fuera=True)
        if f_lo is not None and f_lo > 0 or f_hi < 0:
            raise FueraDeAlcance("fuera_de_dominio", f"U = {U:.9g} J con V = {V:.6g} m3 exige T fuera del dominio.",
                                 T_fuera=True)
        if f_lo is None:
            # el extremo frio no es evaluable (P bajo dominio); se busca el primer T valido
            Ts = np.linspace(T_lo, T_hi, 60)
            for Tm in Ts:
                try:
                    f_lo = F(Tm)
                    T_lo = Tm
                    break
                except FueraDeAlcance:
                    continue
            if f_lo is None or f_lo > 0:
                raise FueraDeAlcance("fuera_de_dominio", "Sin estado evaluable en el dominio.", T_fuera=True)
        T = brentq(F, T_lo, T_hi, xtol=1e-3, maxiter=300)
        try:
            # Newton exacto en (T, P, repartos) desde el estado aproximado; certifica estabilidad
            e = self._newton("UV", U, V, n, ult[0])
        except (_Completo, np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError):
            T = brentq(F, max(T_lo, T - 0.01), min(T_hi, T + 0.01), xtol=1e-300, rtol=1e-14, maxiter=300)
            e = self.equilibrio_TV(T, V, n, semilla=ult[0])
        e.especificacion = "UV"
        return e


def _softmax3(zz):
    e = np.exp(np.array([zz[0], zz[1], 0.0]) - max(zz[0], zz[1], 0.0))
    return e / e.sum()


def _T_saturacion(self, P, i):
    """T de coexistencia del componente puro i a P en este modelo, o None."""
    e = self.esp[i]
    lo, hi = max(self.T_rango[0], e.T_rango[0]), min(self.T_rango[1], e.T_rango[1])
    f = lambda T: self.P_saturacion(T, i) - P
    if f(lo) > 0 or f(hi) < 0:
        return None
    return brentq(f, lo, hi, xtol=1e-300, rtol=1e-15)


Sistema.T_saturacion = _T_saturacion


# ----------------------------------------------------------------------
# Flash rapido con semilla (evaluaciones internas del coordinador dinamico)
# ----------------------------------------------------------------------
def flash_rapido(self, espec, a, b, n, semilla):
    """Estado de equilibrio para espec in {'TP','PH','UP','UV'} con (a, b) =
    (T, P), (P, H), (P, U) o (U, V) y cantidades n, partiendo del conjunto de
    fases y composiciones de `semilla` (un EstadoMezcla previo).

    Newton sobre [T, ln P (solo UV), ln n_i^a de todas las fases menos la
    ultima] con residuos (mu_i^a - mu_i^ultima)/RT y la(s) restriccion(es)
    energetica/volumetrica escaladas. Despues: todas las fases con cantidad
    positiva y prueba de estabilidad (vapor analitica + liquido en malla).
    Si algo falla se usa la operacion completa certificada (equilibrio_*).
    La semilla solo es el punto de partida: no fija ninguna propiedad."""
    sem = semilla
    for _ in range(3):
        try:
            return self._newton(espec, a, b, n, sem)
        except _NuevaSemilla as x:
            sem = x.semilla                  # conjunto de fases corregido: se repite el Newton
        except (_Completo, np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError):
            break
    try:
        raise _Completo()
    except _Completo:
        if espec == "TP":
            return self.equilibrio_TP(a, b, n)
        if espec == "PH":
            return self.equilibrio_PH(a, b, n, semilla=semilla)
        if espec == "UP":
            return self.equilibrio_UP(a, b, n, semilla=semilla)
        return self.equilibrio_UV(a, b, n)


def _newton(self, espec, a, b, n, semilla):
    """Newton con semilla (ver flash_rapido); _Completo si no converge o cambia el conjunto de fases."""
    n = np.asarray(n, dtype=float)
    idx = [i for i in range(len(n)) if n[i] > 0]
    if True:
        if semilla is None or len(idx) == 1:
            raise _Completo()
        # la fase mas abundante al final: es la que se obtiene por diferencia (ver _pulir)
        fs_sem = sorted(semilla.fases, key=lambda f: f.n)
        tipos = [f.tipo for f in fs_sem]
        nz = n[idx]
        k = len(tipos)
        # composiciones de la semilla escaladas a las cantidades actuales
        part = [np.maximum(f.n * f.x[idx], 1e-300) for f in fs_sem]
        tot = np.sum(part, axis=0)
        part = [p * nz / tot for p in part]
        T = semilla.T
        P = semilla.P if espec in ("TP", "UV") else a
        if espec == "TP":
            T, P = a, b
        x0 = [] if espec == "TP" else [T]
        if espec == "UV":
            x0.append(math.log(P))
        x0 += list(np.log(np.concatenate(part[:-1]))) if k > 1 else []
        x0 = np.array(x0, dtype=float)
        m = len(idx)

        def desempaquetar(v):
            j = 0
            Tv, Pv = T, P
            if espec != "TP":
                Tv = v[0]
                j = 1
            if espec == "UV":
                Pv = math.exp(v[1])
                j = 2
            elif espec in ("PH", "UP"):
                Pv = a
            ps = [np.exp(v[j + q * m:j + (q + 1) * m]) for q in range(k - 1)]
            ult = nz - np.sum(ps, axis=0) if k > 1 else nz.copy()
            return Tv, Pv, ps + [ult]

        def F(v):
            Tv, Pv, ps = desempaquetar(v)
            if ps[-1].min() <= 0 or not self.T_rango[0] * 0.98 <= Tv <= self.T_rango[1] * 1.02:
                return None
            RT = R * Tv
            res = []
            if k > 1:
                mus = [self.mu(t, Tv, Pv, p / p.sum(), idx) for t, p in zip(tipos, ps)]
                for q in range(k - 1):
                    res.extend((mus[q] - mus[-1]) / RT)
            if espec != "TP":
                fs = [self.fase("x", t, Tv, Pv, p, idx) for t, p in zip(tipos, ps)]
                Hs = sum(f.n * f.h for f in fs)
                Vs = sum(f.n * f.v for f in fs)
                escala = RT * nz.sum()
                if espec == "PH":
                    res.append((Hs - b) / escala)
                elif espec == "UP":
                    res.append((Hs - Pv * Vs - b) / escala)
                else:
                    res.append((Hs - Pv * Vs - a) / escala)
                    res.append((Vs - b) / b)
            return np.array(res)
        v = x0.copy()
        f = F(v)
        if f is None:
            raise _Completo()
        for _ in range(40):
            if np.max(np.abs(f)) < 1e-13:
                break
            J = np.empty((len(v), len(v)))
            for j in range(len(v)):
                d = np.zeros_like(v)
                d[j] = 1e-7 * max(1.0, abs(v[j]))
                fp, fm_ = F(v + d), F(v - d)
                if fp is None or fm_ is None:
                    raise _Completo()
                J[:, j] = (fp - fm_) / (2 * d[j])
            paso = np.linalg.solve(J, -f)
            al = 1.0
            for _ in range(25):
                fn = F(v + al * paso)
                if fn is not None and np.max(np.abs(fn)) < np.max(np.abs(f)):
                    v, f = v + al * paso, fn
                    break
                al *= 0.5
            else:
                break
        if np.max(np.abs(f)) > 1e-10:
            raise _Completo()
        Tv, Pv, ps = desempaquetar(v)
        self.dominio(Tv, Pv)
        if any(p.sum() <= N_AUSENTE * nz.sum() for p in ps):
            # una fase se agota: se repite sin ella (si queda alguna); si no, operacion completa
            restantes = [(t, p) for t, p in zip(tipos, ps) if p.sum() > N_AUSENTE * nz.sum()]
            if not restantes or len(restantes) == len(tipos):
                raise _Completo()
            raise _NuevaSemilla(self._semilla_de(Tv, Pv, n, idx, restantes))
        fases = list(zip(tipos, ps))
        mu_ref = self.mu(tipos[0], Tv, Pv, ps[0] / ps[0].sum(), idx)
        pr = self.prueba_estabilidad(Tv, Pv, mu_ref, idx, incluir_vapor="vapor" not in tipos)
        nuevas_pr = _candidatas_nuevas(pr, [(t, p / p.sum()) for t, p in fases])
        peor = min(nuevas_pr, key=lambda q: q[2]) if nuevas_pr else (None, None, 0.0)
        if peor[2] < -TM_INTENTO:
            # fase inestable: se anade la de prueba con una cantidad pequena y se repite el Newton
            if len(tipos) >= MAX_FASES:
                raise _Completo()
            nueva = 1e-3 * nz.sum() * peor[1]
            ps2 = [p.copy() for p in ps]
            ps2[0] = ps2[0] - np.minimum(nueva, 0.5 * ps2[0])
            raise _NuevaSemilla(self._semilla_de(Tv, Pv, n, idx, list(zip(tipos, ps2)) + [(peor[0], np.minimum(nueva, 0.5 * ps[0]))]))
        e = self._empaquetar(espec, Tv, Pv, n, idx, fases)
        tm_min = min(p[2] for p in pr)
        e.verificaciones["equilibrio"] = (self._residuo_mu(e, idx), TOL_MU,
                                          "max |mu_i^a - mu_i^b|/(R T) entre fases presentes (Newton con semilla)")
        e.verificaciones["estabilidad"] = (max(0.0, -tm_min), TOL_TM,
                                           "-min tm sobre fases de prueba vapor (minimo analitico) y liquido "
                                           "(malla en el simplex y refinamiento local)")
        e.estabilidad = {"tm_min": tm_min, "pruebas": len(pr), "candidatas": sorted({p[0] for p in pr} | set(tipos))}
        return e


class _Completo(Exception):
    pass


Sistema.flash_rapido = flash_rapido
Sistema._newton = _newton


class _NuevaSemilla(Exception):
    def __init__(self, semilla):
        super().__init__("nueva semilla")
        self.semilla = semilla


def _semilla_de(self, T, P, n, idx, fases):
    """EstadoMezcla minimo para sembrar el Newton con un conjunto de fases dado."""
    objs = [self.fase(f"s{k}", t, T, P, nf, idx) for k, (t, nf) in enumerate(fases)]
    return EstadoMezcla(especificacion="semilla", T=T, P=P, especies=self.cas, n=np.asarray(n, dtype=float),
                        fases=objs)


Sistema._semilla_de = _semilla_de


def _candidatas_nuevas(pruebas, presentes, tol=1e-5):
    """Fases de prueba que NO son una fase ya presente (mismo tipo y composicion a tol). La prueba de
    estabilidad sobre un equilibrio encuentra tm ~ 0 en las propias fases coexistentes; con ruido de
    malla ese valor puede salir -1e-10 y no debe tomarse como una fase nueva."""
    return [p for p in pruebas if not any(p[0] == t and np.max(np.abs(np.asarray(p[1]) - x)) < tol
                                          for t, x in presentes)]


def _meseta_general(self, T, P, n, eje, y_nombre, objetivo, delta=1e-9):
    """Estado sobre un salto de la propiedad de equilibrio (coexistencia invariante a esta T, P): las
    fases de ambos lados del salto (por TP a T, P desplazados `delta` relativo en `eje`) coexisten con
    composiciones fijas; sus cantidades salen de los balances de materia por componente mas la
    restriccion `y_nombre` ('h', 'u' o 'v') = objetivo, con cantidades no negativas (NNLS). Certificado
    con la igualdad de potenciales entre esas fases y la prueba de plano tangente. None si no es una
    coexistencia invariante (residuos grandes)."""
    from scipy.optimize import nnls
    n = np.asarray(n, dtype=float)
    idx = [i for i in range(len(n)) if n[i] > 0]
    lados = []
    for f in (1 - delta, 1 + delta):
        try:
            lados.append(self.equilibrio_TP(T * f, P, n) if eje == "T" else self.equilibrio_TP(T, P * f, n))
        except FueraDeAlcance:
            return None
    cand = []
    for e in lados:
        for f in e.fases:
            if not any(t == f.tipo and np.max(np.abs(x - f.x)) < max(1e-5, 1e3 * delta) for t, x in cand):
                cand.append((f.tipo, f.x.copy()))
    if len(cand) < 2:
        return None
    tol_mu = 1e-7
    if len(cand) == len(idx) + 1:
        # Punto invariante (regla de las fases: C + 1 fases a P o T fija): se resuelve EXACTAMENTE con
        # Newton en (ln T o ln P, composiciones de cada fase): (k-1) m ecuaciones mu_i^a = mu_i^0 y
        # 1 + k (m-1) incognitas, cuadrado para k = m + 1. Las composiciones de los lados del salto
        # (a 1e-9 relativo) son la semilla; sin pulir, la tangente comun queda a ~1e-8.
        pul = _pulir_invariante(self, T, P, eje, cand, idx)
        if pul is not None:
            T, P, cand = pul
            tol_mu = TOL_MU
    objs = [self.fase("c", t, T, P, np.maximum(x[idx], 1e-300), idx) for t, x in cand]
    y = [(o.h if y_nombre == "h" else o.h - P * o.v if y_nombre == "u" else o.v) for o in objs]
    A = np.vstack([np.array([o.x[i] for o in objs]) for i in idx] + [np.array(y)])
    b = np.concatenate([n[idx], [objetivo]])
    escala = np.concatenate([np.full(len(idx), 1.0 / n.sum()), [1.0 / max(abs(objetivo), 1e-300)]])
    amounts, res = nnls(A * escala[:, None], b * escala)
    if res > 1e-9:
        return None
    fases = [(t, amounts[k] * x[idx]) for k, (t, x) in enumerate(cand) if amounts[k] > N_AUSENTE * n.sum()]
    e = self._empaquetar("meseta", T, P, n, idx, fases)
    RT = R * T
    ref = e.fases[0].mu[idx]
    res_mu = max(float(np.max(np.abs(f.mu[idx] - ref))) for f in e.fases) / RT
    pr = self.prueba_estabilidad(T, P, ref, idx, incluir_vapor=True)
    tm_min = min(q[2] for q in pr)
    e.verificaciones["equilibrio"] = (res_mu, tol_mu, "coexistencia invariante: max |mu_i^a - mu_i^b|/(R T) entre "
                                      "las fases de ambos lados del salto (punto invariante resuelto por Newton "
                                      "cuando hay C + 1 fases)")
    e.verificaciones["estabilidad"] = (max(0.0, -tm_min), TOL_TM, "-min tm con la mu de la coexistencia")
    e.estabilidad = {"tm_min": tm_min, "pruebas": len(pr), "candidatas": ["liquido", "vapor"]}
    if res_mu > tol_mu or tm_min < -TOL_TM:
        return None
    return e


def _pulir_invariante(self, T, P, eje, cand, idx):
    """Newton para el punto invariante con las fases `cand` (k = m + 1). Composiciones en coordenadas
    softmax respecto de la ultima especie (positivas y normalizadas). Devuelve (T, P, cand) o None."""
    m = len(idx)
    k = len(cand)
    tipos = [t for t, _ in cand]

    def a_x(zs):
        e = np.exp(np.concatenate([zs, [0.0]]))
        return e / e.sum()

    def desempaquetar(v):
        Tv, Pv = (math.exp(v[0]), P) if eje == "T" else (T, math.exp(v[0]))
        xs = [a_x(v[1 + a * (m - 1):1 + (a + 1) * (m - 1)]) for a in range(k)]
        return Tv, Pv, xs

    def F(v):
        Tv, Pv, xs = desempaquetar(v)
        mus = [self.mu(t, Tv, Pv, x, idx) for t, x in zip(tipos, xs)]
        return np.concatenate([(mus[a] - mus[0]) / (R * Tv) for a in range(1, k)])
    v = [math.log(T if eje == "T" else P)]
    for _, x in cand:
        xx = np.maximum(x[idx], 1e-300)
        v.extend(np.log(xx[:-1] / xx[-1]))
    v = np.array(v)
    try:
        f = F(v)
        for _ in range(40):
            if np.max(np.abs(f)) < 1e-14:
                break
            J = np.empty((len(v), len(v)))
            for j in range(len(v)):
                d = np.zeros_like(v)
                d[j] = 1e-7
                J[:, j] = (F(v + d) - F(v - d)) / 2e-7
            paso = np.linalg.solve(J, -f)
            a = 1.0
            for _ in range(30):
                fn = F(v + a * paso)
                if np.max(np.abs(fn)) < np.max(np.abs(f)):
                    v, f = v + a * paso, fn
                    break
                a *= 0.5
            else:
                break
    except (np.linalg.LinAlgError, FloatingPointError, ValueError, FueraDeAlcance):
        return None
    if not np.max(np.abs(f)) < 1e-12:
        return None
    Tv, Pv, xs = desempaquetar(v)
    if abs(Tv / T - 1) > 1e-6 or abs(Pv / P - 1) > 1e-6:
        return None          # el Newton se fue a otro punto: no es el salto encontrado
    sal = []
    for (t, x0), xr in zip(cand, xs):
        x = np.zeros_like(x0)
        x[idx] = xr
        sal.append((t, x))
    return Tv, Pv, sal


Sistema._meseta_general = _meseta_general


def _huella(self):
    """Huella de los DATOS y PARAMETROS del paquete configurado (no de una consulta): identidad y version del
    paquete, CAS en orden, datos de cada especie (Psat, cp, v_L, M, rangos y fuentes), modelo de liquido con
    sus parametros binarios, procedencia, referencia y dominio. Cambia si cambia cualquier dato aunque el
    `modelo.id` siga igual. Independiente del orden en que se declaren los componentes."""
    import dataclasses
    import hashlib
    import json
    orden = sorted(range(len(self.cas)), key=lambda k: self.cas[k])
    liq = {"modelo": type(self.liq).__name__}
    if hasattr(self.liq, "identidad"):
        liq["unifac"] = self.liq.identidad()     # variante, asignaciones, R/Q, interacciones usadas y sha256 de tablas
    for nombre in ("a", "b", "alpha"):
        if hasattr(self.liq, nombre):
            m = np.asarray(getattr(self.liq, nombre), dtype=float)[np.ix_(orden, orden)]
            liq[nombre] = [[float(repr_ := v) for v in fila] for fila in m.tolist()]
    datos = {
        "paquete": [self.paquete.id, self.paquete.version, self.paquete.liquido],
        "cas": [self.cas[k] for k in orden],
        "especies": [dataclasses.asdict(self.esp[k]) for k in orden],
        "liquido": liq,
        "procedencia": self.procedencia,
        "referencia": REFERENCIA,
        "dominio": {"T": list(self.T_rango), "P": [P_MIN, P_MAX]},
        "tolerancias": {"TOL_TM": TOL_TM, "TOL_MU": TOL_MU},
    }
    if getattr(self, "sustituciones", None):
        datos["sustituciones"] = self.sustituciones          # datos y FUENTES sustituidos (F2.4)
    texto = json.dumps(datos, sort_keys=True, separators=(",", ":"), default=repr)
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


Sistema.huella = _huella


# ----------------------------------------------------------------------
# Estabilidad de dimension general (N >= 2 especies activas; usada para N >= 4)
# ----------------------------------------------------------------------
SEMILLA_ESTABILIDAD = 12345
METODO_ESTABILIDAD_GENERAL = (
    "distancia al plano tangente de Michelsen sobre la mu de referencia del paquete: sustitucion sucesiva "
    "(ln W_i = d_i - ln gamma_i(w)) desde los N vertices puros, la estimacion ideal (gamma = 1) y 2^ceil(log2(8N)) "
    "puntos Sobol del simplex (scipy.stats.qmc, aleatorizacion con semilla fija 12345), pulida con L-BFGS-B en "
    "beta_i = 2 sqrt(W_i) >= 0 (las caras y vertices del simplex, W_i = 0, pertenecen al dominio). Una busqueda "
    "finita multisemilla NO demuestra el minimo global.")


def _estabilidad_general(self, T, P, mu_ref, idx):
    """[('liquido', w, tm)] minimos locales distintos de tm(w) = sum w_i (mu_i^L(w) - mu_ref_i)/RT."""
    from scipy.optimize import minimize as _min
    from scipy.stats import qmc
    n = len(idx)
    RT = R * T
    gL = self._g_puros(T, P)[1][idx]
    d = (np.asarray(mu_ref, dtype=float) - gL) / RT
    modelo = self._modelo_sub(idx)

    def lng(w):
        return modelo.lngamma(T, w)

    def tm_norm(w):
        w = np.asarray(w, dtype=float)
        m = w > 0
        return float(np.sum(w[m] * (np.log(w[m]) + lng(w)[m] - d[m])))

    def tm_estrella(beta):
        W = (beta / 2.0) ** 2
        S = W.sum()
        if not S > 0:
            return 1.0, np.zeros_like(beta)
        w = W / S
        lg = lng(w)
        m = W > 0
        lnW = np.where(m, np.log(np.where(m, W, 1.0)), 0.0)
        f = 1.0 + float(np.sum(np.where(m, W * (lnW + lg - d - 1.0), 0.0)))
        g = np.where(m, np.sqrt(W) * (lnW + lg - d), 0.0)
        return f, g

    # semillas deterministas
    arranques = [np.eye(n)[k] for k in range(n)]
    w_id = np.exp(d - d.max())
    arranques.append(w_id / w_id.sum())
    m_sob = int(2 ** math.ceil(math.log2(8 * n)))
    U = qmc.Sobol(d=n - 1, scramble=True, seed=SEMILLA_ESTABILIDAD).random(m_sob)
    for u in U:
        c = np.sort(np.concatenate([[0.0], u, [1.0]]))
        arranques.append(np.diff(c))
    # sustitucion sucesiva de TODOS los arranques a la vez (ln gamma por lotes); se pulen solo los distintos
    Wm = np.array(arranques, dtype=float)
    for _ in range(60):
        lnW = d[None, :] - modelo.lngamma_lote(T, Wm)
        Wn = np.exp(lnW - lnW.max(axis=1, keepdims=True))
        Wn /= Wn.sum(axis=1, keepdims=True)
        cambio = np.max(np.abs(Wn - Wm))
        Wm = Wn
        if cambio < 1e-12:
            break
    candidatos = []
    for w in Wm:
        if not any(np.max(np.abs(w - c)) < 1e-6 for c in candidatos):
            candidatos.append(w)
    minimos = []
    for w in candidatos:
        # pulido en beta, con escala del total de la iteracion
        lnW = d - lng(w)
        W0 = np.exp(np.minimum(lnW, 50.0))
        beta0 = 2.0 * np.sqrt(W0)
        try:
            r = _min(lambda b: tm_estrella(b), beta0, jac=True, method="L-BFGS-B",
                     bounds=[(0.0, None)] * n, options={"ftol": 1e-15, "gtol": 1e-12, "maxiter": 500})
            W = (r.x / 2.0) ** 2
            if W.sum() > 0:
                w = W / W.sum()
        except (ValueError, FloatingPointError, OverflowError):
            pass
        tm = tm_norm(w)
        if not math.isfinite(tm):
            continue
        if not any(np.max(np.abs(w - w2)) < 1e-6 for w2, _ in minimos):
            minimos.append((w, tm))
    self.__dict__["_ultima_estabilidad_general"] = {"arranques": len(arranques), "candidatos": len(candidatos),
                                                    "minimos": len(minimos), "semilla": SEMILLA_ESTABILIDAD}
    return [("liquido", w, float(tm)) for w, tm in minimos]


Sistema._estabilidad_general = _estabilidad_general



def _jacobiano_reparto(self, T, P, tipos, z, nz, idx, m, k):
    """Jacobiano de F_a = (mu^a - mu^resto)/RT respecto de ln n^b_j (b < k-1), desacoplado por fase.

    Cada mu^a depende solo de las cantidades de su fase; la fase resto es n - sum de las demas. Con una
    diferencia finita global en ln n, una fase diminuta (p. ej. 1e-9 mol junto a una frontera) mueve el resto
    menos que el ruido de redondeo de su mu y la direccion de su cantidad total queda dominada por ruido: el
    Newton se estanca. Aqui: dmu^a/d ln n^a_j por diferencia en la propia fase a, y dmu^resto/dn^resto_j por
    diferencia con paso proporcional a la cantidad del resto, combinados por la regla de la cadena:
        dF_a/d ln n^b_j = delta_ab dmu^a/d ln n^a_j / RT + n^b_j dmu^resto/dn^resto_j / RT."""
    RT = R * T
    ps = [np.exp(z[a * m:(a + 1) * m]) for a in range(k - 1)]
    ult = nz - np.sum(ps, axis=0)
    if ult.min() <= 0:
        return None

    def mu_de(tipo, cant):
        return self.mu(tipo, T, P, cant / cant.sum(), idx)
    try:
        # derivada del resto respecto de sus propias cantidades
        D_ult = np.empty((m, m))
        for j in range(m):
            h = 1e-6 * ult[j]
            up, um = ult.copy(), ult.copy()
            up[j] += h
            um[j] -= h
            D_ult[:, j] = (mu_de(tipos[-1], up) - mu_de(tipos[-1], um)) / (2 * h)
        J = np.zeros(((k - 1) * m, (k - 1) * m))
        for a in range(k - 1):
            for j in range(m):
                d = 1e-6
                pp, pm = ps[a].copy(), ps[a].copy()
                pp[j] *= math.exp(d)
                pm[j] *= math.exp(-d)
                col = (mu_de(tipos[a], pp) - mu_de(tipos[a], pm)) / (2 * d) / RT
                J[a * m:(a + 1) * m, a * m + j] += col
            for b in range(k - 1):
                for j in range(m):
                    J[a * m:(a + 1) * m, b * m + j] += ps[b][j] * D_ult[:, j] / RT
    except (FloatingPointError, ValueError, OverflowError):
        return None
    return J


Sistema._jacobiano_reparto = _jacobiano_reparto
