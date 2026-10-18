import type {HojaMotor} from './hojasMotor';
import type {CampoDato,DatoMotor} from './modeloNumerico';
import {camposMotor} from './modeloNumerico';
import {formulacionVolumen,claveVolumen} from './ensamblajeMateria';
import {recorridoMateria} from './recorridoMateria';
import {contextoEnergiaHoja,historialEnergiaHoja,formulacionEnergiaHoja} from './estadoEnergiaHoja';
import {operarEnergia,tienePresionPrescrita} from './recorridoEnergia';

export type TipoVolumenControl='rigido'|'movil'|'presion_dada';
export const OPCIONES_VOLUMEN=[{id:'rigido' as const,nombre:'Volumen fijo',detalle:'La frontera no se mueve'},{id:'movil' as const,nombre:'Frontera móvil',detalle:'El volumen puede cambiar'},{id:'presion_dada' as const,nombre:'Presión exterior dada',detalle:'Frontera móvil · presión uniforme'}];
export const volumenesControl=(h:HojaMotor)=>h.ensamblaje?h.ensamblaje.volumenes.map(v=>({id:v.id,nombre:v.nombre,f:formulacionVolumen(h.ensamblaje!,v)})):[{id:'dominio',nombre:'Volumen de control',f:h.historial.pasos[h.historial.activo].formulacion}];
/** The current formulation is authoritative. There is no second persisted geometry flag. */
export function tipoVolumenControl(h:HojaMotor,id:string):TipoVolumenControl{
  const v=volumenesControl(h).find(v=>v.id===id);if(!v)throw new Error('Volumen no disponible.');
  return v.f.fija?'rigido':id===contextoEnergiaHoja(h).volumenId&&tienePresionPrescrita(formulacionEnergiaHoja(h),contextoEnergiaHoja(h))?'presion_dada':'movil';
}
export function claveGeometria(h:HojaMotor,id:string){
  const existente=h.ensamblaje?claveVolumen(id,'volumen'):'volumen';
  const v=volumenesControl(h).find(v=>v.id===id);
  if(h.config.datos[existente]||h.ensamblaje?.volumenes.find(v=>v.id===id)?.volumenDeclarado||v&&camposMotor(v.f,h.config).campos.some(c=>c.id==='volumen'))return existente;
  return h.ensamblaje?claveVolumen(id,'geometria_V'):'geometria_V';
}
export function campoGeometria(h:HojaMotor,id=contextoEnergiaHoja(h).volumenId):CampoDato|null{
  const v=volumenesControl(h).find(v=>v.id===id);if(!v?.f.fija)return null;
  const clave=claveGeometria(h,id);if(!h.config.datos[clave])return null;
  return {id:clave,nombre:'Volumen geométrico fijo',simbolo:String.raw`V_{\mathrm{geom}}`,magnitud:'volumen',funcion:'geometria',variables:[],grupo:'Volumen de control · geometría'};
}
export function elegirVolumenControl(h:HojaMotor,id:string,tipo:TipoVolumenControl):HojaMotor{
  const v=volumenesControl(h).find(v=>v.id===id);if(!v)throw new Error('Volumen no disponible.');
  if(tipo==='presion_dada'&&id!==contextoEnergiaHoja(h).volumenId)throw new Error('La condición energética de presión se define actualmente para el primer volumen.');
  const titulo=OPCIONES_VOLUMEN.find(o=>o.id===tipo)!.nombre;
  const historial=recorridoMateria(h.ensamblaje?h.ensamblaje.volumenes.find(v=>v.id===id)!.historial:h.historial,{tipo:'cambiar',titulo:`Definir volumen de control: ${titulo}`,cambios:{fija:tipo==='rigido'}});
  let nuevo:HojaMotor=h.ensamblaje?{...h,ensamblaje:{...h.ensamblaje,volumenes:h.ensamblaje.volumenes.map(v=>v.id===id?{...v,historial}:v)}}:{...h,historial};
  if(tipo==='rigido'){const clave=claveGeometria(h,id);nuevo={...nuevo,config:{...nuevo.config,datos:{...nuevo.config.datos,[clave]:nuevo.config.datos[clave]??{texto:'',unidad:'m3'}}}};}
  if(id===contextoEnergiaHoja(h).volumenId){
    const e=formulacionEnergiaHoja(h);
    const r=operarEnergia(historialEnergiaHoja(h),`Definir volumen de control: ${titulo}`,{presionPrescrita:tipo==='rigido'?tienePresionPrescrita(e,contextoEnergiaHoja(h)):tipo==='presion_dada',presionUniforme:tipo==='presion_dada'?true:e.presionUniforme},tipo==='rigido'?[String.raw`V=V_{\mathrm{geom}},\quad dV/dt=0,\quad\dot W_b=0`]:tipo==='presion_dada'?[String.raw`P=P_{\mathrm{ext}}(t),\quad\dot W_b=P_{\mathrm{ext}}\,dV/dt`]:[String.raw`\dot W_b=\oint_{\partial V}p\mathbf v_b\cdot\mathbf n\,dA`],contextoEnergiaHoja(nuevo));
    nuevo={...nuevo,energia:{...h.energia,historial:r,datos:h.energia?.datos??{}}};
  }
  return {...nuevo,revisionMateriaExterna:(h.revisionMateriaExterna??0)+1,resultado:undefined,resultadoRef:undefined};
}
export function guardarGeometria(h:HojaMotor,id:string,dato:DatoMotor):HojaMotor{
  if(tipoVolumenControl(h,id)!=='rigido')throw new Error('El volumen geométrico constante corresponde a una frontera fija.');
  const clave=claveGeometria(h,id);return {...h,config:{...h.config,datos:{...h.config.datos,[clave]:dato}},resultado:undefined,resultadoRef:undefined};
}
/** A declared fixed geometry is a model relation, not a thermodynamic property. */
export function relacionesGeometria(h:HojaMotor):string[]{
  return campoGeometria(h)?[String.raw`V=V_{\mathrm{geom}},\quad\frac{dV}{dt}=0`]:[];
}
export function ecuacionesVolumenControl(h:HojaMotor,id:string){
  const tipo=tipoVolumenControl(h,id),e=formulacionEnergiaHoja(h);
  return [{id:'geometria',titulo:'Geometría',latex:tipo==='rigido'?String.raw`V=V_{\mathrm{geom}},\quad\frac{dV}{dt}=0`:String.raw`V=V(t)`},
    {id:'trabajo-frontera',titulo:'Trabajo de frontera',latex:tipo==='rigido'?String.raw`\dot W_b=0`:tipo==='presion_dada'?String.raw`\dot W_b=P_{\mathrm{ext}}(t)\frac{dV}{dt}`:e.presionUniforme?String.raw`\dot W_b=P(t)\frac{dV}{dt}`:String.raw`\dot W_b=\oint_{\partial V}p\mathbf v_b\cdot\mathbf n\,dA`},
    ...(id===contextoEnergiaHoja(h).volumenId&&tienePresionPrescrita(e,contextoEnergiaHoja(h))?[{id:'presion',titulo:'Presión impuesta',latex:String.raw`P=P_{\mathrm{ext}}(t)`}]:[]),
    ...(id===contextoEnergiaHoja(h).volumenId&&e.densidadConstante?[{id:'relacion-volumen',titulo:'Volumen ocupado · densidad constante',latex:String.raw`V_{\mathrm{ocup}}=\frac{m}{\rho_*},\quad V=V_{\mathrm{ocup}}`},...(tipo==='rigido'?[{id:'compatibilidad-volumen',titulo:'Compatibilidad · dominio fijo y densidad constante',latex:String.raw`\frac{dm}{dt}=0`}]:[])]:[])];
}
