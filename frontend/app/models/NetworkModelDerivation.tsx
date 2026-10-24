'use client';

import { useEffect, useMemo, useState } from 'react';
import type { HojaMotor } from '../motor/hojasMotor';
import { cambiarRed } from '../motor/redTermodinamica';
import { historialEdicionRed } from '../motor/historialEdicionRed';
import MaterialJournalEditor from './MaterialJournalEditor';
import EnergyJournalEditor from './EnergyJournalEditor';
import ThermodynamicJournalEditor from './ThermodynamicJournalEditor';
import {hasPreviousMaterialFormulation,replaceNetworkMaterialJournal,restoreNetworkMaterialFormulation} from '../motor/networkMaterialJournal';
import {hasPreviousEnergyFormulation,replaceNetworkEnergyJournal,restoreNetworkEnergyFormulation} from '../motor/networkEnergyJournal';
import {hasPreviousThermodynamicFormulation,replaceNetworkThermodynamicJournal,restoreNetworkThermodynamicFormulation} from '../motor/networkThermodynamicJournal';
import styles from '../motor/motor.module.css';
import { ModelVolumeTabs } from './ModelWorksheet';

/** Network storage adapter. Journal editors supply the same ModelWorksheet;
 * there is no network equation page or example-specific UI. */
export default function NetworkModelDerivation({model,family,save}:{model:HojaMotor;family:'materia'|'energia'|'termodinamica';save:(change:(current:HojaMotor)=>HojaMotor)=>boolean}){
  const request=model.redTermodinamica!.solicitud;
  const volume=request.volumenes.find(item=>item.id===model.volumenActivo)??request.volumenes[0];
  const history=useMemo(()=>historialEdicionRed(model.id),[model.id]);
  const [,refresh]=useState(0);
  const [error,setError]=useState('');
  useEffect(()=>{history.sincronizar(model.redTermodinamica!);},[history,model.redTermodinamica]);
  function edit(change:Parameters<typeof cambiarRed>[1]){
    let previous:HojaMotor['redTermodinamica'],next:HojaMotor['redTermodinamica'];
    const saved=save(current=>{previous=current.redTermodinamica;const result=cambiarRed(current,change);next=result.redTermodinamica;return result;});
    if(saved&&previous&&next){history.registrar(previous,next);refresh(value=>value+1);setError('');}
    return saved;
  }
  function recover(direction:'deshacer'|'rehacer'){
    try{
      history.mover(model.redTermodinamica!,direction,network=>{
        let persisted:HojaMotor['redTermodinamica'];
        const saved=save(current=>{const next=cambiarRed(current,draft=>Object.assign(draft,network));persisted=next.redTermodinamica;return next;});
        if(!saved||!persisted)throw new Error('The configuration could not be restored.');
        return persisted;
      });
      refresh(value=>value+1);setError('');
    }catch(failure){setError((failure as Error).message);}
  }
  if(!volume)return <p role="alert">This model has no control volume.</p>;
  return <div className={styles.page}>
    <header className={styles.header}><span className={styles.eyebrow}>{model.nombre}</span><h2 className={styles.tituloBalance}>{family==='materia'?'Matter balance':family==='energia'?'Energy balance':'Thermodynamic relations'}</h2></header>
    {error&&<p role="alert">{error}</p>}
    <ModelVolumeTabs volumes={request.volumenes.map(item=>({id:item.id,name:model.redTermodinamica!.nombres[`volumen:${item.id}`]??item.id}))} active={volume.id} select={id=>save(current=>({...current,volumenActivo:id}))}/>
    {family==='materia'?<MaterialJournalEditor key={volume.id} modelId={model.id} request={request} volume={volume} canRestore={hasPreviousMaterialFormulation(request,volume.id)} restore={()=>edit(draft=>restoreNetworkMaterialFormulation(draft.solicitud,volume.id))} save={(journal,state,starting,expected)=>edit(draft=>replaceNetworkMaterialJournal(draft.solicitud,volume.id,journal,state,starting,expected))}/>
      :family==='energia'?<EnergyJournalEditor key={volume.id} request={request} volume={volume} canRestore={hasPreviousEnergyFormulation(request,volume.id)} restore={()=>edit(draft=>restoreNetworkEnergyFormulation(draft.solicitud,volume.id))} save={(journal,state,starting,expected)=>edit(draft=>replaceNetworkEnergyJournal(draft.solicitud,volume.id,journal,state,starting,expected))}/>
      :<ThermodynamicJournalEditor key={volume.id} modelId={model.id} request={request} volume={volume} canRestore={hasPreviousThermodynamicFormulation(request,volume.id)} restore={()=>edit(draft=>restoreNetworkThermodynamicFormulation(draft.solicitud,volume.id))} save={(journal,state,starting,expected)=>edit(draft=>replaceNetworkThermodynamicJournal(draft.solicitud,volume.id,journal,state,starting,expected))}/>}
    <details className={styles.integrationBridge}><summary>Configuration history</summary><button disabled={!history.vigente(model.redTermodinamica!)||!history.puedeDeshacer} onClick={()=>recover('deshacer')}>Undo configuration</button><button disabled={!history.vigente(model.redTermodinamica!)||!history.puedeRehacer} onClick={()=>recover('rehacer')}>Redo configuration</button></details>
  </div>;
}
