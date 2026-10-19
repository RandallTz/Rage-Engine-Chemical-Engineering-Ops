'use client';
import {useState} from 'react';
import {FAMILIAS_BALANCE,PANEL_TERMODINAMICA} from './familiasBalance';
import type {FamiliaBalance,VistaHoja} from './familiasBalance';
import type {SeleccionBalances} from './seleccionBalances';
import FormaBalance from './FormaBalance';
import styles from './balances.module.css';

export default function PanelesBalances({vista,balances,onVista,onBalance,fijos}:{vista:VistaHoja;balances:SeleccionBalances;onVista:(f:VistaHoja)=>void;onBalance:(f:FamiliaBalance,activo:boolean)=>void;
  /** Hojas cuya red fija los balances (red termodinámica): los interruptores solo informan. */
  fijos?:string}){
  const [pausado,setPausado]=useState(false);
  return <section className={styles.selector} aria-label="Balances del sistema">
    <div className={styles.selectorTop}><span>Balances del sistema</span><button onClick={()=>setPausado(v=>!v)} aria-pressed={pausado}>{pausado?'Reanudar movimiento':'Pausar movimiento'}</button></div>
    <div className={styles.paneles}>{FAMILIAS_BALANCE.map(f=><article key={f.id} className={styles.panel} data-familia={f.id} data-seleccionado={vista===f.id}>
      <button className={styles.abrirBalance} onClick={()=>onVista(f.id)} aria-pressed={vista===f.id} aria-label={`Ver balance de ${f.nombre.toLowerCase()}`}>
        <div className={styles.visual}><FormaBalance familia={f.id} pausado={pausado}/></div>
        <div className={styles.panelTexto}><h2>{f.nombre}</h2><p>{f.descripcion}</p><span className={styles.accion}>{vista===f.id?'Viendo ecuaciones':'Ver ecuaciones'}<svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg></span></div>
      </button>
      <div className={styles.activacion}><label title={fijos}><input type="checkbox" role="switch" aria-label={`Activar balance de ${f.nombre.toLowerCase()}`} checked={balances[f.id]} disabled={!!fijos} onChange={e=>onBalance(f.id,e.target.checked)}/><span className={styles.switchVisual} aria-hidden="true"/><span>{balances[f.id]?'Activo':'Inactivo'}</span></label>{fijos?<small>Lo fija la red</small>:<>{f.id==='momento'&&<small>Solver pendiente</small>}{f.id==='energia'&&<small>Temporal · 1 volumen</small>}</>}</div>
    </article>)}
    <article className={styles.panel} data-familia={PANEL_TERMODINAMICA.id} data-seleccionado={vista===PANEL_TERMODINAMICA.id}>
      <button className={styles.abrirBalance} onClick={()=>onVista(PANEL_TERMODINAMICA.id)} aria-pressed={vista===PANEL_TERMODINAMICA.id} aria-label="Ver la termodinámica del sistema">
        <div className={styles.visual}><FormaBalance familia={PANEL_TERMODINAMICA.id} pausado={pausado}/></div>
        <div className={styles.panelTexto}><h2>{PANEL_TERMODINAMICA.nombre}</h2><p>{PANEL_TERMODINAMICA.descripcion}</p><span className={styles.accion}>{vista===PANEL_TERMODINAMICA.id?'Viendo ecuaciones':'Ver ecuaciones'}<svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg></span></div>
      </button>
      <div className={styles.activacion}><span className={styles.siempre}>Siempre presente</span><small>Cierre de estado</small></div>
    </article></div>
  </section>;
}
