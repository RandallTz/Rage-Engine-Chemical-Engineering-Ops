// Audit every registered template and reject new provenance bypasses.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const directory = path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(import.meta.url);
const cache = new Map();
function load(file) {
  if (file.endsWith('.css')) return {__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};
  if (!path.extname(file)) file += fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if (file.endsWith('.json')) return { __esModule: true, default: JSON.parse(fs.readFileSync(file, 'utf8')) };
  if (cache.has(file)) return cache.get(file);
  const loadedModule = { exports: {} }; cache.set(file, loadedModule.exports);
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx:ts.JsxEmit.ReactJSX,
  } }).outputText;
  new Function('exports', 'module', 'require', 'process', source)(loadedModule.exports, loadedModule, dependency => {
    if(dependency==='next/navigation')return {useRouter:()=>({push(){},replace(){}})};
    if (!dependency.startsWith('.')) return require(dependency);
    return load(path.resolve(path.dirname(file), dependency));
  }, { env: {} });
  cache.set(file, loadedModule.exports); return loadedModule.exports;
}

const physical=load(path.join(directory,'app/motor/physicalDerivation'));
const {REGRESSION_MODELS}=load(path.join(directory,'testing/modelFixtures'));
const {auditModelDerivation}=load(path.join(directory,'app/models/modelDerivationAudit'));
const {firmaHoja}=load(path.join(directory,'app/motor/modeloHojaMotor'));
const {cambiarRed}=load(path.join(directory,'app/motor/redTermodinamica'));
const topology=load(path.join(directory,'app/motor/topologiaRed'));
const energyEdit=load(path.join(directory,'app/motor/networkEnergyJournal'));
const thermoEdit=load(path.join(directory,'app/motor/networkThermodynamicJournal'));
const {modeloBalancesDesdeHoja}=load(path.join(directory,'motores/modelo/desdeHojaBalances'));
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {engineCapabilities,checklistMarkdown}=load(path.join(directory,'app/checklist/datos'));
let checks=0;
const check=(condition,message)=>{assert.ok(condition,message);checks++;};
const models=REGRESSION_MODELS.flatMap(group=>group.create());
let displayedModel;
cache.set(path.join(directory,'app/motor/useHojasMotor.ts'),{useHojasMotor:()=>[displayedModel]});
const modelView=load(path.join(directory,'app/motor/HojaGuardada')).default;
const {ModelConfigurationProvider}=load(path.join(directory,'app/models/ModelWorksheet'));
const settingsView=load(path.join(directory,'app/motor/EstadoSistema')).default;
const {nuevaHoja}=load(path.join(directory,'app/motor/hojasMotor'));
const legacy=structuredClone(models.find(model=>model.redTermodinamica));
delete legacy.redTermodinamica.solicitud.derivacion;
for(const source of [...models,nuevaHoja('Blank model'),legacy])for(const family of ['materia','energia','termodinamica','momento'])for(const settings of [false,true]){
  displayedModel={...source,vistaBalance:family};
  const before=JSON.stringify(displayedModel);
  const html=renderToStaticMarkup(React.createElement(ModelConfigurationProvider,{open:settings,content:React.createElement(settingsView,{id:source.id})},React.createElement(modelView,{id:source.id})));
  check((html.match(/data-model-worksheet="canonical"/g)??[]).length===1,'Every template, blank and legacy model renders exactly one canonical worksheet for every family and settings view');
  check((html.match(/<aside/g)??[]).length===1,'No hidden alternate assumptions panel is mounted');
  check(JSON.stringify(displayedModel)===before,'Changing the rendered family or opening settings does not migrate or mutate stored physics');
}
for(const retired of ['BibliotecaHojas','BarraHojaMotor','EditorBalanceModular','DerivacionVolumenRed'])check(!fs.existsSync(path.join(directory,'app/motor',retired+'.tsx')),'Retired Model frontend is deleted: '+retired);
const materialEditor=load(path.join(directory,'app/models/MaterialJournalEditor')).default;
const energyEditor=load(path.join(directory,'app/models/EnergyJournalEditor')).default;
const thermoEditor=load(path.join(directory,'app/models/ThermodynamicJournalEditor')).default;
const matterWorkspace=load(path.join(directory,'app/motor/MateriaFundamental')).default;
for(const model of models){
  if(!model.redTermodinamica){
    const html=renderToStaticMarkup(React.createElement(matterWorkspace,{historialInicial:model.historial}));
    check(html.includes('<aside')&&html.includes('aria-label="Equation assumptions"')&&html.includes('aria-label="Convection"'),'Ordinary templates keep the shared assumptions panel');
    continue;
  }
  const request=model.redTermodinamica.solicitud;
  for(const volume of request.volumenes)for(const [editor,label] of [[materialEditor,'Equation'],[energyEditor,'Energy'],[thermoEditor,'Thermodynamic']]){
    const html=renderToStaticMarkup(React.createElement(editor,{request,volume,modelId:model.id,canRestore:false,restore(){},save(){return true;}}));
    check(html.includes(`<aside`)&&html.includes(`aria-label="${label} assumptions"`),'Every network volume/family keeps its assumptions beside the worksheet');
    check(html.includes('Mathematical development')&&!html.includes('Next deduction')&&!html.includes('Apply deduction'),'Examples do not introduce an alternative deduction workflow');
  }
}
for(const model of models){
  check(auditModelDerivation(model).status==='recorded',model.id+': every new template uses the recorded-derivation standard');
  if(model.redTermodinamica){
    const request=model.redTermodinamica.solicitud,energy=physical.energyJournalInRequest(request.derivacion),thermo=physical.thermodynamicJournalInRequest(request.derivacion);
    for(const volume of request.volumenes){
      check(physical.energyJournalMatches(energy.volumes[volume.id],volume.formulacionEnergia),'First-law recipe matches physical inputs');
      check(physical.thermodynamicJournalMatches(thermo.volumes[volume.id],volume.formulacionEnergia,physical.configuredClosure(request,volume)),'Constitutive selection matches actual package and phase policy');
    }
    const edited=structuredClone(model),id=request.volumenes[0].id;
    edited.redTermodinamica.solicitud.derivacion.energyDerivation.volumes[id].operations[0].title+=' · audit edit';
    check(firmaHoja(edited)!==firmaHoja(model),'Changing first-law evidence invalidates execution provenance');
    const stateEdit=structuredClone(model);stateEdit.redTermodinamica.solicitud.derivacion.thermodynamicDerivation.volumes[id].operations[0].title+=' · audit edit';
    check(firmaHoja(stateEdit)!==firmaHoja(model),'Changing state evidence invalidates execution provenance');
  }else if(model.energia){
    const common=modeloBalancesDesdeHoja(model);leerModeloComun(common);
    check(!!common.motores.energyDerivation&&!!common.motores.thermodynamicDerivation,'New manual energy examples serialize both recorded histories');
    const old=structuredClone(model);delete old.energia.historial.pasos[1].operation;
    check(physical.energyJournalFromHistory(old.energia.historial)===undefined,'A legacy energy snapshot is never promoted to an actual operation');
    const oldThermo=structuredClone(model);delete oldThermo.recorridoTermodinamico.pasos[1].operation;
    check(physical.thermodynamicJournalFromHistory(oldThermo.recorridoTermodinamico)===undefined,'A legacy thermodynamic snapshot is never promoted to an operation');
  }
}
const original=models.find(model=>model.redTermodinamica),id=original.redTermodinamica.solicitud.volumenes[0].id;
let network=structuredClone(original.redTermodinamica),request=network.solicitud,volume=request.volumenes[0];
const beforeEnergy=structuredClone(volume.formulacionEnergia),beforeMaterial=structuredClone(request.derivacion.materialDerivation);
delete request.derivacion.energyDerivation;
const root={...physical.emptyEnergyJournal(),volumes:{[id]:{origin:'reviewed_rebuild',operations:[]}}};
const rootState=physical.energyState(load(path.join(directory,'app/motor/recorridoEnergia')).ENERGIA_FUNDAMENTAL);
energyEdit.replaceNetworkEnergyJournal(request,id,root,rootState,true,JSON.stringify(request));
check(volume.formulacionEnergia.forma==='local','Explicit first-law rebuild begins at the local first law');
check(JSON.stringify(request.derivacion.materialDerivation)===JSON.stringify(beforeMaterial),'Energy rebuild preserves material provenance');
check(volume.formulacionEnergia.monofasico===beforeEnergy.monofasico,'Energy rebuild preserves thermodynamic assumptions');
assert.throws(()=>energyEdit.replaceNetworkEnergyJournal(request,id,root,rootState,false,'outdated'));checks++;
energyEdit.restoreNetworkEnergyFormulation(request,id);
check(JSON.stringify(volume.formulacionEnergia)===JSON.stringify(beforeEnergy),'Restoring the previous energy formulation is lossless');
check(!request.derivacion.energyDerivation,'Last restored energy entry removes the namespace');
network=structuredClone(original.redTermodinamica);request=network.solicitud;volume=request.volumenes[0];
const initialThermo={packageId:volume.paqueteId,policy:structuredClone(volume.politica),energy:structuredClone(volume.formulacionEnergia)};
delete request.derivacion.thermodynamicDerivation;
const thermoRoot={...physical.emptyThermodynamicJournal(),volumes:{[id]:{origin:'reviewed_rebuild',operations:[]}}};
thermoEdit.replaceNetworkThermodynamicJournal(request,id,thermoRoot,physical.fundamentalThermodynamics(),true,JSON.stringify(request));
check(volume.formulacionEnergia.forma===initialThermo.energy.forma,'State rebuild preserves the first-law representation');
check(!physical.thermodynamicJournalMatches(thermoRoot.volumes[id],volume.formulacionEnergia,physical.configuredClosure(request,volume)),'An unbound state closure remains an explicit compilation gap');
thermoEdit.restoreNetworkThermodynamicFormulation(request,id);
check(JSON.stringify(volume.formulacionEnergia)===JSON.stringify(initialThermo.energy)&&JSON.stringify(volume.politica)===JSON.stringify(initialThermo.policy),'Restoring state assumptions and policy preserves energy');
let changed=cambiarRed(original,red=>{const v=red.solicitud.volumenes[0];v.politica.cantidad='monofasico';v.formulacionEnergia.monofasico=true;});
check(changed.redTermodinamica.solicitud.derivacion.thermodynamicDerivation.volumes[id].operations.length===2,'Explicit phase-policy edit records a new constitutive operation');
check(auditModelDerivation(changed).status==='recorded','Updated phase policy passes replay after its actual edit');
const topologyNetwork=structuredClone(original.redTermodinamica),newId=topology.agregarElementoRed(topologyNetwork,'volumen');
check(topologyNetwork.solicitud.volumenes.at(-1).formulacionEnergia.forma==='local','A new volume starts with the local first law');
check(topologyNetwork.solicitud.derivacion.thermodynamicDerivation.volumes[newId].operations.length===0,'A new volume requires explicit package adoption');
topology.quitarElementoRed(topologyNetwork,'volumen',newId);
check(!topologyNetwork.solicitud.derivacion.energyDerivation.volumes[newId]&&!topologyNetwork.solicitud.derivacion.thermodynamicDerivation.volumes[newId],'Deleting a volume removes both journal ownerships');
for(const reader of [physical.readEnergyJournal,physical.readThermodynamicJournal]){assert.throws(()=>reader({format:'fake',version:true,volumes:{}}));checks++;}
const docPath=path.join(directory,'../docs/engine/engine-checklist.md');
// Exercise the real document store in an isolated runtime, never user storage.
const store=load(path.join(directory,'app/motor/hojasMotor'));
const storage=new Map([[store.CLAVE_HOJAS,JSON.stringify([models[0],{...models[1],archivada:true}])]]);
const previousWindow=globalThis.window,previousStorage=globalThis.localStorage;
try{
  globalThis.window={dispatchEvent(){}};
  globalThis.localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)};
  const original=JSON.stringify(store.leerHojas());
  check(store.removeAllModels()===2,'Library reset removes both active and archived models');
  check(store.leerHojas().every(model=>model.removedAt),'Removal is recoverable in the same versioned document store');
  check(store.removeAllModels()===0,'Repeated removal is idempotent');
  check(store.leerHojas().every((model,i)=>firmaHoja(model)===firmaHoja(JSON.parse(original)[i])),'Removal changes presentation, never scientific execution identity');
  check(store.restoreRemovedModels()===2&&JSON.stringify(store.leerHojas())===original,'Restoration preserves exact scientific data, histories, results and archive status');
  globalThis.localStorage.setItem=()=>{throw new Error('Storage unavailable');};
  assert.throws(()=>store.removeAllModels());checks++;
  check(JSON.stringify(store.leerHojas())===original,'Failed storage leaves all models intact');
}finally{
  if(previousWindow===undefined)delete globalThis.window;else globalThis.window=previousWindow;
  if(previousStorage===undefined)delete globalThis.localStorage;else globalThis.localStorage=previousStorage;
}
check(!fs.existsSync(path.join(directory,'app/models/modelTemplates.ts')),'No product template registry remains');
check(!/modelFixtures|MODEL_TEMPLATES|Start from a template/.test(fs.readFileSync(path.join(directory,'app/models/ModelLibrary.tsx'),'utf8')),'The product library does not load internal regression fixtures');
if(process.argv.includes('--update-checklist'))fs.writeFileSync(docPath,checklistMarkdown());
check(fs.readFileSync(docPath,'utf8')===checklistMarkdown(),'Canonical Markdown and live Checklist use one capability registry');
check(engineCapabilities.find(area=>area.id==='energia').available.some(item=>item.includes('recorded')||item.includes('Recorded')),'Checklist exposes delivered energy deductions');
if(process.argv.includes('--browser-fixtures'))fs.writeFileSync(path.join(directory,'../.tmp/physical-energy-common.json'),JSON.stringify(modeloBalancesDesdeHoja(models.find(model=>model.energia&&!model.redTermodinamica))));
if(process.argv.includes('--browser-fixtures'))fs.writeFileSync(path.join(directory,'../.tmp/physical-ui-models.json'),JSON.stringify(models));
console.log(JSON.stringify({checks,templates:models.length,scope:'Recorded derivations, document lifecycle, invalidation and live capability inventory'},null,2));
