'use client';
import {useState} from 'react';
import type {HojaMotor} from '../motor/hojasMotor';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import {readKineticReactions,type KineticVolume,type KineticReaction} from './kineticReactions';
import {readEquationWorkbenchReport} from './equationWorkbench';
import {requestMaterialDevelopment,emptyMaterialJournal} from '../motor/materialDerivation';
import styles from '../motor/motor.module.css';

/** Declarations in the existing assumptions panel; Python owns all science. */
export default function ReactionControls({model}:{model:HojaMotor}){
  const common=model.commonModel;
  const [owner,setOwner]=useState(common?.volumenes[0]?.id??'');
  if(!common)return null;
  if(common.motores.equilibriumReactions)return <details><summary>Equilibrium reaction constraints</summary>{Object.entries(common.motores.equilibriumReactions.volumes).map(([id,entry])=><section key={id}><h4>{id}</h4><p>Recorded phase: {entry.phaseId}. Formation anchor: {entry.anchor}. Standard state: {entry.standardState}.</p><p>Provider: {entry.provider}. Chemical potentials include formation energy; no additional reaction heat is added.</p><p>{entry.extentIds.length} independent extents. Whole-domain certification is required before index-one execution.</p><ul>{entry.reactions.map(reaction=><li key={reaction.id}>{reaction.id} · {reaction.equationId}</li>)}</ul><p>Edit the recorded Gibbs variations and coordinate definitions with the shared equation operations. Physical edits invalidate the selected formulation.</p></section>)}</details>;
  return <details><summary>Kinetic reactions</summary><p className={styles.groupHint}>Declare concentration laws, then substitute their source definitions into the component laws with the equation tools. Chemical equilibrium is pending.</p><label>Physical region<select value={owner} onChange={e=>setOwner(e.target.value)}>{common.volumenes.filter(v=>v.balances.materia).map(v=><option key={v.id} value={v.id}>{v.id}</option>)}</select></label>{common.volumenes.some(v=>v.id===owner)&&<ReactionForm key={owner+JSON.stringify(common.motores.kineticReactions??null)} model={model} owner={owner}/>}</details>;
}

function ReactionForm({model,owner}:{model:HojaMotor;owner:string}){
  const common=model.commonModel!,volume=common.volumenes.find(v=>v.id===owner)!,existing=common.motores.kineticReactions?.volumes[owner];
  const [selected,setSelected]=useState(existing?.reactions[0]?.id??''),[id,setId]=useState(existing?.reactions[0]?.id??''),[volumeId,setVolumeId]=useState((existing&&'volumeDataId' in existing?existing.volumeDataId:undefined)??(volume.frontera.tipo==='rigida'?volume.frontera.datoId:''));
  const [masses,setMasses]=useState(existing?.molarMassDataIds??{}),[nu,setNu]=useState(existing?.reactions[0]?.stoichiometry??{}),[orders,setOrders]=useState<Record<string,string>>(Object.fromEntries(Object.entries(existing?.reactions[0]?.orders??{}).map(([c,n])=>[c,String(n)])));
  const [composition,setComposition]=useState<Record<string,string>>(Object.fromEntries(volume.componenteIds.map(c=>[String(c),Object.entries(existing?.elements??{}).filter(([,row])=>row[String(c)]!==0).map(([name,row])=>name+':'+row[String(c)]).join(' ')])));
  const [rate,setRate]=useState(existing?.reactions[0]?.rateConstantDataId??''),[energy,setEnergy]=useState(existing?.reactions[0]?.arrhenius?.energyDataId??''),[reference,setReference]=useState(existing?.reactions[0]?.arrhenius?.temperatureDataId??''),[error,setError]=useState(''),[pending,setPending]=useState(false);
  function load(r:KineticReaction|undefined){setSelected(r?.id??'');setId(r?.id??'');setNu(r?.stoichiometry??{});setOrders(Object.fromEntries(Object.entries(r?.orders??{}).map(([c,n])=>[c,String(n)])));setRate(r?.rateConstantDataId??'');setEnergy(r?.arrhenius?.energyDataId??'');setReference(r?.arrhenius?.temperatureDataId??'');}
  function data(label:string,value:string,change:(v:string)=>void){return <label>{label}<select value={value} onChange={e=>change(e.target.value)}><option value="">Select a datum</option>{Object.entries(common.datos).map(([key,d])=><option key={key} value={key}>{key} · {d.declaracion.unidad}</option>)}</select></label>;}
  async function assumption(kind:string){
    setPending(true);setError('');const source=JSON.stringify(common);
    try{
      const result=await requestMaterialDevelopment(common.motores.materialDerivation??emptyMaterialJournal(),owner,{kind});
      const latest=leerHojas().find(m=>m.id===model.id);
      if(!latest||JSON.stringify(latest.commonModel)!==source)throw new Error('The model changed. Review its current assumptions.');
      const next=structuredClone(common);next.motores.materialDerivation=result.journal;
      next.volumenes=next.volumenes.map(v=>v.id===owner?{...v,supuestos:{...v.supuestos,materia:result.development.formulation}}:v);
      guardarHoja({...latest,commonModel:next,resultado:undefined,resultadoRef:undefined});
    }catch(failure){setError((failure as Error).message);}finally{setPending(false);}
  }
  async function save(remove=false){
    setPending(true);setError('');const source=JSON.stringify(common);
    try{
      const next=structuredClone(common),config=next.motores.kineticReactions??{format:'rage.kinetic-reactions' as const,version:1 as const,volumes:{}};
      const reactions=(existing?.reactions??[]).filter(r=>r.id!==selected);
      if(!remove){
        if(reactions.some(r=>r.id===id))throw new Error('Choose a distinct reaction identity.');
        const elements:KineticVolume['elements']={};
        for(const c of volume.componenteIds){
          const text=composition[String(c)]?.trim()??'';
          if(!text)throw new Error('Declare elemental composition for every component.');
          for(const pair of text.split(/\s+/)){
            const match=/^([A-Za-z][A-Za-z0-9_]*):(-?\d+)$/.exec(pair);
            if(!match)throw new Error('Write composition as element:count pairs, for example C:2 H:6 O:1.');
            const row=elements[match[1]]??Object.fromEntries(volume.componenteIds.map(component=>[String(component),0]));
            row[String(c)]=Number(match[2]);elements[match[1]]=row;
          }
        }
        reactions.push({id,stoichiometry:Object.fromEntries(volume.componenteIds.map(c=>[String(c),nu[String(c)]??''])),orders:Object.fromEntries(Object.entries(orders).filter(([,n])=>n.trim()!=='').map(([c,n])=>[c,Number(n)])),rateConstantDataId:rate,...(energy||reference?{arrhenius:{energyDataId:energy,temperatureDataId:reference}}:{})});
        if(config.version===1)config.volumes[owner]={volumeDataId:volumeId,molarMassDataIds:masses,elements,reactions};
        else config.volumes[owner]={volumeSource:{kind:'control_volume'},molarMassDataIds:masses,elements,reactions};
      }else if(reactions.length)config.volumes[owner]={...existing!,reactions};else delete config.volumes[owner];
      next.motores.kineticReactions=config;readKineticReactions(config,next);
      const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/equation-workbench`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({modelo:next}),signal:AbortSignal.timeout(30000)});
      const body=await response.json();if(!response.ok)throw new Error(body?.detail?.message??'The kinetic declaration was rejected.');
      const report=readEquationWorkbenchReport(body);if(report.modelId!==common.id)throw new Error('Unexpected model response.');
      const latest=leerHojas().find(m=>m.id===model.id);
      if(!latest||JSON.stringify(latest.commonModel)!==source)throw new Error('The model changed. Reopen the declarations and retry.');
      guardarHoja({...latest,commonModel:next,resultado:undefined,resultadoRef:undefined});
    }catch(failure){setError((failure as Error).message);}finally{setPending(false);}
  }
  return <fieldset className={styles.operationGroup} disabled={pending}><legend>Concentration-based kinetic law</legend><fieldset><legend>Component-law operations</legend><p className={styles.groupHint}>Each button records one shared physical operation. Existing equation operations remain saved and may require review.</p>{(common.motores.materialDerivation?.volumes[owner]?[['reaction_sources','Retain reaction sources'],['fixed_boundary','Fixed boundary'],['integrate','Integrate local conservation'],['total','Define inventories and ports'],['impermeable_remainder','Close the remaining boundary'],['uniform_generation','Uniform generation'],['uniform_consumption','Uniform consumption'],['undo','Undo physical operation']]:[['start','Start component conservation']]).map(([kind,label])=><button type="button" key={kind} onClick={()=>void assumption(kind)}>{label}</button>)}</fieldset><label>Reaction<select value={selected} onChange={e=>load(existing?.reactions.find(r=>r.id===e.target.value))}><option value="">New reaction</option>{existing?.reactions.map(r=><option key={r.id} value={r.id}>{r.id}</option>)}</select></label><label>Reaction identity<input value={id} onChange={e=>setId(e.target.value)}/></label>{common.motores.kineticReactions?.version===2?<p>Concentrations use the dynamic control volume V(t).</p>:data('Reacting volume',volumeId,setVolumeId)}{volume.componenteIds.map(c=><fieldset key={c}><legend>{common.componentes.find(component=>component.id===c)?.nombre??String(c)}</legend>{data('Molar mass',masses[String(c)]??'',value=>setMasses({...masses,[String(c)]:value}))}<label>Stoichiometric coefficient (products positive)<input value={nu[String(c)]??''} onChange={e=>setNu({...nu,[String(c)]:e.target.value})}/></label><label>Concentration order<input inputMode="numeric" value={orders[String(c)]??''} onChange={e=>setOrders({...orders,[String(c)]:e.target.value})}/></label><label>Element counts (element:count)<input value={composition[String(c)]??''} onChange={e=>setComposition({...composition,[String(c)]:e.target.value})}/></label></fieldset>)}{data('Reference rate constant',rate,setRate)}{data('Activation energy (optional)',energy,setEnergy)}{data('Arrhenius reference temperature',reference,setReference)}<p className={styles.groupHint}>Units and elemental/mass conservation are verified on the server. Formation energy belongs in the thermodynamic relations. Declaration edits preserve equation history and invalidate execution until its deductions are reviewed.</p><button type="button" onClick={()=>void save()}>Save kinetic declaration</button>{selected&&<button type="button" onClick={()=>void save(true)}>Remove declaration</button>}{error&&<p role="alert">{error}</p>}</fieldset>;
}
