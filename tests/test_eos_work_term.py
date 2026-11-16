"""F8b: analytic isobaric work term dV/dt of the cubic EOS packages (`PaqueteEOS.dV_dt_PH`).

The network accounting (`core/ensamblaje_red.py`) integrates W = int P dV/dt dt for every isobaric volume. dV/dt is the
total derivative of V(H, P, n) along the rates of P, H and n; it was a centred difference of two (or four) more PH
flashes per right-hand side. The EOS packages now differentiate their own closure. References:

1. `thermo` 0.6.1 PR78MIX (Bell et al., independent implementation) with the package's own T_c, P_c and omega:
   (dV/dT)_P, (dV/dP)_T, partial molar volumes (v + its d(molar V)/dn_i), the departure heat capacity and (d ln phi_i/dT)_P of one phase.
2. Exact identities: (dH/dP)_T = V - T (dV/dT)_P, Euler sums V = sum n_i vbar_i and H = sum n_i hbar_i, and Gibbs-Duhem
   sum_i n_i (d ln f_i/dn_j)_TP = 0.
3. The pure two-phase plateau in closed form from the Maxwell saturation: dV/dt = (v_V - v_L)/(h_V - h_L) dH/dt.
4. Centred differences of certified PH flashes (the previous route) on one- and two-phase states of both packages,
   including PSRK CO2 + ethanol at the Sima et al. (2011) pressure and a state next to the CO2 alpha switch at T_c.
5. The analytic route makes no flash, and its located fallbacks return None.
"""

import os
import sys
import time
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import mezclas as mz                                                    # noqa: E402
from core.termodinamica import cubic_flash                                        # noqa: E402
from core.termodinamica.eos_package import PaqueteEOS                              # noqa: E402

BZ, TO, CO2, ETOH = '71-43-2', '108-88-3', '124-38-9', '64-17-5'
PR, PSRK = 'peng-robinson-vdw1f', 'psrk-unifac'
R = mz.R


def flash_difference(pk, st, dP, dH, dn):
    """Centred difference of V(H, P, n) through certified PH flashes, step as in ensamblaje_red._dVdt."""
    n = np.asarray(st.n, dtype=float)
    ref = np.where(n > 0, n, n.sum())
    scale = max(np.max(np.abs(dn) / ref) if np.any(dn) else 0.0, abs(dH) / max(abs(st.H), R * st.T * n.sum()),
                abs(dP) / st.P, 1e-12)
    eps = 1e-6 / scale

    def V(k):
        return pk.estado('PH', st.P + dP * eps * k, st.H + dH * eps * k, n + dn * eps * k, semilla=st).V
    if np.any(n - dn * eps < 0):        # a species entering at zero amount: second-order forward difference
        return (-3.0 * st.V + 4.0 * V(1) - V(2)) / (2 * eps)
    return (V(1) - V(-1)) / (2 * eps)


RATES = ((0.0, 400.0, None), (-50.0, 0.0, None), (0.0, 0.0, (1e-3, -2e-3)), (30.0, 200.0, (2e-3, 1e-3)))


class OnePhaseAgainstThermo(unittest.TestCase):
    """Phase derivatives against thermo PR78MIX built on the same T_c, P_c and omega."""

    def test_phase_derivatives_equal_thermo(self):
        from thermo.eos_mix import PR78MIX
        pk = PaqueteEOS(PR, (BZ, TO))
        eos = pk._eos(range(2))
        worst = {}
        for T, P, x in ((330.0, 1e5, [0.4, 0.6]), (420.0, 5e4, [0.5, 0.5]), (600.0, 6e6, [0.3, 0.7]),
                        (350.0, 3e7, [0.8, 0.2])):
            x = np.array(x)
            ref = PR78MIX(T=T, P=P, zs=list(x), Tcs=list(eos.Tc), Pcs=list(eos.Pc), omegas=list(eos.omega))
            for Z in eos.z_roots(T, P, x):
                V = Z * R * T / P
                sides = [s for s in ('l', 'g') if getattr(ref, f'V_{s}', None) is not None
                         and abs(getattr(ref, f'V_{s}') - V) < 1e-9 * V]
                if not sides:
                    continue            # the middle (mechanically unstable) root of the cubic
                side = sides[0]
                d = pk._phase_derivatives(eos, T, P, x, V)
                lnphi = ref.dlnphis_dT('l' if side == 'l' else 'g')
                checks = {
                    'dV/dT': (d['V_T'], getattr(ref, f'dV_dT_{side}')),
                    'dV/dP': (d['V_P'], getattr(ref, f'dV_dP_{side}')),
                    'Cp_dep': (d['c'] - float(np.dot(x, [e.cp_ig(T) for e in eos.esp])), getattr(ref, f'Cp_dep_{side}')),
                }
                # thermo's dV_dns is d(molar V)/dn_i of one mole of mixture: vbar_i = v + dv/dn_i
                vbar_ref = V + np.array(ref.dV_dns(Z))
                hres = d['hbar'] - np.array([e.h_ig(T) for e in eos.esp])
                for k in range(2):
                    checks[f'vbar_{k}'] = (d['vbar'][k], vbar_ref[k])
                    checks[f'hbar_res_{k}'] = (hres[k], -R * T * T * lnphi[k])
                for name, (a, b) in checks.items():
                    rel = abs(a - b) / max(abs(b), 1e-30)
                    worst[name] = max(worst.get(name, 0.0), rel)
        print('worst relative difference against thermo PR78MIX: ' +
              ', '.join(f'{k} {v:.1e}' for k, v in worst.items()))
        for name, rel in worst.items():
            self.assertLess(rel, 1e-9, name)


class ExactIdentities(unittest.TestCase):
    def test_identities_for_both_packages(self):
        cases = ((PR, (BZ, TO), [(330.0, 1e5, [0.4, 0.6]), (420.0, 5e4, [0.5, 0.5]), (600.0, 6e6, [0.3, 0.7])]),
                 (PSRK, (CO2, ETOH), [(333.15, 6.06e6, [0.3317, 0.6683]), (360.0, 2e6, [0.9, 0.1]),
                                      (304.1, 1e7, [0.5, 0.5])]))
        worst = [0.0] * 4
        for pid, cas, states in cases:
            pk = PaqueteEOS(pid, cas)
            eos = pk._eos(range(2))
            for T, P, x in states:
                x = np.array(x)
                for Z in eos.z_roots(T, P, x):
                    V = Z * R * T / P
                    d = pk._phase_derivatives(eos, T, P, x, V)
                    props = eos.molar_props(T, P, x, Z)
                    worst[0] = max(worst[0], abs(d['d'] - (V - T * d['V_T'])) / V)
                    worst[1] = max(worst[1], abs(float(np.dot(x, d['vbar'])) - V) / V)
                    worst[2] = max(worst[2], abs(float(np.dot(x, d['hbar'])) - props['h']) / abs(props['h']))
                    worst[3] = max(worst[3], float(np.max(np.abs(x @ d['G']))) / float(np.max(np.abs(d['G']))))
        print('(dH/dP)_T = V - T(dV/dT)_P {:.1e}; sum n vbar = V {:.1e}; sum n hbar = H {:.1e}; '
              'Gibbs-Duhem {:.1e}'.format(*worst))
        self.assertLess(worst[0], 1e-8)
        self.assertLess(worst[1], 1e-12)
        self.assertLess(worst[2], 1e-9)
        self.assertLess(worst[3], 1e-12)


class PurePlateau(unittest.TestCase):
    """Pure toluene inside its dome at fixed P: dV/dt = (v_V - v_L)/(h_V - h_L) dH/dt (lever rule at T_sat)."""

    def test_plateau_against_the_maxwell_saturation(self):
        pk = PaqueteEOS(PR, (TO,))
        eos = pk._eos([0])
        P = 101325.0
        Tsat = pk._pure_saturation_T(eos, P)
        sat = cubic_flash.pure_saturation(eos, 0, Tsat)
        x1 = np.array([1.0])
        pL, pV = eos.molar_props(Tsat, P, x1, sat['ZL']), eos.molar_props(Tsat, P, x1, sat['ZV'])
        hL, hV = pL['h'], pV['h']
        n = np.array([2.0])
        st = pk.estado('PH', P, 2.0 * (0.3 * hV + 0.7 * hL), n)
        self.assertEqual(len(st.fases), 2)
        ref = (pV['v'] - pL['v']) / (hV - hL) * 400.0
        got = pk.dV_dt_PH(st, 0.0, 400.0, np.zeros(1))
        print(f'plateau: analytic {got:.12e} m3/s, closed form {ref:.12e} m3/s, rel {abs(got - ref) / ref:.1e}; '
              f'P_sat check {abs(sat["P"] - P) / P:.1e}')
        self.assertLess(abs(got - ref) / ref, 1e-9)
        # with a pressure rate the plateau moves along the Clapeyron line: compare with flash differences
        got = pk.dV_dt_PH(st, 20.0, 400.0, np.zeros(1))
        fd = flash_difference(pk, st, 20.0, 400.0, np.zeros(1))
        print(f'plateau with dP/dt: analytic {got:.12e}, flash difference {fd:.12e}, rel {abs(got - fd) / abs(fd):.1e}')
        self.assertLess(abs(got - fd) / abs(fd), 1e-6)


class AgainstFlashDifferences(unittest.TestCase):
    """The analytic derivative against the centred difference of certified PH flashes (the previous route)."""

    def check(self, pid, cas, n, states):
        pk = PaqueteEOS(pid, cas)
        worst, t_an, t_fd, kinds = 0.0, 0.0, 0.0, set()
        for T, P in states:
            st = pk.estado('TP', T, P, n)
            st = pk.estado('PH', st.P, st.H, n)
            kinds.add(len(st.fases))
            for dP, dH, dn in RATES:
                dn = np.zeros(len(n)) if dn is None else np.array(dn)
                t0 = time.perf_counter()
                a = pk.dV_dt_PH(st, dP, dH, dn)
                t_an += time.perf_counter() - t0
                t0 = time.perf_counter()
                f = flash_difference(pk, st, dP, dH, dn)
                t_fd += time.perf_counter() - t0
                # the flash difference carries ~1e-10 of V per step of 1e-6: an absolute floor of 1e-4 V/s
                err = abs(a - f) / max(abs(f), 1e-4 * st.V)
                worst = max(worst, err)
        print(f'{pid} {cas}: phases {sorted(kinds)}, worst scaled difference {worst:.1e}; '
              f'analytic {t_an * 1e3:.1f} ms against {t_fd:.1f} s of flashes')
        self.assertLess(worst, 1e-6)
        return kinds

    def test_peng_robinson_benzene_toluene(self):
        kinds = self.check(PR, (BZ, TO), np.array([0.5, 0.5]), ((330.0, 69.5e3), (352.9, 69.5e3), (420.0, 69.5e3),
                                                                (560.0, 4e6)))
        self.assertEqual(kinds, {1, 2})

    def test_psrk_co2_ethanol(self):
        # 6.06 MPa, x_CO2 = 0.3317 (Sima et al. 2011): liquid, two-phase above the package bubble point (320.7 K),
        # and a compressed liquid next to the CO2 alpha switch at T_c = 304.13 K
        kinds = self.check(PSRK, (CO2, ETOH), np.array([0.3317, 0.6683]), ((315.0, 6.06e6), (330.0, 6.06e6),
                                                                            (304.12, 1e7)))
        self.assertEqual(kinds, {1, 2})


class RouteAndFallbacks(unittest.TestCase):
    def test_no_flash_and_located_fallbacks(self):
        pk = PaqueteEOS(PR, (BZ, TO))
        two = pk.estado('TP', 352.9, 69.5e3, np.array([0.5, 0.5]))
        self.assertEqual(len(two.fases), 2)
        with mock.patch.object(PaqueteEOS, 'estado', side_effect=AssertionError('flash called')):
            self.assertIsNotNone(pk.dV_dt_PH(two, 0.0, 400.0, np.zeros(2)))
        # a species fed into a two-phase state where it is absent: the linearization does not apply
        pk3 = PaqueteEOS(PR, (BZ, TO, '67-56-1'))
        st = pk3.estado('TP', 352.9, 69.5e3, np.array([0.5, 0.5, 0.0]))
        self.assertEqual(len(st.fases), 2)
        self.assertIsNone(pk3.dV_dt_PH(st, 0.0, 0.0, np.array([0.0, 0.0, 1e-3])))
        self.assertIsNotNone(pk3.dV_dt_PH(st, 0.0, 400.0, np.zeros(3)))
        # one phase with a species entering at zero amount: its infinite-dilution vbar and hbar, against flashes
        one = pk3.estado('TP', 330.0, 69.5e3, np.array([0.5, 0.5, 0.0]))
        dn = np.array([0.0, 0.0, 1e-3])
        a = pk3.dV_dt_PH(one, 0.0, 0.0, dn)
        f = flash_difference(pk3, one, 0.0, 0.0, dn)
        print(f'species entering at zero amount: analytic {a:.10e}, flash difference {f:.10e}')
        self.assertLess(abs(a - f) / abs(f), 1e-6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
