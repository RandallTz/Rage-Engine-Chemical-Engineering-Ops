'use client';
import {useState} from 'react';
import type {HojaMotor} from './hojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import type {EnsamblajeMateria} from './ensamblajeMateria';
import {actualizarPuertos,planEnsamblaje,datosEnsamblaje,actualizarDatosEnsamblaje} from './ensamblajeMateria';
import {recorridoMateria} from './recorridoMateria';
import type {RecorridoMateria,AccionMateria} from './recorridoMateria';
import {actualizarContextoDinamico} from './estadoEnergiaHoja';
import MateriaFundamental from './MateriaFundamental';
import { ModelVolumeTabs } from '../models/ModelWorksheet';
import styles from './trabajoMotor.module.css';
import {reconcileModelTopology} from '../models/modelTopology';
export default function EditorEnsamblajeMateria({h}:{h:HojaMotor}){
  const e=h.ensamblaje!,activo=e.volumenes.find(v=>v.id===h.volumenActivo)??e.volumenes[0];
  const [revision,setRevision]=useState(0);
  const [abierto,setAbierto]=useState(false),[desde,setDesde]=useState(activo.id),[hasta,setHasta]=useState(''),[error,setError]=useState('');
  const [previos,setPrevios]=useState<({ensamblaje:EnsamblajeMateria}&Pick<HojaMotor,'config'|'momentumDerivation'|'hydraulicNetwork'|'previousHydraulicNetwork'|'archivedMomentumVolumes'>)[]>([]);
  function guardar(nuevo:EnsamblajeMateria,seleccion=h.volumenActivo,refrescar=true,physical=true){
    try{const actual=leerHojas().find(q=>q.id===h.id)!;if(!physical){guardarHoja({...actual,ensamblaje:nuevo});setError('');return;}const anterior=planEnsamblaje(actual.ensamblaje!,actual.config),siguiente=planEnsamblaje(nuevo,actual.config);
      const datos=actual.hydraulicNetwork||actual.cierresDinamicos?datosEnsamblaje(actual.ensamblaje!,actual.config).datos:Object.fromEntries(Object.entries(datosEnsamblaje(actual.ensamblaje!,actual.config).datos).filter(([id])=>siguiente.analisis.campos.some(s=>s.id===id&&anterior.analisis.campos.some(a=>a.id===id&&a.magnitud===s.magnitud))));
      if(refrescar)setPrevios(p=>[...p.slice(-29),{ensamblaje:structuredClone(actual.ensamblaje!),config:structuredClone(actual.config),momentumDerivation:structuredClone(actual.momentumDerivation),hydraulicNetwork:structuredClone(actual.hydraulicNetwork),previousHydraulicNetwork:structuredClone(actual.previousHydraulicNetwork),archivedMomentumVolumes:structuredClone(actual.archivedMomentumVolumes)}]);else setPrevios([]);
      guardarHoja(reconcileModelTopology(actual,actualizarContextoDinamico({...actual,...actualizarDatosEnsamblaje(nuevo,{...actual.config,datos}),volumenActivo:seleccion,resultado:undefined,resultadoRef:undefined})));if(refrescar)setRevision(v=>v+1);setError('');
    }catch{setError('The assembly could not be saved.');}
  }
  function editar(historial:RecorridoMateria,action?:AccionMateria){
    const componentEdit=action?.tipo==='cambiar'&&Object.hasOwn(action.cambios,'componentes');
    const componentes=componentEdit?historial.pasos[historial.activo].formulacion.componentes??[]:e.componentes??activo.historial.pasos[activo.historial.activo].formulacion.componentes??[];
    const anteriores=activo.historial.pasos[activo.historial.activo].formulacion.componentes??[];
    const cambiaComponentes=JSON.stringify(componentes)!==JSON.stringify(anteriores);
    const nuevo={...e,...(cambiaComponentes?{componentes:structuredClone(componentes),corrientes:e.corrientes.map(s=>({...s,componentesIds:componentes.map(c=>c.id)}))}:{}),volumenes:e.volumenes.map(v=>v.id===activo.id?{...v,historial,componentesIds:componentes.map(c=>c.id)}:cambiaComponentes?{...v,componentesIds:componentes.map(c=>c.id),historial:recorridoMateria(v.historial,{tipo:'cambiar',titulo:'Update model components',cambios:{componentes:structuredClone(componentes)}})}:v)};
    guardar(actualizarPuertos(nuevo),activo.id,false);
  }
  const extremos=(valor:string,onChange:(v:string)=>void,nombre:string)=><select aria-label={nombre} value={valor} onChange={ev=>onChange(ev.target.value)}><option value="">Surroundings</option>{e.volumenes.map(v=><option key={v.id} value={v.id}>{v.nombre} · {v.id}</option>)}</select>;
  return <MateriaFundamental volumeSelector={<ModelVolumeTabs volumes={e.volumenes.map(volume=>({id:volume.id,name:volume.nombre}))} active={activo.id} select={id=>{try{const current=leerHojas().find(model=>model.id===h.id)!;guardarHoja({...current,volumenActivo:id});setError('');}catch{setError('The control volume could not be selected.');}}}/>} settings={<details><summary>Material connections</summary><button className={styles.secondary} disabled={!previos.length} onClick={()=>{const previo=previos.at(-1);if(previo)try{const restaurado={...previo.ensamblaje,ultimoVolumen:Math.max(e.ultimoVolumen,previo.ensamblaje.ultimoVolumen),ultimaCorriente:Math.max(e.ultimaCorriente,previo.ensamblaje.ultimaCorriente),volumenes:previo.ensamblaje.volumenes.map(v=>({...v,historial:{...v.historial,ultimoComponenteId:Math.max(v.historial.ultimoComponenteId??0,...e.volumenes.map(w=>w.historial.ultimoComponenteId??0))}}))};guardarHoja(actualizarContextoDinamico({...h,...previo,ensamblaje:restaurado,config:previo.config,resultado:undefined,resultadoRef:undefined}));setPrevios(p=>p.slice(0,-1));setRevision(v=>v+1);}catch{setError('The assembly could not be restored.');}}}>Undo connection edit</button>
    {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError('')}>Close</button></div>}
<button aria-expanded={abierto} onClick={()=>{setAbierto(!abierto);setDesde(activo.id);setHasta('');}}>Streams · {e.corrientes.length}</button>
    {abierto&&<section className={styles.connections} aria-label="Assembly streams"><header><h2>Streams</h2><button onClick={()=>setAbierto(false)}>Close</button></header>{e.corrientes.map(s=><div key={s.id} className={styles.connectionRow}><span>S{s.id}</span><input aria-label={`Name of S${s.id}`} defaultValue={s.nombre} onBlur={ev=>{const nombre=ev.target.value.trim();if(nombre&&nombre!==s.nombre)guardar({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,nombre}:q)},h.volumenActivo,true,false);}}/>{extremos(s.desde??'',id=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,desde:id||null}:q)})),`Origin of S${s.id}`)}<span>→</span>{extremos(s.hasta??'',id=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,hasta:id||null}:q)})),`Destination of S${s.id}`)}<label><input type="checkbox" checked={s.constante} onChange={ev=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.map(q=>q.id===s.id?{...q,constante:ev.target.checked}:q)}))}/>Constant</label><button aria-label={`Remove S${s.id}`} onClick={()=>guardar(actualizarPuertos({...e,corrientes:e.corrientes.filter(q=>q.id!==s.id)}))}>×</button></div>)}
      <div className={styles.connectionRow}><span>New</span>{extremos(desde,setDesde,'New stream origin')}<span>→</span>{extremos(hasta,setHasta,'New stream destination')}<button className={styles.primary} disabled={!desde&&!hasta} onClick={()=>{const id=e.ultimaCorriente+1;guardar(actualizarPuertos({...e,ultimaCorriente:id,corrientes:[...e.corrientes,{id,nombre:`Stream ${id}`,desde:desde||null,hasta:hasta||null,constante:false}]}));}}>Add stream</button></div>
    </section>}
</details>} key={`${activo.id}:${revision}`} historialInicial={{...activo.historial,pasos:activo.historial.pasos.map((p,i)=>i===activo.historial.activo?{...p,formulacion:{...p.formulacion,componentes:e.componentes??p.formulacion.componentes}}:p)}} onHistorial={editar} componentsOverride={e.componentes} enEnsamblaje/>;
}
