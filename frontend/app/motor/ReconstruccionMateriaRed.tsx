'use client';
import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import {formatearNumeroMotor as numero} from './formatearNumeroMotor';
import styles from './trabajoMotor.module.css';

/** Inspection of existing values. A closed material reconstruction is not
 * a new certificate of EOS accuracy or of the complete dynamic balance. */
export default function ReconstruccionMateriaRed({muestra}:{muestra:ContextoMuestraEquilibrio}){
  return <details className={styles.settings}>
    <summary>Matter reconstruction by phase</summary>
    <div className={styles.tableWrap}><table><thead><tr><th>Componente</th><th>Cantidad integrada [mol]</th>{muestra.fases.map(f=><th key={f.id}>{f.tipo} · {f.id} [mol]</th>)}<th>Phase sum [mol]</th><th>Δn [mol]</th><th>Masa [kg]</th><th>Δm [kg]</th></tr></thead><tbody>{muestra.inventarios.map(c=><tr key={c.id}><td>{c.nombre}</td><td>{numero(c.n)}</td>{c.fases.map(f=><td key={f.faseId}>{numero(f.n)}</td>)}<td>{numero(c.nReconstruido)}</td><td>{numero(c.residuoN)}</td><td>{numero(c.m)}</td><td>{numero(c.residuoM)}</td></tr>)}</tbody></table></div>
    <small className={styles.muted}>Δ = suma de fases − cantidad integrada. Reconstrucción de esta muestra; no añade una certificación de la trayectoria.</small>
  </details>;
}
