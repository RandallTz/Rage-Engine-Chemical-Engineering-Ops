'use client';
import {useEffect,useState} from 'react';
import {LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,Legend,ReferenceLine,BarChart,Bar} from 'recharts';
import type {HojaMotor} from './hojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import type {ConjuntoResultados} from '../../motores/resultados/contrato';
import {readChartLayout,readChartReference,defaultChartLayout,defaultChartSummary,prepareCharts,type ChartLayout,type ChartSpec,type PreparedChart} from '../../motores/resultados/chartSpecification';
import {nombreEventoRed} from './metadatosRed';
import {EventMarkerLabel,eventLabelRows} from './ResultEvents';
import styles from './trabajoMotor.module.css';

export function PreparedResultCharts({charts}:{charts:PreparedChart[]}){
  return <section aria-label="Versioned result charts">{charts.map(({spec,traces,events})=><article className={styles.tile} key={spec.id}><h2>{spec.title}</h2>
    <p>{spec.type} · {spec.x?`X [${spec.x.unit}] · `:''}Y [{spec.y.unit}]</p>
    {spec.type==='table'?traces.map(trace=><table key={trace.name}><caption>{trace.name}</caption><thead><tr><th>Published sample</th><th>{spec.y.unit}</th></tr></thead><tbody>{trace.points.map((p,i)=><tr key={i}><td>{i}</td><td>{p.y??'Not defined'}</td></tr>)}</tbody></table>):
    spec.type==='bar'?<BarChart width={700} height={320} style={{maxWidth:'100%'}} data={traces.map(t=>({name:t.name,value:t.points.at(-1)?.y}))}><XAxis dataKey="name"/><YAxis unit={` ${spec.y.unit}`}/><Tooltip/><Bar dataKey="value" fill="#536844" isAnimationActive={false}/></BarChart>:
    <LineChart width={700} height={320} style={{maxWidth:'100%'}}><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="x" domain={['dataMin','dataMax']} unit={` ${spec.x!.unit}`} allowDuplicatedCategory={false}/><YAxis type="number" unit={` ${spec.y.unit}`}/><Tooltip/><Legend/>
      {traces.map((trace,i)=><Line key={trace.name} name={trace.name} data={trace.points} dataKey="y" stroke={['#536844','#9b7048','#52667c'][i%3]} type="linear" dot={false} connectNulls={false} isAnimationActive={false}/>)}
      {(()=>{const xs=traces.flatMap(t=>t.points.map(p=>p.x)).filter((x):x is number=>typeof x==='number'),domain:[number,number]=xs.length?[Math.min(...xs),Math.max(...xs)]:[0,1],texts=events.map(e=>`${nombreEventoRed(e.codigo)} · ${e.propietarioId??'model'}`),rows=eventLabelRows(events.map((e,i)=>({x:e.valor,text:texts[i]})),domain,700);return events.map((event,i)=><ReferenceLine key={i} x={event.valor} stroke="#9b7048" label={{value:texts[i],content:<EventMarkerLabel row={rows[i]}/>}}/>);})()}</LineChart>}
    {events.length>0&&<ul aria-label="Chart events">{events.map((event,i)=><li key={i}>{event.valor} {spec.x!.unit} · {nombreEventoRed(event.codigo)} · {event.descripcion} · {event.propietarioId??'model'}</li>)}</ul>}
  </article>)}</section>;
}

export default function ResultCharts({model,result}:{model:HojaMotor;result:ConjuntoResultados}){
  const [error,setError]=useState(''),[prepared,setPrepared]=useState<{key:string;charts:PreparedChart[]}>();
  let layout:ChartLayout|undefined,reference:ReturnType<typeof readChartReference>,recordError='';
  try{layout=readChartLayout(model.resultCharts);reference=readChartReference(model.chartReference);}catch(e){recordError=(e as Error).message;}
  const key=JSON.stringify([model.resultCharts,result,model.chartReference]);
  useEffect(()=>{const abort=new AbortController();setError('');
    if(model.resultCharts)try{const layout=readChartLayout(model.resultCharts)!;void prepareCharts(layout,{current:result,reference:readChartReference(model.chartReference)?.result},abort.signal).then(charts=>{if(!abort.signal.aborted)setPrepared({key,charts});}).catch(e=>{if(!abort.signal.aborted)setError(e.message);});}catch(e){setError((e as Error).message);}
    return()=>abort.abort();
  },[key]);
  function save(layout:ChartLayout|undefined){try{readChartLayout(layout);const current=leerHojas().find(m=>m.id===model.id);if(current)guardarHoja({...current,resultCharts:layout});}catch(e){setError((e as Error).message);}}

  const axes=[...new Map([...result.ejes,...(reference?.result.ejes??[])].map(row=>[row.id,row])).values()];
  const seriesOptions=[...new Map([...result.series,...(reference?.result.series??[])].map(row=>[row.id,row])).values()];
  const edit=(id:string,changes:Partial<ChartSpec>)=>save({...layout!,charts:layout!.charts.map(c=>c.id===id?{...c,...changes}:c)});
  function pin(){try{const current=leerHojas().find(m=>m.id===model.id);if(current)guardarHoja({...current,chartReference:{version:1,result}});}catch(e){setError((e as Error).message);}}
  return <section><div className={styles.graphTools}>
    {!layout?<button onClick={()=>save(defaultChartLayout(result))}>Use versioned result charts</button>:<><button onClick={()=>save(undefined)}>Use legacy chart layout</button><button onClick={()=>{const next=defaultChartLayout(result).charts[0];if(next)save({...layout,charts:[...layout.charts,{...next,id:crypto.randomUUID()}]});}}>Add result chart</button></>}
    <button onClick={pin}>Pin result as overlay reference</button>
  </div>{reference&&<p>Explicit overlay reference: {reference.result.nombre} · {reference.result.id}</p>}
  {(error||recordError)&&<p role="alert">{error||recordError}</p>}
  {layout&&result.indexedNetwork&&(()=>{const summary=defaultChartSummary(result);return summary.available>summary.shown?<p>Default charts show {summary.shown} of {summary.available} published chart groups (temperature and compositions first); internal quantities and boundary-port values are omitted. Use the series list of a chart to plot others.</p>:null;})()}
  {layout?.charts.map(c=><details key={c.id} className={styles.settings}><summary>Configure {c.title}</summary>
    <label>Chart type<select value={c.type} onChange={e=>{const type=e.target.value as ChartSpec['type'];const axis=axes.find(a=>a.rol==='tiempo');const series=seriesOptions.find(s=>s.ejes.length===1);edit(c.id,{type,events:type==='time_series',x:type==='bar'||type==='table'?undefined:type==='parametric'?{kind:'series',id:series?.id??'',unit:series?.unidadSI??'1'}:{kind:'axis',id:axis?.id??'',unit:axis?.unidadSI??'s'}});}}>{['time_series','xy','parametric','bar','table'].map(type=><option key={type}>{type}</option>)}</select></label>
    {c.x&&<><label>X values<select value={`${c.x.kind}:${c.x.id}`} onChange={e=>{const split=e.target.value.indexOf(':'),kind=e.target.value.slice(0,split) as 'axis'|'series',id=e.target.value.slice(split+1),row=(kind==='axis'?axes:seriesOptions).find(r=>r.id===id)!;edit(c.id,{x:{kind,id,unit:row.unidadSI}});}}>{axes.filter(a=>a.rol!=='coordenada').map(a=><option key={a.id} value={`axis:${a.id}`}>{a.nombre}</option>)}{seriesOptions.filter(s=>s.ejes.length===1).map(s=><option key={s.id} value={`series:${s.id}`}>{s.nombre}</option>)}</select></label><label>X unit<input value={c.x.unit} onChange={e=>edit(c.id,{x:{...c.x!,unit:e.target.value}})}/></label></>}
    <label>Y unit<input value={c.y.unit} onChange={e=>edit(c.id,{y:{unit:e.target.value}})}/></label>
    <fieldset><legend>Published series</legend>{(['current','reference'] as const).flatMap(source=>{const r=source==='current'?result:reference?.result;return r?.series.filter(s=>s.ejes.length<=1).map(s=><label key={`${source}:${s.id}`}><input type="checkbox" checked={c.series.some(v=>v.source===source&&v.id===s.id)} onChange={e=>edit(c.id,{series:e.target.checked?[...c.series,{source,id:s.id}]:c.series.filter(v=>v.source!==source||v.id!==s.id)})}/>{source} · {s.nombre} [{s.unidadSI}]</label>)??[];})}</fieldset>
    {c.type==='time_series'&&<label><input type="checkbox" checked={c.events} onChange={e=>edit(c.id,{events:e.target.checked})}/>Event markers</label>}
  </details>)}
  {layout&&prepared?.key===key&&<PreparedResultCharts charts={prepared.charts}/>}
  </section>;
}
