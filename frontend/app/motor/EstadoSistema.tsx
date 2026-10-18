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
import NavegacionHoja from './NavegacionHoja';
import styles from './estadoTermodinamico.module.css';
export default function EstadoSistema({id,enfoque}:{id:string;enfoque?:EnfoqueRed}){
  const router=useRouter();
  const hojas=useHojasMotor(),h=hojas.find(h=>h.id===id),[seleccion,setSeleccion]=useState(''),[vista,setVista]=useState<'volumen'|'propiedades'>('volumen'),[error,setError]=useState('');
  if(!h)return <div className={styles.page}><Link href="/motor/hojas">Abrir mis hojas</Link></div>;
  if(h.redTermodinamica)return <EspacioRedTermodinamica h={h} enfoque={enfoque} vista="estado"/>;
  const propietarios=propietariosEstado(h),p=propietarios.find(p=>p.id===seleccion)??propietarios[0];
  function guardar(cambio:(h:HojaMotor)=>HojaMotor){try{const actual=leerHojas().find(h=>h.id===id);if(!actual)throw new Error('Hoja no disponible.');guardarHoja(cambio(actual));setError('');}catch(e){setError((e as Error).message);}}
  return <div className={styles.page}><NavegacionHoja id={id} actual="estado"/><header className={styles.heading}><div><small>{h.nombre}</small><h1>{p.tipo==='volumen'?'Definir el sistema':'Estado de la corriente'}</h1></div><select aria-label="Volumen o corriente" value={p.id} onChange={e=>setSeleccion(e.target.value)}>{propietarios.map(p=><option key={p.id} value={p.id}>{p.nombre} · {p.tipo}</option>)}</select></header>
    <button className={styles.scope} onClick={()=>{try{const copia=guardarHoja(copiarARed(h));router.push(`/motor/hojas/${copia.id}/estado`);}catch(e){setError((e as Error).message);}}}>Crear copia para mezclas y volúmenes acoplados →</button>
    {error&&<div role="alert" className={styles.notice}>{error}<button onClick={()=>setError('')}>Cerrar</button></div>}
    {p.tipo==='volumen'&&<nav className={styles.viewTabs} aria-label="Definición o consulta"><button aria-pressed={vista==='volumen'} onClick={()=>setVista('volumen')}>Volumen de control</button><button aria-pressed={vista==='propiedades'} onClick={()=>setVista('propiedades')}>Consultar propiedades</button></nav>}
    {p.tipo==='volumen'&&vista==='volumen'?<DefinirVolumen h={h} volumenId={p.id.slice('volumen:'.length)} onGuardar={guardar}/>:<EditorEstadoTermodinamico key={p.id} id={id} propietarioId={p.id} integrado/>}
  </div>;
}
