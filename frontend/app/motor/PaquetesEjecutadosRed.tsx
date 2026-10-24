import type {ResultadoMotor} from './modeloNumerico';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './trabajoMotor.module.css';

/** Provenance from the saved execution, never inferred from today's selector. */
export default function PaquetesEjecutadosRed({ejecucion}:{ejecucion:NonNullable<ResultadoMotor['ensamblajeV2']>}){
  return <div className={styles.tableWrap}><table><caption>Packages in this run</caption><thead><tr><th>Volumen</th><th>Paquete</th><th>Version</th><th>Data and parameter fingerprint</th></tr></thead><tbody>
    {ejecucion.solicitud.volumenes.map(v=>{
      const modelo=ejecucion.solicitud.paquetes.find(p=>p.id===v.paqueteId)?.modelo;
      const fuente=ejecucion.respuesta.resultados?.procedenciaModelo?.find(p=>p.volumenIds.includes(v.id));
      return <tr key={v.id}><td>{v.id}</td><td>{modelo?.id??'No declarado'}</td><td>{modelo?.version??'No declarada'}</td><td><span className={styles.parameterFingerprint}>{fuente?.huella??"Not published in this run"}</span></td></tr>;
    })}
  </tbody></table>
    <table><caption>Identidades y masas molares usadas · primera muestra publicada</caption><thead><tr><th>Volumen</th><th>Componente · ID</th><th>Identidad declarada</th><th>CAS usado</th><th>Masa molar declarada</th><th>Masa molar usada [kg/mol]</th><th>Fuente usada</th></tr></thead><tbody>
      {ejecucion.solicitud.volumenes.flatMap(v=>v.componenteIds.map(id=>{
        const declarado=ejecucion.solicitud.componentes.find(c=>c.id===id);
        // Use this volume's saved evaluation, never today's property catalog,
        // another volume or a CAS-to-mass fallback. No value is filled into inputs.
        const usado=ejecucion.respuesta.resultados?.estados[v.id]?.[0]?.evaluacion.componentes.find(c=>c.id===id);
        const identidad=declarado?.identidadQuimica,m=declarado?.masaMolar;
        const identificadores=[identidad?.cas?`CAS ${identidad.cas}`:null,identidad?.proveedorId?`Proveedor ${identidad.proveedorId}`:null].filter(Boolean).join(' · ');
        return <tr key={`${v.id}:${id}`}><td>{v.id}</td><td>{declarado?.nombre??'Sin nombre'} · {id}</td><td>{identificadores||'Sin declarar'}</td><td>{usado?.cas??'No publicado'}</td><td>{m?<>{num(m.cantidad.valor,12)} {m.cantidad.unidad}<br/>{m.fuente}</>:'Sin declarar'}</td><td>{usado?num(usado.masaMolarKgMol,12):'No publicada'}</td><td>{usado?.fuente??"Not published in this run"}</td></tr>;
      }))}
    </tbody></table>
    <details><summary>Declared pure-property overrides</summary>{ejecucion.solicitud.paquetes.some(p=>p.datosPuros&&Object.keys(p.datosPuros).length)?ejecucion.solicitud.paquetes.filter(p=>p.datosPuros).map(p=><section key={p.id}><h3>{p.id} · {p.modelo.id} · v{p.modelo.version}</h3><small>Volumes: {ejecucion.solicitud.volumenes.filter(v=>v.paqueteId===p.id).map(v=>v.id).join(', ')}</small><pre>{JSON.stringify(p.datosPuros,null,2)}</pre></section>):<p>Sin sustituciones declaradas en esta ejecución.</p>}</details>
  </div>;
}
