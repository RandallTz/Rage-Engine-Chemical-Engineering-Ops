// Metadata de contribucion de grupos (UNIFAC), especifica de esa familia de modelos: los paquetes que no son
// de contribucion de grupos NO publican este campo y no tienen que aportar grupos.
// Contrato: frontend/CONTRATO_CLAUDE_UNIFAC_MOTOR.md. Informe: docs/MOTOR_UNIFAC.md.
// Se publica (aditivo, sin revision nueva) como `coberturaGrupos` en:
//   - CapacidadesEnsamblajeV2.paquetes[]  (GET /motor/ensamblajes/capacidades, contratoEnsamblajeV2.ts)
//   - CapacidadesDiagramas.paquetes[]     (GET /motor/termodinamica/diagramas/capacidades)
// Ejemplos: docs/ejemplos/motor-unifac/.

/** original: Fredenslund 1975; dortmund: UNIFAC modificado (DOUFIP2016); lle: tabla de ELL de Magnussen 1981
 * con las asignaciones DDBST originales traducidas por nombre de subgrupo con R y Q identicos. */
export type VarianteUNIFAC = 'original' | 'dortmund' | 'lle';

/** Identidad de los datos fijados de la variante. Los sha256 son de los archivos TSV distribuidos con thermo;
 * cambian si cambia cualquier parametro, y con ellos la huella del modelo (`huellaModelo`). */
export type DatosContribucionGrupos = {
  variante: VarianteUNIFAC;
  fuente_interacciones: string; sha256_interacciones: string;
  fuente_asignaciones: string; sha256_asignaciones: string;
  fuente_subgrupos: string;
  /** Solo 'lle': cita de la tabla y su intervalo de T de ajuste [K], que es el dominio en T del paquete. */
  fuente_tabla?: string; rango_T_datos?: [number, number]};

export type SubgrupoAsignado = {
  /** Numero de subgrupo de la tabla de la variante (p. ej. 1 = CH3, 16 = H2O en la original). */
  id: number; nombre: string;
  /** Grupo principal: las interacciones son entre grupos principales; dentro de uno, a = 0 por definicion. */
  grupoPrincipal: number;
  /** Veces que aparece el subgrupo en la molecula (entero >= 1). */
  cuenta: number};

export type CoberturaGrupos = {
  tipo: 'contribucion_de_grupos';
  variante: VarianteUNIFAC;
  datos: DatosContribucionGrupos;
  /** Especies del catalogo con asignacion, y de donde procede cada una. */
  especies: {cas: string; subgrupos: SubgrupoAsignado[]; procedencia: string}[];
  /** Especies del catalogo sin asignacion para esta variante: se rechazan con *_UNIFAC_ASIGNACION_AUSENTE. */
  especiesSinAsignacion: string[];
  /** Pares DIRIGIDOS [m, n] de grupos principales presentes en el catalogo sin parametro a_mn. Un subconjunto
   * que los necesite se rechaza con *_UNIFAC_INTERACCION_AUSENTE; nunca se rellenan con cero. */
  interaccionesDirigidasFaltantes: [number, number][];
  nota: string};

/** Sufijos de diagnostico de datos ausentes (prefijo MOTOR_ESTADO_, MOTOR_ENS_ o MOTOR_DIAG_ segun la ruta).
 * PARAMETRO_AUSENTE se conserva para pares NRTL. */
export type CodigoDatoAusente = 'PARAMETRO_AUSENTE' | 'UNIFAC_ASIGNACION_AUSENTE' | 'UNIFAC_GRUPO_DESCONOCIDO' |
  'UNIFAC_INTERACCION_AUSENTE';
