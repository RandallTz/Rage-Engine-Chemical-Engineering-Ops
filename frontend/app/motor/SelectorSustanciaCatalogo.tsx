'use client';
import {useEffect,useState} from 'react';
import type {CatalogoMotor,SustanciaCatalogo} from './contratoCatalogo';
import type {RedTermodinamica} from './redTermodinamica';
import {catalogoMotor} from './servicioCatalogo';
import {opcionesCatalogoRed} from './seleccionCatalogoRed';
import styles from './catalogoMotor.module.css';

function DatosPuros({s,abierto}:{s:SustanciaCatalogo;abierto:boolean}){
  const d=s.datosPuros;
  return <details className={styles.details} open={abierto}><summary>Datos puros · {s.nombre}</summary>
    <small>Mixture-package data; state properties are calculated during evaluation.</small>
    <dl><dt>Catalog molar mass</dt><dd>{s.masaMolar.valor} {s.masaMolar.unidad} · {s.masaMolar.fuente}</dd></dl>
    {d.faltantes.map(f=><p key={f.dato}>{f.dato} · {f.motivo}</p>)}
    {d.propiedades?.map(p=><section key={p.id}><h4>{p.id.replaceAll('_',' ')} · {p.unidad}</h4><dl><dt>Fuente</dt><dd>{p.fuente}</dd>{p.id==='volumen_liquido'?<><dt>Valor</dt><dd>{p.valor} {p.unidad}</dd><dt>Condition</dt><dd>{p.condicion}</dd></>:<><dt>Forma</dt><dd>{p.forma}</dd><dt>Dominio T</dt><dd>{p.dominio.T.join('–')} K</dd><dt>Coeficientes</dt><dd>{Object.entries(p.coeficientes).map(([k,v])=><span className={styles.coefficient} key={k}>{k} = {v}</span>)}</dd></>}</dl></section>)}
    {d.dominioLiquido&&<p>Dominio líquido · {d.dominioLiquido.T.join('–')} K · {d.dominioLiquido.motivo}</p>}
    {d.huella&&<p className={styles.hash}>{d.huella}</p>}
  </details>;
}
export default function SelectorSustanciaCatalogo({red,destinos,cas,elegir}:{red:RedTermodinamica;destinos:string[];cas:string;elegir:(s:SustanciaCatalogo)=>void}){
  const [catalogo,setCatalogo]=useState<CatalogoMotor|null>(null),[error,setError]=useState(''),[intento,setIntento]=useState(0),[busqueda,setBusqueda]=useState(''),[inspeccion,setInspeccion]=useState('');
  useEffect(()=>{const c=new AbortController();catalogoMotor(c.signal).then(r=>{if(!c.signal.aborted)setCatalogo(r);}).catch(e=>{if(!c.signal.aborted)setError((e as Error).message);});return()=>c.abort();},[intento]);
  if(error)return <div className={styles.failure} role="alert">{error}<button type="button" onClick={()=>{setError('');setCatalogo(null);setIntento(n=>n+1);}}>Retry catalog</button></div>;
  if(!catalogo)return <p className={styles.loading} role="status">Cargando sustancias…</p>;
  const opciones=opcionesCatalogoRed(catalogo,red,destinos,busqueda),seleccion=catalogo.sustancias.find(s=>s.id===inspeccion||!inspeccion&&s.cas===cas.trim());
  return <section className={styles.picker} aria-label="Engine substance catalog">
    <label>Search the catalog<input type="search" aria-label="Buscar sustancia por nombre o CAS" placeholder="Nombre o CAS" value={busqueda} onChange={e=>setBusqueda(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')e.preventDefault();}}/></label>
    <div className={styles.list} aria-label="Sustancias publicadas">{opciones.map(o=><div className={styles.row} key={o.sustancia.id}>
      <button type="button" disabled={!o.elegible} aria-pressed={cas.trim()===o.sustancia.cas} onClick={()=>{setInspeccion('');elegir(o.sustancia);}}><strong>{o.sustancia.nombre}</strong><span>{o.sustancia.cas}</span></button>
      <div className={styles.admission}>{o.presente?<small>Ya está en esta hoja</small>:o.volumenes.map(v=><small key={v.id}>{v.nombre} · {v.admitida?'Admitida':v.motivos.join(' · ')}</small>)}<button type="button" className={styles.inspect} aria-label={`Ver datos puros de ${o.sustancia.nombre}`} onClick={()=>setInspeccion(o.sustancia.id)}>Datos puros</button></div>
    </div>)}</div>
    {!opciones.length&&<p role="status">No matches in the published catalog.</p>}
    <small>Species admission does not verify the pairs or groups of a mixture.</small>
    {seleccion&&<DatosPuros key={seleccion.id+':'+!!inspeccion} s={seleccion} abierto={!!inspeccion}/>}
  </section>;
}
