'use client';
/** Panel Termodinámica de la hoja (ARCHITECTURE.md §3 y §11): la termodinámica no es un balance que se
 * activa, es el cierre de estado de cada volumen y está siempre presente. Muestra, como las vistas de materia
 * y energía, las relaciones generales; después el cierre que declara cada volumen (con las fases candidatas y la
 * familia del modelo de estado que publica el servidor, POST /modelo/termodinamica) y los supuestos que se
 * pueden hacer desde la termodinámica, con su efecto, si están activos y dónde se declaran.
 * Es presentación: no evalúa ningún estado. */
import ModelWorksheet from '../models/ModelWorksheet';
import worksheetStyles from './motor.module.css';
import { ThermodynamicAssumptions } from './ModelAssumptions';
import {useEffect,useMemo,useState} from 'react';
import Link from 'next/link';
import type {HojaMotor} from './hojasMotor';
import FormulaMateria from './FormulaMateria';
import styles from './balances.module.css';
import {firmaHoja} from './modeloHojaMotor';
import {urlEnfoqueRed} from './destinoDiagnosticoRed';
import {cabeEnBalances,modeloBalancesDesdeHoja} from '../../motores/modelo/desdeHojaBalances';
import {modeloDesdeHojaMotor} from '../../motores/modelo/desdeHojaMotor';
import {describirTermodinamica,type DescripcionTermodinamica,type VolumenTermodinamico} from '../../motores/modelo/servicioModelo';
import type {VistaHoja} from './familiasBalance';
import {OPERACIONES_TERMO,valorRetirado,TITULO_FUNDAMENTAL_TERMO,actualTermo,iniciarTermo,migrarTermoHoja,operarTermo,recorridoTermoHoja,rehacerTermo,relacionesTermo,volverTermo,type RecorridoTermodinamico} from './recorridoTermodinamico';
import {aplicarPoliticaDinamica} from './datosEnsamblajeTermodinamico';

type Relacion={id:string;titulo:string;latex:string;nota?:string};

/** Relaciones always present en todo volumen con materia y energía (§3.1). */
export function relacionesGenerales(rigido:boolean):Relacion[]{
  return [
    {id:'fundamental',titulo:"Fundamental relation",latex:String.raw`dU=T\,dS-P\,dV+\sum_i\mu_i\,dn_i`},
    {id:'cierre',titulo:rigido?"State closure · rigid boundary":"State closure · prescribed pressure",latex:rigido?String.raw`(\mathbf n,\,U,\,V)\ \longmapsto\ T,\;P,\;\{\beta_k,\ \mathbf x^k\}`:String.raw`(\mathbf n,\,H,\,P)\ \longmapsto\ T,\;V,\;\{\beta_k,\ \mathbf x^k\}`,nota:"Balances integrate conserved quantities; the closure determines the state at every evaluation."},
    {id:'reparto',titulo:"Distribution among candidate phases",latex:String.raw`n_i=\sum_k \beta_k\,n\,x_i^k,\qquad \sum_k\beta_k=1,\qquad \sum_i x_i^k=1`},
    {id:'propiedades',titulo:"Mixture properties",latex:String.raw`U=\sum_k n_k\,u_k,\qquad V=\sum_k n_k\,v_k,\qquad H=U+PV`},
    {id:'equilibrio',titulo:"Equilibrium between present phases",latex:String.raw`T^k=T,\qquad P^k=P,\qquad \mu_i^k=\mu_i^l`},
    {id:'estabilidad',titulo:"Stability of each candidate phase",latex:String.raw`tm_k=\min_{\mathbf w}\sum_i w_i\left[\ln w_i+\ln\varphi_i(\mathbf w)-\ln z_i-\ln\varphi_i(\mathbf z)\right]`},
    {id:'complementariedad',titulo:"Complementarity: every candidate phase remains in the equations",latex:String.raw`\beta_k\geq0,\qquad tm_k\geq0,\qquad \beta_k\,tm_k=0`,nota:"An absent phase has zero amount and tm > 0. At appearance, tm reaches zero and β grows without changing the model."},
  ];
}

/** Ecuaciones del modelo de estado según la familia del paquete. */
export function relacionesModeloEstado(v:VolumenTermodinamico):Relacion[]{
  const me=v.modeloEstado;if(!me)return [];
  if(me.familia==='iapws95')return [
    {id:'helmholtz',titulo:"Pure-substance Helmholtz energy",latex:String.raw`a(\rho,T)=a^\circ(\rho,T)+a^r(\rho,T),\qquad P=\rho^2\left(\frac{\partial a}{\partial\rho}\right)_T`},
    {id:'coexistencia',titulo:"Liquid–vapor coexistence",latex:String.raw`g^L(T,P)=g^V(T,P),\qquad P^L=P^V`}];
  const vapor={id:'vapor',titulo:'Ideal vapor',latex:String.raw`\mu_i^V=\mu_i^{\mathrm{gi}}(T,P^\circ)+RT\ln\frac{y_iP}{P^\circ},\qquad \varphi_i=1`};
  const poynting=String.raw`\exp\!\left[\frac{v_i^L\,(P-P_i^{\mathrm{sat}})}{RT}\right]`;
  if(me.familia==='ideal')return [vapor,{id:'liquido',titulo:"Ideal liquid solution (Raoult with Poynting correction)",latex:String.raw`y_i\,P=x_i\,P_i^{\mathrm{sat}}(T)\,${poynting},\qquad g^E=0`,nota:"An ideal liquid is stable against splitting into two liquids: there is one liquid candidate."}];
  const r=[vapor,{id:'liquido',titulo:"Liquid with activity coefficients",latex:String.raw`y_i\,P=x_i\,\gamma_i(T,\mathbf x)\,P_i^{\mathrm{sat}}(T)\,${poynting},\qquad \frac{g^E}{RT}=\sum_i x_i\ln\gamma_i`,nota:"A non-ideal liquid may split into two: the layer has two liquid candidates."}];
  if(me.modeloLiquido?.startsWith('unifac'))r.push({id:'unifac',titulo:`UNIFAC ${me.modeloLiquido==='unifac_dortmund'?'(Dortmund)':me.modeloLiquido==='unifac_lle'?'(LLE table)':'(original)'} · group contribution`,latex:String.raw`\ln\gamma_i=\ln\gamma_i^{C}+\ln\gamma_i^{R},\qquad \ln\gamma_i^{R}=\sum_k\nu_k^{(i)}\left(\ln\Gamma_k-\ln\Gamma_k^{(i)}\right)`});
  if(me.modeloLiquido==='nrtl')r.push({id:'nrtl',titulo:'NRTL',latex:String.raw`\frac{g^E}{RT}=\sum_i x_i\,\frac{\sum_j\tau_{ji}G_{ji}x_j}{\sum_k G_{ki}x_k}`});
  return r;
}

export type SupuestoTermodinamico={id:string;nombre:string;latex?:string;efecto:string;activoEn:string[];donde:'estado'|'energia'};
export function supuestosTermodinamicos(d:DescripcionTermodinamica|null,nombre:(id:string)=>string):SupuestoTermodinamico[]{
  const vs=d?.volumenes??[],en=(f:(v:VolumenTermodinamico)=>boolean)=>vs.filter(f).map(v=>nombre(v.id));
  const eq=(v:VolumenTermodinamico)=>v.cierre.tipo==='equilibrio';
  const pol=(v:VolumenTermodinamico)=>v.cierre.tipo==='equilibrio'?v.cierre.politica:null;
  return [
    {id:'equilibrio',nombre:"Equilibrium state with a package",efecto:"Each evaluation solves the closure with every candidate phase; phase presence is a result.",activoEn:en(eq),donde:'estado'},
    {id:'ideal',nombre:"Ideal solution",latex:String.raw`\gamma_i=1`,efecto:"No excess energy: only one liquid phase is possible. Select the ideal-mixture package.",activoEn:en(v=>v.modeloEstado?.familia==='ideal'),donde:'estado'},
    {id:'actividad',nombre:"Activity coefficients (UNIFAC)",latex:String.raw`\gamma_i(T,\mathbf x)`,efecto:"Group-contribution prediction; supports two liquid phases.",activoEn:en(v=>v.modeloEstado?.familia==='actividad'),donde:'estado'},
    {id:'vapor_ideal',nombre:'Ideal vapor',latex:String.raw`\varphi_i=1`,efecto:'Assumed by the published mixture packages within their low-pressure domain (P ≤ 5 bar).',activoEn:en(v=>v.modeloEstado?.familia==='ideal'||v.modeloEstado?.familia==='actividad'),donde:'estado'},
    {id:'incompresible',nombre:"Incompressible liquid",latex:String.raw`v_i^L=\text{cte}`,efecto:"Used in the Poynting correction; liquid volume does not depend on P.",activoEn:en(v=>v.modeloEstado?.familia==='ideal'||v.modeloEstado?.familia==='actividad'),donde:'estado'},
    {id:'monofasico',nombre:"Restrict to one phase",latex:String.raw`N_{\mathrm{fases}}=1`,efecto:"The calculation stops when equilibrium requires another phase, because the assumption is no longer valid.",activoEn:en(v=>pol(v)?.cantidad==='monofasico'),donde:'estado'},
    {id:'sin_cambio',nombre:"Forbid phase change",efecto:"The initial phase set is maintained; the calculation stops if it changes.",activoEn:en(v=>pol(v)?.cambioInterno==='prohibido'),donde:'estado'},
    {id:'u_lineal',nombre:"Linear u(T)",latex:String.raw`U=m\,u(T),\ u=u_{\mathrm{ref}}+c\,(T-T_{\mathrm{ref}})`,efecto:'Replaces the package: one phase, no phase change, constant heat capacity; the Engine monitors T_min ≤ T ≤ T_max.',activoEn:en(v=>v.cierre.tipo==='supuesto'&&v.cierre.supuesto==='u_lineal'),donde:'estado'},
    {id:'no_evaluado',nombre:"State not evaluated",efecto:"T, P and phases are not evaluated. This is valid only when the active balances do not require them.",activoEn:en(v=>v.cierre.tipo==='supuesto'&&v.cierre.supuesto==='fase_no_evaluada'),donde:'estado'},
  ];
}

function cuerpoDescripcion(h:HojaMotor){
  if(h.redTermodinamica)return {solicitudV2:h.redTermodinamica.solicitud};
  if(cabeEnBalances(h))return {modelo:modeloBalancesDesdeHoja(h)};
  return {modelo:modeloDesdeHojaMotor(h)};
}

export default function TermodinamicaHoja({h,onGuardar}:{h:HojaMotor;onVista:(v:VistaHoja)=>void;onGuardar?:(cambio:(h:HojaMotor)=>HojaMotor)=>void}){
  const firma=useMemo(()=>{try{return firmaHoja(h);}catch{return h.id;}},[h]);
  const [d,setD]=useState<DescripcionTermodinamica|null>(null),[error,setError]=useState('');
  useEffect(()=>{const ctl=new AbortController();
    (async()=>{try{const r=await describirTermodinamica(cuerpoDescripcion(h),ctl.signal);if(!ctl.signal.aborted){setD(r);setError('');}}catch(e){if(!ctl.signal.aborted){setD(null);setError((e as Error).message);}}})();
    return()=>ctl.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[firma]);
  const nombre=(vid:string)=>h.redTermodinamica?.nombres[`volumen:${vid}`]??h.ensamblaje?.volumenes.find(v=>v.id===vid)?.nombre??(vid==='dominio'?"Control volume":`Volume ${vid}`);
  const rigido=!!d?.volumenes.every(v=>v.frontera==='rigida');
  const generales=relacionesGenerales(rigido),supuestos=supuestosTermodinamicos(d,nombre);
  // Derivación editable (hojas que no son una red termodinámica): fundamentales -> supuestos declarados.
  const editable=!h.redTermodinamica&&!!onGuardar;
  const recorrido=recorridoTermoHoja(h),actual=actualTermo(recorrido).supuestos;
  const volumenId=h.ensamblaje?.volumenes[0]?.id??'dominio',cierre=h.cierresDinamicos?.[volumenId];
  const guardarTermo=(r:RecorridoTermodinamico)=>onGuardar?.(q=>({...migrarTermoHoja(q),recorridoTermodinamico:r,resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false}));
  function aplicar(op:typeof OPERACIONES_TERMO[number],activo:boolean){
    if(!onGuardar)return;
    // Con un cierre real (IAPWS-95) las fases las decide el equilibrio: una fase o sin cambio de fase son su política.
    if(cierre&&(op.clave==='monofasico'||op.clave==='sinCambioFase')){onGuardar(q=>aplicarPoliticaDinamica(q,{...cierre.politica,...(op.clave==='monofasico'?{cantidad:activo?'monofasico':'sin_restriccion'}:{cambioInterno:activo?'prohibido':'permitido'})}));return;}
    guardarTermo(operarTermo(recorrido,`${activo?'Apply':'Remove'}: ${op.nombre}`,{[op.clave]:activo?op.valor:valorRetirado(op.clave)},activo?[op.relacion]:[]));
  }
  const donde=(s:SupuestoTermodinamico,vid?:string)=>editable&&OPERACIONES_TERMO.some(o=>o.clave===(s.id==='monofasico'?'monofasico':s.id==='sin_cambio'?'sinCambioFase':s.id==='u_lineal'?'modelo':'_'))?<small>Defined in the assumptions above.</small>:<Link href={h.redTermodinamica?urlEnfoqueRed(h.id,'estado',{propietarioId:`volumen:${vid??d?.volumenes[0]?.id??''}`}):`/motor/hojas/${h.id}/estado`}>Configure in Model →</Link>;
  return <div className={styles.pagina}>
    <header className={styles.cabecera}><small>Thermodynamics · always present</small><h2>The state of each volume</h2><p>Start from fundamental thermodynamic relations. Each assumption leads to the state relation used by the model. No phase is assumed by default.</p></header>
    <ModelWorksheet family="termodinamica" label="Thermodynamic derivation" assumptions={<>
      {editable&&<><ThermodynamicAssumptions state={actual} policy={cierre?.politica} equilibrium={!!cierre} change={aplicar}/>
        <small className={styles.notaTermo}>Equilibrium package (calculated phases): <Link href={`/motor/hojas/${h.id}/estado`}>Physical system →</Link></small></>}
      <header><h2>Available assumptions</h2></header>
      {supuestos.map(s=><div key={s.id} className={styles.supuestoTermo}>
        <strong>{s.nombre}</strong>{s.latex&&<FormulaMateria latex={s.latex} lectura={s.nombre}/>}
        <small>{s.efecto}</small>
        <small>{s.activoEn.length?`Active in: ${s.activoEn.join(', ')}`:'Available'}</small>
        {donde(s)}
      </div>)}
    </>}>
      {editable&&<div className={worksheetStyles.sheetToolbar}><h3>Thermodynamic derivation</h3><button disabled={recorrido.pasos.length===1} onClick={()=>guardarTermo(volverTermo(recorrido,recorrido.pasos.length-2))}>Undo</button><button disabled={!recorrido.rehacer.length} onClick={()=>guardarTermo(rehacerTermo(recorrido))}>Redo</button><button onClick={()=>guardarTermo(iniciarTermo())}>Reset derivation</button></div>}
      <article className={worksheetStyles.equation}><header><span>01 · {TITULO_FUNDAMENTAL_TERMO}</span><span>always present</span></header>
        {generales.map(r=><div key={r.id} className={styles.relacion}><small>{r.titulo}</small><FormulaMateria latex={r.latex} lectura={r.titulo}/>{r.nota&&<small>{r.nota}</small>}</div>)}
      </article>
      {editable&&recorrido.pasos.slice(1).map((p,i)=><article key={i} className={worksheetStyles.derivationRow} aria-label={`Thermodynamic step ${i+2}: ${p.titulo}`}><div className={worksheetStyles.rowNumber}>{String(i+2).padStart(2,'0')}</div><div className={worksheetStyles.rowBody}><header><h3>{p.titulo}</h3>{i+1<recorrido.pasos.length-1&&<button onClick={()=>guardarTermo(volverTermo(recorrido,i+1))}>Continue here</button>}<button aria-label={`Remove thermodynamic step ${i+2}`} onClick={()=>guardarTermo(volverTermo(recorrido,i))}>×</button></header>{p.relaciones.map((r,j)=><div className={styles.identidadEnergia} key={j}><FormulaMateria latex={r} lectura="Applied thermodynamic assumption" bloque/></div>)}</div></article>)}
      {editable&&<div className={styles.relacionesEnergia}><h3>Active state relations</h3>{relacionesTermo(actual).length?relacionesTermo(actual).map(r=><div key={r}><FormulaMateria latex={r} lectura="State relation" bloque/></div>):<p className={styles.notaTermo}>Without assumptions, the state is obtained from package equilibrium or is not evaluated.</p>}<p className={styles.notaTermo}>The energy balance uses these relations; they are defined here.</p></div>}
      {error&&<p role="status" className={styles.notaTermo}>{error} Fundamental relations are available locally; each volume closure requires the server.</p>}
      {!d&&!error&&<p role="status" className={styles.notaTermo}>Loading the closure for each volume…</p>}
      {d?.volumenes.map(v=><article key={v.id} className={worksheetStyles.equation} aria-label={`Closure for ${nombre(v.id)}`}>
        <header><span>{nombre(v.id)} · {v.cierre.tipo==='equilibrio'?`Equilibrium with ${v.modeloEstado?.nombre??v.cierre.paquete.id}`:v.cierre.supuesto==='u_lineal'?'Assumption: linear u(T)':'Assumption: state not evaluated'}</span><span>{v.frontera==='rigida'?'Rigid boundary':v.frontera==='presion_prescrita'?'Prescribed pressure':'No mechanical relation'}</span></header>
        {v.cierre.tipo==='equilibrio'?<>
          <p className={styles.notaTermo}>Candidate phases: {v.candidatas?v.candidatas.join(' · '):`unavailable (${v.motivoCandidatas})`}. All candidates are published in every state, whether present or absent.</p>
          {relacionesModeloEstado(v).map(r=><div key={r.id} className={styles.relacion}><small>{r.titulo}</small><FormulaMateria latex={r.latex} lectura={r.titulo}/>{r.nota&&<small>{r.nota}</small>}</div>)}
          {(v.cierre.politica.cantidad==='monofasico'||v.cierre.politica.cambioInterno==='prohibido')&&<div className={styles.relacion}><small>Declared phase policy</small><FormulaMateria latex={v.cierre.politica.cantidad==='monofasico'?String.raw`N_{\mathrm{fases}}=1`:String.raw`\{\text{fases}\}=\{\text{fases}\}_{t=0}`} lectura="Phase policy"/><small>The calculation stops if this condition is violated.</small></div>}
        </>:v.cierre.supuesto==='u_lineal'?<>
          <div className={styles.relacion}><small>Assumed state relation</small><FormulaMateria latex={String.raw`U=m\,u(T),\qquad u(T)=u_{\mathrm{ref}}+c\,(T-T_{\mathrm{ref}}),\qquad N_{\mathrm{fases}}=1`} lectura="Linear u(T)"/></div>
          <div className={styles.relacion}><small>Monitored domain</small><FormulaMateria latex={String.raw`T_{\min}\leq T\leq T_{\max}`} lectura="Validity domain"/><small>The fundamental relations are replaced by this assumption: {v.cierre.motivo}.</small></div>
        </>:<p className={styles.notaTermo}>The fundamental relations are not evaluated in this volume: {v.cierre.motivo}. The active balances do not require T, P or phases. If needed, declare a package or u(T).</p>}
        <details><summary className={styles.notaTermo}>Relations assembled by the Engine</summary><ul>{v.relaciones.map(r=><li key={r.id} className={styles.notaTermo}>{r.id} · {r.descripcion}{r.supuesta?' (assumed)':''}</li>)}</ul></details>
      </article>)}
    </ModelWorksheet>
  </div>;
}
