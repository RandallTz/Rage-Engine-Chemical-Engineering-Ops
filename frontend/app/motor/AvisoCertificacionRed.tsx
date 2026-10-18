'use client';
import type {RespuestaResolucionV2} from './contratoEnsamblajeV2';
import {intervaloNoCertificado,resumenCertificacion} from './metadatosRed';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './trabajoMotor.module.css';
export default function AvisoCertificacionRed({resultado,verDetalles}:{resultado:NonNullable<RespuestaResolucionV2['resultados']>;verDetalles:()=>void}){
  const tramo=intervaloNoCertificado(resultado),falla=resultado.certificacion?.estado==='no_cumple';
  return <div role={falla?'alert':'status'} data-certificacion={resultado.certificacion?.estado??'anterior'} className={`${falla?styles.error:styles.notice} ${styles.certification}`}><span>{resumenCertificacion(resultado)}{tramo?resultado.certificacion?.ultimaMuestraCertificada===null?' · sin muestras aprobadas; evidencia completa':` · última muestra aprobada: ${num(tramo[0])} s; evidencia completa`:''}</span><button onClick={verDetalles}>Ver certificación</button></div>;
}
