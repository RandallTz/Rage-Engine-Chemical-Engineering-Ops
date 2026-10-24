import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import {compararCondicionCorte} from './contextoMuestraEquilibrio';
import type {RespuestaDiagrama,SolicitudDiagrama,CorteEquilibrio,PerfilResolucion} from './contratoDiagramasEquilibrio';
import {normalizarCantidad} from './contratoTermodinamica';
import {leerDiagramaEquilibrio} from './lectorDiagramasEquilibrio';
import {firmaDatosPuros} from './sustitucionesDatosPuros';

export function prepararSolicitudDiagrama(c:ContextoMuestraEquilibrio,corte:CorteEquilibrio,ejeId:number,resolucion:PerfilResolucion,solicitudId:string):SolicitudDiagrama{
  if(c.componentes.length!==2)throw new Error(`El volumen conserva sus ${c.componentes.length} componentes. Este trazado requiere exactamente dos.`);
  if(!c.componentes.some(x=>x.id===ejeId))throw new Error('Componente del eje ajeno al volumen.');
  return {revision:1,solicitudId,componentes:structuredClone(c.componentes),modelo:structuredClone(c.modelo),...(c.datosPuros?{datosPuros:structuredClone(c.datosPuros)}:{}),...(c.huellaParametros?{huellaModeloEsperada:c.huellaParametros}:{}),componenteEjeId:ejeId,corte:structuredClone(corte),intervaloComposicion:[0,1],resolucion};
}
export type PuntoGraficaEquilibrio={x:number;valor:number;puntoId:string};
/** Preserve the backend's segment ordering. Different segments are distinct
 * series, never connected over a gap, and dew points are not re-sorted by y. */
export function curvasDiagrama(r:RespuestaDiagrama,ejeId:number,unidadT:'K'|'degC',unidadP:'Pa'|'kPa'|'bar'){
  if(!r.condicion?.componentes.some(c=>c.id===ejeId))throw new Error('El diagrama no contiene el componente del eje.');
  const tipo=r.condicion.corteSI?.tipo;
  const valor=(T:number,P:number)=>tipo==='Txy'?(unidadT==='K'?T:T-273.15):P/(unidadP==='bar'?1e5:unidadP==='kPa'?1000:1);
  const mapa=new Map(r.puntos.map(p=>[p.id,p]));
  return r.ramas.flatMap(rama=>rama.segmentos.flatMap(seg=>(['liquido','vapor'] as const).map(fase=>({id:`${rama.id}/${seg.id}/${fase}`,fase,segmentoId:seg.id,puntos:seg.puntoIds.map(id=>{const p=mapa.get(id);if(!p)throw new Error('Referencia de punto ausente.');return {x:p.fases.find(f=>f.tipo===fase)!.composicionMolar[ejeId],valor:valor(p.T,p.P),puntoId:id};})}))));
}

/** Plot certified L-L branch order and special-point compositions verbatim. */
export function liquidLiquidPlot(r:RespuestaDiagrama,ejeId:number,unidadT:'K'|'degC',unidadP:'Pa'|'kPa'|'bar'){
  if(!r.condicion?.componentes.some(component=>component.id===ejeId))throw new Error('The diagram does not contain this component axis.');
  const block=r.liquidoLiquido;
  const value=(T:number,P:number)=>r.condicion!.corte.tipo==='Txy'?(unidadT==='K'?T:T-273.15):P/(unidadP==='bar'?1e5:unidadP==='kPa'?1000:1);
  const points=new Map(block?.puntos.map(point=>[point.id,point]));
  const branches=block?.ramas.flatMap(branch=>(['liquido-a','liquido-b'] as const).map(phase=>({id:`${branch.id}/${phase}`,phase,points:branch.puntoIds.map(id=>{const point=points.get(id);if(!point)throw new Error('Missing liquid-liquid point reference.');return {x:point.fases.find(item=>item.id===phase)!.composicionMolar[ejeId],valor:value(point.T,point.P),puntoId:id};})})))??[];
  const critical=block?.puntosEspeciales.flatMap(point=>point.tipo==='critico_ll'&&point.certificado.estado==='cumple'?[{x:point.composiciones['liquido-critico'][ejeId],valor:value(point.T,point.P),puntoId:point.id}]:[])??[];
  const triple=block?.puntosEspeciales.flatMap(point=>point.tipo==='tres_fases'&&point.certificado.estado==='cumple'?(['liquido-a','liquido-b','vapor'] as const).map(phase=>({x:point.composiciones[phase][ejeId],valor:value(point.T,point.P),puntoId:point.id,phase})):[])??[];
  return {branches,critical,triple};
}
export function marcadoresMuestra(c:ContextoMuestraEquilibrio,r:RespuestaDiagrama,ejeId:number,unidadT:'K'|'degC',unidadP:'Pa'|'kPa'|'bar'){
  const corte=r.condicion?.corte;if(!corte)return {estado:'sin_corte' as const,puntos:[]};
  if(c.modelo.id!==r.identidad.modelo.id||c.modelo.version!==r.identidad.modelo.version||c.componentes.length!==r.condicion!.componentes.length||c.componentes.some(x=>r.condicion!.componentes.find(q=>q.id===x.id)?.cas!==x.identidadQuimica?.cas)||c.huellaParametros&&c.huellaParametros!==r.identidad.huellaModelo)return {estado:'otro_modelo' as const,puntos:[]};
  const comparacion=compararCondicionCorte(c,corte);
  if(!comparacion.compatible)return {estado:'otra_condicion' as const,comparacion,puntos:[]};
  if(c.muestraEnTramoSinCertificar)return {estado:'sin_certificar' as const,puntos:[]};
  if(!c.huellaParametros)return {estado:'sin_huella' as const,puntos:[]};
  const valor=corte.tipo==='Txy'?(unidadT==='K'?c.T:c.T-273.15):c.P/(unidadP==='bar'?1e5:unidadP==='kPa'?1000:1);
  return {estado:'misma_condicion' as const,puntos:c.fases.map(f=>({faseId:f.id,tipo:f.tipo,x:f.composicionMolar[ejeId],valor,puntoId:`muestra:${c.indice}:${f.id}`}))};
}

/** Independent generations for concurrent requests. Abort signals alone do not
 * prevent a resolved old promise from publishing into the current selection. */
export class VigenciaConsultaDiagrama{
  private generacion=0;
  private controlador:AbortController|null=null;
  iniciar(){this.controlador?.abort();this.controlador=new AbortController();const id=++this.generacion;return {signal:this.controlador.signal,vigente:()=>this.generacion===id&&!this.controlador!.signal.aborted};}
  cancelar(){this.controlador?.abort();this.generacion++;}
}

/** Cache only complete results whose parameter fingerprint is known. Retain
 * the original request/response identity instead of rewriting solicitudId to
 * masquerade as a new HTTP reply. Display names are not physical cache keys. */
export class MemoriaDiagramas{
  private entradas=new Map<string,{solicitud:SolicitudDiagrama;respuesta:RespuestaDiagrama}>();
  constructor(private limite=16){if(!Number.isInteger(limite)||limite<1)throw new Error('Límite de caché inválido.');}
  private clave(s:SolicitudDiagrama,trazador:{id:string;version:string}){
    if(!s.huellaModeloEsperada)return null;
    const fijo=s.corte.tipo==='Txy'?normalizarCantidad(s.corte.P,'P'):normalizarCantidad(s.corte.T,'T');
    return JSON.stringify([trazador,s.modelo,s.huellaModeloEsperada,firmaDatosPuros(s.datosPuros),s.componentes.map(c=>({id:c.id,identidadQuimica:c.identidadQuimica,masaMolar:c.masaMolar})).sort((a,b)=>a.id-b.id),s.componenteEjeId,s.corte.tipo,fijo,s.intervaloComposicion,s.resolucion]);
  }
  recuperar(s:SolicitudDiagrama,trazador:{id:string;version:string}){const key=this.clave(s,trazador),v=key?this.entradas.get(key):undefined;return v?structuredClone(v):undefined;}
  guardar(s:SolicitudDiagrama,r:RespuestaDiagrama){
    const key=this.clave(s,r.identidad.trazador);
    if(!key||r.estado!=='completo'||r.identidad.huellaModelo!==s.huellaModeloEsperada)return;
    leerDiagramaEquilibrio(r,s);
    this.entradas.delete(key);this.entradas.set(key,structuredClone({solicitud:s,respuesta:r}));
    while(this.entradas.size>this.limite)this.entradas.delete(this.entradas.keys().next().value!);
  }
}
export function csvDiagrama(r:RespuestaDiagrama,includeLiquidLiquid=false){
  if(includeLiquidLiquid&&(r.liquidoLiquido?.puntos.length||r.liquidoLiquido?.puntosEspeciales.some(point=>point.tipo!=='limite_dominio'))){
    const ids=r.condicion?.componentes.map(component=>component.id)??[];
    const rows:(string|number)[][]=[['branch','point','coexistence','phase','T [K]','P [Pa]',...ids.map(id=>`composition_${id} [mol/mol]`),'certificate']];
    for(const branch of r.ramas)for(const segment of branch.segmentos)for(const id of segment.puntoIds){const point=r.puntos.find(item=>item.id===id)!;for(const phase of point.fases)rows.push([branch.id,id,'LV',phase.tipo,point.T,point.P,...ids.map(id=>phase.composicionMolar[id]),point.certificado.estado]);}
    for(const point of r.liquidoLiquido.puntos)for(const phase of point.fases)rows.push([point.ramaId,point.id,'LL',phase.id,point.T,point.P,...ids.map(id=>phase.composicionMolar[id]),point.certificado.estado]);
    for(const point of r.liquidoLiquido.puntosEspeciales){if(point.tipo==='limite_dominio')continue;for(const [phase,composition] of Object.entries(point.composiciones))rows.push([point.ramaId,point.id,point.tipo,phase,point.T,point.P,...ids.map(id=>composition[id]),point.certificado.estado]);}
    return rows.map(row=>row.map(value=>typeof value==='number'?String(value):`"${value.replaceAll('"','""')}"`).join(',')).join('\n');
  }
  const ids=r.condicion?.componentes.map(c=>c.id)??[],cabecera=['rama','segmento','punto','T [K]','P [Pa]',...ids.map(id=>`x_${id} [mol/mol]`),...ids.map(id=>`y_${id} [mol/mol]`),'certificado'];
  const mapa=new Map(r.puntos.map(p=>[p.id,p])),filas=r.ramas.flatMap(b=>b.segmentos.flatMap(seg=>seg.puntoIds.map(id=>{const p=mapa.get(id);if(!p)throw new Error('Referencia de punto ausente.');const L=p.fases.find(f=>f.tipo==='liquido')!,V=p.fases.find(f=>f.tipo==='vapor')!;return [b.id,seg.id,p.id,p.T,p.P,...ids.map(id=>L.composicionMolar[id]),...ids.map(id=>V.composicionMolar[id]),p.certificado.estado];})));
  const celda=(v:string|number)=>typeof v==='number'?String(v):`"${v.replaceAll('"','""')}"`;
  return [cabecera,...filas].map(f=>f.map(celda).join(',')).join('\n');
}
