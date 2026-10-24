'use client';
import { englishLabel } from '../models/english';
import CompilationSummary from '../models/CompilationSummary';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {useHojasMotor} from './useHojasMotor';
import {guardarHoja} from './hojasMotor';
import {leerResultadoMotor} from './resultadosMotor';
import {firmaHoja,formulacionHoja} from './modeloHojaMotor';
import type {ResultadoMotor} from './modeloNumerico';
import {datosGraficasMotor} from './datosGraficasMotor';
import {nombreUnidad} from './unidadesMotor';
import {formatearNumeroMotor} from './formatearNumeroMotor';
import TableroMotor from './TableroMotor';
import NavegacionHoja from './NavegacionHoja';
import styles from './trabajoMotor.module.css';
import {validarResultadoDinamico,mensajeResultadoDinamico} from './resultadoEnsamblaje';
import DetallesEnsamblaje from './DetallesEnsamblaje';
import DetallesRedTermodinamica from './DetallesRedTermodinamica';
import EquilibrioHoja from './EquilibrioHoja';
import AvisoCertificacionRed from './AvisoCertificacionRed';
import {validarResultadoV2} from './resultadoEnsamblajeV2';
const num=formatearNumeroMotor;
export default function ResultadosHoja({id}:{id:string}){
  const hojas=useHojasMotor(),h=hojas.find(h=>h.id===id),[resultado,setResultado]=useState<ResultadoMotor|undefined>(),[error,setError]=useState(''),[vista,setVista]=useState<'graficas'|'tabla'|'tecnico'|'equilibrio'>('graficas'),[equilibrioAbierto,setEquilibrioAbierto]=useState(false);
  const ref=h?.resultadoRef?.firma;
  useEffect(()=>{let vigente=true;if(ref)leerResultadoMotor(id,ref).then(r=>{if(r){validarResultadoDinamico(r);validarResultadoV2(r);}if(vigente){setResultado(r);if(!r)setError("The saved result is unavailable. Run the model again.");}}).catch(e=>{if(vigente){setResultado(undefined);setError((e as Error).message);}});return()=>{vigente=false;};},[id,ref]);
  if(!h)return <div className={styles.empty}><h1>Open a model</h1><Link href="/motor/hojas">Browse models</Link></div>;
  const f=formulacionHoja(h),r=resultado??h.resultado;
  if(!ref&&!h.resultado||ref&&ref!==firmaHoja(h)||r&&r.firma!==firmaHoja(h))return <div className={styles.page}><NavegacionHoja id={id} actual="resultados"/><div className={styles.empty}><h1>No current results</h1><Link href={`/motor/hojas/${id}/resolver`} className={styles.primary}>Complete data and solve</Link></div></div>;
  if(!r)return <div className={styles.page}><NavegacionHoja id={id} actual="resultados"/>{error?<div role="alert" className={styles.error}>{error}<Link href={`/motor/hojas/${id}/resolver`}>Return to Solve</Link></div>:<div className={styles.empty}>Loading results…</div>}</div>;
  const datos=datosGraficasMotor(h,r,'tiempo'),columnas=datos.variables.filter(v=>!!r.seriesEvaluadas||v.id==='t'||v.id.startsWith('m_')||v.id.startsWith('rho_')||v.id.startsWith('prom_')||v.id.startsWith('carga_')||v.id==='V');
  function exportar(){if(!r)return;let csv='';if(r.modo==='1d'){csv='t [s],x [m],componente,rho [kg/m3]\n';r.tiempos.forEach((t,k)=>r.x.forEach((x,j)=>r.componentes.forEach((s,i)=>{csv+=`${t},${x},"${s.nombre.replaceAll('"','""')}",${r.valores[k][i][j]}\n`;})));}else{csv=columnas.map(v=>`"${v.nombre.replaceAll('"','""')} [${nombreUnidad(v.unidad)}]"`).join(',')+'\n'+datos.filas.map(f=>columnas.map(v=>Number.isFinite(f[v.id])?f[v.id]:'').join(',')).join('\n');}const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='resultado-motor.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <div className={`${styles.page} ${styles.resultsPage}`}><NavegacionHoja id={id} actual="resultados"/><header className={styles.heading}><div><span className={styles.eyebrow}>{h.nombre} · {r.modo==='1d'?"1D + time":"Time only"}</span><h1>Results</h1></div><button onClick={exportar}>Download CSV</button></header>{r.estado==='parcial'&&<div className={styles.error} role="status">{r.ensamblajeV2?r.mensaje:r.ensamblajeTermodinamico?mensajeResultadoDinamico(r.ensamblajeTermodinamico.respuesta):r.mensaje} · t = {num(r.tiempos.at(-1)!)} s</div>}{r.ensamblajeV2?.respuesta.resultados&&<AvisoCertificacionRed resultado={r.ensamblajeV2.respuesta.resultados} verDetalles={()=>setVista('tecnico')}/>}{error&&<div role="alert" className={styles.error}>{error}<button onClick={()=>setError('')}>Close</button></div>}<nav className={styles.tabs}><button aria-pressed={vista==='graficas'} onClick={()=>setVista('graficas')}>Charts</button><button aria-pressed={vista==='tabla'} onClick={()=>setVista('tabla')}>Table</button>{r.ensamblajeV2&&<button aria-pressed={vista==='equilibrio'} onClick={()=>{setEquilibrioAbierto(true);setVista('equilibrio');}}>Equilibrium</button>}<button aria-pressed={vista==='tecnico'} onClick={()=>setVista('tecnico')}>Numerical diagnostics</button></nav>
    {r.compilation&&<details className={styles.settings}><summary>Executed formulation and solution strategy</summary><CompilationSummary report={r.compilation}/></details>}
    {vista==='graficas'&&<TableroMotor h={h} r={r} guardar={(graficas,columnas)=>{try{guardarHoja({...h,graficas,columnas,tableroIniciado:true});return true;}catch{setError("The chart layout could not be saved.");return false;}}}/>}
    {vista==='tabla'&&<div className={styles.tableWrap}><table><thead><tr>{columnas.map(v=><th key={v.id}>{englishLabel(v.nombre)} [{nombreUnidad(v.unidad)}]</th>)}</tr></thead><tbody>{datos.filas.map((fila,i)=><tr key={i}>{columnas.map(v=><td key={v.id}>{num(fila[v.id])}</td>)}</tr>)}</tbody></table>{r.modo==='1d'&&<small className={styles.muted}>The CSV contains the complete profiles for every cell.</small>}</div>}
    {equilibrioAbierto&&r.ensamblajeV2&&<div hidden={vista!=='equilibrio'}><EquilibrioHoja h={h} r={r} guardar={vistaEquilibrio=>{try{guardarHoja({...h,vistaEquilibrio});}catch{setError('No se pudo guardar la vista de equilibrio.');}}}/></div>}
    {vista==='tecnico'&&r.ensamblajeV2&&<DetallesRedTermodinamica r={r}/>}
    {vista==='tecnico'&&r.ensamblajeTermodinamico&&<DetallesEnsamblaje r={r}/>}
    {vista==='tecnico'&&!r.ensamblajeV2&&!r.ensamblajeTermodinamico&&<div className={styles.variables}><h2>Method</h2><p>{r.metodo}</p><p>{r.pasos} accepted steps · {r.rechazados} rejected · {r.tiempos.length} samples</p>{r.modo==='1d'&&<p>{r.x.length} cells · {r.x.length*r.componentes.length} discrete states · quantities per unit area</p>}{r.verificationChecks&&<><h2>Published numerical checks</h2><p>Dimensionless residuals; energy and equilibrium certification require their own physical models.</p>{r.verificationChecks.map(check=><p key={check.id}>{check.descripcion}: {check.valor.toExponential(3)} / tolerance {check.tolerancia.toExponential(3)} · {check.valor<=check.tolerancia?'Passed':'Failed'}</p>)}</>}<h2>Integrated balance residuals</h2>{r.conservacion.map((v,i)=><p key={i}>{r.variablesNumericas?.[i]?.magnitud==='energia'?"U · internal energy":r.componentes[i]?.nombre??r.variablesNumericas?.[i]?.id}: {v.toExponential(3)} {r.modo==='1d'?'kg/m²':nombreUnidad(r.variablesNumericas?.[i]?.unidad??r.unidadEstado)}</p>)}{r.conservacionGlobal&&<><h2>Global balance · external streams and sources</h2>{r.conservacionGlobal.map(q=><p key={q.id}>{q.nombre}: {q.residuo.toExponential(3)} kg</p>)}</>}{r.trazabilidadEnergia&&<><h2>Executed energy assembly</h2><pre style={{whiteSpace:'pre-wrap',fontSize:11}}>{JSON.stringify(r.trazabilidadEnergia,null,2)}</pre></>}<details className={styles.settings}><summary>Data and formulation used</summary><pre style={{whiteSpace:'pre-wrap',fontSize:11}}>{JSON.stringify({formulacion:f,ensamblaje:h.ensamblaje,configuracion:h.config,energia:h.energia},null,2)}</pre></details></div>}
  </div>;
}
