'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import styles from '../motor/motor.module.css';
import balanceStyles from '../motor/balances.module.css';
import { DynamicInventoryControls, DynamicInventoryDevelopment } from './DynamicModelDefinition';
import MomentumCoupling from './MomentumCoupling';
import {usePhysicalModel} from './DynamicModelDefinition';
import {EquationWorkbenchProvider,EquationOperationControls,EquationSystemDevelopment} from './EquationWorkbenchPanel';
import ModelDomainControls from './ModelDomainControls';
import ModelReadiness from './ModelReadiness';
import ui from './equationWorkbench.module.css';

const ConfigurationContext=createContext<{open:boolean;content:ReactNode}|null>(null);
export function ModelConfigurationProvider({open,content,children}:{open:boolean;content:ReactNode;children:ReactNode}){
  return <ConfigurationContext.Provider value={{open,content}}>{children}</ConfigurationContext.Provider>;
}
function ConfigurationControls({initiallyOpen,children}:{initiallyOpen:boolean;children:ReactNode}){
  const [open,setOpen]=useState(initiallyOpen);
  return <details className={styles.configurationControls} open={open} onToggle={event=>setOpen(event.currentTarget.open)}><summary>Physical system</summary>{open&&<div className={styles.configurationContent}>{children}</div>}</details>;
}

/** The only Model worksheet. Storage and scientific families supply content,
 * never another layout. All examples and saved models pass through this shell. */
export function ModelVolumeTabs({volumes,active,select}:{volumes:{id:string;name:string}[];active:string;select:(id:string)=>void}){
  const model=usePhysicalModel();
  const connections=model?.ensamblaje?.corrientes.map(stream=>({id:String(stream.id),name:stream.nombre,from:stream.desde,to:stream.hasta}))??model?.redTermodinamica?.solicitud.corrientes.map(stream=>({id:stream.id,name:stream.id,from:stream.desde,to:stream.hasta}))??[];
  const name=(id:string|null)=>id===null?'Surroundings':volumes.find(volume=>volume.id===id)?.name??id;
  return <section className={ui.structure} aria-label="Physical regions and connections"><header><h3>Physical regions</h3><p>Each region owns its balances and assumptions. Select one to inspect its derivation.</p></header><nav className={ui.regions} aria-label="Model volumes">{volumes.map((volume,index)=><button key={volume.id} aria-label={`Select region ${volume.name}`} aria-pressed={volume.id===active} onClick={()=>select(volume.id)}><span>Region {index+1} · v{index+1}</span><strong>{volume.name}</strong></button>)}</nav>{connections.length>0&&<details><summary>Connections · {connections.length}</summary><ul className={ui.connections}>{connections.map(connection=><li key={connection.id}><button disabled={connection.from===null} onClick={()=>connection.from&&select(connection.from)}>{name(connection.from)}</button><span>↔ <small>{connection.name}</small> ↔</span><button disabled={connection.to===null} onClick={()=>connection.to&&select(connection.to)}>{name(connection.to)}</button></li>)}</ul><p>Connections identify shared transport. Their laws and boundary conditions determine the transported quantities; a connection alone does not impose a pressure loss.</p></details>}</section>;
}
export default function ModelWorksheet({family,label,assumptions,variables,settings,children}:{
  family:'materia'|'energia'|'termodinamica'|'momento';label:string;
  assumptions:ReactNode;variables?:ReactNode;settings?:ReactNode;children:ReactNode;
}){
  const configuration=useContext(ConfigurationContext);
  const physicalModel=usePhysicalModel();
  const typed=!!physicalModel;
  const equationFamily=family==='materia'?'matter':family==='momento'?'momentum':family==='energia'?'energy':'thermodynamics';
  const aria=family==='materia'?'Equation assumptions':family==='energia'?'Energy assumptions':family==='termodinamica'?'Thermodynamic assumptions':'Momentum assumptions';
  return <EquationWorkbenchProvider family={equationFamily}><div className={styles.layout} data-model-worksheet="canonical" data-family={family}>
    <section className={styles.equations} aria-label={label}>{typed?<EquationSystemDevelopment/>:children}{!typed&&<><MomentumCoupling family={family}/><DynamicInventoryDevelopment family={family}/></>}</section>
    <aside className={`${styles.assumptions} ${styles.operationsPanel}`} aria-label={aria}>
      <header><div><h2>Assumptions</h2><p className={styles.groupHint}>{physicalModel?.ensamblaje?.volumenes.find(v=>v.id===(physicalModel.volumenActivo??physicalModel.ensamblaje?.volumenes[0]?.id))?.nombre??'Selected physical region'} · {equationFamily}</p><p className={styles.groupHint}>Changes apply to this region and family. Viewing equations does not change the model.</p></div></header>
      <ModelReadiness/>
      <div className={family==='materia'||family==='momento'?undefined:`${balanceStyles.supuestos} ${balanceStyles.operacionesEnergia} ${styles.assumptionBody}`}>{assumptions}</div>
      {typed&&<EquationOperationControls/>}
      <ModelDomainControls/>
      {configuration&&<ConfigurationControls key={String(configuration.open)} initiallyOpen={configuration.open}>{configuration.content}</ConfigurationControls>}
      {settings&&<div className={styles.configurationContent}>{settings}</div>}
      <DynamicInventoryControls family={family}/>
    </aside>
    {!typed&&variables}
  </div></EquationWorkbenchProvider>;
}
