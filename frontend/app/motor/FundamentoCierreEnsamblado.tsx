import type {EstructuraTermodinamica} from './estructuraTermodinamica';
import {fundamentosEquilibrio} from './relacionesTermodinamicas';
import FormulaMateria from './FormulaMateria';
import styles from './ecuacionesFinales.module.css';

/** Kept behind disclosure: framework and conservation audit never masquerade as
 * the backend's executed equation list or add to its degrees-of-freedom count. */
export default function FundamentoCierreEnsamblado({estructura}:{estructura:EstructuraTermodinamica}){
  return <details className={styles.definitions}>
    <summary>Closure foundations and connections</summary>
    <p className={styles.scope}>Marco termodinámico · las ecuaciones ejecutadas son las publicadas arriba por el motor.</p>
    {estructura.cierres.map(c=><section className={styles.relations} key={c.volumenId} aria-label={`Fundamento del cierre ${c.volumenId}`}>
      <h3>{c.volumenId} · {c.modelo?.id??'Modelo pendiente'} · marco del equilibrio</h3>
      {c.reconstruccion!=='pendiente'&&c.politica&&fundamentosEquilibrio(c.reconstruccion,c.politica).map(r=><div className={styles.relation} key={r.id}>
        <span>{r.titulo}</span><FormulaMateria latex={r.latex} lectura={r.titulo} bloque/>
      </div>)}
    </section>)}
    <details className={styles.definitions}><summary>Structural conservation · shared transfers</summary>
      <p className={styles.scope}>Internal terms cancel by identity. This does not certify properties, stability or degrees of freedom.</p>
      <pre>{JSON.stringify({balances:estructura.balances,globales:estructura.globales,diagnosticos:estructura.diagnosticos},null,2)}</pre>
    </details>
  </details>;
}
