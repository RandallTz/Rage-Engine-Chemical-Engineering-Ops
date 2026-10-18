// Protocolo de diagramas de equilibrio del motor (revision 1, independiente del ensamblaje).
// Plan: frontend/PLAN_DIAGRAMAS_EQUILIBRIO_MOTOR.md. Documento: docs/MOTOR_DIAGRAMAS_EQUILIBRIO.md.
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
  diagnosticos: DiagnosticoDiagrama[]};

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
