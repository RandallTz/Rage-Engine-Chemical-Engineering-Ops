import type {RedTermodinamica} from './redTermodinamica';
import {datoRed,sincronizarHipotesis} from './redTermodinamica';
import type {ModeloEstado} from './contratoTermodinamica';

export type TipoElementoRed='volumen'|'corriente'|'calor';
const prefijos={volumen:'v',corriente:'s',calor:'q'} as const;
export function maximoElementoRed(red:RedTermodinamica,tipo:TipoElementoRed){
  const xs=tipo==='volumen'?red.solicitud.volumenes:tipo==='corriente'?red.solicitud.corrientes:red.solicitud.intercambiosTermicos;
  return Math.max(red.ultimosElementos?.[tipo]??0,0,...xs.map(x=>{const n=x.id.startsWith(prefijos[tipo])?x.id.slice(1):'';return /^\d+$/.test(n)&&Number.isSafeInteger(Number(n))?Number(n):0;}));
}
/** IDs are local document identities, never a physical model or equipment preset. */
export function agregarElementoRed(red:RedTermodinamica,tipo:TipoElementoRed){
  const a=red.solicitud,n=maximoElementoRed(red,tipo)+1,id=prefijos[tipo]+n;
  if(!Number.isSafeInteger(n)||!a.volumenes.length)throw new Error('No se pudo crear el elemento.');
  red.ultimosElementos={...red.ultimosElementos,[tipo]:n};
  red.nombres[`${tipo}:${id}`]=`${tipo==='volumen'?'Volumen':tipo==='corriente'?'Corriente':'Calor'} ${n}`;
  if(tipo==='volumen'){
    const v=structuredClone(a.volumenes[0]),base=v.inicial.cantidades.base,tipoInicial=v.inicial.energia.tipo;v.id=id;
    v.inicial={cantidades:{base,datoIds:Object.fromEntries(v.componenteIds.map(cid=>[cid,datoRed(a,`volumen.${id}.n0.${cid}`,base==='masica'?'masa':'cantidad',base==='masica'?'kg':'mol',`volumen:${id}`,'inicial')]))},energia:{tipo:tipoInicial,datoId:datoRed(a,`volumen.${id}.${tipoInicial}0`,tipoInicial==='T'?'temperatura':'energia',tipoInicial==='T'?'K':'J',`volumen:${id}`,'inicial')}};
    v.frontera=v.frontera.tipo==='presion_prescrita'?{tipo:'presion_prescrita',presionId:datoRed(a,`volumen.${id}.P`,'presion','Pa',`volumen:${id}`)}:{tipo:'rigida',datoId:datoRed(a,`volumen.${id}.V`,'volumen','m3',`volumen:${id}`,'geometria')};
    sincronizarHipotesis(v);a.volumenes.push(v);
  }
  if(tipo==='corriente')a.corrientes.push({id,desde:a.volumenes[0].id,hasta:a.volumenes[1]?.id??null,componenteIds:a.volumenes[0].componenteIds.filter(cid=>!a.volumenes[1]||a.volumenes[1].componenteIds.includes(cid)),mecanismo:'convectivo',materia:{modo:'total_desde_donante',base:'masica',caudalId:datoRed(a,`corriente.${id}.F`,'caudal','kg/s',`corriente:${id}`)}});
  if(tipo==='calor')a.intercambiosTermicos.push({id,desde:null,hasta:a.volumenes[0].id,ley:{tipo:'impuesto',potenciaId:datoRed(a,`calor.${id}.Q`,'potencia','W',`calor:${id}`)}});
  return id;
}
export function quitarElementoRed(red:RedTermodinamica,tipo:TipoElementoRed,id:string){
  const a=red.solicitud;
  red.ultimosElementos={...red.ultimosElementos,[tipo]:maximoElementoRed(red,tipo)};
  if(tipo==='volumen'){
    if(!a.volumenes.some(v=>v.id===id))throw new Error('Volumen no disponible.');
    if(a.volumenes.length===1)throw new Error('El sistema necesita al menos un volumen.');
    // Reserve IDs before connected elements leave the active document.
    red.ultimosElementos.corriente=maximoElementoRed(red,'corriente');red.ultimosElementos.calor=maximoElementoRed(red,'calor');
    a.volumenes=a.volumenes.filter(v=>v.id!==id);
    a.corrientes=a.corrientes.filter(c=>c.desde!==id&&c.hasta!==id);
    a.intercambiosTermicos=a.intercambiosTermicos.filter(q=>q.desde!==id&&q.hasta!==id);
  }else if(tipo==='corriente'){
    if(!a.corrientes.some(c=>c.id===id))throw new Error('Corriente no disponible.');
    a.corrientes=a.corrientes.filter(c=>c.id!==id);
  }else{
    if(!a.intercambiosTermicos.some(q=>q.id===id))throw new Error('Intercambio no disponible.');
    a.intercambiosTermicos=a.intercambiosTermicos.filter(q=>q.id!==id);
  }
}
/** Editing a volume must not modify another volume through a shared package ID. */
export function elegirPaqueteVolumen(red:RedTermodinamica,vid:string,modelo:ModeloEstado){
  const a=red.solicitud,v=a.volumenes.find(v=>v.id===vid);
  if(!v)throw new Error('Volumen no disponible.');
  const previo=a.paquetes.find(p=>p.id===v.paqueteId);
  if(previo&&previo.modelo.id===modelo.id&&previo.modelo.version===modelo.version)return;
  if(previo&&!a.volumenes.some(x=>x.id!==vid&&x.paqueteId===previo.id)){previo.modelo=structuredClone(modelo);return;}
  const base=`paquete-${vid}`;let id=base,n=1;
  while(a.paquetes.some(p=>p.id===id))id=`${base}-${++n}`;
  a.paquetes.push({id,modelo:structuredClone(modelo),...(previo?.datosPuros?{datosPuros:structuredClone(previo.datosPuros)}:{})});v.paqueteId=id;
  if(previo&&red.originalesDatosPuros?.[previo.id])red.originalesDatosPuros[id]=structuredClone(red.originalesDatosPuros[previo.id]);
}
