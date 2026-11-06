import {readEquilibriumReactions} from './equilibriumReactions';
import {readIndexSet} from './indexSetContract';
import {readFlowsheet, readFlowsheetLayout} from './flowsheet';
import {readKineticReactions} from '../../app/models/kineticReactions';
import {readEquationWorkbench} from '../../app/models/equationWorkbench';
import {readDerivedExecution} from './derivedExecution';
import { readThermodynamicJournal, thermodynamicJournalMatches } from '../../app/motor/physicalDerivation';
import { readEnergyJournal, energyJournalMatches } from '../../app/motor/physicalDerivation';
/** Lector estricto del modelo común en el cliente: las reglas estructurales de
 * core/modelo/lector.py (claves, identidades, referencias y cierre
 * termodinámico obligatorio). La validación matemática completa y la de la
 * configuración de cada motor las hace el servidor. */
import type { ModeloComun } from "./contrato";
import { VERSION_MODELO } from "./contrato";
import { readMaterialJournal, journalMatches } from '../../app/motor/materialDerivation';
import { readDynamicDefinition } from '../../app/models/dynamicDefinition';
import { readMomentumJournal } from '../../app/models/momentumDerivation';
import { readHydraulicNetwork } from '../../app/models/hydraulicDefinition';

const CLAVES = ["formato", "version", "id", "nombre", "componentes", "termodinamica", "volumenes", "corrientes",
  "intercambios", "datos", "matematico", "estudio", "motores", "procedencia"];

export class ErrorModelo extends Error {
  constructor(public ruta: string, public motivo: string) { super(`${ruta}: ${motivo}`); }
}
const fallo = (ruta: string, motivo: string): never => { throw new ErrorModelo(ruta, motivo); };
type Obj = Record<string, unknown>;
const obj = (v: unknown, ruta: string): Obj => (v && typeof v === "object" && !Array.isArray(v) ? v as Obj : fallo(ruta, "se esperaba un objeto"));
const lista = (v: unknown, ruta: string): unknown[] => (Array.isArray(v) ? v : fallo(ruta, "se esperaba una lista"));
function claves(v: unknown, ruta: string, obligatorias: string[], opcionales: string[] = []): Obj {
  const o = obj(v, ruta);
  const faltan = obligatorias.filter(k => !(k in o));
  if (faltan.length) fallo(ruta, "faltan " + faltan.join(", "));
  const sobran = Object.keys(o).filter(k => !obligatorias.includes(k) && !opcionales.includes(k));
  if (sobran.length) fallo(ruta, "campos desconocidos: " + sobran.join(", "));
  return o;
}
function unicos(items: unknown[], ruta: string): Set<unknown> {
  const vistos = new Set<unknown>();
  items.forEach((x, i) => { const k = obj(x, `${ruta}[${i}]`).id; if (vistos.has(k)) fallo(`${ruta}[${i}].id`, `identidad repetida: ${String(k)}`); vistos.add(k); });
  return vistos;
}
const ref = (v: unknown, conjunto: Set<unknown>, ruta: string, que: string) => { if (!conjunto.has(v)) fallo(ruta, `referencia inexistente (${que} ${String(v)})`); };

export function leerModeloComun(dato: unknown): ModeloComun {
  const m = claves(dato, "modelo", CLAVES, ["restricciones", "observables", "verificaciones", "template", "indexSet", "flowsheet", "flowsheetLayout"]);
  if (m.formato !== "rage.modelo") fallo("formato", "valor no admitido");
  if (m.version !== VERSION_MODELO) fallo("version", "valor no admitido");
  const datos = new Set(Object.keys(obj(m.datos, "datos")));
  for (const [k, d] of Object.entries(m.datos as Obj)) {
    const o = claves(d, `datos.${k}`, ["magnitud", "funcion", "declaracion", "origen"]);
    if (!["inicial", "frontera", "geometria", "estudio", "parametro"].includes(o.funcion as string)) fallo(`datos.${k}.funcion`, "valor no admitido");
    claves(o.declaracion, `datos.${k}.declaracion`, ["texto", "unidad"]);
    claves(o.origen, `datos.${k}.origen`, ["propietarioId", "ruta"]);
  }
  const dato_ = (v: unknown, ruta: string) => ref(v, datos, ruta, "dato");
  const comps = unicos(lista(m.componentes, "componentes"), "componentes");
  const paqs = unicos(lista(claves(m.termodinamica, "termodinamica", ["paquetes"]).paquetes, "termodinamica.paquetes"), "termodinamica.paquetes");
  const volsL = lista(m.volumenes, "volumenes"), vols = unicos(volsL, "volumenes");
  volsL.forEach((v, i) => {
    const r = `volumenes[${i}]`, o = claves(v, r, ["id", "componenteIds", "balances", "supuestos", "frontera", "inicial", "termodinamica"], ["terminos", "volumenDatoId"]);
    lista(o.componenteIds, r + ".componenteIds").forEach((c, j) => ref(c, comps, `${r}.componenteIds[${j}]`, "componente"));
    const f = obj(o.frontera, r + ".frontera");
    if (f.tipo === "rigida") dato_(f.datoId, r + ".frontera.datoId");
    else if (f.tipo === "presion_prescrita") dato_(f.presionId, r + ".frontera.presionId");
    else if (f.tipo !== "sin_relacion" && f.tipo !== "malla_1d") fallo(r + ".frontera.tipo", "valor no admitido");
    const t = o.termodinamica as Obj | null;
    if (!t || typeof t !== "object" || !("tipo" in t)) fallo(r + ".termodinamica", "todo volumen declara su cierre termodinámico (equilibrio con un paquete, o un supuesto explícito con su motivo)");
    if (t!.tipo === "equilibrio") { claves(t, r + ".termodinamica", ["tipo", "paqueteId", "politica"]); ref(t!.paqueteId, paqs, r + ".termodinamica.paqueteId", "paquete"); }
    else if (t!.tipo === "supuesto") { const s = claves(t, r + ".termodinamica", ["tipo", "supuesto", "motivo"], ["parametros"]); if (typeof s.motivo !== "string" || !s.motivo.trim()) fallo(r + ".termodinamica.motivo", "texto requerido"); }
    else fallo(r + ".termodinamica.tipo", "valor no admitido");
  });
  lista(m.corrientes, "corrientes").forEach((c, i) => {
    const r = `corrientes[${i}]`, o = claves(c, r, ["id", "desde", "hasta", "componenteIds", "mecanismo", "materia"], ["estadoExterior", "extraccion", "constante"]);
    for (const k of ["desde", "hasta"] as const) if (o[k] !== null) ref(o[k], vols, `${r}.${k}`, "volumen");
    if (o.desde === null && o.hasta === null) fallo(r, "una corriente necesita al menos un extremo en un volumen");
    const mat = obj(o.materia, r + ".materia");
    if (mat.modo === "por_componente") Object.values(obj(mat.caudalIds, r + ".materia.caudalIds")).forEach(d => dato_(d, r + ".materia.caudalIds"));
    else if (mat.modo === "total_desde_donante") dato_(mat.caudalId, r + ".materia.caudalId");
    else fallo(r + ".materia.modo", "valor no admitido");
    if ('extraccion' in o) for (const key of Object.keys(obj(o.extraccion,r+'.extraccion'))) ref(key,vols,r+'.extraccion.'+key,'volume');
    if ('estadoExterior' in o) dato_(obj(o.estadoExterior,r+'.estadoExterior').temperaturaId,r+'.estadoExterior.temperaturaId');
  });
  unicos(lista(m.intercambios, "intercambios"), "intercambios");
  if (m.estudio !== null) {
    const study=obj(m.estudio,'estudio');
    if(study.tipo==='steady') {
      claves(study,'estudio',['tipo','version','metodoSolicitado']);
      if(study.version!==1||study.metodoSolicitado!=='damped_newton')fallo('estudio','Invalid steady study.');
    }else dato_(study.tiempoId,'estudio.tiempoId');
  }
  if (m.matematico !== null) obj(m.matematico, "matematico");
  if ("restricciones" in m) {
    if (m.matematico === null) fallo("restricciones", "las restricciones se declaran sobre variables del modelo matemático");
    const campos = new Set((m.matematico as { simbolos: { id: string; rol: string }[] }).simbolos.filter(s => s.rol === "campo").map(s => s.id));
    const vistos = new Set<string>();
    lista(m.restricciones, "restricciones").forEach((x, i) => {
      if ("simboloId" in obj(x, `restricciones[${i}]`)) {
        const o = claves(x, `restricciones[${i}]`, ["simboloId", "tipo"]);
        ref(o.simboloId, campos, `restricciones[${i}].simboloId`, "variable del modelo matemático");
        if (vistos.has(o.simboloId as string)) fallo(`restricciones[${i}].simboloId`, "identidad repetida");
        vistos.add(o.simboloId as string);
        if (o.tipo !== "no_negativo") fallo(`restricciones[${i}].tipo`, "valor no admitido");
      } else {
        const o = claves(x, `restricciones[${i}]`, ["expresion", "tipo", "descripcion"]);
        obj(o.expresion, `restricciones[${i}].expresion`);
        if (o.tipo !== "no_negativo") fallo(`restricciones[${i}].tipo`, "valor no admitido");
      }
    });
  }
  obj(m.motores, "motores");
  if ('template' in m) readTemplate(m as unknown as ModeloComun);
  if ('indexSet' in m) readIndexSet(m as unknown as ModeloComun,leerModeloComun);
  if ('flowsheet' in m) readFlowsheet(m as unknown as ModeloComun,leerModeloComun);
  if ('flowsheetLayout' in m) readFlowsheetLayout(m as unknown as ModeloComun);
  for (const k of Object.keys(obj(m.motores, "motores"))) if (!['adimensionalizacion', 'materialDerivation', 'energyDerivation', 'thermodynamicDerivation', 'dynamicDefinition', 'momentumDerivation','hydraulicNetwork','equationWorkbench','derivedExecution','kineticReactions','equilibriumReactions'].includes(k)) fallo(`motores.${k}`, "motor desconocido");
  if((m.motores as Obj).equilibriumReactions!==undefined)readEquilibriumReactions((m.motores as Obj).equilibriumReactions,m as unknown as ModeloComun);
  if((m.motores as Obj).kineticReactions!==undefined)readKineticReactions((m.motores as Obj).kineticReactions,m as unknown as ModeloComun);
  if((m.motores as Obj).derivedExecution!==undefined)readDerivedExecution((m.motores as Obj).derivedExecution,m.datos as Record<string,unknown>);
  if((m.motores as Obj).equationWorkbench!==undefined)readEquationWorkbench((m.motores as Obj).equationWorkbench);
  if((m.motores as Obj).hydraulicNetwork!==undefined)readHydraulicNetwork((m.motores as Obj).hydraulicNetwork,m as unknown as ModeloComun);
  if ((m.motores as Obj).momentumDerivation !== undefined) readMomentumJournal((m.motores as Obj).momentumDerivation, m as unknown as ModeloComun);
  if ((m.motores as Obj).dynamicDefinition !== undefined) readDynamicDefinition((m.motores as Obj).dynamicDefinition, m as unknown as ModeloComun);
  if ((m.motores as Obj).thermodynamicDerivation !== undefined) {
    const model=m as unknown as ModeloComun,journal=readThermodynamicJournal((m.motores as Obj).thermodynamicDerivation);
    for(const [id,entry] of Object.entries(journal.volumes)){
      const volume=model.volumenes.find(v=>v.id===id),thermo=volume?.termodinamica;
      const selected=thermo?.tipo==='equilibrio'?model.termodinamica.paquetes.find(p=>p.id===thermo.paqueteId):undefined;
      const closure=thermo?.tipo==='equilibrio'&&selected?{packageId:thermo.paqueteId,model:selected.modelo,policy:thermo.politica}:null;
      if(!volume||thermo?.tipo==='equilibrio'&&!closure||!thermodynamicJournalMatches(entry,volume.supuestos.energia??{},closure))fallo('motores.thermodynamicDerivation','The journal does not produce the effective thermodynamic closure.');
    }
  }
  if ((m.motores as Obj).energyDerivation !== undefined) {
    const journal = readEnergyJournal((m.motores as Obj).energyDerivation);
    for (const [id,entry] of Object.entries(journal.volumes)) {
      const volume = (m as unknown as ModeloComun).volumenes.find(v=>v.id===id);
      if(!volume?.supuestos.energia||!energyJournalMatches(entry,volume.supuestos.energia))fallo('motores.energyDerivation','The energy journal does not produce the effective first law.');
    }
  }
  if ((m.motores as Obj).materialDerivation !== undefined) {
    const journal = readMaterialJournal((m.motores as Obj).materialDerivation);
    for (const [owner, entry] of Object.entries(journal.volumes)) {
      const volume = (m.volumenes as ModeloComun['volumenes']).find(volume => volume.id === owner);
      if (!volume || !journalMatches(entry, volume.supuestos.materia)) fallo('motores.materialDerivation', 'The material journal does not produce the formulation being compiled.');
    }
  }
  const scaling = (m.motores as Obj).adimensionalizacion;
  if (scaling && 'execution' in obj(scaling, 'motores.adimensionalizacion')) {
    const execution = claves((scaling as Obj).execution, 'execution', ['version', 'objectives', 'freeScales']);
    if (execution.version !== 1) fallo('execution.version', 'Expected execution version 1.');
    const objectives = lista(execution.objectives, 'execution.objectives');
    if (objectives.some(id => typeof id !== 'string' || !id.trim()) || new Set(objectives).size !== objectives.length) fallo('execution.objectives', 'Expected unique term identifiers.');
    for (const [id, value] of Object.entries(obj(execution.freeScales, 'execution.freeScales'))) {
      const quantity = claves(value, 'execution.freeScales.' + id, ['value', 'unit']);
      if (typeof quantity.value !== 'number' || !Number.isFinite(quantity.value) || quantity.value <= 0 || typeof quantity.unit !== 'string') fallo('execution.freeScales.' + id, 'Expected a positive finite scale with a unit.');
    }
  }
  if (!["documento_adimensional", "ensamblaje_v2", "hoja_motor_materia", "nuevo"].includes(obj(m.procedencia, "procedencia").tipo as string)) fallo("procedencia.tipo", "valor no admitido");
  return m as unknown as ModeloComun;
}

type PhysicalJournalName='materialDerivation'|'energyDerivation'|'momentumDerivation'|'thermodynamicDerivation';
export function requiredEquipmentJournals(model:ModeloComun):PhysicalJournalName[] {
  const required:PhysicalJournalName[]=['materialDerivation','energyDerivation','momentumDerivation'];
  if(model.volumenes.some(v=>v.termodinamica.tipo==='equilibrio'))required.push('thermodynamicDerivation');
  return required;
}

function readTemplate(model:ModeloComun) {
  const text=(v:unknown,r:string)=>{if(typeof v!=='string'||!v.trim())fallo(r,'Nonempty text required');};
  const t=claves(model.template,'template',['format','version','id','templateVersion','equipment','recipe','ports']);
  if(t.format!=='rage.model-template'||t.version!==1)fallo('template','Expected rage.model-template version 1');
  text(t.id,'template.id');text(t.templateVersion,'template.templateVersion');
  if(typeof t.equipment!=='boolean')fallo('template.equipment','Boolean required');
  const journals=lista(claves(t.recipe,'template.recipe',['journals']).journals,'template.recipe.journals');
  const allowed=['materialDerivation','energyDerivation','momentumDerivation','thermodynamicDerivation','equationWorkbench'];
  if(!journals.length||new Set(journals).size!==journals.length||journals.some(j=>typeof j!=='string'||!allowed.includes(j)||!Object.hasOwn(model.motores,j)))fallo('template.recipe.journals','Expected unique references to existing deduction journals');
  for(const journal of journals) obj((model.motores as Obj)[journal as string],'motores.'+journal);
  if(t.equipment&&requiredEquipmentJournals(model).some(journal=>!journals.includes(journal)))fallo('template.recipe.journals','Equipment requires recorded matter, energy and momentum journals, plus thermodynamics for package closures');
  const ports=lista(t.ports,'template.ports'),seen=new Set(),boundaries=new Set();
  if(t.equipment&&!ports.length)fallo('template.ports','Equipment requires at least one port');
  ports.forEach((value,i)=>{
    const r=`template.ports[${i}]`,p=claves(value,r,['id','volumeId','direction','kind','boundary','variables'],['donorPhase','exteriorState']);
    text(p.id,r+'.id');text(p.volumeId,r+'.volumeId');
    if(seen.has(p.id))fallo(r+'.id','Duplicate port identity');seen.add(p.id);
    const volume=model.volumenes.find(v=>v.id===p.volumeId);
    if(!volume)fallo(r+'.volumeId','Unknown volume');
    if(!['inlet','outlet'].includes(p.direction as string)||!['material','heat','work'].includes(p.kind as string))fallo(r,'Invalid port direction or kind');
    const b=claves(p.boundary,r+'.boundary',['type','id']);text(b.id,r+'.boundary.id');
    if(!['stream','exchange','term'].includes(b.type as string))fallo(r+'.boundary.type','Invalid boundary type');
    const identity=JSON.stringify([b.type,b.type==='term'?p.volumeId:'',b.id]);
    if(boundaries.has(identity))fallo(r+'.boundary','Boundary already has a port');boundaries.add(identity);
    const open=(s:{desde:string|null;hasta:string|null})=>{if(s.desde!==(p.direction==='inlet'?null:p.volumeId)||s.hasta!==(p.direction==='inlet'?p.volumeId:null))fallo(r+'.boundary','Port direction must match an open boundary of its volume');};
    let units:Record<string,string>;
    if(p.kind==='material'){
      const stream=model.corrientes.find(s=>s.id===b.id);
      if(b.type!=='stream'||!stream)fallo(r+'.boundary','Material port requires an existing stream');
      open(stream!);
      if(p.direction==='inlet'){
        if('donorPhase' in p||p.exteriorState!=='estadoExterior'||!stream!.estadoExterior)fallo(r,'Inlet requires its stream exterior state and no donor phase');
      }else{
        if('exteriorState' in p||!('donorPhase' in p))fallo(r,'Outlet requires donorPhase and no exterior state');
        const extraction=stream!.extraccion?.[p.volumeId as string];
        const expected=extraction?.tipo==='fase'?extraction.fase:null;
        if(p.donorPhase!==expected||(p.donorPhase!==null&&typeof p.donorPhase!=='string'))fallo(r+'.donorPhase','Donor phase must match the stream extraction');
      }
      const base=stream!.materia.base;
      units={flow:{masica:'kg/s',molar:'mol/s',volumetrica:'m^3/s'}[base],composition:'1',temperature:'K',pressure:'Pa',specificEnthalpy:base==='molar'?'J/mol':'J/kg'};
    }else{
      if('donorPhase' in p||'exteriorState' in p)fallo(r,'Only material ports declare donor or exterior states');
      if(b.type==='exchange'&&p.kind==='heat'){
        const exchange=model.intercambios.find(q=>q.id===b.id);
        if(!exchange)fallo(r+'.boundary','Unknown heat exchange');open(exchange!);
      }else if(!(b.type==='term'&&b.id===(p.kind==='heat'?'calor':'trabajo_viscoso')&&Object.hasOwn(volume!.terminos??{},b.id as string)))fallo(r+'.boundary','Expected an existing heat or work boundary term');
      units={power:'W'};
    }
    const variables=claves(p.variables,r+'.variables',Object.keys(units));
    for(const [key,unit]of Object.entries(units))if(claves(variables[key],r+'.variables.'+key,['unitSI']).unitSI!==unit)fallo(r+'.variables.'+key,'Expected SI unit '+unit);
  });
}
