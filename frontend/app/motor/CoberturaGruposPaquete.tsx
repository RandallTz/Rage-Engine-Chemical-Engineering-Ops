import type {CoberturaGrupos} from './contratoContribucionGrupos';
import type {Componente} from './materiaEstado';
import {nombreVarianteUNIFAC,resumirCoberturaGrupos} from './coberturaGrupos';
import styles from './coberturaGrupos.module.css';

export default function CoberturaGruposPaquete({cobertura,componentes}:{cobertura:CoberturaGrupos;componentes:Componente[]}){
  const r=resumirCoberturaGrupos(cobertura,componentes),d=cobertura.datos;
  const pendiente={sin_identidad:'Identidad sin declarar',sin_asignacion:"No assignment in this table",fuera_catalogo:"Outside the published catalog"};
  return <section className={styles.coverage} aria-label="Cobertura de grupos del paquete">
    <h3>{nombreVarianteUNIFAC(cobertura.variante)}</h3>
    <p>Asignaciones publicadas · {r.asignadas} / {componentes.length} componentes</p>
    <div className={styles.scroll}><table><thead><tr><th>Componente</th><th>Subgrupos · cantidad × nombre (ID)</th></tr></thead><tbody>{r.filas.map(f=><tr key={f.componente.id}><th scope="row">{f.componente.nombre}<small>{f.componente.identidadQuimica?.cas??'Sin CAS'}</small></th><td>{f.asignacion?f.asignacion.subgrupos.map(g=>`${g.cuenta} × ${g.nombre} (${g.id})`).join(' + '):pendiente[f.estado as keyof typeof pendiente]}</td></tr>)}</tbody></table></div>
    {r.interaccionesFaltantes.length>0?<p role="status">Interacciones dirigidas sin datos · {r.interaccionesFaltantes.map(([m,n])=>`${m} → ${n}`).join(', ')}</p>:<p>{r.asignadas?"No missing interactions are published between the groups identified in this selection.":"No groups identified for this selection."}</p>}
    <small>Data coverage. State and stability are checked during evaluation.</small>
    <details><summary>Group and table provenance</summary>
      {r.filas.filter(f=>f.asignacion).map(f=><p key={f.componente.id}>{f.componente.nombre} · {f.asignacion!.procedencia}</p>)}
      <dl><dt>Interaction table</dt><dd>{d.fuente_interacciones}</dd><dt>SHA-256 · interacciones</dt><dd className={styles.hash}>{d.sha256_interacciones}</dd><dt>Asignaciones</dt><dd>{d.fuente_asignaciones}</dd><dt>SHA-256 · asignaciones</dt><dd className={styles.hash}>{d.sha256_asignaciones}</dd><dt>Subgrupos</dt><dd>{d.fuente_subgrupos}</dd>{d.fuente_tabla&&<><dt>Table source</dt><dd>{d.fuente_tabla}</dd></>}{d.rango_T_datos&&<><dt>Rango de ajuste de la tabla</dt><dd>{d.rango_T_datos.join('–')} K</dd></>}</dl>
      <p>{cobertura.nota}</p>
    </details>
  </section>;
}
