// Verify the runTimeline v1 reader agrees with the Python verdicts and charts a repeated time at an action.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(here,'../../package.json'));
const ts=require('typescript'),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  new Function('module','exports','require',code)(module,module.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return module.exports;
}
const {leerResultados}=load(path.join(here,'lector'));
const {defaultChartLayout,prepareCharts}=load(path.join(here,'chartSpecification'));
const cases=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
let checks=0;
for(const [name,c] of Object.entries(cases)){
  const copy=JSON.parse(JSON.stringify(c.result));
  if(c.ts)assert.doesNotThrow(()=>leerResultados(copy),name);
  else assert.throws(()=>leerResultados(copy),/runTimeline/,name);
  checks++;
}
// The JSON round trip keeps the timeline, and the existing chart path plots the repeated time with both values.
const result=leerResultados(JSON.parse(JSON.stringify(cases.completed.result)));
assert.equal(result.procedencia.runTimeline.actions.length,2);checks++;
globalThis.fetch=async (_url,options)=>{
  const request=JSON.parse(options.body);
  return {ok:true,json:async()=>({format:'rage.chart-data',version:1,resultId:request.resultId,rows:request.requests.map(({kind,id,unit,values,events})=>({kind,id,unit,values,events,dimension:{}}))})};
};
const layout=defaultChartLayout(result);
const prepared=await prepareCharts(layout,{current:result});
const chart=prepared.find(p=>p.traces[0].points.length===result.ejes[0].valores.length);
assert.ok(chart,'time series chart present');
const points=chart.traces[0].points;
assert.deepEqual(points.map(p=>p.x),result.ejes[0].valores);
assert.deepEqual(points.map(p=>p.y),result.series[0].valores);
assert.equal(points.filter(p=>p.x===2).length,2);assert.equal(points.filter(p=>p.x===3).length,2);
assert.equal(chart.events.filter(e=>e.codigo==='timeline_action').length,2);checks+=4;
console.log(`${checks} run-timeline checks passed`);
