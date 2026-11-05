'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import type {HojaMotor} from '../motor/hojasMotor';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import {prepareIndexedExecution} from '../../motores/modelo/indexedExecution';
import {applyIndexed,currentIndexed,indexedSource} from './indexedSelection';
import AssessmentText from './AssessmentText';
import EquationRows from './EquationRows';
import styles from './workspace.module.css';

export default function IndexedTransform({model}:{model:HojaMotor}){
  const controller=useRef<AbortController|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<Error|null>(null);
  const source=JSON.stringify(indexedSource(model)),current=currentIndexed(model);
  useEffect(()=>()=>controller.current?.abort(),[source]);
  async function prepare(mode:'dynamic'|'steady'){
    const abort=new AbortController();controller.current?.abort();controller.current=abort;setBusy(true);setError(null);
    try{const report=await prepareIndexedExecution(indexedSource(model),mode,abort.signal);
      const latest=leerHojas().find(row=>row.id===model.id);if(!latest)throw new Error('The model is no longer available.');
      abort.signal.throwIfAborted();guardarHoja(applyIndexed(latest,report));
    }catch(failure){if(!abort.signal.aborted)setError(failure as Error);}finally{setBusy(false);}
  }
  return <section className={styles.executionSelection}><h2>Indexed network formulation</h2>
    <p>Use the recorded generic stage and its declared connections. Python validates the complete network.</p>
    <button disabled={busy} onClick={()=>void prepare('dynamic')}>Validate and use dynamic formulation</button>
    <button disabled={busy} onClick={()=>void prepare('steady')}>Steady state (zero accumulation)</button>
    {busy&&<p role="status">Preparing the connected equations…</p>}
    {error&&<><p role="alert">{error.message}</p><AssessmentText error={error}/></>}
    {current?<><p role="status">{current.report.count} stages · {current.report.selection.mode} · {current.report.rateRows.length} original rate rows</p>
      {current.report.selection.mode==='steady'&&current.report.stages.map(stage=>stage.steadyReport?.version===2&&<EquationRows key={stage.index} label={`Stage ${stage.index}: zero accumulation`} steps={stage.steadyReport.rows.map(row=>({id:row.id,title:row.id,latex:row.before,description:`Zero accumulation: ${row.after}`}))}/>)}
      <p>Changing the model, count or Solve data invalidates this selection and its results.</p><Link href={`/models/${model.id}/solve`}>Continue to Solve →</Link></>:<p>No current indexed formulation selected.</p>}
  </section>;
}
