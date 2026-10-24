'use client';
import {useEffect,useState} from 'react';
import {usePhysicalModel} from './DynamicModelDefinition';
import {modelRequest} from './modelRequest';
import {diagnosticView,readModelDiagnostics,type ModelDiagnostic} from './modelDiagnostics';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import styles from './equationWorkbench.module.css';

/** Compiler admission is distinct from recorded history and physical validity. */
export default function ModelReadiness(){
  const model=usePhysicalModel();
  let source='',preparation='';try{if(model?.hydraulicNetwork)source=JSON.stringify(modelRequest(model));}catch(error){preparation=(error as Error).message;}
  const [state,setState]=useState<{source:string;issues:ModelDiagnostic[];error?:string}>();
  useEffect(()=>{
    if(!source)return;
    const controller=new AbortController();
    void fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/hydraulics/admission`,{method:'POST',headers:{'Content-Type':'application/json'},body:source,signal:AbortSignal.any([controller.signal,AbortSignal.timeout(20000)])}).then(async response=>{
      const body=await response.json();const issues=readModelDiagnostics(body.detail?.diagnostics);
      if(response.ok&&(body.format!=='rage.model-admission'||body.version!==1||body.modelId!==JSON.parse(source).modelo.id))throw new Error('Invalid physical admission response.');
      if(!controller.signal.aborted)setState({source,issues,...(!response.ok?{error:body.detail?.message??'Compatibility could not be checked.'}:{})});
    }).catch(error=>{if(!controller.signal.aborted)setState({source,issues:[],error:error.message});});
    return()=>controller.abort();
  },[source]);
  if(!model?.hydraulicNetwork)return null;
  if(preparation)return <p className={styles.readiness} role="alert">{preparation}</p>;
  const current=state?.source===source?state:undefined;
  return <details className={styles.readiness} open={!!current?.error}><summary>{!current?'Checking execution requirements':current.error?'Review before Solve':'Physical reduction supported'}</summary>
    <p>This checks physical assumptions against the available compiler. Numerical data and initialization are checked in Solve; this is not a physical-validity certificate.</p>
    {current?.issues.length?<ul>{current.issues.map(issue=><li key={`${issue.ownerId}.${issue.code}`}><button onClick={()=>{const latest=leerHojas().find(item=>item.id===model.id);if(latest)guardarHoja({...latest,volumenActivo:issue.ownerId,vistaBalance:diagnosticView(issue.family)});}}>{model.ensamblaje?.volumenes.find(volume=>volume.id===issue.ownerId)?.nombre??issue.ownerId} · {issue.family}</button><p>{issue.message}</p></li>)}</ul>:current?.error?<p role="alert">{current.error}</p>:<p>Review numerical values and methods in Solve.</p>}
  </details>;
}
