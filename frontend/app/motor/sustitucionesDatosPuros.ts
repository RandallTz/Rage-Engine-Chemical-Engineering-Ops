import type {PropiedadPura,SustitucionDatosPuros,SustanciaCatalogo} from './contratoCatalogo';
import type {Componente} from './materiaEstado';
export type PropiedadSustituible=keyof SustitucionDatosPuros[string];
export const nombresDatosPuros:Record<PropiedadSustituible,string>={volumen_liquido:'Volumen molar del líquido',cp_gas_ideal:'Cp del gas ideal',presion_vapor:'Presión de vapor'};
/** Stable request identity, not the backend's physical fingerprint. */
export function firmaDatosPuros(d?:SustitucionDatosPuros){
  const ordenar=(v:unknown):unknown=>Array.isArray(v)?v.map(ordenar):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)).map(([k,x])=>[k,ordenar(x)])):v;
  return JSON.stringify(ordenar(d??{}));
}
export function datosPurosDeComponentes(d:SustitucionDatosPuros|undefined,cs:Componente[]){
  if(!d)return undefined;
  const cas=new Set(cs.flatMap(c=>c.identidadQuimica?.cas?[c.identidadQuimica.cas]:[]));
  const out=Object.fromEntries(Object.entries(d).filter(([id])=>cas.has(id)));
  return Object.keys(out).length?structuredClone(out):undefined;
}
export function sustituirDatoPuro(d:SustitucionDatosPuros|undefined,cas:string,id:PropiedadSustituible,valor:SustitucionDatosPuros[string][PropiedadSustituible]){
  const copia=structuredClone(d??{});
  if(valor===undefined){if(copia[cas]){delete copia[cas][id];if(!Object.keys(copia[cas]).length)delete copia[cas];}}
  else copia[cas]={...copia[cas],[id]:structuredClone(valor)};
  return Object.keys(copia).length?copia:undefined;
}
/** Seed an editable draft only on an explicit edit action. Applying it still
 * requires a source and backend validation; the registry is never modified. */
export function borradorDatoPuro(s:SustanciaCatalogo,id:PropiedadSustituible):SustitucionDatosPuros[string][PropiedadSustituible]|undefined{
  const p=s.datosPuros.propiedades?.find(p=>p.id===id);if(!p)return;
  if(p.id==='volumen_liquido')return {valor:p.valor,unidad:p.unidad,fuente:''};
  if(p.id==='cp_gas_ideal')return {coeficientes:{...p.coeficientes},dominio:structuredClone(p.dominio),fuente:''};
  const forma=p.forma.includes('WagnerMcGarry')?'WagnerMcGarry':p.forma.includes('WagnerPoling')?'WagnerPoling':undefined;
  if(forma)return {forma,coeficientes:{...p.coeficientes},dominio:structuredClone(p.dominio),fuente:''};
}
export function problemaBorradorDatoPuro(id:PropiedadSustituible,v:unknown):string|null{
  if(!v||typeof v!=='object')return 'Dato sin declarar.';
  const d=v as Record<string,unknown>,fin=(n:unknown)=>typeof n==='number'&&Number.isFinite(n);
  if(typeof d.fuente!=='string'||!d.fuente.trim())return 'Declara la fuente de la sustitución.';
  if(id==='volumen_liquido')return fin(d.valor)&&Number(d.valor)>0&&['m3/mol','cm3/mol','L/mol'].includes(String(d.unidad))?null:'Declara un volumen positivo con su unidad.';
  const rango=(d.dominio as {T?:unknown})?.T;
  if(!Array.isArray(rango)||rango.length!==2||!rango.every(x=>fin(x)&&x>0)||rango[1]<=rango[0])return 'Declara Tmin < Tmax, en K.';
  const keys=id==='cp_gas_ideal'?['a0','a1','a2','a3','a4']:['A','B','C','D','Tc','Pc'],c=d.coeficientes as Record<string,unknown>;
  if(!c||keys.some(k=>!fin(c[k])))return 'Completa todos los coeficientes.';
  if(id==='presion_vapor'&&(!['WagnerPoling','WagnerMcGarry'].includes(String(d.forma))||Number(c.Tc)<=0||Number(c.Pc)<=0||rango[1]>Number(c.Tc)))return 'Revisa la forma, Tc [K], Pc [Pa] y Tmax ≤ Tc.';
  return null;// Positivity of Cp, Psat monotonicity and derivatives belong to the backend.
}
export function descripcionDatoOriginal(p:PropiedadPura){return p.id==='volumen_liquido'?`${p.valor} ${p.unidad}`:`${p.forma} · ${p.dominio.T.join('–')} K · ${p.unidad}`;}
/** Only checks the explicitly replaced temperature intervals. It does not
 * compute the package's effective domain (which includes other data/models). */
export function temperaturaEnRangosSustituidos(T:number,d?:SustitucionDatosPuros):boolean|undefined{
  let hay=false;
  for(const s of Object.values(d??{}))for(const k of ['cp_gas_ideal','presion_vapor'] as const){
    const p=s[k];if(!p)continue;hay=true;
    if(problemaBorradorDatoPuro(k,p)||T<p.dominio.T[0]||T>p.dominio.T[1])return false;
  }
  return hay?true:undefined;
}
