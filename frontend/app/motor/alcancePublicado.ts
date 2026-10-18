/** Structural checks for published metadata, never a thermodynamic domain test.
 * Identifiers remain opaque: no substance catalog, model list or size ceiling here. */
export const textoPublicado=(v:unknown):v is string=>typeof v==='string'&&v.trim().length>0;
export const textosPublicados=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(textoPublicado);
export const identificadoresPublicados=(v:unknown):v is string[]=>textosPublicados(v)&&new Set(v).size===v.length;
export function dominioPublicado(v:unknown):v is {T:[number,number];P:[number,number]}{
  if(!v||typeof v!=='object'||Array.isArray(v))return false;
  return ['T','P'].every(k=>{
    const d=(v as Record<string,unknown>)[k];
    return Array.isArray(d)&&d.length===2&&d.every(x=>typeof x==='number'&&Number.isFinite(x)&&x>0)&&d[0]<d[1];
  });
}
export const cantidadMaximaPublicada=(v:unknown,disponible:boolean):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=(disponible?1:0);
