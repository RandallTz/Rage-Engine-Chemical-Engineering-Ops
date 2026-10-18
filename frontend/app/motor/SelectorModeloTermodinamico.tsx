'use client';
import type {ModeloEstado} from './contratoTermodinamica';
import {claveModelo,modeloElegido,opcionesModelos} from './modelosTermodinamicos';
import type {ModeloPublicado} from './modelosTermodinamicos';

export default function SelectorModeloTermodinamico({id,actual,publicados,catalogoCargado,nombre,elegir}:{id?:string;actual?:ModeloEstado;publicados:ModeloPublicado[];catalogoCargado:boolean;nombre:string;elegir:(modelo:ModeloEstado)=>void}){
  const opciones=opcionesModelos(publicados,actual,catalogoCargado);
  return <select id={id} aria-label={nombre} value={actual?.id&&actual.version?claveModelo(actual):''} onChange={e=>{const modelo=modeloElegido(opciones,e.target.value);if(modelo)elegir(modelo);}}>
    <option value="">Seleccionar paquete</option>
    {opciones.map(p=><option key={p.clave} value={p.clave} disabled={!p.disponible} title={`${p.modelo.id} · ${p.modelo.version}`}>{p.etiqueta}</option>)}
  </select>;
}
