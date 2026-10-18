import type {SolicitudEnsamblajeV2,VariableV2} from './contratoEnsamblajeV2';
import type {DiagnosticoPreparacion} from './contratoEnsamblajeTermodinamico';

export type EnfoqueRed={propietarioId:string;datoId?:string;control?:'paquete'|'frontera'|'propiedades'|`componente:${number}`};
export type DestinoDiagnosticoRed=EnfoqueRed&{vista:'estado'|'resolver'};
type Consulta=Record<string,string|string[]|undefined>;

export function leerEnfoqueRed(q:Consulta):EnfoqueRed|undefined{
  const propietarioId=q.elemento,datoId=q.dato,control=q.control;
  if(typeof propietarioId!=='string'||!propietarioId||propietarioId.length>512)return;
  if(datoId!==undefined&&(typeof datoId!=='string'||!datoId||datoId.length>1024))return;
  if(control!==undefined&&(typeof control!=='string'||!(/^(paquete|frontera|propiedades|componente:\d+)$/.test(control))))return;
  if(datoId&&control)return;
  return {propietarioId,...(datoId?{datoId}:{}),...(control?{control:control as EnfoqueRed['control']}:{})};
}

export function enfoqueVigenteRed(s:SolicitudEnsamblajeV2,e?:EnfoqueRed):EnfoqueRed|undefined{
  if(!e)return;
  const volumen=s.volumenes.find(v=>`volumen:${v.id}`===e.propietarioId);
  if(e.propietarioId!=='componentes'&&e.propietarioId!=='estudio'&&!volumen&&
    !s.corrientes.some(c=>`corriente:${c.id}`===e.propietarioId)&&
    !s.intercambiosTermicos.some(c=>`calor:${c.id}`===e.propietarioId))return;
  if(e.datoId&&(!Object.hasOwn(s.datos,e.datoId)||s.datos[e.datoId].origen.propietarioId!==e.propietarioId))return;
  if(e.control==='paquete'||e.control==='frontera'||e.control==='propiedades'){if(!volumen)return;}
  else if(e.control){if(e.propietarioId!=='componentes'||!s.componentes.some(c=>`componente:${c.id}`===e.control))return;}
  return e;
}

/** Resolve only structured references. Never infer a field from a message or pick an owner's first datum. */
export function destinoDiagnosticoRed(s:SolicitudEnsamblajeV2,d:DiagnosticoPreparacion,variables:VariableV2[]=[]):DestinoDiagnosticoRed|null{
  const ruta=d.origen.ruta.replace(/^\/redTermodinamica\/solicitud(?=\/)/,'');
  const partes=ruta.split('/').slice(1).map(p=>p.replaceAll('~1','/').replaceAll('~0','~'));
  let datoId=partes[0]==='datos'&&Object.hasOwn(s.datos,partes[1])?partes[1]:undefined;
  if(!datoId){
    const ids=new Set(d.variableIds.flatMap(id=>Object.hasOwn(s.datos,id)?[id]:variables.filter(v=>v.id===id&&v.datoId&&Object.hasOwn(s.datos,v.datoId)).map(v=>v.datoId!)));
    if(ids.size===1)datoId=[...ids][0];
  }
  if(datoId)return {vista:'resolver',propietarioId:s.datos[datoId].origen.propietarioId,datoId};
  if(partes[0]==='componentes'){
    // The current protocol addresses components by stable ID, not by their array position.
    const c=s.componentes.find(c=>String(c.id)===partes[1]);
    return {vista:'estado',propietarioId:'componentes',...(c?{control:`componente:${c.id}` as const}:{})};
  }
  if(partes[0]==='paquetes'&&/^\d+$/.test(partes[1])&&partes[2]==='datosPuros'){
    const paquete=s.paquetes[Number(partes[1])],volumenes=s.volumenes.filter(v=>v.paqueteId===paquete?.id);
    const v=volumenes.find(v=>`volumen:${v.id}`===d.origen.propietarioId)??volumenes[0];
    return v?{vista:'estado',propietarioId:`volumen:${v.id}`,control:'propiedades'}:null;
  }
  let propietarioId=d.origen.propietarioId;
  if(!enfoqueVigenteRed(s,{propietarioId})){
    const listas={volumenes:s.volumenes,corrientes:s.corrientes,intercambiosTermicos:s.intercambiosTermicos};
    const tipos={volumenes:'volumen',corrientes:'corriente',intercambiosTermicos:'calor'};
    const k=partes[0] as keyof typeof listas,index=Number(partes[1]);
    if(Object.hasOwn(listas,k)&&/^\d+$/.test(partes[1])&&listas[k][index])propietarioId=`${tipos[k]}:${listas[k][index].id}`;
  }
  if(!enfoqueVigenteRed(s,{propietarioId}))return null;
  const control=propietarioId.startsWith('volumen:')&&partes[0]==='volumenes'?
    partes[2]==='paqueteId'?'paquete':partes[2]==='frontera'?'frontera':undefined:undefined;
  return {vista:'estado',propietarioId,...(control?{control}:{})};
}

export function urlEnfoqueRed(hojaId:string,vista:'estado'|'resolver',enfoque:EnfoqueRed){
  const q=new URLSearchParams({elemento:enfoque.propietarioId});
  if(enfoque.datoId)q.set('dato',enfoque.datoId);
  if(enfoque.control)q.set('control',enfoque.control);
  return `/motor/hojas/${encodeURIComponent(hojaId)}/${vista}?${q}`;
}

export function idEnfoqueRed(e:EnfoqueRed){
  return e.datoId?`red-${e.datoId}`:e.control?.startsWith('componente:')?`red-identidad-${e.control.slice(11)}`:
    e.control?`red-${e.control}-${e.propietarioId}`:`red-elemento-${e.propietarioId}`;
}
