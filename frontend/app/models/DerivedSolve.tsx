'use client';
import IndexedStageSolve from './IndexedStageSolve';
import {FlowsheetSolve} from './FlowsheetWorkspace';
import {inverseTransport} from '../../motores/modelo/servicioModelo';
import {inverseDataIds,readInverseSolve,type InverseSolve} from '../../motores/modelo/inverseSpecification';
import {requestFormulation} from './formulationRequests';
import {requestCompilation,startRunSession,runSessionStatus,advanceRunSession,stopRunSession,RunSessionError,type RunSessionAction,type RunSessionAdvance,type RunSessionDiagnostic} from '../../motores/modelo/servicioModelo';
import {PreparedResultCharts} from '../motor/ResultCharts';
import {derivedResult} from '../motor/resolverEngine';
import type {ConjuntoResultados,Evento} from '../../motores/resultados/contrato';
import type {PreparedChart} from '../../motores/resultados/chartSpecification';
import {readEquationWorkbenchReport,type EquationWorkbenchReport} from './equationWorkbench';
import {commonSource,selectedDerivedModel as forwardModel} from './derivedSelection';
import {useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import type {HojaMotor} from '../motor/hojasMotor';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import {firmaHoja} from '../motor/modeloHojaMotor';
import {resolverHojaEngine} from '../motor/resolverEngine';
import {guardarResultadoMotor,saveRejectedAttempt} from '../motor/resultadosMotor';
import AssessmentText from './AssessmentText';
import {selectedDerivedModel} from './derivedSelection';
import styles from '../motor/trabajoMotor.module.css';

export default function DerivedSolve({model}:{model:HojaMotor}){
  return model.commonModel?.flowsheet?<FlowsheetSolve model={model}/>:model.commonModel?.indexSet?<IndexedStageSolve model={model}/>:<OrdinaryDerivedSolve model={model}/>;
}
function OrdinaryDerivedSolve({model}:{model:HojaMotor}){
  const router=useRouter(),controller=useRef<AbortController|null>(null);
  const [quantityError,setQuantityError]=useState<{source:string;message:string}>();
  const [quantities,setQuantities]=useState<{source:string;rows:EquationWorkbenchReport['quantities']}>();
  const source=JSON.stringify(commonSource(model)),steady=model.derivedSelection?.selection.version===5;
  useEffect(()=>{if(!steady)return;const abort=new AbortController();void requestFormulation('equation-workbench',JSON.stringify({modelo:JSON.parse(source)})).then(async response=>{const value=await response.json();if(!response.ok)throw new Error(value.detail?.message??'Quantity metadata unavailable.');return readEquationWorkbenchReport(value);}).then(report=>{if(!abort.signal.aborted){setQuantities({source,rows:report.quantities});setQuantityError(undefined);}}).catch(error=>{if(!abort.signal.aborted)setQuantityError({source,message:error.message});});return()=>abort.abort();},[source,steady]);
  // F3H-3 request: package-closure models are not lowered into the inverse block, so Solve says so instead of offering the controls.
  const [closures,setClosures]=useState<{source:string;volumeIds:string[]}>();
  useEffect(()=>{if(!steady)return;const abort=new AbortController();void Promise.resolve().then(()=>{const stored=JSON.parse(JSON.stringify(model.derivedSelection));delete stored.inverseSolve;return requestCompilation({modelo:forwardModel({...model,derivedSelection:stored})},abort.signal);}).then(report=>{if(!abort.signal.aborted)setClosures({source,volumeIds:'thermodynamicClosures' in report?(report.thermodynamicClosures??[]).map(closure=>closure.volumeId):[]});}).catch(()=>{});return()=>abort.abort();},[source,steady]);
  const [solving,setBusy]=useState(false),[live,setLive]=useState(false),[error,setError]=useState<Error|null>(null),[failureSignature,setFailureSignature]=useState('');
  const busy=solving||live;
  useEffect(()=>()=>controller.current?.abort(),[]);
  const common=model.commonModel!;let unavailable='';try{selectedDerivedModel(model);}catch(failure){unavailable=(failure as Error).message;}
  function change(edit:(source:NonNullable<HojaMotor['commonModel']>)=>NonNullable<HojaMotor['commonModel']>){controller.current?.abort();const latest=leerHojas().find(item=>item.id===model.id);if(latest?.commonModel)guardarHoja({...latest,commonModel:edit(latest.commonModel),resultado:undefined,resultadoRef:undefined});}
  async function run(){const abort=new AbortController();controller.current=abort;setBusy(true);setError(null);try{const result=await resolverHojaEngine(model,{signal:abort.signal,...(model.derivedSelection?.inverseSolve?{transporte:inverseTransport(model.derivedSelection.inverseSolve.record)}:{})});const latest=leerHojas().find(item=>item.id===model.id);if(!latest||firmaHoja(latest)!==result.firma)throw new Error('The model changed; the outdated result was discarded.');abort.signal.throwIfAborted();await guardarResultadoMotor(model.id,result,abort.signal);const saved=leerHojas().find(item=>item.id===model.id);if(!saved||firmaHoja(saved)!==result.firma)throw new Error('The model changed while saving.');guardarHoja({...saved,resultado:undefined,resultadoRef:{firma:result.firma,estado:result.estado,fecha:new Date().toISOString()}});router.push(`/models/${model.id}/results`);}catch(failure){if(!abort.signal.aborted&&leerHojas().some(item=>item.id===model.id&&firmaHoja(item)===firmaHoja(model))){setError(failure as Error);setFailureSignature(firmaHoja(model));try{await saveRejectedAttempt(model.id,firmaHoja(model),failure,abort.signal);}catch(storageError){if(!abort.signal.aborted)setError(Object.assign(failure as Error,{message:(failure as Error).message+' '+(storageError as Error).message}));}}}finally{setBusy(false);}}
  function changeInverse(inverseSolve:InverseSolve|undefined){controller.current?.abort();const latest=leerHojas().find(item=>item.id===model.id);if(latest?.derivedSelection)guardarHoja({...latest,derivedSelection:{...latest.derivedSelection,inverseSolve,inverseNotice:undefined},resultado:undefined,resultadoRef:undefined});}
  const study=common.estudio;
  return <section className={styles.page}><h2>{model.derivedSelection?.selection.version===5?'Steady-state data and solve':'Numerical data and integration'}</h2>{model.derivedSelection?.selection.version===5&&<p>Damped Newton solves the original derived residuals at zero rates. Invariant bindings are fixed; seeds are guesses. A regular local root does not prove global uniqueness or dynamic stability.</p>}<p>These data bind the selected derived quantities. Changing a value or unit requires reviewing its dependent formulation in Transform.</p>{unavailable&&<p role="alert">{unavailable} <Link href={`/models/${model.id}/transform`}>Review Transform</Link></p>}{error&&failureSignature===firmaHoja(model)&&<><p role="alert">{error.message}</p><AssessmentText error={error}/><Link href={`/models/${model.id}/results`}>Review rejected attempt in Results</Link></>}<fieldset disabled={busy}><legend>Declared data</legend>{Object.entries(common.datos).map(([id,datum])=><div className={styles.field} key={id}><label htmlFor={'derived-'+id}>{id}</label><div className={styles.entry}><input id={'derived-'+id} aria-label={`Value ${id}`} value={datum.declaracion.texto} onChange={event=>change(source=>({...source,datos:{...source.datos,[id]:{...datum,declaracion:{...datum.declaracion,texto:event.target.value}}}}))}/><input aria-label={`Unit ${id}`} value={datum.declaracion.unidad} onChange={event=>change(source=>({...source,datos:{...source.datos,[id]:{...datum,declaracion:{...datum.declaracion,unidad:event.target.value}}}}))}/></div></div>)}</fieldset>{quantityError?.source===source&&<p role="alert">{quantityError.message}</p>}{steady&&<InverseControls model={model} quantities={quantities?.source===source?quantities.rows:[]} disabled={busy} change={changeInverse} closureVolumeIds={closures?.source===source?closures.volumeIds:undefined}/>} {model.derivedSelection?.selection.version!==5&&study?.tipo==='temporal'&&<fieldset disabled={busy}><legend>Integration settings</legend><label>Method<select aria-label="Derived integration method" value={study.metodoSolicitado??'rk45'} onChange={event=>change(source=>({...source,estudio:{...study,metodoSolicitado:event.target.value as typeof study.metodoSolicitado}}))}><option value="rk45">RK45</option><option value="bdf">BDF</option></select></label><label>Samples<input aria-label="Derived samples" type="number" min={2} value={study.muestras} onChange={event=>change(source=>({...source,estudio:{...study,muestras:Number(event.target.value)}}))}/></label><label>Relative tolerance<input aria-label="Derived relative tolerance" type="number" value={study.rtol} onChange={event=>change(source=>({...source,estudio:{...study,rtol:Number(event.target.value)}}))}/></label>{Object.entries(study.atol).map(([key,value])=><label key={key}>Absolute tolerance · {key}<input aria-label={`Derived absolute tolerance ${key}`} type="number" value={value} onChange={event=>change(source=>({...source,estudio:{...study,atol:{...study.atol,[key]:Number(event.target.value)}}}))}/></label>)}</fieldset>}<button className={styles.primary} disabled={busy||!!unavailable} onClick={()=>void run()}>{solving?'Solving…':'Run derived model'}</button>{solving&&<button onClick={()=>controller.current?.abort()}>Cancel request</button>}{!steady&&study?.tipo==='temporal'&&!unavailable&&<LiveRun model={model} disabled={solving} onActive={setLive}/>}</section>;
}

/** Shared Solve controls over existing quantities; SI values are declared data. */
export function InverseControls({model,quantities,disabled,change,closureVolumeIds}:{model:HojaMotor;quantities:EquationWorkbenchReport['quantities'];disabled:boolean;change:(value:InverseSolve|undefined)=>void;closureVolumeIds?:string[]}){
  const selection=model.derivedSelection!.selection;if(selection.version!==5)return null;
  const solve=model.derivedSelection?.inverseSolve,notice=model.derivedSelection?.inverseNotice;
  if(closureVolumeIds?.length)return <fieldset><legend>Inverse specifications</legend><p role="alert">Inverse specifications are not yet lowered over package thermodynamic closures (volume(s) {closureVolumeIds.join(', ')}). The forward steady solve supports this model; solve it without an inverse specification.</p>{solve&&<button type="button" disabled={disabled} onClick={()=>change(undefined)}>Clear inverse Solve record</button>}</fieldset>;
  if(solve)try{readInverseSolve(solve);}catch(error){return <fieldset><legend>Inverse specifications</legend><p role="alert">{(error as Error).message}</p><button type="button" disabled={disabled} onClick={()=>change(undefined)}>Clear invalid Solve record</button></fieldset>;}
  const allowedOutputs=[...selection.unknowns,...selection.reconstructions.map(row=>row.quantityId)],allowedInputs=Object.keys(selection.parameters);
  const outputs=quantities.filter(q=>allowedOutputs.includes(q.id)&&q.unit),inputs=quantities.filter(q=>allowedInputs.includes(q.id)&&q.unit);
  function add(){
    const next:InverseSolve=structuredClone(solve??{version:1,record:{format:'rage.inverse-specification',version:1,specifications:[],freedInputs:[]},data:{}});
    const output=outputs.find(q=>!next.record.specifications.some(row=>row.quantityId===q.id)),input=inputs.find(q=>!next.record.freedInputs.some(row=>row.quantityId===q.id));if(!output||!input)return;
    const id='target-'+crypto.randomUUID(),prefix='inverse.'+id;
    const datum=(suffix:string,unit:string)=>{const key=prefix+'.'+suffix;next.data[key]={texto:'',unidad:unit};return key;};
    next.record.specifications.push({id,quantityId:output.id,targetDataId:datum('target',output.unit!),residualScaleDataId:datum('residual-scale',output.unit!)});
    next.record.freedInputs.push({quantityId:input.id,seedDataId:datum('seed',input.unit!),lowerDataId:datum('lower',input.unit!),upperDataId:datum('upper',input.unit!),scaleDataId:datum('scale',input.unit!)});change(next);
  }
  function editData(id:string,texto:string){change({...solve!,data:{...solve!.data,[id]:{...solve!.data[id],texto}}});}
  function select(index:number,kind:'specifications'|'freedInputs',quantityId:string){const next=structuredClone(solve!);const q=quantities.find(q=>q.id===quantityId)!;next.record[kind][index].quantityId=quantityId;for(const [key,id]of Object.entries(next.record[kind][index]))if(key.endsWith('DataId'))next.data[id].unidad=q.unit!;change(next);}
  return <fieldset disabled={disabled}><legend>Inverse specifications</legend>{notice&&<p role="status">{notice}</p>}<p>Choose an output target and the constant input Newton frees. Supply guesses, admissible bounds and positive scales in the displayed SI units. Model and Transform stay unchanged.</p>
    <p role="status">{solve?.record.specifications.length??0} specifications · {solve?.record.freedInputs.length??0} freed inputs · square</p>
    {solve?.record.specifications.map((spec,index)=>{const freed=solve.record.freedInputs[index];return <div key={spec.id}>
      <label>Target quantity<select aria-label={`Target quantity ${index+1}`} value={spec.quantityId} onChange={event=>select(index,'specifications',event.target.value)}>{outputs.filter(q=>q.id===spec.quantityId||!solve.record.specifications.some(r=>r.quantityId===q.id)).map(q=><option key={q.id} value={q.id}>{q.name} [{q.unit}]</option>)}</select></label>
      <label>Input to free<select aria-label={`Input to free ${index+1}`} value={freed.quantityId} onChange={event=>select(index,'freedInputs',event.target.value)}>{inputs.filter(q=>q.id===freed.quantityId||!solve.record.freedInputs.some(r=>r.quantityId===q.id)).map(q=><option key={q.id} value={q.id}>{q.name} [{q.unit}]</option>)}</select></label>
      {([['Target value',spec.targetDataId],['Specification residual scale',spec.residualScaleDataId],['Freed input seed',freed.seedDataId],['Freed input lower bound',freed.lowerDataId],['Freed input upper bound',freed.upperDataId],['Freed input scale',freed.scaleDataId]] as const).map(([label,id])=><label key={id}>{label} [{solve.data[id].unidad}]<input aria-label={`${label} ${index+1}`} value={solve.data[id].texto} onChange={event=>editData(id,event.target.value)}/></label>)}
      <button type="button" onClick={()=>{const next=structuredClone(solve);next.record.specifications.splice(index,1);next.record.freedInputs.splice(index,1);const retained=new Set(inverseDataIds(next.record));next.data=Object.fromEntries(Object.entries(next.data).filter(([id])=>retained.has(id)));change(next.record.specifications.length?next:undefined);}}>Remove specification {index+1}</button>
    </div>;})}
    <button type="button" disabled={!outputs.length||!inputs.length||(solve?.record.specifications.length??0)>=Math.min(50,outputs.length,inputs.length)} onClick={add}>Add output target and free input</button>
    {solve&&<button type="button" onClick={()=>change(undefined)}>Use forward steady solve</button>}
  </fieldset>;
}
/** Demo 0.3 C9 (dec-control-surface): live run, pace, pause, stop and time-input actions in Solve, through the C7
 * run-session routes. Python lowers, steps, applies every action at the edge of the stretch and publishes; the
 * client only decides when to ask for the next stretch (wall-clock pace) and displays the returned samples.
 * The preview is uncertified and never replaces Results: only the published document is saved as the result. */
const PACES=[0.5,1,2,5,10,30,60,300,1800],TICK_MS=500,KEEP_ALIVE_MS=5*60*1000;
type Phase='idle'|'lowering'|'running'|'paused'|'finished'|'failed';
type Session={id:string;horizon:number;edge:number;timeInputs:string[];stateIds:string[]};
type Preview={t:number[];values:Record<string,(number|null)[]>;events:Evento[]};
const show=(t:number)=>String(Number(t.toPrecision(6)));// display only
const describe=(diagnostics:RunSessionDiagnostic[]|undefined)=>(diagnostics??[]).map(d=>`${d.message}${d.path?` (${d.path})`:''}`).join(' ');
function LiveRun({model,disabled,onActive}:{model:HojaMotor;disabled:boolean;onActive:(active:boolean)=>void}){
  const [phase,setPhase]=useState<Phase>('idle'),[message,setMessage]=useState(''),[behind,setBehind]=useState(false),[saved,setSaved]=useState(false);
  const [session,setSession]=useState<Session>(),[preview,setPreview]=useState<Preview>({t:[],values:{},events:[]});
  const [pace,setPace]=useState(10),[shown,setShown]=useState<string[]>([]),[drafts,setDrafts]=useState<Record<string,{value:string;unit:string}>>({}),[queued,setQueued]=useState<RunSessionAction[]>([]);
  const [quantities,setQuantities]=useState<EquationWorkbenchReport['quantities']>([]);
  const sessionRef=useRef<Session|undefined>(undefined),seq=useRef(0),running=useRef(false),paceRef=useRef(pace),queue=useRef<RunSessionAction[]>([]),chain=useRef<Promise<unknown>>(Promise.resolve()),signature=useRef(''),ended=useRef(false),last=useRef(0);
  paceRef.current=pace;
  const active=phase==='lowering'||phase==='running'||phase==='paused';
  useEffect(()=>{onActive(active);},[active,onActive]);
  // Leaving Solve ends the server session so it does not hold one of the two live slots.
  useEffect(()=>()=>{running.current=false;const s=sessionRef.current;if(s&&!ended.current)void stopRunSession(s.id).catch(()=>{});},[]);
  // Keep-alive: a paused client sends a zero-length advance every 5 minutes (C7 idle eviction is 30 minutes).
  useEffect(()=>{if(phase!=='paused')return;const timer=setInterval(()=>{const s=sessionRef.current;if(s)void serial(()=>advance(s.edge,[])).catch(()=>{});},KEEP_ALIVE_MS);return()=>clearInterval(timer);},[phase]);
  const unit=(id:string)=>quantities.find(q=>q.id===id)?.unit??'SI';
  const name=(id:string)=>quantities.find(q=>q.id===id)?.name??id;
  /** Requests are strictly sequential: one sequence number per answer. */
  function serial<T>(task:()=>Promise<T>):Promise<T>{const next=chain.current.then(task,task);chain.current=next.catch(()=>{});return next;}
  function append(response:RunSessionAdvance){
    // Display only: the server's samples, its scheduled jumps (left then right at t*) and the applied action.
    setPreview(previous=>{
      const points:{t:number;row:Record<string,number>;order:number}[]=[];
      response.rows.t.forEach((t,i)=>points.push({t,order:1,row:Object.fromEntries(Object.entries(response.rows.values).map(([id,values])=>[id,values[i]]))}));
      for(const jump of response.jumps)points.push({t:jump.t,order:0,row:jump.left},{t:jump.t,order:2,row:jump.right});
      if(response.applied)points.push({t:response.applied.t,order:3,row:response.applied.right});
      points.sort((a,b)=>a.t-b.t||a.order-b.order);
      const ids=new Set([...Object.keys(previous.values),...points.flatMap(p=>Object.keys(p.row))]);
      const values:Preview['values']={};for(const id of ids)values[id]=[...(previous.values[id]??previous.t.map(()=>null)),...points.map(p=>p.row[id]??null)];
      const events=[...previous.events,...[...response.jumps,...(response.applied?[response.applied]:[])].map(jump=>({codigo:'timeline_action',ejeId:'t',valor:jump.t,descripcion:Object.keys(jump.right).filter(id=>jump.right[id]!==jump.left[id]).map(id=>`${name(id)} ${jump.left[id]} → ${jump.right[id]} ${unit(id)}`).join('; ')||'Action at the edge',propietarioId:response.applied&&jump===response.applied?'operator':'scheduled'}))];
      return {t:[...previous.t,...points.map(p=>p.t)],values,events};
    });
  }
  async function advance(to:number,actions:RunSessionAction[]){
    const s=sessionRef.current!;const number=seq.current;let response:RunSessionAdvance;
    try{response=await advanceRunSession(s.id,number,to,actions);}
    catch(error){if(error instanceof RunSessionError&&error.code==='unavailable')response=await advanceRunSession(s.id,number,to,actions);else throw error;}// a retry with the same seq returns the same answer
    seq.current=number+1;s.edge=response.edge;setSession({...s});append(response);
    if(response.rejected?.length)setMessage(`Action refused at t = ${show(response.edge)} s: ${describe(response.rejected)} The run continued unchanged.`);
    else if(response.applied)setMessage(`Action applied at t = ${show(response.applied.t)} s.`);
    if(response.result)await finish(response.result,'The run reached its horizon.');
    return response;
  }
  async function finish(result:ConjuntoResultados,note:string){
    running.current=false;ended.current=true;setPhase('finished');setMessage(note);
    try{
      const latest=leerHojas().find(item=>item.id===model.id);if(!latest||firmaHoja(latest)!==signature.current)throw new Error('The model changed during the run; its result was not saved.');
      const value=derivedResult(latest,result);await guardarResultadoMotor(model.id,value);
      const current=leerHojas().find(item=>item.id===model.id)!;guardarHoja({...current,resultado:undefined,resultadoRef:{firma:value.firma,estado:value.estado,fecha:new Date().toISOString()}});setSaved(true);
      setMessage(`${note} The published ${result.estado==='parcial'?'partial ':''}result is saved; open it in Results.`);
    }catch(error){setMessage(`${note} ${(error as Error).message}`);}
  }
  function fail(error:unknown){running.current=false;const e=error as RunSessionError;setPhase(previous=>previous==='finished'?previous:'failed');setMessage(`${e.message}${e.diagnostics?.length?' '+describe(e.diagnostics):''}`);}
  async function start(){
    setMessage('');setSaved(false);setPreview({t:[],values:{},events:[]});setQueued([]);queue.current=[];seq.current=0;ended.current=false;sessionRef.current=undefined;setSession(undefined);
    signature.current=firmaHoja(model);setPhase('lowering');
    try{
      const {sessionId}=await startRunSession(selectedDerivedModel(model));
      sessionRef.current={id:sessionId,horizon:0,edge:0,timeInputs:[],stateIds:[]};
      for(;;){// lowering runs on the server (35-200 s); poll its status
        const status=await runSessionStatus(sessionId);
        if(status.state==='failed'){ended.current=true;throw new RunSessionError(422,status.error?.code??'failed',status.error?.message??'The run session failed.',status.error?.diagnostics);}
        if(status.state==='finished'){if(status.result)await finish(status.result,'The run ended at lowering.');return;}
        if(status.state==='ready'){
          const s:Session={id:sessionId,horizon:status.horizon!,edge:status.edge!,timeInputs:status.timeInputs!,stateIds:status.stateIds!};
          sessionRef.current=s;setSession(s);setShown([...s.timeInputs,...s.stateIds.filter(id=>!s.timeInputs.includes(id))].slice(0,4));
          setPace(PACES.reduce((best,p)=>Math.abs(Math.log(p*30/s.horizon))<Math.abs(Math.log(best*30/s.horizon))?p:best,PACES[0]));
          void requestFormulation('equation-workbench',JSON.stringify({modelo:commonSource(model)})).then(async response=>{const value=await response.json();if(response.ok)setQuantities(readEquationWorkbenchReport(value).quantities);}).catch(()=>{});
          setPhase('paused');return;
        }
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
    }catch(error){fail(error);}
  }
  async function loop(){
    last.current=performance.now();
    while(running.current&&!ended.current){
      const s=sessionRef.current!,began=performance.now(),elapsed=Math.max(TICK_MS,began-last.current)/1000;last.current=began;
      const to=Math.min(s.horizon,s.edge+paceRef.current*elapsed),actions=queue.current;queue.current=[];setQueued([]);
      try{await serial(()=>advance(to,actions));}catch(error){fail(error);return;}
      const took=performance.now()-began;setBehind(took>TICK_MS*1.5);
      if(took<TICK_MS)await new Promise(resolve=>setTimeout(resolve,TICK_MS-took));
    }
  }
  function run(){if(!sessionRef.current||ended.current)return;running.current=true;setPhase('running');void loop();}
  function pause(){running.current=false;setPhase('paused');}
  async function stop(){
    running.current=false;const s=sessionRef.current;if(!s||ended.current)return;
    try{const answer=await serial(()=>stopRunSession(s.id));ended.current=true;if(answer.result)await finish(answer.result,'Run stopped by the operator.');else{setPhase('failed');setMessage(answer.error?.message??'The run ended without a result.');}}catch(error){fail(error);}
  }
  function queueAction(id:string){
    const draft=drafts[id];const value=Number(draft?.value);const unitText=draft?.unit?.trim()||unit(id);
    if(!draft||draft.value.trim()===''||!Number.isFinite(value)){setMessage(`Enter a finite value for ${name(id)}.`);return;}
    const action={quantityId:id,value,unit:unitText};
    if(phase==='running'){queue.current=[...queue.current.filter(a=>a.quantityId!==id),action];setQueued(queue.current);setMessage(`${name(id)} will change at the edge of the next stretch.`);}
    else void serial(()=>advance(sessionRef.current!.edge,[action])).catch(fail);// paused: a zero-length advance applies it at the current edge
  }
  const charts:PreparedChart[]=shown.filter(id=>id in preview.values).map(id=>({spec:{id:'live-'+id,title:`${name(id)} · live preview`,type:'time_series',series:[{source:'current',id}],x:{kind:'axis',id:'t',unit:'s'},y:{unit:unit(id)},events:true},
    traces:[{name:name(id),points:preview.t.map((t,i)=>({x:t,y:preview.values[id][i]}))}],events:preview.events}));
  return <fieldset disabled={disabled} aria-label="Live run"><legend>Live run</legend>
    <p>Runs the same derived model on the server, paced against the wall clock. Change a declared time input during the run; the change applies at the edge of the current stretch and is recorded in the run timeline. Model data stay locked while a run is live.</p>
    {phase==='idle'||phase==='finished'||phase==='failed'?<button onClick={()=>void start()}>Start live run</button>:null}
    {phase==='lowering'&&<p role="status">Lowering the model on the server…</p>}
    {session&&(phase==='running'||phase==='paused')&&<>
      <p role="status">t = {show(session.edge)} s of {show(session.horizon)} s · {phase==='running'?'running':'paused'}{behind?' · the server is slower than the requested pace; the run falls behind wall time and skips no physics':''}</p>
      <label>Pace<select aria-label="Live run pace" value={pace} onChange={event=>setPace(Number(event.target.value))}>{PACES.map(p=><option key={p} value={p}>{p} s simulated per second</option>)}</select></label>
      {phase==='running'?<button onClick={pause}>Pause</button>:<button onClick={run}>{session.edge>0?'Resume':'Run'}</button>}
      <button onClick={()=>void stop()}>Stop and publish</button>
      {session.timeInputs.length>0?<fieldset><legend>Time inputs</legend>{session.timeInputs.map(id=><div key={id}><label>{name(id)}<input aria-label={`New value ${id}`} value={drafts[id]?.value??''} placeholder={String(preview.values[id]?.at(-1)??'')} onChange={event=>setDrafts(d=>({...d,[id]:{value:event.target.value,unit:d[id]?.unit??unit(id)}}))}/></label><input aria-label={`Unit ${id}`} value={drafts[id]?.unit??unit(id)} onChange={event=>setDrafts(d=>({...d,[id]:{value:d[id]?.value??'',unit:event.target.value}}))}/><button onClick={()=>queueAction(id)}>{phase==='running'?'Apply at next edge':'Apply now'}</button>{queued.some(a=>a.quantityId===id)&&<small> queued</small>}</div>)}</fieldset>:<p>This model declares no time input, so it accepts no action during the run. Declare a set point or disturbance as a time input in Transform.</p>}
    </>}
    {message&&<p role={phase==='failed'?'alert':'status'}>{message}</p>}
    {saved&&<Link href={`/models/${model.id}/results`}>Open the published result in Results</Link>}
    {session&&preview.t.length>0&&<section aria-label="Live preview">
      <h3>Live preview · uncertified</h3><p>Dense-output samples sent during the run. They are not a result and never replace Results; the published document is built when the run ends.</p>
      <fieldset><legend>Previewed quantities</legend>{session.stateIds.map(id=><label key={id}><input type="checkbox" checked={shown.includes(id)} onChange={event=>setShown(s=>event.target.checked?[...s,id]:s.filter(v=>v!==id))}/>{name(id)}{session.timeInputs.includes(id)?' (time input)':''}</label>)}</fieldset>
      <PreparedResultCharts charts={charts}/>
    </section>}
  </fieldset>;
}
