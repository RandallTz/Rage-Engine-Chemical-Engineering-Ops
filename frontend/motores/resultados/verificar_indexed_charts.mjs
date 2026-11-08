// Verify generic chart defaults and exact presentation of fresh Python publications.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(here,'../../package.json'));
const ts=require('typescript'),cache=new Map();
function load(file){
  if(!path.extname(file))file+='.ts';
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('module','exports','require',code)(module,module.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return module.exports;
}
const {defaultChartLayout,readChartLayout,prepareCharts}=load(path.join(here,'chartSpecification'));
const results=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
// Identity conversion isolates presentation; production unit conversion is covered by verificar_result_charts.
globalThis.fetch=async (_url,options)=>{
  const request=JSON.parse(options.body);
  return {ok:true,json:async()=>({format:'rage.chart-data',version:1,resultId:request.resultId,rows:request.requests.map(({kind,id,unit,values,events})=>({kind,id,unit,values,events,dimension:{}}))})};
};
const {defaultChartSummary,DEFAULT_CHART_LIMIT}=load(path.join(here,'chartSpecification'));
for(const mode of ['steady','dynamic']){
  const result=results[mode],layout=defaultChartLayout(result),byId=new Map(result.series.map(row=>[row.id,row]));
  const display=new Map(result.indexedNetwork.display.map(d=>[d.seriesId,d]));
  readChartLayout(layout,{current:result});
  const prepared=await prepareCharts(layout,{current:result});
  assert.ok(prepared.length&&prepared.length<=DEFAULT_CHART_LIMIT,'defaults are a capped subset');
  // C-1: readable labels from the publisher, never raw symbols or hashed identities.
  for(const chart of prepared){
    assert.doesNotMatch(chart.spec.title,/__|\(t\)|Derivative|volume_|stream_/,chart.spec.title);
    for(const trace of chart.traces)assert.doesNotMatch(trace.name,/__|\(t\)|Derivative|volume_|stream_/,trace.name);
  }
  // C-2: temperature first, then liquid and vapour composition; internal and boundary-port groups are not default charts.
  const rankOf=c=>display.get(c.series[0].id).rank;
  assert.deepEqual(layout.charts.map(rankOf),[...layout.charts.map(rankOf)].sort((a,b)=>a-b),'defaults are ranked');
  assert.equal(display.get(layout.charts[0].series[0].id).label,'Temperature');
  assert.ok(layout.charts.slice(0,8).some(c=>/^Liquid mole fraction of /.test(c.title))&&layout.charts.slice(0,8).some(c=>/^Vapour mole fraction of /.test(c.title)));
  assert.ok(layout.charts.every(c=>rankOf(c)<=7),'no internal or port groups by default');
  // C-3: the omitted groups are counted so the interface can say so.
  const summary=defaultChartSummary(result);
  assert.equal(summary.shown,layout.charts.length);assert.ok(summary.available>summary.shown);
  if(mode==='steady'){
    assert.ok(layout.charts.every(c=>result.indexedNetwork.profiles.some(p=>p.seriesId===c.series[0].id)));
    assert.ok(layout.charts.some(c=>c.y.unit==='K')&&layout.charts.some(c=>c.y.unit==='1'));
    for(const phase of ['Liquid','Vapour'])assert.ok(layout.charts.some(c=>c.title.startsWith(phase+' mole fraction of ')),`Missing ${phase} composition profile`);
  }else{
    assert.ok(layout.charts.some(c=>c.y.unit==='K'&&c.series.length===result.indexedNetwork.count));
    assert.ok(layout.charts.some(c=>c.y.unit==='1'&&c.series.length===result.indexedNetwork.count));
  }
  for(const chart of prepared)for(let i=0;i<chart.traces.length;i++){
    const row=byId.get(chart.spec.series[i].id),axis=result.ejes.find(a=>a.id===chart.spec.x.id);
    assert.deepEqual(chart.traces[i].points,axis.valores.map((x,j)=>({x,y:row.valores[j]})));
    if(mode==='dynamic')assert.match(chart.traces[i].name,/Stage [1-9][0-9]*/);
  }
}
// Version 2 results keep their former defaults (every published series, raw names, capped at the layout limit).
for(const mode of ['steady','dynamic']){
  const legacy=structuredClone(results[mode]);delete legacy.indexedNetwork.display;legacy.indexedNetwork.version=2;
  const layout=defaultChartLayout(legacy);readChartLayout(layout,{current:legacy});
  assert.ok(layout.charts.length>DEFAULT_CHART_LIMIT);
}
console.log('Fresh indexed network chart defaults and published samples verified.');
