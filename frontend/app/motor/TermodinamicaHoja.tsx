'use client';
/** Panel Termodinámica de la hoja (ARQUITECTURA_MOTOR.md §3 y §11): la termodinámica no es un balance que se
 * activa, es el cierre de estado de cada volumen y está siempre presente. Muestra, como las vistas de materia
 * y energía, las relaciones generales; después el cierre que declara cada volumen (con las fases candidatas y la
 * familia del modelo de estado que publica el servidor, POST /modelo/termodinamica) y los supuestos que se
 * pueden hacer desde la termodinámica, con su efecto, si están activos y dónde se declaran.
 * Es presentación: no evalúa ningún estado. */
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
import {OPERACIONES_TERMO,TERMO_FUNDAMENTAL,TITULO_FUNDAMENTAL_TERMO,actualTermo,iniciarTermo,migrarTermoHoja,operarTermo,recorridoTermoHoja,rehacerTermo,relacionesTermo,volverTermo,type RecorridoTermodinamico} from './recorridoTermodinamico';
import {aplicarPoliticaDinamica} from './datosEnsamblajeTermodinamico';

type Relacion={id:string;titulo:string;latex:string;nota?:string};

/** Relaciones siempre presentes en todo volumen con materia y energía (§3.1). */
export function relacionesGenerales(rigido:boolean):Relacion[]{
  return [
    {id:'fundamental',titulo:'Relación fundamental',latex:String.raw`dU=T\,dS-P\,dV+\sum_i\mu_i\,dn_i`},
    {id:'cierre',titulo:rigido?'Cierre de estado · frontera rígida':'Cierre de estado · presión impuesta',latex:rigido?String.raw`(\mathbf n,\,U,\,V)\ \longmapsto\ T,\;P,\;\{\beta_k,\ \mathbf x^k\}`:String.raw`(\mathbf n,\,H,\,P)\ \longmapsto\ T,\;V,\;\{\beta_k,\ \mathbf x^k\}`,nota:'Los balances integran solo las cantidades conservadas; el estado sale del cierre en cada evaluación.'},
    {id:'reparto',titulo:'Reparto entre las fases candidatas',latex:String.raw`n_i=\sum_k \beta_k\,n\,x_i^k,\qquad \sum_k\beta_k=1,\qquad \sum_i x_i^k=1`},
    {id:'propiedades',titulo:'Propiedades de la mezcla',latex:String.raw`U=\sum_k n_k\,u_k,\qquad V=\sum_k n_k\,v_k,\qquad H=U+PV`},
    {id:'equilibrio',titulo:'Equilibrio entre las fases presentes',latex:String.raw`T^k=T,\qquad P^k=P,\qquad \mu_i^k=\mu_i^l`},
    {id:'estabilidad',titulo:'Estabilidad de cada fase candidata',latex:String.raw`tm_k=\min_{\mathbf w}\sum_i w_i\left[\ln w_i+\ln\varphi_i(\mathbf w)-\ln z_i-\ln\varphi_i(\mathbf z)\right]`},
    {id:'complementariedad',titulo:'Complementariedad: las ecuaciones de todas las fases están siempre',latex:String.raw`\beta_k\geq0,\qquad tm_k\geq0,\qquad \beta_k\,tm_k=0`,nota:'Una fase ausente tiene cantidad cero y tm > 0: sus ecuaciones están y no arrojan nada. Al aparecer, tm llega a 0 y β empieza a crecer, sin cambiar de modelo.'},
  ];
}

/** Ecuaciones del modelo de estado según la familia del paquete. */
export function relacionesModeloEstado(v:VolumenTermodinamico):Relacion[]{
  const me=v.modeloEstado;if(!me)return [];
  if(me.familia==='iapws95')return [
    {id:'helmholtz',titulo:'Energía de Helmholtz de la sustancia pura',latex:String.raw`a(\rho,T)=a^\circ(\rho,T)+a^r(\rho,T),\qquad P=\rho^2\left(\frac{\partial a}{\partial\rho}\right)_T`},
    {id:'coexistencia',titulo:'Coexistencia líquido–vapor',latex:String.raw`g^L(T,P)=g^V(T,P),\qquad P^L=P^V`}];
  const vapor={id:'vapor',titulo:'Vapor ideal',latex:String.raw`\mu_i^V=\mu_i^{\mathrm{gi}}(T,P^\circ)+RT\ln\frac{y_iP}{P^\circ},\qquad \varphi_i=1`};
  const poynting=String.raw`\exp\!\left[\frac{v_i^L\,(P-P_i^{\mathrm{sat}})}{RT}\right]`;
  if(me.familia==='ideal')return [vapor,{id:'liquido',titulo:'Solución líquida ideal (Raoult con Poynting)',latex:String.raw`y_i\,P=x_i\,P_i^{\mathrm{sat}}(T)\,${poynting},\qquad g^E=0`,nota:'Un líquido ideal es siempre estable frente a separarse en dos: una sola fase líquida candidata.'}];
  const r=[vapor,{id:'liquido',titulo:'Líquido con coeficientes de actividad',latex:String.raw`y_i\,P=x_i\,\gamma_i(T,\mathbf x)\,P_i^{\mathrm{sat}}(T)\,${poynting},\qquad \frac{g^E}{RT}=\sum_i x_i\ln\gamma_i`,nota:'Un líquido no ideal puede separarse en dos: la capa tiene dos fases líquidas candidatas.'}];
  if(me.modeloLiquido?.startsWith('unifac'))r.push({id:'unifac',titulo:`UNIFAC ${me.modeloLiquido==='unifac_dortmund'?'(Dortmund)':me.modeloLiquido==='unifac_lle'?'(tabla ELL)':'(original)'} · contribución de grupos`,latex:String.raw`\ln\gamma_i=\ln\gamma_i^{C}+\ln\gamma_i^{R},\qquad \ln\gamma_i^{R}=\sum_k\nu_k^{(i)}\left(\ln\Gamma_k-\ln\Gamma_k^{(i)}\right)`});
  if(me.modeloLiquido==='nrtl')r.push({id:'nrtl',titulo:'NRTL',latex:String.raw`\frac{g^E}{RT}=\sum_i x_i\,\frac{\sum_j\tau_{ji}G_{ji}x_j}{\sum_k G_{ki}x_k}`});
  return r;
}

export type SupuestoTermodinamico={id:string;nombre:string;latex?:string;efecto:string;activoEn:string[];donde:'estado'|'energia'};
export function supuestosTermodinamicos(d:DescripcionTermodinamica|null,nombre:(id:string)=>string):SupuestoTermodinamico[]{
  const vs=d?.volumenes??[],en=(f:(v:VolumenTermodinamico)=>boolean)=>vs.filter(f).map(v=>nombre(v.id));
  const eq=(v:VolumenTermodinamico)=>v.cierre.tipo==='equilibrio';
  const pol=(v:VolumenTermodinamico)=>v.cierre.tipo==='equilibrio'?v.cierre.politica:null;
  return [
    {id:'equilibrio',nombre:'Estado de equilibrio con un paquete',efecto:'Cada evaluación resuelve el cierre con todas las fases candidatas; las fases son un resultado.',activoEn:en(eq),donde:'estado'},
    {id:'ideal',nombre:'Solución ideal',latex:String.raw`\gamma_i=1`,efecto:'Sin energía de exceso: un solo líquido posible. Se elige con el paquete «mezcla ideal».',activoEn:en(v=>v.modeloEstado?.familia==='ideal'),donde:'estado'},
    {id:'actividad',nombre:'Coeficientes de actividad (UNIFAC)',latex:String.raw`\gamma_i(T,\mathbf x)`,efecto:'Predicción por contribución de grupos; admite dos líquidos.',activoEn:en(v=>v.modeloEstado?.familia==='actividad'),donde:'estado'},
    {id:'vapor_ideal',nombre:'Vapor ideal',latex:String.raw`\varphi_i=1`,efecto:'Lo suponen todos los paquetes de mezcla publicados (P ≤ 5 bar).',activoEn:en(v=>v.modeloEstado?.familia==='ideal'||v.modeloEstado?.familia==='actividad'),donde:'estado'},
    {id:'incompresible',nombre:'Líquido incompresible',latex:String.raw`v_i^L=\text{cte}`,efecto:'Entra en la corrección de Poynting; el volumen líquido no depende de P.',activoEn:en(v=>v.modeloEstado?.familia==='ideal'||v.modeloEstado?.familia==='actividad'),donde:'estado'},
    {id:'monofasico',nombre:'Restringir a una fase',latex:String.raw`N_{\mathrm{fases}}=1`,efecto:'Si el equilibrio pide otra fase, el cálculo se detiene en ese instante (el supuesto dejó de valer).',activoEn:en(v=>pol(v)?.cantidad==='monofasico'),donde:'estado'},
    {id:'sin_cambio',nombre:'Prohibir cambio de fase',efecto:'El conjunto de fases inicial se mantiene; si cambia, el cálculo se detiene.',activoEn:en(v=>pol(v)?.cambioInterno==='prohibido'),donde:'estado'},
    {id:'u_lineal',nombre:'u(T) lineal',latex:String.raw`U=m\,u(T),\ u=u_{\mathrm{ref}}+c\,(T-T_{\mathrm{ref}})`,efecto:'Sustituye al paquete: una fase, sin cambio de fase, c constante; el Engine vigila T_min ≤ T ≤ T_max.',activoEn:en(v=>v.cierre.tipo==='supuesto'&&v.cierre.supuesto==='u_lineal'),donde:'estado'},
    {id:'no_evaluado',nombre:'Estado no evaluado',efecto:'El Engine no calcula T, P ni fases: válido si los balances activos no los necesitan (solo materia).',activoEn:en(v=>v.cierre.tipo==='supuesto'&&v.cierre.supuesto==='fase_no_evaluada'),donde:'estado'},
  ];
}

function cuerpoDescripcion(h:HojaMotor){
  if(h.redTermodinamica)return {solicitudV2:h.redTermodinamica.solicitud};
  if(cabeEnBalances(h))return {modelo:modeloBalancesDesdeHoja(h)};
  return {modelo:modeloDesdeHojaMotor(h)};
}

export default function TermodinamicaHoja({h,onVista,onGuardar}:{h:HojaMotor;onVista:(v:VistaHoja)=>void;onGuardar?:(cambio:(h:HojaMotor)=>HojaMotor)=>void}){
  const firma=useMemo(()=>{try{return firmaHoja(h);}catch{return h.id;}},[h]);
  const [d,setD]=useState<DescripcionTermodinamica|null>(null),[error,setError]=useState('');
  useEffect(()=>{const ctl=new AbortController();setError('');
    (async()=>{try{const r=await describirTermodinamica(cuerpoDescripcion(h),ctl.signal);if(!ctl.signal.aborted)setD(r);}catch(e){if(!ctl.signal.aborted){setD(null);setError((e as Error).message);}}})();
    return()=>ctl.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[firma]);
  const nombre=(vid:string)=>h.redTermodinamica?.nombres[`volumen:${vid}`]??h.ensamblaje?.volumenes.find(v=>v.id===vid)?.nombre??(vid==='dominio'?'Volumen de control':`Volumen ${vid}`);
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
    guardarTermo(operarTermo(recorrido,`${activo?'Aplicar':'Retirar'}: ${op.nombre}`,{[op.clave]:activo?op.valor:TERMO_FUNDAMENTAL[op.clave]},activo?[op.relacion]:[]));
  }
  const donde=(s:SupuestoTermodinamico,vid?:string)=>editable&&OPERACIONES_TERMO.some(o=>o.clave===(s.id==='monofasico'?'monofasico':s.id==='sin_cambio'?'sinCambioFase':s.id==='u_lineal'?'modelo':'_'))?<small>Se declara en las operaciones de arriba.</small>:<Link href={h.redTermodinamica?urlEnfoqueRed(h.id,'estado',{propietarioId:`volumen:${vid??d?.volumenes[0]?.id??''}`}):`/motor/hojas/${h.id}/estado`}>Declarar en Estado →</Link>;
  return <div className={styles.pagina}>
    <header className={styles.cabecera}><small>Termodinámica · siempre presente</small><h2>El estado de cada volumen</h2><p>Se parte de las relaciones termodinámicas fundamentales y, con cada supuesto, se llega a la relación de estado que usa el modelo. Ninguna fase se supone por omisión.</p></header>
    <div className={styles.layout}><section className={styles.ecuaciones} aria-label="Derivación termodinámica">
      {editable&&<div className={styles.herramientasEnergia}><h3>Derivación termodinámica</h3><button disabled={recorrido.pasos.length===1} onClick={()=>guardarTermo(volverTermo(recorrido,recorrido.pasos.length-2))}>Deshacer</button><button disabled={!recorrido.rehacer.length} onClick={()=>guardarTermo(rehacerTermo(recorrido))}>Rehacer</button><button onClick={()=>guardarTermo(iniciarTermo())}>Reiniciar derivación</button></div>}
      <article className={styles.ecuacion}><header><span>01 · {TITULO_FUNDAMENTAL_TERMO}</span><span>siempre presentes</span></header>
        {generales.map(r=><div key={r.id} className={styles.relacion}><small>{r.titulo}</small><FormulaMateria latex={r.latex} lectura={r.titulo}/>{r.nota&&<small>{r.nota}</small>}</div>)}
      </article>
      {editable&&recorrido.pasos.slice(1).map((p,i)=><article key={i} className={styles.pasoEnergia} aria-label={`Paso termodinámico ${i+2}: ${p.titulo}`}><div className={styles.numeroEnergia}>{String(i+2).padStart(2,'0')}</div><div><header><h3>{p.titulo}</h3>{i+1<recorrido.pasos.length-1&&<button onClick={()=>guardarTermo(volverTermo(recorrido,i+1))}>Continuar aquí</button>}<button aria-label={`Eliminar paso termodinámico ${i+2}`} onClick={()=>guardarTermo(volverTermo(recorrido,i))}>×</button></header>{p.relaciones.map((r,j)=><div className={styles.identidadEnergia} key={j}><FormulaMateria latex={r} lectura="Supuesto termodinámico aplicado" bloque/></div>)}</div></article>)}
      {editable&&<div className={styles.relacionesEnergia}><h3>Relaciones de estado vigentes</h3>{relacionesTermo(actual).length?relacionesTermo(actual).map(r=><div key={r}><FormulaMateria latex={r} lectura="Relación de estado" bloque/></div>):<p className={styles.notaTermo}>Sin supuestos: el estado sale del equilibrio con un paquete (Estado) o no se evalúa.</p>}<p className={styles.notaTermo}>El balance de energía usa estas relaciones; no se declaran allí.</p></div>}
      {error&&<p role="status" className={styles.notaTermo}>{error} Las relaciones fundamentales no dependen del servidor; el cierre de cada volumen sí.</p>}
      {!d&&!error&&<p role="status" className={styles.notaTermo}>Consultando el cierre de cada volumen…</p>}
      {d?.volumenes.map(v=><article key={v.id} className={styles.ecuacion} aria-label={`Cierre de ${nombre(v.id)}`}>
        <header><span>{nombre(v.id)} · {v.cierre.tipo==='equilibrio'?`equilibrio con ${v.modeloEstado?.nombre??v.cierre.paquete.id}`:v.cierre.supuesto==='u_lineal'?'supuesto: u(T) lineal':'supuesto: estado no evaluado'}</span><span>{v.frontera==='rigida'?'frontera rígida':v.frontera==='presion_prescrita'?'presión impuesta':'sin relación mecánica'}</span></header>
        {v.cierre.tipo==='equilibrio'?<>
          <p className={styles.notaTermo}>Fases candidatas: {v.candidatas?v.candidatas.join(' · '):`no disponibles (${v.motivoCandidatas})`}. Se publican todas en cada estado, presentes o no.</p>
          {relacionesModeloEstado(v).map(r=><div key={r.id} className={styles.relacion}><small>{r.titulo}</small><FormulaMateria latex={r.latex} lectura={r.titulo}/>{r.nota&&<small>{r.nota}</small>}</div>)}
          {(v.cierre.politica.cantidad==='monofasico'||v.cierre.politica.cambioInterno==='prohibido')&&<div className={styles.relacion}><small>Política de fases declarada</small><FormulaMateria latex={v.cierre.politica.cantidad==='monofasico'?String.raw`N_{\mathrm{fases}}=1`:String.raw`\{\text{fases}\}=\{\text{fases}\}_{t=0}`} lectura="Política de fases"/><small>Si se incumple, el cálculo se detiene.</small></div>}
        </>:v.cierre.supuesto==='u_lineal'?<>
          <div className={styles.relacion}><small>Relación de estado supuesta</small><FormulaMateria latex={String.raw`U=m\,u(T),\qquad u(T)=u_{\mathrm{ref}}+c\,(T-T_{\mathrm{ref}}),\qquad N_{\mathrm{fases}}=1`} lectura="u(T) lineal"/></div>
          <div className={styles.relacion}><small>Dominio vigilado</small><FormulaMateria latex={String.raw`T_{\min}\leq T\leq T_{\max}`} lectura="Dominio de validez"/><small>Las relaciones fundamentales se sustituyen por este supuesto: {v.cierre.motivo}.</small></div>
        </>:<p className={styles.notaTermo}>Las relaciones fundamentales no se evalúan en este volumen: {v.cierre.motivo}. Los balances activos no necesitan T, P ni fases; si los necesitaran, declara un paquete o u(T).</p>}
        <details><summary className={styles.notaTermo}>Relaciones que ensambla el Engine</summary><ul>{v.relaciones.map(r=><li key={r.id} className={styles.notaTermo}>{r.id} · {r.descripcion}{r.supuesta?' (supuesta)':''}</li>)}</ul></details>
      </article>)}
    </section>
    <aside className={styles.supuestos} aria-label="Supuestos termodinámicos">
      {editable&&<><header><h2>Operaciones</h2></header>
        {OPERACIONES_TERMO.map(op=>{const activo=op.clave==='modelo'?actual.modelo==='u_lineal':!!actual[op.clave];const bloqueado=!!cierre&&(op.clave==='modelo'||op.clave==='densidadConstante');const valor=cierre&&op.clave==='monofasico'?cierre.politica.cantidad==='monofasico':cierre&&op.clave==='sinCambioFase'?cierre.politica.cambioInterno==='prohibido':activo;
          return <label key={op.clave}><input type="checkbox" aria-label={op.nombre} checked={valor} disabled={bloqueado} onChange={e=>aplicar(op,e.target.checked)}/><span>{op.nombre}<small>{bloqueado?'El cierre real (Estado) calcula esta relación.':op.efecto}</small>{valor&&<small><FormulaMateria latex={op.relacion} lectura={op.nombre}/></small>}</span></label>;})}
        <small className={styles.notaTermo}>Equilibrio con un paquete (fases calculadas): <Link href={`/motor/hojas/${h.id}/estado`}>Estado →</Link></small></>}
      <header><h2>Supuestos posibles</h2></header>
      {supuestos.map(s=><div key={s.id} className={styles.supuestoTermo}>
        <strong>{s.nombre}</strong>{s.latex&&<FormulaMateria latex={s.latex} lectura={s.nombre}/>}
        <small>{s.efecto}</small>
        <small>{s.activoEn.length?`Activo en: ${s.activoEn.join(', ')}`:'Disponible'}</small>
        {donde(s)}
      </div>)}
    </aside></div>
  </div>;
}
