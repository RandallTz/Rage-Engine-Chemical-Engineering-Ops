'use client';
import {useEffect,useState} from 'react';
import type {HojaMotor} from './hojasMotor';
import type {CapacidadesEnsamblaje} from './contratoEnsamblajeTermodinamico';
import {capacidadesEnsamblaje} from './servicioEnsamblaje';
import {elegirCierreReal,elegirCierreManual,aplicarPoliticaDinamica} from './datosEnsamblajeTermodinamico';
import {formulacionEnergiaHoja} from './estadoEnergiaHoja';
import {volumenesControl} from './volumenControl';
import {identificarComponenteEstado} from './estadoTermodinamicoHoja';
import styles from './estadoTermodinamico.module.css';
export default function ElegirCierreEnergia({h,volumenId,onGuardar}:{h:HojaMotor;volumenId:string;onGuardar:(f:(h:HojaMotor)=>HojaMotor)=>void}){
  const [cap,setCap]=useState<CapacidadesEnsamblaje|null>(null),[error,setError]=useState(''),[revisar,setRevisar]=useState(false);
  useEffect(()=>{const ctl=new AbortController();capacidadesEnsamblaje(ctl.signal).then(c=>{if(!ctl.signal.aborted)setCap(c);}).catch(e=>{if(!ctl.signal.aborted)setError((e as Error).message);});return()=>ctl.abort();},[]);
  const cierre=h.cierresDinamicos?.[volumenId],e=formulacionEnergiaHoja(h),comps=volumenesControl(h).find(v=>v.id===volumenId)?.f.componentes??[];
  const modelo=cap?.modelos.find(m=>m.id==='agua-iapws95'),admitido=!!cap?.disponible&&!!modelo;
  return <section id="cierre-energia" className={styles.definition} aria-label="Energy closure"><h2>Energy closure</h2><div className={styles.modeGrid}><button aria-pressed={!cierre} onClick={()=>{setRevisar(false);onGuardar(elegirCierreManual);}}><span>Declared u(T) relation</span><small>Custom parameters</small></button><button disabled={!admitido} aria-pressed={!!cierre} onClick={()=>{if(cierre)return;if(e.modelo==='u_lineal'||e.densidadConstante)setRevisar(true);else onGuardar(q=>elegirCierreReal(q,modelo!));}}><span>Agua real · IAPWS-95</span><small>Estado y fases calculados</small></button></div>
    {error&&<small role="status" className={styles.scope}>{error}</small>}{cap&&!cap.disponible&&<small className={styles.scope}>{cap.motivo}</small>}
    {revisar&&<div className={styles.notice}><span>Sustituir u(T) y la densidad constante por IAPWS-95. Tus valores se conservan como datos inactivos.{h.energia?.inicial==='U'?' U(0) se interpretará en la referencia IAPWS-95.':''}</span><button onClick={()=>{onGuardar(q=>elegirCierreReal(q,modelo!));setRevisar(false);}}>Aplicar cierre real</button><button onClick={()=>setRevisar(false)}>Cancel</button></div>}
    {cierre&&<><div className={styles.viewTabs} aria-label="Phase policy">{(['monofasico','sin_restriccion'] as const).map(cantidad=><button key={cantidad} aria-pressed={cierre.politica.cantidad===cantidad} onClick={()=>onGuardar(q=>aplicarPoliticaDinamica(q,{...cierre.politica,cantidad}))}>{cantidad==='monofasico'?'Una fase':"Liquid–vapor equilibrium"}</button>)}</div><label className={styles.phaseSwitch}><input type="checkbox" checked={cierre.politica.cambioInterno==='permitido'} onChange={e=>onGuardar(q=>aplicarPoliticaDinamica(q,{...cierre.politica,cambioInterno:e.target.checked?'permitido':'prohibido'}))}/>Allow phase change</label>
      {comps.map(c=><div key={c.id} className={styles.identityRow}><span>{c.nombre} · {c.identidadQuimica?.cas??'CAS sin declarar'}</span>{!c.identidadQuimica?.cas&&<button onClick={()=>onGuardar(q=>identificarComponenteEstado(q,c.id,'7732-18-5'))}>Identificar como agua</button>}</div>)}
    </>}
  </section>;
}
