'use client';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import {useState} from 'react';
import {guardarHoja,leerHojas,nuevaHoja} from './hojasMotor';
import type {RecorridoMateria} from './recorridoMateria';
import styles from './motor.module.css';
export default function BarraHojaMotor({id,nombre,historial,onNombre}:{id?:string;nombre:string;historial:RecorridoMateria;onNombre?:(n:string)=>void}){
  const router=useRouter();
  const [error,setError]=useState('');
  return <><div className={styles.documentBar}><Link href="/motor/hojas">← Hojas</Link><form onSubmit={e=>{e.preventDefault();const titulo=String(new FormData(e.currentTarget).get('nombre')??'').trim()||nombre;const intento=(e.nativeEvent as SubmitEvent).submitter?.getAttribute('value');try{const anterior=id?leerHojas().find(h=>h.id===id):undefined;const h=guardarHoja({...anterior??nuevaHoja(titulo,historial),nombre:titulo,historial});router.push(`/motor/hojas/${h.id}${intento==='resolver'?'/resolver':''}`);}catch{setError('No se pudo guardar. Revisa el espacio disponible en este navegador.');}}}><label className={styles.srOnly} htmlFor="nombre-hoja">Nombre de la hoja</label><input id="nombre-hoja" name="nombre" aria-label="Nombre de la hoja" defaultValue={nombre} maxLength={100} onBlur={e=>onNombre?.(e.target.value)}/><button type="submit" value="guardar">Guardar hoja</button><button type="submit" value="resolver">Resolver →</button></form>{id&&<Link href={`/motor/hojas/${id}/resultados`}>Gráficos</Link>}</div>{error&&<p role="alert">{error}<button aria-label="Cerrar aviso" onClick={()=>setError('')}>×</button></p>}</>;
}
