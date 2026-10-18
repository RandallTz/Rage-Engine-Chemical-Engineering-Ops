'use client';
import {useState} from 'react';
import Link from 'next/link';
import type {HojaMotor} from './hojasMotor';
import {tipoVolumenControl,OPCIONES_VOLUMEN,elegirVolumenControl,claveGeometria,guardarGeometria,ecuacionesVolumenControl} from './volumenControl';
import {datosVolumen} from './papelesVariables';
import {configuracionHoja} from './modeloHojaMotor';
import {contextoEnergiaHoja} from './estadoEnergiaHoja';
import {nombreUnidad} from './unidadesMotor';
import FormulaMateria from './FormulaMateria';
import VariablesDelVolumen from './VariablesDelVolumen';
import ElegirCierreEnergia from './ElegirCierreEnergia';
import {balancesHoja} from './seleccionBalances';
import {prepararEnsamblajeTermodinamico} from './prepararEnsamblajeTermodinamico';
import styles from './estadoTermodinamico.module.css';

export default function DefinirVolumen({h,volumenId,onGuardar}:{h:HojaMotor;volumenId:string;onGuardar:(cambio:(h:HojaMotor)=>HojaMotor)=>void}){
  const [mostrarTodos,setMostrarTodos]=useState(false),tipo=tipoVolumenControl(h,volumenId),clave=claveGeometria(h,volumenId),dato=h.config.datos[clave]??{texto:'',unidad:'m3'},datos=datosVolumen(h,volumenId),c=configuracionHoja(h),visibles=mostrarTodos?datos:datos.filter(d=>d.funcion==='inicial'||d.id.includes('inicial_'));
  const solicitud=h.cierresDinamicos?.[volumenId]?prepararEnsamblajeTermodinamico(h,'vista').solicitud:null;
  return <>
    {balancesHoja(h).energia&&volumenId===contextoEnergiaHoja(h).volumenId&&<ElegirCierreEnergia h={h} volumenId={volumenId} onGuardar={onGuardar}/>}
    <section className={styles.definition} aria-label="Definición del volumen de control"><h2>¿Cómo se comporta la frontera?</h2><div className={styles.modeGrid}>{OPCIONES_VOLUMEN.map(o=><button key={o.id} aria-pressed={tipo===o.id} disabled={o.id==='presion_dada'&&volumenId!==contextoEnergiaHoja(h).volumenId} onClick={()=>onGuardar(q=>elegirVolumenControl(q,volumenId,o.id))}><span>{o.nombre}</span><small>{o.detalle}</small></button>)}</div>
      {tipo==='rigido'&&<div className={styles.geometryInput}><label htmlFor="valor-geometria">Volumen geométrico</label><input id="valor-geometria" value={dato.texto} placeholder="Valor constante" onChange={e=>onGuardar(q=>guardarGeometria(q,volumenId,{...dato,texto:e.target.value}))}/><select aria-label="Unidad del volumen geométrico" value={dato.unidad} onChange={e=>onGuardar(q=>guardarGeometria(q,volumenId,{...dato,unidad:e.target.value}))}><option value="m3">m³</option><option value="L">L</option></select></div>}
      {tipo==='presion_dada'&&<Link className={styles.next} href={`/motor/hojas/${h.id}/resolver#dato-${solicitud?.volumen.frontera.tipo==='presion_prescrita'?solicitud.volumen.frontera.presionId:'energia_p'}`}>Definir P exterior y sus unidades →</Link>}
      {tipo==='movil'&&<small className={styles.scope}>La frontera móvil conserva el trabajo de presión. Su relación mecánica debe declararse.</small>}
    </section>
    <div className={styles.layout}><section className={styles.paper} aria-label="Ecuaciones del volumen de control">{ecuacionesVolumenControl(h,volumenId).map(r=><article id={r.id} key={r.id}><h2>{r.titulo}</h2><FormulaMateria latex={r.latex} lectura={r.titulo} bloque/></article>)}<VariablesDelVolumen h={h} volumenId={volumenId}/></section>
      <section className={styles.dataMap} aria-label="Datos del modelo"><header><h2>{mostrarTodos?'Datos del modelo':'Condiciones iniciales'}</h2><Link href={`/motor/hojas/${h.id}/resolver`}>Completar valores →</Link></header>{visibles.map(d=><Link className={styles.dataRow} key={d.id} href={`/motor/hojas/${h.id}/resolver#dato-${d.id}`}><div><span>{d.nombre}</span><small>{d.papel}</small></div><span>{(solicitud?.datos[d.id]?.declaracion??c.datos[d.id])?.texto.trim()||'Sin valor'} <small>{nombreUnidad((solicitud?.datos[d.id]?.declaracion??c.datos[d.id])?.unidad??'')}</small></span></Link>)}{datos.length>visibles.length||mostrarTodos?<button className={styles.showData} aria-expanded={mostrarTodos} onClick={()=>setMostrarTodos(v=>!v)}>{mostrarTodos?'Mostrar solo iniciales':`Ver corrientes y parámetros · ${datos.length-visibles.length}`}</button>:null}<small className={styles.scope}>La consulta de propiedades no sustituye estos datos.</small></section>
    </div>
  </>;
}
