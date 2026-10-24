'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import type {HojaMotor} from './hojasMotor';
import {leerHojas,guardarHoja} from './hojasMotor';
import type {CapacidadesEnsamblaje,RespuestaValidacionDinamica,SolicitudEnsamblajeDinamico} from './contratoEnsamblajeTermodinamico';
import {capacidadesEnsamblaje,validarEnsamblaje,resolverEnsamblaje} from './servicioEnsamblaje';
import {prepararEnsamblajeTermodinamico,declararCierreDinamico,puedeExtraerDinamica} from './prepararEnsamblajeTermodinamico';
import {editarDatoDinamico,nombreDatoDinamico,grupoDatoDinamico,elegirPresionCorriente} from './datosEnsamblajeTermodinamico';
import {firmaHoja} from './modeloHojaMotor';
import {adaptarResultadoEnsamblaje} from './resultadoEnsamblaje';
import {guardarResultadoMotor} from './resultadosMotor';
import {historialEnergiaHoja,actualizarContextoDinamico} from './estadoEnergiaHoja';
import {nombreUnidad,UNIDADES_MOTOR} from './unidadesMotor';
import EcuacionesEnsambladas from './EcuacionesEnsambladas';
import {caudalIntroducido} from './presentacionEnsamblaje';
import NavegacionHoja from './NavegacionHoja';
import styles from './trabajoMotor.module.css';

type Validada={firma:string;solicitud:SolicitudEnsamblajeDinamico;respuesta?:RespuestaValidacionDinamica;error?:string};
export default function ResolverEnsamblaje({h}:{h:HojaMotor}){
  const router=useRouter(),firma=firmaHoja(h),preparacion=useMemo(()=>prepararEnsamblajeTermodinamico(h,crypto.randomUUID()),[h]);
  const [cap,setCap]=useState<CapacidadesEnsamblaje|null>(null),[validada,setValidada]=useState<Validada|null>(null),[error,setError]=useState(''),[grupoActivo,setGrupoActivo]=useState('volumen'),[servicio,setServicio]=useState(''),[intento,setIntento]=useState(0),[ejecutando,setEjecutando]=useState(false),controller=useRef<AbortController|null>(null),hashAtendido=useRef('');
  useEffect(()=>{const ctl=new AbortController();capacidadesEnsamblaje(ctl.signal).then(c=>{if(!ctl.signal.aborted){setCap(c);setServicio(c.disponible?'':c.motivo??'Servicio no disponible.');}}).catch(e=>{if(!ctl.signal.aborted)setServicio((e as Error).message);});return()=>ctl.abort();},[intento]);
  useEffect(()=>{
    const s=preparacion.solicitud;if(ejecutando||!s||!cap?.disponible||preparacion.diagnosticos.some(d=>d.estado!=='incompleto'))return;
    const ctl=new AbortController(),timer=setTimeout(()=>{validarEnsamblaje(s,ctl.signal).then(r=>{if(!ctl.signal.aborted)setValidada({firma,solicitud:s,respuesta:r});}).catch(e=>{if(!ctl.signal.aborted)setValidada({firma,solicitud:s,error:(e as Error).message});});},400);
    return()=>{clearTimeout(timer);ctl.abort();};
  },[preparacion,cap,firma,intento,ejecutando]);
  useEffect(()=>()=>controller.current?.abort(),[]);
  const s=preparacion.solicitud,v=validada?.firma===firma?validada:null,r=v?.respuesta;
  const bloqueados=preparacion.diagnosticos.filter(d=>d.estado!=='incompleto'),diagnosticos=r?.diagnosticos??preparacion.diagnosticos,recuento=r?.recuento;
  const aviso=diagnosticos.find(d=>!d.variableIds.some(id=>s?.datos[id]));
  const listo=!!r&&recuento?.estado==='listo'&&r.inicializacion.estado==='compatible'&&!r.diagnosticos.length&&!!r.modeloId&&!bloqueados.length;
  function guardar(cambio:(h:HojaMotor)=>HojaMotor){controller.current?.abort();const actual=leerHojas().find(q=>q.id===h.id);if(!actual)return;try{guardarHoja(cambio(actual));setError('');}catch(e){setError((e as Error).message);}}
  function foco(id?:string){if(!id||!s)return;setGrupoActivo(s.datos[id]?.origen.propietarioId.startsWith('corriente:')?s.datos[id].origen.propietarioId:'volumen');requestAnimationFrame(()=>document.getElementById(`dato-${id}`)?.focus());}
  async function resolver(){
    if(!v?.respuesta?.modeloId||!listo)return;
    const ctl=new AbortController();controller.current=ctl;setEjecutando(true);setError('');
    try{
      guardarHoja({...h,resultado:undefined,resultadoRef:undefined});
      const respuesta=await resolverEnsamblaje(v.solicitud,v.respuesta.modeloId,ctl.signal);if(ctl.signal.aborted)return;
      const actual=leerHojas().find(q=>q.id===h.id);if(!actual||firmaHoja(actual)!==firma)throw new Error("The model changed during calculation; the response was discarded.");
      if(!respuesta.resultados){setValidada({firma,solicitud:v.solicitud,respuesta:respuesta.validacion});throw new Error(respuesta.validacion.diagnosticos[0]?.mensaje??'El modelo no pudo resolverse.');}
      const resultado=adaptarResultadoEnsamblaje(actual,v.solicitud,respuesta);await guardarResultadoMotor(h.id,resultado);if(ctl.signal.aborted)return;
      const ultima=leerHojas().find(q=>q.id===h.id);if(!ultima||firmaHoja(ultima)!==firma)throw new Error("The model changed while saving; the response was discarded.");
      guardarHoja({...ultima,resultado:undefined,resultadoRef:{firma,estado:resultado.estado,fecha:new Date().toISOString()},tableroIniciado:ultima.tableroIniciado&&ultima.graficas.every(g=>g.y.every(id=>resultado.seriesEvaluadas!.some(q=>q.id===id)))});router.push(`/motor/hojas/${h.id}/resultados`);
    }catch(e){if(!ctl.signal.aborted)setError((e as Error).message);}finally{if(controller.current===ctl){setEjecutando(false);controller.current=null;}}
  }
  function campo(id:string){
    if(!s)return null;const d=s.datos[id],nombre=nombreDatoDinamico(s,id),ds=diagnosticos.filter(q=>q.variableIds.includes(id));
    return <div className={styles.field} key={id}><span className={styles.fieldRole}>{d.funcion==='inicial'?(id.endsWith('.U0')?'Inicial · IAPWS-95':"Initial"):d.funcion==='geometria'?"Geometry":"Datum"}</span><label htmlFor={`dato-${id}`}>{nombre}</label><div className={styles.entry}><input id={`dato-${id}`} aria-label={`${nombre} · ${grupoDatoDinamico(s,id)}`} value={d.declaracion.texto} placeholder="Value or expression" autoComplete="off" onChange={e=>guardar(q=>editarDatoDinamico(q,id,{...d.declaracion,texto:e.target.value}))}/><select aria-label={`Unit for ${nombre} · ${grupoDatoDinamico(s,id)}`} value={d.declaracion.unidad} onChange={e=>guardar(q=>editarDatoDinamico(q,id,{...d.declaracion,unidad:e.target.value}))}>{Object.keys(UNIDADES_MOTOR[d.magnitud]).map(u=><option key={u} value={u}>{nombreUnidad(u)}</option>)}</select></div>{ds.length>0&&<span className={styles.fieldError}>{ds[0].mensaje}</span>}</div>;
  }
  const grupos=s?['volumen',...s.corrientes.map(c=>`corriente:${c.id}`)]:[],seleccion=grupos.includes(grupoActivo)?grupoActivo:'volumen';
  const nombreGrupo=(grupo:string)=>grupo==='volumen'?'Volumen':h.ensamblaje?.corrientes.find(c=>`corriente:${c.id}`===grupo)?.nombre??`Corriente ${grupo.split(':')[1]}`;
  const verDato=(id:string)=>{if(!s)return false;const d=s.datos[id],c=s.corrientes.find(c=>d.origen.propietarioId===`corriente:${c.id}`);return !c||caudalIntroducido(c,s)||['caudal','caudal_molar'].includes(d.magnitud);};
  useEffect(()=>{
    let frame=0,focusFrame=0;
    const seguirEnlace=()=>{const hash=window.location.hash;if(hash===hashAtendido.current)return;
      frame=requestAnimationFrame(()=>{const id=decodeURIComponent(hash.slice(1)).replace(/^dato-/,'');
        if(s?.datos[id]){hashAtendido.current=hash;setGrupoActivo(s.datos[id].origen.propietarioId.startsWith('corriente:')?s.datos[id].origen.propietarioId:'volumen');focusFrame=requestAnimationFrame(()=>document.getElementById(`dato-${id}`)?.focus());}
        else if(/^#(ecuacion-|variables-calculadas)/.test(hash)){const panel=document.getElementById('ecuaciones-dinamicas') as HTMLDetailsElement|null;if(panel){panel.open=true;document.getElementById(hash.slice(1))?.scrollIntoView();hashAtendido.current=hash;}}
      });
    };
    seguirEnlace();window.addEventListener('hashchange',seguirEnlace);
    return()=>{cancelAnimationFrame(frame);cancelAnimationFrame(focusFrame);window.removeEventListener('hashchange',seguirEnlace);};
  },[s,r]);
  const estado=ejecutando?"Solving…":r?.inicializacion.estado==='incompatible'?'Iniciales incompatibles':r?.inicializacion.estado==='no_soportada'?"Unsupported initialization":listo?'Listo':recuento?.estado==='conflicto'?'Conflicto':recuento?.estado==='no_evaluable'?'Sin evaluar':r?'Faltan datos':bloqueados.length?'Revisar modelo':'Validando…';
  return <div className={styles.page}><NavegacionHoja id={h.id} actual="resolver"/><header className={styles.heading}><div><span className={styles.eyebrow}>{h.nombre}</span><h1>Solve model</h1></div><span className={styles.eyebrow}>Matter + energy · IAPWS-95</span></header>
    {(servicio||v?.error||error)&&<div className={styles.error} role="alert">{error||v?.error||servicio}<button onClick={()=>{setError('');setIntento(x=>x+1);}}>Retry</button></div>}
    {aviso&&<div className={styles.error} role="alert"><span>{aviso.mensaje}</span>{aviso.codigo==='MOTOR_ENS_CONTEXTO'?<button onClick={()=>guardar(actualizarContextoDinamico)}>Actualizar ecuaciones</button>:aviso.origen.propietarioId.startsWith('corriente:')?<button onClick={()=>setGrupoActivo(aviso.origen.propietarioId)}>Revisar corriente →</button>:<Link href={`/motor/hojas/${h.id}/estado#cierre-energia`}>Revisar modelo →</Link>}</div>}
    <div className={styles.solveLayout}><section>{!(r&&s)&&<section className={styles.equations} aria-live="polite"><h2>Assembled equations</h2><span>{bloqueados.length?"Complete the formulation before assembly.":"Waiting for engine validation…"}</span></section>}
      <nav className={styles.networkTabs} aria-label="Datos a especificar">{grupos.map(grupo=><button key={grupo} aria-pressed={seleccion===grupo} onClick={()=>setGrupoActivo(grupo)}>{nombreGrupo(grupo)}{diagnosticos.some(d=>grupo==='volumen'?d.origen.propietarioId.startsWith('volumen:'):d.origen.propietarioId===grupo)&&<small> · Pendiente</small>}</button>)}</nav>
      <div className={styles.variables}>{grupos.map(grupo=><section key={grupo} hidden={seleccion!==grupo} aria-label={`Datos de ${nombreGrupo(grupo)}`}>
        <h2>{nombreGrupo(grupo)}</h2>
        {grupo==='volumen'&&<div className={styles.extraction}><span>Initial energy</span>{(['T','U'] as const).map(inicial=><button key={inicial} aria-pressed={(h.energia?.inicial??'T')===inicial} onClick={()=>guardar(q=>({...q,energia:{...q.energia,historial:historialEnergiaHoja(q),datos:q.energia?.datos??{},inicial},resultado:undefined,resultadoRef:undefined}))}>{inicial}(0) como dato</button>)}</div>}
        {s?.corrientes.filter(c=>grupo===`corriente:${c.id}`).map(c=><div key={c.id} className={styles.streamDirection}>Sentido positivo · {c.hasta===s.volumen.id?'exterior → volumen':'volumen → exterior'}</div>)}
        {Object.keys(s!.datos).filter(id=>id!==s!.estudio.tiempoId&&verDato(id)&&(grupo==='volumen'?!s!.datos[id].origen.propietarioId.startsWith('corriente:'):s!.datos[id].origen.propietarioId===grupo)).map(id=>id.endsWith('.Pext')&&s!.datos[id].origen.propietarioId.startsWith('corriente:')?null:campo(id))}
        {s?.corrientes.filter(c=>grupo===`corriente:${c.id}`&&c.estadoExterior&&caudalIntroducido(c,s)).map(c=><section key={c.id} className={styles.streamPressure} aria-label={`Presión exterior de corriente ${c.id}`}><span>External pressure</span><div className={styles.boundaries}>{(['dato','continuidad'] as const).map(modo=><button key={modo} aria-pressed={c.estadoExterior!.presion.tipo===modo} onClick={()=>guardar(q=>elegirPresionCorriente(q,c.id,modo))}>{modo==='dato'?'Valor propio':'Igual al volumen'}</button>)}</div>{c.estadoExterior!.presion.tipo==='dato'?campo(c.estadoExterior!.presion.datoId):<a href={`#ecuacion-mecanica.continuidad.${c.id}`}>External P = volume P · inspect relation →</a>}</section>)}
        {s?.corrientes.filter(c=>grupo===`corriente:${c.id}`&&caudalIntroducido(c,s)&&s.volumen.cierre.politica.cantidad!=='monofasico'&&puedeExtraerDinamica(c,s.volumen.id,s.datos)).map(c=><div className={styles.extraction} key={c.id}><span>Extract from volume</span>{(['mezcla_homogenea','liquido','vapor'] as const).map(tipo=><button key={tipo} aria-pressed={c.extraccion?.tipo===tipo||c.extraccion?.tipo==='fase'&&c.extraccion.fase===tipo} onClick={()=>guardar(q=>{const cierre=q.cierresDinamicos![s.volumen.id];return declararCierreDinamico(q,s.volumen.id,{...cierre,extracciones:{...cierre.extracciones,[c.id]:tipo==='mezcla_homogenea'?{tipo}:{tipo:'fase',fase:tipo}}});})}>{tipo==='mezcla_homogenea'?'Mezcla':tipo==='liquido'?"Liquid":'Vapor'}</button>)}</div>)}
      </section>)}</div>
      {r&&s&&<details id="ecuaciones-dinamicas"><summary>Ecuaciones y variables calculadas</summary><EcuacionesEnsambladas r={r} s={s} estructura={preparacion.estructura}/></details>}
    </section><aside className={styles.solveAside}><span className={styles.modelStatus} role="status">{estado}</span><div className={styles.counts}><div><span>Variables / equations</span><strong>{recuento?.variables??'—'} / {recuento?.ecuacionesIndependientes??'—'}</strong></div><div><span>GL · {recuento?.analisis==='rango_numerico'?'rango numérico':'estructural'}</span><strong>{recuento?.gradosLibertad??'—'}</strong></div><div><span>Specified data</span><strong>{recuento?.datosDefinidos??'—'}</strong></div><div><span>Faltan / iniciales</span><strong>{recuento?.datosFaltantes??'—'} / {recuento?.inicialesFaltantes??'—'}</strong></div></div>
      {s&&<><label htmlFor={`dato-${s.estudio.tiempoId}`}>Final time</label><div className={styles.entry}><input id={`dato-${s.estudio.tiempoId}`} aria-label="Final time" value={s.datos[s.estudio.tiempoId].declaracion.texto} onChange={e=>guardar(q=>editarDatoDinamico(q,s.estudio.tiempoId,{...s.datos[s.estudio.tiempoId].declaracion,texto:e.target.value}))}/><select aria-label="Unidad de Tiempo final" value={s.datos[s.estudio.tiempoId].declaracion.unidad} onChange={e=>guardar(q=>editarDatoDinamico(q,s.estudio.tiempoId,{...s.datos[s.estudio.tiempoId].declaracion,unidad:e.target.value}))}>{Object.keys(UNIDADES_MOTOR.tiempo).map(u=><option key={u} value={u}>{nombreUnidad(u)}</option>)}</select></div></>}
      <button className={styles.primary} disabled={!listo||ejecutando} onClick={resolver}>{ejecutando?"Solving…":"Run model"}</button>{ejecutando?<button className={styles.pending} onClick={()=>{controller.current?.abort();setEjecutando(false);}}>Cancel request</button>:!listo&&diagnosticos.some(d=>d.variableIds.some(id=>s?.datos[id]))&&<button className={styles.pending} onClick={()=>foco(diagnosticos.flatMap(d=>d.variableIds).find(id=>s?.datos[id]))}>Ir al dato pendiente →</button>}
      <details className={styles.settings}><summary>Numerical settings</summary><label>Method<select aria-label="Dynamic method" value={h.config.metodo} onChange={e=>guardar(q=>({...q,config:{...q.config,metodo:e.target.value as HojaMotor['config']['metodo']},resultado:undefined,resultadoRef:undefined}))}>{cap?.integradores.map(m=><option key={m.id} value={m.id}>{m.nombre}</option>)}{h.config.metodo!=='rk45'&&<option value={h.config.metodo}>Unsupported method</option>}</select></label><label>Samples<input aria-label="Samples" type="number" min={2} max={cap?.muestrasMaximas??201} value={h.config.muestras} onChange={e=>guardar(q=>({...q,config:{...q.config,muestras:Number(e.target.value)},resultado:undefined,resultadoRef:undefined}))}/></label><label>Relative tolerance<input aria-label="Relative tolerance" type="number" value={h.config.rtol} onChange={e=>guardar(q=>({...q,config:{...q.config,rtol:Number(e.target.value)},resultado:undefined,resultadoRef:undefined}))}/></label><p>Time expressions use t in seconds. Available methods and functions are declared by the service.</p>{r&&<pre>{JSON.stringify({recuento:r.recuento,inicializacion:r.inicializacion,diagnosticos:r.diagnosticos,solicitud:s},null,2)}</pre>}</details>
    </aside></div></div>;
}
