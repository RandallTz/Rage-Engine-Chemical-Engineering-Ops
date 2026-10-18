"""
UNIFAC como modelo de energia de Gibbs de exceso del liquido (frontend/CONTRATO_CLAUDE_UNIFAC_MOTOR.md).

Implementacion propia, vectorizada y valida con T compleja (paso complejo para d(g^E)/dT), sobre DATOS
FIJADOS que distribuye thermo 0.6.1 (no sobre sus objetos UNIFAC, que mutan T y x y no son seguros entre
hilos). La implementacion de thermo se usa como contraste independiente en las pruebas.

Variantes (cada una con su tabla de subgrupos, grupos principales, R, Q, interacciones y asignaciones):
  original  - Fredenslund, Jones y Prausnitz (1975); subgrupos UFSG, interacciones UFIP a_mn [K]
              (archivo 'UNIFAC original interaction parameters.tsv'), Psi = exp(-a_mn/T);
              combinatorio de Staverman-Guggenheim con z = 10.
  dortmund  - Weidlich y Gmehling (1987), Gmehling et al.; subgrupos DOUFSG, interacciones DOUFIP2016
              (a, b, c), Psi = exp(-(a + b T + c T^2)/T); combinatorio con r^(3/4).
  lle       - Magnussen, Rasmussen y Fredenslund (1981), tabla dedicada a ELL: subgrupos LLEUFSG, interacciones
              'UNIFAC LLE interaction parameters.tsv' a_mn [K]; mismas ecuaciones que la original. Ajustada a
              datos de ELL entre 10 y 40 C: el paquete declara ese intervalo como dominio en T.
Asignaciones de grupos: base DDBST distribuida con thermo ('DDBST UNIFAC assignments.tsv'), por variante. Para
'lle' no hay asignaciones propias: se TRADUCE la asignacion DDBST original subgrupo a subgrupo, solo si existe
en la tabla LLE un unico subgrupo con el mismo nombre y los mismos R y Q (misma definicion quimica); si no, la
especie no tiene asignacion (p. ej. metanol: la tabla LLE no tiene el grupo CH3OH).

Ecuaciones (original):
  ln gamma_i = ln gamma_i^C + ln gamma_i^R
  ln gamma_i^C = ln(phi_i/x_i) + (z/2) q_i ln(theta_i/phi_i) + l_i - (phi_i/x_i) sum_j x_j l_j
      phi_i/x_i = r_i / sum_j r_j x_j,  theta_i/phi_i = (q_i/sum q x) / (r_i/sum r x),
      l_i = (z/2)(r_i - q_i) - (r_i - 1)       (definidos tambien en x_i = 0: dilucion infinita)
  ln gamma_i^R = sum_k nu_ki (ln Gamma_k - ln Gamma_k^(i))
  ln Gamma_k = Q_k [1 - ln(sum_m Theta_m Psi_mk) - sum_m Theta_m Psi_km / sum_n Theta_n Psi_nm]
Una interaccion ausente entre dos grupos principales presentes es un diagnostico, nunca cero; dos subgrupos
del mismo grupo principal tienen a = 0 por definicion del modelo.
"""

import hashlib
import json
import os

import numpy as np

from core import mezclas_datos as datos

VARIANTES = ("original", "dortmund", "lle")
_ARCHIVOS = {"original": "UNIFAC original interaction parameters.tsv",
             "dortmund": "UNIFAC modified Dortmund interaction parameters.tsv",
             "lle": "UNIFAC LLE interaction parameters.tsv"}
_MODELO_ASIGNACION = {"original": "UNIFAC", "dortmund": "MODIFIED_UNIFAC", "lle": "UNIFAC"}
# Intervalo de T de los datos de ajuste de la tabla (solo cuando la fuente lo acota): dominio del paquete.
RANGO_T = {"lle": (283.15, 313.15)}
_TABLAS = {}


class FaltaDatoUNIFAC(Exception):
    """Asignacion de grupos, definicion de grupo o interaccion ausente. `detalle` identifica el origen."""

    def __init__(self, mensaje, detalle):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def tablas(variante):
    """Tablas fijadas e inmutables de una variante (carga unica, bajo el cerrojo de datos externos)."""
    if variante not in VARIANTES:
        raise ValueError(variante)
    if variante in _TABLAS:
        return _TABLAS[variante]
    with datos.CARGA_DATOS:
        if variante in _TABLAS:
            return _TABLAS[variante]
        import thermo
        import thermo.unifac as tu
        tu.load_unifac_ip()
        tu.load_group_assignments_DDBST()
        if variante == "original":
            SG, IP = tu.UFSG, tu.UFIP
            inter = {(int(m), int(n)): (float(v), 0.0, 0.0) for m, d in IP.items() for n, v in d.items()}
        elif variante == "lle":
            SG, IP = tu.LLEUFSG, tu.LLEUFIP
            inter = {(int(m), int(n)): (float(v), 0.0, 0.0) for m, d in IP.items() for n, v in d.items()}
        else:
            SG, IP = tu.DOUFSG, tu.DOUFIP2016
            inter = {(int(m), int(n)): tuple(float(x) for x in v) for m, d in IP.items() for n, v in d.items()}
        sub = {int(k): (int(g.main_group_id), float(g.R), float(g.Q), str(g.group)) for k, g in SG.items()}
        carpeta = os.path.join(os.path.dirname(tu.__file__), "Phase Change")
        ident = {
            "variante": variante,
            "fuente_interacciones": f"thermo {thermo.__version__}: '{_ARCHIVOS[variante]}' "
                                    "(parametros publicados por DDBST, tal como los distribuye thermo)",
            "sha256_interacciones": _sha256(os.path.join(carpeta, _ARCHIVOS[variante])),
            "fuente_asignaciones": f"thermo {thermo.__version__}: 'DDBST UNIFAC assignments.tsv' "
                                   f"(modelo {_MODELO_ASIGNACION[variante]})",
            "sha256_asignaciones": _sha256(os.path.join(carpeta, "DDBST UNIFAC assignments.tsv")),
            "fuente_subgrupos": f"thermo {thermo.__version__}: "
                                + {"original": "UFSG", "dortmund": "DOUFSG", "lle": "LLEUFSG"}[variante],
        }
        if variante == "lle":
            ident["fuente_asignaciones"] = (f"thermo {thermo.__version__}: 'DDBST UNIFAC assignments.tsv' (modelo UNIFAC) "
                                            "traducida a LLEUFSG por nombre de subgrupo con R y Q identicos")
            ident["rango_T_datos"] = list(RANGO_T["lle"])
            ident["fuente_tabla"] = ("Magnussen, Rasmussen y Fredenslund, Ind. Eng. Chem. Process Des. Dev. 20 (1981) "
                                     "331-339, doi:10.1021/i200013a024 (ELL, 10-40 C)")
        _TABLAS[variante] = {"sub": sub, "inter": inter, "ident": ident, "asignar": tu.UNIFAC_group_assignment_DDBST}
        return _TABLAS[variante]


def asignacion(cas, variante):
    """{subgrupo: cuenta} de la base DDBST para la variante; FaltaDatoUNIFAC si no hay asignacion."""
    if variante == "lle":
        return _asignacion_traducida(cas)
    t = tablas(variante)
    with datos.CARGA_DATOS:
        try:
            a = t["asignar"](cas, _MODELO_ASIGNACION[variante])
        except Exception:
            a = None
    if not a:
        raise FaltaDatoUNIFAC(f"Sin asignacion de grupos UNIFAC ({variante}) para {cas} en la base DDBST.",
                              {"tipo": "asignacion_ausente", "cas": cas, "variante": variante})
    for k in a:
        if int(k) not in t["sub"]:
            raise FaltaDatoUNIFAC(f"El subgrupo {k} asignado a {cas} no existe en la tabla {variante}.",
                                  {"tipo": "grupo_desconocido", "cas": cas, "subgrupo": int(k), "variante": variante})
    return {int(k): int(v) for k, v in a.items()}


def _asignacion_traducida(cas):
    """Asignacion LLE por traduccion de la DDBST original: cada subgrupo original se sustituye por el UNICO
    subgrupo LLE con el mismo nombre, R y Q. Sin traduccion univoca: asignacion ausente (nunca aproximada)."""
    orig, t = tablas("original"), tablas("lle")
    sal = {}
    for k, n in asignacion(cas, "original").items():
        nombre, R_, Q_ = orig["sub"][k][3], orig["sub"][k][1], orig["sub"][k][2]
        cand = [j for j, g in t["sub"].items() if g[3] == nombre and g[1] == R_ and g[2] == Q_]
        if len(cand) != 1:
            raise FaltaDatoUNIFAC(
                f"Sin asignacion de grupos UNIFAC (lle) para {cas}: el subgrupo original {k} ({nombre}) "
                f"{'no existe' if not cand else 'no es univoco'} en la tabla LLE con los mismos R y Q.",
                {"tipo": "asignacion_ausente", "cas": cas, "variante": "lle", "subgrupo_original": int(k),
                 "nombre": nombre})
        sal[cand[0]] = sal.get(cand[0], 0) + n
    return sal


class LiquidoUNIFAC:
    """g^E de UNIFAC para un conjunto ordenado de especies. Inmutable: los arrays no se pueden escribir."""

    def __init__(self, cas, variante, _asig=None):
        t = tablas(variante)
        self.variante = variante
        self.rango_T = RANGO_T.get(variante)
        self.nombre = f"UNIFAC {variante} (DDBST publicado, distribuido con thermo)"
        self.cas = tuple(cas)
        asig = _asig if _asig is not None else {c: asignacion(c, variante) for c in cas}
        self.asignaciones = {c: dict(asig[c]) for c in cas}
        grupos = sorted({k for c in cas for k in asig[c]})
        self.subgrupos = tuple(grupos)
        G = len(grupos)
        nu = np.zeros((len(cas), G))
        for i, c in enumerate(cas):
            for k, v in asig[c].items():
                nu[i, grupos.index(k)] = v
        main = [t["sub"][k][0] for k in grupos]
        Rk = np.array([t["sub"][k][1] for k in grupos])
        Qk = np.array([t["sub"][k][2] for k in grupos])
        A, B, C = np.zeros((G, G)), np.zeros((G, G)), np.zeros((G, G))
        usadas = {}
        for a in range(G):
            for b in range(G):
                m, n = main[a], main[b]
                if m == n:
                    continue
                if (m, n) not in t["inter"]:
                    raise FaltaDatoUNIFAC(
                        f"Falta la interaccion UNIFAC {variante} del grupo principal {m} con el {n} "
                        f"(subgrupos {grupos[a]} y {grupos[b]}).",
                        {"tipo": "interaccion_ausente", "grupos_principales": [m, n], "variante": variante,
                         "especies": [c for c in cas if grupos[a] in asig[c] or grupos[b] in asig[c]]})
                A[a, b], B[a, b], C[a, b] = t["inter"][(m, n)]
                usadas[f"{m}-{n}"] = t["inter"][(m, n)]
        self.interacciones_usadas = dict(sorted(usadas.items()))
        self._main = tuple(main)
        for arr in (nu, Rk, Qk, A, B, C):
            arr.setflags(write=False)
        self._nu, self._R, self._Q, self._A, self._B, self._C = nu, Rk, Qk, A, B, C
        self._r = nu @ Rk
        self._q = nu @ Qk
        self._r.setflags(write=False)
        self._q.setflags(write=False)
        self._cache_T = None

    # --- identidad para la huella ---------------------------------------------
    def identidad(self):
        t = tablas(self.variante)
        orden = sorted(range(len(self.cas)), key=lambda k: self.cas[k])
        return {"variante": self.variante, "datos": t["ident"],
                "asignaciones": {self.cas[k]: {str(g): n for g, n in sorted(self.asignaciones[self.cas[k]].items())}
                                 for k in orden},
                "subgrupos": {str(g): [t["sub"][g][0], t["sub"][g][1], t["sub"][g][2]] for g in self.subgrupos},
                "interacciones": self.interacciones_usadas}

    def subconjunto(self, idx):
        """El mismo modelo para las especies idx (mismas tablas y asignaciones; sin reconstruir de thermo)."""
        cas = [self.cas[i] for i in idx]
        return LiquidoUNIFAC(cas, self.variante, _asig={c: self.asignaciones[c] for c in cas})

    # --- evaluacion ----------------------------------------------------------
    def _psi(self, T):
        return np.exp(-(self._A + self._B * T + self._C * T * T) / T)

    def _lnGamma(self, T, Xg, psi):
        """ln Gamma_k para composiciones de grupo Xg (K x G, no normalizadas)."""
        Xg = Xg / Xg.sum(axis=1, keepdims=True)
        th = self._Q * Xg
        th = th / th.sum(axis=1, keepdims=True)
        S = th @ psi                               # S_k = sum_m Theta_m Psi_mk
        return self._Q * (1.0 - np.log(S) - (th / S) @ psi.T)

    def _por_T(self, T):
        """Psi(T) y ln Gamma_k de cada especie pura: solo dependen de T. Se guarda el ultimo T real (una tupla
        que se sustituye entera: segura entre hilos); con T compleja (paso complejo) no se guarda nada."""
        c = self._cache_T
        if c is not None and c[0] == T:
            return c[1], c[2]
        psi = self._psi(T)
        lnG_puro = self._lnGamma(T, self._nu.astype(float), psi)       # fila i = especie i pura
        if not isinstance(T, complex) and not np.iscomplexobj(T):
            self._cache_T = (T, psi, lnG_puro)
        return psi, lnG_puro

    def lngamma_lote(self, T, X):
        X = np.asarray(X)
        psi, lnG_puro = self._por_T(T)
        r, q = self._r, self._q
        if self.variante != "dortmund":                # original y lle: Staverman-Guggenheim, z = 10
            sr, sq = X @ r, X @ q
            phx = r[None, :] / sr[:, None]
            thph = (q[None, :] / sq[:, None]) / phx
            l = 5.0 * (r - q) - (r - 1.0)
            lnC = np.log(phx) + 5.0 * q[None, :] * np.log(thph) + l[None, :] - phx * (X @ l)[:, None]
        else:
            r34 = r ** 0.75
            V = r[None, :] / (X @ r)[:, None]
            Vp = r34[None, :] / (X @ r34)[:, None]
            F = q[None, :] / (X @ q)[:, None]
            lnC = 1.0 - Vp + np.log(Vp) - 5.0 * q[None, :] * (1.0 - V / F + np.log(V / F))
        lnG = self._lnGamma(T, X @ self._nu, psi)
        lnR = (lnG[:, None, :] - lnG_puro[None, :, :])                  # K x n x G
        lnR = np.sum(self._nu[None, :, :] * lnR, axis=2)
        return lnC + lnR

    def lngamma(self, T, x):
        return self.lngamma_lote(T, np.asarray(x)[None, :])[0]

    def gE_RT(self, T, x):
        x = np.asarray(x)
        lg = self.lngamma(T, x)
        m = x != 0
        return np.sum(x[m] * lg[m])
