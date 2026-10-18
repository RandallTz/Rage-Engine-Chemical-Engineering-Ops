import type {HojaMotor} from './hojasMotor';
import type {ResultadoMotor} from './modeloNumerico';
import type {DatosGraficaMotor} from './datosGraficasMotor';
import {compilarEnsamblaje,planEnsamblaje,unidadCampo} from './ensamblajeMateria';
export function datosGraficasEnsamblaje(h:HojaMotor,r:ResultadoMotor):DatosGraficaMotor{
  const e=h.ensamblaje!,p=planEnsamblaje(e,h.config),s=compilarEnsamblaje(e,h.config),variables:DatosGraficaMotor['variables']=[{id:'t',nombre:'Tiempo',unidad:'s',grupo:'Dominio'}];
  for(const z of r.estadosAcoplados!)variables.push({id:`m_${z.id}`,nombre:`${z.volumenNombre} · ${z.componenteNombre}`,unidad:'kg',grupo:z.volumenNombre});
  for(const v of e.volumenes){variables.push({id:`m_total_${v.id}`,nombre:`Masa total · ${v.nombre}`,unidad:'kg',grupo:v.nombre});if(p.volumenesConDato.includes(v.id)){variables.push({id:`V_${v.id}`,nombre:`Volumen · ${v.nombre}`,unidad:'m3',grupo:v.nombre});for(const cs of p.especies)variables.push({id:`rho_${cs.simbolo}_${v.id}`,nombre:`Concentración másica · ${v.nombre} · ${cs.nombre}`,unidad:'kg/m3',grupo:v.nombre});}}
  for(const corriente of e.corrientes)if(corriente.datos?.materia.base==='molar'||corriente.datos?.materia.modo==='total_y_composicion')for(const cs of p.especies)variables.push({id:`mdot_s${corriente.id}_c${cs.id}`,nombre:`Caudal másico · S${corriente.id} · ${cs.nombre}`,unidad:'kg/s',grupo:`S${corriente.id} · ${corriente.nombre}`});
  for(const cs of p.especies)variables.push({id:`m_global_${cs.id}`,nombre:`Total del ensamblaje · ${cs.nombre}`,unidad:'kg',grupo:'Global'});
  for(const d of p.analisis.campos)if(d.funcion!=='inicial')variables.push({id:`dato_${d.id}`,nombre:`${d.grupo} · ${d.nombre}`,unidad:unidadCampo(d),grupo:d.grupo});
  const filas=r.tiempos.map((t,k)=>{const y=r.valores[k].map(q=>q[0]),valores=s.valoresDatos!(t,y),fila:Record<string,number>={t,...valores};
    for(const [i,z] of r.estadosAcoplados!.entries())fila[`m_${z.id}`]=y[i];
    for(const cs of p.especies)fila[`m_global_${cs.id}`]=r.estadosAcoplados!.reduce((sum,z,i)=>sum+(z.componenteId===cs.id?y[i]:0),0);
    for(const d of p.analisis.campos)if(d.funcion!=='inicial')fila[`dato_${d.id}`]=valores[d.id];return fila;});
  return {variables,filas};
}
