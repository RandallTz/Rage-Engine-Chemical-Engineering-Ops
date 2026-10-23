// BORRADOR (diseño C4), NO PUBLICADO: frontera abierta con caudal calculado y paquete agua + gases no
// condensables. Documento: docs/engine/open-boundary-water-air-design.md. El servicio actual rechaza estos
// campos (MOTOR_ENS_CAMPO_NO_ADMITIDO); se publicarán, si se aprueban, como revisión explícita o como
// campos opcionales de la revisión 2 anunciados en capacidades, nunca como migración silenciosa.
// Compila contra la revisión 2 (tests/verificar_contrato_ensamblaje_v2.mjs lo comprueba).
import type {CorrienteV2, SolicitudEnsamblajeV2, VolumenV2} from './contratoEnsamblajeV2';

/** Inicial por presión: las cantidades de `calculadas` (p. ej. N2 y O2) son RESULTADO de la
 * inicialización con T0, P0 y el volumen geométrico; las de `datoIds` siguen siendo datos (agua total).
 * `proporcion` fija solo las relaciones entre las calculadas (aire seco 79/21). No se combina con
 * cantidades dadas de las mismas especies: eso sobredetermina y se diagnostica. */
export type InicialPorPresionV2 = {
  tipo: 'por_presion';
  temperaturaId: string;
  presionId: string;
  cantidades: {base: 'masica'|'molar'; datoIds: Record<string, string>};
  calculadas: {componenteIds: number[]; proporcion: {base: 'molar'|'masica'; fracciones: Record<string, number>}};
};

/** Volumen rígido con restricción mecánica P = P_ambiente que se cumple mediante el caudal de una
 * corriente cuyo modo es `por_restriccion`. */
export type VolumenRestriccionPresionV2 = Omit<VolumenV2, 'frontera'|'inicial'> & {
  frontera: {tipo: 'rigida_con_presion'; datoId: string; presionId: string};
  inicial: VolumenV2['inicial'] | InicialPorPresionV2;
};

/** Caudal incógnita: lo fija la restricción mecánica del volumen `volumenId` (una corriente por
 * restricción). La fase extraída debe declararse (gas). La entrada, si el signo se invierte, usa
 * `estadoExterior`; sin él, la inversión detiene la trayectoria con diagnóstico. */
export type MateriaPorRestriccionV2 = {modo: 'por_restriccion'; volumenId: string; base: 'molar'|'masica'};
export type CorrienteRestriccionV2 = Omit<CorrienteV2, 'materia'> & {materia: MateriaPorRestriccionV2};

export type SolicitudFronteraAbiertaBorrador = Omit<SolicitudEnsamblajeV2, 'volumenes'|'corrientes'> & {
  volumenes: (VolumenV2 | VolumenRestriccionPresionV2)[];
  corrientes: (CorrienteV2 | CorrienteRestriccionV2)[];
};

/** Resultados adicionales propuestos: el caudal calculado como serie algebraica y el residuo de la
 * restricción (ecuacionId `mecanica.<v>.presion`), más los cambios de régimen como eventos
 * (`inversion_flujo`, `entrada_sin_estado_exterior`, `limite_equipo`). */
export type ResiduoRestriccionPresion = {ecuacionId: `mecanica.${string}.presion`; maximoEscalado: number;
  tolerancia: number; definicion: string};
