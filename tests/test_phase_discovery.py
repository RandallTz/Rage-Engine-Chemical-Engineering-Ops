"""Phase discovery: independent UNIFAC reference, UV closure and trial safety.

The reference shares published pure-property inputs and group tables, but uses
thermo's independent UNIFAC implementation and isoactivity/linear balances.
It is a numerical implementation cross-check, not experimental validation.
"""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
import warnings
import numpy as np
from scipy.optimize import least_squares,brentq
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import mezclas_datos as data,unifac
from core.mezclas import Sistema,FueraDeAlcance,_trial_phase_amounts
CAS=['7732-18-5','71-36-3']
PACKAGE='unifac-original-public'

def activity(T,x):
    import thermo.unifac as reference
    reference.load_unifac_ip()
    return reference.UNIFAC.from_subgroups(T=T,xs=list(x),chemgroups=[unifac.asignacion(c,'original') for c in CAS],subgroups=reference.UFSG,interaction_data=reference.UFIP,version=0)

def reference_state(T,V,n):
    def tie_residual(ab):
        a,b=ab;xa=np.array([a,1-a]);xb=np.array([b,1-b])
        return np.log(xa)+np.log(activity(T,xa).gammas())-np.log(xb)-np.log(activity(T,xb).gammas())
    tie=least_squares(tie_residual,[.98,.52],bounds=([.9,.1],[.999999,.8]),xtol=1e-14,ftol=1e-14,gtol=1e-14)
    assert max(abs(tie_residual(tie.x)))<1e-10
    xa=np.array([tie.x[0],1-tie.x[0]]);xb=np.array([tie.x[1],1-tie.x[1]])
    species=[data.especie(c) for c in CAS];vL=np.array([item.vL for item in species]);Psat=np.array([item.Psat(T) for item in species])
    activities=xa*np.array(activity(T,xa).gammas())
    fugacity=lambda P:activities*Psat*np.exp(vL*(P-Psat)/(data.R*T))
    P=brentq(lambda P:sum(fugacity(P))-P,100.,5e5,xtol=1e-10)
    y=fugacity(P)/P
    volumes=np.array([data.R*T/P,np.dot(xa,vL),np.dot(xb,vL)])
    amounts=np.linalg.solve(np.array([[y[0],xa[0],xb[0]],[y[1],xa[1],xb[1]],volumes]),np.array([*n,V]))
    assert np.all(amounts>0)
    h=[sum(x*item.h_ig(T) for x,item in zip(y,species))]
    for x in (xa,xb):h.append(sum(xi*item.h_L(T,P) for xi,item in zip(x,species))+activity(T,x).HE())
    U=np.dot(amounts,np.array(h)-P*volumes)
    return {'T':T,'P':P,'U':U,'V':V,'x':[y,xa,xb],'amounts':amounts}

def signature(state,reverse=False):
    return sorted([(phase.tipo,float(phase.n),*(phase.x[::-1] if reverse else phase.x)) for phase in state.fases])

class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system=Sistema(PACKAGE,CAS);cls.n=np.array([.8,.2]);cls.V=.01
        cls.reference=reference_state(298.15,cls.V,cls.n)
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            cls.initial=cls.system.equilibrio_TV(298.15,cls.V,cls.n)
    def test_independent_tv_phase_distribution(self):
        ref=self.reference;actual=self.initial
        self.assertAlmostEqual(actual.P/ref['P'],1.,places=9)
        self.assertLess(abs(actual.U-ref['U']),1e-6)
        observed=sorted(actual.fases,key=lambda p:0 if p.tipo=='vapor' else 1-p.x[0])
        for i,phase in enumerate(observed):
            np.testing.assert_allclose(phase.x,ref['x'][i],atol=1e-9,rtol=0)
            self.assertAlmostEqual(phase.n,ref['amounts'][i],places=9)
    def test_independent_uv_recovery(self):
        ref=self.reference
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            actual=self.system.equilibrio_UV(ref['U'],ref['V'],self.n)
        self.assertAlmostEqual(actual.T,ref['T'],places=7)
        self.assertAlmostEqual(actual.P/ref['P'],1.,places=8)
        self.assertLess(abs(actual.V-ref['V']),1e-10)
        self.assertLess(abs(actual.U-ref['U']),1e-6)
    def test_order_and_unrelated_seed_invariance(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            reordered=Sistema(PACKAGE,CAS[::-1]).equilibrio_TV(298.15,self.V,self.n[::-1])
            vapor_seed=self.system.equilibrio_TV(450.,self.V,self.n)
            actual=self.system.flash_rapido('UV',self.initial.U,self.V,self.n,vapor_seed)
        for other,reverse in [(reordered,True),(actual,False)]:
            left,right=signature(self.initial),signature(other,reverse)
            self.assertEqual([p[0] for p in left],[p[0] for p in right])
            np.testing.assert_allclose([p[1:] for p in left],[p[1:] for p in right],rtol=1e-8,atol=1e-8)
    def test_phase_boundary_from_independent_tie_line(self):
        # Test both sides of the independently found binary miscibility endpoints.
        xa,xb=self.reference['x'][1][0],self.reference['x'][2][0]
        for water,liquids in [(xa+1e-5,1),(xa-1e-5,2),(xb+1e-5,2),(xb-1e-5,1)]:
            with warnings.catch_warnings():
                warnings.simplefilter('error',RuntimeWarning)
                state=self.system.equilibrio_TP(298.15,101325.,np.array([water,1-water]))
            self.assertEqual(sum(p.tipo=='liquido' for p in state.fases),liquids)
            self.assertLessEqual(state.verificaciones['estabilidad'][0],state.verificaciones['estabilidad'][1])
    def test_same_package_discovers_different_phase_sets(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            states=[self.system.equilibrio_TV(T,self.V,self.n) for T in (298.15,400.,420.)]
        self.assertEqual([len(state.fases) for state in states],[3,2,1])
        for state in states:
            for residual,tolerance,*_ in state.verificaciones.values():self.assertLessEqual(residual,tolerance)
    def test_uv_coarse_bracket_preserves_strict_certification(self):
        # Reproduced UV failures: a valid invariant pressure lay 1.087e-6
        # from the seed inside its 5.03e-6 search neighborhood. A fixed 1e-6
        # acceptance window rejected it despite machine-precision equality.
        for U in (-25239.74194191368,-20239.741941913675):
            with warnings.catch_warnings():
                warnings.simplefilter('error',RuntimeWarning)
                state=Sistema(PACKAGE,CAS).equilibrio_UV(U,self.V,self.n)
            self.assertLess(abs(state.U-U),1e-6)
            self.assertLess(abs(state.V-self.V),1e-10)
            self.assertEqual(state.verificaciones['equilibrio'][1],1e-10)
            for residual,tolerance,*_ in state.verificaciones.values():self.assertLessEqual(residual,tolerance)

    def test_invalid_trials_are_rejected_without_warnings(self):
        for logs in ([1000.,1000.],[-1000.,-1000.],[np.nan,0.],[np.inf,0.],np.log([.8,.2]),np.log([.7,.1,.7,.1])):
            with warnings.catch_warnings():
                warnings.simplefilter('error',RuntimeWarning)
                self.assertIsNone(_trial_phase_amounts(logs,self.n))
        result=_trial_phase_amounts(np.log([.1,.01]),self.n)
        np.testing.assert_allclose(sum(result),self.n,rtol=0,atol=1e-16)
        np.testing.assert_allclose(result[0],[.1,.01],atol=1e-16)
    def test_filled_incompressible_vessel_is_not_given_an_invented_pressure(self):
        V=sum(self.n*np.array(self.system.vL))
        with self.assertRaises(FueraDeAlcance) as failure:self.system.equilibrio_TV(298.15,V,self.n)
        self.assertEqual(failure.exception.motivo,'no_soportado')
    def test_corrupt_seed_falls_back_to_full_equilibrium(self):
        corrupted=copy.deepcopy(self.initial);corrupted.T=math.nan
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            actual=self.system.flash_rapido('UV',self.initial.U,self.V,self.n,corrupted)
        self.assertAlmostEqual(actual.T,298.15,places=8)
        self.assertEqual(len(actual.fases),len(self.initial.fases))

if __name__=='__main__':unittest.main()
