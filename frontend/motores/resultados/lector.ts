/** Lector estricto del formato común de resultados en el cliente: estructura,
 * identidades y forma de los valores frente a sus ejes. La validez de las
 * unidades la garantiza el servidor (core/resultados/formato.py). */
import type { ConjuntoResultados } from "./contrato";
import { readCompilationReport } from '../modelo/compilation';
import {readSteadyResult} from '../modelo/steadyContract';
import {readAssessment} from '../modelo/assessment';
import {readIndexedNetwork} from './indexedNetwork';

export class ErrorResultados extends Error { constructor(public ruta: string, motivo: string) { super(`${ruta}: ${motivo}`); } }
const fallo = (ruta: string, motivo: string): never => { throw new ErrorResultados(ruta, motivo); };
type Obj = Record<string, unknown>;

function forma(v: unknown, dims: number[], ruta: string): void {
  if (!dims.length) { if (v !== null && typeof v !== "number") fallo(ruta, "se esperaba un número o null"); return; }
  if (!Array.isArray(v) || v.length !== dims[0]) fallo(ruta, `se esperaban ${dims[0]} valores`);
  (v as unknown[]).forEach((x, i) => forma(x, dims.slice(1), `${ruta}[${i}]`));
}

export function leerResultados(dato: unknown): ConjuntoResultados {
  const r = dato as Obj;
  if (!r || typeof r !== "object" || r.formato !== "rage.resultados" || r.version !== 0) fallo("resultados", "se esperaba rage.resultados v0");
  if (!["resuelto", "parcial", "fallido"].includes(r.estado as string)) fallo("estado", "valor no admitido");
  const provenance = r.procedencia as Obj;
  if (provenance?.compilation !== undefined) readCompilationReport(provenance.compilation);
  const largo = new Map<string, number>();
  (r.ejes as Obj[]).forEach((e, i) => {
    if (largo.has(e.id as string)) fallo(`ejes[${i}].id`, "identidad repetida");
    if (!Array.isArray(e.valores) || !e.valores.every(x => typeof x === "number" && Number.isFinite(x))) fallo(`ejes[${i}].valores`, "números finitos");
    largo.set(e.id as string, (e.valores as number[]).length);
  });
  const ids = new Set<string>();
  (r.series as Obj[]).forEach((s, i) => {
    if (ids.has(s.id as string)) fallo(`series[${i}].id`, "identidad repetida");
    ids.add(s.id as string);
    const ejes = s.ejes as string[];
    if (ejes.length > 2) fallo(`series[${i}].ejes`, "0, 1 o 2 ejes");
    ejes.forEach(k => { if (!largo.has(k)) fallo(`series[${i}].ejes`, `eje inexistente ${k}`); });
    forma(s.valores, ejes.map(k => largo.get(k)!), `series[${i}].valores`);
  });
  (r.eventos as Obj[]).forEach((e, i) => { if (!largo.has(e.ejeId as string)) fallo(`eventos[${i}].ejeId`, "eje inexistente"); });
  if(provenance.steadyDiagnostics!==undefined||provenance.motor==='rage.compilador.steady'||(r as unknown as ConjuntoResultados).procedencia.compilation?.version===2)readSteadyResult(r as unknown as ConjuntoResultados);
  readIndexedNetwork(r as unknown as ConjuntoResultados);
  readPhysicalEvidence(r as unknown as ConjuntoResultados);
  if(provenance.daeDiagnostics!==undefined||(r as unknown as ConjuntoResultados).procedencia.compilation?.derivedExecution?.version===4)readDAEEvidence(r as unknown as ConjuntoResultados);
  if(provenance.nonlinearDiagnostics!==undefined)readNonlinearEvidence(r as unknown as ConjuntoResultados);
  if(provenance.assessment!==undefined)readAssessment(provenance.assessment,r as unknown as ConjuntoResultados);
  return r as unknown as ConjuntoResultados;
}

function readPhysicalEvidence(result: ConjuntoResultados): void {
  const certificate = result.procedencia.physicalCertification;
  if (certificate === undefined) return;
  const detail = result.procedencia.equilibrium;
  const reject = (message: string): never => fallo('procedencia.equilibrium', message);
  if (certificate === null) {
    if (result.estado !== 'fallido' || result.series.length || detail) reject('Missing certificate for published equilibrium samples.');
    return;
  }
  if (!detail || JSON.stringify(detail.certificacion) !== JSON.stringify(certificate)) reject('The physical certificate must match its evidence.');
  const times = result.ejes[0]?.valores;
  if (!times?.length || JSON.stringify(detail!.tiempos) !== JSON.stringify(times)) reject('Certified sample times must match the common results.');
  const scope = certificate.alcance;
  if (!scope || scope.tInicial !== times[0] || scope.tFinal !== times.at(-1) || scope.muestras !== times.length || scope.completa !== (result.estado === 'resuelto')) reject('The certificate must describe the actual published scope.');
  const aspects = certificate.aspectos;
  if (!Array.isArray(aspects) || aspects.length !== 4 || new Set(aspects.map(a=>a.id)).size !== 4 || aspects.some(a=>!['estados_termodinamicos','conservacion','cierre_constitutivo','segunda_ley'].includes(a.id))) reject('All four certification aspects are required.');
  const statuses = aspects.map(a=>a.estado);
  if (statuses.some(s=>!['cumple','no_cumple','no_evaluable'].includes(s))) reject('Invalid physical certification status.');
  const aggregate = statuses.includes('no_cumple') ? 'no_cumple' : statuses.includes('no_evaluable') ? 'no_evaluable' : 'cumple';
  if (certificate.estado !== aggregate) reject('Numerical completion cannot override a failed or unevaluable aspect.');
  const common = new Map(result.series.map(s=>[s.id,s]));
  for (const series of detail!.series) {
    const published = common.get(series.variableId);
    if (!published || JSON.stringify(published.valores) !== JSON.stringify(series.valores) || published.unidadSI !== series.unidadSI) reject('A common series must preserve its certified source quantity.');
  }
  if (Object.values(detail!.estados).some(states=>states.length !== times.length)) reject('Certified states must align with the samples.');
  if (detail!.eventos.some(e=>e.tiempo < times[0] || e.tiempo > times.at(-1)!)) reject('An event cannot lie outside the certified prefix.');
}

function readNonlinearEvidence(result:ConjuntoResultados):void {
  const value=result.procedencia.nonlinearDiagnostics!;
  const reject=(message:string):never=>fallo('procedencia.nonlinearDiagnostics',message);
  const required=['version','method','sourceSignature','settings','evaluatedSolves','lastEvaluation','failures','publishedSamples','scope'];
  if(!value||typeof value!=='object'||Object.keys(value).length!==required.length||Object.keys(value).some(k=>!required.includes(k))||value.version!==1||value.method!=='damped_newton')reject('Expected nonlinear diagnostics v1.');
  const report=result.procedencia.compilation,selection=report?.derivedExecution?.selection;
  if(!selection||![3,4].includes(selection.version)||value.sourceSignature!==selection.sourceSignature||JSON.stringify(value.settings)!==JSON.stringify(selection.nonlinear)||typeof value.scope!=='string'||!Array.isArray(value.failures))reject('Nonlinear evidence disagrees with its formulation.');
  for(const n of [value.evaluatedSolves,value.publishedSamples])if(!Number.isSafeInteger(n)||n<0)reject('Invalid nonlinear counters.');
  if(value.publishedSamples!==result.ejes[0]?.valores.length||value.failures.length&&result.estado==='resuelto')reject('Invalid nonlinear publication scope.');
  const allowed=['iterations','evaluations','backtracks','residualNorm','stepNorm','conditionInfinity','terminationReason','completedProbes','uniqueness','stage','path','equationIds','quantityIds','modelId','sourceSignature','formulationSignature','time','code','message'];
  for(const row of [value.lastEvaluation,...value.failures]){
    if(!row||typeof row!=='object'||Object.keys(row).some(k=>!allowed.includes(k))||row.sourceSignature!==selection!.sourceSignature||row.modelId!==result.modeloId||row.formulationSignature!==report!.signature||row.path!=='motores.derivedExecution.nonlinear'||!['runtime','initialization','publication'].includes(String(row.stage))||JSON.stringify(row.equationIds)!==JSON.stringify(selection!.algebraic!.map(r=>r.equationId))||JSON.stringify(row.quantityIds)!==JSON.stringify(selection!.algebraic!.map(r=>r.quantityId)))reject('Invalid nonlinear diagnostic location.');
    for(const key of ['iterations','evaluations','backtracks'])if(!Number.isSafeInteger(row[key])||Number(row[key])<0)reject('Invalid nonlinear iteration counters.');
    for(const key of ['residualNorm','stepNorm','conditionInfinity','time'])if(row[key]!==null&&(typeof row[key]!=='number'||!Number.isFinite(row[key])||Number(row[key])<0))reject('Invalid nonlinear numerical evidence.');
    if(typeof row.terminationReason!=='string')reject('Missing nonlinear termination reason.');
  }
  for(const row of value.failures)if(typeof row.code!=='string'||typeof row.message!=='string'||row.terminationReason!==row.code)reject('Missing nonlinear failure code.');
}

function readDAEEvidence(result:ConjuntoResultados):void {
  const d=result.procedencia.daeDiagnostics,s=result.procedencia.compilation?.derivedExecution?.selection;
  const fields=['version','method','acceptedChecks','maxResidual','maxConservation','driftTolerance','scope'];
  if(!d||!result.procedencia.nonlinearDiagnostics||!s||s.version!==4||Object.keys(d).length!==fields.length||Object.keys(d).some(k=>!fields.includes(k))||d.version!==1||d.method!=='scipy_bdf_nested_newton'||typeof d.scope!=='string'||!Number.isSafeInteger(d.acceptedChecks)||d.acceptedChecks<0||[d.maxResidual,d.maxConservation,d.driftTolerance].some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0)||d.driftTolerance!==s.dae!.driftTolerance||d.maxResidual>d.driftTolerance||d.maxConservation>1e-6||result.estado==='resuelto'&&d.acceptedChecks<1)fallo('procedencia.daeDiagnostics','Invalid DAE accepted-state/drift evidence.');
}
