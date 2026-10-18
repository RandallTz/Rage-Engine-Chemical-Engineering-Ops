import Link from 'next/link';
import type {HojaMotor} from './hojasMotor';
import {balancesHoja} from './seleccionBalances';
import {formulacionHoja} from './modeloHojaMotor';
import {ecuacionesEnsamblaje} from './ensamblajeMateria';
import {balancesComponentes} from './recorridoMateria';
import {formulacionEnergiaHoja,contextoEnergiaHoja} from './estadoEnergiaHoja';
import {ecuacionEnergia} from './recorridoEnergia';
import {relacionesSistemaEnergia} from './ecuacionesSistemaEnergia';
import FormulaMateria from './FormulaMateria';
import styles from './ecuacionesFinales.module.css';

/** Presentation only: equations keep the same structured formulation used by the compiler. */
export default function EcuacionesFinales({hoja:h}:{hoja:HojaMotor}){
  const b=balancesHoja(h),e=formulacionEnergiaHoja(h);
  const relaciones=relacionesSistemaEnergia(h),activas=relaciones.filter(q=>!q.definicion),definiciones=relaciones.filter(q=>q.definicion);
  const relacion=(q:typeof relaciones[number])=><div id={q.id} className={styles.relation} key={q.id}><span>{q.nombre}</span><FormulaMateria latex={q.latex} lectura={q.nombre} bloque/>{q.datos.length>0&&<Link href={`/motor/hojas/${h.id}/resolver#dato-${q.datos[0]}`} aria-label={`Definir datos de ${q.nombre}`}>Datos →</Link>}</div>;
  const materia=h.ensamblaje?ecuacionesEnsamblaje(h.ensamblaje).flatMap(v=>v.ecuaciones.map(q=>({id:`${v.id}_${q.componente.id}`,ancla:`balance-materia-${v.id}-${q.componente.id}`,nombre:`${v.nombre} · ${q.componente.nombre}`,latex:q.latex}))):balancesComponentes(formulacionHoja(h)).map(q=>({id:String(q.componente?.id??'i'),ancla:`balance-materia-dominio-${q.componente?.id??'i'}`,nombre:q.componente?.nombre??'Componente i',latex:q.latex}));
  return <section className={styles.paper} aria-label="Ecuaciones finales">
    <header className={styles.heading}><h2>Ecuaciones finales</h2><Link href={`/motor/hojas/${h.id}`}>Ver derivación →</Link></header>
    {b.materia&&materia.map(q=><div id={q.ancla} className={styles.balance} data-familia="materia" key={q.id}>
      <div className={styles.label}><span className={styles.family}>Materia</span><span>{q.nombre}</span></div>
      <div className={styles.formula}><FormulaMateria latex={q.latex} lectura={`Balance de materia · ${q.nombre}`} bloque/></div>
    </div>)}
    {b.energia&&<div id="balance-energia" className={styles.balance} data-familia="energia">
      <div className={styles.label}><span className={styles.family}>Energía</span><span>Volumen de control</span></div>
      <div className={styles.formula}><FormulaMateria latex={ecuacionEnergia(e,contextoEnergiaHoja(h))} lectura="Balance de energía del volumen" bloque/></div>
    </div>}
    {b.energia&&<section className={styles.relations} aria-label="Relaciones activas del sistema"><h3>Relaciones activas</h3>{activas.map(relacion)}{definiciones.length>0&&<details className={styles.definitions}><summary>Definiciones de los términos</summary>{definiciones.map(relacion)}</details>}</section>}
  </section>;
}
