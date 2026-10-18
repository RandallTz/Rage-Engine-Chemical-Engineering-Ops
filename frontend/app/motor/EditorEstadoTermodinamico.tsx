'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {useHojasMotor} from './useHojasMotor';
import {guardarHoja,leerHojas} from './hojasMotor';
import type {HojaMotor} from './hojasMotor';
import type {CantidadEstado,CapacidadesEstado,DeclaracionEstado,EspecificacionEstado} from './contratoTermodinamica';
import {analizarSolicitudEstado} from './contratoTermodinamica';
import {propietariosEstado,iniciarDeclaracionEstado,solicitudEstadoHoja,guardarDeclaracionEstado,guardarEvaluacionEstado,evaluacionVigente,identificarComponenteEstado,cambiarTipoEstado} from './estadoTermodinamicoHoja';
import {capacidadesTermodinamica,evaluarEstadoTermodinamico} from './servicioTermodinamica';
import {relacionesTermodinamicas} from './relacionesTermodinamicas';
import FormulaMateria from './FormulaMateria';
import NavegacionHoja from './NavegacionHoja';
import SelectorModeloTermodinamico from './SelectorModeloTermodinamico';
import {nombreUnidad} from './unidadesMotor';
import {ControlOperacionRed} from './operacionRed';
import EditorDatosPuros from './EditorDatosPuros';
import styles from './estadoTermodinamico.module.css';

function Cantidad({nombre,dato,unidades,cambiar}:{nombre:string;dato:CantidadEstado;unidades:string[];cambiar:(v:CantidadEstado)=>void}){
  const inputId=`estado-${nombre.replaceAll(' ','-')}`;
  return <div className={styles.quantity}><label htmlFor={inputId}>{nombre}</label><div><input id={inputId} type="number" value={dato.valor??''} placeholder="Valor" onChange={e=>cambiar({...dato,valor:Number.isFinite(e.target.valueAsNumber)?e.target.valueAsNumber:null})}/><select aria-label={`Unidad de ${nombre}`} value={dato.unidad} onChange={e=>cambiar({...dato,unidad:e.target.value})}>{unidades.map(u=><option key={u} value={u}>{nombreUnidad(u)}</option>)}</select></div></div>;
}
export default function EditorEstadoTermodinamico({id,propietarioId,integrado=false}:{id:string;propietarioId?:string;integrado?:boolean}){
  const hojas=useHojasMotor(),h=hojas.find(h=>h.id===id),[propietario,setPropietario]=useState(''),[capacidades,setCapacidades]=useState<CapacidadesEstado|null>(null),[error,setError]=useState(''),[servicio,setServicio]=useState('Conectando servicio…'),[intento,setIntento]=useState(0),[evaluando,setEvaluando]=useState(false),controller=useRef(new ControlOperacionRed());
  useEffect(()=>{const ctl=new AbortController();capacidadesTermodinamica(ctl.signal).then(c=>{if(!ctl.signal.aborted){setCapacidades(c);setServicio(c.modelos.length?'':'El servicio no publica modelos verificados.');}}).catch(e=>{if(!ctl.signal.aborted){setCapacidades(null);setServicio((e as Error).message);}});return()=>ctl.abort();},[intento]);
  useEffect(()=>{const control=controller.current;return()=>control.cancelar();},[]);
  if(!h)return <div className={styles.page}><Link href="/motor/hojas">Abrir mis hojas</Link></div>;
  const propietarios=propietariosEstado(h),p=propietarios.find(p=>p.id===(propietarioId??propietario))??propietarios[0];
  const d=h.termodinamica?.estados[p.id]?.declaracion??iniciarDeclaracionEstado(p.componentes.map(c=>c.id)),s=d.especificacion;
  const cap=capacidades?.modelos.find(c=>c.id===d.modelo.id&&c.version===d.modelo.version);
  const especificacionAdmitida=!!cap?.especificaciones.includes(s.tipo);
  const pendientes=analizarSolicitudEstado({revision:1,solicitudId:'comprobar',propietarioId:p.id,componentes:p.componentes,declaracion:d});
  const respuesta=evaluacionVigente(h,p.id),estado=respuesta?.estado==='evaluado'?respuesta.evaluacion:null;
  function cancelar(){controller.current.cancelar();setEvaluando(false);}
  function guardar(cambio:(actual:HojaMotor)=>HojaMotor){cancelar();try{const actual=leerHojas().find(q=>q.id===id);if(!actual)throw new Error('Hoja no disponible.');guardarHoja(cambio(actual));setError('');return true;}catch(e){setError((e as Error).message);return false;}}
  function cambiar(cambios:Partial<DeclaracionEstado>){guardar(q=>guardarDeclaracionEstado(q,p.id,{...(q.termodinamica?.estados[p.id]?.declaracion??d),...cambios}));}
  function especificacion(e:EspecificacionEstado){cambiar({especificacion:e});}
  function tipo(tipo:EspecificacionEstado['tipo']){
    if(tipo!==s.tipo)especificacion(cambiarTipoEstado(s,tipo,p.componentes.map(c=>c.id)));
  }
  async function evaluar(){if(!cap)return;const control=controller.current,op=control.iniciar(),signal=op.controller.signal;setEvaluando(true);setError('');try{const actual=leerHojas().find(q=>q.id===id)!;const solicitud=solicitudEstadoHoja(actual,p.id,crypto.randomUUID()),r=await evaluarEstadoTermodinamico(solicitud,cap,signal);if(!control.vigente(op))return;const vigente=leerHojas().find(q=>q.id===id);if(!vigente)throw new Error('Hoja no disponible.');guardarHoja(guardarEvaluacionEstado(vigente,solicitud,r));}catch(e){if(control.vigente(op))setError((e as Error).message);}finally{if(control.finalizar(op)&&!signal.aborted)setEvaluando(false);}}
  return <div className={integrado?styles.embedded:styles.page}>{!integrado&&<><NavegacionHoja id={id} actual="estado"/><header className={styles.heading}><div><small>{h.nombre}</small><h1>Estado y propiedades</h1><small>Consulta de estado · no sustituye el modelo dinámico manual</small></div><select aria-label="Volumen o corriente" value={p.id} onChange={e=>{cancelar();setPropietario(e.target.value);setError('');}}>{propietarios.map(p=><option key={p.id} value={p.id}>{p.nombre} · {p.tipo}</option>)}</select></header></>}
    <div className={styles.layout}><section className={styles.paper} aria-label="Fundamentos termodinámicos">
      {relacionesTermodinamicas(s,d.politica).map(r=><article key={r.id}><h2>{r.titulo}</h2><FormulaMateria latex={r.latex} lectura={r.titulo} bloque/></article>)}
      <details><summary>Símbolos y alcance</summary><dl>{[['n_i','Cantidad total del componente i · mol'],['x_i^α','Fracción molar en la fase α'],['z_i','Composición molar global'],['β / χ / ε','Fracción molar / másica / volumétrica de fase'],['u / h / v / s','Energía interna / entalpía / volumen / entropía específicos'],['μ_i','Potencial químico · J/mol']].map(([a,b])=><div key={a}><dt>{a}</dt><dd>{b}</dd></div>)}</dl><p>Equilibrio macroscópico, sin términos eléctricos o de superficie. Esta evaluación es una consulta de estado; no modifica los balances ni sustituye la relación manual u(T).</p></details>
    </section><section className={styles.inputs} aria-label="Datos del estado">
      <label className={styles.model}>Modelo<SelectorModeloTermodinamico nombre="Modelo termodinámico" actual={d.modelo} catalogoCargado={!!capacidades} publicados={capacidades?.modelos.map(c=>({modelo:{id:c.id,version:c.version},nombre:c.nombre,disponible:true}))??[]} elegir={modelo=>cambiar({modelo})}/></label>
      {servicio&&<div className={styles.notice} role="status">{servicio}<button onClick={()=>{setServicio('Conectando servicio…');setIntento(x=>x+1);}}>Volver a conectar</button></div>}
      <fieldset><legend>Componentes</legend>{p.componentes.map(c=><div className={styles.identity} key={`${c.id}:${c.identidadQuimica?.cas??''}`}><label htmlFor={`cas-${c.id}`}>{c.nombre}</label><input id={`cas-${c.id}`} aria-label={`CAS de ${c.nombre}`} defaultValue={c.identidadQuimica?.cas??''} placeholder="CAS" onBlur={e=>guardar(q=>identificarComponenteEstado(q,c.id,e.target.value.trim()))}/></div>)}</fieldset>
      <div className={styles.specifications}>{(['TP','PH','UV','UP']as const).filter(t=>!cap||cap.especificaciones.includes(t)).map(t=><button key={t} aria-pressed={s.tipo===t} onClick={()=>tipo(t)}>{t==='TP'?'T · P':t==='PH'?'P · h':t==='UV'?'U · V':'U · P'}</button>)}</div>
      {cap&&<small className={styles.scope}>{especificacionAdmitida?'Consulta puntual · no se utiliza como cierre del solver':`La especificación ${s.tipo} aún no está disponible. Elige ${cap.especificaciones.join(' o ')}.`}</small>}
      {'T'in s&&<Cantidad nombre="Temperatura" dato={s.T} unidades={['K','degC','degF']} cambiar={T=>especificacion({...s,T})}/>}
      {'P'in s&&<Cantidad nombre="Presión absoluta" dato={s.P} unidades={['Pa','kPa','bar']} cambiar={P=>especificacion({...s,P})}/>}
      {'h'in s&&<Cantidad nombre="Entalpía específica" dato={s.h} unidades={['J/kg','kJ/kg']} cambiar={h=>especificacion({...s,h})}/>}
      {'U'in s&&<Cantidad nombre="Energía interna total" dato={s.U} unidades={['J','kJ']} cambiar={U=>especificacion({...s,U})}/>}
      {'V'in s&&<Cantidad nombre="Volumen ocupado" dato={s.V} unidades={['m3','L']} cambiar={V=>especificacion({...s,V})}/>}
      {'composicion'in s?<fieldset><legend>Composición</legend><label className={styles.model}>Base<select value={s.composicion.base} onChange={e=>especificacion({...s,composicion:{base:e.target.value as 'masica'|'molar',fracciones:p.componentes.length===1?{[p.componentes[0].id]:1}:{}}})}><option value="molar">Molar</option><option value="masica">Másica</option></select></label>{p.componentes.map(c=><div className={styles.identity} key={c.id}><label htmlFor={`fraccion-${c.id}`}>{c.nombre}</label><input id={`fraccion-${c.id}`} type="number" min={0} max={1} value={s.composicion.fracciones[c.id]??''} onChange={e=>especificacion({...s,composicion:{...s.composicion,fracciones:{...s.composicion.fracciones,[c.id]:Number.isFinite(e.target.valueAsNumber)?e.target.valueAsNumber:null}}})}/></div>)}</fieldset>:<fieldset><legend>Cantidades por componente</legend><label className={styles.model}>Base<select value={s.cantidades.base} onChange={e=>{const base=e.target.value as 'masica'|'molar';especificacion({...s,cantidades:{base,valores:Object.fromEntries(p.componentes.map(c=>[String(c.id),{valor:null,unidad:base==='masica'?'kg':'mol'}]))}});}}><option value="masica">Másica</option><option value="molar">Molar</option></select></label>{p.componentes.map(c=><Cantidad key={c.id} nombre={`Cantidad · ${c.nombre}`} dato={s.cantidades.valores[c.id]??{valor:null,unidad:s.cantidades.base==='masica'?'kg':'mol'}} unidades={s.cantidades.base==='masica'?['kg','g']:['mol','kmol']} cambiar={v=>especificacion({...s,cantidades:{...s.cantidades,valores:{...s.cantidades.valores,[c.id]:v}}})}/>)}</fieldset>}
      <details className={styles.policies}><summary>Restricciones de fase</summary><label><input type="checkbox" checked={d.politica.cantidad==='monofasico'} onChange={e=>cambiar({politica:{...d.politica,cantidad:e.target.checked?'monofasico':'sin_restriccion'}})}/>Solicitar una sola fase</label><label><input type="checkbox" checked={d.politica.cambioInterno==='prohibido'} onChange={e=>cambiar({politica:{...d.politica,cambioInterno:e.target.checked?'prohibido':'permitido'}})}/>Excluir cambio interno de fase</label><small>El equilibrio verifica el estado actual; excluir cambios de fase necesita comprobar una trayectoria.</small></details>
      <EditorDatosPuros modelo={d.modelo} componentes={p.componentes} datos={d.datosPuros} originales={h.termodinamica?.estados[p.id]?.originalesDatosPuros} cambiar={(datosPuros,originales)=>guardar(q=>{const actual=q.termodinamica?.estados[p.id]?.declaracion??d,out=guardarDeclaracionEstado(q,p.id,{...actual,datosPuros});out.termodinamica!.estados[p.id].originalesDatosPuros=originales;return out;})}/>
      <div className={styles.actions}><span>{pendientes.length?'Datos pendientes':'Datos completos'}</span><button className={styles.primary} disabled={!especificacionAdmitida||!!pendientes.length||evaluando} onClick={evaluar}>{evaluando?'Evaluando…':'Evaluar estado'}</button>{evaluando&&<button onClick={cancelar}>Cancelar espera</button>}</div>
      {pendientes.length>0&&<small className={styles.pending}>{pendientes[0].mensaje}</small>}
      {error&&<div className={styles.notice} role="alert">{error}<button onClick={()=>setError('')}>Cerrar</button></div>}
      {respuesta&&respuesta.estado!=='evaluado'&&<div className={styles.notice} role="alert">{respuesta.diagnosticos.map((d,i)=><p key={i}>{d.mensaje}<small>{d.codigo} · {d.ruta}</small></p>)}</div>}
    </section></div>
    {estado&&<section className={styles.result} aria-label="Estado termodinámico verificado"><header><h2>Estado evaluado</h2><span>{estado.T.toPrecision(6)} K · {estado.P.toPrecision(6)} Pa</span></header><div className={styles.phases}>{estado.fases.map(f=><article key={f.id}><h3>{f.tipo} · {f.regimen}</h3><dl>{[['Fracción molar',f.fraccionMolar,'mol/mol'],['Fracción másica',f.fraccionMasica,'kg/kg'],['Fracción de volumen',f.fraccionVolumen,'m³/m³'],['Energía interna',f.propiedades.u,'J/kg'],['Entalpía',f.propiedades.h,'J/kg'],['Densidad de fase',1/f.propiedades.v,'kg/m³']].map(([n,v,u])=><div key={String(n)}><dt>{n}</dt><dd>{Number(v).toPrecision(6)} {u}</dd></div>)}</dl></article>)}</div><details><summary>Estabilidad, referencias y residuos</summary><p>Estabilidad evaluada frente a: {estado.estabilidad.alcance.join(', ')}. Modelo: {d.modelo.id} · {d.modelo.version}. Referencia: {estado.referencia.descripcion}.</p><pre>{JSON.stringify({verificaciones:estado.verificaciones,diagnosticos:respuesta?.diagnosticos},null,2)}</pre></details></section>}
  </div>;
}
