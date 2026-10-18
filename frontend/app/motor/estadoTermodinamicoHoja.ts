import type {HojaMotor} from './hojasMotor';
import type {Componente} from './materiaEstado';
import type {DeclaracionEstado,EstadoGuardado,SolicitudEstado,RespuestaEstado,EspecificacionEstado} from './contratoTermodinamica';
import {analizarSolicitudEstado,firmaEstado,validarRespuestaEstado} from './contratoTermodinamica';
import {catalogoComponentes} from './ensamblajeMateria';
import {recorridoMateria} from './recorridoMateria';

export function propietariosEstado(h:HojaMotor){
  const componentes=h.ensamblaje?catalogoComponentes(h.ensamblaje):h.historial.pasos[h.historial.activo].formulacion.componentes??[];
  return h.ensamblaje?[
    ...h.ensamblaje.volumenes.map(v=>({id:`volumen:${v.id}`,nombre:v.nombre,tipo:'volumen' as const,componentes:componentes.filter(c=>!v.componentesIds||v.componentesIds.includes(c.id))})),
    ...h.ensamblaje.corrientes.map(s=>({id:`corriente:${s.id}`,nombre:s.nombre,tipo:'corriente' as const,componentes:componentes.filter(c=>!s.componentesIds||s.componentesIds.includes(c.id))})),
  ]:[{id:'volumen:dominio',nombre:'Volumen de control',tipo:'volumen' as const,componentes}];
}
export function iniciarDeclaracionEstado(ids:number[]=[]):DeclaracionEstado{return {modelo:{id:'',version:''},especificacion:{tipo:'TP',T:{valor:null,unidad:'K'},P:{valor:null,unidad:'Pa'},composicion:{base:'molar',fracciones:ids.length===1?{[ids[0]]:1}:{}}},politica:{cantidad:'sin_restriccion',cambioInterno:'permitido',evaluacion:'equilibrio_estable'}};}
/** Keep common declarations; never obtain new inputs from a computed state or tank geometry. */
export function cambiarTipoEstado(s:EspecificacionEstado,tipo:EspecificacionEstado['tipo'],ids:number[]):EspecificacionEstado{
  if(s.tipo===tipo)return s;
  const blanco=(unidad:string)=>({valor:null,unidad});
  const composicion='composicion'in s?s.composicion:{base:'molar' as const,fracciones:ids.length===1?{[ids[0]]:1}:{}};
  const cantidades='cantidades'in s?s.cantidades:{base:'masica' as const,valores:Object.fromEntries(ids.map(id=>[String(id),blanco('kg')]))};
  return tipo==='TP'?{tipo,T:blanco('K'),P:'P'in s?s.P:blanco('Pa'),composicion}:tipo==='PH'?{tipo,P:'P'in s?s.P:blanco('Pa'),h:blanco('J/kg'),composicion}:tipo==='UV'?{tipo,U:'U'in s?s.U:blanco('J'),V:blanco('m3'),cantidades}:{tipo,U:'U'in s?s.U:blanco('J'),P:'P'in s?s.P:blanco('Pa'),cantidades};
}
export function solicitudEstadoHoja(h:HojaMotor,propietarioId:string,solicitudId:string):SolicitudEstado{
  const propietario=propietariosEstado(h).find(p=>p.id===propietarioId),estado=h.termodinamica?.estados[propietarioId];
  if(!propietario||!estado)throw new Error('Propietario o declaración de estado no disponible.');
  return {revision:1,solicitudId,propietarioId,componentes:structuredClone(propietario.componentes),declaracion:structuredClone(estado.declaracion)};
}
export function guardarDeclaracionEstado(h:HojaMotor,id:string,declaracion:DeclaracionEstado,uso:EstadoGuardado['uso']='consulta'):HojaMotor{
  if(!propietariosEstado(h).some(p=>p.id===id))throw new Error('El estado debe pertenecer a un volumen o corriente existente.');
  const originales=h.termodinamica?.estados[id]?.originalesDatosPuros;
  return {...h,termodinamica:{version:1,estados:{...h.termodinamica?.estados,[id]:{uso,declaracion:structuredClone(declaracion),...(originales?{originalesDatosPuros:structuredClone(originales)}:{})}}},...(uso==='cierre'||h.termodinamica?.estados[id]?.uso==='cierre'?{resultado:undefined,resultadoRef:undefined}:{})};
}
export function firmaSolicitudHoja(h:HojaMotor,id:string){const {solicitudId:_,...s}=solicitudEstadoHoja(h,id,'firma');void _;return firmaEstado(s);}
export function guardarEvaluacionEstado(h:HojaMotor,s:SolicitudEstado,respuesta:RespuestaEstado):HojaMotor{
  const {solicitudId:_,...entrada}=s;void _;
  if(firmaSolicitudHoja(h,s.propietarioId)!==firmaEstado(entrada))throw new Error('El estado o sus componentes cambiaron durante la evaluación.');
  validarRespuestaEstado(respuesta,s);
  return {...h,termodinamica:{version:1,estados:{...h.termodinamica?.estados,[s.propietarioId]:{...h.termodinamica!.estados[s.propietarioId],resultado:{firma:firmaEstado(entrada),respuesta}}}}};
}
export function evaluacionVigente(h:HojaMotor,id:string){try{const e=h.termodinamica?.estados[id];if(!e?.resultado||e.resultado.firma!==firmaSolicitudHoja(h,id))return null;return validarRespuestaEstado(e.resultado.respuesta,solicitudEstadoHoja(h,id,e.resultado.respuesta.solicitudId));}catch{return null;}}
/** Conserved quantities and manual solver data are never overwritten by an evaluated state. */
export function identificarComponenteEstado(h:HojaMotor,id:number,cas:string):HojaMotor{
  const antes=propietariosEstado(h).flatMap(p=>p.componentes).find(c=>c.id===id);if(!antes)throw new Error('Componente no disponible.');
  if((antes.identidadQuimica?.cas??'')===cas)return h;
  const actualizar=(c:Componente):Componente=>c.id===id?{...c,identidadQuimica:cas?{cas}:undefined,masaMolar:undefined}:c;
  if(h.ensamblaje)return {...h,ensamblaje:{...h.ensamblaje,version:2,componentes:catalogoComponentes(h.ensamblaje).map(actualizar)},resultado:undefined,resultadoRef:undefined};
  const f=h.historial.pasos[h.historial.activo].formulacion;
  return {...h,historial:recorridoMateria(h.historial,{tipo:'cambiar',titulo:`Identificar ${antes.nombre}${cas?` · CAS ${cas}`:''}`,cambios:{componentes:f.componentes?.map(actualizar)}}),resultado:undefined,resultadoRef:undefined};
}
export function bloqueosCierreTermodinamico(h:HojaMotor){
  const cierres=Object.entries(h.termodinamica?.estados??{}).filter(([,e])=>e.uso==='cierre');
  return [...Object.keys(h.cierresDinamicos??{}).map(id=>`${id}: el cierre dinámico requiere validar y resolver el ensamblaje en el backend. El solver manual no sustituye ese cierre.`),...cierres.map(([id,e])=>{try{const solicitud=solicitudEstadoHoja(h,id,'comprobar');const pendientes=analizarSolicitudEstado(solicitud);return `${id}: ${pendientes.length?'faltan datos del cierre termodinámico':'la evaluación estática no sustituye el cierre dinámico'}. El acoplamiento de ${e.declaracion.modelo.id||'propiedades reales'} requiere el ensamblaje del backend.`;}catch{return `${id}: el propietario del cierre ya no existe; revisa su declaración.`;}})];
}
