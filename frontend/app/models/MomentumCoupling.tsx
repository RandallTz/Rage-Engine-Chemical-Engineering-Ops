'use client';
import { useEffect, useState } from 'react';
import { usePhysicalModel } from './DynamicModelDefinition';
import { momentumJournalOf, readMomentumDevelopment, type MomentumDevelopment } from './momentumDerivation';
import { modelRequest } from './modelRequest';
import EquationRows from './EquationRows';
import { panelDeEcuacion } from '../motor/ubicacionEcuaciones';

/** The same Python deduction supplies each equation to its physical family. */
export default function MomentumCoupling({family}:{family:'materia'|'energia'|'termodinamica'|'momento'}){
  const model=usePhysicalModel();let source='';
  try{if(model&&family!=='momento'&&momentumJournalOf(model))source=JSON.stringify(modelRequest(model));}catch{/* Model reader reports invalid evidence. */}
  const [state,setState]=useState<{source:string;developments?:MomentumDevelopment[];error?:string}>();
  useEffect(()=>{
    if(!source)return;const abort=new AbortController();
    const request=JSON.parse(source),volumes='modelo'in request?request.modelo.volumenes:request.solicitudV2.volumenes;
    const active=volumes.filter((volume:{balances:{momento:boolean}})=>volume.balances.momento);
    void Promise.all(active.map(async(volume:{id:string})=>{
      const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/momentum-derivation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...request,volumeId:volume.id}),cache:'no-store',signal:AbortSignal.any([abort.signal,AbortSignal.timeout(20000)])});
      const body=await response.json();if(!response.ok)throw new Error(body?.detail?.message??'Momentum coupling is unavailable.');const development=readMomentumDevelopment(body.development);if(development.volumeId!==volume.id)throw new Error('Unexpected momentum coupling owner.');return development;
    })).then(developments=>{if(!abort.signal.aborted)setState({source,developments});}).catch(failure=>{if(!abort.signal.aborted)setState({source,error:(failure as Error).message});});
    return()=>abort.abort();
  },[source]);
  const current=state?.source===source?state:undefined;
  if(!source||family==='momento')return null;
  const rows=current?.developments?.flatMap(development=>development.couplingSteps.filter(step=>panelDeEcuacion({id:step.id,familia:step.family})===family).map(step=>({...step,id:`${development.volumeId}:${step.id}`,title:`${development.volumeId} · ${step.title}`})))??[];
  if(current?.error)return <p role="alert">{current.error}</p>;
  return rows.length?<section aria-label="Relations coupled from momentum"><h2>Mechanical coupling</h2><EquationRows steps={rows}/></section>:null;
}
