'use client';
import IndexedStageSolve from './IndexedStageSolve';
import {FlowsheetSolve} from './FlowsheetWorkspace';
import {inverseTransport} from '../../motores/modelo/servicioModelo';
import {inverseDataIds,readInverseSolve,type InverseSolve} from '../../motores/modelo/inverseSpecification';
import {requestFormulation} from './formulationRequests';
import {readEquationWorkbenchReport,type EquationWorkbenchReport} from './equationWorkbench';
import {commonSource} from './derivedSelection';
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
  const [busy,setBusy]=useState(false),[error,setError]=useState<Error|null>(null),[failureSignature,setFailureSignature]=useState('');
  useEffect(()=>()=>controller.current?.abort(),[]);
  const common=model.commonModel!;let unavailable='';try{selectedDerivedModel(model);}catch(failure){unavailable=(failure as Error).message;}
  function change(edit:(source:NonNullable<HojaMotor['commonModel']>)=>NonNullable<HojaMotor['commonModel']>){controller.current?.abort();const latest=leerHojas().find(item=>item.id===model.id);if(latest?.commonModel)guardarHoja({...latest,commonModel:edit(latest.commonModel),resultado:undefined,resultadoRef:undefined});}
  async function run(){const abort=new AbortController();controller.current=abort;setBusy(true);setError(null);try{const result=await resolverHojaEngine(model,{signal:abort.signal,...(model.derivedSelection?.inverseSolve?{transporte:inverseTransport(model.derivedSelection.inverseSolve.record)}:{})});const latest=leerHojas().find(item=>item.id===model.id);if(!latest||firmaHoja(latest)!==result.firma)throw new Error('The model changed; the outdated result was discarded.');abort.signal.throwIfAborted();await guardarResultadoMotor(model.id,result,abort.signal);const saved=leerHojas().find(item=>item.id===model.id);if(!saved||firmaHoja(saved)!==result.firma)throw new Error('The model changed while saving.');guardarHoja({...saved,resultado:undefined,resultadoRef:{firma:result.firma,estado:result.estado,fecha:new Date().toISOString()}});router.push(`/models/${model.id}/results`);}catch(failure){if(!abort.signal.aborted&&leerHojas().some(item=>item.id===model.id&&firmaHoja(item)===firmaHoja(model))){setError(failure as Error);setFailureSignature(firmaHoja(model));try{await saveRejectedAttempt(model.id,firmaHoja(model),failure,abort.signal);}catch(storageError){if(!abort.signal.aborted)setError(Object.assign(failure as Error,{message:(failure as Error).message+' '+(storageError as Error).message}));}}}finally{setBusy(false);}}
  function changeInverse(inverseSolve:InverseSolve|undefined){controller.current?.abort();const latest=leerHojas().find(item=>item.id===model.id);if(latest?.derivedSelection)guardarHoja({...latest,derivedSelection:{...latest.derivedSelection,inverseSolve},resultado:undefined,resultadoRef:undefined});}
  const study=common.estudio;
  return <section className={styles.page}><h2>{model.derivedSelection?.selection.version===5?'Steady-state data and solve':'Numerical data and integration'}</h2>{model.derivedSelection?.selection.version===5&&<p>Damped Newton solves the original derived residuals at zero rates. Invariant bindings are fixed; seeds are guesses. A regular local root does not prove global uniqueness or dynamic stability.</p>}<p>These data bind the selected derived quantities. Changing a value or unit requires reviewing its dependent formulation in Transform.</p>{unavailable&&<p role="alert">{unavailable} <Link href={`/models/${model.id}/transform`}>Review Transform</Link></p>}{error&&failureSignature===firmaHoja(model)&&<><p role="alert">{error.message}</p><AssessmentText error={error}/><Link href={`/models/${model.id}/results`}>Review rejected attempt in Results</Link></>}<fieldset disabled={busy}><legend>Declared data</legend>{Object.entries(common.datos).map(([id,datum])=><div className={styles.field} key={id}><label htmlFor={'derived-'+id}>{id}</label><div className={styles.entry}><input id={'derived-'+id} aria-label={`Value ${id}`} value={datum.declaracion.texto} onChange={event=>change(source=>({...source,datos:{...source.datos,[id]:{...datum,declaracion:{...datum.declaracion,texto:event.target.value}}}}))}/><input aria-label={`Unit ${id}`} value={datum.declaracion.unidad} onChange={event=>change(source=>({...source,datos:{...source.datos,[id]:{...datum,declaracion:{...datum.declaracion,unidad:event.target.value}}}}))}/></div></div>)}</fieldset>{quantityError?.source===source&&<p role="alert">{quantityError.message}</p>}{steady&&<InverseControls model={model} quantities={quantities?.source===source?quantities.rows:[]} disabled={busy} change={changeInverse}/>} {model.derivedSelection?.selection.version!==5&&study?.tipo==='temporal'&&<fieldset disabled={busy}><legend>Integration settings</legend><label>Method<select aria-label="Derived integration method" value={study.metodoSolicitado??'rk45'} onChange={event=>change(source=>({...source,estudio:{...study,metodoSolicitado:event.target.value as typeof study.metodoSolicitado}}))}><option value="rk45">RK45</option><option value="bdf">BDF</option></select></label><label>Samples<input aria-label="Derived samples" type="number" min={2} value={study.muestras} onChange={event=>change(source=>({...source,estudio:{...study,muestras:Number(event.target.value)}}))}/></label><label>Relative tolerance<input aria-label="Derived relative tolerance" type="number" value={study.rtol} onChange={event=>change(source=>({...source,estudio:{...study,rtol:Number(event.target.value)}}))}/></label>{Object.entries(study.atol).map(([key,value])=><label key={key}>Absolute tolerance · {key}<input aria-label={`Derived absolute tolerance ${key}`} type="number" value={value} onChange={event=>change(source=>({...source,estudio:{...study,atol:{...study.atol,[key]:Number(event.target.value)}}}))}/></label>)}</fieldset>}<button className={styles.primary} disabled={busy||!!unavailable} onClick={()=>void run()}>{busy?'Solving…':'Run derived model'}</button>{busy&&<button onClick={()=>controller.current?.abort()}>Cancel request</button>}</section>;
}

/** Shared Solve controls over existing quantities; SI values are declared data. */
export function InverseControls({model,quantities,disabled,change}:{model:HojaMotor;quantities:EquationWorkbenchReport['quantities'];disabled:boolean;change:(value:InverseSolve|undefined)=>void}){
  const selection=model.derivedSelection!.selection;if(selection.version!==5)return null;
  const solve=model.derivedSelection?.inverseSolve;
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
  return <fieldset disabled={disabled}><legend>Inverse specifications</legend><p>Choose an output target and the constant input Newton frees. Supply guesses, admissible bounds and positive scales in the displayed SI units. Model and Transform stay unchanged.</p>
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
