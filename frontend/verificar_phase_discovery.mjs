// Verify the ordinary phase-discovery example and optional real solver outputs.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const directory = path.dirname(fileURLToPath(import.meta.url));
const cache = new Map();
function load(file) {
  if (!path.extname(file)) file += '.ts';
  if (file.endsWith('.json')) return { __esModule: true, default: JSON.parse(fs.readFileSync(file, 'utf8')) };
  if (cache.has(file)) return cache.get(file);
  const loadedModule = { exports: {} }; cache.set(file, loadedModule.exports);
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  new Function('exports', 'module', 'require', 'process', source)(loadedModule.exports, loadedModule, dependency => {
    if (!dependency.startsWith('.')) throw new Error('Unexpected external dependency: ' + dependency);
    return load(path.resolve(path.dirname(file), dependency));
  }, { env: {} });
  cache.set(file, loadedModule.exports); return loadedModule.exports;
}

const {createPhaseDiscoveryExamples}=load(path.join(directory,'app/motor/phaseDiscoveryExample'));
const {auditModelDerivation}=load(path.join(directory,'app/models/modelDerivationAudit'));
const {firmaHoja}=load(path.join(directory,'app/motor/modeloHojaMotor'));
const {adaptarResultadoV2,validarResultadoV2,seriesFasesV2}=load(path.join(directory,'app/motor/resultadoEnsamblajeV2'));
const [model]=createPhaseDiscoveryExamples(),request=model.redTermodinamica.solicitud;
if(process.argv.includes('--request')){console.log(JSON.stringify(request));process.exit(0);}
let checks=0;
const check=(condition,message)=>{assert.ok(condition,message);checks++;};
check(auditModelDerivation(model).status==='recorded','The example is derived through the shared tools');
check(!model.resultado&&!model.resultadoRef,'The example stores no solution');
check(request.volumenes[0].frontera.tipo==='rigida','The boundary is rigid');
check(request.volumenes[0].politica.cantidad==='sin_restriccion'&&request.volumenes[0].politica.cambioInterno==='permitido'&&!request.volumenes[0].politica.tiposPermitidos,'No phase count or type is imposed');
check(request.corrientes.length===0,'The vessel has no material streams');
check(!JSON.stringify(request).includes('lle-public'),'The package is not selected as an equilibrium-type switch');
check(!JSON.stringify(request).includes('fraccionMolar'),'No phase fractions are imposed in the input');
for(const stage of ['model','transform','solve','results'])check(typeof model.workspaceNotes[stage]==='string','The example explains '+stage+' within the standard workspace');
const renamed=structuredClone(model);renamed.workspaceNotes.model+=' Editorial note.';
check(firmaHoja(renamed)===firmaHoja(model),'Presentation notes do not alter execution identity');
if(process.argv.includes('--results')){
 const resultFile=path.join(directory,'../.tmp/phase-discovery-native-result.json');
 const response=JSON.parse(fs.readFileSync(resultFile,'utf8'));
 const result=adaptarResultadoV2(model,request,response);validarResultadoV2(result);
 check(result.estado==='resuelto','The real native result passes the unchanged strict reader');
 const phases=seriesFasesV2(result);
 check(phases.some(series=>series.id.endsWith('.x.1'))&&phases.some(series=>series.id.endsWith('.x.2')),'Both component compositions can be plotted');
 check(phases.some(series=>series.id.endsWith('.fraccionMolar')&&series.valores.some(value=>value===0)),'Disappearing phases remain visible with zero fractions');
 const common=JSON.parse(fs.readFileSync(path.join(directory,'../.tmp/phase-discovery-common-result.json'),'utf8'));
 const values=new Map(common.series.map(series=>[series.id,series.valores]));
 const initial=values.get('volumen.A.U')[0];
 // Published U is recomputed by the equilibrium closure, rather than being the
 // integrated state. Compare against the model's declared numerical budget,
 // including event samples, without changing either solver's acceptance rules.
 const energyBudget=request.estudio.atol.energia+request.estudio.rtol*Math.max(Math.abs(initial),50000);
 for(const [index,time] of common.ejes[0].valores.entries())check(Math.abs(values.get('volumen.A.U')[index]-(initial+50*time))<energyBudget,'Published common U(t) agrees with U0+Q t within the declared numerical budget');
 for(const verification of common.verificaciones)check(verification.valor<=verification.tolerancia,'Common conservation and complementarity certificates pass');
 check(response.resultados.certificacion.estado==='cumple','Native state, conservation and second-law certification passes');
 check(common.procedencia.compilation.energyDerivation.length===1&&common.procedencia.compilation.thermodynamicDerivation.length===1,'Common Results retain the derivation evidence');
}
fs.writeFileSync(path.join(directory,'../.tmp/phase-discovery-example.json'),JSON.stringify(model));
console.log(JSON.stringify({checks,modelId:model.id,scope:'Input-only example, shared derivation, unrestricted phase policy and connected workspaces'},null,2));
