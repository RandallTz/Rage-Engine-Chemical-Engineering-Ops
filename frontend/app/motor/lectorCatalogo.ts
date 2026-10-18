import type {CatalogoMotor,PropiedadPura} from './contratoCatalogo';
import {textoPublicado,textosPublicados,identificadoresPublicados} from './alcancePublicado';
import {claveModelo} from './modelosTermodinamicos';
const fallo=(m:string):never=>{throw new Error(`Catálogo del motor incompatible: ${m}.`);};
const fin=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const intervalo=(v:unknown)=>Array.isArray(v)&&v.length===2&&v.every(x=>fin(x)&&x>0)&&v[0]<v[1];
const huella=(v:unknown)=>typeof v==='string'&&/^sha256:[a-f0-9]{64}$/.test(v);
const requerido=(v:unknown)=>typeof v==='string'&&(['registro','masa_molar','presion_vapor','cp_gas_ideal','volumen_liquido','parametros_nrtl_lle','formulacion_iapws95'].includes(v)||/^asignacion_grupos_\S+$/.test(v));
function propiedad(p:PropiedadPura){
  if(!p||!textoPublicado(p.fuente))fallo('propiedad sin fuente');
  if(p.id==='volumen_liquido'){
    if(p.unidad!=='m3/mol'||!fin(p.valor)||p.valor<=0||!textoPublicado(p.condicion))fallo('volumen líquido');
    return;
  }
  if(!['presion_vapor','cp_gas_ideal'].includes(p.id)||!textoPublicado(p.forma)||!intervalo(p.dominio?.T)||!p.coeficientes)fallo('correlación pura');
  const c=p.coeficientes as Record<string,unknown>,ks=p.id==='presion_vapor'?['A','B','C','D','Tc','Pc']:['a0','a1','a2','a3','a4'];
  if(ks.some(k=>!fin(c[k]))||p.id==='presion_vapor'&&(p.unidad!=='Pa'||Number(c.Tc)<=0||Number(c.Pc)<=0)||p.id==='cp_gas_ideal'&&p.unidad!=='J/(mol K)')fallo('coeficientes o unidad');
}
/** Reads the published data and admission rule. It does not evaluate a correlation,
 * infer missing parameters, or certify an equilibrium from catalog membership. */
export function leerCatalogoMotor(raw:unknown):CatalogoMotor{
  const c=raw as CatalogoMotor;
  if(!c||c.revision!==1||!Array.isArray(c.sustancias)||!Array.isArray(c.paquetes)||!textoPublicado(c.regla)||!Array.isArray(c.noDisponible))fallo('estructura');
  if(!identificadoresPublicados(c.sustancias.map(s=>s?.cas))||!identificadoresPublicados(c.sustancias.map(s=>s?.id)))fallo('identidad repetida o vacía');
  for(const s of c.sustancias){
    if(s.id!==s.cas||!textoPublicado(s.nombre)||!s.masaMolar||!fin(s.masaMolar.valor)||s.masaMolar.valor<=0||s.masaMolar.unidad!=='kg/mol'||!textoPublicado(s.masaMolar.fuente))fallo('identidad o masa molar');
    const d=s.datosPuros;
    if(!d||!['completos','incompletos'].includes(d.estado)||!Array.isArray(d.faltantes)||d.faltantes.some(f=>!requerido(f.dato)||!textoPublicado(f.motivo))||new Set(d.faltantes.map(f=>f.dato)).size!==d.faltantes.length)fallo('cobertura de datos puros');
    if((d.estado==='completos')!==(d.faltantes.length===0))fallo('estado de datos puros contradictorio');
    if(d.propiedades!==undefined){
      if(!Array.isArray(d.propiedades)||!identificadoresPublicados(d.propiedades.map(p=>p?.id)))fallo('propiedades repetidas');
      d.propiedades.forEach(propiedad);
    }
    if(d.dominioLiquido!==undefined&&(!intervalo(d.dominioLiquido?.T)||!textoPublicado(d.dominioLiquido.motivo))||d.huella!==undefined&&!huella(d.huella))fallo('dominio o huella de datos puros');
    if(d.estado==='completos'&&(!d.huella||!d.dominioLiquido||!d.propiedades||!['presion_vapor','cp_gas_ideal','volumen_liquido'].every(id=>d.propiedades!.some(p=>p.id===id))))fallo('datos puros completos sin contenido');
  }
  if(new Set(c.paquetes.map(p=>claveModelo(p.modelo))).size!==c.paquetes.length)fallo('paquete y versión repetidos');
  for(const p of c.paquetes){
    if(!textoPublicado(p.modelo?.id)||!textoPublicado(p.modelo.version)||!textoPublicado(p.nombre)||!p.requisitos||!identificadoresPublicados(p.requisitos.porEspecie)||p.requisitos.porEspecie.some(x=>!requerido(x))||!textosPublicados(p.requisitos.porPar)||!textosPublicados(p.requisitos.porGrupo))fallo('requisitos de paquete');
    const o=p.operaciones;
    if(!o||!identificadoresPublicados(o.estado?.especificaciones)||o.estado.especificaciones.some(x=>!['TP','PH','UP','UV'].includes(x))||typeof o.ensamblaje?.disponible!=='boolean'||o.ensamblaje.coberturaGrupos!==undefined&&o.ensamblaje.coberturaGrupos!==true||typeof o.diagramas?.disponible!=='boolean'||!identificadoresPublicados(o.diagramas.operaciones)||o.diagramas.operaciones.some(x=>!['Txy','Pxy'].includes(x))||!o.diagramas.disponible&&o.diagramas.operaciones.length>0)fallo('operaciones de paquete');
    if(!Array.isArray(p.especies)||p.especies.length!==c.sustancias.length||p.especies.some((e,i)=>e.cas!==c.sustancias[i].cas))fallo('cobertura de especies');
    for(const e of p.especies){
      if(typeof e.admitida!=='boolean'||!Array.isArray(e.faltantes)||e.admitida!==(e.faltantes.length===0)||e.faltantes.some(f=>!requerido(f.dato)||!['COMPONENTE_NO_SOPORTADO','DATO_PURO_AUSENTE','PARAMETRO_AUSENTE','UNIFAC_ASIGNACION_AUSENTE','UNIFAC_GRUPO_DESCONOCIDO'].includes(f.codigo)||!textoPublicado(f.mensaje)))fallo('admisión sin diagnóstico coherente');
    }
  }
  if(c.noDisponible.some(x=>!textoPublicado(x.elemento)||!textoPublicado(x.motivo)))fallo('límites sin motivo');
  return c;
}
