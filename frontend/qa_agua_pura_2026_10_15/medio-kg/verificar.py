"""Read-only audit of the actual 0.5 kg worksheet, no backend modifications.
Run from repo root: python frontend/qa_agua_pura_2026_10_15/medio-kg/verificar.py
"""
import json
from pathlib import Path
import chemicals.iapws as w

here=Path(__file__).resolve().parent
p=json.loads((here/'respuesta-ui.json').read_text(encoding='utf-8'))
s,r=p['solicitud'],p['respuesta']
a=r['resultados']
d={q['variableId'].removeprefix('volumen.dominio.'):q['valores'] for q in a['series']}
checks=0
def check(c,msg):
    global checks
    checks+=1
    assert c,msg

check(s['volumen']['frontera']['tipo']=='rigida' and not s['corrientes'],'Closed, rigid, no outlet')
check(r['estado']=='parcial','Do not imply the requested 900 seconds were completed')
check(d['m.1'][0]==.5 and d['V'][0]==.003 and abs(d['T'][0]-283.15)<1e-8,'Actual initial data')
max_energy=max_sat=0
for k,t in enumerate(a['tiempos']):
    e=a['estadosTermodinamicos'][k]
    check(d['m.1'][k]==.5 and d['V'][k]==.003,'Conserve water and volume')
    check(d['Q'][k]==10000,'10 kW net, not 1 kW')
    err=abs(d['U'][k]-d['U'][0]-10000*t)
    max_energy=max(max_energy,err)
    check(err<1e-5,'First law: U-U0=Q t')
    check(abs(sum(f['fraccionMasica'] for f in e['fases'])-1)<1e-9,'Phase mass normalization')
    check(abs(.5*sum(f['fraccionMasica']*f['propiedades']['v'] for f in e['fases'])-.003)<1e-10,'Reconstruct total occupied volume')
    check(abs(.5*sum(f['fraccionMasica']*f['propiedades']['u'] for f in e['fases'])-d['U'][k])<1e-4,'Reconstruct energy from phases')
    check(abs(sum(f['fraccionMasica'] for f in e['fases'] if f['tipo']=='vapor')-d['q'][k])<1e-10,'Vapor fraction follows actual phases')
    if len(e['fases'])==2:
        err=abs(w.Psat_IAPWS(e['T'])/e['P']-1)
        max_sat=max(max_sat,err)
        check(err<.002,'Independent IF97 saturation pressure')

# Final vapor lies in IF97 region 3: use its Helmholtz pressure equation at T,rho.
e=a['estadosTermodinamicos'][-1]
T=e['T'];rho=.5/.003;tau=647.096/T;delta=rho/322
P97=rho*w.iapws97_R*T*delta*w.iapws97_dA_ddelta_region3(tau,delta)
u97=w.iapws97_R*T*tau*w.iapws97_dA_dtau_region3(tau,delta)
check(abs(P97/e['P']-1)<.002,'Final pressure versus independent IF97 region 3')
check(abs(u97-e['mezcla']['u'])<1000,'Final specific energy versus IF97 <1 kJ/kg')
check(d['q'][-1]==1 and e['fases'][0]['tipo']=='vapor','Entirely vapor before domain stop')
check(any('banda critica' in x['mensaje'] for x in r['validacion']['diagnosticos']),'Explicit excluded critical-band limit')
report=dict(comprobaciones=checks,masa_kg=.5,volumen_L=3,calor_W=10000,
            final=dict(t_s=a['tiempos'][-1],T_C=T-273.15,P_bar=e['P']/1e5,q=d['q'][-1]),
            calor_acumulado_J=10000*a['tiempos'][-1],error_primera_ley_J=max_energy,
            max_error_P_saturacion_IF97_rel=max_sat,P_final_IF97_bar=P97/1e5,
            error_P_final_IF97_rel=abs(P97/e['P']-1),error_u_final_IF97_Jkg=abs(u97-e['mezcla']['u']),
            limite='Partial trajectory: excluded critical band, not a prediction of vessel failure.')
(here/'evidencias.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
