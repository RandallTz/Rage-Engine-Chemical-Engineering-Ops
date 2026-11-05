// Real common Python publication: strict contracts, shared lifecycle and scalar export.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.json'))return {default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(loadedModule,loadedModule.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return loadedModule.exports;
}
const {readChartLayout,readChartReference,defaultChartLayout,prepareCharts}=load(path.join(here,'motores/resultados/chartSpecification'));
const {PreparedResultCharts}=load(path.join(here,'app/motor/ResultCharts'));
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),Recharts=require('recharts');
function elements(node,type){if(!node||typeof node!=='object')return [];if(Array.isArray(node))return node.flatMap(n=>elements(n,type));return [...(node.type===type?[node]:[]),...elements(node.props?.children,type)];}
const output=path.join(root,'.tmp/demo02-app-results');let checks=0;const evidence=[];
assert.equal(readChartLayout(undefined),undefined);checks++;
const baseRequest={format:'rage.chart-data.request',version:1,resultId:'unit-reference',requests:[{kind:'series',id:'temperature',unit:'degC',sourceUnit:'K',values:[273.15,null,373.15],events:[]}]};
for(const mutate of [v=>v.version=2,v=>v.extra=true,v=>v.requests[0].extra=true,v=>v.requests[0].kind='mesh',v=>v.requests[0].values=[[1]],v=>v.requests[0].values=[true],v=>v.requests[0].unit='m',v=>v.requests.push(v.requests[0])]){
 const bad=structuredClone(baseRequest);mutate(bad);const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL}/modelo/chart-data`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bad)});assert.equal(response.status,422);checks++;
}
const convertedResponse=await fetch(`${process.env.NEXT_PUBLIC_API_URL}/modelo/chart-data`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(baseRequest)});assert.equal(convertedResponse.status,200);assert.deepEqual((await convertedResponse.json()).rows[0].values,[0,null,100]);checks+=2;

assert.throws(()=>readChartLayout([{tipo:'tiempo',x:'t',y:['T']}]));checks++;
for(const [demo,file] of [['0.1','flash-drum'],['0.2','flash-drum'],['0.1','batch-reactor']]){
 const current=JSON.parse(fs.readFileSync(path.join(output,`demo-${demo}-${file}-dynamic.json`),'utf8'));
 const reference=file==='flash-drum'?JSON.parse(fs.readFileSync(path.join(output,`demo-${demo}-${file}-steady.json`),'utf8')):undefined;
 const sources={current,reference},layout=defaultChartLayout(current);
 const fixture=JSON.parse(fs.readFileSync(path.join(root,`docs/ejemplos/demo-${demo}/${file}.rage-model.json`),'utf8')).model;
 const {firmaHoja}=load(path.join(here,'app/motor/modeloHojaMotor'));
 assert.equal(firmaHoja({...fixture,resultCharts:layout,chartReference:{version:1,result:current}}),firmaHoja(fixture));checks++;
 assert.deepEqual(readChartLayout(JSON.parse(JSON.stringify(layout))),layout);checks++;
 const c=layout.charts[0];c.x.unit='min';c.y.unit='degC';
 if(reference)c.series.push({source:'reference',id:reference.series.find(s=>s.unidadSI==='K').id});
 const original=structuredClone(current);
 readChartLayout(layout,sources);checks++;
 for(const mutate of [v=>v.version=2,v=>v.extra=true,v=>v.charts[0].extra=true,v=>v.charts[0].type='mesh',v=>v.charts[0].series[0].id='absent',v=>v.charts[0].series[0].source='absent',v=>v.charts[0].y.extra=true,v=>v.charts[0].x.kind='mesh',v=>v.charts.push(structuredClone(v.charts[0])),v=>v.charts[0].series.push(v.charts[0].series[0]),v=>delete v.charts[0].events,v=>v.charts[0].title='',v=>v.charts[0].series=[],v=>v.charts[0].events='yes',v=>v.charts[0].type='bar',v=>v.charts[0].x.kind='series']){const bad=structuredClone(layout);mutate(bad);assert.throws(()=>readChartLayout(bad,sources));checks++;}
 const prepared=await prepareCharts(layout,sources);checks++;
 const temp=current.series.find(s=>s.id===c.series[0].id).valores;
 assert.ok(Math.abs(prepared[0].traces[0].points.at(-1).y-(temp.at(-1)-273.15))<1e-8);checks++;
 assert.ok(Math.abs(prepared[0].traces[0].points.at(-1).x-current.ejes[0].valores.at(-1)/60)<1e-8);checks++;
 if(reference){assert.equal(prepared[0].traces[1].points.length,2);assert.ok(prepared[0].events.some(e=>e.codigo==='aparicion_fase'));checks+=2;}
 const html=renderToStaticMarkup(React.createElement(PreparedResultCharts,{charts:prepared}));assert.ok(html.includes('Versioned result charts')&&html.includes('degC'));checks++;
 const tree=PreparedResultCharts({charts:prepared}),lines=elements(tree,Recharts.Line);assert.equal(lines.length,prepared[0].traces.length);assert.deepEqual(lines.map(line=>line.props.data),prepared[0].traces.map(t=>t.points));checks+=2;
 assert.equal(elements(tree,Recharts.ReferenceLine).length,prepared[0].events.length);checks++;
 if(reference){assert.ok(html.includes('vapor-1 appears'));checks++;}
 for(const type of ['bar','table']){
   const spec={format:'rage.result-charts',version:1,charts:[{id:type,title:type,type,series:[{source:'current',id:c.series[0].id}],y:{unit:'K'},events:false}]};
   const chart=await prepareCharts(spec,sources);assert.ok(renderToStaticMarkup(React.createElement(PreparedResultCharts,{charts:chart})).includes(type));checks++;
 }
 const dimensionless=current.series.filter(s=>s.unidadSI==='1'&&s.ejes.length===1);
 if(file==='flash-drum'){
   const liquid=dimensionless.find(s=>/phase_x_1__.*__L/.test(s.nombre)),vapour=dimensionless.find(s=>/phase_x_1__.*__V/.test(s.nombre));
   assert.ok(liquid&&vapour,'Liquid and vapour compositions must be published');checks++;
   for(const type of ['parametric','xy']){
     const phase={format:'rage.result-charts',version:1,charts:[{id:type,title:'Liquid versus vapour composition',type,x:{kind:'series',id:liquid.id,unit:'1'},y:{unit:'1'},series:[{source:'current',id:vapour.id}],events:false}]};
     const chart=await prepareCharts(phase,sources);assert.deepEqual(chart[0].traces[0].points.map(p=>p.x),liquid.valores);assert.deepEqual(chart[0].traces[0].points.map(p=>p.y),vapour.valores);assert.ok(renderToStaticMarkup(React.createElement(PreparedResultCharts,{charts:chart})).includes('Liquid versus vapour composition'));checks+=3;
   }
 }
 const badUnit=structuredClone(layout);badUnit.charts[0].y.unit='m';await assert.rejects(()=>prepareCharts(badUnit,sources));checks++;
 const badMarkers=structuredClone(layout);badMarkers.charts[0].type='xy';assert.throws(()=>readChartLayout(badMarkers,sources));checks++;
 readChartReference({version:1,result:current});checks++;
 assert.throws(()=>readChartReference({version:2,result:current}));checks++;
 const missingReference=structuredClone(layout);missingReference.charts[0].series=[{source:'reference',id:c.series[0].id}];assert.throws(()=>readChartLayout(missingReference,{current}));checks++;
 const noEvents=structuredClone(layout);noEvents.charts[0].events=false;const quiet=await prepareCharts(noEvents,sources);assert.equal(quiet[0].events.length,0);checks++;
 assert.deepEqual(current,original);checks++;
 evidence.push({demo,file,events:prepared[0].events.length,overlay:!!reference});
}
console.log(JSON.stringify({checks,evidence},null,2));
