// Protocolo de diagramas de equilibrio del motor (revision 1, independiente del ensamblaje).
// Plan: docs/history/frontend/plan-diagrams-equilibrium-engine.md. Documento: docs/engine/equilibrium-diagrams.md.
// Rutas: GET /motor/termodinamica/diagramas/capacidades, POST /motor/termodinamica/diagramas/trazar.
// La ruta existente GET /motor/termodinamica/diagrama (P-T del agua con hielo) no cambia.
// Ejemplos compilados contra este archivo: docs/ejemplos/motor-diagramas/ (tests/verificar_contrato_diagramas.mjs).
import type {Componente} from './materiaEstado';
import type {CantidadEstado, ModeloEstado} from './contratoTermodinamica';
import type {CoberturaGrupos} from './contratoContribucionGrupos';
import type {SustitucionDatosPuros} from './contratoCatalogo';

export const REVISION_DIAGRAMAS = 1;

/** Un corte por peticion. La ausencia de T o P no significa cero. */
export type CorteEquilibrio =
  | {tipo: 'Txy'; P: CantidadEstado}
  | {tipo: 'Pxy'; T: CantidadEstado};

export type PerfilResolucion = 'exploratoria' | 'refinada';

export type SolicitudDiagrama = {
  revision: 1;
  solicitudId: string;
  /** Exactamente dos, con identidad quimica verificable (CAS). */
  componentes: Componente[];
  /** Misma identidad que el paquete del volumen consultado. Nunca se sustituye por otro. */
  modelo: ModeloEstado;
  /** Precondicion opcional: si no coincide con la huella actual del backend, la consulta se rechaza. */
  huellaModeloEsperada?: string;
  /** F2.4 (aditivo): sustitucion de entradas del potencial (contratoCatalogo.ts); entra en la huella. */
  datosPuros?: SustitucionDatosPuros;
  /** ID del componente cuya fraccion molar va en el eje. */
  componenteEjeId: number;
  corte: CorteEquilibrio;
  /** Fraccion molar del componente del eje, incluida en [0, 1], ordenada. */
  intervaloComposicion: [number, number];
  resolucion: PerfilResolucion;
};

export type EstadoDiagrama = 'completo' | 'parcial' | 'incompleto' | 'invalido' | 'no_soportado' | 'no_convergente';

/** Fase limite de coexistencia: composicion bien definida, cantidad tendiendo a cero (o indeterminada).
 * NO es una FaseEvaluada de un EvaluacionEstado: no lleva fracciones de fase. */
export type FaseLimite = {id: 'liquido-limite' | 'vapor-limite'; tipo: 'liquido' | 'vapor';
  composicionMolar: Record<string, number>};

export type ResiduoPunto = {id: 'igualdad_mu' | 'normalizacion' | 'condicion_fija' | 'distincion_fases';
  valor: number; tolerancia: number; escala: string; estado: 'cumple' | 'no_cumple'};

export type EstabilidadPunto = {estado: 'estable' | 'inestable' | 'no_evaluable';
  /** min tm (adimensional, por R T) sobre las fases de prueba exploradas con la mu comun. */
  tmMinimo: number | null; tolerancia: number;
  candidatas: ('liquido' | 'vapor')[]; pruebas: number; metodo: string;
  /** Fase de prueba que baja el plano tangente (si inestable): tipo y composicion molar. */
  competidora?: {tipo: 'liquido' | 'vapor'; composicionMolar: Record<string, number>; tm: number}};

export type CertificadoPunto = {estado: 'cumple' | 'no_cumple'; residuos: ResiduoPunto[]; estabilidad: EstabilidadPunto};

export type PuntoCoexistencia = {id: string; T: number; P: number;
  /** Variable de continuacion: fraccion molar del componente del eje en el liquido. */
  xEje: number; fases: [FaseLimite, FaseLimite]; certificado: CertificadoPunto;
  origen: 'extremo_puro' | 'continuacion' | 'refinamiento' | 'semilla_por_flash' | 'singular'};

/** Segmento: puntos certificados consecutivos; una linea entre ellos es interpolacion visual. Ningun segmento
 * cruza un hueco. */
export type SegmentoRama = {id: string; puntoIds: string[]; xEje: [number, number]};
export type RamaDiagrama = {id: string; tipo: 'LV'; segmentos: SegmentoRama[]};

export type PuntoEspecial = {id: string;
  tipo: 'extremo_puro' | 'azeotropo' | 'limite_dominio' | 'encuentro_otra_fase';
  T: number; P: number; xEje: number;
  /** extremo_puro: componente puro; azeotropo: x = y refinado; encuentro_otra_fase: limite LV con la fase
   * competidora identificada (p. ej. tres fases L-L-V). */
  descripcion: string; puntoId?: string;
  composiciones?: Record<string, Record<string, number>>;
  residuos?: ResiduoPunto[]; estabilidad?: EstabilidadPunto;
  /** azeotropo: 'maximo' o 'minimo' de T (Txy) o de P (Pxy), o 'tangente' si |x-y| tiene un minimo sin cruce. */
  clase?: string};

export type IncidenciaDiagrama = {id: string;
  tipo: 'no_convergente' | 'fase_competidora' | 'fuera_de_dominio' | 'region_critica' | 'presupuesto' |
    'extremo_no_evaluable' | 'rama_ambigua';
  intervaloXEje: [number, number]; causa: string; accion: string; referencias: string[]};

export type HuecoCobertura = {intervaloXEje: [number, number];
  /** sin_lv_estable: se exploro y otra fase es mas estable (no es un fallo numerico). */
  motivo: 'sin_lv_estable' | 'no_convergente' | 'fuera_de_dominio' | 'presupuesto' | 'no_explorado';
  incidenciaIds: string[]};

export type CoberturaDiagrama = {intervaloPedido: [number, number]; intervalosPublicados: [number, number][];
  huecos: HuecoCobertura[];
  finalizacion: 'recorrido_completo' | 'presupuesto' | 'sin_semilla';
  presupuesto: {evaluaciones: number; limiteEvaluaciones: number; segundos: number; limiteSegundos: number};
  /** Diferencia maxima entre los dos sentidos de recorrido en los puntos certificados por ambos. */
  reproducibilidad: {puntosComparados: number; maxDiferenciaCondicion: number | null;
    maxDiferenciaComposicion: number | null}};

export type RespuestaDiagrama = {revision: 1; solicitudId: string; estado: EstadoDiagrama;
  identidad: {modelo: ModeloEstado; huellaModelo: string | null; firmaConsulta: string | null;
    trazador: {id: string; version: string}};
  condicion: {corte: CorteEquilibrio; corteSI: {tipo: 'Txy'; P: number} | {tipo: 'Pxy'; T: number} | null;
    componentes: {id: number; cas: string}[]; componenteEjeId: number | null;
    intervaloComposicion: [number, number] | null; resolucion: PerfilResolucion | null} | null;
  ramas: RamaDiagrama[];
  puntos: PuntoCoexistencia[];
  puntosEspeciales: PuntoEspecial[];
  /** Candidatos que no superaron la certificacion (metastables, sin convergencia): solo diagnostico, nunca
   * se dibujan como equilibrio. */
  candidatosDescartados: {xEje: number; T: number | null; P: number | null; motivo: string; incidenciaId: string}[];
  incidencias: IncidenciaDiagrama[];
  cobertura: CoberturaDiagrama | null;
  metodo: string;
  /** pares: null en un paquete sin parametros binarios (mezcla ideal). */
  evidencia: {combinacion: string; nivel: string; motivo: string; pares: {componentesCAS: string[]; evidencia: string;
    procedencia: string}[] | null} | null;
  diagnosticos: DiagnosticoDiagrama[];
  /** F8 (aditivo en la revision 1): ramas L-L, punto critico L-L y punto L-L-V del corte. Ausente en respuestas
   * anteriores; un lector de la revision 1 puede ignorarlo. */
  liquidoLiquido?: LiquidoLiquidoDiagrama};

/** F8: fase liquida de un par L-L (dos liquidos coexistentes, cada uno con su composicion; sin fracciones de fase). */
export type FaseLiquidaLL = {id: 'liquido-a' | 'liquido-b'; tipo: 'liquido'; composicionMolar: Record<string, number>};

/** Par L-L certificado. Cada par es un estado: el intervalo de composicion pedido no lo recorta. */
export type PuntoLiquidoLiquido = {id: string; ramaId: string; T: number; P: number;
  /** Fraccion molar del componente del eje en liquido-a y liquido-b (liquido-a tiene la menor). */
  xEje: [number, number]; fases: [FaseLiquidaLL, FaseLiquidaLL]; certificado: CertificadoPunto;
  origen: 'semilla_por_flash' | 'continuacion'};

/** Rama L-L recorrida por pseudo-longitud de arco; puntoIds en orden creciente de la variable libre (T en Txy,
 * P en Pxy). Las lineas entre puntos consecutivos son interpolacion visual. */
export type RamaLiquidoLiquido = {id: string; tipo: 'LL'; variable: 'T' | 'P'; puntoIds: string[];
  intervalo: [number, number]};

export type ResiduoCriticidad = {id: 'criticidad'; valor: number; tolerancia: number; escala: string;
  estado: 'cumple' | 'no_cumple'};

export type PuntoEspecialLiquidoLiquido =
  | {id: string; ramaId: string; tipo: 'critico_ll'; T: number; P: number; xEje: number;
      composiciones: {'liquido-critico': Record<string, number>};
      certificado: {estado: 'cumple' | 'no_cumple'; residuos: ResiduoCriticidad[]; estabilidad: EstabilidadPunto};
      descripcion: string}
  | {id: string; ramaId: string; tipo: 'tres_fases'; T: number; P: number; xEje: [number, number];
      composiciones: {'liquido-a': Record<string, number>; 'liquido-b': Record<string, number>;
        vapor: Record<string, number>};
      certificado: CertificadoPunto; descripcion: string}
  | {id: string; ramaId: string; tipo: 'limite_dominio'; T: number | null; P: number | null; descripcion: string};

export type IncidenciaLiquidoLiquido = {id: string; ramaId: string | null;
  tipo: 'presupuesto' | 'no_convergente' | 'fase_competidora'; causa: string; accion: string};

export type LiquidoLiquidoDiagrama = {trazador: {id: string; version: string}; estado: 'completo' | 'parcial';
  ramas: RamaLiquidoLiquido[]; puntos: PuntoLiquidoLiquido[]; puntosEspeciales: PuntoEspecialLiquidoLiquido[];
  incidencias: IncidenciaLiquidoLiquido[];
  presupuesto: {evaluaciones: number; limiteEvaluaciones: number; segundos: number; limiteSegundos: number};
  evidencia: {combinacion: 'liquido_liquido'; nivel: string; motivo: string} | null;
  metodo: string};

/** Codigos estables: MOTOR_DIAG_REVISION, MOTOR_DIAG_DATO_INVALIDO, MOTOR_DIAG_UNIDAD, MOTOR_DIAG_PAQUETE_NO_DISPONIBLE,
 * MOTOR_DIAG_PARAMETRO_AUSENTE, MOTOR_DIAG_COMPONENTES_NO_SOPORTADO, MOTOR_DIAG_COMPONENTE_NO_SOPORTADO,
 * MOTOR_DIAG_FUERA_DE_DOMINIO, MOTOR_DIAG_NO_CONVERGENTE, MOTOR_DIAG_FASE_COMPETIDORA, MOTOR_DIAG_REGION_CRITICA,
 * MOTOR_DIAG_RAMA_AMBIGUA, MOTOR_DIAG_PRESUPUESTO, MOTOR_DIAG_HUELLA_DISTINTA. */
export type DiagnosticoDiagrama = {codigo: string; estado: 'invalido' | 'incompleto' | 'no_soportado' | 'aviso';
  ruta: string; mensaje: string; componenteIds: number[]};

/** saltoMaximoT [K] (Txy) y saltoMaximoLnP (Pxy): salto entre puntos consecutivos que dispara refinamiento.
 * Una evaluacion es un Newton de punto o un flash TP (una semilla por flash cuenta 45). */
export type PerfilPublicado = {id: PerfilResolucion; puntosBase: number; refinamientoMaximo: number;
  saltoMaximoT: number; saltoMaximoLnP: number; saltoMaximoComposicion: number; limiteEvaluaciones: number;
  limiteSegundos: number;
  toleranciaMu: number; toleranciaEstabilidad: number};

export type CapacidadesDiagramas = {revision: 1;
  trazador: {id: string; version: string};
  operaciones: ('Txy' | 'Pxy')[];
  componentes: 2;
  perfiles: PerfilPublicado[];
  paquetes: {modelo: ModeloEstado; operaciones: ('Txy' | 'Pxy')[]; fases: ('liquido' | 'vapor')[];
    componentesCAS: string[]; dominio: {T: [number, number]; P: [number, number]};
    /** Pares con datos y su evidencia; sin entrada: el par se rechaza con MOTOR_DIAG_PARAMETRO_AUSENTE.
     * null: paquete sin parametros binarios (ideal) o de contribucion de grupos (ver coberturaGrupos). */
    pares: {componentesCAS: string[]; evidencia: string; procedencia: string}[] | null;
    /** Aditivo (UNIFAC): solo en paquetes de contribucion de grupos. */
    coberturaGrupos?: CoberturaGrupos;
    combinacionesDetectadas: string[]; limites: string[]}[];
  noSoportado: {elemento: string; motivo: string}[]};

// --- Multicomponent diagrams (F8, additive; own protocol revision 1, 24 October 2026) -------------------------
// Routes: GET /motor/termodinamica/diagramas/multicomponent/capabilities,
// POST /motor/termodinamica/diagramas/ternary-liquid-liquid, POST /motor/termodinamica/diagramas/composition-line.
// Service: backend/multicomponent_diagrams.py. The binary types above are unchanged. Compositions are keyed by
// component ID (as text); every declared species is kept. Lines between published points are visual interpolation.

export const MULTICOMPONENT_DIAGRAM_REVISION = 1;

export type MulticomponentOperation = 'ternary_liquid_liquid' | 'composition_line';

/** Fixed condition of both operations. Absence of T or P does not mean zero. */
export type MulticomponentCondition = {T: CantidadEstado; P: CantidadEstado};

export type TernaryLiquidLiquidRequest = {
  revision: 1;
  requestId: string;
  /** Exactly three, with a verifiable chemical identity (CAS). */
  components: Componente[];
  /** The volume's package identity; it is never replaced by another. */
  model: ModeloEstado;
  /** Optional precondition: a different current fingerprint rejects the query (MOTOR_DIAG_HUELLA_DISTINTA). */
  expectedModelFingerprint?: string;
  pureData?: SustitucionDatosPuros;
  condition: MulticomponentCondition;
  resolution: PerfilResolucion;
};

/** Ends of the line z(l) = (1 - l) start + l end, l in [0, 1]: one mole fraction per declared component ID,
 * each end summing to 1. A component absent from both ends is rejected (MOTOR_DIAG_COMPONENTE_AUSENTE). */
export type CompositionLineRequest = Omit<TernaryLiquidLiquidRequest, 'components'> & {
  /** Two or more. */
  components: Componente[];
  line: {start: Record<string, number>; end: Record<string, number>};
};

export type MulticomponentStatus = 'complete' | 'partial' | 'no_coexistence' | 'invalid' | 'incomplete' | 'unsupported';

export type MulticomponentResidual = {id: 'mu_equality' | 'normalization' | 'fixed_condition' | 'distinct_phases';
  value: number; tolerance: number; scale: string; status: 'pass' | 'fail'};

export type MulticomponentStability = {status: 'stable' | 'unstable'; tmMinimum: number; tolerance: number;
  candidates: ('liquid' | 'vapor')[]; trials: number; method: string;
  competitor?: {kind: 'liquid' | 'vapor'; composition: Record<string, number>; tm: number}};

export type MulticomponentCertificate = {status: 'pass' | 'fail'; residuals: MulticomponentResidual[];
  stability: MulticomponentStability};

export type PublishedPhase = {id: 'liquid-a' | 'liquid-b' | 'vapor'; kind: 'liquid' | 'vapor';
  composition: Record<string, number>};

/** One tie line: two liquids with equal mu at (T, P), with its certificate. */
export type TieLine = {id: string; branchId: string; phases: [PublishedPhase, PublishedPhase];
  certificate: MulticomponentCertificate; origin: 'flash_seed' | 'continuation'};

/** A binodal branch: tie lines in continuation order. Its liquid-a and liquid-b compositions are the two sides of
 * the binodal; ends name the special point or incidence where each direction of the walk stopped. */
export type TernaryBranch = {id: string; tieLineIds: string[];
  ends: ({side: 'start' | 'end'; specialPointId: string} | {side: 'start' | 'end'; incidenceId: string})[]};

export type TernarySpecialPoint =
  | {id: string; branchId: string; side: 'start' | 'end'; kind: 'plait_point'; composition: Record<string, number>;
      certificate: {status: 'pass' | 'fail';
        residuals: {id: 'criticality'; value: number; tolerance: number; scale: string; status: 'pass' | 'fail'}[];
        stability: {status: 'stable' | 'unstable'; tmOtherPhase: number | null; tolerance: number; method: string}};
      description: string}
  | {id: string; branchId: string; side: 'start' | 'end'; kind: 'binary_edge'; absentComponentId: number;
      phases: [PublishedPhase, PublishedPhase]; certificate: MulticomponentCertificate; description: string}
  | {id: string; branchId: string; side: 'start' | 'end'; kind: 'three_phase';
      phases: [PublishedPhase, PublishedPhase, PublishedPhase]; certificate: MulticomponentCertificate;
      description: string};

export type MulticomponentIncidence = {id: string; branchId: string | null; side: 'start' | 'end' | null;
  kind: 'budget' | 'no_convergence' | 'competing_phase'; cause: string; action: string};

export type MulticomponentBudget = {evaluations: number; limitEvaluations: number; seconds: number;
  limitSeconds: number};

/** Stable codes: those of the binary protocol plus MOTOR_DIAG_COMPONENTE_AUSENTE (composition line). */
export type MulticomponentDiagnostic = {code: string; status: 'invalid' | 'incomplete' | 'unsupported' | 'aviso';
  path: string; message: string; componentIds: number[]};

export type MulticomponentIdentity = {model: ModeloEstado; modelFingerprint: string | null;
  /** Physical key: package, fingerprint, sorted CAS, T and P in SI, profile, tracer (and line ends by CAS). */
  querySignature: string | null; tracer: {id: string; version: string}};

export type MulticomponentResponseCondition = {input: MulticomponentCondition; T: number; P: number;
  components: {id: number; cas: string}[]; resolution: PerfilResolucion};

export type MulticomponentRejection = {revision: 1; requestId: string; status: 'invalid' | 'incomplete' | 'unsupported';
  identity: MulticomponentIdentity; condition: null; diagnostics: MulticomponentDiagnostic[]};

export type TernaryLiquidLiquidResponse =
  | (MulticomponentRejection & {operation: 'ternary_liquid_liquid'})
  | {revision: 1; requestId: string; operation: 'ternary_liquid_liquid';
      status: 'complete' | 'partial' | 'no_coexistence'; identity: MulticomponentIdentity;
      condition: MulticomponentResponseCondition; branches: TernaryBranch[]; tieLines: TieLine[];
      specialPoints: TernarySpecialPoint[]; incidences: MulticomponentIncidence[]; budget: MulticomponentBudget;
      evidence: {combination: 'liquido_liquido'; level: string; reason: string} | null; method: string;
      diagnostics: MulticomponentDiagnostic[]};

/** One closed feed on the line. Phases carry their mole fraction of the feed; they are sorted by kind and first
 * composition, so phase identity is not tracked between rows. */
export type LineRow = {id: string; l: number; feed: Record<string, number>;
  phases: {kind: 'liquid' | 'vapor'; fraction: number; composition: Record<string, number>}[];
  phaseSet: ('liquid' | 'vapor')[]; certified: boolean;
  checks: {id: string; residual: number; tolerance: number}[]; tmMinimum: number | null};

/** A change of phase set located by bisection inside lInterval; before/after are the closed states at its ends. */
export type LineBoundary = {id: string; lInterval: [number, number]; before: LineRow; after: LineRow};

export type CompositionLineResponse =
  | (MulticomponentRejection & {operation: 'composition_line'})
  | {revision: 1; requestId: string; operation: 'composition_line'; status: 'complete' | 'partial';
      identity: MulticomponentIdentity;
      condition: MulticomponentResponseCondition & {line: {start: Record<string, number>; end: Record<string, number>}};
      rows: LineRow[]; boundaries: LineBoundary[];
      failures: {l: number; reason: string; message: string}[]; completion: 'complete_walk' | 'budget';
      budget: MulticomponentBudget; method: string; diagnostics: MulticomponentDiagnostic[]};

export type MulticomponentCapabilities = {revision: 1;
  operations: {id: MulticomponentOperation; route: string; components: {min: number; max: number | null};
    tracer: {id: string; version: string}; publishes: string[]}[];
  profiles: {id: PerfilResolucion; limitEvaluations: number; limitSeconds: number; ternaryLattice: number;
    ternaryMaxStep: number; lineBasePoints: number; lineBisections: number; muTolerance: number;
    stabilityTolerance: number}[];
  packages: {model: ModeloEstado; componentsCAS: string[]; domain: {T: [number, number]; P: [number, number]}}[];
  unsupported: {element: string; reason: string}[]};
