import type {ResultadoMotor} from './modeloNumerico';
import {formatearNumeroMotor} from './formatearNumeroMotor';
import {nombreUnidad} from './unidadesMotor';
import styles from './trabajoMotor.module.css';
const nombres:Record<string,string>={aparicion_fase:"Phase appearance",desaparicion_fase:"Phase disappearance",fase_ausente:"Extracted phase depleted",cambio_denominacion:'Cambio de denominación',cambio_fase_prohibido:'Cambio de fase no permitido'};
export default function DetallesEnsamblaje({r}:{r:ResultadoMotor}){
  const e=r.ensamblajeTermodinamico!,a=e.respuesta.resultados!,ultimo=a.estadosTermodinamicos.at(-1)!;
  return <div className={styles.variables}><h2>Method</h2><p>{a.metodo}</p><h2>Estado final · {formatearNumeroMotor(a.tiempos.at(-1)!)} s</h2><p>{formatearNumeroMotor(ultimo.T)} K · {formatearNumeroMotor(ultimo.P)} Pa · {a.estadosTermodinamicos.length} muestras certificadas</p><div className={styles.tableWrap}><table><thead><tr><th>Fase</th><th>Mass fraction</th><th>Volume fraction</th><th>u [J/kg]</th><th>h [J/kg]</th></tr></thead><tbody>{ultimo.fases.map(f=><tr key={f.id}><td>{f.tipo}</td><td>{formatearNumeroMotor(f.fraccionMasica)}</td><td>{formatearNumeroMotor(f.fraccionVolumen)}</td><td>{formatearNumeroMotor(f.propiedades.u)}</td><td>{formatearNumeroMotor(f.propiedades.h)}</td></tr>)}</tbody></table></div>
    <h2>Eventos · {a.eventos.length}</h2>{a.eventos.length>0&&<div className={styles.tableWrap}><table><thead><tr><th>Evento</th><th>Tiempo [s]</th></tr></thead><tbody>{a.eventos.map((v,i)=><tr key={i}><td>{nombres[v.codigo]??v.codigo}</td><td>{formatearNumeroMotor(v.tiempo)}</td></tr>)}</tbody></table></div>}
    <h2>Residuos certificados</h2><div className={styles.tableWrap}><table><thead><tr><th>Equation</th><th>Maximum scaled residual</th><th>Tolerancia</th></tr></thead><tbody>{a.residuos.map(q=><tr key={q.ecuacionId}><td>{q.ecuacionId}</td><td>{q.maximoEscalado.toExponential(3)}</td><td>{q.tolerancia.toExponential(3)}</td></tr>)}</tbody></table></div>
    <details className={styles.settings}><summary>Variables y ecuaciones ejecutadas</summary><table><thead><tr><th>Variable</th><th>Papel</th><th>Unidad</th></tr></thead><tbody>{e.respuesta.validacion.variables.map(v=><tr key={v.id}><td>{v.id}</td><td>{v.papel}</td><td>{nombreUnidad(v.unidadSI)}</td></tr>)}</tbody></table><pre>{JSON.stringify({modeloId:e.respuesta.validacion.modeloId,recuento:e.respuesta.validacion.recuento,ecuaciones:e.respuesta.validacion.ecuaciones,diagnosticos:e.respuesta.validacion.diagnosticos},null,2)}</pre></details>
    <details className={styles.settings}><summary>Submitted request and sample certificates</summary><pre>{JSON.stringify(e,null,2)}</pre></details>
  </div>;
}
