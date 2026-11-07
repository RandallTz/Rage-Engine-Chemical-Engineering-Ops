'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import type {HojaMotor} from '../motor/hojasMotor';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import {firmaHoja} from '../motor/modeloHojaMotor';
import {guardarResultadoMotor,saveRejectedAttempt} from '../motor/resultadosMotor';
import {applyFlowsheet,currentFlowsheet,flowsheetResult,flowsheetSourceSignature,prepareFlowsheet,solveFlowsheet} from './flowsheetLifecycle';
import AssessmentText from './AssessmentText';
import styles from './workspace.module.css';

export function FlowsheetTransform({model}:{model:HojaMotor}){
  const controller=useRef<AbortController|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<Error|null>(null);
  const signature=flowsheetSourceSignature(model),selected=currentFlowsheet(model);
  useEffect(()=>()=>controller.current?.abort(),[signature]);
  async function prepare(mode:'dynamic'|'steady'){
    const abort=new AbortController();controller.current?.abort();controller.current=abort;setBusy(true);setError(null);
    try{const report=await prepareFlowsheet(model,mode,abort.signal);const latest=leerHojas().find(row=>row.id===model.id);
      if(!latest)throw new Error('The model is no longer available.');abort.signal.throwIfAborted();guardarHoja(applyFlowsheet(latest,report));
    }catch(failure){if(!abort.signal.aborted)setError(failure as Error);}finally{if(controller.current===abort)setBusy(false);}
  }
  return <section className={styles.executionSelection}><h2>Flowsheet formulation</h2><p>Python replays and prepares the connected equipment equations.</p>
    <button disabled={busy} onClick={()=>void prepare('dynamic')}>Use dynamic formulation</button><button disabled={busy} onClick={()=>void prepare('steady')}>Use steady state (zero accumulation)</button>
    {busy&&<p role="status">Preparing the network…</p>}{error&&<><p role="alert">{error.message}</p><AssessmentText error={error}/></>}
    {model.flowsheetStale&&<p role="alert">stale_flowsheet_execution: The topology or data changed. Prepare the network again.</p>}
    {selected?<><p>{selected.report.count} instances · {selected.report.selection.mode} · {selected.report.rateRows.length} original rate rows</p><Link href={`/models/${model.id}/solve`}>Continue to Solve →</Link></>:<p>No current flowsheet formulation selected.</p>}
  </section>;
}

export function FlowsheetSolve({model}:{model:HojaMotor}){
  const router=useRouter(),controller=useRef<AbortController|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<Error|null>(null);
  const signature=flowsheetSourceSignature(model),selected=currentFlowsheet(model),sheet=model.commonModel!.flowsheet!;
  useEffect(()=>()=>controller.current?.abort(),[signature,model.flowsheetSelection]);
  function editData(instanceId:string,datumId:string,text:string,unit:string){
    const latest=leerHojas().find(row=>row.id===model.id);if(!latest?.commonModel?.flowsheet)return;
    const common=structuredClone(latest.commonModel),instance=common.flowsheet!.instances.find(row=>row.id===instanceId);if(!instance)return;
    instance.data[datumId]={texto:text,unidad:unit};
    try{guardarHoja({...latest,commonModel:common});setError(null);}catch(failure){setError(failure as Error);}
  }
  async function run(){
    if(!selected)return;const abort=new AbortController();controller.current=abort;setBusy(true);setError(null);const pin=firmaHoja(model);
    try{const common=await solveFlowsheet(model,abort.signal);const latest=leerHojas().find(row=>row.id===model.id);
      if(!latest||firmaHoja(latest)!==pin)throw new Error('stale_flowsheet_execution: The model changed while solving.');
      const result=flowsheetResult(latest,common,pin);abort.signal.throwIfAborted();await guardarResultadoMotor(model.id,result,abort.signal);
      const saved=leerHojas().find(row=>row.id===model.id);if(!saved||firmaHoja(saved)!==pin)throw new Error('stale_flowsheet_execution: The model changed while saving.');
      guardarHoja({...saved,resultado:undefined,resultadoRef:{firma:pin,estado:result.estado,fecha:new Date().toISOString()}});router.push(`/models/${model.id}/results`);
    }catch(failure){if(!abort.signal.aborted){setError(failure as Error);try{await saveRejectedAttempt(model.id,pin,failure,abort.signal);}catch(storageError){if(!abort.signal.aborted)setError(storageError as Error);}}}
    finally{if(controller.current===abort)setBusy(false);}
  }
  return <section className={styles.executionSelection}><h2>Flowsheet Solve data</h2><p>Each instance uses its recorded template data unless overridden below. Python validates the complete formulation.</p>
    {sheet.instances.map(instance=><details key={instance.id}><summary>{instance.id} · {instance.template}</summary>{Object.entries(instance.data).map(([id,value])=><label key={id}>{id} <input key={`${id}:${value.texto}`} defaultValue={value.texto} onBlur={event=>{if(event.target.value!==value.texto)editData(instance.id,id,event.target.value,value.unidad);}}/> {value.unidad}</label>)}</details>)}
    {model.flowsheetStale&&<p role="alert">stale_flowsheet_execution: The topology or data changed. Prepare the network again in Transform.</p>}
    {error&&<><p role="alert">{error.message}</p><AssessmentText error={error}/></>}
    {selected?<><p>{selected.report.selection.mode} · {selected.report.count} instances</p><button disabled={busy} onClick={()=>void run()}>{busy?'Solving the network…':'Solve network'}</button>{busy&&<button onClick={()=>controller.current?.abort()}>Cancel</button>}</>:<Link href={`/models/${model.id}/transform`}>Prepare the flowsheet in Transform →</Link>}
  </section>;
}
