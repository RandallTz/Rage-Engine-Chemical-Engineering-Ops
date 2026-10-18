'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import Link from 'next/link';
import type {ResultadoMotor} from './modeloNumerico';
import type {HojaMotor} from './hojasMotor';
import type {CapacidadesDiagramas,RespuestaDiagrama,SolicitudDiagrama,CorteEquilibrio,PerfilResolucion} from './contratoDiagramasEquilibrio';
import {contextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import {prepararSolicitudDiagrama,VigenciaConsultaDiagrama,MemoriaDiagramas,csvDiagrama} from './datosDiagramaEquilibrio';
import {capacidadesDiagramas,trazarDiagrama} from './servicioDiagramasEquilibrio';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import GraficaCorteEquilibrio from './GraficaCorteEquilibrio';
import CoberturaGruposPaquete from './CoberturaGruposPaquete';
import styles from './equilibrioMotor.module.css';

type Tipo='Txy'|'Pxy';
type Panel={resultado?:RespuestaDiagrama;consulta?:SolicitudDiagrama;cargando?:boolean;error?:string};
type Preferencias={volumenId:string;indice:number;ejeId:number;unidadT:'K'|'degC';unidadP:'Pa'|'kPa'|'bar'};
export default function EquilibrioHoja({h,r,guardar}:{h:HojaMotor;r:ResultadoMotor;guardar:(p:Preferencias)=>void}){
  const s=r.ensamblajeV2!.solicitud,pref=h.vistaEquilibrio;
  const [vid,setVid]=useState(pref?.volumenId&&s.volumenes.some(v=>v.id===pref.volumenId)?pref.volumenId:s.volumenes[0].id),[k,setK]=useState(Math.max(0,Math.min(r.tiempos.length-1,pref?.indice??r.tiempos.length-1))),[eje,setEje]=useState(pref?.ejeId??s.volumenes[0].componenteIds[0]);
  const [unidadT,setUnidadT]=useState<Preferencias['unidadT']>(pref?.unidadT??'degC'),[unidadP,setUnidadP]=useState<Preferencias['unidadP']>(pref?.unidadP??'bar');
  const [cap,setCap]=useState<CapacidadesDiagramas>(),[errorCap,setErrorCap]=useState(''),[intento,setIntento]=useState(0),[paneles,setPaneles]=useState<Record<Tipo,Panel>>({Txy:{},Pxy:{}}),[perfil,setPerfil]=useState<PerfilResolucion>('exploratoria');
  const [manualP,setManualP]=useState(false),[manualT,setManualT]=useState(false),[datoP,setDatoP]=useState({valor:'',unidad:'bar'}),[datoT,setDatoT]=useState({valor:'',unidad:'degC'});
  const controles=useRef({Txy:new VigenciaConsultaDiagrama(),Pxy:new VigenciaConsultaDiagrama()});
  const memoria=useRef(new MemoriaDiagramas());
  const muestra=useMemo(()=>contextoMuestraEquilibrio(r,vid,k),[r,vid,k]),ejeId=muestra.componentes.some(c=>c.id===eje)?eje:muestra.componentes[0].id;
  useEffect(()=>{const abort=new AbortController();capacidadesDiagramas(abort.signal).then(setCap).catch(e=>{if(!abort.signal.aborted)setErrorCap((e as Error).message);});return()=>abort.abort();},[intento]);
  useEffect(()=>{const c=controles.current;return()=>{c.Txy.cancelar();c.Pxy.cancelar();};},[]);
  const paquete=cap?.paquetes.find(p=>p.modelo.id===muestra.modelo.id&&p.modelo.version===muestra.modelo.version);
  const soportado=muestra.componentes.length===2&&!!paquete;
  const persistir=(cambio:Partial<Preferencias>={})=>guardar({volumenId:vid,indice:k,ejeId,unidadT,unidadP,...cambio});
  function seleccionarMuestra(indice:number){controles.current.Txy.cancelar();controles.current.Pxy.cancelar();setK(indice);setPaneles(p=>({Txy:{...p.Txy,cargando:false},Pxy:{...p.Pxy,cargando:false}}));}
  async function calcular(tipo:Tipo){
    const control=controles.current[tipo].iniciar();
    setPaneles(p=>({...p,[tipo]:{...p[tipo],cargando:true,error:undefined}}));
    try{
      const manual=tipo==='Txy'?manualP:manualT,dato=tipo==='Txy'?datoP:datoT;
      if(manual&&(!dato.valor.trim()||!Number.isFinite(Number(dato.valor))))throw new Error('Introduce una referencia numérica con su unidad.');
      const corte:CorteEquilibrio=tipo==='Txy'?{tipo,P:manual?{valor:Number(datoP.valor),unidad:datoP.unidad}:{valor:muestra.P,unidad:'Pa'}}:{tipo,T:manual?{valor:Number(datoT.valor),unidad:datoT.unidad}:{valor:muestra.T,unidad:'K'}};
      const solicitud=prepararSolicitudDiagrama(muestra,corte,ejeId,perfil,crypto.randomUUID());
      const guardado=cap?memoria.current.recuperar(solicitud,cap.trazador):undefined;
      const resultado=guardado?.respuesta??await trazarDiagrama(solicitud,control.signal,1000*((cap?.perfiles.find(p=>p.id===perfil)?.limiteSegundos??60)+20));
      if(!guardado)memoria.current.guardar(solicitud,resultado);
      if(control.vigente())setPaneles(p=>({...p,[tipo]:{resultado,consulta:guardado?.solicitud??solicitud,cargando:false}}));
    }catch(e){if(control.vigente())setPaneles(p=>({...p,[tipo]:{...p[tipo],cargando:false,error:(e as Error).name==='TimeoutError'?'Se agotó el tiempo de espera del servicio.':(e as Error).message}}));}
  }
  const calcularAmbos=()=>{persistir();void calcular('Txy');void calcular('Pxy');};
  const huellas=Object.values(paneles).flatMap(p=>p.resultado?.puntos.length?[p.resultado.identidad.huellaModelo]:[]),distintas=new Set(huellas).size>1;
  return <section aria-label="Equilibrio del estado seleccionado" className={styles.workspace}>
    <div className={styles.tools}>
      {s.volumenes.length>1&&<label>Volumen<select aria-label="Volumen del diagrama" value={vid} onChange={e=>{controles.current.Txy.cancelar();controles.current.Pxy.cancelar();setVid(e.target.value);setPaneles({Txy:{},Pxy:{}});}}>{s.volumenes.map(v=><option key={v.id} value={v.id}>{h.redTermodinamica?.nombres[`volumen:${v.id}`]??v.id}</option>)}</select></label>}
      <label>Instante · {num(muestra.tiempo)} s<input aria-label="Instante de equilibrio" type="range" min={0} max={r.tiempos.length-1} value={k} onChange={e=>seleccionarMuestra(Number(e.target.value))} onPointerUp={()=>persistir()} onKeyUp={()=>persistir()}/></label>
      <span className={styles.state}>{num(muestra.T-273.15)} °C · {num(muestra.P/1e5)} bar abs.</span>
      <button className={styles.primary} disabled={!soportado||paneles.Txy.cargando||paneles.Pxy.cargando} onClick={calcularAmbos}>Calcular ambos cortes</button>
    </div>
    {errorCap&&<div role="status" className={styles.notice}>{errorCap} <button onClick={()=>{setErrorCap('');setIntento(x=>x+1);}}>Comprobar servicio</button></div>}
    {!cap&&!errorCap&&<p role="status">Consultando capacidades del trazador…</p>}
    {muestra.componentes.length!==2&&<p className={styles.notice}>Este volumen contiene {muestra.componentes.length} componentes. Los cortes T–xy/P–xy son binarios; todos los componentes permanecen en el ensamblaje y en sus resultados.</p>}
    {cap&&muestra.componentes.length===2&&!paquete&&<p className={styles.notice}>El paquete {muestra.modelo.id} no publica este trazado. No se sustituirá por otro modelo.</p>}
    {soportado&&<>
      {!muestra.huellaParametros&&<p className={styles.notice}>Esta ejecución no incluye la huella de sus parámetros. Puedes consultar los cortes; para superponer su estado, <Link href={`/motor/hojas/${h.id}/resolver`}>vuelve a resolver</Link>.</p>}
      <div className={styles.axis}><label>Componente del eje<select aria-label="Componente del eje de equilibrio" value={ejeId} onChange={e=>{const id=Number(e.target.value);setEje(id);persistir({ejeId:id});}}>{muestra.componentes.map(c=><option value={c.id} key={c.id}>{c.nombre}</option>)}</select></label><span>{muestra.modelo.id} · v{muestra.modelo.version}</span></div>
      <details className={styles.options}><summary>Referencias y resolución</summary><div className={styles.settings}>
        <label>Temperatura en gráficas<select aria-label="Unidad de temperatura del diagrama" value={unidadT} onChange={e=>{const u=e.target.value as Preferencias['unidadT'];setUnidadT(u);persistir({unidadT:u});}}><option value="degC">°C</option><option value="K">K</option></select></label>
        <label>Presión en gráficas<select aria-label="Unidad de presión del diagrama" value={unidadP} onChange={e=>{const u=e.target.value as Preferencias['unidadP'];setUnidadP(u);persistir({unidadP:u});}}><option value="bar">bar abs.</option><option value="kPa">kPa abs.</option><option value="Pa">Pa abs.</option></select></label>
        <label>Resolución<select aria-label="Resolución del trazado" value={perfil} onChange={e=>setPerfil(e.target.value as PerfilResolucion)}>{cap!.perfiles.map(p=><option value={p.id} key={p.id}>{p.id==='exploratoria'?'Exploratoria':'Refinada'}</option>)}</select></label>
        <label className={styles.check}><input type="checkbox" checked={manualP} onChange={e=>{setManualP(e.target.checked);if(!datoP.valor)setDatoP({...datoP,valor:String(muestra.P/1e5)});}}/>Presión manual para T–xy</label>
        {manualP&&<div className={styles.quantity}><input aria-label="Presión de referencia del Txy" inputMode="decimal" value={datoP.valor} onChange={e=>setDatoP({...datoP,valor:e.target.value})}/><select aria-label="Unidad de presión de referencia" value={datoP.unidad} onChange={e=>setDatoP({...datoP,unidad:e.target.value})}>{['bar','kPa','Pa'].map(u=><option key={u}>{u}</option>)}</select></div>}
        <label className={styles.check}><input type="checkbox" checked={manualT} onChange={e=>{setManualT(e.target.checked);if(!datoT.valor)setDatoT({...datoT,valor:String(muestra.T-273.15)});}}/>Temperatura manual para P–xy</label>
        {manualT&&<div className={styles.quantity}><input aria-label="Temperatura de referencia del Pxy" inputMode="decimal" value={datoT.valor} onChange={e=>setDatoT({...datoT,valor:e.target.value})}/><select aria-label="Unidad de temperatura de referencia" value={datoT.unidad} onChange={e=>setDatoT({...datoT,unidad:e.target.value})}><option value="degC">°C</option><option value="K">K</option></select></div>}
      </div>{paquete?.coberturaGrupos&&<CoberturaGruposPaquete cobertura={paquete.coberturaGrupos} componentes={muestra.componentes}/>}</details>
      {distintas&&<p role="alert" className={styles.notice}>Los cortes identifican distintas versiones de parámetros. No se muestran juntos; vuelve a calcularlos.</p>}
      <div className={styles.grid}>{(['Txy','Pxy'] as const).map(tipo=>{
        const p=paneles[tipo],out=p.resultado,corte=out?.condicion?.corteSI;
        const referencia=corte?(corte.tipo==='Txy'?`${num(corte.P/(unidadP==='bar'?1e5:unidadP==='kPa'?1000:1))} ${unidadP} abs.`:`${num(unidadT==='K'?corte.T:corte.T-273.15)} ${unidadT==='K'?'K':'°C'}`):'Según la muestra seleccionada';
        return <article key={tipo} className={styles.panel} aria-label={`Diagrama ${tipo}`}>
          <header><div><h2>{tipo==='Txy'?'T–xy':'P–xy'}</h2><small>{referencia}</small></div><button disabled={p.cargando} onClick={()=>{persistir();void calcular(tipo);}}>Actualizar</button></header>
          {p.cargando&&<p role="status" className={styles.loading}>Calculando y verificando coexistencia…</p>}
          {p.error&&<p role="alert" className={styles.notice}>{p.error}</p>}
          {!out&&!p.cargando&&!p.error&&<div className={styles.empty}>Calcula el corte para obtener sus puntos de equilibrio.</div>}
          {out&&!distintas&&<>{out.puntos.length>0?<GraficaCorteEquilibrio r={out} muestra={muestra} ejeId={ejeId} unidadT={unidadT} unidadP={unidadP}/>:<p className={styles.notice}>{out.diagnosticos[0]?.mensaje??'No hay puntos certificados para este corte.'}</p>}
            <small className={styles.caption}>{out.estado} · {out.puntos.length} puntos · {out.cobertura?.huecos.length??0} huecos</small>
            <details className={styles.options}><summary>Verificación y procedencia</summary><p>{out.evidencia?.nivel} · {out.evidencia?.motivo}</p><p>{muestra.huellaParametros?'La consulta exige la huella de parámetros de la trayectoria.':'Esta ejecución no incluye huella de parámetros: la coincidencia histórica con el trazado no está verificada.'}</p><p>Las líneas interpolan puntos verificados; no certifican todo el intervalo.</p>{out.incidencias.map(i=><p key={i.id}>{i.tipo} · x del componente {out.condicion?.componenteEjeId}: [{num(i.intervaloXEje[0])}, {num(i.intervaloXEje[1])}] · {i.causa}</p>)}<p>{out.metodo}</p><pre>{JSON.stringify({identidad:out.identidad,cobertura:out.cobertura,diagnosticos:out.diagnosticos},null,2)}</pre></details>
            <button className={styles.download} onClick={()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({solicitud:p.consulta,respuesta:out},null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=`equilibrio-${tipo}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Descargar puntos y certificados JSON</button>
            {out.puntos.length>0&&<button className={styles.download} onClick={()=>{const url=URL.createObjectURL(new Blob([csvDiagrama(out)],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`equilibrio-${tipo}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>CSV de puntos</button>}
          </>}
        </article>;
      })}</div>
    </>}
  </section>;
}
