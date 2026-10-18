import type {Componente} from './materiaEstado';
import type {ModeloEstado,PoliticaEstado} from './contratoTermodinamica';
import type {SolicitudEnsamblajeDinamico} from './contratoEnsamblajeTermodinamico';

/** Conservation structure, not a flash or an executable numerical assembly.
 * Scope: component conservation without reaction and total internal energy,
 * neglecting transported kinetic/potential energy. These restrictions must be
 * checked by the executable backend; this graph does not remove other terms.
 * One transfer has one identity at both ends. The backend remains responsible
 * for phase stability, property references, initialization, rank and execution.
 * Physical U balances are retained even when an integrator uses H coordinates. */
export type VolumenEstructural={id:string;componenteIds:number[];
  cierre:{modelo:ModeloEstado;politica:PoliticaEstado}|null;
  frontera:'rigida'|'presion_prescrita'|'sin_relacion'};
export type CorrienteEstructural={id:string;desde:string|null;hasta:string|null;componenteIds:number[];
  mecanismo:'convectivo'|'selectivo'|null};
export type IntercambioTermicoEstructural={id:string;desde:string|null;hasta:string|null;
  relacion:'impuesta'|'conductancia'};
export type RedTermodinamica={componentes:Componente[];volumenes:VolumenEstructural[];
  corrientes:CorrienteEstructural[];intercambios:IntercambioTermicoEstructural[]};
export type TransferenciaEstructural={id:string;desde:string|null;hasta:string|null;
  /** Canonical mass/energy rates, not aliases for raw molar/other-unit inputs.
   * Numerical conversion and donor properties belong to the backend assembly. */
  familia:'materia'|'energia';componenteId?:number;unidad:'kg/s'|'W';
  mecanismo:'materia_corriente'|'entalpia_donante'|'energia_selectiva_pendiente'|'calor'|'trabajo_frontera';
  corrienteId?:string;relacion?:'impuesta'|'conductancia'};
export type TerminoConservacion={transferenciaId:string;coeficiente:1|-1};
export type BalanceEstructural={id:string;propietarioId:string;familia:'materia'|'energia';
  componenteId?:number;variableId:string;unidad:'kg/s'|'W';terminos:TerminoConservacion[]};
export type BalanceGlobalEstructural={id:string;familia:'materia'|'energia';componenteId?:number;
  variableIds:string[];terminos:TerminoConservacion[];transferenciasInternasCanceladas:string[]};
export type DiagnosticoEstructural={codigo:string;estado:'invalido'|'pendiente';
  propietarioId:string;ruta:string};
export type CierreEstructural={volumenId:string;modelo:ModeloEstado|null;
  /** A set of phase types is an admissibility check, never a computed topology. */
  politica:PoliticaEstado|null;topologiaFases:'por_determinar';
  reconstruccion:'UV'|'PH'|'pendiente';estabilidad:'maximo_S_UVn'|'estable_a_TP_reconstruidos'|'pendiente';
  requisitos:('cantidades_por_componente'|'identidad_quimica'|'referencia_compatible'|'propiedades_consistentes'|'estabilidad_multifasica')[]};
export type EstructuraTermodinamica={revision:1;alcance:'conservacion_simbolica';ejecutable:false;
  /** No local equation count is advertised as degrees of freedom. */
  recuento:null;transferencias:TransferenciaEstructural[];balances:BalanceEstructural[];
  globales:BalanceGlobalEstructural[];cierres:CierreEstructural[];diagnosticos:DiagnosticoEstructural[]};

const idMateria=(v:string,c:number)=>`volumen.${v}.m.${c}`;
const idEnergia=(v:string)=>`volumen.${v}.U`;

/** Builds an incidence graph from declarations, independently of a scenario name,
 * phase count, component count, donor direction or numerical flow value.
 * A signed current changes donor at runtime, not incidence or its identity. */
export function estructurarTermodinamica(red:RedTermodinamica):EstructuraTermodinamica{
  const diagnosticos:DiagnosticoEstructural[]=[],transferencias:TransferenciaEstructural[]=[],balances:BalanceEstructural[]=[],cierres:CierreEstructural[]=[];
  const error=(codigo:string,ruta:string,propietarioId:string,estado:DiagnosticoEstructural['estado']='invalido')=>diagnosticos.push({codigo,estado,ruta,propietarioId});
  const componentes=new Set(red.componentes.map(c=>c.id)),volumenes=new Map(red.volumenes.map(v=>[v.id,v]));
  if(!componentes.size||componentes.size!==red.componentes.length||red.componentes.some(c=>!Number.isInteger(c.id)||c.id<1))error('CATALOGO_COMPONENTES','/componentes','modelo');
  if(!volumenes.size||volumenes.size!==red.volumenes.length)error('CATALOGO_VOLUMENES','/volumenes','modelo');
  const idsCorrientes=new Set<string>(),idsIntercambios=new Set<string>();
  const seleccionValida=(ids:number[])=>ids.length>0&&new Set(ids).size===ids.length&&ids.every(id=>componentes.has(id));
  for(const [i,v]of red.volumenes.entries()){
    if(!v.id||!seleccionValida(v.componenteIds))error('COMPONENTES_VOLUMEN',`/volumenes/${i}`,v.id);
    for(const c of v.componenteIds)balances.push({id:`materia.${v.id}.${c}`,propietarioId:v.id,familia:'materia',componenteId:c,variableId:idMateria(v.id,c),unidad:'kg/s',terminos:[]});
    balances.push({id:`energia.${v.id}`,propietarioId:v.id,familia:'energia',variableId:idEnergia(v.id),unidad:'W',terminos:[]});
    const reconstruccion=v.frontera==='rigida'?'UV':v.frontera==='presion_prescrita'?'PH':'pendiente';
    cierres.push({volumenId:v.id,modelo:v.cierre?.modelo??null,politica:v.cierre?.politica??null,
      topologiaFases:'por_determinar',reconstruccion,estabilidad:reconstruccion==='UV'?'maximo_S_UVn':reconstruccion==='PH'?'estable_a_TP_reconstruidos':'pendiente',
      requisitos:['cantidades_por_componente','identidad_quimica','referencia_compatible','propiedades_consistentes','estabilidad_multifasica']});
    if(!v.cierre?.modelo.id||!v.cierre.modelo.version)error('MODELO_PENDIENTE',`/volumenes/${i}/cierre`,v.id,'pendiente');
    if(v.frontera==='sin_relacion')error('RELACION_MECANICA_PENDIENTE',`/volumenes/${i}/frontera`,v.id,'pendiente');
  }
  // Invalid topology never yields a partial graph that could masquerade as the whole model.
  const extremosValidos=(desde:string|null,hasta:string|null)=>desde!==hasta&&[desde,hasta].every(id=>id===null||volumenes.has(id));
  for(const [i,s]of red.corrientes.entries()){
    const ruta=`/corrientes/${i}`;
    if(!s.id||idsCorrientes.has(s.id))error('CORRIENTE_REPETIDA',ruta,s.id);idsCorrientes.add(s.id);
    if(!extremosValidos(s.desde,s.hasta))error('EXTREMOS_CORRIENTE',ruta,s.id);
    if(!seleccionValida(s.componenteIds)||[s.desde,s.hasta].some(id=>id!==null&&s.componenteIds.some(c=>!volumenes.get(id)?.componenteIds.includes(c))))error('COMPONENTES_CORRIENTE',ruta,s.id);
    if(s.mecanismo!==null&&!['convectivo','selectivo'].includes(s.mecanismo))error('MECANISMO_CORRIENTE',ruta,s.id);
    if(s.mecanismo==='selectivo')error('ENERGIA_SELECTIVA_PENDIENTE',`${ruta}/mecanismo`,s.id,'pendiente');
  }
  for(const [i,q]of red.intercambios.entries()){
    if(!q.id||idsIntercambios.has(q.id))error('INTERCAMBIO_REPETIDO',`/intercambios/${i}`,q.id);idsIntercambios.add(q.id);
    if(!extremosValidos(q.desde,q.hasta))error('EXTREMOS_INTERCAMBIO',`/intercambios/${i}`,q.id);
    if(!['impuesta','conductancia'].includes(q.relacion))error('RELACION_INTERCAMBIO',`/intercambios/${i}/relacion`,q.id);
  }
  if(diagnosticos.some(d=>d.estado==='invalido'))return {revision:1,alcance:'conservacion_simbolica',ejecutable:false,recuento:null,transferencias:[],balances:[],globales:[],cierres,diagnosticos};

  function transferir(t:TransferenciaEstructural){
    transferencias.push(t);
    for(const b of balances){
      if(b.familia!==t.familia||b.componenteId!==t.componenteId)continue;
      if(b.propietarioId===t.desde)b.terminos.push({transferenciaId:t.id,coeficiente:-1});
      if(b.propietarioId===t.hasta)b.terminos.push({transferenciaId:t.id,coeficiente:1});
    }
  }
  for(const s of red.corrientes){
    // IDs are namespaced AND encoded: user IDs cannot alias a different transfer.
    const id=encodeURIComponent(s.id);
    for(const c of s.componenteIds)transferir({id:`corriente:${id}:materia:${c}`,desde:s.desde,hasta:s.hasta,familia:'materia',componenteId:c,unidad:'kg/s',mecanismo:'materia_corriente',corrienteId:s.id});
    transferir({id:`corriente:${id}:energia`,desde:s.desde,hasta:s.hasta,familia:'energia',unidad:'W',mecanismo:s.mecanismo==='selectivo'?'energia_selectiva_pendiente':'entalpia_donante',corrienteId:s.id});
  }
  for(const q of red.intercambios)transferir({id:`calor:${encodeURIComponent(q.id)}`,desde:q.desde,hasta:q.hasta,familia:'energia',unidad:'W',mecanismo:'calor',relacion:q.relacion});
  for(const v of red.volumenes)if(v.frontera!=='rigida')transferir({id:`trabajo:${encodeURIComponent(v.id)}`,desde:v.id,hasta:null,familia:'energia',unidad:'W',mecanismo:'trabajo_frontera'});

  const globales:BalanceGlobalEstructural[]=[];
  for(const componenteId of [...componentes,undefined]){
    const familia=componenteId===undefined?'energia':'materia',locales=balances.filter(b=>b.familia===familia&&b.componenteId===componenteId),coeficientes=new Map<string,number>();
    for(const b of locales)for(const t of b.terminos)coeficientes.set(t.transferenciaId,(coeficientes.get(t.transferenciaId)??0)+t.coeficiente);
    globales.push({id:componenteId===undefined?'global.energia':`global.materia.${componenteId}`,familia,componenteId,
      variableIds:locales.map(b=>b.variableId),terminos:[...coeficientes].filter(([,k])=>k!==0).map(([id,k])=>({transferenciaId:id,coeficiente:k as 1|-1})),
      transferenciasInternasCanceladas:[...coeficientes].filter(([,k])=>k===0).map(([id])=>id)});
  }
  return {revision:1,alcance:'conservacion_simbolica',ejecutable:false,recuento:null,transferencias,balances,globales,cierres,diagnosticos};
}

/** Bridge for the EXISTING v1 protocol. Never changes/sends a new HTTP field,
 * imports a saved flash result or claims multivolume support from the server. */
export function estructuraSolicitudDinamica(s:SolicitudEnsamblajeDinamico):EstructuraTermodinamica{
  return estructurarTermodinamica({componentes:s.componentes,volumenes:[{id:s.volumen.id,componenteIds:s.volumen.componenteIds,cierre:s.volumen.cierre,frontera:s.volumen.frontera.tipo}],
    corrientes:s.corrientes.map(c=>({id:String(c.id),desde:c.desde,hasta:c.hasta,componenteIds:c.componenteIds,mecanismo:c.mecanismo})),
    intercambios:Object.keys(s.transferencias).map(id=>({id,desde:null,hasta:s.volumen.id,relacion:'impuesta'}))});
}
