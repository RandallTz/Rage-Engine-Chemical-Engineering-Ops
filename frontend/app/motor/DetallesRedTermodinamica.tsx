'use client';
import {useState} from 'react';
import type {ResultadoMotor} from './modeloNumerico';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import {nombreEventoRed,nombrePapelSerie,resumenCertificacion} from './metadatosRed';
import {repartoComponente} from './resultadoEnsamblajeV2';
import {contextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import ReconstruccionMateriaRed from './ReconstruccionMateriaRed';
import PaquetesEjecutadosRed from './PaquetesEjecutadosRed';
import FormulaMateria from './FormulaMateria';
import styles from './trabajoMotor.module.css';
const aspectos:Record<string,string>={estados_termodinamicos:'Estados termodinámicos',conservacion:'Conservación',cierre_constitutivo:'Cierre constitutivo',segunda_ley:'Segunda ley'};
export default function DetallesRedTermodinamica({r}:{r:ResultadoMotor}){
  const [k,setK]=useState(r.tiempos.length-1),[vid,setVid]=useState('');
  const e=r.ensamblajeV2!,a=e.respuesta.resultados!,c=a.certificacion,v=e.solicitud.volumenes.find(v=>v.id===vid)??e.solicitud.volumenes[0],m=a.estados[v.id][k];
  const unidades=m.potenciales.unidades;
  const muestra=contextoMuestraEquilibrio(r,v.id,k);
  return <div className={styles.variables}>
    <h2>{resumenCertificacion(a)}</h2>
    {c&&<><p>{c.motivo}</p><div className={styles.tableWrap}><table><thead><tr><th>Aspecto</th><th>Estado</th><th>Primer incumplimiento</th></tr></thead><tbody>{c.aspectos.map(x=><tr key={x.id}><td title={x.motivo}>{aspectos[x.id]}</td><td>{x.estado.replaceAll('_',' ')}</td><td>{x.primeraMuestraNoCumple===null?'—':`${num(a.tiempos[x.primeraMuestraNoCumple])} s`}</td></tr>)}</tbody></table></div><p>{c.alcance.muestras} muestras · {num(c.alcance.tInicial)}–{num(c.alcance.tFinal)} s · {c.alcance.completa?'Horizonte completo':'Horizonte parcial'}</p>{c.estado==='no_cumple'&&<p>Última muestra sin incumplimientos comprobados: {c.ultimaMuestraCertificada===null?'ninguna':`${num(a.tiempos[c.ultimaMuestraCertificada])} s`}. Se conserva toda la evidencia.</p>}<details className={styles.settings}><summary>Referencias de certificación</summary><PaquetesEjecutadosRed ejecucion={e}/><pre>{JSON.stringify(c.aspectos,null,2)}</pre></details></>}
    <h2>Estado y fases por muestra</h2><div className={styles.boundaries}>{e.solicitud.volumenes.map(v=><button key={v.id} aria-pressed={v.id===m.volumenId} onClick={()=>setVid(v.id)}>{v.id}</button>)}</div>
    <label>t = {num(r.tiempos[k])} s <input aria-label="Muestra termodinámica" type="range" min={0} max={r.tiempos.length-1} value={k} onChange={e=>setK(Number(e.target.value))}/></label>
    {c?.estado==='no_cumple'&&(c.ultimaMuestraCertificada===null||k>c.ultimaMuestraCertificada)&&<p role="status">Muestra en el tramo sin certificar.</p>}
    <p>{num(m.evaluacion.T)} K · {num(m.evaluacion.P)} Pa</p><div className={styles.tableWrap}><table><thead><tr><th>Fase · ID</th><th>Fracción molar</th><th>Fracción másica</th><th>Fracción de volumen</th>{v.componenteIds.map(id=><th key={id}>Composición molar · {e.solicitud.componentes.find(c=>c.id===id)?.nombre}</th>)}</tr></thead><tbody>{m.evaluacion.fases.map(f=><tr key={f.id}><td>{f.tipo} · {f.id}</td><td>{num(f.fraccionMolar)}</td><td>{num(f.fraccionMasica)}</td><td>{num(f.fraccionVolumen)}</td>{v.componenteIds.map(id=><td key={id}>{num(f.composicionMolar[id])}</td>)}</tr>)}</tbody></table></div>
    <h3>Reparto por componente</h3><div className={styles.tableWrap}><table><thead><tr><th>Componente</th>{m.evaluacion.fases.map(f=><th key={f.id}>Fracción en {f.tipo} · {f.id}</th>)}</tr></thead><tbody>{v.componenteIds.map(id=><tr key={id}><td>{e.solicitud.componentes.find(c=>c.id===id)?.nombre}</td>{m.evaluacion.fases.map(f=>{const valor=repartoComponente(m.evaluacion,f.id,id);return <td key={f.id}>{Number.isFinite(valor)?num(valor):'—'}</td>;})}</tr>)}</tbody></table></div>
    <ReconstruccionMateriaRed muestra={muestra}/>
    <details className={styles.settings}><summary>Segunda ley · {a.segundaLey.estado.replaceAll('_',' ')}</summary><p>{a.segundaLey.motivo}</p>{a.segundaLey.generacionMinima!==null&&<p>Mínimo: {num(a.segundaLey.generacionMinima)} J/K</p>}</details>
    <details className={styles.settings}><summary>Potenciales químicos y estabilidad</summary><p>Referencia: {m.potenciales.referencia.descripcion}</p><p>{m.potenciales.metodo}</p><div className={styles.tableWrap}><table><thead><tr><th>Fase</th>{v.componenteIds.map(id=><th key={id}>μ · {e.solicitud.componentes.find(c=>c.id===id)?.nombre} [J/mol]</th>)}</tr></thead><tbody>{m.potenciales.fases.map(f=><tr key={f.faseId}><td>{f.faseId}</td>{v.componenteIds.map(id=><td key={id}>{f.mu[id]==null?'No aplica':num(f.mu[id])}</td>)}</tr>)}</tbody></table></div>{unidades?<p>G = {num(m.potenciales.G)} {unidades.G} · A = {num(m.potenciales.A)} {unidades.A} · S = {num(m.potenciales.S)} {unidades.S} · totales del volumen</p>:<p>Esta ejecución no declara las unidades de G, A y S. Vuelve a resolver para consultarlos.</p>}<pre>{JSON.stringify(m.evaluacion.verificaciones,null,2)}</pre></details>
    <details className={styles.settings}><summary>Eventos · {a.eventos.length}</summary>{a.eventos.map((x,i)=><article key={i}><h3>{nombreEventoRed(x.codigo)} · {num(x.tiempo)} s · {x.volumenId??'red'}</h3>{x.faseIdsAntes&&x.faseIdsDespues?<p>{x.faseIdsAntes.join(', ')||'∅'} → {x.faseIdsDespues.join(', ')||'∅'}</p>:<p>{x.faseIds.join(', ')}</p>}{x.descripcion&&<p>{x.descripcion}</p>}</article>)}<p>Vigilancia puntual dentro de cada paso; no es una certificación continua de eventos.</p></details>
    <details className={styles.settings}><summary>Catálogo de series · {a.catalogoSeries?.length??'no disponible'}</summary>{a.catalogoSeries?<div className={styles.tableWrap}><table><thead><tr><th>Serie</th><th>Unidad SI</th><th>Magnitud</th><th>Obtención</th><th>Variable del ensamblaje</th></tr></thead><tbody>{a.catalogoSeries.map(x=><tr key={x.variableId}><td title={x.procedencia}>{x.variableId}</td><td>{x.unidadSI}</td><td>{x.magnitud}</td><td>{nombrePapelSerie(x.papel)}</td><td>{x.variableEnsamblajeId??'Presentación'}</td></tr>)}</tbody></table></div>:<p>La ejecución anterior no incluye el catálogo. Vuelve a resolver para obtenerlo.</p>}</details>
    <details className={styles.settings}><summary>Ecuaciones ejecutadas y residuos</summary>{e.respuesta.validacion.ecuaciones.map(q=><article className={styles.equations} key={q.id}><h2>{q.propietarioId} · {q.id}</h2><FormulaMateria latex={q.latex} lectura={q.id} bloque/><small>{q.procedencia.relacion}</small></article>)}<pre>{JSON.stringify(a.residuos,null,2)}</pre></details>
    <details className={styles.settings}><summary>Solicitud y certificados originales</summary><pre>{JSON.stringify(e,null,2)}</pre></details>
  </div>;
}
