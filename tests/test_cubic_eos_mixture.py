"""f8b: Peng-Robinson mixture EOS and the gas-liquid critical region (core/termodinamica/cubic_eos.py,
cubic_flash.py, cubic_critical.py and the layer closure in capa.py).

Independent references, each reached by another path than the code under test:
1. Constants: Omega_a, Omega_b, Z_c solved from the critical conditions against Peng and Robinson,
   Ind. Eng. Chem. Fundam. 15 (1976) 59 (0.45724, 0.07780, 0.307).
2. Derivatives: every chain-rule derivative of F = A^r/RT against a complex step of F itself; the (T, P)
   composition derivative against central differences of ln phi at fixed (T, P).
3. ln phi against the textbook closed form (Peng and Robinson 1976, eq. 9 with quadratic mixing), written
   here separately, and against the `thermo` package (PRMIX, Bell et al.) for species with omega < 0.491.
4. Thermodynamic consistency: Gibbs-Duhem sum_i n_i d ln phi_i/dn_j = 0, symmetry, d(g^r/RT)/dP = (Z - 1)/P,
   d(g^r/RT)/dT = -h^r/RT^2, G^r/RT = sum x ln phi.
5. Pure-component limits: the critical solver returns the catalog (T_c, P_c); saturation against IAPWS-95
   (water) and the catalog's Wagner records (benzene, toluene up to 0.99 T_c, 4.8 MPa); omega reproduced.
6. Binary VLE: benzene + toluene at 333.15 and 353.15 K, Lee, Chen, Lee, Chang and Ko, Fluid Phase Equilib.
   280 (2009) 42-48 (NIST ThermoML 10.1016/j.fluid.2009.03.012), bubble pressures with k_ij = 0.
7. Critical points: Heidemann-Khalil (T, V) criterion against the classical binary determinant criterion in
   molar Helmholtz (v, x) by nested finite differences; pure ends; bubble curves traced by continuation reach
   the critical point; flash and stability certified within 0.01 K of it; the gamma-phi packages reject it.
8. Flash energy and layer closure: PH and UV inverses of TP, Gibbs energy decrease, complementarity.
Experimental mixture critical loci and elevated-pressure binary VLE for catalog-only pairs were not reachable
in this delivery (recorded as a finding in the roadmap F8 section). Run: python -m pytest tests/test_cubic_eos_mixture.py
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import agua_iapws95 as agua
from core import mezclas as mz
from core.termodinamica import capa
from core.termodinamica import cubic_critical as cc
from core.termodinamica import cubic_flash as cf
from core.termodinamica.cubic_eos import R, PengRobinsonMixture, critical_constants

warnings.filterwarnings('ignore')
BZ, TO, W, AC, ME = '71-43-2', '108-88-3', '7732-18-5', '67-64-1', '67-56-1'
S2 = math.sqrt(2.0)


def closed_form_lnphi(eos, T, P, x, Z):
    """Peng and Robinson (1976) eq. 9 generalised to quadratic mixing; independent of the F route."""
    a, _ = eos.a_pure(T)
    aij = (1 - eos.kij) * np.sqrt(np.outer(a, a))
    am = x @ aij @ x
    bm = x @ eos.b
    A = am * P / (R * T) ** 2
    B = bm * P / (R * T)
    return (eos.b / bm * (Z - 1) - math.log(Z - B)
            - A / (2 * S2 * B) * (2 * (aij @ x) / am - eos.b / bm) * math.log((Z + (1 + S2) * B) / (Z + (1 - S2) * B)))


class Derivation(unittest.TestCase):
    def test_constants_from_critical_conditions(self):
        oa, ob, zc = critical_constants()
        self.assertAlmostEqual(oa, 0.45724, places=5)
        self.assertAlmostEqual(ob, 0.07780, places=5)
        self.assertAlmostEqual(zc, 0.3074, places=4)

    def test_gradient_against_complex_step_of_F(self):
        k = np.array([[0, 0.02, -0.05], [0.02, 0, 0.08], [-0.05, 0.08, 0]])
        eos = PengRobinsonMixture((BZ, TO, AC), kij=k)
        rng = np.random.default_rng(7)
        h = 1e-30
        worst = 0.0
        for _ in range(20):
            n = rng.uniform(0.05, 2.0, 3)
            T = rng.uniform(300, 600)
            V = float(n @ eos.b) * rng.uniform(1.3, 200)
            Fn, FV, FT = eos.gradient(T, V, n)
            cs_n = np.array([eos.F(T, V, n + 1j * h * np.eye(3)[i]).imag / h for i in range(3)])
            cs_V = eos.F(T, V + 1j * h * V, n).imag / (h * V)
            cs_T = eos.F(T + 1j * h, V, n).imag / h
            for a, b in ((Fn, cs_n), (FV * V, cs_V * V), (FT * T, cs_T * T)):
                worst = max(worst, float(np.max(np.abs(np.asarray(a) - b) / (1 + np.abs(b)))))
        print(f'chain rule vs complex step of F: {worst:.2e}')
        self.assertLess(worst, 1e-12)

    def test_lnphi_closed_form_and_thermo(self):
        from thermo.eos_mix import PRMIX
        k = np.array([[0, 0.015, 0.03], [0.015, 0, -0.02], [0.03, -0.02, 0]])
        eos = PengRobinsonMixture((BZ, TO, W), kij=k)
        worst_cf = worst_th = 0.0
        for T, P, x in ((350.0, 1e5, [0.2, 0.3, 0.5]), (480.0, 2e6, [0.6, 0.3, 0.1]), (550.0, 8e6, [0.3, 0.3, 0.4])):
            x = np.array(x)
            ref = PRMIX(T=T, P=P, zs=list(x), Tcs=list(eos.Tc), Pcs=list(eos.Pc), omegas=list(eos.omega),
                        kijs=k.tolist())
            for Z in eos.z_roots(T, P, x):
                lp = eos.ln_phi_Z(T, P, x, Z)
                worst_cf = max(worst_cf, float(np.max(np.abs(lp - closed_form_lnphi(eos, T, P, x, Z)))))
                for zr, phis in ((getattr(ref, 'Z_l', None), getattr(ref, 'phis_l', None)),
                                 (getattr(ref, 'Z_g', None), getattr(ref, 'phis_g', None))):
                    if zr is not None and abs(zr - Z) < 1e-8 * Z:
                        worst_th = max(worst_th, float(np.max(np.abs(lp - np.log(phis)))))
        print(f'ln phi vs closed form {worst_cf:.2e}, vs thermo PRMIX {worst_th:.2e}')
        self.assertLess(worst_cf, 1e-12)
        self.assertLess(worst_th, 1e-9)

    def test_consistency_identities(self):
        eos = PengRobinsonMixture((BZ, TO, ME), kij=np.array([[0, 0, 0.08], [0, 0, 0.07], [0.08, 0.07, 0]]))
        n = np.array([0.7, 1.1, 0.4])
        worst = {}
        for T, P in ((400.0, 3e5), (520.0, 6e6)):
            x = n / n.sum()
            for Z in eos.z_roots(T, P, x):
                J = eos.dlnphi_dn(T, P, n, Z)
                worst['gibbs-duhem'] = max(worst.get('gibbs-duhem', 0), float(np.max(np.abs(n @ J))))
                worst['symmetry'] = max(worst.get('symmetry', 0), float(np.max(np.abs(J - J.T))))
                # central differences of ln phi at fixed (T, P) on the same root branch
                fd = np.empty((3, 3))
                for j in range(3):
                    d = 1e-6 * n[j]
                    up, dn = n.copy(), n.copy()
                    up[j] += d
                    dn[j] -= d
                    zu = min(eos.z_roots(T, P, up / up.sum()), key=lambda r: abs(r - Z))
                    zd = min(eos.z_roots(T, P, dn / dn.sum()), key=lambda r: abs(r - Z))
                    fd[:, j] = (eos.ln_phi_Z(T, P, up / up.sum(), zu) - eos.ln_phi_Z(T, P, dn / dn.sum(), zd)) / (2 * d)
                worst['dlnphi_dn vs FD'] = max(worst.get('dlnphi_dn vs FD', 0), float(np.max(np.abs(J - fd))))
                # d(g^r/RT)/dP = (Z - 1)/P and d(g^r/RT)/dT = -h^r/(R T^2), same branch
                gr = lambda TT, PP: float(x @ eos.ln_phi_Z(TT, PP, x, min(eos.z_roots(TT, PP, x), key=lambda r: abs(r - Z))))
                hP = 1e-6 * P
                dP = (gr(T, P + hP) - gr(T, P - hP)) / (2 * hP)
                worst['dg/dP'] = max(worst.get('dg/dP', 0), abs(dP - (Z - 1) / P) * P)
                hT = 1e-5 * T
                dT = (gr(T + hT, P) - gr(T - hT, P)) / (2 * hT)
                hr, sr, g_r = eos.residual_TP(T, P, x, Z)
                worst['dg/dT'] = max(worst.get('dg/dT', 0), abs(dT + hr / (R * T ** 2)) * T)
                worst['g^r'] = max(worst.get('g^r', 0), abs(g_r / (R * T) - gr(T, P)))
        print('consistency:', {k: f'{v:.1e}' for k, v in worst.items()})
        self.assertLess(worst['gibbs-duhem'], 1e-11)
        self.assertLess(worst['symmetry'], 1e-11)
        self.assertLess(worst['dlnphi_dn vs FD'], 1e-7)
        self.assertLess(worst['dg/dP'], 1e-8)
        self.assertLess(worst['dg/dT'], 1e-8)
        self.assertLess(worst['g^r'], 1e-13)


class PureLimits(unittest.TestCase):
    def test_critical_solver_returns_catalog_constants(self):
        for c in (BZ, W):
            eos = PengRobinsonMixture((c,))
            cp = cc.critical_points(eos, [1.0])
            self.assertEqual(len(cp), 1)
            self.assertAlmostEqual(cp[0]['T'] / eos.Tc[0], 1.0, places=10)
            self.assertAlmostEqual(cp[0]['P'] / eos.Pc[0], 1.0, places=8)
            self.assertAlmostEqual(cp[0]['P'] * cp[0]['V'] / (R * cp[0]['T']), critical_constants()[2], places=8)

    def test_saturation_against_iapws95_and_wagner(self):
        w = PengRobinsonMixture((W,))
        dev_w = max(abs(cf.pure_saturation(w, 0, T)['P'] / agua.saturacion(T).Psat - 1)
                    for T in np.linspace(300, 640, 18))
        dev_w_hot = max(abs(cf.pure_saturation(w, 0, T)['P'] / agua.saturacion(T).Psat - 1)
                        for T in np.linspace(450, 640, 10))
        tc = abs(w.Tc[0] - agua.TC) / agua.TC
        out = {'water vs IAPWS-95 300-640 K': dev_w, 'water 450-640 K': dev_w_hot, 'water T_c': tc}
        for c in (BZ, TO):
            e = PengRobinsonMixture((c,))
            sp = e.esp[0]
            Ts = np.linspace(0.6 * e.Tc[0], 0.99 * e.Tc[0], 14)
            out[c] = max(abs(cf.pure_saturation(e, 0, T)['P'] / sp.Psat(T) - 1) for T in Ts)
            out[c + ' at 0.7 Tc'] = abs(cf.pure_saturation(e, 0, 0.7 * e.Tc[0])['P'] / sp.Psat(0.7 * e.Tc[0]) - 1)
        print('pure saturation deviations:', {k: f'{v:.2%}' for k, v in out.items()})
        self.assertLess(dev_w, 0.16)          # PR is known to under-predict water at low T
        self.assertLess(dev_w_hot, 0.03)
        self.assertLess(tc, 5e-4)
        for c in (BZ, TO):
            self.assertLess(out[c], 0.025)
            self.assertLess(out[c + ' at 0.7 Tc'], 0.01)


class BinaryVLE(unittest.TestCase):
    # (T, x_benzene, P kPa): Lee et al. 2009, interior points
    DATA = [(333.15, 0.104, 21.7), (333.15, 0.303, 28.3), (333.15, 0.505, 35.1), (333.15, 0.696, 42.0),
            (333.15, 0.845, 47.2), (353.15, 0.096, 44.8), (353.15, 0.301, 56.8), (353.15, 0.5, 69.5),
            (353.15, 0.702, 82.7), (353.15, 0.894, 94.7)]

    def test_benzene_toluene_bubble_pressures(self):
        eos = PengRobinsonMixture((BZ, TO))
        dev = [cf.saturation(eos, [x, 1 - x], T=T, kind='bubble')['P'] / (P * 1e3) - 1 for T, x, P in self.DATA]
        print('PR k_ij = 0 bubble P vs Lee et al. 2009:', ' '.join(f'{d:+.2%}' for d in dev))
        self.assertLess(max(abs(d) for d in dev), 0.04)


class CriticalRegion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eos = PengRobinsonMixture((BZ, TO))
        cls.cp = {x: cc.critical_points(cls.eos, [x, 1 - x]) for x in (0.25, 0.5, 0.75)}

    def test_heidemann_khalil_against_helmholtz_determinants(self):
        worst_T = worst_P = 0.0
        for x, cps in self.cp.items():
            self.assertEqual(len(cps), 1)
            c = cps[0]
            r = cc.binary_critical_reference(self.eos, x, c['T'] * 1.01, c['V'] * 1.05)
            worst_T = max(worst_T, abs(r['T'] - c['T']))
            worst_P = max(worst_P, abs(r['P'] / c['P'] - 1))
        # the locus lies between the pure critical points, monotone in x
        Ts = [self.cp[x][0]['T'] for x in (0.25, 0.5, 0.75)]
        print(f'critical points {[(x, round(c[0]["T"], 3), round(c[0]["P"] / 1e6, 4)) for x, c in self.cp.items()]};'
              f' vs determinant route {worst_T:.1e} K, {worst_P:.1e}')
        self.assertLess(worst_T, 1e-3)
        self.assertLess(worst_P, 1e-5)
        self.assertTrue(self.eos.Tc[1] > Ts[0] > Ts[1] > Ts[2] > self.eos.Tc[0])

    def test_bubble_curve_reaches_the_critical_point_and_flash_certifies_near_it(self):
        z = np.array([0.5, 0.5])
        c = self.cp[0.5][0]
        Ts = list(np.arange(500.0, 570.0, 5.0)) + list(c['T'] - np.geomspace(8, 1e-3, 30))
        bub = cf.saturation_curve(self.eos, z, Ts, 'bubble')
        dew = cf.saturation_curve(self.eos, z, Ts, 'dew')
        self.assertEqual(len(bub), len(Ts))
        last = bub[-1]
        print(f'bubble at Tc - {c["T"] - last["T"]:.1e} K: P/Pc - 1 = {last["P"] / c["P"] - 1:.1e}, '
              f'|y - z| = {abs(last["w"][0] - 0.5):.1e}')
        self.assertLess(abs(last['P'] / c['P'] - 1), 3e-5)
        self.assertLess(abs(last['w'][0] - 0.5), 1e-4)
        bd = {round(r['T'], 9): r for r in bub}
        dd = {round(r['T'], 9): r for r in dew}
        gaps = []
        for dl in (1.0, 0.1, 0.01):
            T = min(set(bd) & set(dd), key=lambda t: abs(c['T'] - t - dl))
            P = 0.5 * (bd[T]['P'] + dd[T]['P'])
            st = cf.flash_TP(self.eos, T, P, z)
            self.assertEqual(len(st['phases']), 2)
            self.assertLess(st['mu_residual'], cf.TOL_MU)
            ph = st['phases']
            self.assertGreater(ph[1]['v'], 0)
            self.assertLess(ph[1]['v'], ph[0]['v'])        # liquid denser
            gaps.append(abs(ph[0]['x'][0] - ph[1]['x'][0]))
            # one phase just above the bubble pressure: no negative tangent-plane minimum
            self.assertEqual(len(cf.flash_TP(self.eos, T, bd[T]['P'] * 1.001, z)['phases']), 1)
        print('tie-line length at Tc - (1, 0.1, 0.01) K:', [f'{g:.2e}' for g in gaps])
        self.assertTrue(gaps[0] > gaps[1] > gaps[2])
        # above the critical temperature at the critical pressure: one stable phase
        st = cf.flash_TP(self.eos, c['T'] + 1.0, c['P'], z)
        self.assertEqual(len(st['phases']), 1)
        self.assertGreaterEqual(st['tm_min'], -cf.TOL_TM)

    def test_gamma_phi_packages_exclude_the_critical_region(self):
        c = self.cp[0.5][0]
        s = mz.Sistema('mezcla-ideal', [BZ, TO])
        with self.assertRaises(mz.FueraDeAlcance):
            s.equilibrio_TP(c['T'] - 1.0, c['P'], np.array([0.5, 0.5]))
        self.assertLess(s.T_rango[1], 0.9 * min(self.eos.Tc) + 1e-9)


class FlashAndLayer(unittest.TestCase):
    def test_ph_uv_inverses_and_gibbs_decrease(self):
        eos = PengRobinsonMixture((BZ, TO))
        z = np.array([0.4, 0.6])
        T, P = 500.0, 1.5e6
        st = cf.flash_TP(eos, T, P, z)
        self.assertEqual(len(st['phases']), 2)
        H = sum(p['n'] * p['h'] for p in st['phases'])
        U = sum(p['n'] * p['u'] for p in st['phases'])
        V = sum(p['n'] * p['v'] for p in st['phases'])
        G2 = sum(p['n'] * p['g'] for p in st['phases'])
        g1 = min(eos.molar_props(T, P, z, Z)['g'] for Z in eos.z_roots(T, P, z))
        self.assertLess(G2, g1)
        ph = cf.flash_PH(eos, P, H, z, T_bracket=(450.0, 560.0))
        uv = cf.flash_UV(eos, U, V, z, T_bracket=(450.0, 560.0))
        print(f'PH: T err {ph["T"] - T:.1e} K; UV: T err {uv["T"] - T:.1e} K, P rel {uv["P"] / P - 1:.1e}; '
              f'G drop {(G2 - g1) / (R * T):.3e} RT')
        self.assertLess(abs(ph['T'] - T), 1e-7)
        self.assertLess(abs(uv['T'] - T), 1e-6)
        self.assertLess(abs(uv['P'] / P - 1), 1e-8)

    def test_layer_closure(self):
        modelo = {
            'componentes': [{'id': 'b', 'identidadQuimica': {'cas': BZ}}, {'id': 't', 'identidadQuimica': {'cas': TO}}],
            'termodinamica': {'paquetes': [{'id': 'p', 'modelo': {'id': capa.CUBICO}}]},
            'volumenes': [{'id': 'v', 'componenteIds': ['b', 't'],
                           'termodinamica': {'tipo': 'equilibrio', 'paqueteId': 'p'}}]}
        self.assertEqual(capa.candidatas(modelo, 'v'), ['vapor-1', 'liquido-1'])
        n = {'b': 0.5, 't': 0.5}
        two = capa.cierre(modelo, 'v', n, ('TP', 500.0, 1.6e6))
        self.assertEqual(sorted(two['presentes']), ['liquido-1', 'vapor-1'])
        self.assertLess(two['complementariedad'], 1e-12)
        liq = capa.cierre(modelo, 'v', n, ('TP', 500.0, 1.65e6))
        self.assertEqual(liq['presentes'], ['liquido-1'])
        vap = next(f for f in liq['fases'] if f['id'] == 'vapor-1')
        self.assertGreater(vap['tm'], 0)
        self.assertLess(liq['complementariedad'], 1e-12)
        ph = capa.cierre(modelo, 'v', n, ('PH', 1.6e6, two['H']))
        self.assertLess(abs(ph['T'] - 500.0), 1e-6)
        print(f'layer: two-phase beta_V {two["fases"][0]["beta"]:.6f}; subcooled tm_vapor {vap["tm"]:.3e}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
