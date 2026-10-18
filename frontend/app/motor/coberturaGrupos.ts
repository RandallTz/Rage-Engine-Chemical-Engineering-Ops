import type {CoberturaGrupos,SubgrupoAsignado,VarianteUNIFAC} from './contratoContribucionGrupos';
import type {Componente} from './materiaEstado';

const texto=(x:unknown):x is string=>typeof x==='string'&&!!x.trim();
const entero=(x:unknown):x is number=>Number.isSafeInteger(x)&&Number(x)>0;
const cas=(x:unknown):x is string=>typeof x==='string'&&/^\d{2,7}-\d{2}-\d$/.test(x);
const variantes:VarianteUNIFAC[]=['original','dortmund','lle'];
const fallo=(ruta:string):never=>{throw new Error(`Cobertura de grupos incompatible: ${ruta}.`);};

/** Metadata integrity only. No activity coefficient, flash, stability or physical certification is computed here. */
export function leerCoberturaGrupos(raw:unknown,componentesCAS?:string[]):CoberturaGrupos{
  const c=raw as CoberturaGrupos;
  if(!c||c.tipo!=='contribucion_de_grupos'||!variantes.includes(c.variante)||!c.datos||c.datos.variante!==c.variante)fallo('tipo o variante');
  for(const k of ['fuente_interacciones','fuente_asignaciones','fuente_subgrupos'] as const)if(!texto(c.datos[k]))fallo(`datos.${k}`);
  for(const k of ['sha256_interacciones','sha256_asignaciones'] as const)if(typeof c.datos[k]!=='string'||!/^[a-fA-F0-9]{64}$/.test(c.datos[k]))fallo(`datos.${k}`);
  if(c.datos.fuente_tabla!==undefined&&!texto(c.datos.fuente_tabla))fallo('datos.fuente_tabla');
  const rango=c.datos.rango_T_datos;
  if(rango!==undefined&&(!Array.isArray(rango)||rango.length!==2||!rango.every(x=>typeof x==='number'&&Number.isFinite(x)&&x>0)||rango[0]>=rango[1]))fallo('datos.rango_T_datos');
  if(!Array.isArray(c.especies)||!Array.isArray(c.especiesSinAsignacion)||!Array.isArray(c.interaccionesDirigidasFaltantes)||!texto(c.nota))fallo('catálogo o nota');
  const identificadas=new Set<string>(),principales=new Set<number>(),subgrupos=new Map<number,SubgrupoAsignado>();
  for(const e of c.especies){
    if(!e||!cas(e.cas)||identificadas.has(e.cas)||!texto(e.procedencia)||!Array.isArray(e.subgrupos)||!e.subgrupos.length)fallo('especie o asignación');
    identificadas.add(e.cas);
    const ids=new Set<number>();
    for(const g of e.subgrupos){
      if(!g||!entero(g.id)||!entero(g.grupoPrincipal)||!entero(g.cuenta)||!texto(g.nombre)||ids.has(g.id))fallo(`especies.${e.cas}.subgrupos`);
      const anterior=subgrupos.get(g.id);
      if(anterior&&(anterior.nombre!==g.nombre||anterior.grupoPrincipal!==g.grupoPrincipal))fallo(`subgrupo ${g.id} con identidades diferentes`);
      ids.add(g.id);principales.add(g.grupoPrincipal);subgrupos.set(g.id,g);
    }
  }
  const asignadas=new Set(identificadas);
  for(const id of c.especiesSinAsignacion){if(!cas(id)||identificadas.has(id))fallo('especiesSinAsignacion duplicada o contradictoria');identificadas.add(id);}
  // componentesCAS is the admitted list: known species WITHOUT an assignment
  // remain in the coverage diagnosis but must not become an admitted capability.
  if(componentesCAS!==undefined&&(!Array.isArray(componentesCAS)||componentesCAS.some(x=>!cas(x))||new Set(componentesCAS).size!==componentesCAS.length||asignadas.size!==componentesCAS.length||componentesCAS.some(x=>!asignadas.has(x))))fallo('asignaciones distintas de las especies admitidas');
  const pares=new Set<string>();
  for(const p of c.interaccionesDirigidasFaltantes){
    if(!Array.isArray(p)||p.length!==2||!p.every(entero)||p[0]===p[1]||!p.every(x=>principales.has(x)))fallo('interacción dirigida sin grupos identificados');
    const clave=JSON.stringify(p);if(pares.has(clave))fallo('interacción dirigida duplicada');pares.add(clave);
  }
  return c;
}

export const nombreVarianteUNIFAC=(v:VarianteUNIFAC)=>({original:'UNIFAC original',dortmund:'UNIFAC Dortmund',lle:'UNIFAC · tabla ELL'}[v]);

export function resumirCoberturaGrupos(c:CoberturaGrupos,componentes:Componente[]){
  const grupos=new Set<number>();
  const filas=componentes.map(componente=>{
    const id=componente.identidadQuimica?.cas,asignacion=c.especies.find(e=>e.cas===id);
    asignacion?.subgrupos.forEach(g=>grupos.add(g.grupoPrincipal));
    const estado=!id?'sin_identidad':asignacion?'publicada':c.especiesSinAsignacion.includes(id)?'sin_asignacion':'fuera_catalogo';
    return {componente,asignacion,estado};
  });
  return {filas,asignadas:filas.filter(f=>f.estado==='publicada').length,
    interaccionesFaltantes:c.interaccionesDirigidasFaltantes.filter(([m,n])=>grupos.has(m)&&grupos.has(n))};
}
