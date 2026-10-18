'use client';
import {useState} from 'react';
import type {HojaMotor} from './hojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import type {EnsamblajeMateria} from './ensamblajeMateria';
import {agregarVolumen,actualizarPuertos,planEnsamblaje,datosEnsamblaje,actualizarDatosEnsamblaje} from './ensamblajeMateria';
import {recorridoMateria} from './recorridoMateria';
import type {RecorridoMateria} from './recorridoMateria';
import {actualizarContextoDinamico} from './estadoEnergiaHoja';
import MateriaFundamental from './MateriaFundamental';
import NavegacionHoja from './NavegacionHoja';
import styles from './trabajoMotor.module.css';
export default function EditorEnsamblajeMateria({h,integrado=false}:{h:HojaMotor;integrado?:boolean}){
  const e=h.ensamblaje!,activo=e.volumenes.find(v=>v.id===h.volumenActivo)??e.volumenes[0];
  const [revision,setRevision]=useState(0);
  const [abierto,setAbierto]=useState(false),[desde,setDesde]=useState(activo.id),[hasta,setHasta]=useState(''),[error,setError]=useState('');
  const [previos,setPrevios]=useState<{ensamblaje:EnsamblajeMateria;config:HojaMotor['config']}[]>([]);
  function guardar(nuevo:EnsamblajeMateria,seleccion=h.volumenActivo,refrescar=true){
    try{const actual=leerHojas().find(q=>q.id===h.id)!;const anterior=planEnsamblaje(actual.ensamblaje!,actual.config),siguiente=planEnsamblaje(nuevo,actual.config);
      const datos=actual.cierresDinamicos?datosEnsamblaje(actual.ensamblaje!,actual.config).datos:Object.fromEntries(Object.entries(datosEnsamblaje(actual.ensamblaje!,actual.config).datos).filter(([id])=>siguiente.analisis.campos.some(s=>s.id===id&&anterior.analisis.campos.some(a=>a.id===id&&a.magnitud===s.magnitud))));
      setPrevios(p=>[...p.slice(-29),{ensamblaje:structuredClone(actual.ensamblaje!),config:structuredClone(actual.config)}]);
      guardarHoja(actualizarContextoDinamico({...actual,...actualizarDatosEnsamblaje(nuevo,{...actual.config,datos}),volumenActivo:seleccion,resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false}));if(refrescar)setRevision(v=>v+1);setError('');
    }catch{setError('No se pudo guardar el ensamblaje.');}
  }
  function editar(historial:RecorridoMateria){
    const componentes=historial.pasos[historial.activo].formulacion.componentes??[];
    const anteriores=activo.historial.pasos[activo.historial.activo].formulacion.componentes??[];
    const cambiaComponentes=JSON.stringify(componentes)!==JSON.stringify(anteriores);
    const nuevo={...e,...(cambiaComponentes?{componentes:structuredClone(componentes),corrientes:e.corrientes.map(s=>({...s,componentesIds:componentes.map(c=>c.id)}))}:{}),volumenes:e.volumenes.map(v=>v.id===activo.id?{...v,historial,componentesIds:componentes.map(c=>c.id)}:cambiaComponentes?{...v,componentesIds:componentes.map(c=>c.id),historial:recorridoMateria(v.historial,{tipo:'cambiar',titulo:'Actualizar componentes de la hoja',cambios:{componentes:structuredClone(componentes)}})}:v)};
    guardar(actualizarPuertos(nuevo),activo.id,false);
  }
  const extremos=(valor:string,onChange:(v:string)=>void,nombre:string)=><select aria-label={nombre} value={valor} onChange={ev=>onChange(ev.target.value)}><option value="">Exterior</option>{e.volumenes.map(v=><option key={v.id} value={v.id}>{v.nombre} · {v.id}</option>)}</select>;
  return <><div className={styles.page} style={{paddingBottom:0}}>{!integrado&&<NavegacionHoja id={h.id} actual="ecuaciones"/>}
    <header className={styles.heading}><div><span className={styles.eyebrow}>{h.nombre}</span>{integrado?<h2>Volúmenes del sistema</h2>:<h1>Ensamblaje de materia</h1>}</div><button className={styles.secondary} disabled={!previos.length} onClick={()=>{const previo=previos.at(-1);if(previo)try{const restaurado={...previo.ensamblaje,ultimoVolumen:Math.max(e.ultimoVolumen,previo.ensamblaje.ultimoVolumen),ultimaCorriente:Math.max(e.ultimaCorriente,previo.ensamblaje.ultimaCorriente),volumenes:previo.ensamblaje.volumenes.map(v=>({...v,historial:{...v.historial,ultimoComponenteId:Math.max(v.historial.ultimoComponenteId??0,...e.volumenes.map(w=>w.historial.ultimoComponenteId??0))}}))};guardarHoja(actualizarContextoDinamico({...h,ensamblaje:restaurado,config:previo.config,resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false}));setPrevios(p=>p.slice(0,-1));setRevision(v=>v+1);}catch{setError('No se pudo recuperar el ensamblaje.');}}}>Deshacer ensamblaje</button></header>
    {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Cerrar</button></div>}
    <div className={styles.networkTabs}>{e.volumenes.map(v=><button key={v.id} aria-pressed={activo.id===v.id} onClick={()=>{try{const actual=leerHojas().find(q=>q.id===h.id)!;guardarHoja({...actual,volumenActivo:v.id});setError('');}catch{setError('No se pudo seleccionar el volumen.');}}}>{v.nombre}<small>{v.id}</small></button>)}<button onClick={()=>{const nuevo=agregarVolumen(e);guardar(nuevo,`v${nuevo.ultimoVolumen}`);}}>+ Volumen</button><button aria-expanded={abierto} onClick={()=>{setAbierto(!abierto);setDesde(activo.id);setHasta('');}}>Corrientes · {e.corrientes.length}</button></div>
    {abierto&&<section className={styles.connections} aria-label="Corrientes del ensamblaje"><header><h2>Corrientes</h2><button onClick={()=>setAbierto(false)}>Cerrar</button></header>{e.corrientes.map(s=><div key={s.id} className={styles.connectionRow}><span>S{s.id}</span><input aria-label={`Nombre de S${s.id}`} defaultValue={s.nombre} onBlur={ev=>{const nombre=ev.target.value.trim();if(nombre&&nombre!==s.nombre)guardar({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,nombre}:q)});}}/>{extremos(s.desde??'',id=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,desde:id||null}:q)})),`Origen de S${s.id}`)}<span>→</span>{extremos(s.hasta??'',id=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,hasta:id||null}:q)})),`Destino de S${s.id}`)}<label><input type="checkbox" checked={s.constante} onChange={ev=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,constante:ev.target.checked}:q)}))}/>Constante</label><button aria-label={`Quitar S${s.id}`} onClick={()=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.filter(q=>q.id!==s.id)}))}>×</button></div>)}
      <div className={styles.connectionRow}><span>Nueva</span>{extremos(desde,setDesde,'Origen de la nueva corriente')}<span>→</span>{extremos(hasta,setHasta,'Destino de la nueva corriente')}<button className={styles.primary} disabled={!desde&&!hasta} onClick={()=>{const id=e.ultimaCorriente+1;guardar(actualizarPuertos({...e,ultimaCorriente:id,corrientes:[...e.corrientes,{id,nombre:`Corriente ${id}`,desde:desde||null,hasta:hasta||null,constante:false}]}));}}>Añadir corriente</button></div>
    </section>}
    <div className={styles.volumeTools}><label>Nombre del volumen<input aria-label="Nombre del volumen" key={activo.id} defaultValue={activo.nombre} onBlur={ev=>{const nombre=ev.target.value.trim();if(nombre&&nombre!==activo.nombre)guardar({...e,volumenes:e.volumenes.map(v=>v.id===activo.id?{...v,nombre}:v)});}}/></label><label><input type="checkbox" aria-label="Declarar volumen como dato" checked={!!activo.volumenDeclarado} onChange={ev=>guardar({...e,volumenes:e.volumenes.map(v=>v.id===activo.id?{...v,volumenDeclarado:ev.target.checked}:v)})}/>V como dato</label><button disabled={e.volumenes.length===1} onClick={()=>guardar(actualizarPuertos({...e,volumenes:e.volumenes.filter(v=>v.id!==activo.id),corrientes:e.corrientes.filter(s=>s.desde!==activo.id&&s.hasta!==activo.id)}),e.volumenes.find(v=>v.id!==activo.id)?.id)}>Quitar volumen</button></div>
  </div><MateriaFundamental key={`${activo.id}:${revision}`} nombreHoja={activo.nombre} historialInicial={{...activo.historial,pasos:activo.historial.pasos.map((p,i)=>i===activo.historial.activo?{...p,formulacion:{...p.formulacion,componentes:e.componentes??p.formulacion.componentes}}:p)}} onHistorial={editar} enEnsamblaje integrado={integrado}/></>;
}
