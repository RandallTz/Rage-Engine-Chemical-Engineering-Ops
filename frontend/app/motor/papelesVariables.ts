import type {CampoDato} from './modeloNumerico';
import type {HojaMotor} from './hojasMotor';
import {analizarHoja} from './modeloHojaMotor';
import {volumenesControl,campoGeometria,tipoVolumenControl} from './volumenControl';
import {contextoEnergiaHoja,formulacionEnergiaHoja} from './estadoEnergiaHoja';
import {balancesHoja} from './seleccionBalances';
import {tienePresionPrescrita} from './recorridoEnergia';
import {usaEnsamblajeTermodinamico,nombreDatoDinamico} from './datosEnsamblajeTermodinamico';
import {prepararEnsamblajeTermodinamico} from './prepararEnsamblajeTermodinamico';

export function papelCampo(c:CampoDato){
  if(c.funcion==='inicial')return 'Dato inicial';
  if(c.funcion==='geometria'||c.magnitud==='volumen'&&!c.variables.length)return 'Geometría';
  if(['energia_c','energia_u_ref','energia_T_ref','energia_rho','energia_T_min','energia_T_max'].includes(c.id))return 'Parámetro';
  if(c.magnitud==='caudal'||c.magnitud==='caudal_molar'||c.id.startsWith('energia_T_')||c.id==='energia_p')return 'Dato de frontera';
  return 'Dato';
}
export type VariableVinculada={id:string;simbolo:string;nombre:string;unidad:string;papel:'Por balance'|'Por relación'|'Por cierre'|'Dato'|'Pendiente'|'Sin modelo';relacion:string;enlace:string;campoId?:string};
export function variablesVolumen(h:HojaMotor,id:string):VariableVinculada[]{
  const v=volumenesControl(h).find(v=>v.id===id);if(!v||v.f.vista!=='cantidad'||v.f.cantidadVolumen)return [];
  const b=balancesHoja(h),esPrimero=id===contextoEnergiaHoja(h).volumenId,e=formulacionEnergiaHoja(h),base=`/motor/hojas/${h.id}/resolver`,r:VariableVinculada[]=[];
  if(b.materia)for(const c of v.f.componentes??[])r.push({id:`m_${id}_${c.id}`,simbolo:String.raw`m_{${c.simbolo}}(t)`,nombre:`Masa · ${c.nombre}`,unidad:'kg',papel:'Por balance',relacion:'Balance de materia',enlace:h.cierresDinamicos?.[id]?`${base}#ecuacion-materia.${c.id}`:`${base}#balance-materia-${id}-${c.id}`});
  if(h.cierresDinamicos?.[id]){
    const tipo=tipoVolumenControl(h,id),geo=campoGeometria(h,id);
    if(b.energia){
      if(tipo==='presion_dada')r.push({id:'H',simbolo:'H(t)',nombre:'Entalpía total',unidad:'J',papel:'Por balance',relacion:'Balance en H',enlace:`${base}#ecuacion-energia`});
      r.push({id:'U',simbolo:'U(t)',nombre:'Energía interna',unidad:'J',papel:tipo==='presion_dada'?'Por cierre':'Por balance',relacion:tipo==='presion_dada'?'U = H − PV':'Balance de energía',enlace:`${base}#ecuacion-${tipo==='presion_dada'?'estado.U':'energia'}`});
      r.push({id:'T',simbolo:'T(t)',nombre:'Temperatura',unidad:'K',papel:'Por cierre',relacion:'Cierre energético',enlace:`${base}#ecuacion-estado.u`});
      r.push({id:'P',simbolo:'P(t)',nombre:'Presión',unidad:'Pa',papel:tipo==='presion_dada'?'Dato':'Por cierre',relacion:tipo==='presion_dada'?'P = Pext(t)':'Relación de volumen',enlace:tipo==='presion_dada'?`${base}#dato-volumen.${id}.Pext`:`${base}#ecuacion-estado.v`});
    }
    r.push({id:'V',simbolo:tipo==='rigido'?String.raw`V_{\mathrm{geom}}`:'V(t)',nombre:tipo==='rigido'?'Volumen del dominio · fijo':'Volumen ocupado',unidad:'m3',papel:tipo==='rigido'?geo?'Dato':'Pendiente':'Por cierre',relacion:tipo==='rigido'?'Geometría declarada':'V = m vestado',enlace:base});
    return r;
  }
  if(b.energia&&esPrimero){r.push({id:'U',simbolo:'U(t)',nombre:'Energía interna',unidad:'J',papel:'Por balance',relacion:'Balance de energía',enlace:`${base}#balance-energia`});r.push({id:'T',simbolo:'T(t)',nombre:'Temperatura del volumen',unidad:'K',papel:e.modelo==='u_lineal'&&e.uniforme?'Por relación':'Pendiente',relacion:e.modelo==='u_lineal'&&e.uniforme?'U = m u(T)':'Relación energética sin declarar',enlace:`${base}#relacion-energia`});}
  const geo=campoGeometria(h,id),tipo=tipoVolumenControl(h,id);
  r.push({id:'V',simbolo:geo?String.raw`V_{\mathrm{geom}}`:'V(t)',nombre:tipo==='rigido'?'Volumen del dominio · fijo':'Volumen del dominio · móvil',unidad:'m3',papel:geo?'Dato':tipo!=='rigido'&&esPrimero&&b.energia&&e.densidadConstante?'Por relación':'Pendiente',relacion:geo?'V = Vgeom':tipo!=='rigido'&&esPrimero&&b.energia&&e.densidadConstante?'V = Vocup':'Relación de volumen sin declarar',enlace:geo?`${base}#dato-${geo.id}`:tipo!=='rigido'&&esPrimero&&b.energia&&e.densidadConstante?`${base}#relacion-volumen`:`/motor/hojas/${h.id}/estado#geometria`,...(geo?{campoId:geo.id}:{})});
  if(esPrimero&&b.energia&&e.densidadConstante)r.push({id:'V_ocupado',simbolo:String.raw`V_{\mathrm{ocup}}(t)`,nombre:'Volumen ocupado por el fluido',unidad:'m3',papel:'Por relación',relacion:'Vocup = m / ρ*',enlace:`${base}#relacion-volumen-ocupado`});
  const presionComoDato=tienePresionPrescrita(e,contextoEnergiaHoja(h));
  if(b.energia&&esPrimero)r.push({id:'P',simbolo:'P(t)',nombre:'Presión',unidad:'Pa',papel:presionComoDato?'Dato':'Sin modelo',relacion:presionComoDato?'P = Pext(t)':'No se obtiene de la relación manual u(T)',enlace:presionComoDato?`${base}#dato-energia_p`:`/motor/hojas/${h.id}/estado#presion`,...(presionComoDato?{campoId:'energia_p'}:{})});
  return r;
}
export function datosVolumen(h:HojaMotor,id:string){
  if(usaEnsamblajeTermodinamico(h)){
    const s=prepararEnsamblajeTermodinamico(h,'datos').solicitud;
    return s?Object.entries(s.datos).filter(([,d])=>d.origen.propietarioId===`volumen:${id}`).map(([key,d])=>({id:key,nombre:nombreDatoDinamico(s,key),simbolo:key,magnitud:d.magnitud,funcion:d.funcion==='inicial'?'inicial' as const:d.funcion==='geometria'?'geometria' as const:'dato' as const,variables:d.funcion==='frontera'?['t']:[],grupo:'Volumen',papel:d.funcion==='inicial'?'Dato inicial':d.funcion==='geometria'?'Geometría':'Dato de frontera'})):[];
  }
  const a=analizarHoja(h),primero=id===contextoEnergiaHoja(h).volumenId;
  return a.campos.filter(c=>h.ensamblaje?c.id.startsWith(`${id}__`)||primero&&c.id.startsWith('energia_'):true).map(c=>({...c,papel:papelCampo(c)}));
}
