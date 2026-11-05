import type {ConjuntoResultados} from '../../motores/resultados/contrato';
import {nombreEventoRed} from './metadatosRed';
import {formatearNumeroMotor} from './formatearNumeroMotor';
import styles from './trabajoMotor.module.css';

/** Reuse assembly event labels; display only the published common time events. */
export function commonTimeEvents(result:ConjuntoResultados|undefined) {
  const axes=new Set(result?.ejes.filter(axis=>axis.rol==='tiempo'&&axis.unidadSI==='s').map(axis=>axis.id));
  return result?.eventos.filter(event=>axes.has(event.ejeId))??[];
}

export function ResultEvents({result}:{result:ConjuntoResultados|undefined}) {
  const events=commonTimeEvents(result);
  if(!result)return null;
  return <details className={styles.settings} open><summary>Events · {events.length}</summary>
    {events.map((event,index)=><article key={index}>
      <h3>{nombreEventoRed(event.codigo)} · {formatearNumeroMotor(event.valor)} s · {event.propietarioId??'model'}</h3>
      <p>{event.descripcion}</p>
    </article>)}
    <p>Published events only. Checks within each step do not constitute continuous event certification.</p>
  </details>;
}
