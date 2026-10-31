'use client';
import DerivedSolve from '../models/DerivedSolve';
import { englishLabel } from '../models/english';
import { selectedTransformedModel } from '../models/transformationSelection';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import {useEffect,useRef,useState} from 'react';
import {useHojasMotor} from './useHojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import {necesitaCierre,esVolumetrico} from './modeloNumerico';
import {guardarResultadoMotor,saveRejectedAttempt} from './resultadosMotor';
import AssessmentText from '../models/AssessmentText';
import type {CampoDato,ConfiguracionMotor,DatoMotor} from './modeloNumerico';
import {actualizarConfiguracionEnergia,historialEnergiaHoja,formulacionEnergiaHoja} from './estadoEnergiaHoja';
import {balancesHoja} from './seleccionBalances';
import {FAMILIAS_BALANCE} from './familiasBalance';
import {formulacionHoja,analizarHoja,compilarHoja,firmaHoja,configuracionHoja} from './modeloHojaMotor';
import {resolverHojaEngine,resuelveEngineComun} from './resolverEngine';
import {actualizarDatosEnsamblaje} from './ensamblajeMateria';
import {nombreUnidad,UNIDADES_MOTOR} from './unidadesMotor';
import FormulaMateria from './FormulaMateria';
import EcuacionesFinales from './EcuacionesFinales';
import {papelCampo} from './papelesVariables';
import NavegacionHoja from './NavegacionHoja';
import styles from './trabajoMotor.module.css';
import ResolverEnsamblaje from './ResolverEnsamblaje';
import EspacioRedTermodinamica from './EspacioRedTermodinamica';
import type {EnfoqueRed} from './destinoDiagnosticoRed';
import {usaEnsamblajeTermodinamico} from './datosEnsamblajeTermodinamico';
import HydraulicSolve from '../models/HydraulicSolve';

function Entrada({id,dato,unidades,cambiar,nombre}:{id:string;dato:DatoMotor;unidades:string[];cambiar:(d:DatoMotor)=>void;nombre:string}){return <div className={styles.entry}><input id={id} aria-label={nombre} value={dato.texto} onChange={e=>cambiar({...dato,texto:e.target.value})} placeholder="Value or expression" autoComplete="off"/><select aria-label={`Unit for ${nombre}`} value={dato.unidad} onChange={e=>cambiar({...dato,unidad:e.target.value})}>{unidades.map(u=><option key={u} value={u}>{nombreUnidad(u)}</option>)}</select></div>;}
export default function ResolverHoja({id,enfoque}:{id:string;enfoque?:EnfoqueRed}) {
  const router=useRouter();
  const hojas=useHojasMotor(),hoja=hojas.find(h=>h.id===id),[error,setError]=useState(''),[typedFailure,setTypedFailure]=useState<{signature:string;error:Error}|null>(null),[ejecutando,setEjecutando]=useState(false),[progreso,setProgreso]=useState(0),controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  if(!hoja)return <div className={styles.empty}><h1>Open a model</h1><Link href="/motor/hojas">Browse models</Link></div>;
  if(hoja.commonModel)return <DerivedSolve model={hoja}/>;
  if(hoja.hydraulicNetwork)return <HydraulicSolve model={hoja}/>;
  if(hoja.transformation&&(hoja.redTermodinamica||usaEnsamblajeTermodinamico(hoja)))return <div role="alert">The selected transformation does not support this thermodynamic execution path. <Link href={`/models/${id}/transform`}>Review the selection in Transform</Link></div>;
  if(hoja.redTermodinamica)return <EspacioRedTermodinamica h={hoja} enfoque={enfoque} vista="resolver"/>;
  if(usaEnsamblajeTermodinamico(hoja))return <ResolverEnsamblaje h={hoja}/>;
  const h=hoja,b=balancesHoja(h),f=formulacionHoja(h),c=configuracionHoja(h),a=analizarHoja(h),grupos=[...new Set(a.campos.map(x=>x.grupo))];
  let inicialError='';if(a.listo)try{if(h.transformation)selectedTransformedModel(h);compilarHoja(h);}catch(e){inicialError=(e as Error).message;}
  function cambiar(config:ConfiguracionMotor){controller.current?.abort();try{guardarHoja(b.energia?actualizarConfiguracionEnergia(h,config):{...h,...(h.ensamblaje?actualizarDatosEnsamblaje(h.ensamblaje,config):{config}),resultado:undefined,resultadoRef:undefined});setError('');setTypedFailure(null);}catch{setError("The configuration could not be saved.");}}
  function dato(campo:CampoDato,d:DatoMotor){cambiar({...c,datos:{...c.datos,[campo.id]:d}});}
  function pendiente(){const primero=a.pendientes[0]??Object.keys(a.errores)[0];document.getElementById(primero==='tiempo'?'tiempo':`dato-${primero}`)?.focus();}
  async function resolver(){setEjecutando(true);setError('');setTypedFailure(null);setProgreso(0);const ctl=new AbortController();controller.current=ctl;try{const resultado=await resolverHojaEngine(h,{signal:ctl.signal,progreso:setProgreso});if(ctl.signal.aborted)return;const actual=leerHojas().find(h=>h.id===id);if(!actual||firmaHoja(actual)!==resultado.firma)throw new Error("The model changed during calculation. The outdated result was discarded.");await guardarResultadoMotor(id,resultado,ctl.signal);const ultima=leerHojas().find(h=>h.id===id);if(!ultima||firmaHoja(ultima)!==resultado.firma)throw new Error("The model changed while saving. The result was discarded.");guardarHoja({...ultima,resultado:undefined,resultadoRef:{firma:resultado.firma,estado:resultado.estado,fecha:new Date().toISOString()}});router.push(`/motor/hojas/${id}/resultados`);}catch(e){if(!ctl.signal.aborted&&leerHojas().some(item=>item.id===id&&firmaHoja(item)===firmaHoja(h))){setError((e as Error).message);setTypedFailure({signature:firmaHoja(h),error:e as Error});try{await saveRejectedAttempt(id,firmaHoja(h),e,ctl.signal);}catch(storageError){if(!ctl.signal.aborted)setError((e as Error).message+' '+(storageError as Error).message);}}}finally{setEjecutando(false);controller.current=null;}}
  return <div className={styles.page}><NavegacionHoja id={id} actual="resolver"/><header className={styles.heading}><div><span className={styles.eyebrow}>{h.nombre}</span><h1>Solve model</h1></div><span className={styles.eyebrow}>{FAMILIAS_BALANCE.filter(f=>balancesHoja(h)[f.id]).map(f=>f.nombre).join(' + ')||"No active balances"} · {h.ensamblaje?`${h.ensamblaje.volumenes.length} volumes · ${h.ensamblaje.corrientes.length} streams`:a.modo==='1d'?"1D + time":a.modo==='temporal'?"Time only":"Incomplete formulation"}</span></header>
    {a.bloqueos.length>0&&<div className={styles.error} role="alert"><span>{englishLabel(a.bloqueos[0])}</span><Link href={`/motor/hojas/${id}`}>Review Model →</Link></div>}
    {error&&(!typedFailure||typedFailure.signature===firmaHoja(h))&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Close</button></div>}
    {typedFailure?.signature===firmaHoja(h)&&<><AssessmentText error={typedFailure.error}/><Link href={`/models/${id}/results`}>Review rejected attempt in Results</Link></>}
    {inicialError&&<div className={styles.error} role="alert">{inicialError}</div>}
    <div className={styles.solveLayout}><section>
      <EcuacionesFinales hoja={h}/>
      {a.modo==='1d'&&<section id="dato-frontera" tabIndex={-1}><h2 style={{fontSize:14,fontWeight:500}}>Boundary conditions</h2><div className={styles.boundaries}>{([['periodica',"Periodic"],['valores',"Inlet / diffusion"],['sin_flujo',"No flux"]] as const).map(([tipo,nombre])=><button key={tipo} aria-pressed={c.frontera===tipo} onClick={()=>cambiar({...c,frontera:tipo})}>{nombre}</button>)}</div></section>}
      {!h.ensamblaje&&necesitaCierre(f)&&<section id="dato-cierre" tabIndex={-1}><h2 style={{fontSize:14,fontWeight:500}}>Choose the prescribed closure function</h2><div className={styles.boundaries}><button aria-pressed={c.cierre==='densidad'} onClick={()=>cambiar({...c,cierre:'densidad'})}>Density ρ(t)</button><button aria-pressed={c.cierre==='volumen'} onClick={()=>cambiar({...c,cierre:'volumen'})}>Volume V(t)</button></div></section>}
      {b.energia&&formulacionEnergiaHoja(h).modelo==='u_lineal'&&<section><h2 style={{fontSize:14,fontWeight:500}}>Initial energy condition</h2><div className={styles.boundaries}>{(['T','U'] as const).map(inicial=><button key={inicial} aria-pressed={(h.energia?.inicial??'T')===inicial} onClick={()=>{controller.current?.abort();guardarHoja({...h,energia:{...h.energia,historial:historialEnergiaHoja(h),datos:h.energia?.datos??{},inicial},resultado:undefined,resultadoRef:undefined});}}>{inicial}(0) as data</button>)}</div></section>}
      <div className={styles.variables}>{grupos.map(grupo=><section key={grupo}><h2>{englishLabel(grupo)}</h2>{a.campos.filter(x=>x.grupo===grupo).map(campo=><div className={styles.field} key={campo.id}><FormulaMateria latex={campo.simbolo} lectura={campo.simbolo}/><label htmlFor={`dato-${campo.id}`}>{englishLabel(campo.nombre)}<small className={styles.fieldRole}>{englishLabel(papelCampo(campo))}</small></label><Entrada id={`dato-${campo.id}`} nombre={`${englishLabel(campo.nombre)} · ${englishLabel(grupo)}`} dato={c.datos[campo.id]??{texto:'',unidad:Object.keys(UNIDADES_MOTOR[campo.magnitud])[0]}} unidades={Object.keys(UNIDADES_MOTOR[campo.magnitud])} cambiar={d=>dato(campo,d)}/>{a.errores[campo.id]&&<span className={styles.fieldError}>{englishLabel(a.errores[campo.id])}</span>}</div>)}</section>)}</div>
    </section><aside className={styles.solveAside}>
      <div className={styles.counts}><div><span>{a.modo==='1d'?"Functions / balances":"Variables / equations"}</span><strong>{a.bloqueos.length?'—':`${a.variables} / ${a.ecuaciones}`}</strong></div><div><span>Structural DOF</span><strong>{a.bloqueos.length||a.modo==='1d'&&!c.frontera?'—':a.gl}</strong></div><div><span>Specified data</span><strong>{a.definidas} / {a.totalDatos}</strong></div><div><span>Initial conditions</span><strong>{a.totalIniciales-a.inicialesPendientes} / {a.totalIniciales}</strong></div></div>
      <label htmlFor="tiempo">Final time</label><Entrada id="tiempo" nombre="Final time" dato={c.tiempo} unidades={Object.keys(UNIDADES_MOTOR.tiempo)} cambiar={tiempo=>cambiar({...c,tiempo})}/>{a.errores.tiempo&&<span className={styles.fieldError}>{englishLabel(a.errores.tiempo)}</span>}
      <button className={styles.primary} disabled={!a.listo||!!inicialError||ejecutando} onClick={resolver}>{ejecutando?"Solving…":"Run model"}</button>
      <p className={styles.eyebrow} aria-live="polite">{resuelveEngineComun(h)?"Runs the shared Python compiler and solver on the server.":"This formulation currently uses the existing browser solver. Migration to the shared Python path is pending."}</p>
      {ejecutando?<><div className={styles.progress}><span style={{width:`${progreso*100}%`}}/></div><button className={styles.pending} onClick={()=>controller.current?.abort()}>Cancel calculation</button></>:!a.listo&&!a.bloqueos.length&&<button className={styles.pending} onClick={pendiente}>Go to the next missing datum →</button>}
      <details className={styles.settings}><summary>Numerical settings</summary><label>Method<select value={c.metodo} onChange={e=>cambiar({...c,metodo:e.target.value as ConfiguracionMotor['metodo']})}><option value="rk45">{a.modo==='1d'?"Finite volumes + RK45":"Adaptive RK45"}</option>{a.modo!=='1d'&&<option value="euler_implicito">{resuelveEngineComun(h)?"Adaptive implicit BDF":"Adaptive implicit Euler"}</option>}</select></label>{a.modo==='1d'&&<p>{c.celdas} finite-volume cells · <Link href={`/models/${id}/transform`}>Edit mesh in Transform →</Link></p>}<label>Samples<input aria-label="Samples" type="number" min={2} max={201} value={c.muestras} onChange={e=>cambiar({...c,muestras:Number(e.target.value)})}/></label>{b.energia&&<label>Absolute tolerance for U [J]<input type="number" aria-label="Absolute energy tolerance" value={h.energia?.atol??1e-6} onChange={e=>guardarHoja({...h,energia:{...h.energia,historial:historialEnergiaHoja(h),datos:h.energia?.datos??{},atol:Number(e.target.value)},resultado:undefined,resultadoRef:undefined})}/></label>}<label>Relative tolerance<input type="number" aria-label="Relative tolerance" value={c.rtol} onChange={e=>cambiar({...c,rtol:Number(e.target.value)})}/></label>{b.materia&&<label>Absolute tolerance [{h.ensamblaje?'kg':a.modo==='1d'||f.vista==='campo'?'kg/m³':esVolumetrico(f)?'m³':'kg'}]<input type="number" aria-label="Absolute tolerance" value={c.atol} onChange={e=>cambiar({...c,atol:Number(e.target.value)})}/></label>}{Object.entries(a.errores).filter(([k])=>['celdas','muestras','tolerancias','metodo','frontera','cierre'].includes(k)).map(([k,v])=><p key={k}>{englishLabel(v)}</p>)}<p>Expressions: t in s, the active coordinate in m, m in kg, rho in kg/m³ and V in m³. The selected unit applies to the result. Examples: 0, 2 + t, exp(-t/10). Operators + − * / ^; sin, cos, exp, log, sqrt, abs, min, max, step.</p><p>In assemblies, m_A_v1 is the mass of A in v1; m_total_v1 sums its components. V_v1 and rho_A_v1 require V to be declared as a datum in that volume. Each shared stream is specified once.</p><p>Components: {f.componentes?.map(s=>`${s.nombre} = m_${s.simbolo} / rho_${s.simbolo}`).join('; ')}. Aliases: m_total and rho_total. Each field accepts only the variables available in its equation.</p><p>Total flows are oriented: a negative value reverses the direction. Generation and consumption are non-negative gross rates.</p><p>Structural DOF counts unspecified data functions. Initial conditions and the time horizon are checked separately; this is not the numerical rank of a PDE.</p><p>This path solves time-dependent matter balances and Cartesian 1D models on a fixed mesh. Energy supports one volume and one species with a declared u(T) relation; 2D, 3D, spatial energy, multicomponent energy, momentum and inverse problems remain pending on this path. Internal dimensions of free expressions are not yet certified.</p></details>
    </aside></div>
  </div>;
}
