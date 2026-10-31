import { englishLabel } from '../models/english';
import type {EstructuraTermodinamica} from './estructuraTermodinamica';
import {fundamentosEquilibrio} from './relacionesTermodinamicas';
import FormulaMateria from './FormulaMateria';
import styles from './ecuacionesFinales.module.css';

/** Kept behind disclosure: framework and conservation audit never masquerade as
 * the backend's executed equation list or add to its degrees-of-freedom count. */
export default function FundamentoCierreEnsamblado({estructura}:{estructura:EstructuraTermodinamica}){
  return <details className={styles.definitions}>
    <summary>Closure foundations and connections</summary>
    <p className={styles.scope}>Thermodynamic framework · the executed equations are those published above by the Engine.</p>
    {estructura.cierres.map(c=><section className={styles.relations} key={c.volumenId} aria-label={`Closure foundation ${c.volumenId}`}>
      <h3>{c.volumenId} · {c.modelo?.id??'Missing model'} · equilibrium framework</h3>
      {c.reconstruccion!=='pendiente'&&c.politica&&fundamentosEquilibrio(c.reconstruccion,c.politica).map(r=><div className={styles.relation} key={r.id}>
        <span>{englishLabel(r.titulo)}</span><FormulaMateria latex={r.latex} lectura={englishLabel(r.titulo)} bloque/>
      </div>)}
    </section>)}
    <details className={styles.definitions}><summary>Structural conservation · shared transfers</summary>
      <p className={styles.scope}>Internal terms cancel by identity. This does not certify properties, stability or degrees of freedom.</p>
      <pre>{JSON.stringify({balances:estructura.balances,globales:estructura.globales,diagnosticos:estructura.diagnosticos},null,2)}</pre>
    </details>
  </details>;
}
