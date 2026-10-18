'use client';
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
  useEffect(()=>{let vigente=true;if(ref)leerResultadoMotor(id,ref).then(r=>{if(r){validarResultadoDinamico(r);validarResultadoV2(r);}if(vigente){setResultado(r);if(!r)setError('El resultado guardado no está disponible. Vuelve a resolver la hoja.');}}).catch(e=>{if(vigente){setResultado(undefined);setError((e as Error).message);}});return()=>{vigente=false;};},[id,ref]);
  if(!h)return <div className={styles.empty}><h1>Abrir una hoja</h1><Link href="/motor/hojas">Ver mis hojas</Link></div>;
  const f=formulacionHoja(h),r=resultado??h.resultado;
  if(!ref&&!h.resultado||ref&&ref!==firmaHoja(h)||r&&r.firma!==firmaHoja(h))return <div className={styles.page}><NavegacionHoja id={id} actual="resultados"/><div className={styles.empty}><h1>Sin resultados actuales</h1><Link href={`/motor/hojas/${id}/resolver`} className={styles.primary}>Completar y resolver</Link></div></div>;
  if(!r)return <div className={styles.page}><NavegacionHoja id={id} actual="resultados"/>{error?<div role="alert" className={styles.error}>{error}<Link href={`/motor/hojas/${id}/resolver`}>Volver a Resolver</Link></div>:<div className={styles.empty}>Cargando resultados…</div>}</div>;
  const datos=datosGraficasMotor(h,r,'tiempo'),columnas=datos.variables.filter(v=>!!r.seriesEvaluadas||v.id==='t'||v.id.startsWith('m_')||v.id.startsWith('rho_')||v.id.startsWith('prom_')||v.id.startsWith('carga_')||v.id==='V');
  function exportar(){if(!r)return;let csv='';if(r.modo==='1d'){csv='t [s],x [m],componente,rho [kg/m3]\n';r.tiempos.forEach((t,k)=>r.x.forEach((x,j)=>r.componentes.forEach((s,i)=>{csv+=`${t},${x},"${s.nombre.replaceAll('"','""')}",${r.valores[k][i][j]}\n`;})));}else{csv=columnas.map(v=>`"${v.nombre.replaceAll('"','""')} [${nombreUnidad(v.unidad)}]"`).join(',')+'\n'+datos.filas.map(f=>columnas.map(v=>Number.isFinite(f[v.id])?f[v.id]:'').join(',')).join('\n');}const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='resultado-motor.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <div className={`${styles.page} ${styles.resultsPage}`}><NavegacionHoja id={id} actual="resultados"/><header className={styles.heading}><div><span className={styles.eyebrow}>{h.nombre} · {r.modo==='1d'?'1D + tiempo':'Solo tiempo'}</span><h1>Resultados</h1></div><button onClick={exportar}>Descargar datos CSV</button></header>{r.estado==='parcial'&&<div className={styles.error} role="status">{r.ensamblajeV2?r.mensaje:r.ensamblajeTermodinamico?mensajeResultadoDinamico(r.ensamblajeTermodinamico.respuesta):r.mensaje} · t = {num(r.tiempos.at(-1)!)} s</div>}{r.ensamblajeV2?.respuesta.resultados&&<AvisoCertificacionRed resultado={r.ensamblajeV2.respuesta.resultados} verDetalles={()=>setVista('tecnico')}/>}{error&&<div role="alert" className={styles.error}>{error}<button onClick={()=>setError('')}>Cerrar</button></div>}<nav className={styles.tabs}><button aria-pressed={vista==='graficas'} onClick={()=>setVista('graficas')}>Gráficos</button><button aria-pressed={vista==='tabla'} onClick={()=>setVista('tabla')}>Tabla</button>{r.ensamblajeV2&&<button aria-pressed={vista==='equilibrio'} onClick={()=>{setEquilibrioAbierto(true);setVista('equilibrio');}}>Equilibrio</button>}<button aria-pressed={vista==='tecnico'} onClick={()=>setVista('tecnico')}>Detalles técnicos</button></nav>
    {vista==='graficas'&&<TableroMotor h={h} r={r} guardar={(graficas,columnas)=>{try{guardarHoja({...h,graficas,columnas,tableroIniciado:true});}catch{setError('No se pudo guardar el tablero.');}}}/>}
    {vista==='tabla'&&<div className={styles.tableWrap}><table><thead><tr>{columnas.map(v=><th key={v.id}>{v.nombre} [{nombreUnidad(v.unidad)}]</th>)}</tr></thead><tbody>{datos.filas.map((fila,i)=><tr key={i}>{columnas.map(v=><td key={v.id}>{num(fila[v.id])}</td>)}</tr>)}</tbody></table>{r.modo==='1d'&&<small className={styles.muted}>Los perfiles completos por celda están en el CSV.</small>}</div>}
    {equilibrioAbierto&&r.ensamblajeV2&&<div hidden={vista!=='equilibrio'}><EquilibrioHoja h={h} r={r} guardar={vistaEquilibrio=>{try{guardarHoja({...h,vistaEquilibrio});}catch{setError('No se pudo guardar la vista de equilibrio.');}}}/></div>}
    {vista==='tecnico'&&r.ensamblajeV2&&<DetallesRedTermodinamica r={r}/>}
    {vista==='tecnico'&&r.ensamblajeTermodinamico&&<DetallesEnsamblaje r={r}/>}
    {vista==='tecnico'&&!r.ensamblajeV2&&!r.ensamblajeTermodinamico&&<div className={styles.variables}><h2>Método</h2><p>{r.metodo}</p><p>{r.pasos} pasos aceptados · {r.rechazados} rechazados · {r.tiempos.length} muestras</p>{r.modo==='1d'&&<p>{r.x.length} celdas · {r.x.length*r.componentes.length} estados discretos · cantidades por unidad de área</p>}<h2>Cierre del presupuesto integrado</h2>{r.conservacion.map((v,i)=><p key={i}>{r.variablesNumericas?.[i]?.magnitud==='energia'?'U · energía interna':r.componentes[i]?.nombre??r.variablesNumericas?.[i]?.id}: {v.toExponential(3)} {r.modo==='1d'?'kg/m²':nombreUnidad(r.variablesNumericas?.[i]?.unidad??r.unidadEstado)}</p>)}{r.conservacionGlobal&&<><h2>Presupuesto global · corrientes exteriores y fuentes</h2>{r.conservacionGlobal.map(q=><p key={q.id}>{q.nombre}: {q.residuo.toExponential(3)} kg</p>)}</>}{r.trazabilidadEnergia&&<><h2>Ensamblaje energético ejecutado</h2><pre style={{whiteSpace:'pre-wrap',fontSize:11}}>{JSON.stringify(r.trazabilidadEnergia,null,2)}</pre></>}<details className={styles.settings}><summary>Datos y formulación usados</summary><pre style={{whiteSpace:'pre-wrap',fontSize:11}}>{JSON.stringify({formulacion:f,ensamblaje:h.ensamblaje,configuracion:h.config,energia:h.energia},null,2)}</pre></details></div>}
  </div>;
}
