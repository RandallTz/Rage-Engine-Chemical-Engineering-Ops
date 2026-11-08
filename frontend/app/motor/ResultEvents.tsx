'use client';
import {useLayoutEffect,useRef,useState} from 'react';
import {usePlotArea} from 'recharts';
import type {ConjuntoResultados} from '../../motores/resultados/contrato';
import {nombreEventoRed} from './metadatosRed';
import {formatearNumeroMotor} from './formatearNumeroMotor';
import styles from './trabajoMotor.module.css';

/** Reuse assembly event labels; display only the published common time events. */
export function commonTimeEvents(result:ConjuntoResultados|undefined) {
  const axes=new Set(result?.ejes.filter(axis=>axis.rol==='tiempo'&&axis.unidadSI==='s').map(axis=>axis.id));
  return result?.eventos.filter(event=>axes.has(event.ejeId))??[];
}

/** Row for each marker label so labels closer than one label width never share a height. Keeps the full text in the event list. */
export function eventLabelRows(items:{x:number;text:string}[],domain:[number,number],width:number,maxRows=5){
  const span=domain[1]-domain[0]||1,ends:number[]=[],rows=new Array<number>(items.length).fill(0);
  items.map((item,index)=>({index,px:(item.x-domain[0])/span*width,w:item.text.length*6+10})).sort((a,b)=>a.px-b.px).forEach(({index,px,w})=>{
    let row=ends.findIndex(end=>end<=px);if(row<0)row=ends.length<maxRows?ends.length:ends.indexOf(Math.min(...ends));
    ends[row]=px+w;rows[index]=row;
  });
  return rows;
}
export function EventMarkerLabel({viewBox,value,row=0}:{viewBox?:{x?:number;y?:number};value?:unknown;row?:number}){
  const area=usePlotArea(),text=useRef<SVGTextElement>(null),[measured,setMeasured]=useState(0);
  useLayoutEffect(()=>{if(text.current)setMeasured(text.current.getComputedTextLength());},[value]);
  if(!area||typeof value!=='string')return null;
  const available=Math.max(1,area.width-12),width=Math.min(measured||value.length*10,available);
  const x=Math.max(area.x+6,Math.min((viewBox?.x??area.x)+6,area.x+area.width-6-width));
  return <text ref={text} className="common-event-label" x={x} y={area.y+6+row*13} textAnchor="start" dominantBaseline="hanging" fontSize={10} textLength={measured>available?available:undefined} lengthAdjust="spacingAndGlyphs">{value}</text>;
}

export function ResultEvents({result}:{result:ConjuntoResultados|undefined}) {
  const events=commonTimeEvents(result);
  if(!result)return null;
  return <details className={styles.settings} open><summary>Events · {events.length}</summary>
    {events.map((event,index)=><article key={index}>
      <h3>{nombreEventoRed(event.codigo)} · {formatearNumeroMotor(event.valor)} s · {event.propietarioId??'model'}</h3>
      <p>{event.descripcion}</p>
    </article>)}
    <p>Published events only. Checks within each step do not constitute continuous event certification.</p>
  </details>;
}
