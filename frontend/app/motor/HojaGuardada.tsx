'use client';
import NetworkModelDerivation from '../models/NetworkModelDerivation';
import MomentumJournalEditor from '../models/MomentumJournalEditor';
import {useState} from 'react';
import Link from 'next/link';
import {useHojasMotor} from './useHojasMotor';
import type {HojaMotor} from './hojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import MateriaFundamental from './MateriaFundamental';
import {analizarMotor,esVolumetrico,esTemporalLocal} from './modeloNumerico';
import {iniciarEnsamblaje} from './ensamblajeMateria';
import EditorEnsamblajeMateria from './EditorEnsamblajeMateria';
import styles from './trabajoMotor.module.css';
import balanceStyles from './balances.module.css';
import PanelesBalances from './PanelesBalances';
import EnergiaFundamental from './EnergiaFundamental';
import {balancesHoja,seleccionarBalance} from './seleccionBalances';
import {actualizarContextoDinamico} from './estadoEnergiaHoja';
import TermodinamicaHoja from './TermodinamicaHoja';
export default function HojaGuardada({id}:{id:string}){
  const hojas=useHojasMotor(),h=hojas.find(h=>h.id===id),[error,setError]=useState('');
  if(!h)return <div className={styles.empty}><h1>Open a model</h1><Link href="/motor/hojas">Browse models</Link></div>;
  // Every document uses the same worksheet. Networks own their balance inputs;
  // their adapters supply recorded development without selecting another layout.
  const red=!!h.redTermodinamica;
  const vista=h.vistaBalance??'materia';
  function guardar(cambio:(actual:HojaMotor)=>HojaMotor){
    try{const actual=leerHojas().find(q=>q.id===id);if(!actual)throw new Error("Model not available");guardarHoja(cambio(actual));setError('');return true;}
    catch{setError("The model could not be saved.");return false;}
  }
  return <>
    <div className={balanceStyles.pagina} style={{paddingBottom:0}}>
      {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Close</button></div>}
      <PanelesBalances vista={vista} balances={balancesHoja(h)} fijos={red?"The thermodynamic network defines the balances of each volume.":undefined} onVista={vistaBalance=>guardar(q=>({...q,vistaBalance}))} onBalance={(f,activo)=>guardar(q=>seleccionarBalance(q,f,activo))}/>
    </div>
    {red&&(vista==='materia'||vista==='energia'||vista==='termodinamica')&&<NetworkModelDerivation key={vista} model={h} family={vista} save={guardar}/>}
    {!red&&vista==='materia'&&<div><MateriaHoja key={`${id}:${h.revisionMateriaExterna??0}`} h={h}/></div>}
    {!red&&vista==='energia'&&<EnergiaFundamental h={h} onGuardar={guardar} onTermodinamica={()=>guardar(q=>({...q,vistaBalance:'termodinamica'}))}/>}
    {!red&&vista==='termodinamica'&&<TermodinamicaHoja h={h} onGuardar={guardar} onVista={vistaBalance=>guardar(q=>({...q,vistaBalance}))}/>}
    {vista==='momento'&&<MomentumJournalEditor model={h} save={guardar}/>}
  </>;
}
function MateriaHoja({h}:{h:HojaMotor}){
  const id=h.id,[error,setError]=useState('');
  if(h.ensamblaje)return <EditorEnsamblajeMateria h={h}/>;
  function actualizarHistorial(historial: import('./recorridoMateria').RecorridoMateria) {
    if(!h)return;
    try {
      const antes=h.historial.pasos[h.historial.activo].formulacion,despues=historial.pasos[historial.activo].formulacion;
      const previa=analizarMotor(antes,h.config);
      const actual=analizarMotor(despues,h.config);
      const cambiaEstado=previa.modo!==actual.modo||esVolumetrico(antes)!==esVolumetrico(despues)||esTemporalLocal(antes)!==esTemporalLocal(despues);
      const datos=h.cierresDinamicos?h.config.datos:Object.fromEntries(Object.entries(h.config.datos).filter(([id])=>actual.campos.some(c=>c.id===id&&previa.campos.some(p=>p.id===id&&p.magnitud===c.magnitud))));
      guardarHoja(actualizarContextoDinamico({...h,historial,config:{...h.config,datos},resultado:undefined,resultadoRef:undefined,...(cambiaEstado?{graficas:[],tableroIniciado:false}:{})}));setError('');
    } catch {setError("Changes could not be saved. Check the available browser storage.");}
  }
  return <>{error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Close</button></div>}<div className={styles.enableNetwork}><button className={styles.secondary} onClick={()=>{try{const nuevo=iniciarEnsamblaje(h.historial,h.config);guardarHoja({...h,...nuevo,volumenActivo:'v1',resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false});}catch{setError("The assembly could not be created.");}}}>Connect multiple volumes</button></div><MateriaFundamental key={id} historialInicial={h.historial} onHistorial={actualizarHistorial}/></>;
}
