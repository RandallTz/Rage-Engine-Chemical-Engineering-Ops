import type {ResultadoMotor} from './modeloNumerico';
import type {Componente} from './materiaEstado';
import type {CantidadEstado,ModeloEstado,FaseEstado} from './contratoTermodinamica';
import {normalizarCantidad} from './contratoTermodinamica';
import {esMuestraFronteraEvento,validarEstadoVolumenV2} from './lectorEnsamblajeV2';
import {unidadesEstadoVolumen} from './verificarEstadoMateriaRed';
import type {SustitucionDatosPuros} from './contratoCatalogo';
import {datosPurosDeComponentes} from './sustitucionesDatosPuros';

export type InventarioFaseComponente={faseId:string;tipo:FaseEstado;x:number;n:number;m:number;reparto:number|null};
export type InventarioComponente={id:number;nombre:string;z:number;masaMolarKgMol:number;n:number;m:number;fases:InventarioFaseComponente[];nReconstruido:number;mReconstruida:number;residuoN:number;residuoM:number};
export type ContextoMuestraEquilibrio={
  volumenId:string;indice:number;tiempo:number;T:number;P:number;
  modelo:ModeloEstado;modeloEnsamblajeId:string;referencia:{id:string;descripcion:string};
  componentes:Componente[];inventarios:InventarioComponente[];
  fases:{id:string;tipo:FaseEstado;fraccionMolar:number;fraccionMasica:number;fraccionVolumen:number;composicionMolar:Record<string,number>}[];
  certificacionTrayectoria:'cumple'|'no_cumple'|'no_evaluable'|'no_disponible';
  muestraEnTramoSinCertificar:boolean;
  /** Historical responses may lack this additive field. Model ID/version
   * alone is never proof that parameter data match. */
  huellaParametros:string|null;
  datosPuros?:SustitucionDatosPuros;
};

/** Selected-sample adapter for any number of components and phases.
 * It reconstructs quantities from certified beta/x and the integrated n_i;
 * it does not call an EOS, decide phases, round, clip or normalize results.
 * Full trajectory validation remains the reader's responsibility. */
export function contextoMuestraEquilibrio(r:ResultadoMotor,volumenId:string,indice:number):ContextoMuestraEquilibrio{
  const e=r.ensamblajeV2,a=e?.respuesta.resultados;
  if(!e||!a)throw new Error('La muestra necesita un resultado del ensamblaje multifásico.');
  if(!Number.isInteger(indice)||indice<0||indice>=a.tiempos.length)throw new Error('Índice de muestra fuera de la trayectoria.');
  const v=e.solicitud.volumenes.find(v=>v.id===volumenId),m=a.estados[volumenId]?.[indice];
  if(!v||!m)throw new Error('Volumen o estado no disponible en la muestra.');
  const paquete=e.solicitud.paquetes.find(p=>p.id===v.paqueteId);
  if(!paquete||!e.respuesta.validacion.modeloId)throw new Error('La muestra no identifica su modelo.');
  const unidades=unidadesEstadoVolumen(v),valores:Record<string,number>={};
  for(const s of a.series){
    if(Object.hasOwn(valores,s.variableId)||!Number.isFinite(s.valores[indice])||unidades[s.variableId]&&s.unidadSI!==unidades[s.variableId])throw new Error(`Serie incompatible en la muestra: ${s.variableId}.`);
    valores[s.variableId]=s.valores[indice];
  }
  validarEstadoVolumenV2(m,e.solicitud,volumenId,valores,esMuestraFronteraEvento(e.respuesta,volumenId,indice));
  const N=v.componenteIds.reduce((s,id)=>s+valores[`volumen.${volumenId}.n.${id}`],0),ev=m.evaluacion;
  const componentes=v.componenteIds.map(id=>{const c=e.solicitud.componentes.find(c=>c.id===id);if(!c)throw new Error(`Componente ${id} sin identidad.`);return structuredClone(c);});
  const inventarios=componentes.map(c=>{
    const n=valores[`volumen.${volumenId}.n.${c.id}`],M=ev.componentes.find(x=>x.id===c.id)!.masaMolarKgMol;
    const fases=ev.fases.map(f=>{const cantidad=N*f.fraccionMolar*f.composicionMolar[c.id];return {faseId:f.id,tipo:f.tipo,x:f.composicionMolar[c.id],n:cantidad,m:cantidad*M,reparto:n>0?cantidad/n:null};});
    const nReconstruido=fases.reduce((s,f)=>s+f.n,0),mReconstruida=fases.reduce((s,f)=>s+f.m,0);
    if(![n*M,nReconstruido,mReconstruida].every(Number.isFinite))throw new Error(`Cantidad fuera de rango numérico para ${c.nombre}.`);
    return {id:c.id,nombre:c.nombre,z:ev.composicionMolar[c.id],masaMolarKgMol:M,n,m:n*M,fases,nReconstruido,mReconstruida,residuoN:nReconstruido-n,residuoM:mReconstruida-n*M};
  });
  const cert=a.certificacion;
  return {volumenId,indice,tiempo:a.tiempos[indice],T:ev.T,P:ev.P,modelo:structuredClone(paquete.modelo),modeloEnsamblajeId:e.respuesta.validacion.modeloId,referencia:structuredClone(ev.referencia),componentes,inventarios,...(paquete.datosPuros?{datosPuros:datosPurosDeComponentes(paquete.datosPuros,componentes)}:{}),
    fases:ev.fases.map(f=>({id:f.id,tipo:f.tipo,fraccionMolar:f.fraccionMolar,fraccionMasica:f.fraccionMasica,fraccionVolumen:f.fraccionVolumen,composicionMolar:{...f.composicionMolar}})),
    certificacionTrayectoria:cert?.estado??'no_disponible',muestraEnTramoSinCertificar:cert?.estado==='no_cumple'&&(cert.ultimaMuestraCertificada===null||indice>cert.ultimaMuestraCertificada),huellaParametros:a.procedenciaModelo?.find(p=>p.volumenIds.includes(volumenId))?.huella??null};
}

/** Local preparation, not an HTTP DTO or a declaration of backend support.
 * N-component contexts above stay intact. A binary view never drops species. */
export function referenciasCortesBinarios(c:ContextoMuestraEquilibrio,componenteEjeId:number){
  if(c.componentes.length!==2)return {estado:'no_binario' as const,motivo:`El volumen contiene ${c.componentes.length} componentes. T–xy y P–xy requieren un binario; el ensamblaje conserva todos sus componentes.`};
  if(!c.componentes.some(x=>x.id===componenteEjeId))throw new Error('El componente del eje no pertenece al volumen.');
  return {estado:'preparado' as const,servicio:'pendiente_contrato' as const,modelo:structuredClone(c.modelo),componentes:structuredClone(c.componentes),componenteEjeId,
    Txy:{P:{valor:c.P,unidad:'Pa'} satisfies CantidadEstado},Pxy:{T:{valor:c.T,unidad:'K'} satisfies CantidadEstado}};
}

/** A display comparison, not a physical certificate: a marker must not be
 * presented as lying on a cut at a different fixed T or P. Tolerances have
 * separate dimensional absolute scales and are reported to the caller. */
export function compararCondicionCorte(c:Pick<ContextoMuestraEquilibrio,'T'|'P'>,corte:{tipo:'Txy';P:CantidadEstado}|{tipo:'Pxy';T:CantidadEstado}){
  const magnitud=corte.tipo==='Txy'?'P':'T',referencia=normalizarCantidad(corte.tipo==='Txy'?corte.P:corte.T,magnitud),muestra=c[magnitud];
  const tolerancia=(magnitud==='P'?1e-3:1e-6)+1e-9*Math.max(Math.abs(muestra),Math.abs(referencia));
  return {compatible:Math.abs(muestra-referencia)<=tolerancia,magnitud,unidadSI:magnitud==='P'?'Pa':'K',muestra,referencia,diferencia:muestra-referencia,tolerancia};
}
