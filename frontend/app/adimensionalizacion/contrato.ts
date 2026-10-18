/** Contrato de intercambio v1. No ejecuta álgebra ni valida dimensiones físicas.
 * El núcleo científico debe consumir este árbol, nunca el texto de presentación.
 */
export type Racional = { n: number; d: number };
export type Dimension = Record<string, Racional> | null;
export type Expresion =
  | { tipo: "numero"; valor: number }
  | { tipo: "simbolo"; id: string }
  | { tipo: "suma" | "producto"; argumentos: Expresion[] }
  | { tipo: "cociente"; numerador: Expresion; denominador: Expresion }
  | { tipo: "potencia"; base: Expresion; exponente: Expresion }
  | { tipo: "funcion"; nombre: "exp" | "log" | "sin" | "cos" | "tan" | "tanh" | "sinh" | "cosh" | "atan" | "erf" | "abs" | "min" | "max"; argumentos: Expresion[] }
  | { tipo: "llamada"; funcionId: string; argumentos: Expresion[] }
  | { tipo: "derivada"; expresion: Expresion; respecto: string; orden: number }
  | { tipo: "gradiente" | "divergencia" | "laplaciano"; expresion: Expresion; coordenadas: string[] };
export type Simbolo = {
  id: string; nombre: string;
  rol: "tiempo" | "coordenada" | "campo" | "parametro" | "constante";
  dimension: Dimension; unidad: string | null;
  constante: boolean; dependeDe: string[];
  signo: "positivo" | "negativo" | "cero" | "desconocido";
};
export type Igualdad = { id: string; izquierda: Expresion; derecha: Expresion };
export type Modelo = {
  id: string; revision: number; simbolos: Simbolo[];
  funciones: { id: string; nombre: string; entradas: Dimension[]; salida: Dimension; dependeDe: string[]; escala?: { simboloId: string; funcionAdimensional: string } }[];
  ecuaciones: Igualdad[];
  dominios: { id: string; variableId: string; desde: Expresion; hasta: Expresion }[];
  condiciones: { id: string; tipo: "inicial" | "dirichlet" | "flujo" | "mixta"; dominioId: string; ecuacion: Igualdad; ubicacion?: { variableId: string; extremo: "desde" | "hasta" } }[];
};
export type Escala = {
  simboloId: string; transformar: boolean; nuevoNombre: string;
  dimension: Dimension;
  valor: { tipo: "libre" } | { tipo: "cantidad"; valor: number; unidad: string }
    | { tipo: "expresion"; expresion: Expresion };
};
export type Forma = {
  id: string; nombre: string; padreId: string | null; modeloRevision: number;
  escalas: Escala[];
  objetivos: { id: string; ecuacionId: string; termino?: Expresion; terminoId?: string; valor: 1 | -1; accion: "normalizar" | "conservar_grupo" }[];
  presentacion: "factorizada" | "desarrollada";
  transformaciones?: Transformacion[];
  referencias?: { ecuacionId: string; terminoId: string }[];
  prioridadEscalas?: string[];
};
export type Transformacion = {
  variableId: string; nuevoId: string; directa: Expresion; inversa: Expresion;
  constantes: { id: string; nombre: string; papel: "escala" | "referencia"; dimension: Dimension; valor: Escala["valor"] }[];
  dominio: { original: "positivo" | "negativo" | null; nuevo: "positivo" | "negativo" | null };
};
export type Documento = {
  formato: "adimensionalizacion"; version: 1 | 2; id: string; nombre: string;
  modelo: Modelo; formas: Forma[]; activaId: string;
  exploracion?: ConfigExploracion;
};
/** Preferencias declarativas para el núcleo; no certifican ningún resultado. */
export type ConfigExploracion = {
  presupuesto: number;
  maxObjetivos: number;
  respetarEscalasFijadas: boolean;
  incluirGruposPi: boolean;
  maxExponentePi: number;
  maxDenominadorPi: number;
};
/** Cada línea de la derivación es un dato del núcleo, no una explicación
 * reconstruida en la UI a partir de la fórmula final. El orden es del cálculo. */
export type ExpresionDePaso =
  | { tipo: "expresion"; expresion: Expresion }
  | { tipo: "igualdad"; igualdad: Igualdad };
export type PasoDesarrollo = {
  id: string;
  operacion: "analisis_dimensional" | "cambio_variables" | "regla_cadena" | "sustitucion"
    | "factorizacion" | "normalizacion" | "agrupacion" | "simplificacion"
    | "geometria_condiciones" | "verificacion_inversa" | "hipotesis_fisica";
  regla: string; justificacion: string;
  antes: ExpresionDePaso; despues: ExpresionDePaso;
  supuestos: string[];
  objetosAfectados: string[];
};
export type { FormulacionNucleo as ResultadoNucleo } from "./contratoNucleo";
