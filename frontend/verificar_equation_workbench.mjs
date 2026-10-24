// Real Python publications, strict readers, source identity and topology edits.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';
const directory=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};cache.set(file,loaded);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',code)(loaded.exports,loaded,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loaded.exports;
}
const {equationSections,readEquationWorkbench,readEquationWorkbenchReport}=load(path.join(directory,'app/models/equationWorkbench'));
const EquationRows=load(path.join(directory,'app/models/EquationRows')).default;
const {readCompilationReport}=load(path.join(directory,'motores/modelo/compilation'));
const {pressureExamples}=load(path.join(directory,'testing/pressureExamples'));
const {modelRequest}=load(path.join(directory,'app/models/modelRequest'));
const {physicalExecutionSignature}=load(path.join(directory,'app/motor/modeloHojaMotor'));
const {reconcileModelTopology}=load(path.join(directory,'app/models/modelTopology'));
const {equationSource}=load(path.join(directory,'app/models/EquationWorkbenchPanel'));
const {nuevaHoja}=load(path.join(directory,'app/motor/hojasMotor'));
const {regionEditRevision}=load(path.join(directory,'app/models/ModelDomainControls'));
const {recorridoMateria}=load(path.join(directory,'app/motor/recorridoMateria'));
const {iniciarEnergia,operarEnergia,volverEnergia,rehacerEnergia}=load(path.join(directory,'app/motor/recorridoEnergia'));
const {iniciarTermo,operarTermo,volverTermo,rehacerTermo}=load(path.join(directory,'app/motor/recorridoTermodinamico'));
const blank=nuevaHoja('An unbound model');
const initialSource=equationSource(blank);
assert.equal(initialSource.draft.version,3);
assert.deepEqual(initialSource.draft.materialJournal.operations,[]);
const symbolicEdit={format:'rage.equation-workbench',version:1,operations:[{kind:'declare_function',family:'matter',name:'testInventory',unit:'kg',dependencies:['time-id']}],cursor:1};
assert.deepEqual(equationSource({...blank,equationWorkbench:symbolicEdit}).draft.definition,symbolicEdit,'Operations remain in the symbolic request instead of switching to a fictitious component model.');
readEquationWorkbench(symbolicEdit);
const pinnedEdit={format:'rage.equation-workbench',version:1,operations:[{kind:'substitute',family:'matter',sources:['law'],relation:'closure',symbol:'quantity',sourceSignatures:{law:'a'.repeat(64),closure:'b'.repeat(64)}}],cursor:1};
assert.deepEqual(readEquationWorkbench(pinnedEdit),pinnedEdit);
const domainEdit={format:'rage.equation-workbench',version:1,operations:[{kind:'declare_domain',family:'matter',sources:['law'],symbol:'x',domain:'positive',reason:'Positive validity regime'}],cursor:1};
assert.deepEqual(readEquationWorkbench(domainEdit),domainEdit);
const intervalEdit={...domainEdit,operations:[{...domainEdit.operations[0],domain:'interval',lower:'1/2',upper:'2',lowerOpen:false,upperOpen:true}]};
assert.deepEqual(readEquationWorkbench(intervalEdit),intervalEdit);
const convertedInterval={...intervalEdit,operations:[{...intervalEdit.operations[0],endpointUnit:'cm/s'}]};
assert.deepEqual(readEquationWorkbench(convertedInterval),convertedInterval);
for(const invalid of [{...convertedInterval.operations[0],endpointUnit:42},{...convertedInterval.operations[0],endpointUnit:''},{...domainEdit.operations[0],endpointUnit:'m'}])assert.throws(()=>readEquationWorkbench({...intervalEdit,operations:[invalid]}));
for(const invalid of [{...intervalEdit.operations[0],lowerOpen:'false'},{...intervalEdit.operations[0],upper:undefined},{...domainEdit.operations[0],lower:'0'}])assert.throws(()=>readEquationWorkbench({...intervalEdit,operations:[invalid]}));
assert.throws(()=>readEquationWorkbench({...domainEdit,operations:[{...domainEdit.operations[0],domain:'automatic'}]}));
assert.throws(()=>readEquationWorkbench({...pinnedEdit,operations:[{...pinnedEdit.operations[0],domains:['domain']}]}),'Pinned inputs must include every selected domain.');
for(const sourceSignatures of [{law:'a'.repeat(64)},{law:'a'.repeat(64),closure:'invalid'},{law:'a'.repeat(64),closure:'b'.repeat(64),extra:'c'.repeat(64)}]){
  assert.throws(()=>readEquationWorkbench({...pinnedEdit,operations:[{...pinnedEdit.operations[0],sourceSignatures}]}));
}
assert.throws(()=>readEquationWorkbench({...symbolicEdit,operations:[{...symbolicEdit.operations[0],dependencies:['duplicate','duplicate']}]}));
const blankChanged={...blank,historial:recorridoMateria(blank.historial,{tipo:'cambiar',titulo:'Remove convection',cambios:{campo:{...blank.historial.pasos[0].formulacion.campo,sinConveccion:true}}})};
assert.notDeepEqual(equationSource(blankChanged),initialSource,'A component-free physical edit must change the Python request.');
const undone={...blankChanged,historial:recorridoMateria(blankChanged.historial,{tipo:'ir',indice:0})};
assert.deepEqual(equationSource(undone),initialSource);
const redone={...undone,historial:recorridoMateria(undone.historial,{tipo:'rehacer'})};
assert.deepEqual(equationSource(redone),equationSource(blankChanged));
const withPort={...blank,historial:recorridoMateria(blank.historial,{tipo:'cambiar',titulo:'Declare inlet',cambios:{fronteras:[{id:1,sentido:'entrada',constante:false}]}})};
assert.notDeepEqual(equationSource(withPort),initialSource,'Topology is part of the symbolic source.');
const withMomentum={...blank,momentumDerivation:{format:'rage.momentum-derivation',version:1,volumes:{dominio:{origin:'recorded',operations:[{id:'body',title:'Neglect body forces',changes:{negligibleBodyForce:true}}]}}}};
assert.notDeepEqual(equationSource(withMomentum),initialSource,'Momentum changes are not lost before component declaration.');
const energyRoot=iniciarEnergia({volumenId:'dominio',puertos:[],fija:true,restoCerrado:true});
const energyChanged=operarEnergia(energyRoot,'Negligible kinetic energy',{sinCinetica:true});
const energySource=history=>equationSource({...blank,energia:{historial:history}});
assert.notDeepEqual(energySource(energyChanged),energySource(energyRoot));
assert.deepEqual(energySource(volverEnergia(energyChanged,0)),energySource(energyRoot));
assert.deepEqual(energySource(rehacerEnergia(volverEnergia(energyChanged,0))),energySource(energyChanged));
const thermoRoot=iniciarTermo(),thermoChanged=operarTermo(thermoRoot,'Constant density',{densidadConstante:true});
const thermoSource=history=>equationSource({...blank,recorridoTermodinamico:history});
assert.notDeepEqual(thermoSource(thermoChanged),thermoSource(thermoRoot));
assert.deepEqual(thermoSource(volverTermo(thermoChanged,0)),thermoSource(thermoRoot));
assert.deepEqual(thermoSource(rehacerTermo(volverTermo(thermoChanged,0))),thermoSource(thermoChanged));
const publication=JSON.parse(fs.readFileSync(path.join(directory,'../.tmp/equation-workbench-publications.json'),'utf8'));
// Optional real Python reports exercise new acceptance documents through the
// same strict reader and renderer; no separate fixture UI is introduced.
const additionalReports=process.argv.slice(2).map(file=>JSON.parse(fs.readFileSync(path.resolve(file),'utf8')));
let formulas=0;
for(const report of [publication.source,publication.combined,publication.draft,publication.recovered,...(publication.symbolic??[]),...additionalReports]){
  readEquationWorkbenchReport(report);
  for(const row of report.equations)for(const latex of [row.latex,...row.derivation.beforeLatex,...row.derivation.assumptions.filter(condition=>condition.includes('\\')),...(row.derivation.branches??[]).map(branch=>branch.latex)]){katex.renderToString(latex,{throwOnError:true,displayMode:true,strict:'error'});formulas++;}
  const branchRow=report.equations.find(row=>row.derivation.branches);
  if(branchRow){
    const html=require('react-dom/server').renderToStaticMarkup(require('react').createElement(EquationRows,{steps:[branchRow]}));
    assert.ok(html.includes('Branch selection evidence')&&html.includes('Admitted by the recorded domains'),'The canonical row exposes real Python branch evidence.');
    if(branchRow.derivation.branches.some(branch=>!branch.admitted))assert.ok(html.includes('Excluded by the recorded domains'));
    const malformed=structuredClone(report);const row=malformed.equations.find(row=>row.id===branchRow.id);
    row.derivation.branches.forEach(branch=>{branch.admitted=false;});assert.throws(()=>readEquationWorkbenchReport(malformed));
  }
  const bad=structuredClone(report);bad.equations.at(-1).derivation.inputIds=['missing'];assert.throws(()=>readEquationWorkbenchReport(bad));
}
for(const family of ['matter','momentum','energy','thermodynamics']){
  const snapshot=JSON.stringify(publication.source);
  const view=equationSections(publication.source,family,'upper');
  assert.ok(view.roots.length>0,'Every supported family opens with its unreduced fundamental laws.');
  assert.ok(view.roots.every(row=>row.derivation.rule==='declared_law'&&!row.derivation.inputIds.length));
  assert.deepEqual([...view.roots,...view.steps].map(row=>row.id).sort(),publication.source.equations.filter(row=>row.family===family&&row.ownerId==='upper').map(row=>row.id).sort(),'No source or intermediate equation is hidden by a current-system filter.');
  assert.ok(view.result.every(row=>row.current));
  equationSections(publication.source,family,'lower');
  assert.equal(JSON.stringify(publication.source),snapshot,'Viewing another domain or history section must not mutate source data.');
}
assert.equal(equationSections(publication.combined,'matter','upper').shared.at(-1).id,'operation.1');
assert.equal(publication.recovered.execution.supported,false);
assert.deepEqual(publication.recovered.definition,publication.combined.definition,'Recovery preserves the full stored operation history.');
for(const replay of [{completed:-1,failedOperation:0,message:'bad'},{completed:0,failedOperation:2,message:'bad'}])assert.throws(()=>readEquationWorkbenchReport({...publication.recovered,replay}));
assert.throws(()=>readEquationWorkbenchReport({...publication.recovered,execution:{supported:true,reason:'Invalid recovery cannot run'}}));
readCompilationReport(publication.compilation);
assert.throws(()=>readEquationWorkbench({...publication.combined.definition,cursor:1000}));
const model=pressureExamples()[1],changed={...structuredClone(model),equationWorkbench:publication.combined.definition};
assert.equal(regionEditRevision(model),regionEditRevision({...model,volumenActivo:'lower'}),'Navigation cannot prevent restoring a region edit.');
const laterHistory=structuredClone(model);
laterHistory.ensamblaje.volumenes[0].historial.pasos[0].titulo='Reviewed fundamental law';
assert.notEqual(regionEditRevision(model),regionEditRevision(laterHistory),'Snapshot restoration must not discard later history just because final equations match.');
assert.deepEqual(modelRequest(changed).modelo.motores.equationWorkbench,publication.combined.definition);
assert.notEqual(physicalExecutionSignature(model),physicalExecutionSignature(changed));
const withUnits={...structuredClone(model),equationWorkbench:convertedInterval};
const differentUnits={...structuredClone(withUnits),equationWorkbench:{...convertedInterval,operations:[{...convertedInterval.operations[0],endpointUnit:'m/s'}]}};
assert.notEqual(physicalExecutionSignature(withUnits),physicalExecutionSignature(differentUnits),'Changing endpoint units invalidates the selected formulation and its runs.');
assert.deepEqual(modelRequest(withUnits).modelo.motores.equationWorkbench,convertedInterval,'Endpoint units survive the common-model handoff.');
changed.equationWorkbench={...changed.equationWorkbench,cursor:0};
assert.equal(physicalExecutionSignature(model),physicalExecutionSignature(changed),'Inactive future operations cannot change executed physics.');
const renamed=structuredClone(model);renamed.ensamblaje.volumenes[0].nombre='Arbitrary name';
assert.ok(reconcileModelTopology(model,renamed).hydraulicNetwork,'Display labels cannot retire numerical bindings.');
assert.equal(physicalExecutionSignature(model),physicalExecutionSignature(renamed),'Region display names cannot invalidate physical results.');
renamed.ensamblaje.corrientes[0].nombre='A display connection label';
assert.equal(physicalExecutionSignature(model),physicalExecutionSignature(renamed),'Connection display names cannot invalidate physical results.');
const topology=structuredClone(model);topology.ensamblaje.volumenes.pop();
const revised=reconcileModelTopology(model,topology);assert.equal(revised.hydraulicNetwork,undefined);assert.deepEqual(revised.previousHydraulicNetwork,model.hydraulicNetwork);
const {publishedSeriesCharts}=load(path.join(directory,'app/motor/TableroMotor'));
const result={tiempos:[0,1],seriesEvaluadas:[{id:'a',grupo:'Arbitrary family',unidad:'kg',valores:[1,2]},{id:'b',grupo:'Arbitrary family',unidad:'kg',valores:[2,3]},{id:'c',grupo:'Another quantity',unidad:'Pa',valores:[4,5]}]};
const charts=publishedSeriesCharts(result);
assert.equal(charts.length,2);assert.deepEqual(charts[0].y,['a','b']);assert.deepEqual(charts[1].y,['c']);
assert.ok(charts.every(chart=>chart.y.every(id=>result.seriesEvaluadas.some(series=>series.id===id))),'Default plots must reference actual published variables.');
console.log(JSON.stringify({equationReaders:'passed',operationHandoff:'passed',sourceInvalidation:'passed',editableTopology:'passed',renderedFormulas:formulas}));
