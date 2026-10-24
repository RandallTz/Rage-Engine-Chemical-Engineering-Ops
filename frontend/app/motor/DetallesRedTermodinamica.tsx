'use client';
import {useState} from 'react';
import type {ResultadoMotor} from './modeloNumerico';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import {nombreEventoRed,nombrePapelSerie,resumenCertificacion,certificationStatusName} from './metadatosRed';
import {repartoComponente} from './resultadoEnsamblajeV2';
import {contextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import ReconstruccionMateriaRed from './ReconstruccionMateriaRed';
import PaquetesEjecutadosRed from './PaquetesEjecutadosRed';
import FormulaMateria from './FormulaMateria';
import styles from './trabajoMotor.module.css';
const aspectos:Record<string,string>={estados_termodinamicos:"Thermodynamic states",conservacion:"Conservation",cierre_constitutivo:'Constitutive closure',segunda_ley:'Second law'};
export default function DetallesRedTermodinamica({r}:{r:ResultadoMotor}){
  const [k,setK]=useState(r.tiempos.length-1),[vid,setVid]=useState('');
  const e=r.ensamblajeV2!,a=e.respuesta.resultados!,c=a.certificacion,v=e.solicitud.volumenes.find(v=>v.id===vid)??e.solicitud.volumenes[0],m=a.estados[v.id][k];
  const unidades=m.potenciales.unidades;
  const muestra=contextoMuestraEquilibrio(r,v.id,k);
  return <div className={styles.variables}>
    <h2>{resumenCertificacion(a)}</h2>
    {c&&<><p>{c.motivo}</p><div className={styles.tableWrap}><table><thead><tr><th>Aspect</th><th>Status</th><th>First failed sample</th></tr></thead><tbody>{c.aspectos.map(x=><tr key={x.id}><td title={x.motivo}>{aspectos[x.id]}</td><td>{certificationStatusName(x.estado)}</td><td>{x.primeraMuestraNoCumple===null?'—':`${num(a.tiempos[x.primeraMuestraNoCumple])} s`}</td></tr>)}</tbody></table></div><p>{c.alcance.muestras} samples · {num(c.alcance.tInicial)}–{num(c.alcance.tFinal)} s · {c.alcance.completa?'Complete horizon':'Partial horizon'}</p>{c.estado==='no_cumple'&&<p>Last sample without failed checks: {c.ultimaMuestraCertificada===null?'none':`${num(a.tiempos[c.ultimaMuestraCertificada])} s`}. All evidence is retained.</p>}<details className={styles.settings}><summary>Certification references</summary><PaquetesEjecutadosRed ejecucion={e}/><pre>{JSON.stringify(c.aspectos,null,2)}</pre></details></>}
    <h2>State and phases by sample</h2><div className={styles.boundaries}>{e.solicitud.volumenes.map(v=><button key={v.id} aria-pressed={v.id===m.volumenId} onClick={()=>setVid(v.id)}>{v.id}</button>)}</div>
    <label>t = {num(r.tiempos[k])} s <input aria-label="Thermodynamic sample" type="range" min={0} max={r.tiempos.length-1} value={k} onChange={e=>setK(Number(e.target.value))}/></label>
    {c?.estado==='no_cumple'&&(c.ultimaMuestraCertificada===null||k>c.ultimaMuestraCertificada)&&<p role="status">Sample in an uncertified interval.</p>}
    <p>{num(m.evaluacion.T)} K · {num(m.evaluacion.P)} Pa</p><div className={styles.tableWrap}><table><thead><tr><th>Phase · ID</th><th>Mole fraction</th><th>Mass fraction</th><th>Volume fraction</th>{v.componenteIds.map(id=><th key={id}>Mole composition · {e.solicitud.componentes.find(c=>c.id===id)?.nombre}</th>)}</tr></thead><tbody>{m.evaluacion.fases.map(f=><tr key={f.id}><td>{f.tipo} · {f.id}</td><td>{num(f.fraccionMolar)}</td><td>{num(f.fraccionMasica)}</td><td>{num(f.fraccionVolumen)}</td>{v.componenteIds.map(id=><td key={id}>{num(f.composicionMolar[id])}</td>)}</tr>)}</tbody></table></div>
    <h3>Component distribution</h3><div className={styles.tableWrap}><table><thead><tr><th>Component</th>{m.evaluacion.fases.map(f=><th key={f.id}>Fraction in {f.tipo} · {f.id}</th>)}</tr></thead><tbody>{v.componenteIds.map(id=><tr key={id}><td>{e.solicitud.componentes.find(c=>c.id===id)?.nombre}</td>{m.evaluacion.fases.map(f=>{const valor=repartoComponente(m.evaluacion,f.id,id);return <td key={f.id}>{Number.isFinite(valor)?num(valor):'—'}</td>;})}</tr>)}</tbody></table></div>
    <ReconstruccionMateriaRed muestra={muestra}/>
    <details className={styles.settings}><summary>Second law · {certificationStatusName(a.segundaLey.estado)}</summary><p>{a.segundaLey.motivo}</p>{a.segundaLey.generacionMinima!==null&&<p>Minimum: {num(a.segundaLey.generacionMinima)} J/K</p>}</details>
    <details className={styles.settings}><summary>Chemical potentials and stability</summary><p>Reference: {m.potenciales.referencia.descripcion}</p><p>{m.potenciales.metodo}</p><div className={styles.tableWrap}><table><thead><tr><th>Phase</th>{v.componenteIds.map(id=><th key={id}>μ · {e.solicitud.componentes.find(c=>c.id===id)?.nombre} [J/mol]</th>)}</tr></thead><tbody>{m.potenciales.fases.map(f=><tr key={f.faseId}><td>{f.faseId}</td>{v.componenteIds.map(id=><td key={id}>{f.mu[id]==null?'Not applicable':num(f.mu[id])}</td>)}</tr>)}</tbody></table></div>{unidades?<p>G = {num(m.potenciales.G)} {unidades.G} · A = {num(m.potenciales.A)} {unidades.A} · S = {num(m.potenciales.S)} {unidades.S} · volume totals</p>:<p>This run does not declare units for G, A and S. Run the model again to obtain them.</p>}<pre>{JSON.stringify(m.evaluacion.verificaciones,null,2)}</pre></details>
    <details className={styles.settings}><summary>Events · {a.eventos.length}</summary>{a.eventos.map((x,i)=><article key={i}><h3>{nombreEventoRed(x.codigo)} · {num(x.tiempo)} s · {x.volumenId??'network'}</h3>{x.faseIdsAntes&&x.faseIdsDespues?<p>{x.faseIdsAntes.join(', ')||'∅'} → {x.faseIdsDespues.join(', ')||'∅'}</p>:<p>{x.faseIds.join(', ')}</p>}{x.descripcion&&<p>{x.descripcion}</p>}</article>)}<p>Checks within each step do not constitute continuous event certification.</p></details>
    <details className={styles.settings}><summary>Series catalog · {a.catalogoSeries?.length??'unavailable'}</summary>{a.catalogoSeries?<div className={styles.tableWrap}><table><thead><tr><th>Series</th><th>SI unit</th><th>Quantity</th><th>Role</th><th>Assembly variable</th></tr></thead><tbody>{a.catalogoSeries.map(x=><tr key={x.variableId}><td title={x.procedencia}>{x.variableId}</td><td>{x.unidadSI}</td><td>{x.magnitud}</td><td>{nombrePapelSerie(x.papel)}</td><td>{x.variableEnsamblajeId??"Presentation"}</td></tr>)}</tbody></table></div>:<p>The previous run has no catalog. Run the model again to obtain it.</p>}</details>
    <details className={styles.settings}><summary>Executed equations and residuals</summary>{e.respuesta.validacion.ecuaciones.map(q=><article className={styles.equations} key={q.id}><h2>{q.propietarioId} · {q.id}</h2><FormulaMateria latex={q.latex} lectura={q.id} bloque/><small>{q.procedencia.relacion}</small></article>)}<pre>{JSON.stringify(a.residuos,null,2)}</pre></details>
    <details className={styles.settings}><summary>Original request and certificates</summary><pre>{JSON.stringify(e,null,2)}</pre></details>
  </div>;
}
