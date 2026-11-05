'use client';
import IndexedTransform from './IndexedTransform';

import {useEffect,useState} from 'react';

import Link from 'next/link';

import type {HojaMotor} from '../motor/hojasMotor';

import {guardarHoja,leerHojas} from '../motor/hojasMotor';

import {describeCompilation} from '../../motores/modelo/servicioModelo';

import {readDerivedExecution,readDerivedExecutionSource,type TemporalDerivedExecution} from '../../motores/modelo/derivedExecution';

import {requestSteadyTransform} from '../../motores/modelo/steadyTransform';
import AssessmentText from './AssessmentText';
import EquationRows from './EquationRows';
import {commonSource,derivedSourceIdentity,applySteadyTransformResult} from './derivedSelection';

import {readEquationWorkbenchReport,type EquationWorkbenchReport} from './equationWorkbench';

import styles from './workspace.module.css';

import {requestFormulation} from './formulationRequests';



type Selection=Omit<TemporalDerivedExecution,'version'> & {version:1|2|3|4|5;unknowns?:string[];invariants?:Record<string,string>};
export default function DerivedExecution({model}:{model:HojaMotor}){
  return model.commonModel?.indexSet?<IndexedTransform model={model}/>:<OrdinaryDerivedExecution model={model}/>;
}
function OrdinaryDerivedExecution({model}:{model:HojaMotor}){

  const source=JSON.stringify(commonSource(model));

  const [loaded,setLoaded]=useState<{source:string;report:EquationWorkbenchReport;pin:string}>();

  const [draft,setDraft]=useState<Selection>(()=>({initialValues:{},initialEquations:[],...structuredClone(model.derivedSelection?.selection??model.commonModel?.motores.derivedExecution??{format:'rage.derived-execution',version:1,sourceSignature:'0'.repeat(64),timeId:'',states:[],parameters:{},initialValues:{},initialEquations:[],reconstructions:[],checks:[]})}));

  const [transformError,setTransformError]=useState<Error|null>(null);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[saved,setSaved]=useState(false);

  useEffect(()=>{const abort=new AbortController();void Promise.all((['equation-workbench','derived-execution-source'] as const).map(async endpoint=>{const response=await requestFormulation(endpoint,JSON.stringify({modelo:JSON.parse(source)}));const value=await response.json();if(!response.ok)throw new Error(value.detail?.message??'The graph could not be read.');return value;})).then(([raw,pin])=>{const report=readEquationWorkbenchReport(raw),signature=readDerivedExecutionSource(pin);if(report.modelId!==model.id||signature.modelId!==model.id)throw new Error('Unexpected formulation source.');if(!abort.signal.aborted)setLoaded({source,report,pin:signature.sourceSignature});}).catch(failure=>{if(!abort.signal.aborted)setError(failure.message);});return()=>abort.abort();},[source,model.id]);

  const current=loaded?.source===source?loaded:undefined;

  const equations=current?.report.equations??[],quantities=current?.report.quantities??[];

  const data=Object.keys(model.commonModel!.datos);

  function choose(value:string,options:{id:string;label:string}[],change:(value:string)=>void,label:string){return <select aria-label={label} value={value} onChange={event=>{change(event.target.value);setSaved(false);}}><option value="">Choose…</option>{options.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</select>;}

  const qs=quantities.map(q=>({id:q.id,label:`${q.name} · ${q.unit??'unknown unit'}`})),es=equations.map(row=>({id:row.id,label:`${row.id} · ${row.title}`})),ds=data.map(id=>({id,label:`${id} [${model.commonModel!.datos[id].declaracion.unidad}]`}));

  function pairs(name:'states'|'reconstructions'|'algebraic'){

    const rows=draft[name]??[];return <fieldset><legend>{name==='states'?'Retained states and derivative rows':name==='algebraic'?(draft.version>=3?'Coupled nonlinear block':'Coupled constant affine block'):'Algebraic reconstructions'}</legend>{rows.map((row,index)=><div key={index}>{choose(row.quantityId,qs,value=>setDraft({...draft,[name]:rows.map((item,i)=>i===index?{...item,quantityId:value}:item)}),`${name} quantity ${index+1}`)}{choose(row.equationId,es,value=>setDraft({...draft,[name]:rows.map((item,i)=>i===index?{...item,equationId:value}:item)}),`${name} equation ${index+1}`)}<button type="button" onClick={()=>setDraft({...draft,[name]:rows.filter((_,i)=>i!==index)})}>Remove {name} row {index+1}</button></div>)}<button type="button" onClick={()=>setDraft({...draft,[name]:[...rows,{quantityId:'',equationId:''}]})}>Add {name} row</button></fieldset>;

  }

  function bindings(name:'parameters'|'initialValues'|'scaling'|'invariants'){

    const entries=Object.entries(draft[name]??{});return <fieldset><legend>{name==='parameters'?'Parameter data':name==='initialValues'?'Initial data':name==='invariants'?'Explicit individual invariant values':'Optional positive multiplicative scales'}</legend>{entries.map(([quantity,datum],index)=><div key={index}>{choose(quantity,qs,value=>setDraft({...draft,[name]:Object.fromEntries(entries.map((row,i)=>i===index?[value,row[1]]:row))}),`${name} quantity ${index+1}`)}{choose(datum,ds,value=>setDraft({...draft,[name]:{...draft[name],[quantity]:value}}),`${name} datum ${index+1}`)}<button type="button" onClick={()=>setDraft({...draft,[name]:Object.fromEntries(entries.filter((_,i)=>i!==index))})}>Remove {name} binding {index+1}</button></div>)}<button type="button" onClick={()=>setDraft({...draft,[name]:{...draft[name],[''] :''}})}>Add {name} binding</button></fieldset>;

  }

  function nonlinearSettings(){

    const config=draft.nonlinear!;
    const rows=draft.version===5?[...draft.states.filter(row=>!Object.hasOwn(draft.invariants??{},row.quantityId)),...(draft.algebraic??[])]:draft.algebraic??[];

    const update=(next:NonNullable<Selection['nonlinear']>)=>{setDraft({...draft,nonlinear:next});setSaved(false);};

    return <fieldset><legend>Nonlinear Solve data</legend><p>Bind guesses, admissible bounds and positive scales to existing unit-bearing data. Guesses are not fixed initial constraints. A converged local root is not a global uniqueness certificate.</p>{rows.map(row=><div key={row.quantityId+row.equationId}>{(['seedDataId','lowerDataId','upperDataId','scaleDataId'] as const).map(key=><label key={key}>{row.quantityId} · {key}{choose(config.variables[row.quantityId]?.[key]??'',ds,value=>update({...config,variables:{...config.variables,[row.quantityId]:{...(config.variables[row.quantityId]??{seedDataId:'',lowerDataId:'',upperDataId:'',scaleDataId:''}),[key]:value}}}),`${row.quantityId} ${key}`)}</label>)}<label>{row.equationId} · residual scale{choose(config.residualScales[row.equationId]??'',ds,value=>update({...config,residualScales:{...config.residualScales,[row.equationId]:value}}),`${row.equationId} residual scale`)}</label></div>)}{(['residualTolerance','stepTolerance','maxIterations','maxBacktracks'] as const).map(key=><label key={key}>{key}<input aria-label={key} type="number" value={config[key]} onChange={event=>update({...config,[key]:Number(event.target.value)})}/></label>)}</fieldset>;

  }

  function daeSettings(){

    const config=draft.dae!;

    return <fieldset><legend>Index-one domain and drift</legend><p>BDF solves algebraic variables from given differential states. Bind every state initial value; free-state initialization and fully implicit systems are deferred.</p>{draft.states.map(row=><div key={row.quantityId}>{(['lowerDataId','upperDataId'] as const).map(key=><label key={key}>{row.quantityId} {key}{choose(config.stateBounds[row.quantityId]?.[key]??'',ds,value=>setDraft({...draft,dae:{...config,stateBounds:{...config.stateBounds,[row.quantityId]:{...(config.stateBounds[row.quantityId]??{lowerDataId:'',upperDataId:''}),[key]:value}}}}),`${row.quantityId} DAE ${key}`)}</label>)}</div>)}<label>Scaled constraint drift tolerance<input type="number" value={config.driftTolerance} onChange={event=>{setDraft({...draft,dae:{...config,driftTolerance:Number(event.target.value)}});setSaved(false);}}/></label></fieldset>;

  }

  async function save(){if(!current)return;const identity=derivedSourceIdentity(commonSource(model));setBusy(true);setError('');try{const selection:Partial<Selection>={...draft,sourceSignature:current.pin};const rows=draft.version===5?[...draft.states.filter(row=>!Object.hasOwn(draft.invariants??{},row.quantityId)),...(draft.algebraic??[])]:draft.algebraic??[];if(draft.version===5){delete selection.initialValues;delete selection.initialEquations;delete selection.scaling;delete selection.dae;selection.unknowns=rows.map(row=>row.quantityId);selection.invariants=draft.invariants??{};}else{delete selection.unknowns;delete selection.invariants;}if(selection.nonlinear){selection.nonlinear={...selection.nonlinear,variables:Object.fromEntries(rows.map(row=>[row.quantityId,selection.nonlinear!.variables[row.quantityId]])),residualScales:Object.fromEntries(rows.map(row=>[row.equationId,selection.nonlinear!.residualScales[row.equationId]]))};}if(selection.dae)selection.dae={...selection.dae,stateBounds:Object.fromEntries(draft.states.map(row=>[row.quantityId,selection.dae!.stateBounds[row.quantityId]]))};if(!selection.scaling||!Object.keys(selection.scaling).length)delete selection.scaling;const candidate=commonSource(model);const admitted=readDerivedExecution(selection,candidate.datos);candidate.motores.derivedExecution=admitted;if(admitted.version===5)candidate.estudio={tipo:'steady',version:1,metodoSolicitado:'damped_newton'};await describeCompilation(candidate);const latest=leerHojas().find(item=>item.id===model.id);if(!latest||derivedSourceIdentity(commonSource(latest))!==identity)throw new Error('The model changed during compilation. Review the selection again.');guardarHoja({...latest,transformation:undefined,derivedSelection:{version:1,sourceSignature:identity,selection:admitted},resultado:undefined,resultadoRef:undefined});setSaved(true);}catch(failure){setError((failure as Error).message);}finally{setBusy(false);}}

  async function applySteady(){
    const identity=JSON.stringify(model);setBusy(true);setTransformError(null);setSaved(false);
    try{
      const candidate=commonSource(model);
      const dynamic=model.derivedSelection?.selection.version!==5?model.derivedSelection?.selection:model.commonModel?.motores.derivedExecution;
      if(!dynamic||dynamic.version===5)throw new Error('Select a dynamic formulation first.');
      candidate.motores.derivedExecution=structuredClone(dynamic);
      const response=await requestSteadyTransform(candidate);
      const latest=leerHojas().find(item=>item.id===model.id);
      if(!latest||JSON.stringify(latest)!==identity)throw new Error('The model changed during the Transform. Apply it again.');
      guardarHoja(applySteadyTransformResult(latest,response));setSaved(true);
    }catch(failure){setTransformError(failure as Error);}finally{setBusy(false);}
  }

  const stale=model.derivedSelection&&model.derivedSelection.sourceSignature!==derivedSourceIdentity(commonSource(model));

  return <section className={styles.executionSelection} aria-label="Derived graph formulation"><h2>Derived graph formulation</h2><p>Select existing derivative rows, data and algebraic reconstructions. Python checks units, initialization and validity before connecting this formulation to Solve.</p><button disabled={busy||!current||!!stale} onClick={()=>void applySteady()}>Steady state (zero accumulation)</button><p>Uses the current dynamic rows. Initial values become Newton guesses; individually conserved states become explicit invariant bindings. Proposed bounds and scales are editable numerical defaults, not physical assumptions.</p>{transformError&&<><p role="alert">{transformError.message}</p><AssessmentText error={transformError}/></>}{model.derivedSelection?.steadyTransform&&<EquationRows label="Zero accumulation handoff" steps={model.derivedSelection.steadyTransform.rows.map(row=>({id:row.id,title:row.id,latex:row.before,description:`Zero accumulation: ${row.after}${row.identity?' · explicit invariant':''}`}))}/>}<p role="status">{stale?'Outdated selection · review after the model change':model.derivedSelection?'Selected derived formulation':'No derived formulation selected'}</p>{error&&<p role="alert">{error}</p>}{!current?<p>Reading the current equation graph…</p>:<details><summary>Review equation and data selection</summary><fieldset disabled={busy}><label>Time quantity{choose(draft.timeId,qs,value=>setDraft({...draft,timeId:value}),'Time quantity')}</label>{pairs('states')}{pairs('reconstructions')}<label>Algebraic method<select aria-label="Algebraic method" value={draft.version} onChange={event=>{const version=Number(event.target.value) as 1|2|3|4|5;const next={...draft,version};if(version===1)delete next.algebraic;else next.algebraic??=[];if(version>=3)next.nonlinear??={variables:{},residualScales:{},residualTolerance:1e-10,stepTolerance:1e-12,maxIterations:30,maxBacktracks:20};else delete next.nonlinear;if(version===4)next.dae??={stateBounds:{},driftTolerance:1e-9};else delete next.dae;if(version===5)next.invariants??={};setDraft(next);setSaved(false);}}><option value={1}>Explicit reconstructions</option><option value={2}>Constant affine block</option><option value={3}>Nonlinear block · damped Newton</option><option value={4}>Semi-explicit index-1 DAE - BDF</option><option value={5}>Steady residual - damped Newton</option></select></label>{draft.version!==1&&pairs('algebraic')}{draft.version>=3&&nonlinearSettings()}{draft.version===4&&daeSettings()}{bindings('parameters')}{draft.version===5?bindings('invariants'):bindings('initialValues')}{draft.version!==5&&<fieldset><legend>Initialization equations</legend>{draft.initialEquations.map((id,index)=><div key={index}>{choose(id,es,value=>setDraft({...draft,initialEquations:draft.initialEquations.map((row,i)=>i===index?value:row)}),`Initialization equation ${index+1}`)}<button onClick={()=>setDraft({...draft,initialEquations:draft.initialEquations.filter((_,i)=>i!==index)})}>Remove initialization equation {index+1}</button></div>)}<button onClick={()=>setDraft({...draft,initialEquations:[...draft.initialEquations,'']})}>Add initialization equation</button></fieldset>}<fieldset><legend>Conservation checks</legend>{draft.checks.map((row,index)=><div key={index}>{choose(row.equationId,es,value=>setDraft({...draft,checks:draft.checks.map((item,i)=>i===index?{...item,equationId:value}:item)}),`Conservation equation ${index+1}`)}{choose(row.scaleDataId,ds,value=>setDraft({...draft,checks:draft.checks.map((item,i)=>i===index?{...item,scaleDataId:value}:item)}),`Conservation scale ${index+1}`)}<button onClick={()=>setDraft({...draft,checks:draft.checks.filter((_,i)=>i!==index)})}>Remove conservation check {index+1}</button></div>)}<button onClick={()=>setDraft({...draft,checks:[...draft.checks,{equationId:'',scaleDataId:''}]})}>Add conservation check</button></fieldset>{draft.version!==5&&bindings('scaling')}</fieldset></details>}<button className={styles.primary} disabled={!current||busy} onClick={()=>void save()}>{busy?'Checking compilation…':'Validate and use derived formulation'}</button>{saved&&<p role="status">Selected for execution. <Link href={`/models/${model.id}/solve`}>Continue to Solve →</Link></p>}</section>;

}

