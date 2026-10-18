import type {RedTermodinamica} from './redTermodinamica';
import {maximoElementoRed} from './topologiaRed';

/** Reserve retired identities even when branching from an earlier configuration. */
export function conservarIdentidadesRed(destino:RedTermodinamica,actual:RedTermodinamica):RedTermodinamica{
  const r=structuredClone(destino);
  r.ultimoComponenteId=Math.max(r.ultimoComponenteId??0,actual.ultimoComponenteId??0,0,...r.solicitud.componentes.map(c=>c.id),...actual.solicitud.componentes.map(c=>c.id));
  for(const t of ['volumen','corriente','calor'] as const)r.ultimosElementos={...r.ultimosElementos,[t]:Math.max(maximoElementoRed(r,t),maximoElementoRed(actual,t))};
  return r;
}
const firma=(r:RedTermodinamica)=>JSON.stringify(r);
export class HistorialEdicionRed{
  private antes:RedTermodinamica[]=[];
  private despues:RedTermodinamica[]=[];
  private actual:string|null=null;
  private grupo:string|undefined;
  constructor(private limite=30){}
  get puedeDeshacer(){return this.antes.length>0;}
  get puedeRehacer(){return this.despues.length>0;}
  vigente(r:RedTermodinamica){return this.actual===null||this.actual===firma(r);}
  sincronizar(r:RedTermodinamica){
    if(this.actual!==null&&this.actual!==firma(r)){this.antes=[];this.despues=[];this.grupo=undefined;}
    this.actual=firma(r);
  }
  registrar(anterior:RedTermodinamica,siguiente:RedTermodinamica,grupo?:string){
    this.sincronizar(anterior);
    if(firma(anterior)===firma(siguiente))return;
    if(!grupo||grupo!==this.grupo||!this.antes.length)this.antes=[...this.antes,structuredClone(anterior)].slice(-this.limite);
    this.despues=[];this.grupo=grupo;this.actual=firma(siguiente);
  }
  terminarGrupo(){this.grupo=undefined;}
  mover(r:RedTermodinamica,direccion:'deshacer'|'rehacer',guardar:(r:RedTermodinamica)=>RedTermodinamica){
    this.sincronizar(r);
    const origen=direccion==='deshacer'?this.antes:this.despues,destino=direccion==='deshacer'?this.despues:this.antes;
    if(!origen.length)return false;
    const restaurada=conservarIdentidadesRed(origen.at(-1)!,r);
    // Persist first: failed localStorage writes must not consume undo/redo.
    const persistida=guardar(restaurada);origen.pop();destino.push(structuredClone(r));
    this.actual=firma(persistida);this.grupo=undefined;
    return true;
  }
}
// Client session only, configurations only: no trajectories or server-side user state.
const sesiones=new Map<string,HistorialEdicionRed>();
export function historialEdicionRed(id:string){
  if(typeof window==='undefined')return new HistorialEdicionRed();
  let h=sesiones.get(id);if(!h){h=new HistorialEdicionRed();sesiones.set(id,h);}
  if(sesiones.size>24)sesiones.delete(sesiones.keys().next().value!);
  return h;
}
