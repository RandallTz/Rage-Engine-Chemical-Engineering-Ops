// Revision 2 del protocolo de ensamblaje del motor independiente (aditiva y discriminada).
// Rutas: las mismas de la revision 1 (/motor/ensamblajes/{capacidades,validar,resolver});
// el backend despacha por `revision`. La revision 1 sigue igual y funcional.
// Documento: docs/MOTOR_EQUILIBRIO_MULTIFASICO.md. Ejemplos compilados contra este archivo:
// docs/ejemplos/motor-v2/motor-ensamblaje-v2-*.json (tests/verificar_contrato_ensamblaje_v2.mjs).
import type {Componente} from './materiaEstado';
import type {ModeloEstado, PoliticaEstado, EvaluacionEstado, FaseEstado} from './contratoTermodinamica';
import type {FormulacionMateria} from './recorridoMateria';
import type {FormulacionEnergia} from './recorridoEnergia';
import type {MagnitudMotor} from './unidadesMotor';
import type {DiagnosticoPreparacion, RecuentoDinamico, FronteraDinamica, PresionExteriorDinamica,
  OrigenDato} from './contratoEnsamblajeTermodinamico';
import type {CoberturaGrupos} from './contratoContribucionGrupos';
import type {SustitucionDatosPuros} from './contratoCatalogo';

/** Magnitudes nuevas de la revision 2: cantidad (mol, kmol) y conductancia (W/K, kW/K). */
export type MagnitudV2 = MagnitudMotor | 'cantidad' | 'conductancia';
export type DatoV2 = {magnitud: MagnitudV2; funcion: 'inicial'|'frontera'|'geometria'|'estudio'|'parametro';
  declaracion: {texto: string; unidad: string}; origen: OrigenDato};

/** Paquete configurado por ID local; varios volumenes pueden compartirlo. */
/** datosPuros (F2.4, aditivo): sustitucion de entradas del potencial, ver contratoCatalogo.ts. */
export type PaqueteV2 = {id: string; modelo: ModeloEstado; datosPuros?: SustitucionDatosPuros};

/** Extraccion desde un volumen donante. Con dos liquidos presentes, `fase:'liquido'` es ambiguo:
 * se exige `criterio` (fisico, no un indice de solucion numerica). */
export type ExtraccionV2 =
  | {tipo: 'mezcla_homogenea'}
  | {tipo: 'fase'; fase: Exclude<FaseEstado, 'solido'>; criterio?: 'mayor_densidad'|'menor_densidad'};

/** Materia de una corriente. `total_desde_donante`: caudal total; la composicion la fija el donante
 * en cada instante (volumen o estado exterior). Caudales por componente desde un volumen de varias
 * especies sobreespecifican la composicion y se rechazan. */
export type MateriaV2 =
  | {modo: 'por_componente'; base: 'masica'|'molar'; caudalIds: Record<string, string>}
  | {modo: 'total_desde_donante'; base: 'masica'|'molar'; caudalId: string};

export type EstadoExteriorV2 = {tipo: 'TP'; temperaturaId: string; presion: PresionExteriorDinamica;
  /** Composicion del donante exterior; obligatoria con mas de un componente si puede entrar materia. */
  composicion?: {base: 'masica'|'molar'; fracciones: Record<string, number>}};

/** Corriente: UN id y UNA transferencia por componente y energia, con signos opuestos en sus extremos.
 * Caudal positivo en el sentido desde -> hasta; el donante sale del signo actual. */
export type CorrienteV2 = {id: string; desde: string|null; hasta: string|null; componenteIds: number[];
  mecanismo: 'convectivo'|'selectivo'|null; materia: MateriaV2; estadoExterior?: EstadoExteriorV2;
  /** Por volumen donante (clave = id del volumen extremo). */
  extraccion?: Record<string, ExtraccionV2>};

/** Calor de desde -> hasta (positivo). Un extremo null es el exterior.
 * impuesto: Q(t) dato. conductancia: Q = G (T_desde - T_hasta), con la T exterior como dato si un extremo es null.
 * temperaturaFronteraId: T de la frontera exterior para la segunda ley; sin ella esa verificacion es no evaluable. */
export type IntercambioTermicoV2 = {id: string; desde: string|null; hasta: string|null;
  ley: {tipo: 'impuesto'; potenciaId: string} | {tipo: 'conductancia'; conductanciaId: string; temperaturaExteriorId?: string};
  temperaturaFronteraId?: string};

export type VolumenV2 = {id: string; componenteIds: number[];
  balances: {materia: boolean; energia: boolean; momento: boolean};
  formulacionMateria: Omit<FormulacionMateria, 'componentes'|'fronteras'>; formulacionEnergia: FormulacionEnergia;
  paqueteId: string; politica: PoliticaEstado; frontera: FronteraDinamica;
  inicial: {cantidades: {base: 'masica'|'molar'; datoIds: Record<string, string>}; energia: {tipo: 'U'|'T'; datoId: string}}};

export type SolicitudEnsamblajeV2 = {revision: 2; solicitudId: string; componentes: Componente[]; paquetes: PaqueteV2[];
  volumenes: VolumenV2[]; corrientes: CorrienteV2[]; intercambiosTermicos: IntercambioTermicoV2[];
  datos: Record<string, DatoV2>;
  estudio: {tipo: 'temporal'; tiempoId: string; metodoSolicitado: string|null; muestras: number; rtol: number;
    atol: {cantidad: number; energia: number}};
  derivacion?: unknown};

// ---------------------------------------------------------------- respuestas
export type VariableV2 = {id: string; propietarioId: string; componenteId?: number; faseId?: string; magnitud: string;
  unidadSI: string; papel: 'diferencial'|'algebraica'|'dato'|'parametro'; datoId?: string};
export type EcuacionV2 = {id: string; propietarioId: string;
  familia: 'materia'|'energia'|'estado'|'equilibrio'|'mecanica'|'transferencia'|'verificacion';
  variableIds: string[]; incognitas: string[]; dimension: string; latex: string; unidadResiduo: string;
  procedencia: {tipo: 'balance'|'transferencia'|'constitutiva'|'restriccion'|'verificacion'; paquete?: ModeloEstado;
    relacion: string; transferenciaId?: string}};

/** Evidencia de potenciales de un estado: base molar, J/mol; estado estandar de cada especie: gas ideal
 * puro a T y P0 = 1e5 Pa con la referencia del paquete. mu de una especie ausente de una fase no se publica. */
/** ERRATUM (consolidacion): `base` y `unidad` se refieren SOLO a mu (molar, J/mol). G, A y S han sido
 * siempre totales extensivos del volumen (J, J, J/K); `unidades` (aditivo) lo declara explicitamente. */
export type PotencialesV2 = {base: 'molar'; unidad: 'J/mol';
  unidades?: {mu: 'J/mol'; G: 'J'; A: 'J'; S: 'J/K'}; referencia: {id: string; descripcion: string};
  estadoEstandar: string; T: number; P: number; G: number; A: number; S: number;
  fases: {faseId: string; mu: Record<string, number|null>}[];
  residuoIgualdadMu: number|null; candidatasExploradas: FaseEstado[]; tmMinimo: number|null; metodo: string};

export type EstadoVolumenV2 = {volumenId: string; evaluacion: EvaluacionEstado; potenciales: PotencialesV2};

export type InicializacionV2 = {estado: 'pendiente'|'compatible'|'incompatible'|'no_soportada';
  volumenes: Record<string, {estado: 'pendiente'|'compatible'|'incompatible'|'no_soportada';
    variables: Record<string, number>; estadoTermodinamico: EstadoVolumenV2|null}>};

export type RespuestaValidacionV2 = {revision: 2; solicitudId: string; modeloId: string|null; recuento: RecuentoDinamico;
  variables: VariableV2[]; ecuaciones: EcuacionV2[]; diagnosticos: DiagnosticoPreparacion[];
  inicializacion: InicializacionV2};

export type ResiduoV2 = {ecuacionId: string; maximoEscalado: number; tolerancia: number; definicion: string};
export type SegundaLeyV2 = {estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string;
  generacionMinima: number|null; tolerancia: number|null; unidad: 'J/K'};

export type RespuestaResolucionV2 = {revision: 2; validacion: RespuestaValidacionV2;
  estado: 'resuelto'|'parcial'|'invalido'|'no_convergente'|'no_soportado';
  resultados: null | {metodo: string; tiempos: number[]; series: {variableId: string; unidadSI: string; valores: number[]}[];
    estados: Record<string, EstadoVolumenV2[]>;
    eventos: EventoV2[];
    residuos: ResiduoV2[]; segundaLey: SegundaLeyV2;
    /** Aditivo (consolidacion C2): metadatos de cada serie publicada. No suma ecuaciones ni grados de libertad. */
    catalogoSeries?: SerieCatalogoV2[];
    /** Aditivo (consolidacion C1): certificacion fisica, separada del resultado numerico `estado`. */
    certificacion?: CertificacionV2;
    /** Aditivo (diagramas de equilibrio): huella de datos y parametros del paquete que produjo los estados.
     * Un diagrama (docs/contratos/contratoDiagramasEquilibrio.ts) solo se compara si su huella coincide. */
    procedenciaModelo?: {volumenIds: string[]; modelo: ModeloEstado; componentesCAS: string[]; huella: string}[]}};

/** Codigos de evento: aparicion_fase, desaparicion_fase, sustitucion_fase (mismo numero de fases, una
 * desaparece y otra aparece), cambio_denominacion (solo vapor/liquido <-> fluido supercritico: continuo, no
 * es transicion de primer orden) y codigos de detencion (agotamiento, salida_dominio, fase_ambigua...). */
export type EventoV2 = {codigo: string; tiempo: number; volumenId: string|null;
  /** Fases que aparecen o desaparecen (diferencia simetrica de los IDs antes/despues); [] si el evento no es de fase. */
  faseIds: string[]; variableIds: string[];
  /** Aditivos (C2): IDs presentes en la muestra anterior y en la del evento; ausentes en eventos sin volumen. */
  faseIdsAntes?: string[]; faseIdsDespues?: string[];
  descripcion?: string};

/** papel: como se obtiene el valor de la serie (no su papel en el recuento, que esta en validacion.variables):
 * estado_integrado (estado diferencial), algebraica (cierre o relacion), dato, integral_auxiliar (cuadratura
 * acumulada, no estado fisico), derivada (presentacion: masa, S, S_gen; sin ecuacion propia). */
export type SerieCatalogoV2 = {variableId: string; propietarioId: string; unidadSI: string; magnitud: string;
  papel: 'estado_integrado'|'algebraica'|'dato'|'integral_auxiliar'|'derivada';
  /** ID en validacion.variables cuando la serie es una variable del ensamblaje; null si es de presentacion. */
  variableEnsamblajeId: string|null; procedencia: string};

export type AspectoCertificacionV2 = {id: 'estados_termodinamicos'|'conservacion'|'cierre_constitutivo'|'segunda_ley';
  estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string;
  /** ecuacionId de residuos, 'segundaLey', 'red.Sgen' o 'estados'. */
  referencias: string[];
  /** Indice en `tiempos` de la primera muestra que incumple este aspecto; null si ninguna. */
  primeraMuestraNoCumple: number|null};

/** Global: no_cumple si algun aspecto no cumple; si no, no_evaluable si alguno no es evaluable (p. ej.
 * segunda ley sin temperatura de frontera); si no, cumple. La trayectoria no se recorta: toda la evidencia se
 * conserva y `ultimaMuestraCertificada` marca hasta donde no hay incumplimientos comprobados. */
export type CertificacionV2 = {estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string;
  aspectos: AspectoCertificacionV2[];
  alcance: {tInicial: number; tFinal: number; muestras: number; completa: boolean};
  ultimaMuestraCertificada: number|null};

/** contrastada: comparada con datos/referencias primarias; cualitativa: resuelta y certificada por el
 * algoritmo, parametros no ajustados a ese equilibrio; imposible_en_el_modelo; sin_modelo; excluida. */
export type EvidenciaV2 = 'contrastada'|'cualitativa'|'imposible_en_el_modelo'|'sin_modelo'|'excluida';
export type CombinacionV2 = {nombre: string; publicada: boolean; motivo: string;
  /** Aditivos (C0): id estable (una_fase, liquido_vapor, liquido_liquido, solido, region_critica,
   * liquido_rigido_lleno) y nivel de evidencia. */
  id?: string; evidencia?: EvidenciaV2};

export type CapacidadesEnsamblajeV2 = {revision: 2; revisionesAdmitidas: (1|2)[];
  /** false si la formulacion del agua no supera su auditoria (entonces no se resuelve nada). */
  disponible: boolean;
  /** Por que no esta disponible (null si lo esta). */
  motivo: string|null;
  paquetes: {modelo: ModeloEstado; operaciones: ('TP'|'PH'|'UP'|'UV'|'TV')[]; fases: FaseEstado[];
    combinaciones: CombinacionV2[]; dinamica: boolean;
    /** Aditivos (C0): especies, dominio, limites y pares binarios con su evidencia. */
    componentesCAS?: string[]; dominio?: {T: [number, number]; P: [number, number]}; limites?: string[];
    pares?: {componentesCAS: [string, string]; procedencia: string; evidencia: EvidenciaV2; motivo: string}[];
    /** Aditivo (UNIFAC): solo en paquetes de contribucion de grupos, que no publican `pares`. */
    coberturaGrupos?: CoberturaGrupos}[];
  volumenesMaximos: number;
  /** Componentes DECLARADOS por volumen admitidos (7 desde la ampliacion N; antes 3). Ver `tamanos`. */
  componentesMaximos: number;
  /** Aditivo (ampliacion N): tamanos admitidos frente a contrastados por paquete, fases maximas, metodo de
   * estabilidad por dimension y presupuesto. */
  tamanos?: {cuenta: string; componentesMaximosPorVolumen: number; fasesMaximas: number;
    contrastados: Record<string, {estatico: number[]; dinamico: number[]}>;
    estabilidad: Record<string, string>; presupuesto: string};
  fronteras: ('rigida'|'presion_prescrita')[];
  corrientes: {mecanismos: 'convectivo'[]; materia: MateriaV2['modo'][]; internas: boolean; inversion: boolean;
    /** Aditivo (F2.5): una corriente puede unir volumenes con paquetes distintos solo si comparten referencia
     * (`referencia.id` del paquete; todos los de mezcla). Si no: MOTOR_ENS_REFERENCIAS_INCOMPATIBLES. */
    entrePaquetes?: 'misma_referencia'};
  intercambiosTermicos: ('impuesto'|'conductancia')[]; extracciones: ('mezcla_homogenea'|'fase')[];
  segundaLey: boolean; integradores: {id: 'rk45'; nombre: string}[]; muestrasMaximas: number;
  noSoportado: {elemento: string; motivo: string}[]};
