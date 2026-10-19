import {cambiarTermoHoja} from './recorridoTermodinamico';
import type {HojaMotor} from './hojasMotor';
import type {DatoMotor} from './modeloNumerico';
import type {SolicitudEnsamblajeDinamico} from './contratoEnsamblajeTermodinamico';
import {prepararEnsamblajeTermodinamico,declararCierreDinamico} from './prepararEnsamblajeTermodinamico';
import {historialEnergiaHoja,contextoEnergiaHoja,formulacionEnergiaHoja,actualizarContextoDinamico} from './estadoEnergiaHoja';
import {analizarExpresion,dependeDe} from './expresionesMotor';
import {actualizarPuertos} from './ensamblajeMateria';
import {operarEnergia} from './recorridoEnergia';
import {recorridoMateria} from './recorridoMateria';
import type {FormulacionMateria} from './recorridoMateria';
import type {PoliticaEstado as Politica} from './contratoTermodinamica';

export const usaEnsamblajeTermodinamico=(h:HojaMotor)=>Object.keys(h.cierresDinamicos??{}).length>0;
/** Exclusive active pressure choice. The inactive user datum stays in the worksheet,
 * outside the request and calculation identity; restoring it never uses a result. */
export function elegirPresionCorriente(h:HojaMotor,corrienteId:number,modo:'dato'|'continuidad'):HojaMotor{
  const s=prepararEnsamblajeTermodinamico(h,'presion').solicitud,c=s?.corrientes.find(c=>c.id===corrienteId);
  if(!s||!c?.estadoExterior)throw new Error('La corriente actual no necesita estado exterior.');
  const nuevo=structuredClone(h),cierre=nuevo.cierresDinamicos![s.volumen.id],guardadas={...nuevo.presionesExterioresInactivas};
  const corriente=nuevo.ensamblaje?.corrientes.find(c=>c.id===corrienteId),clave=`corriente_${corrienteId}_P`;
  const P=corriente?.datos?.P??(!nuevo.ensamblaje?nuevo.config.datos[clave]:undefined);
  const presiones={...cierre.presionesCorrientes};
  if(modo==='continuidad'){
    if(P)guardadas[corrienteId]=structuredClone(P);
    if(corriente?.datos)delete corriente.datos.P;else if(!nuevo.ensamblaje)delete nuevo.config.datos[clave];
    presiones[corrienteId]='continuidad';
  }else{
    delete presiones[corrienteId];
    const anterior=guardadas[corrienteId];
    if(!P&&anterior){if(corriente?.datos)corriente.datos.P=anterior;else if(!nuevo.ensamblaje)nuevo.config.datos[clave]=anterior;}
    delete guardadas[corrienteId];
  }
  return {...nuevo,presionesExterioresInactivas:guardadas,cierresDinamicos:{...nuevo.cierresDinamicos,[s.volumen.id]:{...cierre,presionesCorrientes:presiones}},resultado:undefined,resultadoRef:undefined};
}
function cambiarMateria(h:HojaMotor,titulo:string,cambios:Partial<FormulacionMateria>):HojaMotor{
  const recorrido=h.ensamblaje?h.ensamblaje.volumenes[0].historial:h.historial,historial=recorridoMateria(recorrido,{tipo:'cambiar',titulo,cambios});
  return h.ensamblaje?{...h,ensamblaje:{...h.ensamblaje,volumenes:h.ensamblaje.volumenes.map((v,i)=>i===0?{...v,historial}:v)}}:{...h,historial};
}
/** The UI explicitly reviews replacement of manual closures. Numeric declarations are retained.
 * No geometry, identity, initial state or unsupported physical hypothesis is invented. */
export function elegirCierreReal(h:HojaMotor,modelo:{id:string;version:string}):HojaMotor{
  const id=contextoEnergiaHoja(h).volumenId,f=h.ensamblaje?h.ensamblaje.volumenes[0].historial.pasos[h.ensamblaje.volumenes[0].historial.activo].formulacion:h.historial.pasos[h.historial.activo].formulacion;
  let nuevo=cambiarMateria(h,'Sustituir cierre manual por propiedades reales',{densidadMediaConstante:false,densidadComunPuertos:false,...(f.reglasEstado?.densidades?{reglasEstado:{...f.reglasEstado,densidades:f.reglasEstado.densidades.map(r=>({...r,constanciaTemporal:'sin_restriccion' as const}))}}:{})});
  // Supuestos termodinámicos: en la derivación termodinámica, no en la de energía.
  nuevo=cambiarTermoHoja(nuevo,'Sustituir u(T) lineal y densidad constante por el cierre real',{modelo:'sin_declarar',densidadConstante:false},[String.raw`U=m\,u_{\mathrm{eq}},\quad V=m\,v_{\mathrm{eq}}`]);
  const e=formulacionEnergiaHoja(nuevo),politica:Politica={cantidad:e.monofasico?'monofasico':'sin_restriccion',cambioInterno:e.sinCambioFase?'prohibido':'permitido',evaluacion:'equilibrio_estable'};
  return aplicarPoliticaDinamica(declararCierreDinamico(nuevo,id,{modelo,politica}),politica);
}
export function aplicarPoliticaDinamica(h:HojaMotor,politica:Politica):HojaMotor{
  const id=contextoEnergiaHoja(h).volumenId,cierre=h.cierresDinamicos?.[id];if(!cierre)throw new Error('Cierre dinámico sin seleccionar.');
  const f=h.ensamblaje?h.ensamblaje.volumenes[0].historial.pasos[h.ensamblaje.volumenes[0].historial.activo].formulacion:h.historial.pasos[h.historial.activo].formulacion;
  let nuevo=cambiarMateria(h,'Declarar política de fases compartida',{reglasEstado:{...f.reglasEstado,fases:{cantidad:politica.cantidad,cambioInterno:politica.cambioInterno==='prohibido'?'sin_cambio_de_fase':'sin_restriccion',evaluacion:'termodinamica'}}});
  nuevo=cambiarTermoHoja(nuevo,'Declarar política de fases compartida',{monofasico:politica.cantidad==='monofasico',sinCambioFase:politica.cambioInterno==='prohibido'});
  return declararCierreDinamico(nuevo,id,{...cierre,politica});
}
/** Return to a manual relation explicitly; keep declared parameters and phase hypotheses. */
export function elegirCierreManual(h:HojaMotor):HojaMotor{
  const id=contextoEnergiaHoja(h).volumenId,nuevo=declararCierreDinamico(h,id,null);
  return cambiarTermoHoja(nuevo,'Elegir relación manual u(T)',{modelo:'u_lineal'});
}
export function editarDatoDinamico(h:HojaMotor,datoId:string,dato:DatoMotor):HojaMotor{
  const s=prepararEnsamblajeTermodinamico(h,'editar').solicitud,origen=s?.datos[datoId]?.origen;if(!origen)throw new Error('El dato ya no pertenece al ensamblaje actual.');
  const path=origen.ruta.split('/').slice(1).map(s=>s.replaceAll('~1','/').replaceAll('~0','~'));
  if(path.some(s=>['__proto__','constructor','prototype'].includes(s))||!['config','energia','ensamblaje'].includes(path[0]))throw new Error('Ruta de dato no admitida.');
  let nuevo=structuredClone(h);if(path[0]==='energia'&&!nuevo.energia)nuevo.energia={historial:historialEnergiaHoja(h),datos:{}};
  let target:Record<string,unknown>=nuevo as unknown as Record<string,unknown>;
  for(const key of path.slice(0,-1)){if(target[key]===undefined)target[key]={};if(!target[key]||typeof target[key]!=='object')throw new Error('Ruta de dato inválida.');target=target[key] as Record<string,unknown>;}
  target[path.at(-1)!]=structuredClone(dato);
  // An explicitly entered F(t) retracts an earlier constant-flow assumption.
  // Do not infer constancy in the opposite direction or from incomplete typing.
  const entrada=s!.datos[datoId];let temporal=false;
  if(origen.propietarioId.startsWith('corriente:')&&['caudal','caudal_molar'].includes(entrada.magnitud))try{temporal=dependeDe(analizarExpresion(dato.texto,['t']),'t');}catch{}
  if(temporal){
    const id=Number(origen.propietarioId.split(':')[1]);
    if(nuevo.ensamblaje){if(nuevo.ensamblaje.corrientes.some(c=>c.id===id&&c.constante!==false))nuevo={...nuevo,ensamblaje:actualizarPuertos({...nuevo.ensamblaje,corrientes:nuevo.ensamblaje.corrientes.map(c=>c.id===id?{...c,constante:false}:c)})};}
    else{const f=nuevo.historial.pasos[nuevo.historial.activo].formulacion;if(f.fronteras.some(p=>p.id===id&&p.constante!==false))nuevo={...nuevo,historial:recorridoMateria(nuevo.historial,{tipo:'cambiar',titulo:`Declarar caudal temporal en corriente ${id}`,cambios:{fronteras:f.fronteras.map(p=>p.id===id?{...p,constante:false}:p)}})};}
    nuevo=actualizarContextoDinamico(nuevo);
  }
  return {...nuevo,resultado:undefined,resultadoRef:undefined};
}
export function nombreDatoDinamico(s:SolicitudEnsamblajeDinamico,id:string){
  const d=s.datos[id],component=s.componentes.find(c=>id.endsWith(`.${c.id}`));
  const nombres:Record<string,string>={T0:'Temperatura inicial',U0:'Energía interna inicial',V:'Volumen geométrico',Pext:'Presión exterior',Q:'Calor hacia el volumen',Text:'Temperatura exterior',tfinal:'Tiempo final'};
  return id.startsWith('volumen.')&&id.endsWith('.Pext')?'Presión impuesta al volumen':id.includes('.m0.')?`Masa inicial · ${component?.nombre??'componente'}`:id.includes('.F')?`Caudal${component?` · ${component.nombre}`:''}`:nombres[id.split('.').at(-1)!]??(d.funcion==='inicial'?'Condición inicial':id);
}
export function grupoDatoDinamico(s:SolicitudEnsamblajeDinamico,id:string){const d=s.datos[id];return d.origen.propietarioId.startsWith('corriente:')?`Corriente ${d.origen.propietarioId.split(':')[1]}`:d.funcion==='inicial'?'Condiciones iniciales':d.funcion==='geometria'?'Geometría':d.funcion==='estudio'?'Estudio':'Energía y frontera';}
