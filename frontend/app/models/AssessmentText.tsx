'use client';
import {useEffect,useState} from 'react';
import type {HojaMotor} from '../motor/hojasMotor';
import {assessmentLines,ModelDiagnosticError,type ModelAssessment} from '../../motores/modelo/assessment';
import {requestAssessment} from '../../motores/modelo/servicioModelo';
import {modelRequest} from './modelRequest';

/** Inline evidence inside existing workspaces; owns no panel or layout. */
export default function AssessmentText({assessment,error}:{assessment?:ModelAssessment;error?:Error}){
  const typed=error instanceof ModelDiagnosticError?error:undefined;
  const value=assessment??typed?.assessment;
  return <>{assessmentLines(value).map((line,index)=><p key={index}>{line}</p>)}
    {value?.certification.scope.samples!==undefined&&<p>Published scope · {String(value.certification.scope.samples)} samples · {String(value.certification.scope.startSI)}–{String(value.certification.scope.endSI)} s · {value.certification.scope.complete?'complete':'partial'}</p>}
    {typed&&!value&&<>{typed.code&&<p>{typed.code} · {typed.path??'modelo'} · HTTP {typed.httpStatus}</p>}{typed.diagnostics.map((d,index)=><p key={index}>{d.code} · {d.path}: {d.message}</p>)}</>}
  </>;
}

export function ModelAssessmentText({model}:{model:HojaMotor}){
  let body='';
  try{
    // Draft inspection must not pass through the strict executable reader.
    // Preserve absent data; omit only the selected numerical lowering in Model.
    const source=model.commonModel?{modelo:{...model.commonModel,id:model.id,nombre:model.nombre,
      motores:{...model.commonModel.motores,derivedExecution:undefined}}}:modelRequest(model);
    if('modelo' in source)body=JSON.stringify(source.modelo);
  }catch{/* Unbound symbolic models have no executable assessment request. */}
  const [state,setState]=useState<{body:string;assessment?:ModelAssessment;error?:Error}|null>(null);
  useEffect(()=>{
    if(!body)return;
    const controller=new AbortController();
    requestAssessment(JSON.parse(body),controller.signal,false).then(assessment=>{if(!controller.signal.aborted)setState({body,assessment});})
      .catch(error=>{if(!controller.signal.aborted)setState({body,error});});
    return()=>controller.abort();
  },[body]);
  const current=state?.body===body?state:null;
  return <>{current?.error&&<p role="alert">{current.error.message}</p>}{current?<AssessmentText assessment={current.assessment} error={current.error}/>:<p>Structure · Not evaluated{body?' · inspecting current model':' · no common numerical model bound'}. Initialization and certification are evaluated in Solve and Results.</p>}</>;
}
