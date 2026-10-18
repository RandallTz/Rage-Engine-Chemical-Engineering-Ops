"""Audit the unmodified worksheet response; no changes to backend physics.
Run from repository root: python frontend/qa_agua_pura_2026_10_15/verificar_fisica.py
IF97 is a different formulation of the same reference water data, not a new
experiment or a second implementation of IAPWS-95. No vessel strength model.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import chemicals.iapws as w
from scipy.optimize import brentq
from backend.motor_ensamblaje import resolver

HERE = Path(__file__).resolve().parent
pair = json.loads((HERE / 'respuesta-ui.json').read_text(encoding='utf-8'))
checks = 0


def check(c, msg):
    global checks
    checks += 1
    assert c, msg


def regional(T, P, region):
    """Direct IF97 Gibbs derivatives, regions 1/2, including saturation sides."""
    R = w.iapws97_R
    if region == 1:
        tau, pi = 1386 / T, P / 16.53e6
        g = w.iapws97_G_region1(tau, pi)
        gt = w.iapws97_dG_dtau_region1(tau, pi)
        gp = w.iapws97_dG_dpi_region1(tau, pi)
    else:
        tau, pi = 540 / T, P / 1e6
        g = w.iapws97_G0_region2(tau, pi) + w.iapws97_Gr_region2(tau, pi)
        gt = w.iapws97_dG0_dtau_region2(tau, pi) + w.iapws97_dGr_dtau_region2(tau, pi)
        gp = 1/pi + w.iapws97_dGr_dpi_region2(tau, pi)
    return dict(v=R*T*pi*gp/P, u=R*T*(tau*gt-pi*gp), s=R*(tau*gt-g))


def if97_fixed_volume(T, v):
    """Independent equilibrium path at fixed v for this dense-water test only."""
    R = w.iapws97_R
    if T <= 623.15:
        ps = w.Psat_IAPWS(T)
        l, g = regional(T, ps, 1), regional(T, ps, 2)
        q = (v-l['v'])/(g['v']-l['v'])
        if 0 <= q <= 1:
            return dict(P=ps, u=(1-q)*l['u']+q*g['u'], q=q)
        # At this fixed density the post-coexistence branch is compressed liquid.
        p = w.iapws97_P(T, 1/v)
        return dict(P=p, u=regional(T, p, 1)['u'], q=0)
    # Region 3 Helmholtz equation: all high-T states in this test are dense.
    tau, delta = 647.096/T, (1/v)/322
    return dict(P=(1/v)*R*T*delta*w.iapws97_dA_ddelta_region3(tau, delta),
                u=R*T*tau*w.iapws97_dA_dtau_region3(tau, delta), q=None)


def audit(s, r):
    a = r['resultados']
    check(a is not None and r['estado'] in ('resuelto', 'parcial'), 'Certified trajectory')
    check(s['volumen']['frontera']['tipo'] == 'rigida' and not s['corrientes'], 'Closed rigid system')
    d = {x['variableId'].split('volumen.dominio.')[-1]: x['valores'] for x in a['series']}
    check(d['m.1'][0] == 2 and d['V'][0] == .003 and abs(d['T'][0]-283.15)<1e-8, 'Original geometry/initials')
    max_energy = max_p = max_heat_if97 = max_q = 0.
    q_checked = 0
    initial_ref = if97_fixed_volume(d['T'][0], .0015)
    for k, t in enumerate(a['tiempos']):
        st = a['estadosTermodinamicos'][k]
        m, U, T, P, V, q, Q = (d[x][k] for x in ('m.1', 'U', 'T', 'P', 'V', 'q', 'Q'))
        check(m == 2 and V == .003, 'Mass and geometric volume conserved')
        err = abs(U-d['U'][0]-Q*t)
        max_energy = max(max_energy, err)
        check(err < 1e-5, 'First law: U-U0 = Q t; no hidden latent-heat source')
        check(P > 0 and T > 0 and all(0 <= f['fraccionMasica'] <= 1 for f in st['fases']), 'Positive physical state')
        check(abs(sum(f['fraccionMasica'] for f in st['fases'])-1)<1e-9, 'Phase masses normalized')
        check(abs(sum(f['fraccionVolumen'] for f in st['fases'])-1)<1e-9, 'Phase volumes normalized')
        check(abs(q-sum(f['fraccionMasica'] for f in st['fases'] if f['tipo']=='vapor'))<1e-10, 'q means vapor, not all non-liquid material')
        check(abs(m*sum(f['fraccionMasica']*f['propiedades']['v'] for f in st['fases'])-V)<1e-10, 'Phase volumes reconstruct vessel volume')
        check(abs(m*sum(f['fraccionMasica']*f['propiedades']['u'] for f in st['fases'])-U)<1e-4, 'Phase energies reconstruct U')
        check(all(v['estado'] != 'no_cumple' for v in st['verificaciones']), 'Published certificates pass')
        ref = if97_fixed_volume(T, V/m)
        max_p = max(max_p, abs(ref['P']-P)/P)
        max_heat_if97 = max(max_heat_if97, abs((ref['u']-initial_ref['u'])*m-(U-d['U'][0])))
        check(abs(ref['P']-P)/P < .002, 'Pressure versus independent IF97 formulation <0.2%')
        check(abs((ref['u']-initial_ref['u'])*m-(U-d['U'][0])) < 3000, 'Heat gain versus IF97 <3 kJ')
        if ref['q'] is not None:
            max_q = max(max_q, abs(ref['q']-q)); q_checked += 1
            check(abs(ref['q']-q) < .0002, 'Vapor mass fraction versus IF97 lever rule')
        if k:
            check(T>d['T'][k-1] and P>d['P'][k-1], 'T and P rise on this positive-heating dense-water path')
            check(st['mezcla']['s']>a['estadosTermodinamicos'][k-1]['mezcla']['s'], 'Entropy of heated closed water increases')
    return dict(estado=r['estado'],muestras=len(a['tiempos']),potencia_W=d['Q'][0],
                tiempo_final_s=a['tiempos'][-1],T_final_C=d['T'][-1]-273.15,P_final_bar=d['P'][-1]/1e5,
                fases_finales=[dict(tipo=f['tipo'],masa_kg=2*f['fraccionMasica'],fraccionMasica=f['fraccionMasica'],fraccionVolumen=f['fraccionVolumen']) for f in a['estadosTermodinamicos'][-1]['fases']],
                error_energia_J=max_energy,error_P_IF97_rel=max_p,error_calor_IF97_J=max_heat_if97,
                error_q_IF97_abs=max_q,muestras_q_IF97=q_checked,eventos=a['eventos'])


actual = audit(pair['solicitud'], pair['respuesta'])
check(pair['respuesta']['estado']=='parcial', '10 kW does not falsely complete 15 minutes')
check(any(e['codigo']=='salida_dominio' for e in pair['respuesta']['resultados']['eventos']), 'Explicit domain stop')
check(actual['P_final_bar'] <= 1000 and abs(actual['P_final_bar']-1000)<.01, 'Stops at 100 MPa without publishing outside')

refine_actual = copy.deepcopy(pair['solicitud'])
refine_actual['solicitudId'] = 'qa-agua-10kw-refinado'
refine_actual['estudio']['muestras'] = 201
refine_actual['estudio']['rtol'] = 1e-10
refine_actual['estudio']['atol'] = dict(masa=1e-13,energia=1e-8)
r10f = resolver(refine_actual)
check(r10f['estado']=='parcial', 'Refined 10 kW case also stops at domain')
check([e['codigo'] for e in r10f['resultados']['eventos']]==[e['codigo'] for e in pair['respuesta']['resultados']['eventos']], 'Refinement preserves all events and their order')
event_error=max(abs(e['tiempo']-f['tiempo']) for e,f in zip(r10f['resultados']['eventos'],pair['respuesta']['resultados']['eventos']))
check(event_error<1e-4, '10 kW event times converge <0.1 ms')
actual_series={v['variableId']:v['valores'] for v in pair['respuesta']['resultados']['series']}
refined_series={v['variableId']:v['valores'] for v in r10f['resultados']['series']}
matched=0
for k,t in enumerate(pair['respuesta']['resultados']['tiempos']):
    j=next((j for j,x in enumerate(r10f['resultados']['tiempos']) if abs(t-x)<1e-9),None)
    if j is not None:
        matched+=1
        for name,tol in [('T',1e-4),('P',10),('q',1e-8),('U',1e-4)]:
            key='volumen.dominio.'+name
            check(abs(actual_series[key][k]-refined_series[key][j])<tol, '10 kW convergence at common sample: '+name)
check(matched>=35, 'Enough common samples to compare actual 10 kW run')

# Reference case and a numerical refinement: no mutation of the current 10 kW worksheet.
base = copy.deepcopy(pair['solicitud'])
base['datos']['volumen.dominio.Q']['declaracion'] = dict(texto='1', unidad='kW')
base['solicitudId'] = 'qa-agua-1kw'
r1 = resolver(base)
(HERE/'respuesta-1kw.json').write_text(json.dumps(dict(solicitud=base,respuesta=r1),indent=2),encoding='utf-8')
reference = audit(base, r1)
check(r1['estado']=='resuelto' and r1['resultados']['tiempos'][-1]==900, '1 kW completes 15 minutes')
fine = copy.deepcopy(base)
fine['solicitudId'] = 'qa-agua-1kw-refinado'
fine['estudio']['muestras'] = 201
fine['estudio']['rtol'] = 1e-10
fine['estudio']['atol'] = dict(masa=1e-13,energia=1e-8)
rf = resolver(fine)
check(rf['estado']=='resuelto', 'Refined trajectory completes')
coarse_series = {v['variableId']:v['valores'] for v in r1['resultados']['series']}
fine_series = {v['variableId']:v['valores'] for v in rf['resultados']['series']}
convergence = {}
for name, tol in [('T',1e-5),('P',.1),('q',1e-9),('U',1e-5)]:
    key='volumen.dominio.'+name
    dif=max(abs(v-fine_series[key][2*k]) for k,v in enumerate(coarse_series[key]))
    check(dif<tol, 'Sampling/tolerance convergence: '+name)
    convergence[name] = dif

# Independent reference temperature obtained from IF97 energy and volume, not UV flash.
u0 = if97_fixed_volume(283.15,.0015)['u']
Tref = brentq(lambda T: if97_fixed_volume(T,.0015)['u']-u0-1000*900/2, 350,450)
check(abs(Tref-(reference['T_final_C']+273.15))<.2, 'Final T versus independent IF97 energy inversion <0.2 K')

# Negative controls prove that the checks detect broken coupling and wrong fractions.
for label, mutate in [
    ('energy',lambda r:r['resultados']['series'][1]['valores'].__setitem__(5,r['resultados']['series'][1]['valores'][5]+100)),
    ('mass',lambda r:r['resultados']['series'][0]['valores'].__setitem__(5,1.9)),
    ('pressure',lambda r:next(x for x in r['resultados']['series'] if x['variableId'].endswith('.P'))['valores'].__setitem__(5,1e5)),
    ('phase',lambda r:r['resultados']['estadosTermodinamicos'][5]['fases'][0].__setitem__('fraccionMasica',.5)),
]:
    broken=copy.deepcopy(r1);mutate(broken)
    try:
        audit(base,broken)
    except AssertionError:
        check(True,'Negative control caught: '+label)
    else:
        raise AssertionError('Negative control escaped: '+label)

report=dict(comprobaciones=checks,actual_10kw=actual,referencia_1kw=reference,
            convergencia_maxima=convergence,convergencia_10kw=dict(error_eventos_s=event_error,muestras_comunes=matched),T_final_IF97_C=Tref-273.15,
            referencia='IAPWS-IF97 R7-97(2012), regions 1/2/3/4 via chemicals.iapws',
            limites='Ideal equilibrium vessel; no air, wall heat capacity, losses, valve or structural failure. IF97 shares reference water data with IAPWS-95.')
(HERE/'evidencias.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
