'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import type {HojaMotor} from './hojasMotor';
import {balancesHoja} from './seleccionBalances';
import {equationSource} from '../models/modelRequest';
import {readEquationWorkbenchReport,type EquationWorkbenchReport} from '../models/equationWorkbench';
import EquationRows from '../models/EquationRows';
import styles from './ecuacionesFinales.module.css';

/** Solve presents the exact Model graph; no browser formula recipe or fallback. */
export default function EcuacionesFinales({hoja:h}:{hoja:HojaMotor}){
  let source='',preparation='';
  try{source=JSON.stringify(equationSource(h));}catch(error){preparation=(error as Error).message;}
  const [state,setState]=useState<{source:string;report?:EquationWorkbenchReport;error?:string}>();
  useEffect(()=>{
    if(!source)return;
    const controller=new AbortController();
    void fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/equation-workbench`,{
      method:'POST',headers:{'Content-Type':'application/json'},body:source,cache:'no-store',
      signal:AbortSignal.any([controller.signal,AbortSignal.timeout(60000)])
    }).then(async response=>{
      const value=await response.json();
      if(!response.ok)throw new Error(value?.detail?.message??'The current equation graph is unavailable.');
      const report=readEquationWorkbenchReport(value),envelope=JSON.parse(source);
      if(report.modelId!==(envelope.modelo?.id??envelope.solicitudV2?.solicitudId??envelope.draft?.modelId))throw new Error('Unexpected equation source.');
      if(!controller.signal.aborted)setState({source,report});
    }).catch(error=>{if(!controller.signal.aborted)setState({source,error:(error as Error).message});});
    return()=>controller.abort();
  },[source]);
  const current=state?.source===source?state:undefined,b=balancesHoja(h);
  const active={matter:b.materia,energy:b.energia,momentum:b.momento,thermodynamics:true};
  const error=preparation||current?.error;
  return <section className={styles.paper} aria-label="Final equations">
    <header className={styles.heading}><h2>Final equations</h2><Link href={`/models/${h.id}/model`}>View derivation →</Link></header>
    {error&&<p role="alert">{error} Review Model; no earlier equations have been substituted.</p>}
    {!current&&!error&&<p role="status">Reading the current Model equations…</p>}
    {current?.report?.replay&&<p role="alert">The saved equation history needs review. The valid source remains visible; numerical execution is blocked.</p>}
    {current?.report&&<EquationRows label="Final physical equations" steps={current.report.equations.filter(row=>row.current&&active[row.family])}/>}
  </section>;
}
