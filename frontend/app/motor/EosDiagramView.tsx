'use client';
import {useEffect,useRef,useState} from 'react';
import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import {VigenciaConsultaDiagrama} from './datosDiagramaEquilibrio';
import {EOS_PACKAGES,EOS_PACKAGE_LABEL,eosCapabilities,eosFeed,eosPlot,prepareIsothermRequest,prepareLocusRequest,prepareSaturationRequest,traceEos} from './eosDiagrams';
import type {EosCapabilities,EosOperation,EosPackageId,EosPlot,EosRequest,EosResponse} from './eosDiagrams';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './equilibrioMotor.module.css';

export const EOS_CHART={W:520,H:300,M:{l:56,r:14,t:12,b:40}};
const {W,H,M}=EOS_CHART;
const COLORS=['var(--accent, #2563eb)','var(--accent-2, #c2410c)'];
function ticks(lo:number,hi:number,n=5){return Array.from({length:n},(_,k)=>lo+(hi-lo)*k/(n-1));}
/** Plain SVG line chart of already published points; marks are drawn at the published coordinates. */
export function EosChart({plot}:{plot:EosPlot}){
  const all=plot.series.flatMap(s=>s.points);
  const xs=all.map(p=>p[0]),ys=all.map(p=>p[1]);
  const pad=(a:number,b:number)=>a===b?[a-1,b+1]:[a-(b-a)*0.04,b+(b-a)*0.04];
  const [x0,x1]=pad(Math.min(...xs),Math.max(...xs)),[y0,y1]=pad(Math.min(...ys),Math.max(...ys));
  const X=(v:number)=>M.l+(v-x0)/(x1-x0)*(W-M.l-M.r),Y=(v:number)=>H-M.b-(v-y0)/(y1-y0)*(H-M.t-M.b);
  return <figure style={{margin:0}}><svg role="img" aria-label={`${plot.yLabel} against ${plot.xLabel}`} viewBox={`0 0 ${W} ${H}`} style={{width:'100%',height:'auto'}}>
    {ticks(x0,x1).map((t,k)=><g key={`x${k}`}><line x1={X(t)} x2={X(t)} y1={M.t} y2={H-M.b} stroke="currentColor" opacity={0.12}/><text x={X(t)} y={H-M.b+16} fontSize={11} textAnchor="middle" fill="currentColor">{num(t)}</text></g>)}
    {ticks(y0,y1).map((t,k)=><g key={`y${k}`}><line x1={M.l} x2={W-M.r} y1={Y(t)} y2={Y(t)} stroke="currentColor" opacity={0.12}/><text x={M.l-6} y={Y(t)+4} fontSize={11} textAnchor="end" fill="currentColor">{num(t)}</text></g>)}
    <rect x={M.l} y={M.t} width={W-M.l-M.r} height={H-M.t-M.b} fill="none" stroke="currentColor" opacity={0.4}/>
    {plot.series.map((s,k)=><g key={s.id} data-series={s.id}>
      <polyline fill="none" stroke={COLORS[k%2]} strokeWidth={2} strokeDasharray={s.dashed?'6 4':undefined} points={s.points.map(p=>`${X(p[0])},${Y(p[1])}`).join(' ')}/>
      {s.points.map((p,j)=><circle key={j} cx={X(p[0])} cy={Y(p[1])} r={3} fill={COLORS[k%2]}/>)}</g>)}
    <text x={(M.l+W-M.r)/2} y={H-6} fontSize={12} textAnchor="middle" fill="currentColor">{plot.xLabel}</text>
    <text transform={`translate(14 ${(M.t+H-M.b)/2}) rotate(-90)`} fontSize={12} textAnchor="middle" fill="currentColor">{plot.yLabel}</text>
  </svg><figcaption className={styles.caption}>{plot.series.map((s,k)=><span key={s.id} style={{marginRight:12}}><span style={{color:COLORS[k%2]}}>{s.dashed?'╌╌':'──'}</span> {s.label}</span>)}</figcaption></figure>;
}

type Panel={request?:EosRequest;response?:EosResponse;loading?:boolean;error?:string};
function download(name:string,body:object){const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const toK=(v:string,u:'K'|'degC')=>({valor:Number(v),unidad:u});

/** Results view of the two layer EOS packages for the species of the selected sample: bubble and dew curves at
 * elevated pressure, isotherms and critical loci. The package is chosen here, never inferred from the sample's own. */
export default function EosDiagramView({muestra}:{muestra:ContextoMuestraEquilibrio}){
  const [cap,setCap]=useState<EosCapabilities>(),[capError,setCapError]=useState(''),[attempt,setAttempt]=useState(0);
  const [pkg,setPkg]=useState<EosPackageId>('psrk-unifac'),[op,setOp]=useState<EosOperation>('isotherm'),[panel,setPanel]=useState<Panel>({});
  const [unit,setUnit]=useState<'K'|'degC'>('degC'),[kind,setKind]=useState<'bubble'|'dew'>('bubble'),[points,setPoints]=useState('8');
  const [T,setT]=useState(String(Math.round((muestra.T-273.15)*100)/100)),[T0,setT0]=useState(String(Math.round((muestra.T-273.15-40)*100)/100)),[T1,setT1]=useState(String(Math.round((muestra.T-273.15+40)*100)/100));
  const [f0,setF0]=useState(''),[f1,setF1]=useState('');
  const control=useRef(new VigenciaConsultaDiagrama());
  const binary=muestra.componentes.length===2;
  useEffect(()=>{const abort=new AbortController();eosCapabilities(abort.signal).then(setCap).catch(e=>{if(!abort.signal.aborted)setCapError((e as Error).message);});return()=>abort.abort();},[attempt]);
  useEffect(()=>{const c=control.current;return()=>c.cancelar();},[]);
  const operations=(cap?.operations??[]).filter(o=>o.id==='saturation_curve'||binary);
  const names=Object.fromEntries(muestra.componentes.map(c=>[String(c.id),c.nombre]));
  const defaultRange=op==='isotherm'?[0.02,0.98]:[0.05,0.95];
  function range():[number,number]{const a=f0.trim()?Number(f0):defaultRange[0],b=f1.trim()?Number(f1):defaultRange[1];if(!(a>0&&b<1&&a<b))throw new Error('Enter a fraction range 0 < from < to < 1.');return [a,b];}
  async function run(){
    const c=control.current.iniciar();setPanel(p=>({...p,loading:true,error:undefined}));
    try{
      const n=Number(points);if(!Number.isInteger(n))throw new Error('Enter an integer number of points.');
      const id=crypto.randomUUID();let request:EosRequest;
      const need=(...v:string[])=>{if(!v.every(x=>x.trim()&&Number.isFinite(Number(x))))throw new Error('Enter numerical temperatures.');};
      if(op==='saturation_curve'){need(T0,T1);request=prepareSaturationRequest(muestra,pkg,kind,toK(T0,unit),toK(T1,unit),n,eosFeed(muestra),id);}
      else if(op==='isotherm'){need(T);request=prepareIsothermRequest(muestra,pkg,toK(T,unit),range(),n,id);}
      else request=prepareLocusRequest(muestra,pkg,range(),n,id);
      const limit=cap?.budgetSeconds??150;
      const response=await traceEos(request,c.signal,limit+20);
      if(c.vigente())setPanel({request,response});
    }catch(e){if(c.vigente())setPanel(p=>({...p,loading:false,error:(e as Error).name==='TimeoutError'?'The diagram service timed out.':(e as Error).message}));}
  }
  const r=panel.response,q=panel.request;
  const plot=r&&q&&r.points.length?eosPlot(r,q,names):undefined;
  return <section aria-label="Elevated-pressure equation-of-state diagrams" className={styles.workspace}>
    <details className={styles.options} open><summary>Elevated-pressure EOS diagrams (Peng–Robinson, PSRK)</summary>
      <p className={styles.notice}>These curves use the species of the selected sample with the package chosen here, not the package of the run. Unsupported species or temperatures are reported as located rejections, never replaced.</p>
      {capError&&<div role="status" className={styles.notice}>{capError} <button onClick={()=>{setCapError('');setAttempt(x=>x+1);}}>Check service</button></div>}
      {!cap&&!capError&&<p role="status">Loading EOS diagram capabilities…</p>}
      {cap&&<>
        <div className={styles.settings}>
          <label>EOS package<select aria-label="EOS diagram package" value={pkg} onChange={e=>{setPkg(e.target.value as EosPackageId);setPanel({});}}>{EOS_PACKAGES.filter(id=>cap.packages.some(p=>p.model.id===id)).map(id=><option key={id} value={id}>{EOS_PACKAGE_LABEL[id]}</option>)}</select></label>
          <label>Diagram<select aria-label="EOS diagram type" value={op} onChange={e=>{setOp(e.target.value as EosOperation);setPanel({});}}>{operations.map(o=><option key={o.id} value={o.id}>{o.id==='saturation_curve'?'Bubble or dew curve (sample composition)':o.id==='isotherm'?'Isotherm P–xy (binary)':'Critical locus (binary)'}</option>)}</select></label>
          <label>Points<input aria-label="EOS diagram points" inputMode="numeric" value={points} onChange={e=>setPoints(e.target.value)}/></label>
          {op!=='critical_locus'&&<label>Temperature unit<select aria-label="EOS temperature unit" value={unit} onChange={e=>setUnit(e.target.value as 'K'|'degC')}><option value="degC">°C</option><option value="K">K</option></select></label>}
          {op==='saturation_curve'&&<><label>Curve<select aria-label="EOS saturation kind" value={kind} onChange={e=>setKind(e.target.value as 'bubble'|'dew')}><option value="bubble">Bubble</option><option value="dew">Dew</option></select></label>
            <label>From<input aria-label="EOS temperature from" inputMode="decimal" value={T0} onChange={e=>setT0(e.target.value)}/></label><label>To<input aria-label="EOS temperature to" inputMode="decimal" value={T1} onChange={e=>setT1(e.target.value)}/></label></>}
          {op==='isotherm'&&<label>Temperature<input aria-label="EOS isotherm temperature" inputMode="decimal" value={T} onChange={e=>setT(e.target.value)}/></label>}
          {op!=='saturation_curve'&&<><label>{names[String(muestra.componentes[0]?.id)]??'Component 1'} fraction from<input aria-label="EOS fraction from" inputMode="decimal" placeholder={String(defaultRange[0])} value={f0} onChange={e=>setF0(e.target.value)}/></label>
            <label>to<input aria-label="EOS fraction to" inputMode="decimal" placeholder={String(defaultRange[1])} value={f1} onChange={e=>setF1(e.target.value)}/></label></>}
          <button className={styles.primary} disabled={panel.loading} onClick={()=>void run()}>Calculate</button>
        </div>
        {panel.loading&&<p role="status" className={styles.loading}>Solving and certifying each point…</p>}
        {panel.error&&<p role="alert" className={styles.notice}>{panel.error}</p>}
        {!r&&!panel.loading&&!panel.error&&<div className={styles.empty}>Calculate to obtain certified points of the selected package.</div>}
        {r&&!plot&&<p className={styles.notice}>{r.status} · {r.diagnostics.map(d=>`${d.code} (${d.path}): ${d.message}`).join(' ')||'No certified points.'}</p>}
        {r&&plot&&<>
          <EosChart plot={plot}/>
          <small className={styles.caption}>{r.status} · {r.points.length} certified points · {r.rejected.length} located rejections · {r.budget?.seconds} s</small>
          {r.rejected.length>0&&<details className={styles.options}><summary>Located rejections</summary>{r.rejected.map((x,k)=><p key={k}>{x.T!==undefined?`T = ${num(x.T)} K`:`x = ${num(x.x!)}`} · {x.cause} · {x.message}</p>)}</details>}
          <button className={styles.download} onClick={()=>download('eos-diagram.json',{request:q,response:r})}>Download points and certificates JSON</button>
        </>}
        {r&&!plot&&r.rejected.length>0&&<details className={styles.options}><summary>Located rejections</summary>{r.rejected.map((x,k)=><p key={k}>{x.T!==undefined?`T = ${num(x.T)} K`:`x = ${num(x.x!)}`} · {x.cause} · {x.message}</p>)}</details>}
      </>}
    </details>
  </section>;
}
