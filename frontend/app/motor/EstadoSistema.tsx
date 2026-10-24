'use client';
import EspacioRedTermodinamica from './EspacioRedTermodinamica';
import type {EnfoqueRed} from './destinoDiagnosticoRed';
import {copiarARed} from './redTermodinamica';
import {useRouter} from 'next/navigation';
import {useState} from 'react';
import Link from 'next/link';
import {useHojasMotor} from './useHojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import type {HojaMotor} from './hojasMotor';
import {propietariosEstado} from './estadoTermodinamicoHoja';
import EditorEstadoTermodinamico from './EditorEstadoTermodinamico';
import DefinirVolumen from './DefinirVolumen';
import styles from './estadoTermodinamico.module.css';
export default function EstadoSistema({id,enfoque}:{id:string;enfoque?:EnfoqueRed}){
  const router=useRouter();
  const hojas=useHojasMotor(),h=hojas.find(h=>h.id===id),[seleccion,setSeleccion]=useState(''),[vista,setVista]=useState<'volumen'|'propiedades'>('volumen'),[error,setError]=useState('');
  if(!h)return <div className={styles.page}><Link href="/motor/hojas">Browse models</Link></div>;
  if(h.redTermodinamica)return <EspacioRedTermodinamica h={h} enfoque={enfoque??(h.volumenActivo?{propietarioId:`volumen:${h.volumenActivo}`} : undefined)} vista="estado" incrustada/>;
  const propietarios=propietariosEstado(h),p=propietarios.find(p=>p.id===(seleccion||`volumen:${h.volumenActivo??'dominio'}`))??propietarios[0];
  function guardar(cambio:(h:HojaMotor)=>HojaMotor){try{const actual=leerHojas().find(h=>h.id===id);if(!actual)throw new Error("Model not available.");guardarHoja(cambio(actual));setError('');}catch(e){setError((e as Error).message);}}
  return <div><label>Volume or stream<select aria-label="Volume or stream" value={p.id} onChange={event=>{const owner=event.target.value;setSeleccion(owner);if(owner.startsWith('volumen:'))guardar(current=>({...current,volumenActivo:owner.slice(8)}));}}>{propietarios.map(owner=><option key={owner.id} value={owner.id}>{owner.nombre}</option>)}</select></label>
    <button className={styles.scope} onClick={()=>{try{const copia=guardarHoja(copiarARed(h));router.push(`/motor/hojas/${copia.id}/estado`);}catch(e){setError((e as Error).message);}}}>Copy with an equilibrium closure →</button>
    {error&&<div role="alert" className={styles.notice}>{error}<button onClick={()=>setError('')}>Close</button></div>}
    {p.tipo==='volumen'&&<nav className={styles.viewTabs} aria-label="Definition or property lookup"><button aria-pressed={vista==='volumen'} onClick={()=>setVista('volumen')}>Control volume</button><button aria-pressed={vista==='propiedades'} onClick={()=>setVista('propiedades')}>Inspect properties</button></nav>}
    {p.tipo==='volumen'&&vista==='volumen'?<DefinirVolumen h={h} volumenId={p.id.slice('volumen:'.length)} onGuardar={guardar}/>:<EditorEstadoTermodinamico key={p.id} id={id} propietarioId={p.id} integrado/>}
  </div>;
}
