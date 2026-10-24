"""First-law provenance and independent conservation/pressure-work references."""
import copy
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.balances.energy_derivation import edit_journal, describe_volume, read_journal, fundamental
from core.modelo.operation_journal import JournalError
from core.modelo import desde_ensamblaje_v2, a_ensamblaje_v2, leer_modelo_comun, ErrorModelo
from core.compilador import compilar, NoSoportado
from core.compilador.report import compilation_report
ROOT=Path(__file__).resolve().parents[1]
CONTEXT={"fixed":False,"remainderClosed":True,"streamIds":[],"pressurePrescribed":True}

def journal():
    result={"format":"rage.energy-derivation","version":1,"volumes":{}}
    for kind in ("start","integrate","reynolds","pressure_stress","enthalpy","total","no_kinetic","no_viscous_work","no_body_work","no_volume_source","uniform_state","uniform_pressure","prescribed_pressure"):
        result=edit_journal(result,"A",{"kind":kind})
    return result

def model():
    source=json.loads((ROOT/'frontend/app/motor/ejemplosMultifasicos.json').read_text(encoding='utf-8'))[0]
    source['derivacion']={"energyDerivation":journal()}
    return desde_ensamblaje_v2(source)

class EnergyTests(unittest.TestCase):
    def test_ordered_development(self):
        result=describe_volume(journal(),'A',CONTEXT)
        self.assertEqual(result['steps'][0]['latex'].split('=')[0],r"\frac{\partial(\rho e)}{\partial t}")
        self.assertEqual(result['steps'][-1]['latex'],r"\frac{dU}{dt}=\dot Q-\dot W_b")
        self.assertTrue(any('Gauss' in step['title'] for step in result['steps']))
        self.assertTrue(any('Reynolds' in step['title'] for step in result['steps']))
        self.assertTrue(any('V dP/dt' in note for note in result['notes']))
    def test_strict_reader(self):
        for mutate in (lambda j:j.update(version=True),lambda j:j.update(extra=1),lambda j:j['volumes']['A']['operations'][0]['changes'].update(foo=True),lambda j:j['volumes']['A']['operations'][0]['changes'].update(adiabatico='true'),lambda j:j['volumes']['A']['operations'].append(copy.deepcopy(j['volumes']['A']['operations'][0]))):
            value=journal();mutate(value)
            with self.assertRaises(JournalError):read_journal(value)
    def test_enthalpy_requires_pressure_separation(self):
        value=edit_journal({'format':'rage.energy-derivation','version':1,'volumes':{}},'A',{'kind':'start'})
        with self.assertRaises(JournalError):edit_journal(value,'A',{'kind':'enthalpy'})
        with self.assertRaises(JournalError):edit_journal(value,'A',{'kind':'prescribed_pressure'})
    def test_nonmutating_edit_undo(self):
        before=journal();copy_before=copy.deepcopy(before)
        changed=edit_journal(before,'A',{'kind':'adiabatic'})
        self.assertEqual(before,copy_before)
        self.assertEqual(edit_journal(changed,'A',{'kind':'undo'}),before)
    def test_roundtrip_and_provenance(self):
        value=model();self.assertIs(leer_modelo_comun(value),value)
        self.assertEqual(desde_ensamblaje_v2(a_ensamblaje_v2(value)),value)
        report=compilation_report(value)
        self.assertEqual(report['energyDerivation'][0]['relationIds'],['energia.A'])
        self.assertEqual(len(report['energyDerivation'][0]['signature']),64)
    def test_mismatch_rejected_on_both_apis(self):
        value=model();value['volumenes'][0]['supuestos']['energia']['adiabatico']=True
        with self.assertRaises(ErrorModelo):leer_modelo_comun(value)
        from backend.motor_ensamblaje_v2 import validar_v2
        response,_=validar_v2(a_ensamblaje_v2(value))
        self.assertTrue(any(d['codigo']=='MOTOR_ENS_ENERGY_JOURNAL' for d in response['diagnosticos']))
    def test_ignored_energy_terms_rejected(self):
        for change in ({'sinCinetica':False},{'sinAcumulacionTotal':True},{'sinConduccionLocal':True}):
            value=model();value['motores']={};value['volumenes'][0]['supuestos']['energia'].update(change)
            with self.assertRaises(NoSoportado):compilar(value)
    def test_closed_heating_reference(self):
        # rho e -> total U, m and heat capacity fixed: U'=Q, T'=Q/(m c).
        mass,capacity,Q,dt=10.,4000.,1000.,300.
        T0=293.15;U0=mass*capacity*T0
        U1=U0+Q*dt
        self.assertAlmostEqual(U1/(mass*capacity),T0+7.5)
        from core.balances.energy_derivation import equation,normalize
        state=normalize({**fundamental(), 'forma':'total','separarPresion':True,'sinCinetica':True,'sinTrabajoViscoso':True,'sinFuerzasVolumen':True,'sinFuenteVolumetrica':True})
        self.assertEqual(equation(state,{**CONTEXT,'fixed':True}),r"\frac{dU}{dt}=\dot Q")
    def test_prescribed_pressure_rhs_reference(self):
        # Check the actual compiled RHS independently: no streams, H'=Q+V P'.
        system=compilar(model());volume=system.vols[0]
        volume.dato_P=SimpleNamespace(d_dt=lambda t:17.)
        state=SimpleNamespace(T=300.,V=0.03)
        system._estados=lambda t,y:{volume.id:state}
        system.dato=lambda id:lambda t:120.
        dy=system.rhs(0.,np.zeros(system.tam))
        self.assertAlmostEqual(dy[volume.i_E],120.+0.03*17.)
        self.assertAlmostEqual(dy[system.i_aux_E],dy[volume.i_E])
    def test_moving_open_balance_algebra(self):
        # U=m c(T-Tref); U'=Fin hin-Fout hout+Q-P V'; h=u+P/rho.
        mass,c,rho,T,Tref,Tin,Fin,Fout,Q,P=100.,4000.,1000.,310.,293.15,330.,3.,2.,8000.,100000.
        mdot=Fin-Fout;u=c*(T-Tref);uin=c*(Tin-Tref)
        Udot=Fin*(uin+P/rho)-Fout*(u+P/rho)+Q-P*mdot/rho
        Tdot=(Udot-u*mdot)/(mass*c)
        self.assertAlmostEqual(Tdot,(Fin*c*(Tin-T)+Q)/(mass*c))

if __name__=='__main__':unittest.main()

