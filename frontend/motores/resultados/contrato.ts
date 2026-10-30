/** Formato común de resultados v0 (docs/contracts/results-format.md). Lo publica todo
 * motor de cálculo y lo consume el motor de gráficas. Genérico: ejes y series
 * con unidad SI y dimensión exacta; ningún campo sabe de equipos u operaciones. */
export type DimensionJSON = Record<string, { n: number; d: number }>;
export type Eje = { id: string; nombre: string; rol: "tiempo" | "coordenada" | "parametro" | "otro"; unidadSI: string; dimension: DimensionJSON; valores: number[] };
/** valores: número (sin ejes), lista (un eje) o lista de listas (dos ejes; el primero es el índice exterior). null = no definido. */
export type Valores = number | null | (number | null)[] | (number | null)[][];
export type Serie = {
  id: string; nombre: string; unidadSI: string; dimension: DimensionJSON; magnitudes: string[]; ejes: string[]; valores: Valores;
  propietarioId?: string; componenteId?: number; faseId?: string;
};
export type Evento = { codigo: string; ejeId: string; valor: number; descripcion: string; propietarioId?: string };
export type ConjuntoResultados = {
  formato: "rage.resultados"; version: 0; id: string; nombre: string; modeloId: string | null;
  estado: "resuelto" | "parcial" | "fallido";
  procedencia: { motor: string; metodo: string | null; firma: string | null; mensaje?: string; pasos?: number; rechazos?: number; compilation?: import('../modelo/compilation').CompilationReport;
    steadyDiagnostics?:import('../modelo/steadyContract').SteadyDiagnostics;
    daeDiagnostics?:{version:1;method:'scipy_bdf_nested_newton';acceptedChecks:number;maxResidual:number;maxConservation:number;driftTolerance:number;scope:string};
    nonlinearDiagnostics?:{version:1;method:'damped_newton';sourceSignature:string;settings:NonNullable<import('../modelo/derivedExecution').DerivedExecution['nonlinear']>;evaluatedSolves:number;lastEvaluation:Record<string,unknown>;failures:Record<string,unknown>[];publishedSamples:number;scope:string};
    assessment?: import('../modelo/assessment').ModelAssessment;
    physicalCertification?: import('../../app/motor/contratoEnsamblajeV2').CertificacionV2 | null;
    equilibrium?: NonNullable<import('../../app/motor/contratoEnsamblajeV2').RespuestaResolucionV2['resultados']>;
    diagnostics?: {codigo:string; estado:string; mensaje:string; variableIds:string[]; origen:{propietarioId:string; ruta:string}}[] };
  ejes: Eje[]; series: Serie[]; eventos: Evento[];
  verificaciones: { id: string; valor: number; tolerancia: number; descripcion: string }[];
};
