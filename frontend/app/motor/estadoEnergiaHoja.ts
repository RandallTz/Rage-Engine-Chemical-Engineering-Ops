import type {HojaMotor} from './hojasMotor';
import {formulacionVolumen,datosEnsamblaje,actualizarDatosEnsamblaje,normalizarEnsamblaje,claveCorriente,claveTotalCorriente} from './ensamblajeMateria';
import type {ConfiguracionMotor} from './modeloNumerico';
import {contextoEnergia,iniciarEnergia,actualEnergia,operarEnergia,tienePresionPrescrita} from './recorridoEnergia';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
export function materiaEnergiaHoja(h:HojaMotor){return h.ensamblaje?formulacionVolumen(h.ensamblaje,h.ensamblaje.volumenes[0]):h.historial.pasos[h.historial.activo].formulacion;}
export const contextoEnergiaHoja=(h:HojaMotor)=>contextoEnergia(materiaEnergiaHoja(h),h.ensamblaje?.volumenes[0].id??'dominio');
export function historialEnergiaHoja(h:HojaMotor){
  if(h.energia){
    const r=h.energia.historial;
    if([...r.pasos,...r.rehacer].every(p=>p.formulacion.presionPrescrita!==undefined))return r;
    const migrar=(p:typeof r.pasos[number])=>({...p,formulacion:{...p.formulacion,presionPrescrita:tienePresionPrescrita(p.formulacion,p.contexto)}});
    return {...r,pasos:r.pasos.map(migrar),rehacer:r.rehacer.map(migrar)};
  }
  let r=iniciarEnergia(contextoEnergiaHoja(h));const previo=h.supuestosBalances?.energia;
  if(previo?.estacionario)r=operarEnergia(r,'Recuperar hipótesis local de estacionario',{estacionario:true});
  if(previo?.sinConduccion)r=operarEnergia(r,'Recuperar hipótesis sin conducción local',{sinConduccionLocal:true});
  if(previo?.sinFuerzasVolumen)r=operarEnergia(r,'Recuperar hipótesis sin trabajo de fuerzas de volumen',{sinFuerzasVolumen:true});
  if(previo?.sinTrabajoEsfuerzos)r=operarEnergia(r,'Conservar restricción heredada del trabajo total de esfuerzos',{trabajoTotalHeredado:true},[String.raw`\nabla\cdot(\boldsymbol\sigma\cdot\mathbf v)=0`]);
  // The old full-stress exclusion is not equated to the weaker viscous-only hypothesis.
  return r;
}
export const formulacionEnergiaHoja=(h:HojaMotor)=>actualEnergia(historialEnergiaHoja(h)).formulacion;
/** Rebind the existing first law to the edited boundary; no hypotheses or data
 * are added. Keep the former equation as a journal step for audit/undo. */
export function actualizarContextoDinamico(h:HojaMotor):HojaMotor{
  if(!h.energia||!Object.keys(h.cierresDinamicos??{}).length)return h;
  const ctx=contextoEnergiaHoja(h),r=historialEnergiaHoja(h);
  if(JSON.stringify(actualEnergia(r).contexto)===JSON.stringify(ctx))return h;
  const puertos=new Set(h.ensamblaje?h.ensamblaje.corrientes.map(c=>c.id):ctx.puertos.map(p=>p.id));
  const componentes=new Set(materiaEnergiaHoja(h).componentes?.map(c=>c.id));
  // Removed ports must not silently seed a later port reusing a legacy ID.
  // Preserve declarations of surviving ports, geometry and initial states.
  const datos=Object.fromEntries(Object.entries(h.config.datos).filter(([id])=>{
    const flujo=/^(entrada|salida)_(\d+)_(\d+)$/.exec(id),presion=/^corriente_(\d+)_P$/.exec(id),inicial=/^inicial_(\d+)$/.exec(id);
    return flujo?puertos.has(Number(flujo[3]))&&componentes.has(Number(flujo[2])):presion?puertos.has(Number(presion[1])):inicial?componentes.has(Number(inicial[1])):true;
  }));
  const termicos=Object.fromEntries(Object.entries(h.energia.datos).filter(([id])=>{const corriente=/^energia_T_(\d+)$/.exec(id);return !corriente||puertos.has(Number(corriente[1]));}));
  const activas=<T,>(map:Record<string,T>|undefined)=>map?Object.fromEntries(Object.entries(map).filter(([id])=>puertos.has(Number(id)))):undefined;
  return {...h,config:{...h.config,datos},presionesExterioresInactivas:activas(h.presionesExterioresInactivas),cierresDinamicos:Object.fromEntries(Object.entries(h.cierresDinamicos!).map(([id,c])=>[id,{...c,presionesCorrientes:activas(c.presionesCorrientes),extracciones:activas(c.extracciones)}])),energia:{...h.energia,datos:termicos,historial:operarEnergia(r,'Actualizar el volumen y sus corrientes',{},[],ctx)},resultado:undefined,resultadoRef:undefined};
}
/** Shared by boundary-field selection, final equations and the manual compiler.
 * A flow that is not provably constant needs a donor on either side. */
export function donanteCorrienteEnergia(h:HojaMotor,id:number):'exterior'|'volumen'|'variable'{
  const p=contextoEnergiaHoja(h).puertos.find(p=>p.id===id),componente=materiaEnergiaHoja(h).componentes?.[0];
  if(!p||!componente)return 'variable';
  const c=h.ensamblaje?datosEnsamblaje(h.ensamblaje,h.config):h.config;
  const total=h.ensamblaje?.corrientes.find(s=>s.id===id)?.datos?.materia?.modo==='total_y_composicion';
  const clave=h.ensamblaje?total?claveTotalCorriente(id):claveCorriente(id,componente.id):`${p.sentido}_${componente.id}_${id}`;
  const d=c.datos[clave];
  if(d?.texto.trim())try{return (p.sentido==='entrada'?1:-1)*evaluarExpresion(analizarExpresion(d.texto,[]),{})>0?'exterior':'volumen';}catch{}
  return 'variable';
}
export function configuracionConEnergia(h:HojaMotor):ConfiguracionMotor{
  const c=h.ensamblaje?datosEnsamblaje(h.ensamblaje,h.config):h.config,datos={...c.datos,...h.energia?.datos};
  for(const s of h.ensamblaje?.corrientes??[])if(s.datos?.T){const id=`energia_T_${s.id}`;datos[id]=s.datos.T;}
  return {...c,datos};
}
export function actualizarConfiguracionEnergia(h:HojaMotor,c:ConfiguracionMotor):HojaMotor{
  const datos=Object.fromEntries(Object.entries(c.datos).filter(([id])=>!id.startsWith('energia_'))),termicos=Object.fromEntries(Object.entries(c.datos).filter(([id])=>id.startsWith('energia_')));
  let e=h.ensamblaje;
  if(e?.version===1){const normalizado=normalizarEnsamblaje(e,{...c,datos});e=normalizado.ensamblaje;}
  if(e)e={...e,corrientes:e.corrientes.map(s=>{const id=`energia_T_${s.id}`,T=termicos[id];delete termicos[id];return s.datos?{...s,datos:{...s.datos,...(T?{T}: {})},resultado:undefined}:s;})};
  return {...h,...(e?actualizarDatosEnsamblaje(e,{...c,datos}):{config:{...c,datos}}),energia:{...h.energia,historial:historialEnergiaHoja(h),datos:termicos},resultado:undefined,resultadoRef:undefined};
}
