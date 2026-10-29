/** Cliente HTTP del modelo común (sin interfaz): POST /modelo/resolver. El cálculo es del servidor. */
import type { ModeloComun } from "./contrato";
import { leerResultados } from "../resultados/lector";
import type { ConjuntoResultados } from "../resultados/contrato";
import { readCompilationReport } from './compilation';
import {readAssessment, responseError, rejectedAssessment} from './assessment';

const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8004") + "/modelo";

export type TransporteModelo = (modelo: ModeloComun, signal?: AbortSignal) => Promise<unknown>;

export const transporteHTTP: TransporteModelo = async (modelo, signal) => {
  const tiempo = AbortSignal.timeout(600000);
  let r: Response;
  try {
    r = await fetch(`${API}/resolver`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ modelo, assessmentVersion:1 }), cache: "no-store", signal: signal ? AbortSignal.any([signal, tiempo]) : tiempo });
  } catch (e) {
    if (signal?.aborted) throw new Error("Cálculo cancelado.");
    throw new Error(`Servicio del Engine no disponible (${(e as Error).message}).`);
  }
  const cuerpo = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
  if (r.status === 422) {
    throw responseError(cuerpo,r.status,'The Engine rejected the model.');
  }
  if (!r.ok || !cuerpo) throw new Error(`Servicio del Engine no disponible (HTTP ${r.status}).`);
  return cuerpo;
};

export async function resolverModelo(modelo: ModeloComun, signal?: AbortSignal, transporte: TransporteModelo = transporteHTTP): Promise<ConjuntoResultados> {
  const result=leerResultados(await transporte(modelo, signal));
  if(result.procedencia.assessment&&result.modeloId!==modelo.id)throw new Error('The assessed result belongs to another model.');
  return result;
}

export async function describeCompilation(model: ModeloComun, signal?: AbortSignal) {
  return requestCompilation({ modelo: model }, signal);
}

export async function requestCompilation(body: { modelo: ModeloComun } | { solicitudV2: unknown }, signal?: AbortSignal) {
  return (await requestCompilationAssessment(body,signal)).report;
}

export async function requestAssessment(model:ModeloComun, signal?:AbortSignal, initialize=true){
  const response=await fetch(`${API}/assessment`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({format:'rage.model-assessment.request',version:1,model,initialize}),cache:'no-store',
    signal:signal?AbortSignal.any([signal,AbortSignal.timeout(60000)]):AbortSignal.timeout(60000)});
  const value=await response.json();
  if(!response.ok)throw responseError(value,response.status,'The model could not be assessed.');
  const assessment=readAssessment(value);
  if(assessment.modelId!==model.id)throw new Error('The assessment belongs to another model.');
  return assessment;
}

export async function requestCompilationAssessment(body: { modelo: ModeloComun } | { solicitudV2: unknown }, signal?: AbortSignal) {
  if('modelo' in body){
    const assessment=await requestAssessment(body.modelo,signal);
    if(!assessment.compilation)throw rejectedAssessment(assessment);
    return {report:assessment.compilation,assessment};
  }
  // The native network remains on its existing route pending migration review.
  const response = await fetch(`${API}/compilation`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), cache: 'no-store', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(60000) });
  const value = await response.json();
  if (!response.ok) throw responseError(value,response.status,'The selected formulation could not be compiled.');
  return {report:readCompilationReport(value),assessment:undefined};
}

/** Descripción termodinámica de un modelo (POST /modelo/termodinamica): cierre declarado, fases candidatas
 * de la capa, familia del modelo de estado y relaciones siempre presentes, por volumen. No calcula estados. */
export type RelacionModelo = { id: string; familia: string; propietarioId: string; descripcion: string; supuesta?: boolean };
export type VolumenTermodinamico = {
  id: string; componenteIds: number[]; frontera: string; relaciones: RelacionModelo[];
  cierre: { tipo: "equilibrio"; paquete: { id: string; version: string }; politica: { cantidad: string; cambioInterno: string; tiposPermitidos?: string[] } }
    | { tipo: "supuesto"; supuesto: "fase_no_evaluada" | "u_lineal"; motivo: string };
  modeloEstado: { familia: "ideal" | "actividad" | "iapws95" | "no_envuelto"; modeloLiquido: string | null; nombre: string } | null;
  candidatas: string[] | null; motivoCandidatas?: string;
};
export type DescripcionTermodinamica = { formato: "rage.modelo.termodinamica"; version: 0; volumenes: VolumenTermodinamico[] };

export async function describirTermodinamica(cuerpo: { modelo: ModeloComun } | { solicitudV2: unknown }, signal?: AbortSignal): Promise<DescripcionTermodinamica> {
  const tiempo = AbortSignal.timeout(60000);
  let r: Response;
  try {
    r = await fetch(`${API}/termodinamica`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo), cache: "no-store", signal: signal ? AbortSignal.any([signal, tiempo]) : tiempo });
  } catch (e) {
    throw new Error(`Servicio del Engine no disponible (${(e as Error).message}).`);
  }
  const d = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
  if (!r.ok || !d || d.formato !== "rage.modelo.termodinamica" || !Array.isArray(d.volumenes))
    throw new Error(r.status === 422 ? `El Engine no puede describir este modelo: ${d?.detail?.mensaje ?? ""}` : `Servicio del Engine no disponible (HTTP ${r.status}).`);
  return d as DescripcionTermodinamica;
}
