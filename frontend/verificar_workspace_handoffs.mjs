// Strict compiler-reader and LaTeX checks against actual Python publications.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';
import katex from 'katex';

const directory = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url), cache = new Map();
function load(file) {
  if (!path.extname(file)) file += fs.existsSync(file + '.ts') ? '.ts' : '.tsx';
  if (file.endsWith('.json')) return { default: JSON.parse(fs.readFileSync(file, 'utf8')) };
  if (file.endsWith('.css')) return {default:new Proxy({},{get:(_target,key)=>String(key)})};
  if (cache.has(file)) return cache.get(file).exports;
  const loadedModule = { exports: {} }; cache.set(file, loadedModule);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { fileName:file, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  new Function('exports', 'module', 'require', 'process', code)(loadedModule.exports, loadedModule, dependency => dependency.startsWith('.') ? load(path.resolve(path.dirname(file), dependency)) : require(dependency), process);
  return loadedModule.exports;
}
const python = spawnSync('python', ['-c', `
import json,sys
sys.path.insert(0,'tests')
from test_workspace_handoffs import example
from test_transformed_execution import fixture,select
from core.compilador.presentation import formulation_summary
from core.compilador.report import compilation_report
from core.modelo.dynamic_definition import describe_definition
from core.balances.momentum_derivation import describe_volume,edit_journal
from test_momentum_derivation import model_with_momentum,journal,PUMP,HYDRAULIC
constrained=example();constrained['motores']['dynamicDefinition']={'format':'rage.dynamic-definition','version':1,'operations':[{'id':'fixed-mass','volumeId':'A','inventory':{'kind':'total_mass'},'mode':'fixed','reason':'Keep the total mass while compositions change.','dependent':{'kind':'stream_total','id':'feed'}}]}
scaled=select(fixture());scaled['estudio']['metodoSolicitado']='bdf'
local=journal(['pressure_stress','newtonian','mass_continuity','constant_viscosity','divergence_free'])
for name in ['velocityInvariantX','velocityInvariantZ','zeroVelocityY','zeroVelocityZ','zeroLocalAccumulation']:
    local=edit_journal(local,'A',{'kind':'set_assumption','name':name,'value':True})
print(json.dumps({'summary':formulation_summary(example()),'momentumModel':model_with_momentum(),'momentumSummary':formulation_summary(model_with_momentum()),'momentum':[describe_volume(journal(PUMP),'A'),describe_volume(journal(HYDRAULIC),'A'),describe_volume(local,'A')],'constrainedModel':constrained,'constrained':describe_definition(constrained),'reports':[compilation_report(example()),compilation_report(fixture()),compilation_report(scaled)]}))
`], { cwd: path.dirname(directory), encoding: 'utf8' });
assert.equal(python.status, 0, python.stderr);
const publications = JSON.parse(python.stdout);
const { readCompilationReport } = load(path.join(directory, 'motores/modelo/compilation'));
const { latexExpresion } = load(path.join(directory, 'app/adimensionalizacion/exportar'));
let checkedLatex = 0;
function formula(latex) { katex.renderToString(latex, { throwOnError: true, displayMode: true, strict: 'error' }); checkedLatex++; }
for (const report of publications.reports) {
  assert.deepEqual(readCompilationReport(report), report);
  report.strategy.steps.forEach(step => formula(step.latex));
  report.systemEquations?.forEach(row => formula(row.latex));
  report.equations.forEach(row => formula(`${latexExpresion(row.izquierda)}=${latexExpresion(row.derecha)}`));
  [...report.direct, ...report.inverse].forEach(map => formula(`${map.simboloId}=${latexExpresion(map.expresion)}`));
  const oldReport = structuredClone(report); delete oldReport.strategy; delete oldReport.systemEquations;
  assert.doesNotThrow(() => readCompilationReport(oldReport));
  for (const mutate of [
    value => { value.strategy.methods[0].available = 'yes'; },
    value => { value.strategy.steps[0].latex = null; },
    value => { value.strategy.methods.forEach(method => { method.available = false; }); },
    value => { value.systemEquations = [{ id: 'broken', family: 'Matter' }]; },
    value => { value.direct = [{ simboloId: 'x' }]; },
  ]) { const broken = structuredClone(report); mutate(broken); assert.throws(() => readCompilationReport(broken)); }
}
publications.summary.families.forEach(family => family.volumes.forEach(volume => volume.steps.forEach(step => formula(step.latex))));
const momentum = load(path.join(directory, 'app/models/momentumDerivation'));
for(const development of publications.momentum){
  assert.deepEqual(momentum.readMomentumDevelopment(development),development);
  [...development.steps,...development.finalSteps,...development.couplingSteps].forEach(step=>formula(step.latex));
  development.variables.forEach(variable=>formula(variable.symbol));
  for(const mutate of [value=>{value.finalSteps[0].family='energy';},value=>{value.formulation.newtonian='yes';},value=>{value.steps[0].latex=null;},value=>{value.available=null;},value=>{value.controls[0].value=!value.controls[0].value;},value=>{value.controls.push(value.controls[0]);},value=>{value.forms[0].selected=!value.forms[0].selected;}]){const invalid=structuredClone(development);mutate(invalid);assert.throws(()=>momentum.readMomentumDevelopment(invalid));}
}
const oldMomentumReport=structuredClone(publications.momentum[0]);delete oldMomentumReport.controls;delete oldMomentumReport.forms;
momentum.fieldMomentumFlags.forEach(key=>delete oldMomentumReport.formulation[key]);
assert.equal(momentum.readMomentumDevelopment(oldMomentumReport).formulation.invariantX,false,'Additive controls must preserve old journal/report readability.');
const {MomentumAssumptions}=load(path.join(directory,'app/motor/ModelAssumptions'));
const markup=require('react-dom/server').renderToStaticMarkup(require('react').createElement(MomentumAssumptions,{development:publications.momentum[2],disabled:false,change:()=>{},represent:()=>{}}));
assert.ok(!markup.includes('<select'),'Momentum assumptions must be direct controls, never a recipe dropdown.');
for(const label of ['No variation in x','No velocity variation in x','Zero y velocity','No local momentum accumulation','No total fluid-momentum accumulation'])assert.ok(markup.includes(`aria-label="${label}"`));
const dynamic = load(path.join(directory, 'app/models/dynamicDefinition'));
const { leerModeloComun } = load(path.join(directory, 'motores/modelo/lector'));
for (const publication of [publications.summary.dynamicFormulation, publications.constrained]) {
  assert.deepEqual(dynamic.readDynamicFormulation(publication), publication);
  publication.inventories.forEach(item => item.steps.forEach(step => formula(step.latex)));
  publication.domains.forEach(item => formula(item.latex));
  for (const mutate of [value => { value.inventories[0].options[0].dataId = undefined; }, value => { value.variables[0].role = 'free_guess'; }, value => { value.closures[0].balanceIds = ['missing']; }, value => { value.inventories[0].steps[0].latex = null; }]) {
    const invalid = structuredClone(publication); mutate(invalid); assert.throws(() => dynamic.readDynamicFormulation(invalid));
  }
}
assert.deepEqual(leerModeloComun(publications.constrainedModel), publications.constrainedModel);
assert.deepEqual(leerModeloComun(publications.momentumModel), publications.momentumModel);
for (const mutate of [value => { value.motores.dynamicDefinition.version = 2; }, value => { value.motores.dynamicDefinition.operations[0].dependent.id = 'missing'; }, value => { value.motores.dynamicDefinition.operations[0].inventory = {kind:'component_amount',componentId:999}; }]) {
  const invalid = structuredClone(publications.constrainedModel); mutate(invalid); assert.throws(() => leerModeloComun(invalid));
}
const document = JSON.parse(fs.readFileSync(path.join(directory, '../docs/ejemplos/heated-filling-vessel.model.json'), 'utf8'));
const { auditModelDerivation } = load(path.join(directory, 'app/models/modelDerivationAudit'));
assert.equal(auditModelDerivation(document.model).status, 'recorded');
assert.equal(document.model.redTermodinamica.solicitud.volumenes.length, 1);
assert.equal(document.model.redTermodinamica.solicitud.corrientes.length, 1);
assert.equal(document.model.redTermodinamica.solicitud.paquetes[0].modelo.id, 'unifac-original-public');
assert.ok(!document.model.resultado && !document.model.resultadoRef);
assert.equal(document.model.graficas.length, 4);
const constrainedSheet = dynamic.withDefinition(document.model, publications.constrainedModel.motores.dynamicDefinition);
assert.throws(() => dynamic.ensureInventoryExecution(constrainedSheet), /constrained dynamic execution/);
assert.notEqual(JSON.stringify(constrainedSheet.redTermodinamica.solicitud.derivacion), JSON.stringify(document.model.redTermodinamica.solicitud.derivacion));
const restoredDefinition = structuredClone(publications.constrainedModel.motores.dynamicDefinition);
restoredDefinition.operations.push({ id:'restore-dynamic',volumeId:'A',inventory:{kind:'total_mass'},mode:'dynamic',reason:'Remove the permanent inventory condition.' });
assert.doesNotThrow(() => dynamic.ensureInventoryExecution(dynamic.withDefinition(constrainedSheet, restoredDefinition)));
const library = fs.readFileSync(path.join(directory, 'app/models/ModelLibrary.tsx'), 'utf8');
assert.ok(library.includes('Import model file') && !library.includes('heatedFillingVessel') && !library.includes('modelFixtures'));
const { swapCharts } = load(path.join(directory, 'app/models/chartLayout'));
const charts = document.model.graficas;
const before = structuredClone(charts);
const swapped = swapCharts(charts, charts[0].id, charts[3].id);
assert.deepEqual(swapped.map(chart => chart.id), [charts[3].id, charts[1].id, charts[2].id, charts[0].id]);
assert.deepEqual(charts, before, 'Chart dragging must not mutate persisted inputs before saving.');
assert.equal(swapped[0], charts[3], 'Keep the complete chart specification, axes and height.');
assert.equal(swapCharts(charts, charts[0].id, charts[0].id), charts);
assert.equal(swapCharts(charts, 'missing', charts[0].id), charts);
assert.equal(swapCharts(charts, charts[0].id, 'missing'), charts);
const { firmaHoja } = load(path.join(directory, 'app/motor/modeloHojaMotor'));
const mechanical=momentum.withMomentumJournal(document.model,publications.momentumModel.motores.momentumDerivation);
assert.notEqual(firmaHoja(mechanical),firmaHoja(document.model));
assert.equal(momentum.momentumJournalOf(mechanical).volumes.A.operations.length,publications.momentumModel.motores.momentumDerivation.volumes.A.operations.length);
const mechanicalActive=momentum.includeMomentum(mechanical,'A',true);
assert.equal(mechanicalActive.redTermodinamica.solicitud.volumenes[0].balances.momento,true);
const topologySource=structuredClone(mechanicalActive);
topologySource.redTermodinamica.solicitud.corrientes.push({id:'momentum-in',desde:null,hasta:'A'});
momentum.momentumJournalOf(topologySource).volumes.A.operations.push({id:'bind-test',title:'Bind test inlet',changes:{inletStreamId:'momentum-in',outletStreamId:null}});
const topologyBefore=structuredClone(topologySource),portRemoved=structuredClone(topologySource);
portRemoved.redTermodinamica.solicitud.corrientes=portRemoved.redTermodinamica.solicitud.corrientes.filter(s=>s.id!=='momentum-in');
const portRepaired=momentum.reconcileMomentumTopology(topologySource,portRemoved);
assert.equal(momentum.momentumJournalOf(portRepaired).volumes.A.operations.at(-1).changes.inletStreamId,null);
assert.deepEqual(topologySource,topologyBefore,'Topology maintenance must not mutate prior history.');
const volumeRemoved=structuredClone(portRepaired);
volumeRemoved.redTermodinamica.solicitud.volumenes=volumeRemoved.redTermodinamica.solicitud.volumenes.filter(v=>v.id!=='A');
const volumeArchived=momentum.reconcileMomentumTopology(portRepaired,volumeRemoved);
assert.equal(momentum.momentumJournalOf(volumeArchived).volumes.A,undefined);
assert.ok(volumeArchived.archivedMomentumVolumes.A.operations.length);
const volumeRestored={...volumeArchived,redTermodinamica:structuredClone(portRepaired.redTermodinamica)};
const recovered=momentum.reconcileMomentumTopology(volumeArchived,volumeRestored);
assert.deepEqual(momentum.momentumJournalOf(recovered).volumes.A,momentum.momentumJournalOf(portRepaired).volumes.A);
assert.equal(recovered.archivedMomentumVolumes.A,undefined);
const readded=structuredClone(volumeArchived);
readded.redTermodinamica.solicitud.volumenes=structuredClone(portRepaired.redTermodinamica.solicitud.volumenes);
assert.deepEqual(momentum.momentumJournalOf(momentum.reconcileMomentumTopology(volumeArchived,readded)).volumes.A,momentum.momentumJournalOf(portRepaired).volumes.A);
for(const assembly of [false,true]){
  const ordinary=structuredClone(topologySource);delete ordinary.redTermodinamica;
  const owner=assembly?'A':'dominio',streamId=assembly?'s1':'puerto.1';
  ordinary.momentumDerivation={format:'rage.momentum-derivation',version:1,volumes:{[owner]:{origin:'recorded',operations:[{id:'bind',title:'Bind material inlet',changes:{inletStreamId:streamId,outletStreamId:null}}]}}};
  if(assembly)ordinary.ensamblaje={version:2,volumenes:[{id:'A'}],corrientes:[{id:1,desde:null,hasta:'A'}]};
  else{delete ordinary.ensamblaje;ordinary.historial.pasos[ordinary.historial.activo].formulacion.fronteras=[{id:1,sentido:'entrada'}];}
  const removed=structuredClone(ordinary);
  if(assembly)removed.ensamblaje.corrientes=[];else removed.historial.pasos[removed.historial.activo].formulacion.fronteras=[];
  assert.equal(momentum.momentumJournalOf(momentum.reconcileMomentumTopology(ordinary,removed)).volumes[owner].operations.at(-1).changes.inletStreamId,null);
}
const renamed={...portRepaired,nombre:'Renamed'};
assert.equal(momentum.reconcileMomentumTopology(portRepaired,renamed),renamed);
const {auditModelDerivation:auditMomentum}=load(path.join(directory,'app/models/modelDerivationAudit'));
assert.ok(!auditMomentum(mechanicalActive).findings.some(finding=>finding.family==='momentum'));
const {panelDeEcuacion}=load(path.join(directory,'app/motor/ubicacionEcuaciones'));
publications.momentum.forEach(development=>development.couplingSteps.forEach(step=>assert.notEqual(panelDeEcuacion({id:step.id,familia:step.family}),'momento')));
assert.notEqual(firmaHoja(constrainedSheet), firmaHoja(document.model), 'Inventory operations must invalidate the executed formulation.');
const { prepararEnsamblajeTermodinamico } = load(path.join(directory, 'app/motor/prepararEnsamblajeTermodinamico'));
const ordinaryConstrained = { ...document.model, redTermodinamica: undefined, dynamicDefinition: publications.constrainedModel.motores.dynamicDefinition };
const guardedLegacy = prepararEnsamblajeTermodinamico(ordinaryConstrained, 'inventory-guard');
assert.equal(guardedLegacy.solicitud, null);
assert.equal(guardedLegacy.diagnosticos[0].codigo, 'MOTOR_ENS_INVENTORY_CONSTRAINT');
assert.equal(firmaHoja({ ...document.model, graficas: swapped }), firmaHoja(document.model), 'Layout changes must retain the existing numerical result identity.');
console.log(JSON.stringify({ compilerBranches: 3, checkedLatex, strictReader: 'passed', recordedExample: 'passed', chartSwap: 'passed' }));
