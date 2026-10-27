'use client';
import {useEffect,useRef,useState} from 'react';
import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import type {CantidadEstado} from './contratoTermodinamica';
import type {CompositionLineRequest,CompositionLineResponse,MulticomponentCapabilities,PerfilResolucion,TernaryLiquidLiquidRequest,TernaryLiquidLiquidResponse} from './contratoDiagramasEquilibrio';
import {VigenciaConsultaDiagrama} from './datosDiagramaEquilibrio';
import {linePlot,multicomponentCapabilities,prepareLineRequest,prepareTernaryRequest,sampleFeed,ternaryPlot,traceLine,traceTernary} from './multicomponentDiagrams';
import TernaryLiquidLiquidChart,{CompositionLineChart} from './TernaryLiquidLiquidChart';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './equilibrioMotor.module.css';

type Panel<Q,R>={request?:Q;response?:R;loading?:boolean;error?:string};
function download(name:string,body:object){const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

/** Ternary liquid-liquid diagram and composition-line slice of the selected sample (three or more components).
 * Requests carry every species of the volume; the backend computes and certifies everything that is drawn. */
export default function MulticomponentEquilibrium({muestra}:{muestra:ContextoMuestraEquilibrio}){
  const [cap,setCap]=useState<MulticomponentCapabilities>(),[capError,setCapError]=useState(''),[attempt,setAttempt]=useState(0);
  const [profile,setProfile]=useState<PerfilResolucion>('exploratoria'),[manual,setManual]=useState(false);
  const [T,setT]=useState({valor:'',unidad:'degC'}),[P,setP]=useState({valor:'',unidad:'bar'});
  const ids=muestra.componentes.map(c=>String(c.id));
  const [start,setStart]=useState<Record<string,string>>({}),[end,setEnd]=useState<Record<string,string>>({});
  const [ternary,setTernary]=useState<Panel<TernaryLiquidLiquidRequest,TernaryLiquidLiquidResponse>>({}),[line,setLine]=useState<Panel<CompositionLineRequest,CompositionLineResponse>>({});
  const controls=useRef({ternary:new VigenciaConsultaDiagrama(),line:new VigenciaConsultaDiagrama()});
  useEffect(()=>{const abort=new AbortController();multicomponentCapabilities(abort.signal).then(setCap).catch(e=>{if(!abort.signal.aborted)setCapError((e as Error).message);});return()=>abort.abort();},[attempt]);
  useEffect(()=>{const c=controls.current;return()=>{c.ternary.cancelar();c.line.cancelar();};},[]);
  const supported=!!cap?.packages.some(p=>p.model.id===muestra.modelo.id&&p.model.version===muestra.modelo.version);
  const limit=1000*((cap?.profiles.find(p=>p.id===profile)?.limitSeconds??60)+20);
  const feed=sampleFeed(muestra),startValue=(id:string)=>start[id]??String(feed[id]),endValue=(id:string)=>end[id]??String(1/ids.length);
  function condition():[CantidadEstado,CantidadEstado]{
    if(!manual)return [{valor:muestra.T,unidad:'K'},{valor:muestra.P,unidad:'Pa'}];
    if(![T.valor,P.valor].every(v=>v.trim()&&Number.isFinite(Number(v))))throw new Error('Enter a numerical temperature and pressure with their units.');
    return [{valor:Number(T.valor),unidad:T.unidad},{valor:Number(P.valor),unidad:P.unidad}];
  }
  async function runTernary(){
    const control=controls.current.ternary.iniciar();setTernary(p=>({...p,loading:true,error:undefined}));
    try{const [t,p]=condition(),request=prepareTernaryRequest(muestra,t,p,profile,crypto.randomUUID()),response=await traceTernary(request,control.signal,limit);if(control.vigente())setTernary({request,response});}
    catch(e){if(control.vigente())setTernary(p=>({...p,loading:false,error:(e as Error).name==='TimeoutError'?'The diagram service timed out.':(e as Error).message}));}
  }
  async function runLine(){
    const control=controls.current.line.iniciar();setLine(p=>({...p,loading:true,error:undefined}));
    try{
      const [t,p]=condition(),read=(f:(id:string)=>string)=>Object.fromEntries(ids.map(id=>[id,Number(f(id))]));
      const request=prepareLineRequest(muestra,t,p,read(startValue),read(endValue),profile,crypto.randomUUID()),response=await traceLine(request,control.signal,limit);
      if(control.vigente())setLine({request,response});
    }catch(e){if(control.vigente())setLine(p=>({...p,loading:false,error:(e as Error).name==='TimeoutError'?'The diagram service timed out.':(e as Error).message}));}
  }
  const order=muestra.componentes.map(c=>c.id),names=muestra.componentes.map(c=>c.nombre);
  const t=ternary.response,l=line.response;
  const lineData=l&&'rows' in l?linePlot(l,order):undefined;
  const sameCondition=!!(t&&l&&'tieLines' in t&&'rows' in l&&t.condition.T===l.condition.T&&t.condition.P===l.condition.P&&t.identity.modelFingerprint===l.identity.modelFingerprint);
  return <section aria-label="Multicomponent equilibrium diagrams">
    <p className={styles.notice}>This volume contains {muestra.componentes.length} components. T–xy/P–xy slices are binary; every component stays in the assembly, in its results and in the requests below.</p>
    {capError&&<div role="status" className={styles.notice}>{capError} <button onClick={()=>{setCapError('');setAttempt(x=>x+1);}}>Check service</button></div>}
    {cap&&!supported&&<p className={styles.notice}>Package {muestra.modelo.id} does not publish multicomponent diagrams. It will not be replaced by another model.</p>}
    {supported&&<>
      <details className={styles.options}><summary>Condition and resolution</summary><div className={styles.settings}>
        <label className={styles.check}><input type="checkbox" checked={manual} onChange={e=>{setManual(e.target.checked);if(!T.valor){setT({...T,valor:String(muestra.T-273.15)});setP({...P,valor:String(muestra.P/1e5)});}}}/>Prescribed T and P (otherwise the selected sample&apos;s)</label>
        {manual&&<><div className={styles.quantity}><input aria-label="Diagram temperature" inputMode="decimal" value={T.valor} onChange={e=>setT({...T,valor:e.target.value})}/><select aria-label="Diagram temperature unit" value={T.unidad} onChange={e=>setT({...T,unidad:e.target.value})}><option value="degC">°C</option><option value="K">K</option></select></div>
          <div className={styles.quantity}><input aria-label="Diagram pressure" inputMode="decimal" value={P.valor} onChange={e=>setP({...P,valor:e.target.value})}/><select aria-label="Diagram pressure unit" value={P.unidad} onChange={e=>setP({...P,unidad:e.target.value})}>{['bar','kPa','Pa'].map(u=><option key={u}>{u}</option>)}</select></div></>}
        <label>Resolution<select aria-label="Multicomponent diagram resolution" value={profile} onChange={e=>setProfile(e.target.value as PerfilResolucion)}>{cap!.profiles.map(p=><option value={p.id} key={p.id}>{p.id==='exploratoria'?'Exploratory':'Refined'}</option>)}</select></label>
      </div></details>
      <div className={styles.grid}>
        {muestra.componentes.length===3&&<article className={styles.panel} aria-label="Ternary liquid-liquid diagram">
          <header><div><h2>Ternary liquid–liquid</h2><small>{t&&'tieLines' in t?`${num(t.condition.T-273.15)} °C · ${num(t.condition.P/1e5)} bar abs.`:'At fixed T and P'}</small></div><button disabled={ternary.loading} onClick={()=>void runTernary()}>Calculate</button></header>
          {ternary.loading&&<p role="status" className={styles.loading}>Tracing and certifying tie lines…</p>}
          {ternary.error&&<p role="alert" className={styles.notice}>{ternary.error}</p>}
          {!t&&!ternary.loading&&!ternary.error&&<div className={styles.empty}>Calculate the diagram to obtain certified tie lines.</div>}
          {t&&!('tieLines' in t)&&<p className={styles.notice}>{t.status} · {t.diagnostics.map(d=>`${d.code} (${d.path}): ${d.message}`).join(' ')}</p>}
          {t&&'tieLines' in t&&<>
            {t.branches.length?<TernaryLiquidLiquidChart plot={ternaryPlot(t,order)} names={names} line={sameCondition?lineData:undefined}/>:<p className={styles.notice}>No liquid–liquid split was found at this condition (seed lattice of the profile; not a proof of miscibility).</p>}
            <small className={styles.caption}>{t.status} · {t.branches.length} branches · {t.tieLines.length} certified tie lines · {t.budget.seconds} s</small>
            <details className={styles.options}><summary>Certificates and branch ends</summary><p>{t.evidence?`${t.evidence.level} · ${t.evidence.reason}`:'No pair evidence published.'}</p>
              {t.specialPoints.map(p=><p key={p.id}>{p.kind} · {p.branchId} {p.side} · {p.certificate.status} · {p.description}</p>)}
              {t.incidences.map(i=><p key={i.id}>{i.kind} · {i.cause} · {i.action}</p>)}<p>{t.method}</p>
              <pre>{JSON.stringify({identity:t.identity,budget:t.budget,diagnostics:t.diagnostics},null,2)}</pre></details>
            <button className={styles.download} onClick={()=>download('ternary-liquid-liquid.json',{request:ternary.request,response:t})}>Download tie lines and certificates JSON</button>
          </>}
        </article>}
        <article className={styles.panel} aria-label="Composition-line slice">
          <header><div><h2>Composition line</h2><small>Feeds between two compositions at fixed T and P</small></div><button disabled={line.loading} onClick={()=>void runLine()}>Calculate</button></header>
          <div className={styles.settings}>{(['start','end'] as const).map(side=><fieldset key={side} style={{border:0,padding:0,display:'grid',gap:6,minWidth:0}}><legend style={{fontSize:12}}>{side==='start'?'Start (default: sample feed)':'End'}</legend>
            {muestra.componentes.map(c=><label key={c.id}>{c.nombre}<input aria-label={`${side} mole fraction of ${c.nombre}`} inputMode="decimal" value={side==='start'?startValue(String(c.id)):endValue(String(c.id))} onChange={e=>(side==='start'?setStart:setEnd)(v=>({...v,[String(c.id)]:e.target.value}))}/></label>)}
          </fieldset>)}</div>
          {line.loading&&<p role="status" className={styles.loading}>Closing and certifying every feed…</p>}
          {line.error&&<p role="alert" className={styles.notice}>{line.error}</p>}
          {l&&!('rows' in l)&&<p className={styles.notice}>{l.status} · {l.diagnostics.map(d=>`${d.code} (${d.path}): ${d.message}`).join(' ')}</p>}
          {l&&'rows' in l&&lineData&&<>
            <CompositionLineChart plot={lineData}/>
            <small className={styles.caption}>{l.status} · {l.rows.length} rows ({lineData.rows.length} certified) · {l.boundaries.length} boundaries · {l.failures.length} failures{t&&'tieLines' in t&&!sameCondition?' · not overlaid: another condition or fingerprint than the ternary diagram':''}</small>
            <details className={styles.options}><summary>Boundaries and method</summary>
              {l.boundaries.map(b=><p key={b.id}>l in [{num(b.lInterval[0])}, {num(b.lInterval[1])}] · {b.before.phaseSet.join('+')} → {b.after.phaseSet.join('+')}</p>)}
              {l.failures.map((f,k)=><p key={k}>l = {num(f.l)} · {f.reason} · {f.message}</p>)}<p>{l.method}</p></details>
            <button className={styles.download} onClick={()=>download('composition-line.json',{request:line.request,response:l})}>Download rows and certificates JSON</button>
          </>}
        </article>
      </div>
    </>}
  </section>;
}
