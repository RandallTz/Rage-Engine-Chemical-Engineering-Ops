"""Interval extension of UNIFAC ln gamma_i with analytic first and second derivatives (F5 liquid bounds, Claude,
5 November 2026).

The function enclosed is the one `core.unifac.LiquidoUNIFAC.lngamma` evaluates, with its data taken from the
model's public parameter set `identidad()` (the set the reaction-bounds fingerprint pins): sub-group R_k, Q_k and
main group, the DDBST assignments nu_ki and the interaction coefficients (a, b, c) of every used main-group pair,
all as exact binary64 values. Derived constants (r_i = sum_k nu_ki R_k, q_i, l_i, r_i^(3/4)) are computed in
interval arithmetic, never taken from the model's float arrays.

Amount form. ln gamma_i is homogeneous of degree zero in the amounts n, so it is written directly in n
(N = sum n_j) with every normalisation either cancelled or isolated in a single logarithm; this removes the
interval dependency that x_i = n_i/N would otherwise introduce.

  Combinatorial, original and LLE (Staverman-Guggenheim, z = 10), with Lr = ln sum r_j n_j, Lq = ln sum q_j n_j,
  LN = ln N, SL = sum l_j n_j, l_i = 5 (r_i - q_i) - (r_i - 1):
      ln gamma_i^C = ln r_i + LN - Lr + 5 q_i (ln q_i - ln r_i + Lr - Lq) + l_i - r_i SL / sum r_j n_j
  Combinatorial, Dortmund (r^(3/4)), with L34 = ln sum r_j^(3/4) n_j:
      Vp_i = r_i^(3/4) N / sum r^(3/4) n,   ln(V_i/F_i) = ln r_i - ln q_i + Lq - Lr
      ln gamma_i^C = 1 - Vp_i + ln Vp_i - 5 q_i (1 - V_i/F_i + ln(V_i/F_i))
  Residual, with group amounts X_m = sum_i nu_mi n_i, W = sum_m Q_m X_m, Psi_mk = exp(-(a_mk + b_mk T + c_mk T^2)/T)
  and S'_k = sum_m Q_m X_m Psi_mk (the normalisation W cancels from the last sum and appears once as ln W):
      ln Gamma_k = Q_k (1 - ln S'_k + ln W - sum_m Q_m X_m Psi_km / S'_m)
      ln gamma_i^R = sum_k nu_ki (ln Gamma_k - ln Gamma_k^(i))      (Gamma_k^(i): pure i, a function of T only)

These are the module's equations rearranged without approximation; the test suite checks them against an mpmath
UNIFAC rebuilt from the thermo tables in mole-fraction form.
"""

from mpmath import iv

from core.termodinamica import interval_ad as ad

__all__ = ["UnifacIntervalModel"]


class UnifacIntervalModel:
    """Interval UNIFAC for the species order of a `LiquidoUNIFAC` (built from its `identidad()`)."""

    def __init__(self, liquid_model):
        ident = liquid_model.identidad()
        self.variant = ident["variante"]
        if self.variant not in ("original", "dortmund", "lle"):
            raise ValueError(f"unknown UNIFAC variant {self.variant!r}")
        self.cas = tuple(liquid_model.cas)
        groups = sorted(int(g) for g in ident["subgrupos"])
        self.groups = groups
        sub = {int(g): v for g, v in ident["subgrupos"].items()}
        self.main = [int(sub[g][0]) for g in groups]
        self.Rk = [float(sub[g][1]) for g in groups]
        self.Qk = [float(sub[g][2]) for g in groups]
        self.nu = [[int(ident["asignaciones"][c].get(str(g), 0)) for g in groups] for c in self.cas]
        inter = {tuple(int(v) for v in k.split("-")): tuple(float(x) for x in abc)
                 for k, abc in ident["interacciones"].items()}
        G = len(groups)
        self.abc = [[(0.0, 0.0, 0.0) if self.main[a] == self.main[b] else inter[(self.main[a], self.main[b])]
                     for b in range(G)] for a in range(G)]
        self.dependent_groups = [[k for k in range(G) if self.nu[i][k]] for i in range(len(self.cas))]

    # --- interval constants (recomputed at the caller's precision) ------------------------------------
    def _constants(self):
        s, G = len(self.cas), len(self.groups)
        R = [iv.mpf(v) for v in self.Rk]
        Q = [iv.mpf(v) for v in self.Qk]
        r = [sum((self.nu[i][k] * R[k] for k in range(G) if self.nu[i][k]), iv.mpf(0)) for i in range(s)]
        q = [sum((self.nu[i][k] * Q[k] for k in range(G) if self.nu[i][k]), iv.mpf(0)) for i in range(s)]
        return R, Q, r, q

    def _psi(self, T):
        """Psi_mk(T) as AD objects (T only): exp(-a/T - b - c T)."""
        G = len(self.groups)
        out = [[None] * G for _ in range(G)]
        invT = 1 / T
        for m in range(G):
            for k in range(G):
                a, b, c = self.abc[m][k]
                if a == 0.0 and b == 0.0 and c == 0.0:
                    out[m][k] = ad.const(1, T.order)
                else:
                    out[m][k] = ad.exp(-(invT.scale(a) + T.scale(c)) - iv.mpf(b))
        return out

    def _ln_Gamma(self, X, Q, psi, groups):
        """ln Gamma_k for group amounts X (list of AD or interval, None for an absent group), k in `groups`."""
        present = [m for m in range(len(X)) if X[m] is not None]
        QX = {m: X[m] * Q[m] for m in present}
        W = sum((QX[m] for m in present[1:]), QX[present[0]])
        lnW = ad.log(W, "UNIFAC sum Q X")
        S = {}
        for k in present:
            S[k] = sum((QX[m] * psi[m][k] for m in present[1:]), QX[present[0]] * psi[present[0]][k])
        lnS = {k: ad.log(S[k], f"UNIFAC S'_{k}") for k in present}
        out = {}
        for k in groups:
            tail = sum((QX[m] * psi[k][m] / S[m] for m in present[1:]),
                       QX[present[0]] * psi[k][present[0]] / S[present[0]])
            out[k] = (lnW - lnS[k] - tail + 1) * Q[k]
        return out

    def lngamma(self, T, n):
        """[ln gamma_i] as AD objects. T: AD in temperature; n: list of AD amounts (strictly positive)."""
        s, G = len(self.cas), len(self.groups)
        R, Q, r, q = self._constants()
        order = T.order
        N = sum(n[1:], n[0])
        LN = ad.log(N, "total amount")
        Sr = sum((n[j] * r[j] for j in range(1, s)), n[0] * r[0])
        Sq = sum((n[j] * q[j] for j in range(1, s)), n[0] * q[0])
        Lr, Lq = ad.log(Sr, "sum r n"), ad.log(Sq, "sum q n")
        lnC = []
        if self.variant != "dortmund":
            l = [(r[i] - q[i]) * 5 - (r[i] - 1) for i in range(s)]
            SL = sum((n[j] * l[j] for j in range(1, s)), n[0] * l[0])
            SL_over_Sr = SL / Sr
            for i in range(s):
                lnC.append(LN - Lr + iv.log(r[i])
                           + (Lr - Lq + (iv.log(q[i]) - iv.log(r[i]))) * (5 * q[i])
                           + l[i] - SL_over_Sr * r[i])
        else:
            r34 = [ad.power(r[i], 0.75, "r_i") for i in range(s)]
            S34 = sum((n[j] * r34[j] for j in range(1, s)), n[0] * r34[0])
            L34 = ad.log(S34, "sum r^(3/4) n")
            for i in range(s):
                lnVp = LN - L34 + iv.log(r34[i])
                Vp = ad.exp(lnVp)
                lnVF = Lq - Lr + (iv.log(r[i]) - iv.log(q[i]))
                VF = ad.exp(lnVF)
                lnC.append(1 - Vp + lnVp - (1 - VF + lnVF) * (5 * q[i]))
        psi = self._psi(T)
        X = []
        for k in range(G):
            terms = [n[i].scale(self.nu[i][k]) for i in range(s) if self.nu[i][k]]
            X.append(sum(terms[1:], terms[0]) if terms else None)
        all_groups = [k for k in range(G) if X[k] is not None]
        lnG = self._ln_Gamma(X, Q, psi, all_groups)
        out = []
        for i in range(s):
            gi = self.dependent_groups[i]
            Xi = [ad.const(self.nu[i][k], order) if k in gi else None for k in range(G)]
            lnG_pure = self._ln_Gamma(Xi, Q, psi, gi)
            res = sum(((lnG[k] - lnG_pure[k]).scale(self.nu[i][k]) for k in gi[1:]),
                      (lnG[gi[0]] - lnG_pure[gi[0]]).scale(self.nu[i][gi[0]]))
            out.append(lnC[i] + res)
        return out
