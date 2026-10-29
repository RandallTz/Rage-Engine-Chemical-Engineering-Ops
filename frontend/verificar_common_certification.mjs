// The common reader preserves physical evidence independently of solve status.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url));
const cache=new Map();
function load(filename){
  const file=filename.endsWith('.ts')?filename:filename+'.ts';
  if(cache.has(file))return cache.get(file);
  const loaded={exports:{}};cache.set(file,loaded.exports);
  const compiled=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('module','exports','require',compiled)(loaded,loaded.exports,name=>load(path.resolve(path.dirname(file),name)));
  return loaded.exports;
}
const {leerResultados}=load(path.join(here,'motores/resultados/lector.ts'));
const script=`
import sys,json,copy
sys.path.insert(0,'tests')
from test_common_admission import model
from core.compilador import resolver
value=model(horizon='1')
plain=resolver(value)
value['datos']['boundary.temperature']=copy.deepcopy(value['datos']['volumen.A.T0'])
value['datos']['boundary.temperature']['declaracion']['texto']='100'
value['intercambios'][0]['temperaturaFronteraId']='boundary.temperature'
print(json.dumps([plain,resolver(value)]))
`;
const processResult=spawnSync('python',['-c',script],{cwd:path.resolve(here,'..'),encoding:'utf8',maxBuffer:16*1024*1024});
assert.equal(processResult.status,0,processResult.stderr);
const [plain,failed]=JSON.parse(processResult.stdout);
for(const value of [plain,failed])assert.equal(leerResultados(value),value);
assert.equal(plain.estado,'resuelto');assert.equal(plain.procedencia.physicalCertification.estado,'no_evaluable');
assert.equal(failed.estado,'resuelto');assert.equal(failed.procedencia.physicalCertification.estado,'no_cumple');
const corruptions=[
  value=>value.procedencia.physicalCertification.estado='cumple',
  value=>value.procedencia.equilibrium.certificacion.estado='cumple',
  value=>value.procedencia.equilibrium.tiempos.pop(),
  value=>value.procedencia.equilibrium.estados.A.pop(),
  value=>value.procedencia.equilibrium.series[0].valores[0]+=1,
  value=>value.procedencia.equilibrium.eventos.push({tiempo:2,codigo:'aparicion_fase'}),
];
for(const corrupt of corruptions){const value=structuredClone(failed);corrupt(value);assert.throws(()=>leerResultados(value));}
console.log('Common physical certification: 2 live results and 6 rejected corruptions.');
