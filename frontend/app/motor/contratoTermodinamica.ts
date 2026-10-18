import type {Componente} from './materiaEstado';
import {masaMolarKg} from './materiaEstado';
import {textoPublicado,identificadoresPublicados,dominioPublicado} from './alcancePublicado';
import type {SustitucionDatosPuros,PropiedadPura} from './contratoCatalogo';
import {temperaturaEnRangosSustituidos} from './sustitucionesDatosPuros';

/** Protocol for the independent /motor. No flash algorithm or phase assignment in the client. */
export const REVISION_ESTADO=1;
/** null preserves an unfilled datum in saved sheets; it never means zero. */
export type CantidadEstado={valor:number|null;unidad:string};
export type FaseEstado='liquido'|'vapor'|'solido'|'fluido';
export type PoliticaEstado={cantidad:'sin_restriccion'|'monofasico';tiposPermitidos?:FaseEstado[];cambioInterno:'permitido'|'prohibido';evaluacion:'equilibrio_estable'};
export type ComposicionEstado={base:'masica'|'molar';fracciones:Record<string,number|null>};
export type CantidadesEstado={base:'masica'|'molar';valores:Record<string,CantidadEstado>};
export type EspecificacionEstado=
  |{tipo:'TP';T:CantidadEstado;P:CantidadEstado;composicion:ComposicionEstado}
  |{tipo:'PH';P:CantidadEstado;h:CantidadEstado;composicion:ComposicionEstado}
  |{tipo:'UV';U:CantidadEstado;V:CantidadEstado;cantidades:CantidadesEstado}
  |{tipo:'UP';U:CantidadEstado;P:CantidadEstado;cantidades:CantidadesEstado};
export type ModeloEstado={id:string;version:string};
export type DeclaracionEstado={modelo:ModeloEstado;especificacion:EspecificacionEstado;politica:PoliticaEstado;datosPuros?:SustitucionDatosPuros};
export type SolicitudEstado={revision:1;solicitudId:string;propietarioId:string;componentes:Componente[];declaracion:DeclaracionEstado};
/** All returned scalars use SI: J/kg, m3/kg, J/(kg K); energy and entropy may be negative. */
export type PropiedadesEstado={u:number;h:number;v:number;s:number;cp?:number;cv?:number};
export type FaseEvaluada={id:string;tipo:FaseEstado;regimen:'ordinario'|'supercritico';fraccionMolar:number;fraccionMasica:number;fraccionVolumen:number;composicionMolar:Record<string,number>;propiedades:PropiedadesEstado};
export type VerificacionEstado={id:string;estado:'cumple'|'no_cumple'|'no_evaluable';residuo:number|null;tolerancia:number|null;motivo?:string};
export type EvaluacionEstado={T:number;P:number;composicionMolar:Record<string,number>;componentes:{id:number;cas?:string;masaMolarKgMol:number;fuente:string}[];fases:FaseEvaluada[];mezcla:PropiedadesEstado;referencia:{id:string;descripcion:string};estabilidad:{estado:'estable'|'metastable'|'no_evaluada';alcance:FaseEstado[];metodo:string};verificaciones:VerificacionEstado[]};
export type DiagnosticoEstado={codigo:string;mensaje:string;ruta:string;componenteIds:number[];propietarioId:string;alternativas?:string[][]};
export type RespuestaEstado={revision:1;solicitudId:string;modelo:ModeloEstado;estado:'evaluado'|'incompleto'|'invalido'|'no_soportado'|'no_convergente';evaluacion:EvaluacionEstado|null;diagnosticos:DiagnosticoEstado[]};
export type CapacidadModeloEstado={id:string;version:string;nombre:string;componentesCAS:string[]|null;especificaciones:EspecificacionEstado['tipo'][];fases:FaseEstado[];dominio:{T:[number,number];P:[number,number]};referencia:{id:string;descripcion:string};propiedades:string[];dinamica:boolean};
export type CapacidadesEstado={revision:1;modelos:CapacidadModeloEstado[]};
export type EstadoGuardado={uso:'consulta'|'cierre';declaracion:DeclaracionEstado;originalesDatosPuros?:Record<string,PropiedadPura[]>;resultado?:{firma:string;respuesta:RespuestaEstado}};
export type TermodinamicaHoja={version:1;estados:Record<string,EstadoGuardado>};

/** Independent identity check for the model actually audited in H1.
 * This is the VSMOW value used by IAPWS-95, not a generic CAS -> molar-mass fallback.
 * Source: IAPWS G5-01(2020), §3.2, https://www.iapws.org/relguide/fundam.pdf.
 * No value is inserted into user declarations or the material solver. */
const IDENTIDADES_MODELOS:Record<string,Record<string,number>>={
  'agua-iapws95:1':{'7732-18-5':0.018015268},
};

export function firmaEstado(s:Omit<SolicitudEstado,'solicitudId'>):string{
  const ordenar=(v:unknown):unknown=>Array.isArray(v)?v.map(ordenar):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)).map(([k,x])=>[k,ordenar(x)])):v;
  return JSON.stringify(ordenar(s));
}
export function analizarSolicitudEstado(s:SolicitudEstado):DiagnosticoEstado[]{
  const ds:DiagnosticoEstado[]=[],error=(ruta:string,mensaje:string)=>ds.push({codigo:'MOTOR_ESTADO_DATO_INVALIDO',ruta,mensaje,componenteIds:[],propietarioId:s.propietarioId});
  if(s.revision!==1||!s.solicitudId||!s.propietarioId)error('revision','Identificación de solicitud o revisión inválida.');
  const ids=s.componentes.map(c=>String(c.id));
  if(!ids.length||new Set(ids).size!==ids.length||s.componentes.some(c=>!Number.isInteger(c.id)||c.id<1))error('componentes','Declara componentes con IDs únicos.');
  for(const c of s.componentes)if(!c.identidadQuimica?.cas&&!c.identidadQuimica?.proveedorId)error(`componentes.${c.id}.identidadQuimica`,'Identidad química sin declarar; el nombre no identifica un modelo físico.');
  if(!s.declaracion.modelo.id||!s.declaracion.modelo.version)error('declaracion.modelo','Modelo y versión sin declarar.');
  const p=s.declaracion.politica;
  if(!['sin_restriccion','monofasico'].includes(p.cantidad)||!['permitido','prohibido'].includes(p.cambioInterno)||p.evaluacion!=='equilibrio_estable')error('declaracion.politica','Política de estado inválida.');
  if(p.tiposPermitidos&&(!p.tiposPermitidos.length||new Set(p.tiposPermitidos).size!==p.tiposPermitidos.length||p.tiposPermitidos.some(x=>!['liquido','vapor','solido','fluido'].includes(x))))error('declaracion.politica.tiposPermitidos','Restricción de fases inválida.');
  const e=s.declaracion.especificacion,tipos={TP:['tipo','T','P','composicion'],PH:['tipo','P','h','composicion'],UV:['tipo','U','V','cantidades'],UP:['tipo','U','P','cantidades']};
  if(!Object.hasOwn(tipos,e.tipo)){error('declaracion.especificacion','Especificación desconocida.');return ds;}
  if(Object.keys(e).some(k=>!tipos[e.tipo].includes(k)))error('declaracion.especificacion','Datos adicionales o especificaciones duplicadas.');
  const q=(ruta:string,v:CantidadEstado,m:string)=>{try{normalizarCantidad(v,m);}catch(ex){error(ruta,(ex as Error).message);}};
  if('T'in e)q('declaracion.especificacion.T',e.T,'T');if('P'in e)q('declaracion.especificacion.P',e.P,'P');if('h'in e)q('declaracion.especificacion.h',e.h,'h');if('U'in e)q('declaracion.especificacion.U',e.U,'U');if('V'in e)q('declaracion.especificacion.V',e.V,'V');
  if('composicion'in e){const z=e.composicion;if(!['masica','molar'].includes(z.base)||!composicionValida(z.fracciones,ids))error('declaracion.especificacion.composicion','Declara cada componente y fracciones no negativas que sumen uno.');}
  else {const n=e.cantidades;if(!['masica','molar'].includes(n.base)||Object.keys(n.valores).length!==ids.length||ids.some(id=>!n.valores[id]))error('declaracion.especificacion.cantidades','Declara una cantidad de cada componente.');let total=0;for(const [id,v]of Object.entries(n.valores)){if(!ids.includes(id))error(`cantidades.${id}`,'Componente desconocido.');try{total+=normalizarCantidad(v,n.base==='masica'?'m':'n');}catch(ex){error(`cantidades.${id}`,(ex as Error).message);}}if(total<=0)error('declaracion.especificacion.cantidades','El estado necesita una cantidad total positiva.');}
  return ds;
}
/** Explicit unit families; never apply a universal mass-to-moles conversion. */
export function normalizarCantidad(q:CantidadEstado,m:string):number{
  const unidades:Record<string,Record<string,number>>={T:{K:1,degC:1,degF:5/9},P:{Pa:1,kPa:1000,bar:1e5},h:{'J/kg':1,'kJ/kg':1000},U:{J:1,kJ:1000},V:{m3:1,L:.001},m:{kg:1,g:.001},n:{mol:1,kmol:1000}};
  if(!q||typeof q.valor!=='number'||!Number.isFinite(q.valor)||!unidades[m]||!Object.hasOwn(unidades[m],q.unidad))throw new Error(q?.valor===null?'Dato sin especificar.':'Cantidad o unidad incompatible.');
  const v=m==='T'?q.unidad==='degC'?q.valor+273.15:q.unidad==='degF'?(q.valor-32)*5/9+273.15:q.valor:q.valor*unidades[m][q.unidad];
  if(['T','P','V'].includes(m)&&v<=0||['m','n'].includes(m)&&v<0)throw new Error('Valor fuera del dominio de la magnitud.');return v;
}
const cerca=(a:number,b:number,rel=1e-7,abs=1e-9)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=abs+rel*Math.max(Math.abs(a),Math.abs(b));
function composicionValida(z:Record<string,number|null>,ids:string[]){return z&&Object.keys(z).length===ids.length&&ids.every(id=>{const v=z[id];return typeof v==='number'&&Number.isFinite(v)&&v>=0;})&&cerca(ids.reduce((a,id)=>a+Number(z[id]),0),1,0,1e-10);}
export function validarCapacidadesEstado(raw:unknown):CapacidadesEstado{
  const c=raw as CapacidadesEstado;
  if(!c||c.revision!==1||!Array.isArray(c.modelos)||new Set(c.modelos.map(m=>JSON.stringify([m.id,m.version]))).size!==c.modelos.length)throw new Error('Catálogo termodinámico incompatible.');
  for(const m of c.modelos)if(!textoPublicado(m.id)||!textoPublicado(m.version)||!textoPublicado(m.nombre)||!identificadoresPublicados(m.especificaciones)||!m.especificaciones.length||m.especificaciones.some(x=>!['TP','PH','UV','UP'].includes(x))||!identificadoresPublicados(m.fases)||!m.fases.length||m.fases.some(x=>!['liquido','vapor','solido','fluido'].includes(x))||!textoPublicado(m.referencia?.id)||!textoPublicado(m.referencia.descripcion)||!dominioPublicado(m.dominio)||typeof m.dinamica!=='boolean'||!identificadoresPublicados(m.propiedades)||m.componentesCAS!==null&&(!identificadoresPublicados(m.componentesCAS)||!m.componentesCAS.length))throw new Error('Capacidad termodinámica incompleta.');
  return c;
}
/** Independently reconstruct material, volume and energy. This validates the protocol,
 * not the provider's global stability algorithm or experimental accuracy. */
export function validarRespuestaEstado(raw:unknown,s:SolicitudEstado,capacidad?:CapacidadModeloEstado):RespuestaEstado{
  const r=raw as RespuestaEstado,fallo=(mensaje:string):never=>{throw new Error(`Respuesta termodinámica incompatible: ${mensaje}`);};
  if(!r||r.revision!==1||r.solicitudId!==s.solicitudId||r.modelo?.id!==s.declaracion.modelo.id||r.modelo.version!==s.declaracion.modelo.version||!Array.isArray(r.diagnosticos)||!['evaluado','incompleto','invalido','no_soportado','no_convergente'].includes(r.estado))fallo('identidad o revisión.');
  if(capacidad&&(capacidad.id!==r.modelo.id||capacidad.version!==r.modelo.version||!capacidad.especificaciones.includes(s.declaracion.especificacion.tipo)))fallo('capacidad solicitada.');
  if(r.estado!=='evaluado'){if(r.evaluacion!==null||!r.diagnosticos.length)fallo('un rechazo no debe conservar un estado calculado.');return r;}
  const e=r.evaluacion;if(!e)return fallo('estado ausente.');
  const ids=s.componentes.map(c=>String(c.id));
  if(!Number.isFinite(e.T)||e.T<=0||!Number.isFinite(e.P)||e.P<=0||!e.referencia?.id||!e.referencia.descripcion||!Array.isArray(e.componentes)||e.componentes.length!==ids.length||new Set(e.componentes.map(c=>c.id)).size!==ids.length||e.componentes.some(c=>!ids.includes(String(c.id))||!Number.isFinite(c.masaMolarKgMol)||c.masaMolarKgMol<=0||!c.fuente))fallo('estado, referencia o identidades.');
  for(const c of s.componentes){
    const real=e.componentes.find(z=>z.id===c.id)!;
    if(c.identidadQuimica?.cas&&real.cas!==c.identidadQuimica.cas)fallo('identidad CAS.');
    if(c.masaMolar&&!cerca(masaMolarKg(c),real.masaMolarKgMol,1e-7,1e-12))fallo('masa molar incompatible con el catálogo.');
    const identidades=IDENTIDADES_MODELOS[`${r.modelo.id}:${r.modelo.version}`];
    if(identidades&&(!real.cas||!Object.hasOwn(identidades,real.cas)||!cerca(identidades[real.cas],real.masaMolarKgMol,1e-7,1e-12)))fallo('masa molar o identidad incompatible con el modelo verificado.');
  }
  if(!composicionValida(e.composicionMolar,ids)||!Array.isArray(e.fases)||!e.fases.length||new Set(e.fases.map(f=>f.id)).size!==e.fases.length)fallo('composición o fases.');
  const masas=Object.fromEntries(e.componentes.map(c=>[String(c.id),c.masaMolarKgMol]));
  const M=(z:Record<string,number>)=>ids.reduce((a,id)=>a+z[id]*masas[id],0),Mglobal=M(e.composicionMolar);
  const props=(p:PropiedadesEstado)=>{if(!p||!['u','h','v','s'].every(k=>Number.isFinite(p[k as keyof PropiedadesEstado]))||p.v<=0||!cerca(p.h,p.u+e.P*p.v)||[p.cp,p.cv].some(v=>v!==undefined&&(!Number.isFinite(v)||v<=0)))fallo('propiedades o h=u+Pv.');};props(e.mezcla);
  if(e.fases.length>1&&(e.mezcla.cp!==undefined||e.mezcla.cv!==undefined))fallo('capacidad monofásica presentada como capacidad bifásica.');
  if(r.modelo.id==='agua-iapws95'&&r.modelo.version==='1'&&Array.isArray(e.verificaciones)&&e.verificaciones.some(v=>v.id==='equilibrio')&&(e.mezcla.cp!==undefined||e.mezcla.cv!==undefined))fallo('capacidad global de fase presentada como derivada del estado en saturación.');
  // Permit only machine-roundoff above one; do not clamp or rewrite certified fractions.
  for(const f of e.fases){if(!f.id||!['liquido','vapor','solido','fluido'].includes(f.tipo)||!['ordinario','supercritico'].includes(f.regimen)||f.regimen==='supercritico'&&f.tipo!=='fluido'||!composicionValida(f.composicionMolar,ids)||![f.fraccionMolar,f.fraccionMasica,f.fraccionVolumen].every(v=>Number.isFinite(v)&&v>0&&v<=1+8*Number.EPSILON))fallo('fase inválida o ausente.');props(f.propiedades);if(!cerca(f.fraccionMasica,f.fraccionMolar*M(f.composicionMolar)/Mglobal)||!cerca(f.fraccionVolumen,f.fraccionMasica*f.propiedades.v/e.mezcla.v))fallo('bases de fracción de fase.');}
  for(const k of ['fraccionMolar','fraccionMasica','fraccionVolumen']as const)if(!cerca(e.fases.reduce((a,f)=>a+f[k],0),1,0,1e-9))fallo('suma de fracciones.');
  for(const id of ids)if(!cerca(e.fases.reduce((a,f)=>a+f.fraccionMolar*f.composicionMolar[id],0),e.composicionMolar[id],1e-7,1e-12))fallo('reconstrucción de componentes.');
  for(const k of ['u','h','v','s']as const)if(!cerca(e.fases.reduce((a,f)=>a+f.fraccionMasica*f.propiedades[k],0),e.mezcla[k]))fallo('reconstrucción de propiedades.');
  if(e.estabilidad?.estado!=='estable'||!e.estabilidad.metodo||!Array.isArray(e.estabilidad.alcance)||!e.estabilidad.alcance.length)fallo('certificación de estabilidad ausente.');
  const rangoSustituido=temperaturaEnRangosSustituidos(e.T,s.declaracion.datosPuros);
  // Static capabilities describe the unmodified package. A changed thermal input
  // has its declared interval AND must carry the backend's domain verification.
  // No message parsing or independent reconstruction of a mixture domain here.
  if(rangoSustituido!==undefined&&(rangoSustituido!==true||!e.verificaciones?.some(v=>v.id==='dominio'&&v.estado==='cumple')))fallo('dominio de datos sustituidos no certificado.');
  if(capacidad&&(e.referencia.id!==capacidad.referencia.id||rangoSustituido===undefined&&(e.T<capacidad.dominio.T[0]||e.T>capacidad.dominio.T[1])||e.P<capacidad.dominio.P[0]||e.P>capacidad.dominio.P[1]||capacidad.fases.some(f=>!e.estabilidad.alcance.includes(f))))fallo('dominio, referencia o búsqueda de estabilidad incompletos.');
  if(capacidad?.componentesCAS&&e.componentes.some(c=>!c.cas||!capacidad.componentesCAS!.includes(c.cas)))fallo('sustancias no admitidas por el modelo.');
  const p=s.declaracion.politica;
  if(p.cantidad==='monofasico'&&e.fases.length!==1||p.tiposPermitidos&&e.fases.some(f=>!p.tiposPermitidos!.includes(f.tipo)))fallo('restricción de fases incumplida.');
  if(p.tiposPermitidos&&p.tiposPermitidos.some(f=>!e.estabilidad.alcance.includes(f))||e.fases.some(f=>!e.estabilidad.alcance.includes(f.tipo)))fallo('alcance de estabilidad insuficiente.');
  if(!Array.isArray(e.verificaciones)||!e.verificaciones.some(v=>v.id==='estabilidad'&&v.estado==='cumple')||e.fases.length>1&&!e.verificaciones.some(v=>v.id==='equilibrio'&&v.estado==='cumple'))fallo('verificaciones ausentes.');
  for(const v of e.verificaciones)if(!v.id||!['cumple','no_cumple','no_evaluable'].includes(v.estado)||v.estado==='no_cumple'||v.residuo!==null&&(!Number.isFinite(v.residuo)||v.residuo<0)||v.tolerancia!==null&&(!Number.isFinite(v.tolerancia)||v.tolerancia<0)||v.estado==='cumple'&&v.residuo!==null&&(v.tolerancia===null||v.residuo>v.tolerancia))fallo('residuo no certificado.');
  const x=s.declaracion.especificacion;
  if('T'in x&&!cerca(e.T,normalizarCantidad(x.T,'T'))||'P'in x&&!cerca(e.P,normalizarCantidad(x.P,'P'))||'h'in x&&!cerca(e.mezcla.h,normalizarCantidad(x.h,'h')))fallo('especificaciones no respetadas.');
  if('composicion'in x){const z=x.composicion.fracciones;for(const id of ids){const calculada=x.composicion.base==='molar'?e.composicionMolar[id]:e.composicionMolar[id]*masas[id]/Mglobal;if(typeof z[id]!=='number'||!cerca(calculada,z[id],1e-7,1e-12))fallo('composición especificada.');}}
  else {const n=Object.fromEntries(ids.map(id=>[id,normalizarCantidad(x.cantidades.valores[id],x.cantidades.base==='molar'?'n':'m')/(x.cantidades.base==='molar'?1:masas[id])]));const N=Object.values(n).reduce((a,v)=>a+v,0),m=ids.reduce((a,id)=>a+n[id]*masas[id],0);for(const id of ids)if(!cerca(e.composicionMolar[id],n[id]/N,1e-7,1e-12))fallo('cantidades por componente.');if(!cerca(m*e.mezcla.u,normalizarCantidad(x.U,'U'))||'V'in x&&!cerca(m*e.mezcla.v,normalizarCantidad(x.V,'V'),1e-7,1e-12))fallo('reconstrucción U/V.');}
  return r;
}
