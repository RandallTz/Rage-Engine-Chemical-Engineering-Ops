import type {ModeloEstado} from './contratoTermodinamica';

/** UI identities only. No inference about variant, physics or parameter data. */
export const claveModelo=(m:ModeloEstado)=>JSON.stringify([m.id,m.version]);
export const mismoModelo=(a:ModeloEstado,b:ModeloEstado)=>a.id===b.id&&a.version===b.version;
export type ModeloPublicado={modelo:ModeloEstado;nombre?:string;disponible:boolean};
export type OpcionModelo=ModeloPublicado&{clave:string;etiqueta:string;guardadoSinPublicar:boolean};

export function opcionesModelos(publicados:ModeloPublicado[],actual?:ModeloEstado,catalogoCargado=true):OpcionModelo[]{
  const vistos=new Set<string>();
  const opciones=publicados.map(p=>{
    if(typeof p.modelo?.id!=='string'||!p.modelo.id.trim()||typeof p.modelo.version!=='string'||!p.modelo.version.trim()||typeof p.disponible!=='boolean')throw new Error('Identidad de paquete termodinámico incompleta.');
    const clave=claveModelo(p.modelo);if(vistos.has(clave))throw new Error('El catálogo repite el mismo paquete y versión.');vistos.add(clave);
    return {...p,modelo:{...p.modelo},clave,etiqueta:`${p.nombre||p.modelo.id} · v${p.modelo.version}${p.disponible?'':' · no disponible para esta operación'}`,guardadoSinPublicar:false};
  });
  if(actual?.id&&actual.version&&!vistos.has(claveModelo(actual)))opciones.push({modelo:{...actual},disponible:false,clave:claveModelo(actual),etiqueta:`${actual.id} · v${actual.version} · ${catalogoCargado?'guardado; no publicado':'catálogo sin cargar'}`,guardadoSinPublicar:true});
  return opciones;
}

/** Only an explicit selection from the current published operation is usable. */
export function modeloElegido(opciones:OpcionModelo[],clave:string):ModeloEstado|null{
  const p=opciones.find(p=>p.clave===clave);
  return p?.disponible&&!p.guardadoSinPublicar?{...p.modelo}:null;
}
