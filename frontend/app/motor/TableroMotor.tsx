'use client';
import { englishLabel } from '../models/english';
import {useEffect,useMemo,useRef,useState} from 'react';
import {LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,Legend,ReferenceArea} from 'recharts';
import type {HojaMotor,GraficaMotor} from './hojasMotor';
import {useChartDrag} from '../models/useChartDrag';
import type {ResultadoMotor} from './modeloNumerico';
import {datosGraficasMotor,limitesGraficaMotor} from './datosGraficasMotor';
import {graficasInicialesEnsamblaje} from './graficasInicialesEnsamblaje';
import {formatearNumeroMotor} from './formatearNumeroMotor';
import {nombreUnidad} from './unidadesMotor';
import {intervaloNoCertificado} from './metadatosRed';
import styles from './trabajoMotor.module.css';
import {graficasInicialesV2,graficasComponentesV2} from './resultadoEnsamblajeV2';
import {graficasInicialesDinamicas} from './resultadoEnsamblaje';
const numero=(x:unknown)=>typeof x==='number'?formatearNumeroMotor(x,5):String(x??'');
const colores=['#536844','#9b7048','#52667c','#96626f','#5b8b88','#84713e'];
/** Presentation defaults come from published variables, never an assumed family. */
export function publishedSeriesCharts(r:ResultadoMotor):GraficaMotor[]{
  const groups=new Map<string,{name:string;ids:string[]}>();
  for(const series of r.seriesEvaluadas??[]){const key=JSON.stringify([series.grupo,series.unidad]);const group=groups.get(key)??{name:`${series.grupo} · ${series.unidad}`,ids:[]};group.ids.push(series.id);groups.set(key,group);}
  return [...groups.values()].map((group,index)=>({id:`published-${index+1}`,nombre:group.name,tipo:'tiempo',x:'t',y:group.ids,ancha:false,altura:310,instante:r.tiempos.length-1}));
}
function Grafica({g,h,r,cambiar}:{g:GraficaMotor;h:HojaMotor;r:ResultadoMotor;cambiar:(g:GraficaMotor)=>void}){
  const host=useRef<HTMLDivElement>(null),resize=useRef<{y:number;altura:number}|null>(null),[ancho,setAncho]=useState(0),[altura,setAltura]=useState<number|null>(null);
  useEffect(()=>{const el=host.current;if(!el)return;const observer=new ResizeObserver(([e])=>setAncho(e.contentRect.width));observer.observe(el);return()=>observer.disconnect();},[]);
  const datos=useMemo(()=>datosGraficasMotor(h,r,g.tipo,g.instante),[h,r,g.tipo,g.instante]);
  const tramo=r.ensamblajeV2?.respuesta.resultados?intervaloNoCertificado(r.ensamblajeV2.respuesta.resultados):null;
  const vx=datos.variables.find(v=>v.id===g.x),ys=g.y.map(id=>datos.variables.find(v=>v.id===id)).filter(v=>v!==undefined),unidades=[...new Set(ys.map(v=>v.unidad))];
  return <>{g.tipo==='perfil'&&<label style={{display:'flex',alignItems:'center',gap:16,fontSize:11,padding:'0 10px 14px'}}>t = {numero(r.tiempos[Math.min(g.instante,r.tiempos.length-1)])} s<input aria-label={`Instante de ${g.nombre}`} type="range" min={0} max={r.tiempos.length-1} value={Math.min(g.instante,r.tiempos.length-1)} onChange={e=>cambiar({...g,instante:Number(e.target.value)})}/></label>}
    <div ref={host} style={{height:altura??g.altura,minWidth:0}}>{!vx||!ys.length?<span className={styles.muted}>Edit the chart to choose available variables.</span>:ancho>0&&<LineChart width={ancho} height={altura??g.altura} data={datos.filas} margin={{top:14,right:22,bottom:28,left:8}} accessibilityLayer><CartesianGrid vertical={false} stroke="#dfe3d7" strokeDasharray="3 5"/><XAxis dataKey={g.x} type="number" domain={limitesGraficaMotor(datos.filas,[g.x],['dataMin','dataMax'])} tickFormatter={numero} tick={{fontSize:10}} height={48} label={{value:`${vx.nombre} [${nombreUnidad(vx.unidad)}]`,position:'insideBottom',offset:0,fontSize:11}}/>{unidades.map((u,i)=><YAxis key={u} yAxisId={u} domain={limitesGraficaMotor(datos.filas,ys.filter(v=>v.unidad===u).map(v=>v.id))} orientation={i%2?'right':'left'} tickFormatter={numero} width={62} tick={{fontSize:10}} label={{value:nombreUnidad(u),angle:i%2?90:-90,position:i%2?'insideRight':'insideLeft',fontSize:11}}/>)}{tramo&&g.x==='t'&&unidades[0]&&<ReferenceArea x1={tramo[0]} x2={tramo[1]} yAxisId={unidades[0]} fill="#ad8050" fillOpacity={0.14} strokeOpacity={0}/> }<Tooltip labelFormatter={v=>`${vx.nombre}: ${numero(v)} ${nombreUnidad(vx.unidad)}`} formatter={(v,n)=>[numero(v),String(n)]}/><Legend wrapperStyle={{fontSize:11}}/>{ys.map((v,i)=><Line key={v.id} dataKey={v.id} yAxisId={v.unidad} name={`${v.nombre} [${nombreUnidad(v.unidad)}]`} type="linear" stroke={colores[i%colores.length]} strokeWidth={2} dot={datos.filas.length===1} isAnimationActive={false} connectNulls={false}/>)}</LineChart>}</div>
    <button className={styles.resize} aria-label={`Resize ${g.nombre}`} title="Drag or use the arrow keys to resize" onKeyDown={e=>{if(['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();cambiar({...g,altura:Math.min(800,Math.max(240,g.altura+(e.key==='ArrowUp'?-40:40)))});}}} onPointerDown={e=>{resize.current={y:e.clientY,altura:g.altura};e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{if(resize.current)setAltura(Math.min(800,Math.max(240,resize.current.altura+e.clientY-resize.current.y)));}} onPointerUp={e=>{if(resize.current)cambiar({...g,altura:Math.min(800,Math.max(240,resize.current.altura+e.clientY-resize.current.y))});resize.current=null;setAltura(null);}} onPointerCancel={()=>{resize.current=null;setAltura(null);}}>―</button>
  </>;
}
export function graficasIniciales(r:ResultadoMotor,h?:HojaMotor):GraficaMotor[]{if(r.ensamblajeV2)return graficasInicialesV2(r);if(r.ensamblajeTermodinamico)return graficasInicialesDinamicas(r);if(r.seriesEvaluadas?.length)return publishedSeriesCharts(r);if(r.estadosAcoplados)return graficasInicialesEnsamblaje(r);const id=r.componentes[0].id;const f=h?.historial.pasos[h.historial.activo].formulacion;const principal=f?.cantidadVolumen?(f.fija||h?.config.cierre==='volumen'?`rho_${id}`:'V'):r.unidadEstado==='m3'?'V':r.unidadEstado==='kg'?`m_${id}`:`rho_${id}`;const base={id:'primera',nombre:principal==='V'?"Volume over time":principal.startsWith('rho_')||r.modo==='1d'?"Density over time":"Mass over time",tipo:'tiempo' as const,x:'t',y:[r.modo==='1d'?`celda_${id}_${Math.floor(r.x.length/2)}`:principal],ancha:false,altura:310,instante:r.tiempos.length-1};return r.modo==='1d'?[base,{...base,id:'perfil',nombre:"Spatial profile",tipo:'perfil',x:'x',y:[`rho_${id}`]}]:[base];}
export default function TableroMotor({h,r,guardar}:{h:HojaMotor;r:ResultadoMotor;guardar:(graficas:GraficaMotor[],columnas:1|2)=>boolean|void}) {
  const graficas=h.tableroIniciado?h.graficas:graficasIniciales(r,h),[editor,setEditor]=useState<GraficaMotor|null>(null),[busqueda,setBusqueda]=useState(''),[eje,setEje]=useState<'x'|'y'>('y');
  const chartDrag=useChartDrag(graficas,charts=>guardar(charts,h.columnas),!editor);
  const actualizar=(g:GraficaMotor)=>guardar(graficas.map(x=>x.id===g.id?g:x),h.columnas);
  const porComponente=graficasComponentesV2(r).filter(g=>!graficas.some(x=>x.id===g.id));
  if(editor){const datos=datosGraficasMotor(h,r,editor.tipo,editor.instante),opciones=datos.variables.filter(v=>(v.nombre+' '+v.grupo+' '+v.unidad).toLowerCase().includes(busqueda.toLowerCase()));return <section className={styles.graphEditor} aria-label="Configure chart"><header><h2>Choose what to plot</h2><button onClick={()=>setEditor(null)}>Cancel</button></header><label>Name<input aria-label="Chart name" value={editor.nombre} onChange={e=>setEditor({...editor,nombre:e.target.value})}/></label>{r.modo==='1d'&&<div className={styles.boundaries}><button aria-pressed={editor.tipo==='tiempo'} onClick={()=>setEditor({...editor,tipo:'tiempo',x:'t',y:[`prom_${r.componentes[0].id}`]})}>Over time</button><button aria-pressed={editor.tipo==='perfil'} onClick={()=>setEditor({...editor,tipo:'perfil',x:'x',y:[`rho_${r.componentes[0].id}`]})}>Spatial profile</button></div>}<div className={styles.boundaries}><button aria-pressed={eje==='x'} onClick={()=>setEje('x')}>X axis</button><button aria-pressed={eje==='y'} onClick={()=>setEje('y')}>Eje Y · {editor.y.length}</button></div><label>Search variables<input type="search" aria-label="Search variables" value={busqueda} onChange={e=>setBusqueda(e.target.value)} placeholder="Name, component or unit"/></label><div className={styles.choices}>{opciones.map(v=>{const seleccionada=eje==='x'?editor.x===v.id:editor.y.includes(v.id);return <button key={v.id} aria-pressed={seleccionada} onClick={()=>setEditor(eje==='x'?{...editor,x:v.id}:{...editor,y:seleccionada?editor.y.filter(y=>y!==v.id):[...editor.y,v.id]})}><span>{englishLabel(v.nombre)}<small style={{display:'block',marginTop:4}}>{v.grupo}</small></span><small>{nombreUnidad(v.unidad)} {seleccionada?'✓':''}</small></button>;})}</div><footer><button className={styles.primary} disabled={!editor.y.length} onClick={()=>{guardar(graficas.some(g=>g.id===editor.id)?graficas.map(g=>g.id===editor.id?editor:g):[...graficas,editor],h.columnas);setEditor(null);}}>Save chart</button></footer></section>;}
  return <section aria-label="Chart dashboard">
    <header className={styles.graphTools}><div><button aria-pressed={h.columnas===1} onClick={()=>guardar(graficas,1)}>Stacked</button><button aria-pressed={h.columnas===2} onClick={()=>guardar(graficas,2)}>Side by side</button></div><div>{r.ensamblajeV2&&<button disabled={!porComponente.length} onClick={()=>guardar([...graficas,...porComponente],h.columnas)}>Component distribution</button>}<button className={styles.primary} onClick={()=>{setEditor({...graficasIniciales(r,h)[0],id:crypto.randomUUID(),nombre:"New chart"});setBusqueda('');setEje('y');}}>Add chart</button></div></header>
    <p className={styles.dragHint}>Drag a chart onto another to swap positions. On touch screens, use the move handle.</p>
    <span className={styles.dragStatus} role="status" aria-live="polite">{chartDrag.announcement}</span>
    <div ref={element=>chartDrag.bindGrid(element)} onPointerDown={event=>chartDrag.start(event)} onDragStart={event=>event.preventDefault()} className={`${styles.graphGrid} ${h.columnas===1?styles.vertical:''}`}>
      {graficas.map((g,i)=><article data-plot-id={g.id} key={g.id} className={`${styles.tile} ${g.ancha?styles.wide:''}`}>
        <header>
          <button data-chart-handle className={styles.grip} aria-label={`Move chart ${g.nombre}`} title="Drag to swap charts, or use the arrow keys" onKeyDown={e=>{if(['ArrowUp','ArrowLeft','ArrowDown','ArrowRight'].includes(e.key)){e.preventDefault();const otro=graficas[i+(['ArrowUp','ArrowLeft'].includes(e.key)?-1:1)];if(otro)chartDrag.swap(g.id,otro.id);}}}>⠿</button>
          <h2>{englishLabel(g.nombre)}</h2>
          <button aria-label={`Edit ${g.nombre}`} onClick={()=>{setEditor(structuredClone(g));setBusqueda('');setEje('y');}}>Edit</button>
          <button aria-label={`Expand ${g.nombre}`} onClick={()=>actualizar({...g,ancha:!g.ancha})}>{g.ancha?"Narrow":"Expand"}</button>
          <button aria-label={`Remove ${g.nombre}`} onClick={()=>guardar(graficas.filter(x=>x.id!==g.id),h.columnas)}>×</button>
        </header>
        <Grafica g={g} h={h} r={r} cambiar={actualizar}/>
      </article>)}
    </div>
  </section>;
}
