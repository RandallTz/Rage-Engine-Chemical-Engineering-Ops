"""Liquid equilibrium-reaction author and independent references (B3, claude-b, 6 November 2026).

The Model is authored by the shared operations in equilibrium_reaction_inputs.author:
mu_i = mu_i*(T,P) + R T log(x_i gamma_i) is a recorded thermodynamic constitutive
relation of the declared package liquid.

The references do not call core.mezclas, core.unifac or core.reactions:
- ln gamma_i: thermo's UNIFAC implementation (thermo.unifac.UNIFAC, its own DDBST
  group assignments and interaction tables; version 0 original, 1 Dortmund).
- mu_i*(T,P): a 50-digit mpmath evaluation of the pure-liquid Gibbs energy written
  here from the published coefficient tuples (Poling ideal-gas cp, Wagner Psat,
  liquid molar volume, DIPPR-100 liquid cp of a liquid-only species) and the
  tabulated liquid formation data of `chemicals` (Hfl, S0l), with the liquid
  formation anchor mu_i*(T0, P0) = Hfl_i - T0 S0l_i and -dmu_i*/dT(T0, P0) = S0l_i.
"""
import mpmath as mp
from chemicals import reaction as rx
from chemicals.identifiers import search_chemical
from thermo import unifac as tu
from core import mezclas_datos as data   # coefficient tuples only (data, not code)
from equilibrium_reaction_inputs import author

ACID, ETHANOL, ACETATE, WATER, ACETONE = '64-19-7', '64-17-5', '141-78-6', '7732-18-5', '67-64-1'
SPECIES = [ACID, ETHANOL, ACETATE, WATER]
NU = [-1, -1, 1, 1]
MOLAR_MASSES = (.06005, .04607, .08811, .01802, .05808)
TEMPERATURE, PRESSURE = 350, 101325
R, T0, P0 = mp.mpf('8.314462618'), mp.mpf('298.15'), mp.mpf(100000)


def esterification(package='unifac-original', form='activity', inert=False, extent_box=(.625, .66), seed=.64):
    """Acetic acid + ethanol = ethyl acetate + water in one liquid at 350 K, 1 atm.

    Liquid formation anchor: acetic acid is a liquid-only species of the catalog."""
    species = SPECIES + ([ACETONE] if inert else [])
    nu = NU + ([0] if inert else [])
    reference = (1, 1, 0, 0) + ((2,) if inert else ())
    return author(owner='liquid', species=species, nu=nu, molar_masses=MOLAR_MASSES[:len(species)],
                  reference=reference, temperature=TEMPERATURE, pressure=PRESSURE, extent_box=extent_box,
                  seed=seed, state_width=1e-3, step_tolerance=1e-13,
                  liquid={'package': package, 'anchor': 'liquid', 'form': form})


# --- independent pure-liquid standard potential ----------------------------------------------------------
def _ideal_gas_g(e, T):
    """g_ig(T, P0) - g_ig(T0, P0) = h - T s with Poling cp/R = sum a_k T^k (zero at T0, P0)."""
    a = [mp.mpf(repr(v)) for v in e.cp]
    h = sum(a[k] * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k in range(len(a)))
    s = a[0] * mp.log(T / T0) + sum(a[k] * (T**k - T0**k) / k for k in range(1, len(a)))
    return R * h - T * R * s


def _ln_psat(e, T):
    A, B, C, D, Tc, Pc = (mp.mpf(repr(v)) for v in e.psat)
    tau = 1 - T / Tc
    third, fourth = (mp.mpf('2.5'), 5) if e.psat_forma == 'WagnerPoling' else (3, 6)
    return mp.log(Pc) + Tc / T * (A * tau + B * tau**mp.mpf('1.5') + C * tau**third + D * tau**fourth)


def _liquid_g(e, T, P):
    """Pure-liquid Gibbs energy through the vapour: ideal gas + R T ln(Psat/P0) + v_L (P - Psat)."""
    vL = mp.mpf(repr(e.vL))
    return _ideal_gas_g(e, T) + R * T * (_ln_psat(e, T) - mp.log(P0)) + vL * (P - mp.e**_ln_psat(e, T))


def pure_liquid_potential(cas, T, P):
    """mu_i*(T, P) [J/mol] with the liquid formation anchor (50 digits)."""
    mp.mp.dps = 50
    e = data.especie(cas)
    T, P = mp.mpf(repr(float(T))), mp.mpf(repr(float(P)))
    Hl, Sl = mp.mpf(repr(rx.Hfl(cas))), mp.mpf(repr(rx.S0l(cas)))
    vL = mp.mpf(repr(e.vL))
    if e.cp_L is not None:
        # Tabulated liquid cp: h = Hl + int cp_L dT + v_L (P - P0), s = Sl + int cp_L/T dT.
        c = [mp.mpf(repr(v)) for v in e.cp_L]
        H = sum(c[k] * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k in range(len(c)))
        S = c[0] * mp.log(T / T0) + sum(c[k] * (T**k - T0**k) / k for k in range(1, len(c)))
        return Hl + H + vL * (P - P0) - T * (Sl + S)
    # Psat route shifted so that h(T0, P0) = Hl and s(T0, P0) = Sl.
    dg = mp.diff(lambda t: _liquid_g(e, t, P0), T0)
    h0, s0 = _liquid_g(e, T0, P0) - T0 * dg, -dg
    return _liquid_g(e, T, P) + (Hl - h0) - T * (Sl - s0)


def ln_k(species, nu, T, P):
    return -mp.fsum(v * pure_liquid_potential(c, T, P) for c, v in zip(species, nu) if v) / (R * mp.mpf(T))


# --- independent activity coefficients -------------------------------------------------------------------
def ln_gamma(species, x, T, variant):
    """thermo's UNIFAC: version 0 (original, UFSG/UFIP) or 1 (Dortmund, DOUFSG/DOUFIP2016)."""
    tu.load_group_assignments_DDBST()
    table = tu.DDBST_UNIFAC_assignments if variant == 'original' else tu.DDBST_MODIFIED_UNIFAC_assignments
    groups = [table[search_chemical(c).InChI_key] for c in species]
    options = ({'version': 0, 'subgroups': tu.UFSG, 'interaction_data': tu.UFIP} if variant == 'original' else
               {'version': 1, 'subgroups': tu.DOUFSG, 'interaction_data': tu.DOUFIP2016})
    model = tu.UNIFAC.from_subgroups(float(T), [float(v) for v in x], groups, **options)
    return [mp.mpf(repr(v)) for v in model.lngammas()]


def reference_extent(species, nu, n0, T, P, variant, guess):
    """Root of sum_i nu_i ln(x_i gamma_i) = ln K in the single extent (variant None: ideal solution)."""
    lnK = ln_k(species, nu, T, P)

    def residual(xi):
        n = [mp.mpf(a) + v * xi for a, v in zip(n0, nu)]
        x = [v / mp.fsum(n) for v in n]
        lg = ln_gamma(species, x, T, variant) if variant else [0] * len(x)
        return mp.fsum(v * (mp.log(xv) + g) for v, xv, g in zip(nu, x, lg) if v) - lnK

    # thermo's ln gamma is binary64, so the attainable residual is ~1e-15, not 50 digits.
    root = mp.findroot(residual, (mp.mpf(guess) - mp.mpf('0.01'), mp.mpf(guess) + mp.mpf('0.01')), solver='secant',
                       tol=mp.mpf('1e-28'), verify=False)
    assert abs(residual(root)) < 1e-13
    return root
