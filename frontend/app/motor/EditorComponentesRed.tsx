'use client';
import {useState} from 'react';
import type {RedTermodinamica} from './redTermodinamica';
import type {CapacidadesEnsamblajeV2} from './contratoEnsamblajeV2';
import {restriccionComponenteRed} from './alcanceEdicionPaquete';
import {agregarComponenteRed,asignarComponenteVolumen,quitarComponenteRed} from './componentesRed';
import SelectorSustanciaCatalogo from './SelectorSustanciaCatalogo';
import styles from './componentesRed.module.css';

export default function EditorComponentesRed({red,maximo,paquetes,cambiar}:{red:RedTermodinamica;maximo?:number;paquetes?:CapacidadesEnsamblajeV2['paquetes'];cambiar:(fn:(red:RedTermodinamica)=>void,grupo?:string)=>boolean}){
  const s=red.solicitud,[nombre,setNombre]=useState(''),[cas,setCas]=useState(''),[elegidos,setElegidos]=useState<string[]>([]),[abierto,setAbierto]=useState(false);
  const nombreVol=(id:string)=>red.nombres[`volumen:${id}`]??id;
  const restriccion=(vid:string,cas?:string)=>restriccionComponenteRed(red,vid,cas,paquetes);
  function comprobar(r:RedTermodinamica,vid:string,cas?:string){const motivo=restriccionComponenteRed(r,vid,cas,paquetes);if(motivo)throw new Error(`${nombreVol(vid)}: ${motivo}.`);}
  return <div className={styles.editor}>
    <div className={styles.list}>{s.componentes.map(c=><article key={c.id}>
      <div className={styles.identity}>
        <label>Name<input aria-label={`Component name ${c.id}`} value={c.nombre} onChange={e=>cambiar(r=>{r.solicitud.componentes.find(x=>x.id===c.id)!.nombre=e.target.value;},`componente:${c.id}:nombre`)}/></label>
        <label>CAS<input id={`red-identidad-${c.id}`} aria-label={`CAS de ${c.nombre}`} value={c.identidadQuimica?.cas??''} placeholder="Sin identificar" onChange={e=>cambiar(r=>{const x=r.solicitud.componentes.find(x=>x.id===c.id)!;x.identidadQuimica={...x.identidadQuimica};if(e.target.value.trim())x.identidadQuimica.cas=e.target.value.trim();else delete x.identidadQuimica.cas;},`componente:${c.id}:cas`)}/></label>
        <button aria-label={`Remove ${c.nombre}`} disabled={s.componentes.length===1||s.volumenes.some(v=>v.componenteIds.length===1&&v.componenteIds.includes(c.id))||s.corrientes.some(x=>x.componenteIds.length===1&&x.componenteIds.includes(c.id))} onClick={()=>cambiar(r=>quitarComponenteRed(r,c.id))}>Quitar</button>
      </div>
      <fieldset><legend className={styles.srOnly}>Volúmenes de {c.nombre}</legend>{s.volumenes.map(v=><label key={v.id}><input type="checkbox" aria-label={`${c.nombre} en ${nombreVol(v.id)}`} checked={v.componenteIds.includes(c.id)} disabled={!v.componenteIds.includes(c.id)&&(maximo===undefined||v.componenteIds.length>=maximo||!!restriccion(v.id,c.identidadQuimica?.cas))} onChange={e=>cambiar(r=>{if(e.target.checked)comprobar(r,v.id,r.solicitud.componentes.find(x=>x.id===c.id)?.identidadQuimica?.cas);asignarComponenteVolumen(r,v.id,c.id,e.target.checked,maximo);})}/>{nombreVol(v.id)}{restriccion(v.id,c.identidadQuimica?.cas)&&<small>{restriccion(v.id,c.identidadQuimica?.cas)}</small>}</label>)}</fieldset>
    </article>)}</div>
    {!abierto?<button className={styles.add} onClick={()=>{setElegidos([]);setAbierto(true);}}>+ Componente</button>:<form className={styles.new} onSubmit={e=>{e.preventDefault();if(cambiar(r=>{elegidos.forEach(vid=>comprobar(r,vid,cas));agregarComponenteRed(r,nombre,cas,elegidos,maximo);})){setNombre('');setCas('');setAbierto(false);}}}>
      <SelectorSustanciaCatalogo red={red} destinos={elegidos} cas={cas} elegir={s=>{setNombre(s.nombre);setCas(s.cas);}}/>
      <div className={styles.identity}><label>Name<input aria-label="Nombre del nuevo componente" required value={nombre} onChange={e=>setNombre(e.target.value)}/></label><label>CAS<input aria-label="CAS del nuevo componente" value={cas} onChange={e=>setCas(e.target.value)} placeholder="Opcional al preparar"/></label></div>
      <fieldset><legend>Add to volumes</legend>{s.volumenes.map(v=><label key={v.id}><input type="checkbox" aria-label={`Añadir nuevo componente a ${nombreVol(v.id)}`} checked={elegidos.includes(v.id)} disabled={!elegidos.includes(v.id)&&(maximo===undefined||v.componenteIds.length>=maximo||!!restriccion(v.id,cas))} onChange={e=>setElegidos(xs=>e.target.checked?[...xs,v.id]:xs.filter(id=>id!==v.id))}/>{nombreVol(v.id)}{restriccion(v.id,cas)&&<small>{restriccion(v.id,cas)}</small>}<small>{v.componenteIds.length}{maximo!==undefined?` / ${maximo}`:''}</small></label>)}</fieldset>
      <div className={styles.actions}><button type="submit" disabled={!nombre.trim()||elegidos.some(vid=>!!restriccion(vid,cas))||s.componentes.some(c=>c.nombre===nombre.trim()&&c.identidadQuimica?.cas===(cas.trim()||undefined))}>Añadir a la hoja</button><button type="button" onClick={()=>{setAbierto(false);setNombre('');setCas('');}}>Close</button></div>
    </form>}
    {maximo!==undefined&&<small className={styles.scope}>Servicio actual: hasta {maximo} componentes por volumen.</small>}
  </div>;
}
