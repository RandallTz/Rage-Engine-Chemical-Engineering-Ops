'use client';
import {useState} from 'react';
import type {HojaMotor} from '../motor/hojasMotor';
import {guardarHoja,leerHojas} from '../motor/hojasMotor';
import ModelWorksheet from './ModelWorksheet';
import styles from './workspace.module.css';

/** Backing-document content in the sole canonical worksheet, never a layout. */
export default function CommonModelContent({model}:{model:HojaMotor}){
  const [family,setFamily]=useState<'materia'|'energia'|'termodinamica'|'momento'|'senal'>('materia');
  const common=model.commonModel!;
  function choose(id:string){const latest=leerHojas().find(item=>item.id===model.id);if(latest)guardarHoja({...latest,volumenActivo:id});}
  const volume=common.volumenes.find(item=>item.id===model.volumenActivo)??common.volumenes[0];
  // dec-control-surface (Demo 0.3 C9): the Signal family appears once the recorded history holds signal rows.
  const signal=(common.motores.equationWorkbench?.operations??[]).some(operation=>operation.family==='signal');
  const families=[['materia','Matter'],['energia','Energy'],['momento','Momentum'],['termodinamica','Thermodynamics'],...(signal?[['senal','Signal']] as const:[])] as const;
  const journal=family==='senal'?undefined:family==='materia'?common.motores.materialDerivation:family==='energia'?common.motores.energyDerivation:family==='termodinamica'?common.motores.thermodynamicDerivation:common.motores.momentumDerivation;
  return <><nav className={styles.subnav} aria-label="Equation families">{families.map(([key,title])=><button key={key} aria-pressed={family===key} onClick={()=>setFamily(key)}>{title}</button>)}</nav><ModelWorksheet family={family==='senal'&&!signal?'materia':family} label="Recorded common-model equations" assumptions={<><h3>Recorded physical assumptions</h3><label>Physical region<select aria-label="Physical region" value={volume?.id??''} onChange={event=>choose(event.target.value)}>{common.volumenes.map(item=><option key={item.id}>{item.id}</option>)}</select></label><p>Use the shared mathematical controls below to inspect, record or undo equation operations. The physical producer history remains attached to each region.</p><ol>{journal?.volumes[volume?.id]?.operations.map((operation,index)=><li key={index}>{operation.title}</li>)}</ol><p>Closure: {volume?.termodinamica.tipo==='supuesto'?volume.termodinamica.motivo:'Declared equilibrium package'}</p></>}>{null}</ModelWorksheet></>;
}
