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
for(const mode of ['steady','dynamic']){
  const result=results[mode],layout=defaultChartLayout(result),byId=new Map(result.series.map(row=>[row.id,row]));
  readChartLayout(layout,{current:result});
  const prepared=await prepareCharts(layout,{current:result});
  assert.ok(prepared.length);
  if(mode==='steady'){
    assert.deepEqual(layout.charts.map(c=>c.series[0].id),result.indexedNetwork.profiles.map(p=>p.seriesId));
    assert.ok(layout.charts.some(c=>c.y.unit==='K'));
    assert.ok(layout.charts.some(c=>c.y.unit==='1'));
    for(const phase of ['L','V'])assert.ok(layout.charts.some(c=>/phase_x_/.test(byId.get(c.series[0].id).nombre)&&byId.get(c.series[0].id).nombre.includes(`__${phase}(`)),`Missing ${phase} composition profile`);
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
console.log('Fresh indexed network chart defaults and published samples verified.');
