import {commonSource,derivedSourceIdentity} from '../models/derivedSelection';
import { thermodynamicJournalFromHistory, derivationFingerprint } from './physicalDerivation';
import {actualTermo} from './recorridoTermodinamico';
import {analizarEnergia,compilarEnergia} from './modeloEnergia';
import {configuracionConEnergia} from './estadoEnergiaHoja';
import {balancesHoja,bloqueosBalances,BALANCES_LEGADOS} from './seleccionBalances';
import type {HojaMotor} from './hojasMotor';
import {analizarMotor,compilarMotor,firmaMotor,VERSION_SOLVER} from './modeloNumerico';
import {planEnsamblaje,compilarEnsamblaje,formulacionVolumen,datosEnsamblaje} from './ensamblajeMateria';
import {resolverMotor,resolverSistemaMotor} from './integracionMotor';
import {bloqueosCierreTermodinamico} from './estadoTermodinamicoHoja';
import { definitionOf, ensureInventoryExecution } from '../models/dynamicDefinition';
import { momentumJournalOf } from '../models/momentumDerivation';
import { equationSourceRevision } from '../models/equationWorkbench';
export const formulacionHoja=(h:HojaMotor)=>h.ensamblaje?formulacionVolumen(h.ensamblaje,h.ensamblaje.volumenes[0]):h.historial.pasos[h.historial.activo].formulacion;
export const analizarHoja=(h:HojaMotor)=>{
  const a=balancesHoja(h).energia?analizarEnergia(h):h.ensamblaje?planEnsamblaje(h.ensamblaje,h.config).analisis:analizarMotor(formulacionHoja(h),h.config);
  const bloqueos=[...bloqueosBalances(h),...bloqueosCierreTermodinamico(h)];
  return bloqueos.length?{...a,listo:false,bloqueos:[...bloqueos,...a.bloqueos]}:a;
};
export const compilarHoja=(h:HojaMotor)=>{
  if(h.equationWorkbench?.cursor)throw new Error('Equation operations require Python compilation; the browser compiler cannot substitute the earlier formulation.');
  ensureInventoryExecution(h);
  const bloqueos=[...bloqueosBalances(h),...bloqueosCierreTermodinamico(h)];if(bloqueos.length)throw new Error(bloqueos[0]);
  return balancesHoja(h).energia?compilarEnergia(h):h.ensamblaje?compilarEnsamblaje(h.ensamblaje,h.config):compilarMotor(formulacionHoja(h),h.config);
};
export const configuracionHoja=(h:HojaMotor)=>balancesHoja(h).energia?configuracionConEnergia(h):h.ensamblaje?datosEnsamblaje(h.ensamblaje,h.config):h.config;
const firmaMateriaHoja=(h:HojaMotor)=>{
  if(!h.ensamblaje)return firmaMotor(formulacionHoja(h),h.config);
  const e=h.ensamblaje;
  const corrientes=e.corrientes.map(s=>{const base={id:s.id,desde:s.desde,hasta:s.hasta,constante:s.constante};const d=s.datos;
    return s.mecanismo||d?.T||d?.P||d?.fasesPermitidas||d?.materia.base==='molar'||d?.materia.modo==='total_y_composicion'?{...base,mecanismo:s.mecanismo??null,datos:d}:base;
  });
  return JSON.stringify([VERSION_SOLVER,'ensamblaje-materia-1',e.volumenes.map(v=>[v.id,v.volumenDeclarado,formulacionVolumen(e,v)]),corrientes,datosEnsamblaje(h.ensamblaje,h.config)]);
};
const physicalExecutionBase=(h:HojaMotor)=>{
  if(h.redTermodinamica){const request=h.redTermodinamica.solicitud;return JSON.stringify(['motor-ensamblaje-v2','phase-event-context-1',{...request,solicitudId:'',derivacion:derivationFingerprint(request.derivacion)}]);}
  const balances=balancesHoja(h);
  // Energy data are separate: inactive energy cannot change the material calculation identity.
  const base=firmaMateriaHoja(h);
  const thermoJournal=h.recorridoTermodinamico?thermodynamicJournalFromHistory(h.recorridoTermodinamico):undefined;
  const thermoEvidence=thermoJournal?.operations.length?[{thermodynamicDerivation:thermoJournal}]:[];
  if(Object.keys(h.cierresDinamicos??{}).length)return JSON.stringify([base,'ensamblaje-termodinamico-borrador-1',balances,h.energia,h.cierresDinamicos,...thermoEvidence]);
  const cierres=Object.entries(h.termodinamica?.estados??{}).filter(([,e])=>e.uso==='cierre').map(([id,e])=>[id,e.declaracion]);
  if(cierres.length)return JSON.stringify([base,'cierre-termodinamico-1',balances,h.energia,cierres,...thermoEvidence]);
  if(balances.energia)return JSON.stringify([base,'energia-fundamental-1',balances,h.energia,h.supuestosBalances?.energia,...(h.recorridoTermodinamico?[actualTermo(h.recorridoTermodinamico).supuestos]:[]),...thermoEvidence]);
  // Preserve legacy material result identities; navigation and inactive assumptions are not physics.
  return JSON.stringify(balances)===JSON.stringify(BALANCES_LEGADOS)?base:JSON.stringify([base,balances]);
};
/** Numerical settings do not change a derived mathematical formulation. */
export const physicalExecutionSignature=(h:HojaMotor)=>{
  if(h.commonModel)return JSON.stringify(['common-derived-v1',derivedSourceIdentity(commonSource(h)),h.commonModel.estudio,h.derivedSelection??null]);
  const base=physicalExecutionBase(h),definition=definitionOf(h);
  const journal=momentumJournalOf(h);
  const physical=definition?.operations.length&&!h.redTermodinamica?JSON.stringify([base,definition]):base;
  let current=journal&&!h.redTermodinamica?JSON.stringify([physical,journal]):physical;
  if(h.equationWorkbench?.cursor)current=JSON.stringify([current,'equation-workbench-1',h.equationWorkbench.operations.slice(0,h.equationWorkbench.cursor)]);
  if(h.redTermodinamica||balancesHoja(h).energia||journal||h.equationWorkbench?.cursor)current=JSON.stringify([current,equationSourceRevision]);
  return h.hydraulicNetwork?JSON.stringify([current,'reduced-hydraulics-equation-operations-3',h.hydraulicNetwork,h.ensamblaje?.volumenes.map(v=>v.balances)]):current;
};
export const transformationSourceSignature=(h:HojaMotor)=>physicalExecutionSignature({...h,config:{...h.config,metodo:'rk45',muestras:2,rtol:1e-6,atol:1e-9}});
export const firmaHoja=(h:HojaMotor)=>h.transformation?JSON.stringify([physicalExecutionSignature(h),'selected-transformation-v1',h.transformation]):physicalExecutionSignature(h);
export async function resolverHoja(h:HojaMotor,opciones:{signal?:AbortSignal;progreso?:(v:number)=>void}={}){
  if(h.equationWorkbench?.cursor)throw new Error('Equation operations require Python compilation; this legacy browser route is not connected.');
  ensureInventoryExecution(h);
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
