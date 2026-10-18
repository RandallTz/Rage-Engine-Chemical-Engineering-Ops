import {analizarEnergia,compilarEnergia} from './modeloEnergia';
import {configuracionConEnergia} from './estadoEnergiaHoja';
import {balancesHoja,bloqueosBalances,BALANCES_LEGADOS} from './seleccionBalances';
import type {HojaMotor} from './hojasMotor';
import {analizarMotor,compilarMotor,firmaMotor,VERSION_SOLVER} from './modeloNumerico';
import {planEnsamblaje,compilarEnsamblaje,formulacionVolumen,datosEnsamblaje} from './ensamblajeMateria';
import {resolverMotor,resolverSistemaMotor} from './integracionMotor';
import {bloqueosCierreTermodinamico} from './estadoTermodinamicoHoja';
export const formulacionHoja=(h:HojaMotor)=>h.ensamblaje?formulacionVolumen(h.ensamblaje,h.ensamblaje.volumenes[0]):h.historial.pasos[h.historial.activo].formulacion;
export const analizarHoja=(h:HojaMotor)=>{
  const a=balancesHoja(h).energia?analizarEnergia(h):h.ensamblaje?planEnsamblaje(h.ensamblaje,h.config).analisis:analizarMotor(formulacionHoja(h),h.config);
  const bloqueos=[...bloqueosBalances(h),...bloqueosCierreTermodinamico(h)];
  return bloqueos.length?{...a,listo:false,bloqueos:[...bloqueos,...a.bloqueos]}:a;
};
export const compilarHoja=(h:HojaMotor)=>{
  const bloqueos=[...bloqueosBalances(h),...bloqueosCierreTermodinamico(h)];if(bloqueos.length)throw new Error(bloqueos[0]);
  return balancesHoja(h).energia?compilarEnergia(h):h.ensamblaje?compilarEnsamblaje(h.ensamblaje,h.config):compilarMotor(formulacionHoja(h),h.config);
};
export const configuracionHoja=(h:HojaMotor)=>balancesHoja(h).energia?configuracionConEnergia(h):h.ensamblaje?datosEnsamblaje(h.ensamblaje,h.config):h.config;
const firmaMateriaHoja=(h:HojaMotor)=>{
  if(!h.ensamblaje)return firmaMotor(formulacionHoja(h),h.config);
  const e=h.ensamblaje;
  const corrientes=e.corrientes.map(s=>{const base={id:s.id,nombre:s.nombre,desde:s.desde,hasta:s.hasta,constante:s.constante};const d=s.datos;
    return s.mecanismo||d?.T||d?.P||d?.fasesPermitidas||d?.materia.base==='molar'||d?.materia.modo==='total_y_composicion'?{...base,mecanismo:s.mecanismo??null,datos:d}:base;
  });
  return JSON.stringify([VERSION_SOLVER,'ensamblaje-materia-1',e.volumenes.map(v=>[v.id,v.nombre,v.volumenDeclarado,formulacionVolumen(e,v)]),corrientes,datosEnsamblaje(h.ensamblaje,h.config)]);
};
export const firmaHoja=(h:HojaMotor)=>{
  if(h.redTermodinamica)return JSON.stringify(['motor-ensamblaje-v2',{...h.redTermodinamica.solicitud,solicitudId:'',derivacion:undefined}]);
  const balances=balancesHoja(h);
  // Energy data are separate: inactive energy cannot change the material calculation identity.
  const base=firmaMateriaHoja(h);
  if(Object.keys(h.cierresDinamicos??{}).length)return JSON.stringify([base,'ensamblaje-termodinamico-borrador-1',balances,h.energia,h.cierresDinamicos]);
  const cierres=Object.entries(h.termodinamica?.estados??{}).filter(([,e])=>e.uso==='cierre').map(([id,e])=>[id,e.declaracion]);
  if(cierres.length)return JSON.stringify([base,'cierre-termodinamico-1',balances,h.energia,cierres]);
  if(balances.energia)return JSON.stringify([base,'energia-fundamental-1',balances,h.energia,h.supuestosBalances?.energia]);
  // Preserve legacy material result identities; navigation and inactive assumptions are not physics.
  return JSON.stringify(balances)===JSON.stringify(BALANCES_LEGADOS)?base:JSON.stringify([base,balances]);
};
export async function resolverHoja(h:HojaMotor,opciones:{signal?:AbortSignal;progreso?:(v:number)=>void}={}){
  const bloqueos=[...bloqueosBalances(h),...bloqueosCierreTermodinamico(h)];if(bloqueos.length)throw new Error(bloqueos[0]);
  if(balancesHoja(h).energia){
    const s=compilarEnergia(h),componentes=formulacionHoja(h).componentes!;
    const r=await resolverSistemaMotor(s,h.config,{componentes,firma:firmaHoja(h)},opciones);
    const estados=r.tiempos.map((t,k)=>s.evaluarEnergia(t,r.valores[k].map(v=>v[0])));
    return {...r,balancesEjecutados:balancesHoja(h).materia?['materia' as const,'energia' as const]:['energia' as const],trazabilidadEnergia:s.trazabilidad,seriesEvaluadas:s.catalogoSeries.map(q=>({...q,valores:estados.map(v=>v[q.id.startsWith('m_')?'m':q.id])}))};
  }
  if(!h.ensamblaje)return resolverMotor(formulacionHoja(h),h.config,opciones);
  const s=compilarEnsamblaje(h.ensamblaje,h.config);
  return resolverSistemaMotor(s,h.config,{firma:firmaHoja(h),componentes:s.estadosAcoplados!.map((v,i)=>({id:i+1,nombre:`${v.volumenNombre} · ${v.componenteNombre}`,simbolo:v.simbolo}))},opciones);
}
