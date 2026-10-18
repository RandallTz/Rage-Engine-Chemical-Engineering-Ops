import type {RespuestaResolucionV2,SolicitudEnsamblajeV2} from './contratoEnsamblajeV2';
const fallo=(m:string):never=>{throw new Error(`Metadatos multifásicos incompatibles: ${m}`);};
const texto=(v:unknown):v is string=>typeof v==='string'&&v.length>0;
const estados=['cumple','no_cumple','no_evaluable'];
const listaIds=(a:unknown):a is string[]=>Array.isArray(a)&&a.every(texto)&&new Set(a).size===a.length;
export function validarMetadatosRed(r:RespuestaResolucionV2,s?:SolicitudEnsamblajeV2){
  const a=r.resultados!;
  if(a.procedenciaModelo!==undefined){
    if(!Array.isArray(a.procedenciaModelo)||!a.procedenciaModelo.length)fallo('procedencia de modelos ausente');
    const propietarios=new Set<string>();
    for(const p of a.procedenciaModelo){
      if(!listaIds(p.volumenIds)||!p.volumenIds.length||!texto(p.modelo?.id)||!texto(p.modelo.version)||!texto(p.huella)||!listaIds(p.componentesCAS)||!p.componentesCAS.length)fallo('procedencia de paquete incompleta');
      for(const id of p.volumenIds){
        if(propietarios.has(id)||!a.estados[id])fallo('propietario de huella duplicado o desconocido');propietarios.add(id);
        if(s){const v=s.volumenes.find(v=>v.id===id),paq=s.paquetes.find(q=>q.id===v?.paqueteId),cas=v?.componenteIds.map(cid=>s.componentes.find(c=>c.id===cid)?.identidadQuimica?.cas);
          if(!v||!paq||paq.modelo.id!==p.modelo.id||paq.modelo.version!==p.modelo.version||cas?.length!==p.componentesCAS.length||cas.some(c=>!c||!p.componentesCAS.includes(c)))fallo('huella de otro modelo o componentes');}
      }
    }
    if(Object.keys(a.estados).some(id=>!propietarios.has(id)))fallo('procedencia que omite volúmenes');
  }
  if(a.catalogoSeries!==undefined){
    const c=a.catalogoSeries;
    if(!Array.isArray(c)||c.length!==a.series.length||new Set(c.map(x=>x.variableId)).size!==c.length)fallo('catálogo incompleto o duplicado');
    for(const x of c){const serie=a.series.find(s=>s.variableId===x.variableId),v=r.validacion.variables.find(v=>v.id===x.variableEnsamblajeId);
      if(!serie||x.unidadSI!==serie.unidadSI||!texto(x.propietarioId)||!texto(x.magnitud)||!texto(x.procedencia)||!['estado_integrado','algebraica','dato','integral_auxiliar','derivada'].includes(x.papel)||x.variableEnsamblajeId!==null&&(!v||v.unidadSI!==x.unidadSI||v.propietarioId!==x.propietarioId))fallo('serie sin unidad, papel o referencia válida');
    }
  }
  for(const e of a.eventos){
    if(!listaIds(e.faseIds)||!Array.isArray(e.variableIds)||!e.variableIds.every(texto)||e.faseIdsAntes!==undefined&&!listaIds(e.faseIdsAntes)||e.faseIdsDespues!==undefined&&!listaIds(e.faseIdsDespues)||e.descripcion!==undefined&&!texto(e.descripcion))fallo('referencias del evento');
    if(e.volumenId!==null){const conocidos=new Set(a.estados[e.volumenId].flatMap(m=>m.evaluacion.fases.map(f=>f.id)));
      if([...e.faseIds,...e.faseIdsAntes??[],...e.faseIdsDespues??[]].some(id=>!conocidos.has(id)))fallo('ID de fase ajeno al volumen');
    }else if(e.faseIds.length||e.faseIdsAntes?.length||e.faseIdsDespues?.length)fallo('evento sin volumen con fases');
    if(e.faseIdsAntes&&e.faseIdsDespues){const diff=[...e.faseIdsAntes.filter(id=>!e.faseIdsDespues!.includes(id)),...e.faseIdsDespues.filter(id=>!e.faseIdsAntes!.includes(id))];if(diff.length!==e.faseIds.length||diff.some(id=>!e.faseIds.includes(id)))fallo('fases del evento no reconstruyen el cambio');}
  }
  const c=a.certificacion;if(c===undefined)return;
  const indice=(n:unknown)=>n===null||Number.isInteger(n)&&Number(n)>=0&&Number(n)<a.tiempos.length;
  const ids=['estados_termodinamicos','conservacion','cierre_constitutivo','segunda_ley'];
  if(!c||!estados.includes(c.estado)||!texto(c.motivo)||!Array.isArray(c.aspectos)||c.aspectos.length!==ids.length||new Set(c.aspectos.map(x=>x.id)).size!==ids.length||!indice(c.ultimaMuestraCertificada)||!c.alcance||c.alcance.tInicial!==a.tiempos[0]||c.alcance.tFinal!==a.tiempos.at(-1)||c.alcance.muestras!==a.tiempos.length||typeof c.alcance.completa!=='boolean')fallo('alcance de certificación');
  const referencias=new Set(['estados','segundaLey',...a.series.map(s=>s.variableId),...a.residuos.map(s=>s.ecuacionId)]);
  for(const x of c.aspectos)if(!ids.includes(x.id)||!estados.includes(x.estado)||!texto(x.motivo)||!listaIds(x.referencias)||x.referencias.some(id=>!referencias.has(id))||!indice(x.primeraMuestraNoCumple)||x.estado!=='no_cumple'&&x.primeraMuestraNoCumple!==null)fallo('aspecto de certificación');
  const esperado=c.aspectos.some(x=>x.estado==='no_cumple')?'no_cumple':c.aspectos.some(x=>x.estado==='no_evaluable')?'no_evaluable':'cumple';
  if(c.estado!==esperado||c.aspectos.find(x=>x.id==='segunda_ley')!.estado!==a.segundaLey.estado)fallo('estados de certificación contradictorios');
  const primeras=c.aspectos.flatMap(x=>x.primeraMuestraNoCumple===null?[]:[x.primeraMuestraNoCumple]);
  if(primeras.length&&c.ultimaMuestraCertificada!==null&&c.ultimaMuestraCertificada>=Math.min(...primeras)||c.estado==='cumple'&&c.ultimaMuestraCertificada!==a.tiempos.length-1)fallo('corte de certificación');
  for(const q of a.residuos)if(q.maximoEscalado>q.tolerancia&&!c.aspectos.some(x=>x.estado==='no_cumple'&&x.referencias.includes(q.ecuacionId)))fallo('residuo fallido presentado como certificado');
}
