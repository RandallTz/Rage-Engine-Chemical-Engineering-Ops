import type {RespuestaValidacionDinamica,SolicitudEnsamblajeDinamico,CorrienteDinamica} from './contratoEnsamblajeTermodinamico';
import {analizarExpresion} from './expresionesMotor';
import {UNIDADES_MOTOR} from './unidadesMotor';

/** Only a presentation stage; completeness and solvability still come from the
 * backend. An empty flow must not prompt for an exterior donor prematurely. */
export function caudalIntroducido(c:CorrienteDinamica,s:SolicitudEnsamblajeDinamico){
  const ids=c.materia.modo==='por_componente'?Object.values(c.materia.caudalIds):[c.materia.caudalId];
  return ids.every(id=>{const d=s.datos[id];try{analizarExpresion(d.declaracion.texto,['t']);return Object.hasOwn(UNIDADES_MOTOR[d.magnitud],d.declaracion.unidad);}catch{return false;}});
}

export const anclaEcuacionDinamica=(id:string)=>`ecuacion-${id}`;
export function nombreEcuacionDinamica(id:string){
  const nombres:Record<string,string>={energia:'Balance de energía','estado.u':'Cierre energético','estado.h':'Cierre en entalpía','estado.v':'Volumen específico','estado.reparto':'Reparto de fases','estado.U':'Reconstrucción de U','mecanica.trabajo':'Trabajo de frontera','estado.flujo':'Trabajo de flujo'};
  return nombres[id]??(id.startsWith('materia.')?'Balance de materia':id.startsWith('estado.donante.')?`Donante · corriente ${id.split('.').at(-1)}`:id.startsWith('mecanica.continuidad.')?`Continuidad de presión · corriente ${id.split('.').at(-1)}`:id);
}
export function nombreVariableDinamica(id:string,s:SolicitudEnsamblajeDinamico){
  const nombres:Record<string,string>={m:'Masa',U:'Energía interna',H:'Entalpía total',T:'Temperatura',P:'Presión',V:'Volumen',W:'Trabajo de frontera acumulado',q:'Fracción másica de vapor',h:'Entalpía transportada'};
  if(id.startsWith('volumen.')&&id.includes('.m.'))return `Masa · ${s.componentes.find(c=>id.endsWith(`.${c.id}`))?.nombre??'componente'}`;
  const nombre=nombres[id.split('.').at(-1)!]??id;
  return id.startsWith('corriente.')?`${nombre} · corriente ${id.split('.')[1]}`:nombre;
}
/** Incidence is provided by the backend. It is not a solved-for map and does
 * not assert that one algebraic variable is determined by a single equation. */
export const ecuacionesDeVariable=(r:RespuestaValidacionDinamica,id:string)=>r.ecuaciones.filter(e=>e.variableIds.includes(id));
