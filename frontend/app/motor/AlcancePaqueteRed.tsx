import type {CapacidadesEnsamblajeV2} from './contratoEnsamblajeV2';
import type {Componente} from './materiaEstado';
import {nombreEvidencia} from './metadatosRed';
import CoberturaGruposPaquete from './CoberturaGruposPaquete';
import styles from './trabajoMotor.module.css';
export default function AlcancePaqueteRed({paquete,componentes,tamanos}:{paquete:CapacidadesEnsamblajeV2['paquetes'][number];componentes:Componente[];tamanos?:CapacidadesEnsamblajeV2['tamanos']}){
  const cas=componentes.flatMap(c=>c.identidadQuimica?.cas?[c.identidadQuimica.cas]:[]),pares=paquete.pares?.filter(p=>p.componentesCAS.every(id=>cas.includes(id)));
  const nombre=(id:string)=>componentes.find(c=>c.identidadQuimica?.cas===id)?.nombre??id;
  const contrastados=tamanos?.contrastados[paquete.modelo.id];
  return <details className={styles.settings}><summary>Package scope and evidence</summary>
    {tamanos&&<><div className={styles.tableWrap}><table><caption>Componentes por volumen · {paquete.modelo.id} · v{paquete.modelo.version}</caption><tbody>
      <tr><th scope="row">Admitidos por el servicio</th><td>Hasta {tamanos.componentesMaximosPorVolumen}</td></tr>
      <tr><th scope="row">Verified sizes · state</th><td>{contrastados?.estatico.join(', ')||'No publicados'}</td></tr>
      <tr><th scope="row">Verified sizes · trajectory</th><td>{contrastados?.dinamico.join(', ')||'No publicados'}</td></tr>
      <tr><th scope="row">Fases simultáneas</th><td>Hasta {tamanos.fasesMaximas}</td></tr>
    </tbody></table></div><small>Parameter availability and domain are checked for the selected components.</small>
    <details><summary>Stability method and budget</summary>{Object.entries(tamanos.estabilidad).map(([id,metodo])=><p key={id}>{id}: {metodo}</p>)}<p>{tamanos.presupuesto}</p></details></>}
    {paquete.coberturaGrupos&&<CoberturaGruposPaquete cobertura={paquete.coberturaGrupos} componentes={componentes}/>}
    <div className={styles.tableWrap}><table><thead><tr><th>Combination</th><th>Evidencia</th><th>Disponible</th></tr></thead><tbody>{paquete.combinaciones.map((c,i)=><tr key={c.id??i}><td title={c.motivo}>{c.nombre}</td><td>{c.evidencia?nombreEvidencia(c.evidencia):'No declarada'}</td><td>{c.publicada?"Yes":'No'}</td></tr>)}</tbody></table></div>{pares?.map(p=><p key={p.componentesCAS.join(':')}>{p.componentesCAS.map(nombre).join(' / ')} · {nombreEvidencia(p.evidencia)} · {p.procedencia}<br/>{p.motivo}</p>)}{paquete.limites?.map((l,i)=><p key={i}>{l}</p>)}</details>;
}
