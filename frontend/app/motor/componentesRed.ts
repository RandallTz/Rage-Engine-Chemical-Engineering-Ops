import type {RedTermodinamica} from './redTermodinamica';
import {datoRed} from './redTermodinamica';

// Document editing only: never fills compositions, inventories or properties.
// Call inside cambiarRed so an invalid operation is atomic and results expire.
export function asignarComponenteVolumen(red:RedTermodinamica,vid:string,cid:number,incluir:boolean,maximo?:number){
  const s=red.solicitud,v=s.volumenes.find(v=>v.id===vid);
  if(!v||!s.componentes.some(c=>c.id===cid))throw new Error('Volumen o componente no disponible.');
  if(v.componenteIds.includes(cid)===incluir)return;
  if(incluir){
    if(maximo!==undefined&&v.componenteIds.length>=maximo)throw new Error(`El servicio admite ${maximo} componentes por volumen.`);
    v.componenteIds.push(cid);
    const base=v.inicial.cantidades.base;
    v.inicial.cantidades.datoIds[cid]=datoRed(s,`volumen.${vid}.n0.${cid}`,base==='masica'?'masa':'cantidad',base==='masica'?'kg':'mol',`volumen:${vid}`,'inicial');
  }else{
    if(v.componenteIds.length===1)throw new Error('Cada volumen necesita al menos un componente.');
    const usadas=s.corrientes.filter(c=>(c.desde===vid||c.hasta===vid)&&c.componenteIds.includes(cid));
    if(usadas.length)throw new Error(`Retira primero el componente de las corrientes ${usadas.map(c=>c.id).join(', ')}.`);
    v.componenteIds=v.componenteIds.filter(id=>id!==cid);
    delete v.inicial.cantidades.datoIds[cid];
  }
}

export function agregarComponenteRed(red:RedTermodinamica,nombre:string,cas:string,volumenIds:string[],maximo?:number){
  const s=red.solicitud;
  if(!nombre.trim())throw new Error('Escribe el nombre del componente.');
  if(cas.trim()&&s.componentes.some(c=>c.identidadQuimica?.cas===cas.trim()))throw new Error('Ese CAS ya está en el catálogo.');
  if(volumenIds.some(id=>!s.volumenes.some(v=>v.id===id)))throw new Error('Volumen no disponible.');
  const id=Math.max(red.ultimoComponenteId??0,0,...s.componentes.map(c=>c.id))+1;
  if(!Number.isSafeInteger(id))throw new Error('No se pudo asignar un ID al componente.');
  red.ultimoComponenteId=id;
  s.componentes.push({id,nombre:nombre.trim(),simbolo:`C${id}`,...(cas.trim()?{identidadQuimica:{cas:cas.trim()}}:{})});
  for(const vid of new Set(volumenIds))asignarComponenteVolumen(red,vid,id,true,maximo);
  // Streams keep their explicit component sets. No implicit selective transport.
  return id;
}

export function asignarComponenteCorriente(red:RedTermodinamica,sid:string,cid:number,incluir:boolean){
  const s=red.solicitud,c=s.corrientes.find(c=>c.id===sid);
  if(!c||!s.componentes.some(x=>x.id===cid))throw new Error('Corriente o componente no disponible.');
  if(c.componenteIds.includes(cid)===incluir)return;
  if(incluir){
    if([c.desde,c.hasta].some(id=>id!==null&&!s.volumenes.find(v=>v.id===id)?.componenteIds.includes(cid)))throw new Error('Añade primero el componente a cada volumen conectado.');
    c.componenteIds.push(cid);
    if(c.materia.modo==='por_componente')c.materia.caudalIds[cid]=datoRed(s,`corriente.${sid}.F.${cid}`,c.materia.base==='masica'?'caudal':'caudal_molar',c.materia.base==='masica'?'kg/s':'mol/s',`corriente:${sid}`);
    if(c.estadoExterior&&c.componenteIds.length>1&&!c.estadoExterior.composicion)c.estadoExterior.composicion={base:'molar',fracciones:{}};
  }else{
    if(c.componenteIds.length===1)throw new Error('Cada corriente necesita al menos un componente.');
    c.componenteIds=c.componenteIds.filter(id=>id!==cid);
    if(c.materia.modo==='por_componente')delete c.materia.caudalIds[cid];
    if(c.estadoExterior?.composicion)delete c.estadoExterior.composicion.fracciones[cid];
  }
}

export function quitarComponenteRed(red:RedTermodinamica,cid:number){
  const s=red.solicitud;
  if(!s.componentes.some(c=>c.id===cid))throw new Error('Componente no disponible.');
  if(s.componentes.length===1)throw new Error('El catálogo necesita al menos un componente.');
  if(s.volumenes.some(v=>v.componenteIds.length===1&&v.componenteIds.includes(cid))||s.corrientes.some(c=>c.componenteIds.length===1&&c.componenteIds.includes(cid)))throw new Error('El componente es el único de un volumen o corriente.');
  red.ultimoComponenteId=Math.max(red.ultimoComponenteId??0,...s.componentes.map(c=>c.id));
  s.componentes=s.componentes.filter(c=>c.id!==cid);
  for(const v of s.volumenes){v.componenteIds=v.componenteIds.filter(id=>id!==cid);delete v.inicial.cantidades.datoIds[cid];}
  for(const c of s.corrientes){c.componenteIds=c.componenteIds.filter(id=>id!==cid);if(c.materia.modo==='por_componente')delete c.materia.caudalIds[cid];if(c.estadoExterior?.composicion)delete c.estadoExterior.composicion.fracciones[cid];}
  // Remaining fractions retain the user's values, even when they no longer sum to 1.
}

export function resumenComposicionExterior(ids:number[],fracciones:Record<string,number>){
  const faltan=ids.filter(id=>!Object.hasOwn(fracciones,id)),invalidas=ids.filter(id=>Object.hasOwn(fracciones,id)&&(!Number.isFinite(fracciones[id])||fracciones[id]<0||fracciones[id]>1));
  const sobran=Object.keys(fracciones).filter(id=>!ids.some(cid=>String(cid)===id));
  const suma=ids.reduce((total,id)=>total+(Number.isFinite(fracciones[id])?fracciones[id]:0),0);
  return {faltan,invalidas,sobran,suma,completa:!faltan.length&&!invalidas.length&&!sobran.length&&Math.abs(suma-1)<=1e-8};
}
