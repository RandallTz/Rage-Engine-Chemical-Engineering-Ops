import {reconcileDerived} from '../models/derivedSelection';
import {migrarTermoHoja} from './recorridoTermodinamico';
import {reconcileMomentumTopology} from '../models/momentumDerivation';
import {reconcileModelTopology} from '../models/modelTopology';
import type {RecorridoEnergia} from './recorridoEnergia';
import type {TermodinamicaHoja} from './contratoTermodinamica';
import type {CierreDinamico} from './contratoEnsamblajeTermodinamico';
import type {SeleccionBalances} from './seleccionBalances';
import type {SupuestosFundamentales} from './familiasBalance';
import { iniciarRecorrido } from './recorridoMateria';
import type { RecorridoMateria } from './recorridoMateria';
import { iniciarConfiguracion } from './modeloNumerico';
import type { ConfiguracionMotor, ResultadoMotor } from './modeloNumerico';
import type {EnsamblajeMateria} from './ensamblajeMateria';
import {normalizarEnsamblaje} from './ensamblajeMateria';
export type GraficaMotor={id:string;nombre:string;tipo:'tiempo'|'perfil';x:string;y:string[];ancha:boolean;altura:number;instante:number};
export type HojaMotor={commonModel?:import('../../motores/modelo/contrato').ModeloComun;derivedSelection?:import('../models/derivedSelection').DerivedSelection;previousHydraulicNetwork?:import('../models/hydraulicDefinition').HydraulicNetwork;equationWorkbench?:import("../models/equationWorkbench").EquationWorkbench;hydraulicNetwork?:import('../models/hydraulicDefinition').HydraulicNetwork;archivedMomentumVolumes?:import('../models/momentumDerivation').MomentumJournal['volumes'];momentumDerivation?:import('../models/momentumDerivation').MomentumJournal;previousMomentumAssumptions?:SupuestosFundamentales;dynamicDefinition?:import('../models/dynamicDefinition').DynamicDefinition;removedAt?:string;workspaceNotes?:Partial<Record<'model'|'transform'|'solve'|'results',string>>;transformation?:import("../models/transformationSelection").TransformationSelection;vistaEquilibrio?:{volumenId:string;indice:number;ejeId:number;unidadT:'K'|'degC';unidadP:'Pa'|'kPa'|'bar'};version:1;id:string;nombre:string;actualizada:string;historial:RecorridoMateria;config:ConfiguracionMotor;resultado?:ResultadoMotor;resultadoRef?:{firma:string;estado:'resuelto'|'parcial';fecha:string};graficas:GraficaMotor[];tableroIniciado?:boolean;columnas:1|2;archivada?:boolean;ensamblaje?:EnsamblajeMateria;volumenActivo?:string;revisionMateriaExterna?:number;energia?:{historial:RecorridoEnergia;datos:Record<string,import('./modeloNumerico').DatoMotor>;inicial?:'T'|'U';atol?:number};balances?:SeleccionBalances;vistaBalance?:import('./familiasBalance').VistaHoja;recorridoTermodinamico?:import('./recorridoTermodinamico').RecorridoTermodinamico;supuestosBalances?:Partial<Record<'energia'|'momento',SupuestosFundamentales>>;termodinamica?:TermodinamicaHoja;cierresDinamicos?:Record<string,CierreDinamico>;redTermodinamica?:import('./redTermodinamica').RedTermodinamica;presionesExterioresInactivas?:Record<string,import('./modeloNumerico').DatoMotor>};
export const CLAVE_HOJAS='rage.motor.hojas.v1';
export function nuevaHoja(nombre:string,historial=iniciarRecorrido()):HojaMotor {return {version:1,id:crypto.randomUUID(),nombre:nombre.trim()||'Untitled model',actualizada:new Date().toISOString(),historial:structuredClone(historial),config:iniciarConfiguracion(),graficas:[],columnas:2};}
let textoCache:string|null=null,cache:HojaMotor[]=[];
export const hojasServidor:HojaMotor[]=[];
/** Una derivación de energía anterior que declaraba supuestos termodinámicos se separa, sin pérdida, en su
 * derivación termodinámica (recorridoTermodinamico.ts): cada ecuación en su lugar. */
export const normalizarHoja=(h:HojaMotor):HojaMotor=>h.commonModel||h.redTermodinamica?h:migrarTermoHoja(h.ensamblaje?{...h,...normalizarEnsamblaje(h.ensamblaje,h.config)}:h);
export function leerHojas():HojaMotor[] {
  if(typeof window==='undefined')return hojasServidor;
  const raw=localStorage.getItem(CLAVE_HOJAS);if(raw===textoCache)return cache;
  if(!raw){textoCache=raw;cache=[];return cache;}
  const data:unknown=JSON.parse(raw);
  if(!Array.isArray(data)||data.some(d=>!d||d.version!==1||typeof d.id!=='string'||typeof d.nombre!=='string'||!Array.isArray(d.historial?.pasos)||!d.historial.pasos.length||!d.config||!Array.isArray(d.graficas)))throw new Error('El archivo de hojas guardadas no tiene un formato válido.');
  if(data.some(d=>d.ensamblaje&&(![1,2].includes(d.ensamblaje.version)||!Array.isArray(d.ensamblaje.volumenes)||!d.ensamblaje.volumenes.length||!Array.isArray(d.ensamblaje.corrientes)||d.ensamblaje.volumenes.some((v:{id?:unknown;nombre?:unknown;historial?:{pasos?:unknown[];activo?:number}})=>typeof v.id!=='string'||typeof v.nombre!=='string'||!Array.isArray(v.historial?.pasos)||!Number.isInteger(v.historial?.activo)||(v.historial?.activo??-1)<0||(v.historial?.activo??-1)>=(v.historial?.pasos?.length??0)))))throw new Error('El ensamblaje guardado no tiene un formato válido. Los datos se conservan.');
  cache=(data as HojaMotor[]).map(normalizarHoja);textoCache=raw;return cache;
}
export function guardarHoja(hoja:HojaMotor) {
  const existentes=leerHojas(),otras=existentes.filter(h=>h.id!==hoja.id);
  const previous=existentes.find(h=>h.id===hoja.id);
  const actualizada={...reconcileDerived(previous,reconcileModelTopology(previous??hoja,reconcileMomentumTopology(previous,normalizarHoja(hoja)))),actualizada:new Date().toISOString()};
  localStorage.setItem(CLAVE_HOJAS,JSON.stringify([actualizada,...otras]));window.dispatchEvent(new Event('motor-hojas'));return actualizada;
}
/** Atomic addition; existing documents, including archived ones, are preserved. */
export function guardarHojasNuevas(nuevas:HojaMotor[]){
  const existentes=leerHojas(),ids=new Set(existentes.map(h=>h.id)),agregadas=nuevas.filter(h=>{if(ids.has(h.id))return false;ids.add(h.id);return true;});
  if(agregadas.length){localStorage.setItem(CLAVE_HOJAS,JSON.stringify([...agregadas.map(normalizarHoja),...existentes]));window.dispatchEvent(new Event('motor-hojas'));}
  return agregadas.length;
}
export function escucharHojas(callback:()=>void){const listener=()=>callback();window.addEventListener('storage',listener);window.addEventListener('motor-hojas',listener);return()=>{window.removeEventListener('storage',listener);window.removeEventListener('motor-hojas',listener);};}
export function duplicarHoja(h:HojaMotor){return {...structuredClone(h),id:crypto.randomUUID(),nombre:`${h.nombre} · copy`,actualizada:new Date().toISOString(),archivada:false,derivedSelection:undefined,resultado:undefined,resultadoRef:undefined};}
export function moverGrafica(g:GraficaMotor[],id:string,destino:string){const origen=g.findIndex(x=>x.id===id),fin=g.findIndex(x=>x.id===destino);if(origen<0||fin<0||origen===fin)return g;const copia=[...g],item=copia.splice(origen,1)[0];copia.splice(fin,0,item);return copia;}

/** Recoverable removal from the product library; scientific data/results stay intact. */
export function removeAllModels(){
  const models=leerHojas(),removedAt=new Date().toISOString(),count=models.filter(model=>!model.removedAt).length;
  if(count){localStorage.setItem(CLAVE_HOJAS,JSON.stringify(models.map(model=>model.removedAt?model:{...model,removedAt})));window.dispatchEvent(new Event('motor-hojas'));}
  return count;
}
export function restoreRemovedModels(){
  const models=leerHojas(),count=models.filter(model=>model.removedAt).length;
  if(count){localStorage.setItem(CLAVE_HOJAS,JSON.stringify(models.map(model=>{const restored={...model};delete restored.removedAt;return restored;})));window.dispatchEvent(new Event('motor-hojas'));}
  return count;
}
