import type {ConjuntoResultados,Evento} from './contrato';
import {leerResultados} from './lector';
import {responseError} from '../modelo/assessment';

export type ChartSources={current:ConjuntoResultados;reference?:ConjuntoResultados};
export type ChartSpec={id:string;title:string;type:'time_series'|'xy'|'parametric'|'bar'|'table';
  series:{source:'current'|'reference';id:string}[];x?:{kind:'axis'|'series';id:string;unit:string};y:{unit:string};events:boolean};
export type ChartLayout={format:'rage.result-charts';version:1;charts:ChartSpec[]};
export type ChartReference={version:1;result:ConjuntoResultados};
const fail=(message:string):never=>{throw new Error('Result charts: '+message);};
function keys(value:unknown,required:string[],optional:string[]=[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))return fail('Expected an object.');
  const v=value as Record<string,unknown>;if(required.some(k=>!Object.hasOwn(v,k))||Object.keys(v).some(k=>!required.includes(k)&&!optional.includes(k)))fail('Unknown or missing fields.');return v;
}
const text=(v:unknown)=>{if(typeof v!=='string'||!v.trim())fail('Nonempty text required.');};
export function readChartReference(value:unknown):ChartReference|undefined{
  if(value===undefined)return undefined;const r=keys(value,['version','result']);
  if(r.version!==1)fail('Unsupported overlay reference version.');leerResultados(r.result);return value as ChartReference;
}
export function readChartLayout(value:unknown,sources?:ChartSources):ChartLayout|undefined{
  if(value===undefined)return undefined; // Existing graficas remains its own unchanged contract.
  const v=keys(value,['format','version','charts']);
  if(v.format!=='rage.result-charts'||v.version!==1||!Array.isArray(v.charts)||v.charts.length>100)fail('Unsupported chart layout version.');
  const layout=value as ChartLayout,ids=new Set<string>();
  if(sources){leerResultados(sources.current);if(sources.reference)leerResultados(sources.reference);}
  for(const c of layout.charts){
    keys(c,['id','title','type','series','y','events'],['x']);text(c.id);text(c.title);
    if(ids.has(c.id))fail('Duplicate chart identity.');ids.add(c.id);
    if(!['time_series','xy','parametric','bar','table'].includes(c.type)||typeof c.events!=='boolean'||!Array.isArray(c.series)||!c.series.length||c.series.length>100)fail('Invalid chart type, events or series.');
    keys(c.y,['unit']);text(c.y.unit);
    const plotted=['time_series','xy','parametric'].includes(c.type);
    if(plotted!==!!c.x)fail('Only line/phase plots require an x axis.');
    if(c.events&&c.type!=='time_series')fail('Event markers require a time axis.');
    if(c.x){keys(c.x,['kind','id','unit']);text(c.x.id);text(c.x.unit);if(!['axis','series'].includes(c.x.kind)||c.type==='time_series'&&c.x.kind!=='axis'||c.type==='parametric'&&c.x.kind!=='series')fail('Invalid x-axis selection.');}
    const seen=new Set<string>();let dynamic=false;
    for(const ref of c.series){
      keys(ref,['source','id']);text(ref.id);if(!['current','reference'].includes(ref.source))fail('Unknown result source.');
      const key=JSON.stringify(ref);if(seen.has(key))fail('Duplicate series selection.');seen.add(key);
      if(!sources)continue;
      const result=sources[ref.source];if(!result)fail('The explicit overlay reference is unavailable.');
      const row=result!.series.find(s=>s.id===ref.id);if(!row||row.ejes.length>1||row.ejes.some(id=>result!.ejes.find(a=>a.id===id)?.rol==='coordenada'))fail('Unknown or spatial series; meshes are deferred.');
      if(!c.x)continue;
      if(!row!.ejes.length){if(c.type!=='time_series')fail('Only time plots admit a scalar steady overlay.');continue;}
      dynamic=true;
      const x=c.x.kind==='axis'?result!.ejes.find(a=>a.id===c.x!.id):result!.series.find(a=>a.id===c.x!.id);
      if(!x||!Array.isArray(x.valores)||x.valores.length!==(row!.valores as unknown[]).length)fail('X and Y require aligned published samples.');
      const matched=x!;
      if(c.x.kind==='axis'&&(row!.ejes[0]!==matched.id||('rol' in matched&&matched.rol==='coordenada')))fail('Spatial or unaligned axis.');
      if(c.type==='time_series'&&(!('rol' in matched)||matched.rol!=='tiempo'))fail('Expected the published time axis.');
      if(c.x.kind==='series'&&(!('ejes' in matched)||matched.ejes.length!==1||matched.ejes[0]!==row!.ejes[0]))fail('Phase plots require the same sample axis.');
    }
    if(sources&&plotted&&!dynamic)fail('A line plot needs a sampled result; use bar/table for a standalone steady result.');
  }
  return layout;
}
export function defaultChartLayout(result:ConjuntoResultados):ChartLayout{
  const network=result.indexedNetwork;
  if(network){
    const rows=new Map(result.series.map(row=>[row.id,row]));
    const charts:ChartSpec[]=[];
    if(network.mode==='steady'){
      for(const profile of network.profiles){
        const row=rows.get(profile.seriesId)!;
        charts.push({id:`profile-${charts.length+1}`,title:row.nombre,type:'xy',x:{kind:'axis',id:network.stageAxisId!,unit:'1'},y:{unit:row.unidadSI},events:false,series:[{source:'current',id:row.id}]});
      }
    }else{
      const groups=new Map<string,{axis:string;unit:string;title:string;ids:string[]}>();
      for(const stage of network.stages)for(const id of stage.seriesIds){
        const row=rows.get(id)!;
        const axis=result.ejes.find(a=>a.id===row.ejes[0]&&a.rol==='tiempo');
        if(!axis||row.ejes.length!==1)continue;
        const key=JSON.stringify([id.slice(stage.ownerId.length+1),axis.id,row.unidadSI]);
        const group=groups.get(key)??{axis:axis.id,unit:row.unidadSI,title:row.nombre,ids:[]};
        group.ids.push(id);groups.set(key,group);
      }
      for(const group of groups.values())for(let offset=0;offset<group.ids.length;offset+=100){
        const axis=result.ejes.find(a=>a.id===group.axis)!;
        charts.push({id:`stages-${charts.length+1}`,title:group.title,type:'time_series',x:{kind:'axis',id:axis.id,unit:axis.unidadSI},y:{unit:group.unit},events:true,series:group.ids.slice(offset,offset+100).map(id=>({source:'current',id}))});
      }
    }
    if(charts.length)return {format:'rage.result-charts',version:1,charts:charts.slice(0,100)};
  }
  const series=result.series.find(s=>s.unidadSI==='K'&&s.ejes.length<=1)??result.series.find(s=>s.ejes.length<=1);
  if(!series)return {format:'rage.result-charts',version:1,charts:[]};
  const axis=result.ejes.find(a=>a.id===series.ejes[0]&&a.rol==='tiempo');
  return {format:'rage.result-charts',version:1,charts:[{id:'published-values',title:series.nombre,type:axis?'time_series':'table',series:[{source:'current',id:series.id}],...(axis?{x:{kind:'axis' as const,id:axis.id,unit:axis.unidadSI}}:{}),y:{unit:series.unidadSI},events:!!axis}]};
}
export type PreparedChart={spec:ChartSpec;traces:{name:string;points:{x:number|null;y:number|null}[]}[];events:Evento[]};
type Converted={kind:'axis'|'series';id:string;unit:string;values:number|null|(number|null)[];events:Evento[]};
export async function prepareCharts(layout:ChartLayout,sources:ChartSources,signal?:AbortSignal):Promise<PreparedChart[]>{
  readChartLayout(layout,sources);const prepared:PreparedChart[]=[];
  for(const spec of layout.charts){
    const traces:PreparedChart['traces']=[],events:Evento[]=[];
    for(const ref of spec.series){
      const result=sources[ref.source]!,row=result.series.find(s=>s.id===ref.id)!;
      const raw=[{kind:'series' as const,id:ref.id,unit:spec.y.unit},...(spec.x&&row.ejes.length?[{...spec.x}]:[])];
      const requests=raw.filter((r,i)=>raw.findIndex(v=>JSON.stringify(v)===JSON.stringify(r))===i);
      const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/chart-data`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format:'rage.chart-data.request',version:1,resultId:result.id,requests:requests.map(r=>{const selected=(r.kind==='axis'?result.ejes:result.series).find(v=>v.id===r.id)!;return {...r,sourceUnit:selected.unidadSI,values:selected.valores,events:r.kind==='axis'?result.eventos.filter(e=>e.ejeId===r.id):[]};})}),signal});
      const value=await response.json();if(!response.ok)throw responseError(value,response.status,'Chart data rejected.');
      keys(value,['format','version','resultId','rows']);
      if(value.format!=='rage.chart-data'||value.version!==1||value.resultId!==result.id||!Array.isArray(value.rows)||value.rows.length!==requests.length)fail('Invalid converted chart data.');
      const rows=value.rows as Converted[];
      rows.forEach((r,i)=>{
        keys(r,['kind','id','unit','dimension','values','events']);
        if(r.kind!==requests[i].kind||r.id!==requests[i].id||r.unit!==requests[i].unit||!Array.isArray(r.events))fail('Converted data selection mismatch.');
        const original=(r.kind==='axis'?result.ejes:result.series).find(v=>v.id===r.id)!;
        if(Array.isArray(original.valores)!==Array.isArray(r.values)||Array.isArray(original.valores)&&original.valores.length!==(r.values as unknown[]).length)fail('Converted sample shape mismatch.');
        const values=Array.isArray(r.values)?r.values:[r.values];if(values.some(v=>v!==null&&(typeof v!=='number'||!Number.isFinite(v))))fail('Invalid converted values.');
        const originalValues=Array.isArray(original.valores)?original.valores:[original.valores];if(values.some((v,j)=>(v===null)!==(originalValues[j]===null)))fail('Converted data changed undefined samples.');
        const expectedEvents=r.kind==='axis'?result.eventos.filter(e=>e.ejeId===r.id):[];
        if(r.events.length!==expectedEvents.length)fail('Converted event count mismatch.');
        r.events.forEach((e,j)=>{keys(e,['codigo','ejeId','valor','descripcion'],['propietarioId']);const expected=expectedEvents[j];if(!Number.isFinite(e.valor)||e.codigo!==expected.codigo||e.ejeId!==expected.ejeId||e.descripcion!==expected.descripcion||e.propietarioId!==expected.propietarioId)fail('Converted event metadata mismatch.');});
      });
      const values=Array.isArray(rows[0].values)?rows[0].values:[rows[0].values];
      const xRow=raw[1]?rows.find(r=>r.kind===raw[1].kind&&r.id===raw[1].id&&r.unit===raw[1].unit):undefined;
      const xs=xRow?.values as number[]|undefined;
      const stage=result.indexedNetwork?.stages.find(s=>s.seriesIds.includes(row.id));
      traces.push({name:`${ref.source} · ${stage?`Stage ${stage.index} · `:''}${row.nombre}`,points:values.map((y,i)=>({x:xs?xs[i]:i,y}))});
      if(spec.events&&xRow)events.push(...xRow.events);
    }
    if(spec.type==='time_series'){
      const sampled=traces.filter((_,i)=>sources[spec.series[i].source]!.series.find(s=>s.id===spec.series[i].id)!.ejes.length);
      const xs=sampled.flatMap(t=>t.points.map(p=>p.x)).filter((x):x is number=>x!==null);
      traces.forEach((t,i)=>{if(!sources[spec.series[i].source]!.series.find(s=>s.id===spec.series[i].id)!.ejes.length)t.points=[{x:xs.reduce((a,b)=>Math.min(a,b),Infinity),y:t.points[0].y},{x:xs.reduce((a,b)=>Math.max(a,b),-Infinity),y:t.points[0].y}];});
    }
    prepared.push({spec,traces,events:[...new Map(events.map(e=>[JSON.stringify(e),e])).values()]});
  }
  return prepared;
}
