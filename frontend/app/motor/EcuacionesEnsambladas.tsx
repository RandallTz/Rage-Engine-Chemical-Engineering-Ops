import type {RespuestaValidacionDinamica,SolicitudEnsamblajeDinamico} from './contratoEnsamblajeTermodinamico';
import FormulaMateria from './FormulaMateria';
import styles from './ecuacionesFinales.module.css';
import {anclaEcuacionDinamica,nombreEcuacionDinamica,nombreVariableDinamica,ecuacionesDeVariable} from './presentacionEnsamblaje';
import {estructuraSolicitudDinamica} from './estructuraTermodinamica';
import type {EstructuraTermodinamica} from './estructuraTermodinamica';
import FundamentoCierreEnsamblado from './FundamentoCierreEnsamblado';
export default function EcuacionesEnsambladas({r,s,estructura}:{r:RespuestaValidacionDinamica;s:SolicitudEnsamblajeDinamico;estructura?:EstructuraTermodinamica}){
  return <section className={styles.paper} aria-label="Ecuaciones ensambladas por el motor">
    <header className={styles.heading}><h2>Ecuaciones del modelo · {s.volumen.cierre.modelo.id}</h2></header>
    {r.ecuaciones.filter(e=>['materia','energia'].includes(e.familia)).map(e=><div id={anclaEcuacionDinamica(e.id)} tabIndex={-1} className={styles.balance} data-familia={e.familia} key={e.id}>
      <div className={styles.label}><span className={styles.family}>{nombreEcuacionDinamica(e.id)}</span><span>{s.volumen.id}</span></div>
      <div className={styles.formula}><FormulaMateria latex={e.latex} lectura={nombreEcuacionDinamica(e.id)} bloque/></div>
    </div>)}
    <section className={styles.relations}><h3>Relaciones ensambladas</h3>{r.ecuaciones.filter(e=>!['materia','energia'].includes(e.familia)).map(e=><div id={anclaEcuacionDinamica(e.id)} tabIndex={-1} className={styles.relation} key={e.id}>
      <span>{nombreEcuacionDinamica(e.id)}</span><FormulaMateria latex={e.latex} lectura={nombreEcuacionDinamica(e.id)} bloque/>
    </div>)}</section>
    <details className={styles.definitions} id="variables-calculadas"><summary>Variables calculadas · {r.variables.filter(v=>['diferencial','algebraica'].includes(v.papel)).length}</summary>
      {r.variables.filter(v=>['diferencial','algebraica'].includes(v.papel)).map(v=><div className={styles.variable} key={v.id}><span>{nombreVariableDinamica(v.id,s)} <small>{v.unidadSI}</small></span><div aria-label={`Ecuaciones relacionadas con ${nombreVariableDinamica(v.id,s)}`}>{ecuacionesDeVariable(r,v.id).map(e=><a key={e.id} href={`#${anclaEcuacionDinamica(e.id)}`}>{nombreEcuacionDinamica(e.id)}</a>)}</div></div>)}
    </details>
    <FundamentoCierreEnsamblado estructura={estructura??estructuraSolicitudDinamica(s)}/>
  </section>;
}
