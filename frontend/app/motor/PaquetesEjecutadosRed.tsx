import type {ResultadoMotor} from './modeloNumerico';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './trabajoMotor.module.css';

/** Provenance from the saved execution, never inferred from today's selector. */
export default function PaquetesEjecutadosRed({ejecucion}:{ejecucion:NonNullable<ResultadoMotor['ensamblajeV2']>}){
  return <div className={styles.tableWrap}><table><caption>Packages in this run</caption><thead><tr><th>Volume</th><th>Package</th><th>Version</th><th>Data and parameter fingerprint</th></tr></thead><tbody>
    {ejecucion.solicitud.volumenes.map(v=>{
      const modelo=ejecucion.solicitud.paquetes.find(p=>p.id===v.paqueteId)?.modelo;
      const fuente=ejecucion.respuesta.resultados?.procedenciaModelo?.find(p=>p.volumenIds.includes(v.id));
      return <tr key={v.id}><td>{v.id}</td><td>{modelo?.id??'Not declared'}</td><td>{modelo?.version??'Not declared'}</td><td><span className={styles.parameterFingerprint}>{fuente?.huella??"Not published in this run"}</span></td></tr>;
    })}
  </tbody></table>
    <table><caption>Identities and molar masses used · first published sample</caption><thead><tr><th>Volume</th><th>Component · ID</th><th>Declared identity</th><th>CAS used</th><th>Declared molar mass</th><th>Molar mass used [kg/mol]</th><th>Source used</th></tr></thead><tbody>
      {ejecucion.solicitud.volumenes.flatMap(v=>v.componenteIds.map(id=>{
        const declarado=ejecucion.solicitud.componentes.find(c=>c.id===id);
        // Use this volume's saved evaluation, never today's property catalog,
        // another volume or a CAS-to-mass fallback. No value is filled into inputs.
        const usado=ejecucion.respuesta.resultados?.estados[v.id]?.[0]?.evaluacion.componentes.find(c=>c.id===id);
        const identidad=declarado?.identidadQuimica,m=declarado?.masaMolar;
        const identificadores=[identidad?.cas?`CAS ${identidad.cas}`:null,identidad?.proveedorId?`Provider ${identidad.proveedorId}`:null].filter(Boolean).join(' · ');
        return <tr key={`${v.id}:${id}`}><td>{v.id}</td><td>{declarado?.nombre??'Unnamed'} · {id}</td><td>{identificadores||'Not declared'}</td><td>{usado?.cas??'Not published'}</td><td>{m?<>{num(m.cantidad.valor,12)} {m.cantidad.unidad}<br/>{m.fuente}</>:'Not declared'}</td><td>{usado?num(usado.masaMolarKgMol,12):'Not published'}</td><td>{usado?.fuente??"Not published in this run"}</td></tr>;
      }))}
    </tbody></table>
    <details><summary>Declared pure-property overrides</summary>{ejecucion.solicitud.paquetes.some(p=>p.datosPuros&&Object.keys(p.datosPuros).length)?ejecucion.solicitud.paquetes.filter(p=>p.datosPuros).map(p=><section key={p.id}><h3>{p.id} · {p.modelo.id} · v{p.modelo.version}</h3><small>Volumes: {ejecucion.solicitud.volumenes.filter(v=>v.paqueteId===p.id).map(v=>v.id).join(', ')}</small><pre>{JSON.stringify(p.datosPuros,null,2)}</pre></section>):<p>No overrides declared in this run.</p>}</details>
  </div>;
}
