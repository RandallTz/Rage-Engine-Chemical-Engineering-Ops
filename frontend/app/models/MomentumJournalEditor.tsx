'use client';
import { useEffect, useRef, useState } from 'react';
import type { HojaMotor } from '../motor/hojasMotor';
import { modelRequest } from './modelRequest';
import { momentumJournalOf, readMomentumJournal, readMomentumDevelopment, withMomentumJournal, includeMomentum, type MomentumDevelopment } from './momentumDerivation';
import RecordedDerivation from './RecordedDerivation';
import EquationRows from './EquationRows';
import { MomentumAssumptions } from '../motor/ModelAssumptions';
import { ModelVolumeTabs } from './ModelWorksheet';
import FormulaMateria from '../motor/FormulaMateria';
import styles from '../motor/motor.module.css';

export default function MomentumJournalEditor({ model, save }: { model:HojaMotor;save:(change:(current:HojaMotor)=>HojaMotor)=>boolean }) {
  const [result,setResult]=useState<{source:string;development:MomentumDevelopment}>();
  const [pending,setPending]=useState(false),[error,setError]=useState(''),[inlet,setInlet]=useState(''),[outlet,setOutlet]=useState('');
  const controller=useRef<AbortController|null>(null);
  let request:ReturnType<typeof modelRequest>|undefined,invalid='';
  try{request=modelRequest(model);}catch(failure){invalid=(failure as Error).message;}
  const volumes=request?.modelo?.volumenes??request?.solicitudV2?.volumenes??[];
  const volume=volumes.find(item=>item.id===model.volumenActivo)??volumes[0];
  const source=JSON.stringify(request),owner=volume?.id;
  const current=result?.source===source&&result.development.volumeId===owner?result:undefined;
  useEffect(()=>{
    controller.current?.abort();if(!request||!owner)return;
    const abort=new AbortController();controller.current=abort;
    void fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/momentum-derivation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...JSON.parse(source),volumeId:owner}),cache:'no-store',signal:AbortSignal.any([abort.signal,AbortSignal.timeout(20000)])}).then(async response=>{
      const body=await response.json();if(!response.ok)throw new Error(body?.detail?.message??'Momentum development is unavailable.');
      const development=readMomentumDevelopment(body.development);if(body.journal!==null)readMomentumJournal(body.journal);
      if(development.volumeId!==owner)throw new Error('Unexpected momentum development owner.');
      if(!abort.signal.aborted){setResult({source,development});setError('');}
    }).catch(failure=>{if(!abort.signal.aborted)setError((failure as Error).message);});
    return()=>abort.abort();
    // The serialized request owns all scientific dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[source,owner]);
  async function apply(action:{kind:string;index?:number;inletStreamId?:string|null;outletStreamId?:string|null;name?:string;value?:boolean}){
    if(!owner||!request||pending)return;
    controller.current?.abort();const abort=new AbortController();controller.current=abort;setPending(true);setError('');
    try{
      const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/momentum-derivation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...JSON.parse(source),volumeId:owner,action}),cache:'no-store',signal:AbortSignal.any([abort.signal,AbortSignal.timeout(20000)])});
      const body=await response.json();if(!response.ok)throw new Error(body?.detail?.message??'Momentum operation was rejected.');
      const journal=readMomentumJournal(body.journal),development=readMomentumDevelopment(body.development);
      if(development.volumeId!==owner)throw new Error('Unexpected momentum operation owner.');
      if(!abort.signal.aborted&&!save(latest=>{if(JSON.stringify(modelRequest(latest))!==source)throw new Error('The physical model changed. The outdated deduction was discarded.');return withMomentumJournal(latest,journal);} ))throw new Error('The momentum operation could not be saved.');
    }catch(failure){if(!abort.signal.aborted)setError((failure as Error).message);}finally{setPending(false);}
  }
  const streams=request?.modelo?.corrientes??request?.solicitudV2?.corrientes??[];
  let journal;try{journal=momentumJournalOf(model);}catch{/* Reader/server reports invalid evidence. */}
  const entry=owner?journal?.volumes[owner]:undefined;
  return <div className={styles.page}>
    <header className={styles.header}><span className={styles.eyebrow}>{model.nombre}</span><h2 className={styles.tituloBalance}>Momentum balance</h2></header>
    {volumes.length>1&&volume&&<ModelVolumeTabs volumes={volumes.map(item=>({id:item.id,name:model.redTermodinamica?.nombres[`volumen:${item.id}`]??model.ensamblaje?.volumenes.find(v=>v.id===item.id)?.nombre??item.id}))} active={volume.id} select={id=>save(latest=>({...latest,volumenActivo:id}))}/>}
    <RecordedDerivation family="Momentum" steps={current?.development.steps} notes={current?.development.notes} preview={!entry} startDescription="Fundamental Cauchy preview. Start explicitly to record reductions; any previous unrecorded momentum flags are preserved as archived source data." pending={pending} canUndo={!!entry?.operations.length} undo={()=>void apply({kind:'undo'})} start={!entry&&owner?()=>void apply({kind:'start'}):undefined} error={error||invalid} rebuilt={entry?.origin==='reviewed_rebuild'}
      sidebar={<>
        {entry&&<fieldset className={styles.operationGroup}><legend>Physical changes</legend><div className={styles.boundaryActions}><button disabled={pending||(entry.cursor??entry.operations.length)===0} onClick={()=>void apply({kind:'seek',index:(entry.cursor??entry.operations.length)-1})}>Undo last assumption</button><button disabled={pending||(entry.cursor??entry.operations.length)===entry.operations.length} onClick={()=>void apply({kind:'seek',index:(entry.cursor??entry.operations.length)+1})}>Redo assumption</button></div><p className={styles.groupHint}>Undo reverses one physical change. Reading the equations on the left leaves your model unchanged.</p><details><summary>Recorded physical assumptions · {entry.cursor??entry.operations.length}</summary><ol><li>Fundamental Cauchy law</li>{entry.operations.slice(0,entry.cursor??entry.operations.length).map(op=><li key={op.id}>{op.title}</li>)}</ol>{(entry.cursor??entry.operations.length)<entry.operations.length&&<p>Later changes remain available to redo. A new change replaces that redo branch.</p>}</details></fieldset>}
        {volume&&<label className={styles.smallOption}><input type="checkbox" aria-label="Include momentum for this volume" checked={volume.balances.momento} disabled={pending} onChange={event=>save(latest=>includeMomentum(latest,volume.id,event.target.checked))}/><span>Include momentum in this model<small>Solve checks the supported compiler scope. Unsupported momentum terms remain blocked.</small></span></label>}
        <fieldset className={styles.assumptionControls} disabled={pending||!entry}>
          <MomentumAssumptions development={current?.development} disabled={!entry||pending} change={(name,value)=>void apply({kind:'set_assumption',name,value})} represent={kind=>void apply({kind})}/>
          <fieldset className={styles.operationGroup}><legend>Shared material ports</legend><label className={styles.diffusionChoice}>Nominal inlet<select aria-label="Momentum inlet stream" value={inlet} onChange={event=>setInlet(event.target.value)}><option value="">Select an existing inlet</option>{streams.filter(stream=>stream.hasta===owner&&stream.desde!==owner).map(stream=><option key={stream.id}>{stream.id}</option>)}</select></label><label className={styles.diffusionChoice}>Nominal outlet<select aria-label="Momentum outlet stream" value={outlet} onChange={event=>setOutlet(event.target.value)}><option value="">Select an existing outlet</option>{streams.filter(stream=>stream.desde===owner&&stream.hasta!==owner).map(stream=><option key={stream.id}>{stream.id}</option>)}</select></label><button disabled={!inlet||!outlet||inlet===outlet} onClick={()=>void apply({kind:'bind_ports',inletStreamId:inlet,outletStreamId:outlet})}>Bind existing ports</button><button onClick={()=>void apply({kind:'bind_ports',inletStreamId:null,outletStreamId:null})}>Unbind ports</button><p className={styles.groupHint}>Recorded: {current?.development.bindings.inletStreamId??'unbound'} → {current?.development.bindings.outletStreamId??'unbound'}. Pressure, flow, composition and enthalpy keep their common identity.</p></fieldset>
        </fieldset>
        {current?.development.requirements.length?<details className={styles.integrationBridge}><summary>Coupling requirements · {current.development.requirements.length}</summary>{current.development.requirements.map(item=><p key={item.code}>{item.message}</p>)}</details>:null}
        <p className={styles.groupHint}>Density and state assumptions belong to Thermodynamics. Continuity appears in Matter; shaft power and ideal head appear in Energy. No real pump curve, viscosity, slip or efficiency is invented.</p>
      </>}
      result={current&&<section aria-label="Deduced momentum formulation"><h2>Deduced momentum formulation</h2><EquationRows steps={current.development.finalSteps}/></section>}
      variables={current&&<section id="variables-materia" tabIndex={-1} className={`${styles.symbols} ${styles.variablesSection}`} aria-label="Momentum variables and units"><header><h2>Variables</h2><span>Momentum · units & roles</span></header><dl>{current.development.variables.map(item=><div key={item.id}><dt><FormulaMateria latex={item.symbol} lectura={item.name}/></dt><dd>{item.name}<span>{item.unit} · {item.role.replaceAll('_',' ')}</span></dd></div>)}</dl></section>}/>
  </div>;
}
