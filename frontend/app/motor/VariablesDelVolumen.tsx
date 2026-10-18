import Link from 'next/link';
import type {HojaMotor} from './hojasMotor';
import {variablesVolumen} from './papelesVariables';
import {nombreUnidad} from './unidadesMotor';
import FormulaMateria from './FormulaMateria';
import styles from './estadoTermodinamico.module.css';
export default function VariablesDelVolumen({h,volumenId}:{h:HojaMotor;volumenId:string}){
  const variables=variablesVolumen(h,volumenId);
  if(!variables.length)return null;
  return <section className={styles.variableMap} aria-label="Variables y ecuaciones del volumen"><h2>Variables del volumen</h2>{variables.map(v=><div className={styles.variableRow} key={v.id}><div><FormulaMateria latex={v.simbolo} lectura={v.nombre}/><small>{v.nombre} · {nombreUnidad(v.unidad)}</small></div><span className={styles.role}>{v.papel}</span>{v.papel==='Pendiente'||v.papel==='Sin modelo'?<small>{v.relacion}</small>:<Link href={v.enlace}>{v.relacion} →</Link>}</div>)}</section>;
}
