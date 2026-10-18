import type {CatalogoMotor} from './contratoCatalogo';
import type {RedTermodinamica} from './redTermodinamica';
import {mismoModelo} from './modelosTermodinamicos';
/** Admission per species is necessary, never a certificate for the whole mixture. */
export function opcionesCatalogoRed(c:CatalogoMotor,red:RedTermodinamica,destinos:string[],busqueda:string){
  const limpiar=(s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim(),q=limpiar(busqueda);
  const vs=red.solicitud.volumenes.filter(v=>!destinos.length||destinos.includes(v.id));
  return c.sustancias.filter(s=>!q||limpiar(`${s.nombre} ${s.cas}`).includes(q)).map(s=>{
    const volumenes=vs.map(v=>{
      const modelo=red.solicitud.paquetes.find(p=>p.id===v.paqueteId)?.modelo,p=modelo?c.paquetes.find(p=>mismoModelo(p.modelo,modelo)):undefined,e=p?.especies.find(e=>e.cas===s.cas);
      return {id:v.id,nombre:red.nombres[`volumen:${v.id}`]??v.id,admitida:!!p?.operaciones.ensamblaje.disponible&&!!e?.admitida,motivos:!p?['Paquete sin publicar en este catálogo']:!p.operaciones.ensamblaje.disponible?['Paquete sin ensamblaje dinámico']:e?.faltantes.map(f=>`${f.dato}: ${f.mensaje}`)??['Especie sin admisión publicada']};
    });
    const presente=red.solicitud.componentes.some(x=>x.identidadQuimica?.cas===s.cas);
    return {sustancia:s,volumenes,presente,elegible:!presente&&volumenes.length>0&&(destinos.length?volumenes.every(v=>v.admitida):volumenes.some(v=>v.admitida))};
  });
}
