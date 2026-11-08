import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),ts=require('typescript'),cache=new Map();
function load(file){
  if(!path.extname(file))file+='.ts';
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('module','exports','require',code)(module,module.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return module.exports;
}
const {leerResultados}=load(path.join(here,'motores/resultados/lector'));
const {readChartLayout}=load(path.join(here,'motores/resultados/chartSpecification'));
function readProduced(file,producer){if(!fs.existsSync(file))throw new Error(`Missing ${path.relative(process.cwd(),file)}: produced by ${producer}; run it first.`);return JSON.parse(fs.readFileSync(file,'utf8'));}
const data=readProduced(path.resolve(here,'../.tmp/indexed-results.json'),'tests/test_indexed_results.py');
let checks=0;
for(const result of Object.values(data.valid)){assert.deepEqual(leerResultados(result),result);checks++;}
for(const test of data.invalid){assert.throws(()=>leerResultados(test.result),Error,test.name);checks++;}
const steady=data.valid.steady;
const layout={format:'rage.result-charts',version:1,charts:[{id:'stage-temperature',title:'Temperature by stage',type:'xy',
  x:{kind:'axis',id:'stage-index',unit:'1'},y:{unit:'K'},events:false,
  series:[{source:'current',id:'thermal.temperature'}]}]};
assert.deepEqual(readChartLayout(layout,{current:steady}),layout);checks++;
const legacy=structuredClone(data.valid.dynamic);delete legacy.indexedNetwork;assert.deepEqual(leerResultados(legacy),legacy);checks++;
legacy.indexedNetwork=null;assert.throws(()=>leerResultados(legacy),/indexedNetwork/);checks++;
console.log(`Indexed publication: ${checks} checks passed, including the existing x-y chart reader.`);
if(process.argv.includes('--connected')){
  let connectedChecks=0;
  for(const mode of ['dynamic','steady']){
    const result=readProduced(path.resolve(here,`../.tmp/indexed-${mode}-result.json`),'tests/test_indexed_publication.py');
    assert.deepEqual(leerResultados(result),result);connectedChecks++;
    assert.equal(result.indexedNetwork.mode,mode);connectedChecks++;
    assert.ok(result.verificaciones.every(row=>row.valor<=row.tolerancia));connectedChecks++;
    const temperature=mode==='steady'
      ? result.series.find(row=>row.unidadSI==='K'&&result.indexedNetwork.profiles.some(profile=>profile.seriesId===row.id))
      : result.series.find(row=>row.unidadSI==='K'&&row.id.includes('.closure.'));
    assert.ok(temperature);connectedChecks++;
    const chart={format:'rage.result-charts',version:1,charts:[{
      id:`connected-${mode}`,title:'Connected stage temperature',type:mode==='steady'?'xy':'time_series',
      x:{kind:'axis',id:mode==='steady'?result.indexedNetwork.stageAxisId:'t',unit:mode==='steady'?'1':'s'},
      y:{unit:'K'},events:mode==='dynamic',series:[{source:'current',id:temperature.id}],
    }]};
    assert.deepEqual(readChartLayout(chart,{current:result}),chart);connectedChecks++;
  }
  console.log(`Connected publication: ${connectedChecks} checks passed on actual dynamic and steady samples.`);
}
