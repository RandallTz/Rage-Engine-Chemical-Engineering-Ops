// Catalogo del motor (F2.1-F2.3, revision 1): GET /motor/catalogo. Sin efectos; no recibe parametros.
// Documento: docs/MOTOR_CATALOGO_PROPIEDADES.md. Ejemplos: docs/ejemplos/motor-catalogo/
// (tests/generar_ejemplos_motor_catalogo.py; verificador tests/verificar_contrato_catalogo.mjs).
//
// Semantica:
// - `sustancias` es el registro unico del servidor: identidad (CAS) y datos puros con su procedencia. El cliente
//   no mantiene otra lista quimica; un componente simbolico (sin identidadQuimica) sigue siendo valido en los
//   balances que no necesitan propiedades.
// - Estar registrada NO implica estar admitida en todos los paquetes: `paquetes[].especies[]` dice, por especie,
//   si el paquete la admite y que le falta. La regla es la misma para la especie pura y para las mezclas.
// - Los requisitos por par (NRTL) o por grupo (interacciones UNIFAC) dependen del conjunto: no se enumeran por
//   combinacion; se diagnostican al evaluar con su codigo (PARAMETRO_AUSENTE, UNIFAC_INTERACCION_AUSENTE).
// - Tamanos admitidos/contrastados, dominios de estado y evidencia siguen en las capacidades de cada ruta.

import type {ModeloEstado} from './contratoTermodinamica';

export const REVISION_CATALOGO = 1;

/** Dato requerido por especie. Los de UNIFAC llevan la variante: asignacion_grupos_original|dortmund|lle. */
export type DatoRequerido = 'registro' | 'masa_molar' | 'presion_vapor' | 'cp_gas_ideal' | 'volumen_liquido' |
  'parametros_nrtl_lle' | 'formulacion_iapws95' | `asignacion_grupos_${string}`;

/** Sufijo del diagnostico (prefijo MOTOR_ESTADO_, MOTOR_ENS_ o MOTOR_DIAG_ segun la ruta). */
export type CodigoAdmision = 'COMPONENTE_NO_SOPORTADO' | 'DATO_PURO_AUSENTE' | 'PARAMETRO_AUSENTE' |
  'UNIFAC_ASIGNACION_AUSENTE' | 'UNIFAC_GRUPO_DESCONOCIDO';

export type PropiedadPura =
  | {id: 'presion_vapor'; unidad: 'Pa'; forma: string; fuente: string;
     coeficientes: {A: number; B: number; C: number; D: number; Tc: number; Pc: number}; dominio: {T: [number, number]}}
  | {id: 'cp_gas_ideal'; unidad: 'J/(mol K)'; forma: string; fuente: string;
     coeficientes: {a0: number; a1: number; a2: number; a3: number; a4: number}; dominio: {T: [number, number]}}
  | {id: 'volumen_liquido'; unidad: 'm3/mol'; valor: number; condicion: string; fuente: string};

export type SustanciaCatalogo = {
  /** Identidad estable: el CAS. */
  id: string; cas: string; nombre: string;
  masaMolar: {valor: number; unidad: 'kg/mol'; fuente: string};
  datosPuros: {
    estado: 'completos' | 'incompletos';
    faltantes: {dato: DatoRequerido; motivo: string}[];
    /** Solo con estado 'completos'. Son los datos que entran en los paquetes de mezcla (no en IAPWS-95). */
    propiedades?: PropiedadPura[];
    /** T donde el liquido puro esta definido en los paquetes de mezcla [K]. */
    dominioLiquido?: {T: [number, number]; motivo: string};
    /** sha256 de los datos puros usados; forma parte de la huella de cada paquete de mezcla. */
    huella?: string};
};

export type FaltanteAdmision = {dato: DatoRequerido; codigo: CodigoAdmision; mensaje: string};

export type PaqueteCatalogo = {
  modelo: ModeloEstado; nombre: string;
  requisitos: {porEspecie: DatoRequerido[]; porPar: string[]; porGrupo: string[]};
  operaciones: {
    estado: {especificaciones: string[]};
    ensamblaje: {disponible: boolean; coberturaGrupos?: true};
    diagramas: {disponible: boolean; operaciones: ('Txy' | 'Pxy')[]}};
  /** Una entrada por sustancia del catalogo, en su orden. */
  especies: {cas: string; admitida: boolean; faltantes: FaltanteAdmision[]}[];
};

// ------------------------------------------------------------------------------------------------------------
// F2.4 · Sustitucion de datos puros (aditivo, sin revision nueva). Se acepta en:
//   - POST /motor/termodinamica/evaluar: `declaracion.datosPuros`
//   - POST /motor/ensamblajes/{validar,resolver} (revision 2): `paquetes[].datosPuros` (vale para las especies
//     que declare cada volumen con ese paquete)
//   - POST /motor/termodinamica/diagramas/trazar: `datosPuros`
// Solo paquetes de mezcla. Se sustituyen ENTRADAS del potencial de la especie; h, s, mu, densidad y cp del
// liquido se derivan de ellas (no se sustituyen sueltas). Cambiar un dato o su fuente cambia la huella del
// paquete (huellaModelo / procedenciaModelo[].huella): un resultado o cache con otra huella esta caducado.
// Rechazos: *_SUSTITUCION_NO_ADMITIDA (no_soportado: masa_molar, propiedades del estado, IAPWS-95) y
// *_SUSTITUCION_INVALIDA (invalido: sin fuente, unidad, dominio, cp <= 0, Psat no creciente o > Pc, especie
// ajena a la peticion). No se publica un eco de las sustituciones: la peticion es su registro y la huella su prueba.
/** {cas: {propiedad: dato}}; varias propiedades por especie se combinan en un mismo objeto. */
export type SustitucionDatosPuros = Record<string, {
  volumen_liquido?: {valor: number; unidad: 'm3/mol' | 'cm3/mol' | 'L/mol'; fuente: string};
  cp_gas_ideal?: {coeficientes: {a0: number; a1: number; a2: number; a3: number; a4: number};
    dominio: {T: [number, number]}; fuente: string};
  presion_vapor?: {forma: 'WagnerPoling' | 'WagnerMcGarry';
    coeficientes: {A: number; B: number; C: number; D: number; Tc: number; Pc: number};
    dominio: {T: [number, number]}; fuente: string}}>;

export type CodigoSustitucion = 'SUSTITUCION_NO_ADMITIDA' | 'SUSTITUCION_INVALIDA';

export type CatalogoMotor = {
  revision: 1;
  sustancias: SustanciaCatalogo[];
  paquetes: PaqueteCatalogo[];
  regla: string;
  noDisponible: {elemento: string; motivo: string}[];
};
