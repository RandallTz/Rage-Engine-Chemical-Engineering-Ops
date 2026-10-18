'use client';
import EspacioRedTermodinamica from './EspacioRedTermodinamica';
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
import NavegacionHoja from './NavegacionHoja';
import PanelesBalances from './PanelesBalances';
import EnergiaFundamental from './EnergiaFundamental';
import FundamentoBalance from './FundamentoBalance';
import {balancesHoja,seleccionarBalance} from './seleccionBalances';
import {actualizarContextoDinamico} from './estadoEnergiaHoja';
import {SIN_SUPUESTOS} from './familiasBalance';
export default function HojaGuardada({id}:{id:string}){
  const hojas=useHojasMotor(),h=hojas.find(h=>h.id===id),[error,setError]=useState('');
  if(!h)return <div className={styles.empty}><h1>Abrir una hoja</h1><Link href="/motor/hojas">Ver mis hojas</Link></div>;
  if(h.redTermodinamica)return <EspacioRedTermodinamica h={h} vista="ecuaciones"/>;
  const vista=h.vistaBalance??'materia';
  function guardar(cambio:(actual:HojaMotor)=>HojaMotor){
    try{const actual=leerHojas().find(q=>q.id===id);if(!actual)throw new Error('Hoja no disponible');guardarHoja(cambio(actual));setError('');}
    catch{setError('No se pudo guardar el sistema.');}
  }
  return <>
    <div className={balanceStyles.pagina} style={{paddingBottom:0}}>
      <NavegacionHoja id={id} actual="ecuaciones"/>
      <header className={balanceStyles.sistemaHeader}><span>Sistema</span><form onSubmit={e=>{e.preventDefault();const nombre=String(new FormData(e.currentTarget).get('nombre')??'').trim();if(nombre)guardar(q=>({...q,nombre}));}}><h1 aria-label={h.nombre}><input name="nombre" aria-label="Nombre del sistema" key={h.nombre} defaultValue={h.nombre} maxLength={100} onBlur={e=>{const nombre=e.target.value.trim();if(nombre&&nombre!==h.nombre)guardar(q=>({...q,nombre}));}}/></h1><button>Guardar nombre</button></form></header>
      {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Cerrar</button></div>}
      <PanelesBalances vista={vista} balances={balancesHoja(h)} onVista={vistaBalance=>guardar(q=>({...q,vistaBalance}))} onBalance={(f,activo)=>guardar(q=>seleccionarBalance(q,f,activo))}/>
    </div>
    <div hidden={vista!=='materia'}><MateriaHoja key={`${id}:${h.revisionMateriaExterna??0}`} h={h}/></div>
    {vista==='energia'&&<EnergiaFundamental h={h} onGuardar={guardar}/>}
    {vista==='momento'&&<FundamentoBalance familia={vista} supuestos={h.supuestosBalances?.[vista]??SIN_SUPUESTOS} onSupuestos={supuestos=>guardar(q=>({...q,supuestosBalances:{...q.supuestosBalances,[vista]:supuestos}}))}/>}
  </>;
}
function MateriaHoja({h}:{h:HojaMotor}){
  const id=h.id,[error,setError]=useState('');
  if(h.ensamblaje)return <EditorEnsamblajeMateria h={h} integrado/>;
  function actualizarHistorial(historial: import('./recorridoMateria').RecorridoMateria) {
    if(!h)return;
    try {
      const antes=h.historial.pasos[h.historial.activo].formulacion,despues=historial.pasos[historial.activo].formulacion;
      const previa=analizarMotor(antes,h.config);
      const actual=analizarMotor(despues,h.config);
      const cambiaEstado=previa.modo!==actual.modo||esVolumetrico(antes)!==esVolumetrico(despues)||esTemporalLocal(antes)!==esTemporalLocal(despues);
      const datos=h.cierresDinamicos?h.config.datos:Object.fromEntries(Object.entries(h.config.datos).filter(([id])=>actual.campos.some(c=>c.id===id&&previa.campos.some(p=>p.id===id&&p.magnitud===c.magnitud))));
      guardarHoja(actualizarContextoDinamico({...h,historial,config:{...h.config,datos},resultado:undefined,resultadoRef:undefined,...(cambiaEstado?{graficas:[],tableroIniciado:false}:{})}));setError('');
    } catch {setError('No se pudo guardar. Revisa el espacio disponible en el navegador.');}
  }
  return <>{error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Cerrar</button></div>}<div className={styles.enableNetwork}><button className={styles.secondary} onClick={()=>{try{const nuevo=iniciarEnsamblaje(h.historial,h.config);guardarHoja({...h,...nuevo,volumenActivo:'v1',resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false});}catch{setError('No se pudo crear el ensamblaje.');}}}>Acoplar varios volúmenes</button></div><MateriaFundamental key={id} integrado hojaId={id} nombreHoja={h.nombre} historialInicial={h.historial} onHistorial={actualizarHistorial} onNombre={nombre=>{try{guardarHoja({...h,nombre:nombre.trim()||h.nombre});}catch{setError('No se pudo guardar el nombre.');}}}/></>;
}
