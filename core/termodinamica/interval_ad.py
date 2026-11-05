"""Second-order forward automatic differentiation over mpmath intervals (F5 liquid bounds, Claude, 5 November 2026).

`AD` carries a value, a gradient and (order 2) a Hessian, every entry an `mpmath.iv` interval. Gradients and
Hessians are sparse dictionaries keyed by variable index (Hessian keys (i, j) with i <= j), so a quantity that
depends on few variables (temperature only, one group amount) stays cheap.

Enclosure property. If every independent variable v_i is seeded with the interval [v_i] (value [v_i], gradient
{i: 1}), then for every point p of the box the true value, first and second derivatives of the composed
expression at p lie in the returned intervals. Each rule below is the chain rule evaluated with interval
factors: for f(u), f1 = f'(u) and f2 = f''(u) are evaluated on the enclosure of u, and the product of enclosures
encloses the product of the pointwise values. With degenerate (point) seeds the same code returns the value and
derivatives at that point, enclosed against rounding.

    (a b)'   = a' b + a b'                (a b)''  = a'' b + a b'' + a' b'^T + b' a'^T
    f(u)'    = f1 u'                      f(u)''   = f1 u'' + f2 u' u'^T

All arithmetic uses the caller's `mpmath.iv` precision (directed rounding). Logarithms and non-integer powers
require a strictly positive argument enclosure; `require_positive` raises `ValueError` otherwise, so a caller can
never obtain an enclosure of a function outside its domain.
"""

from mpmath import iv, mp

__all__ = ["AD", "const", "var", "log", "exp", "power", "require_positive"]


def _I(x):
    return x if isinstance(x, type(iv.mpf(0))) else iv.mpf(x)


def require_positive(x, what="argument"):
    lo = mp.make_mpf(x._mpi_[0])
    if not lo > 0:
        raise ValueError(f"{what} enclosure is not strictly positive (lower bound {lo})")


class AD:
    __slots__ = ("v", "g", "h", "order")

    def __init__(self, v, g=None, h=None, order=2):
        self.v = v
        self.g = g if g is not None else {}
        self.h = h if h is not None else {}
        self.order = order

    # --- linear operations ---------------------------------------------------------------------------
    def __add__(self, o):
        if not isinstance(o, AD):
            return AD(self.v + _I(o), dict(self.g), dict(self.h), self.order)
        g = dict(self.g)
        for k, d in o.g.items():
            g[k] = g[k] + d if k in g else d
        h = {}
        if self.order > 1:
            h = dict(self.h)
            for k, d in o.h.items():
                h[k] = h[k] + d if k in h else d
        return AD(self.v + o.v, g, h, min(self.order, o.order))

    __radd__ = __add__

    def __neg__(self):
        return AD(-self.v, {k: -d for k, d in self.g.items()}, {k: -d for k, d in self.h.items()}, self.order)

    def __sub__(self, o):
        return self + (-o if isinstance(o, AD) else -_I(o))

    def __rsub__(self, o):
        return (-self) + o

    def scale(self, c):
        c = _I(c)
        return AD(c * self.v, {k: c * d for k, d in self.g.items()}, {k: c * d for k, d in self.h.items()},
                  self.order)

    # --- products ------------------------------------------------------------------------------------
    def __mul__(self, o):
        if not isinstance(o, AD):
            return self.scale(o)
        a, b = self, o
        g = {k: b.v * d for k, d in a.g.items()}
        for k, d in b.g.items():
            g[k] = g[k] + a.v * d if k in g else a.v * d
        order = min(a.order, b.order)
        h = {}
        if order > 1:
            h = {k: b.v * d for k, d in a.h.items()}
            for k, d in b.h.items():
                h[k] = h[k] + a.v * d if k in h else a.v * d
            # H_pq += a_p b_q + a_q b_p. Iterating every (i in a, j in b) visits a_p b_q at (p, q) and a_q b_p at
            # (q, p); both land on the unordered key. On the diagonal the single visit counts twice.
            for i, ai in a.g.items():
                for j, bj in b.g.items():
                    key = (i, j) if i <= j else (j, i)
                    t = ai * bj
                    if i == j:
                        t = t + t
                    h[key] = h[key] + t if key in h else t
        return AD(a.v * b.v, g, h, order)

    __rmul__ = __mul__

    def _unary(self, f0, f1, f2):
        g = {k: f1 * d for k, d in self.g.items()}
        h = {}
        if self.order > 1:
            h = {k: f1 * d for k, d in self.h.items()}
            items = sorted(self.g.items())
            for x in range(len(items)):
                i, ui = items[x]
                for y in range(x, len(items)):
                    j, uj = items[y]
                    t = f2 * ui * uj
                    h[(i, j)] = h[(i, j)] + t if (i, j) in h else t
        return AD(f0, g, h, self.order)

    def reciprocal(self):
        require_positive_or_negative(self.v)
        r = 1 / self.v
        return self._unary(r, -r * r, 2 * r * r * r)

    def __truediv__(self, o):
        if not isinstance(o, AD):
            return self.scale(1 / _I(o))
        return self * o.reciprocal()

    def __rtruediv__(self, o):
        return self.reciprocal().scale(o)


def require_positive_or_negative(x):
    lo, hi = mp.make_mpf(x._mpi_[0]), mp.make_mpf(x._mpi_[1])
    if not (lo > 0 or hi < 0):
        raise ValueError(f"division by an enclosure that contains zero [{lo}, {hi}]")


def const(c, order=2):
    return AD(_I(c), order=order)


def var(lo, hi, index, order=2):
    """Independent variable `index` seeded with the interval [lo, hi] (lo == hi for a point)."""
    return AD(iv.mpf([lo, hi]), {index: iv.mpf(1)}, {}, order)


def log(u, what="log argument"):
    if not isinstance(u, AD):
        require_positive(_I(u), what)
        return iv.log(_I(u))
    require_positive(u.v, what)
    r = 1 / u.v
    return u._unary(iv.log(u.v), r, -r * r)


def exp(u):
    if not isinstance(u, AD):
        return iv.exp(_I(u))
    e = iv.exp(u.v)
    return u._unary(e, e, e)


def power(u, a, what="power base"):
    """u**a for a real constant a and u > 0 (u**a = exp(a ln u)); a non-negative integer a needs no sign."""
    a_is_int = float(a).is_integer() and a >= 0
    if not isinstance(u, AD):
        u = _I(u)
        if a_is_int:
            return u ** int(a)
        require_positive(u, what)
        return iv.exp(_I(a) * iv.log(u))
    if a_is_int:
        k = int(a)
        if k == 0:
            return const(1, u.order)
        f0 = u.v ** k
        f1 = k * u.v ** (k - 1)
        f2 = k * (k - 1) * u.v ** (k - 2) if k >= 2 else iv.mpf(0)
        return u._unary(f0, f1, f2)
    require_positive(u.v, what)
    A = _I(a)
    lu = iv.log(u.v)
    f0 = iv.exp(A * lu)
    f1 = A * iv.exp((A - 1) * lu)
    f2 = A * (A - 1) * iv.exp((A - 2) * lu)
    return u._unary(f0, f1, f2)
