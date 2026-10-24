"use client";
import { useReducer, useState, type ReactNode } from 'react';
import ModelWorksheet from '../models/ModelWorksheet';
import ProgresoMateria from './ProgresoMateria';
import GestorComponentesMateria from './GestorComponentesMateria';
import VariablesMateria from './VariablesMateria';
import { iniciarRecorrido, recorridoMateria } from './recorridoMateria';
import type { AccionMateria, FormulacionMateria, RecorridoMateria } from './recorridoMateria';
import styles from './motor.module.css';
import { MaterialAssumptions } from './ModelAssumptions';
import type { Coordenadas } from './operadores';
import {englishLabel} from '../models/english';

export default function MateriaFundamental({historialInicial,onHistorial,enEnsamblaje=false,settings,volumeSelector,componentsOverride}:{settings?:ReactNode;volumeSelector?:ReactNode;historialInicial?:RecorridoMateria;onHistorial?:(history:RecorridoMateria,action?:AccionMateria)=>void;enEnsamblaje?:boolean;componentsOverride?:import('./materiaEstado').Componente[]}={}) {
  const [localHistory, dispatchReducer] = useReducer(recorridoMateria, historialInicial, h=>h??iniciarRecorrido());
  // Persisted models have one source of truth for both controls and equations.
  // A rejected save must not leave an optimistic, unsaved checkbox selected.
  const historial=onHistorial&&historialInicial?historialInicial:localHistory;
  const dispatch=(accion:AccionMateria)=>{if(onHistorial)onHistorial(recorridoMateria(historial,accion),accion);else dispatchReducer(accion);};
  const current=historial.pasos[historial.activo].formulacion;
  const f = componentsOverride?{...current,componentes:componentsOverride}:current;
  const componentHistory=componentsOverride?{...historial,pasos:historial.pasos.map((p,i)=>i===historial.activo?{...p,formulacion:f}:p)}:historial;
  const [coordinateReview,setCoordinateReview]=useState<Coordenadas|null>(null);
  const cambiar = (titulo: string, cambios: Partial<FormulacionMateria>) => dispatch({ tipo: 'cambiar', titulo, cambios });
  function seleccionPaso(indice: number) { setCoordinateReview(null); dispatch({ tipo: 'ir', indice }); }
  function sourceStep(index:number){if(index<historial.pasos.length){seleccionPaso(index);return;}dispatch({tipo:'rehacer'});}
  return <div className={styles.page}>
    <header className={styles.header}><span className={styles.eyebrow}>Fundamental conservation laws</span><h2 className={styles.tituloBalance}>Matter balance</h2><span className={styles.scope}>Symbolic derivation · per component · mass basis</span></header>
    {volumeSelector}
    <ModelWorksheet settings={settings} family="materia" label="Matter equations" assumptions={<><fieldset className={styles.operationGroup}><legend>Physical changes</legend><div className={styles.boundaryActions}><button disabled={historial.activo===0} onClick={()=>seleccionPaso(historial.activo-1)}>Undo last assumption</button><button disabled={!historial.rehacer?.length} onClick={()=>sourceStep(historial.pasos.length)}>Redo assumption</button></div><p className={styles.groupHint}>Undo reverses one change and keeps it available to redo. Read the development on the left to inspect earlier equations.</p><details><summary>Recorded physical assumptions · {historial.activo}</summary><ol>{historial.pasos.slice(0,historial.activo+1).map((p,index)=><li key={index}>{englishLabel(p.titulo)}</li>)}</ol>{!!historial.rehacer?.length&&<p>{historial.rehacer.length} later changes available to redo. Making a new change replaces that redo branch.</p>}</details></fieldset><MaterialAssumptions formulation={f} stepNumber={historial.activo + 1} cambiar={cambiar} enEnsamblaje={enEnsamblaje} coordinateReview={{pending:coordinateReview,setPending:setCoordinateReview}} components={<GestorComponentesMateria historial={componentHistory} onCambiar={cambiar}/>}/></>} variables={<VariablesMateria formulacion={f}/>}>
        <article className={styles.equation}><header><h2>Fundamental balance</h2></header><div className={styles.wordBalance} aria-label="Accumulation = Inflow − Outflow + Generation − Consumption"><span>Accumulation</span><b>=</b><span>Inflow</span><b>−</b><span>Outflow</span><b>+</b><span>Generation</span><b>−</b><span>Consumption</span></div></article>
        <ProgresoMateria historial={historial} onIr={seleccionPaso} onRehacer={() => { setCoordinateReview(null); dispatch({ tipo: 'rehacer' }); }} onNueva={() => { setCoordinateReview(null); dispatch({ tipo: 'reiniciar' }); requestAnimationFrame(() => document.getElementById('workspace')?.scrollTo({ top: 0 })); }} />
    </ModelWorksheet>
  </div>;
}
