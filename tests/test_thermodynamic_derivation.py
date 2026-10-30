"""State-closure provenance and independent thermodynamic identity checks."""
import copy
import json
from pathlib import Path
import sys
import unittest
import math
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.termodinamica.derivation import edit_journal,read_journal,describe_volume,expected_closure
from core.modelo.operation_journal import JournalError
from core.modelo import desde_ensamblaje_v2,leer_modelo_comun,ErrorModelo,a_ensamblaje_v2
from core.compilador.report import compilation_report
ROOT=Path(__file__).resolve().parents[1]

def source():return json.loads((ROOT/'frontend/app/motor/ejemplosUNIFAC.json').read_text(encoding='utf-8'))[0]['solicitud']
def journal(model):
    result={'format':'rage.thermodynamic-derivation','version':1,'volumes':{}}
    for volume in model['volumenes']:
        result=edit_journal(result,volume['id'],{'kind':'start'})
        result=edit_journal(result,volume['id'],{'kind':'select_closure'},expected_closure(model,volume))
    return result
def model():
    original=source();original['derivacion']={'thermodynamicDerivation':journal(desde_ensamblaje_v2(original))};return desde_ensamblaje_v2(original)

class ThermodynamicTests(unittest.TestCase):
    def test_excess_caloric_and_chemical_potential_identities(self):
        from core.mezclas import Sistema,R
        # Independent centered differences of the selected excess potential;
        # the production caloric path uses a complex derivative instead.
        for package in ('unifac-original-public','unifac-dortmund-public','unifac-original-lle-public'):
            system=Sistema(package,['7732-18-5','71-36-3'])
            T,P,x=300.,101325.,np.array([.7,.3])
            excess=system._modelo_sub([0,1])
            def G(amounts,temperature=T):
                total=sum(amounts)
                return total*R*temperature*float(excess.gE_RT(temperature,np.array(amounts)/total))
            entropy=-(G(x,T+.001)-G(x,T-.001))/.002
            enthalpy=G(x)+T*entropy
            phase=system.fase('test','liquido',T,P,x,[0,1])
            mu=system.mu('liquido',T,P,x,[0,1])
            self.assertAlmostEqual(phase.g,float(x@mu),delta=1e-6)
            dmu_dT=(system.mu('liquido',T+.001,P,x,[0,1])-system.mu('liquido',T-.001,P,x,[0,1]))/.002
            dmu_dP=(system.mu('liquido',T,P+1.,x,[0,1])-system.mu('liquido',T,P-1.,x,[0,1]))/2.
            self.assertAlmostEqual(float(x@dmu_dT),-phase.s,delta=1e-4)
            self.assertAlmostEqual(float(x@dmu_dP),phase.v,delta=1e-9)
            pure_h=sum(x[i]*species.h_L(T,P) for i,species in enumerate(system.esp))
            self.assertAlmostEqual(phase.h-pure_h,enthalpy,delta=1e-4)
            for i in range(2):
                plus=x.copy();minus=x.copy();plus[i]+=1e-5;minus[i]-=1e-5
                mu=(G(plus)-G(minus))/2e-5
                self.assertAlmostEqual(mu,R*T*excess.lngamma(T,x)[i],delta=1e-4)
            development=describe_volume(model()['motores']['thermodynamicDerivation'],'A',False)
            self.assertTrue(any(item['id'].endswith('.caloric') for item in development['steps']))
    def test_fundamental_to_unifac_closure(self):
        value=model();development=describe_volume(value['motores']['thermodynamicDerivation'],'A',False)
        self.assertTrue(development['steps'][0]['latex'].startswith('dU='))
        self.assertTrue(any('UNIFAC' in item['title'] for item in development['steps']))
        self.assertIn('H,P',development['steps'][-1]['latex'])
        self.assertTrue(any('empirical' in item for item in development['notes']))
    def test_roundtrip_and_actual_relation_ids(self):
        value=model();self.assertIs(leer_modelo_comun(value),value)
        self.assertEqual(desde_ensamblaje_v2(a_ensamblaje_v2(value)),value)
        report=compilation_report(value)
        self.assertIn('estado.A.energia',report['thermodynamicDerivation'][0]['relationIds'])
    def test_package_and_policy_mismatch_rejected(self):
        for mutate in (lambda m:m['termodinamica']['paquetes'][0]['modelo'].update(version='changed'),lambda m:m['volumenes'][0]['termodinamica']['politica'].update(cantidad='monofasico')):
            value=model();mutate(value)
            with self.assertRaises(ErrorModelo):leer_modelo_comun(value)
    def test_strict_reader(self):
        for mutate in (lambda j:j.update(version=True),lambda j:j['volumes']['A']['operations'][0].update(extra=True),lambda j:j['volumes']['A']['operations'][0]['changes']['closure']['policy'].update(tiposPermitidos=[{}]),lambda j:j['volumes']['A']['operations'][0]['changes'].update(modelo='u_lineal')):
            value=model()['motores']['thermodynamicDerivation'];mutate(value)
            with self.assertRaises(JournalError):read_journal(value)
    def test_manual_and_package_closures_do_not_mix(self):
        value=model()['motores']['thermodynamicDerivation']
        for kind in ('constant_density','linear_caloric'):
            with self.assertRaises(JournalError):edit_journal(value,'A',{'kind':kind})
    def test_policy_edit_updates_both_contracts(self):
        before=model()['motores']['thermodynamicDerivation'];after=edit_journal(before,'A',{'kind':'one_phase'})
        state=describe_volume(after,'A',False)['formulation']
        self.assertTrue(state['monofasico']);self.assertEqual(state['closure']['policy']['cantidad'],'monofasico')
        self.assertEqual(edit_journal(after,'A',{'kind':'undo'}),before)
    def test_manual_caloric_inverse(self):
        value={'format':'rage.thermodynamic-derivation','version':1,'volumes':{}}
        for kind in ('start','one_phase','no_phase_change','linear_caloric','constant_density'):value=edit_journal(value,'v',{'kind':kind})
        result=describe_volume(value,'v',True)
        self.assertIn('U/m',result['steps'][-1]['latex'])
        c,Tref,uref,m,T=4000.,293.15,20.,10.,315.
        U=m*(uref+c*(T-Tref));self.assertAlmostEqual(Tref+(U/m-uref)/c,T)
    def test_chemical_potential_reference(self):
        # Independently differentiate the ideal mixing potential at fixed T,P.
        R,T,n=8.314462618,310.,[2.,3.]
        def G(amounts):return R*T*sum(item*math.log(item/sum(amounts)) for item in amounts)
        mu=[R*T*math.log(item/sum(n)) for item in n]
        for i in range(2):
            plus=n.copy();minus=n.copy();plus[i]+=1e-5;minus[i]-=1e-5
            self.assertAlmostEqual((G(plus)-G(minus))/2e-5,mu[i],places=5)
        self.assertAlmostEqual(G(n),sum(a*b for a,b in zip(n,mu)))
    def test_route_response_and_invalid_owner(self):
        from backend.api_modelo import thermodynamic_derivation
        from fastapi import HTTPException
        value=model()['motores']['thermodynamicDerivation']
        response=thermodynamic_derivation({'journal':value,'volumeId':'A','fixed':False})
        self.assertEqual(response['journal'],value)
        for owner in ([],None,'missing'):
            with self.assertRaises(HTTPException) as error:thermodynamic_derivation({'journal':value,'volumeId':owner,'fixed':False})
            self.assertEqual(error.exception.status_code,422)
        with self.assertRaises(HTTPException) as error:thermodynamic_derivation({'journal':{'format':'rage.thermodynamic-derivation','version':1,'volumes':[]},'volumeId':'A','fixed':False,'action':{'kind':'start'}})
        self.assertEqual(error.exception.status_code,422)
    def test_native_api_rejects_forged_closure(self):
        from backend.motor_ensamblaje_v2 import validar_v2
        value=model();value['volumenes'][0]['termodinamica']['politica']['cantidad']='monofasico'
        response,_=validar_v2(a_ensamblaje_v2(value))
        self.assertTrue(any(d['codigo']=='MOTOR_ENS_THERMODYNAMIC_JOURNAL' for d in response['diagnosticos']))

if __name__=='__main__':unittest.main()
