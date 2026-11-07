'use client';

import {useRef,useState} from 'react';
import type {HojaMotor} from '../motor/hojasMotor';
import {CLAVE_HOJAS,guardarHoja,leerHojas} from '../motor/hojasMotor';
import type {ModeloComun} from '../../motores/modelo/contrato';
import {canonical,executableSource,type FlowsheetEndpoint,type FlowsheetLayout} from '../../motores/modelo/flowsheet';
import {responseError,type Diagnostic} from '../../motores/modelo/assessment';

type Point=[number,number];
const point=(model:ModeloComun,id:string,index:number):Point=>model.flowsheetLayout?.blocks[id]?.position??[30+(index%2)*220,35+Math.floor(index/2)*125];
export function moveFlowsheetBlock(model:ModeloComun,id:string,position:Point):ModeloComun{
  const sheet=model.flowsheet;
  if(!sheet?.instances.some(row=>row.id===id)||!position.every(Number.isFinite))throw new Error('Invalid block position.');
  const layout:FlowsheetLayout=model.flowsheetLayout?structuredClone(model.flowsheetLayout):{format:'rage.flowsheet-layout',version:1,flowsheetId:sheet.id,blocks:{}};
  layout.blocks[id]={position};
  return {...model,flowsheetLayout:layout};
}
export function moveStoredFlowsheetBlock(rows:HojaMotor[],modelId:string,id:string,position:Point):HojaMotor[]{
  return rows.map(row=>row.id===modelId&&row.commonModel?.flowsheet?{...row,commonModel:moveFlowsheetBlock(row.commonModel,id,position)}:row);
}
export function connectionDiagnostics(diagnostics:Diagnostic[],id:string){
  const path=`flowsheet.connections.${id}`;
  return diagnostics.filter(row=>row.path===path||row.path.startsWith(path+'.'));
}
export function unplacedDiagnostics(diagnostics:Diagnostic[],connectionIds:string[]){
  return diagnostics.filter(diagnostic=>!connectionIds.some(id=>connectionDiagnostics([diagnostic],id).length>0));
}
const endpointKey=(p:FlowsheetEndpoint)=>JSON.stringify([p.instance,p.port]);

/** The diagram edits the common topology; all physical admission remains in Python. */
export default function FlowsheetDiagram({model,initialDiagnostics=[]}:{model:HojaMotor;initialDiagnostics?:Diagnostic[]}){
  const common=model.commonModel!,sheet=common.flowsheet!;
  const [diagnostics,setDiagnostics]=useState<Diagnostic[]>(initialDiagnostics),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const [preview,setPreview]=useState<ModeloComun>(),[moving,setMoving]=useState<{id:string;position:Point}>();
  const [from,setFrom]=useState(''),[to,setTo]=useState(''),[connectionId,setConnectionId]=useState('');
  const [template,setTemplate]=useState(''),[instanceId,setInstanceId]=useState('');
  const svg=useRef<SVGSVGElement>(null),drag=useRef<{id:string;offset:Point}|null>(null);
  const proposed=preview?.flowsheet;
  const visible=proposed?{...proposed,connections:[...proposed.connections,...sheet.connections.filter(row=>!proposed.connections.some(item=>item.id===row.id)&&connectionDiagnostics(diagnostics,row.id).length>0)]}:sheet;
  const positions=Object.fromEntries(visible.instances.map((row,i)=>[row.id,moving?.id===row.id?moving.position:point(common,row.id,i)]));
  const width=Math.max(480,...Object.values(positions).map(p=>p[0]+190)),height=Math.max(220,...Object.values(positions).map(p=>p[1]+110));
  function savePosition(id:string,position:Point){
    const rows=leerHojas(),latest=rows.find(row=>row.id===model.id);
    if(!latest?.commonModel?.flowsheet)return;
    localStorage.setItem(CLAVE_HOJAS,JSON.stringify(moveStoredFlowsheetBlock(rows,model.id,id,position)));
    window.dispatchEvent(new Event('motor-hojas'));
  }
  function svgPoint(event:{clientX:number;clientY:number}):Point{
    const box=svg.current!.getBoundingClientRect();return [(event.clientX-box.left)*width/box.width,(event.clientY-box.top)*height/box.height];
  }
  async function submit(next:ModeloComun){
    setBusy(true);setMessage('');setDiagnostics([]);
    const source=canonical(executableSource(common));
    try{
      const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/flowsheet-expansion`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format:'rage.flowsheet-expansion.request',version:1,model:next}),cache:'no-store',signal:AbortSignal.timeout(3600000)});
      const body=await response.json();if(!response.ok)throw responseError(body,response.status,'The topology was rejected.');
      const latest=leerHojas().find(row=>row.id===model.id);
      if(!latest?.commonModel||canonical(executableSource(latest.commonModel))!==source)throw new Error('The model changed; the proposed topology was discarded.');
      // Preserve a concurrent presentation-only move, but remove layout entries for deleted connections.
      const layout=latest.commonModel.flowsheetLayout?structuredClone(latest.commonModel.flowsheetLayout):undefined;
      if(layout?.streams)for(const id of Object.keys(layout.streams))if(!next.flowsheet!.connections.some(row=>row.id===id))delete layout.streams[id];
      guardarHoja({...latest,commonModel:{...next,...(layout?{flowsheetLayout:layout}:{})},indexedSelection:undefined,derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined,chartReference:undefined});
      setPreview(undefined);setMessage('Topology validated by Python and saved. Prepare the formulation again in Transform.');
    }catch(error){const failure=error as Error & {diagnostics?:Diagnostic[]};setDiagnostics(failure.diagnostics??[]);setPreview(next);setMessage(failure.message);}
    finally{setBusy(false);}
  }
  const available=sheet.exposures.flatMap(exposure=>{
    const instance=sheet.instances.find(row=>row.id===exposure.instance),port=instance&&sheet.templates[instance.template].template?.ports.find(p=>p.id===exposure.port);
    return port?.kind==='material'?[{...exposure,direction:port.direction}]:[];
  });
  function connect(){
    const a=available.find(p=>endpointKey(p)===from),b=available.find(p=>endpointKey(p)===to);
    if(!a||!b||!connectionId)return;
    const next=structuredClone(common),s=next.flowsheet!;
    s.connections.push({id:connectionId,from:{instance:a.instance,port:a.port},to:{instance:b.instance,port:b.port}});
    s.exposures=s.exposures.filter(p=>p.id!==a.id&&p.id!==b.id);void submit(next);
  }
  function disconnect(id:string){
    const next=structuredClone(common),s=next.flowsheet!,link=s.connections.find(row=>row.id===id);if(!link)return;
    s.connections=s.connections.filter(row=>row.id!==id);s.recycles=s.recycles.filter(row=>row!==id);
    const used=new Set([...s.connections.map(row=>row.id),...s.exposures.map(row=>row.id)]);
    for(const [i,end] of [link.from,link.to].entries()){let name=`exposed_${id}_${i+1}`,n=1;while(used.has(name))name=`exposed_${id}_${i+1}_${n++}`;used.add(name);s.exposures.push({id:name,...end});}
    if(next.flowsheetLayout?.streams)delete next.flowsheetLayout.streams[id];void submit(next);
  }
  function addInstance(){
    if(!sheet.templates[template]||!instanceId)return;
    const next=structuredClone(common),s=next.flowsheet!;s.instances.push({id:instanceId,template,data:{}});
    const used=new Set([...s.connections.map(row=>row.id),...s.exposures.map(row=>row.id)]);
    for(const [i,port] of s.templates[template].template!.ports.entries()){let id=`exposed_${instanceId}_${i+1}`,n=1;while(used.has(id))id=`exposed_${instanceId}_${i+1}_${n++}`;used.add(id);s.exposures.push({id,instance:instanceId,port:port.id});}
    void submit(next);
  }
  return <details open><summary>Process topology</summary>
    <p>Drag a block to arrange the diagram. Connections and instances are validated by Python; positions do not change the formulation.</p>
    <div style={{overflowX:'auto',maxWidth:'100%'}}><svg ref={svg} role="group" aria-label="Process topology diagram" viewBox={`0 0 ${width} ${height}`} style={{width:'100%',minWidth:480,background:'#f8fafb',touchAction:'none'}}
      onPointerMove={event=>{if(!drag.current)return;const p=svgPoint(event);setMoving({id:drag.current.id,position:[Math.max(0,p[0]-drag.current.offset[0]),Math.max(0,p[1]-drag.current.offset[1])]});}}
      onPointerUp={event=>{if(drag.current&&moving)savePosition(moving.id,moving.position);drag.current=null;setMoving(undefined);if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);}} onPointerCancel={()=>{drag.current=null;setMoving(undefined);}}>
      {visible.connections.map(link=>{const a=positions[link.from.instance],b=positions[link.to.instance];if(!a||!b)return null;const issues=connectionDiagnostics(diagnostics,link.id);return <g key={link.id} data-connection-id={link.id} data-diagnostic={issues.length?'true':'false'}><line x1={a[0]+150} y1={a[1]+35} x2={b[0]} y2={b[1]+35} stroke={issues.length?'#b42318':'#335c70'} strokeWidth={issues.length?4:2}/><text x={(a[0]+150+b[0])/2} y={(a[1]+b[1])/2+28} fontSize="11">{link.id}</text><title>{`${link.from.instance}.${link.from.port} → ${link.to.instance}.${link.to.port}${issues.map(d=>` · ${d.message}`).join('')}`}</title></g>;})}
      {visible.instances.map(row=>{const [x,y]=positions[row.id],stored=sheet.instances.some(item=>item.id===row.id);return <g key={row.id} data-instance-id={row.id} role="button" tabIndex={stored?0:-1} aria-label={`Move ${row.id} with arrow keys`} transform={`translate(${x} ${y})`} onKeyDown={event=>{const delta:Record<string,Point>={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]};if(stored&&delta[event.key]){event.preventDefault();const [dx,dy]=delta[event.key];savePosition(row.id,[Math.max(0,x+dx),Math.max(0,y+dy)]);}}} onPointerDown={event=>{if(!stored)return;const p=svgPoint(event);drag.current={id:row.id,offset:[p[0]-x,p[1]-y]};svg.current?.setPointerCapture(event.pointerId);}} style={{cursor:'move'}}><rect width="150" height="70" rx="5" fill="white" stroke="#335c70"/><text x="10" y="27" fontSize="13">{row.id}</text><text x="10" y="48" fontSize="11">{row.template}</text><title>{`${row.id} · ${row.template}`}</title></g>;})}
    </svg></div>
    {preview&&<p>Proposed topology was not saved. <button onClick={()=>{setPreview(undefined);setDiagnostics([]);setMessage('');}}>Discard proposal</button></p>}
    <ul>{visible.connections.map(link=><li key={link.id}>{link.id}: {link.from.instance}.{link.from.port} → {link.to.instance}.{link.to.port} {!preview&&<button disabled={busy} onClick={()=>disconnect(link.id)}>Disconnect</button>}{connectionDiagnostics(diagnostics,link.id).map((d,i)=><p role="alert" key={i}>{d.code}: {d.message}</p>)}</li>)}</ul>
    <fieldset disabled={busy}><legend>Connect exposed material ports</legend><label>Connection ID <input value={connectionId} onChange={e=>setConnectionId(e.target.value)}/></label><label>Outlet <select value={from} onChange={e=>setFrom(e.target.value)}><option value="">Select outlet</option>{available.filter(p=>p.direction==='outlet').map(p=><option key={p.id} value={endpointKey(p)}>{p.instance}.{p.port}</option>)}</select></label><label>Inlet <select value={to} onChange={e=>setTo(e.target.value)}><option value="">Select inlet</option>{available.filter(p=>p.direction==='inlet').map(p=><option key={p.id} value={endpointKey(p)}>{p.instance}.{p.port}</option>)}</select></label><button disabled={!connectionId||!from||!to} onClick={connect}>Validate and connect</button></fieldset>
    <fieldset disabled={busy}><legend>Add an instance from an embedded template</legend><label>Instance ID <input value={instanceId} onChange={e=>setInstanceId(e.target.value)}/></label><label>Template <select value={template} onChange={e=>setTemplate(e.target.value)}><option value="">Select template</option>{Object.keys(sheet.templates).map(id=><option key={id}>{id}</option>)}</select></label><button disabled={!instanceId||!template} onClick={addInstance}>Validate and add</button></fieldset>
    {busy&&<p role="status">Validating topology in Python…</p>}{message&&<p role="status">{message}</p>}
    {unplacedDiagnostics(diagnostics,visible.connections.filter(link=>positions[link.from.instance]&&positions[link.to.instance]).map(link=>link.id)).map((diagnostic,index)=><p role="alert" key={`${diagnostic.path}:${index}`}>{diagnostic.code} · {diagnostic.path}: {diagnostic.message}</p>)}
  </details>;
}
