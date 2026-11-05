'use client';
import {useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import type {HojaMotor} from '../motor/hojasMotor';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import type {IndexSetExpansion} from '../../motores/modelo/indexSets';
import {changeStageCount,expandStages} from './indexSetSolve';
import {currentIndexed,indexedSource,indexedResult} from './indexedSelection';
import {solveIndexedExecution} from '../../motores/modelo/indexedExecution';
import {firmaHoja} from '../motor/modeloHojaMotor';
import {guardarResultadoMotor,saveRejectedAttempt} from '../motor/resultadosMotor';
import AssessmentText from './AssessmentText';
import styles from '../motor/trabajoMotor.module.css';

export default function IndexedStageSolve({model}:{model:HojaMotor}){
  const router=useRouter(),controller=useRef<AbortController|null>(null),[busy,setBusy]=useState(false),selected=currentIndexed(model);
  const set=model.commonModel!.indexSet!,datum=model.commonModel!.datos[set.countDataId];
  const signature=JSON.stringify(model.commonModel),[draft,setDraft]=useState(datum.declaracion.texto),[error,setError]=useState<Error|null>(null);
  const [published,setPublished]=useState<{signature:string;expansion:IndexSetExpansion;rejection?:Error}>();
  useEffect(()=>{setDraft(datum.declaracion.texto);const controller=new AbortController();
    expandStages(model,controller.signal).then(async expansion=>{
      if(!controller.signal.aborted)setPublished({signature,expansion});
    }).catch(e=>{if(!controller.signal.aborted)setError(e as Error);});return()=>controller.abort();
  // Identity is the complete input, so stale responses never replace newer data.
  },[signature,model.id]);
  useEffect(()=>()=>controller.current?.abort(),[signature,model.indexedSelection]);
  async function run(){
    if(!selected)return;const abort=new AbortController();controller.current=abort;setBusy(true);setError(null);
    const pin=firmaHoja(model);
    try{const common=await solveIndexedExecution(indexedSource(model),selected.report.selection,abort.signal);
      const latest=leerHojas().find(row=>row.id===model.id);if(!latest||firmaHoja(latest)!==pin)throw new Error('The model changed; the outdated result was discarded.');
      const result=indexedResult(latest,common,pin);abort.signal.throwIfAborted();await guardarResultadoMotor(model.id,result,abort.signal);
      const saved=leerHojas().find(row=>row.id===model.id);if(!saved||firmaHoja(saved)!==pin)throw new Error('The model changed while saving.');
      guardarHoja({...saved,resultado:undefined,resultadoRef:{firma:pin,estado:result.estado,fecha:new Date().toISOString()}});router.push(`/models/${model.id}/results`);
    }catch(failure){if(!abort.signal.aborted){setError(failure as Error);try{await saveRejectedAttempt(model.id,pin,failure,abort.signal);}catch(storageError){if(!abort.signal.aborted)setError(storageError as Error);}}}
    finally{setBusy(false);}
  }
  function edit(text:string){setDraft(text);setError(null);try{
    const latest=leerHojas().find(row=>row.id===model.id);if(!latest)throw new Error('The model is no longer available.');
    guardarHoja(changeStageCount(latest,text));
  }catch(e){setError(e as Error);}}
  const current=published?.signature===signature?published:undefined;
  return <section className={styles.page}><h2>Indexed stage Solve data</h2>
    <fieldset><legend>Declared data</legend><label>{set.countDataId}<input aria-label={`Value ${set.countDataId}`} type="number" min={1} max={256} step={1} value={draft} onChange={e=>edit(e.target.value)}/></label><p>Unit: 1 · Integer stage count. Changing n clears Transform selections and results.</p></fieldset>
    {error&&<><p role="alert">{error.message}</p><AssessmentText error={error}/></>}
    {!current?<p role="status">Expanding recorded stages…</p>:<><p>Expanded stages: {current.expansion.count}</p><ul>{current.expansion.ports.map(({port})=><li key={port.id}>{port.id} · {port.kind} {port.direction}</li>)}</ul>
    {current.rejection&&<><p role="alert">{current.rejection.message}</p><AssessmentText error={current.rejection}/></>}</>}
    {selected?<><p>Selected {selected.report.selection.mode} network · {selected.report.rateRows.length} original rate rows · {selected.report.method}</p><button disabled={busy} onClick={()=>void run()}>{busy?'Solving connected stages…':'Solve network'}</button>{busy&&<button onClick={()=>controller.current?.abort()}>Cancel</button>}</>:<p><Link href={`/models/${model.id}/transform`}>Prepare the indexed formulation in Transform.</Link></p>}
  </section>;
}
