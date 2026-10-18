'use client';
import {useEffect,useRef,useState} from 'react';
import {ScatterChart,Scatter,XAxis,YAxis,CartesianGrid,Tooltip} from 'recharts';
import type {RespuestaDiagrama} from './contratoDiagramasEquilibrio';
import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import {curvasDiagrama,marcadoresMuestra} from './datosDiagramaEquilibrio';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './equilibrioMotor.module.css';

export default function GraficaCorteEquilibrio({r,muestra,ejeId,unidadT,unidadP}:{r:RespuestaDiagrama;muestra:ContextoMuestraEquilibrio;ejeId:number;unidadT:'K'|'degC';unidadP:'Pa'|'kPa'|'bar'}){
  const host=useRef<HTMLDivElement>(null),[ancho,setAncho]=useState(0);
  useEffect(()=>{if(!host.current)return;const o=new ResizeObserver(([x])=>setAncho(x.contentRect.width));o.observe(host.current);return()=>o.disconnect();},[]);
  const curvas=curvasDiagrama(r,ejeId,unidadT,unidadP),marcadores=marcadoresMuestra(muestra,r,ejeId,unidadT,unidadP),tipo=r.condicion!.corte.tipo;
  const unidad=tipo==='Txy'?(unidadT==='K'?'K':'°C'):unidadP,nombre=muestra.componentes.find(c=>c.id===ejeId)?.nombre??String(ejeId);
  const especiales=r.puntosEspeciales.filter(p=>p.tipo==='azeotropo'&&p.puntoId).flatMap(e=>{const p=curvas.flatMap(c=>c.puntos).find(p=>p.puntoId===e.puntoId);return p?[p]:[];});
  return <>
    <div ref={host} className={styles.chart}>{ancho>0&&<ScatterChart width={ancho} height={340} margin={{top:20,right:22,bottom:26,left:4}} accessibilityLayer>
      <CartesianGrid stroke="#dfe3d7" strokeDasharray="3 5"/>
      <XAxis dataKey="x" type="number" domain={[0,1]} name={`Fracción molar de ${nombre}`} tick={{fontSize:11}} label={{value:`x, y · ${nombre} [mol/mol]`,position:'insideBottom',offset:-16,fontSize:11}}/>
      <YAxis dataKey="valor" type="number" domain={['auto','auto']} width={72} name={tipo==='Txy'?'Temperatura':'Presión'} unit={` ${unidad}`} tickFormatter={x=>num(x,5)} tick={{fontSize:11}}/>
      <Tooltip formatter={(valor,nombre)=>[typeof valor==='number'?num(valor):String(valor),String(nombre)]}/>
      {curvas.map(c=><Scatter key={c.id} name={c.fase==='liquido'?'Líquido · x':'Vapor · y'} data={c.puntos} fill={c.fase==='liquido'?'#536844':'#9b7048'} line={{stroke:c.fase==='liquido'?'#536844':'#9b7048',strokeWidth:1.7}} lineType="joint" shape={(props:unknown)=>{const p=props as {cx:number;cy:number};return <circle cx={p.cx} cy={p.cy} r={1.3} fill={c.fase==='liquido'?'#536844':'#9b7048'}/>;}} isAnimationActive={false}/>)}
      {marcadores.puntos.map(p=><Scatter key={p.faseId} name={`Muestra · ${p.tipo} · ${p.faseId}`} data={[p]} fill="#18261d" shape="cross" isAnimationActive={false}/>)}
      {especiales.length>0&&<Scatter name="Azeótropo certificado" data={especiales} fill="#5b626b" shape="diamond" isAnimationActive={false}/>}
    </ScatterChart>}</div>
    <div className={styles.legend}><span><i className={styles.liquid}/>Líquido · x</span><span><i className={styles.vapor}/>Vapor · y</span>{marcadores.puntos.length>0&&<span>+ Muestra</span>}{especiales.length>0&&<span>◆ Azeótropo</span>}</div>
    {marcadores.estado==='otra_condicion'&&<small className={styles.notice}>La muestra pertenece a otra {tipo==='Txy'?'presión':'temperatura'}. Actualiza el corte para compararla.</small>}
    {marcadores.estado==='sin_certificar'&&<small className={styles.notice}>Muestra en un tramo sin certificar; no se superpone.</small>}
    {marcadores.estado==='otro_modelo'&&<small className={styles.notice}>La muestra y el diagrama no identifican el mismo paquete o componentes.</small>}
  </>;
}
