import type { Dimension, Documento, Escala, Expresion, Forma, Igualdad, PasoDesarrollo, Transformacion } from "./contrato";

export type OpcionesBusqueda = {
  presupuesto?: number; maxObjetivos?: number; desde?: number; gruposPi?: boolean;
  maxExponentePi?: number; maxDenominadorPi?: number; presentacion?: "factorizada" | "desarrollada";
  referencias?: { ecuacionId: string; terminoId: string }[]; prioridadEscalas?: string[];
};
export type SolicitudNucleo = {
  formato: "adimensionalizacion.solicitud"; version: 1;
  operacion: "analizar" | "transformar" | "adimensionalizar";
  documento: Documento; formaId?: string; transformaciones?: Transformacion[]; opciones?: OpcionesBusqueda;
};
export type DiagnosticoNucleo = { ruta: string; codigo: string; severidad: "error" | "aviso"; mensaje: string; simbolos?: string[] };
export type FormulacionNucleo = {
  id?: string;
  objetivosAplicados?: string[];
  simbolos: { id: string; nombre: string; rol: "escala" | "variable_adimensional"; variableId: string; dimension: Dimension; rolOrigen?: string; papel?: string; estado?: string; valor?: Expresion | null; dependeDe?: string[]; signo?: string }[];
  escalas: { simboloId: string; escalaId: string; papel: string; estado: string; valor: Expresion }[];
  libres: string[];
  normalizacion: { estado: "completa" | "parcial"; motivos: { codigo: string; [k: string]: unknown }[] };
  ecuaciones: { igualdad: Igualdad; factorGlobal: Expresion; terminos: { id: string; coeficiente: Expresion; original: Expresion; nucleo: Expresion; grupoId: string | null; dimensionNucleo: Dimension }[] }[];
  dominios: { id: string; variableId: string; desde: Expresion; hasta: Expresion }[];
  condiciones: { id: string; tipo: string; dominioId: string; ecuacion: Igualdad; ubicacion: string; factorGlobal?: Expresion; lugar?: { variableId: string; variableOriginal: string; extremo: "desde" | "hasta"; valor: Expresion; original: Expresion } }[];
  directa: { simboloId: string; expresion: Expresion }[];
  inversa: { simboloId: string; expresion: Expresion }[];
  transformaciones: { variableId: string; nuevoId: string; familia: string; directa: Expresion; inversa: Expresion; dominio: Transformacion["dominio"]; constantes: string[] }[];
  funcionesAdimensionales?: { id: string; nombre: string; funcionId: string; escalaId: string; entradas: Dimension[]; salida: Dimension; dependeDe: string[]; argumentos: { escala: Expresion; extraida: boolean }[]; definicion: string }[];
  grupos: { id: string; definicion: Expresion; dimension: Dimension; adimensional: boolean; contieneEscalasLibres: boolean; usos: string[]; interno: boolean; inversoDe: string | null }[];
  objetivos: { id: string; terminoId?: string; estado: "satisfecho" | "dependiente" | "incompatible" | "pendiente" | "conservado"; motivo: string; responsables?: string[]; valorObjetivo?: number; coeficienteFinal?: Expresion; relacion?: { izquierda: Expresion; derecha: Expresion }; comprobado?: boolean }[];
  restricciones: { id: string; tipo: "positivo" | "negativo" | "no_nulo" | "signo" | "igualdad"; expresion: Expresion; motivo: string; signo?: string; valor?: Expresion }[];
  pasos: { ambito: string; regla: string; antes: Omit<Igualdad, "id">; despues: Omit<Igualdad, "id">; supuestos: string[] }[];
  desarrollo: PasoDesarrollo[];
  desarrolloEstado: { estado: "completo"; nota: string };
  equivalencia: { estado: "demostrada" | "no_demostrada"; alcance: string; restricciones: string[]; comprobaciones: { ambito: string; tipo: string; estado: string }[] };
};
export type RespuestaNucleo = {
  formato: "adimensionalizacion.resultado"; version: 1;
  operacion: string; estado: "correcto" | "rechazado" | "no_soportado" | "requiere_datos";
  nucleo: string; diagnosticos: DiagnosticoNucleo[];
  vinculo: null | { documentoId: string; modeloId: string; modeloRevision: number; formaId?: string | null; eleccion?: { escalas: Escala[]; objetivos: Forma["objetivos"]; presentacion: string; transformaciones?: Transformacion[]; referencias?: { ecuacionId: string; terminoId: string }[]; prioridadEscalas?: string[] }; firma: string; opciones?: Record<string, unknown> };
  dimensional?: { estado: "compatible" | "incompatible" | "indeterminado"; faltantes: string[]; simbolos: { id: string; dimension: Dimension; origen: string }[]; funciones: unknown[] };
  formaBase?: Forma;
  formulaciones?: FormulacionNucleo[];
  cobertura?: { familia?: string; completa?: boolean; agotado?: string | null; siguiente?: number | null; desde?: number; evaluados?: number; formulacionesDistintas: number; nota?: string; excluidos?: { terminoId: string; motivo: string }[]; [k: string]: unknown };
  gruposPi?: { rango: number; numeroGrupos: number; cantidades: string[]; bases: { id: string; grupos: { id: string; definicion: Expresion }[] }[]; cobertura: Record<string, unknown> };
};
